# Google Drive handoff

## Goal and canonical location

Store an **actual importable JSON file** at `Nerdio/Gamepacks/<playlist_name>/gamepack.json`. A filename ending in `.json` is not sufficient: Drive metadata must identify the stored file as `application/json` (not `application/vnd.google-apps.document`).

Resolve folder and file IDs with Drive search or folder listing. Older `Hitster/Gamepacks/` files must not be moved or deleted without user permission.

## Required upload route

1. Run `python scripts/validate_pack.py gamepack.json --check-only` successfully on the local source.
2. Use the connected Drive **raw-file upload/update** action, with the validated local JSON file or supported uploaded-file reference, filename `gamepack.json`, and MIME type `application/json`. Use the connector's actual supported input contract. Some environments accept a local validated file path as the `file_uri` input; others require a connector-produced reference. Inspect the tool contract and result rather than guessing argument types. Do **not** call `import_document` or `create_file` with a Docs MIME type as a fallback.
3. For an existing raw `application/json` file, update its bytes in place if safe. If a legacy Google Doc named `gamepack.json` exists, it is not a valid replacement target for raw-byte update; do not delete it without authorization. Upload a raw JSON file and identify the exact resulting raw file URL/ID.
4. Read Drive metadata for the uploaded item (not just the upload response). Require `mime_type` / `mimeType` = `application/json`, `title` / `name` = `gamepack.json`, and a normal file. Reject any native Google Workspace MIME type and any `.txt`, `.docx`, or Google Doc substitute.

## Mandatory raw read-back

1. Download the saved file as **raw bytes** using Drive's raw download/fetch route (e.g. `fetch(download_raw_file=True)` or the connector's equivalent). A default text-mode `fetch` may return an empty `content` for binary/raw files; that is not a successful read-back. Use the returned complete byte stream or materializable authenticated file reference. Never read only Google Docs paragraphs and call that the saved JSON.
2. Save the exact returned bytes to `drive-copy.json`. If a transport byte-order mark occurs, preserve it for byte verification; never silently rewrite the stored copy to force equality.
3. Run `python scripts/validate_pack.py drive-copy.json --check-only`.
4. Save verified `get_file_metadata` output (the response object or its `result`) as `drive-metadata.json`, then run:

   `python scripts/verify_drive_handoff.py --source gamepack.json --drive-copy drive-copy.json --metadata drive-metadata.json`

5. Confirm both commands exit with code 0. This verifies that the stored Drive file is **byte-for-byte identical** to the validated local JSON and has the correct MIME type and name.

## Failure handling and user report

- Never mark `Drive: PASSED` for a Google Doc titled `gamepack.json`, a text file renamed to `.json`, or a file that was not downloaded and checked.
- If a raw upload fails, try an alternate **raw-file** route supported by the current connector, but **never** use Google Docs as a final substitute.
- If Drive's raw download is unavailable, say `Drive: UNVERIFIED` and provide a local validated `.json` download; do not claim handoff success.
- Keep the file private under the current user/workspace permissions; do not make it public.
- Report the exact Drive link of the raw file. If older same-titled Google Docs exist, make clear which link is the actual JSON.
- Do not claim an application-level upload was tested unless an authorized Nerdio app upload test actually ran.
