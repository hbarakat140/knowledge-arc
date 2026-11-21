# Knowledge Arc — Architecture (v0.3)

*Status: vision reset agreed with the owner on 21 Nov 2026 (sections 1-4, 7, 10). The scripts still build the v0.2 layout until phases 2-4 in `NEXT-SESSION.md` are done; section 12 records the launcher prototype as tested on v0.2.*

---

## 1. Design principles

1. **The drive is the product.** Everything needed to read the content lives on the drive, including the software. Nothing assumes an internet connection or a pre-installed app.
2. **It explains itself.** A stranger who finds a copy years from now, with none of us there, can tell what it is, use it, keep it alive and pass it on.
3. **A learning library, not a crisis tool.** People browse subjects and learn. Emergencies and first aid are a topic like any other.
4. **Degrade gracefully.** With the library engine running: one website, one search over everything. With no program at all: the website's pages and every start-here guide still open in a plain browser.
5. **Open formats only.** ZIM, PDF, HTML, plain text, images, MP4. No databases, no containers, no proprietary formats as the only copy of anything.
6. **Trusted sources only.** Every item comes from an approved publisher or has been individually reviewed, and every item is recorded in the catalog with its origin.
7. **Built to grow.** A stable top level of subjects; new topics, items, shelves and editions slot in without a redesign. Pages are generated from the catalog.
8. **AI-ready, not AI-dependent.** Real text and clean metadata, so a future local AI can index it; nothing requires AI.

---

## 2. What the arc is, and how someone uses it

**An offline website on a drive.** Plain files underneath (PDF, ZIM), a small portable engine on the drive (the Kiwix library server, which runs without installing), a website on top.

### The journey of someone who holds a copy

1. **They open the drive.** The top level shows four things only (section 3). A sticker on the drive says "Offline library - open START-HERE".
2. **They double-click `START-HERE.html`.** It opens in the browser on any computer, with no program. They see what this is, the subjects, the shelves and the doors. Every topic page works, and every start-here guide (PDF) opens.
3. **A banner offers the full library.** It recognises the computer (Windows or Mac) and names the one file to double-click: "Open full library (Windows)". A browser page cannot start a program itself, so this one deliberate double-click is unavoidable.
4. **The full library runs.** A window says to keep it open while reading. START-HERE detects the running library and switches to the full site: **one website**, the same subjects and topics, plus the big collections (Wikipedia, medicine, iFixit, CD3WD, Gutenberg, courses, maps), and **one search over everything**. Closing the window stops it and leaves nothing on the computer.
5. **On an Android phone:** plug in the drive (USB-C, or an adapter), open guides from the Files app, install the Kiwix app from `arc/software/android/` to open the collections. The arc's own collection shows the same subjects.
6. **Passing it on:** copy the whole drive to another exFAT drive, or make a pocket copy (section 7). The maintenance guide explains how, for a stranger.

**iPhones** are not designed for: they can open the PDF guides from the Files app, nothing more. **Sharing over Wi-Fi** from a laptop (so phones nearby read in their browser) is a secondary, advanced option: it raises the Windows firewall question, so it has its own launcher and lives in the advanced instructions.

### Users, devices and power

- **Users:** anyone, from technical to non-technical, adults, teens and children (children with an adult or through the "For children" door).
- **Devices:** Windows and Mac laptops, Android phones and tablets. Linux possible.
- **Power:** may be limited. The arc must stay usable from a charged Android phone (the pocket arc is sized for that).

---

## 3. Drive layout (target, phase 3)

```
/  (drive root)
├── START-HERE.html                    ← the website's front page (opens in any browser)
├── Open full library (Windows).bat    ← starts the library engine from the drive
├── Open full library (Mac).command
└── arc/
    ├── START-HERE.txt                 ← plain-text twin, for a computer without a browser
    ├── open-full-library.sh           ← Linux
    ├── site/                          ← the website's other pages (subjects, topics, shelves, doors)
    ├── guides/<subject>/              ← PDFs: start-here guides and other books, one folder per subject
    ├── collections/                   ← ZIMs: encyclopedias, courses, videos, maps, the arc's own collection
    ├── software/                      ← windows/, mac/, linux/ (Kiwix server), android/ (Kiwix app)
    └── system/                        ← CATALOG.csv, CHECKSUMS.sha256, VERSION.txt, verify.bat/.sh,
                                         MAINTENANCE.txt
```

