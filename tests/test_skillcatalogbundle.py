import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from damage_lab.skillcatalogbundle import read


def persisted(directory, artifact, descriptor):
    raw = json.dumps(artifact, ensure_ascii=False, allow_nan=False).encode("utf-8")
    (directory / "installed-skill-catalog.json").write_bytes(raw)
    descriptor["sha256"] = hashlib.sha256(raw).hexdigest()


def failure(directory, code="catalog_shape", *, unbound=False):
    """Bind a fictional catalog acquisition failure to temporary source bytes."""
    source = directory / "source.json"
    if not source.exists():
        source.write_bytes(b"{}")
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    flags = {field: False for field in ("arithmeticReady", "runtimeVerified", "identityVerified", "importComplete")}
    artifact = {"format": "tli-installed-skill-catalog-error-v1", "version": "0.1.0", "status": "error",
                "error": code, "source": {"file": "source.json", "sha256": None if unbound else digest}, **flags}
    descriptor = {"file": "installed-skill-catalog.json", "version": "0.1.0", "status": "error", "error": code,
                  "sourceSha256": None if unbound else digest,
                  **{field: None for field in ("catalogDocuments", "requested", "records", "missing")}, **flags}
    persisted(directory, artifact, descriptor)
    return artifact, descriptor, digest


def diagnostic(directory):
    """Select one fictional catalog record for a source-bound four-gem installation."""
    from damage_lab.installedskills import project
    from test_installedskills import document
    from test_supportcatalog import document as catalog

    _, descriptor, source = failure(directory)
    raw = document()
    raw["source"]["sha256"] = source
    installation = project(raw, source)
    descriptor.pop("error")
    descriptor.update(status="diagnostic", catalogDocuments=3, requested=4, records=1, missing=3)
    artifact = {"format": "tli-installed-skill-catalog-v1", "version": "0.1.0", "status": "diagnostic",
                "source": {"file": "source.json", "sha256": source},
                **{field: False for field in ("arithmeticReady", "runtimeVerified", "identityVerified", "importComplete")},
                "catalog": catalog(), "requestedIds": [90017, 90029, 90041, 90053],
                "records": {"90017": {"tlidbId": 90017, "id": "synthetic-installed-spell", "category": "Active",
                    "tags": ["Spell", "Projectile", "Physical"], "mainStat": ["Dexterity"],
                    "effectivenessOfAddedDamage": "123%", "castSpeed": "0.73 s"}}}
    persisted(directory, artifact, descriptor)
    return artifact, descriptor, source, installation


def attached(directory, *, error=False):
    """Attach a fictional skill-catalog acquisition to a complete synthetic package."""
    if error:
        artifact, descriptor, _ = failure(directory)
    else:
        from test_skillbundle import attached as skills

        skills(directory)
        artifact, descriptor, _, _ = diagnostic(directory)
    path = directory / "manifest.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    manifest["installedSkillCatalog"] = descriptor
    path.write_text(json.dumps(manifest), encoding="utf-8")
    return artifact, descriptor


def focus(directory):
    """Attach a fictional Focus buff with exact saved catalog and installation bytes."""
    from test_installedprofiles import icefocus
    from test_skillbundle import attached as skills, saved

    raw, skill = skills(directory)
    raw["groups"][0]["members"][0].update(skillId=8318, gemLevel=17)
    saved(directory, raw, skill)
    artifact, descriptor, source, _ = diagnostic(directory)
    records, observed, metadata = icefocus(raw_catalog=True)
    observed["source"]["sha256"] = source
    artifact.update(records=json.loads(json.dumps(records, default=float)), catalog=metadata,
                    requestedIds=[8318, 90029, 90041, 90053])
    descriptor["catalogDocuments"] = len(metadata["documents"])
    persisted(directory, artifact, descriptor)
    path = directory / "manifest.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    manifest.update(installedSkills=skill, installedSkillCatalog=descriptor)
    path.write_text(json.dumps(manifest), encoding="utf-8")
    return descriptor, source, observed


