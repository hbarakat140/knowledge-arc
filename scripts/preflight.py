"""The checks make-arc.py runs before a long download, and on its own with
--check: can this computer write to the drive, does the edition fit, does
the internet reach Kiwix and the publishers, will the guides be searchable,
and will the computer stay awake.

Each source is asked for its first kilobyte the way download.py asks for the
whole file (same address, same downloader, same HTTPS settings, the same
first checks), so a site that refuses here would refuse the real download
too. Items already in the download folder and files kept in this repository
(hosted/) are not asked.

    quick (before every build): one item per website, many websites at once
    thorough (make-arc --check): every item still to fetch, a few at a time

Standard library only.
"""

import concurrent.futures
import ctypes
import http.client
import os
import shutil
import subprocess
import sys
import urllib.error
import urllib.parse
from pathlib import Path

import catalog_lib as cl
import download

PROBE_TIMEOUT = 20   # seconds per source
QUICK_THREADS = 32   # quick mode asks each website once: many at a time is polite
THOROUGH_THREADS = 8 # --check asks a website several times: fewer at a time
OK, WARNING, PROBLEM = "OK", "WARNING", "PROBLEM"


# ------------------------------------------------------------------ sources

def fetched(row, staging):
    """Already in the download folder: a folder (multi-file item), a file of
    the catalog's size (any size when the catalog has none), or a file
    download.py recorded (a newer Kiwix version saved in place of a pinned
    one that was gone). make-arc's size estimate uses the same rule."""
    target = staging / row["folder"]
    if target.is_dir():
        return True
    if not target.is_file():
        return False
    size = int(row["size_bytes"] or 0)
    if not size or target.stat().st_size == size:
        return True
    dest = staging / cl.KIT if row["folder"].startswith(cl.KIT + "/") else staging
    return bool(download.State(dest).get(dest, target))


def hosted(row):
    """Kept in this repository, so download.py copies it (pdf and software
    rows only; a pocket-kit row's folder starts with cl.KIT on a bigger drive)."""
    folder = row["folder"].removeprefix(cl.KIT + "/")
    return download.kind_of(row)[0] in ("pdf", "archive") and (download.HOSTED / folder).is_file()


def to_fetch(rows, staging):
    """Rows that still need the internet."""
    return [r for r in rows if not fetched(r, staging) and not hosted(r)]


def site(row):
    return urllib.parse.urlsplit(row["source_url"]).netloc.lower()


class ItemOnly(str):
    """A failure of this item only (gone, or its pinned list out of date),
    not of its website: quick mode doesn't count it for the site's others."""


def why(err):
    if isinstance(err, urllib.error.HTTPError):
        if err.code in (401, 403):
            return f"refuses downloads by script (HTTP {err.code})"
        return ItemOnly("file not found (HTTP 404)") if err.code == 404 else f"HTTP {err.code}"
    if isinstance(err, download.Failed):
        return ItemOnly(err)
    return f"no answer ({getattr(err, 'reason', None) or str(err) or type(err).__name__})"


def probe(row):
    """None if the source answers as the real download expects, else why not."""
    kind, _ = download.kind_of(row)
    try:
        if kind == "unsupported":
            return "the build can't fetch this kind of item"
        if kind == "zim":
            try:
                download.parse_meta4(download.fetch_text(row["source_url"], PROBE_TIMEOUT))
            except urllib.error.HTTPError as e:
                # Kiwix keeps only the newest versions; download.py then takes
                # the newest of the same collection.
                if e.code != 404 or not download.newest_same_book(row["source_url"], PROBE_TIMEOUT):
                    raise
            return None
        if kind == "hesperian":
            download.hesperian_urls(row, PROBE_TIMEOUT)   # also checks the file count
            return None
        if kind == "file-list":
            files = cl.file_list(row)
            if len(files) != cl.file_count(row):   # download.py's first check
                return ItemOnly(f"catalog/files/{row['id']}.csv lists {len(files)} files, "
                                f"the row expects {cl.file_count(row)}")
            url, name = files[0]["url"], files[0]["file"]
        else:
            url, name = row["source_url"], row["folder"]
        with download.open_url(url, 0, 1023, timeout=PROBE_TIMEOUT) as r:
            head = r.read(1024)
        magic = download.magic_for(Path(name))
        return "answers with a web page, not the file" if magic and not head.startswith(magic) else None
    except urllib.error.HTTPError as e:
        return None if e.code == 429 else why(e)   # 429: there, busy; download.py waits and retries
    except (urllib.error.URLError, OSError, ValueError, http.client.HTTPException, download.Failed) as e:
        return why(e)


