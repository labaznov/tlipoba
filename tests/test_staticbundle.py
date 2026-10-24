import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from damage_lab.staticbundle import read, summary


def fixture(directory, *, error=False):
    """Create a fictional source-bound compiler bundle with one catalog member."""
    from test_staticcombat import document

    source = hashlib.sha256((directory / "source.json").read_bytes()).hexdigest()
    ledger = document()
    ledger["source"]["sha256"] = source
    path = next(iter(ledger["catalog"]["documents"]))
    artifact = {
        "format": "tli-static-combat-bundle-v1", "version": "0.1.0", "status": "diagnostic", "model": "partial",
        "runtimeVerified": False, "importComplete": False, "identityVerified": False, "freshnessVerified": False,
        "source": {"file": "source.json", "sha256": source},
        "catalog": {"derivation": "cache_member_exact_slice", "networkBytesVerified": False, "documents": [{
            "logicalPath": path, "address": "/data/SS14/" + path + ".json", "member": path,
            "cacheFile": "1234567890abcdef.json", "cacheFileSha256": "c" * 64, "byteRange": [17, 319],
            "memberSha256": "b" * 64, "encoding": "utf-8"}]}, "ledger": ledger}
    bundle = {
        "file": "static-combat-modifiers.json", "status": "diagnostic", "sourceSha256": source,
        "version": "0.1.0", "compilerVersion": "0.3.2", "model": "partial", "runtimeVerified": False,
        "importComplete": False, "identityVerified": False, "sourceSection": "captured", "catalogDocuments": 1,
        "catalogFlags": [], "compiled": 1, "omitted": 1, "structuralGaps": 1}
    if error:
        artifact = {key: artifact[key] for key in ("format", "version", "source", "runtimeVerified", "importComplete")}
        artifact.update(status="error", error="catalog_bytes_unavailable")
        bundle.update(status="error", error="catalog_bytes_unavailable")
        for key in ("sourceSection", "catalogDocuments", "catalogFlags", "compiled", "omitted", "structuralGaps"):
            bundle[key] = None
    saved(directory, artifact, bundle)
    return artifact, bundle


