"""Private, bounded lexical context bound to an existing printed-tree snapshot."""

import hashlib
import json
import os
import re
from pathlib import Path

from . import buildlog

LIMITS = {"events": 20, "lines": 20_000, "line_bytes": 4096,
          "retained_bytes": 4 << 20, "artifact_bytes": 8 << 20, "neighbours": 20}
SENSITIVE = re.compile(r"authorization|bearer|password|secret|token|cookie|authkey|sessionkey", re.I)


def _events(snapshot):
    if snapshot["format"] != buildlog.FORMAT or snapshot["version"] not in ('0.1.3', buildlog.VERSION):
        raise ValueError("Unsupported log context snapshot")
    source = snapshot["source"]
    for field, limit in (("snapshotBytes", buildlog.LIMITS["max_source_bytes"]),
                         ("lines", buildlog.LIMITS["max_lines"])):
        if type(source[field]) is not int or not 0 <= source[field] <= limit:
            raise ValueError("Invalid log context source bounds")
    if not re.fullmatch(r"[0-9a-f]{64}", source["sha256"]):
        raise ValueError("Invalid log context source hash")
    events = []
    for field, status in (("events", "parsed"), ("rejected", "rejected")):
        if type(snapshot[field]) is not list or len(snapshot[field]) > buildlog.LIMITS["max_events"]:
            raise ValueError("Invalid log context event collection")
        for index, event in enumerate(snapshot[field]):
            start, end = event["start_line"], event["end_line"]
            if (type(start) is not int or type(end) is not int
                    or not 1 <= start <= end <= source["lines"]):
                raise ValueError("Invalid log context event bounds")
            events.append({"parser_status": status, "index": index,
                           "start_line": start, "end_line": end,
                           "window_start": max(1, start - LIMITS["neighbours"]),
                           "window_end": min(source["lines"], end + LIMITS["neighbours"])})
    events.sort(key=lambda event: event["start_line"])
    if (len(events) > buildlog.LIMITS["max_events"]
            or any(right["start_line"] <= left["end_line"] for left, right in zip(events, events[1:]))):
        raise ValueError("Invalid log context event ordering")
    return events


def collect(path, snapshot):
    """Recheck the initial source prefix and retain bounded physical-line windows.

    Hash equality binds two observations, without proving an atomic read or identity.
    Sensitive-marker omission is a heuristic; the entire artifact remains private.
    """
    events = _events(snapshot)
    source = snapshot["source"]
    selected = events[:LIMITS["events"]]
    digest, rows, retained, omitted, skipped, cursor, number = hashlib.sha256(), [], 0, 0, 0, 0, 0
    try:
        with Path(path).open("rb") as handle:
            if os.fstat(handle.fileno()).st_size < source["snapshotBytes"]:
                raise ValueError("Log context source prefix shrank")
            for number, data, length, raw, complete in buildlog.lines(
                    handle, source["snapshotBytes"], digest, LIMITS["line_bytes"], buildlog.LIMITS["chunk_bytes"]):
                if number > buildlog.LIMITS["max_lines"]:
                    raise ValueError("Log context source line limit exceeded")
                while cursor < len(selected) and number > selected[cursor]["window_end"]:
                    cursor += 1
                if cursor == len(selected) or number < selected[cursor]["window_start"]:
                    continue
                if len(rows) >= LIMITS["lines"]:
                    skipped += 1
                    continue
                row = {"number": number, "bytes": raw}
                if not complete:
                    row["omission"] = "incomplete_final_line"
                elif length > LIMITS["line_bytes"]:
                    row["omission"] = "line_limit"
                else:
                    try:
                        text = data.decode("utf-8")
                    except UnicodeDecodeError:
                        row["omission"] = "encoding"
                    else:
                        if SENSITIVE.search(text):
                            row["omission"] = "sensitive_marker"
                        elif retained + length > LIMITS["retained_bytes"]:
                            row["omission"] = "retained_limit"
                        else:
                            row["text"] = text
                            retained += length
                omitted += "omission" in row
                rows.append(row)
            if os.fstat(handle.fileno()).st_size < source["snapshotBytes"]:
                raise ValueError("Log context source prefix shrank")
    except buildlog.BuildLogError:
        raise ValueError("Log context source prefix unavailable") from None
    if digest.hexdigest() != source["sha256"] or number != source["lines"]:
        raise ValueError("Log context source prefix changed")
    result = {"format": "tli-log-context-v1", "version": "0.1.0",
              "scope": "source_bound_physical_lines", "events_merged": False,
              "import_complete": False, "identity": "unknown", "runtime": "unknown",
              "freshness": "unknown", "selected_skill": "unknown", "build_code": "unknown",
              "status": ("no_events" if not events else
                         "partial" if omitted or skipped or len(events) > len(selected) else "complete"),
              "source": {"sha256": source["sha256"], "snapshot_bytes": source["snapshotBytes"],
                         "lines": number}, "limits": dict(LIMITS),
              "omitted_events": len(events) - len(selected), "omitted_lines": omitted,
              "unretained_lines": skipped, "retained_bytes": retained,
              "events": selected, "lines": rows}
    if len(serialize(result)) > LIMITS["artifact_bytes"]:
        raise ValueError("Log context artifact byte limit exceeded")
    return result


def serialize(context):
    """Encode the bounded private packet consistently for saving and hashing."""
    return (json.dumps(context, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode("utf-8")
