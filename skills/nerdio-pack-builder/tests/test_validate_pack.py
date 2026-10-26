#!/usr/bin/env python3
import copy
import hashlib
import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VALIDATOR = ROOT / "scripts" / "validate_pack.py"
SCHEMA = ROOT / "references" / "gamepack-schema.json"


def song(i, full=False, autoplay=True, legacy=False, only_asin=False):
    asin = f"C{i:09d}"
    album = f"B{i:09d}"
    suffix = "&do=play" if autoplay else ""
    url = (f"https://music.amazon.de/albums/{album}?trackAsin={asin}{suffix}"
           if legacy else f"https://music.amazon.de/tracks/{asin}{'?do=play' if autoplay else ''}")
    s = {
        "song_id": f"song-{i}",
        "title": f"Song {i}",
        "artist": f"Artist {i}",
        "scoring_year": 1980 + i % 40,
        "verification_status": "OK",
        "verification_notes": "Playlist track ASIN; MusicBrainz recording year.",
    }
    if only_asin:
        s["amazon_track_asin"] = asin
    else:
        s["amazon_play_url"] = url
    if full:
        s.update({
            "album": f"Album {i}",
            "version": "Original",
            "duration_seconds": 180 + i,
            "amazon_album_id": album,
            "amazon_track_asin": asin,
        })
    return s


def pack(n=25, full=False, autoplay=True, legacy=False, playlist_count=None, only_asin=False):
    songs = [song(i, full=full, autoplay=autoplay, legacy=legacy, only_asin=only_asin)
             for i in range(1, n + 1)]
    return {
        "schema_version": "1.5",
        "pack_id": "amazon-de-B012345678",
        "playlist_url": "https://music.amazon.de/playlists/B012345678",
        "playlist_name": "Test",
        "created_at": "2026-10-25T08:45:00+01:00",
        "playlist_song_count": n if playlist_count is None else playlist_count,
        "validated_song_count": len(songs),
        "status": "NOT_READY",
        "validation": {
            "validator_version": "1.5",
            "validated_at": None,
            "songs_sha256": None,
        },
        "songs": songs,
    }


