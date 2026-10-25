---
name: nerdio-pack-builder
description: Build a reusable READY Nerdio game pack from one public Amazon Music Germany playlist and persist it in connected Google Drive. Use when the user wants to create or refresh a Nerdio music pack from an Amazon Music DE playlist URL. Preserve playlist playback identity, use MusicBrainz primarily for scoring years, canonicalize every Amazon play URL to an autoplay-safe album link with trackAsin and do=play, validate the pack deterministically, persist a real application/json Drive file (not a Google Doc), verify its raw bytes, and never run gameplay.
---

# Nerdio Pack Builder

Build one reusable `gamepack.json` from a public Amazon Music Germany playlist. Do not conduct gameplay.

## Core principle

- **Read Amazon once at playlist level.** Treat the playlist entry as the playback identity and keep any title, artist, direct play URL, track URL, ASIN, album ID, album, version, or duration exposed by the playlist response.
- **Do not open individual Amazon track or album pages in the normal path.** Per-track Amazon lookup is fallback-only when the playlist entry does not expose a usable play URL.
- **MusicBrainz supplies chronology.** For ordinary songs, search title + main artist and use the earliest official release year of the clearly matching recording.
- **The validator owns final playback-link normalization.** The normal validation pass rewrites any usable Amazon Music DE album link into the canonical Nerdio form `https://music.amazon.de/albums/<ALBUM_ASIN>?trackAsin=<TRACK_ASIN>&do=play`. The final Drive copy must pass strict check-only validation without modification.
- **Deliver an actual JSON file.** A native Google Doc named `gamepack.json` is not an importable gamepack. Google Drive must store the output as a raw file with MIME type `application/json`; verify the MIME type and read back raw bytes before reporting success.
- Escalate only for real version ambiguity such as live, remix, re-recording, acoustic, demo, edit, or cover conflicts.

Read `references/verification-policy.md` before researching tracks.

## Hard boundaries

- Accept exactly one required user input: public Amazon Music DE playlist URL.
- Never ask for player count or target score.
- Inspect the whole playlist when practical; do not stop at 20 merely because the minimum is met.
- Require at least 20 final `OK` songs before a pack may become `READY`.
- Never invent titles, artists, play URLs, IDs, versions, durations, MusicBrainz IDs, ISRCs, or years.
- Never use Amazon album/reissue dates as `scoring_year` merely because they are available.
- Never use Amazon per-track pages to prove chronology.
- Never include `PRUEFEN` or `AUSSCHLIESSEN` candidates in the final `songs` array.
- Write `status = "NOT_READY"` before validation. Only `scripts/validate_pack.py` may set `READY`.
- Never hand-edit the final `amazon_play_url` after validation.
- Never start the game, assign start years, shuffle songs, or reveal links as gameplay.
- Never use `import_document` or create a Google Doc as the final `gamepack.json`. Filename and JSON-looking text do not make a Google Doc a JSON file.
- Never claim `Drive: PASSED` from upload acknowledgement, file title, or parsed Google Docs text alone. Require actual `application/json` metadata plus raw-byte readback and strict validation.

## Workflow

1. Parse the public Amazon Music DE playlist URL.
2. Read the playlist track list in as few Amazon requests as practical. Extract all track-level data available directly from that playlist response.
3. For each playlist track, require a real Amazon Music DE album playback URL containing a usable `trackAsin`. Reuse the direct URL already present in playlist data. It may omit `do=play` at this stage because the validator normalizes it.
4. If a playlist entry has no usable play URL or no recoverable `trackAsin`, perform at most one focused Amazon fallback lookup for that track to recover a real play URL. If it still cannot be grounded, exclude that track and continue.
5. Determine `scoring_year` with MusicBrainz:
   - search normalized title + main artist;
   - prefer the clearly matching recording;
   - use the earliest official release year associated with that recording;
   - when clear and no material version conflict exists, mark `OK` immediately.
6. Escalate only for version exceptions. Use playlist title/version wording, MusicBrainz recording/release evidence, and optional playlist-supplied duration/album metadata. Use one additional reliable source only if still needed. If unresolved, exclude the song and continue.
7. Apply year rules: remasters/reissues/compilations keep the underlying recording year; live recordings, re-recordings, remixes, covers, and materially distinct edits are separate recordings.
8. Create a stable `pack_id` from the playlist identity and write schema version `1.4` using `references/gamepack-schema.json`.
9. Required per-song fields are only: `song_id`, `title`, `artist`, `scoring_year`, `amazon_play_url`, `verification_status`, `verification_notes`. Album, version, duration, Amazon IDs, MusicBrainz ID, and ISRC are optional enrichment only when already known without extra Amazon browsing.
10. Set `validated_song_count`, keep top-level `status = "NOT_READY"`, and run:
   `python scripts/validate_pack.py gamepack.json`
   This pass canonicalizes every usable Amazon playback URL and then writes `READY` plus validation metadata.
