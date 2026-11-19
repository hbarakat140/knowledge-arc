# Catalogue strategy

Draft, 18 Nov 2026. How the full catalogue is built from existing collections instead of item by item, what the first scan found, and what is still open.

## 1. Two decisions for the owner

**Decided 19 Nov 2026:** D8 = (b) layered knowledge ark; D9 = (b) one sign-off per collection after a recorded spot check. Both as recommended below.

| # | Question | Options | Recommendation |
|---|---|---|---|
| D8 | **Scope** | (a) *Family library*: get a household through months without internet (CLAUDE.md today). (b) *Knowledge ark*: also hold what's needed to **rebuild**: trades, materials, metalwork, farming at scale. | (b), as layers: survive and sustain stay core; *rebuild* goes in standard and full. The coverage map below already includes the rebuild layer so nothing is missed; it can be trimmed. If (b), reconsider Survivor Library (old scanned trade books, 220 GB): it was rejected for outdated *medicine*, which a "historical" label handles. |
| D9 | **Quality bar** | (a) Every item reviewed (CLAUDE.md today). (b) **One sign-off per collection**, after a recorded spot check of a sample, with community content clearly labelled. | (b). Nobody can review Wikipedia or Gutenberg page by page. About 60 sign-offs instead of thousands. Tier 1 stays hand-picked (rule 3). |

## 2. The method

The catalogue is driven by a **coverage map**, not by what we happen to find.

```
catalog/coverage.csv      35 knowledge areas x 6 layers: what each must answer,
                          matching keywords, catalog items covering it, status
        |
scripts/scan_kiwix.py     reads the official Kiwix catalogue (1,314 English
                          packages) and scores each against the map
        |
catalog/candidates-kiwix.csv   every package: in-catalog / rejected / candidate
                               / unmatched, with areas, flags, size, date
        |
decision per collection   -> catalog.csv (taken) or catalog/rejected.csv (not taken)
```

Layers: **survive** (hours to days), **sustain** (months), **rebuild** (years), **understand**, **teach**, **culture**.

### The source ladder

For each gap, use the highest rung that has a trusted answer:

1. **Kiwix/openZIM packages.** Ready-made, dated, with sha-256 hashes. This is already most of the catalog (53 of 83 rows, nearly all the bytes).
2. **Gutenberg subject sets.** Kiwix splits Project Gutenberg into 40 Library of Congress classes: agriculture (S), technology and crafts (T), medicine (R), military science (U), geography and recreation (G), and more. Old books, but exactly the rebuild layer. Pick classes, not books.
3. **Whole publisher sets.** Take all of a trusted publisher's guides through one scripted index page, as already done for Hesperian. Examples: all MSF guidelines, all WHO technical notes, the Peace Corps manuals.
4. **Our own Kiwix packages of trusted websites** (zimit, runs in Docker). One *site* per build, instead of one PDF per row. For sites nobody has packaged. The website's licence still applies.
5. **Single items:** only Tier 1 and real gaps.
6. **Print** for copyrighted essentials with no open equivalent.

Kolibri courses (with exercises) need a server program running, which breaks the zero-install rule. They're a level-3 extra at most.

## 3. First scan (18 Nov 2026)

1,257 packages (best flavour of each): 52 already in the catalog, 21 rejected, 457 matched an area, 727 matched nothing (programming, games, fandom wikis and so on).

### Big families: decide each as a family

| Family | Packages | Size | In catalog | Proposal |
|---|---|---|---|---|
| TED talks | 359 | 680 GB | 0 | Skip for v1. They're multilingual and mostly inspiration, not instructions. Revisit with the videos decision (D6). |
| OpenStreetMap regions | 193 | 331 GB | France, Europe | Enough. Add neighbouring regions only if the owner travels. |
| Gutenberg subject sets | 42 | 654 GB (the full library is 221 GB) | 7 | Standard adds **R** (medicine, historical, 1.5 GB), **U** (military science, 0.9 GB), **G** (geography and recreation, 6.3 GB) and **H** (social sciences, 4.1 GB). Full keeps the whole library. |
| Stack Exchange | 175 | 71 GB | 11 (decision rows) | Already an owner decision. Only practical sites, labelled "community answers". |
| Wikipedia subsets | 29 | 212 GB | full Wikipedia | Nothing to add. |

### By area

Status is my judgement of coverage today. "Scan found" lists only curated (non-family) Kiwix packages worth a look.

