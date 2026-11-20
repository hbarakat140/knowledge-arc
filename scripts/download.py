"""Download catalog items into a staging folder, check them, and (optionally)
write sha256 / size / date back into catalog/catalog.csv.

    python scripts/download.py --dest D:/staging --bundle core
    python scripts/download.py --dest D:/staging --ids T1-003 T2-036
    python scripts/download.py --dest D:/staging --bundle core --dry-run
    python scripts/download.py --dest D:/staging --bundle core --update-catalog

Three kinds of source, decided from source_url:
  *.meta4            Kiwix ZIM: fastest mirror first, resumable, sha-256 checked
  languages.hesperian.org + "(N files)"   Hesperian book: chapter PDFs scraped
                     from the page; fails if the count isn't N
  *.zip / *.tar.gz / *.apk   software (tier 9): zip or gzip signature, size_bytes,
                     and the publisher's .md5 file next to it when there is one
  anything else      one PDF: must start with %PDF- and match size_bytes if known

Pages that block scripts or are HTML landing pages are reported as MANUAL:
download them by hand to the path shown, then run again to hash them.

Standard library only. Safe to interrupt and run again: finished files are
remembered in <dest>/.download-state.json and skipped.
"""

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import catalog_lib as cl  # noqa: E402

USER_AGENT = "Mozilla/5.0 (compatible; offline-family-library-build/1.0)"
CHUNK = 1024 * 1024
TIMEOUT = 60
ML = "{urn:ietf:params:xml:ns:metalink}"


class Manual(Exception):
    """The item needs a person to download it in a browser."""


class Failed(Exception):
    """The item could not be fetched or failed a check."""


# --------------------------------------------------------------------- utils

def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(CHUNK), b""):
            h.update(block)
    return h.hexdigest()


def open_url(url, start=0, end=None, timeout=TIMEOUT):
    headers = {"User-Agent": USER_AGENT}
    if start or end is not None:
        headers["Range"] = f"bytes={start}-" + ("" if end is None else str(end))
    return urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=timeout)


def fetch_text(url):
    with open_url(url) as r:
        return r.read().decode("utf-8", errors="replace")


def human(n):
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or unit == "TB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024


class State:
    """Remembers files already downloaded and checked, keyed by path relative
    to dest, so a re-run doesn't re-hash 100+ GB."""

    def __init__(self, dest):
        self.path = dest / ".download-state.json"
        self.data = {}
        if self.path.exists():
            self.data = json.loads(self.path.read_text(encoding="utf-8"))

    def get(self, dest, target):
        rel = target.relative_to(dest).as_posix()
        entry = self.data.get(rel)
        if not entry or not target.exists():
            return None
        st = target.stat()
        if st.st_size != entry["size"] or st.st_mtime_ns != entry["mtime_ns"]:
            return None
        return entry

    def put(self, dest, target, sha):
        st = target.stat()
        self.data[target.relative_to(dest).as_posix()] = {
            "size": st.st_size, "mtime_ns": st.st_mtime_ns, "sha256": sha}
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.data, indent=1, sort_keys=True), encoding="utf-8")
        os.replace(tmp, self.path)


# ------------------------------------------------------------- downloading

def stream_to(url, part, start, total=None, label=""):
    """Append url (from byte `start`) to `part`. Returns bytes now in part."""
    with open_url(url, start) as r:
        if start and r.status != 206:
            start = 0  # server ignored Range: start over
        mode = "ab" if start else "wb"
        done, last = start, time.time()
        with open(part, mode) as f:
            for block in iter(lambda: r.read(CHUNK), b""):
                f.write(block)
                done += len(block)
                if total and time.time() - last > 15:
                    print(f"    {label} {human(done)} / {human(total)} ({100 * done / total:.0f}%)", flush=True)
                    last = time.time()
    return done


MAGIC = {".pdf": b"%PDF-", ".zip": b"PK\x03\x04", ".apk": b"PK\x03\x04", ".gz": b"\x1f\x8b"}
SOFTWARE = (".zip", ".tar.gz", ".apk")   # tier 9 files: signature + publisher .md5


def magic_for(target):
    return MAGIC.get(target.suffix.lower(), b"%PDF-")


