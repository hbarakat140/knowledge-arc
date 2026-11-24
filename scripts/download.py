"""Download catalog items into a staging folder, check them, and (optionally)
write sha256 / size / date back into catalog/catalog.csv.

    python scripts/download.py --dest D:/staging --bundle core
    python scripts/download.py --dest D:/archive --bundle all     (every edition: fills the archive)
    python scripts/download.py --dest D:/staging --ids T1-003 T2-036
    python scripts/download.py --dest D:/staging --bundle core --dry-run
    python scripts/download.py --dest D:/staging --bundle core --update-catalog

Kinds of source, decided from source_url:
  *.meta4            Kiwix ZIM: fastest mirror first, resumable, sha-256 checked
  languages.hesperian.org + "(N files)"   Hesperian book: chapter PDFs scraped
                     from the page; fails if the count isn't N
  "(N files)" + catalog/files/<id>.csv   the N files pinned in that list
                     (e.g. the EMA herbal monographs), one at a time
  *.zip / *.tar.gz / *.tar.xz / *.apk / *.exe / *.dmg / *.appimage   software (tier 9): signature, size_bytes,
                     and the publisher's .md5 file next to it when there is one
  anything else      one PDF: must start with %PDF- and match size_bytes if known

Pages that block scripts or are HTML landing pages are reported as MANUAL:
download them by hand to the path shown, then run again to hash them. The
few such files the arc needs are kept in this repository instead
(hosted/<catalog folder>, see hosted/README.md) and copied from there.

A Kiwix collection whose pinned version has left Kiwix's servers (they keep
the two newest of each) is replaced by the newest version of the same
collection, saved under the catalog's file name; the build notes it in
VERSION.txt.

Standard library only. Safe to interrupt and run again: finished files are
remembered in <dest>/.download-state.json and skipped.
"""

import argparse
import datetime as dt
import functools
import hashlib
import http.client
import json
import os
import re
import shutil
import sys
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import catalog_lib as cl  # noqa: E402

HOSTED = cl.REPO / "hosted"   # copies of files whose sites block scripts

USER_AGENT = "Mozilla/5.0 (compatible; offline-family-library-build/1.0)"
CHUNK = 1024 * 1024
TIMEOUT = 60
ML = "{urn:ietf:params:xml:ns:metalink}"
RATE_LIMIT_WAITS = 6     # HTTP 429 "too many requests": waits before giving up
MAX_RESUMES = 50         # a PDF whose connection keeps dropping: times to ask for the rest
FILE_LIST_PAUSE = 1.0    # seconds between the files of a pinned file list


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
    return urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=timeout,
                                  context=cl.ssl_context())


def retry_after(err, n):
    """Seconds to wait after HTTP 429: the server's Retry-After if it gives
    one (capped at 5 minutes), else 15, 30, 60... seconds."""
    try:
        return min(int(err.headers.get("Retry-After", "")), 300)
    except (TypeError, ValueError, AttributeError):
        return min(15 * 2 ** (n - 1), 300)


def fetch_text(url, timeout=TIMEOUT):
    with open_url(url, timeout=timeout) as r:
        return r.read().decode("utf-8", errors="replace")


@functools.lru_cache(maxsize=None)
def folder_listing(url, timeout=TIMEOUT):
    """A Kiwix folder's file listing, fetched once per run (several
    collections share a folder)."""
    return fetch_text(url, timeout)


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

    def put(self, dest, target, sha, source=None):
        """source: the file actually fetched, when it differs from the
        catalog's (a newer Kiwix version); assemble.py notes it."""
        st = target.stat()
        entry = {"size": st.st_size, "mtime_ns": st.st_mtime_ns, "sha256": sha}
        if source:
            entry["source"] = source
        self.data[target.relative_to(dest).as_posix()] = entry
        self.save()

    def forget(self, rel):
        self.data.pop(rel, None)
        self.save()

    def save(self):
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


# .dmg has no signature at its start (its "koly" block is at the end): size only.
MAGIC = {".pdf": b"%PDF-", ".zip": b"PK\x03\x04", ".apk": b"PK\x03\x04", ".gz": b"\x1f\x8b",
         ".exe": b"MZ", ".dmg": b"", ".xz": b"\xfd7zXZ\x00", ".appimage": b"\x7fELF"}
