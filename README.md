# Knowledge Arc

**A library you can carry on a drive, for a world without internet.**

The Knowledge Arc is a website that lives on a USB drive or memory card. It holds trusted, practical knowledge (first aid and medicine, growing food, clean water, repairs, building, energy), plus an encyclopedia, school subjects, books, courses, maps and films. It works with **no internet and nothing to install**: plug in the drive, open one file, and start reading.

It is made to be **copied and passed on**. Anyone who has a copy can use it, learn from it and make copies for others, years from now, with nobody there to explain it.

> **Status: work in progress (November 2026).** Everything described here works, and you can make your own drive today. A first official release will follow tests on real drives, Macs and Android phones.

---

## What is inside

Everything is sorted by **subject**, then by **topic**, and every topic says where to start.

| Subject | Examples |
|---|---|
| Health & medicine | First aid, *Where There Is No Doctor*, medicines, pregnancy and birth, mental health, a medical encyclopedia |
| Food & farming | Growing vegetables, keeping animals, preserving food, wild food, cooking |
| Home, water & energy | Making water safe, toilets, heating, solar power, getting ready for a crisis |
| Making & repairing | Repair guides, tools, wood, metal, textiles, electricity, computers |
| Maps, radio & travel | Map reading, weather, radio, maps of France and Europe |
| Science, maths & nature | How science works, physics, chemistry, life, the sky, maths, plants and animals |
| History, society & ideas | History, countries, rights and law, money, philosophy, the world's sacred texts |
| Languages & reference | Wikipedia, dictionaries, learning French, English and other languages, sign language and Morse |
| Learning & teaching | School maths and reading, early childhood, how to study, teaching others |
| Stories & literature | Classic novels and poems, Shakespeare, books from around the world, children's books |
| Arts, music & games | Reading music, songs, drawing, art from every continent, rules of games, puzzles, films |

Every item comes from a **trusted publisher**: the World Health Organization, universities, national agencies, museums, Wikipedia, Project Gutenberg and others. Each one is listed, with where it came from and its licence, in [`catalog/catalog.csv`](catalog/catalog.csv).

---

## You have a drive? Here is how to open it

1. **Plug in the drive** and open it like any folder.
2. **Double-click `1 START-HERE`.** It opens in your web browser, with no internet. You can read every guide straight away.
3. **For everything else** (Wikipedia, the big libraries, search), double-click **`2 Open full library`** for your computer (Windows or Mac). A small window opens: keep it open while you read. Your browser then shows the whole library with one search box.

**On an Android phone or tablet:** install the *Kiwix* app (its installer is on the drive, in `arc > software > android`), then open the library's files from the drive. The guides open with any PDF reader.

**iPhone and iPad:** not designed for, but the guides (PDFs) open from the *Files* app.

Inside the drive, *Keep it alive* explains how to check the drive, copy it, print its small card, and share it over Wi-Fi.

---

## Make your own drive

You can build a Knowledge Arc yourself, while you still have internet. The script downloads everything from the original publishers, checks every file, and builds the drive. You do not need to know how to code.

### 1. Choose a size

| Edition | Space needed | Good for | What it adds |
|---|---|---|---|
| **Pocket** | about 24 GB | a phone, or a 32 GB stick or memory card | All the guides, a medical encyclopedia, repair guides, Wikipedia's 50,000 most important articles in full (and the opening of a million more), 79 classic books, Shakespeare, world literature, short films, and the programs to open them |
| **Core** | about 259 GB | a 500 GB drive | Adds the complete Wikipedia with pictures, the map of France, children's books, English and European literature, textbooks, educational videos |
| **Standard** | about 357 GB | a 500 GB drive | Adds courses, more textbooks, picture books, and question-and-answer sites |
| **Full** | about 727 GB | a 1 TB or 2 TB drive | Adds all of Project Gutenberg (about 60,000 books in English), Khan Academy, Wikisource, maps of Europe |

Each edition contains everything in the smaller ones. Every drive bigger than *Pocket* can also make *Pocket* copies on a stick, later, without internet.

### 2. Check what you need

