# Build scripts

Python 3.9 or newer, standard library only. Run them from the repo root on the build machine. The family never runs these. On the drive they only need `arc/system/verify.bat` or `verify.sh`, which need nothing installed.

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
| `download.py` | ZIMs: size and sha-256 from the Kiwix `.meta4`. For files over 64 MB, every mirror is timed on a 2 MB sample and the fastest is tried first (on 20 Nov 2026 the first listed mirror gave 0.4 MB/s and others 7-13 MB/s). A download interrupted by a dropped connection carries on from the next mirror; one stopped by Ctrl+C, a closed window or a power cut resumes from its `.part` on the next run. A damaged `.part` fails the sha-256 check and is deleted. PDFs: file starts with `%PDF-`, and if `size_bytes` is in the catalog the download must match it, because servers sometimes send an error page as a "PDF". Hesperian books: the page must list exactly the number of chapter files given in `format`. Software (tier 9: `.zip`, `.tar.gz`, `.apk`): zip or gzip signature, `size_bytes`, and the publisher's `.md5` next to the file. Sites that block scripts are reported as MANUAL. |
| `assemble.py` | The quality gate (below). Every content file on the drive is hashed against the hash taken at download time, including files it doesn't need to copy: bit rot doesn't change a file's date. A damaged file is replaced from staging and reported. `CHECKSUMS.sha256` lists content files with their download-time hashes, and only files of items that passed the gate. Stray files in the content folders are reported and never fingerprinted, so they never get mirrored. `--prune` deletes them. `VERSION.txt` keeps every build, newest first. Each placed kiwix-tools archive (tier 9, `90_SOFTWARE/`) is unpacked next to itself, and then the launchers in `launchers/` are copied to the drive root (CRLF for `.bat`, LF for the shell scripts), and `libraryhome.py` writes the library's home page, `99_SYSTEM/library-home.html`. |
| `arczim.py` | Called by `assemble.py` when libzim and pypdf are installed. Packs the served version of the website, the guides and the catalog into `arc/site/knowledge-arc_en_all.zim`, with the guides' text in the search index. |
| `frontdoor.py` | Called by `assemble.py`. Builds `START-HERE.html` and `START-HERE.txt` from the items placed on the drive, linking only to files that exist. Drafts appear only on test builds. See `frontdoor/README.md`. |
| `mirror.py` | Copies only what the master's `CHECKSUMS.sha256` lists, then hashes every file on the copy. |
| `drive/verify.*` | Copied to `arc/system` on every drive. Re-checks every file against `CHECKSUMS.sha256`. |

## The quality gate

`assemble.py` puts an item on the drive only if:
- its publisher is `approved`, and
- its row has a real `reviewer`, not `pending-owner`.

`--allow-pending` loosens this for **test drives only**, and `VERSION.txt` then says it's a test build. `candidate` and `excluded-licence` publishers never go on. `item-review-required` items always need a signed-off row.

## Bundles

Bundles are cumulative: `standard` includes `core`, and `full` includes both. `decision` rows are never picked by bundle. A row whose notes say `REPLACES T3-030..T3-035` (or `REPLACES T3-040`) removes those rows from the selection.

## Finding new collections

```
python scripts/scan_kiwix.py
```

Reads the official Kiwix catalogue and scores every English package against `catalog/coverage.csv`. It writes `catalog/candidates-kiwix.csv`, marking each package as in the catalog, rejected (`catalog/rejected.csv`), a candidate or unmatched, and prints the candidates for each area. Big families (TED, maps, Gutenberg, Stack Exchange, Wikipedia subsets) are summarised on one line each. See `docs/catalogue-strategy.md`.

## Tests

```
python -m unittest discover -s tests
```

`tests/test_build.py` runs `assemble.py` and `mirror.py` end to end on fake files, covering:
- the strict gate
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
