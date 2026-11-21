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

A = "01_LIVING/test/a_signed_2026.pdf"
B = "01_LIVING/test/b_pending_2026.pdf"


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
        self.assertIn("TEST BUILD", (self.drive / "99_SYSTEM/VERSION.txt").read_text())

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
        text = (self.drive / "99_SYSTEM/VERSION.txt").read_text(encoding="utf-8")
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
    ZIP = "90_SOFTWARE/windows/kiwix-tools_win-x86_64-9.9.9.zip"

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
        self.assertEqual((self.drive / "90_SOFTWARE/windows/kiwix/kiwix-serve.exe").read_bytes(),
                         b"MZ fake server")
        self.assertFalse((self.drive / "90_SOFTWARE/windows/evil.txt").exists())
        bat = (self.drive / "OPEN-LIBRARY.bat").read_bytes()
        self.assertEqual(bat.count(b"\n"), bat.count(b"\r\n"), "Windows launcher needs CRLF")
        self.assertIn(b"90_SOFTWARE\\windows\\kiwix\\kiwix-serve.exe", bat)
        self.assertNotIn(b"\r\n", (self.drive / "open-library.sh").read_bytes())
        self.assertIn("OPEN-LIBRARY.bat", (self.drive / "START-HERE.html").read_text(encoding="utf-8"))

    def add_zims(self):
        """One checked collection and one community collection."""
        state_path = self.staging / ".download-state.json"
        state = json.loads(state_path.read_text(encoding="utf-8"))
        extra = [("T2-010", "01_LIVING/zim/medicine_en_all_2026-01.zim", "ok", "Medicine wiki"),
                 ("T2-011", "01_LIVING/zim/diy.stackexchange.com_en_all_2026-01.zim", "comm", "Home Q&A")]
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
        page = (self.drive / "99_SYSTEM/library-home.html").read_text(encoding="utf-8")
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
        self.assertIn("90_SOFTWARE/windows/kiwix/kiwix-serve.exe", paths)

    APK = "90_SOFTWARE/android/kiwix-android-9.9.9.apk"

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
        self.assertFalse((self.drive / "90_SOFTWARE/android/kiwix").exists(), "an APK is not unpacked")
        self.assertIn(self.APK, (self.drive / assemble.CHECKSUMS).read_text(encoding="utf-8"))
        page = (self.drive / "START-HERE.html").read_text(encoding="utf-8")
        txt = (self.drive / "START-HERE.txt").read_text(encoding="utf-8-sig")
        self.assertIn("Android phone or tablet", page)
        self.assertIn("kiwix-android-9.9.9.apk", page)
        self.assertIn("<code>01_LIVING/zim</code>", page)
        self.assertIn("90_SOFTWARE > android > kiwix-android-9.9.9.apk", txt)
        self.assertIn("01_LIVING > zim", txt)

    def test_no_android_line_without_app_or_collections(self):
        self.add_apk()          # app but no collections
        self.assemble()
        self.assertNotIn("Android", (self.drive / "START-HERE.html").read_text(encoding="utf-8"))
        self.tmp.cleanup()
        self.setUp()
        self.add_zims()         # collections but no app
        self.assemble()
        self.assertNotIn("Android", (self.drive / "START-HERE.html").read_text(encoding="utf-8"))

    def test_no_server_no_launchers(self):
        self.tmp.cleanup()
        Fixture.setUp(self)   # fresh fixture without the archive
        self.assemble()
        self.assertFalse((self.drive / "OPEN-LIBRARY.bat").exists())


class FrontDoorTest(Fixture):
    def page(self):
        return (self.drive / "START-HERE.html").read_text(encoding="utf-8")

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
        txt = (self.drive / "START-HERE.txt").read_text(encoding="utf-8-sig")
        for text in (page, txt):
            self.assertNotIn("DRAFT-MARKER", text)
            self.assertNotIn("TEST BUILD", text)
            self.assertNotIn("Pending guide", text)
        self.assertIn(A.split("/")[-1] + "#page=3", page)

    def test_checked_notes_show_on_strict_builds(self):
        self.assemble()
        txt = (self.drive / "START-HERE.txt").read_text(encoding="utf-8-sig")
        for text in (self.page(), txt):
            self.assertEqual(text.count("NOTE-MARKER"), 1, "once, under its situation")
            self.assertNotIn("DRAFT, not checked", text)

    def test_note_only_situation_shows_its_note_without_no_guide_line(self):
        with open(self.fd / "situations.csv", "a", encoding="utf-8") as f:
            f.write("09,No phone or internet,,,,test\n")
        (self.fd / "notes" / "09_radio.txt").write_text("RADIO-MARKER listen to the radio", encoding="utf-8")
        self.assemble()
        txt = (self.drive / "START-HERE.txt").read_text(encoding="utf-8-sig")
        for text in (self.page(), txt):
            self.assertEqual(text.count("RADIO-MARKER"), 1)
            section = text[text.index("No phone or internet"):text.index("RADIO-MARKER")]
            self.assertNotIn("No guide for this", section)

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
        self.assertIn("START-HERE.html", sums)
        self.assertIn("START-HERE.txt", sums)

    def test_maintenance_guide_on_drive_and_linked(self):
        self.assemble()
        raw = (self.drive / "99_SYSTEM/MAINTENANCE.txt").read_bytes()
        self.assertEqual(raw.count(b"\n"), raw.count(b"\r\n"), "Notepad-friendly line endings")
        self.assertIn('href="99_SYSTEM/MAINTENANCE.txt"', self.page())
        sums = self.checksums(self.drive)
        self.assertIn("99_SYSTEM/MAINTENANCE.txt", sums)

    def test_text_version_uses_windows_line_endings(self):
        self.assemble()
        raw = (self.drive / "START-HERE.txt").read_bytes()
        self.assertEqual(raw.count(b"\n"), raw.count(b"\r\n"))

    def test_unknown_situation_id_fails(self):
        with open(self.fd / "situations.csv", "a", encoding="utf-8") as f:
            f.write("09,Typo,T9-999,1,x,test\n")
        with self.assertRaises(SystemExit):
            self.assemble()


if __name__ == "__main__":
    unittest.main()
