#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

SCHEMA_VERSION = "1.5"
VALIDATOR_VERSION = "1.5"
STATUS_NOT_READY = "NOT_READY"
STATUS_READY = "READY"
MIN_PACK_SONGS = 20
MIN_YEAR = 1800
MAX_YEAR = 2100

AMAZON_ID_RE = re.compile(r"^[A-Z0-9]{10}$")
AMAZON_ID_LOOSE_RE = re.compile(r"^[A-Za-z0-9]{10}$")
AMAZON_ALBUM_PATH_RE = re.compile(r"^/albums/([A-Za-z0-9]{10})/?$")
AMAZON_TRACK_PATH_RE = re.compile(r"^/tracks/([A-Za-z0-9]{10})/?$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")

TOP_REQUIRED = (
    "schema_version", "pack_id", "playlist_url", "playlist_name", "created_at",
    "playlist_song_count", "validated_song_count", "status", "validation", "songs",
)
TOP_ALLOWED = set(TOP_REQUIRED)
SONG_REQUIRED = (
    "song_id", "title", "artist", "scoring_year", "amazon_play_url",
    "verification_status", "verification_notes",
)
SONG_OPTIONAL = {
    "album", "version", "duration_seconds", "amazon_album_id",
    "amazon_track_asin", "musicbrainz_recording_id", "isrc",
}
SONG_ALLOWED = set(SONG_REQUIRED) | SONG_OPTIONAL
VALIDATION_REQUIRED = ("validator_version", "validated_at", "songs_sha256")
VALIDATION_ALLOWED = set(VALIDATION_REQUIRED)


def nonempty(v: Any) -> bool:
    return isinstance(v, str) and bool(v.strip())


def valid_datetime(v: Any) -> bool:
    if not nonempty(v):
        return False
    try:
        d = datetime.fromisoformat(v[:-1] + "+00:00" if v.endswith("Z") else v)
    except ValueError:
        return False
    return d.tzinfo is not None


