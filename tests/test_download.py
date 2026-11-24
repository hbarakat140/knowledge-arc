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

        def fake_fetch(url, timeout=None):
            if url == old_meta4:
                raise urllib.error.HTTPError(url, 404, "Not Found", None, None)
            return pages[url]

        real, download.fetch_text = download.fetch_text, fake_fetch
        download.folder_listing.cache_clear()   # listings are cached per run
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


class PdfResumeTest(unittest.TestCase):
    """A big PDF whose server drops the connection every 100 KB (the EU's
    JRC does this) is fetched in pieces with Range, not restarted."""

    def setUp(self):
        global PAYLOAD
        self.saved, self.tmp = PAYLOAD, tempfile.TemporaryDirectory()
        PAYLOAD = b"%PDF-1.7\n" + os.urandom(350 * 1024)
        download.time.sleep, self.sleep = (lambda s: None), download.time.sleep

    def tearDown(self):
        global PAYLOAD
        PAYLOAD = self.saved
        download.time.sleep = self.sleep
        self.mirror.close()
        self.tmp.cleanup()

    def test_dropped_pdf_resumes(self):
        self.mirror = Mirror("drop")
        target = Path(self.tmp.name) / "big.pdf"
        size = download.get_pdf(self.mirror.url, target)
        self.assertEqual(target.read_bytes(), PAYLOAD)
        self.assertEqual(size, len(PAYLOAD))
        self.assertEqual(self.mirror.ranges, [0, 100 * 1024, 200 * 1024, 300 * 1024])
        self.assertFalse(target.with_name("big.pdf.part").exists())


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
        readme = (self.saved / "README.md").read_text(encoding="utf-8")
        files = [p for p in self.saved.rglob("*") if p.is_file() and p.name != "README.md"]
        self.assertTrue(files)
        sets = {}   # multi-file items: folder -> {file name: sha-256}
        for p in files:
            rel = p.relative_to(self.saved).as_posix()
            sha = hashlib.sha256(p.read_bytes()).hexdigest()
            parent = rel.rsplit("/", 1)[0]
            if parent in rows and cl.is_multi_file(rows[parent]):
                self.assertIn(p.name, cl.part_labels(rows[parent]), f"hosted/{rel} is not on its item's file list")
                sets.setdefault(parent, {})[p.name] = sha
                self.assertIn(parent.split("/")[-1], readme)
                continue
            self.assertIn(rel, rows, f"hosted/{rel} has no catalog row")
            self.assertEqual(sha, rows[rel]["sha256"], rel)
            self.assertIn(rel.split("/")[-1], readme)
        for folder, shas in sets.items():
            row = rows[folder]
            if len(shas) == cl.file_count(row):   # every file hosted: the set's fingerprint is the row's
                lines = "".join(sorted(f"{s}  {n}\n" for n, s in shas.items()))
                self.assertEqual(hashlib.sha256(lines.encode()).hexdigest(), row["sha256"], folder)


class HtmlBookTest(unittest.TestCase):
    """A book saved as one HTML page (Project Gutenberg): pictures become their
    captions, an error page is refused, and the names are allowed in a list."""

    def test_pictures_become_captions_and_error_pages_are_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            book = Path(tmp) / "a-tale_dickens.html"
            book.write_text("<?xml version='1.0'?><html><body>" + "It was the best of times. " * 100
                            + '<img src="images/i.jpg" alt="The road to Dover"/><IMG SRC="x.png"></body></html>',
                            encoding="utf-8")
            download.clean_html_book(book)
            text = book.read_text(encoding="utf-8")
            self.assertIn("[The road to Dover]", text)
            self.assertNotIn("<img", text.lower())
            first = book.read_bytes()
            download.clean_html_book(book)
            self.assertEqual(book.read_bytes(), first, "cleaning twice changes nothing")
            short = Path(tmp) / "blocked_x.html"
            short.write_text("<html><body>Checking your browser</body></html>", encoding="utf-8")
            with self.assertRaises(download.Failed):
                download.clean_html_book(short)

    def test_html_names_and_signature(self):
        sys.path.insert(0, str(Path(download.__file__).parent))
        import catalog_lib as cl
        self.assertTrue(cl.SAFE_FILE_NAME.match("pride-and-prejudice_austen.html"))
        self.assertEqual(download.magic_for(Path("x.html")), b"<")


