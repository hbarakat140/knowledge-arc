"""Scan the official Kiwix catalogue against catalog/coverage.csv and write a
candidates table, so new collections are found by script, not by hand.

    python scripts/scan_kiwix.py                      # fetch the live feed
    python scripts/scan_kiwix.py --feed saved.xml     # use a saved copy

Output: catalog/candidates-kiwix.csv (one row per Kiwix package, best
flavour only) and a per-domain summary on screen. Each package gets:
  status   in-catalog | rejected | candidate | unmatched
  domains  coverage ids whose keywords match its title/summary/name
  flags    community (Q&A, user wikis), subset (part of something we have),
           old (> 4 years), video
Nothing here goes on a drive: a person still decides, and the decision is
recorded in catalog.csv (taken) or rejected.csv (not taken).
"""

import argparse
import csv
import datetime as dt
import re
import sys
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import catalog_lib as cl  # noqa: E402

FEED = "https://opds.library.kiwix.org/catalog/v2/entries?lang=eng&count=-1"
ATOM = "{http://www.w3.org/2005/Atom}"
COVERAGE = cl.REPO / "catalog" / "coverage.csv"
REJECTED = cl.REPO / "catalog" / "rejected.csv"
OUT = cl.REPO / "catalog" / "candidates-kiwix.csv"
FLAVOUR_RANK = ["maxi", "", "nopic", "mini"]   # best first
COMMUNITY = re.compile(r"stackexchange|stack_exchange|mathoverflow|askubuntu|superuser|serverfault|reddit|fandom|wikihow", re.I)
SUBSET = re.compile(r"^wikipedia_en_(?!all\b)|^wiktionary_en_(?!all\b)|^gutenberg_en_lcc|^mdwiki_en_(?!all\b)|_simple_", re.I)
# Large families are reported as one line each instead of flooding the
# per-domain lists: they are decided as a family.
FAMILIES = [
    ("ted", re.compile(r"^ted_"), "TED talk collections (video, multilingual)"),
    ("maps", re.compile(r"^maps_"), "OpenStreetMap regions"),
    ("gutenberg", re.compile(r"^gutenberg_"), "Project Gutenberg subject sets (Library of Congress classes)"),
    ("stack_exchange", re.compile(r"stackexchange|mathoverflow|askubuntu|superuser|serverfault"), "Stack Exchange Q&A sites (community)"),
    ("wikipedia", re.compile(r"^wikipedia_"), "Wikipedia subsets and other languages"),
]


def family(name):
    return next((key for key, pat, _ in FAMILIES if pat.search(name)), "")


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (compatible; offline-family-library-build/1.0)"})
    with urllib.request.urlopen(req, timeout=180, context=cl.ssl_context()) as r:
        return r.read()


def parse_feed(data):
    root = ET.fromstring(data)
    out = []
    for e in root.findall(f"{ATOM}entry"):
        get = lambda tag: (e.findtext(f"{ATOM}{tag}") or "").strip()  # noqa: E731
        acq = next((l for l in e.findall(f"{ATOM}link") if l.get("type") == "application/x-zim"), None)
        out.append({
            "name": get("name"), "flavour": get("flavour"), "title": get("title"),
            "summary": get("summary"), "category": get("category"), "tags": get("tags"),
            "date": get("issued")[:10] or get("updated")[:10],
            "size_bytes": int(acq.get("length", 0)) if acq is not None else 0,
            "meta4": acq.get("href", "") if acq is not None else "",
        })
    return out


def best_flavours(entries):
    best = {}
    for e in entries:
        rank = FLAVOUR_RANK.index(e["flavour"]) if e["flavour"] in FLAVOUR_RANK else len(FLAVOUR_RANK)
        cur = best.get(e["name"])
        if cur is None or rank < cur[0]:
            best[e["name"]] = (rank, e)
    return [e for _, e in best.values()]


def book_key(meta4_url):
    """'.../mdwiki_en_all_maxi_2025-11.zim.meta4' -> 'mdwiki_en_all_maxi'"""
    base = meta4_url.rsplit("/", 1)[-1]
    return re.sub(r"_\d{4}-\d{2}[a-z]?\.zim(\.meta4)?$", "", base)


