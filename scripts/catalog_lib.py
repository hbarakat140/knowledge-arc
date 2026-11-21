"""Shared helpers for the build scripts: read the catalog, pick a bundle,
write the catalog back safely. Standard library only."""

import csv
import os
import re
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

# Navigation tags (docs/architecture.md section 4). A row's `topic` lists
# coverage ids separated by ";", its home topic first; `job` is its role in
# that home topic (CLAUDE.md rule 8). Software rows have no topic and no job.
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
AUDIENCES = ["all", "children", "advanced"]
JOBS = ["primary", "depth", "cross-check", "gap-filler", "copy"]


def topics(row):
    """The row's topic ids, home topic first."""
    return [t for t in row.get("topic", "").split(";") if t]

# Each bundle includes the ones before it. "decision" rows are never picked
# by bundle; the owner moves them to a real bundle first.
BUNDLES = ["core", "standard", "full"]

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
    if bundle not in BUNDLES:
        raise SystemExit(f"--bundle must be one of {BUNDLES}")
    allowed = set(BUNDLES[: BUNDLES.index(bundle) + 1])
    picked = [r for r in rows if r["bundle"] in allowed]
    dropped = set()
    for r in picked:
        dropped |= replaced_ids(r)
    return [r for r in picked if r["id"] not in dropped]


def file_count(row):
    """'pdf (32 files)' -> 32; plain 'pdf' or 'zim' -> 1."""
    m = re.search(r"\((\d+) files?\)", row["format"])
    return int(m.group(1)) if m else 1


def is_multi_file(row):
    return file_count(row) > 1