class SkillCatalogBundleTests(unittest.TestCase):
    """Bind saved installed-skill catalog evidence without filling missing effective levels."""

    def test_passive_decimal_and_rational_cells_reach_the_source_bound_profile_without_rounding(self):
        from test_damage_archive import package

        with tempfile.TemporaryDirectory() as folder:
            directory = package(Path(folder))
            descriptor, source, observed = focus(directory)
            result, _ = read(directory, descriptor, source, observed)
            value = result["members"][0]["passive_effect"]
            self.assertEqual((value["candidate"]["value"]["fraction"], value["candidate"]["scope"],
                              value["effective_level"], value["arithmetic_ready"]),
                             ({"numerator": -13, "denominator": 800}, "focus_buff", None, False))

    def test_exact_decimal_support_cells_reach_the_ordinary_candidate_without_a_float_round_trip(self):
        from test_installedprofiles import ordinary

        with tempfile.TemporaryDirectory() as folder:
            directory = Path(folder)
            artifact, descriptor, source, _ = diagnostic(directory)
            records, observed, metadata = ordinary(raw_catalog=True)
            observed["source"]["sha256"] = source
            artifact.update(records=json.loads(json.dumps(records, default=float)), catalog=metadata,
                            requestedIds=[7420, 90029, 90041, 90053])
            descriptor["catalogDocuments"] = len(metadata["documents"])
            persisted(directory, artifact, descriptor)
            result, _ = read(directory, descriptor, source, observed)
            leaf = result["members"][0]["ordinary_support"]
            self.assertEqual((leaf["status"], leaf["candidate"]["value"]["fraction"], leaf["effective_level"]),
                             ("candidate", {"numerator": 37, "denominator": 400}, None))

    def test_a_hashed_producer_failure_remains_a_gap_without_installation_or_profiles(self):
        with tempfile.TemporaryDirectory() as folder:
            directory = Path(folder)
            _, descriptor, source = failure(directory)
            result, origin = read(directory, descriptor, source, None)
            self.assertEqual((result, origin), (None, (str((directory / descriptor["file"]).resolve()),
                descriptor["sha256"], (directory / descriptor["file"]).stat().st_size, 0)))

    def test_only_an_unread_source_failure_can_lack_the_source_hash(self):
        for code, valid in (("source_missing", True), ("source_unreadable", True), ("source_shape", False)):
            with self.subTest(code=code), tempfile.TemporaryDirectory() as folder:
                directory = Path(folder)
                _, descriptor, source = failure(directory, code, unbound=True)
                if valid:
                    self.assertIsNone(read(directory, descriptor, source, None)[0])
                else:
                    with self.assertRaises(ValueError):
                        read(directory, descriptor, source, None)

    def test_descriptor_file_versions_flags_counts_and_source_cannot_be_coerced(self):
        for field, value in (("file", "../secret.json"), ("version", "0.2.0"), ("status", "complete"),
                              ("arithmeticReady", 0), ("runtimeVerified", True), ("sourceSha256", "b" * 64),
                              ("records", 0), ("error", "PRIVATE-CATALOG-MARKER")):
            with self.subTest(field=field), tempfile.TemporaryDirectory() as folder:
                directory = Path(folder)
                _, descriptor, source = failure(directory)
                descriptor[field] = value
                with self.assertRaises(ValueError):
                    read(directory, descriptor, source, None)

    def test_artifact_bytes_cannot_change_after_the_descriptor_hash_is_recorded(self):
        with tempfile.TemporaryDirectory() as folder:
            directory = Path(folder)
            _, descriptor, source = failure(directory)
            with (directory / descriptor["file"]).open("ab") as stream:
                stream.write(b" ")
            with self.assertRaises(ValueError):
                read(directory, descriptor, source, None)

    def test_a_producer_error_cannot_retain_semantic_records_or_catalog_claims(self):
        for field, value in (("error", "source_shape"), ("version", "0.2.0"), ("runtimeVerified", True),
                              ("records", None), ("requestedIds", []), ("catalog", {})):
            with self.subTest(field=field), tempfile.TemporaryDirectory() as folder:
                directory = Path(folder)
                artifact, descriptor, source = failure(directory)
                artifact[field] = value
                persisted(directory, artifact, descriptor)
                with self.assertRaises(ValueError):
                    read(directory, descriptor, source, None)

    def test_strict_bounded_json_refuses_duplicate_nonfinite_and_unrepresentable_numbers(self):
        for suffix in (b',"status":"error"}', b',"extra":NaN}', b',"extra":1e999}',
                        b',"extra":1e-999999999999999999}', b',"extra":"\xff"}'):
            with self.subTest(suffix=suffix), tempfile.TemporaryDirectory() as folder:
                directory = Path(folder)
                artifact, descriptor, source = failure(directory)
                raw = json.dumps(artifact).encode("utf-8")[:-1] + suffix
                (directory / descriptor["file"]).write_bytes(raw)
                descriptor["sha256"] = hashlib.sha256(raw).hexdigest()
                with self.assertRaises(ValueError):
                    read(directory, descriptor, source, None)

    def test_byte_limits_are_strict_positive_integers_and_bound_the_actual_read(self):
        for limit in (True, 0, -1, 1.3, 64 * 1024 * 1024 + 1, 19):
            with self.subTest(limit=limit), tempfile.TemporaryDirectory() as folder:
                directory = Path(folder)
                _, descriptor, source = failure(directory)
                with self.assertRaises(ValueError):
                    read(directory, descriptor, source, None, max_bytes=limit)

    def test_diagnostics_profile_only_observed_gem_levels_and_keep_effective_levels_unknown(self):
        with tempfile.TemporaryDirectory() as folder:
            directory = Path(folder)
            _, descriptor, source, installation = diagnostic(directory)
            result, origin = read(directory, descriptor, source, installation)
            self.assertEqual((result["source"]["sha256"], result["members"][0]["gem_level"],
                              result["members"][0]["effective_level"], result["members"][0]["profile"]["level"],
                              result["arithmetic_ready"], origin[-1]), (source, 7, None, 7, False, 1))

    def test_descriptor_counts_must_match_exact_record_and_requested_id_cardinality(self):
        for field in ("catalogDocuments", "requested", "records", "missing"):
            for value in (None, True, 1.0, 29):
                with self.subTest(field=field, value=value), tempfile.TemporaryDirectory() as folder:
                    directory = Path(folder)
                    _, descriptor, source, installation = diagnostic(directory)
                    descriptor[field] = value
                    with self.assertRaises(ValueError):
                        read(directory, descriptor, source, installation)

    def test_selected_records_cannot_outnumber_all_resolved_catalog_records(self):
        with tempfile.TemporaryDirectory() as folder:
            directory = Path(folder)
            artifact, descriptor, source, installation = diagnostic(directory)
            artifact["catalog"].update(records=0, skills=0, invalidRecords=0, withheldRecords=0,
                                       recordsWithoutEnglish=0, withheldRecordIds=[])
            persisted(directory, artifact, descriptor)
            with self.assertRaises(ValueError):
                read(directory, descriptor, source, installation)

    def test_requested_ids_cannot_omit_duplicate_reorder_or_coerce_observed_identities(self):
        for identities in (None, [], [90017], [90017, 90017, 90029, 90041, 90053],
                           [90029, 90017, 90041, 90053], ["90017", 90029, 90041, 90053],
                           [True, 90029, 90041, 90053], [90017.0, 90029, 90041, 90053]):
            with self.subTest(identities=identities), tempfile.TemporaryDirectory() as folder:
                directory = Path(folder)
                artifact, descriptor, source, installation = diagnostic(directory)
                artifact["requestedIds"] = identities
                persisted(directory, artifact, descriptor)
                with self.assertRaises(ValueError):
                    read(directory, descriptor, source, installation)

    def test_record_keys_require_canonical_requested_ids_and_real_record_objects(self):
        for key, record in (("090017", {}), ("90019", {}), ("90017", None), ("90017", [])):
            with self.subTest(key=key, record=record), tempfile.TemporaryDirectory() as folder:
                directory = Path(folder)
                artifact, descriptor, source, installation = diagnostic(directory)
                artifact["records"] = {key: record}
                persisted(directory, artifact, descriptor)
                with self.assertRaises(ValueError):
                    read(directory, descriptor, source, installation)

    def test_diagnostics_require_a_valid_installation_bound_to_the_same_source(self):
        for invalid in (None, {}, "different-source"):
            with self.subTest(invalid=invalid), tempfile.TemporaryDirectory() as folder:
                directory = Path(folder)
                _, descriptor, source, installation = diagnostic(directory)
                if invalid == "different-source":
                    installation["source"]["sha256"] = "b" * 64
                else:
                    installation = invalid
                with self.assertRaises(ValueError):
                    read(directory, descriptor, source, installation)

    def test_unknown_installation_keeps_requests_and_records_null_without_zero_counts(self):
        from damage_lab.installedskills import project
        from test_installedskills import absent

        with tempfile.TemporaryDirectory() as folder:
            directory = Path(folder)
            artifact, descriptor, source, _ = diagnostic(directory)
            raw = absent("client", "absent")
            raw["source"]["sha256"] = source
            installation = project(raw, source)
            artifact.update(requestedIds=None, records=None)
            descriptor.update(requested=None, records=None, missing=None)
            persisted(directory, artifact, descriptor)
            result, _ = read(directory, descriptor, source, installation)
            self.assertEqual((result["client_layer"], result["members"], result["accounting"]),
                             ("absent", None, {"members": None, "profiled": None, "gaps": None, "reconciles": None}))

    def test_unknown_raw_catalog_text_is_not_copied_into_typed_profiles(self):
        with tempfile.TemporaryDirectory() as folder:
            directory = Path(folder)
            artifact, descriptor, source, installation = diagnostic(directory)
            artifact["records"]["90017"]["opaque"] = "PRIVATE-CATALOG-MARKER"
            artifact["catalog"]["opaque"] = "PRIVATE-CATALOG-MARKER"
            artifact["opaque"] = "PRIVATE-CATALOG-MARKER"
            persisted(directory, artifact, descriptor)
            self.assertNotIn("PRIVATE-CATALOG-MARKER", json.dumps(read(directory, descriptor, source, installation)[0]))

    def test_an_unrepresentable_decimal_exponent_has_a_controlled_error_with_either_trap_policy(self):
        from decimal import InvalidOperation, localcontext

        for trap in (True, False):
            with self.subTest(trap=trap), tempfile.TemporaryDirectory() as folder, localcontext() as context:
                context.traps[InvalidOperation] = trap
                directory = Path(folder)
                artifact, descriptor, source = failure(directory)
                raw = json.dumps(artifact).encode("utf-8")[:-1] + b',"extra":0e-999999999999999999999999999}'
                (directory / descriptor["file"]).write_bytes(raw)
                descriptor["sha256"] = hashlib.sha256(raw).hexdigest()
                with self.assertRaisesRegex(ValueError, "^Installed skill catalog requires strict bounded UTF-8 JSON$"):
                    read(directory, descriptor, source, None)
