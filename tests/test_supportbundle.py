import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from damage_lab.supportbundle import read


def failure(directory, code="catalog_shape", source=True):
    """Create a fictional producer failure bound to a real temporary source file."""
    path = directory / "source.json"
    if not path.exists():
        path.write_bytes(b"{}")
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    flags = {key: False for key in ("arithmeticReady", "runtimeVerified", "identityVerified", "importComplete")}
    artifact = {"format": "tli-installed-support-effects-error-v1", "version": "0.2.0", "status": "error",
                "error": code, "source": {"file": "source.json", "sha256": digest if source else None}, **flags}
    descriptor = {"file": "installed-support-effects.json", "version": "0.2.0", "inventoryVersion": "0.2.0",
                  "status": "error", "error": code, "sourceSha256": digest if source else None,
                  **flags, **{key: None for key in ("catalogDocuments", "members", "effectCandidates", "excluded", "gaps")}}
    persisted(directory, artifact, descriptor)
    return artifact, descriptor, digest


def persisted(directory, artifact, descriptor, raw=None):
    raw = json.dumps(artifact, ensure_ascii=False).encode("utf-8") if raw is None else raw
    (directory / "installed-support-effects.json").write_bytes(raw)
    descriptor["sha256"] = hashlib.sha256(raw).hexdigest()


def diagnostic(directory):
    """Bind synthetic candidate and catalog metadata factories to persisted package bytes."""
    from test_supportinventory import document as inventory
    from test_supportcatalog import document as catalog

    _, descriptor, source = failure(directory)
    descriptor.pop("error")
    descriptor.update(status="diagnostic", catalogDocuments=4, members=3, effectCandidates=1, excluded=1, gaps=1)
    artifact = {"format": "tli-installed-support-effects-bundle-v1", "version": "0.2.0", "status": "diagnostic",
                "inventoryVersion": "0.2.0", "source": {"file": "source.json", "sha256": source},
                **{field: False for field in ("arithmeticReady", "runtimeVerified", "identityVerified", "importComplete")},
                "inventory": inventory(), "catalog": catalog()}
    artifact["inventory"]["source"]["sha256"] = source
    path = "skill/Noble_Support/i18n/en"
    artifact["catalog"]["documents"].append({**artifact["catalog"]["documents"][1], "category": "Noble_Support",
        "logicalPath": path, "member": path, "address": f"/data/SS14/{path}.json", "byteRange": [411, 612]})
    artifact["catalog"]["categories"]["Noble_Support"]["english"] = "present"
    persisted(directory, artifact, descriptor)
    return artifact, descriptor, source


def attached(directory, *, error=False):
    """Add a synthetic diagnostic or acquisition gap to an existing fictional package."""
    artifact, descriptor, _ = failure(directory) if error else diagnostic(directory)
    path = directory / "manifest.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    manifest["installedSupportEffects"] = descriptor
    path.write_text(json.dumps(manifest), encoding="utf-8")
    return artifact, descriptor


