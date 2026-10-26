---
name: nerdio-pack-builder
description: Build complete reusable Nerdio gamepacks from Amazon Music Germany playlists, including saved HTML/MHTML snapshots when the public page is inaccessible. Use playlist track ASINs to create direct autoplay links without album IDs, verify original recording years with MusicBrainz, enforce full playlist coverage with the deterministic validator, and store the exact READY JSON bytes in Google Drive. Do not start gameplay.
---

# Nerdio Pack Builder

Create one reusable `gamepack.json` for an Amazon Music DE playlist. **Do not start gameplay.**

## Mandatory operating principles

1. **The playlist is the source of playback identity.** Read the complete playlist, retaining each track's title, displayed artist, 10-character Amazon track ASIN, position, and any already exposed version/duration metadata. A public playlist URL is the only required user input. A user-provided saved HTML/MHTML playlist snapshot is an accepted fallback when Amazon does not expose the list to the tool. Do not mistake a redirect to Amazon's home page for an empty playlist.
2. **Track ASIN is sufficient for the playback URL.** No album ASIN, album page, or per-song Amazon lookup is needed when the playlist supplies the track ASIN. The direct-track autoplay format was tested successfully by the user for multiple tracks in Amazon Music DE. This is evidence of their playback environment, not proof that every link plays in every environment.
3. **MusicBrainz supplies the scoring year.** Match normalized title + main artist to the correct recording and use the earliest official release year of that recording. A later remaster, reissue, or compilation does not change the recording year. Escalate only genuine live/remix/re-recording/acoustic/demo/cover/edit/version conflicts.
4. **Completeness comes before READY.** Record the actual complete playlist size in `playlist_song_count`. A 50-song playlist with only 20 validated songs must be `NOT_READY`, not a successful pack. Keep a separate report of unresolved songs and reasons; do not silently omit them or insert unverified entries.
5. **The validator owns final URL normalization and READY.** Build schema `1.5` with `status = "NOT_READY"`, run normal validation, then run `--check-only`. Only the validator may mark a pack READY. URL syntax checks do not prove a song was actually streamed.
6. **Drive handoff is verified from raw bytes.** Store a real `application/json` file (never a Google Doc) and require Drive metadata, raw download, strict validation, and byte-for-byte identity before reporting `Drive: PASSED`.

Read `references/verification-policy.md` before researching songs.

## Workflow

1. Parse the single Amazon Music DE playlist URL and obtain the entire playlist. If the live page is inaccessible, use a supplied HTML/MHTML snapshot; preserve the playlist URL/ID and extract the full song list and track ASINs from the snapshot. Confirm the actual source count before proceeding. Inspect the whole playlist, not just the first 20 results.
2. For each entry, extract a real 10-character alphanumeric track ASIN from the playlist's track link, ID, or structured DOM data. Preserve the exact track identity and track order. **Never invent or substitute an ASIN based on a similar title.** If an entry lacks a track ASIN, perform at most one targeted Amazon fallback lookup for that entry. Otherwise avoid individual Amazon track/album pages.
3. Set `amazon_track_asin` when known, and either set `amazon_play_url` to its direct-track link or let the normal validator derive it from the verified `amazon_track_asin`. No album ID or album URL is required. If an existing verified legacy album link is supplied, the validator converts it to a direct-track link.
4. For every source song, obtain `scoring_year` using MusicBrainz recording/release chronology. In ordinary unambiguous cases accept a clear matching title and primary artist; do not mandate ISRC, exact album, duration equality, or a second source. Use optional version information to distinguish separate recordings; unresolved versions are **not OK**.
5. Prepare `songs` with `song_id`, `title`, `artist`, `scoring_year`, `amazon_play_url` (or a grounded `amazon_track_asin` to generate it), `verification_status = "OK"`, and `verification_notes`. Keep optional album/version/duration/MusicBrainz/ISRC fields only when actually known. Do not fabricate metadata.
6. Set `playlist_song_count` from the fully inspected source, `validated_song_count` to `len(songs)`, `schema_version = "1.5"`, stable `pack_id` from the playlist ID, and `status = "NOT_READY"`. For `validation` initially set `validator_version = "1.5"`, `validated_at = null`, `songs_sha256 = null`. Schema: `references/gamepack-schema.json`.
7. If some playlist songs are missing from `songs`, report the exact count, positions, titles, and reasons as **NOT_READY**. Resolve remaining gaps instead of treating a 20-song minimum as permission to truncate. If the whole playlist has fewer than 20 songs, it cannot satisfy the standard gamepack minimum.
8. Run `python scripts/validate_pack.py gamepack.json`. It canonicalizes the direct-track URLs, checks that `playlist_song_count == validated_song_count == len(songs)`, checks IDs/years/uniqueness, computes the hash, and sets READY only on success.
9. Run `python scripts/validate_pack.py gamepack.json --check-only`. If this fails, do not publish the pack. Never hand-edit links or hashes after validation.
10. Read `references/google-drive-handoff.md`. Upload the exact validated local JSON bytes to `Nerdio/Gamepacks/<playlist_name>/gamepack.json` with MIME `application/json`. Verify stored metadata, download original raw bytes, and run both:
   - `python scripts/validate_pack.py drive-copy.json --check-only`
   - `python scripts/verify_drive_handoff.py --source gamepack.json --drive-copy drive-copy.json --metadata drive-metadata.json`
