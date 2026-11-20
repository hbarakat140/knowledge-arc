"""Build 99_SYSTEM/library-home.html: the home page of the library server
(kiwix-serve -c). Called by assemble.py when a library server is on the drive.

Why a custom page: Kiwix's own welcome page has a box that only filters the
list of collections, and the search bar inside a collection searches only that
collection. This page gives the family one search box across the checked
collections, a separate, clearly labelled box for community answers
(CLAUDE.md quality bar), and the list of collections, marking the ones the
search cannot reach (packages built without a full-text index).

No scripts and no external files: the page is served by kiwix-serve, and
search goes to its /search endpoint. A collection's address is
/content/<ZIM file name without .zim>, which is how kiwix-serve names books
passed on its command line (the launchers do that).
"""

import html
import os
import subprocess
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

import frontdoor

HOME = "99_SYSTEM/library-home.html"
KIWIX_MANAGE = "90_SOFTWARE/windows/kiwix/kiwix-manage.exe"
COMMUNITY_STATUS = "item-review-required"


def esc(text):
    return html.escape(text, quote=True)


def zim_facts(drive, rels):
    """{rel: {"ftindex": bool, "lang": str}} read with kiwix-manage when this
    build runs on Windows and the Windows server is on the drive; {} otherwise
    (then every collection is offered to the search, without marks)."""
    tool = drive / KIWIX_MANAGE
    if os.name != "nt" or not tool.is_file() or not rels:
        return {}
    with tempfile.TemporaryDirectory() as tmp:
        lib = Path(tmp) / "library.xml"
        try:
            subprocess.run([str(tool), str(lib), "add", *[str(drive / r) for r in rels]],
                           capture_output=True, timeout=600, check=False)
            root = ET.parse(lib).getroot()
        except (OSError, subprocess.SubprocessError, ET.ParseError):
            return {}
    facts = {}
    for book in root.iter("book"):
        name = Path(book.get("path", "")).name
        tags = book.get("tags", "")
        facts[name] = {"ftindex": "_ftindex:yes" in tags, "lang": book.get("language", "")}
    return {rel: facts[Path(rel).name] for rel in rels if Path(rel).name in facts}


def build(drive, placed, publishers):
    """Write the home page for the ZIM collections in `placed`; return its
    path relative to the drive, or None if there are no collections."""
    drive = Path(drive)
    zims = [r for r in placed if r["format"] == "zim" and (drive / r["folder"]).is_file()]
    if not zims:
        return None
    facts = zim_facts(drive, [r["folder"] for r in zims])

    def book(r):
        return Path(r["folder"]).stem

    def searchable(r):
        f = facts.get(r["folder"])
        # Unknown (no kiwix-manage): offer it; Kiwix simply skips unindexed books.
        return f is None or (f["ftindex"] and f["lang"] == "eng")

    def community(r):
        return publishers.get(r["publisher"], {}).get("status") == COMMUNITY_STATUS

    groups = [
        ("Health and practical life", [r for r in zims if r["tier"] == "2" and not community(r)]),
        ("Encyclopedias, books, courses and maps", [r for r in zims if r["tier"] == "3" and not community(r)]),
    ]
    checked = [r for _, rows in groups for r in rows]
    shared = [r for r in zims if community(r)]

    def form(rows, label, placeholder):
        hidden = "".join(f'<input type="hidden" name="books.name" value="{esc(book(r))}">'
                         for r in rows if searchable(r))
        if not hidden:
            return ""
        return (f'<form class="search" action="/search" method="get">{hidden}'
                f'<input type="search" name="pattern" placeholder="{esc(placeholder)}" '
                f'aria-label="{esc(label)}" required>'
                f'<button type="submit">{esc(label)}</button></form>\n')

    def listing(rows):
        out = ['<ul>']
        for r in sorted(rows, key=lambda r: r["title"].lower()):
            note = ""
            f = facts.get(r["folder"])
            if f is not None and not searchable(r):
                note = ' <span class="small">(open it to browse: not covered by the search box)</span>'
            out.append(f'<li><a href="/content/{esc(book(r))}">{esc(r["title"])}</a>{note}</li>')
        out.append('</ul>\n')
        return "".join(out)

    o = ['<!DOCTYPE html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
         '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
         '<title>Family Library</title>\n<style>\n' + frontdoor.CSS + EXTRA_CSS + '</style>\n</head>\n<body>\n'
         '<header id="top"><h1>Family Library</h1>'
         '<p>Search everything at once, or open a collection below.</p></header>\n']
    o.append(form(checked, "Search the library", "For example: burn, water filter, bread"))
    for heading, rows in groups:
        if rows:
            o.append(f'<h2>{esc(heading)}</h2>\n' + listing(rows))
    if shared:
        o.append('<section class="community"><h2>Community answers</h2>\n'
                 '<p><b>Written by members of the public, not checked by experts.</b> Often useful, '
                 'but check anything important against the guides above.</p>\n')
        o.append(form(shared, "Search community answers", "For example: sourdough, bicycle chain"))
        o.append(listing(shared) + '</section>\n')
    o.append('<p class="small">Inside a collection, the bar at the top searches that collection only. '
             'The house button brings you back here. Emergency guides are in START-HERE.html on the drive.</p>\n'
             '</body>\n</html>\n')
    out = drive / HOME
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("".join(o), encoding="utf-8", newline="")
    return HOME


EXTRA_CSS = """
.search { display: flex; flex-wrap: wrap; gap: .5em; margin: 1em 0; }
.search input[type=search] { flex: 1 1 14em; font: inherit; padding: .5em .7em; border: 2px solid var(--ink); border-radius: 8px; }
.search button { font: inherit; padding: .5em 1em; border: 0; border-radius: 8px; background: var(--blue); color: #fff; }
.community { border-left: 6px solid #b58900; padding-left: 1em; margin-top: 2em; }
"""