class SupportBundleTests(unittest.TestCase):
    """Bind producer failures to actual artifact bytes without inventing an empty effect inventory."""

    def test_a_hashed_producer_error_is_an_explicit_gap_with_a_stored_false_origin(self):
        with tempfile.TemporaryDirectory() as folder:
            directory = Path(folder)
            _, descriptor, source = failure(directory)
            inventory, catalog, origin = read(directory, descriptor, source)
            self.assertEqual((inventory, catalog, origin), (None, None, (
                str((directory / "installed-support-effects.json").resolve()), descriptor["sha256"],
                (directory / "installed-support-effects.json").stat().st_size, 0)))

    def test_only_unread_source_failures_can_have_an_unbound_source_hash(self):
        for code, valid in (("source_missing", True), ("source_unreadable", True), ("source_shape", False)):
            with self.subTest(code=code), tempfile.TemporaryDirectory() as folder:
                directory = Path(folder)
                _, descriptor, source = failure(directory, code, source=False)
                if valid:
                    self.assertEqual(read(directory, descriptor, source)[:2], (None, None))
                else:
                    with self.assertRaises(ValueError):
                        read(directory, descriptor, source)

    def test_changed_artifact_bytes_cannot_reuse_a_descriptor_hash(self):
        with tempfile.TemporaryDirectory() as folder:
            directory = Path(folder)
            _, descriptor, source = failure(directory)
            with (directory / descriptor["file"]).open("ab") as handle:
                handle.write(b" ")
            with self.assertRaises(ValueError):
                read(directory, descriptor, source)

    def test_descriptor_source_versions_flags_counts_and_paths_are_not_coerced(self):
        for field, value in (("sourceSha256", "a" * 64), ("file", "../private.json"),
                              ("version", "0.1.0"), ("inventoryVersion", "0.1.0"),
                              ("runtimeVerified", 0), ("arithmeticReady", True), ("members", 0)):
            with self.subTest(field=field), tempfile.TemporaryDirectory() as folder:
                directory = Path(folder)
                _, descriptor, source = failure(directory)
                descriptor[field] = value
                with self.assertRaises(ValueError):
                    read(directory, descriptor, source)

    def test_artifact_error_code_source_and_claims_must_match_the_descriptor(self):
        for field, value in (("error", "private-marker"), ("version", "0.1.0"),
                              ("status", "diagnostic"), ("runtimeVerified", True), ("catalog", {})):
            with self.subTest(field=field), tempfile.TemporaryDirectory() as folder:
                directory = Path(folder)
                artifact, descriptor, source = failure(directory)
                artifact[field] = value
                persisted(directory, artifact, descriptor)
                with self.assertRaises(ValueError):
                    read(directory, descriptor, source)

    def test_nonfinite_duplicate_invalid_utf8_and_underflow_json_are_refused(self):
        for suffix in (b',"extra":NaN}', b',"extra":1e999}', b',"extra":1e-999999999999999999999}',
                        b',"status":"error"}', b',"extra":"\xff"}'):
            with self.subTest(suffix=suffix), tempfile.TemporaryDirectory() as folder:
                directory = Path(folder)
                artifact, descriptor, source = failure(directory)
                raw = json.dumps(artifact).encode("utf-8")[:-1] + suffix
                persisted(directory, artifact, descriptor, raw)
                with self.assertRaises(ValueError):
                    read(directory, descriptor, source)

    def test_the_reader_requires_a_bounded_positive_integer_limit(self):
        for limit in (True, 0, -1, 1.5, 64 * 1024 * 1024 + 1):
            with self.subTest(limit=limit), tempfile.TemporaryDirectory() as folder:
                directory = Path(folder)
                _, descriptor, source = failure(directory)
                with self.assertRaises(ValueError):
                    read(directory, descriptor, source, max_bytes=limit)

    def test_an_artifact_over_the_explicit_byte_limit_is_refused(self):
        with tempfile.TemporaryDirectory() as folder:
            directory = Path(folder)
            _, descriptor, source = failure(directory)
            with self.assertRaises(ValueError):
                read(directory, descriptor, source, max_bytes=23)

    def test_an_exporter_catalog_acquisition_gap_preserves_its_hashed_error_origin(self):
        with tempfile.TemporaryDirectory() as folder:
            directory = Path(folder)
            _, descriptor, source = failure(directory, "catalog_bytes_unavailable")
            self.assertEqual(read(directory, descriptor, source)[:2], (None, None))

    def test_diagnostics_return_canonical_source_bound_candidates_and_declared_catalog_metadata(self):
        with tempfile.TemporaryDirectory() as folder:
            directory = Path(folder)
            _, descriptor, source = diagnostic(directory)
            inventory, catalog, origin = read(directory, descriptor, source)
            self.assertEqual((inventory["source"]["sha256"], inventory["accounting"],
                              catalog["network_bytes_verified"], catalog["current_patch_verified"],
                              len(catalog["documents"]), origin[-1]),
                             (source, {"members": 3, "effect_candidates": 1, "excluded": 1, "gaps": 1,
                                       "reconciles": True}, False, False, 4, 1))

    def test_typed_candidates_require_their_declared_category_master_and_english_members(self):
        for role in ("english", "both"):
            with self.subTest(role=role), tempfile.TemporaryDirectory() as folder:
                directory = Path(folder)
                artifact, descriptor, source = diagnostic(directory)
                artifact["catalog"]["documents"] = [row for row in artifact["catalog"]["documents"]
                    if row["category"] != "Noble_Support" or role == "english" and row["role"] == "master"]
                artifact["catalog"]["categories"]["Noble_Support"] = {
                    "master": "present" if role == "english" else "missing", "english": "missing"}
                descriptor["catalogDocuments"] = len(artifact["catalog"]["documents"])
                persisted(directory, artifact, descriptor)
                with self.assertRaises(ValueError):
                    read(directory, descriptor, source)

    def test_a_withheld_catalog_identity_cannot_reappear_as_a_resolved_candidate(self):
        with tempfile.TemporaryDirectory() as folder:
            directory = Path(folder)
            artifact, descriptor, source = diagnostic(directory)
            artifact["catalog"]["withheldRecordIds"].append(90017)
            persisted(directory, artifact, descriptor)
            with self.assertRaises(ValueError):
                read(directory, descriptor, source)

    def test_canonical_pair_summary_rechecks_cross_catalog_claims(self):
        from damage_lab.supportbundle import summary

        with tempfile.TemporaryDirectory() as folder:
            directory = Path(folder)
            _, descriptor, source = diagnostic(directory)
            inventory, catalog, _ = read(directory, descriptor, source)
            catalog["withheld_record_ids"].append(90017)
            with self.assertRaises(ValueError):
                summary(inventory, catalog)

    def test_each_descriptor_count_must_match_the_validated_data_without_coercion(self):
        for field in ("catalogDocuments", "members", "effectCandidates", "excluded", "gaps"):
            for value in (None, True, 17, 1.0):
                with self.subTest(field=field, value=value), tempfile.TemporaryDirectory() as folder:
                    directory = Path(folder)
                    _, descriptor, source = diagnostic(directory)
                    descriptor[field] = value
                    with self.assertRaises(ValueError):
                        read(directory, descriptor, source)

    def test_nested_source_counts_catalog_claims_and_effect_values_are_revalidated(self):
        for path, value in ((("inventory", "source", "sha256"), "b" * 64),
                            (("inventory", "accounting", "members"), 4),
                            (("inventory", "runtimeVerified"), True),
                            (("catalog", "networkBytesVerified"), True),
                            (("catalog", "records"), 90),
                            (("catalog", "documents", 0, "member"), "../private"),
                            (("inventory", "members", 1, "effects", "arithmeticReady"), True)):
            with self.subTest(path=path), tempfile.TemporaryDirectory() as folder:
                directory = Path(folder)
                artifact, descriptor, source = diagnostic(directory)
                node = artifact
                for field in path[:-1]:
                    node = node[field]
                node[path[-1]] = value
                persisted(directory, artifact, descriptor)
                with self.assertRaises(ValueError):
                    read(directory, descriptor, source)

    def test_unknown_inventory_members_remain_null_instead_of_an_empty_inventory(self):
        with tempfile.TemporaryDirectory() as folder:
            directory = Path(folder)
            artifact, descriptor, source = diagnostic(directory)
            artifact["inventory"].update(clientLayer="not_captured", members=None)
            artifact["inventory"]["accounting"] = {field: None for field in artifact["inventory"]["accounting"]}
            descriptor.update(members=None, effectCandidates=None, excluded=None, gaps=None)
            persisted(directory, artifact, descriptor)
            inventory, _, _ = read(directory, descriptor, source)
            self.assertEqual((inventory["members"], inventory["accounting"]),
                             (None, {"members": None, "effect_candidates": None, "excluded": None,
                                     "gaps": None, "reconciles": None}))

    def test_unknown_nested_text_cannot_escape_into_the_safe_projections(self):
        with tempfile.TemporaryDirectory() as folder:
            directory = Path(folder)
            artifact, descriptor, source = diagnostic(directory)
            for node in (artifact, artifact["inventory"], artifact["inventory"]["members"][1],
                         artifact["inventory"]["members"][1]["effects"], artifact["catalog"],
                         artifact["catalog"]["documents"][0]):
                node["opaque"] = "PRIVATE-BUNDLE-CANARY"
            persisted(directory, artifact, descriptor)
            self.assertNotIn("PRIVATE-BUNDLE-CANARY", json.dumps(read(directory, descriptor, source)[:2]))