def get_pdf(url, target, expected_size=None):
    """Download one file (a PDF unless target's suffix says otherwise) to
    target, checking its first bytes. Raises Manual or Failed."""
    magic = magic_for(target)
    part = target.with_name(target.name + ".part")
    target.parent.mkdir(parents=True, exist_ok=True)
    last_err, complete = None, False
    for attempt in range(3):
        try:
            with open_url(url) as r:
                ctype = r.headers.get("Content-Type", "")
                length = r.headers.get("Content-Length")
                head = r.read(len(magic))
                if head != magic:
                    raise Manual(f"not a {target.suffix} file (Content-Type {ctype or 'none'}): "
                                 f"open {url} in a browser and save it as {target}")
                with open(part, "wb") as f:
                    f.write(head)
                    for block in iter(lambda: r.read(CHUNK), b""):
                        f.write(block)
            if length and part.stat().st_size != int(length):
                raise ConnectionError(f"got {part.stat().st_size} of {length} bytes")
            complete = True
            break
        except urllib.error.HTTPError as e:
            if e.code in (401, 403, 429):
                raise Manual(f"HTTP {e.code} (site blocks scripts): open {url} in a browser "
                             f"and save the PDF as {target}")
            last_err = f"HTTP {e.code}"
            if e.code == 404:
                break
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            last_err = str(e)
        time.sleep(2 * (attempt + 1))
    if not complete:
        if part.exists():
            part.unlink()
        raise Failed(f"download failed: {last_err}")
    size = part.stat().st_size
    if expected_size and size != expected_size:
        bad = target.with_name(target.name + ".size-mismatch")
        os.replace(part, bad)
        raise Failed(f"size {size} differs from catalog size_bytes {expected_size} "
                     f"(error page or new edition?). Kept as {bad.name} for a look.")
    os.replace(part, target)
    return size


def parse_meta4(text):
    root = ET.fromstring(text)
    f = root.find(f"{ML}file")
    if f is None:
        raise Failed("meta4 has no <file>")
    sha = next((h.text.strip() for h in f.findall(f"{ML}hash") if h.get("type") == "sha-256"), None)
    urls = sorted(f.findall(f"{ML}url"), key=lambda u: int(u.get("priority", "999")))
    return {"name": f.get("name"), "size": int(f.find(f"{ML}size").text),
            "sha256": sha, "urls": [u.text.strip() for u in urls]}


PROBE_BYTES = 2 * 1024 * 1024   # sample read from each mirror
PROBE_SECONDS = 10              # a mirror slower than this is just ranked low
PROBE_ABOVE = 64 * 1024 * 1024  # only worth probing for big downloads


def fastest_first(urls):
    """Mirrors sorted by measured speed, fastest first. Tested 20 Nov 2026:
    the meta4's first mirror gave 0.4 MB/s while others gave 7-13 MB/s,
    which turns a 148 GB bundle from about 4 hours into 5 days. A mirror
    that fails the probe is kept, last, in case the others fail too."""
    speeds = {}
    for url in urls:
        got, t0 = 0, time.monotonic()
        try:
            with open_url(url, 0, end=PROBE_BYTES - 1, timeout=PROBE_SECONDS) as r:
                while got < PROBE_BYTES and time.monotonic() - t0 < PROBE_SECONDS:
                    block = r.read(64 * 1024)
                    if not block:
                        break
                    got += len(block)
        except (urllib.error.URLError, TimeoutError, ConnectionError, OSError):
            got = 0
        speeds[url] = got / max(time.monotonic() - t0, 1e-6)
    return sorted(urls, key=lambda u: -speeds[u]), speeds


# --------------------------------------------------------------- per kind

