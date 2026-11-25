"""Stage a test version of an edition without downloading the content:
every guide a one-page PDF naming what it stands for, every collection a tiny
real ZIM under its real name, every HTML book a small page; software from
--real (path to real files by drive path) or a tiny placeholder archive.
Usage (with .venv-build's Python, for libzim):
    python stage_test_full.py <repo> <staging> <bundle> [rel=path ...]"""
import csv, hashlib, html, io, json, shutil, sys, tarfile, tempfile, zipfile
from pathlib import Path

repo, staging, bundle = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3]
real = dict(a.split("=", 1) for a in sys.argv[4:])
sys.path.insert(0, str(repo / "scripts"))
import catalog_lib as cl  # noqa: E402
from libzim.writer import Creator, Item, StringProvider, Hint  # noqa: E402

rows = list(csv.DictReader(open(cl.CATALOG, encoding="utf-8")))
want = cl.BUNDLES.index(bundle)


def pdf(lines):
    """A one-page A4 PDF with these lines of text (Helvetica)."""
    def s(t):
        t = t.encode("latin-1", "replace").decode("latin-1")
        return t.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    body, y = [], 780
    for i, line in enumerate(lines):
        size = 20 if i == 0 else 12
        while line:
            cut = line[:70] if size == 12 else line[:45]
            if len(line) > len(cut) and " " in cut:
                cut = cut[:cut.rindex(" ")]
            body.append(f"BT /F1 {size} Tf 60 {y} Td ({s(cut)}) Tj ET")
            y -= size + 8
            line = line[len(cut):].lstrip()
        y -= 8
    stream = "\n".join(body).encode("latin-1")
    objs = [b"<< /Type /Catalog /Pages 2 0 R >>",
            b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Contents 4 0 R "
            b"/Resources << /Font << /F1 5 0 R >> >> >>",
            b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream",
            b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"]
    out = io.BytesIO(); out.write(b"%PDF-1.4\n")
    offs = []
    for i, o in enumerate(objs, 1):
        offs.append(out.tell()); out.write(b"%d 0 obj\n" % i + o + b"\nendobj\n")
    x = out.tell()
    out.write(b"xref\n0 %d\n0000000000 65535 f \n" % (len(objs) + 1))
    for o in offs:
        out.write(b"%010d 00000 n \n" % o)
    out.write(b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objs) + 1, x))
    return out.getvalue()


def note(r):
    size = int(r["size_bytes"]) if r["size_bytes"].isdigit() else 0
    return [r.get("label") or r["title"],
            "TEST VERSION: a stand-in, not the real file.",
            f"The real one: {r['title']} ({r['publisher']}, {r['edition_or_date']})"
            + (f", about {size / 1e6:,.0f} MB." if size else "."),
            r.get("about", ""),
            "make-arc.py downloads the real file when the arc is built for real."]


class Page(Item):
    def __init__(s, path, title, text):
        super().__init__(); s.p, s.t, s.h = path, title, text
    def get_path(s): return s.p
    def get_title(s): return s.t
    def get_mimetype(s): return "text/html"
    def get_contentprovider(s): return StringProvider(s.h)
    def get_hints(s): return {Hint.FRONT_ARTICLE: True}


def zim(r, out):
    lines = [x for x in note(r) if x]
    body = "".join(f"<p>{html.escape(x)}</p>" for x in lines[1:])
    page = (f"<!DOCTYPE html><html><head><meta charset='utf-8'><title>{html.escape(lines[0])}</title></head>"
            f"<body style='font-family:sans-serif;max-width:40em;margin:2em auto'>"
            f"<h1>{html.escape(lines[0])}</h1>{body}</body></html>")
    with tempfile.TemporaryDirectory() as tmp:
        t = Path(tmp) / out.name
        with Creator(str(t)).config_indexing(True, "eng") as c:
            c.set_mainpath("index.html")
            for k, v in {"Name": out.stem, "Title": lines[0][:30], "Description": "Test version stand-in",
                         "Language": "eng", "Creator": r["publisher"], "Publisher": "test",
                         "Date": "2026-11-25"}.items():
                c.add_metadata(k, v)
            c.add_item(Page("index.html", lines[0], page))
        out.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(t, out)
    return out.read_bytes()


def archive(name, member):
    buf = io.BytesIO()
    if name.endswith(".zip"):
        with zipfile.ZipFile(buf, "w") as z:
            z.writestr(member, b"placeholder")
    else:
        with tarfile.open(fileobj=buf, mode="w:xz" if name.endswith(".xz") else "w:gz") as t:
            i = tarfile.TarInfo(member); i.size = 11; i.mode = 0o755
            t.addfile(i, io.BytesIO(b"placeholder"))
    return buf.getvalue()


state, n = {}, 0
for r in rows:
    b = r.get("bundle", "")
    if b not in cl.BUNDLES or cl.BUNDLES.index(b) > want:
        continue
    folder = r["folder"].strip("/")
    name = folder.rsplit("/", 1)[-1]
    files = []
    if folder in real:
        files = [(folder, Path(real[folder]).read_bytes())]
    elif r["format"] == "zim":
        files = [(folder, zim(r, staging / folder))]
    elif cl.is_multi_file(r):
        pinned = cl.file_list(r)
        names = [f["file"] for f in pinned] or [f"chapter-{i:02d}.pdf" for i in range(1, cl.file_count(r) + 1)]
        labels = {f["file"]: f.get("label", "") for f in pinned}
        for x in names:
            lines = note(r); lines[0] = labels.get(x) or x
            if x.endswith(".html"):
                data = ("<!DOCTYPE html><html><head><meta charset='utf-8'><title>" + html.escape(lines[0])
                        + "</title></head><body>" + "".join(f"<p>{html.escape(l)}</p>" for l in lines if l)
                        + "</body></html>").encode("utf-8")
            else:
                data = pdf(lines)
            files.append((f"{folder}/{x}", data))
    elif name.startswith("kiwix-tools_"):
        files = [(folder, archive(name, "kiwix-tools/kiwix-serve" + (".exe" if "_win" in name else "")))]
    elif name.endswith((".zip", ".tar.gz", ".tar.xz")):
        files = [(folder, archive(name, "app/placeholder.txt"))]
    elif r["format"] in ("exe", "apk", "dmg", "appimage"):
        if name.startswith("firefox-setup-"):
            continue   # assemble runs it: only the real one will do
        files = [(folder, b"placeholder")]
    else:
        files = [(folder, pdf(note(r)))]
    for rel, data in files:
        out = staging / rel
        out.parent.mkdir(parents=True, exist_ok=True)
        if not out.exists() or out.read_bytes() != data:
            out.write_bytes(data)
        state[rel] = {"sha256": hashlib.sha256(data).hexdigest(), "size": len(data)}
        n += 1
(staging / ".download-state.json").write_text(json.dumps(state, indent=1), encoding="utf-8")
print(f"staged {n} files for the {bundle} edition")
