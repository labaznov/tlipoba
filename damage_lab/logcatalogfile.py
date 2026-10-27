"""Read a bounded explicit saved skill-catalog input without discovering cache paths."""

import hashlib
import json
from pathlib import Path

from .logcatalog import validate
from .supportbundle import _constant, _float, _pairs

MAX_BYTES = 16 * 1024**2


def read(path, *, max_bytes=MAX_BYTES):
    """Return records, raw provenance and a hashed saved-file origin."""
    if type(max_bytes) is not int or not 1 <= max_bytes <= MAX_BYTES:
        raise ValueError("Saved skill catalog limit must be a positive integer up to 16 MiB")
    with Path(path).open("rb") as stream:
        raw = stream.read(max_bytes + 1)
    if len(raw) > max_bytes:
        raise ValueError("Saved skill catalog exceeds its byte limit")
    try:
        data = json.loads(raw.decode("utf-8"), object_pairs_hook=_pairs, parse_float=_float,
                          parse_constant=_constant)
    except (UnicodeError, RecursionError) as error:
        raise ValueError("Saved skill catalog must be bounded strict UTF-8 JSON") from error
    if (type(data) is not dict or set(data) != {"format", "version", "records", "catalog"}
            or data["format"] != "tli-log-skill-catalog-input-v1" or data["version"] != "0.1.0"):
        raise ValueError("Saved skill catalog requires the exact supported versioned envelope")
    validate(data["records"], data["catalog"])
    return data["records"], data["catalog"], {"kind": "saved_skill_catalog",
        "sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)}
