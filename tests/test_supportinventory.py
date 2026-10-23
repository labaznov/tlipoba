import copy
import json
import unittest
from decimal import Inexact, Rounded, localcontext

from damage_lab.supportinventory import FORMAT, project
from damage_lab.supporteffects import effects
from test_supporteffects import catalog, row


SHA = "a" * 64
LIMITATIONS = [
    "source sha256 binds the caller-supplied document only; no source bytes are read or verified",
    "catalog records are taken as supplied; no catalog bytes or hashes are verified",
    "installation is observed membership only; activation, effective level and panel skill are unknown",
]


def document():
    legacy = effects(catalog(), native_base_id=90017, prefix_rows=[None, row("X91", ["24.125"])])
    legacy["version"] = "0.2.0"
    legacy.pop("mediumTrigger", None)
    return {
        "format": "tli-installed-support-effects-v0", "version": "0.2.0", "inventoryVersion": "0.1.2",
        "effectsVersion": "0.2.0", "source": {"sha256": SHA, "binding": "caller_supplied_document_only"},
        "arithmeticReady": False, "runtimeVerified": False, "identityVerified": False, "importComplete": False,
        "activation": "unknown", "patch": "unknown", "effectiveLevel": None,
        "clientLayer": "captured", "serverLayer": "absent", "limitations": list(LIMITATIONS),
        "members": [
            {"alias": "gem[1]", "group": "group[1]", "tabPosition": 0, "groupStatus": "ok",
             "slot": 1, "path": "sections.SkillLayout.data[0][0]", "baseId": 90001,
             "gemLevel": {"value": 19, "meaning": "observed_gem_level_not_effective"},
             "category": "active_skill", "status": "excluded_category", "reason": None, "effects": None},
            {"alias": "gem[2]", "group": "group[1]", "tabPosition": 0, "groupStatus": "ok",
             "slot": 5, "path": "sections.SkillLayout.data[0][1]", "baseId": 90017,
             "gemLevel": {"value": 7, "meaning": "observed_gem_level_not_effective"},
             "category": "noble_support", "status": "effect_candidates", "reason": None,
             "effects": legacy},
            {"alias": "gem[3]", "group": "group[1]", "tabPosition": 0, "groupStatus": "ok",
             "slot": 6, "path": "sections.SkillLayout.data[0][2]", "baseId": 90033,
             "gemLevel": {"value": 2, "meaning": "observed_gem_level_not_effective"},
             "category": None, "status": "gap", "reason": "catalog_record_missing", "effects": None}],
        "accounting": {"members": 3, "effectCandidates": 1, "excluded": 1, "gaps": 1, "reconciles": True},
    }


def medium_document():
    """A fictional installed medium with a declared creation line and exact native slot values."""
    raw = document()
    raw["effectsVersion"] = "0.3.0"
    member = raw["members"][1]
    member.update(baseId=8030, category="activation_medium")
    effect = member["effects"]
    effect.update(version="0.3.0", prefix={"status": "supplied", "rows": 1, "nullRows": 0},
                  rolledLines=[], omissions=[], constants=[], constantIssues=[])
    effect["identity"].update(catalogTlidbId=8030, nativeBaseId=8030, category="Activation_Medium")
    effect["mediumTrigger"] = {
        "status": "bound", "reason": None, "paths": ["prefix[0]"],
        "pin": {"tlidbId": 8030, "category": "Activation_Medium", "lineId": "77103277",
                "templateSource": "english.lineTemplates"},
        "line": {
            "origin": "native_prefix_row", "path": "prefix[0]", "lineId": "77103277",
            "nativeId": "771032771", "tier": 1, "tierSource": "exact_native_modifier_id",
            "tierMeaning": "catalog_line_tier",
            "role": "medium_tangle_creation_trigger",
            "template": "When the number of Tangles within # m is below the upper limit, triggers the supported "
                        "skill, creating it in the form of a Tangle. Interval: # s\nCreates 1 additional Tangle",
            "templateSource": "english.lineTemplates",
            "slots": [
                {"slot": 1, "quantity": "tangle_count_radius", "unit": "metre", "exact": "10",
                 "range": {"min": "10", "max": "10"}},
                {"slot": 2, "quantity": "creation_trigger_interval", "unit": "second", "exact": "0.4",
                 "range": {"min": "0.4", "max": "0.4"}},
            ],
            "nativeVersion": {"value": 7, "meaning": "unverified"}, "status": "native_roll_exact",
            "semantics": "catalog_creation_interval", "runtime": "unverified", "rateDerived": False,
        },
    }
    return raw