def check_sources(rows, staging, thorough=False):
    """({site: [(row, reason)]} of failures, sites, items still to fetch).
    Quick: one row per site; a failure of the site (no answer, refused) counts
    for every row of that site, a failure of the item (ItemOnly) for it alone."""
    todo = to_fetch(rows, staging)
    by_site = {}
    for r in todo:
        by_site.setdefault(site(r), []).append(r)
    asked = todo if thorough else [rs[0] for rs in by_site.values()]
    with concurrent.futures.ThreadPoolExecutor(THOROUGH_THREADS if thorough else QUICK_THREADS) as pool:
        results = list(pool.map(lambda r: probe(r), asked))   # looked up now: tests replace probe
    failed = {}
    for r, reason in zip(asked, results):
        if reason:
            hit = [r] if thorough or isinstance(reason, ItemOnly) else by_site[site(r)]
            failed.setdefault(site(r), []).extend((x, reason) for x in hit)
    return failed, len(by_site), len(todo)


# -------------------------------------------------------------------- drive

def writable(folder):
    """None if a file can be written and removed in folder, else why not."""
    test = Path(folder) / ".arc-write-test"
    try:
        test.write_bytes(b"ok")
        test.unlink()
        return None
    except OSError as e:
        return e.strerror or str(e)


# ------------------------------------------------------------------- awake

def keep_awake():
    """Ask the computer not to sleep while this process runs (the screen may
    still turn off): Windows SetThreadExecutionState, Mac caffeinate, Linux
    systemd-inhibit, all ending by themselves when make-arc ends. Returns the
    report line: OK only if it worked."""
    awake = (OK, "This computer will be kept awake while it works (a laptop: keep it plugged in).")
    try:
        if os.name == "nt":
            ES_CONTINUOUS, ES_SYSTEM_REQUIRED = 0x80000000, 0x00000001
            if ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS | ES_SYSTEM_REQUIRED):
                return awake
        elif sys.platform == "darwin" and shutil.which("caffeinate"):
            subprocess.Popen(["caffeinate", "-i", "-w", str(os.getpid())])
            return awake
        elif shutil.which("systemd-inhibit") and shutil.which("tail"):
            p = subprocess.Popen(["systemd-inhibit", "--what=sleep:idle", "--who=Knowledge Arc",
                                  "--why=Downloading the library", "--mode=block",
                                  "tail", f"--pid={os.getpid()}", "-f", "/dev/null"],
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            try:
                p.wait(timeout=1)   # still running after a second: the lock holds
            except subprocess.TimeoutExpired:
                return awake
    except (OSError, AttributeError, ValueError):
        pass
    return (WARNING, "Set this computer not to go to sleep until it has finished "
                     "(a laptop: plugged in, lid open).")


# ------------------------------------------------------------------- report

def report(lines, say):
    """lines: [(level, text)]. Prints them; returns True if nothing blocks."""
    say("\n== Checks before the download ==")
    for level, text in lines:
        say(f"  {level:8} {text}")
    blocked = any(level == PROBLEM for level, _ in lines)
    if blocked:
        say("\nNot ready: fix the PROBLEM lines first.")
    elif any(level == WARNING for level, _ in lines):
        say("\nReady, with the warnings above.")
    else:
        say("\nReady.")
    return not blocked


def source_lines(failed, sites, todo, thorough):
    """Report lines for check_sources' result."""
    if not todo:
        return [(OK, "Everything is already downloaded or kept in this recipe: no internet needed.")]
    down = {s for s, items in failed.items() if any(not isinstance(reason, ItemOnly) for _, reason in items)}
    if len(down) == sites:
        return [(PROBLEM, "No website answered. Check the internet connection.")]
    if not failed:
        return [(OK, f"Internet: all {f'{todo} items' if thorough else f'{sites} websites'} answer.")]
    lines = []
    if any("kiwix" in s for s in down):
        lines.append((PROBLEM, "The Kiwix servers don't answer: the big collections "
                               "(Wikipedia, medicine, books...) can't be fetched now."))
    n = sum(len(v) for v in failed.values())
    lines.append((WARNING, f"{n} of {todo} items can't be fetched now; the arc is built without "
                           "them, and a later run adds them:"))
    for s, items in sorted(failed.items()):
        ids = ", ".join(r["id"] for r, _ in items[:8]) + (" ..." if len(items) > 8 else "")
        lines.append(("", f"  {s}: {items[0][1]} ({len(items)} items: {ids})"))
    return lines
