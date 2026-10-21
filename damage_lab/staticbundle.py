"""Read a source-bound partial gear ledger and its declared local cache provenance."""

import hashlib
import json
import re
from pathlib import Path

from .staticcombat import VERSIONS as COMPILERS, project, summary as ledger_summary


FILE = "static-combat-modifiers.json"
VERSIONS = ("0.1.0", "0.1.1")
COUNTS = ("catalogDocuments", "compiled", "omitted", "structuralGaps")
CLAIMS = ("runtimeVerified", "importComplete", "identityVerified")
FIELDS = ("logicalPath", "address", "cacheFile", "cacheFileSha256", "member", "byteRange", "memberSha256", "encoding")
ERRORS = ("catalog_bytes_unavailable", "catalog_masters_missing", "cache_token_invalid", "cache_file_missing",
          "cache_member_missing", "cache_duplicate_member", "cache_not_json", "cache_not_object", "limit",
          "source_duplicate_key", "source_parse_limit", "source_not_json", "source_shape", "source_hash_mismatch", "source_too_large",
          "OSError", "PermissionError", "FileNotFoundError", "IsADirectoryError", "NotADirectoryError",
          "KeyError", "TypeError", "ValueError")


def _name(value):
    return re.sub(r"([A-Z])", r"_\1", value).lower()


def _fields(value, fields):
    if type(value) is not dict or not set(fields).issubset(value):
        raise ValueError("Static combat bundle requires all named contract fields")


def _pattern(value, pattern):
    if type(value) is not str or not re.fullmatch(pattern, value, re.ASCII):
        raise ValueError("Static combat bundle has an invalid provenance coordinate")


def _hash(value):
    _pattern(value, "[0-9a-f]{64}")


def _false(value, fields):
    if any(value.get(field) is not False for field in fields):
        raise ValueError("Static combat bundle cannot verify runtime completeness identity or freshness")


def _provenance(data, ledger, *, canonical=False):
    names = {field: _name(field) if canonical else field for field in ("derivation", "networkBytesVerified", "documents")}
    _fields(data, names.values())
    if data[names["derivation"]] != "cache_member_exact_slice" or data[names["networkBytesVerified"]] is not False:
        raise ValueError("Static combat catalog requires unverified local exact member slices")
    rows = data[names["documents"]]
    if type(rows) is not list or not 1 <= len(rows) <= 512:
        raise ValueError("Static combat catalog requires a bounded nonempty document list")
    result, paths, caches = [], set(), {}
    for row in rows:
        names = {field: _name(field) if canonical else field for field in FIELDS}
        _fields(row, names.values())
        entry = {_name(field): row[name] for field, name in names.items()}
        path = entry["logical_path"]
        _pattern(path, r"(?:gear|legendaries)/[a-z0-9_-]{1,64}(?:/[a-z0-9_-]{1,64}){0,4}/master")
        if path in paths or path not in ledger["catalog"]["documents"]:
            raise ValueError("Static combat catalog members must uniquely match compiler inputs")
        paths.add(path)
        if (entry["member"] != path or entry["address"] != f"/data/SS14/{path}.json"
                or entry["encoding"] != "utf-8"):
            raise ValueError("Static combat catalog address member and encoding must agree")
        _pattern(entry["cache_file"], r"[0-9a-f]{16}\.json")
        _hash(entry["cache_file_sha256"])
        _hash(entry["member_sha256"])
        if entry["member_sha256"] != ledger["catalog"]["documents"][path]["sha256"]:
            raise ValueError("Static combat catalog member hash differs from the compiler input")
        span = entry["byte_range"]
        if (type(span) is not list or len(span) != 2 or any(type(value) is not int for value in span)
                or not 0 <= span[0] < span[1] <= 32 * 1024 * 1024):
            raise ValueError("Static combat catalog byte ranges require bounded ordered integers")
        cache = caches.setdefault(entry["cache_file"], {"sha256": entry["cache_file_sha256"], "ranges": []})
        if cache["sha256"] != entry["cache_file_sha256"] or any(
                span[0] < end and start < span[1] for start, end in cache["ranges"]):
            raise ValueError("Static combat shared cache provenance cannot disagree or overlap")
        cache["ranges"].append(tuple(span))
        entry["byte_range"] = list(span)
        result.append(entry)
    if paths != set(ledger["catalog"]["documents"]):
        raise ValueError("Static combat catalog provenance must cover every compiler input")
    return {"derivation": "cache_member_exact_slice", "network_bytes_verified": False, "documents": result}


