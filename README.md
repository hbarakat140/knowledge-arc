# Knowledge Arc

Build recipe for an offline knowledge arc: **an offline website on a drive** that carries trusted practical knowledge, reference, education and culture across a time without internet. Anyone who has a copy can use it, learn from it and pass it on, with nothing installed and nobody there to explain it.

This repository contains the **recipe**, not the content: the catalog of sources, the scripts that download, check and assemble them, the website generator and the launchers. The arc itself (ZIM collections, PDFs, videos, software) is written to drives and is not committed here, except a handful of documents whose publishers' sites block scripts (`hosted/`).

## How someone uses a copy

1. **Open `1 START-HERE`** at the top of the drive. It opens in any browser with nothing installed: subjects, topics and the start-here guides.
2. **One double-click on "2 Open full library"** for that computer starts the library engine from the drive. START-HERE then becomes the full website: the same subjects plus the big collections (Wikipedia, medicine, repair guides, books, courses, maps, videos) and one search over the collections that have a search index (the others are marked "open to browse").
3. **On an Android phone**, install the Kiwix app from the drive to open the collections; the guides open from the Files app.

Everything is organised by **subject** (health, food and farming, making and repairing, science, history, stories, arts...) and by **shelf** (guides, books, encyclopedias, courses, videos, films, music, maps), with doors for children, search and an A-Z of topics. See `docs/architecture.md`.

## Make your own arc

Anyone can build an arc from this repository while the internet works.

### Before you start

- [ ] **A drive** big enough for the edition you want (table below), **formatted exFAT** (or NTFS, APFS, ext4). Not FAT32: most new 32 GB sticks and SD cards come as FAT32, which can't hold a file over 4 GB. The script refuses FAT32 and tells you how to reformat it. Use an empty drive: reformatting erases it.
- [ ] **An internet connection without a data limit.** The script downloads a little less than the edition holds: about 20 GB for pocket, 244 GB for core, 341 GB for standard, 711 GB for full. Not a phone's mobile data. At about 10 MB/s, pocket takes under an hour and full a day or two.
- [ ] **A computer** with Windows 10 or 11, a Mac or Linux. Any of the three builds the same arc. **Nothing to install:** the script uses the computer's own Python if it is 3.11 or newer, and otherwise fetches a portable Python once (25-36 MB, checked against its fingerprint) into the computer's own cache folder: `%LOCALAPPDATA%\knowledge-arc` on Windows, `~/Library/Caches/knowledge-arc` on a Mac, `~/.cache/knowledge-arc` on Linux. Delete that folder afterwards to remove it. The searchable guides need macOS 13 or newer, or a Linux from 2018 or later; on older ones the script says so and asks first.
- [ ] **Power.** A laptop stays plugged in with its lid open. The script keeps the computer awake while it works (Windows, Mac, and Linux with systemd); on another system, turn off sleep first.

Before it downloads anything, the script checks the drive, the space, and the internet (one item from each website), and says plainly what is wrong. To check every item's source without downloading, run `make-arc.bat --check` (Windows, in a Command Prompt in this folder) or `sh make-arc.command --check` (Mac, Linux).

### Then

1. Get this repository: **Code > Download ZIP** on GitHub (unzip it), or `git clone`.
2. Plug in the drive.
3. Double-click **`make-arc.bat`** (Windows) or **`make-arc.command`** (Mac, Linux). With Python 3.11 or newer already on the computer you can also run `python make-arc.py`. (On a Mac, if it says the file can't be opened: right-click it, Open, then Open again; or in Terminal, `sh make-arc.command`.)
4. Choose the drive and the edition. The script offers the largest edition that fits:

   | Edition | On the drive | For |
   |---|---|---|
   | pocket | about 24 GB | a phone or a 32 GB stick: every guide, medicine, repairs, Wikipedia's most important articles, classics in translation, short films, the programs |
   | core | about 259 GB | adds the full Wikipedia with pictures, the map of France, children's books, English and European literature, textbooks, Crash Course videos, more references |
   | standard | about 357 GB | adds community answers, books, courses and textbooks |
   | full | about 727 GB | adds all of Project Gutenberg, Khan Academy, Wikisource, maps of Europe |

5. Read the checks it shows, then start. It downloads every item from its publisher (or, for the few sites that refuse scripts, from this repository's `hosted/` folder), checks each file's fingerprint, and builds the drive. An item whose site doesn't answer is left out and listed; run the script again later to add it.

Every edition bigger than pocket also carries a **pocket kit** (about 15 GB): with it, anyone holding the drive can make a pocket copy on a stick with no internet and nothing installed (`arc/Make a pocket copy`).

It is **safe to stop** with Ctrl+C or by closing the window: run it again and it carries on where it stopped. Running it again later also brings the drive up to date: items added to the catalog since are downloaded and added. When it's done, open `1 START-HERE` on the drive and print the card (Keep it alive > The card to print).

Options: `python make-arc.py --drive E:\ --edition core --yes` asks no questions; `--archive D:\arc-archive` keeps the downloads in a separate folder (useful to build several drives); `--no-search` skips the two build packages that make the guides searchable; `--check` checks everything and downloads nothing. The step-by-step build behind it is in `scripts/README.md`.

## Repository layout

| Path | Contents |
|---|---|
| `CONTRIBUTING.md` | The rules every change follows (quality bar, licences, rules 1-10) |
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

**Work in progress (November 2026).** The scripts build the whole drive: the website, the arc's own searchable collection, the launchers (including Wi-Fi sharing), the printed card and the maintenance guide, and anyone with this repository can make their own arc (`make-arc`). Still to come before a first release:

- a first real build of each edition, and tests on real drives, a Mac and Android phones;
- the sha-256 of every downloaded document recorded in the catalog.

Sizes on a drive today: pocket about 24 GB, core about 259 GB, standard about 357 GB, full about 727 GB. Design and decisions: `docs/architecture.md`; how items are chosen: `docs/catalogue-strategy.md` and `docs/content-review.md`.
