#!/usr/bin/env python3
"""Verify that a persisted Nerdio pack is a real raw JSON Drive file.

This gate complements validate_pack.py: it checks Drive MIME metadata and
byte identity as well as the existing strict schema/hash/URL checks.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from validate_pack import validate_pack


def check_handoff(source: Path, drive_copy: Path, metadata_path: Path) -> list[str]:
    errors: list[str] = []
    try:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeError, ValueError) as exc:
        return [f"Cannot read Drive metadata JSON: {exc}"]
    if isinstance(metadata, dict) and isinstance(metadata.get("result"), dict):
        metadata = metadata["result"]
    if not isinstance(metadata, dict):
        return ["Drive metadata must be a JSON object."]

    mime = metadata.get("mime_type", metadata.get("mimeType"))
    name = metadata.get("title", metadata.get("name"))
    if mime != "application/json":
        errors.append(f"Drive MIME type must be application/json, got {mime!r}.")
    if name != "gamepack.json":
        errors.append(f"Drive filename must be gamepack.json, got {name!r}.")
    kind = metadata.get("file_or_folder")
    if kind and kind != "file":
        errors.append(f"Drive item must be a file, got {kind!r}.")

    try:
        source_raw = source.read_bytes()
        copy_raw = drive_copy.read_bytes()
    except OSError as exc:
        errors.append(f"Cannot read local or Drive copy: {exc}")
        return errors
    if source_raw != copy_raw:
        errors.append("Drive copy bytes differ from the locally validated source.")

    for label, raw in (("Source", source_raw), ("Drive copy", copy_raw)):
        try:
            pack = json.loads(raw.decode("utf-8-sig"))
        except (UnicodeError, ValueError) as exc:
            errors.append(f"{label} is not valid UTF-8 JSON: {exc}")
            continue
        for message in validate_pack(pack, check_only=True):
            errors.append(f"{label}: {message}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--drive-copy", type=Path, required=True)
    parser.add_argument("--metadata", type=Path, required=True)
    args = parser.parse_args()
    errors = check_handoff(args.source, args.drive_copy, args.metadata)
    if errors:
        print("NERDIO DRIVE HANDOFF FAILED")
        for error in errors:
            print(f"- {error}")
        return 1
    print("NERDIO DRIVE HANDOFF PASSED")
    print("MIME: application/json")
    print("Filename: gamepack.json")
    print("Drive bytes: IDENTICAL")
    print("Strict validation: PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
