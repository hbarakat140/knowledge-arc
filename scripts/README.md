# Build scripts

Python 3.9 or newer, standard library only; the two optional build packages (`requirements-build.txt`) need Python 3.11 or newer. `make-arc.bat` / `make-arc.command` don't need a Python on the computer: without 3.11 or newer they fetch the portable Python pinned in `portable-python.txt` (`get-python.ps1` on Windows, `get-python.sh` on Mac and Linux; python-build-standalone, checked by sha-256, unpacked into the user's cache folder), and make-arc then installs the build packages into it, not into `.venv-build`. `ARC_PORTABLE_PYTHON=1` forces the portable one (for testing). Run them from the repo root on the build machine. Someone who only reads an arc never runs these: on the drive, `arc/system/verify.bat` or `verify.sh` need nothing installed.

## The quick way: make-arc.py

`make-arc.py` at the repo root (double-click `make-arc.bat` or `make-arc.command`) does steps 1, 3 and 3b below in one go, for one drive:

- creates `.venv-build` with the build packages and re-runs itself inside it (skip with `--no-search`);
- lists the drives, and refuses the repo folder, the system drive and FAT32 (with how to format exFAT);
- shows which editions fit, offering the largest;
- runs the checks in `preflight.py`: the drive can be written, the edition fits, the search packages, and the internet. Each source is asked for its first kilobyte the way `download.py` asks (same address, downloader and HTTPS settings), skipping files already there and hosted ones: one item per website before every build (a few seconds), every item with `--check` (about 30 s for pocket), which then stops. No website answering, Kiwix down, or a drive that can't be written is a PROBLEM and it asks before starting; sites that refuse are listed with their items. Then it keeps the computer awake while it works (Windows `SetThreadExecutionState`, Mac `caffeinate`, Linux `systemd-inhibit`; all end with make-arc);
- runs `download.py --bundle <edition>` straight onto the drive (or into `--archive <folder>`), then `assemble.py` with `--staging` and `--drive` on the same drive. In that one-drive build `assemble.py` checks the files in place and never overwrites or deletes them;
- hides `.download-state.json` at the top of the drive.

`--drive E:\ --edition core --yes` runs without questions. Tests: `tests/test_make_arc.py`.

## The build, step by step

```
# 1. Download into the archive: a staging folder on its own big drive (not the master).
#    Paths in it are the catalog's drive paths (arc/...).
#    Safe to stop and restart; finished files are skipped.
python scripts/download.py --dest D:/library-staging --bundle core --dry-run
python scripts/download.py --dest D:/library-staging --bundle core --update-catalog

# 2. Download the MANUAL items in a browser, saving each one to the path the
#    script printed. Then run step 1 again so they get hashed.

# 3. (Optional, recommended) a separate Python with the packages that build the
#    arc's own collection, so the full library is one website with one search:
#      python -m venv .venv-build
#      .venv-build\Scripts\python -m pip install -r requirements-build.txt
#    and run assemble.py below with .venv-build\Scripts\python instead of python.
#    Without it the build still works and prints a NOTE.
#
# 3b. Put the approved items on the master drive: the entry files at the top,
#    everything else in arc/, and arc/system (checksums, version log, verify
#    tools, maintenance guide, a copy of the recipe).
python scripts/assemble.py --staging D:/library-staging --drive E:/ --bundle core --note "first build"

# 4. Copy the master to each other drive, checking every file.
python scripts/mirror.py --master E:/ --copy F:/

# 5. Commit catalog/catalog.csv: --update-catalog filled in sha256,
#    size_bytes and download_date.
```

`--ids T1-003 T2-036 ...` works instead of `--bundle` in every script.

## What each script checks

