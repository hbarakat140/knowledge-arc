#!/usr/bin/env python3
"""Make your own Knowledge Arc: download everything and build it onto a drive.

    python make-arc.py                                   asks which drive and which edition
    python make-arc.py --drive E:\\ --edition full        no questions (add --yes to skip the last one)
    python make-arc.py --drive E:\\ --archive D:\\arc-archive
                                                         keep the downloads in a separate folder
    python make-arc.py --check                           check everything, download nothing

Windows: double-click make-arc.bat. Mac: double-click make-arc.command.

What it does:
  1. Sets up the two build packages (search inside the guides) in
     .venv-build, next to this file. If that can't be done (Python older than
     3.11, no internet to PyPI), it says what the arc will lack and asks.
  2. Checks the drive: big enough, and formatted exFAT (or NTFS, APFS, ext4),
     not FAT32, which cannot hold files over 4 GB.
  2b. Checks before the download (scripts/preflight.py): the drive can be
     written, the edition fits, Kiwix and one item from each website answer
     (every item with --check). A PROBLEM asks before starting. Then the
     computer is kept awake while it works.
  3. Downloads every item of the edition from its publisher (or from this
     repository's hosted/ folder), checking each file's fingerprint.
     Straight onto the drive, unless --archive names another folder.
  4. Builds the drive: the website, the search, the launchers, the card, the
     checks. Then open "1 START-HERE" on the drive.

Safe to stop (Ctrl+C) and run again: finished files are kept and a large
download resumes where it stopped. Running it again later also brings the
drive up to date with the catalog: new items are added.
Needs Python 3.11 or newer and nothing else (3.9 and 3.10 build an arc
without the searchable guides). make-arc.bat and make-arc.command use the
computer's own Python when it is new enough, and otherwise fetch a portable
one (scripts/portable-python.txt); with that one, the two build packages go
into it directly, not into .venv-build. Windows, Mac and Linux all build the same
arc: on one built on a Mac or Linux, the drive's browser for Windows is
unpacked when the full library is first opened on a Windows computer.
"""

import argparse
import importlib
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

if sys.version_info < (3, 9):
    sys.exit("Python 3.9 or newer is needed: https://www.python.org/downloads/")

REPO = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO / "scripts"))
import catalog_lib as cl  # noqa: E402
import preflight  # noqa: E402

VENV = REPO / ".venv-build"
GB = 1000 ** 3
FAT = {"FAT", "FAT12", "FAT16", "FAT32", "VFAT", "MSDOS"}
EXTRA = int(1.5 * GB)   # Hesperian books (no size in the catalog) and unpacked programs
SPEED = 10 * 1000 ** 2  # bytes per second, for the time estimate (7-13 MB/s measured)
FULL_PYTHON = (3, 11)   # libzim 4.1 (the searchable collection) has wheels for 3.11+ only
# Written into the portable Python's folder by scripts/get-python.ps1 / .sh.
PORTABLE_MARK = "knowledge-arc-portable.txt"


def say(text=""):
    print(text, flush=True)


def ask(question, default=""):
    try:
        answer = input(f"{question} ").strip()
    except EOFError:
        answer = ""
    return answer or default


# ------------------------------------------------------------ build packages

def venv_python():
    win = VENV / "Scripts" / "python.exe"
    return win if win.exists() else VENV / "bin" / "python"


def has_build_packages():
    try:
        import libzim  # noqa: F401
        import pypdf  # noqa: F401
        return True
    except ImportError:
        return False


def without_search(args, why):
    """Say plainly what an arc built without the build packages lacks, and
    ask before going on (unless --yes)."""
    say(f"\nThe two build packages that make the guides searchable can't be used: {why}\n"
        "Without them the arc still works: START-HERE, every guide and collection, and the\n"
        "full library. But the guides are not searchable in the full library, and START-HERE\n"
        "does not switch to the full library by itself.\n"
        "For the complete arc, double-click make-arc.bat (Windows) or make-arc.command (Mac,\n"
        "Linux): they fetch a Python that can use them. Or install Python "
        f"{FULL_PYTHON[0]}.{FULL_PYTHON[1]} or newer from\n"
        "https://www.python.org/downloads/ and run this again.")
    if not args.yes and ask("Go on without them? [y/N]", "n").lower() not in ("y", "yes"):
        sys.exit("Stopped.")
    say()


def is_portable():
    """Running on the portable Python that make-arc.bat / .command fetched."""
    return (Path(sys.prefix) / PORTABLE_MARK).is_file()


def pip_install(python):
    subprocess.run([str(python), "-m", "pip", "install", "-q", "--disable-pip-version-check",
                    "-r", str(REPO / "requirements-build.txt")], check=True)


