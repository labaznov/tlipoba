"""Decode the observed export key shape without claiming a server API contract."""

import base64
import uuid


def decode(code: str) -> dict:
    """Return a mechanical UUID candidate from a 16-byte Base64 record key.

    Local exporter metadata exposes a Base64 build-code candidate and a record
    key shape; the export explicitly marks code and selection as unverified.
    UUID byte order here is only a display convention, not a proven server ID.
    Decoding does not retrieve build data or verify any transport endpoint.
    """
    try:
        if len(code) != 24:
            raise ValueError
        raw = base64.b64decode(code, validate=True)
        if len(raw) != 16 or base64.b64encode(raw).decode("ascii") != code:
            raise ValueError
    except (ValueError, TypeError):
        raise ValueError("Share code must be canonical standard Base64 for a 16-byte record key") from None
    return {
        "format": "tli-record-key",
        "record_key_hex": raw.hex(),
        "record_uuid": str(uuid.UUID(bytes=raw)),
        "transport_verified": False,
    }