- [ ] **A drive** with enough space, ideally empty. It must be formatted **exFAT** (works on Windows, Mac and Linux). Many new sticks and memory cards come as *FAT32*, which cannot hold large files: the script spots this and tells you how to change it. *Changing the format erases the drive.*
- [ ] **Internet without a data limit** (not a phone's mobile data). The download is about **20 GB** for Pocket, **244 GB** for Core, **341 GB** for Standard and **711 GB** for Full. On a typical home connection, Pocket takes under an hour; Full takes a day or two.
- [ ] **A computer** with Windows 10 or 11, a Mac, or Linux. **Nothing to install first.**
- [ ] **Power:** keep a laptop plugged in with the lid open. The script stops the computer from going to sleep while it works.

### 3. Run it

1. **Download this project:** on this page, click the green **Code** button, then **Download ZIP**, and unzip it.
2. **Plug in your drive.**
3. In the unzipped folder, **double-click**:
   - **`make-arc.bat`** on Windows
   - **`make-arc.command`** on a Mac or Linux. *(If a Mac says it cannot open it: right-click the file, choose Open, then Open again.)*
4. **Answer its questions:** which drive, and which edition. It suggests the largest edition that fits.
5. **Read its checks, then let it run.** It tells you in plain words if anything is wrong (drive format, space, internet) before it downloads anything.

**It is safe to stop** at any time (close the window). Run it again and it carries on where it stopped. Running it again months later also adds anything new to the drive.

**When it is done:** open `1 START-HERE` on the drive and print the small card (*Keep it alive > The card to print*). Keep the drive somewhere safe, make a second copy, and give copies away.

---

## Questions

**Is it free?** Yes. Everything in it is free to download from its publisher. This project only gathers it, checks it and organises it.

**Is it legal to copy and share?** The website and scripts are free to share (MIT licence). Each book and guide keeps its publisher's own terms, which are recorded item by item. Most are public domain or openly licensed; a publisher who objects can ask for its item to be removed.

**Does it need updating?** No. Once built, it works on its own for years. You can refresh it whenever you have internet by running the script again.

**Why not just save web pages?** Because a stranger needs to find their way: the Knowledge Arc sorts everything by subject, says where to start, and explains itself on every page.

**Can I help?** Yes: see [`CONTRIBUTING.md`](CONTRIBUTING.md) for how items are chosen and checked.

---

<details>
<summary><b>For technical users</b>: options, layout and how it works</summary>

### Command-line options

`make-arc` uses the computer's own Python 3.11 or newer if there is one. Otherwise it fetches a pinned, checked portable Python once (25-36 MB) into the user's cache folder (`%LOCALAPPDATA%\knowledge-arc` on Windows, `~/Library/Caches/knowledge-arc` on a Mac, `~/.cache/knowledge-arc` on Linux), never onto the drive. Delete that folder afterwards to remove it. The searchable guides need macOS 13 or newer, or a Linux from 2018 or later.

- `python make-arc.py --drive E:\ --edition core --yes`: no questions asked
- `--archive D:\arc-archive`: keep the downloads in a separate folder (to build several drives)
- `--no-search`: skip the packages that make the guides searchable
- `--check`: check every source and download nothing (`make-arc.bat --check`, or `sh make-arc.command --check`)

The step-by-step build behind it is described in [`scripts/README.md`](scripts/README.md).

### How a drive is laid out

The top of a drive holds only `1 START-HERE.html`, the two `2 Open full library` launchers, and a folder `arc/` with everything else: the website, the guides (PDF and HTML), the collections (ZIM files, read by the Kiwix engine that runs from the drive), the programs for each system, and a copy of this recipe. Design and decisions: [`docs/architecture.md`](docs/architecture.md).

### What is in this repository

This repository is the **recipe**, not the content. The books, collections and programs are downloaded from their publishers when a drive is built.

| Path | Contents |
|---|---|
| `make-arc.py`, `.bat`, `.command` | Make a drive in one double-click |
| `catalog/` | Every item (`catalog.csv`), the approved publishers, the topics, pinned file lists |
| `scripts/` | Download, assemble, website, verify and copy scripts |
| `launchers/` | Open the full library on Windows, Mac and Linux |
| `frontdoor/` | Inputs for the website: emergency numbers, notes, learning paths |
| `hosted/` | The few documents whose publishers' sites refuse downloads by script (sources and licences in `hosted/README.md`) |
| `docs/` | Architecture, how sources are chosen, the content review |
| `tests/` | The checks every change must pass (`python -m pytest -q`) |
| `CONTRIBUTING.md` | The rules every change follows |

### Principles

- Trusted sources only; every item recorded in the catalog with its origin and licence.
- Open formats (ZIM, PDF, HTML) readable for decades on any system.
- Written for a stranger: one obvious entry, plain words, nothing to install.
- Start-here guides never depend on a program.
- Several identical, verified copies in different places, made to be passed on.

### Still to do before a first release

- A first real build of each edition, and tests on real drives, a Mac and Android phones.
- The fingerprint (sha-256) of every downloaded document recorded in the catalog.
- Planned additions: recordings and films, the audio for the language courses, and tools to run code offline.

</details>

---

## Licence

The recipe (scripts, launchers, website generator, catalog, texts and docs) is under the **MIT licence**: see [`LICENSE`](LICENSE). The documents in `hosted/` and everything the scripts download are **not** covered by it: each keeps its publisher's own terms, recorded in the catalog's `licence` column and in [`hosted/README.md`](hosted/README.md).
