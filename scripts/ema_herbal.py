"""Pin the EU herbal monographs (European Medicines Agency, HMPC) as a file
list for download.py: catalog/files/<id>.csv, one line per file.

    python scripts/ema_herbal.py            (writes catalog/files/T2-158.csv)
    python scripts/ema_herbal.py --check    (prints what would change)
    python scripts/ema_herbal.py --verify <download folder>/arc/guides/health/eu-herbal-monographs_ema
                                            (after download.py: reads every file; needs pypdf)

Run while the internet works, when refreshing the catalog; the build itself
only reads the pinned list. For each herbal substance in EMA's own table
(the JSON twin of medicines-output-herbal_medicines-report_en.xlsx), it reads
the substance's page and keeps, of the documents EMA lists there:

  summary     the "summary for the public" (plain English, 2-3 pages)
  monograph   the EU herbal monograph (uses, doses, warnings, interactions)
  statement   a public statement, where EMA found no monograph possible
              (not enough evidence, or a safety concern)

never drafts or superseded versions; when EMA lists more than one final
version, the most recently updated one (dates from EMA's documents table).
EMA limits request rates (HTTP 429): pages are read one at a time, slowly.

Standard library only.
"""

import argparse
import html
import json
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import catalog_lib as cl  # noqa: E402

ROW_ID = "T2-158"
EMA = "https://www.ema.europa.eu"
HERBAL_JSON = f"{EMA}/en/documents/report/medicines-output-herbal_medicines-report-output-json_en.json"
DOCS_JSON = f"{EMA}/en/documents/report/documents-output-non_epar_documents_json-report_en.json"
USER_AGENT = "Mozilla/5.0 (compatible; offline-family-library-build/1.0)"
PAUSE = 2.0
KINDS = {"herbal-summary": "summary", "herbal-monograph": "monograph", "public-statement": "statement"}
LABELS = {"summary": "summary for the public", "monograph": "EU herbal monograph",
          "statement": "public statement"}
ORDER = ["summary", "monograph", "statement"]
FILLER = {"for", "use", "in", "as", "and", "the", "also", "or", "with", "of"}


def get(url, tries=8):
    for n in range(1, tries + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=120, context=cl.ssl_context()) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            if e.code != 429 or n == tries:
                raise
            wait = e.headers.get("Retry-After", "")
            time.sleep(min(int(wait), 300) if wait.isdigit() else min(15 * 2 ** (n - 1), 300))


def slug(text, cap=40):
    """Short, safe file-name stem: lower case, digits and hyphens, at most
    `cap` characters (cut at a hyphen), so paths stay short on any drive."""
    text = html.unescape(text).replace("'", "").replace("’", "").replace(".", "")
    words = [w for w in re.split(r"[^a-z0-9]+", text.lower()) if w and w not in FILLER]
    s = "-".join(words)
    while len(s) > cap and "-" in s:
        s = s.rsplit("-", 1)[0]
    return s[:cap].strip("-")


def plant_name(text):
    """'St. John&#039;s Wort' -> "St. John's Wort"; first letter upper case."""
    text = html.unescape(text).strip()
    return text[:1].upper() + text[1:]


def page_field(page, label):
    """The value after a <dt>label</dt> on an EMA substance page ('' if none)."""
    text = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " | ", page)))
    m = re.search(re.escape(label) + r"\s*\|[\s|]*([^|]+)", text)
    return m.group(1).strip() if m else ""


def name_words(*names):
    """Words a document address should contain for this plant: the genus
    from the botanical name and the first word of the Latin name, both in
    lower case ('Hypericum perforatum L.' -> 'hypericum')."""
    words = set()
    for n in names:
        first = re.split(r"[\s;,(]+", html.unescape(n).strip().lower())[0] if n.strip() else ""
        if len(first) > 3:
            words.add(first)
    return words


def choose(urls, updated):
    """The highest revision of a kind; ties: the most recently updated. (Not
    the date first: EMA re-dates an old version when it stamps it superseded.)"""
    def key(u):
        rev = re.search(r"revision-(\d+)", u)
        return (int(rev.group(1)) if rev else 0, updated.get(u, ""))
    return max(urls, key=key)


