# Knowledge Arc — Architecture (v0.3)

*Status: vision reset agreed with the owner on 21 Nov 2026 (sections 1-4, 7, 10). Navigation tags (phase 2) and the drive layout (phase 3) are built; the website (phase 4), the pocket edition (phase 5) and the card and keep-alive instructions (phase 6) followed the same day; the README's Status section says what is still to come. Section 12 records the launcher prototype, first tested on the v0.2 layout and re-run on the new one. Section 13 records the AI helper agreed on 25 Nov 2026 (not built).*

---

## 1. Design principles

1. **The drive is the product.** Everything needed to read the content lives on the drive, including the software. Nothing assumes an internet connection or a pre-installed app.
2. **It explains itself.** A stranger who finds a copy years from now, with none of us there, can tell what it is, use it, keep it alive and pass it on.
3. **A learning library, not a crisis tool.** People browse subjects and learn. Emergencies and first aid are a topic like any other.
4. **Degrade gracefully.** With the library engine running: one website, one search over the indexed collections. With no program at all: the website's pages and every start-here guide still open in a plain browser.
5. **Open formats only.** ZIM, PDF, HTML, plain text, images, MP4. No databases, no containers, no proprietary formats as the only copy of anything.
6. **Trusted sources only.** Every item comes from an approved publisher or has been individually reviewed, and every item is recorded in the catalog with its origin.
7. **Built to grow.** A stable top level of subjects; new topics, items, shelves and editions slot in without a redesign. Pages are generated from the catalog.
8. **AI-ready, not AI-dependent.** Real text and clean metadata, so a future local AI can index it; nothing requires AI.

---

## 2. What the arc is, and how someone uses it

**An offline website on a drive.** Plain files underneath (PDF, ZIM), a small portable engine on the drive (the Kiwix library server, which runs without installing), a website on top.

### The journey of someone who holds a copy

1. **They open the drive.** The top level shows four things only (section 3). A sticker on the drive says "Offline library: double-click 1 Open Knowledge Arc".
2. **They double-click `1 Open Knowledge Arc`** for their computer (Windows or Mac; D19, 25 Nov 2026). On Windows a small "Knowledge Arc" window appears at once ("Opening the library..."), the library engine starts hidden, and **one** browser opens on the library. The window has two buttons, "Open the library again" and "Close the library"; closing it stops the engine. No console window stays open.
3. **If nothing opens,** they double-click `2 If nothing opens.html`. It opens in the browser on any computer, with no program and no script: a short panel says what to try (the launcher again, a plain link to the library, the Kiwix reader, Android, reading the guides), then the usual home. Every topic page works, and every start-here guide (PDF) opens.
4. **The library runs: one website**, the same subjects and topics, plus the big collections (Wikipedia, medicine, iFixit, CD3WD, Gutenberg, courses, maps), and **one search** over every collection that has a search index. Collections built without one (iFixit, LibreTexts, Khan Academy, all-Gutenberg, maps; section 12) are marked "open to browse". Closing the small window stops it and leaves nothing on the computer.
5. **On an Android phone:** plug in the drive (USB-C, or an adapter), open guides from the Files app, install the Kiwix app from `arc/software/android/` to open the collections. The arc's own collection shows the same subjects.
6. **Passing it on:** copy the whole drive to another exFAT drive, or make a pocket copy (section 7). The maintenance guide explains how, for a stranger.

**The drive carries its own programs** (phase 4d, owner 21 Nov 2026), so nothing on the computer has to work except the operating system: `1 Open Knowledge Arc` opens the library in the drive's own Firefox ESR (`arc/software/windows/firefox/`, Mozilla's Mac disk image, or the Linux build), in a fresh temporary profile with `arc/software/firefox-user.js` (no first-run pages or update attempts), and falls back to the computer's browser. The How to use page lists, for whatever is on the drive, what to open when something fails: the drive's Firefox, SumatraPDF (Windows) or MuPDF (Android) for the guides, and the Kiwix desktop reader (Windows, Mac, Linux), which opens the collections with no browser and no server. Windows Firefox is unpacked from Mozilla's installer with its `/ExtractDir` switch, so that step needs a Windows build machine. Tested on Windows 21 Nov 2026: the launcher started the drive's Firefox, which showed the arc's home.

**iPhones** are not designed for: they can open the PDF guides from the Files app, nothing more. **Sharing over Wi-Fi** from a laptop (so phones nearby read in their browser) is a secondary, advanced option: it raises the Windows firewall question, so it has its own launcher and lives in the advanced instructions.

### Users, devices and power

- **Users:** anyone, from technical to non-technical, adults, teens and children (children with an adult or through the "For children" door).
- **Devices:** Windows and Mac laptops, Android phones and tablets. Linux possible.
- **Power:** may be limited. The arc must stay usable from a charged Android phone (the pocket arc is sized for that).

---

## 3. Drive layout (built since phase 3, 21 Nov 2026)

