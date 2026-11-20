# Build scripts

Python 3.9 or newer, standard library only. Run them from the repo root on the build machine. The family never runs these. On the drive they only need `99_SYSTEM/verify.bat` or `verify.sh`, which need nothing installed.

## The build, step by step

```
# 1. Download into a staging folder on a big local disk (not the target drive).
#    Safe to stop and restart; finished files are skipped.
python scripts/download.py --dest D:/library-staging --bundle core --dry-run
python scripts/download.py --dest D:/library-staging --bundle core --update-catalog

# 2. Download the MANUAL items in a browser, saving each one to the path the
#    script printed. Then run step 1 again so they get hashed.

# 3. Put the approved items on the master drive and write 99_SYSTEM.
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
| `download.py` | ZIMs: size and sha-256 from the Kiwix `.meta4`; mirrors tried in order; interrupted downloads resume. PDFs: file starts with `%PDF-`, and if `size_bytes` is in the catalog the download must match it, because servers sometimes send an error page as a "PDF". Hesperian books: the page must list exactly the number of chapter files given in `format`. Software (tier 9: `.zip`, `.tar.gz`, `.apk`): zip or gzip signature, `size_bytes`, and the publisher's `.md5` next to the file. Sites that block scripts are reported as MANUAL. |
| `assemble.py` | The quality gate (below). Every content file on the drive is hashed against the hash taken at download time, including files it doesn't need to copy: bit rot doesn't change a file's date. A damaged file is replaced from staging and reported. `CHECKSUMS.sha256` lists content files with their download-time hashes, and only files of items that passed the gate. Stray files in the content folders are reported and never fingerprinted, so they never get mirrored. `--prune` deletes them. `VERSION.txt` keeps every build, newest first. Each placed kiwix-tools archive (tier 9, `90_SOFTWARE/`) is unpacked next to itself, and then the launchers in `launchers/` are copied to the drive root (CRLF for `.bat`, LF for the shell scripts), and `libraryhome.py` writes the library's home page, `99_SYSTEM/library-home.html`. |
| `frontdoor.py` | Called by `assemble.py`. Builds `START-HERE.html` and `START-HERE.txt` from the items placed on the drive, linking only to files that exist. Drafts appear only on test builds. See `frontdoor/README.md`. |
| `mirror.py` | Copies only what the master's `CHECKSUMS.sha256` lists, then hashes every file on the copy. |
| `drive/verify.*` | Copied to `99_SYSTEM` on every drive. Re-checks every file against `CHECKSUMS.sha256`. |

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
