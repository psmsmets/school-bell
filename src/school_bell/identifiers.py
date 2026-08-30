#!/usr/bin/python3

"""Deterministic identifiers for configuration and scheduled executions."""

import hashlib
import json


def canonical_json(value) -> bytes:
    """Serialize JSON data deterministically as UTF-8."""
    return json.dumps(
        value, ensure_ascii=False, separators=(',', ':'), sort_keys=True
    ).encode('utf-8')


def content_hash(value) -> str:
    """Return the SHA-256 hash of canonical JSON data."""
    return hashlib.sha256(canonical_json(value)).hexdigest()


def schedule_entry_id(weekday: str, local_time: str, wav_key: str) -> str:
    """Identify one normalized schedule entry."""
    return content_hash([weekday, local_time, str(wav_key)])


def trigger_id(device_id: str, schedule_hash: str, entry_id: str,
               planned_at: str) -> str:
    """Identify one planned execution across all related events."""
    return content_hash([
        device_id, schedule_hash, entry_id, planned_at
    ])