Rules:
- **Only four things at the top.** Everything a stranger shouldn't have to understand lives in `arc/`.
- **Start-here guides exist as PDF or HTML,** even if they are also inside a ZIM (CLAUDE.md rule 3).
- **Plain, descriptive English file names** (`poultry-slaughter-smallholder_hsa_2016.pdf`), no special characters, folder names that read as words.

The v0.2 layout (`00_EMERGENCY/`, `01_LIVING/`, `02_KNOWLEDGE/`, `90_SOFTWARE/`, `99_SYSTEM/` at the root, by tier) is what the scripts build until phase 3.

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

**Subjects** (main menu; stable; plain labels) → **topics** (the areas in `catalog/coverage.csv`, 35 today) → **items**. Three levels at most.

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

**Tags that drive it** (phase 2): each catalog row gets `topic` (coverage ids, home first), `shelf` and `audience` (all, children, advanced); its job (primary or depth) sets its order. `catalog/subjects.csv` lists the subjects; `coverage.csv` gains a `subject` column. All pages are generated from these by the build.

**Two ways into the same site:**
- **No program** (`file://`): START-HERE and the pages in `arc/site/`, with links to the PDFs.
- **Full library:** the same pages and guides packed as the arc's own ZIM (built with python-libzim on the build machine, never needed by users), served by kiwix-serve as the home page, with one search over the arc's own pages, the guides and every indexed collection.

---

## 5. Formats

