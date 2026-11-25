# Contributing to the Knowledge Arc

The arc is an offline learning website on a drive, for anyone who has a copy (see `README.md` and `docs/architecture.md`). This file holds the rules every change follows. The code, the docs and the tests refer to them by number ("rule 4").

## Principles

- **Quality bar: no garbage.** Trusted publishers only (`catalog/publishers.csv`), or items reviewed one by one. Every item is recorded in the catalog. Community content (Stack Exchange, WikiCiv, Low-tech Magazine) appears only in a clearly labelled "community answers" area.
- **The catalog is the gate.** Every row of an edition goes on the drive if its publisher is `approved`, `approved-pending-owner` or `item-review-required`. The checks happen before a row is added (rule 1), so new rows join on the next build. The `reviewer` column records spot checks and sign-offs; it does not block a build. First-aid guides are read item by item before they enter the catalog.
- **Licences.** Free-to-download items are included even when "all rights reserved"; the catalog records each stated licence. Files whose publishers' sites refuse downloads by script are kept in `hosted/`, with their sources and licences in `hosted/README.md`. A publisher who objects gets its file removed. The recipe itself is MIT-licensed (`LICENSE`); hosted and downloaded documents keep their publishers' terms.
- **Copies.** Several identical, verified copies, on at least two kinds of media, in different places. Copies are meant to be passed on.
- **Language.** This edition is in English, content and interface. The one exception is material in French for learning French. Other language editions come later, as separate versions.

## Rules

1. **Verify before adding.** Check that every source is current and comes from an approved publisher. Look up the current version, address and size online; don't rely on memory.
2. **Record everything in the catalog.** No file lands on the drive without a catalog row.
3. **Start-here guides never depend on software.** Where a topic's start-here item is a single document, it must exist as PDF or HTML, even if it is also inside a ZIM. Topics whose start-here is a collection (Wikipedia, Gutenberg, courses) are exempt.
4. **The website is self-contained.** No CDNs, web fonts or external scripts; relative links to files on the drive. Two deliberate exceptions: the only absolute address is the full library on the same computer, `http://127.0.0.1:8642` (or `/...` inside the served pages), and inline scripts (never `src=`) are allowed only where the full library needs them: the served pages in the arc's own collection, the library home page, and the drive's own search page `arc/site/search.html` (every other page reaches it with a plain form, no script). The tests enforce exactly this.
5. **Prefer text over scans.** Scanned PDFs only when nothing better exists, flagged in the catalog.
6. **Test on Windows first**, then Mac and Android, from the drive itself (not from the repository folder).
7. **Write for a stranger.** Anything a person touches (pages, file names, instructions) must make sense to someone who has never heard of this project. Simplicity beats features.
8. **Every item has one job:** primary (start here), depth, cross-check, gap-filler, or a copy a rule requires, in one topic of `catalog/coverage.csv`. An item with no job, or written for the wrong climate or level, is cut. See `docs/redundancy-review.md` section 2.
9. **Discuss before changing direction.** Changes to the vision, the navigation or the editions are agreed with the maintainer before they are built. Content and best-practice calls (which edition, which source wins) are made on the evidence and cited in the catalog notes.
10. **Nothing offline needs Python.** Anything a person may need to do without internet (read, open the full library, check, copy, pass on) works with only what is on the drive and what the computer already has: a browser, `cmd`/PowerShell or `sh`, and the drive's own programs. Python is only for building while the internet works, and the build checks its own needs and says plainly what is missing. Nobody has to install Python to build: `make-arc.bat` / `make-arc.command` use the computer's own Python 3.11+, or fetch a pinned portable Python (`scripts/portable-python.txt`, checked by sha-256) into the user's cache folder, never onto a drive.

## Working on the catalog

- CSV files are UTF-8 with LF line endings. Write them with `catalog_lib.write_csv_atomic`, and re-read the file just before writing it.
- After a change, run the tests (`python -m pytest -q`) and regenerate the review table (`python scripts/review_table.py`).
- `catalog/README.md` explains every column; `scripts/README.md` explains the build.