def songs_hash(songs):
    raw = json.dumps(songs, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class ValidatorTests(unittest.TestCase):
    def runv(self, p, check=False):
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "gamepack.json"
            f.write_text(json.dumps(p), encoding="utf-8")
            cmd = [sys.executable, str(VALIDATOR), str(f)] + (["--check-only"] if check else [])
            r = subprocess.run(cmd, text=True, capture_output=True)
            return r, json.loads(f.read_text())

    def test_minimal_25_song_pack_passes(self):
        r, saved = self.runv(pack())
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertEqual(saved["status"], "READY")
        self.assertEqual(saved["validation"]["validator_version"], "1.5")
        self.assertEqual(saved["playlist_song_count"], 25)

    def test_full_50_song_pack_without_album_ids_passes(self):
        r, saved = self.runv(pack(50, only_asin=True))
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertEqual(len(saved["songs"]), 50)
        self.assertTrue(all("/tracks/" in s["amazon_play_url"] for s in saved["songs"]))
        self.assertTrue(all("amazon_album_id" not in s for s in saved["songs"]))

    def test_20_of_50_playlist_never_ready(self):
        r, saved = self.runv(pack(20, playlist_count=50))
        self.assertNotEqual(r.returncode, 0)
        self.assertEqual(saved["status"], "NOT_READY")
        self.assertIn("Playlist incomplete", r.stdout)

    def test_missing_playlist_song_count_fails(self):
        p = pack()
        del p["playlist_song_count"]
        r, _ = self.runv(p)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("playlist_song_count", r.stdout)

    def test_not_invented_source_count_fails(self):
        p = pack()
        p["playlist_song_count"] = 10
        r, _ = self.runv(p)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("Playlist incomplete", r.stdout)

    def test_direct_track_id_only_url_is_normalized(self):
        r, saved = self.runv(pack(autoplay=False))
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertEqual(saved["songs"][0]["amazon_play_url"],
                         "https://music.amazon.de/tracks/C000000001?do=play")

    def test_missing_url_derived_only_from_track_asin(self):
        r, saved = self.runv(pack(only_asin=True))
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertEqual(saved["songs"][0]["amazon_play_url"],
                         "https://music.amazon.de/tracks/C000000001?do=play")

    def test_legacy_album_url_normalized_to_track(self):
        r, saved = self.runv(pack(legacy=True))
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertEqual(saved["songs"][0]["amazon_play_url"],
                         "https://music.amazon.de/tracks/C000000001?do=play")

    def test_legacy_album_url_without_do_play_normalized(self):
        r, saved = self.runv(pack(legacy=True, autoplay=False))
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertEqual(saved["songs"][0]["amazon_play_url"],
                         "https://music.amazon.de/tracks/C000000001?do=play")

    def test_extra_query_params_removed(self):
        p = pack()
        p["songs"][0]["amazon_play_url"] = (
            "https://music.amazon.de/tracks/C000000001?utm_source=spam&do=wrong"
        )
        r, saved = self.runv(p)
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertEqual(saved["songs"][0]["amazon_play_url"],
                         "https://music.amazon.de/tracks/C000000001?do=play")

    def test_lowercase_asin_normalized(self):
        p = pack()
        p["songs"][0]["amazon_play_url"] = "https://music.amazon.de/tracks/c000000001"
        r, saved = self.runv(p)
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertEqual(saved["songs"][0]["amazon_play_url"],
                         "https://music.amazon.de/tracks/C000000001?do=play")

    def test_check_only_rejects_direct_url_without_autoplay(self):
        r, ready = self.runv(pack())
        self.assertEqual(r.returncode, 0, r.stdout)
        ready["songs"][0]["amazon_play_url"] = "https://music.amazon.de/tracks/C000000001"
        ready["validation"]["songs_sha256"] = songs_hash(ready["songs"])
        r, _ = self.runv(ready, check=True)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("not canonical", r.stdout)

    def test_check_only_rejects_legacy_album_url(self):
        r, ready = self.runv(pack())
        self.assertEqual(r.returncode, 0, r.stdout)
        ready["songs"][0]["amazon_play_url"] = (
            "https://music.amazon.de/albums/B000000001?trackAsin=C000000001&do=play"
        )
        ready["validation"]["songs_sha256"] = songs_hash(ready["songs"])
        r, _ = self.runv(ready, check=True)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("not canonical", r.stdout)

    def test_legacy_album_missing_track_asin_fails(self):
        p = pack()
        p["songs"][0]["amazon_play_url"] = "https://music.amazon.de/albums/B000000001?do=play"
        r, _ = self.runv(p)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("valid Amazon Music DE track", r.stdout)

    def test_wrong_host_fails(self):
        p = pack()
        p["songs"][0]["amazon_play_url"] = "https://music.amazon.com/tracks/C000000001?do=play"
        r, _ = self.runv(p)
        self.assertNotEqual(r.returncode, 0)

    def test_wrong_host_not_repaired_from_optional_track_id(self):
        p = pack(full=True)
        p["songs"][0]["amazon_play_url"] = "https://evil.invalid/tracks/C000000001"
        r, _ = self.runv(p)
        self.assertNotEqual(r.returncode, 0)
        self.assertEqual(p["songs"][0]["amazon_track_asin"], "C000000001")

    def test_unknown_path_fails(self):
        p = pack()
        p["songs"][0]["amazon_play_url"] = "https://music.amazon.de/playlist/C000000001?do=play"
        r, _ = self.runv(p)
        self.assertNotEqual(r.returncode, 0)

    def test_invalid_track_id_fails(self):
        p = pack()
        p["songs"][0]["amazon_play_url"] = "https://music.amazon.de/tracks/NOTVALID?do=play"
        r, _ = self.runv(p)
        self.assertNotEqual(r.returncode, 0)

    def test_mismatch_track_query_with_direct_path_fails(self):
        p = pack()
        p["songs"][0]["amazon_play_url"] = "https://music.amazon.de/tracks/C000000001?trackAsin=C000000002&do=play"
        r, _ = self.runv(p)
        self.assertNotEqual(r.returncode, 0)

    def test_missing_play_url_and_missing_track_id_fails(self):
        p = pack()
        del p["songs"][0]["amazon_play_url"]
        r, _ = self.runv(p)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("amazon_play_url", r.stdout)

    def test_full_fields_and_optional_album_id_pass(self):
        r, saved = self.runv(pack(full=True))
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertEqual(saved["songs"][0]["amazon_album_id"], "B000000001")

    def test_optional_album_id_not_required_to_match_track_path(self):
        p = pack(full=True)
        p["songs"][0]["amazon_album_id"] = "B999999999"
        r, _ = self.runv(p)
        self.assertEqual(r.returncode, 0, r.stdout)

    def test_optional_ids_must_be_valid(self):
        p = pack(full=True)
        p["songs"][0]["amazon_album_id"] = "bad"
        r, _ = self.runv(p)
        self.assertNotEqual(r.returncode, 0)

    def test_track_id_metadata_mismatch_fails(self):
        p = pack(full=True)
        p["songs"][0]["amazon_track_asin"] = "C999999999"
        r, _ = self.runv(p)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("does not match", r.stdout)

    def test_duplicate_track_id_without_optional_id_fails(self):
        p = pack()
        p["songs"][1]["amazon_play_url"] = p["songs"][0]["amazon_play_url"]
        r, _ = self.runv(p)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("Duplicate Amazon track ASIN", r.stdout)

    def test_duplicate_song_id_fails(self):
        p = pack()
        p["songs"][1]["song_id"] = p["songs"][0]["song_id"]
        r, _ = self.runv(p)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("Duplicate song_id", r.stdout)

    def test_bad_year_fails(self):
        p = pack()
        p["songs"][0]["scoring_year"] = None
        r, _ = self.runv(p)
        self.assertNotEqual(r.returncode, 0)

    def test_19_songs_below_minimum(self):
        r, _ = self.runv(pack(19))
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("at least 20", r.stdout)

    def test_hash_tamper_fails_check_only(self):
        r, ready = self.runv(pack())
        self.assertEqual(r.returncode, 0, r.stdout)
        ready["songs"][0]["title"] = "Tampered"
        r, _ = self.runv(ready, check=True)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("songs_sha256", r.stdout)

    def test_check_only_passes_after_normal_validation(self):
        r, ready = self.runv(pack(legacy=True, autoplay=False))
        self.assertEqual(r.returncode, 0, r.stdout)
        r, _ = self.runv(ready, check=True)
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertIn("CHECK-ONLY", r.stdout)

    def test_three_user_tested_asins_have_correct_direct_url_shape(self):
        schema = json.loads(SCHEMA.read_text())
        pattern = schema["$defs"]["song"]["properties"]["amazon_play_url"]["pattern"]
        for asin in ("B076DWYFTR", "B093TL5Z2Z", "B0GC58JG6S"):
            url = f"https://music.amazon.de/tracks/{asin}?do=play"
            self.assertIsNotNone(re.fullmatch(pattern, url), url)

    def test_schema_requires_playlist_count_and_v15(self):
        schema = json.loads(SCHEMA.read_text())
        self.assertIn("playlist_song_count", schema["required"])
        self.assertEqual(schema["properties"]["schema_version"]["const"], "1.5")
        self.assertEqual(schema["properties"]["playlist_song_count"]["type"], "integer")


if __name__ == "__main__":
    unittest.main(verbosity=2)
