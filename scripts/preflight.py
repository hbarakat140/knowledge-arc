"""The checks make-arc.py runs before a long download, and on its own with
--check: can this computer write to the drive, does the edition fit, does
the internet reach Kiwix and the publishers, will the guides be searchable,
and will the computer stay awake.

Each source is asked for its first kilobyte the way download.py asks for the
whole file (same address, same downloader, same HTTPS settings), so a site
that refuses here would refuse the real download too. Items already on the
drive and files kept in this repository (hosted/) are not asked.

    quick (before every build): one item per website, so a site that refuses
                                scripts is found in seconds
    thorough (make-arc --check): every item still to fetch

Standard library only.
"""

import concurrent.futures
import ctypes
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
PROBE_THREADS = 8
OK, WARNING, PROBLEM = "OK", "WARNING", "PROBLEM"


# ------------------------------------------------------------------ sources

def repo_folder(row):
    """The row's folder as the catalog has it (a pocket-kit row's folder is
    prefixed with cl.KIT on a bigger drive)."""
    folder = row["folder"]
    return folder[len(cl.KIT) + 1:] if folder.startswith(cl.KIT + "/") else folder


def to_fetch(rows, staging):
    """Rows that still need the internet: not already in the download folder
    (same size), not kept in this repository (hosted/)."""
    out = []
    for r in rows:
        target = staging / r["folder"]
        size = int(r["size_bytes"] or 0)
        if target.is_dir() or (target.is_file() and (not size or target.stat().st_size == size)):
            continue
        if (download.HOSTED / repo_folder(r)).is_file():
            continue
        out.append(r)
    return out


def site(row):
    return urllib.parse.urlsplit(row["source_url"]).netloc.lower()


def probe_url(row):
    """The address download.py fetches first for this row."""
    kind, _ = download.kind_of(row)
    if kind == "file-list":
        return cl.file_list(row)[0]["url"]
    return row["source_url"]


def why(err):
    if isinstance(err, urllib.error.HTTPError):
        return {403: "refuses downloads by script (HTTP 403)", 404: "file not found (HTTP 404)",
                429: "busy (HTTP 429)"}.get(err.code, f"HTTP {err.code}")
    reason = getattr(err, "reason", err)
    return f"no answer ({reason})" if str(reason) else f"no answer ({type(err).__name__})"


def probe(row):
    """None if the source answers as the real download expects, else why not."""
    kind, _ = download.kind_of(row)
    url = probe_url(row)
    try:
        if kind == "unsupported":
            return "the build can't fetch this kind of item"
        if kind == "zim":
            try:
                download.parse_meta4(download.fetch_text(url))
            except urllib.error.HTTPError as e:
                # Kiwix keeps only the newest versions; download.py then takes
                # the newest of the same collection.
                if e.code != 404 or not download.newest_same_book(url):
                    raise
            return None
        if kind == "hesperian":
            download.fetch_text(url)
            return None
        with download.open_url(url, 0, 1023, timeout=PROBE_TIMEOUT) as r:
            head = r.read(1024)
        magic = download.magic_for(Path(urllib.parse.urlsplit(url).path if kind == "file-list"
                                        else row["folder"]))
        if magic and not head.startswith(magic):
            return "answers with a web page, not the file"
        return None
    except (urllib.error.URLError, OSError, ValueError, download.Failed) as e:
        if isinstance(e, urllib.error.HTTPError) and e.code == 429:
            return None   # rate-limited, but there: download.py waits and retries
        return why(e)


def check_sources(rows, staging, thorough=False, probe_fn=None):
    """({site: [(row, reason)]} of failures, sites, items still to fetch).
    Quick: one row per site; a failure counts for every row of that site."""
    probe_fn = probe_fn or probe
    todo = to_fetch(rows, staging)
    by_site = {}
    for r in todo:
        by_site.setdefault(site(r), []).append(r)
    asked = todo if thorough else [rs[0] for rs in by_site.values()]
    with concurrent.futures.ThreadPoolExecutor(PROBE_THREADS) as pool:
        results = list(pool.map(probe_fn, asked))
    failed = {}
    for r, reason in zip(asked, results):
        if reason:
            hit = [r] if thorough else by_site[site(r)]
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
    still turn off). Returns a sentence for the person, and whether it worked.
    Windows: SetThreadExecutionState; Mac: caffeinate; Linux: systemd-inhibit.
    All end by themselves when make-arc ends."""
    try:
        if os.name == "nt":
            ES_CONTINUOUS, ES_SYSTEM_REQUIRED = 0x80000000, 0x00000001
            if ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS | ES_SYSTEM_REQUIRED):
                return "This computer will be kept awake while it works (a laptop: keep it plugged in).", True
        elif sys.platform == "darwin" and shutil.which("caffeinate"):
            subprocess.Popen(["caffeinate", "-i", "-w", str(os.getpid())])
            return "This Mac will be kept awake while it works (keep it plugged in).", True
        elif shutil.which("systemd-inhibit") and shutil.which("tail"):
            p = subprocess.Popen(["systemd-inhibit", "--what=sleep:idle", "--who=Knowledge Arc",
                                  "--why=Downloading the library", "--mode=block",
                                  "tail", f"--pid={os.getpid()}", "-f", "/dev/null"],
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            try:
                p.wait(timeout=1)   # still running after a second: the lock holds
            except subprocess.TimeoutExpired:
                return "This computer will be kept awake while it works (a laptop: keep it plugged in).", True
    except (OSError, AttributeError, ValueError):
        pass
    return ("Set this computer not to go to sleep until it has finished "
            "(a laptop: plugged in, lid open).", False)


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
    bad_sites = len(failed)
    if bad_sites == sites:
        return [(PROBLEM, "No website answered. Check the internet connection.")]
    lines = []
    kiwix = [s for s in failed if "kiwix" in s]
    if kiwix:
        lines.append((PROBLEM, "The Kiwix servers don't answer: the big collections "
                               "(Wikipedia, medicine, books...) can't be fetched now."))
    asked = f"{todo} items" if thorough else f"{sites} websites"
    if bad_sites:
        n = sum(len(v) for v in failed.values())
        lines.append((WARNING, f"{n} of {todo} items can't be fetched now; the arc is built without "
                               "them, and a later run adds them:"))
        for s, items in sorted(failed.items()):
            ids = ", ".join(r["id"] for r, _ in items[:8]) + (" ..." if len(items) > 8 else "")
            lines.append(("", f"  {s}: {items[0][1]} ({len(items)} items: {ids})"))
    else:
        lines.append((OK, f"Internet: all {asked} answer."))
    return lines
