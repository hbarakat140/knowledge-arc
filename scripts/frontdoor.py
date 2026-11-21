"""Build "1 START-HERE.html" at the drive root and arc/START-HERE.txt from the
items actually placed on the drive. Called by assemble.py on every build.
(Phase 3 layout; the page itself is redesigned in phase 4, NEXT-SESSION.md.)

Inputs, all in frontdoor/:
  situations.csv   emergency situations -> item id + PDF page (hand-checked)
  numbers.csv      French emergency numbers (hand-checked)
  notes/*.txt      checked text shown under a situation on every build
  drafts/*.txt     text not checked yet: shown only on test builds, marked DRAFT
                   A note or draft file is named <order>_<name>.txt and goes under
                   the first situation with that order in situations.csv.

Rules (CLAUDE.md rule 4): one self-contained file, no scripts, no web fonts,
relative links only. Links are made only to files that exist on the drive.
"""

import csv
import html
import re
import sys
import textwrap
from pathlib import Path
from urllib.parse import quote

sys.path.insert(0, str(Path(__file__).resolve().parent))
import catalog_lib as cl  # noqa: E402

FRONTDOOR = cl.REPO / "frontdoor"

HTML_NAME = "1 START-HERE.html"           # at the drive root
TXT_NAME = f"{cl.ARC}/START-HERE.txt"      # plain-text twin, inside arc/

# Daily life headings: one per subject (catalog/subjects.csv, in its order),
# plus a heading for a subfolder of a subject's guides, shown after it.
SUBFOLDER_HEADINGS = {
    "learning-to-read": "Teaching children to read",
}

# One line under a Daily life heading, in both the HTML and the text page.
LIVING_INTROS = {
    "learning-to-read": (
        "For a parent teaching a child of about 4 to 7. Read the guide first: Phase One is games "
        "for listening, and letters start at Phase Two (page 47 of the PDF). Books 1 to 12 are for "
        "the child to read aloud, in order; every word in them can be sounded out once its letters "
        "are taught. Start book 1 after the guide's Phase Three sets 6 and 7. Book 2 goes with the "
        "Phase Three letter pairs (sh, ch, th, ng), books 3 and 4 with Phase Four, and book 5 "
        "onwards with Phase Five. If a word stumps the child, just tell them the word."),
}

# (system, launcher at the drive root, what to do, server paths it needs).
# The server folders match KIWIX_UNPACK in assemble.py.
LAUNCHERS = [
    ("Windows", "2 Open full library (Windows).bat", "double-click",
     ("arc/software/windows/kiwix/kiwix-serve.exe",)),
    ("Mac", "2 Open full library (Mac).command", "double-click",
     ("arc/software/mac/kiwix-arm64/kiwix-serve", "arc/software/mac/kiwix-x86_64/kiwix-serve")),
    ("Linux", "arc/open-full-library.sh", "in a terminal, run sh",
     ("arc/software/linux/kiwix/kiwix-serve",)),
]

BOOK_PART_ORDER =["fm", "toc", "int", "info", "#", "gp", "resc", "gloss", "indx", "bm"]
BOOK_PART_LABELS = {"fm": "Front pages", "toc": "Contents", "int": "Introduction",
                    "info": "Information", "gp": "Green Pages (medicines)",
                    "resc": "Resources", "gloss": "Glossary (words explained)",
                    "indx": "Index", "bm": "Back pages"}


def read(path):
    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def load_situations(all_ids, folder=FRONTDOOR):
    rows = read(folder / "situations.csv")
    # A blank item_id is a note-only situation: its checked note is the content.
    unknown = sorted({r["item_id"] for r in rows if r["item_id"]} - set(all_ids))
    if unknown:
        raise SystemExit(f"frontdoor/situations.csv refers to unknown catalog ids: {', '.join(unknown)}")
    return rows


def load_notes(folder, orders):
    """{order: [text, ...]} from <order>_<name>.txt files. An order that no
    situation has stops the build, so a note is never silently dropped."""
    notes = {}
    for p in sorted(folder.glob("*.txt")) if folder.is_dir() else []:
        order = p.stem.split("_", 1)[0]
        if order not in orders:
            raise SystemExit(f"frontdoor/{folder.name}/{p.name}: no situation has order '{order}'")
        notes.setdefault(order, []).append(p.read_text(encoding="utf-8").strip())
    return notes


