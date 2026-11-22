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


if __name__ == "__main__":
    unittest.main()
