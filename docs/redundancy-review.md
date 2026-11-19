# Redundancy review

19 Nov 2026. This document only proposes changes. Nothing in `catalog.csv` changes until the owner agrees, item by item.

The owner said there is too much redundancy and random material in the ark. The review looks at all 106 catalog rows together instead of one at a time.

## 1. What the review found

1. **Drive size depends on about eight items.** Every other row together is under 15 GB.

   | Item | GB | Bundle today |
   |---|---|---|
   | Gutenberg, all books (T3-036) | 221 | full (replaces the subject sets) |
   | Survivor Library (T2-091) | 220 | decision |
   | Khan Academy, 2023 (T3-019) | 180 | full |
   | Wikipedia with pictures (T3-001) | 127 (53 without pictures) | core |
   | Gutenberg subject sets (T3-030..035), 39 GB of it fiction and literature | 65 | standard |
   | Europe map (T3-041) | 27 | full (replaces France) |
   | CrashCourse videos (T3-020) | 23 | standard |
   | Wiktionary (T3-002) | 15 | core |

   Size is therefore a handful of owner choices (section 6). Cutting small PDFs saves almost no space.

2. **The clutter is about 25 small rows with no clear job.** Examples: a second survival manual, travel guides, booklets written for tropical smallholders, and books for needs nobody in the family has. They take few GB, but each one costs a sign-off (D9), a permission request, and a family member choosing between near-duplicates.

3. **CD3WD was under-used in our own coverage map.** We indexed it on 19 Nov 2026 (section 4). It already contains 3 of our 5 separately listed Peace Corps manuals. It also covers areas the map marks as "gap": blacksmithing, toolmaking, weaving, soap, lime, cement, bricks and kilns. That makes the case for Survivor Library weaker than it looked.

## 2. Selection rule (adopted 19 Nov 2026, now CLAUDE.md rule 8)

Every item has **one role** in one area of `coverage.csv`:

| Role | Meaning | Limit per area |
|---|---|---|
| **primary** | What the front door points to first. Written for a non-expert. | 1 |
| **depth** | Goes further: clinician level, trade level, reference tables. | 1–2 |
| **cross-check** | Only for medicine and drugs, where a second opinion matters. | 1–2 |
| **gap-filler** | The only source for something the others don't cover. | as needed |
| **deliberate copy** | Required by a rule, e.g. a Tier 1 PDF that also exists inside a ZIM. | — |

Two tests come on top of the role:
- **Fit:** written for a temperate climate (or methods that carry over), at a level a skilled amateur can use, and current where age matters (medicine, drugs).
- **Unique value per GB:** for the big collections, what does it hold that nothing else in the catalog does?

An item with no role, or one that fails the fit test, is cut. That is what "random stuff" means here.

## 3. Redundancy kept on purpose

- **Tier 1 copies** of content that also sits in ZIMs or full books (rule 3). Example: *Where There Is No Doctor* chapter 10 is in `00_EMERGENCY` and also in the full book.
- **Medicine cross-checks:** a lay guide (Hesperian), a clinical guide (MSF), an encyclopedia (WikiMed) and drug references (NHS, MSF *Essential Drugs*, the WTIND Green Pages). If one has a wrong dose, the others catch it.
- **REPLACES pairs:** Gutenberg sets vs. all of Gutenberg, and France vs. Europe. These never sit on the same drive.
- **Multiple drive copies** (CLAUDE.md "Copies"). This is the redundancy that actually protects the library.

## 4. Verified by remote indexing (19 Nov 2026)

The ZIMs' tables of contents were read with HTTP range requests, without downloading the whole files. Script: `zimindex.py` in the session scratchpad. Same method as T2-016 in `catalogue-strategy.md`.

### CD3WD (T2-015, 0.57 GB, core)

- 64,021 entries in total. **288 complete books**: WHO 49, FAO 45, GTZ 38, BOSTID 22, ILO 19, Peace Corps 17, IIRR 14, SKAT 14, and others. Mostly 1980s–1990s.
- **Already inside:** Peace Corps *Small Scale Irrigation Systems* (T2-121), *Traditional Field Crops* (T2-122) and *Solar and Energy Conserving Food Technologies* (T2-123).
- **Not inside:** Peace Corps *Soils, Crops and Fertilizer Use* (T2-120) and *Small Scale Charcoal Making* (T2-124). No Agrodok booklets and no FAO Diversification booklets.
- **Fills "gap" areas:**
  - B1 metalwork and tools: *Basic Techniques of Blacksmithing* and *How to Make Tools* (both Peace Corps).
  - B3 textiles: *Small-Scale Weaving* (ILO).
  - B4 chemistry and materials: soap (GTZ, CDI), *Small Scale Production of Lime for Building*, *Small-Scale Production of Portland Cement*, brickmaking (ILO, GTZ), *The Self-Reliant Potter: Refractories and Kilns*.
  - Also: hand-dug wells, wind pumps, pit silos, rabbits, cattle breeding, food drying and storage (Peace Corps T0020, which the strategy doc listed as "next to find"), and a 1-storey building manual.