```
/  (drive root)
├── 1 Open Knowledge Arc (Windows).bat ← starts the library from the drive and opens it in the browser
├── 1 Open Knowledge Arc (Mac).command
├── 2 If nothing opens.html            ← the website with no program (opens in any browser, no script)
└── arc/
    ├── START-HERE.txt                 ← plain-text twin, for a computer without a browser
    ├── open-knowledge-arc.sh          ← Linux (--share: over Wi-Fi)
    ├── Share over Wi-Fi (Windows).bat ← advanced: phones nearby read the library in a browser
    ├── Share over Wi-Fi (Mac).command
    ├── Make a pocket copy (Windows).bat ← above pocket: makes a pocket copy on a stick, offline
    ├── Make a pocket copy (Mac).command
    ├── pocket/                        ← above pocket: the pocket kit, laid out like a pocket drive
    ├── site/                          ← the website's other pages (subjects, topics, shelves, doors)
    ├── guides/<subject>/              ← PDFs: start-here guides and other books, one folder per subject
    ├── collections/                   ← ZIMs: encyclopedias, courses, videos, maps, the arc's own collection
    ├── software/                      ← windows/, mac/, linux/ (Kiwix server), android/ (Kiwix app)
    └── system/                        ← CATALOG.csv, CHECKSUMS.sha256, VERSION.txt, verify.bat/.sh,
                                         MAINTENANCE.txt, library-home.html, open-knowledge-arc.ps1 (the
                                         Windows small window), recipe/ (the build recipe);
                                         site/ also holds card.html, the card to print, and paper.html, what to print
```

Rules:
- **Only four things at the top.** Everything a stranger shouldn't have to understand lives in `arc/`. The names start with 1 and 2 because Windows Explorer and the Mac Finder sort by name: the launcher comes first, the fallback page second, `arc/` last. A rebuild removes the entry files of earlier builds (`1 START-HERE.html`, `2 Open full library (...)`, `arc/open-full-library.sh`; `assemble.RETIRED`) if they name the arc, so the old way in never sits next to the new one.
- **Catalog paths are drive paths.** Each catalog row's `folder` starts with `arc/` (`arc/guides/<home subject>/`, `arc/collections/`, `arc/software/<os>/`); the lint checks it against the row's tags. The archive (staging) uses the same paths.
- **The recipe travels with the arc.** `arc/system/recipe/` holds the files git tracks (catalog, scripts, docs, tests), so anyone holding a copy can refresh or rebuild it.
- **Start-here guides exist as PDF or HTML,** even if they are also inside a ZIM (CONTRIBUTING.md rule 3). Topics whose start-here is a collection (Wikipedia, Gutenberg, courses) are exempt.
- **Plain, descriptive English file names** (`poultry-slaughter-smallholder_hsa_2016.pdf`), no special characters, folder names that read as words.

The v0.2 layout (`00_EMERGENCY/`, `01_LIVING/`, `02_KNOWLEDGE/`, `90_SOFTWARE/`, `99_SYSTEM/` at the root, by tier) was replaced in phase 3.

---

## 4. The website and its navigation

### Research basis (21 Nov 2026)

- **Separate topic and format schemes** (Rosenfeld & Morville, *Information Architecture*): grouping by subject suits browsing, grouping by format or A-Z suits finding a known thing. Mixing both in one list confuses ("which aisle has the marshmallows?"), so they are two separate menus.
- **Flat beats deep** (Nielsen Norman Group): every extra level loses people; top labels must be distinct and not overlap; add shortcuts (A-Z, most used) and breadcrumbs. Kolibri keeps topic trees 2-4 levels deep.
- **Independent facets** (Europeana's "Theme" and "Type of media" filters; the Internet Archive's media types plus collections, an item in several collections). Faceted navigation tests well in digital libraries when the tags are consistent and people are tested regularly (Blumer, Hügi & Schneider 2014).
- **A stable top covering all knowledge** (Britannica's *Outline of Knowledge*, 10 parts read as a circle; Dewey's 10 classes): new things go in underneath, the top doesn't change.
- **Plain labels on top, precise codes underneath** (public libraries moving from Dewey to bookstore-style BISAC categories browse better, Dewey stays more precise at scale; evidence is thin).
- **What comparable offline projects do:** Internet-in-a-Box and Kiwix show a flat list of packages, with no subject layer.

### The scheme (agreed 21 Nov 2026)

**Subjects** (main menu; stable; plain labels) → **topics** (the areas in `catalog/coverage.csv`, 35 today) → **items**. Big topics are split into **sections** (a 4th level, owner 21 Nov 2026): Animals has Poultry, Small animals, Sheep and goats, Pigs, Cattle, Bees, Animal health; each section has its own "start here" items. The owner expects more depth over time, so new levels go in as sections first.

