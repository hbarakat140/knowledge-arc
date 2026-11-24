"""Copy downloaded items from the archive (staging) folder onto a drive (or a
test folder), then write arc/system: CATALOG.csv, VERSION.txt, CHECKSUMS.sha256,
the verify tools, the maintenance guide and a copy of the recipe.

Drive layout (docs/architecture.md section 3): the top level holds only
"1 START-HERE.html", the two "2 Open full library" launchers and arc/.

    python scripts/assemble.py --staging D:/staging --drive E:/ --bundle core
    python scripts/assemble.py --staging E:/ --drive E:/ --bundle core     (one drive: downloaded in place)

The quality gate is the catalog (owner, 21 Nov 2026): every row of the
chosen edition goes on the drive if its publisher is `approved`,
`approved-pending-owner` or `item-review-required` (community answers, which
the website keeps in their own labelled area). `candidate`, `excluded-licence`
and unknown publishers never go on. The `reviewer` column records sign-offs;
it is not a gate. `--allow-pending` makes a test build: it adds the draft
notes in frontdoor/drafts (not yet checked) and marks every page TEST BUILD.

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
    # Advanced, so inside arc/: phones on the same Wi-Fi read the library.
    "share-over-wifi.bat": f"{cl.ARC}/Share over Wi-Fi (Windows).bat",
    "share-over-wifi.command": f"{cl.ARC}/Share over Wi-Fi (Mac).command",
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
# taken at download time; anything else in them is a stray file), on the drive
# and in the pocket kit.
CONTENT_DIRS = (f"{cl.ARC}/guides/", f"{cl.ARC}/collections/",
                f"{cl.KIT}/{cl.ARC}/guides/", f"{cl.KIT}/{cl.ARC}/collections/")
SYSTEM = f"{cl.ARC}/system"
# The downloader's record at the top of its folder: on a one-drive build it
# sits at the top of the drive (and in the kit, for the kit's own rows).
# Allowed there, never fingerprinted.
DOWNLOAD_STATE = (".download-state.json", ".download-state.tmp")
KIT_STATE = tuple(f"{cl.KIT}/{name}" for name in DOWNLOAD_STATE)
CHECKSUMS = f"{SYSTEM}/CHECKSUMS.sha256"
KIT_CHECKSUMS = f"{cl.KIT}/{CHECKSUMS}"   # the pocket copy's file list, in sha256sum format
# "Make a pocket copy", only on drives that carry the pocket kit.
POCKET_COPY_DEST = {
    "make-pocket-copy.bat": cl.POCKET_COPY_WINDOWS,
    "make-pocket-copy.command": cl.POCKET_COPY_MAC,
    "make-pocket-copy.ps1": f"{SYSTEM}/make-pocket-copy.ps1",
    "make-pocket-copy.sh": f"{SYSTEM}/make-pocket-copy.sh",
}
# Files each edition writes for itself: a pocket copy takes the kit's, never
# the bigger drive's (with everything in arc/site).
EDITION_FILES = {frontdoor.HTML_NAME, frontdoor.TXT_NAME, f"{SYSTEM}/CATALOG.csv", f"{SYSTEM}/VERSION.txt",
                 libraryhome.HOME}
RECIPE = f"{SYSTEM}/recipe"
# Repo files left out of the drive's recipe copy: owner to-dos, not for strangers.
RECIPE_EXCLUDE = {"NEXT-SESSION.md", "CLAUDE.md"}   # local working notes, never part of the recipe
# Working folders at the top of the repo (.gitignore), never part of the recipe.
RECIPE_WORK_DIRS = {"downloads", "staging", "build", "drive", "cache"}


# Publisher statuses whose catalog rows go on the drive.
ON_THE_DRIVE = ("approved", "approved-pending-owner", "item-review-required")


def gate(row, publishers):
    """Return None if the row may go on the drive, else the reason it can't.
    The catalog is the gate: a row is there because it was checked and
    chosen; sign-offs (`reviewer`) are a record, not a condition."""
    pub = publishers.get(row["publisher"])
    if pub is None:
        return f"publisher '{row['publisher']}' not in publishers.csv"
    if pub["status"] in ON_THE_DRIVE:
        return None
    return f"publisher status is {pub['status']}"


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


def newer_versions(staging, placed):
    """(drive path, file actually downloaded) for placed collections that
    download.py replaced with a newer version of the same collection."""
    state_path = staging / ".download-state.json"
    state = json.loads(state_path.read_text(encoding="utf-8")) if state_path.exists() else {}
    return [(r["folder"], state[r["folder"]]["source"]) for r in placed
            if state.get(r["folder"], {}).get("source")]


def place(src, dst, staged_sha):
    """Make dst an exact copy of src, whose hash at download time was
    staged_sha. Every file on the drive is read once: a file that looks
    unchanged (same size and date) is still hashed, because bit rot does not
    change the date. Returns 'kept', 'copied' or 'repaired'; raises OSError if
    the copy does not match."""
    if dst.exists() and os.path.samefile(src, dst):
        # One-drive build (downloaded straight onto the drive): nothing to
        # copy, and never overwrite or delete the only copy.
        if sha256_file(dst) == staged_sha:
            return "kept"
        raise OSError("this file changed since it was downloaded (damaged?): delete it and "
                      "run the download again")
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
    if name.lower().endswith((".dmg", ".apk", ".appimage")):
        return None   # used as they are (the Mac launcher opens Firefox's disk image read-only)
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


def can_unpack_firefox():
    """Only Windows can run Mozilla's installer to unpack it."""
    return os.name == "nt"


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