- **Watch out:** it also holds older WHO, MSF and Hesperian editions. The front door must point to our current editions for medicine, not to CD3WD.

### Survivor Library (T2-091, 220 GB, decision)

- **11,802 PDFs**, 222.6 GB. About 75% are dated 1880–1929.
- **Text layer:** 6 of 7 sampled trade books have OCR text (readable, with typical OCR errors). One, a Google Books scan, has none. The earlier claim that it is "mostly scans with no searchable text" was too strong: they are scans, but most can be searched.
- **Content, by title keywords** (a rough sort, not a review):
  - About 2,014 titles (55 GB) are periodicals and other mostly off-scope material: magazine and journal runs (*73 Magazine*, *Scientific American*, *The Woman Citizen*), law encyclopedias, political pamphlets, gun manuals and a *Great Books* set.
  - About **888 titles (15 GB) are trade manuals**: blacksmithing, foundry, machine shop, sheet metal, weaving, tanning, soap, pottery, masonry and similar.
  - The other ~8,900 titles (153 GB) are a mix of farming, medicine, science, schoolbooks and general old books. Medicine is outdated and must not be used for treatment.
- **The Kiwix package can't be split.** A subset means taking individual PDFs by hand: from survivorlibrary.com, or by range-reading the ZIM as we did here.

## 5. Proposed changes, by area

