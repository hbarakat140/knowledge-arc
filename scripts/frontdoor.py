"""Build the arc's website from the items actually placed on the drive:
"1 START-HERE.html" at the drive root, the other pages in arc/site/, and the
plain-text twin arc/START-HERE.txt. Called by assemble.py on every build.

Navigation (docs/architecture.md section 4): subjects -> topics -> items, with
format shelves as a separate menu, and doors for children, A-Z and search.
Inputs: the catalog's tags (topic, shelf, audience, job, label),
catalog/subjects.csv, catalog/coverage.csv (topics and their search words), and
in frontdoor/:
  situations.csv   "where to look first": situation -> topic, item, PDF page
  numbers.csv      French emergency numbers (hand-checked)
  notes/*.txt      checked text shown under a situation on every build
  drafts/*.txt     text not checked yet: shown only on test builds, marked DRAFT
                   A note or draft file is named <order>_<name>.txt and goes under
                   the first situation with that order in situations.csv.

Rules (CLAUDE.md rule 4): self-contained pages (inline CSS, no scripts, no web
fonts), relative links to files that exist on the drive. The only absolute
address is the library on this computer (LIBRARY), for links that need the
full library running; they say so.
"""

import csv
import html
import posixpath
import re
import shutil
import sys
import textwrap
from pathlib import Path
from urllib.parse import quote

sys.path.insert(0, str(Path(__file__).resolve().parent))
import catalog_lib as cl  # noqa: E402

FRONTDOOR = cl.REPO / "frontdoor"
HTML_NAME = "1 START-HERE.html"           # at the drive root
TXT_NAME = f"{cl.ARC}/START-HERE.txt"      # plain-text twin, inside arc/
SITE = f"{cl.ARC}/site"                    # every other page
LIBRARY = "http://127.0.0.1:8642"          # the full library, once it runs

JOB_ORDER = ["primary", "depth", "cross-check", "gap-filler", "copy"]
SHELF_ORDER = [s for s in cl.SHELVES if s != "software"]

# A short paragraph at the top of a topic page.
TOPIC_INTROS = {
    "T2": (
        "For a parent teaching a child of about 4 to 7. Read the guide first: Phase One is games "
        "for listening, and letters start at Phase Two (page 47 of the PDF). Books 1 to 12 are for "
        "the child to read aloud, in order; every word in them can be sounded out once its letters "
        "are taught. Start book 1 after the guide's Phase Three sets 6 and 7. Book 2 goes with the "
        "Phase Three letter pairs (sh, ch, th, ng), books 3 and 4 with Phase Four, and book 5 "
        "onwards with Phase Five. If a word stumps the child, just tell them the word."),
}

# (system, launcher on the drive, what to do, server paths it needs).
# The server folders match KIWIX_UNPACK in assemble.py.
LAUNCHERS = [
    ("Windows", "2 Open full library (Windows).bat", "double-click",
     ("arc/software/windows/kiwix/kiwix-serve.exe",)),
    ("Mac", "2 Open full library (Mac).command", "double-click",
     ("arc/software/mac/kiwix-arm64/kiwix-serve", "arc/software/mac/kiwix-x86_64/kiwix-serve")),
    ("Linux", "arc/open-full-library.sh", "in a terminal, run sh",
     ("arc/software/linux/kiwix/kiwix-serve",)),
]

BOOK_PART_ORDER = ["fm", "toc", "int", "info", "#", "gp", "resc", "gloss", "indx", "bm"]
BOOK_PART_LABELS = {"fm": "Front pages", "toc": "Contents", "int": "Introduction",
                    "info": "Information", "gp": "Green Pages (medicines)",
                    "resc": "Resources", "gloss": "Glossary (words explained)",
                    "indx": "Index", "bm": "Back pages"}


def read(path):
    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def load_situations(all_ids, folder=FRONTDOOR, topics=None):
    rows = read(folder / "situations.csv")
    # A blank item_id is a note-only situation: its checked note is the content.
    unknown = sorted({r["item_id"] for r in rows if r["item_id"]} - set(all_ids))
    if unknown:
        raise SystemExit(f"frontdoor/situations.csv refers to unknown catalog ids: {', '.join(unknown)}")
    if topics is not None:
        bad = sorted({r["topic"] for r in rows} - set(topics))
        if bad:
            raise SystemExit(f"frontdoor/situations.csv refers to unknown topics: {', '.join(bad)}")
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


def esc(text):
    return html.escape(text, quote=True)


def plain_path(rel):
    return " > ".join(rel.split("/"))


