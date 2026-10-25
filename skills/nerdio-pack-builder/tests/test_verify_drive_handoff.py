#!/usr/bin/env python3
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from test_validate_pack import pack

ROOT = Path(__file__).resolve().parents[1]
VALIDATOR = ROOT / "scripts" / "validate_pack.py"
HANDOFF = ROOT / "scripts" / "verify_drive_handoff.py"


class DriveHandoffTests(unittest.TestCase):
    def make_files(self, root, mime="application/json", name="gamepack.json"):
        source = root / "gamepack.json"
        source.write_text(json.dumps(pack(20), ensure_ascii=False), encoding="utf-8")
        validated = subprocess.run([sys.executable, str(VALIDATOR), str(source)], capture_output=True, text=True)
        self.assertEqual(validated.returncode, 0, validated.stdout)
        drive_copy = root / "drive-copy.json"
        drive_copy.write_bytes(source.read_bytes())
        metadata = root / "drive-metadata.json"
        metadata.write_text(json.dumps({"result": {"title": name, "mime_type": mime, "file_or_folder": "file"}}))
        return source, drive_copy, metadata

    def run_check(self, files):
        source, copy, metadata = files
        return subprocess.run([
            sys.executable, str(HANDOFF),
            "--source", str(source),
            "--drive-copy", str(copy),
            "--metadata", str(metadata),
        ], capture_output=True, text=True)

    def test_real_json_passes(self):
        with tempfile.TemporaryDirectory() as temp:
            files = self.make_files(Path(temp))
            checked = self.run_check(files)
            self.assertEqual(checked.returncode, 0, checked.stdout)
            self.assertIn("HANDOFF PASSED", checked.stdout)

    def test_google_doc_named_json_fails(self):
        with tempfile.TemporaryDirectory() as temp:
            files = self.make_files(Path(temp), mime="application/vnd.google-apps.document")
            checked = self.run_check(files)
            self.assertNotEqual(checked.returncode, 0)
            self.assertIn("MIME type", checked.stdout)

    def test_text_file_named_json_fails(self):
        with tempfile.TemporaryDirectory() as temp:
            files = self.make_files(Path(temp), mime="text/plain")
            checked = self.run_check(files)
            self.assertNotEqual(checked.returncode, 0)
            self.assertIn("MIME type", checked.stdout)

    def test_wrong_filename_fails(self):
        with tempfile.TemporaryDirectory() as temp:
            files = self.make_files(Path(temp), name="gamepack.json.txt")
            checked = self.run_check(files)
            self.assertNotEqual(checked.returncode, 0)
            self.assertIn("filename", checked.stdout)

    def test_modified_bytes_fail_even_if_json_valid(self):
        with tempfile.TemporaryDirectory() as temp:
            files = self.make_files(Path(temp))
            copy = files[1]
            copy.write_bytes(copy.read_bytes() + b"\n")
            checked = self.run_check(files)
            self.assertNotEqual(checked.returncode, 0)
            self.assertIn("bytes differ", checked.stdout)

    def test_modified_song_fails_hash_check(self):
        with tempfile.TemporaryDirectory() as temp:
            files = self.make_files(Path(temp))
            copy = files[1]
            data = json.loads(copy.read_text())
            data["songs"][0]["title"] = "Tampered"
            copy.write_text(json.dumps(data))
            checked = self.run_check(files)
            self.assertNotEqual(checked.returncode, 0)
            self.assertIn("songs_sha256", checked.stdout)


if __name__ == "__main__":
    unittest.main(verbosity=2)
