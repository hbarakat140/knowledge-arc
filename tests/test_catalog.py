"""Offline tests: the catalog rules, bundle selection and the quality gate.

    python -m unittest discover -s tests
"""

import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import catalog_lib as cl  # noqa: E402
from assemble import gate  # noqa: E402

FIELDS = ["id", "title", "label", "about", "publisher", "source_url", "edition_or_date", "download_date",
          "licence", "tier", "folder", "language", "format", "size_bytes", "sha256",
          "text_layer", "reviewer", "bundle", "topic", "section", "shelf", "audience", "job", "notes"]
PUB_STATUSES = {"approved", "approved-pending-owner", "candidate",
                "item-review-required", "excluded-licence"}


def row(**kw):
    r = {k: "" for k in FIELDS}
    r.update(kw)
    return r


class CatalogLint(unittest.TestCase):
    """The real catalog must follow the rules in catalog/README.md."""

    @classmethod
    def setUpClass(cls):
        cls.fields, cls.rows = cl.read_csv(cl.CATALOG)
        cls.pubs = {p["id"]: p for p in cl.read_csv(cl.PUBLISHERS)[1]}

    def test_schema(self):
        self.assertEqual(self.fields, FIELDS)

    def test_ids_unique_and_well_formed(self):
        ids = [r["id"] for r in self.rows]
        self.assertEqual(len(ids), len(set(ids)))
        for i in ids:
            self.assertRegex(i, r"^T[1239]-\d{3}$")

    def test_pinned_file_lists(self):
        """catalog/files/<id>.csv: a multi-file row with exactly that many
        files, safe unique file names, a label and an https address each."""
        by_id = {r["id"]: r for r in self.rows}
        for path in sorted(cl.FILE_LISTS.glob("*.csv")):
            r = by_id.get(path.stem)
            self.assertIsNotNone(r, f"{path.name}: no catalog row")
            fields, files = cl.read_csv(path)
            self.assertEqual(fields, ["file", "label", "url", "updated"], path.name)
            self.assertEqual(len(files), cl.file_count(r), f"{path.name}: count differs from the row's format")
            names = [f["file"] for f in files]
            self.assertEqual(len(names), len(set(names)), path.name)
            for f in files:
                self.assertRegex(f["file"], cl.SAFE_FILE_NAME, path.name)
                self.assertTrue(f["label"].strip(), f["file"])
                self.assertTrue(f["url"].startswith("https://"), f["file"])

    def test_tier_matches_id(self):
        for r in self.rows:
            self.assertEqual(r["tier"], r["id"][1], r["id"])

    def test_every_publisher_exists(self):
        for r in self.rows:
            self.assertIn(r["publisher"], self.pubs, r["id"])

    def test_publisher_statuses_known(self):
        for p in self.pubs.values():
            self.assertIn(p["status"], PUB_STATUSES, p["id"])

    def test_bundles(self):
        for r in self.rows:
            self.assertIn(r["bundle"], cl.BUNDLES + ["decision"], r["id"])

    def test_language_is_english(self):
        for r in self.rows:
            self.assertEqual(r["language"], "en", r["id"])

    def test_single_files_have_plain_file_names(self):
        for r in self.rows:
            if cl.is_multi_file(r):
                self.assertFalse(re.search(r"\.\w+$", r["folder"]), r["id"])
                continue
            name = r["folder"].rsplit("/", 1)[-1]
            self.assertRegex(name, r"^[A-Za-z0-9._-]+\.(pdf|zim|zip|tar\.gz|tar\.xz|apk|exe|dmg|appimage)$", r["id"])

    def test_folders_follow_the_drive_layout(self):
        """PDFs in arc/guides/<home subject>/ (one optional subfolder),
        collections flat in arc/collections/, software in arc/software/<os>/."""
        subject = {c["id"]: c["subject"] for c in cl.read_csv(cl.COVERAGE)[1]}
        for r in self.rows:
            parts = r["folder"].split("/")
            if r["shelf"] == "software":
                self.assertEqual(parts[:2], ["arc", "software"], r["id"])
                self.assertIn(parts[2], ("windows", "mac", "linux", "android"), r["id"])
                self.assertEqual(len(parts), 4, r["id"])
            elif r["format"] == "zim":
                self.assertEqual(parts[:2], ["arc", "collections"], r["id"])
                self.assertEqual(len(parts), 3, r["id"])
            else:
                self.assertEqual(parts[:3], ["arc", "guides", subject[cl.topics(r)[0]]], r["id"])
                self.assertIn(len(parts), (4, 5), r["id"])

    def test_tier1_never_needs_software(self):
        for r in self.rows:
            if r["tier"] == "1":
                self.assertIn(r["format"].split()[0], ("pdf", "html"), r["id"])

    def test_no_two_rows_share_a_path(self):
        folders = [r["folder"] for r in self.rows]
        self.assertEqual(len(folders), len(set(folders)))

    def test_replaces_points_at_real_rows(self):
        ids = {r["id"] for r in self.rows}
        for r in self.rows:
            self.assertLessEqual(cl.replaced_ids(r), ids, r["id"])

    def test_front_door_situations_point_at_tier1_pdfs(self):
        by_id = {r["id"]: r for r in self.rows}
        notes = {p.stem.split("_", 1)[0] for p in (cl.REPO / "frontdoor" / "notes").glob("*.txt")}
        for s in cl.read_csv(cl.REPO / "frontdoor" / "situations.csv")[1]:
            if not s["item_id"]:
                # Note-only situation: no link, so it needs a checked note.
                self.assertEqual(s["pdf_page"], "", s)
                self.assertIn(s["order"], notes, s)
                continue
            self.assertIn(s["item_id"], by_id, s)
            r = by_id[s["item_id"]]
            self.assertEqual(r["tier"], "1", s)
            self.assertTrue(r["folder"].endswith(".pdf"), s)
            self.assertTrue(s["pdf_page"].isdigit(), s)

    def test_sha256_shape(self):
        for r in self.rows:
            if r["sha256"]:
                self.assertRegex(r["sha256"], r"^[0-9a-f]{64}$", r["id"])


