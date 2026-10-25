#!/usr/bin/env python3
import copy
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VALIDATOR = ROOT / "scripts" / "validate_pack.py"


def song(i, full=False, autoplay=True):
    suffix = "&do=play" if autoplay else ""
    s = {
        "song_id": f"song-{i}",
        "title": f"Song {i}",
        "artist": f"Artist {i}",
        "scoring_year": 1980 + i % 40,
        "amazon_play_url": f"https://music.amazon.de/albums/B{i:09d}?trackAsin=C{i:09d}{suffix}",
        "verification_status": "OK",
        "verification_notes": "Amazon playlist identity; MusicBrainz year.",
    }
    if full:
        s.update({
            "album": f"Album {i}",
            "version": "Original",
            "duration_seconds": 180 + i,
            "amazon_album_id": f"B{i:09d}",
            "amazon_track_asin": f"C{i:09d}",
        })
    return s


def pack(n=25, full=False, autoplay=True):
    songs = [song(i, full, autoplay=autoplay) for i in range(1, n + 1)]
    return {
        "schema_version": "1.4",
        "pack_id": "amazon-de-B012345678",
        "playlist_url": "https://music.amazon.de/playlists/B012345678",
        "playlist_name": "Test",
        "created_at": "2026-10-25T08:45:00+01:00",
        "validated_song_count": len(songs),
        "status": "NOT_READY",
        "validation": {
            "validator_version": "1.4",
            "validated_at": None,
            "songs_sha256": None,
        },
        "songs": songs,
    }


def songs_hash(songs):
    raw = json.dumps(songs, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class T(unittest.TestCase):
    def runv(self, p, check=False):
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "gamepack.json"
            f.write_text(json.dumps(p), encoding="utf-8")
            cmd = [sys.executable, str(VALIDATOR), str(f)] + (["--check-only"] if check else [])
            r = subprocess.run(cmd, text=True, capture_output=True)
            return r, json.loads(f.read_text())

    def test_minimal_pack_passes(self):
        r, saved = self.runv(pack())
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertEqual(saved["status"], "READY")
        self.assertEqual(saved["validation"]["validator_version"], "1.4")

    def test_optional_amazon_fields_not_required(self):
        r, _ = self.runv(pack())
        self.assertEqual(r.returncode, 0, r.stdout)

    def test_full_fields_still_pass(self):
        r, _ = self.runv(pack(full=True))
        self.assertEqual(r.returncode, 0, r.stdout)

    def test_top100_style_missing_do_play_is_normalized(self):
        p = pack(autoplay=False)
        self.assertEqual(
            p["songs"][0]["amazon_play_url"],
            "https://music.amazon.de/albums/B000000001?trackAsin=C000000001",
        )
        r, saved = self.runv(p)
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertEqual(
            saved["songs"][0]["amazon_play_url"],
            "https://music.amazon.de/albums/B000000001?trackAsin=C000000001&do=play",
        )

    def test_extra_query_params_are_removed_and_order_is_canonical(self):
        p = pack()
        p["songs"][0]["amazon_play_url"] = (
            "https://music.amazon.de/albums/B000000001?do=wrong&utm_source=x&trackAsin=C000000001"
        )
        r, saved = self.runv(p)
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertEqual(
            saved["songs"][0]["amazon_play_url"],
            "https://music.amazon.de/albums/B000000001?trackAsin=C000000001&do=play",
        )

    def test_lowercase_asins_are_normalized(self):
        p = pack()
        p["songs"][0]["amazon_play_url"] = (
            "https://music.amazon.de/albums/b000000001?trackAsin=c000000001"
        )
        r, saved = self.runv(p)
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertEqual(
            saved["songs"][0]["amazon_play_url"],
            "https://music.amazon.de/albums/B000000001?trackAsin=C000000001&do=play",
        )

    def test_check_only_rejects_noncanonical_url(self):
        p = pack()
        r, ready = self.runv(p)
        self.assertEqual(r.returncode, 0, r.stdout)
        ready["songs"][0]["amazon_play_url"] = (
            "https://music.amazon.de/albums/B000000001?trackAsin=C000000001"
        )
        ready["validation"]["songs_sha256"] = songs_hash(ready["songs"])
        r, _ = self.runv(ready, check=True)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("not canonical", r.stdout)

    def test_missing_track_asin_fails(self):
        p = pack()
        p["songs"][0]["amazon_play_url"] = "https://music.amazon.de/albums/B000000001?do=play"
        r, _ = self.runv(p)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("valid trackAsin", r.stdout)

    def test_non_album_url_fails(self):
        p = pack()
        p["songs"][0]["amazon_play_url"] = "https://music.amazon.de/tracks/C000000001?do=play"
        r, _ = self.runv(p)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("album URL", r.stdout)

    def test_wrong_host_fails(self):
        p = pack()
        p["songs"][0]["amazon_play_url"] = (
            "https://music.amazon.com/albums/B000000001?trackAsin=C000000001&do=play"
        )
        r, _ = self.runv(p)
        self.assertNotEqual(r.returncode, 0)

    def test_missing_play_url_fails(self):
        p = pack()
        del p["songs"][0]["amazon_play_url"]
        r, _ = self.runv(p)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("amazon_play_url", r.stdout)

    def test_bad_year_fails(self):
        p = pack()
        p["songs"][0]["scoring_year"] = None
        r, _ = self.runv(p)
        self.assertNotEqual(r.returncode, 0)

    def test_duplicate_song_id_fails(self):
        p = pack()
        p["songs"][1]["song_id"] = p["songs"][0]["song_id"]
        r, _ = self.runv(p)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("Duplicate song_id", r.stdout)

    def test_optional_ids_validate_when_present(self):
        p = pack(full=True)
        p["songs"][0]["amazon_album_id"] = "bad"
        r, _ = self.runv(p)
        self.assertNotEqual(r.returncode, 0)

    def test_optional_album_id_crosschecks_url(self):
        p = pack(full=True)
        p["songs"][0]["amazon_album_id"] = "B999999999"
        r, _ = self.runv(p)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("does not match amazon_play_url album ASIN", r.stdout)

    def test_optional_track_asin_crosschecks_url(self):
        p = pack(full=True)
        p["songs"][0]["amazon_track_asin"] = "C999999999"
        r, _ = self.runv(p)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("does not match amazon_play_url trackAsin", r.stdout)

    def test_too_small_fails(self):
        r, _ = self.runv(pack(19))
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("at least 20", r.stdout)

    def test_hash_tamper_fails_check_only(self):
        r, ready = self.runv(pack())
        self.assertEqual(r.returncode, 0, r.stdout)
        ready["songs"][0]["title"] = "X"
        r, _ = self.runv(ready, True)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("songs_sha256", r.stdout)

    def test_check_only_passes_after_normal_validation(self):
        r, ready = self.runv(pack(autoplay=False))
        self.assertEqual(r.returncode, 0, r.stdout)
        r, _ = self.runv(ready, True)
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertIn("CHECK-ONLY", r.stdout)


if __name__ == "__main__":
    unittest.main(verbosity=2)
