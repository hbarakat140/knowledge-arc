# Offline Family Library

Build recipe for a curated offline knowledge library stored on external drives: emergency help, practical knowledge for daily life, and general reference and education, usable on any computer without internet.

This repository contains the **recipe**, not the content: the catalog of sources, the scripts that download and verify them, the START HERE page and the launchers. The library itself (ZIM files, PDFs, videos, software) is written to the drives and is never committed here.

## How the drive works

1. **Browser only:** open `START-HERE.html` on the drive. Emergency guides and core manuals open with nothing installed.
2. **One double-click:** run `OPEN-LIBRARY` for your system to search the whole library (encyclopedias, medical references, repair guides, books, maps, videos) in your browser.
3. **Installed:** install a reader from `90_SOFTWARE/` for longer use, and optionally a local AI later.

## Repository layout

| Path | Contents |
|---|---|
| `CLAUDE.md` | Project context, decisions and working rules |
| `docs/architecture.md` | Drive structure, formats, quality gate, copies, open decisions |
| `catalog/` | Approved publishers and the item catalog that drives the build |
| `scripts/` | Download, verify, manifest and mirror scripts |
| `frontdoor/` | The self-contained START HERE page |
| `launchers/` | One-click launchers for Windows, Mac and Linux |

## Principles

- Trusted sources only; every item is recorded in the catalog with its origin.
- Open formats (ZIM, PDF, HTML, MP4) readable for years on any system.
- Emergency content never depends on an app.
- Several identical, verified copies in different places.

## Status

Architecture defined (v0.2). Publisher list and Tier 1 catalog drafted (17 Nov 2026), awaiting owner review; see `catalog/README.md` for open actions and gaps. Next: fill Tier 1 gaps, then Tier 2 and 3 catalogs, then size the drives.