| Content type | Format on drive | Why |
|---|---|---|
| Websites / encyclopedias / courses | ZIM (Kiwix) | Compressed, searchable, standard, readable by other tools later |
| Guides, manuals, books | PDF with real text layer | Opens in any browser; searchable; AI-indexable |
| The website | HTML (and the arc's own ZIM) | Zero dependency in the browser; one search in the full library |
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
5. **One sign-off per collection** after a recorded spot check (D9). Health and first-aid start-here guides are reviewed item by item.

---

## 7. Editions and copies

| Edition | Size | Holds | For |
|---|---|---|---|
| **pocket** (phase 5) | 32-64 GB | the website, all guides, the medical encyclopedia, a smaller Wikipedia, the Kiwix app | phones, small sticks, passing on |
| **core** | ~150 GB | survive and sustain, full Wikipedia with pictures, France map | the everyday copy |
| **standard** | ~285 GB | adds the rebuild layer, Gutenberg subject sets, courses, children's reading | the main copy |
| **full** | ~660 GB | adds all of Gutenberg, Khan Academy, Wikisource, Europe maps | the master and the station |

Each edition includes the one before. Survive, sustain and rebuild size the editions; they are not the navigation.

- **File system: exFAT.** Readable and writable on Windows, Mac, modern Linux and Android, and handles files over 4 GB. FAT32 sticks cannot hold the big collections; the maintenance guide warns about this.
- **Several identical copies, at least two media types, in different places,** and more copies made to pass on. One master is built and verified, then mirrored; copies are checked against `CHECKSUMS.sha256`.
- **Size:** 2 TB for the full master (room to grow); copies sized by edition.

---

## 8. Maintenance (light)

- **Every 6–12 months:** plug each drive in, run `verify`, open a few files. Drives left in a drawer can degrade silently; this catches it while other copies are still good.
- **Optional refresh** while the internet works: update key items on the master, regenerate checksums, re-mirror.
- **Version log** in `VERSION.txt`.
- **On the drive:** `arc/system/MAINTENANCE.txt` (source: `scripts/drive/MAINTENANCE.txt`), plain text, written for a stranger (phase 6): check, repair a file from another copy, make a whole or pocket copy, the exFAT trap, run the library, share it over Wi-Fi (advanced).

---

## 9. The tiny card

One printed page, kept with each drive: the French emergency numbers, what the arc is, how to open it on a computer and on an Android phone. Built with the website (phase 6).

---

## 10. Later forms

- **Station:** the same drive served over Wi-Fi from a small box with its own power, so any phone or laptop nearby reads it in a browser. Location undecided, so it must work anywhere. Compare a plain kiwix-serve box with Internet-in-a-Box and Project NOMAD. Includes a "take a copy" page (Kiwix app, guides, collections).
- **Paper layer:** items that should exist on paper, marked in the catalog, decided together.
- **Download website:** where people can download the arc while the internet works. Not a priority.
- **Other language editions:** French first (`catalog/deferred-non-english.csv`).
- **AI layer:** a local model plus an index over the guides and selected ZIMs (NOMAD, Survival LLM, Zimi). Requirement now: clean text and metadata.

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
| D9 | Quality bar | **Per collection after a recorded spot check** (19 Nov 2026); health and first-aid start-here guides item by item; community content labelled. |
| D10 | Vision | **Offline learning website on a drive, for anyone who has a copy** (21 Nov 2026). Replaces the family crisis kit: the Emergency door, "needed in minutes" Tier 1, the emergency binder and the family-only audience. |
| D11 | Entry point | **START-HERE first, one double-click for the full library; four items at the top of the drive** (21 Nov 2026). |
| D12 | Navigation | **Subjects → topics → items, format shelves, doors; generated from catalog tags** (21 Nov 2026). |
| D13 | Forms | **Drive copy first, then pocket arc; station, paper, download website later** (21 Nov 2026). iPhones not designed for; Wi-Fi sharing secondary. |

---

## 12. Launcher prototype (D1), Windows, 20 Nov 2026

*Tested on the v0.2 layout. In phase 3 the launchers become "Open full library (Windows/Mac)" at the top of the drive and the paths move under `arc/`; the findings below still apply.*

**How it works.** `OPEN-LIBRARY.bat` (in `launchers/`, copied to the drive root by `assemble.py`) lists every `.zim` in `01_LIVING/zim`, `02_KNOWLEDGE/zim` and `02_KNOWLEDGE/maps`, and starts `90_SOFTWARE/windows/kiwix/kiwix-serve.exe -i 127.0.0.1 -p 8642 -b -k -c 99_SYSTEM/library-home.html <zims>`. It waits until the server answers, then opens the default browser on `http://127.0.0.1:8642/`. The window stays open while the library runs, and closing it stops the server. The server's messages go to `%TEMP%\family-library.log`. The server comes from catalog rows T9-001..004 (kiwix-tools 3.8.1 for Windows, 3.8.2 for Mac and Linux), which `assemble.py` unpacks.

**The library home page** (`99_SYSTEM/library-home.html`, built by `scripts/libraryhome.py` on every build) replaces Kiwix's welcome page:
- one search box over the checked English collections
- a separate, labelled "Community answers" area with its own search (CLAUDE.md quality bar)
- the list of collections, with the ones the search can't reach marked "open it to browse", and any the server could not open marked as possibly damaged

It's needed because Kiwix's own welcome-page box only filters the list of collections, and the bar inside a collection searches only that collection. A family member would never reach the cross-collection search.

**Not searchable from the box** (packages built without a full-text index, checked in the Kiwix feed 20 Nov 2026): iFixit (T2-012), USDA canning (T2-011), CIA Factbook, PhET, all LibreTexts, Khan Academy, CrashCourse, all-Gutenberg, the maps. Kiwix silently skips them in a search, so they must be opened and browsed. Low-tech Magazine is tagged with 11 languages, so it stays out of the shared search. The page reads both facts with `kiwix-manage` when the build runs on Windows.

**Tested on Windows 11 from a scratch test drive** (not yet from a real exFAT drive):

| Check | Result |
|---|---|
| Starts from the drive, relative paths, any drive letter | yes |
| Launched in its own console window, as a double-click does | yes. Windows Terminal shows the title "Family Library - keep this window open while you read". |
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
