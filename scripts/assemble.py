"""Copy downloaded items from the archive (staging) folder onto a drive (or a
test folder), then write arc/system: CATALOG.csv, VERSION.txt, CHECKSUMS.sha256,
the verify tools, the maintenance guide and a copy of the recipe.

Drive layout (docs/architecture.md section 3): the top level holds only
"1 START-HERE.html", the two "2 Open full library" launchers and arc/.

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
import arczim  # noqa: E402
import frontdoor  # noqa: E402
import libraryhome  # noqa: E402

DRIVE_FILES = Path(__file__).resolve().parent / "drive"   # verify tools for arc/system
LAUNCHERS = cl.REPO / "launchers"
# Each launcher in launchers/ and where it goes on the drive. Names starting
# "1 " and "2 " sort the entry first in Windows Explorer and the Mac Finder.
LAUNCHER_DEST = {
    "open-full-library.bat": "2 Open full library (Windows).bat",
    "open-full-library.command": "2 Open full library (Mac).command",
    "open-full-library.sh": f"{cl.ARC}/open-full-library.sh",
    "firefox-user.js": f"{cl.ARC}/software/firefox-user.js",   # settings for the drive's Firefox
}
# Kiwix server archives (tier 9 rows) and the folder each one is unpacked into.
# The launchers look for kiwix-serve in exactly these folders.
KIWIX_UNPACK = {
    "win-x86_64": f"{cl.ARC}/software/windows/kiwix",
    "macos-arm64": f"{cl.ARC}/software/mac/kiwix-arm64",
    "macos-x86_64": f"{cl.ARC}/software/mac/kiwix-x86_64",
    "linux-x86_64": f"{cl.ARC}/software/linux/kiwix",
}
# Folders that hold only catalog items' files (fingerprinted with the hash
# taken at download time; anything else in them is a stray file).
CONTENT_DIRS = (f"{cl.ARC}/guides/", f"{cl.ARC}/collections/")
SYSTEM = f"{cl.ARC}/system"
CHECKSUMS = f"{SYSTEM}/CHECKSUMS.sha256"
RECIPE = f"{SYSTEM}/recipe"
# Repo files left out of the drive's recipe copy: owner to-dos, not for strangers.
RECIPE_EXCLUDE = {"NEXT-SESSION.md"}


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


# Other software archives: (file name start, folder, how). "flat" drops the
# archive's folders (a few programs side by side); "tree" keeps them (apps
# with libraries in subfolders); "firefox-exe" runs Mozilla's installer with
# its /ExtractDir switch, which extracts without installing (Windows only).
UNPACK_RULES = [
    ("sumatrapdf-", f"{cl.ARC}/software/windows/sumatrapdf", "flat"),
    ("kiwix-desktop_windows", f"{cl.ARC}/software/windows/kiwix-desktop", "tree"),
    ("firefox-setup-", f"{cl.ARC}/software/windows/firefox", "firefox-exe"),
    ("firefox-", f"{cl.ARC}/software/linux/firefox", "tree"),
]


def unpack_target(rel):
    """(folder, how) a software archive unpacks into, or None."""
    name = rel.rsplit("/", 1)[-1]
    if name.startswith("kiwix-tools_"):
        platform = name[len("kiwix-tools_"):].rsplit("-", 1)[0]   # e.g. win-x86_64
        return (KIWIX_UNPACK[platform], "flat") if platform in KIWIX_UNPACK else None
    for start, folder, how in UNPACK_RULES:
        if name.startswith(start):
            return folder, how
    return None


def kiwix_target(rel):
    """Folder a kiwix-tools archive unpacks into, or None if rel isn't one."""
    t = unpack_target(rel)
    return t[0] if t and rel.rsplit("/", 1)[-1].startswith("kiwix-tools_") else None


def safe_parts(name):
    """An archive member's path as parts, or None if it could escape the
    target (absolute, drive letter, ..)."""
    name = name.replace("\\", "/")
    parts = [p for p in name.split("/") if p not in ("", ".")]
    if not parts or name.startswith("/") or ":" in parts[0] or ".." in parts:
        return None
    return parts


def unpack_tree(archive, target):
    """Unpack a zip or tar (gz, xz) keeping its folders, minus one top folder
    shared by every member. Members that could escape target are skipped."""
    if archive.name.endswith(".zip"):
        with zipfile.ZipFile(archive) as z:
            members = [(m.filename, m, False) for m in z.infolist() if not m.is_dir()]
            _write_tree(target, members, z.read)
    else:
        with tarfile.open(archive, "r:*") as t:
            members = [(m.name, m, bool(m.mode & 0o111)) for m in t.getmembers() if m.isfile()]
            _write_tree(target, members, lambda m: t.extractfile(m).read())


