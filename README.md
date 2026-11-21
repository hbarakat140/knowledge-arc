# Knowledge Arc

Build recipe for an offline knowledge arc: **an offline website on a drive** that carries trusted practical knowledge, reference, education and culture across a time without internet. Anyone who has a copy can use it, learn from it and pass it on, with nothing installed and nobody there to explain it.

This repository contains the **recipe**, not the content: the catalog of sources, the scripts that download, check and assemble them, the website generator and the launchers. The arc itself (ZIM collections, PDFs, videos, software) is written to drives and is never committed here.

## How someone uses a copy

1. **Open `1 START-HERE`** at the top of the drive. It opens in any browser with nothing installed: subjects, topics and the start-here guides.
2. **One double-click on "2 Open full library"** for that computer starts the library engine from the drive. START-HERE then becomes the full website: the same subjects plus the big collections (Wikipedia, medicine, repair guides, books, courses, maps, videos) and one search over the collections that have a search index (the others are marked "open to browse").
3. **On an Android phone**, install the Kiwix app from the drive to open the collections; the guides open from the Files app.

Everything is organised by **subject** (health, food and farming, making and repairing, science, history, stories, arts...) and by **shelf** (guides, books, encyclopedias, courses, videos, films, music, maps), with doors for children, search and an A-Z of topics. See `docs/architecture.md`.

## Repository layout

| Path | Contents |
|---|---|
| `CLAUDE.md` | Project context, decisions and working rules |
| `NEXT-SESSION.md` | Where things stand and the phase plan |
| `docs/architecture.md` | What the arc is, the user journey, drive layout, navigation, editions, decisions |
| `catalog/` | Approved publishers, the item catalog and the topics (coverage) that drive the build |
| `scripts/` | Download, assemble, website, verify and mirror scripts |
| `frontdoor/` | Inputs for the website: emergency numbers, notes, checked page lists |
| `launchers/` | Open the full library on Windows, Mac and Linux |

## Principles

- Trusted sources only; every item is recorded in the catalog with its origin.
- Open formats (ZIM, PDF, HTML, MP4) readable for decades on any system.
- Written for a stranger: one obvious entry, plain words, nothing to install.
- Start-here guides never depend on a program.
- Several identical, verified copies in different places, made to be passed on.

## Status

21 Nov 2026: vision reset agreed (offline learning website for anyone, replacing the family crisis-kit design). The catalog holds 150 checked items (13 of them programs) in four editions (pocket ~26 GB, core ~150 GB, standard ~285 GB, full ~660 GB). The scripts build the new drive layout (phase 3); the website itself is rebuilt in phase 4 (`NEXT-SESSION.md`).