11. Only report `NERDIO PACK READY` and `Drive: PASSED` when all checks succeed. Otherwise distinguish local `READY` from a `FAILED/UNVERIFIED` Drive handoff, and provide the local validated `.json` download where possible.

## Canonical direct-track URL

The **only** canonical final value for `amazon_play_url` is:

`https://music.amazon.de/tracks/<TRACK_ASIN>?do=play`

Example verified by the user: `https://music.amazon.de/tracks/B076DWYFTR?do=play`.

- HTTPS, host exactly `music.amazon.de`, path `/tracks/` plus a 10-character uppercase alphanumeric ASIN, and query exactly `do=play`.
- No album ASIN, `trackAsin` query parameter, or extraneous query parameter in the final URL.
- In normal validation mode, legacy `https://music.amazon.de/albums/<ALBUM_ASIN>?trackAsin=<TRACK_ASIN>` input and noncanonical direct-track input are converted. In strict `--check-only` mode they are rejected until normalized.
- A missing or invalid track ASIN is a hard failure. An `amazon_album_id` is optional metadata and is never a playback prerequisite. If `amazon_track_asin` is present, it must agree with the URL's track identity.
- Do not convert an unrelated or suspicious nonempty URL into a legitimate-looking one using fallback metadata.

## Validation and reporting contract

- `playlist_song_count` is **required** and must equal the final `songs` array length; at least 20 OK songs are required for READY.
- Every retained song must be `OK`; do not include `PRUEFEN`/`AUSSCHLIESSEN` entries in the final `songs` array.
- Strict validation rejects malformed/noncanonical URLs, bad years, duplicate track ASINs (even without the optional ASIN metadata), duplicate song IDs, count differences, and hash tampering.
- Keep an explicit list of unresolved songs **outside** the final JSON. Do not claim that a partially processed playlist is complete.
- Count `amazon_fallback_lookups`; with playlist track ASINs this should normally be zero.
- The app's ability to open a URL and the validation of its URL format are different claims. Do not claim end-to-end autoplay was checked for every song unless the user actually tested them.

Report the complete source song count, OK song count, unresolved count, fallback lookups, validation status, and Drive status. Never start the game or reveal gameplay links in sequence.

## Bundled resources

- `references/verification-policy.md`
- `references/gamepack-schema.json`
- `references/google-drive-handoff.md`
- `scripts/validate_pack.py`
- `scripts/verify_drive_handoff.py`
- `tests/test_validate_pack.py`
- `tests/test_verify_drive_handoff.py`
