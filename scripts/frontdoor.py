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

Two versions of the same pages:
  file mode    on the drive, opened with no program (file://). No scripts.
  served mode  packed into the arc's own collection (arczim.py) and shown by the
               library server: same pages, plus one search box on the home
               page; collections and searches are server addresses (/...).

Rules (CONTRIBUTING.md rule 4): self-contained pages (inline CSS, no web fonts),
relative links to files that exist on the drive. In file mode the only
absolute address is the library on this computer (LIBRARY), for links that
need the full library running; they say so. Inline scripts only in served
mode (LIBRARY_SCRIPT).
"""

import csv
import html
import json
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

# The editions (catalog bundles), smallest first; each holds the one before.
EDITIONS = {
    "pocket": ("Pocket edition", "for a phone or a 32 GB stick: the website, the guides, a medical encyclopedia, "
               "repair guides, school maths and science, Wikipedia (the 50,000 most important articles in full, the opening of a million more), Shakespeare, classic literature in "
               "translation from Europe and Asia, short films and the programs to open them"),
    "core": ("Core edition", "about 259 GB: adds the full Wikipedia with pictures, the map of France, Wikibooks, "
             "children's books and stories, English and European literature, textbooks on biology, the human body, algebra, statistics, chemistry and astronomy, "
             "Crash Course videos, and more medical and energy references"),
    "standard": ("Standard edition", "about 356 GB: adds the rebuild layer (trades, materials, farming), "
                 "Project Gutenberg subject sets, courses and children's reading"),
    "full": ("Full edition", "about 727 GB: adds all of Project Gutenberg, Khan Academy, Wikisource and "
             "maps of Europe"),
}

BOOK_PART_ORDER = ["fm", "toc", "int", "info", "#", "gp", "appa", "appb", "resc", "gloss", "indx", "ind", "bm"]
BOOK_PART_LABELS = {"fm": "Front pages", "toc": "Contents", "int": "Introduction",
                    "info": "Information", "gp": "Green Pages (medicines)",
                    "resc": "Resources", "gloss": "Glossary (words explained)",
                    "indx": "Index", "ind": "Index", "appa": "Appendix A", "appb": "Appendix B",
                    "bm": "Back pages"}


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


def load_paths(folder=FRONTDOOR):
    """Learning paths ("read these in order"), from paths.csv if the folder
    has one: {path: {"title", "topic", "steps": [row, ...]}} in file order."""
    paths = {}
    if not (folder / "paths.csv").is_file():
        return paths
    for row in read(folder / "paths.csv"):
        p = paths.setdefault(row["path"], {"title": row["title"], "topic": row["topic"], "steps": []})
        p["steps"].append(row)
    return paths


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
        suffix = Path(name).stem.rsplit("_", 1)[-1].lower()
        if suffix.isdigit():
            return (BOOK_PART_ORDER.index("#"), int(suffix))
        if suffix in BOOK_PART_ORDER:
            return (BOOK_PART_ORDER.index(suffix), 0)
        return (BOOK_PART_ORDER.index("#"), 0)   # a named chapter, e.g. "Community": before chapter 1

    out = []
    for name in sorted(files, key=key):
        suffix = Path(name).stem.rsplit("_", 1)[-1]
        label = f"Chapter {int(suffix)}" if suffix.isdigit() else BOOK_PART_LABELS.get(suffix.lower(), suffix)
        out.append((name, label))
    return out


def esc(text):
    return html.escape(text, quote=True)


def count(n, word):
    """'1 page', '1,250 pages'."""
    return f"{n:,} {word}{'' if n == 1 else 's'}"


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
                 publishers=None, served=False, search_books=(), arc_zim=None, edition=None, overlay=None):
        self.drive = Path(drive)   # where the content is read (pages are written by build())
        self.overlay = Path(overlay) if overlay else None   # the pocket kit, read first, when building it
        self.edition = edition if edition in EDITIONS else None   # catalog bundle, if built by bundle
        self.served = served
        self.lib = "" if served else LIBRARY   # prefix for the library's addresses
        self.search_books = list(search_books)  # books the served home page searches
        self.titles = {}      # drive path -> page title
        self.arc_zim = arc_zim   # drive path of the arc's own collection, if built
        self.include_drafts = include_drafts
        self.version_line = version_line
        self.publishers = publishers or {}
        self.subjects = read(cl.SUBJECTS)
        self.topics = {c["id"]: c for c in read(cl.COVERAGE)}
        self.situations = load_situations(all_ids, folder, self.topics)
        self.paths = load_paths(folder)
        self.numbers = read(folder / "numbers.csv")
        books = folder / "paper-books.csv"
        self.paper_books = read(books) if books.is_file() else []
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
        return self.at(rel).is_file()

    def at(self, rel):
        return cl.on_drive(self.drive, rel, self.overlay)

    def present(self, r):
        if cl.is_multi_file(r):
            folder = self.at(r["folder"])
            return folder.is_dir() and any(p.suffix in (".pdf", ".html") for p in folder.iterdir())
        return self.exists(r["folder"])

    def home_items(self, topic):
        rows = [r for r in self.items if cl.topics(r)[:1] == [topic]]
        return sorted(rows, key=lambda r: (JOB_ORDER.index(r["job"]) if r["job"] in JOB_ORDER else 9,
                                           self.items.index(r)))

    def sectioned(self, c, home):
        """[(heading, rows)] for a topic with sections, in their order; items
        with no section come last under "More on this topic". [] if the topic
        has no sections."""
        names = cl.sections(c)
        if not names:
            return []
        groups = [(name, [r for r in home if r.get("section") == name]) for name in names]
        rest = [r for r in home if r.get("section") not in names]
        groups.append(("More on this topic", rest))
        return [(name, rows) for name, rows in groups if rows]

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

    def fallbacks(self):
        """[(problem, [(device, what to open)])]: the drive's own programs, for
        when the computer's browser, PDF reader or the library server fails.
        Only programs actually on the drive are named."""
        def first(pattern):
            hits = sorted(self.drive.glob(pattern))
            return hits[0].relative_to(self.drive).as_posix() if hits else None

        out = []
        ff = [(d, p) for d, p in (("Windows", first("arc/software/windows/firefox/firefox.exe")),
                                  ("Mac", first("arc/software/mac/firefox-*.dmg")),
                                  ("Linux", first("arc/software/linux/firefox/firefox"))) if p]
        if ff:
            out.append(("No web browser on the computer, or it will not show these pages", ff))
        pdf = [(d, p) for d, p in (("Windows", first("arc/software/windows/sumatrapdf/*.exe")),
                                   ("Android", first("arc/software/android/mupdf-*.apk"))) if p]
        if pdf:
            out.append(("The guides (PDFs) will not open", pdf))
        kx = [(d, p) for d, p in (("Windows", first("arc/software/windows/kiwix-desktop/kiwix-desktop.exe")),
                                  ("Mac", first("arc/software/mac/kiwix-macos_*.dmg")),
                                  ("Linux", first("arc/software/linux/kiwix-desktop_*.appimage"))) if p]
        if kx:
            out.append(("The full library will not start", kx))
        return out

    def collections(self):
        return [r for r in self.items if r["format"] == "zim"]

    def paper_items(self, tier):
        """The guides on this drive marked for printing (catalog `paper`), in
        the site's order: subject, topic, start-here first. One file each."""
        seen, out = set(), []
        for s in self.subjects:
            for c in self.subject_topics(s["id"]):
                for r in self.home_items(c["id"]):
                    if r.get("paper") == tier and r["id"] not in seen and not cl.is_multi_file(r) \
                            and r["format"] != "zim":
                        seen.add(r["id"])
                        out.append(r)
        return out

    # ---- links -----------------------------------------------------------

    def href(self, page, target, fragment=""):
        """Relative link from page (a drive path) to target (a drive path).
        In served mode both are mapped to their paths inside the ZIM."""
        self.linked.add(target)
        if self.served:
            page, target = zim_path(page), zim_path(target)
        rel = posixpath.relpath(target, posixpath.dirname(page) or ".")
        return quote(rel) + fragment

    @staticmethod
    def page_path(kind, key=""):
        if kind == "home":
            return HTML_NAME
        return f"{SITE}/{kind}{'-' + key if key else ''}.html"

    def page_link(self, page, kind, key=""):
        # File mode: Home from another drive page keeps the reader on the
        # drive's pages (START_SCRIPT switches only on a fresh open).
        stay = "#stay" if kind == "home" and page != HTML_NAME and self.arc_zim and not self.served else ""
        return self.href(page, self.page_path(kind, key), stay)

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
            kind = "books" if r["format"].startswith("html") else "documents"
            bits.append(f"{cl.file_count(r)} {kind}" if cl.file_list(r) else "book in chapters")
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
        about = f'<p class="about">{esc(r["about"])}</p>' if r.get("about", "").strip() else ""
        if cl.is_multi_file(r):
            parts = self.parts(r)
            links = "".join(f'<li><a href="{self.href(page, r["folder"] + "/" + name)}">{esc(label)}</a></li>'
                            for name, label in parts)
            return (f'<li class="item"><details><summary>{esc(display(r))}</summary>'
                    f'<ul class="parts">{links}</ul></details>{tags}{meta}{about}</li>')
        if r["format"] == "zim":
            url = f'{self.lib}/content/{quote(library_book(r))}'
            return f'<li class="item"><a class="lib" href="{url}">{esc(display(r))}</a>{tags}{meta}{about}</li>'
        return (f'<li class="item"><a href="{self.href(page, r["folder"])}">{esc(display(r))}</a>'
                f'{tags}{meta}{about}</li>')

    def parts(self, r):
        """[(file name, label)] of a multi-file item on this drive: in its
        pinned list's order with its labels, else as a book's chapters."""
        folder = self.at(r["folder"])
        pinned = cl.part_labels(r)
        if pinned:
            return [(name, label) for name, label in pinned.items() if (folder / name).is_file()]
        return book_parts([p.name for p in folder.glob("*.pdf")])

    def item_list(self, page, rows, topic=None):
        if not rows:
            return ""
        return '<ul class="items">' + "".join(self.item_html(page, r, topic) for r in rows) + '</ul>\n'

    def full_library_note(self, page):
        if self.served:
            return ""
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

    def find_form(self, page, big=False, field_id=""):
        """The search box: on the drive's own pages a plain form (no script)
        that opens search.html?q=...; in the full library, the library's
        own search over the arc and the checked collections. field_id: the
        search page's own box, which its script fills in."""
        cls = "find big" if big else "find"
        hint = "For example: burn, bread, solar"
        idattr = f' id="{field_id}"' if field_id else ""
        if self.served:
            hidden = "".join(f'<input type="hidden" name="books.name" value="{esc(b)}">' for b in self.search_books)
            return (f'<form class="{cls}" action="/search" method="get" role="search">{hidden}'
                    f'<input type="search" name="pattern" placeholder="{hint}" aria-label="Search everything" required>'
                    '<button type="submit">Search</button></form>\n')
        return (f'<form class="{cls}" action="{self.page_link(page, "search")}" method="get" role="search">'
                f'<input type="search" name="q"{idattr} placeholder="{hint}" aria-label="Search this library" required>'
                '<button type="submit">Search</button></form>\n')

    def frame(self, page, title, body, crumbs=(), css=""):
        home = self.page_link(page, "home")
        top = (f'<header class="topbar"><a class="brand" href="{home}"><span class="mark">{LOGO}</span>'
               f'Knowledge Arc</a>' + (self.find_form(page) if page not in (HTML_NAME, self.page_path("search")) else "")
               + '</header>\n')
        nav = ""
        if page != HTML_NAME:
            trail = [f'<a href="{home}">Home</a>'] + \
                [f'<a href="{self.href(page, target)}">{esc(label)}</a>' for label, target in crumbs]
            nav = '<nav class="crumbs">' + " › ".join(trail) + f' › <span>{esc(title)}</span></nav>\n'
        test = ('<p class="testbuild">TEST BUILD: some notes here are drafts that have not been checked yet.</p>\n'
                if self.include_drafts else "")
        emergency = ""
        if page != HTML_NAME and "S1" in self.topics and self.topic_items("S1"):   # home has it at the top
            emergency = (f'<p><b>Emergency?</b> If a phone works, call 112 (anywhere in Europe) or 15 (medical '
                         f'help in France). <a href="{self.page_link(page, "topic", "S1")}">First aid</a></p>')
        return ('<!DOCTYPE html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
                '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
                '<meta name="color-scheme" content="light dark">\n'
                f'<title>{esc(title)} · Knowledge Arc</title>\n<style>\n{CSS}{css}</style>\n</head>\n<body>\n'
                f'{top}{nav}{test}{body}'
                f'<footer>{emergency}<p><a href="{home}">Home</a> · '
                f'<a href="{self.page_link(page, "a-z")}">A to Z</a> · '
                f'<a href="{self.page_link(page, "how")}">How to use</a> · '
                f'<a href="{self.page_link(page, "keep")}">Keep it alive and pass it on</a> · '
                f'<a href="{self.page_link(page, "about")}">About</a></p></footer>\n</body>\n</html>\n')

    def add(self, page, title, body, crumbs=(), css=""):
        self.pages[page] = self.frame(page, title, body, crumbs, css)
        self.titles[page] = title

    # ---- pages -----------------------------------------------------------

    def holds(self, rows):
        """What a set of items holds, in a few words: '17 guides · MDWiki
        Medical Encyclopedia, NHS Medicines A to Z and 2 more'."""
        docs = [r for r in rows if r["format"] != "zim"]
        zims = [display(r) for r in sorted((r for r in rows if r["format"] == "zim"),   # start-here ones first
                                           key=lambda r: JOB_ORDER.index(r["job"]) if r["job"] in JOB_ORDER else 9)]
        bits = []
        if docs:
            bits.append(f'{len(docs)} guide{"s" if len(docs) != 1 else ""}')
        if zims:
            more = f" and {len(zims) - 2} more" if len(zims) > 2 else ""
            bits.append(", ".join(zims[:2]) + more)
        return " · ".join(bits)

    def path_steps(self, p):
        """[(catalog row, step)] of a learning path whose guide is on this
        drive; a path with fewer than two is not shown."""
        on_drive = {r["id"]: r for r in self.items}
        steps = [(on_drive[s["item_id"]], s) for s in p["steps"] if s["item_id"] in on_drive]
        return steps if len(steps) >= 2 else []

    def shown_paths(self):
        return [(key, p) for key, p in self.paths.items() if p["topic"] in self.topics and self.path_steps(p)]

    def step_link(self, page, r, step):
        if r["format"] == "zim":
            return f'{self.lib}/content/{quote(library_book(r))}'
        if cl.is_multi_file(r):
            return self.page_link(page, "topic", cl.topics(r)[0])
        return self.href(page, r["folder"], f'#page={step["pdf_page"]}' if step["pdf_page"] else "")

    def path_html(self, page, p):
        subject = self.topics[p["topic"]]["subject"]
        o = [f'<section class="panel path s-{esc(subject)}" id="path"><h2>New to this? Read these in order</h2>'
             f'<p class="small">{esc(p["title"])}</p><ol>']
        for n, (r, step) in enumerate(self.path_steps(p), 1):
            o.append(f'<li><span class="stepno">{n}</span><span><a href="{self.step_link(page, r, step)}">'
                     f'{esc(display(r))}</a><br><span class="small">{esc(step["why"])}</span></span></li>')
        o.append('</ol></section>\n')
        return "".join(o)

    def subject_items(self, subject):
        seen, out = set(), []
        for c in self.subject_topics(subject):
            for r in self.topic_items(c["id"]):
                if r["id"] not in seen:
                    seen.add(r["id"])
                    out.append(r)
        return out

    def home(self):
        page = HTML_NAME
        o = []
        if "S1" in self.topics and self.topic_items("S1"):
            o.append(f'<p class="emergency"><b>Emergency?</b> If a phone works, call 112 (anywhere in Europe) or 15 '
                     f'(medical help in France). <a href="{self.page_link(page, "topic", "S1")}">First aid →</a></p>\n')
        o.append('<section class="hero"><h1>What do you want to learn today?</h1>'
                 '<p>Everything in this library works without internet: trusted guides on health, food, water, '
                 'energy and repairs, encyclopedias, books and courses. Search, pick a way in, or explore a subject.</p>'
                 + self.find_form(page, big=True))
        quick = [(label, t) for label, t in QUICK if t in self.topics and self.topic_items(t)]
        if quick:
            o.append('<nav class="quick" aria-label="Quick ways in">' + "".join(
                f'<a href="{self.page_link(page, "topic", t)}">{esc(label)}</a>' for label, t in quick) + '</nav>')
        o.append('</section>\n')
        if self.served:
            o.append('<p class="small">The search covers the guides and the collections. Community answers have '
                     '<a href="/?list">their own search</a>.</p>\n')
        else:
            o.append('<section class="panel"><h2>Want everything?</h2>' + self.library_box(page) + '</section>\n')
        paths = self.shown_paths()
        if paths:
            o.append('<h2>Learning paths</h2>\n<ul class="cards">')
            for key, p in paths:
                steps = self.path_steps(p)
                subject = self.topics[p["topic"]]["subject"]
                o.append(f'<li><a class="tcard s-{esc(subject)}" href="{self.page_link(page, "topic", p["topic"])}#path">'
                         f'<span class="count">{esc(self.topics[p["topic"]]["domain"])} · {len(steps)} steps</span>'
                         f'<b>{esc(p["title"])}</b><span>Start: {esc(display(steps[0][0]))}</span></a></li>')
            o.append('</ul>\n')
        o.append('<h2>Explore subjects</h2>\n<div class="tiles">')
        for s in self.subjects:
            rows = self.subject_items(s["id"])
            count = self.holds(rows) if rows else "Nothing in this edition yet"
            o.append(f'<a class="tile s-{esc(s["id"])}{"" if rows else " empty"}" '
                     f'href="{self.page_link(page, "subject", s["id"])}">{icon(s["id"])}'
                     f'<b>{esc(s["label"])}</b><span>{esc(s["description"])}</span>'
                     f'<span class="count">{esc(count)}</span></a>')
        o.append('</div>\n<h2>Other ways in</h2>\n<div class="chips">')
        for shelf in SHELF_ORDER:
            n = sum(1 for r in self.items if r["shelf"] == shelf)
            if n:
                o.append(f'<a class="chip" href="{self.page_link(page, "shelf", shelf)}">'
                         f'{esc(cl.SHELVES[shelf])} <span class="count">{n}</span></a>')
        if any(r.get("audience") == "children" for r in self.items):
            o.append(f'<a class="chip" href="{self.page_link(page, "children")}">For children</a>')
        o.append(f'<a class="chip" href="{self.page_link(page, "a-z")}">A to Z of topics and items</a>')
        if self.served:
            o.append('<a class="chip" href="/?list">All collections</a>')
        elif self.collections():
            o.append(f'<a class="chip lib" href="{LIBRARY}/">Search everything (full library)</a>')
        o.append('</div>\n')
        o.append(f'<p class="panel">This is one copy of the Knowledge Arc. Its knowledge lasts as long as copies '
                 f'exist: check it, copy it, pass it on. <a href="{self.page_link(page, "keep")}">Keep it alive →</a></p>\n')
        edition = (f'<a href="{self.page_link(page, "about")}#editions">{esc(EDITIONS[self.edition][0])}</a>. '
                   if self.edition else '')
        o.append(f'<p class="small">{edition}{esc(self.version_line)}</p>\n')
        if self.served:
            o.append('<script>var ARC_BOOK = "";' + LIBRARY_SCRIPT + '</script>\n')
        elif self.launchers():
            o.append('<script>var ARC_BOOK = ' + json.dumps(self.arc_book()) + ';' + START_SCRIPT + '</script>\n')
        self.add(page, "Start here", "".join(o))

    def arc_book(self):
        """The arc's own collection's name in the library's addresses, or ''."""
        return Path(self.arc_zim).stem if self.arc_zim else ""

    def library_box(self, page):
        """File mode: how to open the full library. Without a script, one
        paragraph names the launchers. START_SCRIPT shows instead the variant
        for this computer, or, when the library already runs, switches to it
        (or offers a link, with #stay)."""
        how = f'<a href="{self.page_link(page, "how")}">How to use this drive</a>'
        launchers = self.launchers()
        if not launchers:
            return f'<p class="howto">{how}</p>\n'
        intro = 'For search and the big collections (Wikipedia, medicine, repairs, books, maps), open the full library'
        names = " or ".join(f'<b>{esc(Path(n).stem)}</b>' for s, n, _ in launchers if s != "Linux")
        o = ['<div id="library">']
        if names:
            o.append(f'<p class="howto" data-os="">{intro}: double-click {names} in the drive window. {how}</p>')
        else:
            o.append(f'<p class="howto" data-os="">{intro}. {how}</p>')
        for system, name, action in launchers:
            o.append(f'<p class="howto" data-os="{esc(system)}" hidden>{intro}: {esc(action)} '
                     f'<b>{esc(Path(name).stem if "/" not in name else name)}</b>'
                     f'{" in the drive window" if "/" not in name else ""}. A small window opens: keep it open while '
                     f'you read. {how}</p>')
        if self.arc_zim and self.android_app():
            o.append(f'<p class="howto" data-os="Android" hidden>On this phone or tablet, the full library opens '
                     f'in the Kiwix app. {how}</p>')
        if self.arc_zim:
            target = f'{LIBRARY}/content/{quote(self.arc_book())}/index.html'
            o.append(f'<p class="howto running" data-os="running" hidden><b>The full library is running on this '
                     f'computer.</b> <a href="{target}">Open it</a> for search and the big collections.</p>')
        o.append('</div>\n')
        return "".join(o)

    def search_page(self):
        """File mode: search the drive's own pages with nothing started
        (owner, 22 Nov 2026; CONTRIBUTING.md rule 4: the one page besides
        START-HERE with an inline script). It finds topics, guides, the
        first-aid situations and the collections by their names and
        descriptions; the collections' own contents need the full library."""
        page = self.page_path("search")
        index = []

        def add(title, url, kind, about="", words=""):
            index.append({"t": title, "u": url, "k": kind, "d": about, "w": words})

        for c in self.topics.values():
            if self.topic_items(c["id"]):
                subject = next((s["label"] for s in self.subjects if s["id"] == c["subject"]), "")
                add(c["domain"], self.page_link(page, "topic", c["id"]), "Topic", c["must_answer"],
                    " ".join([subject, c.get("search", "").replace(";", " "), c.get("sections", "").replace(";", " ")]))
        for r in self.items:
            topics = " ".join(self.topics[t]["domain"] for t in cl.topics(r) if t in self.topics)
            pub = self.publishers.get(r["publisher"], {}).get("name") or ""
            words = " ".join([r["title"], pub, topics, r.get("section", "")])
            if r["format"] == "zim":
                add(display(r), f'{LIBRARY}/content/{quote(library_book(r))}', "Collection (full library)",
                    r.get("about", ""), words)
            elif cl.is_multi_file(r):
                home = cl.topics(r)[0] if cl.topics(r) else ""
                if home in self.topics:
                    add(display(r), self.page_link(page, "topic", home),
                        "Documents" if cl.file_list(r) else "Book in chapters", r.get("about", ""), words)
                if cl.file_list(r):   # each document of a pinned list is found by its own name
                    for name, label in self.parts(r):
                        add(label, self.href(page, r["folder"] + "/" + name), "Guide", display(r), words)
            else:
                add(display(r), self.href(page, r["folder"]), "Guide", r.get("about", ""), words)
        for key, p in self.shown_paths():
            add(p["title"], self.page_link(page, "topic", p["topic"]) + "#path", "Learning path",
                " → ".join(display(r) for r, _ in self.path_steps(p)), self.topics[p["topic"]]["domain"])
        for s in self.situations:
            row = self.by_id.get(s["item_id"])
            if row and not cl.is_multi_file(row) and self.exists(row["folder"]):
                frag = f"#page={s['pdf_page']}" if s["pdf_page"] else ""
                add(s["label"], self.href(page, row["folder"], frag), s["situation"], display(row), s["topic"])
        data = json.dumps(index, ensure_ascii=True).replace("</", "<\\/")
        o = ['<h1>Search this library</h1>\n', self.find_form(page, big=True, field_id="q"),
             '<p id="status" class="small">Type a word, for example: burn, bread, solar, choking.</p>\n'
             '<ol id="results" class="results"></ol>\n'
             f'<noscript><p>Search needs JavaScript, which this browser has turned off. Use the '
             f'<a href="{self.page_link(page, "a-z")}">A to Z</a> instead.</p></noscript>\n']
        if self.collections():
            o.append(f'<p class="panel">This searches the names and descriptions of the guides and topics on this '
                     f'drive. To search inside Wikipedia and the other collections, '
                     f'<a id="full" class="lib" href="{LIBRARY}/">search the full library</a> '
                     f'(<a href="{self.page_link(page, "how")}">open it first</a>).</p>\n')
        o.append(f'<script>var ARC_INDEX = {data};{SEARCH_SCRIPT}</script>\n')
        self.add(page, "Search", "".join(o))

    def band(self, subject_id, title, text):
        return (f'<header class="band s-{esc(subject_id)}">{icon(subject_id, 44)}<div><h1>{esc(title)}</h1>'
                f'<p>{text}</p></div></header>\n')

    def subject(self, s):
        page = self.page_path("subject", s["id"])
        o = [self.band(s["id"], s["label"], esc(s["description"])), f'<ul class="cards topics s-{esc(s["id"])}">']
        for c in self.subject_topics(s["id"]):
            rows = self.topic_items(c["id"])
            count = self.holds(rows) if rows else "Nothing in this edition yet"
            o.append(f'<li><a class="tcard" href="{self.page_link(page, "topic", c["id"])}"><b>{esc(c["domain"])}</b>'
                     f'<span>{esc(c["must_answer"])}</span><span class="count">{esc(count)}</span></a></li>')
        o.append('</ul>\n')
        self.add(page, s["label"], "".join(o))

    def topic(self, c):
        page = self.page_path("topic", c["id"])
        subject = next(s for s in self.subjects if s["id"] == c["subject"])
        o = [self.band(c["subject"], c["domain"], f'<b>What you can learn here:</b> {esc(c["must_answer"])}.')]
        if c["id"] in TOPIC_INTROS:
            o.append(f'<p class="intro">{esc(TOPIC_INTROS[c["id"]])}</p>\n')
        if c["id"] == "S1" and self.numbers:
            o.append(self.numbers_html())
        for key, p in self.shown_paths():
            if p["topic"] == c["id"]:
                o.append(self.path_html(page, p))
                break
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
        also = self.also_items(c["id"])
        groups = self.sectioned(c, home)
        if groups:
            # A big topic: one heading per section, each with its own "Start here" items.
            if len(groups) > 2:
                o.append('<p class="toc">On this page: ' + "".join(
                    f'<a href="#s{i}">{esc(name)}</a>' for i, (name, _) in enumerate(groups, 1)) + '</p>\n')
            for i, (name, rows) in enumerate(groups, 1):
                o.append(f'<h2 id="s{i}">{esc(name)}</h2>\n' + self.item_list(page, rows, c["id"]))
        else:
            start = [r for r in home if r["job"] == "primary"]
            deeper = [r for r in home if r["job"] != "primary"]
            if start:
                o.append('<h2>Start here</h2>\n' + self.item_list(page, start, c["id"]))
            if deeper:
                o.append('<h2>Go deeper</h2>\n' + self.item_list(page, deeper, c["id"]))
        if also:
            o.append('<h2>Also useful</h2>\n' + self.item_list(page, also, c["id"]))
        if not (home or also):
            o.append('<p>Nothing on this drive for this topic yet.</p>\n')
        words = [w for w in c.get("search", "").split(";") if w]
        if words and self.collections():
            links = "".join(f'<a class="chip lib" href="{self.lib}/?q={quote(w)}">{esc(w)}</a>' for w in words)
            o.append(f'<h2>Search the full library</h2>\n<div class="chips">{links}</div>\n')
        if any(r["format"] == "zim" for r in home + also) or (words and self.collections()):
            o.append(self.full_library_note(page))
        related = [t for t in self.subject_topics(c["subject"]) if t["id"] != c["id"] and self.topic_items(t["id"])]
        if related:
            o.append('<h2>Related topics</h2>\n<div class="chips">' + "".join(
                f'<a class="chip" href="{self.page_link(page, "topic", t["id"])}">{esc(t["domain"])}</a>'
                for t in related) + '</div>\n')
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
                     'If the browser does not open by itself, type <code>127.0.0.1:8642</code> in its address bar.' +
                     (' While it runs, <a href="{}">1 START-HERE</a> goes straight to the full library; to stay on '
                      'the drive\'s own pages, add <code>#stay</code> to the end of its address.'.format(
                          self.page_link(page, "home")) if self.arc_zim else '') + '</li>')
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
                     f'collections (files ending in <code>.zim</code>) from <code>{cl.ARC}/collections</code>' +
                     (f', and first of all <code>{esc(self.arc_zim)}</code>: it has the subjects and the guides'
                      if self.arc_zim else '') +
                     '. The guides (PDFs) also open from the Files app.</li>')
        if self.paper_items("first"):
            o.append(f'<li><b>On paper:</b> any guide can be printed from the browser or the PDF reader. '
                     f'<a href="{self.page_link(page, "paper")}">Print a paper copy</a> says which ones to print '
                     'first.</li>')
        o.append('<li><b>If this page does not open</b>, open the folder <code>arc</code>, then '
                 '<code>START-HERE.txt</code>: it lists the same things with their folders.</li></ol>\n')
        fallbacks = self.fallbacks()
        if fallbacks:
            o.append('<h2 id="fallbacks">If something does not work</h2>\n<p>This drive carries its own programs. '
                     'They run from the drive; nothing is installed. On a Mac, a file ending in '
                     '<code>.dmg</code> opens as a window: double-click the program inside it.</p>\n<ul class="steps">')
            for problem, entries in fallbacks:
                o.append(f'<li><b>{esc(problem)}:</b><ul>' + "".join(
                    f'<li>{esc(device)}: open <code>{esc(plain_path(path))}</code></li>' for device, path in entries)
                    + '</ul></li>')
            o.append('</ul>\n<p class="small">With the drive\'s browser or the Kiwix program open, the full library '
                     'still needs the library window (step 2) to be running: then go to <code>127.0.0.1:8642</code>. '
                     'The Kiwix program opens the collections (files ending in <code>.zim</code>) by itself, '
                     'without the library window.</p>\n')
        self.add(page, "How to use this drive", "".join(o))

    def keep(self):
        page = self.page_path("keep")
        if self.edition != "pocket" and self.exists(cl.POCKET_COPY_WINDOWS):
            phone = ('<li><b>Put it on a phone or a small stick:</b> this drive can make a pocket copy, the '
                     'smallest edition (about 24 GB: every guide, medicine, repairs, the most important Wikipedia '
                     'articles, the programs). Plug in a stick or memory card of 32 GB or more, formatted <b>exFAT</b>, then '
                     'double-click <code>Make a pocket copy</code> in the folder <code>arc</code>. It needs no '
                     'internet, copies the files and checks every one. On an Android phone, install the Kiwix app '
                     'from <code>arc/software/android</code> on the copy and open the files ending in '
                     '<code>.zim</code> in it.</li>')
        else:
            phone = ('<li><b>Put it on a phone:</b> copy everything at the top of this drive onto an Android phone '
                     'or tablet, install the Kiwix app from <code>arc/software/android</code>, and open the files '
                     'ending in <code>.zim</code> in it. Memory cards of 32 GB or less are usually FAT32: format '
                     'them as exFAT first.</li>')
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
             + phone +
             '<li><b>Keep copies apart:</b> different houses if you can, never all in one bag.</li></ol>\n']
        if self.exists(f"{cl.ARC}/Share over Wi-Fi (Windows).bat"):
            o.append('<p><b>Share it over Wi-Fi (advanced):</b> one computer can serve the full library to phones '
                     'nearby, which read it in their browser. Double-click <code>Share over Wi-Fi</code> in the '
                     'folder <code>arc</code>; the maintenance guide explains the rest.</p>\n')
        if self.exists(f"{cl.ARC}/system/MAINTENANCE.txt"):
            o.append(f'<p>Step by step, including what to do when something goes wrong: '
                     f'<a href="{self.href(page, cl.ARC + "/system/MAINTENANCE.txt")}">the maintenance guide</a>.</p>\n')
        o.append(f'<p><a href="{self.page_link(page, "card")}">The card to print</a>: one small page to keep with '
                 'the drive, with how to open it and the emergency numbers.</p>\n')
        if self.paper_items("first"):
            o.append(f'<p><a href="{self.page_link(page, "paper")}">Print a paper copy</a>: the guides to print '
                     'first, with their number of pages, and the books worth having on paper.</p>\n')
        o.append('<p>If you ever have internet again, the recipe that built this arc is in '
                 '<code>arc/system/recipe</code>: with it the arc can be refreshed or rebuilt.</p>\n')
        self.add(page, "Keep it alive and pass it on", "".join(o))

    def card(self):
        """The tiny printed card kept with each drive (A6, a quarter of A4):
        what this is, how to open it, the emergency numbers, local radio to
        write in, how to keep it alive, and a strip to stick on the drive."""
        page = self.page_path("card")
        built = self.version_line.split(". ")[0]
        edition = f"{EDITIONS[self.edition][0]}. " if self.edition else ""
        o = ['<p class="noprint small">Print this page and keep it with the drive. It is sized for an A6 card '
             '(a quarter of A4). Cut off the strip at the bottom and stick it on the drive.</p>\n'
             '<div class="card"><h1>Knowledge Arc</h1>\n'
             '<p>An offline library on this drive: health, food, water, energy, making and repairing, '
             'encyclopedias, books, courses and maps. <b>No internet needed.</b></p>\n'
             '<h2>Open it</h2>\n<p><b>Computer:</b> open the drive and double-click <b>1 START-HERE</b>. '
             'It opens in the web browser.']
        names = [Path(n).stem for s, n, _ in self.launchers() if s != "Linux"]
        if names:
            o.append(' For search and the big collections, double-click '
                     + " or ".join(f"<b>{esc(n)}</b>" for n in names)
                     + ' and keep its small window open while you read.')
        o.append('</p>\n')
        if self.android_app():
            first = f' (first <b>{esc(Path(self.arc_zim).name)}</b> in arc › site)' if self.arc_zim else ''
            o.append('<p><b>Android phone or tablet:</b> in the Files app, open arc › software › android and tap the '
                     f'Kiwix app to install it. Then open the files ending <b>.zim</b> in Kiwix{first}, and those in '
                     'arc › collections.</p>\n')
        if self.numbers:
            o.append('<h2>Emergency numbers in France, if a phone works</h2>\n<table>' + "".join(
                f'<tr><td class="num">{esc(n["number"])}</td><td>{esc(n["what"])}</td></tr>' for n in self.numbers)
                + '</table>\n')
        o.append('<h2>Local FM radio for official alerts</h2>\n<p class="small">Write the frequencies in while you '
                 'can still look them up.</p>\n<p>France Inter <span class="write"></span> '
                 'franceinfo <span class="write"></span> ici (local) <span class="write"></span></p>\n'
                 '<h2>Keep it alive, pass it on</h2>\n<p>Check it every 6 to 12 months: arc › system › verify. '
                 'Keep copies in different places. To pass it on, copy everything at the top of this drive onto '
                 'another drive formatted <b>exFAT</b>. Step by step: arc › system › MAINTENANCE.txt.</p>\n'
                 f'<p class="small">{esc(edition)}{esc(built)}.</p>\n'
                 '<p class="sticker">Offline library: open 1 START-HERE</p></div>\n')
        self.add(page, "The card to print", "".join(o), css=CARD_CSS)

    def paper(self):
        """Print a paper copy: the card, then the guides marked `first`, then
        `more`, each with its pages and a running total, ticks to mark what
        is printed, and the books worth having on paper."""
        page = self.page_path("paper")
        sets = [(tier, rows, sum(cl.pages(r) or 0 for r in rows))
                for tier, rows in ((t, self.paper_items(t)) for t in cl.PAPER) if rows]
        sheets = {tier: sum(-(-(cl.pages(r) or 0) // 2) for r in rows) for tier, rows, _ in sets}
        heads = {"first": "First: the essentials", "more": "Then, if you can print more"}
        o = ['<h1>Print a paper copy</h1>\n'
             '<p>Paper needs no power and no screen, and anyone can read it. The whole library is far too big to '
             'print: its guides alone come to tens of thousands of pages, its encyclopedias to millions. So '
             'print the most useful guides first, while there is still a printer, ink and paper.</p>\n'
             '<ol class="steps">'
             f'<li><b>The card:</b> <a href="{self.page_link(page, "card")}">The card to print</a>, one small '
             'page to keep with the drive.</li>']
        for tier, rows, total in sets:
            o.append(f'<li><b>{esc(heads[tier])}:</b> {count(len(rows), "guide")}, {count(total, "page")} '
                     f'({count(sheets[tier], "sheet")} of paper printed on both sides).</li>')
        o.append('</ol>\n<p class="small">To print a guide, open it and choose Print in the browser or the PDF '
                 'reader (Ctrl+P on Windows and Linux, Cmd+P on a Mac). Print on both sides of the paper if you can. '
                 'Print this page too, keep it on top and tick each guide once printed. Keep the pages flat, dry '
                 'and out of the light, in folders or binders.</p>\n')
        for tier, rows, total in sets:
            domains = list(dict.fromkeys(self.topics[cl.topics(r)[0]]["domain"] for r in rows))
            o.append(f'<h2>{esc(heads[tier])}</h2>\n<p class="small">{count(total, "page")} in all, on: '
                     f'{esc(" · ".join(domains))}.</p>\n<table class="paper"><tr><th>Done</th><th>Guide</th>'
                     '<th>Pages</th><th>Total so far</th></tr>')
            run = 0
            for r in rows:
                n = cl.pages(r) or 0
                run += n
                topic = self.topics[cl.topics(r)[0]]["domain"]
                o.append(f'<tr><td class="tick"></td><td><a href="{self.href(page, r["folder"])}">'
                         f'{esc(display(r))}</a><br><span class="small">{esc(topic)}</span></td>'
                         f'<td class="n">{n:,}</td><td class="n">{run:,}</td></tr>')
            o.append('</table>\n')
        if self.paper_books:
            o.append('<h2>Worth having as printed books</h2>\n<p>Some knowledge is not on this drive, or is '
                     'better in a book. If you can still buy or borrow these, keep them with the paper copy:</p>\n'
                     '<ul class="steps">' + "".join(f'<li><b>{esc(b["title"])}:</b> {esc(b["why"])}</li>'
                                                     for b in self.paper_books) + '</ul>\n')
        self.add(page, "Print a paper copy", "".join(o),
                 crumbs=[("Keep it alive and pass it on", self.page_path("keep"))], css=PAPER_CSS)

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
             f'<h2>Publishers on this drive</h2>\n<p class="small">{esc(", ".join(pubs))}</p>\n']
        if self.edition:
            o.append('<h2 id="editions">Editions</h2>\n<p>The arc comes in four sizes; each holds everything in '
                     f'the one before. This copy is the <b>{esc(EDITIONS[self.edition][0].lower())}</b>.</p>\n<ul>')
            for key, (name, what) in EDITIONS.items():
                here = " <b>(this copy)</b>" if key == self.edition else ""
                o.append(f'<li><b>{esc(name)}</b>{here}: {esc(what)}.</li>')
            o.append('</ul>\n')
        o.append(f'<p class="small">{esc(self.version_line)}</p>\n')
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
        self.card()
        if self.paper_items("first"):
            self.paper()
        self.about()
        if not self.served:
            self.search_page()

    # ---- text twin -------------------------------------------------------

    def render_text(self):
        o = []
        w = o.append
        w("KNOWLEDGE ARC: START HERE")
        w("An offline library. Everything on this drive works without internet.")
        w('Best: open "1 START-HERE" (at the top of the drive) in a web browser.')
        w("This text file lists the same things, with the folder each one is in.")
        if self.include_drafts:
            w("TEST BUILD: some notes here are drafts that have not been checked yet.")
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
            if self.arc_zim:
                w(f"First of all add {plain_path(self.arc_zim)}: it has the subjects and the guides.")
            w("")
        fallbacks = self.fallbacks()
        if fallbacks:
            w("IF SOMETHING DOES NOT WORK: this drive carries its own programs (nothing to install):")
            for problem, entries in fallbacks:
                w(f"  {problem}:")
                for device, path in entries:
                    w(f"    {device}: {plain_path(path)}")
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
                home = self.home_items(c["id"])
                for name, rows in self.sectioned(c, home) or [("", home)]:
                    if name:
                        w(f"  [{name}]")
                    for r in rows:
                        start = " (start here)" if r["job"] == "primary" else ""
                        where = (f"collection {Path(r['folder']).name} (full library)" if r["format"] == "zim"
                                 else plain_path(r["folder"]))
                        w(f"  - {display(r)}{start}\n    {where}")
            w("")
        first = self.paper_items("first")
        if first:
            w(f"TO PRINT FIRST (paper needs no power), {count(sum(cl.pages(r) or 0 for r in first), 'page')}:")
            for r in first:
                w(f"  - {display(r)}, {count(cl.pages(r) or 0, 'page')}\n    {plain_path(r['folder'])}")
            w("  What to print next, and books worth having on paper: arc > site > paper.html")
            w("")
        w("CHECKING THE DRIVE: every 6 to 12 months, open arc > system and double-click")
        w("verify.bat (Windows), or run 'sh verify.sh' in a terminal (Mac, Linux).")
        if self.exists(f"{cl.ARC}/system/MAINTENANCE.txt"):
            w("Looking after the drives (checking, repairing, making a new copy): arc > system > MAINTENANCE.txt")
        w("")
        w(self.version_line)
        return "\r\n".join(o).replace("\n", "\r\n").replace("\r\r\n", "\r\n") + "\r\n"


# Shared by the library home page and the served home page. Drops books the
# server did not load (damaged, skipped by -k) from the search forms and marks
# them in the lists. Old-style JavaScript, for old browsers.
# START-HERE in file mode (the page opened from the drive). Shows how to open
# the full library on this kind of computer. Then asks the library on this
# computer for its book list (kiwix-serve allows this from a file:// page) and,
# only if the arc's own collection (ARC_BOOK) is in it, switches to the arc's
# home there: another program on the same port is not followed. With #stay at
# the end of the address it offers a link instead. Asks again every few
# seconds for a while, so the page also switches once the library is started.
# If anything fails, the page stays as it is. Old-style JavaScript.
START_SCRIPT = r"""
(function () {
  var LIB = '""" + LIBRARY + r"""';
  var box = document.getElementById('library');
  if (!box) return;
  function show(which) {
    var ps = box.getElementsByTagName('p'), hit = null, i;
    for (i = 0; i < ps.length; i++) {
      if (ps[i].getAttribute('data-os') === which) hit = ps[i];
    }
    if (!hit) return;
    for (i = 0; i < ps.length; i++) {
      if (ps[i] === hit) ps[i].removeAttribute('hidden');
      else ps[i].setAttribute('hidden', '');
    }
  }
  var ua = navigator.userAgent || '', os = '';
  if (/Android/i.test(ua)) os = 'Android';
  else if (/iPhone|iPad|iPod|CrOS/i.test(ua)) os = '';
  else if (/Windows/i.test(ua)) os = 'Windows';
  else if (/Macintosh/i.test(ua)) os = navigator.maxTouchPoints > 1 ? '' : 'Mac';   // an iPad says Macintosh
  else if (/Linux|X11/i.test(ua)) os = 'Linux';
  if (os) show(os);
  if (!ARC_BOOK || !window.fetch || !window.DOMParser) return;
  var home = LIB + '/content/' + encodeURIComponent(ARC_BOOK) + '/index.html';
  var tries = 0;
  function ask() {
    tries++;
    fetch(LIB + '/catalog/v2/entries?count=100000', {cache: 'no-store', credentials: 'omit'}).then(function (r) {
      if (!r.ok) throw new Error('feed');
      return r.text();
    }).then(function (text) {
      var doc = new DOMParser().parseFromString(text, 'application/xml');
      var links = doc.getElementsByTagName('link'), found = false, i, m;
      for (i = 0; i < links.length; i++) {
        m = /^\/content\/([^\/?#]+)$/.exec(links[i].getAttribute('href') || '');
        if (m && decodeURIComponent(m[1]) === ARC_BOOK) found = true;
      }
      if (!found) throw new Error('not the arc');
      if (location.hash === '#stay') show('running');
      else location.replace(home);
    })['catch'](function () {
      if (tries < 400) setTimeout(ask, 3000);   // about 20 minutes
    });
  }
  ask();
})();
"""

LIBRARY_SCRIPT = r"""
(function () {
  // A topic page of the arc's website links here with ?q=<words>: once the
  // damaged books are dropped (or if that can't be done), run that search
  // with the main form.
  // On the library home (kiwix-serve -c), ARC_BOOK names the arc's own
  // collection: without ?q= or ?list, go to its home page if it loaded.
  var done = false;
  function go(loaded) {
    if (done) return;
    done = true;
    var m = /[?&]q=([^&#]*)/.exec(location.search);
    var form = document.querySelector('form.search');
    if (m && form) {
      form.querySelector('input[name="pattern"]').value = decodeURIComponent(m[1].replace(/\+/g, ' '));
      form.submit();
    } else if (!m && ARC_BOOK && loaded && loaded[ARC_BOOK] && !/[?&]list/.test(location.search)) {
      location.replace('/content/' + encodeURIComponent(ARC_BOOK) + '/index.html');
    }
  }
  if (!window.fetch || !window.DOMParser) { go(null); return; }
  fetch('/catalog/v2/entries?count=100000').then(function (r) {
    if (!r.ok) throw new Error('feed');
    return r.text();
  }).then(function (text) {
    var doc = new DOMParser().parseFromString(text, 'application/xml');
    var entries = doc.getElementsByTagName('entry');
    var total = doc.getElementsByTagNameNS('*', 'totalResults')[0];
    if (!entries.length || !total || Number(total.textContent) !== entries.length) { go(null); return; }
    var loaded = {}, links = doc.getElementsByTagName('link'), i, m;
    for (i = 0; i < links.length; i++) {
      m = /^\/content\/([^\/?#]+)$/.exec(links[i].getAttribute('href') || '');
      if (m) loaded[decodeURIComponent(m[1])] = true;
    }
    var inputs = document.querySelectorAll('input[name="books.name"]');
    for (i = 0; i < inputs.length; i++) {
      if (!loaded[inputs[i].value]) inputs[i].parentNode.removeChild(inputs[i]);
    }
    var forms = document.querySelectorAll('form.search');
    for (i = 0; i < forms.length; i++) {
      if (!forms[i].querySelector('input[name="books.name"]')) {
        var p = document.createElement('p');
        p.className = 'damaged';
        p.textContent = 'This search is not available: its collections could not be opened.';
        forms[i].parentNode.replaceChild(p, forms[i]);
      }
    }
    var items = document.querySelectorAll('li[data-book]');
    for (i = 0; i < items.length; i++) {
      if (!loaded[items[i].getAttribute('data-book')]) {
        var s = document.createElement('span');
        s.className = 'damaged';
        s.textContent = ' Could not be opened: this file may be damaged. Check the drive ' +
          '(arc > system > verify.bat) and see MAINTENANCE.txt there.';
        items[i].appendChild(s);
      }
    }
    go(loaded);
  })['catch'](function () { go(null); });
})();
"""


# The drive's own search page (search.html): reads ?q= (a plain form on every
# page sends it), finds every entry of ARC_INDEX holding all the words, best
# first. Plain ES5, accents ignored, results built as text (never as HTML).
SEARCH_SCRIPT = r"""
(function () {
  function fold(s) {
    s = String(s || "").toLowerCase();
    if (s.normalize) { s = s.normalize("NFD").replace(/[̀-ͯ]/g, ""); }
    return s;
  }
  function param(name) {
    var m = new RegExp("[?&]" + name + "=([^&#]*)").exec(location.search);
    if (!m) { return ""; }
    try { return decodeURIComponent(m[1].replace(/\+/g, " ")); } catch (e) { return m[1]; }
  }
  var q = param("q"), box = document.getElementById("q"), list = document.getElementById("results"),
      status = document.getElementById("status"), full = document.getElementById("full");
  if (box) { box.value = q; }
  if (full && q) { full.href = full.href.replace(/\/$/, "") + "/?q=" + encodeURIComponent(q); }
  var words = fold(q).split(/[^a-z0-9]+/), want = [], i, j;
  for (i = 0; i < words.length; i++) { if (words[i].length > 1 || /[0-9]/.test(words[i])) { want.push(words[i]); } }
  if (!want.length) { return; }
  var hits = [];
  for (i = 0; i < ARC_INDEX.length; i++) {
    var e = ARC_INDEX[i], title = " " + fold(e.t), rest = " " + fold(e.k + " " + e.d + " " + e.w), score = 0, ok = true;
    for (j = 0; j < want.length && ok; j++) {
      var w = want[j];
      if (title.indexOf(" " + w) >= 0) { score += 4; }
      else if (title.indexOf(w) >= 0) { score += 3; }
      else if (rest.indexOf(" " + w) >= 0) { score += 2; }
      else if (rest.indexOf(w) >= 0) { score += 1; }
      else { ok = false; }
    }
    if (ok) { hits.push([score, i, e]); }
  }
  hits.sort(function (a, b) { return b[0] - a[0] || a[1] - b[1]; });
  status.textContent = hits.length
    ? hits.length + (hits.length === 1 ? " result" : " results") + " for “" + q + "” on this drive."
    : "Nothing on this drive's own pages for “" + q + "”. Try another word, or search the full library.";
  for (i = 0; i < hits.length && i < 60; i++) {
    var h = hits[i][2], li = document.createElement("li"), kind = document.createElement("div"),
        a = document.createElement("a"), d = document.createElement("div");
    kind.className = "kind"; kind.appendChild(document.createTextNode(h.k));
    a.href = h.u; a.appendChild(document.createTextNode(h.t));
    li.appendChild(kind); li.appendChild(a);
    if (h.d) { d.className = "small"; d.appendChild(document.createTextNode(h.d)); li.appendChild(d); }
    list.appendChild(li);
  }
})();
"""

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

# The card page only: an A6 sheet when printed.
CARD_CSS = """
.card { max-width: 105mm; margin: 0 auto; border: 1px solid var(--line); padding: 4mm 5mm; font-size: .8em; line-height: 1.35; }
.card h1 { font-size: 1.5em; margin: 0 0 .2em; }
.card h2 { font-size: 1em; margin: .6em 0 .15em; padding-bottom: 0; border-bottom: 1px solid #999; }
.card p { margin: .2em 0; }
.card table { border-collapse: collapse; }
.card td { padding: 0 .5em 0 0; vertical-align: top; }
.card .num { font-weight: bold; color: var(--red); white-space: nowrap; }
.card .write { display: inline-block; min-width: 16mm; border-bottom: 1px solid #333; margin-right: .6em; }
.card .sticker { border: 1px dashed #333; padding: 1.5mm 3mm; margin-top: 3mm; font-weight: bold; text-align: center; }
@page { size: 105mm 148mm; margin: 5mm; }   /* A6; Chrome ignores the keyword */
@media print {
  body { max-width: none; padding: 0; font-size: 7.5pt; }
  .noprint, .testbuild, nav.crumbs, footer { display: none !important; }
  .card { border: 0; padding: 0; max-width: none; font-size: 1em; }
  .card .small { color: #333; }
}
"""

# The page "Print a paper copy": a checklist when printed.
PAPER_CSS = """
table.paper { border-collapse: collapse; width: 100%; margin: .4em 0 1.2em; }
table.paper th, table.paper td { border-bottom: 1px solid var(--line); padding: .35em .5em; text-align: left; vertical-align: top; }
table.paper .n { text-align: right; white-space: nowrap; }
table.paper td.tick { width: 1.2em; }
table.paper td.tick::before { content: ""; display: inline-block; width: .9em; height: .9em; border: 1.5px solid currentColor; border-radius: 2px; }
@media print { table.paper th, table.paper td { border-bottom: 1px solid #999; } }
"""

# The look (D17, owner 22 Nov 2026: "learning app"): friendly and bright,
# one colour per subject, system fonts only (nothing to load), dark mode from
# the device's own setting (it saves battery on most phones). Every colour
# behind white text passes 4.5:1.
CSS = """
:root { --bg:#f4f6fb; --card:#fff; --ink:#1b1f2a; --soft:#565e73; --line:#dde2ee; --accent:#2b4fd8;
  --accent-ink:#fff; --red:#b42318; --green:#15803d; --panel:#eef1f8; --shadow:0 2px 8px rgba(20,30,60,.08); }
@media (prefers-color-scheme: dark) {
  :root { --bg:#12151c; --card:#1c212b; --ink:#e8ebf2; --soft:#a9b1c3; --line:#2c3342; --accent:#8fa8ff;
    --accent-ink:#0d1330; --red:#ff8a80; --green:#6fd394; --panel:#232937; --shadow:none; }
}
* { box-sizing: border-box; }
html { background: var(--bg); }
body { margin: 0 auto; max-width: 70em; padding: 0 1.2em 1.5em; font: 18px/1.5 system-ui, -apple-system, "Segoe UI", Roboto, Arial, sans-serif; color: var(--ink); background: var(--bg); }
h1 { font-size: 2em; margin: .3em 0; line-height: 1.2; }
h2 { font-size: 1.4em; margin: 1.6em 0 .6em; line-height: 1.25; }
h3 { margin: .8em 0 .3em; font-size: 1.1em; }
a { color: var(--accent); }
code { background: var(--panel); padding: 0 .3em; border-radius: 4px; }
.topbar { display: flex; flex-wrap: wrap; gap: .6em 1.2em; align-items: center; justify-content: space-between; padding: .9em 0; }
.brand { display: flex; gap: .55em; align-items: center; color: var(--ink); text-decoration: none; font-weight: 800; font-size: 1.15em; }
.brand .mark { width: 2em; height: 2em; border-radius: .6em; background: var(--accent); color: var(--accent-ink); display: flex; align-items: center; justify-content: center; }
.find { display: flex; gap: .4em; flex: 1 1 16em; max-width: 30em; margin: 0; }
.find input[type=search] { flex: 1 1 8em; min-width: 0; font: inherit; font-size: .95em; padding: .5em .9em; border: 2px solid var(--line); border-radius: 999px; background: var(--card); color: var(--ink); }
.find button, .search button { font: inherit; font-size: .95em; font-weight: 700; padding: .5em 1.1em; border: 0; border-radius: 999px; background: var(--accent); color: var(--accent-ink); cursor: pointer; }
.find.big { max-width: none; margin: 1.1em 0 .4em; }
.find.big input[type=search] { font-size: 1.05em; padding: .7em 1.1em; border-color: transparent; }
.find.big button { background: var(--ink); color: var(--bg); padding: .7em 1.4em; }
.emergency { background: var(--red); color: #fff; border-radius: 0 0 14px 14px; padding: .45em 1em; font-size: .9em; margin: 0 0 .2em; }
.emergency a { color: #fff; font-weight: 700; }
@media (prefers-color-scheme: dark) { .emergency { background: #8c1d18; } }
.hero { background: var(--accent); color: var(--accent-ink); border-radius: 24px; padding: 1.6em 1.8em 1.4em; margin-top: .4em; }
.hero h1 { font-size: 2.3em; margin: 0 0 .25em; }
.hero p { font-size: 1.1em; margin: 0; }
.quick { display: flex; flex-wrap: wrap; gap: .5em; margin-top: .9em; }
.quick a { background: var(--card); color: var(--ink); border-radius: 999px; padding: .45em 1em; text-decoration: none; font-weight: 600; }
.panel { background: var(--card); border-radius: 20px; padding: 1.1em 1.4em; box-shadow: var(--shadow); margin: 1.4em 0; }
.panel h2 { margin: 0 0 .3em; font-size: 1.25em; }
.howto { margin: .3em 0; }
.tiles { display: grid; grid-template-columns: repeat(auto-fill, minmax(14em, 1fr)); gap: .8em; }
.tile { display: flex; flex-direction: column; gap: .2em; min-height: 9.5em; padding: 1em 1.1em; border-radius: 20px; background: var(--c, #475569); color: #fff; text-decoration: none; }
.tile .ico { margin-bottom: .3em; }
.tile b { font-size: 1.15em; line-height: 1.25; }
.tile span { font-size: .85em; }
.tile .count { color: #fff; opacity: .92; margin-top: auto; padding-top: .4em; font-weight: 600; }
.tile.empty { --c: #6b7280; }
.tile:focus, .tile:hover, .chip:focus, .chip:hover, .quick a:hover, .quick a:focus { outline: 4px solid #f5c211; outline-offset: 2px; }
.s-health { --c:#c2410c; } .s-food { --c:#15803d; } .s-home { --c:#1d4ed8; } .s-making { --c:#92400e; }
.s-maps-radio { --c:#6d28d9; } .s-science { --c:#0f766e; } .s-society { --c:#7c2d12; } .s-reference { --c:#334155; }
.s-learning { --c:#9d174d; } .s-stories { --c:#9f1239; } .s-arts { --c:#854d0e; }
.band { display: flex; gap: 1em; align-items: center; background: var(--c, var(--accent)); color: #fff; border-radius: 24px; padding: 1.2em 1.5em; margin-top: .4em; }
.band h1 { margin: 0; }
.band p { margin: .2em 0 0; }
.band .ico { flex: 0 0 auto; }
.count { font-size: .85em; color: var(--soft); }
.chips { display: flex; flex-wrap: wrap; gap: .5em; }
.chip { display: inline-block; padding: .45em 1em; background: var(--card); border: 2px solid var(--line); border-radius: 999px; text-decoration: none; font-weight: 600; }
.cards { display: grid; grid-template-columns: repeat(auto-fill, minmax(17em, 1fr)); gap: .8em; padding: 0; margin: 0; list-style: none; }
.tcard { display: block; height: 100%; background: var(--card); border-radius: 18px; padding: 1em 1.2em; box-shadow: var(--shadow); text-decoration: none; color: var(--ink); border-top: 6px solid var(--c, var(--accent)); }
.tcard b { display: block; font-size: 1.1em; color: var(--accent); }
.tcard span { display: block; font-size: .9em; color: var(--soft); margin-top: .2em; }
.crumbs { font-size: .9em; margin: .2em 0 .5em; }
.items, .az { list-style: none; padding: 0; margin: 0; display: grid; gap: .7em; }
.item { background: var(--card); border-radius: 16px; padding: .85em 1.1em; box-shadow: var(--shadow); }
.item > a, .item summary { font-weight: 700; font-size: 1.05em; }
.about { margin: .25em 0 0; font-size: .95em; }
.az li { background: none; box-shadow: none; padding: 0; }
.meta { display: block; font-size: .82em; color: var(--soft); margin-top: .15em; }
.tag { display: inline-block; font-size: .72em; font-weight: 700; padding: .05em .55em; border-radius: 999px; margin-left: .3em; vertical-align: middle; }
.tag.start { background: var(--green); color: #fff; }
.tag.kids { background: #f5c211; color: #111; }
.tag.adv { background: #475569; color: #fff; }
.tag.comm { background: #8a5a00; color: #fff; }
@media (prefers-color-scheme: dark) { .tag.start { background: #15803d; } }
.comm-box { border-left: 6px solid #b58900; padding-left: .8em; }
.intro { background: var(--panel); border-radius: 14px; padding: .7em 1.1em; }
.numbers { background: var(--card); border: 3px solid var(--red); border-radius: 18px; padding: .4em 1.2em; margin: 1em 0; }
.numbers table { border-collapse: collapse; }
.numbers td { padding: .2em .8em .2em 0; vertical-align: top; }
.num { font-size: 1.3em; font-weight: bold; white-space: nowrap; color: var(--red); }
.situations { list-style: none; padding: 0; display: grid; gap: .7em; }
.situations > li { background: var(--card); border-left: 6px solid var(--red); border-radius: 14px; padding: .3em 1.1em .6em; box-shadow: var(--shadow); }
.small { font-size: .85em; color: var(--soft); }
.draft, .testbuild { background: #fff3cd; color: #111; border: 2px dashed #b58900; padding: .5em 1em; border-radius: 10px; }
.note { background: var(--panel); border-left: 6px solid var(--accent); padding: .5em 1em; border-radius: 10px; margin: .5em 0; }
.note pre, .draft pre { white-space: pre-wrap; font: inherit; font-size: .9em; margin: 0; }
details summary { cursor: pointer; color: var(--accent); }
.parts { columns: 2 12em; }
.steps li { margin: .5em 0; }
.toc { display: flex; flex-wrap: wrap; gap: .4em .6em; align-items: center; }
.toc a { background: var(--card); border: 2px solid var(--line); border-radius: 999px; padding: .2em .8em; text-decoration: none; }
.search { display: flex; flex-wrap: wrap; gap: .5em; margin: 1em 0; }
.search input[type=search] { flex: 1 1 14em; font: inherit; padding: .6em 1em; border: 2px solid var(--line); border-radius: 999px; background: var(--card); color: var(--ink); }
.path { border-top: 6px solid var(--c, var(--accent)); }
.path ol { list-style: none; padding: 0; margin: .5em 0 0; display: grid; gap: .7em; }
.path li { display: flex; gap: .8em; align-items: flex-start; }
.stepno { flex: 0 0 2em; height: 2em; border-radius: 50%; background: var(--c, var(--accent)); color: #fff; font-weight: 800; display: flex; align-items: center; justify-content: center; }
.tcard .count { margin: 0 0 .2em; }
.results { list-style: none; padding: 0; display: grid; gap: .6em; }
.results li { background: var(--card); border-radius: 14px; padding: .7em 1.1em; box-shadow: var(--shadow); }
.results .kind { font-size: .78em; font-weight: 700; color: var(--soft); text-transform: uppercase; letter-spacing: .04em; }
.damaged { color: var(--red); font-weight: bold; }
.pic { max-width: 100%; height: auto; display: block; margin: .5em 0; }
footer { margin-top: 3em; padding-top: 1em; border-top: 2px solid var(--line); font-size: .9em; display: grid; gap: .4em; }
footer p { margin: 0; }
@media (max-width: 34em) {
  body { font-size: 17px; padding: 0 .8em 1em; }
  h1, .hero h1 { font-size: 1.65em; }
  .hero, .band { border-radius: 18px; padding: 1.1em 1.1em; }
  .tiles { grid-template-columns: 1fr; gap: .5em; }
  .tile { min-height: 0; flex-direction: row; flex-wrap: wrap; align-items: center; gap: .1em .8em; border-radius: 16px; padding: .7em 1em; }
  .tile .ico { margin: 0; }
  .tile b { flex: 1 1 10em; }
  .tile span:not(.ico):not(.count) { display: none; }
  .tile .count { flex: 1 1 100%; margin: 0; padding: 0; font-weight: 400; }
  .band .ico { display: none; }
}
@media print { footer, .chips, .crumbs, .topbar, .quick, .find, .emergency { display: none !important; }
  body { font-size: 12pt; background: #fff; color: #000; } html { background: #fff; } a { color: #000; }
  .hero, .band, .tile { background: #fff !important; color: #000 !important; border: 1px solid #999; } }
"""

# Subject icons: simple line drawings, drawn in the text colour.
ICONS = {
    "health": '<circle cx="12" cy="12" r="9"/><path d="M12 8v8M8 12h8"/>',
    "food": '<path d="M12 21v-9"/><path d="M12 12c0-4 3-6 7-6 0 4-3 6-7 6z"/><path d="M12 15c0-3-2-5-6-5 0 3 2 5 6 5z"/>',
    "home": '<path d="M3 11l9-7 9 7"/><path d="M5 10v10h14V10"/><path d="M12 12.5c-1.6 2-2.2 3-2.2 4a2.2 2.2 0 004.4 0c0-1-.6-2-2.2-4z"/>',
    "making": '<path d="M14.7 6.3a4 4 0 00-5.4 5.4L4 17l3 3 5.3-5.3a4 4 0 005.4-5.4l-2.5 2.5-2.5-.5-.5-2.5z"/>',
    "maps-radio": '<circle cx="12" cy="12" r="9"/><path d="M15.5 8.5l-2 5-5 2 2-5z"/>',
    "science": '<path d="M9 3h6M10 3v6l-5 9a2 2 0 002 3h10a2 2 0 002-3l-5-9V3"/><path d="M7.5 15h9"/>',
    "society": '<path d="M3 21h18M5 21V10M9.5 21V10M14.5 21V10M19 21V10M2 10l10-6 10 6z"/>',
    "reference": '<path d="M4 5a2 2 0 012-2h13v16H6a2 2 0 00-2 2z"/><path d="M4 19V5"/>',
    "learning": '<path d="M2 9l10-5 10 5-10 5z"/><path d="M6 11v5c0 1 3 3 6 3s6-2 6-3v-5"/>',
    "stories": '<path d="M2 5h7a3 3 0 013 3v12a2 2 0 00-2-2H2z"/><path d="M22 5h-7a3 3 0 00-3 3v12a2 2 0 012-2h8z"/>',
    "arts": '<path d="M9 18V5l12-2v13"/><circle cx="6" cy="18" r="3"/><circle cx="18" cy="16" r="3"/>',
}
LOGO = ('<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" '
        'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M4 16c3-6 13-6 16 0"/>'
        '<path d="M3 16h18l-2 4H5z"/><path d="M12 4v9M12 4l5 5h-5"/></svg>')


def icon(subject, size=30):
    """A subject's icon as inline SVG (decorative), or ''."""
    if subject not in ICONS:
        return ""
    return (f'<span class="ico" aria-hidden="true"><svg width="{size}" height="{size}" viewBox="0 0 24 24" '
            f'fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
            f'{ICONS[subject]}</svg></span>')


# Quick ways in on the home page: (words people would use, topic).
QUICK = [("Treat an injury", "S1"), ("Make water safe", "S2"), ("Grow vegetables", "F1"),
         ("Fix things", "R1"), ("Get ready for a crisis", "S4"), ("Teach a child to read", "T2")]


def build(drive, placed, all_ids, include_drafts=False, version_line="", folder=FRONTDOOR, publishers=None,
          arc_zim=None, edition=None, out=None, overlay=None):
    """Write the website and the text twin; return the drive paths the pages
    link to (for tests). arc_zim: drive path of the arc's own collection, if
    it will be built (named in the Android instructions). out: where to write
    them (the pocket kit), if not the drive itself; overlay: read files there
    first (the kit's own files)."""
    site = Site(Path(drive), placed, all_ids, include_drafts, version_line, Path(folder), publishers,
                arc_zim=arc_zim, edition=edition, overlay=overlay)
    site.build_all()
    drive = Path(out or drive)
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


def build_served(drive, placed, all_ids, version_line="", folder=FRONTDOOR, publishers=None,
                 search_books=(), edition=None, overlay=None):
    """The same pages for the arc's own collection: {zim path: (title, html)},
    and the drive paths they link to (guides and system files to pack)."""
    site = Site(Path(drive), placed, all_ids, False, version_line, Path(folder), publishers,
                served=True, search_books=search_books, edition=edition, overlay=overlay)
    site.build_all()
    pages = {zim_path(rel): (site.titles[rel], text) for rel, text in site.pages.items()}
    return pages, sorted(t for t in site.linked if t not in site.pages)


def guide_page(title, pdf_name, text):
    """Served mode: the readable page a search result opens for a guide (PDF):
    its name, a button to open it, and the start of its text."""
    excerpt = " ".join(text.split()[:120])
    return ('<!DOCTYPE html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
            '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
            f'<title>{esc(title)} · Knowledge Arc</title>\n<style>\n{CSS}</style>\n</head>\n<body>\n'
            '<nav class="crumbs"><a href="/">Home</a></nav>\n'
            f'<h1>{esc(title)}</h1>\n<p><a class="chip" href="{quote(pdf_name)}">Open the guide (PDF)</a></p>\n'
            + (f'<p class="small">How it begins: {esc(excerpt)}…</p>\n' if excerpt else '')
            + '</body>\n</html>\n')


def zim_path(drive_path):
    """Where a drive path lives inside the arc's ZIM: the home page is
    index.html, everything else drops the leading arc/."""
    if drive_path == HTML_NAME:
        return "index.html"
    prefix = cl.ARC + "/"
    return drive_path[len(prefix):] if drive_path.startswith(prefix) else drive_path


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
        if h.startswith("#") or h.startswith(LIBRARY) or h.startswith("/"):
            continue
        out.append(posixpath.normpath(posixpath.join(base, unquote(h.split("#", 1)[0]))))
    return out
