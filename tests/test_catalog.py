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

FIELDS = ["id", "title", "publisher", "source_url", "edition_or_date", "download_date",
          "licence", "tier", "folder", "language", "format", "size_bytes", "sha256",
          "text_layer", "reviewer", "bundle", "notes"]
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
            self.assertRegex(i, r"^T[123]-\d{3}$")

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
            self.assertRegex(name, r"^[A-Za-z0-9._-]+\.(pdf|zim)$", r["id"])

    def test_folders_are_in_tier_folders(self):
        top = {"1": "00_EMERGENCY/", "2": "01_LIVING/", "3": "02_KNOWLEDGE/"}
        for r in self.rows:
            self.assertTrue(r["folder"].startswith(top[r["tier"]]), r["id"])

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
        for s in cl.read_csv(cl.REPO / "frontdoor" / "situations.csv")[1]:
            self.assertIn(s["item_id"], by_id, s)
            r = by_id[s["item_id"]]
            self.assertEqual(r["tier"], "1", s)
            self.assertTrue(r["folder"].endswith(".pdf"), s)
            self.assertTrue(s["pdf_page"].isdigit(), s)

    def test_sha256_shape(self):
        for r in self.rows:
            if r["sha256"]:
                self.assertRegex(r["sha256"], r"^[0-9a-f]{64}$", r["id"])


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

    def check(self, pub, reviewer, allow):
        return gate(row(publisher=pub, reviewer=reviewer), self.pubs, allow) is None

    def test_approved_and_signed(self):
        self.assertTrue(self.check("a", "owner 2026-12-01", False))

    def test_unsigned_rows_need_allow_pending(self):
        self.assertFalse(self.check("a", "pending-owner", False))
        self.assertTrue(self.check("a", "pending-owner", True))
        self.assertFalse(self.check("p", "owner", False))
        self.assertTrue(self.check("p", "pending-owner", True))

    def test_never_on_drive(self):
        for pub in ("c", "x"):
            self.assertFalse(self.check(pub, "owner", True))

    def test_item_review_needs_signature_even_when_testing(self):
        self.assertFalse(self.check("r", "pending-owner", True))
        self.assertTrue(self.check("r", "owner", False))

    def test_unknown_publisher(self):
        self.assertFalse(self.check("zz", "owner", True))


if __name__ == "__main__":
    unittest.main()