def install_into_portable(args):
    """The portable Python is this arc's own, in the computer's cache folder:
    the build packages go straight into it, no .venv-build needed."""
    try:
        say("Setting up the build packages (about 20 MB, once) ...")
        pip_install(sys.executable)
    except (subprocess.CalledProcessError, OSError) as e:
        return without_search(args, f"they could not be installed ({e}).")
    importlib.invalidate_caches()
    if not has_build_packages():
        return without_search(args, "they were installed but could not be loaded.")


def ensure_build_packages(args):
    """Re-run this script with .venv-build's Python, creating it and
    installing the packages if needed. Returns only if the script should go on
    with the current Python (it has the packages, or the person agreed to go
    on without them)."""
    if args.no_search or has_build_packages() or os.environ.get("ARC_MAKE_INNER"):
        return
    if is_portable():
        return install_into_portable(args)
    if sys.version_info < FULL_PYTHON:
        return without_search(args, f"they need Python {FULL_PYTHON[0]}.{FULL_PYTHON[1]} or newer, "
                                    f"and this is Python {sys.version_info[0]}.{sys.version_info[1]}.")
    try:
        if not venv_python().exists():
            say("Setting up the build packages (a few MB, once) in .venv-build ...")
            subprocess.run([sys.executable, "-m", "venv", str(VENV)], check=True)
        check = [str(venv_python()), "-c", "import libzim, pypdf"]
        if subprocess.run(check, capture_output=True).returncode:
            pip_install(venv_python())
            subprocess.run(check, check=True)
    except (subprocess.CalledProcessError, OSError) as e:
        return without_search(args, f"they could not be installed ({e}).")
    env = dict(os.environ, ARC_MAKE_INNER="1")
    sys.exit(subprocess.call([str(venv_python()), str(Path(__file__).resolve()), *sys.argv[1:]], env=env))


# -------------------------------------------------------------------- drives

def file_system(path):
    """The file system's name for path ('exFAT', 'NTFS', 'vfat', ...), or ''."""
    path = Path(path).resolve()
    if os.name == "nt":
        import ctypes
        name = ctypes.create_unicode_buffer(64)
        root = path.anchor
        ok = ctypes.windll.kernel32.GetVolumeInformationW(ctypes.c_wchar_p(root), None, 0, None, None,
                                                          None, name, len(name))
        return name.value if ok else ""
    best, kind = "", ""
    try:
        if sys.platform == "darwin":
            lines = subprocess.run(["mount"], capture_output=True, text=True).stdout.splitlines()
            mounts = []
            for line in lines:   # /dev/disk4s1 on /Volumes/STICK (exfat, local, ...)
                if " on " in line and " (" in line:
                    where, rest = line.split(" on ", 1)[1].rsplit(" (", 1)
                    mounts.append((where, rest.split(",")[0]))
        else:
            mounts = [(f.split()[1].replace("\\040", " "), f.split()[2])
                      for f in Path("/proc/mounts").read_text().splitlines()]
    except OSError:
        return ""
    for where, fs in mounts:
        if (str(path) + "/").startswith(where.rstrip("/") + "/") and len(where) >= len(best):
            best, kind = where, fs
    return kind


def candidate_drives():
    """[(path, label)] of drives a person would plug in."""
    out = []
    if os.name == "nt":
        import ctypes
        k = ctypes.windll.kernel32
        system = os.environ.get("SystemDrive", "C:").upper()
        mask = k.GetLogicalDrives()
        for i in range(26):
            if not mask & (1 << i):
                continue
            root = f"{chr(65 + i)}:\\"
            if root[:2] == system or k.GetDriveTypeW(root) not in (2, 3):   # removable, fixed
                continue
            label = ctypes.create_unicode_buffer(64)
            k.GetVolumeInformationW(root, label, len(label), None, None, None, None, 0)
            out.append((root, label.value))
    else:
        bases = [Path("/Volumes")] if sys.platform == "darwin" else \
            [Path("/media") / os.environ.get("USER", ""), Path("/run/media") / os.environ.get("USER", ""),
             Path("/mnt")]
        for base in bases:
            for p in sorted(base.glob("*")) if base.is_dir() else []:
                if os.path.ismount(p) and p.resolve() != Path("/"):
                    out.append((str(p), p.name))
    return out


def describe(path):
    try:
        usage = shutil.disk_usage(path)
    except OSError:
        return "not available"
    fs = file_system(path) or "unknown format"
    return f"{usage.free / GB:.0f} GB free of {usage.total / GB:.0f} GB, {fs}"