def display(row):
    """The item's name as shown to people: its label, else its title."""
    return row.get("label") or row["title"]


def year(row):
    m = re.search(r"\b(19|20)\d\d\b", row.get("edition_or_date", ""))
    return m.group(0) if m else ""


def library_book(row):
    """The ZIM's name in the library server's addresses (its file name)."""
    return Path(row["folder"]).stem


class Site:
    """Everything on the drive's website, rendered as several pages."""

    def __init__(self, drive, placed, all_ids, include_drafts, version_line, folder=FRONTDOOR,
                 publishers=None):
        self.drive = Path(drive)
        self.include_drafts = include_drafts
        self.version_line = version_line
        self.publishers = publishers or {}
        self.subjects = read(cl.SUBJECTS)
        self.topics = {c["id"]: c for c in read(cl.COVERAGE)}
        self.situations = load_situations(all_ids, folder, self.topics)
        self.numbers = read(folder / "numbers.csv")
        orders = {s["order"] for s in self.situations}
        self.notes = load_notes(folder / "notes", orders)
        drafts = load_notes(folder / "drafts", orders)
        self.drafts = drafts if include_drafts else {}
        self.by_id = {r["id"]: r for r in placed}
        # Items people can open: not software, and present on the drive.
        self.items = [r for r in placed if r.get("shelf") != "software" and self.present(r)]
        self.software = [r for r in placed if r.get("shelf") == "software" and self.exists(r["folder"])]
        self.linked = set()   # drive paths the pages link to
        self.pages = {}       # drive path -> html

    # ---- facts -----------------------------------------------------------

    def exists(self, rel):
        return (self.drive / rel).is_file()

    def present(self, r):
        if cl.is_multi_file(r):
            folder = self.drive / r["folder"]
            return folder.is_dir() and any(folder.glob("*.pdf"))
        return self.exists(r["folder"])

    def home_items(self, topic):
        rows = [r for r in self.items if cl.topics(r)[:1] == [topic]]
        return sorted(rows, key=lambda r: (JOB_ORDER.index(r["job"]) if r["job"] in JOB_ORDER else 9,
                                           self.items.index(r)))

    def also_items(self, topic):
        return [r for r in self.items if topic in cl.topics(r)[1:]]

    def topic_items(self, topic):
        return self.home_items(topic) + self.also_items(topic)

    def subject_topics(self, subject):
        return [c for c in self.topics.values() if c["subject"] == subject]

    def subject_count(self, subject):
        ids = set()
        for c in self.subject_topics(subject):
            ids.update(r["id"] for r in self.topic_items(c["id"]))
        return len(ids)

    def launchers(self):
        return [(system, name, how) for system, name, how, servers in LAUNCHERS
                if self.exists(name) and any(self.exists(s) for s in servers)]

    def android_app(self):
        apps = [r["folder"] for r in self.software if r["format"] == "apk"]
        return apps[0] if apps else None

    def collections(self):
        return [r for r in self.items if r["format"] == "zim"]

    # ---- links -----------------------------------------------------------

    def href(self, page, target, fragment=""):
        """Relative link from page (a drive path) to target (a drive path)."""
        self.linked.add(target)
        rel = posixpath.relpath(target, posixpath.dirname(page) or ".")
        return quote(rel) + fragment

    @staticmethod
    def page_path(kind, key=""):
        if kind == "home":
            return HTML_NAME
        return f"{SITE}/{kind}{'-' + key if key else ''}.html"

    def page_link(self, page, kind, key=""):
        return self.href(page, self.page_path(kind, key))

    # ---- pieces ----------------------------------------------------------

    def meta(self, r):
        bits = []
        pub = self.publishers.get(r["publisher"], {}).get("name") or ""
        if pub:
            bits.append(pub.split(" (")[0])
        if year(r):
            bits.append(year(r))
        if r["format"] == "zim":
            bits.append("collection: opens in the full library")
        elif cl.is_multi_file(r):
            bits.append("book in chapters")
        else:
            bits.append("PDF")
        return " · ".join(esc(b) for b in bits)

    def tags(self, r, topic=None):
        out = []
        if topic and r["job"] == "primary" and cl.topics(r)[:1] == [topic]:
            out.append('<span class="tag start">Start here</span>')
        if r.get("audience") == "children":
            out.append('<span class="tag kids">For children</span>')
        if r.get("audience") == "advanced":
            out.append('<span class="tag adv">Advanced</span>')
        if r.get("shelf") == "community":
            out.append('<span class="tag comm">Community answers: not checked by experts</span>')
        return " ".join(out)

    def item_html(self, page, r, topic=None):
        tags = self.tags(r, topic)
        tags = f" {tags}" if tags else ""
        meta = f'<span class="meta">{self.meta(r)}</span>'
        if cl.is_multi_file(r):
            folder = self.drive / r["folder"]
            parts = book_parts([p.name for p in folder.glob("*.pdf")])
            links = "".join(f'<li><a href="{self.href(page, r["folder"] + "/" + name)}">{esc(label)}</a></li>'
                            for name, label in parts)
            return (f'<li class="item"><details><summary>{esc(display(r))}</summary>'
                    f'<ul class="parts">{links}</ul></details>{tags}<br>{meta}</li>')
        if r["format"] == "zim":
            url = f'{LIBRARY}/content/{quote(library_book(r))}'
            return f'<li class="item"><a class="lib" href="{url}">{esc(display(r))}</a>{tags}<br>{meta}</li>'
        return (f'<li class="item"><a href="{self.href(page, r["folder"])}">{esc(display(r))}</a>'
                f'{tags}<br>{meta}</li>')

    def item_list(self, page, rows, topic=None):
        if not rows:
            return ""
        return '<ul class="items">' + "".join(self.item_html(page, r, topic) for r in rows) + '</ul>\n'

    def full_library_note(self, page):
        return (f'<p class="small">Links marked as collections open in the full library. '
                f'<a href="{self.page_link(page, "how")}">How to open it</a>.</p>\n')

    def situations_for(self, topic):
        groups = []   # (situation, [(rel, page, label)], notes, drafts)
        noted = set()
        for s in self.situations:
            if s["topic"] != topic:
                continue
            row = self.by_id.get(s["item_id"])
            entry = None
            if row and not cl.is_multi_file(row) and self.exists(row["folder"]):
                entry = (row["folder"], s["pdf_page"] or None, s["label"])
            if not groups or groups[-1][0] != s["situation"]:
                first = s["order"] not in noted
                noted.add(s["order"])
                groups.append((s["situation"], [],
                               self.notes.get(s["order"], []) if first else [],
                               self.drafts.get(s["order"], []) if first else []))
            if entry:
                groups[-1][1].append(entry)
        return [g for g in groups if g[1] or g[2] or g[3]]

    def numbers_html(self):
        rows = "".join(f'<tr><td class="num">{esc(n["number"])}</td><td>{esc(n["what"])}</td></tr>'
                       for n in self.numbers)
        return ('<div class="numbers"><h3>Emergency numbers in France, if a phone works</h3>'
                f'<table>{rows}</table>'
                '<p class="small">Checked 18 Nov 2026. 112 works in every EU country.</p></div>\n')

    # ---- page frame ------------------------------------------------------

    def frame(self, page, title, body, crumbs=()):
        nav = ""
        if page != HTML_NAME:
            trail = [f'<a href="{self.page_link(page, "home")}">Home</a>'] + \
                [f'<a href="{self.href(page, target)}">{esc(label)}</a>' for label, target in crumbs]
            nav = '<nav class="crumbs">' + " › ".join(trail) + f' › <span>{esc(title)}</span></nav>\n'
        test = ('<p class="testbuild">TEST BUILD: some items and notes here have not been checked yet.</p>\n'
                if self.include_drafts else "")
        return ('<!DOCTYPE html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
                '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
                f'<title>{esc(title)} · Knowledge Arc</title>\n<style>\n{CSS}</style>\n</head>\n<body>\n'
                f'{nav}{test}{body}'
                f'<footer><a href="{self.page_link(page, "home")}">Home</a> · '
                f'<a href="{self.page_link(page, "a-z")}">A to Z</a> · '
                f'<a href="{self.page_link(page, "how")}">How to use</a> · '
                f'<a href="{self.page_link(page, "keep")}">Keep it alive and pass it on</a> · '
                f'<a href="{self.page_link(page, "about")}">About</a></footer>\n</body>\n</html>\n')

    def add(self, page, title, body, crumbs=()):
        self.pages[page] = self.frame(page, title, body, crumbs)

    # ---- pages -----------------------------------------------------------

    def home(self):
        page = HTML_NAME
        o = ['<header class="hero"><h1>Knowledge Arc</h1>'
             '<p>An offline library of trusted practical knowledge, reference and culture. '
             'Everything here works without internet. Choose a subject to begin; '
             'the guides open right here in your browser.</p></header>\n']
        launchers = [(s, n) for s, n, _ in self.launchers() if s != "Linux"]
        if launchers:
            names = " or ".join(f'<b>{esc(Path(n).stem)}</b>' for _, n in launchers)
            o.append(f'<p class="howto">For search and the big collections (Wikipedia, medicine, repairs, '
                     f'books, maps), open the full library: double-click {names} in the drive window. '
                     f'<a href="{self.page_link(page, "how")}">How to use this drive</a></p>\n')
        else:
            o.append(f'<p class="howto"><a href="{self.page_link(page, "how")}">How to use this drive</a></p>\n')
        o.append('<h2>Subjects</h2>\n<div class="tiles">')
        for s in self.subjects:
            n = self.subject_count(s["id"])
            count = f'{n} item{"s" if n != 1 else ""}' if n else "nothing in this edition yet"
            o.append(f'<a class="tile{"" if n else " empty"}" href="{self.page_link(page, "subject", s["id"])}">'
                     f'<b>{esc(s["label"])}</b><span>{esc(s["description"])}</span>'
                     f'<span class="count">{count}</span></a>')
        o.append('</div>\n<h2>Shelves</h2>\n<div class="chips">')
        for shelf in SHELF_ORDER:
            n = sum(1 for r in self.items if r["shelf"] == shelf)
            if n:
                o.append(f'<a class="chip" href="{self.page_link(page, "shelf", shelf)}">'
                         f'{esc(cl.SHELVES[shelf])} <span class="count">{n}</span></a>')
        o.append('</div>\n<h2>More ways in</h2>\n<div class="chips">')
        if any(r.get("audience") == "children" for r in self.items):
            o.append(f'<a class="chip" href="{self.page_link(page, "children")}">For children</a>')
        o.append(f'<a class="chip" href="{self.page_link(page, "a-z")}">A to Z of topics and items</a>')
        if self.collections():
            o.append(f'<a class="chip lib" href="{LIBRARY}/">Search everything (full library)</a>')
        o.append('</div>\n')
        if "S1" in self.topics:
            o.append(f'<div class="urgent"><b>In an emergency:</b> call 112 (anywhere in Europe) or 15 '
                     f'(medical help in France) if a phone works. '
                     f'<a href="{self.page_link(page, "topic", "S1")}">First aid</a></div>\n')
        o.append(f'<p class="small">{esc(self.version_line)}</p>\n')
        self.add(page, "Start here", "".join(o))

    def subject(self, s):
        page = self.page_path("subject", s["id"])
        o = [f'<h1>{esc(s["label"])}</h1>\n<p>{esc(s["description"])}</p>\n<ul class="topics">']
        for c in self.subject_topics(s["id"]):
            n = len(self.topic_items(c["id"]))
            count = f'{n} item{"s" if n != 1 else ""}' if n else "nothing in this edition yet"
            o.append(f'<li><a href="{self.page_link(page, "topic", c["id"])}">{esc(c["domain"])}</a> '
                     f'<span class="count">{count}</span><br><span class="meta">{esc(c["must_answer"])}</span></li>')
        o.append('</ul>\n')
        self.add(page, s["label"], "".join(o))

    def topic(self, c):
        page = self.page_path("topic", c["id"])
        subject = next(s for s in self.subjects if s["id"] == c["subject"])
        o = [f'<h1>{esc(c["domain"])}</h1>\n<p><b>What you can learn here:</b> {esc(c["must_answer"])}.</p>\n']
        if c["id"] in TOPIC_INTROS:
            o.append(f'<p class="intro">{esc(TOPIC_INTROS[c["id"]])}</p>\n')
        if c["id"] == "S1" and self.numbers:
            o.append(self.numbers_html())
        groups = self.situations_for(c["id"])
        if groups:
            o.append('<h2>Where to look first</h2>\n<ul class="situations">')
            for situation, entries, notes, drafts in groups:
                o.append(f'<li><h3>{esc(situation)}</h3>')
                if entries:
                    o.append('<ul>')
                    for rel, pg, label in entries:
                        frag = f"#page={pg}" if pg else ""
                        o.append(f'<li><a href="{self.href(page, rel, frag)}">{esc(label)}</a>'
                                 + (f' <span class="small">(page {esc(pg)} of the PDF)</span>' if pg and pg != "1" else '')
                                 + '</li>')
                    o.append('</ul>')
                for note in notes:
                    o.append(f'<div class="note"><pre>{esc(note)}</pre></div>')
                for draft in drafts:
                    o.append(f'<div class="draft"><b>DRAFT, not checked yet:</b><pre>{esc(draft)}</pre></div>')
                o.append('</li>\n')
            o.append('</ul>\n')
        home = self.home_items(c["id"])
        start = [r for r in home if r["job"] == "primary"]
        deeper = [r for r in home if r["job"] != "primary"]
        also = self.also_items(c["id"])
        if start:
            o.append('<h2>Start here</h2>\n' + self.item_list(page, start, c["id"]))
        if deeper:
            o.append('<h2>Go deeper</h2>\n' + self.item_list(page, deeper, c["id"]))
        if also:
            o.append('<h2>Also useful</h2>\n' + self.item_list(page, also, c["id"]))
        if not (start or deeper or also):
            o.append('<p>Nothing on this drive for this topic yet.</p>\n')
        words = [w for w in c.get("search", "").split(";") if w]
        if words and self.collections():
            links = " · ".join(f'<a class="lib" href="{LIBRARY}/?q={quote(w)}">{esc(w)}</a>' for w in words)
            o.append(f'<h2>Search the full library</h2>\n<p>{links}</p>\n')
        if any(r["format"] == "zim" for r in home + also) or (words and self.collections()):
            o.append(self.full_library_note(page))
        related = [t for t in self.subject_topics(c["subject"]) if t["id"] != c["id"] and self.topic_items(t["id"])]
        if related:
            o.append('<h2>Related topics</h2>\n<p>' + " · ".join(
                f'<a href="{self.page_link(page, "topic", t["id"])}">{esc(t["domain"])}</a>' for t in related) + '</p>\n')
        self.add(page, c["domain"], "".join(o), [(subject["label"], self.page_path("subject", subject["id"]))])

    def shelf(self, shelf):
        page = self.page_path("shelf", shelf)
        rows = [r for r in self.items if r["shelf"] == shelf]
        o = [f'<h1>{esc(cl.SHELVES[shelf])}</h1>\n']
        if shelf == "community":
            o.append('<p class="comm-box"><b>Written by members of the public, not checked by experts.</b> '
                     'Often useful, but check anything important against the guides.</p>\n')
        for s in self.subjects:
            in_subject = [r for r in rows if self.topics.get(cl.topics(r)[0], {}).get("subject") == s["id"]]
            if in_subject:
                o.append(f'<h2>{esc(s["label"])}</h2>\n' + self.item_list(page, in_subject))
        if any(r["format"] == "zim" for r in rows):
            o.append(self.full_library_note(page))
        self.add(page, cl.SHELVES[shelf], "".join(o))

    def children(self):
        page = self.page_path("children")
        rows = [r for r in self.items if r.get("audience") == "children"]
        o = ['<h1>For children</h1>\n<p>Books and stories for children, and guides for adults teaching them.</p>\n']
        if self.topic_items("T2"):
            o.append(f'<p><a href="{self.page_link(page, "topic", "T2")}">Teaching a child to read</a> '
                     '(the parent\'s guide and the first reading books)</p>\n')
        o.append(self.item_list(page, rows))
        if any(r["format"] == "zim" for r in rows):
            o.append(self.full_library_note(page))
        self.add(page, "For children", "".join(o))

    def a_to_z(self):
        page = self.page_path("a-z")
        o = ['<h1>A to Z</h1>\n<h2>Topics</h2>\n<ul class="az">']
        for c in sorted(self.topics.values(), key=lambda c: c["domain"].lower()):
            if self.topic_items(c["id"]):
                o.append(f'<li><a href="{self.page_link(page, "topic", c["id"])}">{esc(c["domain"])}</a></li>')
        o.append('</ul>\n<h2>Everything on this drive</h2>\n')
        o.append(self.item_list(page, sorted(self.items, key=lambda r: display(r).lower())))
        self.add(page, "A to Z", "".join(o))

    def how(self):
        page = self.page_path("how")
        o = ['<h1>How to use this drive</h1>\n<ol class="steps">'
             f'<li><b>Any computer, nothing installed:</b> <a href="{self.page_link(page, "home")}">1 START-HERE</a> '
             'and every guide linked from it open in the web browser.</li>']
        launchers = self.launchers()
        if launchers:
            o.append('<li><b>The full library</b> (search, Wikipedia, medicine, repairs, books, courses, maps):<ul>')
            for system, name, how in launchers:
                o.append(f'<li>{esc(system)}: {esc(how)} <code>{esc(name)}</code> on this drive.</li>')
            o.append('</ul>A small window opens next to the browser. <b>Keep it open while you read</b>; close it '
                     'when you have finished. The first time, the computer may ask whether to run it: choose Run or Open. '
                     'If the browser does not open by itself, type <code>127.0.0.1:8642</code> in its address bar.</li>')
            if launchers[0][0] == "Windows":
                o.append(LAUNCHER_PICTURE.replace("{name}", "2 Open full library (Windows)"))
        else:
            o.append('<li><b>The full library:</b> the program that opens it is not on this drive. '
                     'The collections need the Kiwix reader (see <code>arc/software</code>).</li>')
        app = self.android_app()
        if app and self.collections():
            folder, name = app.rsplit("/", 1)
            o.append(f'<li id="android"><b>Android phone or tablet:</b> open this drive in the phone\'s Files app, '
                     f'go to <code>{esc(folder)}</code> and tap <code>{esc(name)}</code> to install the Kiwix app. '
                     'If the phone asks, allow installing apps from this source. Then open Kiwix and add the '
                     f'collections (files ending in <code>.zim</code>) from <code>{cl.ARC}/collections</code>. '
                     'The guides (PDFs) open from the Files app.</li>')
        o.append('<li><b>If this page does not open</b>, open the folder <code>arc</code>, then '
                 '<code>START-HERE.txt</code>: it lists the same things with their folders.</li></ol>\n')
        self.add(page, "How to use this drive", "".join(o))

    def keep(self):
        page = self.page_path("keep")
        o = ['<h1>Keep it alive and pass it on</h1>\n'
             '<p>This drive is one copy of the arc. Its knowledge lasts as long as copies exist, '
             'so check it, repair it, and make copies for others.</p>\n<ol class="steps">'
             '<li><b>Check it every 6 to 12 months:</b> open the folders <code>arc</code> then <code>system</code> '
             'and double-click <code>verify.bat</code> (Windows). On a Mac or Linux, run <code>sh verify.sh</code> '
             'in a terminal. It tells you if any file is damaged.</li>'
             '<li><b>Repair a damaged file</b> by copying the same file from another copy of the arc.</li>'
             '<li><b>Make a copy:</b> format a drive at least as big as this one as <b>exFAT</b> (ordinary sticks '
             'are often FAT32, which cannot hold the big collections), copy everything at the top of this drive '
             'onto it, then run the check on the new drive.</li>'
             '<li><b>Keep copies apart:</b> different houses if you can, never all in one bag.</li></ol>\n']
        if self.exists(f"{cl.ARC}/system/MAINTENANCE.txt"):
            o.append(f'<p>Step by step, including what to do when something goes wrong: '
                     f'<a href="{self.href(page, cl.ARC + "/system/MAINTENANCE.txt")}">the maintenance guide</a>.</p>\n')
        o.append('<p>If you ever have internet again, the recipe that built this arc is in '
                 '<code>arc/system/recipe</code>: with it the arc can be refreshed or rebuilt.</p>\n')
        self.add(page, "Keep it alive and pass it on", "".join(o))

    def about(self):
        page = self.page_path("about")
        pubs = sorted({self.publishers.get(r["publisher"], {}).get("name") or r["publisher"] for r in self.items})
        o = ['<h1>About this arc</h1>\n'
             '<p>The Knowledge Arc is an offline library for a time without internet. It was put together in 2026 '
             'from free, trusted sources, so that knowledge can be carried across that time and passed on.</p>\n'
             '<h2>How the sources were chosen</h2>\n<ul>'
             '<li>Only established publishers (health agencies, universities, aid organisations, official manuals, '
             'well-known open libraries), or items reviewed one by one.</li>'
             '<li>Each item has one job in one topic: the place to start, more depth, a cross-check, or the only '
             'source for something.</li>'
             '<li>Community-written answers are kept apart and labelled.</li>'
             '<li>Dates matter: some items are old. For medicine, prefer the newest edition here.</li></ul>\n'
             f'<p>Every item, with its source, edition and licence: '
             f'<a href="{self.href(page, cl.ARC + "/system/CATALOG.csv")}">the catalog</a> (opens in a spreadsheet). '
             f'Which version this copy is: <a href="{self.href(page, cl.ARC + "/system/VERSION.txt")}">VERSION.txt</a>.</p>\n'
             f'<h2>Publishers on this drive</h2>\n<p class="small">{esc(", ".join(pubs))}</p>\n'
             f'<p class="small">{esc(self.version_line)}</p>\n']
        self.add(page, "About this arc", "".join(o))

    def build_all(self):
        self.home()
        for s in self.subjects:
            self.subject(s)
        for c in self.topics.values():
            self.topic(c)
        for shelf in SHELF_ORDER:
            if any(r["shelf"] == shelf for r in self.items):
                self.shelf(shelf)
        if any(r.get("audience") == "children" for r in self.items):
            self.children()
        self.a_to_z()
        self.how()
        self.keep()
        self.about()

    # ---- text twin -------------------------------------------------------

    def render_text(self):
        o = []
        w = o.append
        w("KNOWLEDGE ARC: START HERE")
        w("An offline library. Everything on this drive works without internet.")
        w('Best: open "1 START-HERE" (at the top of the drive) in a web browser.')
        w("This text file lists the same things, with the folder each one is in.")
        if self.include_drafts:
            w("TEST BUILD: some items and notes here have not been checked yet.")
        w("")
        launchers = self.launchers()
        if launchers:
            w("The full library (search and the big collections):")
            for system, name, how in launchers:
                w(f"  {system}: {how} {name}")
            w("  Keep the small window that opens open while you read.")
            w("  If the browser does not open by itself, type 127.0.0.1:8642 in its address bar.")
            w("")
        app = self.android_app()
        if app and self.collections():
            w("Android phone or tablet: in the Files app, open this drive and tap")
            w(f"  {plain_path(app)}")
            w("to install the Kiwix app (if the phone asks, allow installing apps from this source).")
            w(f"Then open Kiwix and add the collections (names ending in .zim) from {plain_path(cl.ARC + '/collections')}.")
            w("")
        if self.numbers:
            w("EMERGENCY NUMBERS IN FRANCE (if a phone works):")
            for n in self.numbers:
                w(f"  {n['number']:<15} {n['what']}")
            w("")
        for s in self.subjects:
            topics = [c for c in self.subject_topics(s["id"])
                      if self.home_items(c["id"]) or self.situations_for(c["id"])]
            if not topics:
                continue
            w(f"== {s['label'].upper()} ==")
            for c in topics:
                w(f"{c['domain']}:")
                if c["id"] in TOPIC_INTROS:
                    w(textwrap.fill(TOPIC_INTROS[c["id"]], width=78, initial_indent="  ", subsequent_indent="  "))
                for situation, entries, notes, drafts in self.situations_for(c["id"]):
                    w(f"  * {situation}")
                    for rel, pg, label in entries:
                        w(f"      {label}: {plain_path(rel)}" + (f", page {pg}" if pg and pg != "1" else ""))
                    for note in notes:
                        for line in note.splitlines():
                            w(("      " + line).rstrip())
                    for draft in drafts:
                        w("      DRAFT, not checked yet:")
                        for line in draft.splitlines():
                            w("        " + line)
                for r in self.home_items(c["id"]):
                    start = " (start here)" if r["job"] == "primary" else ""
                    where = (f"collection {Path(r['folder']).name} (full library)" if r["format"] == "zim"
                             else plain_path(r["folder"]))
                    w(f"  - {display(r)}{start}\n    {where}")
            w("")
        w("CHECKING THE DRIVE: every 6 to 12 months, open arc > system and double-click")
        w("verify.bat (Windows), or run 'sh verify.sh' in a terminal (Mac, Linux).")
        if self.exists(f"{cl.ARC}/system/MAINTENANCE.txt"):
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
:root { --red:#b00020; --blue:#1a5fb4; --ink:#111; --soft:#555; --line:#ccc; --bg:#fff; --panel:#f4f4f4; --green:#26734d; }
* { box-sizing: border-box; }
body { margin: 0 auto; max-width: 60em; padding: 1em; font: 18px/1.5 system-ui, -apple-system, "Segoe UI", Roboto, Arial, sans-serif; color: var(--ink); background: var(--bg); }
h1 { font-size: 1.9em; margin: .3em 0; line-height: 1.2; }
h2 { font-size: 1.35em; border-bottom: 2px solid var(--line); padding-bottom: .15em; margin-top: 1.6em; }
h3 { margin: .8em 0 .3em; font-size: 1.1em; }
a { color: var(--blue); }
code { background: var(--panel); padding: 0 .3em; border-radius: 3px; }
.hero p { font-size: 1.1em; }
.howto { background: var(--panel); border-radius: 10px; padding: .7em 1em; }
.tiles { display: grid; grid-template-columns: repeat(auto-fill, minmax(15em, 1fr)); gap: .7em; }
.tile { display: block; padding: .9em 1em; border-radius: 12px; background: var(--blue); color: #fff; text-decoration: none; }
.tile b { display: block; font-size: 1.15em; }
.tile span { display: block; font-size: .85em; opacity: .92; }
.tile.empty { background: #8a8a8a; }
.tile:focus, .tile:hover, .chip:focus, .chip:hover { outline: 4px solid #f5c211; }
.count { font-size: .8em; color: var(--soft); }
.tile .count { color: #fff; opacity: .85; margin-top: .3em; }
.chips { display: flex; flex-wrap: wrap; gap: .5em; }
.chip { display: inline-block; padding: .45em .9em; border: 2px solid var(--blue); border-radius: 999px; text-decoration: none; }
.urgent { margin-top: 1.5em; border: 3px solid var(--red); border-radius: 10px; padding: .6em 1em; }
.crumbs { font-size: .9em; margin-bottom: .5em; }
.items, .topics, .az { padding-left: 1.1em; }
.item, .topics li { margin: .45em 0; }
.meta { font-size: .82em; color: var(--soft); }
.tag { display: inline-block; font-size: .72em; font-weight: bold; padding: 0 .45em; border-radius: 4px; margin-left: .3em; vertical-align: middle; }
.tag.start { background: var(--green); color: #fff; }
.tag.kids { background: #f5c211; color: #111; }
.tag.adv { background: #555; color: #fff; }
.tag.comm { background: #b58900; color: #fff; }
.comm-box { border-left: 6px solid #b58900; padding-left: .8em; }
.intro { background: var(--panel); border-radius: 8px; padding: .6em 1em; }
.numbers { border: 3px solid var(--red); border-radius: 10px; padding: .3em 1em; margin: 1em 0; }
.numbers table { border-collapse: collapse; }
.numbers td { padding: .2em .8em .2em 0; vertical-align: top; }
.num { font-size: 1.3em; font-weight: bold; white-space: nowrap; color: var(--red); }
.situations { list-style: none; padding: 0; }
.situations > li { border-left: 6px solid var(--red); padding: .1em 0 .4em 1em; margin: .8em 0; }
.small { font-size: .85em; color: var(--soft); }
.draft, .testbuild { background: #fff3cd; border: 2px dashed #b58900; padding: .5em 1em; border-radius: 8px; }
.note { background: var(--panel); border-left: 6px solid var(--blue); padding: .5em 1em; border-radius: 8px; margin: .5em 0; }
.note pre, .draft pre { white-space: pre-wrap; font: inherit; font-size: .9em; margin: 0; }
details summary { cursor: pointer; color: var(--blue); text-decoration: underline; }
.parts { columns: 2 12em; }
.steps li { margin: .5em 0; }
.pic { max-width: 100%; height: auto; display: block; margin: .5em 0; }
footer { margin-top: 2.5em; padding-top: .6em; border-top: 2px solid var(--line); font-size: .9em; }
@media (max-width: 30em) { body { font-size: 17px; padding: .7em; } h1 { font-size: 1.6em; } }
@media print { footer, .chips, .crumbs { display: none; } body { font-size: 12pt; } a { color: var(--ink); } }
"""


def build(drive, placed, all_ids, include_drafts=False, version_line="", folder=FRONTDOOR, publishers=None):
    """Write the website and the text twin; return the drive paths the pages
    link to (for tests)."""
    drive = Path(drive)
    site = Site(drive, placed, all_ids, include_drafts, version_line, Path(folder), publishers)
    site.build_all()
    if (drive / SITE).exists():
        shutil.rmtree(drive / SITE)   # generated: no stale pages
    for rel, text in site.pages.items():
        out = drive / rel
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text, encoding="utf-8", newline="")
    (drive / TXT_NAME).parent.mkdir(parents=True, exist_ok=True)
    with open(drive / TXT_NAME, "w", encoding="utf-8-sig", newline="") as f:
        f.write(site.render_text())
    return sorted(site.linked)


def pages(drive):
    """Every generated page on the drive, as drive paths."""
    drive = Path(drive)
    out = [HTML_NAME] if (drive / HTML_NAME).is_file() else []
    out += sorted(p.relative_to(drive).as_posix() for p in (drive / SITE).glob("*.html"))
    return out


def links_in(html_text, page=HTML_NAME):
    """Every link in a page that points at a file on the drive, as a drive
    path (resolved from the page's folder, URL-decoded, without #fragments).
    Links to the full library (LIBRARY) are left out."""
    from urllib.parse import unquote
    base = posixpath.dirname(page)
    out = []
    for h in re.findall(r'href="([^"]+)"', html_text):
        if h.startswith("#") or h.startswith(LIBRARY):
            continue
        out.append(posixpath.normpath(posixpath.join(base, unquote(h.split("#", 1)[0]))))
    return out
