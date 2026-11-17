# Catalog

Two files drive the build. Both are UTF-8 CSV with LF line endings. To open them in Excel without broken accents, use **Data → From Text/CSV** and pick UTF-8.

## publishers.csv: the quality gate

One row per source organisation.

| status | Meaning |
|---|---|
| `approved-pending-owner` | Proposed as trusted. Waiting for the owner's sign-off. |
| `approved` | Signed off. Its items can go on the drive. |
| `candidate` | Likely source for Tier 2/3. Not reviewed yet. |
| `item-review-required` | Never trusted as a whole. Each item needs its own review. |
| `excluded-licence` | Good content, but the licence blocks copying without permission. |

## catalog.csv: one row per file on the drive

| Column | Filled by | Notes |
|---|---|---|
| `id` | hand | `T1-NNN`, `T2-NNN`, `T3-NNN`. Never reused. |
| `title`, `publisher`, `source_url`, `edition_or_date`, `licence`, `tier`, `folder`, `language`, `format`, `notes` | hand | `publisher` must be an `id` from publishers.csv. `folder` is the path on the drive. |
| `download_date`, `sha256` | download script | Left blank until the file is actually downloaded. |
| `size_bytes` | check / script | Pre-filled only from a real HTTP Content-Length or download, for drive sizing. The script overwrites it. |
| `text_layer` | check / script | `y` only after text was actually extracted from the file. |
| `reviewer` | owner | `pending-owner` until a person has read the item and signed off. |

"To verify" in `licence` or `edition_or_date` means it wasn't confirmed at the source yet. Check it before the full build.

## Tier 1 status (draft, 17 Nov 2026)

14 items. What was actually checked on 17 Nov 2026:

| Check | Items |
|---|---|
| PDF fetched and its text read | T1-003, T1-004, T1-005, T1-007, T1-009, T1-010 |
| PDF fetched, but it has no text layer (scan) | T1-014 (Arabic water note) |
| HTML page fetched and read | T1-001, T1-002, T1-011 |
| Only the landing page was read (subagent); the PDF itself was never retrieved | T1-008 (CDC returns 403 to scripts) |
| Not reached at all: site blocks scripts | T1-006 (IFRC 2025; only the 2020 fallback URL was confirmed, by HEAD request), T1-012 and T1-013 (DGSCGC PSC1/GQS; edition known only from search results) |

**Owner actions before the build:**
1. Review and sign off each `pending-owner` row.
2. Email `permissions@hesperian.org` about keeping *Where There Is No Doctor* on private family drives and using it for teaching. Their copyright page asks for permission for "any digital format".
3. Download these by hand in a browser, because the sites block scripts:
   - **T1-006** IFRC 2025 guidelines
   - **T1-012** PSC1 recommendations, plus the companion "Recueil"
   - **T1-013** GQS recommendations

   All three are on the page given in `source_url`. Afterwards, fill in the real edition, size and licence.

## How the situation folders are covered

| Folder | Standalone item | Page links into the manuals |
|---|---|---|
| `00_call-for-help` | T1-001, T1-002 | — |
| `01_bleeding-wounds` | — | Hesperian ch. 10, PDF p. 8–16; ATP 4-02.11 (tourniquet pages); PSC1 |
| `02_breathing-cpr` | T1-013 GQS (fr) | ATP 4-02.11 PDF p. 94–96 (CPR); Hesperian ch. 10, PDF p. 5–6 (choking, rescue breathing); PSC1 |
| `03_burns` | — | Hesperian ch. 10, PDF p. 22–23; PSC1 |
| `04_poisoning` | T1-002 | Hesperian ch. 10, PDF p. 29 |
| `05_water-purification` | T1-007 (en), T1-008 (en), T1-014 (ar) | — |
| `06_cold-heat` | T1-009, T1-010, T1-011 | Hesperian ch. 10, PDF p. 7 (heat) |
| `10_first-aid-manuals` | T1-003 to T1-006, T1-012 | — |

The front door will link straight to a page, for example `en_wtnd_2025_10.pdf#page=8`. Check that this works on Windows browsers during the prototype (step 4). After downloading PSC1, add its page numbers here.

## Remaining Tier 1 gaps

- **No short CPR sheet in English.** The manuals cover CPR, so this is a nice-to-have. The good candidates aren't freely reusable: ERC/RCUK 2025 needs permission, the Canadian Red Cross guide (2018) is all rights reserved, and Stop the Bleed needs a DoD agreement.
- **Metric water dose.** The CDC sheet uses drops per gallon, and no official metric equivalent was found. Write a short metric note on the front door and have the owner review it.
- **Arabic first aid.** Only the water note exists in Arabic so far, and it's a scan. Hesperian has no Arabic *Where There Is No Doctor* online; its Arabic edition is published by the Arab Resource Collective in Beirut. The IFRC Arabic guidelines may exist on ifrc.org (blocked to scripts). Check during the manual download.

Rejected on 17 Nov 2026: the French Federation of Cardiology pocket card and brochure (no how-to steps), Santé publique France "grand froid" downloads (dead links or a policy note), and third-party mirrors of Hesperian or Stop the Bleed (not official).
