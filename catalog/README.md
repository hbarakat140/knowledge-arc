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
| `id` | hand | `T1-NNN`, `T2-NNN`, `T3-NNN`. Never reused. |
| `title`, `publisher`, `source_url`, `edition_or_date`, `licence`, `tier`, `folder`, `language`, `format`, `notes` | hand | `publisher` must be an `id` from publishers.csv. `folder` is the path on the drive. For a ZIM, `source_url` is the Kiwix `.meta4` link, which lists the mirrors and the sha-256. |
| `bundle` | hand | `core`, `standard`, `full` or `decision`. See below. |
| `download_date`, `sha256` | download script | Left blank until the file is actually downloaded. |
| `size_bytes` | check / script | Only from a real HTTP Content-Length, a download, or the Kiwix feed. The script overwrites it. |
| `text_layer` | check / script | `y` only after text was actually extracted, or for HTML/ZIM content. |
| `reviewer` | owner | `pending-owner` until a person has read the item and signed off. |

"To verify" in `licence` or `edition_or_date` means it wasn't confirmed at the source yet. Check it before the full build.

## Bundles (17 Nov 2026)

The library is built mainly from ready-made collections: the official Kiwix/openZIM catalogue (1,314 English packages, read live with exact sizes and dates) and Hesperian's complete English book list. Each item belongs to one bundle, and each bundle includes the ones before it.

| Bundle | Size | What it adds |
|---|---|---|
| **core** | **~165 GB** | Tier 1 emergency PDFs. Medicine: WikiMed, MedlinePlus, NHS medicines, US military medical manuals, 6 Hesperian books (*Where There Is No Doctor*, *Where Women Have No Doctor*, *Where There Is No Dentist*, *A Book for Midwives*, *Community Guide to Environmental Health*, *Community Mental Health*). Living: WHO water notes, USDA home canning, Ready.gov, iFixit, Appropedia, energypedia, CD3WD, WikiVet. Reference: full English Wikipedia with pictures (127 GB of the 165), Wiktionary, Wikibooks, CIA World Factbook, PhET. Maps: France. |
| **standard** | **~283 GB** | US Army publications library (8 GB), CDC travel health, 4 more Hesperian books, Wikiversity, Wikisource, Wikivoyage, 8 LibreTexts textbook sets, Crash Course videos (23 GB), Gutenberg subject sets (agriculture, technology, science, children's, English and American literature, 65 GB). |
| **full** | **~640 GB** | Khan Academy (180 GB, 2023 snapshot), all of Gutenberg (221 GB; replaces the subject sets), maps of Europe (replaces France), 5 more Hesperian books. |

Hesperian PDFs add under 1 GB in total; their server doesn't report sizes. Videos beyond Crash Course and Khan Academy aren't chosen yet (D6).

Rough drive fit:
- core fits on 500 GB
- standard fits on 1 TB
- full fits on 1 TB with little headroom, so plan 2 TB to leave room for later additions and the AI layer

### Owner decisions (`bundle = decision`)

1. **Stack Exchange** (11 sites, 8.75 GB): DIY, gardening, cooking, outdoors, mechanics, bicycles, electronics, ham radio, woodworking, homebrew, sustainability. It holds practical know-how found nowhere else, but it's community Q&A, which `CLAUDE.md` had flagged as below the quality bar. *Recommendation: include it in a clearly labelled "community answers" area.*
2. **Survivor Library** (220 GB): mostly scanned books from 1800–1930 with outdated medicine. *Recommendation: reject.*
3. **Gardenology** (0.11 GB): plant encyclopedia from a community wiki with unknown editorial control. *Recommendation: review a sample first.*
4. **Wikipedia with or without pictures:** core uses pictures (127 GB). Without pictures it's 53 GB, which saves 75 GB but loses plant, anatomy and tool images.

### Rejected after inspection (no rows)

| Package | Why |
|---|---|
| `zimgit-medicine`, `zimgit-post-disaster`, `zimgit-food-preparation`, `zimgit-water`, `zimgit-knots` | Opened on 17 Nov 2026: they mix good documents with outdated editions (*Where There Is No Doctor* 2011, superseded FM 4-25.11), a suture-maker's brochure, an acupuncture "visual diagnosis" sheet, and gift-jar recipes. Their good items are covered better elsewhere (Hesperian 2025, ATP 4-02.11, USDA canning). The Agrodok farming booklets inside them are worth sourcing directly (see gaps). |
| Prepper YouTube channels (`canadian-prepper`, `urban-prepper`, `s2underground`, `lrnselfreliance`), `trueprepper.com`, `quickguidesformedicine` | Individual creators, not trusted publishers. |
| `wikipedia_en_medicine`, `wikipedia_en_top`, `wikipedia_en_top1m`, `wikipedia_en_100` | Already contained in the full Wikipedia. |
| TED collections | Multilingual packages. Revisit with the video selection. |
| `onemorelibrary`, `voa_learning`, games, programming and fandom wikis | Unknown curation or off-topic. |

## Tier 1 (emergency PDFs, English)

Seven items: T1-003 to T1-008 and T1-010. What was actually checked on 17 Nov 2026:

| Check | Items |
|---|---|
| PDF fetched and its text read | T1-003, T1-004, T1-005, T1-007, T1-010 |
| Only the landing page was read; the PDF itself was never retrieved | T1-008 (CDC returns 403 to scripts) |
| Not reached at all: site blocks scripts | T1-006 (IFRC 2025; only the 2020 fallback URL was confirmed, by HEAD request) |

### How the situation folders are covered

| Folder | Standalone item | Page links into the manuals |
|---|---|---|
| `00_call-for-help` | none yet: the front door shows the French emergency numbers in English (sources in `deferred-non-english.csv`) | — |
| `01_bleeding-wounds` | — | Hesperian ch. 10, PDF p. 8–16; ATP 4-02.11 (tourniquet pages) |
| `02_breathing-cpr` | — | ATP 4-02.11 PDF p. 94–96 (CPR); Hesperian ch. 10, PDF p. 5–6 (choking, rescue breathing) |
| `03_burns` | — | Hesperian ch. 10, PDF p. 22–23 |
| `04_poisoning` | — | Hesperian ch. 10, PDF p. 29 |
| `05_water-purification` | T1-007, T1-008 | — |
| `06_cold-heat` | T1-010 (heat) | Hesperian ch. 10, PDF p. 7 (heat); ATP 4-02.11 (hypothermia pages) |
| `10_first-aid-manuals` | T1-003 to T1-006 | — |

The front door will link straight to a page, for example `en_wtnd_2025_10.pdf#page=8`. Check that this works in Windows browsers during the prototype (step 4).

## Owner actions before the build

1. Make the decisions above, then review and sign off each `pending-owner` row.
2. Email `permissions@hesperian.org` about keeping the Hesperian books on private family drives and using them for teaching. Their copyright page asks for permission for "any digital format".
3. Download T1-006 (IFRC 2025) by hand in a browser, because the site blocks scripts.

## Remaining gaps

- **Moving to English-only reopened two Tier 1 gaps.** The French GQS sheet and the sante.fr cold page are now deferred. There's no short, freely reusable CPR sheet in English (ERC/RCUK needs permission, the Canadian Red Cross guide is all rights reserved), and no English cold-weather leaflet. The manuals cover both topics.
- **Farming and food growing:** Agrodok booklets (Agromisa/CTA) and FAO guides, sourced directly. **Foraging:** the European flora gap from `CLAUDE.md` is still open.
- **Metric water dose:** the CDC sheet uses US units. Write a metric note on the front door and have the owner review it.
