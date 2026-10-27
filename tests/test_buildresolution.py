import copy
import json
import unittest

from damage_lab.buildresolution import project, summary


def document():
    """Return fictional saved-controller evidence without a raw code or player identifier."""
    return {
        "format": "tli-build-resolution-v0", "version": "0.1.1", "status": "matched_saved_code",
        "source": {"sha256": "a" * 64},
        "transport": {"kind": "saved_client_snapshot", "verified": False},
        "identity": {"basis": "saved_controller_code", "codeFingerprint": "sha256:0b73e19a",
                     "expectedCodeMatched": True, "descriptorMatch": "not_supplied", "payloadSelfIdentifies": False,
                     "captureVerifiedFlag": False, "authorConsistency": "consistent", "playerIdConsistency": "consistent",
                     "codeStructure": "uuid_v1", "codeMintedAt": "2026-02-03T04:05:06+00:00"},
        "gate": {"status": "allowed", "featureStatus": "Feature_CanView", "realFeatureStatus": "Feature_CanView"},
        "coverage": {"dataVersion": {"first": 7, "second": 113}, "affixVersions": {"checked": 11, "mismatched": 0},
                     "sections": {name: "captured" for name in
                                  ("PlayeBaseInfo", "WearItems", "SkillLayout", "GeniusInfos", "HeroCharacter")},
                     "requiredMissing": []},
        "freshness": {"status": "unknown", "capturedAt": "2026-02-04T07:08:09+03:00", "capturedAtStatus": "valid",
                      "codeMintedAt": "2026-02-03T04:05:06+00:00", "payloadGeneratedAt": None, "isOldData": "not_captured"},
        "warnings": [],
        "sourcePaths": ["buildIdentity.buildCode", "buildIdentity.buildCodeVerified", "capturedAt",
                        "sections.ServerSource.data.featureStatus", "sections.ServerSource.data.realFeatureStatus",
                        "sections.ServerSource.data.playerId", "sections.ServerSource.data.baseInfo",
                        "sections.ServerSource.data.version", "sections.ServerSource.data.**.Version (affix records)"]}


