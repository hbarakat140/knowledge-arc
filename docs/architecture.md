# Offline Family Library — Drive Architecture (v0.2)

*Status: decisions D4–D7 settled on 17 Nov 2026 (see section 10). Content lists come in the next step; this document defines the container.*

---

## 1. Design principles

1. **The drive is the product.** Everything needed to read the content lives on the drive, including the software. Nothing assumes an internet connection or a pre-installed app.
2. **Degrade gracefully.** If an app runs, you get full search across everything. If no app runs, the critical content still opens in a plain web browser.
3. **Open formats only.** ZIM, PDF, HTML, plain text, images. No databases, no containers, no proprietary formats as the only copy of anything.
4. **Trusted sources only.** Every item comes from an approved publisher or has been individually reviewed, and every item is recorded in a catalog with its origin.
5. **Simple for a non-technical family member.** One obvious entry point, plain words, big buttons, nothing to configure.
6. **AI-ready, not AI-dependent.** Content is kept in a form a future local AI can index (real text, good metadata), but nothing requires AI to be useful.

---

## 2. How someone uses it (the three levels)

| Level | When | What they do | What they get |
|---|---|---|---|
| **1. Browser only** | Any computer, nothing can be installed or run | Open `START-HERE.html` | Emergency guides and core practical manuals as PDF/HTML |
| **2. One double-click** | A computer that allows running a program | Double-click `OPEN-LIBRARY` (Windows/Mac/Linux versions) | The whole library (Wikipedia, WikiMed, iFixit, books, maps) in the browser, with search |
| **3. Installed** | A computer you'll use for a while | Install a reader from `90_SOFTWARE/` | Faster, nicer reading; later, a local AI over the same files |

The level-2 launcher idea: a small script starts a portable Kiwix server on the drive and opens the browser on it. The user never sees a ZIM file. *(To be tested on Windows, Mac and Linux before we commit; Windows may show a security or firewall prompt the first time.)*

### Users, devices and power (owner, 19 Nov 2026)

- **Users:** the owner (technical), non-technical adults, teens and young children. Every path a family member touches must work for a non-technical adult; young children use it with an adult.
- **Devices:** Windows and Mac laptops, and Android phones and tablets. No iPhones or iPads, so nothing has to work on iOS.
- **Power:** no plan yet; it's part of a wider preparedness plan outside this project. Design for the worst case: the library must still be usable from a charged Android phone.
- **Print:** a printed emergency binder is part of v1: the Tier 1 pages, the French emergency numbers and a one-page "how to use the drive" card.

---

## 3. Folder structure

```
/  (drive root)
├── START-HERE.html          ← the front door (opens in any browser)
├── START-HERE.txt           ← plain-text fallback with the same instructions
├── OPEN-LIBRARY.bat         ← Windows: one double-click to open the full library
├── OPEN-LIBRARY.command     ← Mac
├── open-library.sh          ← Linux
│
├── 00_EMERGENCY/            ← Tier 1: needed in minutes. PDF/HTML only, never app-dependent
│   ├── 00_call-for-help/    (French emergency numbers, poison centres)
│   ├── 01_bleeding-wounds/
│   ├── 02_breathing-cpr/
│   ├── 03_burns/
│   ├── 04_poisoning/
│   ├── 05_water-purification/
│   ├── 06_cold-heat/
│   ├── ...                  (numbered by urgency, one folder per situation)
│   └── 10_first-aid-manuals/ (complete first-aid references covering many situations)
│
├── 01_LIVING/               ← Tier 2: sustaining daily life over months
│   ├── survival-skills/     (shelter, fire, water, navigation in the field)
│   ├── health-ongoing/      (illness, medicines, childbirth, dental)
│   ├── water-sanitation/
│   ├── food-growing/
│   ├── food-preservation/
│   ├── cooking-from-scratch/
│   ├── foraging-nature/     (French/European flora first)
│   ├── animals/
│   ├── energy-power/
│   ├── repair-tools/
│   ├── building-shelter/
│   ├── communication/
│   └── zim/                 (Tier 2 ZIMs: WikiMed, MedlinePlus, iFixit, Appropedia, CD3WD, ...)
│
├── 02_KNOWLEDGE/            ← Tier 3: reference, education, culture
│   ├── zim/                 (Wikipedia EN/FR/AR, WikiMed, iFixit, Wiktionary, etc.)
│   ├── books/               (Gutenberg selection, textbooks)
│   ├── education/           (courses, children's learning)
│   ├── videos/              (how-to and course videos)
│   └── maps/
│
├── 90_SOFTWARE/             ← readers and tools for each system
│   ├── windows/             (portable Kiwix, portable PDF/EPUB reader)
│   ├── mac/
│   ├── linux/
│   └── android/
│
├── 95_AI/                   ← empty for now; reserved for a local model + index later
│
└── 99_SYSTEM/
    ├── CATALOG.csv          (every item: source, date, licence, tier, language, reviewer)
    ├── CHECKSUMS.sha256     (fingerprint of every file, to detect corruption)
    ├── VERSION.txt          (build date, what changed)
    ├── verify.bat / verify.sh   (check the drive is intact)
    └── MAINTENANCE.md       (how to check, refresh and copy the drives)
```

Rules:
- **Tier 1 content is duplicated as plain PDF/HTML** even if it also exists inside a ZIM. It must never depend on a program.
- **Numbered folder names** so the order is the same on every operating system.
- **Plain, descriptive file names** (`burns-first-aid_hesperian_2025.pdf`), no special characters.

---

## 4. The front door (`START-HERE.html`)

