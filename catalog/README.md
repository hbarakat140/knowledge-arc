# Catalog

Two files drive the build: `catalog.csv` (what goes on the drive) and `publishers.csv` (who we trust). `deferred-non-english.csv` keeps French and Arabic items researched earlier, for a later version (v1 is English only). Both are UTF-8 CSV with LF line endings. To open them in Excel without broken accents, use **Data → From Text/CSV** and pick UTF-8.

## Navigation tags (added 21 Nov 2026)

The arc is an offline learning website for anyone who has a copy (`docs/architecture.md` sections 2-4). Its pages are generated from these files:

- `subjects.csv`: the 11 stable subjects (`id, order, label, description`), the main menu.
- `coverage.csv`: each area is a **topic** under one `subject`. `covered_by` lists the items tagged with that topic; the lint keeps it equal to the catalog's `topic` tags.
- `catalog.csv`: four tags per row, described in the column table below. Software rows (T9) have shelf `software` and no topic or job. `label` is the name people see when the title is a code or not unique (e.g. "Gutenberg: science books", "Survival (US Army manual)"); the lint keeps displayed names unique.
- `coverage.csv` `search`: hand-picked search words per topic (21 Nov 2026), shown on its page as ready-made searches of the full library.
- `coverage.csv` `sections` and `catalog.csv` `section`: a big topic's section headings, in order, and the section an item sits in (a 4th level, owner 21 Nov 2026). 9 topics have sections today (S3, H4, F1, F2, E1, R2, B1, B6, T2). Items with no section come last under "More on this topic". The lint checks every section is listed by the item's home topic and every listed section has items.
- `frontdoor/situations.csv` `topic`: the topic page each "where to look first" situation appears on.