class BuildResolutionTest(unittest.TestCase):
    """A saved-controller match cannot verify payload identity, transport or freshness."""

    def test_a_saved_code_match_never_promotes_verification(self):
        result = project(document(), "a" * 64)
        self.assertEqual((result["status"], result["transport"]["verified"],
                          result["identity"]["payload_self_identifies"], result["freshness"]["status"]),
                         ("matched_saved_code", False, False, "unknown"))

    def test_source_binding_and_supported_version_are_mandatory(self):
        for key, value in (("format", "other"), ("version", "0.1.0"), ("status", "resolved_offline")):
            data = document()
            data[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                project(data, "a" * 64)
        for digest in ("b" * 64, "A" * 64, True, None):
            with self.subTest(digest=digest), self.assertRaises(ValueError):
                project(document(), digest)

    def test_transport_payload_and_freshness_cannot_be_verified(self):
        for section, key, value in (("transport", "verified", True), ("transport", "verified", 0),
                                    ("transport", "kind", "network"), ("identity", "payloadSelfIdentifies", True),
                                    ("identity", "payloadSelfIdentifies", 0), ("freshness", "status", "fresh"),
                                    ("freshness", "payloadGeneratedAt", "2026-02-04T00:00:00+00:00"),
                                    ("freshness", "isOldData", False)):
            data = document()
            data[section][key] = value
            with self.subTest(section=section, key=key), self.assertRaises(ValueError):
                project(data, "a" * 64)

    def test_identity_metadata_accepts_only_redacted_typed_evidence(self):
        for key, value in (("basis", "verified_identity"), ("codeFingerprint", "private-canary"),
                           ("expectedCodeMatched", 1), ("captureVerifiedFlag", 0), ("descriptorMatch", "verified"),
                           ("authorConsistency", "private-canary"), ("playerIdConsistency", {}),
                           ("codeStructure", "private-canary")):
            data = document()
            data["identity"][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                project(data, "a" * 64)

    def test_timestamps_reject_private_text_invalid_dates_and_false_freshness(self):
        for section, key, value in (("identity", "codeMintedAt", "private-canary"),
                                    ("freshness", "capturedAt", "2026-02-31T03:04:05+00:00"),
                                    ("freshness", "capturedAt", "2026-02-03"),
                                    ("freshness", "capturedAtStatus", "private-canary"),
                                    ("freshness", "codeMintedAt", "2026-02-02T03:04:05+00:00")):
            data = document()
            data[section][key] = value
            with self.subTest(section=section, key=key), self.assertRaises(ValueError):
                project(data, "a" * 64)

    def test_identity_claims_cannot_exist_without_their_saved_code_evidence(self):
        for key, value in (("basis", "none"), ("codeFingerprint", None), ("codeStructure", None),
                           ("codeStructure", "other")):
            data = document()
            data["identity"][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                project(data, "a" * 64)

    def test_gate_values_and_status_must_be_consistent_fixed_words(self):
        for key, value in (("status", "denied"), ("status", "private-canary"),
                           ("featureStatus", "private-canary"), ("realFeatureStatus", False)):
            data = document()
            data["gate"][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                project(data, "a" * 64)

    def test_coverage_requires_strict_counts_versions_and_missing_sections(self):
        for section, key, value in (("affixVersions", "checked", True), ("affixVersions", "mismatched", -1),
                                    ("affixVersions", "mismatched", 12), ("dataVersion", "first", False),
                                    ("dataVersion", "second", 113.0), ("sections", "WearItems", "private-canary"),
                                    ("top", "requiredMissing", ["HeroCharacter"])):
            data = document()
            row = data["coverage"] if section == "top" else data["coverage"][section]
            row[key] = value
            with self.subTest(section=section, key=key), self.assertRaises(ValueError):
                project(data, "a" * 64)

    def test_paths_and_warnings_cannot_carry_private_or_unknown_text(self):
        for field, value in (("sourcePaths", ["sections.Account.private-canary"]),
                             ("warnings", ["private-canary"]), ("warnings", [True]),
                             ("warnings", ["data_version_invalid", "data_version_invalid"])):
            data = document()
            data[field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                project(data, "a" * 64)

    def test_final_status_cannot_hide_mismatches_denials_or_missing_evidence(self):
        for issue in ("code", "descriptor", "gate", "author", "affix", "section", "unbound"):
            data = document()
            if issue == "code":
                data["identity"]["expectedCodeMatched"] = False
            elif issue == "descriptor":
                data["identity"]["descriptorMatch"] = "mismatch"
            elif issue == "gate":
                data["gate"].update(status="denied", featureStatus="other")
            elif issue == "author":
                data["identity"]["authorConsistency"] = "inconsistent"
            elif issue == "affix":
                data["coverage"]["affixVersions"]["mismatched"] = 1
            elif issue == "section":
                data["coverage"]["sections"]["HeroCharacter"] = "absent"
                data["coverage"]["requiredMissing"] = ["HeroCharacter"]
            else:
                data["status"] = "unbound"
            with self.subTest(issue=issue), self.assertRaises(ValueError):
                project(data, "a" * 64)

    def test_a_descriptor_candidate_match_cannot_upgrade_an_unbound_controller(self):
        data = document()
        data["identity"].update(expectedCodeMatched=None, descriptorMatch="candidate_match", captureVerifiedFlag=True)
        with self.assertRaises(ValueError):
            project(data, "a" * 64)

    def test_invalid_payload_cannot_retain_successful_identity_evidence(self):
        data = document()
        data["status"] = "invalid_payload"
        with self.assertRaises(ValueError):
            project(data, "a" * 64)

    def test_timestamp_and_version_warnings_must_match_their_observations(self):
        for issue in ("future", "false_future", "version", "other"):
            data = document()
            if issue == "future":
                data["freshness"]["capturedAt"] = "2026-02-03T06:00:00+03:00"
            elif issue == "false_future":
                data["warnings"] = ["code_minted_after_capture"]
            elif issue == "version":
                data["coverage"]["dataVersion"]["first"] = None
            else:
                data["identity"].update(codeStructure="other", codeMintedAt=None)
                data["freshness"]["codeMintedAt"] = None
            with self.subTest(issue=issue), self.assertRaises(ValueError):
                project(data, "a" * 64)

    def test_unknown_properties_are_removed_at_every_depth(self):
        data = document()
        for row in (data, data["source"], data["transport"], data["identity"], data["gate"], data["freshness"],
                    data["coverage"], data["coverage"]["dataVersion"], data["coverage"]["affixVersions"], data["coverage"]["sections"]):
            row["rawAccount"] = {"private": "SYNTHETIC-PRIVATE-CANARY"}
        self.assertNotIn("SYNTHETIC-PRIVATE-CANARY", json.dumps(project(data, "a" * 64)))

    def test_summary_revalidates_and_detaches_the_safe_projection(self):
        data = project(document(), "a" * 64)
        for row in (data, data["identity"], data["coverage"]["data_version"]):
            row["rawAccount"] = {"private": "SYNTHETIC-PRIVATE-CANARY"}
        self.assertEqual(summary(data), project(document(), "a" * 64))

    def test_summary_rejects_new_proof_or_malformed_coverage_claims(self):
        for section, key, value in (("transport", "verified", True), ("identity", "payload_self_identifies", True),
                                    ("freshness", "status", "fresh"), ("identity", "expected_code_matched", 1),
                                    ("coverage", "affix_versions", {"checked": False, "mismatched": 0})):
            data = project(document(), "a" * 64)
            data[section][key] = value
            with self.subTest(section=section, key=key), self.assertRaises(ValueError):
                summary(data)

    def test_project_and_summary_never_mutate_or_share_nested_inputs(self):
        data = document()
        before = copy.deepcopy(data)
        result = project(data, "a" * 64)
        copied = summary(result)
        copied["source_paths"].append("synthetic")
        copied["coverage"]["sections"].clear()
        copied["warnings"].append("synthetic")
        copied["coverage"]["affix_versions"]["checked"] = 37
        self.assertEqual((data, result), (before, project(before, "a" * 64)))

    def test_required_nested_shapes_fail_with_value_errors(self):
        for section, key, value in (("top", "identity", []), ("top", "warnings", "private-canary"),
                                    ("top", "sourcePaths", None), ("top", "source", False),
                                    ("coverage", "sections", []), ("coverage", "requiredMissing", {}),
                                    ("coverage", "dataVersion", None), ("top", "gate", None)):
            data = document()
            (data if section == "top" else data[section])[key] = value
            with self.subTest(section=section, key=key), self.assertRaises(ValueError):
                project(data, "a" * 64)

    def test_an_unbound_capture_flag_and_matching_descriptor_stay_unbound(self):
        data = document()
        data["status"] = "unbound"
        data["identity"].update(expectedCodeMatched=None, descriptorMatch="candidate_match", captureVerifiedFlag=True)
        self.assertEqual(project(data, "a" * 64)["status"], "unbound")

    def test_a_warning_about_time_or_data_version_never_rejects_a_saved_match(self):
        data = document()
        data["freshness"]["capturedAt"] = "2026-02-03T06:00:00+03:00"
        data["coverage"]["dataVersion"]["first"] = None
        data["warnings"] = ["code_minted_after_capture", "data_version_invalid"]
        self.assertEqual(summary(project(data, "a" * 64))["status"], "matched_saved_code")

    def test_unobserved_data_versions_are_not_rejected_by_an_invented_version_list(self):
        data = document()
        data["coverage"]["dataVersion"].update(first=-7, second=201)
        self.assertEqual(project(data, "a" * 64)["coverage"]["data_version"], {"first": -7, "second": 201})

    def test_explicit_failure_states_follow_the_documented_precedence(self):
        results = []
        for status in ("code_mismatch", "not_viewable", "inconsistent", "incomplete", "invalid_code", "planner_code"):
            data = document()
            data["status"] = status
            if status == "code_mismatch":
                data["identity"]["expectedCodeMatched"] = False
            elif status == "not_viewable":
                data["gate"].update(status="denied", featureStatus="other")
            elif status == "inconsistent":
                data["coverage"]["affixVersions"]["mismatched"] = 1
            elif status == "incomplete":
                data["coverage"]["sections"]["WearItems"] = "invalid"
                data["coverage"]["requiredMissing"] = ["WearItems"]
            else:
                data["identity"]["expectedCodeMatched"] = None
            results.append(summary(project(data, "a" * 64))["status"])
        self.assertEqual(results, ["code_mismatch", "not_viewable", "inconsistent", "incomplete", "invalid_code", "planner_code"])


if __name__ == "__main__":
    unittest.main()