def _write_tree(target, members, read):
    paths = [(safe_parts(name), m, x) for name, m, x in members]
    paths = [(p, m, x) for p, m, x in paths if p]
    tops = {p[0] for p, _, _ in paths}
    strip = 1 if len(tops) == 1 and all(len(p) > 1 for p, _, _ in paths) else 0
    for parts, m, executable in paths:
        out = target.joinpath(*parts[strip:])
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(read(m))
        if executable:
            out.chmod(0o755)   # no effect on exFAT; kept for other file systems


def unpack_firefox_installer(archive, target):
    """Mozilla publishes no portable zip for Windows: its installer extracts
    the program without installing it (/ExtractDir); the program is core/."""
    if os.name != "nt":
        raise OSError("the Windows Firefox installer can only be unpacked on a Windows build machine")
    tmp = target.with_name(target.name + ".extract")
    if tmp.exists():
        shutil.rmtree(tmp)
    subprocess.run([str(archive), f"/ExtractDir={tmp}"], check=True, timeout=900)
    if not (tmp / "core" / "firefox.exe").is_file():
        raise OSError("the installer did not extract core/firefox.exe")
    os.replace(tmp / "core", target)
    shutil.rmtree(tmp)


def unpack(archive, target, how="flat"):
    """Unpack a software archive into target, replacing what was there
    (every build, so the unpacked copy always matches the checked archive).
    "flat" drops the archive's folders, so no path tricks are possible."""
    if target.exists():
        shutil.rmtree(target)
    if how == "tree":
        target.mkdir(parents=True)
        return unpack_tree(archive, target)
    if how == "firefox-exe":
        target.parent.mkdir(parents=True, exist_ok=True)
        return unpack_firefox_installer(archive, target)
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
    """The launchers, under their drive names (LAUNCHER_DEST), with the line
    endings each system needs whatever the clone's git settings."""
    names = []
    for src_name, dest in LAUNCHER_DEST.items():
        src = LAUNCHERS / src_name
        if not src.is_file():
            continue
        text = src.read_bytes().replace(b"\r\n", b"\n")
        if src.suffix.lower() in (".bat", ".cmd"):
            text = text.replace(b"\n", b"\r\n")
        out = drive / dest
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(text)
        if src.suffix in (".sh", ".command"):
            out.chmod(0o755)
        names.append(dest)
    return names


def recipe_files(repo):
    """Relative paths of the recipe's files: what git tracks, or, in a folder
    that is not a git repository (such as a drive's own recipe copy), every
    file except git and Python cache files. RECIPE_EXCLUDE is left out."""
    rels = []
    try:
        out = subprocess.run(["git", "-C", str(repo), "ls-files", "-z"],
                             capture_output=True, timeout=30, check=True)
        rels = [r for r in out.stdout.decode("utf-8").split("\0") if r]
    except (OSError, subprocess.SubprocessError):
        pass
    if not rels:
        for path in repo.rglob("*"):
            rel = path.relative_to(repo).as_posix()
            parts = rel.split("/")
            if path.is_file() and ".git" not in parts and "__pycache__" not in parts \
                    and not rel.endswith(".pyc"):
                rels.append(rel)
    return sorted(r for r in rels if r not in RECIPE_EXCLUDE and (repo / r).is_file())


def copy_recipe(drive, repo=cl.REPO):
    """Copy the build recipe to arc/system/recipe, so whoever holds a copy can
    refresh or rebuild it (MAINTENANCE.txt Part 2). Returns the number of
    files. Refuses to run from the target drive's own recipe copy, which it
    would delete while running."""
    repo, target = Path(repo).resolve(), (drive / RECIPE).resolve()
    if repo == target or target in repo.parents:
        raise ValueError("this build runs from the drive's own recipe copy: copy "
                         "arc/system/recipe to the computer first, then run it from there")
    files = recipe_files(repo)
    if target.exists():
        shutil.rmtree(target)
    for rel in files:
        dst = target / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(repo / rel, dst)
    return len(files)


def top_level_extras(drive):
    """Entries at the top of the drive other than the entry files and arc/
    (system folders aside). Reported, never deleted: they may be someone's."""
    allowed = {frontdoor.HTML_NAME, cl.ARC, "System Volume Information", "$RECYCLE.BIN"} | \
        {dest for dest in LAUNCHER_DEST.values() if "/" not in dest}
    return sorted(p.name for p in drive.iterdir() if p.name not in allowed)