# Tier 9 files: signature + size, and the publisher's .md5 when there is one
# (Kiwix publishes them; Mozilla and others publish SHA256SUMS, checked by hand
# and recorded in the row notes).
SOFTWARE = (".zip", ".tar.gz", ".apk", ".exe", ".dmg", ".tar.xz", ".appimage")


def magic_for(target):
    return MAGIC.get(target.suffix.lower(), b"%PDF-")


def get_pdf(url, target, expected_size=None):
    """Download one file (a PDF unless target's suffix says otherwise) to
    target, checking its first bytes. Raises Manual or Failed."""
    magic = magic_for(target)
    part = target.with_name(target.name + ".part")
    target.parent.mkdir(parents=True, exist_ok=True)
    last_err, complete, waits = None, False, 0
    attempt, total, resumes = 0, None, 0
    while attempt < 3:
        attempt += 1
        # A connection dropped part-way: ask for the rest (servers such as the
        # EU's JRC cut big PDFs off every few minutes).
        have = part.stat().st_size if total and part.exists() else 0
        try:
            with open_url(url, have) as r:
                if have and r.status != 206:
                    have = 0  # server ignored Range: start over
                ctype = r.headers.get("Content-Type", "")
                length = r.headers.get("Content-Length")
                head = b""
                if not have:
                    head = r.read(len(magic))
                    if head != magic:
                        raise Manual(f"not a {target.suffix} file (Content-Type {ctype or 'none'}): "
                                     f"open {url} in a browser and save it as {target}")
                    total = int(length) if length else None
                with open(part, "ab" if have else "wb") as f:
                    f.write(head)
                    for block in iter(lambda: r.read(CHUNK), b""):
                        f.write(block)
            if total and part.stat().st_size != total:
                raise ConnectionError(f"got {part.stat().st_size} of {total} bytes")
            complete = True
            break
        except (http.client.IncompleteRead, ConnectionError, TimeoutError) as e:
            last_err = str(e) or type(e).__name__
            if total and part.exists() and part.stat().st_size > have and resumes < MAX_RESUMES:
                resumes += 1
                attempt -= 1  # progress was made: resuming doesn't use up a try
                continue
            time.sleep(2 * attempt)
            continue
        except urllib.error.HTTPError as e:
            if e.code == 429 and waits < RATE_LIMIT_WAITS:
                # "Too many requests" (the EMA does this): wait as asked, try again.
                waits += 1
                attempt -= 1
                time.sleep(retry_after(e, waits))
                continue
            if e.code in (401, 403, 429):
                raise Manual(f"HTTP {e.code} (site blocks scripts): open {url} in a browser "
                             f"and save the PDF as {target}")
            last_err = f"HTTP {e.code}"
            if e.code == 404:
                break
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            last_err = str(e)
        time.sleep(2 * attempt)
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

ZIM_NAME = re.compile(r"^(?P<book>.+)_(?P<date>\d{4}-\d{2}[a-z]?)\.zim$")


def newest_same_book(meta4_url, timeout=TIMEOUT):
    """The .meta4 address of the newest version of the same Kiwix collection
    (same name and flavour, any date), read from the server's folder listing;
    None if there is none."""
    folder, name = meta4_url.rsplit("/", 1)
    m = ZIM_NAME.match(name[:-len(".meta4")])
    if not m:
        return None
    listing = folder + "/"   # Kiwix's servers list each folder's files
    found = set(re.findall(r'href="(' + re.escape(m["book"]) + r'_\d{4}-\d{2}[a-z]?\.zim)"',
                           folder_listing(listing, timeout)))
    if not found:
        return None
    return f"{listing}{max(found, key=lambda n: ZIM_NAME.match(n)['date'])}.meta4"