class NavigationTags(unittest.TestCase):
    """Subjects, topics, shelves, audience and job drive the website's pages."""

    @classmethod
    def setUpClass(cls):
        cls.rows = cl.read_csv(cl.CATALOG)[1]
        cls.subjects = cl.read_csv(cl.SUBJECTS)[1]
        cls.coverage = cl.read_csv(cl.COVERAGE)[1]

    def test_subjects(self):
        ids = [s["id"] for s in self.subjects]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual([s["order"] for s in self.subjects],
                         [str(n) for n in range(1, len(ids) + 1)])
        for s in self.subjects:
            self.assertRegex(s["id"], r"^[a-z]+(-[a-z]+)*$")
            self.assertTrue(s["label"] and s["description"], s["id"])

    def test_every_topic_has_a_subject(self):
        ids = {s["id"] for s in self.subjects}
        for c in self.coverage:
            self.assertIn(c["subject"], ids, c["id"])

    def test_every_subject_has_a_topic(self):
        used = {c["subject"] for c in self.coverage}
        for s in self.subjects:
            self.assertIn(s["id"], used, s["id"])

    def test_row_tags(self):
        areas = {c["id"] for c in self.coverage}
        for r in self.rows:
            self.assertIn(r["shelf"], cl.SHELVES, r["id"])
            self.assertIn(r["audience"], cl.AUDIENCES, r["id"])
            ts = cl.topics(r)
            self.assertEqual(len(ts), len(set(ts)), r["id"])
            if r["shelf"] == "software":
                self.assertEqual((ts, r["job"]), ([], ""), r["id"])
                continue
            self.assertTrue(ts, r["id"])
            self.assertLessEqual(set(ts), areas, r["id"])
            self.assertIn(r["job"], cl.JOBS, r["id"])

    def test_display_names_are_unique(self):
        """People see the label (else the title): no two items may look alike."""
        names = [r["label"] or r["title"] for r in self.rows if r["shelf"] != "software"]
        dupes = sorted({n for n in names if names.count(n) > 1})
        self.assertEqual(dupes, [])

    def test_sections_belong_to_the_home_topic(self):
        topics = {c["id"]: c for c in self.coverage}
        used = set()
        for r in self.rows:
            if r["section"]:
                home = cl.topics(r)[0]
                self.assertIn(r["section"], cl.sections(topics[home]), r["id"])
                used.add((home, r["section"]))
        for c in self.coverage:
            names = cl.sections(c)
            self.assertEqual(len(names), len(set(names)), c["id"])
            for name in names:
                self.assertIn((c["id"], name), used, f"{c['id']}: section '{name}' has no items")

    def test_every_topic_has_search_words(self):
        for c in self.coverage:
            words = [w for w in c["search"].split(";") if w]
            self.assertTrue(words, c["id"])
            for w in words:
                self.assertRegex(w, r"^[A-Za-z][A-Za-z '-]*$", c["id"])

    def test_situations_point_at_topics(self):
        areas = {c["id"] for c in self.coverage}
        for s in cl.read_csv(cl.REPO / "frontdoor" / "situations.csv")[1]:
            self.assertIn(s["topic"], areas, s)

    def test_about_lines(self):
        """`about`: what is inside, shown under each guide; short, and never
        on a program."""
        for r in self.rows:
            self.assertLessEqual(len(r["about"]), 150, r["id"])
            self.assertEqual(r["about"], r["about"].strip(), r["id"])
            if r["shelf"] == "software":
                self.assertEqual(r["about"], "", r["id"])

    def test_learning_paths(self):
        """frontdoor/paths.csv: real items and topics, steps 1, 2, 3... per
        path, one title and topic per path, a short reason and a check date
        for every step (each step held to the same standard as situations)."""
        areas = {c["id"] for c in self.coverage}
        ids = {r["id"] for r in self.rows}
        paths = {}
        for s in cl.read_csv(cl.REPO / "frontdoor" / "paths.csv")[1]:
            self.assertIn(s["item_id"], ids, s)
            self.assertIn(s["topic"], areas, s)
            self.assertTrue(s["why"].strip() and s["checked"].strip(), s)
            self.assertLessEqual(len(s["why"]), 140, s)
            paths.setdefault(s["path"], []).append(s)
        self.assertTrue(paths)
        for name, steps in paths.items():
            self.assertEqual([int(s["step"]) for s in steps], list(range(1, len(steps) + 1)), name)
            self.assertEqual(len({(s["title"], s["topic"]) for s in steps}), 1, name)
            self.assertGreaterEqual(len(steps), 2, name)

    def test_topics_match_coverage(self):
        """A row's topics and coverage.csv covered_by say the same thing."""
        tagged = {c["id"]: {r["id"] for r in self.rows if c["id"] in cl.topics(r)}
                  for c in self.coverage}
        for c in self.coverage:
            listed = set(filter(None, c["covered_by"].split(";")))
            self.assertEqual(listed, tagged[c["id"]], c["id"])