def copy_launchers(drive, dests=None):
    """The launchers, under their drive names (LAUNCHER_DEST, or dests), with
    the line endings each system needs whatever the clone's git settings."""
    names = []
    for src_name, dest in (dests or LAUNCHER_DEST).items():
        src = LAUNCHERS / src_name
        if not src.is_file():
            continue
        text = src.read_bytes().replace(b"\r\n", b"\n")
        if src.suffix.lower() in (".bat", ".cmd", ".ps1"):
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
    that is not a git repository (a drive's own recipe copy, or the repository
    downloaded as a ZIP), every file except those in hidden folders (.git,
    .venv-build, which make-arc.py creates there), the build's working folders
    and Python caches. RECIPE_EXCLUDE is left out."""
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
            folders = rel.split("/")[:-1]
            if path.is_file() and not any(f.startswith(".") or f == "__pycache__" for f in folders) \
                    and not (folders and folders[0] in RECIPE_WORK_DIRS) and not rel.endswith(".pyc"):
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
    allowed = {frontdoor.HTML_NAME, cl.ARC, "System Volume Information", "$RECYCLE.BIN"} | set(DOWNLOAD_STATE) | \
        {dest for dest in LAUNCHER_DEST.values() if "/" not in dest}
    return sorted(p.name for p in drive.iterdir() if p.name not in allowed)


def build_arc_zim(drive, placed, all_ids, version_line, folder, publishers, facts, edition=None,
                  out=None, overlay=None):
    """Write arc/site/<arczim.FILE_NAME> (under out, if given: the pocket
    kit); return its drive path."""
    books = [arczim.BOOK] + libraryhome.search_books(drive, placed, publishers, facts, overlay)
    pages, linked = frontdoor.build_served(drive, placed, all_ids, version_line, folder, publishers, books,
                                           edition=edition, overlay=overlay)
    names = {}   # drive path -> title shown in the library
    for r in placed:
        names[r["folder"]] = frontdoor.display(r)
        for name, label in cl.part_labels(r).items():   # a pinned list's documents, by their labels
            names[f"{r['folder']}/{name}"] = f"{frontdoor.display(r)}: {label}"
    files = []
    for rel in linked:
        src = cl.on_drive(drive, rel, overlay)
        if not src.is_file():
            continue
        owner = names.get(rel) or names.get(rel.rsplit("/", 1)[0])
        title = owner if rel in names else (f"{owner}: {Path(rel).stem}" if owner else Path(rel).name)
        files.append((frontdoor.zim_path(rel), src, title))
    rel_out = f"{frontdoor.SITE}/{arczim.FILE_NAME}"
    n = arczim.build(Path(out or drive) / rel_out, pages, files, "Knowledge Arc",
                     "Offline library: subjects, topics and guides", dt.date.today().isoformat(),
                     frontdoor.guide_page)
    print(f"  {len(pages)} pages and {len(files)} files packed ({n} entries)")
    return rel_out


def recipe_version():
    try:
        out = subprocess.run(["git", "-C", str(cl.REPO), "describe", "--always", "--dirty"],
                             capture_output=True, text=True, timeout=10)
        return out.stdout.strip() or "unknown"
    except (OSError, subprocess.SubprocessError):
        return "unknown"


def checksum_entries(drive, content_hashes, stray_top=()):
    """{drive path: sha256} for CHECKSUMS.sha256.

    Content folders: only the files of placed catalog items, with the hash
    taken at download time, so neither stray files nor decayed bytes get
    fingerprinted as good. Everything else (arc/system, front door, launchers,
    software, the pocket kit's pages) is hashed as it is now. Entries in
    stray_top (unexpected things at the top of the drive) are left out, and so
    are the two file lists themselves."""
    entries = dict(content_hashes)
    for path in drive.rglob("*"):
        rel = path.relative_to(drive).as_posix()
        if not path.is_file() or rel.startswith(CONTENT_DIRS) or rel in content_hashes:
            continue
        if rel.split("/", 1)[0] in stray_top:
            continue
        if rel in (CHECKSUMS, KIT_CHECKSUMS) or rel.endswith(".part") or rel in DOWNLOAD_STATE \
                or rel in KIT_STATE or rel.startswith(("System Volume Information/", "$RECYCLE.BIN/")):
            continue
        entries[rel] = sha256_file(path)
    return entries


def write_list(path, entries):
    """Write {path: sha} in the format `sha256sum -c` reads: hash, two spaces,
    path with forward slashes, sorted by path."""
    lines = sorted(f"{sha}  {rel}\n" for rel, sha in entries.items())
    lines.sort(key=lambda line: line[66:])
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.writelines(lines)
    return len(lines)


def write_checksums(drive, content_hashes, stray_top=()):
    """Write the drive's CHECKSUMS.sha256 (see checksum_entries)."""
    return write_list(drive / CHECKSUMS, checksum_entries(drive, content_hashes, stray_top))


def pocket_entries(entries, pocket_files):
    """The pocket copy's file list, {path on the pocket drive: sha256}, from
    the big drive's entries: the pocket rows' files (pocket_files, with the
    hash taken at download time), the kit's own generated files (pages, the
    arc's collection, catalog, version log), and the files every edition
    shares (programs, launchers, check tools, the recipe). Never the bigger
    edition's own pages and lists, nor the pocket-copy scripts themselves."""
    prefix = cl.KIT + "/"
    kit = {rel[len(prefix):]: sha for rel, sha in entries.items()
           if rel.startswith(prefix) and not rel.startswith(CONTENT_DIRS)}
    out = dict(pocket_files)
    for rel, sha in entries.items():
        if rel.startswith(CONTENT_DIRS) or rel.startswith(prefix) or rel in kit:
            continue
        if rel.startswith(frontdoor.SITE + "/") or rel in EDITION_FILES or rel in POCKET_COPY_DEST.values():
            continue
        out[rel] = sha
    out.update(kit)
    return out


def place_row(row, src_root, drive, prefix=""):
    """Copy (or check) every file of row from src_root to drive/prefix.
    Returns (files [(path, staged sha)], actions); raises FileNotFoundError if
    the row isn't staged there, OSError if a copy doesn't match."""
    files = staged_files(row, src_root)
    actions = []
    for rel, sha in files:
        try:
            actions.append(place(src_root / rel, drive / prefix / rel, sha))
        except FileNotFoundError:
            raise
        except OSError as e:
            raise OSError(f"{rel}: {e}") from e
    return files, actions


def version_lines(args, placed, edition_text, notes=()):
    total = sum(int(r["size_bytes"] or 0) for r in placed)
    version = [
        f"Built: {dt.datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"Selection: {edition_text}",
        f"Items: {len(placed)} ({human(total)})",
        f"Recipe version (git): {recipe_version()}",
    ]
    if args.allow_pending:
        version.append("TEST BUILD: includes draft notes that have not been checked yet.")
    version += list(notes)
    if args.note:
        version.append(f"Changes: {args.note}")
    return version


def write_version(system, version):
    """Newest build first; earlier entries are kept as the drive's history."""
    log = system / "VERSION.txt"
    previous = log.read_text(encoding="utf-8") if log.exists() else ""
    system.mkdir(parents=True, exist_ok=True)
    with open(log, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(version) + "\n" + ("\n" + previous if previous else ""))


def build_pages(drive, placed, rows, fields, publishers, args, version, server, edition,
                out=None, overlay=None):
    """Everything an edition writes for itself: the library's home page, the
    catalog of what is on it, the version log, the website and the arc's own
    collection. out/overlay: write into the pocket kit, reading its own files
    there first. Returns a list of problems."""
    root = Path(out or drive)
    problems = []
    arc_ok, arc_why = arczim.available()
    zims = libraryhome.placed_zims(drive, placed, overlay)
    facts = libraryhome.zim_facts(drive, [r["folder"] for r in zims], overlay)
    if server:
        home = libraryhome.build(drive, placed, publishers, facts, arczim.BOOK if arc_ok else None,
                                 out=out, overlay=overlay)
        if home:
            print(f"Library home page: {cl.KIT + '/' if out else ''}{home}")
    system = root / SYSTEM
    system.mkdir(parents=True, exist_ok=True)
    cl.write_csv_atomic(system / "CATALOG.csv", fields, placed)
    write_version(system, version)

    # Front door: built from what is actually on the drive, every run.
    all_ids = {r["id"] for r in rows}
    frontdoor.build(drive, placed, all_ids, include_drafts=args.allow_pending,
                    version_line=f"{version[0]}. {version[2]}." + (" Test build." if args.allow_pending else ""),
                    folder=args.frontdoor, publishers=publishers,
                    arc_zim=f"{frontdoor.SITE}/{arczim.FILE_NAME}" if arc_ok else None, edition=edition,
                    out=out, overlay=overlay)

    # The arc's own collection: the same pages, served by the library, with
    # the guides inside and their text searchable. Built after the pages,
    # because frontdoor.build() clears arc/site.
    if arc_ok:
        try:
            rel = build_arc_zim(drive, placed, all_ids, version[0], args.frontdoor, publishers, facts,
                                edition=edition, out=out, overlay=overlay)
            print(f"The arc's own collection: {cl.KIT + '/' if out else ''}{rel}")
        except Exception as e:   # the rest of the drive is still good
            problems.append(("arc collection", f"{arczim.FILE_NAME} was not built: {e}"))
    else:
        print(f"NOTE: {arc_why}")
    return problems


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
                    help="TEST BUILD: also show the draft notes (frontdoor/drafts), marked TEST BUILD")
    ap.add_argument("--note", default="", help="one line for VERSION.txt (what changed)")
    ap.add_argument("--frontdoor", type=Path, default=frontdoor.FRONTDOOR,
                    help="folder with situations.csv, numbers.csv and drafts/ (tests use a fixture)")
    ap.add_argument("--prune", action="store_true",
                    help="delete files in arc/guides and arc/collections that no placed catalog item accounts for")
    args = ap.parse_args(argv)

    fields, rows = cl.read_csv(args.catalog)
    publishers = {p["id"]: p for p in cl.read_csv(args.publishers)[1]}
    if args.bundle:
        chosen, kit_rows = cl.drive_rows(rows, args.bundle)
    else:
        chosen, kit_rows = cl.select(rows, None, args.ids), []
    staging, drive = args.staging.resolve(), args.drive.resolve()
    if not staging.is_dir():
        raise SystemExit(f"staging folder not found: {staging}")
    drive.mkdir(parents=True, exist_ok=True)

    placed, skipped, problems = [], [], []
    content_hashes = {}   # drive path -> staged sha, for placed items only
    row_files = {}        # row id -> [(path on a drive of its edition, staged sha)]
    kit_placed, kit_notes = [], []

    def report(row, actions, where=""):
        summary = ", ".join(f"{actions.count(a)} {a}" for a in ("copied", "repaired", "kept") if a in actions)
        print(f"[{row['id']}] {summary}{where}: {row['title'][:70]}", flush=True)
        if "repaired" in actions:
            problems.append((row["id"], "a file on the drive had changed since it was copied "
                                        "(bit rot?) and was replaced from staging: check the drive's health"))

    for row in chosen:
        reason = gate(row, publishers)
        if reason:
            skipped.append((row["id"], reason))
            continue
        try:
            files, actions = place_row(row, staging, drive)
        except FileNotFoundError as e:
            problems.append((row["id"], str(e)))
            continue
        except OSError as e:
            problems.append((row["id"], str(e)))
            continue
        placed.append(row)
        row_files[row["id"]] = files
        content_hashes.update(dict(files))
        report(row, actions)

    # The pocket kit's own files: pocket rows this edition replaced. Staged in
    # the kit (download.py --bundle <edition>) or at their usual place (an
    # archive filled with --bundle all); always placed in the kit.
    for row in kit_rows:
        if gate(row, publishers):
            continue
        for src_root in (staging / cl.KIT, staging):
            try:
                files, actions = place_row(row, src_root, drive, cl.KIT)
            except FileNotFoundError as e:
                missing = str(e)
                continue
            except OSError as e:
                problems.append((row["id"], f"pocket kit: {e}"))
                break
            kit_placed.append(row)
            row_files[row["id"]] = files
            content_hashes.update({f"{cl.KIT}/{rel}": sha for rel, sha in files})
            kit_notes += [f"Newer than the catalog: {rel} holds {source} (the catalog's version had left "
                          "Kiwix's servers)." for rel, source in newer_versions(src_root, [row])]
            report(row, actions, f" (pocket kit, {cl.KIT})")
            break
        else:
            problems.append((row["id"], f"pocket kit: {missing}"))

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
            if how == "firefox-exe" and not can_unpack_firefox():
                # Only Windows can unpack Mozilla's installer. The Windows
                # launcher unpacks it on first use instead (into the
                # computer's temporary folder), so the arc is complete.
                print(f"NOTE: {row['folder']} stays packed (this is not a Windows computer); "
                      "the Windows launcher unpacks it when the library is first opened.")
                continue
            try:
                unpack(drive / row["folder"], drive / target, how)
                unpacked.append(target)
            except (OSError, subprocess.SubprocessError, zipfile.BadZipFile, tarfile.TarError) as e:
                problems.append((row["id"], f"could not unpack {row['folder']}: {e}"))
    if unpacked:
        print(f"Library server unpacked: {', '.join(unpacked)}; "
              f"launchers: {', '.join(copy_launchers(drive))}")

    # The pocket kit: on every drive bigger than pocket, so a pocket copy can
    # be made from it with no internet and nothing installed.
    pocket = []
    if args.bundle and args.bundle != "pocket":
        done = {r["id"] for r in placed + kit_placed}
        pocket = [r for r in cl.select(rows, "pocket") if r["id"] in done]
    if pocket:
        print(f"Make a pocket copy: {', '.join(copy_launchers(drive, POCKET_COPY_DEST))}")

    system = drive / SYSTEM
    system.mkdir(parents=True, exist_ok=True)
    for tool in sorted(DRIVE_FILES.iterdir()):
        # Force line endings whatever the clone's git settings: Windows
        # scripts get CRLF, shell scripts LF.
        text = tool.read_bytes().replace(b"\r\n", b"\n")
        if tool.suffix.lower() in (".bat", ".cmd", ".ps1", ".txt"):
            text = text.replace(b"\n", b"\r\n")
        (system / tool.name).write_bytes(text)
    try:
        if not copy_recipe(drive):
            problems.append(("recipe", "no recipe files found: arc/system/recipe is empty"))
    except ValueError as e:
        problems.append(("recipe", str(e)))

    notes = [f"Newer than the catalog: {rel} holds {source} (the catalog's version had left Kiwix's servers)."
             for rel, source in newer_versions(staging, placed)]
    version = version_lines(args, placed, 'bundle ' + args.bundle if args.bundle else 'ids ' + ' '.join(args.ids),
                            notes)
    problems += build_pages(drive, placed, rows, fields, publishers, args, version, bool(unpacked), args.bundle)

    if pocket:
        kit = drive / cl.KIT
        print(f"\nThe pocket kit ({cl.KIT}): the pocket edition's own pages, for a pocket copy.")
        for generated in (frontdoor.HTML_NAME, frontdoor.TXT_NAME):
            if (kit / generated).exists():
                (kit / generated).unlink()
        if (kit / SYSTEM).exists():
            shutil.rmtree(kit / SYSTEM)
        kit_version = version_lines(args, pocket, f"bundle pocket (a pocket copy made from a {args.bundle} drive)",
                                    kit_notes + [n for n in notes if any(r["folder"] in n for r in pocket)])
        problems += build_pages(drive, pocket, rows, fields, publishers, args, kit_version, bool(unpacked),
                                "pocket", out=kit, overlay=kit)

    stray_top = top_level_extras(drive)
    entries = checksum_entries(drive, content_hashes, stray_top)
    if pocket:
        files = {rel: sha for r in pocket for rel, sha in row_files[r["id"]]}
        n_pocket = write_list(drive / KIT_CHECKSUMS, pocket_entries(entries, files))
        entries[KIT_CHECKSUMS] = sha256_file(drive / KIT_CHECKSUMS)
        print(f"Pocket copy: {len(pocket)} items, {n_pocket} files listed in {KIT_CHECKSUMS}.")
    n = write_list(drive / CHECKSUMS, entries)

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