class FileListTest(unittest.TestCase):
    """A multi-file item pinned in catalog/files/<id>.csv: exactly those
    files, by their names, waiting when the site says "too many requests"."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.dest, self.lists = root / "dest", root / "files"
        self.lists.mkdir()
        self.bodies = {"/a.pdf": b"%PDF-1.4 a\n" * 30, "/b.pdf": b"%PDF-1.4 b\n" * 30}
        self.busy = 1   # the first request gets HTTP 429
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_GET(self):
                if outer.busy:
                    outer.busy -= 1
                    self.send_response(429)
                    self.send_header("Retry-After", "0")
                    self.end_headers()
                    return
                body = outer.bodies[self.path]
                self.send_response(200)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        base = f"http://127.0.0.1:{self.server.server_port}"
        (self.lists / "T2-950.csv").write_text(
            "file,label,url,updated\n"
            f"thyme_summary.pdf,Thyme: summary for the public,{base}/a.pdf,2016-09-20\n"
            f"thyme_monograph.pdf,Thyme: EU herbal monograph,{base}/b.pdf,2013-11-26\n", encoding="utf-8")
        self.saved = download.FILE_LIST_PAUSE
        download.FILE_LIST_PAUSE = 0

    def tearDown(self):
        download.FILE_LIST_PAUSE = self.saved
        self.server.shutdown()
        self.server.server_close()
        self.tmp.cleanup()

    def fetch(self, count):
        row = {"id": "T2-950", "folder": "arc/guides/health/plants", "format": f"pdf ({count} files)"}
        with contextlib.redirect_stdout(io.StringIO()):
            return download.do_file_list(row, self.dest, download.State(self.dest), False, folder=self.lists)

    def test_exactly_the_pinned_files_after_a_429(self):
        status, size, sha, new = self.fetch(2)
        self.assertEqual(status, "downloaded")
        folder = self.dest / "arc/guides/health/plants"
        self.assertEqual(sorted(p.name for p in folder.iterdir()), ["thyme_monograph.pdf", "thyme_summary.pdf"])
        self.assertEqual((folder / "thyme_summary.pdf").read_bytes(), self.bodies["/a.pdf"])
        self.assertEqual(size, 2 * len(self.bodies["/a.pdf"]))
        self.assertEqual(self.fetch(2), ("present", size, sha, False))   # a second run fetches nothing

    def test_a_new_address_for_a_file_is_fetched_again(self):
        self.fetch(2)
        listing = self.lists / "T2-950.csv"
        listing.write_text(listing.read_text(encoding="utf-8").replace("/b.pdf", "/a.pdf"), encoding="utf-8")
        status, _, _, new = self.fetch(2)
        self.assertEqual((status, new), ("downloaded", True))
        self.assertEqual((self.dest / "arc/guides/health/plants/thyme_monograph.pdf").read_bytes(),
                         self.bodies["/a.pdf"])

    def hosted_fetch(self, sha):
        saved, download.HOSTED = download.HOSTED, Path(self.tmp.name) / "hosted"
        try:
            folder = download.HOSTED / "arc/guides/health/plants"
            folder.mkdir(parents=True)
            (folder / "thyme_summary.pdf").write_bytes(b"%PDF-1.4 hosted a\n" * 30)
            (folder / "thyme_monograph.pdf").write_bytes(b"%PDF-1.4 hosted b\n" * 30)
            self.busy = 0
            row = {"id": "T2-950", "folder": "arc/guides/health/plants", "format": "pdf (2 files)", "sha256": sha}
            with contextlib.redirect_stdout(io.StringIO()):
                return download.do_file_list(row, self.dest, download.State(self.dest), False, folder=self.lists)
        finally:
            download.HOSTED = saved

    def test_hosted_files_are_copied_and_checked_as_a_set(self):
        lines = "".join(sorted(f"{hashlib.sha256(b).hexdigest()}  {n}\n" for n, b in [
            ("thyme_summary.pdf", b"%PDF-1.4 hosted a\n" * 30), ("thyme_monograph.pdf", b"%PDF-1.4 hosted b\n" * 30)]))
        status, _, sha, new = self.hosted_fetch(hashlib.sha256(lines.encode()).hexdigest())
        self.assertEqual((status, new), ("copied-from-repository", True))
        self.assertEqual((self.dest / "arc/guides/health/plants/thyme_summary.pdf").read_bytes(),
                         b"%PDF-1.4 hosted a\n" * 30)

    def test_hosted_files_that_do_not_match_are_refused(self):
        with self.assertRaises(download.Failed):
            self.hosted_fetch("0" * 64)
        self.assertEqual(list((self.dest / "arc/guides/health/plants").iterdir()), [])
        self.assertFalse([k for k in download.State(self.dest).data if k.startswith("arc/")])

    def test_a_file_dropped_from_the_list_is_removed(self):
        self.fetch(2)
        listing = self.lists / "T2-950.csv"
        listing.write_text("\n".join(listing.read_text(encoding="utf-8").splitlines()[:2]) + "\n", encoding="utf-8")
        self.fetch(1)
        folder = self.dest / "arc/guides/health/plants"
        self.assertEqual([p.name for p in folder.iterdir()], ["thyme_summary.pdf"])
        state = download.State(self.dest).data
        self.assertEqual([k for k in state if k.startswith("arc/")], ["arc/guides/health/plants/thyme_summary.pdf"])

    def test_a_dry_run_removes_nothing(self):
        self.fetch(2)
        listing = self.lists / "T2-950.csv"
        listing.write_text("\n".join(listing.read_text(encoding="utf-8").splitlines()[:2]) + "\n", encoding="utf-8")
        row = {"id": "T2-950", "folder": "arc/guides/health/plants", "format": "pdf (1 file)"}
        with contextlib.redirect_stdout(io.StringIO()):
            download.do_file_list(row, self.dest, download.State(self.dest), True, folder=self.lists)
        self.assertTrue((self.dest / "arc/guides/health/plants/thyme_monograph.pdf").exists())
        self.assertIn("arc/guides/health/plants/thyme_monograph.pdf", download.State(self.dest).data)

    def test_a_count_that_differs_from_the_row_stops(self):
        with self.assertRaises(download.Failed):
            self.fetch(3)

    def test_kind_of_finds_the_list(self):
        self.assertEqual(download.kind_of({"id": "T2-158", "source_url": "https://www.ema.europa.eu/x",
                                           "folder": "arc/guides/health/x", "format": "pdf (2 files)"})[0],
                         "file-list" if (download.cl.FILE_LISTS / "T2-158.csv").exists() else "unsupported")


class PocketKitDownloadTest(unittest.TestCase):
    """--bundle core also fetches the pocket rows core replaces, into the
    pocket kit (arc/pocket), where the drive's library never serves them."""
    tearDown = HostedTest.tearDown

    def setUp(self):
        HostedTest.setUp(self)
        import csv
        from test_catalog import FIELDS, row
        self.big = "arc/guides/home/big_2026.pdf"
        (download.HOSTED / self.big).write_bytes(self.body + b"big")
        self.catalog = Path(self.tmp.name) / "catalog.csv"
        rows = [row(id="T2-901", title="Short", folder=self.rel, format="pdf", bundle="pocket",
                    size_bytes=str(len(self.body)), sha256=hashlib.sha256(self.body).hexdigest(),
                    source_url="http://127.0.0.1:9/short.pdf"),
                row(id="T2-902", title="Long", folder=self.big, format="pdf", bundle="core",
                    notes="REPLACES T2-901", source_url="http://127.0.0.1:9/big.pdf",
                    size_bytes=str(len(self.body) + 3), sha256=hashlib.sha256(self.body + b"big").hexdigest())]
        with open(self.catalog, "w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=FIELDS, lineterminator="\n")
            w.writeheader()
            w.writerows(rows)

    def download(self, bundle):
        with contextlib.redirect_stdout(io.StringIO()) as out:
            code = download.main(["--dest", str(self.dest), "--bundle", bundle, "--catalog", str(self.catalog)])
        return code, out.getvalue()

    def test_the_replaced_pocket_row_goes_into_the_kit(self):
        code, out = self.download("core")
        self.assertEqual(code, 0, out)
        self.assertTrue((self.dest / self.big).is_file())
        self.assertFalse((self.dest / self.rel).exists())
        self.assertEqual((self.dest / "arc/pocket" / self.rel).read_bytes(), self.body)
        import json
        kit_state = json.loads((self.dest / "arc/pocket/.download-state.json").read_text(encoding="utf-8"))
        self.assertIn(self.rel, kit_state)
        code, out = self.download("core")
        self.assertNotIn("copied", out, "a second run fetches nothing")

    def test_an_archive_filled_with_all_is_not_fetched_twice(self):
        self.download("all")
        self.assertTrue((self.dest / self.rel).is_file())
        code, out = self.download("core")
        self.assertEqual(code, 0, out)
        self.assertIn(f"present at {self.rel}", out)
        self.assertFalse((self.dest / "arc/pocket" / self.rel).exists())


class MacCertificatesTest(unittest.TestCase):
    """Python from python.org on a Mac has no certificates until its "Install
    Certificates" step: then the Mac's own root certificates are loaded."""

    @unittest.skipUnless(hasattr(__import__("ssl"), "enum_certificates"), "needs Windows' certificate store")
    def test_the_macs_root_certificates_are_loaded_one_by_one(self):
        import ssl
        import subprocess
        import catalog_lib as cl
        ders = [der for der, enc, _ in ssl.enum_certificates("ROOT") if enc == "x509_asn"][:2]
        pem = "".join(ssl.DER_cert_to_PEM_cert(d) for d in ders)
        broken = "-----BEGIN CERTIFICATE-----\nnot a certificate\n-----END CERTIFICATE-----\n"

        def fake_security(cmd, **kw):
            self.assertEqual(cmd[:3], ["security", "find-certificate", "-a"])
            return subprocess.CompletedProcess(cmd, 0, stdout=pem + broken, stderr="")

        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)   # empty, like the python.org Mac Python
        self.assertEqual(cl.add_mac_roots(ctx, run=fake_security), len(ders), "the broken one is skipped")
        self.assertEqual(ctx.cert_store_stats()["x509"], len(ders))

    def test_no_security_tool_is_not_fatal(self):
        import ssl
        import catalog_lib as cl

        def missing(cmd, **kw):
            raise FileNotFoundError("security")
        self.assertEqual(cl.add_mac_roots(ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT), run=missing), 0)

    def test_downloads_use_the_shared_https_settings(self):
        import catalog_lib as cl
        self.assertIs(cl.ssl_context(), cl.ssl_context())
        self.assertIn("context=cl.ssl_context()", Path(download.__file__).read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
