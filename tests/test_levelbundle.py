"""Synthetic packages bind level diagnostics to exact bytes and installation."""

import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from damage_lab.levelbundle import read, summary


def persisted(directory, artifact, descriptor):
    raw = json.dumps(artifact, ensure_ascii=False, allow_nan=False).encode("utf-8")
    (directory / "installed-level-candidates.json").write_bytes(raw)
    descriptor["sha256"] = hashlib.sha256(raw).hexdigest()


def failure(directory, code="catalog_mapping_missing", *, unbound=False):
    """Bind a fictional acquisition failure to temporary source bytes."""
    path = directory / "source.json"
    if not path.exists():
        path.write_bytes(b"{}")
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    flags = {key: False for key in ("arithmeticReady", "runtimeVerified", "identityVerified", "importComplete")}
    artifact = {"format": "tli-installed-level-candidates-error-v1", "version": "0.1.2", "status": "error",
                "resolverFormat": "tli-effective-level-candidates-v0", "resolverVersion": "0.3.1",
                "error": code, "source": {"file": "source.json", "sha256": None if unbound else digest}, **flags}
    descriptor = {"file": "installed-level-candidates.json", "version": "0.1.2", "resolverVersion": "0.3.1",
                  "status": "error", "error": code, "sourceSha256": artifact["source"]["sha256"], **flags,
                  **{key: None for key in ("catalogDocuments", "auxiliaryFiles", "requested", "targets",
                                           "candidates", "gaps", "ambiguousTargets")}}
    persisted(directory, artifact, descriptor)
    return artifact, descriptor, digest


def diagnostic(directory):
    """One fictional observed gem and six diagnostic level-grant candidates."""
    from damage_lab.installedskills import project
    from test_installedskills import absent
    from test_levelcandidates import document

    artifact, descriptor, source = failure(directory)
    raw = absent("server", "absent")
    raw["source"]["sha256"] = source
    raw["domains"]["client"].update(tabs=1, nullTabs=0, rows=1, nullRows=0)
    raw["groups"] = raw["groups"][:1]
    raw["groups"][0]["members"] = raw["groups"][0]["members"][:1]
    raw["groups"][0]["members"][0].update(skillId=91437, gemLevel=17)
    raw["relationships"], raw["issues"] = [], []
    installation = project(raw, source)
    target = document()
    target["source"]["sha256"] = source
    target["target"]["path"] = "sections.SkillLayout.data[0][0]"
    target["domains"]["supports"]["observed"] = 1
    artifact.pop("error")
    descriptor.pop("error")
    artifact.update(format="tli-installed-level-candidates-v1", status="diagnostic",
        catalog={"status": "members_read", "derivation": "cache_member_exact_slice",
                 "networkBytesVerified": False, "currentPatchVerified": False,
                 "mappingFiles": [{"file": "needed-bundles.json", "sha256": "b" * 64, "bytes": 163}],
                 "documents": [{"role": "master", "domain": "gear", "logicalPath": "gear/wand/master",
                     "address": "/data/SS14/gear/wand/master.json", "cacheFile": "1234567890abcdef.json",
                     "wrapperSha256": "c" * 64, "byteRange": [47, 139], "memberSha256": "d" * 64,
                     "encoding": "utf-8"}]},
        auxiliary={key: {"status": "absent", "sha256": None, "bytes": None}
                   for key in ("endgameIdBridge", "verifiedNativeMappings")},
        selection={"policy": "distinct_observed_config_base_ids", "clientLayer": "captured",
                   "observedMembers": 1, "invalidSkillIds": 0}, requestedIds=[91437], targets={"91437": target})
    descriptor.update(status="diagnostic", catalogDocuments=1, auxiliaryFiles=0, requested=1,
                      targets=1, candidates=6, gaps=1, ambiguousTargets=0)
    artifact["catalog"]["documents"] = [{"role": "master", "domain": path.split("/")[0],
        "logicalPath": path, "address": f"/data/SS14/{path}.json", "cacheFile": "1234567890abcdef.json",
        "wrapperSha256": "c" * 64, "byteRange": [47 + index * 100, 139 + index * 100],
        "memberSha256": "d" * 64, "encoding": "utf-8"} for index, path in enumerate((
            "gear/one_handed/wand/master", "talent-tree/synthetic_tree/master", "divinity-slate/master",
            "pactspirit/master", "skill/Active/master"))]
    descriptor["catalogDocuments"] = 5
    artifact["auxiliary"]["endgameIdBridge"].update(status="supplied", sha256="e" * 64, bytes=137)
    descriptor["auxiliaryFiles"] = 1
    persisted(directory, artifact, descriptor)
    return artifact, descriptor, source, installation