11. Run a local strict verification pass:
   `python scripts/validate_pack.py gamepack.json --check-only`
   Do not persist a pack that fails this pass.
12. Read `references/google-drive-handoff.md` and persist the **actual locally validated `gamepack.json` bytes** in connected Google Drive at `Nerdio/Gamepacks/<playlist_name>/gamepack.json`, using a raw file upload/update, not a native Google Doc.
13. Read Drive file metadata after upload. Require name `gamepack.json` and MIME type exactly `application/json`; a Google Docs MIME type is a **hard failure**, regardless of its name.
14. Download the **raw stored file bytes** into `drive-copy.json` (not the Google Doc text extraction). Run:
   `python scripts/validate_pack.py drive-copy.json --check-only`
15. Save Drive metadata as `drive-metadata.json` and run the stronger handoff check:
   `python scripts/verify_drive_handoff.py --source gamepack.json --drive-copy drive-copy.json --metadata drive-metadata.json`
   It checks actual MIME type, name, strict pack validity, and byte-for-byte equality with the validated local source.
16. Report `Drive: PASSED` only when both checks exit 0. If raw upload or raw download is unavailable, report Drive handoff as **FAILED/UNVERIFIED**, supply the local validated `.json` download, and never substitute a Google Doc as a successful result.

## Canonical Amazon playback URL

Every final song must use exactly:

`https://music.amazon.de/albums/<10-char album ASIN>?trackAsin=<10-char track ASIN>&do=play`

Rules:

- host must be `music.amazon.de`;
- scheme must be `https`;
- path must be `/albums/<ALBUM_ASIN>`;
- `trackAsin` must be present and be 10 uppercase alphanumeric characters;
- `do=play` must be present;
- no unrelated query parameters may remain in the final validated link.

Do not manually concatenate final URLs in the reasoning loop. Let `scripts/validate_pack.py` canonicalize them in normal mode, then require `--check-only` to pass.

## Amazon lookup budget

Use Amazon playlist retrieval as the default and MusicBrainz as the per-song lookup. Individual Amazon track/album page reads are exceptional fallback operations, never the standard loop.

Track and report `amazon_fallback_lookups` internally while building. A normal successful build should have far fewer fallback lookups than playlist tracks.

## MusicBrainz matching policy

For ordinary tracks, do not require ISRC, exact album match, duration equality, or a second source. A song is `OK` when:

- the playlist provides a real playable Amazon link with a recoverable `trackAsin`;
- title + main artist clearly match a MusicBrainz recording;
- a plausible earliest official release year exists;
- no material version conflict is visible.

Use `PRUEFEN` only for genuine unresolved version/year ambiguity, not ordinary metadata imperfections.

## Game pack contract

Required song fields:

- `song_id`
- `title`
- `artist`
- `scoring_year`
- `amazon_play_url`
- `verification_status = "OK"`
- `verification_notes`

Optional song fields, only when already grounded:

- `album`
- `version`
- `duration_seconds`
- `amazon_album_id`
- `amazon_track_asin`
- `musicbrainz_recording_id`
- `isrc`

Do not browse Amazon merely to populate optional fields.

## Validation contract

The offline validator must fail for missing required fields, non-OK songs, invalid years, invalid/non-canonical Amazon play URLs in check-only mode, duplicate `song_id`, duplicate optional ASINs when present, fewer than 20 songs, count mismatches, or hash tampering.

In normal mode, the validator may normalize a structurally usable Amazon album URL by:

- extracting the album ASIN from `/albums/<ASIN>`;
- extracting `trackAsin` from the query string;
- removing unrelated query parameters;
- writing the canonical `trackAsin=<ASIN>&do=play` query.

A missing or invalid album ASIN or `trackAsin` is not repairable and must fail validation.

If optional `amazon_album_id` or `amazon_track_asin` are present, the validator must verify that they match the canonical play URL. Their absence must not fail validation.

## Final report

Print the READY report only when the raw Drive file passed metadata, raw-byte readback, and strict validation. Otherwise report local validation separately and mark `Drive: FAILED/UNVERIFIED`; do not describe the overall handoff as complete.

```text
NERDIO PACK READY
Playlist: ...
Pack ID: ...
Playlist-Songs: xx
OK-Songs: xx
Ausgeschlossen/unklar: xx
Amazon-Fallback-Lookups: xx
Validierung: PASSED
Drive: PASSED
```

## Bundled resources

- `references/verification-policy.md`
- `references/gamepack-schema.json`
- `references/google-drive-handoff.md`
- `scripts/validate_pack.py`
- `scripts/verify_drive_handoff.py`
- `tests/test_validate_pack.py`
- `tests/test_verify_drive_handoff.py`