class SupportInventoryTests(unittest.TestCase):
    """Preserve safe installed effect candidates without promoting their runtime or arithmetic status."""

    def test_legacy_absence_is_explicit_and_survives_canonical_revalidation(self):
        from damage_lab.supportinventory import summary

        self.assertEqual(summary(project(document(), SHA))["members"][1]["effects"]["medium_trigger"],
                         {"status": "legacy_absent"})

    def test_legacy_canonical_markers_refuse_foreign_keys_and_values_before_callbacks(self):
        from damage_lab.supportinventory import summary

        class Foreign(str):
            """A foreign string which must not be admitted as a schema field."""

        class Hostile:
            """A foreign value which raises if compared before type admission."""

            def __eq__(self, other):
                raise RuntimeError("PRIVATE-LEGACY-CANARY")

        for marker in ({Foreign("status"): "legacy_absent"}, {"status": Foreign("legacy_absent")},
                       {"status": Hostile()}, {"status": "legacy_absent", "extra": True}):
            with self.subTest(marker=type(marker["status"]).__name__):
                raw = project(document(), SHA)
                raw["members"][1]["effects"]["medium_trigger"] = marker
                with self.assertRaises(ValueError):
                    summary(raw)

    def test_leaf_versions_must_match_the_declared_adapter_version(self):
        for raw, version in ((document(), "0.3.0"), (medium_document(), "0.2.0")):
            with self.subTest(version=version):
                raw["members"][1]["effects"]["version"] = version
                with self.assertRaises(ValueError):
                    project(raw, SHA)

    def test_a_legacy_producer_cannot_smuggle_new_medium_semantics(self):
        raw = document()
        raw["members"][1]["effects"]["mediumTrigger"] = {"status": "not_applicable"}
        with self.assertRaises(ValueError):
            project(raw, SHA)

    def test_a_current_adapter_requires_the_explicit_medium_subtree(self):
        raw = medium_document()
        del raw["members"][1]["effects"]["mediumTrigger"]
        with self.assertRaises(ValueError):
            project(raw, SHA)

    def test_medium_rows_and_null_padding_reconcile_without_percent_rolls(self):
        raw = medium_document()
        effect = raw["members"][1]["effects"]
        effect["prefix"].update(rows=3, nullRows=2)
        effect["mediumTrigger"]["paths"] = ["prefix[1]"]
        effect["mediumTrigger"]["line"]["path"] = "prefix[1]"
        self.assertEqual(project(raw, SHA)["members"][1]["effects"]["prefix"],
                         {"status": "supplied", "rows": 3, "null_rows": 2})

    def test_medium_and_percent_rows_cannot_reuse_a_source_path_or_identity(self):
        for field in ("path", "lineId", "nativeId"):
            with self.subTest(field=field):
                raw = medium_document()
                effect = raw["members"][1]["effects"]
                effect["prefix"]["rows"] = 2
                roll = document()["members"][1]["effects"]["rolledLines"][0]
                roll["path"] = "prefix[1]"
                roll[field] = effect["mediumTrigger"]["line"][field]
                effect["rolledLines"] = [roll]
                with self.assertRaises(ValueError):
                    project(raw, SHA)

    def test_a_held_medium_and_unknown_peer_keep_both_omissions(self):
        raw = medium_document()
        effect = raw["members"][1]["effects"]
        effect["prefix"]["rows"] = 2
        effect["omissions"] = [
            {"origin": "native_prefix_row", "path": "prefix[0]", "reason": "unresolved_prefix_peer"},
            {"origin": "native_prefix_row", "path": "prefix[1]", "reason": "no_exact_definition"}]
        effect["mediumTrigger"].update(status="gap", reason="line_unresolved_rows_present",
                                       paths=["prefix[0]", "prefix[1]"], line=None)
        self.assertEqual(project(raw, SHA)["members"][1]["effects"]["medium_trigger"]["status"], "gap")

    def test_medium_creation_slots_keep_metres_and_seconds_without_damage_fractions(self):
        effect = project(medium_document(), SHA)["members"][1]["effects"]
        line = effect["medium_trigger"]["line"]
        self.assertEqual((effect["version"], effect["arithmetic_ready"], line["semantics"],
                          line["runtime"], line["rate_derived"], line["slots"]), (
            "0.3.0", False, "catalog_creation_interval", "unverified", False, [
                {"slot": 1, "quantity": "tangle_count_radius", "unit": "metre", "exact": "10",
                 "range": {"min": "10", "max": "10"}},
                {"slot": 2, "quantity": "creation_trigger_interval", "unit": "second", "exact": "0.4",
                 "range": {"min": "0.4", "max": "0.4"}},
            ]))

    def test_absent_client_keeps_members_and_all_counts_unknown(self):
        raw = document()
        raw.update(clientLayer="absent", members=None)
        raw["accounting"] = {key: None for key in raw["accounting"]}
        result = project(raw, SHA)
        self.assertEqual((result["format"], result["client_layer"], result["members"], result["accounting"]),
                         (FORMAT, "absent", None, {"members": None, "effect_candidates": None,
                                                "excluded": None, "gaps": None, "reconciles": None}))

    def test_top_contract_hashes_flags_and_unknown_layers_cannot_be_forged(self):
        paths = [(("format",), "other"), (("version",), "0.1.0"), (("inventoryVersion",), "0.2.0"),
                 (("effectsVersion",), "0.1.0"), (("source", "sha256"), "b" * 64),
                 (("source", "binding"), "verified_bytes"), (("arithmeticReady",), True),
                 (("runtimeVerified",), 0), (("identityVerified",), True), (("importComplete",), True),
                 (("activation",), "active"), (("patch",), "SS14"), (("effectiveLevel",), 7),
                 (("clientLayer",), "unknown"), (("serverLayer",), "unknown"),
                 (("limitations",), ["PRIVATE-INVENTORY-CANARY"])]
        for path, value in paths:
            with self.subTest(path=path):
                raw = document()
                node = raw
                for name in path[:-1]:
                    node = node[name]
                node[path[-1]] = value
                with self.assertRaises(ValueError):
                    project(raw, SHA)
        for expected in (True, None, "A" * 64, "a" * 63):
            with self.subTest(expected=expected), self.assertRaises(ValueError):
                project(document(), expected)

    def test_valid_member_roll_and_catalog_literal_keep_separate_safe_origins(self):
        result = project(document(), SHA)
        member = result["members"][1]
        effect = member["effects"]
        self.assertEqual((member["alias"], member["group_status"], member["gem_level"], effect["format"],
                          effect["rolled_lines"][0]["origin"], effect["rolled_lines"][0]["values"][0],
                          [entry for entry in effect["constants"] if entry["kind"] == "conversion"], result["accounting"]),
                         ("gem[2]", "ok", {"value": 7, "meaning": "observed_gem_level_not_effective"},
                          "tli-support-effects-canonical-v1", "native_prefix_row",
                          {"exact": "24.125", "fraction": "0.24125", "range": {"min": "23", "max": "29"}},
                          [{"origin": "catalog_literal", "source": {"field": "templateDescription", "line": 2},
                            "kind": "conversion", "parameters": {"from": "physical", "to": "cold", "percent": "100"},
                            "status": "catalog_literal_unverified_runtime"}],
                          {"members": 3, "effect_candidates": 1, "excluded": 1, "gaps": 1, "reconciles": True}))

    def test_accounting_and_layer_absence_require_typed_exact_counts(self):
        for key in ("members", "effectCandidates", "excluded", "gaps", "reconciles"):
            for value in ((False, 1, None) if key == "reconciles" else (True, -1, None, 999)):
                with self.subTest(key=key, value=value):
                    raw = document()
                    raw["accounting"][key] = value
                    with self.assertRaises(ValueError):
                        project(raw, SHA)

    def test_member_status_identity_coordinates_and_metadata_are_strict(self):
        cases = [("alias", "gem[1]"), ("group", "group[9]"), ("tabPosition", True),
                 ("tabPosition", 1), ("groupStatus", "unknown"), ("groupStatus", "no_primary_slot"),
                 ("slot", True), ("slot", 0), ("slot", None), ("baseId", True), ("baseId", None),
                 ("path", "sections.SkillLayout.data[0][0]"), ("path", "sections.Other.data[0][1]"),
                 ("path", "sections.SkillLayout.data[0][1];PRIVATE-INVENTORY-CANARY"), ("path", None),
                 ("category", "ordinary_support"), ("category", None), ("status", "verified"),
                 ("status", "excluded_category"), ("reason", "PRIVATE-INVENTORY-CANARY"),
                 ("gemLevel", {"value": True, "meaning": "observed_gem_level_not_effective"}),
                 ("gemLevel", {"value": 7, "meaning": "effective_level"})]
        for key, value in cases:
            with self.subTest(key=key, value=value):
                raw = document()
                raw["members"][1][key] = value
                with self.assertRaises(ValueError):
                    project(raw, SHA)
        raw = document()
        raw["members"][1]["slot"] = 6
        for member in raw["members"]:
            member["groupStatus"] = "ambiguous_slot"
        with self.assertRaises(ValueError):
            project(raw, SHA)

    def test_non_captured_client_cannot_report_empty_complete_counts(self):
        for status in ("absent", "invalid", "not_captured"):
            for change in ("members", "count"):
                with self.subTest(status=status, change=change):
                    raw = document()
                    raw.update(clientLayer=status, members=None)
                    raw["accounting"] = {key: None for key in raw["accounting"]}
                    if change == "members":
                        raw["members"] = []
                    else:
                        raw["accounting"]["gaps"] = 0
                    with self.assertRaises(ValueError):
                        project(raw, SHA)

    def test_nested_effect_identity_schema_and_unknown_claims_are_bound_to_the_member(self):
        cases = [(("format",), "other"), (("version",), "0.1.0"), (("catalogSchema",), "invalid"),
                 (("arithmeticReady",), True), (("runtimeVerified",), 0), (("activation",), "active"),
                 (("effectiveLevel",), None), (("patch",), "current"), (("additionalGroupIdentity",), "shared"),
                 (("identity", "status"), "base_identity_mismatch"), (("identity", "nativeBaseId"), True),
                 (("identity", "catalogTlidbId"), 90018), (("identity", "category"), "Magnificent_Support"),
                 (("identity", "guid"), {"accountId": "PRIVATE-INVENTORY-CANARY"}),
                 (("identity", "guid"), "x" * 65), (("prefix", "status"), "complete"),
                 (("prefix", "rows"), True), (("prefix", "nullRows"), 3)]
        for path, value in cases:
            with self.subTest(path=path):
                raw = document()
                node = raw["members"][1]["effects"]
                for key in path[:-1]:
                    node = node[key]
                node[path[-1]] = value
                with self.assertRaises(ValueError):
                    project(raw, SHA)

    def test_roll_identity_template_paths_and_lexical_values_cannot_be_reinterpreted(self):
        cases = [(("origin",), "catalog_literal"), (("status",), "verified"), (("path",), "prefix[2]"),
                 (("path",), "sections.Other[0]"), (("lineId",), "x" * 65), (("nativeId",), "x" * 33),
                 (("nativeId",), 913721), (("tier",), True), (("role",), "additional_damage"),
                 (("unit",), "fraction"), (("template",), "+#% unknown damage"),
                 (("values", 0, "exact"), 24.125), (("values", 0, "exact"), "1e2"),
                 (("values", 0, "fraction"), "0.24"), (("values", 0, "range", "min"), "29"),
                 (("values", 0, "range", "min"), "-1"), (("nativeVersion", "value"), True),
                 (("nativeVersion", "meaning"), "rank")]
        for path, value in cases:
            with self.subTest(path=path):
                raw = document()
                node = raw["members"][1]["effects"]["rolledLines"][0]
                for key in path[:-1]:
                    node = node[key]
                node[path[-1]] = value
                with self.assertRaises(ValueError):
                    project(raw, SHA)
        raw = document()
        effect = raw["members"][1]["effects"]
        effect["omissions"] = [{"origin": "native_prefix_row", "path": "prefix[1]", "reason": "invalid_row"}]
        effect["prefix"]["rows"] = 3
        with self.assertRaises(ValueError):
            project(raw, SHA)

    def test_one_duplicate_omission_cannot_claim_that_all_duplicate_peers_were_removed(self):
        from damage_lab.supportinventory import summary

        raw = document()
        canonical = project(raw, SHA)
        for data, operation in ((raw, lambda value: project(value, SHA)), (canonical, summary)):
            with self.subTest(format=data["format"]):
                effect = data["members"][1]["effects"]
                effect["prefix"]["rows"] = 3
                effect["omissions"] = [{"origin": "native_prefix_row", "path": "prefix[2]", "reason": "duplicate_line"}]
                with self.assertRaises(ValueError):
                    operation(data)

    def test_multiple_duplicate_omissions_keep_other_unsupported_rows_and_exact_rolls_separate(self):
        from damage_lab.supportinventory import summary

        for count in (2, 3):
            with self.subTest(count=count):
                raw = document()
                effect = raw["members"][1]["effects"]
                effect["prefix"]["rows"] = count + 3
                effect["omissions"] = [{"origin": "native_prefix_row", "path": f"prefix[{index}]", "reason": "duplicate_line"}
                                       for index in range(2, count + 2)]
                effect["omissions"].append({"origin": "native_prefix_row", "path": f"prefix[{count + 2}]",
                                             "reason": "unsupported_template"})
                result = project(raw, SHA)
                self.assertEqual((result["members"][1]["effects"]["omissions"],
                                  len(result["members"][1]["effects"]["rolled_lines"]), summary(result)),
                                 (effect["omissions"], 1, result))

    def test_catalog_literals_keep_exact_known_parameters_and_lf_line_coordinates(self):
        for path, value in ((("origin",), "native_prefix_row"), (("status",), "verified"),
                            (("source", "field"), "templateDescriptionDetail"), (("source", "line"), True),
                            (("source", "line"), -1), (("source", "line"), 1),
                            (("parameters", "to"), "fire"), (("parameters", "percent"), True)):
            with self.subTest(path=path):
                raw = document()
                node = raw["members"][1]["effects"]["constants"][2]
                for key in path[:-1]:
                    node = node[key]
                node[path[-1]] = value
                with self.assertRaises(ValueError):
                    project(raw, SHA)
        raw = document()
        raw["members"][1]["effects"]["constantIssues"] = [
            {"source": {"field": "templateDescription", "line": 9}, "reason": "PRIVATE-INVENTORY-CANARY"}]
        with self.assertRaises(ValueError):
            project(raw, SHA)

    def test_summary_revalidates_the_canonical_tree_and_removes_deep_unknown_properties(self):
        from damage_lab.supportinventory import summary

        canonical = project(document(), SHA)
        dirty = copy.deepcopy(canonical)
        nodes = [dirty, dirty["source"], dirty["accounting"], dirty["members"][1],
                 dirty["members"][1]["gem_level"], dirty["members"][1]["effects"],
                 dirty["members"][1]["effects"]["identity"], dirty["members"][1]["effects"]["prefix"],
                 dirty["members"][1]["effects"]["rolled_lines"][0],
                 dirty["members"][1]["effects"]["rolled_lines"][0]["values"][0]["range"],
                 dirty["members"][1]["effects"]["constants"][2]["source"],
                 dirty["members"][1]["effects"]["constants"][2]["parameters"]]
        for node in nodes:
            node["rawItemId"] = {"accountId": "PRIVATE-INVENTORY-CANARY"}
        result = summary(dirty)
        result["members"][1]["effects"]["constants"][2]["parameters"]["to"] = "changed"
        self.assertEqual((summary(dirty), canonical), (canonical, canonical))

    def test_gap_reasons_cannot_claim_metadata_unavailable_at_that_stage(self):
        for reason, base, category in (("raw_node_invalid", 90033, None),
                                       ("native_base_invalid", None, "noble_support"),
                                       ("catalog_record_missing", None, None),
                                       ("catalog_identity_mismatch", 90033, "active_skill"),
                                       ("prefix_invalid", 90033, None),
                                       ("slot_position_invalid", 90033, "noble_support"),
                                       ("slot_position_ambiguous", 90033, "noble_support")):
            with self.subTest(reason=reason):
                raw = document()
                raw["members"][2].update(reason=reason, baseId=base, category=category)
                with self.assertRaises(ValueError):
                    project(raw, SHA)

    def test_summary_rejects_forged_canonical_runtime_numbers_and_versions(self):
        from damage_lab.supportinventory import summary

        for path, value in ((("format",), "tli-installed-support-effects-v0"), (("runtime_verified",), True),
                            (("accounting", "effect_candidates"), False),
                            (("members", 1, "effects", "version"), "0.1.0"),
                            (("members", 1, "effects", "rolled_lines", 0, "values", 0, "fraction"), "0.5")):
            with self.subTest(path=path):
                result = project(document(), SHA)
                node = result
                for key in path[:-1]:
                    node = node[key]
                node[path[-1]] = value
                with self.assertRaises(ValueError):
                    summary(result)

    def test_unique_members_can_keep_candidates_in_an_ambiguous_tab(self):
        raw = document()
        raw["members"][2]["slot"] = 1
        for member in raw["members"]:
            member["groupStatus"] = "ambiguous_slot"
        result = project(raw, SHA)
        self.assertEqual((result["members"][1]["status"], result["members"][1]["group_status"]),
                         ("effect_candidates", "ambiguous_slot"))

    def test_missing_prefix_gem_level_and_guid_stay_unknown_without_zero_defaults(self):
        raw = document()
        raw["members"][1]["gemLevel"]["value"] = None
        raw["members"][1]["effects"] = effects(catalog(), native_base_id=90017, prefix_rows=None)
        raw["effectsVersion"] = "0.3.0"
        raw["members"][1]["effects"]["identity"]["guid"] = None
        member = project(raw, SHA)["members"][1]
        self.assertEqual((member["gem_level"]["value"], member["effects"]["identity"]["guid"],
                          member["effects"]["prefix"], member["effects"]["rolled_lines"], member["effects"]["omissions"]),
                         (None, None, {"status": "absent", "rows": None, "null_rows": None}, None, None))

    def test_signed_lexical_values_survive_a_hostile_caller_decimal_context(self):
        raw = document()
        line = raw["members"][1]["effects"]["rolledLines"][0]
        line.update(role="additional_damage", template="#% additional damage for the supported skill")
        line["values"] = [{"exact": "-27.7500", "fraction": "-0.2775", "range": {"min": "-29", "max": "-23"}}]
        with localcontext() as context:
            context.prec = 2
            context.Emin, context.Emax = -1, 1
            context.traps[Inexact] = context.traps[Rounded] = True
            value = project(raw, SHA)["members"][1]["effects"]["rolled_lines"][0]["values"][0]
        self.assertEqual(value, {"exact": "-27.7500", "fraction": "-0.2775", "range": {"min": "-29", "max": "-23"}})

    def test_partial_unsupported_evidence_remains_diagnostic_with_explicit_omissions(self):
        raw = document()
        effect = raw["members"][1]["effects"]
        effect["rolledLines"] = []
        effect["omissions"] = [{"origin": "native_prefix_row", "path": "prefix[1]", "reason": "unsupported_template"}]
        effect["constantIssues"] = [{"source": {"field": "templateDescription", "line": 9}, "reason": "unknown_constant"}]
        result = project(raw, SHA)
        self.assertEqual((result["members"][1]["status"], result["arithmetic_ready"], result["import_complete"],
                          result["members"][1]["effects"]["omissions"][0]["reason"]),
                         ("effect_candidates", False, False, "unsupported_template"))

    def test_raw_extra_properties_are_removed_without_mutating_the_document(self):
        raw = document()
        nodes = [raw, raw["source"], raw["members"][1], raw["members"][1]["effects"]["identity"],
                 raw["members"][1]["effects"]["rolledLines"][0]["values"][0]]
        for node in nodes:
            node["rawItemId"] = {"accountId": "PRIVATE-INVENTORY-CANARY"}
        before = copy.deepcopy(raw)
        result = project(raw, SHA)
        self.assertEqual((raw == before, "PRIVATE-INVENTORY-CANARY" in json.dumps(result)), (True, False))

    def test_equal_constants_on_distinct_members_are_preserved_without_shared_mutation(self):
        raw = document()
        raw["members"][2] = copy.deepcopy(raw["members"][1])
        raw["members"][2].update(alias="gem[3]", slot=6, path="sections.SkillLayout.data[0][2]")
        raw["accounting"].update(effectCandidates=2, gaps=0)
        result = project(raw, SHA)
        first, second = result["members"][1:]
        first["effects"]["constants"][2]["parameters"]["to"] = "changed"
        self.assertEqual((len(first["effects"]["constants"]), len(second["effects"]["constants"]),
                          second["effects"]["constants"][2]["parameters"]["to"],
                          second["effects"]["additional_group_identity"]), (4, 4, "cold", "unresolved"))

    def test_captured_empty_inventory_is_explicit_zero_without_a_completeness_claim(self):
        raw = document()
        raw["members"] = []
        raw["accounting"] = {"members": 0, "effectCandidates": 0, "excluded": 0, "gaps": 0, "reconciles": True}
        result = project(raw, SHA)
        self.assertEqual((result["members"], result["accounting"]["members"], result["import_complete"]), ([], 0, False))

    def test_missing_required_shapes_raise_controlled_errors_without_raw_payload(self):
        raws = [None, [], {}]
        for key in document():
            raw = document()
            del raw[key]
            raws.append(raw)
        for path in (("members", 1, "gemLevel"), ("members", 1, "effects", "identity"),
                     ("members", 1, "effects", "rolledLines", 0, "values", 0, "range")):
            raw = document()
            node = raw
            for key in path[:-1]:
                node = node[key]
            node[path[-1]] = {"raw": "PRIVATE-INVENTORY-CANARY"}
            raws.append(raw)
        for raw in raws:
            with self.subTest(kind=type(raw).__name__), self.assertRaises(ValueError):
                project(raw, SHA)