- A single self-contained HTML file: no internet fonts, no external scripts, relative links only, so it works when opened directly from the drive.
- **Four big buttons:** Emergency · Daily life · Encyclopedia & books · How to use this drive.
- **Emergency first:** the Emergency button leads to a one-screen list of situations ("Someone is bleeding", "Water is unsafe"...), each linking straight to the PDF.
- **"Encyclopedia & books"** explains in one sentence to double-click `OPEN-LIBRARY`, with a picture of what to click.
- Interface in English (decision D5); the language of each item is marked on its link when it isn't English.

---

## 5. Formats

| Content type | Format on drive | Why |
|---|---|---|
| Websites / encyclopedias | ZIM (Kiwix) | Compressed, searchable, standard, readable by NOMAD/AI tools later |
| Manuals, guides, books | PDF with real text layer | Opens in any browser; searchable; AI-indexable |
| Emergency guides | PDF + HTML | Zero dependency |
| Ebooks | PDF preferred; EPUB kept alongside if that's the original | Windows has no built-in EPUB reader |
| Maps | ZIM (Kiwix OpenStreetMap) and/or PDF map sheets for your regions | Search + printable fallback |
| Videos (how-to, courses) | Included (decision D6). MP4 for standalone videos, ZIM where Kiwix packages a channel or course | Largest space driver; selection made in the content step |

Scanned-image PDFs are only accepted when nothing better exists, and are flagged in the catalog (not searchable, not AI-indexable).

---

## 6. Quality gate ("no garbage")

1. **Approved publisher list.** Institutional and established sources only (e.g. WHO, MSF, Hesperian, Red Cross/Croix-Rouge, national health agencies, official field manuals, WikiMed/MDWiki, iFixit, university extension services, French government agencies). The full list is built in the content step.
2. **Anything outside the list** needs an individual review, recorded in the catalog with who reviewed it and why it's included.
3. **Every item gets a catalog row** in `catalog/catalog.csv`. Its header is the canonical schema: `id, title, publisher, source_url, edition_or_date, download_date, licence, tier, folder, language, format, size_bytes, sha256, text_layer, reviewer, bundle, notes`. `download_date` and `sha256` are filled by the download script. `size_bytes` and `text_layer` may be pre-filled from real checks (HTTP size, text extraction) and are confirmed by the scripts; see `catalog/README.md`.
4. **Medical content gets a date check.** Prefer the newest edition; note the edition in the file name.

---

## 7. Drives and copies

- **File system: exFAT.** Readable and writable on Windows, Mac and modern Linux, and handles files over 4 GB (full English Wikipedia is one file of roughly 110+ GB).
- **Size:** to be fixed once the content list exists. Before videos, the rough range was 0.5–1 TB of content; including videos may push it well past that. Size the drives from the final content list plus space for an AI model later, with headroom (2 TB is the floor to plan around; 4 TB may be needed).
- **Three identical copies, at least two media types, in different places.** For example: one SSD (fast, shock-resistant), one hard drive (holds data better when left unpowered for long periods), in at least two locations.
- **Identical builds:** one master copy is built and verified, then mirrored to the others. Copies are checked against `CHECKSUMS.sha256`.

---

## 8. Maintenance (light, since this is a one-time project)

- **Every 6–12 months:** plug each drive in, run `verify`, read a few files. Drives left in a drawer can degrade silently; this catches it while the other copies are still good.
- **Optional refresh:** if internet is available, update a few key items (WikiMed, Wikipedia) on the master, regenerate checksums, re-mirror.
- **Version log** in `VERSION.txt` so you always know which copy is current.

---

## 9. AI layer (later)

- Kept out of v1. `95_AI/` is reserved.
- When added: a local model plus an index built over `00_EMERGENCY`, `01_LIVING` and selected ZIMs. Tools seen in research (NOMAD, Survival LLM, Zimi) can all read ZIM and/or PDF from these folders without changing the library.
- Requirement now: keep the text layer and catalog metadata clean so indexing is easy later.

---

## 10. Decisions

**Settled (17 Nov 2026)**

| # | Decision | Outcome |
|---|---|---|
| D4 | Personal family folder | **None.** No personal documents on the drive. |
| D5 | Front-door language | **English.** |
| D6 | Videos | **Included.** Selection in the content step. |
| D7 | Maps scope | **France in full detail.** Other regions decided in the content step by comparing detail levels and sizes. |

**Still open**

| # | Decision | Options | Notes |
|---|---|---|---|
| D1 | Level-2 launcher | Portable Kiwix server + browser, or portable Kiwix desktop app | **Decided 19 Nov 2026: library server + browser.** Same look as the front door; a laptop can share the library with Android phones over local Wi-Fi. Fallbacks: Kiwix Android app reading a USB-C stick; Kiwix desktop in `90_SOFTWARE/`. Prototype on Windows first, then Mac. To test: firewall prompt, macOS blocking a program run from the drive, one search across all packages, Android opening a 127 GB file from a stick. |
| D2 | Drive types and count | e.g. 2× SSD + 1× HDD | **Deferred by the owner (19 Nov 2026):** doesn't change what is built. exFAT, size from the bundles. |
| D3 | Locations of the copies | Home, second location, trusted person | **Deferred (19 Nov 2026):** doesn't change what is built. |
| D8 | Scope | Family library, or knowledge ark (adds a *rebuild* layer) | **Decided 19 Nov 2026:** layered knowledge ark (rebuild layer in standard and full only) |
| D9 | Quality bar | Review every item, or one sign-off per collection after a spot check | **Decided 19 Nov 2026:** per collection after a recorded spot check; Tier 1 item by item; community content labelled |

---

## 11. Next steps

1. Set up the repo (build recipe only; content lives on the drives).
2. Build the content list per tier, with the approved publisher list.
3. Size the drives from the content list.
4. Prototype: front door + launcher + a few items, tested on Windows, Mac and Linux.
5. Full build, verify, mirror to copies.
