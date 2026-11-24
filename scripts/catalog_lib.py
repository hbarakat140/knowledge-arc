"""Shared helpers for the build scripts: read the catalog, pick a bundle,
write the catalog back safely. Standard library only."""

import csv
import os
import re
import ssl
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
CATALOG = REPO / "catalog" / "catalog.csv"
PUBLISHERS = REPO / "catalog" / "publishers.csv"
COVERAGE = REPO / "catalog" / "coverage.csv"

# On the drive everything but the entry files lives under arc/; catalog
# `folder` values are paths from the drive root, so they start with "arc/":
#   arc/guides/<subject>/...   PDFs (one folder per subject in subjects.csv)
#   arc/collections/<name>.zim ZIM collections
#   arc/software/<os>/...      the Kiwix server and app
ARC = "arc"
SUBJECTS = REPO / "catalog" / "subjects.csv"
# The pocket kit, on drives bigger than pocket: the pocket edition's own pages,
# its pocket-only files and its file list, laid out as on a pocket drive.
# "Make a pocket copy" copies a pocket drive from it and the drive's own files.
KIT = f"{ARC}/pocket"
POCKET_COPY_WINDOWS = f"{ARC}/Make a pocket copy (Windows).bat"
POCKET_COPY_MAC = f"{ARC}/Make a pocket copy (Mac).command"

# Navigation tags (docs/architecture.md section 4). A row's `topic` lists
# coverage ids separated by ";", its home topic first; `job` is its role in
# that home topic (CONTRIBUTING.md rule 8). Software rows have no topic and no job.
SHELVES = {
    "guides": "Guides & manuals",
    "books": "Books",
    "encyclopedias": "Encyclopedias",
    "courses": "Courses",
    "videos": "Videos",
    "films": "Films",
    "music": "Music & audio",
    "maps": "Maps",
    "community": "Community answers",
    "software": "Software",
}
MAC_ROOTS = "/System/Library/Keychains/SystemRootCertificates.keychain"
_SSL = None


def add_mac_roots(ctx, run=subprocess.run):
    """Load the Mac's own root certificates into ctx. Returns how many."""
    try:
        pem = run(["security", "find-certificate", "-a", "-p", MAC_ROOTS],
                  capture_output=True, text=True, timeout=60).stdout
    except (OSError, subprocess.SubprocessError):
        return 0
    added = 0
    end = "-----END CERTIFICATE-----"
    for block in pem.split(end)[:-1]:
        try:
            ctx.load_verify_locations(cadata=block[block.index("-----BEGIN"):] + end + "\n")
            added += 1
        except (ValueError, ssl.SSLError):
            pass   # one certificate Python can't read: skip it, keep the others
    return added


def ssl_context():
    """The HTTPS settings for every download. Python from python.org on a Mac
    has no certificates until its "Install Certificates" step has been run,
    and then every download fails; in that case the Mac's own root
    certificates are used instead, so nobody has to know about that step."""
    global _SSL
    if _SSL is None:
        _SSL = ssl.create_default_context()
        if sys.platform == "darwin" and not _SSL.cert_store_stats().get("x509"):
            add_mac_roots(_SSL)
    return _SSL


AUDIENCES = ["all", "children", "advanced"]
JOBS = ["primary", "depth", "cross-check", "gap-filler", "copy"]

# The paper set (24 Nov 2026): `first` is printed before anything else (a
# small binder), `more` when there is paper and ink to spare. Blank: not
# suggested for printing. The page "Print a paper copy" lists them in order.
PAPER = ["first", "more"]
PAPER_FIRST_MAX = 400     # pages: the first binder stays one binder
PAPER_MORE_MAX = 2000     # pages: the second set stays printable at home

_PAGES = re.compile(r"\b(one|\d[\d,]*) (?:[a-z]+ )?pages?\b", re.I)


def pages(row):
    """The item's page count, from its `about` line ("32 pages.", "76
    illustrated pages.", "One page: ..."), or None."""
    m = _PAGES.search(row.get("about", ""))
    if not m:
        return None
    n = m.group(1).replace(",", "")
    return 1 if n.lower() == "one" else int(n)


def topics(row):
    """The row's topic ids, home topic first."""
    return [t for t in row.get("topic", "").split(";") if t]


def sections(topic_row):
    """A topic's section headings, in order (coverage.csv `sections`). A big
    topic is split into sections; an item's `section` names one of its home
    topic's sections, or is blank."""
    return [s for s in topic_row.get("sections", "").split(";") if s]