def songs_hash(songs: Any) -> str:
    raw = json.dumps(songs, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def canonical_url(track_asin: str) -> str:
    """Build the user-tested direct-track autoplay URL (no album context)."""
    return f"https://music.amazon.de/tracks/{track_asin}?do=play"


def parse_amazon_play_url(url: Any) -> tuple[str | None, str | None, str | None]:
    """Return (canonical_direct_track_url, optional_legacy_album_asin, track_asin).

    Accept direct-track URLs and legacy album URLs as *input*. Check-only
    validation requires the direct-track canonical output, never a legacy URL.
    """
    if not nonempty(url):
        return None, None, None
    try:
        parsed = urlparse(url.strip())
    except Exception:
        return None, None, None
    if parsed.scheme != "https" or parsed.netloc != "music.amazon.de":
        return None, None, None

    query = parse_qs(parsed.query, keep_blank_values=True)
    track_match = AMAZON_TRACK_PATH_RE.fullmatch(parsed.path)
    if track_match:
        track_asin = track_match.group(1).upper()
        query_track = query.get("trackAsin")
        if query_track and (len(query_track) != 1 or query_track[0].strip().upper() != track_asin):
            return None, None, None
        return canonical_url(track_asin), None, track_asin

    album_match = AMAZON_ALBUM_PATH_RE.fullmatch(parsed.path)
    if not album_match:
        return None, None, None
    track_values = query.get("trackAsin")
    if not track_values or len(track_values) != 1:
        return None, None, None
    track_asin = track_values[0].strip().upper()
    if not AMAZON_ID_LOOSE_RE.fullmatch(track_asin):
        return None, None, None
    return canonical_url(track_asin), album_match.group(1).upper(), track_asin


def normalize_pack_urls(pack: Any) -> None:
    """Canonicalize URLs; derive missing URLs solely from verified playlist track ASINs."""
    if not isinstance(pack, dict):
        return
    songs = pack.get("songs")
    if not isinstance(songs, list):
        return
    for song in songs:
        if not isinstance(song, dict):
            continue
        source_url = song.get("amazon_play_url")
        canonical, _, _ = parse_amazon_play_url(source_url)
        if canonical:
            song["amazon_play_url"] = canonical
        elif not nonempty(source_url):
            track_asin = song.get("amazon_track_asin")
            if isinstance(track_asin, str) and AMAZON_ID_LOOSE_RE.fullmatch(track_asin.strip()):
                song["amazon_play_url"] = canonical_url(track_asin.strip().upper())


def validate_pack(pack: Any, check_only: bool = False) -> list[str]:
    e: list[str] = []
    if not isinstance(pack, dict):
        return ["Top level must be a JSON object."]

    for f in TOP_REQUIRED:
        if f not in pack:
            e.append(f"Missing required top-level field: {f}")
    for f in sorted(set(pack) - TOP_ALLOWED):
        e.append(f"Unexpected top-level field: {f}")

    if pack.get("schema_version") != SCHEMA_VERSION:
        e.append(f"schema_version must be {SCHEMA_VERSION!r}.")
    if not nonempty(pack.get("pack_id")):
        e.append("pack_id must be a non-empty string.")

    purl = pack.get("playlist_url")
    if not nonempty(purl) or not purl.startswith("https://music.amazon.de/"):
        e.append("playlist_url must be a non-empty https://music.amazon.de/ URL.")
    if not nonempty(pack.get("playlist_name")):
        e.append("playlist_name must be a non-empty string.")
    if not valid_datetime(pack.get("created_at")):
        e.append("created_at must be an ISO-8601 date-time with timezone.")

    playlist_count = pack.get("playlist_song_count")
    if not isinstance(playlist_count, int) or isinstance(playlist_count, bool) or playlist_count < 0:
        e.append("playlist_song_count must be a non-negative integer sourced from the complete playlist.")

    count = pack.get("validated_song_count")
    if not isinstance(count, int) or isinstance(count, bool) or count < 0:
        e.append("validated_song_count must be a non-negative integer.")
    if pack.get("status") not in {STATUS_NOT_READY, STATUS_READY}:
        e.append("status must be NOT_READY or READY.")
    if check_only and pack.get("status") != STATUS_READY:
        e.append("check-only requires status READY.")

    val = pack.get("validation")
    if not isinstance(val, dict):
        e.append("validation must be an object.")
        val = {}
    else:
        for f in VALIDATION_REQUIRED:
            if f not in val:
                e.append(f"validation missing required field: {f}")
        for f in sorted(set(val) - VALIDATION_ALLOWED):
            e.append(f"validation has unexpected field: {f}")

    if val.get("validator_version") != VALIDATOR_VERSION:
        e.append(f"validation.validator_version must be {VALIDATOR_VERSION!r}.")
    if check_only:
        if not valid_datetime(val.get("validated_at")):
            e.append("validation.validated_at must be a valid timezone-aware date-time.")
        digest = val.get("songs_sha256")
        if not nonempty(digest) or not SHA256_RE.fullmatch(digest):
            e.append("validation.songs_sha256 must be a lowercase SHA-256 hex digest.")

    songs = pack.get("songs")
    if not isinstance(songs, list):
        e.append("songs must be an array.")
        return e
    if len(songs) < MIN_PACK_SONGS:
        e.append(f"Pool too small: {len(songs)} songs present, at least {MIN_PACK_SONGS} required.")
    if isinstance(count, int) and not isinstance(count, bool) and count != len(songs):
        e.append(f"validated_song_count is {count}, but songs contains {len(songs)} entries.")
    if isinstance(playlist_count, int) and not isinstance(playlist_count, bool) and playlist_count != len(songs):
        e.append(
            f"Playlist incomplete: playlist_song_count is {playlist_count}, "
            f"but songs contains only {len(songs)} entries. No partial READY pack."
        )

    seen_ids: dict[str, int] = {}
    seen_asins: dict[str, int] = {}

    for i, song in enumerate(songs):
        prefix = f"songs[{i}]"
        if not isinstance(song, dict):
            e.append(f"{prefix} must be an object.")
            continue

        for f in SONG_REQUIRED:
            if f not in song:
                e.append(f"{prefix} missing required field: {f}")
        for f in sorted(set(song) - SONG_ALLOWED):
            e.append(f"{prefix} has unexpected field: {f}")
        for f in ("song_id", "title", "artist", "amazon_play_url", "verification_notes"):
            if f in song and not nonempty(song.get(f)):
                e.append(f"{prefix}.{f} must be a non-empty string.")

        if song.get("verification_status") != "OK":
            e.append(f"{prefix}.verification_status must be OK.")

        year = song.get("scoring_year")
        if not isinstance(year, int) or isinstance(year, bool) or not MIN_YEAR <= year <= MAX_YEAR:
            e.append(f"{prefix}.scoring_year must be an integer between {MIN_YEAR} and {MAX_YEAR}.")

        url = song.get("amazon_play_url")
        canonical, _, url_track_asin = parse_amazon_play_url(url)
        if nonempty(url):
            if not canonical:
                e.append(
                    f"{prefix}.amazon_play_url must identify a valid Amazon Music DE track "
                    "(direct /tracks/<ASIN> or legacy album URL with trackAsin)."
                )
            elif url != canonical:
                e.append(
                    f"{prefix}.amazon_play_url is not canonical. Expected: {canonical}"
                )

        for f in ("album", "version", "musicbrainz_recording_id", "isrc"):
            if f in song and not nonempty(song.get(f)):
                e.append(f"{prefix}.{f}, when present, must be a non-empty string.")
        if "duration_seconds" in song and (
            not isinstance(song["duration_seconds"], int)
            or isinstance(song["duration_seconds"], bool)
            or song["duration_seconds"] <= 0
        ):
            e.append(f"{prefix}.duration_seconds, when present, must be a positive integer.")

        album_id = song.get("amazon_album_id")
        track_asin = song.get("amazon_track_asin")
        if album_id is not None and (not nonempty(album_id) or not AMAZON_ID_RE.fullmatch(album_id)):
            e.append(f"{prefix}.amazon_album_id, when present, must be 10 uppercase alphanumeric characters.")
        if track_asin is not None and (not nonempty(track_asin) or not AMAZON_ID_RE.fullmatch(track_asin)):
            e.append(f"{prefix}.amazon_track_asin, when present, must be 10 uppercase alphanumeric characters.")

        song_id = song.get("song_id")
        if nonempty(song_id):
            if song_id in seen_ids:
                e.append(f"Duplicate song_id {song_id!r} at songs[{i}] and songs[{seen_ids[song_id]}].")
            else:
                seen_ids[song_id] = i

        # Detect duplicates even when optional amazon_track_asin metadata is absent.
        identity_asin = url_track_asin or (track_asin if nonempty(track_asin) else None)
        if identity_asin:
            if identity_asin in seen_asins:
                e.append(
                    f"Duplicate Amazon track ASIN {identity_asin!r} at songs[{i}] and songs[{seen_asins[identity_asin]}]."
                )
            else:
                seen_asins[identity_asin] = i

        # Album ID is informational metadata only, never required for direct playback.
        if canonical and nonempty(track_asin) and track_asin != url_track_asin:
            e.append(
                f"{prefix}.amazon_track_asin does not match amazon_play_url track ASIN {url_track_asin}."
            )

    if check_only and isinstance(val, dict):
        digest = val.get("songs_sha256")
        if nonempty(digest) and SHA256_RE.fullmatch(digest) and digest != songs_hash(songs):
            e.append("validation.songs_sha256 does not match the current songs array.")

    return e


def write_json(path: Path, pack: dict[str, Any]) -> None:
    path.write_text(json.dumps(pack, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("pack", nargs="?", default="gamepack.json")
    parser.add_argument("--check-only", action="store_true")
    args = parser.parse_args(argv)
    path = Path(args.pack)

    try:
        pack = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception as ex:
        print("NERDIO PACK NOT READY")
        print(f"- Cannot read valid JSON: {ex}")
        return 1

    if not args.check_only:
        normalize_pack_urls(pack)

    errors = validate_pack(pack, args.check_only)
    if errors:
        if not args.check_only and isinstance(pack, dict):
            pack["status"] = STATUS_NOT_READY
            write_json(path, pack)
        print("NERDIO PACK NOT READY")
        for error in errors:
            print(f"- {error}")
        return 1

    if args.check_only:
        print("NERDIO PACK READY")
        print(f"Playlist: {pack['playlist_name']}")
        print(f"Pack ID: {pack['pack_id']}")
        print(f"Playlist-Songs: {pack['playlist_song_count']}")
        print(f"OK-Songs: {len(pack['songs'])}")
        print("Validierung: PASSED")
        print("Modus: CHECK-ONLY")
        return 0

    pack["validated_song_count"] = len(pack["songs"])
    pack["validation"] = {
        "validator_version": VALIDATOR_VERSION,
        "validated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "songs_sha256": songs_hash(pack["songs"]),
    }
    pack["status"] = STATUS_READY
    write_json(path, pack)

    print("NERDIO PACK READY")
    print(f"Playlist: {pack['playlist_name']}")
    print(f"Pack ID: {pack['pack_id']}")
    print(f"Playlist-Songs: {pack['playlist_song_count']}")
    print(f"OK-Songs: {len(pack['songs'])}")
    print("Validierung: PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
