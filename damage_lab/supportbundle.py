"""Read source-bound support effect candidates and declared local catalog provenance."""

import hashlib
import json
import math
from pathlib import Path
import re


FILE = "installed-support-effects.json"
VERSION = "0.2.0"
MAX_BYTES = 64 * 1024 * 1024
FLAGS = ("arithmeticReady", "runtimeVerified", "identityVerified", "importComplete")
COUNTS = ("catalogDocuments", "members", "effectCandidates", "excluded", "gaps")
ERRORS = (
    "source_missing", "source_unreadable", "source_too_large", "source_not_json", "source_duplicate_key",
    "source_nonfinite_number", "source_parse_limit", "source_shape", "inventory_failed",
    "catalog_bytes_unavailable", "catalog_location_invalid", "catalog_mapping_missing", "catalog_mapping_invalid", "catalog_mapping_conflict",
    "catalog_masters_missing", "catalog_limit", "catalog_shape", "catalog_category_mismatch",
    "cache_token_invalid", "cache_file_missing", "cache_unreadable", "cache_not_object", "cache_not_json",
    "cache_duplicate_member", "cache_member_missing", "cache_duplicate_key", "cache_nonfinite_number", "cache_parse_limit",
)


def _object(value, fields):
    if type(value) is not dict or not set(fields).issubset(value):
        raise ValueError("Support effect bundle is missing required contract fields")


def _hash(value):
    if type(value) is not str or re.fullmatch(r"[0-9a-f]{64}", value) is None:
        raise ValueError("Support effect bundle requires lowercase SHA256 hashes")


def _false(value):
    if any(value.get(field) is not False for field in FLAGS):
        raise ValueError("Support effect bundle cannot verify arithmetic runtime identity or completeness")


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Support effect bundle repeats a JSON member")
        result[key] = value
    return result


def _float(token):
    value = float(token)
    if (not math.isfinite(value)
            or value == 0 and any(digit in "123456789" for digit in token.lower().partition("e")[0])):
        raise ValueError("Support effect bundle has an unrepresentable JSON number")
    return value


def _constant(token):
    raise ValueError("Support effect bundle has a nonfinite JSON constant")


def _join(inventory, catalog):
    from .supportinventory import CATEGORY_NAMES

    for member in inventory["members"] or []:
        if member["status"] != "effect_candidates":
            continue
        if member["base_id"] in catalog["withheld_record_ids"]:
            raise ValueError("Support effect candidates cannot resolve a withheld catalog identity")
        effect = member["effects"]
        if (effect["rolled_lines"] or effect["constants"]) and catalog["categories"].get(
                CATEGORY_NAMES[member["category"]]) != {"master": "present", "english": "present"}:
            raise ValueError("Typed support candidates require their category master and English catalog members")
    return inventory, catalog


def summary(inventory, catalog):
    """Revalidate a detached canonical pair and its internal catalog coordinates without byte reads."""
    from .supportinventory import summary as inventory_summary
    from .supportcatalog import summary as catalog_summary

    return _join(inventory_summary(inventory), catalog_summary(catalog))


def read(package, descriptor, source_sha256, *, max_bytes=MAX_BYTES):
    """Return a safe inventory, declared catalog metadata and hashed artifact origin.

    A producer error returns two null projections and an origin whose stored flag
    is zero; it does not turn an unavailable layer into an empty effect inventory.
    """
    if type(max_bytes) is not int or not 1 <= max_bytes <= MAX_BYTES:
        raise ValueError("Support effect byte limit must be a positive integer up to 64 MiB")
    _hash(source_sha256)
    _object(descriptor, ("file", "version", "inventoryVersion", "status", "sha256", "sourceSha256", *FLAGS, *COUNTS))
    if descriptor["file"] != FILE or descriptor["version"] != VERSION or descriptor["inventoryVersion"] != VERSION:
        raise ValueError("Support effect file and producer versions must match the supported contract")
    if descriptor["status"] not in ("diagnostic", "error"):
        raise ValueError("Support effect descriptor has an unsupported status")
    _false(descriptor)
    _hash(descriptor["sha256"])
    code = descriptor.get("error")
    if descriptor["status"] == "error":
        if type(code) is not str or code not in ERRORS:
            raise ValueError("Support effect descriptor has an unsupported producer error")
    elif code is not None:
        raise ValueError("Diagnostic support effects cannot retain a producer error")
    source = descriptor["sourceSha256"]
    if source is None:
        if descriptor["status"] != "error" or code not in ("source_missing", "source_unreadable"):
            raise ValueError("Only unread source errors can lack a support effect source hash")
    else:
        _hash(source)
        if source != source_sha256:
            raise ValueError("Support effect descriptor differs from the package source hash")
    path = Path(package) / FILE
    with path.open("rb") as stream:
        raw = stream.read(max_bytes + 1)
    if len(raw) > max_bytes:
        raise ValueError("Support effect artifact exceeds its supported size")
    if hashlib.sha256(raw).hexdigest() != descriptor["sha256"]:
        raise ValueError("Support effect artifact differs from its descriptor hash")
    try:
        artifact = json.loads(raw.decode("utf-8"), object_pairs_hook=_pairs, parse_float=_float, parse_constant=_constant)
    except (UnicodeError, ValueError, RecursionError):
        raise ValueError("Support effect artifact requires strict bounded UTF-8 JSON") from None
    _object(artifact, ("format", "version", "status", "source", *FLAGS))
    _object(artifact["source"], ("file", "sha256"))
    _false(artifact)
    if (artifact["version"] != VERSION or artifact["status"] != descriptor["status"]
            or artifact["source"]["file"] != "source.json" or artifact["source"]["sha256"] != source):
        raise ValueError("Support effect artifact differs from its source or descriptor contract")
    origin = (str(path.resolve()), descriptor["sha256"], len(raw), int(descriptor["status"] == "diagnostic"))
    if descriptor["status"] == "error":
        if (artifact["format"] != "tli-installed-support-effects-error-v1" or artifact.get("error") != code
                or any(descriptor[field] is not None for field in COUNTS)
                or any(field in artifact for field in ("inventory", "catalog", "inventoryVersion"))):
            raise ValueError("Support effect producer errors require matching codes null counts and no semantic data")
        return None, None, origin
    _object(artifact, ("inventoryVersion", "inventory", "catalog"))
    if (artifact["format"] != "tli-installed-support-effects-bundle-v1"
            or artifact["inventoryVersion"] != VERSION or "error" in artifact):
        raise ValueError("Support effect diagnostic artifact has an unsupported contract")
    from .supportinventory import project as inventory_project
    from .supportcatalog import project as catalog_project

    inventory = inventory_project(artifact["inventory"], source_sha256)
    catalog = catalog_project(artifact["catalog"])
    expected = (len(catalog["documents"]), inventory["accounting"]["members"],
                inventory["accounting"]["effect_candidates"], inventory["accounting"]["excluded"],
                inventory["accounting"]["gaps"])
    if any(type(descriptor[field]) is not type(value) or descriptor[field] != value
           for field, value in zip(COUNTS, expected)):
        raise ValueError("Support effect descriptor counts differ from its validated diagnostic data")
    inventory, catalog = _join(inventory, catalog)
    return inventory, catalog, origin
