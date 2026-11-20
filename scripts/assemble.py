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
import json
import os
import shutil
import subprocess
import sys
import tarfile
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import catalog_lib as cl  # noqa: E402
from download import sha256_file, human  # noqa: E402
import frontdoor  # noqa: E402
import libraryhome  # noqa: E402

DRIVE_FILES = Path(__file__).resolve().parent / "drive"   # verify tools for 99_SYSTEM
LAUNCHERS = cl.REPO / "launchers"                           # OPEN-LIBRARY for each system
# Kiwix server archives (tier 9 rows) and the folder each one is unpacked into.
# The launchers in launchers/ look for kiwix-serve in exactly these folders.
KIWIX_UNPACK = {
    "win-x86_64": "90_SOFTWARE/windows/kiwix",
    "macos-arm64": "90_SOFTWARE/mac/kiwix-arm64",
    "macos-x86_64": "90_SOFTWARE/mac/kiwix-x86_64",
    "linux-x86_64": "90_SOFTWARE/linux/kiwix",
}
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


def place(src, dst, staged_sha):
    """Make dst an exact copy of src, whose hash at download time was
    staged_sha. Every file on the drive is read once: a file that looks
    unchanged (same size and date) is still hashed, because bit rot does not
    change the date. Returns 'kept', 'copied' or 'repaired'; raises OSError if
    the copy does not match."""
    action = "copied"
    if dst.exists() and dst.stat().st_size == src.stat().st_size \
            and int(dst.stat().st_mtime) == int(src.stat().st_mtime):
        if sha256_file(dst) == staged_sha:
            return "kept"
        action = "repaired"
    dst.parent.mkdir(parents=True, exist_ok=True)
    tmp = dst.with_name(dst.name + ".part")
    shutil.copy2(src, tmp)
    os.replace(tmp, dst)
    if sha256_file(dst) != staged_sha:
        dst.unlink()
        raise OSError("the copy does not match the hash taken at download "
                      "(staging file damaged, or the drive is failing)")
    return action


def kiwix_target(rel):
    """Folder a kiwix-tools archive unpacks into, or None if rel isn't one."""
    name = rel.rsplit("/", 1)[-1]
    if not name.startswith("kiwix-tools_"):
        return None
    platform = name[len("kiwix-tools_"):].rsplit("-", 1)[0]   # e.g. win-x86_64
    return KIWIX_UNPACK.get(platform)


def unpack(archive, target):
    """Unpack the programs in a zip or tar.gz into target, flat (archive
    folders dropped, so no path tricks are possible). Replaces what was there."""
    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True)
    if archive.name.endswith(".zip"):
        with zipfile.ZipFile(archive) as z:
            for info in z.infolist():
                if not info.is_dir():
                    (target / Path(info.filename).name).write_bytes(z.read(info))
    else:
        with tarfile.open(archive, "r:gz") as t:
            for m in t.getmembers():
                if m.isfile():
                    out = target / Path(m.name).name
                    out.write_bytes(t.extractfile(m).read())
                    out.chmod(0o755)   # no effect on exFAT; kept for other file systems


def copy_launchers(drive):
    """OPEN-LIBRARY for each system, at the drive root, with the line endings
    each system needs whatever the clone's git settings."""
    names = []
    for src in sorted(LAUNCHERS.iterdir()) if LAUNCHERS.is_dir() else []:
        if src.name.startswith(".") or not src.is_file():
            continue
        text = src.read_bytes().replace(b"\r\n", b"\n")
        if src.suffix.lower() in (".bat", ".cmd"):
            text = text.replace(b"\n", b"\r\n")
        out = drive / src.name
        out.write_bytes(text)
        if src.suffix in (".sh", ".command"):
            out.chmod(0o755)
        names.append(src.name)
    return names


def recipe_version():
    try:
        out = subprocess.run(["git", "-C", str(cl.REPO), "describe", "--always", "--dirty"],
                             capture_output=True, text=True, timeout=10)
        return out.stdout.strip() or "unknown"
    except (OSError, subprocess.SubprocessError):
        return "unknown"