def choose_drive(args):
    if args.drive:
        return Path(args.drive)
    drives = candidate_drives()
    say("Where should the arc go? Plug in the drive first.")
    for n, (path, label) in enumerate(drives, 1):
        say(f"  {n}. {path}  {label}  ({describe(path)})")
    if not drives:
        say("  (no external drive found)")
    answer = ask("Type a number, or a folder path:")
    if answer.isdigit() and 1 <= int(answer) <= len(drives):
        return Path(drives[int(answer) - 1][0])
    if not answer:
        sys.exit("No drive chosen.")
    return Path(answer)


def check_target(drive):
    drive = drive.resolve()
    if drive == REPO or REPO in drive.parents:
        sys.exit("Choose a drive or folder outside this repository.")
    if os.name == "nt" and drive == Path(os.environ.get("SystemDrive", "C:") + "\\"):
        sys.exit("That is the computer's system drive. Choose an external drive, or a folder on it.")
    drive.mkdir(parents=True, exist_ok=True)
    fs = file_system(drive)
    if fs.upper() in FAT:
        sys.exit(f"{drive} is formatted {fs}, which cannot hold files over 4 GB (Wikipedia is 14 GB or more).\n"
                 "Format it as exFAT first. This ERASES the drive:\n"
                 "  Windows: File Explorer, right-click the drive, Format..., File system: exFAT, Start.\n"
                 "  Mac: Disk Utility, select the drive, Erase, Format: ExFAT, Scheme: GUID Partition Map.\n"
                 "  Linux: the Disks program, Format Partition, type exFAT.")
    return drive


# ------------------------------------------------------------------ editions

def drive_rows(all_rows, edition):
    """What a drive of this edition holds: its rows, plus (above pocket) the
    pocket kit's own rows, with the folder they are kept in (cl.KIT/...)."""
    rows, kit = cl.drive_rows(all_rows, edition)
    return rows + [dict(r, folder=f"{cl.KIT}/{r['folder']}") for r in kit]


def still_to_fetch(rows, staging):
    """Bytes of the rows' files not yet in the download folder."""
    return sum(int(r["size_bytes"] or 0) for r in rows if not preflight.fetched(r, staging))


def needed_on_drive(rows):
    """Catalog sizes, plus the arc's own collection (a second copy of every
    document; a third with the pocket kit's own collection) and EXTRA."""
    docs = sum(int(r["size_bytes"] or 0) for r in rows if r["format"] != "zim" and r["shelf"] != "software")
    kit = any(r["folder"].startswith(cl.KIT + "/") for r in rows)
    return sum(int(r["size_bytes"] or 0) for r in rows) + docs * (2 if kit else 1) + EXTRA


def space_needed(rows, drive, staging):
    """{folder: bytes still needed there} for building rows onto drive."""
    todo = still_to_fetch(rows, staging)
    if staging == drive:   # one drive: what is already downloaded is already there
        return {drive: needed_on_drive(rows) - sum(int(r["size_bytes"] or 0) for r in rows) + todo}
    return {staging: todo, drive: needed_on_drive(rows)}


def fits(rows, drive, staging):
    return all(need * 1.03 < shutil.disk_usage(where).free
               for where, need in space_needed(rows, drive, staging).items())


def choose_edition(args, all_rows, drive, staging):
    """(edition, whether it fits)."""
    fits_ed = {}
    say("\nWhich edition? Each holds everything in the one before.")
    for n, ed in enumerate(cl.BUNDLES, 1):
        rows = drive_rows(all_rows, ed)
        fits_ed[ed] = fits(rows, drive, staging)
        say(f"  {n}. {ed:8} {needed_on_drive(rows) / GB:6.0f} GB   {len(rows)} items   "
            + ("fits" if fits_ed[ed] else "does NOT fit on this drive"))
    best = next((ed for ed in reversed(cl.BUNDLES) if fits_ed[ed]), None)
    if args.edition:
        edition = args.edition
    else:
        if not best:
            sys.exit("No edition fits on this drive. The smallest (pocket) needs a 32 GB drive.")
        answer = ask(f"Type a number [{cl.BUNDLES.index(best) + 1} = {best}]:", str(cl.BUNDLES.index(best) + 1))
        if not (answer.isdigit() and 1 <= int(answer) <= len(cl.BUNDLES)):
            sys.exit("No edition chosen.")
        edition = cl.BUNDLES[int(answer) - 1]
    if not fits_ed[edition] and not args.yes:
        if ask(f"The {edition} edition may not fit. Try anyway? [y/N]", "n").lower() != "y":
            sys.exit("Stopped.")
    return edition, fits_ed[edition]


# ---------------------------------------------------------------------- main

