"""Read exact memory-ledger artifact bytes without promoting declared catalog provenance."""

import hashlib
import json
import math
from pathlib import Path
import re

from .memorydefinitions import project as ledger_project, summary as ledger_summary


FILE = "memory-definition-ledger.json"
FORMAT = "tli-memory-definition-ledger-bundle-v1"
ERROR_FORMAT = "tli-memory-definition-ledger-error-v1"
VERSION = "0.1.0"
COMPILER = "0.1.1"
MAX_BYTES = 64 * 1024 * 1024
FLAGS = ("arithmeticReady", "runtimeVerified", "identityVerified", "importComplete")
COUNTS = ("catalogDocuments", "jewels", "rows", "candidates", "omitted", "structuralGaps")
MEMBERS = ("hero-memory/i18n/en", "hero-memory/master")
ERRORS = (
    "source_missing", "source_unreadable", "compiler_version_unreviewed", "source_too_large", "source_not_json",
    "source_duplicate_key", "source_nonfinite_number", "source_parse_limit", "source_shape",
    "catalog_location_invalid", "catalog_mapping_missing", "catalog_mapping_invalid", "catalog_mapping_conflict",
    "catalog_limit", "catalog_member_unmapped", "cache_token_invalid", "cache_file_missing", "cache_unreadable",
    "cache_not_json", "cache_not_object", "cache_duplicate_member", "cache_member_missing", "cache_parse_limit",
    "cache_duplicate_key", "cache_nonfinite_number", "compiler_failed", "compiler_ledger_mismatch", "artifact_limit",
)
ERROR = "Memory definition bundle contains an invalid source-bound diagnostic contract"


def _require(condition):
    if not condition:
        raise ValueError(ERROR)


def _object(value, fields):
    _require(type(value) is dict and set(fields).issubset(value))


def _hash(value):
    _require(type(value) is str and re.fullmatch(r"[0-9a-f]{64}", value) is not None)


def _false(value):
    _require(all(value.get(field) is False for field in FLAGS))


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        _require(key not in result)
        result[key] = value
    return result


def _float(token):
    value = float(token)
    _require(math.isfinite(value) and not (
        value == 0 and any(digit in "123456789" for digit in token.lower().partition("e")[0])))
    return value


def _constant(token):
    raise ValueError(ERROR)


def _bounds(value):
    stack, seen, count = [(value, 0)], set(), 0
    while stack:
        node, depth = stack.pop()
        count += 1
        _require(count <= 25_000 and depth <= 64)
        if type(node) in (dict, list):
            _require(id(node) not in seen and len(node) <= 4096)
            seen.add(id(node))
            if type(node) is dict:
                _require(all(type(key) is str for key in node))
                stack.extend((key, depth + 1) for key in node)
            stack.extend((child, depth + 1) for child in (node.values() if type(node) is dict else node))
        elif type(node) is str:
            _require(len(node) <= 4096)
            try:
                node.encode("utf-8")
            except UnicodeError:
                raise ValueError(ERROR) from None
        elif type(node) is float:
            _require(math.isfinite(node))
        else:
            _require(node is None or type(node) in (int, bool))


def _catalog(value, canonical):
    fields = ("derivation", "network_bytes_verified", "current_patch_verified", "documents") if canonical else (
        "derivation", "networkBytesVerified", "currentPatchVerified", "documents")
    _object(value, fields)
    _require(value[fields[0]] == "cache_member_exact_slice" and value[fields[1]] is False and value[fields[2]] is False)
    _require(type(value["documents"]) is list and len(value["documents"]) == 2)
    names = ("logical_path", "address", "cache_file", "wrapper_sha256", "member", "byte_range", "member_sha256", "encoding")
    keys = names if canonical else (
        "logicalPath", "address", "cacheFile", "wrapperSha256", "member", "byteRange", "memberSha256", "encoding")
    documents = []
    for entry in value["documents"]:
        _object(entry, keys)
        row = {name: entry[key] for name, key in zip(names, keys)}
        path = row["logical_path"]
        _require(type(path) is str and path in MEMBERS)
        _require(row["address"] == f"/data/SS14/{path}.json" and row["member"] == path and row["encoding"] == "utf-8")
        _require(type(row["cache_file"]) is str and re.fullmatch(r"[0-9a-f]{16}\.json", row["cache_file"]) is not None)
        _hash(row["wrapper_sha256"])
        _hash(row["member_sha256"])
        span = row["byte_range"]
        _require(type(span) is list and len(span) == 2 and all(type(number) is int for number in span)
                 and 0 <= span[0] < span[1] <= 32 * 1024 * 1024)
        row["byte_range"] = list(span)
        documents.append(row)
    _require({row["logical_path"] for row in documents} == set(MEMBERS))
    first, second = documents
    if first["cache_file"] == second["cache_file"]:
        _require(first["wrapper_sha256"] == second["wrapper_sha256"] and (
            first["byte_range"][1] <= second["byte_range"][0] or second["byte_range"][1] <= first["byte_range"][0]))
    return {"derivation": "cache_member_exact_slice", "network_bytes_verified": False,
            "current_patch_verified": False, "documents": documents}


