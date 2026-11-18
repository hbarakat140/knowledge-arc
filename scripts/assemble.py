"""Copy downloaded items from the staging folder onto a drive (or a test
folder), then write 99_SYSTEM: CATALOG.csv, VERSION.txt, CHECKSUMS.sha256 and
the verify tools.

    python scripts/assemble.py --staging D:/staging --drive E:/ --bundle core
    python scripts/assemble.py --staging D:/staging --drive E:/ --bundle core --allow-pending

The quality gate: an item goes on the drive only if its publisher is
`approved` and its row has a reviewer (not `pending-owner`). Until the owner
signs off, `--allow-pending` also accepts `approved-pending-owner` publishers
and unsigned rows: use it for test drives only. `candidate` and
`excluded-licence` publishers never go on; `item-review-required` items need a
signed-off row.

Every file copied is re-hashed on the drive and compared with the hash taken
at download time, so a bad copy is caught here, not years later.
"""

import argparse
import datetime as dt
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import catalog_lib as cl  # noqa: E402
from download import sha256_file, human  # noqa: E402

DRIVE_FILES = Path(__file__).resolve().parent / "drive"   # verify tools for 99_SYSTEM
CONTENT_DIRS = ("00_EMERGENCY", "01_LIVING", "02_KNOWLEDGE")
SYSTEM = "99_SYSTEM"
CHECKSUMS = f"{SYSTEM}/CHECKSUMS.sha256"


def gate(row, publishers, allow_pending):
    """Return None if the row may go on the drive, else the reason it can't."""
    pub = publishers.get(row["publisher"])
    if pub is None:
        return f"publisher '{row['publisher']}' not in publishers.csv"
    status = pub["status"]
    signed = row["reviewer"].strip() not in ("", "pending-owner")
    if status == "approved":
        return None if (signed or allow_pending) else "row not signed off (reviewer)"
    if status == "approved-pending-owner":
        return None if allow_pending else "publisher not signed off yet"
    if status == "item-review-required":
        return None if signed else "needs an individual review"
    return f"publisher status is {status}"


def staged_files(row, staging):
    """(relative path, staged sha) for every file of a row, from the
    downloader's state file. Raises if anything is missing."""
    state_path = staging / ".download-state.json"
    state = json.loads(state_path.read_text(encoding="utf-8")) if state_path.exists() else {}
    folder = row["folder"].strip("/")
    if cl.is_multi_file(row):
        files = sorted((rel, e["sha256"]) for rel, e in state.items()
                       if rel.startswith(folder + "/"))
        if len(files) != cl.file_count(row):
            raise FileNotFoundError(f"{len(files)} of {cl.file_count(row)} files staged in {folder}")
    else:
        if folder not in state:
            raise FileNotFoundError(f"{folder} not downloaded (or not checked) in staging")
        files = [(folder, state[folder]["sha256"])]
    for rel, _ in files:
        if not (staging / rel).exists():
            raise FileNotFoundError(f"{rel} is in the state file but missing from staging")
    return files


def copy_if_needed(src, dst):
    if dst.exists() and dst.stat().st_size == src.stat().st_size \
            and int(dst.stat().st_mtime) == int(src.stat().st_mtime):
        return False
    dst.parent.mkdir(parents=True, exist_ok=True)
    tmp = dst.with_name(dst.name + ".part")
    shutil.copy2(src, tmp)
    os.replace(tmp, dst)
    return True


def recipe_version():
    try:
        out = subprocess.run(["git", "-C", str(cl.REPO), "describe", "--always", "--dirty"],
                             capture_output=True, text=True, timeout=10)
        return out.stdout.strip() or "unknown"
    except (OSError, subprocess.SubprocessError):
        return "unknown"


def write_checksums(drive):
    """Hash every file on the drive except the checksum list itself, in the
    format `sha256sum -c` reads: hash, two spaces, path with forward slashes."""
    lines = []
    for path in sorted(p for p in drive.rglob("*") if p.is_file()):
        rel = path.relative_to(drive).as_posix()
        if rel == CHECKSUMS or rel.endswith(".part") or rel.startswith(("System Volume Information/", "$RECYCLE.BIN/")):
            continue
        lines.append(f"{sha256_file(path)}  {rel}\n")
    out = drive / CHECKSUMS
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8", newline="\n") as f:
        f.writelines(lines)
    return len(lines)