# Each bundle includes the ones before it. "decision" rows are never picked
# by bundle; the owner moves them to a real bundle first.
BUNDLES = ["pocket", "core", "standard", "full"]

_REPLACES = re.compile(r"REPLACES (T\d-\d{3})(?:\.\.(T\d-\d{3}))?")


def read_csv(path):
    with open(path, encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        return reader.fieldnames, list(reader)


def write_csv_atomic(path, fieldnames, rows):
    """Write to a temp file in the same folder, then replace, so an
    interrupted run never leaves a half-written catalog. LF line endings."""
    path = Path(path)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=path.name, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=fieldnames, lineterminator="\n")
            w.writeheader()
            w.writerows(rows)
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise


def _id_range(first, last):
    """'T3-030', 'T3-035' -> {'T3-030', ..., 'T3-035'}"""
    if not last:
        return {first}
    prefix = first[:3]
    if last[:3] != prefix:
        raise ValueError(f"range spans tiers: {first}..{last}")
    return {f"{prefix}{n:03d}" for n in range(int(first[3:]), int(last[3:]) + 1)}


def replaced_ids(row):
    """IDs this row replaces, from 'REPLACES T3-030..T3-035' in its notes."""
    out = set()
    for first, last in _REPLACES.findall(row["notes"]):
        out |= _id_range(first, last)
    return out


def select(rows, bundle=None, ids=None):
    """Rows for a bundle (cumulative, with replacements applied) or an explicit
    list of IDs. Explicit IDs win and ignore bundles."""
    if ids:
        wanted = set(ids)
        unknown = wanted - {r["id"] for r in rows}
        if unknown:
            raise SystemExit(f"Unknown id(s): {', '.join(sorted(unknown))}")
        return [r for r in rows if r["id"] in wanted]
    if bundle == "all":
        # Every row some edition needs, replaced ones included: a bigger
        # edition's replacement doesn't remove a smaller edition's item from
        # the archive (e.g. the pocket edition's short Wikipedia).
        return [r for r in rows if r["bundle"] in BUNDLES]
    if bundle not in BUNDLES:
        raise SystemExit(f"--bundle must be one of {BUNDLES}")
    allowed = set(BUNDLES[: BUNDLES.index(bundle) + 1])
    picked = [r for r in rows if r["bundle"] in allowed]
    dropped = set()
    for r in picked:
        dropped |= replaced_ids(r)
    return [r for r in picked if r["id"] not in dropped]


def drive_rows(rows, bundle):
    """(edition rows, pocket-only rows) a drive of this edition holds. A drive
    bigger than pocket also carries the pocket kit (KIT), so a pocket copy can
    be made from it with no internet: the pocket-only rows are the pocket
    edition's rows that the bigger edition replaced (the short Wikipedia).
    They sit at KIT/<folder>, where the drive's own library never sees them."""
    chosen = select(rows, bundle)
    if bundle in (None, "pocket", "all"):
        return chosen, []
    ids = {r["id"] for r in chosen}
    return chosen, [r for r in select(rows, "pocket") if r["id"] not in ids]


def on_drive(drive, rel, overlay=None):
    """The file for drive path rel: overlay/rel if it exists (the pocket kit,
    when building the kit's pages), else drive/rel."""
    if overlay is not None and (Path(overlay) / rel).exists():
        return Path(overlay) / rel
    return Path(drive) / rel


def file_count(row):
    """'pdf (32 files)' -> 32; plain 'pdf' or 'zim' -> 1."""
    m = re.search(r"\((\d+) files?\)", row["format"])
    return int(m.group(1)) if m else 1


def is_multi_file(row):
    return file_count(row) > 1


# A multi-file item that is not a Hesperian book has its files pinned in
# catalog/files/<id>.csv (file, label, url, updated): download.py fetches
# exactly those, the website shows each file by its label, in that order.
FILE_LISTS = REPO / "catalog" / "files"
SAFE_FILE_NAME = re.compile(r"^[a-z0-9][a-z0-9-]*_[a-z]+\.pdf$")


def file_list(row, folder=None):
    """[{file, label, url, updated}] pinned for this row, or [] if none."""
    path = Path(folder or FILE_LISTS) / f"{row['id']}.csv"
    return read_csv(path)[1] if path.is_file() else []


def part_labels(row, folder=None):
    """{file name: label} for a row with a pinned file list (else {})."""
    return {f["file"]: f["label"] for f in file_list(row, folder)}
