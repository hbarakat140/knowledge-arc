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
import arczim  # noqa: E402
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
        tags = dict(topic="S2", shelf="guides", audience="all", job="primary")
        rows = [row(id="T2-001", title="Signed", publisher="ok", folder=A, format="pdf",
                    tier="2", bundle="core", reviewer="owner 2026-11-18", **tags),
                row(id="T2-002", title="Pending", publisher="pend", folder=B, format="pdf",
                    tier="2", bundle="core", reviewer="pending-owner", **tags)]
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
            "order,situation,topic,item_id,pdf_page,label,checked\n"
            "06,Water may be unsafe to drink,S2,T2-001,3,Signed guide,test\n"
            "06,Water may be unsafe to drink,S2,T2-002,2,Pending guide,test\n", encoding="utf-8")
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
                    tier="9", bundle="core", reviewer="owner 2026-11-20", shelf="software", audience="all"))

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
                               tier="2", bundle="core", reviewer="owner 2026-11-20",
                               topic="H2", shelf="community" if pub == "comm" else "encyclopedias",
                               audience="all", job="depth"))
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

    def test_tree_unpack_keeps_folders_and_refuses_escapes(self):
        import zipfile
        src = Path(self.tmp.name) / "app.zip"
        with zipfile.ZipFile(src, "w") as z:
            z.writestr("app/app.exe", b"MZ")
            z.writestr("app/plugins/one.dll", b"MZ")
            z.writestr("app/../../escape.txt", b"no")
        out = Path(self.tmp.name) / "unpacked"
        assemble.unpack(src, out, "tree")
        self.assertEqual((out / "app.exe").read_bytes(), b"MZ", "the shared top folder is dropped")
        self.assertTrue((out / "plugins" / "one.dll").is_file(), "subfolders are kept")
        self.assertFalse((Path(self.tmp.name) / "escape.txt").exists())

    def test_launcher_opens_the_drives_firefox_and_fallbacks_are_listed(self):
        self.assemble()
        bat = (self.drive / BAT).read_bytes()
        self.assertIn(b"arc\\software\\windows\\firefox\\firefox.exe", bat)
        self.assertIn(b"-no-remote -profile", bat)
        self.assertTrue((self.drive / "arc/software/firefox-user.js").is_file())
        self.assertIn(b"software/mac/firefox-*.dmg", (self.drive / "arc/open-full-library.sh").read_bytes())
        # A fake SumatraPDF next to the server: named on the How to use page.
        exe = self.drive / "arc/software/windows/sumatrapdf/SumatraPDF-9-64.exe"
        exe.parent.mkdir(parents=True)
        exe.write_bytes(b"MZ")
        self.assemble()
        how = (self.drive / "arc/site/how.html").read_text(encoding="utf-8")
        self.assertIn("The guides (PDFs) will not open", how)
        self.assertIn("arc &gt; software &gt; windows &gt; sumatrapdf &gt; SumatraPDF-9-64.exe", how)

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
                    tier="9", bundle="core", reviewer="owner 2026-11-20", shelf="software", audience="all"))

    def test_android_app_copied_as_is_and_explained(self):
        self.add_apk()
        self.add_zims()
        code, out = self.assemble()
        self.assertEqual(code, 0, out)
        self.assertEqual((self.drive / self.APK).read_bytes(), b"PK\x03\x04 fake android app")
        self.assertFalse((self.drive / "arc/software/android/kiwix").exists(), "an APK is not unpacked")
        self.assertIn(self.APK, (self.drive / assemble.CHECKSUMS).read_text(encoding="utf-8"))
        page = (self.drive / "arc/site/how.html").read_text(encoding="utf-8")
        txt = (self.drive / TXT).read_text(encoding="utf-8-sig")
        self.assertIn("Android phone or tablet", page)
        self.assertIn("kiwix-android-9.9.9.apk", page)
        self.assertIn("<code>arc/collections</code>", page)
        self.assertIn("arc > software > android > kiwix-android-9.9.9.apk", txt)
        self.assertIn("arc > collections", txt)

    def test_no_android_line_without_app_or_collections(self):
        self.add_apk()          # app but no collections
        self.assemble()
        self.assertNotIn("Android", (self.drive / "arc/site/how.html").read_text(encoding="utf-8"))
        self.tmp.cleanup()
        self.setUp()
        self.add_zims()         # collections but no app
        self.assemble()
        self.assertNotIn("Android", (self.drive / "arc/site/how.html").read_text(encoding="utf-8"))

    def test_no_server_no_launchers(self):
        self.tmp.cleanup()
        Fixture.setUp(self)   # fresh fixture without the archive
        self.assemble()
        self.assertFalse((self.drive / BAT).exists())


