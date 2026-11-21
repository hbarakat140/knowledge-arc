"""Pack the arc's own collection: the website's pages (full-library version),
the guides (PDFs) and a few system files into one ZIM, with the guides' text
in the search index. kiwix-serve then shows the arc as one website with one
search, and the Kiwix app on Android shows the same subjects.

Optional build dependencies (never needed by people using a drive):
    python -m venv .venv-build
    .venv-build/Scripts/python -m pip install -r requirements-build.txt
    .venv-build/Scripts/python scripts/assemble.py ...
Without them assemble.py still builds everything else and says the arc's
collection was skipped.

The file goes in arc/site/ with the other generated pages (not in
arc/collections/, which holds only catalog items), so assemble.py fingerprints
it, mirror.py copies it, and --prune never touches it. Its bytes change on
every build (libzim stamps it), so every mirror copies it again.
"""

import glob
import logging
import os
import shutil
import struct
import zlib
from pathlib import Path

BOOK = "knowledge-arc_en_all"          # the book's name in kiwix-serve addresses
FILE_NAME = f"{BOOK}.zim"

MIMETYPES = {".html": "text/html", ".pdf": "application/pdf", ".csv": "text/csv",
             ".txt": "text/plain", ".png": "image/png"}


def available():
    """(True, "") if libzim and pypdf can be imported, else (False, why)."""
    try:
        import libzim.writer  # noqa: F401
        import pypdf  # noqa: F401
    except ImportError as e:
        return False, (f"{e.name or e} is not installed: the arc's own collection (one search over the "
                       "subjects and the guides' text) was skipped. See scripts/arczim.py.")
    return True, ""


def icon_png(size=48, rgb=(26, 95, 180)):
    """A plain square PNG for the library's book list (stdlib only)."""
    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xffffffff)
    row = b"\x00" + bytes(rgb) * size
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", size, size, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(row * size)) + chunk(b"IEND", b""))


def pdf_text(path):
    """The PDF's text for the search index ('' if it has none or can't be read)."""
    from pypdf import PdfReader
    logging.getLogger("pypdf").setLevel(logging.ERROR)
    try:
        return " ".join((page.extract_text() or "") for page in PdfReader(str(path)).pages)
    except Exception:   # a damaged or scanned PDF still goes in, just without text
        return ""


def build(out, pages, files, title, description, date, guide_page=None):
    """Write the ZIM to `out`.
    pages: {zim path: (title, html)}; "index.html" is the main page.
    files: [(zim path, source file, title)].
    guide_page(title, pdf_name, text) -> html: for each PDF, a small page at
    <pdf path>.html that links to it and carries its text in the search index,
    so a search result is a readable page (kiwix shows snippets from the stored
    item, and a PDF's bytes are not readable). Returns the number of entries."""
    from libzim.writer import Creator, FileProvider, Hint, IndexData, Item, StringProvider

    class Index(IndexData):
        def __init__(self, title, text):
            self.title, self.text = title, text

        def has_indexdata(self):
            return bool(self.text.strip())

        def get_title(self):
            return self.title

        def get_content(self):
            return self.text

        def get_keywords(self):
            return ""

        def get_wordcount(self):
            return len(self.text.split())

    class Page(Item):
        # No get_indexdata: libzim indexes the HTML itself. (Defining it and
        # returning None would switch indexing off for the page.)
        def __init__(self, path, title, html):
            super().__init__()
            self.path, self.title, self.html = path, title, html

        def get_path(self):
            return self.path

        def get_title(self):
            return self.title

        def get_mimetype(self):
            return "text/html"

        def get_contentprovider(self):
            return StringProvider(self.html)

        def get_hints(self):
            return {Hint.FRONT_ARTICLE: True}

    class GuidePage(Page):
        """Indexed with its PDF's text instead of its own short HTML."""
        def __init__(self, path, title, html, text):
            super().__init__(path, title, html)
            self.text = text

        def get_indexdata(self):
            return Index(self.title, self.text or self.title)

    class File(Item):
        def __init__(self, path, src, title):
            super().__init__()
            self.path, self.src, self.title = path, Path(src), title
            self.mime = MIMETYPES.get(self.src.suffix.lower(), "application/octet-stream")
            self.text = pdf_text(self.src) if self.mime == "application/pdf" else ""

        def get_path(self):
            return self.path

        def get_title(self):
            return self.title

        def get_mimetype(self):
            return self.mime

        def get_contentprovider(self):
            return FileProvider(str(self.src))

        def get_hints(self):
            # Already compressed. Not a front article: its guide page is.
            return {Hint.FRONT_ARTICLE: False, Hint.COMPRESS: False}

        def get_indexdata(self):
            return None   # never index raw PDF bytes; the guide page carries the text

    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_name(out.name + ".part")
    if tmp.exists():
        tmp.unlink()
    with Creator(str(tmp)).config_indexing(True, "eng").config_verbose(False) as c:
        c.set_mainpath("index.html")
        for key, value in {"Name": BOOK, "Title": title, "Description": description[:80],
                           "Language": "eng", "Creator": "Knowledge Arc", "Publisher": "Knowledge Arc",
                           "Date": date, "Tags": "_ftindex:yes;_category:other"}.items():
            c.add_metadata(key, value)
        c.add_metadata("Illustration_48x48@1", icon_png(), "image/png")
        for path, (page_title, html) in pages.items():
            c.add_item(Page(path, page_title, html))
        guides = 0
        for path, src, file_title in files:
            item = File(path, src, file_title)
            c.add_item(item)
            if guide_page and item.mime == "application/pdf":
                c.add_item(GuidePage(path + ".html", file_title,
                                     guide_page(file_title, path.rsplit("/", 1)[-1], item.text), item.text))
                guides += 1
    os.replace(tmp, out)
    # libzim (on Windows at least) leaves its working index files next to the
    # .part file; they must not land on the drive.
    for left in out.parent.glob(glob.escape(tmp.name) + "_*"):
        shutil.rmtree(left, ignore_errors=True) if left.is_dir() else left.unlink(missing_ok=True)
    return len(pages) + len(files) + guides