def run_checks(args, rows, drive, staging, edition, edition_fits):
    """The checks before a long download (scripts/preflight.py): quick before
    every build, every item with --check. True if nothing blocks."""
    searchable = not args.no_search and has_build_packages()
    lines = [(preflight.OK if searchable else preflight.WARNING,
              f"Python {platform.python_version()}; the guides will "
              + ("be searchable." if searchable else
                 "not be searchable (" + ("--no-search" if args.no_search else "see above") + ")."))]
    for where in dict.fromkeys([drive, staging]):
        err = preflight.writable(where)
        lines.append((preflight.PROBLEM, f"Can't write to {where}: {err}.") if err else
                     (preflight.OK, f"{where}: {describe(where)}; files can be written there."))
    lines.append((preflight.OK, f"The {edition} edition fits (about {needed_on_drive(rows) / GB:.0f} GB "
                                "on the drive).") if edition_fits else
                 (preflight.WARNING, f"The {edition} edition may not fit on {drive}."))
    say("\nAsking the websites for " + ("every item still to fetch (a minute or so) ..." if args.check
                                         else "one item each (under a minute) ..."))
    failed, sites, todo = preflight.check_sources(rows, staging, thorough=args.check)
    lines += preflight.source_lines(failed, sites, todo, args.check)
    # Asked for now, so the line says what really happened (it holds until make-arc ends).
    lines.append(preflight.keep_awake())
    return preflight.report(lines, say)


def hide(path):
    if os.name == "nt" and path.exists():
        import ctypes
        ctypes.windll.kernel32.SetFileAttributesW(str(path), 0x2)   # hidden


def main(argv=None):
    ap = argparse.ArgumentParser(description="Make your own Knowledge Arc on a drive.")
    ap.add_argument("--drive", help="the drive (or folder) to build the arc on")
    ap.add_argument("--edition", choices=cl.BUNDLES, help="pocket, core, standard or full")
    ap.add_argument("--archive", help="keep the downloads in this folder instead of straight on the drive")
    ap.add_argument("--yes", action="store_true", help="don't ask before starting")
    ap.add_argument("--no-search", action="store_true", help="skip the build packages (no searchable guides)")
    ap.add_argument("--check", action="store_true",
                    help="check the drive, the internet and every item's source, then stop (downloads nothing)")
    ap.add_argument("--catalog", type=Path, default=cl.CATALOG, help=argparse.SUPPRESS)   # tests
    args = ap.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")

    ensure_build_packages(args)
    import assemble   # noqa: E402  (after the packages: assemble checks for them)
    import download   # noqa: E402

    say("KNOWLEDGE ARC: MAKE YOUR OWN COPY\n")
    drive = check_target(choose_drive(args))
    staging = Path(args.archive).resolve() if args.archive else drive
    staging.mkdir(parents=True, exist_ok=True)
    _, all_rows = cl.read_csv(args.catalog)
    edition, edition_fits = choose_edition(args, all_rows, drive, staging)
    rows = drive_rows(all_rows, edition)
    ready = run_checks(args, rows, drive, staging, edition, edition_fits)
    if args.check:
        return 0 if ready else 1
    todo = still_to_fetch(rows, staging)
    hours = todo / SPEED / 3600
    say(f"\n{edition} edition onto {drive}: about {todo / GB:.1f} GB still to download "
        f"(roughly {hours:.0f} hours at 10 MB/s)" + (f", kept in {staging}." if staging != drive else "."))
    if not args.yes:
        question = "Start? [Y/n]" if ready else "Start anyway? [y/N]"
        if ask(question, "y" if ready else "n").lower() not in ("y", "yes"):
            sys.exit("Stopped.")

    say("\n== Downloading (safe to stop with Ctrl+C and run again) ==")
    try:
        download.main(["--dest", str(staging), "--bundle", edition, "--catalog", str(args.catalog)])
    except KeyboardInterrupt:
        sys.exit("\nStopped. Run the same command again to continue: finished files are kept.")
    say("\n== Building the drive ==")
    code = assemble.main(["--staging", str(staging), "--drive", str(drive), "--bundle", edition,
                          "--catalog", str(args.catalog)])
    hide(staging / ".download-state.json")
    hide(staging / cl.KIT / ".download-state.json")

    say("\n" + "=" * 70)
    say(f"Your arc is on {drive}. Open \"1 START-HERE\" there.")
    if code:
        say("Some items are missing or had problems: they are listed above. Run this again later to\n"
            "fetch them (a site may have been down); everything else on the drive works.")
    say("Then print the card: 1 START-HERE > Keep it alive > The card to print.")
    return code


if __name__ == "__main__":
    sys.exit(main())
