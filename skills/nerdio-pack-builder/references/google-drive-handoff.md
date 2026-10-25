# Google Drive handoff

Use connected Google Drive as the durable boundary for reusable Nerdio packs.

## Canonical location

`Nerdio/Gamepacks/<playlist_name>/gamepack.json`

Resolve actual folder and file IDs with Drive search/listing before writes.

Older packs may still exist under `Hitster/Gamepacks/...`; do not move or delete them unless the user explicitly asks. New builds use the Nerdio path.

## Preferred storage

1. Prefer a raw `application/json` file when a Drive-uploadable file reference is available.
2. Otherwise create/use a native Google Doc titled `gamepack.json` as a transport container.
3. For the Google Doc fallback, the document body must be the exact JSON text only. Do not wrap it in Markdown or add human-readable headings.

## Read-back gate

After any create/update:

1. Fetch the stored Drive item again.
2. Extract the JSON text exactly.
3. Save it locally as `drive-copy.json`.
4. Run `python scripts/validate_pack.py drive-copy.json --check-only`.
5. Consider Drive handoff successful only when this command exits 0.

Do not make the file publicly accessible. Existing user/workspace permissions are sufficient.

## Replacement behavior

For the same playlist, prefer updating/replacing the canonical `gamepack.json` rather than creating multiple indistinguishable copies. If the connector cannot safely replace an existing item, create a uniquely timestamped item and return its exact Drive URL or ID so the user can import the correct file explicitly.
