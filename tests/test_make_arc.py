"""make-arc.py, the one command that makes an arc: drive checks, space, and
that it downloads straight onto the drive unless --archive is given. The
download and build themselves are covered by test_download and test_build.

Run: python -m unittest discover -s tests
"""

import contextlib
import importlib.util
import io
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("make_arc", REPO / "make-arc.py")
make_arc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(make_arc)
sys.path.insert(0, str(REPO / "scripts"))
import assemble  # noqa: E402
import download  # noqa: E402


class MakeArcTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.calls = []
        self.saved = (download.main, assemble.main, make_arc.file_system)
        download.main = lambda argv: self.calls.append(("download", argv)) or 0
        assemble.main = lambda argv: self.calls.append(("assemble", argv)) or 0

    def tearDown(self):
        download.main, assemble.main, make_arc.file_system = self.saved
        self.tmp.cleanup()

    def run_main(self, *argv):
        with contextlib.redirect_stdout(io.StringIO()) as out:
            code = make_arc.main(["--no-search", "--yes", "--edition", "pocket", *argv])
        return code, out.getvalue()

    def test_downloads_straight_onto_the_drive(self):
        drive = self.root / "drive"
        code, out = self.run_main("--drive", str(drive))
        self.assertEqual(code, 0, out)
        (_, dl), (_, asm) = self.calls
        self.assertEqual(dl[dl.index("--dest") + 1], str(drive.resolve()))
        self.assertEqual(asm[asm.index("--staging") + 1], asm[asm.index("--drive") + 1])
        self.assertEqual(dl[dl.index("--bundle") + 1], "pocket")
        self.assertIn('Open "1 START-HERE"', out)

    def test_archive_keeps_downloads_apart(self):
        drive, archive = self.root / "drive", self.root / "archive"
        self.run_main("--drive", str(drive), "--archive", str(archive))
        (_, dl), (_, asm) = self.calls
        self.assertEqual(dl[dl.index("--dest") + 1], str(archive.resolve()))
        self.assertEqual(asm[asm.index("--drive") + 1], str(drive.resolve()))

    def test_fat32_is_refused_with_how_to_fix(self):
        make_arc.file_system = lambda path: "FAT32"
        with self.assertRaises(SystemExit) as e:
            self.run_main("--drive", str(self.root / "stick"))
        self.assertIn("exFAT", str(e.exception))
        self.assertEqual(self.calls, [])

    def test_never_inside_the_repository(self):
        with self.assertRaises(SystemExit):
            self.run_main("--drive", str(REPO / "build-here"))
        self.assertEqual(self.calls, [])

    def test_space_on_one_drive_counts_what_is_already_there(self):
        rows = [{"folder": "arc/collections/a.zim", "size_bytes": str(10 ** 9), "format": "zim", "shelf": "x"}]
        drive = self.root / "drive"
        before = make_arc.space_needed(rows, drive, drive)[drive]
        (drive / "arc/collections").mkdir(parents=True)
        with open(drive / "arc/collections/a.zim", "wb") as f:
            f.truncate(10 ** 9)   # sparse: already downloaded
        after = make_arc.space_needed(rows, drive, drive)[drive]
        self.assertEqual(before - after, 10 ** 9)
        self.assertEqual(after, make_arc.EXTRA)


# The pocket fitting pass at the end of the content review (owner, 23 Nov 2026).
FIT_PASS_PENDING = True


class PocketBudgetTest(unittest.TestCase):
    def test_the_pocket_edition_fits_a_32_gb_stick(self):
        """A "32 GB" stick holds about 31 GB once formatted exFAT. Keep the
        pocket edition (with the arc's own collection and the programs) under
        29 GB on the drive (owner, 23 Nov 2026; was 28), so no catalog change quietly overflows it."""
        import catalog_lib as cl
        rows = make_arc.drive_rows(cl.read_csv(cl.CATALOG)[1], "pocket")
        size = make_arc.needed_on_drive(rows)
        if FIT_PASS_PENDING and size >= 29e9:
            # Owner, 23 Nov 2026: during the content review, gather everything
            # first and cut pocket to fit at the end. Until that pass, an
            # overflow is reported, not a failure. Set FIT_PASS_PENDING to
            # False when the fitting pass is done.
            self.skipTest(f"pocket is {size / 1e9:.1f} GB on the drive, over 29 GB: fitting pass pending")
        self.assertLess(size, 29e9)


class BuildPackagesTest(unittest.TestCase):
    """Python older than 3.11 can't install libzim: make-arc says what the
    arc will lack and asks, instead of quietly building a lesser arc."""

    def setUp(self):
        self.saved = (make_arc.FULL_PYTHON, make_arc.has_build_packages, make_arc.ask)
        make_arc.FULL_PYTHON = (99, 0)          # this Python counts as too old
        make_arc.has_build_packages = lambda: False

    def tearDown(self):
        make_arc.FULL_PYTHON, make_arc.has_build_packages, make_arc.ask = self.saved

    def ensure(self, *argv, answer="n"):
        self.asked = []
        make_arc.ask = lambda question, default="": self.asked.append(question) or answer
        args = make_arc.argparse.Namespace(no_search=False, yes="--yes" in argv)
        with contextlib.redirect_stdout(io.StringIO()) as out:
            make_arc.ensure_build_packages(args)
        return out.getvalue()

    def test_too_old_python_explains_and_stops_unless_agreed(self):
        with self.assertRaises(SystemExit):
            self.ensure()
        out = self.ensure(answer="y")
        self.assertIn("need Python 99.0 or newer", out)
        self.assertIn("not searchable", out)
        self.assertIn("python.org", out)

    def test_yes_goes_on_without_asking(self):
        self.assertIn("not searchable", self.ensure("--yes"))
        self.assertEqual(self.asked, [])


if __name__ == "__main__":
    unittest.main()
