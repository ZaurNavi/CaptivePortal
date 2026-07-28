"""Backfill CLI for captured Omada webhook JSONL records."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

from .webhook_normalized_journal import (
    OmadaWebhookNormalizedJournal,
)
from .webhook_normalizer import MODULE_NAME, SCHEMA_VERSION, normalize_webhook


@dataclass
class BackfillStats:
    raw_records_processed: int = 0
    text_items_processed: int = 0
    normalized_events: int = 0
    partial_events: int = 0
    unclassified_events: int = 0
    invalid_raw_lines: int = 0
    normalization_failures: int = 0

    def add_events(self, events: list[dict[str, Any]]) -> None:
        self.normalized_events += len(events)
        self.partial_events += sum(
            event.get("parse_status") == "partial"
            for event in events
        )
        self.unclassified_events += sum(
            event.get("parse_status") == "unclassified"
            for event in events
        )

    def format(self) -> str:
        return "\n".join(
            [
                (
                    "Raw records processed: "
                    f"{self.raw_records_processed}"
                ),
                (
                    "Text items processed: "
                    f"{self.text_items_processed}"
                ),
                f"Normalized events: {self.normalized_events}",
                f"Partial events: {self.partial_events}",
                (
                    "Unclassified events: "
                    f"{self.unclassified_events}"
                ),
                f"Invalid raw lines: {self.invalid_raw_lines}",
                (
                    "Normalization failures: "
                    f"{self.normalization_failures}"
                ),
            ]
        )


def normalize_log(
    *,
    input_path: str | os.PathLike[str],
    output_path: str | os.PathLike[str],
    overwrite: bool = False,
    append: bool = False,
) -> BackfillStats:
    """Normalize one raw JSONL file without stopping on bad lines."""
    if overwrite and append:
        raise ValueError("--overwrite and --append are mutually exclusive")

    source = Path(input_path)
    target = Path(output_path)
    if source.resolve() == target.resolve():
        raise ValueError("Input and output paths must be different")
    if not source.is_file():
        raise FileNotFoundError(f"Input file does not exist: {source}")

    _prepare_output(target, overwrite=overwrite, append=append)
    journal = OmadaWebhookNormalizedJournal(
        str(target),
        rotation_max_bytes=0,
        rotation_backup_count=0,
    )
    stats = BackfillStats()
    try:
        with source.open("rb") as stream:
            for line_number, raw_line in enumerate(stream, start=1):
                line_bytes = raw_line.rstrip(b"\r\n")
                if not line_bytes.strip():
                    continue
                stats.raw_records_processed += 1
                record = _strict_raw_record(line_bytes)
                if record is None:
                    stats.invalid_raw_lines += 1
                    events = [
                        invalid_raw_line_event(
                            line_number=line_number,
                            line_bytes=line_bytes,
                        )
                    ]
                else:
                    stats.text_items_processed += _text_item_count(
                        record
                    )
                    try:
                        events = normalize_webhook(record)
                    except Exception as exc:
                        stats.normalization_failures += 1
                        events = [
                            normalization_failure_event(
                                line_number=line_number,
                                line_bytes=line_bytes,
                                exception_type=type(exc).__name__,
                            )
                        ]
                journal.append_many(events)
                stats.add_events(events)
    finally:
        journal.close()
    return stats


def invalid_raw_line_event(
    *,
    line_number: int,
    line_bytes: bytes,
) -> dict[str, Any]:
    """Return a secret-safe deterministic diagnostic record."""
    return _backfill_diagnostic_event(
        line_number=line_number,
        line_bytes=line_bytes,
        reason="INVALID_RAW_JSON",
        exception_type=None,
    )


def normalization_failure_event(
    *,
    line_number: int,
    line_bytes: bytes,
    exception_type: str,
) -> dict[str, Any]:
    """Describe an internal per-line failure without input content."""
    return _backfill_diagnostic_event(
        line_number=line_number,
        line_bytes=line_bytes,
        reason="NORMALIZATION_FAILED",
        exception_type=exception_type,
    )


def _backfill_diagnostic_event(
    *,
    line_number: int,
    line_bytes: bytes,
    reason: str,
    exception_type: str | None,
) -> dict[str, Any]:
    line_sha256 = hashlib.sha256(line_bytes).hexdigest()
    id_prefix = (
        "invalid-raw"
        if reason == "INVALID_RAW_JSON"
        else "normalization-failed"
    )
    return {
        "timestamp": None,
        "level": "warning",
        "service": "captive_portal",
        "module": MODULE_NAME,
        "event": "omada.webhook_unclassified",
        "schema_version": SCHEMA_VERSION,
        "normalized_event_id": (
            f"{id_prefix}:{line_number}:{line_sha256}"
        ),
        "webhook_id": None,
        "text_index": None,
        "text_count": None,
        "received_at": None,
        "controller_timestamp": None,
        "controller_timestamp_ms": None,
        "delivery_latency_ms": None,
        "source_ip": None,
        "site": None,
        "controller_name": None,
        "payload_sha256": None,
        "parse_status": "unclassified",
        "parse_reason": reason,
        "parse_warnings": [],
        "raw_text": None,
        "source_line_number": line_number,
        "source_line_sha256": line_sha256,
        "exception_type": exception_type,
    }


def _prepare_output(
    target: Path,
    *,
    overwrite: bool,
    append: bool,
) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        if overwrite:
            target.open("wb").close()
            _chmod_created_file(target)
            return
        if append:
            return
        raise FileExistsError(
            f"Output file already exists: {target}. "
            "Use --overwrite or --append."
        )
    target.open("xb").close()
    _chmod_created_file(target)


def _chmod_created_file(target: Path) -> None:
    if os.name == "posix":
        os.chmod(target, 0o640)


def _strict_raw_record(line_bytes: bytes) -> dict[str, Any] | None:
    try:
        text = line_bytes.decode("utf-8", errors="strict")
        value = json.loads(
            text,
            parse_constant=_reject_json_constant,
        )
    except (UnicodeDecodeError, ValueError, RecursionError):
        return None
    return value if isinstance(value, dict) else None


def _reject_json_constant(value: str):
    raise ValueError(f"Non-standard JSON constant: {value}")


def _text_item_count(record: dict[str, Any]) -> int:
    payload = record.get("parsed_payload")
    if not isinstance(payload, dict):
        return 0
    text_items = payload.get("text")
    return len(text_items) if isinstance(text_items, list) else 0


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Normalize captured Omada webhook JSONL records."
    )
    parser.add_argument("--input", required=True, dest="input_path")
    parser.add_argument("--output", required=True, dest="output_path")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--overwrite", action="store_true")
    mode.add_argument("--append", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_argument_parser().parse_args(argv)
    try:
        stats = normalize_log(
            input_path=args.input_path,
            output_path=args.output_path,
            overwrite=args.overwrite,
            append=args.append,
        )
    except (FileExistsError, FileNotFoundError, ValueError) as exc:
        raise SystemExit(str(exc)) from exc
    print(stats.format())
    return 1 if stats.normalization_failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
