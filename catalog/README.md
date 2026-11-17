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

What was actually checked on 17 Nov 2026:

| Check | Items |
|---|---|
| PDF fetched and its text read | T1-003, T1-004, T1-005, T1-007, T1-009, T1-010 |
| HTML page fetched and read | T1-001, T1-002 |
| Only the landing page was read (subagent); the PDF itself was never retrieved | T1-008 (CDC returns 403 to scripts) |
| Not reached at all (Cloudflare block) | T1-006 (IFRC 2025). Only the 2020 fallback URL was confirmed, by HEAD request. |

**Owner actions before the build:**
1. Review and sign off each `pending-owner` row.
2. Email `permissions@hesperian.org` about keeping *Where There Is No Doctor* on private family drives and using it for teaching. Their copyright page asks for permission for "any digital format".
3. Download the IFRC 2025 guidelines by hand in a browser. The site blocks scripts.

**Known gaps in Tier 1 (still to source):**
- **No standalone item in `01_bleeding-wounds`, `02_breathing-cpr` or `03_burns` yet.** That content sits inside the large manuals in `10_first-aid-manuals`, and ATP 4-02.11 alone is 12.6 MB. The plan is for the front door to link straight to the right page, for example `en_wtnd_2025_10.pdf#page=8` for bleeding. The PDF page numbers are recorded in the T1-003 notes. Check that page links work on Windows during the prototype (step 4).
- **No modern CPR (chest compressions) source.** Hesperian chapter 10 covers mouth-to-mouth only. A **CPR / "gestes qui sauvent" sheet**, ideally in French, is the top Tier 1 gap. Candidates: Croix-Rouge française, Fédération Française de Cardiologie. The ERC/RCUK 2025 guidelines can't be copied without permission.
- A **cold weather / hypothermia** leaflet in French. Santé publique France "grand froid" links found online were stale.
- Standalone **burns** and **choking** one-pagers. These are covered inside the first-aid manuals, but there's no quick sheet yet.
- **Arabic** Tier 1 items, for example Hesperian Arabic editions and WHO EMRO water notes.
- A metric conversion note for the CDC water sheet, which uses US units.