def do_zim(row, dest, state, dry_run):
    target = dest / row["folder"]
    try:
        meta = parse_meta4(fetch_text(row["source_url"]))
    except (urllib.error.URLError, ET.ParseError) as e:
        raise Failed(f"could not read meta4: {e}")
    if meta["name"] != target.name:
        raise Failed(f"meta4 file is {meta['name']} but catalog folder says {target.name}")
    if not meta["sha256"]:
        raise Failed("meta4 has no sha-256")
    cat = int(row["size_bytes"] or 0)
    if cat and abs(cat - meta["size"]) > 4096:
        print(f"    note: catalog size {cat} vs meta4 {meta['size']}; using meta4", flush=True)

    entry = state.get(dest, target)
    if entry and entry["sha256"] == meta["sha256"]:
        return "present", meta["size"], meta["sha256"], False
    if dry_run:  # never hash or move files in a dry run
        return ("present-unchecked" if target.exists() else "would-download"), meta["size"], "", False
    if target.exists():  # copied in by hand or state lost: check it
        if sha256_file(target) == meta["sha256"]:
            state.put(dest, target, meta["sha256"])
            return "present", meta["size"], meta["sha256"], False
        os.replace(target, target.with_name(target.name + ".bad"))
        print(f"    existing file failed sha-256, moved aside as {target.name}.bad", flush=True)
    target.parent.mkdir(parents=True, exist_ok=True)
    part = target.with_name(target.name + ".part")
    errors = []
    urls = meta["urls"]
    have = part.stat().st_size if part.exists() else 0
    if len(urls) > 1 and meta["size"] - have > PROBE_ABOVE:
        urls, speeds = fastest_first(urls)
        print(f"    fastest mirror: {urls[0].split('/')[2]} ({human(speeds[urls[0]])}/s)", flush=True)
    for url in urls:
        start = part.stat().st_size if part.exists() else 0
        if start > meta["size"]:
            part.unlink()
            start = 0
        if start == meta["size"]:
            break
        print(f"    from {url.split('/')[2]}" + (f", resuming at {human(start)}" if start else ""), flush=True)
        try:
            if stream_to(url, part, start, meta["size"], target.name) == meta["size"]:
                break
        except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as e:
            errors.append(f"{url.split('/')[2]}: {e}")
    if not part.exists() or part.stat().st_size != meta["size"]:
        raise Failed("all mirrors failed: " + "; ".join(errors[-3:]))
    sha = sha256_file(part)
    if sha != meta["sha256"]:
        part.unlink()
        raise Failed("sha-256 does not match the meta4; partial file deleted, run again")
    os.replace(part, target)
    state.put(dest, target, sha)
    return "downloaded", meta["size"], sha, True


def do_pdf(row, dest, state, dry_run):
    target = dest / row["folder"]
    entry = state.get(dest, target)
    if entry:
        return "present", entry["size"], entry["sha256"], False
    expected = int(row["size_bytes"]) if row["size_bytes"] else None
    if dry_run:
        return ("present-unchecked" if target.exists() else "would-download"), expected or 0, "", False
    if target.exists():  # placed by hand (MANUAL items) or state lost
        magic = magic_for(target)
        with open(target, "rb") as f:
            if f.read(len(magic)) != magic:
                raise Failed(f"{target} exists but is not a {target.suffix} file")
        size = target.stat().st_size
        if expected and size != expected:
            raise Failed(f"{target} is {size} bytes, catalog says {expected}")
        sha = sha256_file(target)
        state.put(dest, target, sha)
        return "present", size, sha, False
    size = get_pdf(row["source_url"], target, expected)
    check_md5(row["source_url"], target)
    sha = sha256_file(target)
    state.put(dest, target, sha)
    return "downloaded", size, sha, True


def check_md5(url, target):
    """Software archives: compare with the publisher's <url>.md5 when it
    exists (Kiwix publishes one per release file). PDFs have none."""
    if not target.name.endswith(SOFTWARE):
        return
    try:
        published = fetch_text(url + ".md5").split()[0].lower()
    except (urllib.error.URLError, IndexError):
        print("    note: no .md5 published next to the archive", flush=True)
        return
    h = hashlib.md5()
    with open(target, "rb") as f:
        for block in iter(lambda: f.read(CHUNK), b""):
            h.update(block)
    if h.hexdigest() != published:
        bad = target.with_name(target.name + ".bad")
        os.replace(target, bad)
        raise Failed(f"md5 differs from the publisher's .md5; kept as {bad.name}")


HESPERIAN_LINK = 'href="(https://hesperian\\.org/wp-content/uploads/pdf/{p}/{p}_[A-Za-z0-9_]+\\.pdf)"'


