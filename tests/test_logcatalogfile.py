import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from damage_lab.logcatalogfile import read
from test_logcatalog import records
from test_supportcatalog import document as metadata


def envelope():
    """Bind a fictional explicit catalog envelope without live-source claims."""
    return {"format": "tli-log-skill-catalog-input-v1", "version": "0.1.0",
            "records": records(), "catalog": metadata()}


class LogCatalogFileTests(unittest.TestCase):
    """Read only the explicit bounded versioned input and verify its declared provenance."""

    def test_saved_catalog_input_retains_exact_byte_origin(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "catalog.json"
            raw = json.dumps(envelope()).encode("utf-8")
            path.write_bytes(raw)
            result = read(path, max_bytes=len(raw))
            self.assertEqual(result, (records(), metadata(), {"kind": "saved_skill_catalog",
                             "sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)}))

    def test_duplicate_nonfinite_underflow_and_invalid_utf8_are_refused(self):
        for raw in (b'{"format":1,"format":2}', b'{"x":NaN}', b'{"x":1e999}', b'{"x":1e-999}', b'\xff', b'{'):
            with self.subTest(raw=raw), tempfile.TemporaryDirectory() as folder:
                path = Path(folder) / "input.json"
                path.write_bytes(raw)
                with self.assertRaises(ValueError):
                    read(path, max_bytes=4096)

    def test_version_fields_and_claims_cannot_expand_the_envelope(self):
        for field, value in (("version", "9"), ("format", "other"), ("runtime_verified", True)):
            supplied = envelope()
            supplied[field] = value
            with self.subTest(field=field), tempfile.TemporaryDirectory() as folder:
                path = Path(folder) / "input.json"
                path.write_text(json.dumps(supplied), encoding="utf-8")
                with self.assertRaises(ValueError):
                    read(path, max_bytes=4096)

    def test_file_quota_and_limit_types_refuse_without_a_fallback(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "input.json"
            raw = json.dumps(envelope()).encode("utf-8")
            path.write_bytes(raw)
            for limit in (len(raw) - 1, 0, True, 16 * 1024**2 + 1):
                with self.subTest(limit=limit), self.assertRaises(ValueError):
                    read(path, max_bytes=limit)

    def test_record_and_catalog_semantics_are_validated_without_any_event(self):
        supplied = envelope()
        supplied["records"]["9001"]["tlidbId"] = 9011
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "input.json"
            path.write_text(json.dumps(supplied), encoding="utf-8")
            with self.assertRaises(ValueError):
                read(path, max_bytes=4096)