def main(argv=None):
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--staging", required=True, type=Path)
    ap.add_argument("--drive", required=True, type=Path, help="drive root, or a test folder")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--bundle", choices=cl.BUNDLES)
    g.add_argument("--ids", nargs="+")
    ap.add_argument("--catalog", type=Path, default=cl.CATALOG)
    ap.add_argument("--publishers", type=Path, default=cl.PUBLISHERS)
    ap.add_argument("--allow-pending", action="store_true",
                    help="TEST DRIVES ONLY: include items not yet signed off by the owner")
    ap.add_argument("--note", default="", help="one line for VERSION.txt (what changed)")
    args = ap.parse_args(argv)

    fields, rows = cl.read_csv(args.catalog)
    publishers = {p["id"]: p for p in cl.read_csv(args.publishers)[1]}
    chosen = cl.select(rows, args.bundle, args.ids)
    staging, drive = args.staging.resolve(), args.drive.resolve()
    if not staging.is_dir():
        raise SystemExit(f"staging folder not found: {staging}")
    drive.mkdir(parents=True, exist_ok=True)

    placed, skipped, problems = [], [], []
    expected_paths = set()
    for row in chosen:
        reason = gate(row, publishers, args.allow_pending)
        if reason:
            skipped.append((row["id"], reason))
            continue
        try:
            files = staged_files(row, staging)
        except FileNotFoundError as e:
            problems.append((row["id"], str(e)))
            continue
        copied = 0
        bad = False
        for rel, staged_sha in files:
            src, dst = staging / rel, drive / rel
            if copy_if_needed(src, dst):
                copied += 1
                if sha256_file(dst) != staged_sha:
                    problems.append((row["id"], f"copy of {rel} does not match the staged file"))
                    dst.unlink()
                    bad = True
            expected_paths.add(rel)
        if not bad:
            placed.append(row)
            print(f"[{row['id']}] {'copied' if copied else 'already on drive'}: {row['title'][:70]}", flush=True)

    # Files in the content folders that no placed catalog row accounts for.
    extras = []
    for top in CONTENT_DIRS:
        for p in (drive / top).rglob("*") if (drive / top).exists() else []:
            if p.is_file() and p.relative_to(drive).as_posix() not in expected_paths:
                extras.append(p.relative_to(drive).as_posix())

    system = drive / SYSTEM
    system.mkdir(exist_ok=True)
    cl.write_csv_atomic(system / "CATALOG.csv", fields, placed)
    for tool in sorted(DRIVE_FILES.iterdir()):
        shutil.copyfile(tool, system / tool.name)

    total = sum(int(r["size_bytes"] or 0) for r in placed)
    version = [
        f"Built: {dt.datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"Selection: {'bundle ' + args.bundle if args.bundle else 'ids ' + ' '.join(args.ids)}",
        f"Items: {len(placed)} ({human(total)})",
        f"Recipe version (git): {recipe_version()}",
    ]
    if args.allow_pending:
        version.append("TEST BUILD: includes items the owner has not signed off yet.")
    if args.note:
        version.append(f"Changes: {args.note}")
    with open(system / "VERSION.txt", "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(version) + "\n")

    print("\nHashing every file on the drive for CHECKSUMS.sha256 ...", flush=True)
    n = write_checksums(drive)

    print(f"\nOn the drive: {len(placed)} items, {n} files fingerprinted.")
    if skipped:
        print(f"Left off by the quality gate: {len(skipped)}")
        for rid, why in skipped:
            print(f"  {rid}: {why}")
    if extras:
        print(f"Files on the drive with no catalog row ({len(extras)}): remove them or add rows")
        for e in extras[:20]:
            print(f"  {e}")
    if problems:
        print(f"PROBLEMS ({len(problems)}):")
        for rid, why in problems:
            print(f"  {rid}: {why}")
    return 1 if problems or extras else 0


if __name__ == "__main__":
    sys.exit(main())