def build_arc_zim(drive, placed, all_ids, version_line, folder, publishers, facts, edition=None):
    """Write arc/site/<arczim.FILE_NAME>; return its drive path."""
    books = [arczim.BOOK] + libraryhome.search_books(drive, placed, publishers, facts)
    pages, linked = frontdoor.build_served(drive, placed, all_ids, version_line, folder, publishers, books,
                                           edition=edition)
    names = {}   # drive path -> title shown in the library
    for r in placed:
        names[r["folder"]] = frontdoor.display(r)
    files = []
    for rel in linked:
        if not (drive / rel).is_file():
            continue
        owner = names.get(rel) or names.get(rel.rsplit("/", 1)[0])
        title = owner if rel in names else (f"{owner}: {Path(rel).stem}" if owner else Path(rel).name)
        files.append((frontdoor.zim_path(rel), drive / rel, title))
    out = f"{frontdoor.SITE}/{arczim.FILE_NAME}"
    n = arczim.build(drive / out, pages, files, "Knowledge Arc",
                     "Offline library: subjects, topics and guides", dt.date.today().isoformat(),
                     frontdoor.guide_page)
    print(f"  {len(pages)} pages and {len(files)} files packed ({n} entries)")
    return out


def recipe_version():
    try:
        out = subprocess.run(["git", "-C", str(cl.REPO), "describe", "--always", "--dirty"],
                             capture_output=True, text=True, timeout=10)
        return out.stdout.strip() or "unknown"
    except (OSError, subprocess.SubprocessError):
        return "unknown"


def write_checksums(drive, content_hashes, stray_top=()):
    """Write CHECKSUMS.sha256 in the format `sha256sum -c` reads: hash, two
    spaces, path with forward slashes.

    Content folders: only the files of placed catalog items, with the hash
    taken at download time, so neither stray files nor decayed bytes get
    fingerprinted as good. Everything else (arc/system, front door, launchers,
    software) is hashed as it is now. Entries in stray_top (unexpected things
    at the top of the drive) are left out."""
    lines = [f"{sha}  {rel}\n" for rel, sha in content_hashes.items()]
    for path in drive.rglob("*"):
        rel = path.relative_to(drive).as_posix()
        if not path.is_file() or rel.startswith(CONTENT_DIRS) or rel in content_hashes:
            continue
        if rel.split("/", 1)[0] in stray_top:
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
                    help="delete files in arc/guides and arc/collections that no placed catalog item accounts for")
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
        top = top.rstrip("/")
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
        rule = unpack_target(row["folder"])
        if rule:
            target, how = rule
            try:
                unpack(drive / row["folder"], drive / target, how)
                unpacked.append(target)
            except (OSError, subprocess.SubprocessError, zipfile.BadZipFile, tarfile.TarError) as e:
                problems.append((row["id"], f"could not unpack {row['folder']}: {e}"))
    # The arc's own collection (arczim.py) needs optional packages.
    arc_ok, arc_why = arczim.available()
    facts = libraryhome.zim_facts(drive, [r["folder"] for r in libraryhome.placed_zims(drive, placed)])
    if unpacked:
        print(f"Library server unpacked: {', '.join(unpacked)}; "
              f"launchers: {', '.join(copy_launchers(drive))}")
        home = libraryhome.build(drive, placed, publishers, facts, arczim.BOOK if arc_ok else None)
        if home:
            print(f"Library home page: {home}")

    system = drive / SYSTEM
    system.mkdir(parents=True, exist_ok=True)
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

    try:
        if not copy_recipe(drive):
            problems.append(("recipe", "no recipe files found: arc/system/recipe is empty"))
    except ValueError as e:
        problems.append(("recipe", str(e)))

    # Front door: built from what is actually on the drive, every run.
    frontdoor.build(drive, placed, {r["id"] for r in rows}, include_drafts=args.allow_pending,
                    version_line=f"{version[0]}. {version[2]}." + (" Test build." if args.allow_pending else ""),
                    folder=args.frontdoor, publishers=publishers,
                    arc_zim=f"{frontdoor.SITE}/{arczim.FILE_NAME}" if arc_ok else None, edition=args.bundle)

    # The arc's own collection: the same pages, served by the library, with
    # the guides inside and their text searchable. Built after the pages,
    # because frontdoor.build() clears arc/site.
    if arc_ok:
        try:
            out = build_arc_zim(drive, placed, {r["id"] for r in rows}, version[0], args.frontdoor,
                                publishers, facts, edition=args.bundle)
            print(f"The arc's own collection: {out}")
        except Exception as e:   # the rest of the drive is still good
            problems.append(("arc collection", f"{arczim.FILE_NAME} was not built: {e}"))
    else:
        print(f"NOTE: {arc_why}")

    stray_top = top_level_extras(drive)
    n = write_checksums(drive, content_hashes, stray_top)

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
    if stray_top:
        print(f"Unexpected things at the top of the drive ({len(stray_top)}). The top should hold only "
              f"{frontdoor.HTML_NAME}, the launchers and {cl.ARC}/. They are left out of CHECKSUMS.sha256 "
              "and won't be mirrored; move or delete them by hand:")
        for e in stray_top:
            print(f"  {e}")
    if problems:
        print(f"PROBLEMS ({len(problems)}):")
        for rid, why in problems:
            print(f"  {rid}: {why}")
    return 1 if problems or extras or stray_top else 0


if __name__ == "__main__":
    sys.exit(main())