def compile_domains(rows):
    out = []
    for r in rows:
        pats = [re.compile(r"\b" + k.strip(), re.I) for k in r["keywords"].split(";") if k.strip()]
        out.append((r, pats))
    return out


def classify(e, catalog_keys, rejected, domains, today):
    key = e["name"] + (f"_{e['flavour']}" if e["flavour"] else "")
    text = " ".join((e["title"], e["summary"], e["name"].replace("_", " ").replace(".", " "), e["category"]))
    matched = []
    for r, pats in domains:
        hits = sum(1 for p in pats if p.search(text))
        if hits:
            matched.append((r["id"], hits))
    flags = []
    if COMMUNITY.search(e["name"]) or e["category"] == "stack_exchange":
        flags.append("community")
    if SUBSET.search(e["name"]):
        flags.append("subset")
    if e["category"] == "ted" or re.search(r"youtube|crashcourse|khanacademy", e["name"], re.I):
        flags.append("video")
    try:
        if (today - dt.date.fromisoformat(e["date"])).days > 4 * 365:
            flags.append("old")
    except ValueError:
        pass
    reason = next((why for pat, why in rejected if pat.search(e["name"])), "")
    if key in catalog_keys or e["name"] in catalog_keys:
        status = "in-catalog"
    elif reason:
        status = "rejected"
    elif matched:
        status = "candidate"
    else:
        status = "unmatched"
    return {
        "name": e["name"], "flavour": e["flavour"], "title": e["title"], "category": e["category"],
        "date": e["date"], "size_gb": f"{e['size_bytes'] / 1e9:.2f}",
        "status": status, "domains": ";".join(f"{d}:{h}" for d, h in sorted(matched, key=lambda x: -x[1])),
        "score": max((h for _, h in matched), default=0), "flags": ";".join(flags),
        "family": family(e["name"]), "reason": reason, "summary": e["summary"][:200], "meta4": e["meta4"],
    }


def main(argv=None):
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--feed", type=Path, help="saved OPDS feed instead of fetching it")
    ap.add_argument("--out", type=Path, default=OUT)
    ap.add_argument("--top", type=int, default=6, help="candidates to show per domain")
    args = ap.parse_args(argv)

    data = args.feed.read_bytes() if args.feed else fetch(FEED)
    entries = best_flavours(parse_feed(data))
    _, catalog = cl.read_csv(cl.CATALOG)
    catalog_keys = {book_key(r["source_url"]) for r in catalog if r["source_url"].endswith(".meta4")}
    _, cov = cl.read_csv(COVERAGE)
    domains = compile_domains(cov)
    rejected = [(re.compile(r["pattern"], re.I), r["reason"]) for r in cl.read_csv(REJECTED)[1]]
    today = dt.date.today()

    rows = sorted((classify(e, catalog_keys, rejected, domains, today) for e in entries),
                  key=lambda r: (r["status"], -r["score"], r["name"]))
    cl.write_csv_atomic(args.out, list(rows[0].keys()), rows)

    counts = {}
    for r in rows:
        counts[r["status"]] = counts.get(r["status"], 0) + 1
    print(f"{len(entries)} Kiwix packages (best flavour each): "
          + ", ".join(f"{k} {v}" for k, v in sorted(counts.items())) + f"\nWritten to {args.out}\n")

    for key, _, label in FAMILIES:
        fam = [r for r in rows if r["family"] == key]
        taken = sum(1 for r in fam if r["status"] == "in-catalog")
        print(f"Family {label}: {len(fam)} packages, {taken} in catalog, "
              f"{sum(float(r['size_gb']) for r in fam):.0f} GB in all")
    print()

    for d in cov:
        cands = [r for r in rows if r["status"] == "candidate" and not r["family"]
                 and any(x.split(":")[0] == d["id"] for x in r["domains"].split(";"))
                 and not ({"community", "subset"} & set(r["flags"].split(";")))]
        cands.sort(key=lambda r: -int(next(x.split(":")[1] for x in r["domains"].split(";") if x.startswith(d["id"] + ":"))))
        print(f"{d['id']:<3} {d['status']:<8} {d['domain']}  ({len(cands)} curated candidates)")
        for r in cands[:args.top]:
            print(f"      {r['name']:<45} {r['size_gb']:>7} GB  {r['date']}  {r['flags']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
