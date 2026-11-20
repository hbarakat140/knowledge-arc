# Catalog

Two files drive the build: `catalog.csv` (what goes on the drive) and `publishers.csv` (who we trust). `deferred-non-english.csv` keeps French and Arabic items researched earlier, for a later version (v1 is English only). Both are UTF-8 CSV with LF line endings. To open them in Excel without broken accents, use **Data → From Text/CSV** and pick UTF-8.

## publishers.csv: the quality gate

One row per source organisation.

| status | Meaning |
|---|---|
| `approved-pending-owner` | Proposed as trusted. Waiting for the owner's sign-off. |
| `approved` | Signed off. Its items can go on the drive. |
| `candidate` | Possible source. Not reviewed yet. |
| `item-review-required` | Never trusted as a whole. Each item needs its own review. |
| `excluded-licence` | Good content, but the licence blocks copying without permission. |

## catalog.csv: one row per item on the drive

An item is one file. The exception is a Hesperian book: it ships as one PDF per chapter, so it gets one row, and `format` gives the file count.

| Column | Filled by | Notes |
|---|---|---|
| `id` | hand | `T1-NNN`, `T2-NNN`, `T3-NNN`, and `T9-NNN` for software in `90_SOFTWARE/` (the library server for each system, and the Kiwix app for Android). Never reused. |
| `title`, `publisher`, `source_url`, `edition_or_date`, `licence`, `tier`, `folder`, `language`, `format`, `notes` | hand | `publisher` must be an `id` from publishers.csv. `folder` is the path on the drive: the full file path (plain ASCII, `topic_publisher_year.pdf`) for a single file, or a directory for a multi-file item such as a Hesperian book, whose files keep the publisher's names. The front door links to these exact names. For a ZIM, `source_url` is the Kiwix `.meta4` link, which lists the mirrors and the sha-256. |
| `bundle` | hand | `core`, `standard`, `full` or `decision`. See below. |
| `download_date`, `sha256` | download script | Left blank until the file is actually downloaded. For a multi-file book, `sha256` is the sha-256 of its sorted list of `<file sha256>  <file name>` lines. |
| `size_bytes` | check / script | Only from a real HTTP Content-Length, a download, or the Kiwix feed. If it is filled and the download differs, the script stops that item and leaves the file aside: servers sometimes send an error page as a "PDF". Blank values are filled in by the script. |
| `text_layer` | check / script | `y` only after text was actually extracted, or for HTML/ZIM content. |
| `reviewer` | owner | `pending-owner` until a person has read the item and signed off. |

"To verify" in `licence` or `edition_or_date` means it wasn't confirmed at the source yet. Check it before the full build.

## Bundles (17 Nov 2026)

A row whose notes say `REPLACES T3-030..T3-035` takes the place of those rows when its bundle is built; the scripts read that exact wording. See `scripts/README.md`.


The library is built mainly from ready-made collections: the official Kiwix/openZIM catalogue (1,314 English packages, read live with exact sizes and dates) and Hesperian's complete English book list. Each item belongs to one bundle, and each bundle includes the ones before it.