| Script | Checks |
|---|---|
| `download.py` | ZIMs: size and sha-256 from the Kiwix `.meta4`. For files over 64 MB, every mirror is timed on a 2 MB sample and the fastest is tried first (on 20 Nov 2026 the first listed mirror gave 0.4 MB/s and others 7-13 MB/s). A download interrupted by a dropped connection carries on from the next mirror; one stopped by Ctrl+C, a closed window or a power cut resumes from its `.part` on the next run. A damaged `.part` fails the sha-256 check and is deleted. PDFs: file starts with `%PDF-`, and if `size_bytes` is in the catalog the download must match it, because servers sometimes send an error page as a "PDF". Hesperian books: the page must list exactly the number of chapter files given in `format`. Pinned sets (`catalog/files/<id>.csv`): exactly the files listed, one at a time, 1 s apart; HTTP 429 ("too many requests") waits as the server asks (or 15, 30, 60 s...) up to six times, for every download. Software (tier 9: `.zip`, `.tar.gz`, `.apk`): zip or gzip signature, `size_bytes`, and the publisher's `.md5` next to the file. Files whose sites block scripts are copied from the repo's `hosted/` folder and checked against the catalog's `sha256`; any other blocked site is reported as MANUAL. Hesperian file names are matched without regard to case. A Kiwix collection whose pinned version is gone (Kiwix keeps only the two newest) is replaced by the newest of the same collection from the folder listing, saved under the catalog's file name and recorded in `.download-state.json`; `assemble.py` notes it in `VERSION.txt` ("Newer than the catalog"). |
| `assemble.py` | The quality gate (below). Every content file on the drive is hashed against the hash taken at download time, including files it doesn't need to copy: bit rot doesn't change a file's date. A damaged file is replaced from staging and reported. `CHECKSUMS.sha256` lists content files with their download-time hashes, and only files of items that passed the gate. Stray files in the content folders are reported and never fingerprinted, so they never get mirrored. `--prune` deletes them. `VERSION.txt` keeps every build, newest first. Each placed kiwix-tools archive (tier 9, `90_SOFTWARE/`) is unpacked next to itself, and then the launchers in `launchers/` are copied to the drive root (CRLF for `.bat`, LF for the shell scripts), and `libraryhome.py` writes the library's home page, `99_SYSTEM/library-home.html`. |
| `assemble.py` software | Unpacks each software archive in `arc/software/` on every build (`unpack_target`): flat for small tools, with folders (`tree`) for apps, and the Windows Firefox installer with its `/ExtractDir` switch, which only runs on Windows. Built on a Mac or Linux, the installer stays packed (a NOTE, not a problem) and the Windows launcher unpacks it on first use into the computer's temporary folder (its short name: `/ExtractDir` refuses spaces and quotes; if the short name still has a space, the computer's own browser opens instead). Tested 22 Nov 2026: 12 s the first time, then reused. |
| `arczim.py` | Called by `assemble.py` when libzim and pypdf are installed. Packs the served version of the website, the guides and the catalog into `arc/site/knowledge-arc_en_all.zim`, with the guides' text in the search index. |
| `frontdoor.py` | Called by `assemble.py`. Builds `START-HERE.html` and `START-HERE.txt` from the items placed on the drive, linking only to files that exist. Drafts appear only on test builds. See `frontdoor/README.md`. |
| `mirror.py` | Copies only what the master's `CHECKSUMS.sha256` lists, then hashes every file on the copy. |
| `drive/verify.*` | Copied to `arc/system` on every drive. Re-checks every file against `CHECKSUMS.sha256`. |

## The quality gate

The catalog is the gate (owner, 21 Nov 2026). `assemble.py` puts every row of the edition on the drive if its publisher is `approved`, `approved-pending-owner` or `item-review-required` (community answers, in their labelled area). `candidate`, `excluded-licence` and unknown publishers never go on. `reviewer` is a record of spot checks, not a condition.

`--allow-pending` makes a **test build**: it adds the unchecked draft notes from `frontdoor/drafts/` and marks every page and `VERSION.txt` TEST BUILD.

## The pocket kit (drives bigger than pocket)

`assemble.py --bundle core` (or standard, full) also builds `arc/pocket/`, so a pocket copy can be made from the drive with no internet and no Python (`launchers/make-pocket-copy.*`, copied to `arc/Make a pocket copy (Windows).bat`, `arc/Make a pocket copy (Mac).command` and `arc/system/make-pocket-copy.ps1` / `.sh`):

