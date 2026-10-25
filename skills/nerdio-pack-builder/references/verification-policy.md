# Verification policy

## Goal

Maximize playlist coverage while keeping Amazon work minimal and guarantee autoplay-safe Nerdio playback links.

## Source roles

- Amazon playlist data is authoritative for what will play and for playback identity.
- MusicBrainz is the primary source for `scoring_year`.
- Individual Amazon track/album pages are fallback-only when playlist data lacks a usable play URL or a recoverable `trackAsin`.

## Fast path

1. Read title, artist, play URL, and any optional metadata from the playlist entry.
2. Confirm the URL is an Amazon Music DE album URL with a recoverable `trackAsin`.
3. Do not open the Amazon track or album page.
4. Search MusicBrainz for title + main artist.
5. Prefer the clearly matching recording.
6. Use its earliest official release year.
7. If no material version conflict exists, mark `OK`.
8. Let `scripts/validate_pack.py` normalize the final URL to `...?trackAsin=<ASIN>&do=play`.

Do not require ISRC, exact album match, duration equality, Amazon album ID, track ASIN as a separate field, or a second source.

## Amazon fallback

Only when the playlist entry has no usable play URL or `trackAsin`, perform one focused Amazon lookup to recover a real playable URL. Do not use that lookup to determine the year. If the link cannot be grounded quickly, exclude the track.

## Exception triggers

Escalate only for materially distinct versions such as Live, Remix, Re-Recorded, Acoustic, Demo, Radio Edit, cover ambiguity, multiple materially different MusicBrainz recordings, or a strong duration/version conflict. `Remastered` alone normally keeps the original recording year.

## Resolution

Use playlist wording plus MusicBrainz evidence first. Optional playlist-supplied album/duration data may help. Use one additional reliable source only if necessary. If ambiguity remains, exclude the song and continue.
