# Verification policy (direct-track links)

## Objective

Capture every song in an Amazon Music DE playlist without requiring album identities. Keep exact track ASINs and recording-specific year evidence. A partial playlist is NOT_READY even if 20 songs have been verified.

## Source roles

- **Amazon playlist or saved HTML/MHTML snapshot:** authoritative track selection, positions, titles, displayed artists, track ASINs, and any version/duration metadata shown there.
- **MusicBrainz:** authoritative starting point for chronology of the **matching recording**.
- **Individual Amazon track/album pages:** exceptional fallback only when the playlist does not expose a valid track ASIN. Never necessary solely to find an album ID or assign a scoring year.
- **User playback test:** the direct-track `?do=play` URL has been confirmed for several examples in the user's environment; URL validation is not a streaming test.

## Fast path

1. Inspect the whole playlist and capture the source count.
2. Extract the actual 10-character track ASIN for each song. For a saved HTML/MHTML page, inspect track-associated DOM IDs/links, not unrelated album/artwork IDs. Never infer an ASIN from the title alone.
3. Let the validator build `https://music.amazon.de/tracks/<TRACK_ASIN>?do=play` from a grounded `amazon_track_asin`, or normalize an existing direct-track link. **Do not look up album IDs.**
4. Search MusicBrainz for title + main artist, choose the clearly matching recording, and use its earliest official release year. Do not require ISRC/album/duration or a second source for ordinary unambiguous recordings.
5. Distinguish live versions, remixes, re-recordings, acoustic/demo tracks, covers, and materially different edits; remasters and compilations retain the underlying recording's year.
6. If a track ID or version/year cannot be grounded, mark it unresolved in a separate diagnostic report. Do not create a fake song entry and do not silently omit it from a READY pack.
7. Require `playlist_song_count == validated_song_count == len(songs)` before READY. Report `NOT_READY` when unresolved songs remain.

## Canonicalization and safety

- Accept legacy album URLs with a real `trackAsin` as input for backward compatibility, but normalize their final URL to the direct-track format. The album ASIN is optional information only.
- Do not repair a wrong-host or unknown nonempty URL using an unrelated optional ASIN field.
- Detect duplicate track ASINs from the actual URLs even if `amazon_track_asin` metadata is absent.
- Normal validation may repair missing `amazon_play_url` **only** when a verified `amazon_track_asin` is available.
- Do not claim that all URLs were manually played merely because the validator passes.