def build():
    substances = json.loads(get(HERBAL_JSON))["data"]
    docs = json.loads(get(DOCS_JSON))["data"]
    updated = {d["document_url"]: d.get("last_updated_date") or d.get("first_published_date") or ""
               for d in docs}
    seen, plants = set(), []
    for s in sorted(substances, key=lambda s: html.unescape(s["english_common_name"]).lower()):
        page_url = s["herbal_medicine_url"]
        if page_url in seen:
            continue
        seen.add(page_url)
        time.sleep(PAUSE)
        page = get(page_url).decode("utf-8", "replace")
        # The page's own names: EMA's table has had a row pointing at another plant's page.
        common = page_field(page, "English common name") or s["english_common_name"]
        latin = page_field(page, "Latin name") or s["latin_name"]
        botanical = page_field(page, "Botanical name") or s["botanical_name"]
        found = {}
        for kind_dir, name in sorted(set(re.findall(r'/en/documents/([a-z-]+)/([^"#?]+?\.pdf)', page))):
            # A public statement is sometimes filed with the monographs or reports.
            kind = "statement" if "public-statement" in name else KINDS.get(kind_dir)
            if not kind or name.startswith(("draft", "superseded")) or "superseded" in name:
                continue
            if kind == "statement" and kind_dir not in KINDS and kind_dir != "herbal-report":
                continue
            if kind == "summary" and "summary" not in name:   # EMA has filed a full report here
                continue
            found.setdefault(kind, []).append(f"{EMA}/en/documents/{kind_dir}/{name}")
        if not found:
            print(f"  nothing final: {plant_name(common)} ({s['status']})", flush=True)
            continue
        chosen = {k: choose(found[k], updated) for k in ORDER if k in found}
        if any(set(chosen.values()) == set(p["chosen"].values()) for p in plants):
            print(f"  same documents as an earlier entry, skipped: {plant_name(common)} ({page_url})", flush=True)
            continue
        words = name_words(botanical, latin)
        combination = s.get("combination", "No") != "No" or "combination" in common.lower()
        for k, url in chosen.items():
            if k != "summary" and not combination and words and not any(w[:5] in url for w in words):
                print(f"  CHECK {plant_name(common)}: {k} address names none of {sorted(words)}: {url}", flush=True)
        plants.append({"name": plant_name(common), "latin": html.unescape(latin).strip(), "page": page_url,
                       "chosen": chosen})
        print(f"  {plant_name(common)}: {', '.join(chosen)}", flush=True)

    # Two substances with one common name (e.g. two dandelion root pages):
    # the Latin name goes in both labels, and in the file names.
    count = {}
    for p in plants:
        count[p["name"].lower()] = count.get(p["name"].lower(), 0) + 1
    out, used = [], set()
    for p in plants:
        twin = count[p["name"].lower()] > 1
        label = f"{p['name']} ({p['latin']})" if twin and p["latin"] else p["name"]
        base = slug(f"{p['name']} {p['latin']}" if twin else p["name"], cap=60 if twin else 40)
        while base in used:
            base = slug(base + "-" + p["page"].rstrip("/").rsplit("/", 1)[-1], cap=60)
        used.add(base)
        for k, url in p["chosen"].items():
            out.append({"file": f"{base}_{k}.pdf", "label": f"{label}: {LABELS[k]}",
                        "url": url, "updated": updated.get(url, "")[:10]})
    return out


def verify(folder):
    """Read the downloaded set (needs pypdf): every pinned file is there, has
    text, names its plant on its first pages, is not stamped "Superseded",
    and summaries and statements are short. Returns the problems."""
    import logging
    from pypdf import PdfReader
    logging.getLogger("pypdf").setLevel(logging.ERROR)
    problems = []
    for f in cl.file_list({"id": ROW_ID}):
        path = Path(folder) / f["file"]
        if not path.is_file():
            problems.append(f"{f['file']}: missing")
            continue
        pdf = PdfReader(str(path))
        first = " ".join((pdf.pages[i].extract_text() or "") for i in range(min(2, len(pdf.pages)))).lower()
        words = [w for w in re.split(r"[^a-z]+", f["label"].split(":")[0].lower()) if len(w) > 2]
        words += re.findall(r"(?:monograph|statement)-([a-z]+)-", f["url"])
        kind = f["file"].rsplit("_", 1)[1][:-4]
        if not first.strip():
            problems.append(f"{f['file']}: no text on its first pages")
        elif not any(w[:5] in first for w in words):
            problems.append(f"{f['file']}: first pages name none of {words}")
        if "superseded" in first[:300]:
            problems.append(f"{f['file']}: stamped Superseded")
        if kind in ("summary", "statement") and len(pdf.pages) > 12:
            problems.append(f"{f['file']}: {len(pdf.pages)} pages, too long for a {kind}")
    return problems


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--check", action="store_true", help="print the changes, write nothing")
    ap.add_argument("--verify", metavar="FOLDER",
                    help="instead: read the downloaded set in FOLDER (the item's folder) and report problems")
    args = ap.parse_args(argv)
    if args.verify:
        problems = verify(args.verify)
        print("\n".join(problems) or f"all {len(cl.file_list({'id': ROW_ID}))} files read: no problems")
        return 1 if problems else 0
    rows = build()
    path = cl.FILE_LISTS / f"{ROW_ID}.csv"
    old = {r["file"]: r for r in cl.file_list({"id": ROW_ID})}
    new = {r["file"]: r for r in rows}
    for f in sorted(set(old) | set(new)):
        if f not in new:
            print(f"gone: {f}")
        elif f not in old:
            print(f"new: {f}")
        elif old[f]["url"] != new[f]["url"]:
            print(f"changed: {f}")
    print(f"{len(rows)} files for {len({r['file'].rsplit('_', 1)[0] for r in rows})} substances")
    if not args.check:
        path.parent.mkdir(parents=True, exist_ok=True)
        cl.write_csv_atomic(path, ["file", "label", "url", "updated"], rows)
        print(f"wrote {path.relative_to(cl.REPO)}; set the row's format to \"pdf ({len(rows)} files)\"")


if __name__ == "__main__":
    sys.exit(main())
