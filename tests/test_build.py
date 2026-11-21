"""Offline end-to-end tests for assemble.py and mirror.py, using small fake
PDFs in temporary folders. No network.

    python -m unittest discover -s tests
"""

import contextlib
import csv
import hashlib
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import assemble  # noqa: E402
import frontdoor  # noqa: E402
import mirror  # noqa: E402
from test_catalog import FIELDS, row  # noqa: E402

A = "arc/guides/home/a_signed_2026.pdf"
B = "arc/guides/home/b_pending_2026.pdf"
HTML = "1 START-HERE.html"
TXT = "arc/START-HERE.txt"
BAT = "2 Open full library (Windows).bat"
COMMAND = "2 Open full library (Mac).command"


def quiet(fn, *args):
    with contextlib.redirect_stdout(io.StringIO()) as out:
        code = fn(*args)
    return code, out.getvalue()


class Fixture(unittest.TestCase):
    """A staging folder with two fake PDFs (one signed, one pending), a
    catalog, publishers and a small front-door folder."""
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.staging, self.drive, self.copy = root / "staging", root / "drive", root / "copy"
        state = {}
        for rel, body in ((A, b"%PDF-1.4 signed item\n" * 50), (B, b"%PDF-1.4 pending item\n" * 50)):
            p = self.staging / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(body)
            st = p.stat()
            state[rel] = {"size": st.st_size, "mtime_ns": st.st_mtime_ns,
                          "sha256": hashlib.sha256(body).hexdigest()}
        (self.staging / ".download-state.json").write_text(json.dumps(state), encoding="utf-8")
        self.sha = {rel: e["sha256"] for rel, e in state.items()}

        self.catalog = root / "catalog.csv"
        self.publishers = root / "publishers.csv"
        rows = [row(id="T2-001", title="Signed", publisher="ok", folder=A, format="pdf",
                    tier="2", bundle="core", reviewer="owner 2026-11-18"),
                row(id="T2-002", title="Pending", publisher="pend", folder=B, format="pdf",
                    tier="2", bundle="core", reviewer="pending-owner")]
        with open(self.catalog, "w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=FIELDS, lineterminator="\n")
            w.writeheader()
            w.writerows(rows)
        with open(self.publishers, "w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=["id", "status"], lineterminator="\n")
            w.writeheader()
            w.writerows([{"id": "ok", "status": "approved"}, {"id": "pend", "status": "approved-pending-owner"}])

        # A small front-door folder: one situation pointing at the signed item.
        self.fd = root / "frontdoor"
        (self.fd / "drafts").mkdir(parents=True)
        (self.fd / "notes").mkdir(parents=True)
        (self.fd / "situations.csv").write_text(
            "order,situation,item_id,pdf_page,label,checked\n"
            "06,Water may be unsafe to drink,T2-001,3,Signed guide,test\n"
            "06,Water may be unsafe to drink,T2-002,2,Pending guide,test\n", encoding="utf-8")
        (self.fd / "numbers.csv").write_text("number,what,source,checked\n112,All emergencies,x,test\n",
                                             encoding="utf-8")
        (self.fd / "drafts" / "06_water-metric.txt").write_text("DRAFT-MARKER bleach dose", encoding="utf-8")
        (self.fd / "notes" / "06_water-boil.txt").write_text("NOTE-MARKER boil 1 minute", encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def assemble(self, *extra):
        return quiet(assemble.main, ["--staging", str(self.staging), "--drive", str(self.drive),
                                     "--bundle", "core", "--catalog", str(self.catalog),
                                     "--publishers", str(self.publishers),
                                     "--frontdoor", str(self.fd), *extra])

    def checksums(self, drive):
        text = (drive / assemble.CHECKSUMS).read_text(encoding="utf-8")
        return {line[66:]: line[:64] for line in text.splitlines()}


class BuildTest(Fixture):
    def test_strict_build_takes_only_signed_items(self):
        code, out = self.assemble()
        self.assertEqual(code, 0, out)
        self.assertTrue((self.drive / A).exists())
        self.assertFalse((self.drive / B).exists())
        self.assertEqual(self.checksums(self.drive)[A], self.sha[A])

    def test_bit_rot_with_unchanged_date_is_caught_and_repaired(self):
        self.assemble()
        target = self.drive / A
        st = target.stat()
        data = bytearray(target.read_bytes())
        data[100] ^= 0xFF
        target.write_bytes(data)
        os.utime(target, ns=(st.st_atime_ns, st.st_mtime_ns))  # rot keeps the date

        code, out = self.assemble()
        self.assertEqual(code, 1, "a repaired file must be reported")
        self.assertIn("repaired", out)
        self.assertEqual(hashlib.sha256(target.read_bytes()).hexdigest(), self.sha[A])
        self.assertEqual(self.checksums(self.drive)[A], self.sha[A])

    def test_leftovers_from_a_test_build_are_not_fingerprinted_or_mirrored(self):
        code, out = self.assemble("--allow-pending")
        self.assertTrue((self.drive / B).exists())
        self.assertIn("TEST BUILD", (self.drive / "arc/system/VERSION.txt").read_text())

        code, out = self.assemble()  # strict build on the same drive
        self.assertEqual(code, 1, "leftover files must be reported")
        self.assertNotIn(B, self.checksums(self.drive))

        code, out = quiet(mirror.main, ["--master", str(self.drive), "--copy", str(self.copy)])
        self.assertEqual(code, 0, out)
        self.assertTrue((self.copy / A).exists())
        self.assertFalse((self.copy / B).exists())

        code, out = self.assemble("--prune")
        self.assertEqual(code, 0, out)
        self.assertFalse((self.drive / B).exists())

    def test_version_log_keeps_history(self):
        self.assemble("--note", "first")
        self.assemble("--note", "second")
        text = (self.drive / "arc/system/VERSION.txt").read_text(encoding="utf-8")
        self.assertLess(text.index("Changes: second"), text.index("Changes: first"))

    def test_mirror_catches_damage_on_the_copy(self):
        self.assemble()
        quiet(mirror.main, ["--master", str(self.drive), "--copy", str(self.copy)])
        target = self.copy / A
        st = target.stat()
        data = bytearray(target.read_bytes())
        data[10] ^= 0xFF
        target.write_bytes(data)
        os.utime(target, ns=(st.st_atime_ns, st.st_mtime_ns))
        code, out = quiet(mirror.main, ["--master", str(self.drive), "--copy", str(self.copy)])
        self.assertEqual(code, 1)
        self.assertIn("DAMAGED", out)


class LibraryServerTest(Fixture):
    """A signed kiwix-tools archive: unpacked next to itself, launchers added."""
    ZIP = "arc/software/windows/kiwix-tools_win-x86_64-9.9.9.zip"

    def setUp(self):
        super().setUp()
        import zipfile
        p = self.staging / self.ZIP
        p.parent.mkdir(parents=True)
        with zipfile.ZipFile(p, "w") as z:
            z.writestr("kiwix-tools_win-x86_64-9.9.9/kiwix-serve.exe", b"MZ fake server")
            z.writestr("../evil.txt", b"must not escape the target folder")
        body = p.read_bytes()
        state_path = self.staging / ".download-state.json"
        state = json.loads(state_path.read_text(encoding="utf-8"))
        state[self.ZIP] = {"size": len(body), "mtime_ns": p.stat().st_mtime_ns,
                           "sha256": hashlib.sha256(body).hexdigest()}
        state_path.write_text(json.dumps(state), encoding="utf-8")
        with open(self.catalog, "a", encoding="utf-8", newline="") as f:
            csv.DictWriter(f, fieldnames=FIELDS, lineterminator="\n").writerow(
                row(id="T9-001", title="Kiwix", publisher="ok", folder=self.ZIP, format="zip",
                    tier="9", bundle="core", reviewer="owner 2026-11-20"))

    def test_server_unpacked_and_launchers_added(self):
        code, out = self.assemble()
        self.assertEqual(code, 0, out)
        self.assertEqual((self.drive / "arc/software/windows/kiwix/kiwix-serve.exe").read_bytes(),
                         b"MZ fake server")
        self.assertFalse((self.drive / "arc/software/windows/evil.txt").exists())
        bat = (self.drive / BAT).read_bytes()
        self.assertEqual(bat.count(b"\n"), bat.count(b"\r\n"), "Windows launcher needs CRLF")
        self.assertIn(b"arc\\software\\windows\\kiwix\\kiwix-serve.exe", bat)
        self.assertIn(b"arc/open-full-library.sh", (self.drive / COMMAND).read_bytes())
        self.assertNotIn(b"\r\n", (self.drive / "arc/open-full-library.sh").read_bytes())
        self.assertIn("2 Open full library (Windows)", (self.drive / HTML).read_text(encoding="utf-8"))

    def test_top_of_the_drive_holds_only_the_entry(self):
        code, out = self.assemble()
        self.assertEqual(code, 0, out)
        self.assertEqual(sorted(p.name for p in self.drive.iterdir()), [HTML, COMMAND, BAT, "arc"])

    def test_recipe_copy_works_without_git_and_never_from_the_drive_itself(self):
        src = Path(self.tmp.name) / "recipe-copy"       # like arc/system/recipe: no .git
        (src / "scripts" / "__pycache__").mkdir(parents=True)
        (src / "scripts" / "assemble.py").write_text("x", encoding="utf-8")
        (src / "scripts" / "__pycache__" / "assemble.cpython-312.pyc").write_bytes(b"x")
        (src / "NEXT-SESSION.md").write_text("owner notes", encoding="utf-8")
        self.assertEqual(assemble.copy_recipe(self.drive, src), 1)
        recipe = self.drive / assemble.RECIPE
        self.assertTrue((recipe / "scripts" / "assemble.py").is_file())
        self.assertFalse((recipe / "scripts" / "__pycache__").exists())
        self.assertFalse((recipe / "NEXT-SESSION.md").exists())
        with self.assertRaises(ValueError):
            assemble.copy_recipe(self.drive, recipe)
        self.assertTrue((recipe / "scripts" / "assemble.py").is_file(), "nothing deleted")

    def test_stray_files_at_the_top_are_reported_not_fingerprinted(self):
        self.drive.mkdir(parents=True)
        (self.drive / "old-notes.txt").write_text("someone's file", encoding="utf-8")
        code, out = self.assemble()
        self.assertEqual(code, 1, out)
        self.assertIn("old-notes.txt", out)
        self.assertTrue((self.drive / "old-notes.txt").exists(), "never deleted")
        self.assertNotIn("old-notes.txt", self.checksums(self.drive))

    def test_recipe_copied_without_owner_notes(self):
        self.assemble()
        recipe = self.drive / assemble.RECIPE
        self.assertTrue((recipe / "CLAUDE.md").is_file())
        self.assertTrue((recipe / "catalog" / "catalog.csv").is_file())
        self.assertTrue((recipe / "scripts" / "assemble.py").is_file())
        self.assertFalse((recipe / "NEXT-SESSION.md").exists())
        self.assertIn(f"{assemble.RECIPE}/CLAUDE.md", self.checksums(self.drive))

    def add_zims(self):
        """One checked collection and one community collection."""
        state_path = self.staging / ".download-state.json"
        state = json.loads(state_path.read_text(encoding="utf-8"))
        extra = [("T2-010", "arc/collections/medicine_en_all_2026-01.zim", "ok", "Medicine wiki"),
                 ("T2-011", "arc/collections/diy.stackexchange.com_en_all_2026-01.zim", "comm", "Home Q&A")]
        with open(self.catalog, "a", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=FIELDS, lineterminator="\n")
            for rid, rel, pub, title in extra:
                p = self.staging / rel
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_bytes(b"ZIM\x04 fake " + rel.encode())
                state[rel] = {"size": p.stat().st_size, "mtime_ns": p.stat().st_mtime_ns,
                              "sha256": hashlib.sha256(p.read_bytes()).hexdigest()}
                w.writerow(row(id=rid, title=title, publisher=pub, folder=rel, format="zim",
                               tier="2", bundle="core", reviewer="owner 2026-11-20"))
        state_path.write_text(json.dumps(state), encoding="utf-8")
        with open(self.publishers, "a", encoding="utf-8", newline="") as f:
            f.write("comm,item-review-required\n")

    def test_library_home_page_separates_community_answers(self):
        self.add_zims()
        code, out = self.assemble()
        self.assertEqual(code, 0, out)
        page = (self.drive / "arc/system/library-home.html").read_text(encoding="utf-8")
        main, community = page.split("Community answers", 1)
        self.assertIn('value="medicine_en_all_2026-01"', main)
        self.assertNotIn("stackexchange", main, "community books stay out of the main search")
        self.assertIn('value="diy.stackexchange.com_en_all_2026-01"', community)
        self.assertIn("not checked by experts", community)
        self.assertIn('href="/content/medicine_en_all_2026-01"', page)
        # The inline script only trims damaged books; the static list is the fallback.
        self.assertIn('<li data-book="medicine_en_all_2026-01">', page)
        self.assertEqual(page.count("<script"), 1)
        for bad in ("http:", "https:", "src=", "//cdn", "<link"):
            self.assertNotIn(bad, page)

    def test_each_file_fingerprinted_once(self):
        self.assemble()
        paths = [line[66:] for line in
                 (self.drive / assemble.CHECKSUMS).read_text(encoding="utf-8").splitlines()]
        self.assertEqual(len(paths), len(set(paths)))
        self.assertIn(self.ZIP, paths)
        self.assertIn("arc/software/windows/kiwix/kiwix-serve.exe", paths)

    APK = "arc/software/android/kiwix-android-9.9.9.apk"

    def add_apk(self):
        p = self.staging / self.APK
        p.parent.mkdir(parents=True)
        p.write_bytes(b"PK\x03\x04 fake android app")
        state_path = self.staging / ".download-state.json"
        state = json.loads(state_path.read_text(encoding="utf-8"))
        state[self.APK] = {"size": p.stat().st_size, "mtime_ns": p.stat().st_mtime_ns,
                           "sha256": hashlib.sha256(p.read_bytes()).hexdigest()}
        state_path.write_text(json.dumps(state), encoding="utf-8")
        with open(self.catalog, "a", encoding="utf-8", newline="") as f:
            csv.DictWriter(f, fieldnames=FIELDS, lineterminator="\n").writerow(
                row(id="T9-005", title="Kiwix Android", publisher="ok", folder=self.APK, format="apk",
                    tier="9", bundle="core", reviewer="owner 2026-11-20"))

    def test_android_app_copied_as_is_and_explained(self):
        self.add_apk()
        self.add_zims()
        code, out = self.assemble()
        self.assertEqual(code, 0, out)
        self.assertEqual((self.drive / self.APK).read_bytes(), b"PK\x03\x04 fake android app")
        self.assertFalse((self.drive / "arc/software/android/kiwix").exists(), "an APK is not unpacked")
        self.assertIn(self.APK, (self.drive / assemble.CHECKSUMS).read_text(encoding="utf-8"))
        page = (self.drive / HTML).read_text(encoding="utf-8")
        txt = (self.drive / TXT).read_text(encoding="utf-8-sig")
        self.assertIn("Android phone or tablet", page)
        self.assertIn("kiwix-android-9.9.9.apk", page)
        self.assertIn("<code>arc/collections</code>", page)
        self.assertIn("arc > software > android > kiwix-android-9.9.9.apk", txt)
        self.assertIn("arc > collections", txt)

    def test_no_android_line_without_app_or_collections(self):
        self.add_apk()          # app but no collections
        self.assemble()
        self.assertNotIn("Android", (self.drive / HTML).read_text(encoding="utf-8"))
        self.tmp.cleanup()
        self.setUp()
        self.add_zims()         # collections but no app
        self.assemble()
        self.assertNotIn("Android", (self.drive / HTML).read_text(encoding="utf-8"))

    def test_no_server_no_launchers(self):
        self.tmp.cleanup()
        Fixture.setUp(self)   # fresh fixture without the archive
        self.assemble()
        self.assertFalse((self.drive / BAT).exists())


class FrontDoorTest(Fixture):
    def page(self):
        return (self.drive / HTML).read_text(encoding="utf-8")

    def test_every_link_resolves_to_a_file_on_the_drive(self):
        for extra in ((), ("--allow-pending",)):
            self.assemble(*extra)
            links = frontdoor.links_in(self.page())
            self.assertTrue(links)
            for rel in links:
                self.assertTrue((self.drive / rel).is_file(), f"broken link {rel} ({extra})")

    def test_no_external_references(self):
        self.assemble("--allow-pending")
        for bad in ("http:", "https:", "//", "<script", "@import", "url("):
            self.assertNotIn(bad, self.page())

    def test_strict_build_has_no_drafts_and_no_unsigned_items(self):
        self.assemble()
        page = self.page()
        txt = (self.drive / TXT).read_text(encoding="utf-8-sig")
        for text in (page, txt):
            self.assertNotIn("DRAFT-MARKER", text)
            self.assertNotIn("TEST BUILD", text)
            self.assertNotIn("Pending guide", text)
        self.assertIn(A.split("/")[-1] + "#page=3", page)

    def test_checked_notes_show_on_strict_builds(self):
        self.assemble()
        txt = (self.drive / TXT).read_text(encoding="utf-8-sig")
        for text in (self.page(), txt):
            self.assertEqual(text.count("NOTE-MARKER"), 1, "once, under its situation")
            self.assertNotIn("DRAFT, not checked", text)

    def test_note_only_situation_shows_its_note_without_no_guide_line(self):
        with open(self.fd / "situations.csv", "a", encoding="utf-8") as f:
            f.write("09,No phone or internet,,,,test\n")
        (self.fd / "notes" / "09_radio.txt").write_text("RADIO-MARKER listen to the radio", encoding="utf-8")
        self.assemble()
        txt = (self.drive / TXT).read_text(encoding="utf-8-sig")
        for text in (self.page(), txt):
            self.assertEqual(text.count("RADIO-MARKER"), 1)
            section = text[text.index("No phone or internet"):text.index("RADIO-MARKER")]
            self.assertNotIn("No guide for this", section)

    def add_pdfs(self, items):
        """items: (id, rel, title, tier, topic). Staged and catalogued, signed."""
        state_path = self.staging / ".download-state.json"
        state = json.loads(state_path.read_text(encoding="utf-8"))
        with open(self.catalog, "a", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=FIELDS, lineterminator="\n")
            for rid, rel, title, tier, topic in items:
                p = self.staging / rel
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_bytes(b"%PDF-1.4 " + rel.encode())
                state[rel] = {"size": p.stat().st_size, "mtime_ns": p.stat().st_mtime_ns,
                              "sha256": hashlib.sha256(p.read_bytes()).hexdigest()}
                w.writerow(row(id=rid, title=title, publisher="ok", folder=rel, format="pdf",
                               tier=tier, topic=topic, bundle="core", reviewer="owner 2026-11-21"))
        state_path.write_text(json.dumps(state), encoding="utf-8")

    def test_first_aid_manuals_listed_once_in_emergency(self):
        manual = "arc/guides/health/first-aid-manual_2025.pdf"
        sheet = "arc/guides/home/water-sheet_2024.pdf"
        self.add_pdfs([("T1-001", manual, "MANUAL-MARKER", "1", "S1"),
                       ("T1-002", sheet, "SHEET-MARKER", "1", "S2")])
        code, out = self.assemble()
        self.assertEqual(code, 0, out)
        page = self.page()
        manuals = page[page.index("Complete first-aid manuals"):page.index('id="daily"')]
        self.assertIn("MANUAL-MARKER", manuals)
        self.assertNotIn("SHEET-MARKER", manuals)
        self.assertEqual(page.count("MANUAL-MARKER"), 1, "Tier 1 stays off Daily life")

    def test_reading_books_show_under_daily_life_in_catalog_order(self):
        state_path = self.staging / ".download-state.json"
        state = json.loads(state_path.read_text(encoding="utf-8"))
        guide = "arc/guides/learning/learning-to-read/guide_2007.pdf"
        book = "arc/guides/learning/learning-to-read/book-01_2016.pdf"
        other = "arc/guides/science/maths_2020.pdf"   # its subject's heading comes first
        with open(self.catalog, "a", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=FIELDS, lineterminator="\n")
            for rid, rel, title in (("T3-001", guide, "GUIDE-MARKER phonics guide"),
                                    ("T3-002", book, "BOOK-MARKER book 1"),
                                    ("T3-003", other, "MATHS-MARKER")):
                p = self.staging / rel
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_bytes(b"%PDF-1.4 " + rel.encode())
                state[rel] = {"size": p.stat().st_size, "mtime_ns": p.stat().st_mtime_ns,
                              "sha256": hashlib.sha256(p.read_bytes()).hexdigest()}
                w.writerow(row(id=rid, title=title, publisher="ok", folder=rel, format="pdf",
                               tier="3", bundle="core", reviewer="owner 2026-11-21"))
        state_path.write_text(json.dumps(state), encoding="utf-8")
        code, out = self.assemble()
        self.assertEqual(code, 0, out)
        txt = (self.drive / TXT).read_text(encoding="utf-8-sig")
        for text, start, end in ((self.page(), 'id="daily"', 'id="library"'),
                                 (txt, "== DAILY LIFE ==", "== ENCYCLOPEDIA")):
            daily = text[text.index(start):text.index(end)]
            self.assertIn("Teaching children to read", daily)
            self.assertIn("Phase Three", daily, "the intro with the phase mapping")
            self.assertLess(daily.index("GUIDE-MARKER"), daily.index("BOOK-MARKER"))
            self.assertIn("Science, maths &", daily)
            self.assertLess(daily.index("MATHS-MARKER"), daily.index("Teaching children to read"))
        self.assertIn(f'href="{guide}"', self.page())
        self.assertIn("arc > guides > learning > learning-to-read > book-01_2016.pdf", txt)

    def test_note_for_an_unknown_situation_stops_the_build(self):
        (self.fd / "notes" / "99_orphan.txt").write_text("orphan", encoding="utf-8")
        with self.assertRaises(SystemExit):
            self.assemble()

    def test_test_build_shows_drafts_and_says_so(self):
        self.assemble("--allow-pending")
        self.assertIn("DRAFT-MARKER", self.page())
        self.assertIn("TEST BUILD", self.page())

    def test_front_door_is_fingerprinted(self):
        self.assemble()
        sums = self.checksums(self.drive)
        self.assertIn(HTML, sums)
        self.assertIn(TXT, sums)

    def test_maintenance_guide_on_drive_and_linked(self):
        self.assemble()
        raw = (self.drive / "arc/system/MAINTENANCE.txt").read_bytes()
        self.assertEqual(raw.count(b"\n"), raw.count(b"\r\n"), "Notepad-friendly line endings")
        self.assertIn('href="arc/system/MAINTENANCE.txt"', self.page())
        sums = self.checksums(self.drive)
        self.assertIn("arc/system/MAINTENANCE.txt", sums)

    def test_text_version_uses_windows_line_endings(self):
        self.assemble()
        raw = (self.drive / TXT).read_bytes()
        self.assertEqual(raw.count(b"\n"), raw.count(b"\r\n"))

    def test_unknown_situation_id_fails(self):
        with open(self.fd / "situations.csv", "a", encoding="utf-8") as f:
            f.write("09,Typo,T9-999,1,x,test\n")
        with self.assertRaises(SystemExit):
            self.assemble()


if __name__ == "__main__":
    unittest.main()