| Area | Status | Scan found in Kiwix | Next source to check (rung) |
|---|---|---|---|
| S1 First aid | good | - | Done (hand-picked Tier 1) |
| S2 Water, sanitation | good | - | Metric bleach note (needs CDC sheet) |
| S3 Shelter, warmth | partial | nothing | **Done 18 Nov:** Army *Survival* (T2-100). Still missing: home heating and insulation (Low-tech Magazine T2-093, owner decision) |
| S4 Preparedness | partial | nothing | UK/EU government guidance (4) |
| H1–H4 Medicine | good | nothing new | - |
| H5 Nutrition | partial | nothing | FAO nutrition guides (3): FAO repository refuses scripts; www.fao.org PDFs work |
| F1 Growing food | partial | gardenology (owner decision) | Extension services as own packages (4); Gutenberg S is in standard |
| F2 Livestock | partial | nothing | **Done 18 Nov:** FAO booklets on poultry, small animals, sheep and goats (T2-110..112). Next: FAO beekeeping and dairy booklets (1, 6); extension services (4) |
| F3 Cooking, preserving | partial | 4 small community recipe sites | **Done 18 Nov:** FAO food processing (T2-114), Peace Corps solar food technologies (T2-123). Next: Peace Corps *Improved Food Drying and Storage* (T0020) |
| F4 Wild plants, fungi | **gap** | nothing | Print field guide; Wikipedia's plant articles with pictures |
| E1 Off-grid energy | partial | **Low-tech Magazine** (0.7 GB, licence unconfirmed; T2-093 decision) | Practical Action briefs need permission; DOE small-wind guide unverified |
| R1 Repair | partial | nothing new | iFixit is in |
| R2 Building | partial | **WikiCiv** (T2-092, owner decision) | **Done 18 Nov:** Army *Carpentry* (T2-101), *Concrete and Masonry* (T2-102), USDA *Wood Handbook* (T2-103). Missing: plumbing and house wiring (Navy Seabee manuals, manual download) |
| C1 Radio | **gap** | nothing | Army signal manuals in T2-016 are organisational, not how-to. Print ham radio handbook |
| N1 Navigation, weather | partial | nothing | Survival manual covers field navigation. The Army land navigation manual (TC 3-25.26) is restricted and not in T2-016: not taken |
| B1 Metalwork, tools | **gap** | WikiCiv (smelting, casting) | Navy Seabee *Steelworker* (welding, metalwork), manual download; Gutenberg T (in standard); print |
| B2 Woodworking, crafts | partial | nothing | **Done 18 Nov:** Army *Carpentry* (T2-101); Gutenberg T |
| B3 Textiles, leather | **gap** | nothing | Gutenberg T; Peace Corps (3) |
| B4 Practical chemistry | partial | nothing | Gutenberg T; CD3WD is in |
| B5 Electricity | partial | nothing new | **Done 18 Nov:** *Lessons in Electric Circuits*, 6 volumes (T3-050..055, CC BY). Army power generation manual is in T2-016 but mostly military planning |
| B6 Farming at scale | partial | nothing | **Done 18 Nov:** Peace Corps soils, irrigation, field crops (T2-120..122). Gutenberg S (in); CD3WD is in |
| B7 Engineering, machines | partial | nothing | Army T2-016 (1) |
| U1–U5 Reference, science | good/partial | Encyclopédie de l'environnement, Internet Encyclopedia of Philosophy | Optional |
| T1 School curriculum | partial | Milne open textbooks, OER4Schools | Khan Academy (full) is in |
| T2 Children's reading | **gap** | **Book Dash** (150+ picture books, CC BY 4.0, 11.7 GB); **Vikidia** (children's encyclopedia, 9,400 articles) | - |
| T3 Teaching others | partial | OER4Schools | Hesperian *Helping Health Workers Learn* is in |
| K1 Literature | good | - | - |
| K2 Arts, music | gap (low priority) | Mutopia sheet music, Celtic scores | Optional |

### What this shows

- Kiwix covers **understand**, **health** and **reference** well.
- It has almost nothing curated for **livestock, wild plants, trades, textiles, building, radio and field farming**. Those gaps must be filled from rungs 2–6.
- **Army library (T2-016), indexed 18 Nov 2026** without downloading it: the ZIM's table of contents was read over the network (about 5 MB of an 8 GB file).
  - It holds 5,768 PDFs, about 565 of them doctrine and technical manuals; the rest are forms and directives.
  - Useful for civilians: *Survival*, *Carpentry*, *Concrete and Masonry*, *Waste Management*, *Electric Power Generation*.
  - Missing: plumbing, house wiring, welding and land navigation.
  - Three manuals have been replaced on armypubs since the snapshot.

## 4. Next steps

1. **Owner:** decide D8 (scope) and D9 (quality bar).
2. ~~Index T2-016~~ (done 18 Nov 2026). Next, the manual downloads that sites block for scripts:
   - Navy Seabee *Builder*, *Steelworker*, *Construction Electrician* and *Utilitiesman* (netc.navy.mil). Check each title page's distribution statement: some Seabee manuals are restricted.
   - Air Force *Survival* handbook AFH 10-644 (2017), via irp.fas.org.
   - The newer editions of ATP 4-25.12 (field hygiene) and ATP 4-44 (water support).
3. **Verify the rung-3 publisher sets.** *Done 18 Nov 2026 for the first picks:* Peace Corps (5 manuals; reuse allowed without royalty) and FAO (5 Diversification booklets). Both catalog sites refuse most scripted requests, so finishing these sets needs a person with a browser to list the remaining titles; the PDFs themselves download normally. For each set, record its licence, how to list everything in it, and its size:
   - Peace Corps manuals (official catalog: 66 titles)
   - FAO (open repository)
   - Practical Action technical briefs
4. **Review the new Kiwix candidates:** Book Dash, Vikidia, WikiCiv, Low-tech Magazine, OER4Schools. Each gets a spot check (D9), then a catalog row or a rejected row.
5. ~~**Gutenberg classes for standard:** confirm R, U, G and H.~~ **Dropped 19 Nov 2026 (owner):** their books stay available in the full bundle (all of Gutenberg, T3-036); standard keeps S, T, Q, PZ, PR and PS.
6. **Own packages (rung 4):** shortlist trusted temperate extension-service sites and check their licences before building anything.
7. **Print list:** field guide (F4), ham radio handbook (C1), *Machinery's Handbook* (B1).

Re-run `python scripts/scan_kiwix.py` before each build: Kiwix adds and updates packages every month.

## Not verified

- **Low-tech Magazine:** licence not found.
- **WikiCiv:** who edits it is unknown.
- **Peace Corps manuals:** copyright status unknown (US government work is usually public domain, but check each manual).
- **Army library (T2-016):** contents not listed yet.
- **Not found at all:** a current list of RACHEL's offline modules, and a list of Kolibri's public courses.