def native(directory):
    """Persist the new pinned pair with a fictional native-level row."""
    from test_levelcandidates import native as observation

    artifact, descriptor, source, installation = diagnostic(directory)
    artifact.update(version="0.2.0", resolverVersion="0.4.0")
    descriptor.update(version="0.2.0", resolverVersion="0.4.0")
    ledger = artifact["targets"]["91437"]
    ledger["version"] = "0.4.0"
    ledger["target"]["nativeLevelFields"] = observation()["target"]["nativeLevelFields"]
    persisted(directory, artifact, descriptor)
    return artifact, descriptor, source, installation


class LevelBundleTests(unittest.TestCase):
    """Exact bytes and observed installations constrain diagnostic level evidence."""

    def test_a_source_bound_producer_error_remains_missing_evidence(self):
        with tempfile.TemporaryDirectory() as folder:
            directory = Path(folder)
            _, descriptor, source = failure(directory)
            result, origin = read(directory, descriptor, source, None)
            self.assertEqual((result, origin[-1]), (None, 0))

    def test_an_exporter_without_catalog_bytes_retains_a_hashed_acquisition_gap(self):
        with tempfile.TemporaryDirectory() as folder:
            directory = Path(folder)
            _, descriptor, source = failure(directory, "catalog_bytes_unavailable")
            result, origin = read(directory, descriptor, source, None)
            self.assertEqual((result, origin[1], origin[-1]), (None, descriptor["sha256"], 0))

    def test_diagnostic_evidence_preserves_candidates_and_unknown_effective_level(self):
        with tempfile.TemporaryDirectory() as folder:
            directory = Path(folder)
            _, descriptor, source, installation = diagnostic(directory)
            result, origin = read(directory, descriptor, source, installation)
            self.assertEqual((result["version"], result["targets"]["91437"]["effective_level"],
                              result["targets"]["91437"]["candidates"][0]["amount"]["exact"],
                              result["accounting"]["candidates"], origin[-1]), ("0.1.2", None, "2.70", 6, 1))

    def test_the_new_pinned_pair_preserves_native_observations_through_revalidation(self):
        with tempfile.TemporaryDirectory() as folder:
            directory = Path(folder)
            _, descriptor, source, installation = native(directory)
            result, _ = read(directory, descriptor, source, installation)
            self.assertEqual(summary(result, installation)["targets"]["91437"]["target"]["native_level_fields"]["fields"],
                             {"Level": {"value": 17, "type": "int"}, "SkillItemLevel": {"value": 63, "type": "int"}})

    def test_a_new_bundle_cannot_contain_a_legacy_resolver_target(self):
        with tempfile.TemporaryDirectory() as folder:
            directory = Path(folder)
            artifact, descriptor, source, installation = native(directory)
            artifact["targets"]["91437"]["version"] = "0.3.1"
            artifact["targets"]["91437"]["target"].pop("nativeLevelFields")
            persisted(directory, artifact, descriptor)
            with self.assertRaises(ValueError):
                read(directory, descriptor, source, installation)

    def test_legacy_bundles_cannot_smuggle_new_resolver_targets(self):
        with tempfile.TemporaryDirectory() as folder:
            directory = Path(folder)
            artifact, descriptor, source, installation = native(directory)
            artifact.update(version="0.1.2", resolverVersion="0.3.1")
            descriptor.update(version="0.1.2", resolverVersion="0.3.1")
            persisted(directory, artifact, descriptor)
            with self.assertRaises(ValueError):
                read(directory, descriptor, source, installation)

    def test_mixed_bundle_and_resolver_versions_are_unreviewed(self):
        for bundle, resolver in (("0.1.2", "0.4.0"), ("0.2.0", "0.3.1")):
            with self.subTest(bundle=bundle, resolver=resolver), tempfile.TemporaryDirectory() as folder:
                directory = Path(folder)
                artifact, descriptor, source, installation = native(directory)
                artifact.update(version=bundle, resolverVersion=resolver)
                descriptor.update(version=bundle, resolverVersion=resolver)
                persisted(directory, artifact, descriptor)
                with self.assertRaises(ValueError):
                    read(directory, descriptor, source, installation)

    def test_artifact_and_descriptor_must_agree_on_the_reviewed_pair(self):
        with tempfile.TemporaryDirectory() as folder:
            directory = Path(folder)
            artifact, descriptor, source, installation = native(directory)
            artifact.update(version="0.1.2", resolverVersion="0.3.1")
            persisted(directory, artifact, descriptor)
            with self.assertRaises(ValueError):
                read(directory, descriptor, source, installation)

    def test_canonical_version_containers_fail_with_a_controlled_contract_error(self):
        for field in ("version", "resolver_version"):
            with self.subTest(field=field), tempfile.TemporaryDirectory() as folder:
                directory = Path(folder)
                _, descriptor, source, installation = native(directory)
                result, _ = read(directory, descriptor, source, installation)
                result[field] = ["0.4.0"]
                with self.assertRaises(ValueError):
                    summary(result, installation)

    def test_summary_is_detached_and_strips_unknown_properties_at_every_known_boundary(self):
        with tempfile.TemporaryDirectory() as folder:
            directory = Path(folder)
            _, descriptor, source, installation = diagnostic(directory)
            result, _ = read(directory, descriptor, source, installation)
            expected = copy.deepcopy(result)
            for row in (result, result["source"], result["catalog"], result["catalog"]["documents"][0],
                        result["auxiliary"], result["selection"], result["accounting"],
                        result["targets"]["91437"]["candidates"][0]):
                row["unreviewed"] = "discard-me"
            self.assertEqual(summary(result, installation), expected)

    def test_only_unread_source_errors_can_lack_a_source_hash(self):
        for code, valid in (("source_missing", True), ("source_unreadable", True), ("resolver_version_unreviewed", False)):
            with self.subTest(code=code), tempfile.TemporaryDirectory() as folder:
                directory = Path(folder)
                _, descriptor, source = failure(directory, code, unbound=True)
                if valid:
                    self.assertIsNone(read(directory, descriptor, source, None)[0])
                else:
                    with self.assertRaises(ValueError):
                        read(directory, descriptor, source, None)

    def test_unknown_versions_flags_and_descriptor_counts_cannot_be_promoted(self):
        for key, value in (("version", "0.1.1"), ("resolverVersion", "0.3.0"), ("file", "../elsewhere.json"),
                           ("runtimeVerified", True), ("arithmeticReady", 0), ("catalogDocuments", True),
                           ("sourceSha256", "f" * 64), ("candidates", 7)):
            with self.subTest(key=key), tempfile.TemporaryDirectory() as folder:
                directory = Path(folder)
                _, descriptor, source, installation = diagnostic(directory)
                descriptor[key] = value
                with self.assertRaises(ValueError):
                    read(directory, descriptor, source, installation)

    def test_artifact_tampering_and_byte_limits_are_rejected_before_evidence_is_returned(self):
        for limit, tamper in ((1, False), (False, False), (64 * 1024 * 1024 + 1, False), (64 * 1024 * 1024, True)):
            with self.subTest(limit=limit, tamper=tamper), tempfile.TemporaryDirectory() as folder:
                directory = Path(folder)
                _, descriptor, source, installation = diagnostic(directory)
                if tamper:
                    with (directory / descriptor["file"]).open("ab") as stream:
                        stream.write(b" ")
                with self.assertRaises(ValueError):
                    read(directory, descriptor, source, installation, max_bytes=limit)

    def test_strict_json_rejects_duplicate_nonfinite_underflow_and_invalid_unicode(self):
        for payload in (b'{"version":1,"version":2}', b'{"x":NaN}', b'{"x":1e-999}', b'\xff',
                        b'{"private":"\\ud800"}'):
            with self.subTest(payload=payload), tempfile.TemporaryDirectory() as folder:
                directory = Path(folder)
                _, descriptor, source = failure(directory)
                (directory / descriptor["file"]).write_bytes(payload)
                descriptor["sha256"] = hashlib.sha256(payload).hexdigest()
                with self.assertRaises(ValueError):
                    read(directory, descriptor, source, None)

    def test_errors_cannot_retain_semantic_records_or_nonnull_counts(self):
        for key in ("catalog", "auxiliary", "selection", "requestedIds", "targets"):
            with self.subTest(key=key), tempfile.TemporaryDirectory() as folder:
                directory = Path(folder)
                artifact, descriptor, source = failure(directory)
                artifact[key] = None
                persisted(directory, artifact, descriptor)
                with self.assertRaises(ValueError):
                    read(directory, descriptor, source, None)

    def test_target_membership_paths_and_levels_must_agree_with_the_installation(self):
        for field, value in (("path", "sections.SkillLayout.data[0][1]"), ("skillId", 91439), ("level", 19),
                             ("source", "b" * 64), ("requested", [91437, 91439]), ("targets", {})):
            with self.subTest(field=field), tempfile.TemporaryDirectory() as folder:
                directory = Path(folder)
                artifact, descriptor, source, installation = diagnostic(directory)
                target = artifact["targets"]["91437"]
                if field == "level":
                    target["target"]["gemLevel"]["value"] = value
                elif field == "source":
                    target["source"]["sha256"] = value
                elif field in ("path", "skillId"):
                    target["target"][field] = value
                else:
                    artifact["requestedIds" if field == "requested" else "targets"] = value
                persisted(directory, artifact, descriptor)
                with self.assertRaises(ValueError):
                    read(directory, descriptor, source, installation)

    def test_declared_catalog_coordinates_remain_allowlisted_consistent_and_bounded(self):
        for field, value in (("domain", "skill"), ("role", "english"), ("encoding", "latin1"),
                             ("logicalPath", "gear/wand/i18n/en"), ("address", "https://unrelated.invalid"),
                             ("cacheFile", "../private.json"), ("byteRange", [139, 47]),
                             ("byteRange", [0, 32 * 1024 * 1024 + 1]), ("memberSha256", "D" * 64)):
            with self.subTest(field=field), tempfile.TemporaryDirectory() as folder:
                directory = Path(folder)
                artifact, descriptor, source, installation = diagnostic(directory)
                artifact["catalog"]["documents"][0][field] = value
                persisted(directory, artifact, descriptor)
                with self.assertRaises(ValueError):
                    read(directory, descriptor, source, installation)

    def test_summary_rejects_forged_counts_and_finite_effective_levels(self):
        with tempfile.TemporaryDirectory() as folder:
            directory = Path(folder)
            _, descriptor, source, installation = diagnostic(directory)
            result, _ = read(directory, descriptor, source, installation)
            for path, value in ((("accounting", "candidates"), 7), (("selection", "observed_members"), True),
                                (("targets", "91437", "effective_level"), 29),
                                (("auxiliary", "endgame_id_bridge", "bytes"), 0)):
                changed = copy.deepcopy(result)
                target = changed
                for key in path[:-1]:
                    target = target[key]
                target[path[-1]] = value
                with self.subTest(path=path), self.assertRaises(ValueError):
                    summary(changed, installation)

    def test_unknown_installation_is_distinct_from_a_captured_empty_installation(self):
        for status in ("absent", "captured"):
            with self.subTest(status=status), tempfile.TemporaryDirectory() as folder:
                directory = Path(folder)
                artifact, descriptor, source, installation = diagnostic(directory)
                installation["groups"] = []
                installation["domains"]["client"] = {"status": status, **{key: 0 if status == "captured" else None
                    for key in ("tabs", "null_tabs", "rows", "null_rows")}}
                artifact["selection"].update(clientLayer=status,
                    observedMembers=0 if status == "captured" else None, invalidSkillIds=0 if status == "captured" else None)
                artifact["requestedIds"] = [] if status == "captured" else None
                artifact["targets"] = {} if status == "captured" else None
                descriptor.update({key: 0 if status == "captured" else None for key in
                                   ("requested", "targets", "candidates", "gaps", "ambiguousTargets")})
                persisted(directory, artifact, descriptor)
                result, _ = read(directory, descriptor, source, installation)
                self.assertEqual((result["requested_ids"], result["targets"], result["accounting"]["targets"]),
                                 ([], {}, 0) if status == "captured" else (None, None, None))

    def test_duplicate_installations_cannot_select_the_first_observed_instance(self):
        with tempfile.TemporaryDirectory() as folder:
            directory = Path(folder)
            artifact, descriptor, source, installation = diagnostic(directory)
            group = copy.deepcopy(installation["groups"][0])
            group.update(alias="group[2]", tab_position=1, tab_idx=2)
            group["members"][0].update(alias="gem[2]", path="sections.SkillLayout.data[1][0]", gem_level=23)
            installation["groups"].append(group)
            installation["domains"]["client"].update(tabs=2, rows=2)
            artifact["selection"]["observedMembers"] = 2
            artifact["targets"]["91437"]["domains"]["supports"]["observed"] = 2
            persisted(directory, artifact, descriptor)
            with self.assertRaises(ValueError):
                read(directory, descriptor, source, installation)

    def test_duplicate_installations_keep_a_null_level_and_an_ambiguous_target(self):
        with tempfile.TemporaryDirectory() as folder:
            directory = Path(folder)
            artifact, descriptor, source, installation = diagnostic(directory)
            group = copy.deepcopy(installation["groups"][0])
            group.update(alias="group[2]", tab_position=1, tab_idx=2)
            group["members"][0].update(alias="gem[2]", path="sections.SkillLayout.data[1][0]", gem_level=23)
            installation["groups"].append(group)
            installation["domains"]["client"].update(tabs=2, rows=2)
            artifact["selection"]["observedMembers"] = 2
            artifact["targets"]["91437"]["domains"]["supports"]["observed"] = 2
            artifact["targets"]["91437"]["target"].update(status="ambiguous_installation", path=None, gemLevel=None)
            descriptor["ambiguousTargets"] = 1
            persisted(directory, artifact, descriptor)
            result, _ = read(directory, descriptor, source, installation)
            self.assertEqual((result["targets"]["91437"]["target"]["gem_level"],
                              result["accounting"]["requested"], result["accounting"]["ambiguous_targets"]), (None, 1, 1))

    def test_a_supplied_auxiliary_has_hashed_positive_bytes_without_becoming_verified(self):
        with tempfile.TemporaryDirectory() as folder:
            directory = Path(folder)
            artifact, descriptor, source, installation = diagnostic(directory)
            artifact["auxiliary"]["endgameIdBridge"].update(status="supplied", sha256="e" * 64, bytes=137)
            descriptor["auxiliaryFiles"] = 1
            persisted(directory, artifact, descriptor)
            result, _ = read(directory, descriptor, source, installation)
            self.assertEqual((result["auxiliary"]["endgame_id_bridge"]["sha256"],
                              result["accounting"]["auxiliary_files"], result["identity_verified"]), ("e" * 64, 1, False))

    def test_shared_wrappers_cannot_claim_overlapping_member_ranges_or_different_hashes(self):
        for field, value in (("wrapperSha256", "f" * 64), ("byteRange", [130, 201])):
            with self.subTest(field=field), tempfile.TemporaryDirectory() as folder:
                directory = Path(folder)
                artifact, descriptor, source, installation = diagnostic(directory)
                row = copy.deepcopy(artifact["catalog"]["documents"][0])
                row.update(logicalPath="gear/staff/master", address="/data/SS14/gear/staff/master.json", byteRange=[141, 201])
                row[field] = value
                artifact["catalog"]["documents"].append(row)
                descriptor["catalogDocuments"] = 6
                persisted(directory, artifact, descriptor)
                with self.assertRaises(ValueError):
                    read(directory, descriptor, source, installation)

    def test_catalog_bindings_require_declared_member_provenance(self):
        with tempfile.TemporaryDirectory() as folder:
            directory = Path(folder)
            artifact, descriptor, source, installation = diagnostic(directory)
            artifact["catalog"].update(status="no_allowlisted_members_mapped", documents=[])
            descriptor["catalogDocuments"] = 0
            persisted(directory, artifact, descriptor)
            with self.assertRaises(ValueError):
                read(directory, descriptor, source, installation)

    def test_a_bridged_candidate_requires_supplied_auxiliary_provenance(self):
        with tempfile.TemporaryDirectory() as folder:
            directory = Path(folder)
            artifact, descriptor, source, installation = diagnostic(directory)
            artifact["auxiliary"] = {key: {"status": "absent", "sha256": None, "bytes": None}
                                     for key in ("endgameIdBridge", "verifiedNativeMappings")}
            descriptor["auxiliaryFiles"] = 0
            persisted(directory, artifact, descriptor)
            with self.assertRaises(ValueError):
                read(directory, descriptor, source, installation)

    def test_domain_catalog_census_must_match_the_declared_member_set(self):
        with tempfile.TemporaryDirectory() as folder:
            directory = Path(folder)
            artifact, descriptor, source, installation = diagnostic(directory)
            artifact["targets"]["91437"]["domains"]["supports"]["catalogMembers"] = 37
            persisted(directory, artifact, descriptor)
            with self.assertRaises(ValueError):
                read(directory, descriptor, source, installation)

    def test_the_support_census_cannot_claim_a_different_number_of_installed_gems(self):
        with tempfile.TemporaryDirectory() as folder:
            directory = Path(folder)
            artifact, descriptor, source, installation = diagnostic(directory)
            artifact["targets"]["91437"]["domains"]["supports"]["observed"] = 71
            persisted(directory, artifact, descriptor)
            with self.assertRaises(ValueError):
                read(directory, descriptor, source, installation)