class FrontDoorTest(Fixture):
    """The website: 1 START-HERE.html, arc/site/*.html and arc/START-HERE.txt."""

    def page(self, rel=HTML):
        return (self.drive / rel).read_text(encoding="utf-8")

    def txt(self):
        return (self.drive / TXT).read_text(encoding="utf-8-sig")

    def all_pages(self):
        return {rel: self.page(rel) for rel in frontdoor.pages(self.drive)}

    def add_pdfs(self, items):
        """items: (id, rel, title, tier, tags). Staged and catalogued, signed."""
        state_path = self.staging / ".download-state.json"
        state = json.loads(state_path.read_text(encoding="utf-8"))
        with open(self.catalog, "a", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=FIELDS, lineterminator="\n")
            for rid, rel, title, tier, tags in items:
                p = self.staging / rel
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_bytes(b"%PDF-1.4 " + rel.encode())
                state[rel] = {"size": p.stat().st_size, "mtime_ns": p.stat().st_mtime_ns,
                              "sha256": hashlib.sha256(p.read_bytes()).hexdigest()}
                w.writerow(row(id=rid, title=title, publisher="ok", folder=rel, format="pdf",
                               tier=tier, bundle="core", reviewer="owner 2026-11-21",
                               **{"shelf": "guides", "audience": "all", "job": "primary", **tags}))
        state_path.write_text(json.dumps(state), encoding="utf-8")

    def test_one_page_per_subject_and_topic(self):
        self.assemble()
        pages = frontdoor.pages(self.drive)
        self.assertEqual(pages[0], HTML)
        subjects = [s["id"] for s in frontdoor.read(frontdoor.cl.SUBJECTS)]
        topics = [c["id"] for c in frontdoor.read(frontdoor.cl.COVERAGE)]
        for s in subjects:
            self.assertIn(f"arc/site/subject-{s}.html", pages)
        for c in topics:
            self.assertIn(f"arc/site/topic-{c}.html", pages)
        self.assertEqual(self.page().count('<a class="tile'), len(subjects))

    def test_every_link_resolves_to_a_file_on_the_drive(self):
        for extra in ((), ("--allow-pending",)):
            self.assemble(*extra)
            for rel, text in self.all_pages().items():
                links = frontdoor.links_in(text, rel)
                self.assertTrue(links, rel)
                for target in links:
                    self.assertTrue((self.drive / target).is_file(), f"broken link {target} in {rel} ({extra})")

    def test_no_external_references(self):
        self.assemble("--allow-pending")
        for rel, text in self.all_pages().items():
            for bad in ("https:", "<script", "@import", "url(", "src="):
                self.assertNotIn(bad, text, rel)
            # The only absolute address is the full library on this computer.
            self.assertEqual(text.count("http:"), text.count("http://127.0.0.1:8642"), rel)

    def test_strict_build_has_no_drafts_and_no_unsigned_items(self):
        self.assemble()
        texts = list(self.all_pages().values()) + [self.txt()]
        for text in texts:
            self.assertNotIn("DRAFT-MARKER", text)
            self.assertNotIn("TEST BUILD", text)
            self.assertNotIn("Pending guide", text)
        self.assertIn(A.split("/")[-1] + "#page=3", self.page("arc/site/topic-S2.html"))

    def test_checked_notes_show_once_under_their_topic(self):
        self.assemble()
        self.assertEqual(sum(t.count("NOTE-MARKER") for t in self.all_pages().values()), 1)
        self.assertEqual(self.page("arc/site/topic-S2.html").count("NOTE-MARKER"), 1)
        self.assertEqual(self.txt().count("NOTE-MARKER"), 1)
        self.assertNotIn("DRAFT, not checked", self.page("arc/site/topic-S2.html"))

    def test_note_only_situation_shows_under_its_topic(self):
        with open(self.fd / "situations.csv", "a", encoding="utf-8") as f:
            f.write("09,No phone or internet,C1,,,,test\n")
        (self.fd / "notes" / "09_radio.txt").write_text("RADIO-MARKER listen to the radio", encoding="utf-8")
        self.assemble()
        self.assertEqual(self.page("arc/site/topic-C1.html").count("RADIO-MARKER"), 1)
        self.assertEqual(self.txt().count("RADIO-MARKER"), 1)

    def test_first_aid_topic_has_numbers_and_its_start_here_items(self):
        manual = "arc/guides/health/first-aid-manual_2025.pdf"
        sheet = "arc/guides/home/water-sheet_2024.pdf"
        self.add_pdfs([("T1-001", manual, "MANUAL-MARKER", "1", {"topic": "S1"}),
                       ("T1-002", sheet, "SHEET-MARKER", "1", {"topic": "S2", "label": "SHEET-LABEL"})])
        code, out = self.assemble()
        self.assertEqual(code, 0, out)
        s1 = self.page("arc/site/topic-S1.html")
        self.assertIn("All emergencies", s1, "the numbers table")
        self.assertLess(s1.index("Start here"), s1.index("MANUAL-MARKER"))
        self.assertNotIn("SHEET", s1)
        s2 = self.page("arc/site/topic-S2.html")
        self.assertIn("SHEET-LABEL", s2, "the label is shown instead of the title")
        self.assertNotIn("SHEET-MARKER", s2)
        self.assertIn("topic-S1.html", self.page(), "the home page points to first aid")

    def test_reading_books_on_their_topic_in_catalog_order(self):
        guide = "arc/guides/learning/learning-to-read/guide_2007.pdf"
        book = "arc/guides/learning/learning-to-read/book-01_2016.pdf"
        other = "arc/guides/science/maths_2020.pdf"
        self.add_pdfs([("T3-001", guide, "GUIDE-MARKER phonics guide", "3", {"topic": "T2"}),
                       ("T3-002", book, "BOOK-MARKER book 1", "3", {"topic": "T2", "audience": "children",
                                                                     "shelf": "books"}),
                       ("T3-003", other, "MATHS-MARKER", "3", {"topic": "U3"})])
        code, out = self.assemble()
        self.assertEqual(code, 0, out)
        t2 = self.page("arc/site/topic-T2.html")
        self.assertIn("Phase Three", t2, "the intro with the phase mapping")
        self.assertLess(t2.index("GUIDE-MARKER"), t2.index("BOOK-MARKER"))
        self.assertNotIn("MATHS-MARKER", t2)
        self.assertIn("MATHS-MARKER", self.page("arc/site/topic-U3.html"))
        self.assertIn("BOOK-MARKER", self.page("arc/site/children.html"))
        self.assertIn("BOOK-MARKER", self.page("arc/site/shelf-books.html"))
        self.assertIn("arc > guides > learning > learning-to-read > book-01_2016.pdf", self.txt())
        a_z = self.page("arc/site/a-z.html")
        self.assertLess(a_z.index("BOOK-MARKER"), a_z.index("MATHS-MARKER"))

    def test_big_topics_are_split_into_sections(self):
        self.add_pdfs([("T2-201", "arc/guides/food/pigs_2020.pdf", "PIGS-MARKER", "2",
                        {"topic": "F2", "section": "Pigs"}),
                       ("T2-202", "arc/guides/food/hens_2011.pdf", "HENS-MARKER", "2",
                        {"topic": "F2", "section": "Poultry"}),
                       ("T2-203", "arc/guides/food/misc_2011.pdf", "MISC-MARKER", "2",
                        {"topic": "F2", "job": "depth"})])
        code, out = self.assemble()
        self.assertEqual(code, 0, out)
        f2 = self.page("arc/site/topic-F2.html")
        # Sections follow coverage.csv's order (Poultry before Pigs), unsectioned items last.
        self.assertLess(f2.index(">Poultry</h2>"), f2.index("HENS-MARKER"))
        self.assertLess(f2.index("HENS-MARKER"), f2.index(">Pigs</h2>"))
        self.assertLess(f2.index(">Pigs</h2>"), f2.index("PIGS-MARKER"))
        self.assertLess(f2.index("PIGS-MARKER"), f2.index(">More on this topic</h2>"))
        self.assertLess(f2.index(">More on this topic</h2>"), f2.index("MISC-MARKER"))
        self.assertNotIn(">Bees</h2>", f2, "empty sections are left out")
        self.assertIn("[Poultry]", self.txt())

    def test_community_items_are_labelled(self):
        self.add_pdfs([("T2-090", "arc/guides/food/qa_2026.pdf", "QA-MARKER", "2",
                        {"topic": "F3", "shelf": "community", "job": "depth"})])
        self.assemble()
        f3 = self.page("arc/site/topic-F3.html")
        self.assertIn("not checked by experts", f3[f3.index("QA-MARKER"):])
        self.assertIn("not checked by experts", self.page("arc/site/shelf-community.html"))

    def test_note_for_an_unknown_situation_stops_the_build(self):
        (self.fd / "notes" / "99_orphan.txt").write_text("orphan", encoding="utf-8")
        with self.assertRaises(SystemExit):
            self.assemble()

    def test_unknown_situation_topic_stops_the_build(self):
        with open(self.fd / "situations.csv", "a", encoding="utf-8") as f:
            f.write("06,Water,ZZ,T2-001,1,x,test\n")
        with self.assertRaises(SystemExit):
            self.assemble()

    def test_test_build_shows_drafts_and_says_so(self):
        self.assemble("--allow-pending")
        self.assertIn("DRAFT-MARKER", self.page("arc/site/topic-S2.html"))
        self.assertIn("TEST BUILD", self.page())

    def test_site_is_fingerprinted_and_stale_pages_removed(self):
        (self.drive / "arc/site").mkdir(parents=True)
        (self.drive / "arc/site/old-page.html").write_text("stale", encoding="utf-8")
        self.assemble()
        sums = self.checksums(self.drive)
        for rel in (HTML, TXT, "arc/site/topic-S2.html", "arc/site/about.html"):
            self.assertIn(rel, sums)
        self.assertFalse((self.drive / "arc/site/old-page.html").exists())

    def test_maintenance_guide_on_drive_and_linked(self):
        self.assemble()
        raw = (self.drive / "arc/system/MAINTENANCE.txt").read_bytes()
        self.assertEqual(raw.count(b"\n"), raw.count(b"\r\n"), "Notepad-friendly line endings")
        keep = "arc/site/keep.html"
        self.assertIn("arc/system/MAINTENANCE.txt", frontdoor.links_in(self.page(keep), keep))
        self.assertIn("arc/system/MAINTENANCE.txt", self.checksums(self.drive))

    def test_text_version_uses_windows_line_endings(self):
        self.assemble()
        raw = (self.drive / TXT).read_bytes()
        self.assertEqual(raw.count(b"\n"), raw.count(b"\r\n"))

    def test_unknown_situation_id_fails(self):
        with open(self.fd / "situations.csv", "a", encoding="utf-8") as f:
            f.write("09,Typo,S1,T9-999,1,x,test\n")
        with self.assertRaises(SystemExit):
            self.assemble()