**Owner decisions, 19 Nov 2026 (applied to `catalog.csv`):**
- **Accepted:**
  - Cut T2-104 (SERE), T2-029 (*Workers' Guide*), T2-030 (*Health Actions for Women*), T2-033 (HIV), T2-071 (Agrodok preserving) and T2-090 (Gardenology).
  - T2-016 moves to full.
  - T1-005 moves out of Tier 1 and becomes **T2-038** in `01_LIVING/health-ongoing`.
- **Kept, against the proposal:**
  - CDC *Travelers' Health*, and the disability and child titles (T2-027, T2-031, T2-032, T2-034).
  - The three Peace Corps PDFs that are also inside CD3WD.
  - Agrodok compost, and the FAO gardens and processing booklets.
- **Round 2 (same day):**
  - Accepted all the reference proposals: Wiktionary, the Factbook and Ready.gov to standard; Wikisource to full; Wikivoyage and Wikiversity cut.
  - WikiCiv and Low-tech Magazine go **into standard, labelled** ("community answers"; Low-tech Magazine's licence still to ask).
  - Wikipedia **keeps its pictures**.
  - CrashCourse and Khan Academy **stay as they are**.
- **Not yet asked:** dropping the strategy doc's plan to add the Gutenberg R, U, G and H sets (section 6, question 4).

The tables below are the original proposals.

GB = change in the bundle that holds the item. "Cut" means a row in `rejected.csv` with the reason.

### Survival field manuals
| Item | Role | Proposal |
|---|---|---|
| T2-100 Army *Survival* (core) | primary | keep |
| T2-104 Air Force SERE handbook (652 pp., standard) | none: same topics as T2-100, more military | **cut** |
| T2-016 Army publications library (8.2 GB, standard) | none after extraction: its useful manuals (Survival, Carpentry, Concrete) are already separate rows; most of its 5,768 PDFs are forms and military doctrine | **move to full** (−8.2 GB standard) |

### Tier 1 first aid
| Item | Role | Proposal |
|---|---|---|
| T1-003 Hesperian ch. 10 | primary (lay) | keep |
| T1-004 ATP 4-02.11 | depth: severe bleeding, CPR | keep |
| T1-006 IFRC 2025 guidelines | cross-check: current evidence | keep |
| T1-005 WHO-ICRC *Basic Emergency Care* | depth, written for health workers | **move** from `00_EMERGENCY` to `01_LIVING/health-ongoing` (still core). Fewer choices in an emergency. |

### Medicine
Roles as in section 3; all core medical rows are kept. Cut the niche titles unless someone in the family needs one:
| Item | Proposal |
|---|---|
| T2-005 CDC *Travelers' Health* | **cut**: travel advice by country |
| T2-029 *Workers' Guide to Health and Safety* | **cut**: factory workplace rights |
| T2-027 *Disabled Village Children*, T2-030 *Health Actions for Women*, T2-031 *Deaf*, T2-032 *Blind*, T2-033 *HIV*, T2-034 *Women with Disabilities* | **cut** unless relevant to a family member (owner) |

### Appropriate technology and rebuild
| Item | Role | Proposal |
|---|---|---|
| T2-015 CD3WD | primary for rebuild and appropriate technology | keep (core) |
| T2-014 energypedia | depth: energy | keep |
| T2-013 Appropedia | depth: community wiki | keep (core, small) |
| T2-121, T2-122, T2-123 Peace Corps PDFs | duplicates of CD3WD | **cut** |
| T2-120 Peace Corps *Soils, Crops and Fertilizer* | gap-filler for B6 | keep |
| T2-124 Peace Corps *Charcoal* (scan) | weak: CD3WD has charcoal pages | keep for now, low priority |
| T2-092 WikiCiv | none: CD3WD covers lime, cement, kilns and charcoal from known publishers; authors unknown, has explosives pages | **reject** |
| T2-093 Low-tech Magazine | licence unknown | **reject for v1** |
| T2-091 Survivor Library | see section 6, question 1 | **reject the 220 GB package** |

### Food growing, preserving, animals
| Item | Role | Proposal |
|---|---|---|
| T2-073 Virginia *Gardener Handbook* | primary (temperate) | keep |
| T2-072 Agrodok mushrooms | gap-filler | keep |
| T2-070 Agrodok compost | none: covered by T2-073 and CD3WD | **cut** |
| T2-071 Agrodok preserving | none: USDA canning (T2-011) is primary; CD3WD has FAO *Rural processing and preserving* and Peace Corps food drying | **cut** |
| T2-113 FAO *Livelihoods grow in gardens* | fails fit: tropical, livelihoods focus | **cut** |
| T2-114 FAO *Processing for prosperity* | fails fit: small-business focus | **cut** |
| T2-110..112 FAO poultry, small animals, sheep and goats | primary for livestock | keep |
| T2-090 Gardenology | none: Wikipedia with pictures covers plants; community wiki | **reject** |

The four cuts above also remove two licence problems: Agrodok, whose rights holder no longer exists, and two of the four FAO permission requests.

### Reference
| Item | Role | Proposal |
|---|---|---|
| T3-002 Wiktionary (15 GB) | nice to have, not survive or sustain | **move core → standard** (−14.9 GB core) |
| T3-007 CIA Factbook 2020 | understand layer | **move core → standard** |
| T2-010 Ready.gov (2 GB, US-centric) | depth for preparedness | **move core → standard**. The front door carries the French basics. |
| T3-006 Wikivoyage | none without travel | **cut** |
| T3-004 Wikiversity | none: LibreTexts and Wikibooks do it better | **cut** |
| T3-005 Wikisource | overlaps Gutenberg | **move standard → full** |
| T3-003 Wikibooks | the only cooking-from-scratch source (Cookbook) | keep |

## 6. Owner questions (the big GB levers)

1. **Survivor Library.**
   - (a) Reject it outright. The rebuild layer comes from CD3WD, Gutenberg T (technology) and S (agriculture), and the trade manuals in the catalog.
   - (b) Later, a **hand-picked trades subset**: about 900 titles and 15 GB, as one catalog row with one sign-off, in the full bundle.
   - (c) The whole 220 GB in the full bundle.

   *Recommendation: (a) now, with (b) noted as a v2 option if the CD3WD and Gutenberg trade books prove too thin once someone actually reads them.*

   **Decided 19 Nov 2026: (a).** T2-091 removed from `catalog.csv` and recorded in `rejected.csv`; the trades subset is a v2 option.
2. **Wikipedia pictures** (127 vs. 53 GB). Pictures are our fallback for identifying wild plants (F4 has no other open source) and for anatomy and tools. *Recommendation: keep the pictures.* Without Wiktionary in core, core is still under 150 GB.
3. **Education videos.** CrashCourse (23 GB, standard) and Khan Academy (180 GB, 2023, full) overlap with each other and with LibreTexts. The answer depends on who is being taught and at what age. *Owner input needed.*
4. **Gutenberg fiction.** Literature and children's sets (PZ, PR, PS) take 39 of the 65 GB in standard. They matter for morale and teaching, so they're kept. The strategy doc's idea of adding R, U, G and H in standard is **dropped**: it adds bulk, and R is historical medicine.

## 7. Bundle totals

**After both rounds of decisions (19 Nov 2026): core 148.3 GB (37 items), standard 272.6 GB (89), full 646.6 GB (90).** The table below shows the original proposal.

Computed from `catalog.csv` on 19 Nov 2026, with Stack Exchange now in standard. Hesperian PDFs aren't counted (under 1 GB in total).

| Bundle | Today | With the section 5 proposals | Plus Wikipedia without pictures |
|---|---|---|---|
| core | 165.6 GB, 40 items | 148.3 GB, 37 items | 73.6 GB |
| standard | 292.0 GB, 94 items | 271.7 GB, 79 items | — |
| full | 649.1 GB, 95 items | 645.7 GB, 77 items | — |

The section 5 proposals mainly remove items (18 fewer in full). Big GB savings only come from the section 6 choices: Khan Academy −180, Wikipedia without pictures −75, CrashCourse −23.

## 8. Follow-up once agreed

- Change `bundle` in `catalog.csv` and add rejected rows to `rejected.csv`.
- Fix `coverage.csv`: B1, B3 and B4 move from "gap" to "partial" (CD3WD); credit CD3WD for wells, wind pumps and food drying.
- Remove from `catalogue-strategy.md` next steps the browser hunt for more Peace Corps titles. CD3WD already holds 17 of them.

## Not verified

- The keyword sort of Survivor Library is rough. Counts are good to about ±20%. Nobody has reviewed the titles.
- Whether Gutenberg T or S holds the same trade books as Survivor Library (title matching not done).
- How deep CD3WD's charcoal, soap and weaving material goes. Only titles were read, not the text.
- Whether Kiwix full-text search indexes the text inside PDFs in zimit packages such as Survivor Library.