def do_zim(row, dest, state, dry_run):
    target = dest / row["folder"]
    source = None   # set when a newer version replaces the pinned one
    try:
        meta = parse_meta4(fetch_text(row["source_url"]))
    except urllib.error.HTTPError as e:
        if e.code != 404:
            raise Failed(f"could not read meta4: {e}")
        try:
            newer = newest_same_book(row["source_url"])
        except urllib.error.URLError as e2:
            raise Failed(f"pinned version gone (404) and the server listing failed: {e2}")
        if not newer:
            raise Failed("pinned version gone from Kiwix's servers (404), and no other version found")
        try:
            meta = parse_meta4(fetch_text(newer))
        except (urllib.error.URLError, ET.ParseError) as e2:
            raise Failed(f"could not read meta4 of the newer version: {e2}")
        source = meta["name"]
        print(f"    NOTE: {target.name} is no longer on Kiwix's servers; using the newest version, "
              f"{source}, saved under the catalog's name", flush=True)
    except (urllib.error.URLError, ET.ParseError) as e:
        raise Failed(f"could not read meta4: {e}")
    if source is None and meta["name"] != target.name:
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
            state.put(dest, target, meta["sha256"], source)
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
    state.put(dest, target, sha, source)
    return "downloaded", meta["size"], sha, True


def do_pdf(row, dest, state, dry_run):
    target = dest / row["folder"]
    entry = state.get(dest, target)
    if entry:
        return "present", entry["size"], entry["sha256"], False
    expected = int(row["size_bytes"]) if row["size_bytes"] else None
    hosted = HOSTED / row["folder"]
    if dry_run:
        if target.exists():
            return "present-unchecked", expected or 0, "", False
        return ("would-copy-from-repository" if hosted.is_file() else "would-download"), expected or 0, "", False
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
    if hosted.is_file():
        return copy_hosted(row, hosted, dest, target, state)
    size = get_pdf(row["source_url"], target, expected)
    check_md5(row["source_url"], target)
    sha = sha256_file(target)
    state.put(dest, target, sha)
    return "downloaded", size, sha, True


def copy_hosted(row, hosted, dest, target, state):
    """Copy the repository's own copy (hosted/), checked against the
    catalog's sha256 when it has one."""
    target.parent.mkdir(parents=True, exist_ok=True)
    part = target.with_name(target.name + ".part")
    shutil.copyfile(hosted, part)
    sha = sha256_file(part)
    if row["sha256"] and sha != row["sha256"]:
        part.unlink()
        raise Failed(f"the repository's copy {hosted.name} (in hosted/) does not match "
                     "the catalog's sha256")
    os.replace(part, target)
    state.put(dest, target, sha)
    return "copied-from-repository", target.stat().st_size, sha, True


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


def hesperian_urls(row, timeout=TIMEOUT):
    """The chapter PDFs a Hesperian book's page lists, checked against the
    catalog's file count (a new printing changes it)."""
    prefix = Path(row["folder"]).name  # e.g. en_wtnd_2025
    try:
        page = fetch_text(row["source_url"], timeout)
    except urllib.error.URLError as e:
        raise Failed(f"could not read {row['source_url']}: {e}")
    urls = sorted(set(re.findall(HESPERIAN_LINK.format(p=re.escape(prefix)), page, re.IGNORECASE)))
    want = cl.file_count(row)
    if len(urls) != want:
        raise Failed(f"page lists {len(urls)} files for {prefix}, catalog expects {want} "
                     "(new printing? update the catalog row)")
    return urls


def do_hesperian(row, dest, state, dry_run):
    folder = dest / row["folder"]
    urls = hesperian_urls(row)
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


def do_file_list(row, dest, state, dry_run, folder=None):
    """A multi-file item whose files are pinned in catalog/files/<id>.csv:
    fetch exactly those, politely (some sites limit request rates)."""
    files = cl.file_list(row, folder)
    want = cl.file_count(row)
    if len(files) != want:
        raise Failed(f"catalog/files/{row['id']}.csv lists {len(files)} files, the row expects {want}")
    target_dir = dest / row["folder"]
    lines, total, new, missing = [], 0, False, 0
    for f in files:
        target = target_dir / f["file"]
        entry = state.get(dest, target)
        if entry and entry.get("source") != f["url"]:
            entry = None   # fetched from another address (or not recorded): fetch again
        if entry:
            sha, size = entry["sha256"], entry["size"]
        elif dry_run:
            missing += 1
            continue
        else:
            if new:
                time.sleep(FILE_LIST_PAUSE)
            size = get_pdf(f["url"], target)
            sha = sha256_file(target)
            state.put(dest, target, sha, f["url"])
            new = True
        total += size
        lines.append(f"{sha}  {target.name}\n")
    if missing:
        return "would-download", total, "", False
    # Files a refreshed list no longer names: fetched by this function from an
    # older list, so remove them (and forget them), or the build counts them.
    folder_rel = target_dir.relative_to(dest).as_posix() + "/"
    keep = {f["file"] for f in files}
    for rel in [r for r in list(state.data) if r.startswith(folder_rel)]:
        if rel[len(folder_rel):] not in keep and not dry_run:
            (dest / rel).unlink(missing_ok=True)
            state.forget(rel)
            print(f"    removed {rel[len(folder_rel):]}: no longer on the list", flush=True)
    book_sha = hashlib.sha256("".join(sorted(lines)).encode()).hexdigest()
    return ("downloaded" if new else "present"), total, book_sha, new