ARC_ZIM = f"arc/site/{arczim.FILE_NAME}"


@unittest.skipUnless(arczim.available()[0], "libzim and pypdf not installed (requirements-build.txt)")
class ArcCollectionTest(LibraryServerTest):
    """The arc's own collection: the website served by the library, with the
    guides inside. Runs only where the optional build packages are installed."""

    def build(self):
        self.add_zims()
        code, out = self.assemble()
        self.assertEqual(code, 0, out)
        from libzim.reader import Archive
        return Archive(str(self.drive / ARC_ZIM))

    def test_collection_holds_the_pages_and_the_guides(self):
        zim = self.build()
        self.assertEqual(zim.main_entry.get_item().path, "index.html")
        for path in ("site/topic-S2.html", "site/about.html", "guides/home/a_signed_2026.pdf",
                     "guides/home/a_signed_2026.pdf.html", "system/CATALOG.csv"):
            self.assertTrue(zim.has_entry_by_path(path), path)
        self.assertEqual(bytes(zim.get_entry_by_path("guides/home/a_signed_2026.pdf").get_item().content),
                         (self.drive / A).read_bytes())
        self.assertTrue(zim.has_fulltext_index)
        guide = bytes(zim.get_entry_by_path("guides/home/a_signed_2026.pdf.html").get_item().content).decode("utf-8")
        self.assertIn('href="a_signed_2026.pdf"', guide, "the guide page opens its PDF")

    def test_served_pages_link_inside_the_collection_or_to_the_server(self):
        import re
        from urllib.parse import unquote
        import posixpath
        zim = self.build()
        for entry_path in ("index.html", "site/topic-S2.html", "site/topic-H2.html", "site/shelf-community.html"):
            html = bytes(zim.get_entry_by_path(entry_path).get_item().content).decode("utf-8")
            self.assertNotIn("http:", html, f"{entry_path}: no absolute addresses when served")
            for h in re.findall(r'href="([^"]+)"', html):
                if h.startswith(("#", "/")):
                    continue
                target = posixpath.normpath(posixpath.join(posixpath.dirname(entry_path), unquote(h.split("#")[0])))
                self.assertTrue(zim.has_entry_by_path(target), f"{entry_path} -> {target}")
        home = bytes(zim.get_entry_by_path("index.html").get_item().content).decode("utf-8")
        self.assertIn('action="/search"', home)
        self.assertIn(f'value="{arczim.BOOK}"', home)
        self.assertIn('value="medicine_en_all_2026-01"', home)
        self.assertNotIn('value="diy.stackexchange.com_en_all_2026-01"', home, "community has its own search")
        self.assertEqual(home.count("<script"), 1)
        self.assertIn('href="/content/medicine_en_all_2026-01"', bytes(
            zim.get_entry_by_path("site/topic-H2.html").get_item().content).decode("utf-8"))

    def test_page_text_is_searchable(self):
        zim = self.build()
        from libzim.search import Query, Searcher
        results = list(Searcher(zim).search(Query().set_query("Drinking water sanitation")).get_results(0, 20))
        self.assertIn("site/topic-S2.html", results)

    def test_collection_is_fingerprinted_kept_by_prune_and_mirrored(self):
        self.build()
        self.assertIn(ARC_ZIM, self.checksums(self.drive))
        code, out = self.assemble("--prune")
        self.assertEqual(code, 0, out)
        self.assertTrue((self.drive / ARC_ZIM).is_file())
        code, out = quiet(mirror.main, ["--master", str(self.drive), "--copy", str(self.copy)])
        self.assertEqual(code, 0, out)
        self.assertTrue((self.copy / ARC_ZIM).is_file())

    def test_library_home_opens_the_collection_and_launchers_find_it(self):
        self.build()
        page = (self.drive / "arc/system/library-home.html").read_text(encoding="utf-8")
        self.assertIn(f'var ARC_BOOK = "{arczim.BOOK}"', page)
        self.assertIn(f'value="{arczim.BOOK}"', page)
        self.assertIn(b"arc\\site", (self.drive / BAT).read_bytes())
        self.assertIn(b"for d in site collections", (self.drive / "arc/open-full-library.sh").read_bytes())
        how = (self.drive / "arc/site/how.html").read_text(encoding="utf-8")
        self.assertNotIn(arczim.FILE_NAME, how, "no Android line without the app")


class WithoutCollectionPackagesTest(Fixture):
    def test_build_works_and_says_the_collection_was_skipped(self):
        real = arczim.available
        arczim.available = lambda: (False, "libzim is not installed: skipped")
        try:
            code, out = self.assemble()
        finally:
            arczim.available = real
        self.assertEqual(code, 0, out)
        self.assertIn("NOTE: libzim is not installed", out)
        self.assertFalse((self.drive / ARC_ZIM).exists())
        self.assertTrue((self.drive / HTML).is_file())


if __name__ == "__main__":
    unittest.main()
