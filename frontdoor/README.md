# Front door

`START-HERE.html` and `START-HERE.txt` are **generated** by `scripts/frontdoor.py`. `scripts/assemble.py` calls it on every build. Never edit them on a drive by hand. They're built from the items actually placed on that drive, so they never link to a missing file.

What you edit here:

| File | What it holds | Rule |
|---|---|---|
| `situations.csv` | Emergency situations in plain words, each pointing to a Tier 1 item and a PDF page | Check every page against the PDF text and record that in `checked`. List the civilian source first. An unknown item id stops the build. |
| `numbers.csv` | Emergency phone numbers shown at the top of the Emergency section | Re-check at the source before each build: service-public.gouv.fr and centres-antipoison.net. |
| `notes/<order>_<name>.txt` | Checked text shown under a situation, e.g. the metric water doses | Shown on every build, under the first situation with that `order` in `situations.csv`. Cite the sources and the check date inside the note. An order no situation has stops the build. |
| `drafts/<order>_<name>.txt` | Text not checked yet | Same naming. Shown only on test builds (`assemble.py --allow-pending`), in a yellow "DRAFT" box. To publish one, check it and move it to `notes/`. |

Page rules (CLAUDE.md rule 4): one self-contained file, no JavaScript, no web fonts, relative links only. `tests/test_build.py` checks that every link resolves, that nothing external is referenced, and that strict builds contain no draft text.

## Open points (updated 20 Nov 2026)

- **`#page=N` links:** confirmed in Chrome on Windows on 20 Nov 2026. A test drive was served from 127.0.0.1, because the browser tool can't open `file://`. Red Cross `#page=29` and, clicked from the front door, Army `#page=94` (254 pages) both opened on the right page. A big PDF shows page 1 for about a second, then jumps. Still to try: a double-click from a real drive (`file://`), Edge and Firefox, and a Mac (step 4 of NEXT-SESSION).
- **Water note (`notes/06_water-metric.txt`):** checked against CDC, WHO and ARS Guadeloupe (19 Nov 2026), including French bleach (4 drops per litre of 2.6% chlore actif). Moved out of `drafts/` on 20 Nov 2026, so it now shows on every build.
- **Library section:** says the opening program isn't on the drive until the launcher (D1) exists.
- **Not tested:** phone-width layout.