def summary(data, ledger):
    """Keep validated cache coordinates without copying unknown fields or opening files."""
    return _provenance(data, ledger_summary(ledger), canonical=True)


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Static combat bundle repeats a JSON member")
        result[key] = value
    return result


def _constant(value):
    raise ValueError("Static combat bundle contains a nonfinite JSON token")


def read(package, bundle, source, *, max_bytes=64 * 1024 * 1024):
    """Return a safe ledger, declared cache provenance and hashed artifact origin."""
    if type(max_bytes) is not int or max_bytes <= 0:
        raise ValueError("Static combat bundle size limit requires a positive integer")
    _hash(source)
    _fields(bundle, ("file", "status", "sha256", "sourceSha256", "version", "compilerVersion", "model",
                     *CLAIMS, "sourceSection", "catalogFlags", *COUNTS))
    if (bundle["file"] != FILE or bundle["status"] not in ("diagnostic", "error")
            or bundle["sourceSha256"] != source or bundle["version"] not in VERSIONS
            or bundle["compilerVersion"] not in COMPILERS or bundle["model"] != "partial"):
        raise ValueError("Static combat manifest has an invalid source or diagnostic contract")
    _false(bundle, CLAIMS)
    _hash(bundle["sha256"])
    path = Path(package) / FILE
    with path.open("rb") as stream:
        raw = stream.read(max_bytes + 1)
    if len(raw) > max_bytes:
        raise ValueError("Static combat artifact exceeds the supported size")
    digest = hashlib.sha256(raw).hexdigest()
    if digest != bundle["sha256"]:
        raise ValueError("Static combat artifact hash differs from its manifest")
    try:
        document = json.loads(raw.decode("utf-8"), object_pairs_hook=_pairs, parse_constant=_constant)
    except (ValueError, RecursionError):
        raise ValueError("Static combat artifact requires bounded UTF-8 JSON without duplicate or nonfinite members") from None
    _fields(document, ("format", "version", "status", "source", "runtimeVerified", "importComplete"))
    _fields(document["source"], ("file", "sha256"))
    if (document["format"] != "tli-static-combat-bundle-v1" or document["version"] != bundle["version"]
            or document["status"] != bundle["status"] or document["source"]["file"] != "source.json"
            or document["source"]["sha256"] != source):
        raise ValueError("Static combat artifact differs from its source or manifest contract")
    _false(document, ("runtimeVerified", "importComplete"))
    origin = (str(path.resolve()), digest, len(raw), int(document["status"] == "diagnostic"))
    if document["status"] == "error":
        if (document.get("error") not in ERRORS or document.get("error") != bundle.get("error")
                or any(key in document for key in ("ledger", "catalog", "model", "identityVerified", "freshnessVerified"))
                or any(bundle[key] is not None for key in ("sourceSection", "catalogFlags", *COUNTS))):
            raise ValueError("Static combat error artifacts cannot contain semantic ledger claims")
        return None, None, origin
    _fields(document, ("model", "identityVerified", "freshnessVerified", "catalog", "ledger"))
    _false(document, ("identityVerified", "freshnessVerified"))
    if document["model"] != "partial":
        raise ValueError("Static combat artifact must remain a partial model")
    ledger = project(document["ledger"], source)
    if ledger["version"] != bundle["compilerVersion"]:
        raise ValueError("Static combat ledger version differs from the manifest compiler version")
    provenance = _provenance(document["catalog"], ledger)
    for key, expected in (("catalogDocuments", len(provenance["documents"])),
                          ("compiled", ledger["accounting"]["compiled"]), ("omitted", ledger["accounting"]["omitted"]),
                          ("structuralGaps", ledger["accounting"]["structural_gaps"])):
        if type(bundle[key]) is not int or bundle[key] != expected:
            raise ValueError("Static combat manifest counts differ from the diagnostic ledger")
    if bundle["sourceSection"] != ledger["source"]["section"] or bundle["catalogFlags"] != ledger["catalog"]["flags"]:
        raise ValueError("Static combat manifest section or catalog flags differ from the ledger")
    return ledger, provenance, origin
