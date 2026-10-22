"""Read exact installed-skill catalog evidence without choosing effective levels or damage gates."""

import hashlib
import json
from pathlib import Path
import re

from .supportbundle import ERRORS, _pairs, _float, _constant


FILE = "installed-skill-catalog.json"
VERSION = "0.1.0"
MAX_BYTES = 64 * 1024 * 1024
FLAGS = ("arithmeticReady", "runtimeVerified", "identityVerified", "importComplete")
COUNTS = ("catalogDocuments", "requested", "records", "missing")


def _object(value, fields):
    if type(value) is not dict or not set(fields).issubset(value):
        raise ValueError("Installed skill catalog is missing required contract fields")


def _hash(value):
    if type(value) is not str or re.fullmatch(r"[0-9a-f]{64}", value) is None:
        raise ValueError("Installed skill catalog requires lowercase SHA256 hashes")


def _flags(value):
    if any(value.get(field) is not False for field in FLAGS):
        raise ValueError("Installed skill catalog cannot verify arithmetic runtime identity or completeness")


def read(package, descriptor, source_sha256, installation, *, max_bytes=MAX_BYTES):
    """Return safe lookup profiles and a hashed origin, retaining producer errors as missing evidence."""
    if type(max_bytes) is not int or not 1 <= max_bytes <= MAX_BYTES:
        raise ValueError("Installed skill catalog byte limit must be a positive integer up to 64 MiB")
    _hash(source_sha256)
    _object(descriptor, ("file", "version", "status", "sha256", "sourceSha256", *FLAGS, *COUNTS))
    if descriptor["file"] != FILE or descriptor["version"] != VERSION or descriptor["status"] not in ("diagnostic", "error"):
        raise ValueError("Installed skill catalog file version and status must match the supported contract")
    _flags(descriptor)
    _hash(descriptor["sha256"])
    code = descriptor.get("error")
    if descriptor["status"] == "error":
        if type(code) is not str or code not in ERRORS:
            raise ValueError("Installed skill catalog has an unsupported producer error")
    elif code is not None:
        raise ValueError("Diagnostic installed skill catalog cannot retain a producer error")
    source = descriptor["sourceSha256"]
    if source is None:
        if descriptor["status"] != "error" or code not in ("source_missing", "source_unreadable"):
            raise ValueError("Only unread source failures can lack an installed skill catalog source hash")
    else:
        _hash(source)
        if source != source_sha256:
            raise ValueError("Installed skill catalog descriptor differs from the package source hash")
    path = Path(package) / FILE
    with path.open("rb") as stream:
        raw = stream.read(max_bytes + 1)
    if len(raw) > max_bytes:
        raise ValueError("Installed skill catalog exceeds its supported byte limit")
    if hashlib.sha256(raw).hexdigest() != descriptor["sha256"]:
        raise ValueError("Installed skill catalog bytes differ from the descriptor hash")
    try:
        artifact = json.loads(raw.decode("utf-8"), object_pairs_hook=_pairs, parse_float=_float, parse_constant=_constant)
    except (ValueError, UnicodeError, RecursionError):
        raise ValueError("Installed skill catalog requires strict bounded UTF-8 JSON") from None
    _object(artifact, ("format", "version", "status", "source", *FLAGS))
    _object(artifact["source"], ("file", "sha256"))
    _flags(artifact)
    if (artifact["version"] != VERSION or artifact["status"] != descriptor["status"]
            or artifact["source"]["file"] != "source.json" or artifact["source"]["sha256"] != source):
        raise ValueError("Installed skill catalog artifact differs from its source or descriptor contract")
    origin = (str(path.resolve()), descriptor["sha256"], len(raw), int(descriptor["status"] == "diagnostic"))
    if descriptor["status"] == "error":
        if (artifact["format"] != "tli-installed-skill-catalog-error-v1" or artifact.get("error") != code
                or any(descriptor[field] is not None for field in COUNTS)
                or any(field in artifact for field in ("catalog", "requestedIds", "records"))):
            raise ValueError("Installed skill catalog errors require matching codes null counts and no semantic records")
        return None, origin
    _object(artifact, ("catalog", "requestedIds", "records"))
    if artifact["format"] != "tli-installed-skill-catalog-v1" or "error" in artifact:
        raise ValueError("Installed skill catalog diagnostic artifact has an unsupported contract")
    from .installedskills import summary as installation_summary
    from .supportcatalog import project as catalog_project
    from .installedprofiles import project

    observed = installation_summary(installation)
    if observed["source"]["sha256"] != source_sha256:
        raise ValueError("Installed skill catalog and installation must share the package source hash")
    catalog = catalog_project(artifact["catalog"])
    requested = None if observed["domains"]["client"]["status"] != "captured" else sorted({
        member["skill_id"] for group in observed["groups"] for member in group["members"]
        if member["skill_id"] is not None})
    claims = artifact["requestedIds"]
    if requested is None:
        if claims is not None or artifact["records"] is not None:
            raise ValueError("Unknown installation requires null requested IDs and catalog records")
        counts = (len(catalog["documents"]), None, None, None)
    else:
        if (type(claims) is not list or any(type(value) is not int or value < 1 for value in claims)
                or claims != requested or type(artifact["records"]) is not dict):
            raise ValueError("Requested catalog IDs must exactly cover the observed distinct installed skill IDs")
        if any(type(key) is not str or key not in {str(value) for value in requested} or type(value) is not dict
               for key, value in artifact["records"].items()):
            raise ValueError("Installed catalog records require exact requested ID keys and record objects")
        if len(artifact["records"]) > catalog["skills"]:
            raise ValueError("Selected installed records cannot outnumber the resolved catalog records")
        counts = (len(catalog["documents"]), len(requested), len(artifact["records"]), len(requested) - len(artifact["records"]))
    if any(type(descriptor[field]) is not type(value) or descriptor[field] != value
           for field, value in zip(COUNTS, counts)):
        raise ValueError("Installed skill catalog descriptor counts differ from its validated records")
    return project(artifact["records"], observed, catalog), origin
