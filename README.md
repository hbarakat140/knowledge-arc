# Knowledge Arc

Build recipe for an offline knowledge arc: **an offline website on a drive** that carries trusted practical knowledge, reference, education and culture across a time without internet. Anyone who has a copy can use it, learn from it and pass it on, with nothing installed and nobody there to explain it.

This repository contains the **recipe**, not the content: the catalog of sources, the scripts that download, check and assemble them, the website generator and the launchers. The arc itself (ZIM collections, PDFs, videos, software) is written to drives and is not committed here, except a handful of documents whose publishers' sites block scripts (`hosted/`).

## How someone uses a copy

1. **Open `1 START-HERE`** at the top of the drive. It opens in any browser with nothing installed: subjects, topics and the start-here guides.
2. **One double-click on "2 Open full library"** for that computer starts the library engine from the drive. START-HERE then becomes the full website: the same subjects plus the big collections (Wikipedia, medicine, repair guides, books, courses, maps, videos) and one search over the collections that have a search index (the others are marked "open to browse").
3. **On an Android phone**, install the Kiwix app from the drive to open the collections; the guides open from the Files app.

Everything is organised by **subject** (health, food and farming, making and repairing, science, history, stories, arts...) and by **shelf** (guides, books, encyclopedias, courses, videos, films, music, maps), with doors for children, search and an A-Z of topics. See `docs/architecture.md`.

## Make your own arc

Anyone can build an arc from this repository while the internet works. You need:

- **A computer** with Windows, a Mac or Linux, and **Python 3.11 or newer** ([python.org/downloads](https://www.python.org/downloads/); on Windows, tick "Add python.exe to PATH" when installing). Python 3.9 and 3.10 build an arc without the searchable guides; the script says so and asks first. Any of the three systems builds the same arc.
- **A drive formatted exFAT** (or NTFS, APFS, ext4), big enough for the edition you want. Not FAT32: most new 32 GB sticks and SD cards come as FAT32, which can't hold a file over 4 GB. The script tells you how to reformat it.

Then:

1. Get this repository: **Code > Download ZIP** on GitHub (unzip it), or `git clone`.
2. Plug in the drive.
3. Double-click **`make-arc.bat`** (Windows) or **`make-arc.command`** (Mac, Linux). Or run `python make-arc.py`. (On a Mac, if it says the file can't be opened: right-click it, Open, then Open again; or in Terminal, `sh make-arc.command`.)
4. Choose the drive and the edition. The script offers the largest edition that fits:

   | Edition | On the drive | For |
   |---|---|---|
   | pocket | about 26 GB | a phone or a 32 GB stick: every guide, medicine, repairs, a short Wikipedia, the programs |
   | core | about 165 GB | adds the full Wikipedia with pictures, the map of France, more references |
   | standard | about 300 GB | adds community answers, books, courses and textbooks |
   | full | about 675 GB | adds all of Project Gutenberg, Khan Academy, Wikisource, maps of Europe |

5. Wait. It downloads every item from its publisher (or, for the few sites that refuse scripts, from this repository's `hosted/` folder), checks each file's fingerprint, and builds the drive. At about 10 MB/s, pocket takes under an hour and full a day or two.

Every edition bigger than pocket also carries a **pocket kit** (about 15 GB): with it, anyone holding the drive can make a pocket copy on a stick with no internet and nothing installed (`arc/Make a pocket copy`).

It is **safe to stop** with Ctrl+C or by closing the window: run it again and it carries on where it stopped. Running it again later also brings the drive up to date: items added to the catalog since are downloaded and added. When it's done, open `1 START-HERE` on the drive and print the card (Keep it alive > The card to print).

Options: `python make-arc.py --drive E:\ --edition core --yes` asks no questions; `--archive D:\arc-archive` keeps the downloads in a separate folder (useful to build several drives); `--no-search` skips the two build packages that make the guides searchable. The step-by-step build behind it is in `scripts/README.md`.

## Repository layout

| Path | Contents |
|---|---|
| `CLAUDE.md` | Project context, decisions and working rules |
| `NEXT-SESSION.md` | Where things stand and the phase plan |
| `docs/architecture.md` | What the arc is, the user journey, drive layout, navigation, editions, decisions |
| `catalog/` | Approved publishers, the item catalog and the topics (coverage) that drive the build |
| `scripts/` | Download, assemble, website, verify and mirror scripts |
| `frontdoor/` | Inputs for the website: emergency numbers, notes, checked page lists |
| `launchers/` | Open the full library on Windows, Mac and Linux |
| `make-arc.py`, `.bat`, `.command` | Make your own arc on a drive, in one double-click |
| `hosted/` | The few documents whose publishers' sites refuse downloads by script (sources and licences in `hosted/README.md`) |

## Principles

- Trusted sources only; every item is recorded in the catalog with its origin.
- Open formats (ZIM, PDF, HTML, MP4) readable for decades on any system.
- Written for a stranger: one obvious entry, plain words, nothing to install.
- Start-here guides never depend on a program.
- Several identical, verified copies in different places, made to be passed on.

## Licence

The recipe (scripts, launchers, website generator, catalog, texts and docs) is under the MIT licence: see `LICENSE`. The documents in `hosted/` and everything the scripts download are not: each stays under its publisher's own terms, recorded in the catalog's `licence` column and in `hosted/README.md`.

## Status

21 Nov 2026: vision reset agreed (offline learning website for anyone, replacing the family crisis-kit design). The catalog holds 150 checked items (13 of them programs) in four editions (pocket ~26 GB, core ~150 GB, standard ~285 GB, full ~660 GB). The scripts build the whole drive: the website, the arc's own searchable collection, the launchers (including Wi-Fi sharing), the printed card and the maintenance guide (phases 1-6 done; next steps in `NEXT-SESSION.md`). 22 Nov 2026: anyone with the repository can make their own arc (`make-arc`); every item in the catalog goes on, and new catalog items join automatically on the next run.