def kind_of(row):
    url = row["source_url"]
    if url.endswith(".meta4"):
        return "zim", do_zim
    if "languages.hesperian.org" in url and cl.is_multi_file(row):
        return "hesperian", do_hesperian
    if cl.is_multi_file(row) and cl.file_list(row):
        return "file-list", do_file_list
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
    g.add_argument("--bundle", choices=cl.BUNDLES + ["all"],
                   help="an edition, or all: every row any edition needs (for the archive)")
    g.add_argument("--ids", nargs="+")
    ap.add_argument("--catalog", type=Path, default=cl.CATALOG)
    ap.add_argument("--dry-run", action="store_true", help="check sources and sizes, download nothing")
    ap.add_argument("--update-catalog", action="store_true",
                    help="write sha256, size_bytes and download_date back to the catalog")
    args = ap.parse_args(argv)

    fields, rows = cl.read_csv(args.catalog)
    if args.bundle:
        chosen, kit_rows = cl.drive_rows(rows, args.bundle)
    else:
        chosen, kit_rows = cl.select(rows, None, args.ids), []
    dest = args.dest.resolve()
    dest.mkdir(parents=True, exist_ok=True)
    state = State(dest)
    today = dt.date.today().isoformat()

    known = sum(int(r["size_bytes"] or 0) for r in chosen + kit_rows)
    print(f"{len(chosen) + len(kit_rows)} items, about {human(known)} (rows with a known size) -> {dest}\n",
          flush=True)

    results = []

    def fetch_rows(selection, where, where_state):
        for row in selection:
            kind, fn = kind_of(row)
            print(f"[{row['id']}] {kind}: {row['title'][:70]}", flush=True)
            try:
                if fn is None:
                    raise Failed(f"don't know how to fetch a multi-file item from {row['source_url']}")
                status, size, sha, new = fn(row, where, where_state, args.dry_run)
                msg = ""
            except Manual as e:
                status, size, sha, new, msg = "MANUAL", 0, "", False, str(e)
            except Failed as e:
                status, size, sha, new, msg = "FAILED", 0, "", False, str(e)
            print(f"    {status} {human(size) if size else ''} {msg}".rstrip(), flush=True)
            results.append((row["id"], status, msg))

            if args.update_catalog and sha:
                row["sha256"] = sha
                if size and (not row["size_bytes"] or kind in ("zim", "hesperian", "file-list")):
                    row["size_bytes"] = str(size)
                if new or not row["download_date"]:
                    row["download_date"] = today
                cl.write_csv_atomic(args.catalog, fields, rows)

    fetch_rows(chosen, dest, state)
    if kit_rows:
        # The pocket kit's own files (pocket rows this edition replaced), kept
        # apart in KIT with their own state file, so the drive's library never
        # serves them and a one-drive build finds them in the same place.
        print(f"\nFor the pocket kit ({cl.KIT}): what a pocket copy made from this drive needs "
              "beyond the drive's own files.", flush=True)
        kit = dest / cl.KIT
        if not args.dry_run:
            kit.mkdir(parents=True, exist_ok=True)
        # Already in this folder at its usual place (an archive filled with
        # --bundle all): assemble.py takes it from there, no second download.
        elsewhere = [r for r in kit_rows if not cl.is_multi_file(r) and state.get(dest, dest / r["folder"])]
        for r in elsewhere:
            print(f"[{r['id']}] present at {r['folder']}: {r['title'][:60]}", flush=True)
            results.append((r["id"], "present", ""))
        fetch_rows([r for r in kit_rows if r not in elsewhere], kit, State(kit))

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