def book_parts(files):
    """Sort and label the chapter files of a multi-file book."""
    def key(name):
        suffix = Path(name).stem.rsplit("_", 1)[-1]
        if suffix.isdigit():
            return (BOOK_PART_ORDER.index("#"), int(suffix))
        pos = BOOK_PART_ORDER.index(suffix) if suffix in BOOK_PART_ORDER else len(BOOK_PART_ORDER)
        return (pos, 0)

    out = []
    for name in sorted(files, key=key):
        suffix = Path(name).stem.rsplit("_", 1)[-1]
        label = f"Chapter {int(suffix)}" if suffix.isdigit() else BOOK_PART_LABELS.get(suffix, suffix)
        out.append((name, label))
    return out


def living_section(rel):
    """The Daily life heading a file goes under, or None: the subject folder
    of arc/guides/<subject>/, or its subfolder if the file is in one."""
    parts = rel.split("/")
    if parts[:2] == [cl.ARC, "guides"] and len(parts) > 3:
        return parts[3] if len(parts) > 4 else parts[2]
    return None


def href(rel, page=None):
    return quote(rel) + (f"#page={page}" if page else "")


def esc(text):
    return html.escape(text, quote=True)


def plain_path(rel):
    return " > ".join(rel.split("/"))


class Page:
    """Collects what goes on the front door, then renders HTML and text."""

    def __init__(self, drive, placed, all_ids, include_drafts, version_line, folder=FRONTDOOR):
        self.drive = drive
        self.placed = placed
        self.by_id = {r["id"]: r for r in placed}
        self.include_drafts = include_drafts
        self.version_line = version_line
        self.situations = load_situations(all_ids, folder)
        self.numbers = read(folder / "numbers.csv")
        orders = {s["order"] for s in self.situations}
        self.notes = load_notes(folder / "notes", orders)
        drafts = load_notes(folder / "drafts", orders)
        self.drafts = drafts if include_drafts else {}
        self.linked = []   # every relative path the page links to
        subjects = cl.read_csv(cl.SUBJECTS)[1]
        self.section_order = [s["id"] for s in subjects]
        self.headings = {s["id"]: s["label"] for s in subjects}
        self.headings.update(SUBFOLDER_HEADINGS)
        self.subfolder_parent = {}   # subfolder -> its subject, filled by living()

    def exists(self, rel):
        return (self.drive / rel).is_file()

    def link(self, rel):
        self.linked.append(rel)
        return rel

    # ---- content model ------------------------------------------------

    def emergency(self):
        groups = []   # (situation, [(rel, page, label)], notes, drafts)
        noted = set()
        for s in self.situations:
            row = self.by_id.get(s["item_id"])
            entry = None
            if row and not cl.is_multi_file(row) and self.exists(row["folder"]):
                entry = (self.link(row["folder"]), s["pdf_page"] or None, s["label"])
            if not groups or groups[-1][0] != s["situation"]:
                first = s["order"] not in noted
                noted.add(s["order"])
                groups.append((s["situation"], [],
                               self.notes.get(s["order"], []) if first else [],
                               self.drafts.get(s["order"], []) if first else []))
            if entry:
                groups[-1][1].append(entry)
        return groups

    def manuals(self):
        """Complete first-aid manuals: the Tier 1 items whose home topic is
        first aid (S1); the other Tier 1 items are single situation sheets."""
        return [(self.link(r["folder"]), r["title"]) for r in self.placed
                if r["tier"] == "1" and cl.topics(r)[:1] == ["S1"] and self.exists(r["folder"])]

    def living(self):
        sections = {}
        for r in self.placed:
            sub = living_section(r["folder"])
            # Tier 1 items are already in the Emergency section.
            if sub is None or r["format"] == "zim" or r["tier"] == "1":
                continue
            parts = r["folder"].split("/")
            if sub != parts[2]:
                self.subfolder_parent[sub] = parts[2]
            if cl.is_multi_file(r):
                folder = self.drive / r["folder"]
                files = [p.name for p in folder.glob("*.pdf")] if folder.is_dir() else []
                parts = [(self.link(f"{r['folder']}/{name}"), label) for name, label in book_parts(files)]
                if parts:
                    sections.setdefault(sub, []).append(("book", r["title"], parts))
            elif self.exists(r["folder"]):
                sections.setdefault(sub, []).append(("file", r["title"], self.link(r["folder"])))
        def key(kv):
            sub = kv[0]
            parent = self.subfolder_parent.get(sub, sub)
            pos = self.section_order.index(parent) if parent in self.section_order else 99
            return (pos, sub != parent, sub)
        return sorted(sections.items(), key=key)

    def library(self):
        zims = [r for r in self.placed if r["format"] == "zim" and self.exists(r["folder"])]
        groups = [("Health and practical life", [r["title"] for r in zims if r["tier"] == "2"]),
                  ("Encyclopedias, books, courses and maps", [r["title"] for r in zims if r["tier"] == "3"])]
        # A system is offered only if both its launcher and its server are here.
        launchers = [(system, name, how) for system, name, how, servers in LAUNCHERS
                     if self.exists(name) and any(self.exists(s) for s in servers)]
        return launchers, [(g, titles) for g, titles in groups if titles]

    def android(self):
        """(app file, folders holding the collections), or None if the
        Android app or the collections are not on the drive."""
        apps = [r["folder"] for r in self.placed if r["format"] == "apk" and self.exists(r["folder"])]
        zim_dirs = sorted({r["folder"].rsplit("/", 1)[0] for r in self.placed
                           if r["format"] == "zim" and self.exists(r["folder"])})
        return (apps[0], zim_dirs) if apps and zim_dirs else None

    # ---- rendering ----------------------------------------------------

    def render_html(self):
        emergency, manuals = self.emergency(), self.manuals()
        living, (launchers, library) = self.living(), self.library()
        o = []
        w = o.append
        w('<!DOCTYPE html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
          '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
          '<title>Start here: Family Library</title>\n<style>\n' + CSS + '</style>\n</head>\n<body>\n')
        w('<header id="top"><h1>Family Library</h1>'
          '<p>Everything here works without internet. Click a big button to begin.</p></header>\n')
        if self.include_drafts:
            w('<p class="testbuild">TEST BUILD: some items and notes here have not been checked yet.</p>\n')
        w('<nav class="doors">'
          '<a class="door red" href="#emergency"><b>Emergency</b><span>Bleeding, breathing, burns, unsafe water…</span></a>'
          '<a class="door" href="#daily"><b>Daily life</b><span>Health, water, food, repairs, teaching children</span></a>'
          '<a class="door" href="#library"><b>Encyclopedia &amp; books</b><span>Wikipedia, medical encyclopedia, maps, books</span></a>'
          '<a class="door grey" href="#help"><b>How to use this drive</b><span>Checking it, copies, what is where</span></a>'
          '</nav>\n')

        # Emergency
        w('<section id="emergency"><h2>Emergency</h2>\n<div class="numbers"><h3>Call for help first, if a phone works</h3><table>\n')
        for n in self.numbers:
            w(f'<tr><td class="num">{esc(n["number"])}</td><td>{esc(n["what"])}</td></tr>\n')
        w('</table><p class="small">Numbers for France, checked 18 Nov 2026. 112 works in every EU country.</p></div>\n')
        w('<p>Find the situation, then click a guide. Each link opens the right page of the PDF.</p>\n<ul class="situations">\n')
        for situation, entries, notes, drafts in emergency:
            w(f'<li><h3>{esc(situation)}</h3>')
            if entries:
                w('<ul>')
                for rel, page, label in entries:
                    w(f'<li><a href="{href(rel, page)}">{esc(label)}</a>'
                      + (f' <span class="small">(page {esc(page)} of the PDF)</span>' if page and page != "1" else '') + '</li>')
                w('</ul>')
            elif not notes:
                w('<p class="small">No guide for this on this drive. Call 15 or 112, and look in the complete manuals below.</p>')
            for note in notes:
                w(f'<div class="note"><pre>{esc(note)}</pre></div>')
            for draft in drafts:
                w(f'<div class="draft"><b>DRAFT, not checked yet:</b><pre>{esc(draft)}</pre></div>')
            w('</li>\n')
        w('</ul>\n')
        if manuals:
            w('<h3>Complete first-aid manuals</h3><ul>')
            for rel, title in manuals:
                w(f'<li><a href="{href(rel)}">{esc(title)}</a></li>')
            w('</ul>\n')
        w('<p class="top"><a href="#top">Back to the top</a></p></section>\n')

        # Daily life
        w('<section id="daily"><h2>Daily life</h2>\n<p>Guides for keeping a household healthy, fed and working over months. '
          'They open in the browser. Big books are split into chapters: click a title to see them.</p>\n')
        for sub, items in living:
            w(f'<h3>{esc(self.headings.get(sub, sub.replace("-", " ").capitalize()))}</h3>')
            if sub in LIVING_INTROS:
                w(f'<p>{esc(LIVING_INTROS[sub])}</p>')
            w('<ul>')
            for item in items:
                if item[0] == "file":
                    w(f'<li><a href="{href(item[2])}">{esc(item[1])}</a></li>')
                else:
                    w(f'<li><details><summary>{esc(item[1])} <span class="small">({len(item[2])} parts)</span></summary><ul>')
                    for rel, label in item[2]:
                        w(f'<li><a href="{href(rel)}">{esc(label)}</a></li>')
                    w('</ul></details></li>')
            w('</ul>\n')
        w('<p>Much more practical knowledge (repairs, appropriate technology, medicine) is in the library: see the next section.</p>\n')
        w('<p class="top"><a href="#top">Back to the top</a></p></section>\n')

        # Library
        w('<section id="library"><h2>Encyclopedia &amp; books</h2>\n')
        if launchers:
            w('<p>The whole library opens in your web browser, with a search box at the top.</p>\n<ul>')
            for system, name, how in launchers:
                w(f'<li><b>{esc(system)}:</b> {esc(how)} <code>{esc(name)}</code> on this drive.</li>')
            w('</ul>\n')
            if launchers[0][0] == "Windows":
                w(LAUNCHER_PICTURE.replace("{name}", "2 Open full library (Windows)"))
            w('<p>A small window opens next to the browser. <b>Keep it open while you read</b>; '
              'close it when you have finished.</p>\n'
              '<p class="small">The first time, the computer may ask whether to run it: choose Run or Open. '
              'If the browser does not open by itself, type <code>127.0.0.1:8642</code> in its address bar.</p>\n')
        else:
            w('<p class="draft">The program that opens the library is not on this drive yet. '
              'Until it is, these collections need the Kiwix reader (see <code>arc/software</code>).</p>\n')
        android = self.android()
        if android:
            app, dirs = android
            folder, name = app.rsplit("/", 1)
            w(f'<p><b>Android phone or tablet:</b> open this drive in the phone\'s Files app, go to the folder '
              f'<code>{esc(folder)}</code> and tap <code>{esc(name)}</code> to install the Kiwix app. '
              'If the phone asks, allow installing apps from this source. '
              'Then open Kiwix and add the library\'s files (their names end in <code>.zim</code>) from the folders '
              + ", ".join(f'<code>{esc(d)}</code>' for d in dirs) + ' on this drive.</p>\n')
        for group, titles in library:
            w(f'<h3>{esc(group)}</h3><ul class="cols">' + "".join(f'<li>{esc(t)}</li>' for t in titles) + '</ul>\n')
        w('<p class="top"><a href="#top">Back to the top</a></p></section>\n')

        # Help
        w('<section id="help"><h2>How to use this drive</h2>\n<ol>'
          '<li><b>Any computer, nothing installed:</b> this page and every guide linked from it open in the web browser.</li>'
          '<li><b>The full library</b> (encyclopedias, books, maps) needs one double-click on <code>2 Open full library</code>: see above.</li>'
          '<li><b>If this page does not open</b>, open the folder <code>arc</code>, then <code>START-HERE.txt</code>: it lists the same guides with their folders.</li>'
          '<li><b>Check the drive is not damaged</b> every 6 to 12 months: open the folders <code>arc</code> then <code>system</code> and double-click <code>verify.bat</code> '
          '(Windows). On a Mac or Linux, run <code>sh verify.sh</code> in a terminal. If it reports a damaged file, copy that file from another copy of the drive.</li>'
          '<li><b>There are several identical copies</b> of this drive, kept in different places. Keep them apart.</li>'
          '</ol>\n')
        if self.exists("arc/system/MAINTENANCE.txt"):
            w(f'<p><b>Looking after the drives</b> (checking, repairing, making a new copy): '
              f'<a href="{href(self.link("arc/system/MAINTENANCE.txt"))}">the maintenance guide</a>.</p>\n')
        w('<p>What is on this drive and where it came from: '
          f'<a href="{href("arc/system/CATALOG.csv")}">the catalog</a> · '
          f'<a href="{href("arc/system/VERSION.txt")}">which version this copy is</a>.</p>\n')
        w(f'<p class="small">{esc(self.version_line)}</p>\n')
        w('<p class="top"><a href="#top">Back to the top</a></p></section>\n</body>\n</html>\n')
        return "".join(o)

    def render_text(self):
        o = []
        w = o.append
        w("FAMILY LIBRARY: START HERE")
        w("Everything on this drive works without internet.")
        w('Best: open "1 START-HERE" (at the top of the drive) in a web browser. This text file lists the same guides.')
        if self.include_drafts:
            w("TEST BUILD: some items and notes here have not been checked yet.")
        w("")
        w("== EMERGENCY: CALL FOR HELP FIRST, IF A PHONE WORKS ==")
        for n in self.numbers:
            w(f"  {n['number']:<15} {n['what']}")
        w("  (France, checked 18 Nov 2026. 112 works in every EU country.)")
        w("")
        w("== EMERGENCY GUIDES (folder > file, then the page to go to) ==")
        for situation, entries, notes, drafts in self.emergency():
            w(f"* {situation}")
            if not entries and not notes:
                w("    No guide for this on this drive. Call 15 or 112; see the complete manuals.")
            for rel, page, label in entries:
                w(f"    - {label}")
                w(f"      {plain_path(rel)}" + (f", page {page}" if page and page != "1" else ""))
            for note in notes:
                w("")
                for line in note.splitlines():
                    w(("    " + line).rstrip())
                w("")
            for draft in drafts:
                w("    DRAFT, not checked yet:")
                for line in draft.splitlines():
                    w("      " + line)
        w("")
        w("Complete first-aid manuals:")
        for rel, title in self.manuals():
            w(f"  - {title}\n    {plain_path(rel)}")
        w("")
        w("== DAILY LIFE ==")
        for sub, items in self.living():
            w(f"{self.headings.get(sub, sub)}:")
            if sub in LIVING_INTROS:
                w(textwrap.fill(LIVING_INTROS[sub], width=78, initial_indent="  ", subsequent_indent="  "))
            for item in items:
                if item[0] == "file":
                    w(f"  - {item[1]}\n    {plain_path(item[2])}")
                else:
                    folder = item[2][0][0].rsplit("/", 1)[0]
                    w(f"  - {item[1]} ({len(item[2])} parts)\n    {plain_path(folder)}")
        w("")
        w("== ENCYCLOPEDIA & BOOKS ==")
        launchers, library = self.library()
        if launchers:
            w("The whole library opens in your web browser:")
            for system, name, how in launchers:
                w(f"  {system}: {how} {name} on this drive.")
            w("Keep the small window that opens next to it open while you read.")
            w("If the browser does not open by itself, type 127.0.0.1:8642 in its address bar.")
        else:
            w("The program that opens the library is not on this drive yet (see arc > software).")
        android = self.android()
        if android:
            app, dirs = android
            w("Android phone or tablet: in the Files app, open this drive and tap")
            w(f"  {plain_path(app)}")
            w("to install the Kiwix app (if the phone asks, allow installing apps from this source).")
            w("Then open Kiwix and add the library's files (names ending in .zim) from these folders:")
            for d in dirs:
                w(f"  {plain_path(d)}")
        for group, titles in library:
            w(f"{group}: " + ", ".join(titles))
        w("")
        w("== CHECKING THE DRIVE ==")
        w("Every 6 to 12 months: open arc > system and double-click verify.bat (Windows),")
        w("or run 'sh verify.sh' in a terminal (Mac, Linux). Replace damaged files from another copy.")
        if self.exists("arc/system/MAINTENANCE.txt"):
            w("Looking after the drives (checking, repairing, making a new copy): arc > system > MAINTENANCE.txt")
        w("")
        w(self.version_line)
        return "\r\n".join(o).replace("\n", "\r\n").replace("\r\r\n", "\r\n") + "\r\n"