def write_checksums(drive, content_hashes):
    """Write CHECKSUMS.sha256 in the format `sha256sum -c` reads: hash, two
    spaces, path with forward slashes.

    Content folders: only the files of placed catalog items, with the hash
    taken at download time, so neither stray files nor decayed bytes get
    fingerprinted as good. Everything else (99_SYSTEM, front door, launchers,
    software) is hashed as it is now."""
    lines = [f"{sha}  {rel}\n" for rel, sha in content_hashes.items()]
    for path in drive.rglob("*"):
        rel = path.relative_to(drive).as_posix()
        if not path.is_file() or rel.split("/", 1)[0] in CONTENT_DIRS or rel in content_hashes:
            continue
        if rel == CHECKSUMS or rel.endswith(".part") or \
                rel.startswith(("System Volume Information/", "$RECYCLE.BIN/")):
            continue
        lines.append(f"{sha256_file(path)}  {rel}\n")
    lines.sort(key=lambda line: line[66:])
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
    ap.add_argument("--frontdoor", type=Path, default=frontdoor.FRONTDOOR,
                    help="folder with situations.csv, numbers.csv and drafts/ (tests use a fixture)")
    ap.add_argument("--prune", action="store_true",
                    help="delete files in the content folders that no placed catalog item accounts for")
    args = ap.parse_args(argv)

    fields, rows = cl.read_csv(args.catalog)
    publishers = {p["id"]: p for p in cl.read_csv(args.publishers)[1]}
    chosen = cl.select(rows, args.bundle, args.ids)
    staging, drive = args.staging.resolve(), args.drive.resolve()
    if not staging.is_dir():
        raise SystemExit(f"staging folder not found: {staging}")
    drive.mkdir(parents=True, exist_ok=True)

    placed, skipped, problems = [], [], []
    content_hashes = {}   # rel path -> staged sha, for placed items only
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
        actions, ok = [], True
        for rel, staged_sha in files:
            try:
                actions.append(place(staging / rel, drive / rel, staged_sha))
            except OSError as e:
                problems.append((row["id"], f"{rel}: {e}"))
                ok = False
        if ok:
            placed.append(row)
            content_hashes.update(dict(files))
            summary = ", ".join(f"{actions.count(a)} {a}" for a in ("copied", "repaired", "kept") if a in actions)
            print(f"[{row['id']}] {summary}: {row['title'][:70]}", flush=True)
            if "repaired" in actions:
                problems.append((row["id"], "a file on the drive had changed since it was copied "
                                            "(bit rot?) and was replaced from staging: check the drive's health"))

    # Files in the content folders that no placed catalog item accounts for.
    # They are never fingerprinted, so mirror.py never copies them.
    extras = []
    for top in CONTENT_DIRS:
        for p in (drive / top).rglob("*") if (drive / top).exists() else []:
            rel = p.relative_to(drive).as_posix()
            if p.is_file() and rel not in content_hashes:
                if args.prune:
                    p.unlink()
                else:
                    extras.append(rel)

    # Library server: unpack each placed kiwix-tools archive next to itself,
    # then add the launchers. No server on the drive, no launchers.
    unpacked = []
    for row in placed:
        target = kiwix_target(row["folder"])
        if target:
            try:
                unpack(drive / row["folder"], drive / target)
                unpacked.append(target)
            except (OSError, zipfile.BadZipFile, tarfile.TarError) as e:
                problems.append((row["id"], f"could not unpack {row['folder']}: {e}"))
    if unpacked:
        print(f"Library server unpacked: {', '.join(unpacked)}; "
              f"launchers: {', '.join(copy_launchers(drive))}")
        home = libraryhome.build(drive, placed, publishers)
        if home:
            print(f"Library home page: {home}")

    system = drive / SYSTEM
    system.mkdir(exist_ok=True)
    cl.write_csv_atomic(system / "CATALOG.csv", fields, placed)
    for tool in sorted(DRIVE_FILES.iterdir()):
        # Force line endings whatever the clone's git settings: Windows
        # scripts get CRLF, shell scripts LF.
        text = tool.read_bytes().replace(b"\r\n", b"\n")
        if tool.suffix.lower() in (".bat", ".cmd", ".ps1", ".txt"):
            text = text.replace(b"\n", b"\r\n")
        (system / tool.name).write_bytes(text)

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
    # Newest build first; earlier entries are kept as the drive's history.
    log = system / "VERSION.txt"
    previous = log.read_text(encoding="utf-8") if log.exists() else ""
    with open(log, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(version) + "\n" + ("\n" + previous if previous else ""))

    # Front door: built from what is actually on the drive, every run.
    frontdoor.build(drive, placed, {r["id"] for r in rows}, include_drafts=args.allow_pending,
                    version_line=f"{version[0]}. {version[2]}." + (" Test build." if args.allow_pending else ""),
                    folder=args.frontdoor)

    n = write_checksums(drive, content_hashes)

    print(f"\nOn the drive: {len(placed)} items, {n} files fingerprinted.")
    if skipped:
        print(f"Left off by the quality gate: {len(skipped)}")
        for rid, why in skipped:
            print(f"  {rid}: {why}")
    if extras:
        print(f"Files in the content folders with no placed catalog item ({len(extras)}). "
              "They are left out of CHECKSUMS.sha256 and won't be mirrored; "
              "run with --prune to delete them:")
        for e in extras[:20]:
            print(f"  {e}")
    if problems:
        print(f"PROBLEMS ({len(problems)}):")
        for rid, why in problems:
            print(f"  {rid}: {why}")
    return 1 if problems or extras else 0


if __name__ == "__main__":
    sys.exit(main())