| Subject | Topics today (coverage ids) | Room for later |
|---|---|---|
| Health & medicine | S1 first aid and emergency care, H1 medicine and diagnosis, H2 medicines, H3 pregnancy, birth and children's health, H4 dental, mental health, disability, H5 nutrition | |
| Food & farming | F1 growing food, F2 animals and livestock, F3 cooking, preserving and storing, F4 wild plants, fungi, hunting and fishing, B6 farming at scale | forestry, fishing |
| Home, water & energy | S2 drinking water and sanitation, S3 shelter and warmth, S4 preparedness, E1 energy off the grid | household skills |
| Making & repairing | R1 repair, R2 building, B1 tools and metalwork, B2 woodworking and crafts, B3 textiles and leather, B4 practical chemistry and materials, B5 electricity and electronics, B7 engineering and machines | vehicles, computers |
| Maps, radio & travel | C1 communication and radio, N1 maps, navigation, weather, time | transport |
| Science, maths & nature | U2 science, U3 mathematics | ecology, astronomy, nature |
| History, society & ideas | U4 history, geography, law and society | philosophy, religion, economics |
| Languages & reference | U1 encyclopedias and reference, U5 languages and dictionaries | other-language editions |
| Learning & teaching | T1 school curriculum, T2 children's reading, T3 teaching others | |
| Stories & literature | K1 literature and books | poetry, plays, children's stories |
| Arts, music, films & games | K2 arts, music and play | films, sport, games |

**Shelves** (second menu, by format): Guides & manuals · Books · Encyclopedias · Courses · Videos · Films · Music & audio · Maps.

