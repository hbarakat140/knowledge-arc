"""download.py against local fake mirrors: resume after a dropped connection,
resume of a .part left by an earlier run, and mirror ranking by speed.

Run: python -m unittest discover -s tests
"""

import contextlib
import hashlib
import io
import os
import sys
import tempfile
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import download  # noqa: E402

PAYLOAD = os.urandom(300 * 1024)
NAME = "test_en_all_2026-01.zim"


class Mirror:
    """A tiny HTTP server that serves PAYLOAD with Range support.
    mode: 'fast', 'slow' (sleeps between blocks) or 'drop' (closes the
    connection after 100 KB)."""

    def __init__(self, mode):
        self.mode, self.ranges = mode, []
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_GET(self):
                if self.path.endswith(".meta4"):
                    body = outer.meta4.encode()
                    self.send_response(200)
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
                    return
                start, end = 0, len(PAYLOAD) - 1
                rng = self.headers.get("Range")
                if rng:
                    a, _, b = rng.split("=", 1)[1].partition("-")
                    start, end = int(a), int(b) if b else end
                outer.ranges.append(start)
                chunk = PAYLOAD[start:end + 1]
                self.send_response(206 if rng else 200)
                self.send_header("Content-Length", str(len(chunk)))
                if rng:
                    self.send_header("Content-Range", f"bytes {start}-{end}/{len(PAYLOAD)}")
                self.end_headers()
                if outer.mode == "drop":
                    chunk = chunk[:100 * 1024]
                for i in range(0, len(chunk), 16 * 1024):
                    if outer.mode == "slow":
                        time.sleep(0.05)
                    try:
                        self.wfile.write(chunk[i:i + 16 * 1024])
                    except OSError:
                        return
                if outer.mode == "drop":
                    self.close_connection = True

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.server.server_port}/{NAME}"
        self.meta4 = ""
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def close(self):
        self.server.shutdown()
        self.server.server_close()


def meta4(urls):
    sha = hashlib.sha256(PAYLOAD).hexdigest()
    items = "".join(f'<url priority="{i + 1}">{u}</url>' for i, u in enumerate(urls))
    return ('<?xml version="1.0" encoding="UTF-8"?><metalink xmlns="urn:ietf:params:xml:ns:metalink">'
            f'<file name="{NAME}"><size>{len(PAYLOAD)}</size><hash type="sha-256">{sha}</hash>'
            f'{items}</file></metalink>')


class DownloadTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dest = Path(self.tmp.name)
        self.mirrors = {}
        self.saved = (download.PROBE_ABOVE, download.PROBE_BYTES, download.PROBE_SECONDS)

    def tearDown(self):
        download.PROBE_ABOVE, download.PROBE_BYTES, download.PROBE_SECONDS = self.saved
        for m in self.mirrors.values():
            m.close()
        self.tmp.cleanup()

    def mirror(self, mode):
        self.mirrors[mode] = Mirror(mode)
        return self.mirrors[mode]

    def fetch(self, order):
        """Run do_zim with a meta4 listing the mirrors in `order`."""
        host = self.mirrors[order[0]]
        host.meta4 = meta4([self.mirrors[m].url for m in order])
        row = {"source_url": host.url + ".meta4", "folder": f"arc/collections/{NAME}", "size_bytes": ""}
        with contextlib.redirect_stdout(io.StringIO()) as out:
            result = download.do_zim(row, self.dest, download.State(self.dest), False)
        return result, out.getvalue()

    def target(self):
        return self.dest / "arc/collections" / NAME

    def test_dropped_connection_resumes_on_next_mirror(self):
        download.PROBE_ABOVE = 10 ** 12          # keep the listed order
        self.mirror("drop"), self.mirror("fast")
        (status, size, sha, new), _ = self.fetch(["drop", "fast"])
        self.assertEqual(status, "downloaded")
        self.assertEqual(self.target().read_bytes(), PAYLOAD)
        self.assertEqual(self.mirrors["fast"].ranges, [100 * 1024], "must resume, not restart")
        self.assertFalse(self.target().with_name(NAME + ".part").exists())

    def test_part_from_an_earlier_run_is_resumed(self):
        download.PROBE_ABOVE = 10 ** 12
        self.mirror("fast")
        part = self.target().with_name(NAME + ".part")
        part.parent.mkdir(parents=True)
        part.write_bytes(PAYLOAD[:123456])
        (status, *_), out = self.fetch(["fast"])
        self.assertEqual(status, "downloaded")
        self.assertIn("resuming at", out)
        self.assertEqual(self.mirrors["fast"].ranges, [123456])
        self.assertEqual(self.target().read_bytes(), PAYLOAD)

    def test_damaged_part_is_caught_and_deleted(self):
        download.PROBE_ABOVE = 10 ** 12
        self.mirror("fast")
        part = self.target().with_name(NAME + ".part")
        part.parent.mkdir(parents=True)
        part.write_bytes(b"X" * 1000 + PAYLOAD[1000:123456])
        with self.assertRaises(download.Failed):
            self.fetch(["fast"])
        self.assertFalse(part.exists())
        self.assertFalse(self.target().exists())

    def test_fastest_mirror_is_tried_first(self):
        download.PROBE_ABOVE, download.PROBE_BYTES, download.PROBE_SECONDS = 0, 64 * 1024, 3
        self.mirror("slow"), self.mirror("fast")
        dead = "http://127.0.0.1:9/nothing.zim"
        ranked, speeds = download.fastest_first([dead, self.mirrors["slow"].url, self.mirrors["fast"].url])
        self.assertEqual(ranked, [self.mirrors["fast"].url, self.mirrors["slow"].url, dead])
        self.assertEqual(speeds[dead], 0)
        (status, *_), out = self.fetch(["slow", "fast"])
        self.assertEqual(status, "downloaded")
        self.assertIn("fastest mirror: 127.0.0.1", out)
        self.assertEqual(self.target().read_bytes(), PAYLOAD)


    def test_gone_version_is_replaced_by_the_newest_of_the_same_collection(self):
        """Kiwix keeps the two newest versions; an older pin gets a 404."""
        import urllib.error
        download.PROBE_ABOVE = 10 ** 12
        fast = self.mirror("fast")
        newer = "test_en_all_2026-05.zim"
        old_meta4 = "http://kiwix.example/zim/test/" + NAME + ".meta4"
        pages = {
            "http://kiwix.example/zim/test/": '<a href="test_en_all_2026-03.zim">x</a> <a href="test_en_all_2026-05.zim">x</a>'
                                              ' <a href="test_en_other_2026-09.zim">x</a>',
            "http://kiwix.example/zim/test/" + newer + ".meta4": meta4([fast.url]).replace(NAME, newer),
        }

        def fake_fetch(url):
            if url == old_meta4:
                raise urllib.error.HTTPError(url, 404, "Not Found", None, None)
            return pages[url]

        real, download.fetch_text = download.fetch_text, fake_fetch
        try:
            row = {"source_url": old_meta4, "folder": f"arc/collections/{NAME}", "size_bytes": ""}
            state = download.State(self.dest)
            with contextlib.redirect_stdout(io.StringIO()) as out:
                status, *_ = download.do_zim(row, self.dest, state, False)
        finally:
            download.fetch_text = real
        self.assertEqual(status, "downloaded")
        self.assertIn("using the newest version, test_en_all_2026-05.zim", out.getvalue())
        self.assertEqual(self.target().read_bytes(), PAYLOAD, "saved under the catalog's name")
        self.assertEqual(state.data[f"arc/collections/{NAME}"]["source"], newer)


class HostedTest(unittest.TestCase):
    """Files whose sites block scripts are copied from the repository (hosted/)."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.dest, self.saved = root / "dest", download.HOSTED
        download.HOSTED = root / "hosted"
        self.rel = "arc/guides/home/blocked_2026.pdf"
        self.body = b"%PDF-1.4 hosted copy\n" * 20
        (download.HOSTED / self.rel).parent.mkdir(parents=True)
        (download.HOSTED / self.rel).write_bytes(self.body)

    def tearDown(self):
        download.HOSTED = self.saved
        self.tmp.cleanup()

    def fetch(self, sha):
        row = {"source_url": "http://127.0.0.1:9/blocked.pdf", "folder": self.rel,
               "size_bytes": str(len(self.body)), "sha256": sha}
        with contextlib.redirect_stdout(io.StringIO()):
            return download.do_pdf(row, self.dest, download.State(self.dest), False)

    def test_copied_from_the_repository_and_checked(self):
        status, size, sha, new = self.fetch(hashlib.sha256(self.body).hexdigest())
        self.assertEqual(status, "copied-from-repository")
        self.assertEqual((self.dest / self.rel).read_bytes(), self.body)

    def test_a_changed_hosted_copy_is_refused(self):
        with self.assertRaises(download.Failed):
            self.fetch("0" * 64)
        self.assertFalse((self.dest / self.rel).exists())

    def test_every_hosted_file_matches_its_catalog_row(self):
        sys.path.insert(0, str(Path(download.__file__).parent))
        import catalog_lib as cl
        rows = {r["folder"]: r for r in cl.read_csv(cl.CATALOG)[1]}
        files = [p for p in self.saved.rglob("*") if p.is_file() and p.name != "README.md"]
        self.assertTrue(files)
        for p in files:
            rel = p.relative_to(self.saved).as_posix()
            self.assertIn(rel, rows, f"hosted/{rel} has no catalog row")
            self.assertEqual(hashlib.sha256(p.read_bytes()).hexdigest(), rows[rel]["sha256"], rel)
            self.assertIn(rel.split("/")[-1], (self.saved / "README.md").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
