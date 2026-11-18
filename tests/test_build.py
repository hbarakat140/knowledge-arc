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
import mirror  # noqa: E402
from test_catalog import FIELDS, row  # noqa: E402

A = "01_LIVING/test/a_signed_2026.pdf"
B = "01_LIVING/test/b_pending_2026.pdf"


def quiet(fn, *args):
    with contextlib.redirect_stdout(io.StringIO()) as out:
        code = fn(*args)
    return code, out.getvalue()


class BuildTest(unittest.TestCase):
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

    def tearDown(self):
        self.tmp.cleanup()

    def assemble(self, *extra):
        return quiet(assemble.main, ["--staging", str(self.staging), "--drive", str(self.drive),
                                     "--bundle", "core", "--catalog", str(self.catalog),
                                     "--publishers", str(self.publishers), *extra])

    def checksums(self, drive):
        text = (drive / assemble.CHECKSUMS).read_text(encoding="utf-8")
        return {line[66:]: line[:64] for line in text.splitlines()}

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


if __name__ == "__main__":
    unittest.main()
