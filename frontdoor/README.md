# Front door

`START-HERE.html` and `START-HERE.txt` are **generated** by `scripts/frontdoor.py`. `scripts/assemble.py` calls it on every build. Never edit them on a drive by hand. They're built from the items actually placed on that drive, so they never link to a missing file.

What you edit here:

| File | What it holds | Rule |
|---|---|---|
| `situations.csv` | Emergency situations in plain words, each pointing to a Tier 1 item and a PDF page | Check every page against the PDF text and record that in `checked`. List the civilian source first. An unknown item id stops the build. |
| `numbers.csv` | Emergency phone numbers shown at the top of the Emergency section | Re-check at the source before each build: service-public.gouv.fr and centres-antipoison.net. |
| `drafts/*.txt` | Text the owner hasn't checked yet | Shown only on test builds (`assemble.py --allow-pending`), in a yellow "DRAFT" box. To publish one, move its text into the generator or a checked file. |

Page rules (CLAUDE.md rule 4): one self-contained file, no JavaScript, no web fonts, relative links only. `tests/test_build.py` checks that every link resolves, that nothing external is referenced, and that strict builds contain no draft text.

## Open points (18 Nov 2026)

- **`#page=N` links:** not yet confirmed in a real browser. Headless Edge can't draw PDFs.
- **Water note (`drafts/water-metric.txt`):** complete and checked against CDC, WHO and ARS Guadeloupe (19 Nov 2026), including French bleach (4 drops per litre of 2.6% chlore actif). Still to do: move it out of `drafts/` so the front door stops showing the "DRAFT, not checked yet" label.
- **Library section:** says the opening program isn't on the drive until the launcher (D1) exists.
- **Not tested:** phone-width layout.