| Bundle | Size | What it adds |
|---|---|---|
| **core** | **~148 GB** | Tier 1 emergency PDFs. Medicine: WikiMed, MedlinePlus, NHS medicines, US military medical manuals, WHO-ICRC *Basic Emergency Care* (T2-038), 6 Hesperian books (*Where There Is No Doctor*, *Where Women Have No Doctor*, *Where There Is No Dentist*, *A Book for Midwives*, *Community Guide to Environmental Health*, *Community Mental Health*), MSF *Clinical Guidelines* and *Essential Drugs*. Living: Virginia Cooperative Extension *Gardener Handbook* (food growing), US Army *Survival*, *Carpentry* and *Concrete and Masonry* manuals, US Navy *Utilitiesman Basic* (plumbing), FAO booklets on poultry, small animals, sheep and goats, WHO water notes, USDA home canning, iFixit, Appropedia, energypedia, CD3WD, WikiVet. Reference: full English Wikipedia with pictures (127 GB of the 148), Wikibooks, PhET. Maps: France. |
| **standard** | **~273 GB** | Stack Exchange, WikiCiv and Low-tech Magazine (labelled "community answers"; 11 Stack Exchange sites, 8.75 GB), Wiktionary (15 GB), CIA World Factbook, Ready.gov, CDC travel health, MSF *Public Health Engineering* (water and sanitation), 2 Agrodok booklets (compost, mushrooms), the USDA *Wood Handbook*, *Lessons in Electric Circuits* (6 volumes), US Navy *Construction Electrician Basic* (wiring) and *Steelworker Basic* (welding), FAO booklets on gardens and food processing, 5 Peace Corps manuals (soils, irrigation, field crops, solar food technologies, charcoal), 3 more Hesperian books, 8 LibreTexts textbook sets, Crash Course videos (23 GB), Gutenberg subject sets (agriculture, technology, science, children's, English and American literature, 65 GB). |
| **full** | **~647 GB** | US Army publications library (8 GB), Wikisource (9 GB), Khan Academy (180 GB, 2023 snapshot), all of Gutenberg (221 GB; replaces the subject sets), maps of Europe (replaces France), 3 more Hesperian books. |

Sizes and contents were updated on 19 Nov 2026 after the redundancy review (`docs/redundancy-review.md`). Hesperian PDFs add under 1 GB in total; their server doesn't report sizes. Videos beyond Crash Course and Khan Academy aren't chosen yet (D6).

Rough drive fit:
- core fits on 500 GB
- standard fits on 1 TB
- full fits on 1 TB with little headroom, so plan 2 TB to leave room for later additions and the AI layer

### Owner decisions (all made 19 Nov 2026; no `decision` rows left)

1. **Stack Exchange** (11 sites, 8.75 GB): included in standard, in a clearly labelled "community answers" area, with a spot check of each site (D9).
2. **Survivor Library** (220 GB): rejected for v1 (in `rejected.csv`). A hand-picked trades subset is an option for v2.
3. **Gardenology**: rejected (in `rejected.csv`).
4. **Wikipedia:** with pictures (127 GB) in core. The pictures are the fallback for identifying plants.
5. **WikiCiv** and **Low-tech Magazine**: included in standard, labelled. Low-tech Magazine's licence is still unknown (owner action 7).
6. **Education videos:** CrashCourse stays in standard and Khan Academy in full.

### Rejected after inspection (no rows)

The redundancy review of 19 Nov 2026 removed further rows: Survivor Library (T2-091), Gardenology (T2-090), the Air Force SERE handbook (T2-104), Agrodok *Preservation of fruits and vegetables* (T2-071), and Hesperian *Workers' Guide* (T2-029), *Health Actions for Women* (T2-030) and *Helping Children Live with HIV* (T2-033). Reasons are in `docs/redundancy-review.md`; Kiwix packages are also in `rejected.csv`.

| Package | Why |
|---|---|
| `zimgit-medicine`, `zimgit-post-disaster`, `zimgit-food-preparation`, `zimgit-water`, `zimgit-knots` | Opened on 17 Nov 2026: they mix good documents with outdated editions (*Where There Is No Doctor* 2011, superseded FM 4-25.11), a suture-maker's brochure, an acupuncture "visual diagnosis" sheet, and gift-jar recipes. Their good items are covered better elsewhere (Hesperian 2025, ATP 4-02.11, USDA canning). The Agrodok farming booklets inside them are worth sourcing directly (see gaps). |
| Prepper YouTube channels (`canadian-prepper`, `urban-prepper`, `s2underground`, `lrnselfreliance`), `trueprepper.com`, `quickguidesformedicine` | Individual creators, not trusted publishers. |
| `wikipedia_en_medicine`, `wikipedia_en_top`, `wikipedia_en_top1m`, `wikipedia_en_100` | Already contained in the full Wikipedia. |
| TED collections | Multilingual packages. Revisit with the video selection. |
| `onemorelibrary`, `voa_learning`, games, programming and fandom wikis | Unknown curation or off-topic. |

## Tier 1 (emergency PDFs, English)

Seven items: T1-003, T1-004, T1-006 to T1-008, T1-010 and T1-014 (Canadian Red Cross *First Aid & CPR*, added 20 Nov 2026; text read that day). T1-005 (WHO-ICRC *Basic Emergency Care*) moved to Tier 2 as T2-038 on 19 Nov 2026: it is written for health workers. What was actually checked on 17 Nov 2026:

| Check | Items |
|---|---|
| PDF fetched and its text read | T1-003, T1-004, T1-005 (now T2-038), T1-007, T1-010 |
| Only the landing page was read; the PDF itself was never retrieved | T1-008 (CDC returns 403 to scripts) |
| Not reached at all: site blocks scripts | T1-006 (IFRC 2025; only the 2020 fallback URL was confirmed, by HEAD request) |

### How the situation folders are covered

| Folder | Standalone item | Page links into the manuals |
|---|---|---|
| `00_call-for-help` | none yet: the front door shows the French emergency numbers in English (sources in `deferred-non-english.csv`) | — |
| `01_bleeding-wounds` | — | Hesperian ch. 10, PDF p. 8–16; ATP 4-02.11 (tourniquet pages) |
| `02_breathing-cpr` | — | Red Cross T1-014 PDF p. 20–22 (choking), 28–30 (CPR: adult, child, baby), 32 (AED); ATP 4-02.11 PDF p. 94–96 (CPR depth); Hesperian ch. 10, PDF p. 5–6 |
| `03_burns` | — | Hesperian ch. 10, PDF p. 22–23 |
| `04_poisoning` | — | Hesperian ch. 10, PDF p. 29; Red Cross T1-014 PDF p. 63 (carbon monoxide) |
| `05_water-purification` | T1-007, T1-008 | — |
| `06_cold-heat` | T1-010 (heat) | Red Cross T1-014 PDF p. 58–61 (frostbite, hypothermia by stage); Hesperian ch. 10, PDF p. 7 (heat); ATP 4-02.11 (cold injury pages) |
| `10_first-aid-manuals` | T1-003, T1-014, T1-004, T1-006 | — |

The front door will link straight to a page, for example `first-aid-chapter_where-there-is-no-doctor_hesperian_2025.pdf#page=8`. Check that this works in Windows browsers during the prototype (step 4).

## Licence rule

**Decided by the owner, 19 Nov 2026: assume full permission.** Items that are free to download but "all rights reserved" or "on request" (WHO, MSF, Hesperian, FAO 2011, Agrodok, Low-tech Magazine, ERC/RCUK) go in like openly licensed ones. No permission emails are sent, and licence alone is never a reason to leave an item out. The licence column still records what each publisher states.

## Owner actions before the build

1. Review and sign off each `pending-owner` row: one sign-off per collection after a recorded spot check (D9), Tier 1 item by item. Publishers were signed off on 19 Nov 2026.
2. ~~Permission emails to Hesperian, MSF, FAO and Low-tech Magazine~~ (not needed: owner assumes full permission, 19 Nov 2026).
3. ~~Download T1-006 (IFRC 2025) by hand~~ (done 18 Nov 2026 via Chrome).
4. ~~Licence edge cases (ERC/RCUK, Agrodok)~~ (settled by the same decision). The English CPR gap was filled on 20 Nov 2026 by T1-014 (Canadian Red Cross).

## Remaining gaps

- **Tier 1 CPR and cold gaps (closed 20 Nov 2026).** Moving to English-only had deferred the French GQS sheet and the sante.fr cold page. The Canadian Red Cross *First Aid & CPR* guide (T1-014, 2025) now covers CPR for adults, children and babies, choking, hypothermia, frostbite and carbon monoxide. Considered and left out: the RCUK 2025 adult BLS guideline (written for professionals; RCUK's PDF is a print of the web page) and the UKHSA *Top tips for keeping warm and well* leaflet (assumes working heating and UK services).
- **Growing food in a temperate climate (checked 18 Nov 2026):** Agrodok booklets and FAO home-garden manuals are written for the tropics. Three climate-neutral Agrodoks were added (T2-070 to T2-072). Most other Agrodoks are tropical or "Limited Access" on CGSpace, and Agromisa, which held the rights, closed in 2021. That gap is now covered by the Virginia Cooperative Extension *Gardener Handbook* (T2-073, CC BY-NC-SA 4.0). Virginia's climate is close to Paris, but planting dates and pesticide rules differ; a French planting calendar belongs with the deferred French content.
- **Foraging (checked 18 Nov 2026):** no trustworthy, freely licensed English field guide to European wild plants was found. Good ones are commercial books. Recommendation: the owner buys a printed field guide for Britain and northern Europe for the print selection, and the drive keeps Wikipedia's plant articles with pictures. Never rely on a single source to identify a wild plant.
- **Metric water dose:** the CDC sheet uses US units. Write a metric note on the front door and have the owner review it.