def do_hesperian(row, dest, state, dry_run):
    folder = dest / row["folder"]
    prefix = folder.name  # e.g. en_wtnd_2025
    try:
        page = fetch_text(row["source_url"])
    except urllib.error.URLError as e:
        raise Failed(f"could not read {row['source_url']}: {e}")
    urls = sorted(set(re.findall(HESPERIAN_LINK.format(p=re.escape(prefix)), page)))
    want = cl.file_count(row)
    if len(urls) != want:
        raise Failed(f"page lists {len(urls)} files for {prefix}, catalog expects {want} "
                     "(new printing? update the catalog row)")
    lines, total, new, missing = [], 0, False, 0
    for url in urls:
        target = folder / url.rsplit("/", 1)[1]
        entry = state.get(dest, target)
        if entry:
            sha, size = entry["sha256"], entry["size"]
        elif dry_run:
            missing += 1
            continue
        else:
            size = get_pdf(url, target)
            sha = sha256_file(target)
            state.put(dest, target, sha)
            new = True
        total += size
        lines.append(f"{sha}  {target.name}\n")
    if missing:
        return "would-download", total, "", False
    # One fingerprint for the whole book: sha-256 of its sorted file list.
    book_sha = hashlib.sha256("".join(sorted(lines)).encode()).hexdigest()
    return ("downloaded" if new else "present"), total, book_sha, new


def kind_of(row):
    url = row["source_url"]
    if url.endswith(".meta4"):
        return "zim", do_zim
    if "languages.hesperian.org" in url and cl.is_multi_file(row):
        return "hesperian", do_hesperian
    if cl.is_multi_file(row):
        return "unsupported", None
    if row["folder"].endswith(SOFTWARE):
        return "archive", do_pdf   # same steps; signature and .md5 differ by suffix
    return "pdf", do_pdf


# ---------------------------------------------------------------------- main

def main(argv=None):
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dest", required=True, type=Path, help="staging folder (not the drive)")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--bundle", choices=cl.BUNDLES)
    g.add_argument("--ids", nargs="+")
    ap.add_argument("--catalog", type=Path, default=cl.CATALOG)
    ap.add_argument("--dry-run", action="store_true", help="check sources and sizes, download nothing")
    ap.add_argument("--update-catalog", action="store_true",
                    help="write sha256, size_bytes and download_date back to the catalog")
    args = ap.parse_args(argv)

    fields, rows = cl.read_csv(args.catalog)
    chosen = cl.select(rows, args.bundle, args.ids)
    dest = args.dest.resolve()
    dest.mkdir(parents=True, exist_ok=True)
    state = State(dest)
    today = dt.date.today().isoformat()

    known = sum(int(r["size_bytes"] or 0) for r in chosen)
    print(f"{len(chosen)} items, about {human(known)} (rows with a known size) -> {dest}\n", flush=True)

    results = []
    for row in chosen:
        kind, fn = kind_of(row)
        print(f"[{row['id']}] {kind}: {row['title'][:70]}", flush=True)
        try:
            if fn is None:
                raise Failed(f"don't know how to fetch a multi-file item from {row['source_url']}")
            status, size, sha, new = fn(row, dest, state, args.dry_run)
            msg = ""
        except Manual as e:
            status, size, sha, new, msg = "MANUAL", 0, "", False, str(e)
        except Failed as e:
            status, size, sha, new, msg = "FAILED", 0, "", False, str(e)
        print(f"    {status} {human(size) if size else ''} {msg}".rstrip(), flush=True)
        results.append((row["id"], status, msg))

        if args.update_catalog and sha:
            row["sha256"] = sha
            if size and (not row["size_bytes"] or kind in ("zim", "hesperian")):
                row["size_bytes"] = str(size)
            if new or not row["download_date"]:
                row["download_date"] = today
            cl.write_csv_atomic(args.catalog, fields, rows)

    print("\nSummary")
    counts = {}
    for _, s, _ in results:
        counts[s] = counts.get(s, 0) + 1
    print("  " + ", ".join(f"{k}: {v}" for k, v in sorted(counts.items())))
    for rid, s, msg in results:
        if s in ("MANUAL", "FAILED"):
            print(f"  {s} {rid}: {msg}")
    return 1 if counts.get("FAILED") else 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:   # Ctrl+C: state and catalog writes are atomic, so nothing is lost
        print("\nStopped. Run the same command again to continue: finished files are kept, "
              "and a ZIM download resumes where it stopped.", flush=True)
        sys.exit(130)