Tagging choices made on 21 Nov 2026: multi-subject collections take the topics they were already listed under in `coverage.csv` (CD3WD's home is B4, the topic its soap, lime and cement manuals lead); all of Gutenberg (T3-036, full) takes over the topics of the subject sets it replaces; Gutenberg's children's set and Book Dash also sit in K1 (stories); Stack Exchange sites, WikiCiv and Low-tech Magazine are on the `community` shelf.

The tiers (1 emergency, 2 living, 3 knowledge) and the bundles stay for now; since phase 3 the tags, not the tiers, decide where a file goes on the drive, and a `pocket` edition sits below core since phase 5 (21 Nov 2026).

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
| `id` | hand | `T1-NNN`, `T2-NNN`, `T3-NNN`, and `T9-NNN` for software in `arc/software/` (the library server for each system, and the Kiwix app for Android). Never reused. |
| `title`, `label` (optional), `publisher`, `source_url`, `edition_or_date`, `licence`, `tier`, `folder`, `language`, `format`, `notes` | hand | `publisher` must be an `id` from publishers.csv. `folder` is the path on the drive from its top (and in the archive): `arc/guides/<home subject>/` for PDFs (one optional subfolder, e.g. `learning-to-read/`), `arc/collections/` for ZIMs, `arc/software/<os>/` for software. It is the full file path (plain ASCII, `topic_publisher_year.pdf`) for a single file, or a directory for a multi-file item such as a Hesperian book, whose files keep the publisher's names. The front door links to these exact names. For a ZIM, `source_url` is the Kiwix `.meta4` link, which lists the mirrors and the sha-256. |
| `bundle` | hand | `pocket`, `core`, `standard`, `full` or `decision`. See below. Every document (anything that isn't a ZIM) goes in `pocket`; the catalog test checks it. |
| `download_date`, `sha256` | download script | Left blank until the file is actually downloaded. For a multi-file book, `sha256` is the sha-256 of its sorted list of `<file sha256>  <file name>` lines. |
| `size_bytes` | check / script | Only from a real HTTP Content-Length, a download, or the Kiwix feed. If it is filled and the download differs, the script stops that item and leaves the file aside: servers sometimes send an error page as a "PDF". Blank values are filled in by the script. |
| `text_layer` | check / script | `y` only after text was actually extracted, or for HTML/ZIM content. |
| `reviewer` | owner | `pending-owner` until a person has read the item and signed off. |
| `topic` | hand | Coverage ids separated by `;`, the item's **home** topic first. The item appears on every listed topic's page. |
| `section` | hand | Optional: one of the home topic's `sections` (coverage.csv). Groups the item under that heading on the topic page. |
| `shelf` | hand | `guides`, `books`, `encyclopedias`, `courses`, `videos`, `films`, `music`, `maps`, `community` (Stack Exchange, WikiCiv, Low-tech Magazine: always labelled "community answers") or `software`. |
| `audience` | hand | `all`, `children` (also gathered by the "For children" door) or `advanced` (written for professionals or university level). |
| `job` | hand | The item's role in its home topic (CLAUDE.md rule 8): `primary` (a "start here" item), `depth`, `cross-check`, `gap-filler` or `copy` (a deliberate copy a rule requires). Sets the order on topic pages. |

"To verify" in `licence` or `edition_or_date` means it wasn't confirmed at the source yet. Check it before the full build.

## Bundles (17 Nov 2026)

A row whose notes say `REPLACES T3-030..T3-035` takes the place of those rows when its bundle is built; the scripts read that exact wording. See `scripts/README.md`.


The library is built mainly from ready-made collections: the official Kiwix/openZIM catalogue (1,314 English packages, read live with exact sizes and dates) and Hesperian's complete English book list. Each item belongs to one bundle, and each bundle includes the ones before it.

| Bundle | Size | What it adds |
|---|---|---|
| **pocket** | **~22.5 GB** (about 26 GB on the drive) | Every document in the catalog (all PDFs: first aid, medicine, water, food growing, animals, building, trades, energy, radio, learning to read; 12 Hesperian books), the programs to open them (T9-001..013), and these collections: WikiMed (the medical encyclopedia), NHS medicines, US military medicine, WikiVet, USDA home canning, iFixit, CD3WD, PhET, and the short English Wikipedia (T3-070: the opening of every article, no pictures, 14.4 GB). Sized for a 32 GB card or stick (phase 5, 21 Nov 2026). |
| **core** | **~149.4 GB** | The full English Wikipedia with pictures (127 GB; replaces the short one), MedlinePlus, Appropedia, energypedia, Wikibooks, the map of France. |
| **standard** | **~285.3 GB** | Stack Exchange, WikiCiv and Low-tech Magazine (labelled "community answers"; 11 Stack Exchange sites, 8.75 GB), Wiktionary (15 GB), CIA World Factbook, Ready.gov, CDC travel health, Book Dash picture books (11.7 GB), 8 LibreTexts textbook sets, Crash Course videos (23 GB), Gutenberg subject sets (agriculture, technology, science, children's, English and American literature, 65 GB). |
| **full** | **~659.3 GB** | US Army publications library (8 GB), Wikisource (9 GB), Khan Academy (180 GB, 2023 snapshot), all of Gutenberg (221 GB; replaces the subject sets), maps of Europe (replaces France). |

Sizes were recomputed from `catalog.csv` on 21 Nov 2026, after phase 5 moved every document into the pocket edition (documents are small, so the editions now differ only in their collections); contents were last reshaped by the redundancy review of 19 Nov 2026 (`docs/redundancy-review.md`). Hesperian PDFs add under 1 GB in total; their server doesn't report sizes. Videos beyond Crash Course and Khan Academy aren't chosen yet (D6).

Rough drive fit:
- pocket fits on 32 GB (a 32 GB card holds about 31.9 billion bytes)
- core fits on 500 GB
- standard fits on 1 TB
- full fits on 1 TB with little headroom, so plan 2 TB to leave room for later additions and the AI layer

### Owner decisions (all made 19 Nov 2026; no `decision` rows left)

1. **Stack Exchange** (11 sites, 8.75 GB): included in standard, in a clearly labelled "community answers" area, with a spot check of each site (D9).
2. **Survivor Library** (220 GB): rejected for v1 (in `rejected.csv`). A hand-picked trades subset is an option for v2.
3. **Gardenology**: rejected (in `rejected.csv`).
4. **Wikipedia:** with pictures (127 GB) in core. The pictures are the fallback for identifying plants. The pocket edition has the short version (T3-070, 14.4 GB), which core's replaces.
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
- **Heating, seed saving, machining, draught animals, cooking (checked 20 Nov 2026):**
  - Insulation: NRCan *Keeping the Heat In* (T2-128). Wood heating: CMHC/NRCan *A Guide to Residential Wood Heating* (T2-129, saved by hand: publications.gc.ca shows an archive notice first).
  - Seed saving: Organic Seed Alliance guide (T2-130), using the publisher's 2010 PDF, because the 2026 revision is a web page only.
  - Machining: US Army TC 9-524 (T2-131, standard), from armypubs, where it is still active.
  - Draught animals: Peace Corps *Animal Traction* M-12 (T2-132, standard), a scan with OCR, written for West Africa.
  - No new items were needed for two of the gaps. Grain storage: CD3WD already holds FAO *Grain storage techniques*. Cooking from scratch: the Wikibooks Cookbook (5,282 pages) is inside the Wikibooks ZIM (T3-003).
  - Still open: a temperate draught-animal guide, and a French planting calendar (deferred with the French content).
- **Bees, radio, children's reading (checked 20-21 Nov 2026):**
  - Bees: the UK National Bee Unit's *Starting Right with Bees* and *Managing Varroa* (T2-133, T2-134, core). Its 2011 "international" training manuals were left out: they are written for African top-bar beekeeping.
  - Radio: US Army FM 24-18 (T2-135, standard, 1987). Its successor, ATP 6-02.53 (2025), has no public PDF. The EverySpec copy changes its PDF ID on every download, so it has no fixed hash.
  - Children's reading: Book Dash picture books (T3-056, standard, 11.7 GB). The ZIM is a crawl of the whole site, in all of its languages.
  - Still open then: a civilian amateur-radio handbook (print), guidance on licence-free radios, graded early readers, pigs and cattle.
- **Livestock, oxen, radio rules, arts (checked 21 Nov 2026):**
  - Pigs: B.C. *Small Lot Pork Producer* manual (T2-136, core, 2020), written by a swine vet practice for small outdoor herds, with a section on humane euthanasia. Chosen over the AHDB guide (mostly UK registration law) and the Canadian vets' 2021 manual (a condensed version of the same text, no licence stated).
  - Animal health without a vet: *Where There Is No Animal Doctor* (T2-137, core, CVM, revised 2016). Written for developing countries, but only a small share is tropical disease, and no temperate guide teaches a keeper to examine, diagnose and dose.
  - Cattle: Teagasc *Beef Manual* (Ireland, 2016), sections 4 (breeding), 6 (nutrition) and 7 (health) as T2-138..140 (standard). The other five sections are Irish business, policy, commercial systems and buildings. Alberta's *Beef Cow-Calf Manual* would have been a single-file choice, but its servers timed out or returned 403.
  - Humane killing: HSA *On-farm Humane Killing of Cattle & Sheep* (T2-141, core), from the National Sheep Association's copy; hsa.org.uk blocks scripts.
  - Oxen: UNH *4-H Working Steer Manual* (T2-142, standard). Horses need nothing new: the Gutenberg agriculture set (T3-030) holds old books on draught breeds, breaking, driving and shoeing.
  - Radio rules: a checked front-door note (`frontdoor/notes/09_radio-france.txt`) on PMR446, CB, ham licensing, which stations carry official alerts, the siren signal and the end of AM in France. No catalog row: it is front-door text, shown on every drive.
  - Arts, music and play: no new item. Wikibooks (T3-003) already has instrument books, songbooks, chess and other games, origami and drawing. The Open Music Theory ZIM holds the old college-level v1 site; Mutopia is 6.6 GB of classical scores.
  - Still open: HSA Technical Note 8 (*On-farm slaughter of livestock for consumption*; fetch in Chrome), a family milk-cow guide (none found), the exact FM 24-18 page to link from the radio situation (EverySpec blocks scripts).
- **Learning to read (checked 21 Nov 2026):**
  - The parent's guide: *Letters and Sounds* (DfES 2007, T3-057, standard), England's phonics programme from 2007. DfE dropped it from its validated list in 2021 because it has no books or training of its own, not because its method was wrong.
  - The child's books: 12 fully decodable Core Knowledge CKLA Skills Strand readers (T3-058..069, standard, CC BY-NC-SA 3.0), Kindergarten Units 6-10 and Grade 1 Units 1-7, from first CVC words to the end of Grade 1 decoding.
  - The two use different sound orders; the front door's "Teaching children to read" section says which book goes with which phase.
  - Left out: NZ *Ready to Read Phonics Plus* (no direct PDF links), McGuffey primers (dated), StoryWeaver (not in the Kiwix feed), the African Storybook ZIM (duplicates Book Dash; in `rejected.csv`), CKLA Grade 2 (not needed for decoding).
- **Off-grid energy (checked 21 Nov 2026):**
  - Solar electricity and batteries: *Your guide to installing solar energy for off-grid buildings* (Arctic Renewables Society and Relay Education, 2025; T2-143, core). Step by step, including lithium iron phosphate batteries and cold weather. Cable sizes are in AWG; the row notes give the metric equivalents.
  - Small wind and micro-hydro: NRCan *Stand-Alone Wind Energy Systems* (2004) and *Micro-Hydropower Systems* (2004) buyer's guides (T2-144, T2-145, standard). Planning, site measurement and maintenance, not build-it-yourself manuals.
  - Left out: NRCan *Photovoltaic Systems: A Buyer's Guide* (2002, before lithium batteries) and the SEIAPI/PPA *Off Grid PV* design guidelines (2012, tropical installer checklist; garbled text layer).
- **Household preparedness (checked 21 Nov 2026):** Sweden's *In case of crisis or war* (MCF, June 2026 English edition; T2-146, core) is the primary: a week on your own, water, heat, food, radio, cash, emergency toilet. Ready.gov (T2-010, standard) stays as depth; the two are complementary. France's *Tous responsables* (SGDSN, 2025) is in `deferred-non-english.csv`. Left out: the EU's 72-hour guidelines staff working document (Oct 2026), written for national authorities.
- **Slaughter for meat (checked 21 Nov 2026):** poultry, HSA *Practical Slaughter of Poultry* (T2-147, core) for humane killing, then K-State EP-71 (T2-148, core) for plucking and gutting (its kill step is replaced by T2-147's, as EU rules require stunning or neck dislocation first). Beef, pork and lamb were already covered: the USDA *Slaughtering, Cutting, Preserving, and Cooking on the Farm* bulletins (1977-78) are in the Gutenberg agriculture set (T3-030). Left out: HSA Technical Note 8 and *Caring to the End* (overlap T2-141; mostly UK law). Still open: rabbits, and a family milk-cow guide.
- **Textiles, soap, lime and glass (checked 21 Nov 2026):** no new items. Read inside the ZIMs rather than by title:
  - Textiles: the Gutenberg technology set (T3-031) has *Encyclopedia of Needlework*, two mending books and many knitting books. CD3WD (T2-015) has VITA *Handloom Construction* (how-to); the ILO weaving and footwear memoranda are workshop planning, depth only. Home tanning is in the Peace Corps rabbit handbook.
  - Soap: VITA *Home Soap Making* (CD3WD) is the family guide. Its lye first aid is out of date (vinegar); `coverage.csv` B4 gives the current advice. GTZ and CDI soap books are small-business depth.
  - Lime: the GTZ lime book plans a lime works and gives no burn warnings; B4 notes the goggles-and-gloves rule. The GTZ *Glazes* book warns against lead glazes.
  - Old Gutenberg tanning, soap, dyeing and glass books are industrial and pre-1930: reference only.
  - Still open on purpose: hand spinning (only histories found) and household glass making (needs a furnace).
- **Metric water dose:** the CDC sheet uses US units. Write a metric note on the front door and have the owner review it.
