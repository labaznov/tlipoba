"""Read a source-bound installation inventory without applying support effects."""

import hashlib
import json
import math
import re
from pathlib import Path

from .installedskills import VERSION, project


FILE = "installed-skills.json"
MAX_BYTES = 64 * 2 ** 20
COUNTS = ("clientRows", "serverReconciled", "relationships", "issues")
CLAIMS = ("runtimeVerified", "identityVerified", "importComplete")
ERRORS = ("source_missing", "source_unreadable", "source_too_large", "source_not_json", "source_duplicate_key",
          "source_nonfinite_number", "source_parse_limit", "source_shape", "inventory_failed")


def _object(value, fields):
    if type(value) is not dict or not set(fields).issubset(value):
        raise ValueError("Installed skills bundle requires all named contract fields")


def _hash(value):
    if type(value) is not str or not re.fullmatch(r"[0-9a-f]{64}", value, re.ASCII):
        raise ValueError("Installed skills bundle requires exact SHA256 hashes")


def _false(value):
    if any(value.get(field) is not False for field in CLAIMS):
        raise ValueError("Installed skills bundle cannot verify runtime identity or completeness")


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Installed skills bundle repeats a JSON member")
        result[key] = value
    return result


def _float(token):
    value = float(token)
    if not math.isfinite(value):
        raise ValueError("Installed skills bundle has a nonfinite JSON number")
    return value


def _constant(token):
    raise ValueError("Installed skills bundle has a nonfinite JSON token")


def _read(path, limit, digest):
    with path.open("rb") as handle:
        raw = handle.read(limit + 1)
    if len(raw) > limit:
        raise ValueError("Installed skills bundle exceeds its supported size")
    if hashlib.sha256(raw).hexdigest() != digest:
        raise ValueError("Installed skills artifact differs from its descriptor hash")
    try:
        data = json.loads(raw.decode("utf-8"), object_pairs_hook=_pairs, parse_float=_float, parse_constant=_constant)
    except (UnicodeError, ValueError, RecursionError):
        raise ValueError("Installed skills bundle requires strict UTF-8 JSON") from None
    return data, len(raw)


def read(package, descriptor, source_sha256, *, max_bytes=MAX_BYTES):
    """Return a validated inventory or producer gap, plus the actual artifact origin."""
    if type(max_bytes) is not int or not 1 <= max_bytes <= MAX_BYTES:
        raise ValueError("Installed skills byte limit must be a positive integer up to 64 MiB")
    _hash(source_sha256)
    _object(descriptor, ("file", "status", "version", "sha256", "sourceSha256", *CLAIMS, *COUNTS))
    if descriptor["file"] != FILE or descriptor["version"] != VERSION:
        raise ValueError("Installed skills bundle file and version must match the supported contract")
    if descriptor["status"] not in ("diagnostic", "error"):
        raise ValueError("Installed skills bundle has an unsupported status")
    _hash(descriptor["sha256"])
    _false(descriptor)
    source = descriptor["sourceSha256"]
    code = descriptor.get("error")
    if descriptor["status"] == "error":
        if type(code) is not str or code not in ERRORS:
            raise ValueError("Installed skills bundle has an unsupported producer error")
    elif code is not None:
        raise ValueError("Diagnostic installed skills cannot retain a producer error")
    if source is None:
        if descriptor["status"] != "error" or code not in ("source_missing", "source_unreadable"):
            raise ValueError("Only unread source errors can lack an installed skills source hash")
    else:
        _hash(source)
        if source != source_sha256:
            raise ValueError("Installed skills descriptor differs from the package source hash")
    path = Path(package) / FILE
    artifact, size = _read(path, max_bytes, descriptor["sha256"])
    if descriptor["status"] == "error":
        _object(artifact, ("format", "version", "status", "error", "source", *CLAIMS))
        _object(artifact["source"], ("file", "sha256"))
        _false(artifact)
        if (artifact["format"] != "tli-support-inventory-error-v1" or artifact["version"] != "0.1.0"
                or artifact["status"] != "error" or artifact["error"] != code
                or artifact["source"]["file"] != "source.json" or artifact["source"]["sha256"] != source
                or any(descriptor[field] is not None for field in COUNTS)):
            raise ValueError("Installed skills producer errors require matching source code and null counts")
        return None, (str(path.resolve()), descriptor["sha256"], size, 0)
    data = project(artifact, source_sha256)
    client, server = data["domains"]["client"], data["domains"]["server"]
    expected = (client["rows"], server["reconciled"],
                len(data["relationships"]) if client["status"] == "captured" else None, len(data["issues"]))
    if any(type(descriptor[field]) is not type(value) or descriptor[field] != value
           for field, value in zip(COUNTS, expected)):
        raise ValueError("Installed skills descriptor counts differ from its validated inventory")
    return data, (str(path.resolve()), descriptor["sha256"], size, 1)