class CoverageLint(unittest.TestCase):
    """catalog/coverage.csv and catalog/rejected.csv drive the scan."""

    def test_coverage_map(self):
        import re as _re
        ids = {r["id"] for r in cl.read_csv(cl.CATALOG)[1]}
        rows = cl.read_csv(cl.REPO / "catalog" / "coverage.csv")[1]
        self.assertEqual(len(rows), len({r["id"] for r in rows}))
        for r in rows:
            self.assertIn(r["layer"], {"survive", "sustain", "rebuild", "understand", "teach", "culture"}, r["id"])
            self.assertIn(r["status"], {"good", "partial", "gap"}, r["id"])
            for item in filter(None, r["covered_by"].split(";")):
                self.assertIn(item, ids, r["id"])
            for kw in filter(None, r["keywords"].split(";")):
                _re.compile(kw)

    def test_rejected_patterns_compile(self):
        import re as _re
        for r in cl.read_csv(cl.REPO / "catalog" / "rejected.csv")[1]:
            _re.compile(r["pattern"])
            self.assertTrue(r["reason"])


class Selection(unittest.TestCase):
    rows = [
        row(id="T1-001", bundle="core"),
        row(id="T3-030", bundle="standard"),
        row(id="T3-031", bundle="standard"),
        row(id="T3-036", bundle="full", notes="In the full bundle this REPLACES T3-030..T3-031."),
        row(id="T3-040", bundle="core"),
        row(id="T3-041", bundle="full", notes="REPLACES T3-040."),
        row(id="T2-090", bundle="decision"),
    ]

    def ids(self, **kw):
        return [r["id"] for r in cl.select(self.rows, **kw)]

    def test_bundles_are_cumulative(self):
        self.assertEqual(self.ids(bundle="core"), ["T1-001", "T3-040"])
        self.assertEqual(self.ids(bundle="standard"), ["T1-001", "T3-030", "T3-031", "T3-040"])

    def test_full_applies_replacements(self):
        self.assertEqual(self.ids(bundle="full"), ["T1-001", "T3-036", "T3-041"])

    def test_pocket_is_below_core_and_its_small_copy_is_replaced(self):
        rows = [row(id="T1-001", bundle="pocket"),
                row(id="T3-070", bundle="pocket"),
                row(id="T3-001", bundle="core", notes="From core up this REPLACES T3-070."),
                row(id="T3-040", bundle="core")]
        ids = lambda b: [r["id"] for r in cl.select(rows, bundle=b)]
        self.assertEqual(ids("pocket"), ["T1-001", "T3-070"])
        self.assertEqual(ids("core"), ["T1-001", "T3-001", "T3-040"])
        self.assertEqual(ids("full"), ["T1-001", "T3-001", "T3-040"])

    def test_real_pocket_fits_a_32_gb_card(self):
        _, rows = cl.read_csv(cl.CATALOG)
        pocket = cl.select(rows, "pocket")
        ids = {r["id"] for r in pocket}
        self.assertIn("T3-070", ids)
        self.assertNotIn("T3-001", ids)
        self.assertIn("T2-001", ids, "the medical encyclopedia")
        self.assertTrue({r["id"] for r in rows if r["shelf"] == "software" and r["bundle"] != "decision"} <= ids,
                        "everything needed to run it")
        # Every single document (PDF) goes in the pocket edition: they are small.
        # Except big documents the owner placed in core and up, one by one:
        # two OpenStax textbooks (22 Nov 2026); four more OpenStax books, the
        # NIST time book and the EU soil atlas (23 Nov 2026, case by case).
        big_books = {"T2-153", "T3-075", "T3-078", "T3-079", "T3-080", "T3-081", "T2-212", "T2-230"}
        self.assertEqual({r["bundle"] for r in rows if r["id"] in big_books}, {"core"})
        docs = [r["id"] for r in rows if not r["format"].startswith("zim") and r["bundle"] != "decision"
                and r["id"] not in big_books]
        self.assertEqual([i for i in docs if i not in ids], [], "documents outside the pocket edition")
        # 32 GB cards hold about 31.9e9 bytes; leave room for the guides
        # without a size, the arc's own collection and the unpacked programs.
        self.assertLess(sum(int(r["size_bytes"] or 0) for r in pocket), 27e9)

    def test_all_keeps_replaced_rows_for_the_archive(self):
        self.assertEqual(self.ids(bundle="all"), ["T1-001", "T3-030", "T3-031", "T3-036", "T3-040", "T3-041"])

    def test_decision_rows_never_picked_by_bundle(self):
        self.assertNotIn("T2-090", self.ids(bundle="full"))

    def test_explicit_ids(self):
        self.assertEqual(self.ids(ids=["T2-090"]), ["T2-090"])
        with self.assertRaises(SystemExit):
            self.ids(ids=["T9-999"])

    def test_file_count(self):
        self.assertEqual(cl.file_count(row(format="pdf (32 files)")), 32)
        self.assertEqual(cl.file_count(row(format="pdf")), 1)


class QualityGate(unittest.TestCase):
    pubs = {"a": {"status": "approved"}, "p": {"status": "approved-pending-owner"},
            "c": {"status": "candidate"}, "x": {"status": "excluded-licence"},
            "r": {"status": "item-review-required"}}

    def check(self, pub, reviewer):
        return gate(row(publisher=pub, reviewer=reviewer), self.pubs) is None

    def test_the_catalog_is_the_gate(self):
        """Owner, 21 Nov 2026: every catalog row goes on; sign-offs are a record."""
        for pub in ("a", "p", "r"):
            for reviewer in ("owner 2026-12-01", "pending-owner", ""):
                self.assertTrue(self.check(pub, reviewer), (pub, reviewer))

    def test_never_on_drive(self):
        for pub in ("c", "x"):
            self.assertFalse(self.check(pub, "owner"))

    def test_unknown_publisher(self):
        self.assertFalse(self.check("zz", "owner"))


if __name__ == "__main__":
    unittest.main()