**Doors:** For children (gathers children's items from every subject) · Search everything (full library) · A-Z of topics.

**Home page:** a short "what is this", the subjects, the shelves, the doors, then "Keep it alive and pass it on" (check, copy, pocket copy) and "About this arc" (who made it, when, how sources were chosen, link to the catalog).

**Topic page:** breadcrumbs (Home › Subject › Topic), then:
1. **Start here:** the item(s) whose job is primary, with one line on what they teach.
2. **Go deeper:** the depth items.
3. **In the big library:** deep links and ready-made searches into Wikipedia, CD3WD, Gutenberg and other collections, built from the topic's keywords in `coverage.csv`. They work when the full library runs; without it the page says so.
4. **Related topics.**

**Placement rules:**
- Each item has one home topic and can appear in others (a farming film lives in Food & farming and on the Films shelf).
- Big multi-subject collections (Wikipedia, CD3WD, Gutenberg, Khan Academy) live on their shelf and appear inside each relevant topic as "in the big library" entries.
- Community content (Stack Exchange, WikiCiv, Low-tech Magazine) is always labelled "community answers".
- First aid is a topic under Health. The checked page links of the old emergency list (`frontdoor/situations.csv`) become its "where to look" list; the French emergency numbers (`frontdoor/numbers.csv`) appear there and on the card.

**Tags that drive it** (added 21 Nov 2026): each catalog row has `label` (the name people see, when the title is a code or not unique), `topic` (coverage ids, home first), `section` (one of its home topic's sections, or blank), `shelf` (the format shelves above, plus `community` for labelled community answers and `software`), `audience` (all, children, advanced) and `job` (primary, depth, cross-check, gap-filler, copy), which sets its order: primary items are the topic's "start here". `catalog/subjects.csv` lists the subjects; `coverage.csv` gains a `subject` column. All pages are generated from these by the build.

**Two ways into the same site:**
- **No program** (`file://`): `2 If nothing opens.html` and the pages in `arc/site/`, with links to the PDFs. The fallback since D19 (25 Nov 2026); before, it was the front door (`1 START-HERE.html`, D11).
- **Full library** (built in phase 4b, 21 Nov 2026): the same pages and the guides packed as the arc's own collection, `arc/site/knowledge-arc_en_all.zim` (`scripts/arczim.py`, with libzim and pypdf from `requirements-build.txt` on the build machine only; never needed by users). The launchers serve it with the other collections; the library home page (`/`) opens it, unless the address asks for a search (`?q=`) or the list of collections (`?list`). Its home page has one search box over the arc's own pages, the guides' text (extracted with pypdf and given to the index) and every indexed checked collection; community answers keep their own box. Each guide also gets a small guide page (`<pdf>.html`) that carries its text in the index and links to the PDF, because Kiwix builds result snippets from the stored item and raw PDF bytes are unreadable. Tested in a visible Chrome on 21 Nov 2026: a search for a word found only inside a guide PDF ("scalding") returns its guide page with a readable snippet, and the PDF opens in Chrome's viewer, also at `#page=N` from a topic page (the PDF responses carry no sandbox policy). The file lives in `arc/site/` (generated, not a catalog item), so it is fingerprinted and mirrored but never pruned; its bytes change on every build. Without the build packages the build still works and prints a NOTE.

**Search and indexing: what to fix** (owner, 25 Nov 2026: "put the indexing/search feature as a thing to fix"). How it works today: each collection's own full-text index (built by openZIM, not by us); the arc's own collection, whose index holds the site's pages, the HTML books and the text of every guide; and, with no program running, `arc/site/search.html`, which searches names and one-line descriptions only. The gaps, in order:
1. **One search, in the arc's design** (step 4 of the "one door, one website" redesign): today a search lands on Kiwix's own results page, collections without an index are skipped, and community answers need their own box.
2. **Guides indexed page by page**: a guide is one entry in the index today, so a search finds the guide but opens it at page 1. Index each PDF page as its own entry linking to `<pdf>#page=N`. The AI helper needs this too (section 13).
3. **Collections without a full-text index** (iFixit, LibreTexts, Khan Academy, all-Gutenberg, maps) are found only by title (`/suggest`); a title-only match must say so.
4. **Scanned PDFs without a text layer** (catalog `text_layer` = n) cannot be found by their words. OCR at build time is possible, but its text must be checked before it is trusted.
5. **Ranking across collections** is Kiwix's, per collection; results are grouped by collection rather than mixed.
6. **Search by meaning** (not just matching words): later, with the AI helper (section 13).

---

## 5. Formats

| Content type | Format on drive | Why |
|---|---|---|
| Websites / encyclopedias / courses | ZIM (Kiwix) | Compressed, searchable, standard, readable by other tools later |
| Guides, manuals, books | PDF with real text layer | Opens in any browser; searchable; AI-indexable |
| The website | HTML (and the arc's own ZIM) | Zero dependency in the browser; search in the full library |
| Ebooks | PDF preferred; EPUB kept alongside if that's the original | Windows has no built-in EPUB reader |
| Maps | ZIM (Kiwix OpenStreetMap) and/or PDF map sheets | Search + printable fallback |
| Videos, films, music | MP4 / audio files, or ZIM where Kiwix packages a channel or course | Shelves of their own |

Scanned-image PDFs are only accepted when nothing better exists, and are flagged in the catalog (not searchable, not AI-indexable).

---

## 6. Quality gate ("no garbage")

1. **Approved publisher list** (`catalog/publishers.csv`). Institutional and established sources only.
2. **Anything outside the list** needs an individual review, recorded in the catalog with who reviewed it and why it's included.
3. **Every item gets a catalog row** in `catalog/catalog.csv`. Its header is the canonical schema; see `catalog/README.md`. `download_date` and `sha256` are filled by the download script.
4. **Medical content gets a date check.** Prefer the newest edition; note the edition in the file name.
5. **The catalog is the gate** (D14, owner, 21 Nov 2026). Every row of an edition goes on the drive if its publisher is `approved`, `approved-pending-owner` or `item-review-required`; there is no separate sign-off step, so a row added to the catalog joins every arc built after it, including arcs others make with `make-arc.py`. The checks happen before a row is added (verified source, approved publisher, contents read). The first-aid guides (formerly Tier 1, 7 items) are read item by item. Spot checks per collection (D9) are still recorded in `reviewer`, as a record.

---

## 7. Editions and copies

| Edition | Size | Holds | For |
|---|---|---|---|
| **pocket** | ~24 GB (32 GB card or stick; limit 29 GB) | the website, every document (all PDFs, every layer, except a few big books the owner placed in core), the medical encyclopedia, repairs (iFixit, CD3WD), Wikipedia (the 50,000 most important articles in full and the opening of the 1 million most-read, no pictures), Shakespeare (Folger, 42 PDFs), classic literature in translation (Greek and Latin, Slavic, German and Scandinavian, Middle Eastern, Indian and Persian, East Asian; 1.8 GB), Blender Studio's open movies, all the programs | phones, small sticks, passing on |
| **core** | ~259 GB | adds the full Wikipedia with pictures, the France map, Wikibooks, Gutenberg children's books, English literature and French, Italian, Spanish and Portuguese literature in English, OpenStax textbooks (biology, the human body, algebra, statistics, chemistry, astronomy), Crash Course videos, more medical and energy references | the everyday copy |
| **standard** | ~357 GB | adds community answers, Gutenberg subject sets, courses and textbooks, picture books, Wiktionary | the main copy |
| **full** | ~727 GB | adds all of Gutenberg, Khan Academy, Wikisource, Europe maps | the master and the station |

Each edition includes the one before. Since phase 5 (21 Nov 2026) every document is in every edition, because documents are small (exceptions, decided by the owner one by one so pocket keeps its room: the OpenStax textbooks *Anatomy and Physiology* and *Concepts of Biology*, 22 Nov 2026; *Elementary Algebra*, *Introductory Statistics*, *Chemistry* and *Astronomy*, NIST's *From Sundials to Atomic Clocks* and the EU soil biodiversity atlas, 23 Nov 2026; more from the history, languages and arts reviews, among them a college music theory textbook and Smarthistory's two art history volumes, 24 Nov 2026; all start in core and are listed in the catalog test. Pocket must stay under 29 GB on the drive); the editions differ in their collections. Survive, sustain and rebuild size the collections; they are not the navigation. Each copy says which edition it is (home page and About, with what the bigger editions add).

**Pocket copies from any bigger drive** (owner, 22 Nov 2026; D16). A bigger drive carries the **pocket kit**, `arc/pocket/`, laid out like a pocket drive: the pocket edition's own pages, its search collection, catalog, version log and file list (`arc/pocket/arc/system/CHECKSUMS.sha256`), and the pocket rows the bigger edition replaces (the pocket edition's two Wikipedias, 8 GB; the drive's own library never sees them). `arc/Make a pocket copy` copies each listed file from the kit if it is there, else from the drive, then checks every file on the copy. It needs no internet and no Python (CONTRIBUTING.md rule 10): PowerShell on Windows, `sh` on Mac and Linux; it refuses FAT32 when a file is 4 GB or more, and a stopped copy carries on. Tested 22 Nov 2026 on the whole catalog with placeholder files: the copy made from a core drive equals a direct pocket build (577 files, identical pages, no broken links). The kit costs about 15 GB per bigger drive.

- **File system: exFAT.** Readable and writable on Windows, Mac, modern Linux and Android, and handles files over 4 GB. FAT32 sticks cannot hold the big collections; the maintenance guide warns about this.
- **Several identical copies, at least two media types, in different places,** and more copies made to pass on. One master is built and verified, then mirrored; copies are checked against `CHECKSUMS.sha256`.
- **Size:** 2 TB for the full master (room to grow); copies sized by edition.

---

## 8. Maintenance (light)

- **Every 6–12 months:** plug each drive in, run `verify`, open a few files. Drives left in a drawer can degrade silently; this catches it while other copies are still good.
- **Optional refresh** while the internet works: update key items on the master, regenerate checksums, re-mirror. For a single drive, running `make-arc` again adds the items new in the catalog.
- **Version log** in `VERSION.txt`.
- **On the drive:** `arc/system/MAINTENANCE.txt` (source: `scripts/drive/MAINTENANCE.txt`), plain text, written for a stranger (phase 6, 21 Nov 2026): open it, check, repair a file from another copy, make a copy (with how to see and fix the FAT32 trap), put it on an Android phone, why a pocket copy can't be cut from a bigger drive, share it over Wi-Fi (advanced), storing, when something doesn't work, and Part 2 (refresh or rebuild with the recipe: `download.py --bundle all` into the archive, `assemble.py --bundle <edition>`).
- **Sharing over Wi-Fi:** `arc/Share over Wi-Fi (Windows).bat` runs the everyday launcher with `ARC_SHARE=1`, and `arc/Share over Wi-Fi (Mac).command` (Linux: `open-knowledge-arc.sh --share`) does the same: kiwix-serve listens with `-i all` instead of `-i 127.0.0.1`, and the window lists this computer's addresses for the phones. The everyday launcher never asks the firewall question.

---

## 9. The tiny card and the paper copy

One printed page, kept with each drive: the French emergency numbers, what the arc is, how to open it on a computer and on an Android phone. Built with the website (phase 6, 21 Nov 2026): `arc/site/card.html`, linked from Keep it alive. It prints on one A6 sheet (105 x 148 mm, a quarter of A4; checked by printing to PDF), and also has blank lines for the local FM frequencies of the stations that carry official alerts, how to keep it alive, the edition and build date, and a strip to cut off and stick on the drive ("Offline library: open 1 START-HERE").

**A paper copy** (24 Nov 2026, replacing the "paper layer, later" of D13). Paper needs no power, but the arc is far too big to print (the guides alone come to tens of thousands of pages). So the catalog's `paper` column marks the guides worth printing, in two sets: `first`, the essentials (8 guides, 216 pages: first aid, psychological first aid, safe water, heat, poisonous mushrooms, the Swedish crisis brochure), and `more`, if there is paper and ink to spare (21 guides, 1,545 pages: stress, nutrition, seeds and compost, animals, bread and cheese, toilets, survival, warmth, solar, mending, map and compass, units, Morse, teaching phonics). Only single PDFs with real text in the pocket edition, so every drive has them; page counts come from `about`, and the catalog test keeps `first` within 400 pages and `more` within 2,000. The page "Print a paper copy" (`arc/site/paper.html`, linked from Keep it alive) lists them in the site's order with pages, a running total and the sheets needed double-sided, a box to tick, and the books worth buying printed (`frontdoor/paper-books.csv`: *Where There Is No Doctor*, field guides to wild plants and birds, an amateur-radio handbook, *Machinery's Handbook*). It prints as a checklist. START-HERE.txt lists the first set; MAINTENANCE.txt step 8 explains. Multi-file books (the Hesperian chapters) are not marked: there is no one file to print, and the whole *Where There Is No Doctor* is better bought printed.

---

## 10. Later forms

- **Station:** the same drive served over Wi-Fi from a small box with its own power, so any phone or laptop nearby reads it in a browser. Location undecided, so it must work anywhere. Compare a plain kiwix-serve box with Internet-in-a-Box and Project NOMAD. Includes a "take a copy" page (Kiwix app, guides, collections).
- **Paper layer:** done as the paper copy (section 9, 24 Nov 2026).
- **Download website:** where people can download the arc while the internet works. Not a priority. Meanwhile the recipe itself is the way to get an arc (D15): anyone with the public repository runs `make-arc` and builds their own drive from the publishers' sites.
- **Other language editions:** French first (`catalog/deferred-non-english.csv`).
- **AI helper:** a local model that searches and explains the arc's own content, and nothing else. Agreed in principle on 25 Nov 2026, built later: section 13 (D18).

---

## 11. Decisions

| # | Decision | Outcome |
|---|---|---|
| D1 | Library launcher | **Library server + browser** (19 Nov 2026). Prototype done on Windows (section 12). |
| D2 | Drive types and count | **Deferred by the owner** (19 Nov 2026). exFAT, sized from the editions. |
| D3 | Locations of the copies | **Deferred** (19 Nov 2026). |
| D4 | Personal documents | **None** (17 Nov 2026). |
| D5 | Interface language | **English** (17 Nov 2026, confirmed 21 Nov 2026). Other language editions later. |
| D6 | Videos | **Included** (17 Nov 2026); now shelves (Videos, Films). |
| D7 | Maps scope | **France in full detail** (17 Nov 2026). |
| D8 | Scope | **Layered knowledge ark** (19 Nov 2026); layers size the editions. |
| D9 | Quality bar | **Per collection after a recorded spot check** (19 Nov 2026); the first-aid guides (formerly Tier 1) item by item; community content labelled. Since D14 the spot checks are a record, not a gate. |
| D10 | Vision | **Offline learning website on a drive, for anyone who has a copy** (21 Nov 2026). Replaces the family crisis kit: the Emergency door, "needed in minutes" Tier 1, the emergency binder and the family-only audience. |
| D11 | Entry point | ~~START-HERE first, one double-click for the full library~~; four items at the top of the drive (21 Nov 2026). **Superseded by D19** (25 Nov 2026). |
| D12 | Navigation | **Subjects → topics → items, format shelves, doors; generated from catalog tags** (21 Nov 2026). |
| D13 | Forms | **Drive copy first, then pocket arc; station, paper, download website later** (21 Nov 2026; the paper copy was added 24 Nov 2026, section 9). iPhones not designed for; Wi-Fi sharing secondary. |
| D14 | Gate | **The catalog is the gate** (owner, 21 Nov 2026): "no [sign-off gate], just make it full and as we add content it should automatically be included". Replaces D9's sign-off gate; `reviewer` is a record. |
| D15 | Make your own arc | **Public recipe** (owner, 21 Nov 2026): the repo will be made public; `make-arc.py` builds an edition onto anyone's drive. Files from sites that block scripts are hosted in the repo (`hosted/`). |
| D16 | Pocket copies | **Every drive bigger than pocket can make a pocket copy offline, without Python** (owner, 22 Nov 2026), carrying the pocket edition's Wikipedias in its pocket kit (+8 GB since 24 Nov 2026; +15 GB before). Section 7. |
| D17 | Look and feel | **Learning app** (owner, 22 Nov 2026, from three mockups: library, field manual, learning app): bright subject tiles with icons, a starting question with quick ways in, learning paths, guides described by what is inside, system fonts, dark mode. **Search on the drive's own pages** (same day): every page has a plain form to `arc/site/search.html`, the only page on the drive with an inline script (rule 4; START-HERE's check for a running library went with D19). |
| D18 | AI helper | **A helper that searches and explains the arc's content, 100% based on that content** (owner, 25 Nov 2026). Never a source of its own, never the only way to anything, optional. Built later, after the "one door, one website" redesign, which is its foundation. Section 13. |
| D19 | One door | **The launcher first, the fallback page second** (owner, 25 Nov 2026, after the first test on Windows: START-HERE, then a `.bat`, a black window and a second browser was confusing). The top of the drive: `1 Open Knowledge Arc (Windows).bat` / `(Mac).command`, `2 If nothing opens.html` (no script), `arc/`. On Windows the `.bat` checks that PowerShell may run `arc/system/open-knowledge-arc.ps1` and starts it hidden; it shows one small window, starts kiwix-serve hidden and opens one browser (the drive's Firefox, else the computer's); if PowerShell cannot run it, the same `.bat` runs the library the old way, in its console. Step 2 of the "one door, one website" redesign (mockup approved 25 Nov 2026); steps 3-5 (collections shown under the arc's bar, one search, checked deep links) follow. Supersedes D11. |

---

## 12. Launcher prototype (D1), Windows, 20 Nov 2026

*Since 25 Nov 2026 (D19) the launchers are `1 Open Knowledge Arc (Windows).bat` (with `arc/system/open-knowledge-arc.ps1`, the small window) and `1 Open Knowledge Arc (Mac).command`, repo `launchers/open-knowledge-arc.*`, Linux `arc/open-knowledge-arc.sh`; the names below are history.* *Tested on the v0.2 layout on 20 Nov 2026. In phase 3 (21 Nov 2026) the launchers became `2 Open full library (Windows).bat` and `2 Open full library (Mac).command` at the top of the drive (repo: `launchers/open-full-library.*`), with `arc/open-full-library.sh` for Linux; the server is in `arc/software/<os>/`, the collections in `arc/collections/`, the home page in `arc/system/`, and the log is `%TEMP%\knowledge-arc.log`. Re-run on Windows on 21 Nov 2026 from a scratch build of five real items: `verify` ALL GOOD (65 files, with both `verify.ps1` and `verify.sh`), the renamed launcher started the library and its browser helper (`cmd /c ""… Open full library (Windows).bat" :openbrowser"`, quoting intact despite the spaces and brackets), a search returned results, and stopping the server stopped the address. A second drive built from the first drive's `arc/system/recipe` copy (outside git) came out identical; running the recipe from the drive itself is refused. Mac and Linux launchers still untested. The findings below still apply; paths below are the v0.2 ones.*

**How it works.** `OPEN-LIBRARY.bat` (in `launchers/`, copied to the drive root by `assemble.py`) lists every `.zim` in `01_LIVING/zim`, `02_KNOWLEDGE/zim` and `02_KNOWLEDGE/maps`, and starts `90_SOFTWARE/windows/kiwix/kiwix-serve.exe -i 127.0.0.1 -p 8642 -b -k -c 99_SYSTEM/library-home.html <zims>`. It waits until the server answers, then opens the default browser on `http://127.0.0.1:8642/`. The window stays open while the library runs, and closing it stops the server. The server's messages go to `%TEMP%\family-library.log`. The server comes from catalog rows T9-001..004 (kiwix-tools 3.8.1 for Windows, 3.8.2 for Mac and Linux), which `assemble.py` unpacks.

**The library home page** (`99_SYSTEM/library-home.html`, built by `scripts/libraryhome.py` on every build) replaces Kiwix's welcome page:
- one search box over the checked English collections
- a separate, labelled "Community answers" area with its own search (CONTRIBUTING.md, quality bar)
- the list of collections, with the ones the search can't reach marked "open it to browse", and any the server could not open marked as possibly damaged

It's needed because Kiwix's own welcome-page box only filters the list of collections, and the bar inside a collection searches only that collection. A reader would never reach the cross-collection search.

**Not searchable from the box** (packages built without a full-text index, checked in the Kiwix feed 20 Nov 2026): iFixit (T2-012), USDA canning (T2-011), CIA Factbook, PhET, all LibreTexts, Khan Academy, CrashCourse, all-Gutenberg, the maps. Kiwix silently skips them in a search, so they must be opened and browsed. Low-tech Magazine is tagged with 11 languages, so it stays out of the shared search. The page reads both facts with `kiwix-manage` when the build runs on Windows.

**Tested on Windows 11 from a scratch test drive** (not yet from a real exFAT drive):

| Check | Result |
|---|---|
| Starts from the drive, relative paths, any drive letter | yes |
| Launched in its own console window, as a double-click does | yes. Windows Terminal shows the window's title, which asks the reader to keep it open while reading (the v0.2 wording; renamed with the launchers in phase 3). |
| Browser opens by itself | the launcher waits for the server, then calls the default browser. The owner should confirm the tab appears. |
| Closing the window stops the library | yes: the address stops answering and no kiwix-serve is left running |
| Firewall prompt | none. The server listens on 127.0.0.1 only and no firewall rule was created. |
| Search across collections from the home page | yes: typed in the box, results come from every listed collection, each marked "from <collection>" |
| Mac and Linux archives | unpacked: three plain binaries each (no symlinks, no library folders) |
| Damaged package | see "Damaged packages" below: skipped or contained, the rest of the library keeps working |

**Damaged packages** (tested 20 Nov 2026 with kiwix-serve 3.8.1, on deliberately damaged copies of real ZIMs):

| Damage | What happens with `-k` |
|---|---|
| Empty file (an interrupted copy) | skipped at start ("Skipping invalid ..."), the others are served |
| Cut off halfway (an interrupted copy) | skipped at start |
| Header, first 2 MB or last 2 MB zeroed | skipped at start |
| 3 × 256 KB zeroed in the middle (bit rot) | loads. About 1 page in 80 shows Kiwix's "Page isn't working" error. The server survived several hundred page loads, and searches including that package still worked. |

Without `-k`, one empty file stops the server from starting at all, so both launchers keep `-k`.

**Trap, fixed:** `/search` answers "No such book" (error 400) for the whole search if it names one book the server skipped. One damaged file would have broken the home page's main search box. The home page now carries a small inline script that reads the server's own list of loaded books (`/catalog/v2/entries`), drops the missing ones from the search forms, and marks them in the list: "Could not be opened: this file may be damaged". It only removes entries. If the list can't be read or looks incomplete (its count must match `totalResults`), the page stays as built. Checked in Chrome: with a truncated book, search works across the others and the book is marked. With all books good, nothing changes.

**Traps found:**
- A Kiwix `library.xml` whose paths contain folders (`../02_KNOWLEDGE/zim/x.zim`) makes kiwix-serve 3.8.1 put the folder into each book's web address, and every link returns 404. The launcher therefore passes the ZIM files directly. 51 ZIMs come to about 2,700 characters, well within the 8,191-character Windows limit.
- Kiwix's interface follows the browser's language (it appeared in Spanish on this PC). The home page is always English.

**Owner test on a real drive:** double-click `OPEN-LIBRARY.bat`, check that the browser tab opens by itself, search for something, close the black window, then check that `127.0.0.1:8642` no longer answers.

**Not done yet:**
- Mac (`OPEN-LIBRARY.command`) and Linux (`open-library.sh`) launchers are written but untested. On a Mac, check that macOS lets the unsigned kiwix-serve run from the drive.
- Sharing with phones over Wi-Fi needs `-i all`, which will raise the Windows firewall question. Keep it as a separate launcher so the everyday one never asks.
- Android: the Kiwix app reading a ZIM straight from a USB-C stick (127 GB Wikipedia).

---

## 13. The AI helper (agreed 25 Nov 2026, built later)

*Agreed in principle with the owner on 25 Nov 2026 (D18), after the first test of the arc led to the "one door, one website" redesign. Not built yet: this section records what it is and what must be true for it to work, so the work done now leaves room for it.*

### What it is

A local AI on the drive that helps a person **find** things in the arc and **explains** what they read: in simpler words, with an example, or with a few questions to check what they learned. It is **100% based on the arc's content** (owner): it first searches the arc, then reads the pages it found, then answers from those pages only, with links to them. It never answers from its own memory, and it never adds knowledge of its own.

It is a helper on top of the library, never a source in it. The arc stays complete without it (principle 8).

### Rules it must respect

1. **Grounded, or silent.** Every answer comes from pages of the arc and shows them as sources, each linked to its exact place (the page of a guide, the article of a collection). When the arc has nothing on the question it says so ("I could not find this in the library") instead of guessing.
2. **Never the only way.** Every guide, topic and search works without it; the AI can be missing, broken or too slow and nobody loses any knowledge (CONTRIBUTING.md rule 3 holds: start-here guides never depend on software).
3. **Labelled.** Every answer says it was written by an AI helper that can be wrong and that the linked source is what counts. For health questions the source guide comes first, as community answers are labelled today.
4. **Tested before it ships.** A set of real questions per topic, each with the source that should answer it (first aid first), is run against the helper; a model that invents, misses the source or gives unsafe health answers does not go on a drive. The same questions test the arc's search now.
5. **A catalog item.** The model and the program that runs it are catalog rows like any other: publisher, version, licence, size, sha-256 (CONTRIBUTING.md rules 1 and 2). Choosing the model is a content call made at build time from what is current (rule 1), not from memory.

### Prerequisites

| Area | What must be true | Where it stands (25 Nov 2026) |
|---|---|---|
| **Search** | One search over everything, with results as data the helper can read. The helper's first version uses it as its search: no new index needed. | The redesign's step 4. Tested on kiwix-serve 3.8.1: `/search?format=xml` returns results from several collections at once (relevance order, at most 140); `/suggest` finds page titles in collections without a search index. |
| **Exact places** | Every source opens at its exact place, under the arc's bar, so a person checks the answer without leaving the arc. | Collection articles have exact addresses (`/content/<book>/<path>`) and open under the bar (redesign step 3, tested). Guides are indexed as one block per PDF: they must be indexed **page by page**, with links that open at that page. |
| **Real text** | Every document has a text layer of good quality (rule 5). | 319 of 339 documents have text, 1 has none (T2-338, xiangqi rules), 19 not recorded. Old scans with machine-read text (FSI courses, 1940s manuals) need a quality check. |
| **Searchable collections** | The helper can only find what the search can find. | iFixit, LibreTexts, Khan Academy, all-Gutenberg and the maps have no full-text index (section 12): title search only, unless a search index is built for them at build time. |
| **Search by meaning** (later) | An index of the guides and key collections by meaning (embeddings), built at build time, never on the reader's computer. | Not started. Whole-Wikipedia embeddings are too big for now; the full-text search covers it. |
| **Runs from the drive** | A portable engine (for example llama.cpp) on the drive for Windows, Mac and Linux, started by the same double-click as the library, nothing installed, no Python (rule 10), listening on this computer only (`127.0.0.1`). | The redesign's new launcher (step 2) must leave room to start a second program next to the library. The chat page needs its own exception to rule 4, written into CONTRIBUTING.md and the tests when built. |
| **Hardware** | A small model (about 1 to 4 billion parameters, compressed: a 2 to 3 GB file, about 8 GB of memory) on the computer's processor. A computer too weak for it gets a clear message and the normal search. | Minimum computer to be set by the owner. Phones are left out at first (computer first, 25 Nov 2026). |
| **Power** | The AI makes the processor work hard and empties a battery fast; it is a convenience, not the main path. | Say so on its page. |
| **Space** | 2 to 5 GB per model. | Core and up have room. Pocket has about 4.8 GB left under its 29 GB limit, which the audio phase also wants: the helper likely starts in core. |
| **Licences** | Copies go to strangers, so the model's and the engine's licences must allow passing them on, with no limit on who may use them (some model licences have excluded people in the EU). Prefer Apache 2.0 or MIT. | Checked when the model is chosen. |
| **Lasting** | Open, widely supported formats (GGUF models, the llama.cpp engine). A model is a snapshot; since it answers from the arc and not from memory, an older model mainly writes less well. New editions can swap it. | Very old computers may not run it at all: the arc doesn't depend on it. |
| **Language** | English for this edition; other language editions need a model that is good in their language. | Pick a multilingual model when the French edition comes. |
| **Privacy** | Nothing leaves the computer: no accounts, no telemetry, no internet. | Same as the library server. |

### What the redesign does for it now

The "one door, one website" redesign (25 Nov 2026) is the helper's foundation. While building it:
1. the unified search (step 4) gets a clean data form a future helper can call;
2. every source opens at its exact place under the arc's bar (step 3), PDF pages included;
3. guides are indexed page by page, not one block per guide;
4. the new launcher (step 2) can start a second program next to the library;
5. a question set per topic, with the right source for each, starts now: it tests the search today and the helper later.

### Still to decide with the owner (when the helper is built)

- Which editions carry it (suggested: core and up).
- The oldest computer it must work on.

Earlier research (CLAUDE.md, research findings): Project NOMAD (Ollama with retrieval and citations, Linux/Docker), Survival LLM (desktop app, library includes unvetted sources), Zimi (search API and MCP server over ZIM files). None fits as is: the helper must run from the drive with nothing installed and use only the arc's checked content.