def _join(ledger, catalog):
    _require(set(ledger["catalog"]["logical_paths"]) == {row["logical_path"] for row in catalog["documents"]})
    return {"ledger": ledger, "catalog": catalog}


def summary(pair):
    """Revalidate detached canonical data and declared coordinates without reading cache bytes."""
    _bounds(pair)
    _object(pair, ("ledger", "catalog"))
    return _join(ledger_summary(pair["ledger"]), _catalog(pair["catalog"], True))


def read(package, descriptor, source_sha256, *, max_bytes=MAX_BYTES):
    """Read one fixed artifact; producer errors retain a hashed origin and no semantic pair."""
    _require(type(max_bytes) is int and 1 <= max_bytes <= MAX_BYTES)
    _bounds(descriptor)
    _hash(source_sha256)
    _object(descriptor, ("file", "version", "compilerVersion", "status", "sha256", "sourceSha256", *FLAGS, *COUNTS))
    _require(descriptor["file"] == FILE and descriptor["version"] == VERSION and descriptor["compilerVersion"] == COMPILER)
    _require(descriptor["status"] in ("diagnostic", "error"))
    _false(descriptor)
    _hash(descriptor["sha256"])
    code = descriptor.get("error")
    if descriptor["status"] == "error":
        _require(type(code) is str and code in ERRORS)
    else:
        _require(code is None)
    source = descriptor["sourceSha256"]
    if source is None:
        _require(descriptor["status"] == "error" and code in ("source_missing", "source_unreadable"))
    else:
        _hash(source)
        _require(source == source_sha256)
    path = Path(package) / FILE
    with path.open("rb") as stream:
        raw = stream.read(max_bytes + 1)
    _require(len(raw) <= max_bytes and hashlib.sha256(raw).hexdigest() == descriptor["sha256"])
    try:
        artifact = json.loads(raw.decode("utf-8"), object_pairs_hook=_pairs, parse_float=_float, parse_constant=_constant)
        _bounds(artifact)
    except (UnicodeError, ValueError, RecursionError):
        raise ValueError("Memory definition artifact requires strict bounded UTF-8 JSON") from None
    _object(artifact, ("format", "version", "compilerVersion", "status", "source", *FLAGS))
    _object(artifact["source"], ("file", "sha256"))
    _false(artifact)
    _require(artifact["version"] == VERSION and artifact["compilerVersion"] == COMPILER
             and artifact["status"] == descriptor["status"] and artifact["source"]["file"] == "source.json"
             and artifact["source"]["sha256"] == source)
    origin = (str(path.resolve()), descriptor["sha256"], len(raw), int(descriptor["status"] == "diagnostic"))
    if descriptor["status"] == "error":
        _require(artifact["format"] == ERROR_FORMAT and artifact.get("error") == code
                 and all(descriptor[field] is None for field in COUNTS)
                 and not any(field in artifact for field in ("ledger", "catalog")))
        return None, origin
    _object(artifact, ("ledger", "catalog"))
    _require(artifact["format"] == FORMAT and "error" not in artifact)
    pair = _join(ledger_project(artifact["ledger"], source_sha256), _catalog(artifact["catalog"], False))
    expected = (2, *(pair["ledger"]["accounting"][field] for field in (
        "jewels", "rows", "candidates", "omitted", "structural_gaps")))
    _require(all(type(descriptor[field]) is type(value) and descriptor[field] == value for field, value in zip(COUNTS, expected)))
    return pair, origin
