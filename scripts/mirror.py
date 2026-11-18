"""Copy a finished, verified master drive to another drive, then check every
file on the copy against the master's CHECKSUMS.sha256.

    python scripts/mirror.py --master E:/ --copy F:/

Only files listed in the master's CHECKSUMS.sha256 are copied, so stray files
on the master never spread. Files already on the copy with the same size and
date are not copied again, but every file is still hashed.
Files on the copy that the master doesn't list are reported, not deleted.
"""

import argparse
import os
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from download import sha256_file  # noqa: E402
from assemble import CHECKSUMS  # noqa: E402


def read_checksums(drive):
    path = drive / CHECKSUMS
    if not path.exists():
        raise SystemExit(f"{path} not found: assemble the master first")
    entries = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            entries.append((line[:64], line[66:]))
    return entries


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--master", required=True, type=Path)
    ap.add_argument("--copy", required=True, type=Path)
    args = ap.parse_args(argv)
    master, copy = args.master.resolve(), args.copy.resolve()
    if master == copy:
        raise SystemExit("master and copy are the same folder")

    entries = read_checksums(master)
    listed = {rel for _, rel in entries} | {CHECKSUMS}
    bad, copied = [], 0
    for i, (sha, rel) in enumerate(entries + [(None, CHECKSUMS)], 1):
        src, dst = master / rel, copy / rel
        if not (dst.exists() and dst.stat().st_size == src.stat().st_size
                and int(dst.stat().st_mtime) == int(src.stat().st_mtime)):
            dst.parent.mkdir(parents=True, exist_ok=True)
            tmp = dst.with_name(dst.name + ".part")
            shutil.copy2(src, tmp)
            os.replace(tmp, dst)
            copied += 1
        if sha and sha256_file(dst) != sha:
            bad.append(rel)
        if i % 50 == 0:
            print(f"  {i} / {len(entries) + 1}", flush=True)

    extras = [p.relative_to(copy).as_posix() for p in copy.rglob("*")
              if p.is_file() and p.relative_to(copy).as_posix() not in listed
              and not p.relative_to(copy).as_posix().startswith(("System Volume Information/", "$RECYCLE.BIN/"))]
    print(f"\nCopied {copied} files; checked {len(entries)}.")
    if extras:
        print(f"Files on the copy that the master doesn't have ({len(extras)}): delete them by hand")
        for e in extras[:20]:
            print(f"  {e}")
    if bad:
        print(f"DAMAGED on the copy ({len(bad)}): run again, or replace the drive")
        for b in bad:
            print(f"  {b}")
        return 1
    print("The copy matches the master.")
    return 1 if extras else 0


if __name__ == "__main__":
    sys.exit(main())