LAUNCHER_PICTURE = """<svg class="pic" viewBox="0 0 480 120" role="img" aria-label="A file named {name}: double-click it">
<rect x="1" y="1" width="478" height="118" rx="10" fill="#f4f4f4" stroke="#999"/>
<path d="M40 22h40l14 14v56H40z" fill="#fff" stroke="#333" stroke-width="2"/>
<path d="M80 22v14h14" fill="none" stroke="#333" stroke-width="2"/>
<rect x="47" y="52" width="40" height="22" rx="3" fill="#1a5fb4"/>
<text x="67" y="67" font-size="11" text-anchor="middle" fill="#fff" font-family="sans-serif">RUN</text>
<text x="112" y="58" font-size="18" font-family="sans-serif" fill="#111" font-weight="bold">{name}</text>
<text x="112" y="84" font-size="15" font-family="sans-serif" fill="#333">Double-click this file</text>
</svg>
"""

CSS = """
:root { --red:#b00020; --blue:#1a5fb4; --ink:#111; --soft:#555; --line:#ccc; --bg:#fff; --panel:#f4f4f4; }
* { box-sizing: border-box; }
body { margin: 0 auto; max-width: 60em; padding: 1em; font: 19px/1.5 system-ui, -apple-system, "Segoe UI", Roboto, Arial, sans-serif; color: var(--ink); background: var(--bg); }
h1 { font-size: 2em; margin: .2em 0; }
h2 { font-size: 1.6em; border-bottom: 3px solid var(--ink); padding-bottom: .2em; margin-top: 2em; }
h3 { margin: 1em 0 .3em; }
a { color: var(--blue); }
code { background: var(--panel); padding: 0 .3em; border-radius: 3px; }
.doors { display: flex; flex-wrap: wrap; gap: .8em; margin: 1em 0; }
.door { flex: 1 1 13em; display: block; padding: 1em; border-radius: 12px; background: var(--blue); color: #fff; text-decoration: none; min-height: 6em; }
.door b { display: block; font-size: 1.35em; }
.door span { display: block; opacity: .9; font-size: .9em; }
.door.red { background: var(--red); }
.door.grey { background: #444; }
.door:focus, .door:hover { outline: 4px solid #f5c211; }
.numbers { border: 3px solid var(--red); border-radius: 10px; padding: .5em 1em; }
.numbers table { border-collapse: collapse; }
.numbers td { padding: .25em .8em .25em 0; vertical-align: top; }
.num { font-size: 1.4em; font-weight: bold; white-space: nowrap; color: var(--red); }
.situations { list-style: none; padding: 0; }
.situations > li { border-left: 6px solid var(--red); padding: .1em 0 .5em 1em; margin: 1em 0; }
.small { font-size: .85em; color: var(--soft); }
.draft, .testbuild { background: #fff3cd; border: 2px dashed #b58900; padding: .5em 1em; border-radius: 8px; }
.note { background: var(--panel); border-left: 6px solid var(--blue); padding: .5em 1em; border-radius: 8px; margin: .5em 0; }
.note pre, .draft pre { white-space: pre-wrap; font: inherit; font-size: .9em; margin: 0; }
details summary { cursor: pointer; color: var(--blue); text-decoration: underline; }
.cols { columns: 2 16em; }
.top { font-size: .85em; }
.pic { max-width: 100%; height: auto; display: block; margin: .5em 0; }
@media print { .doors, .top { display: none; } body { font-size: 12pt; } a { color: var(--ink); } }
"""


def build(drive, placed, all_ids, include_drafts=False, version_line="", folder=FRONTDOOR):
    """Write HTML_NAME and TXT_NAME; return the relative paths the HTML links
    to (for tests)."""
    page = Page(Path(drive), placed, all_ids, include_drafts, version_line, Path(folder))
    html_text = page.render_html()
    (Path(drive) / HTML_NAME).write_text(html_text, encoding="utf-8", newline="")
    (Path(drive) / TXT_NAME).parent.mkdir(parents=True, exist_ok=True)
    with open(Path(drive) / TXT_NAME, "w", encoding="utf-8-sig", newline="") as f:
        f.write(page.render_text())
    return sorted(set(page.linked))


def links_in(html_text):
    """Every href in the page, without #fragments, URL-decoded."""
    from urllib.parse import unquote
    return [unquote(h.split("#", 1)[0]) for h in re.findall(r'href="([^"]+)"', html_text)
            if not h.startswith("#")]