def saved(directory, artifact, bundle):
    """Persist synthetic artifact bytes and update only their descriptor hash."""
    raw = json.dumps(artifact, ensure_ascii=False, allow_nan=False).encode("utf-8")
    (directory / "static-combat-modifiers.json").write_bytes(raw)
    bundle["sha256"] = hashlib.sha256(raw).hexdigest()
    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    manifest["staticCombat"] = bundle
    (directory / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")


def package(directory):
    from test_damage_archive import package

    return package(directory)


def critical_bundle(directory):
    """Bind fictional compiler 0.4.0 critical metadata to exact package source bytes."""
    from test_staticcombat import critical

    artifact, bundle = fixture(directory)
    artifact["ledger"] = critical("critical_damage_modifier", "spell")
    artifact["ledger"]["source"]["sha256"] = bundle["sourceSha256"]
    artifact["version"] = bundle["version"] = "0.1.1"
    bundle["compilerVersion"] = "0.4.0"
    saved(directory, artifact, bundle)
    return artifact, bundle


def cast_bundle(directory):
    """Bind fictional omitted cast evidence to exact package bytes and its own catalog."""
    from test_staticcombat import casted

    artifact, bundle = fixture(directory)
    artifact["ledger"] = casted()
    artifact["ledger"]["source"]["sha256"] = bundle["sourceSha256"]
    artifact["version"] = bundle["version"] = "0.1.1"
    bundle["compilerVersion"] = "0.4.1"
    saved(directory, artifact, bundle)
    return artifact, bundle


def fixed_bundle(directory):
    """Bind one fictional fixed implicit to its master and English catalog declarations."""
    from test_staticcombat import fixed

    artifact, bundle = fixture(directory)
    artifact["ledger"] = fixed()
    artifact["ledger"]["source"]["sha256"] = bundle["sourceSha256"]
    artifact["version"] = bundle["version"] = "0.1.2"
    bundle["compilerVersion"] = "0.4.2"
    path = "gear/one_handed/wand/i18n/en"
    artifact["catalog"]["documents"].append({"logicalPath": path, "address": "/data/SS14/" + path + ".json",
        "member": path, "cacheFile": "fedcba0987654321.json", "cacheFileSha256": "d" * 64,
        "byteRange": [31, 477], "memberSha256": "c" * 64, "encoding": "utf-8"})
    bundle["catalogDocuments"] = 2
    saved(directory, artifact, bundle)
    return artifact, bundle


def lucky_bundle(directory):
    """Bind a fictional corroded critical compound to one declared glove catalog slice."""
    from test_staticcombat import lucky

    artifact, bundle = fixture(directory)
    artifact["ledger"] = lucky()
    artifact["ledger"]["source"]["sha256"] = bundle["sourceSha256"]
    artifact["version"] = bundle["version"] = "0.1.3"
    bundle["compilerVersion"] = "0.4.3"
    path = "legendaries/gloves/dex_gloves/master"
    artifact["catalog"]["documents"][0].update(logicalPath=path, member=path, address="/data/SS14/" + path + ".json")
    saved(directory, artifact, bundle)
    return artifact, bundle


def conditional_bundle(directory):
    """Bind one fictional conditional ledger to the new exact version pair."""
    from test_staticcombat import conditional

    artifact, bundle = fixture(directory)
    ledger = conditional()
    ledger['source']['sha256'] = bundle['sourceSha256']
    artifact['ledger'] = ledger
    artifact['version'] = bundle['version'] = '0.1.4'
    bundle.update(compilerVersion='0.4.4', omitted=0, structuralGaps=0)
    path = next(iter(ledger['catalog']['documents']))
    artifact['catalog']['documents'][0].update(logicalPath=path, address='/data/SS14/' + path + '.json', member=path)
    saved(directory, artifact, bundle)
    return artifact, bundle


class StaticBundleTests(unittest.TestCase):
    """Verify saved diagnostic metadata without accepting it as applied damage."""

    def test_conditional_bundle_keeps_unknown_target_condition(self):
        with tempfile.TemporaryDirectory() as folder:
            directory = package(Path(folder))
            _, bundle = conditional_bundle(directory)
            ledger, provenance, origin = read(directory, bundle, bundle['sourceSha256'])
            self.assertEqual(ledger['modifiers'][0]['condition'], {'kind': 'target_cursed', 'state': 'unknown'})

    def test_a_corroded_compound_round_trip_keeps_its_literal_and_own_scalar_source(self):
        with tempfile.TemporaryDirectory() as folder:
            directory = package(Path(folder))
            _, bundle = lucky_bundle(directory)
            ledger, provenance, origin = read(directory, bundle, bundle["sourceSha256"])
            row = ledger["modifiers"][0]
            self.assertEqual((row["semantics"]["lucky_critical_strike"], row["values"][0],
                              row["pool"]["status"], provenance["network_bytes_verified"], origin[-1]),
                             (True, {"exact": "23.75", "fraction": "0.2375", "source": "DynArgs[0]"},
                              "unresolved", False, 1))

    def test_bundle_013_preserves_the_paired_fixed_implicit_english_provenance(self):
        with tempfile.TemporaryDirectory() as folder:
            directory = package(Path(folder))
            artifact, bundle = fixed_bundle(directory)
            expected = read(directory, bundle, bundle["sourceSha256"])[:2]
            artifact["version"] = bundle["version"] = "0.1.3"
            artifact["ledger"]["version"] = bundle["compilerVersion"] = "0.4.3"
            expected[0]["version"] = "0.4.3"
            saved(directory, artifact, bundle)
            self.assertEqual(read(directory, bundle, bundle["sourceSha256"])[:2], expected)

    def test_compound_bundle_and_compiler_versions_cannot_be_mixed_with_older_contracts(self):
        for version, compiler in (("0.1.3", "0.4.2"), ("0.1.2", "0.4.3"), ("0.1.1", "0.4.3")):
            with self.subTest(version=version, compiler=compiler), tempfile.TemporaryDirectory() as folder:
                directory = package(Path(folder))
                artifact, bundle = fixture(directory, error=True)
                artifact["version"] = bundle["version"] = version
                bundle["compilerVersion"] = compiler
                saved(directory, artifact, bundle)
                with self.assertRaises(ValueError):
                    read(directory, bundle, bundle["sourceSha256"])

    def test_fixed_implicit_retains_exact_native_text_and_both_declared_catalog_members(self):
        with tempfile.TemporaryDirectory() as folder:
            directory = package(Path(folder))
            _, bundle = fixed_bundle(directory)
            ledger, provenance, origin = read(directory, bundle, bundle["sourceSha256"])
            value = ledger["modifiers"][0]["fixed_implicit"]
            self.assertEqual((value["own_value"]["exact"], value["arithmetic_ready"], len(provenance["documents"]),
                              summary(provenance, ledger), origin[-1]), ("37.12500", False, 2, provenance, 1))

    def test_fixed_implicit_english_provenance_cannot_drift_from_the_compiler_member(self):
        for field, invalid in (("memberSha256", "e" * 64), ("logicalPath", "gear/one_handed/staff/i18n/en"),
                               ("member", "gear/one_handed/staff/i18n/en"), ("byteRange", [True, 477])):
            with self.subTest(field=field), tempfile.TemporaryDirectory() as folder:
                directory = package(Path(folder))
                artifact, bundle = fixed_bundle(directory)
                artifact["catalog"]["documents"][1][field] = invalid
                saved(directory, artifact, bundle)
                with self.assertRaises(ValueError):
                    read(directory, bundle, bundle["sourceSha256"])

    def test_english_only_catalog_cannot_replace_the_required_master_acquisition(self):
        from test_staticcombat import empty

        with tempfile.TemporaryDirectory() as folder:
            directory = package(Path(folder))
            artifact, bundle = fixed_bundle(directory)
            english = artifact["ledger"]["catalog"]["documents"]["gear/one_handed/wand/i18n/en"]
            artifact["ledger"] = empty("empty")
            artifact["ledger"].update(version="0.4.2", catalog={"documents": {"gear/one_handed/wand/i18n/en": english}, "flags": []})
            artifact["ledger"]["source"]["sha256"] = bundle["sourceSha256"]
            artifact["catalog"]["documents"] = artifact["catalog"]["documents"][1:]
            bundle.update(sourceSection="empty", catalogDocuments=1, compiled=0, omitted=0, structuralGaps=0)
            saved(directory, artifact, bundle)
            with self.assertRaisesRegex(ValueError, "master"):
                read(directory, bundle, bundle["sourceSha256"])

    def test_fixed_implicit_bundle_errors_remain_hashed_gaps_without_ledger_claims(self):
        with tempfile.TemporaryDirectory() as folder:
            directory = package(Path(folder))
            artifact, bundle = fixture(directory, error=True)
            artifact["version"] = bundle["version"] = "0.1.2"
            bundle["compilerVersion"] = "0.4.2"
            saved(directory, artifact, bundle)
            self.assertEqual(read(directory, bundle, bundle["sourceSha256"])[:2], (None, None))

    def test_fixed_implicit_bundle_and_compiler_versions_cannot_be_mixed_with_legacy_contracts(self):
        for artifact_version, compiler in (("0.1.1", "0.4.2"), ("0.1.0", "0.4.2"), ("0.1.2", "0.4.1")):
            with self.subTest(bundle=artifact_version, compiler=compiler), tempfile.TemporaryDirectory() as folder:
                directory = package(Path(folder))
                artifact, bundle = fixture(directory, error=True)
                artifact["version"] = bundle["version"] = artifact_version
                bundle["compilerVersion"] = compiler
                saved(directory, artifact, bundle)
                with self.assertRaises(ValueError):
                    read(directory, bundle, bundle["sourceSha256"])

    def test_hashed_cast_evidence_retains_own_roll_and_declared_catalog_without_arithmetic(self):
        with tempfile.TemporaryDirectory() as folder:
            directory = package(Path(folder))
            _, descriptor = cast_bundle(directory)
            ledger, provenance, origin = read(directory, descriptor, descriptor["sourceSha256"])
            self.assertEqual((ledger["omitted"][0]["evidence"]["own_values"][0]["exact"],
                              ledger["omitted"][0]["evidence"]["arithmetic_ready"], origin[-1],
                              summary(provenance, ledger) == provenance), ("17.8750", False, 1, True))

    def test_new_critical_compiler_bundle_keeps_arithmetic_blocked(self):
        with tempfile.TemporaryDirectory() as folder:
            directory = package(Path(folder))
            _, bundle = critical_bundle(directory)
            self.assertIs(read(directory, bundle, bundle["sourceSha256"])[0]
                          ["modifiers"][0]["semantics"]["arithmetic_ready"], False)

    def test_manifest_compiler_version_must_equal_the_projected_ledger_version(self):
        for descriptor, ledger in (("0.3.2", "0.4.0"), ("0.4.0", "0.3.2")):
            with self.subTest(descriptor=descriptor), tempfile.TemporaryDirectory() as folder:
                directory = package(Path(folder))
                artifact, bundle = fixture(directory)
                bundle["compilerVersion"] = descriptor
                artifact["ledger"]["version"] = ledger
                saved(directory, artifact, bundle)
                with self.assertRaises(ValueError):
                    read(directory, bundle, bundle["sourceSha256"])

    def test_new_compiler_error_is_a_gap_without_zero_effects(self):
        with tempfile.TemporaryDirectory() as folder:
            directory = package(Path(folder))
            artifact, bundle = fixture(directory, error=True)
            bundle["compilerVersion"] = "0.4.0"
            saved(directory, artifact, bundle)
            self.assertEqual(read(directory, bundle, bundle["sourceSha256"])[:2], (None, None))

    def test_bundle_preserves_bound_ledger_and_catalog_derivation(self):
        with tempfile.TemporaryDirectory() as folder:
            directory = package(Path(folder))
            _, bundle = fixture(directory)
            ledger, provenance, origin = read(directory, bundle, bundle["sourceSha256"])
            self.assertEqual((ledger["runtime"]["verified"], ledger["modifiers"][0]["values"][0]["exact"],
                              provenance["network_bytes_verified"], provenance["documents"][0]["byte_range"], origin[-1]),
                             (False, "11.0", False, [17, 319], 1))

    def test_manifest_rejects_other_files_versions_sources_and_verification(self):
        for key, value in (("file", "../static-combat-modifiers.json"), ("version", "0.2.0"),
                           ("compilerVersion", "0.3.1"), ("sourceSha256", "e" * 64), ("model", "complete"),
                           ("runtimeVerified", 0), ("importComplete", True), ("identityVerified", True),
                           ("status", "ready")):
            with self.subTest(key=key), tempfile.TemporaryDirectory() as folder:
                directory = package(Path(folder))
                _, bundle = fixture(directory)
                bundle[key] = value
                with self.assertRaises(ValueError):
                    read(directory, bundle, hashlib.sha256((directory / "source.json").read_bytes()).hexdigest())

    def test_artifact_requires_exact_bytes_and_rejects_a_rehashed_other_source(self):
        for change in ("bytes", "source", "file", "version", "status", "freshness"):
            with self.subTest(change=change), tempfile.TemporaryDirectory() as folder:
                directory = package(Path(folder))
                artifact, bundle = fixture(directory)
                if change == "bytes":
                    path = directory / bundle["file"]
                    path.write_bytes(path.read_bytes() + b" ")
                else:
                    if change == "source":
                        artifact["source"]["sha256"] = "d" * 64
                    elif change == "file":
                        artifact["source"]["file"] = "another.json"
                    elif change == "freshness":
                        artifact["freshnessVerified"] = True
                    else:
                        artifact[change] = "other"
                    saved(directory, artifact, bundle)
                with self.assertRaises(ValueError):
                    read(directory, bundle, bundle["sourceSha256"])

    def test_manifest_counts_and_flags_match_the_projected_ledger(self):
        for key, value in (("sourceSection", "empty"), ("compiled", True), ("omitted", 1.0),
                           ("structuralGaps", 0), ("catalogDocuments", 2), ("catalogFlags", ["catalog_season_mixed"])):
            with self.subTest(key=key), tempfile.TemporaryDirectory() as folder:
                directory = package(Path(folder))
                _, bundle = fixture(directory)
                bundle[key] = value
                with self.assertRaises(ValueError):
                    read(directory, bundle, bundle["sourceSha256"])

    def test_catalog_coordinates_and_hashes_are_strict(self):
        cases = (("logicalPath", "gear/../master"), ("address", "/data/SS15/gear/wand/master.json"),
                 ("member", "gear/other/master"), ("cacheFile", "../1234567890abcdef.json"),
                 ("cacheFileSha256", "private"), ("memberSha256", "d" * 64), ("encoding", "utf-16"),
                 ("byteRange", [True, 319]), ("byteRange", [319, 17]), ("byteRange", [17, 17]),
                 ("byteRange", [-1, 319]), ("byteRange", [17, 32 * 1024 * 1024 + 1]))
        for key, value in cases:
            with self.subTest(key=key, value=value), tempfile.TemporaryDirectory() as folder:
                directory = package(Path(folder))
                artifact, bundle = fixture(directory)
                artifact["catalog"]["documents"][0][key] = value
                saved(directory, artifact, bundle)
                with self.assertRaises(ValueError):
                    read(directory, bundle, bundle["sourceSha256"])

    def test_catalog_requires_one_provenance_row_for_each_compiler_input(self):
        for change in ("missing", "duplicate", "extra", "network", "derivation"):
            with self.subTest(change=change), tempfile.TemporaryDirectory() as folder:
                directory = package(Path(folder))
                artifact, bundle = fixture(directory)
                catalog = artifact["catalog"]
                if change == "missing":
                    catalog["documents"] = []
                elif change in ("duplicate", "extra"):
                    catalog["documents"].append(copy.deepcopy(catalog["documents"][0]))
                    if change == "extra":
                        catalog["documents"][-1]["logicalPath"] = "gear/other/master"
                else:
                    catalog["networkBytesVerified" if change == "network" else "derivation"] = True
                saved(directory, artifact, bundle)
                with self.assertRaises(ValueError):
                    read(directory, bundle, bundle["sourceSha256"])

    def test_cache_rows_cannot_disagree_about_a_shared_wrapper_or_overlap(self):
        for change in ("hash", "overlap"):
            with self.subTest(change=change), tempfile.TemporaryDirectory() as folder:
                directory = package(Path(folder))
                artifact, bundle = fixture(directory)
                path = "gear/other/master"
                artifact["ledger"]["catalog"]["documents"][path] = copy.deepcopy(
                    next(iter(artifact["ledger"]["catalog"]["documents"].values())))
                row = copy.deepcopy(artifact["catalog"]["documents"][0])
                row.update(logicalPath=path, member=path, address="/data/SS14/" + path + ".json", byteRange=[320, 515])
                row["cacheFileSha256" if change == "hash" else "byteRange"] = "e" * 64 if change == "hash" else [300, 515]
                artifact["catalog"]["documents"].append(row)
                bundle["catalogDocuments"] = 2
                saved(directory, artifact, bundle)
                with self.assertRaises(ValueError):
                    read(directory, bundle, bundle["sourceSha256"])

    def test_summary_drops_unknown_fields_without_losing_catalog_evidence(self):
        with tempfile.TemporaryDirectory() as folder:
            directory = package(Path(folder))
            artifact, bundle = fixture(directory)
            for row in (artifact, artifact["catalog"], artifact["catalog"]["documents"][0]):
                row["raw"] = "PRIVATE-BUNDLE-MARKER"
            saved(directory, artifact, bundle)
            ledger, provenance, _ = read(directory, bundle, bundle["sourceSha256"])
            provenance["raw"] = "PRIVATE-BUNDLE-MARKER"
            provenance["documents"][0]["raw"] = "PRIVATE-BUNDLE-MARKER"
            self.assertNotIn("PRIVATE-BUNDLE-MARKER", json.dumps(summary(provenance, ledger)))

    def test_error_has_no_ledger_or_zero_effect_claims(self):
        with tempfile.TemporaryDirectory() as folder:
            directory = package(Path(folder))
            _, bundle = fixture(directory, error=True)
            ledger, provenance, origin = read(directory, bundle, bundle["sourceSha256"])
            self.assertEqual((ledger, provenance, origin[-1]), (None, None, 0))

    def test_source_oversize_error_from_patch_version_keeps_its_full_source_binding(self):
        with tempfile.TemporaryDirectory() as folder:
            directory = package(Path(folder))
            artifact, bundle = fixture(directory, error=True)
            for row in (artifact, bundle):
                row.update(version="0.1.1", error="source_too_large")
            saved(directory, artifact, bundle)
            self.assertEqual(read(directory, bundle, bundle["sourceSha256"])[:2], (None, None))

    def test_error_artifact_and_descriptor_cannot_keep_semantic_claims(self):
        for change in ("count", "ledger", "error", "model", "identity"):
            with self.subTest(change=change), tempfile.TemporaryDirectory() as folder:
                directory = package(Path(folder))
                artifact, bundle = fixture(directory, error=True)
                if change == "count":
                    bundle["compiled"] = 0
                elif change == "error":
                    artifact["error"] = "other_error"
                else:
                    artifact[{"ledger": "ledger", "model": "model", "identity": "identityVerified"}[change]] = {}
                saved(directory, artifact, bundle)
                with self.assertRaises(ValueError):
                    read(directory, bundle, bundle["sourceSha256"])

    def test_bounded_reader_refuses_oversized_artifacts_before_parsing(self):
        with tempfile.TemporaryDirectory() as folder:
            directory = package(Path(folder))
            _, bundle = fixture(directory)
            with self.assertRaisesRegex(ValueError, "size"):
                read(directory, bundle, bundle["sourceSha256"], max_bytes=13)

    def test_duplicate_and_nonfinite_json_members_are_rejected(self):
        for tail in (b',"private":1,"private":2}', b',"private":NaN}'):
            with self.subTest(tail=tail), tempfile.TemporaryDirectory() as folder:
                directory = package(Path(folder))
                _, bundle = fixture(directory)
                raw = (directory / bundle["file"]).read_bytes()[:-1] + tail
                (directory / bundle["file"]).write_bytes(raw)
                bundle["sha256"] = hashlib.sha256(raw).hexdigest()
                with self.assertRaises(ValueError):
                    read(directory, bundle, bundle["sourceSha256"])

    def test_size_limits_require_positive_integers_without_bool(self):
        for limit in (True, 0, -1, 1.5, float("nan"), float("inf"), None):
            with self.subTest(limit=limit), self.assertRaises(ValueError):
                read(Path("unread"), {}, "a" * 64, max_bytes=limit)