- `cl.drive_rows()` gives an edition's rows plus the **pocket rows it replaces** (today the short Wikipedia, T3-070). `download.py --bundle <edition>` saves those into `<dest>/arc/pocket/` with their own state file (an archive that already has them at their usual place, from `--bundle all`, is not fetched twice); `assemble.py` places them in `arc/pocket/`, where the drive's library never serves them.
- After the edition's own pages, the same `build_pages()` runs again for the pocket edition, writing into `arc/pocket/` and reading the kit's files first (`overlay`): START-HERE, `arc/site/` with the arc's collection, `CATALOG.csv`, `VERSION.txt` ("a pocket copy made from a core drive"), `library-home.html`.
- `arc/pocket/arc/system/CHECKSUMS.sha256` lists every file of the pocket drive in `sha256sum` format: the pocket rows' files, the kit's own files and the files every edition shares (programs, launchers, check tools, recipe); never the bigger edition's pages or the pocket-copy scripts. The script copies each file from the kit if it is there, else from the drive, refuses FAT32 when a file is 4 GB or more, skips files already copied (same size), then checks every file and copies a damaged one once more.
- Tested by `PocketKitTest` (the real PowerShell and `sh` scripts; the copy equals a direct pocket build) and on the whole catalog with placeholder files (22 Nov 2026). The `sh` script has run under Git Bash, not yet on a real Mac or Linux.

## Bundles

Bundles are cumulative: `pocket` < `core` < `standard` < `full`, each including the ones before. A pocket copy (for a phone or a 32 GB stick) is built from the same archive: `--bundle pocket` onto its own drive or folder. Because a bigger edition's item can replace a smaller one's (the full Wikipedia replaces the pocket's short one; Europe maps replace France), fill the archive with `download.py --bundle all`, which fetches every row any edition needs; `--bundle full` alone would miss the replaced ones. `decision` rows are never picked by bundle. A row whose notes say `REPLACES T3-030..T3-035` (or `REPLACES T3-040`) removes those rows from the selection.

## Finding new collections

```
python scripts/scan_kiwix.py
```

Reads the official Kiwix catalogue and scores every English package against `catalog/coverage.csv`. It writes `catalog/candidates-kiwix.csv`, marking each package as in the catalog, rejected (`catalog/rejected.csv`), a candidate or unmatched, and prints the candidates for each area. Big families (TED, maps, Gutenberg, Stack Exchange, Wikipedia subsets) are summarised on one line each. See `docs/catalogue-strategy.md`.

## Content review

```
python scripts/review_table.py
```

Writes `docs/content-review.md`: every subject, topic and item with its publisher, size, edition, role and "about" line, and an empty Decision column, for the owner's subject-by-subject review. Re-run it after each catalog change.

## EU herbal monographs (pinned list)

```
python scripts/ema_herbal.py --check    # what changed at the EMA since the list was pinned
python scripts/ema_herbal.py            # rewrite catalog/files/T2-158.csv
```

Reads the European Medicines Agency's table of herbal substances and each substance's page, and pins, per plant, the final summary for the public, the final EU herbal monograph, or the public statement (never drafts or superseded versions; the most recently updated when there are several). Slow on purpose: the EMA answers fast requests with HTTP 429. After a rewrite, set T2-158's `format` to the count it prints. Only run while the internet works; the build reads the pinned list.

## Tests

```
python -m unittest discover -s tests
```

`tests/test_build.py` runs `assemble.py` and `mirror.py` end to end on fake files, covering:
- the gate (publisher statuses) and the one-drive build
- bit rot that leaves the file date unchanged
- leftovers from a test build, followed by a strict build and a mirror
- the version log
- damage on a mirror copy

`tests/test_catalog.py` lints the real catalog:
- schema, ID format, and that every publisher exists
- English only, plain file names, the right tier folder
- Tier 1 is PDF or HTML only
- navigation tags: every subject has a topic, every row has a valid shelf, audience, job and topics, and `coverage.csv` `covered_by` matches the topic tags
- no two rows share a path

Run it after every catalog edit.

## Tested (18 Nov 2026, Windows 11)

Test set: Tier 1 PDFs, the smallest ZIM (NHS medicines, 15 MB), *Where There Is No Dentist* (14 files) and MSF *Essential Drugs*, downloaded into a scratch folder.
- A second run skipped everything.
- A wrong `size_bytes` was caught.
- The ZIM hash matched its `.meta4`.
- IFRC and CDC were reported as MANUAL (HTTP 403).
- `verify.bat` (via PowerShell) and `verify.sh` (via `sha256sum`) both caught one damaged byte and one missing file.
- Mirroring and re-mirroring both checked clean.
- After a review, a re-run of `assemble.py` now catches bit rot and keeps stray files out of `CHECKSUMS.sha256`, and a dry run never hashes or moves files. All 28 tests pass.
- Not tested yet: a real exFAT drive, Mac `shasum`, and a large ZIM download with resume.
