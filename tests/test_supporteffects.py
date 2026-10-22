import copy
import json
import unittest
from decimal import Inexact, Rounded, localcontext

from damage_lab.supporteffects import EffectsError, effects


def catalog():
    """A fictional tiered support with separate catalog literals and native roll coordinates."""
    return {
        "id": "synthetic-support", "tlidbId": 90017, "category": "Noble_Support",
        "lines": [{"id": "X9", "kind": "tiered"}],
        "tierProgression": [
            {"tier": tier, "lines": [{"id": "X9", "modifierId": f"X9{tier}",
                                      "values": [{"min": low, "max": high}]}]}
            for tier, low, high in ((0, 37, 41), (1, 23, 29), (2, 11, 17))],
        "english": {
            "lineTemplates": {"X9": "+#% additional Hit Damage for the supported skill"},
            "templateDescription": "Supports Chromatic Shot\n+20% additional damage for the supported skill\n"
                                   "Converts 100% of the supported skill's Physical Damage to Cold Damage\n"
                                   "The supported skill gains the Cold Tag\n"
                                   "+#% additional Hit Damage for the supported skill",
        },
    }


def row(identity, values):
    return {"Id": identity, "DynArgs": values, "Version": 7}


class SupportEffectsTests(unittest.TestCase):
    """Keep exact catalog-bound candidates separate from runtime arithmetic and opaque source payloads."""

    def test_a_full_native_id_selects_its_own_tier_and_preserves_exact_percent_values(self):
        result = effects(catalog(), native_base_id=90017, prefix_rows=[row("X91", ["24.125"])])
        self.assertEqual(result["rolledLines"], [{
            "origin": "native_prefix_row", "path": "prefix[0]", "lineId": "X9", "nativeId": "X91", "tier": 1,
            "role": "additional_hit_damage", "unit": "percent",
            "template": "+#% additional Hit Damage for the supported skill",
            "values": [{"exact": "24.125", "fraction": "0.24125", "range": {"min": "23", "max": "29"}}],
            "nativeVersion": {"value": 7, "meaning": "unverified"}, "status": "native_roll_exact",
        }])

    def test_other_tiers_require_their_full_id_and_never_use_the_preview_range(self):
        outcomes = []
        for identity, value in (("X90", "39.125"), ("X92", "13.5")):
            result = effects(catalog(), native_base_id=90017, prefix_rows=[row(identity, [value])])
            outcomes.append((result["rolledLines"][0]["tier"], result["rolledLines"][0]["values"][0]["exact"]))
        self.assertEqual(outcomes, [(0, "39.125"), (2, "13.5")])

    def test_a_roll_cannot_move_to_another_tier_where_it_would_fit(self):
        result = effects(catalog(), native_base_id=90017, prefix_rows=[row("X92", ["24.125"])])
        self.assertEqual((result["rolledLines"], result["omissions"]), ([], [
            {"origin": "native_prefix_row", "path": "prefix[0]", "reason": "value_out_of_range"}]))

    def test_ids_are_not_truncated_or_matched_by_name(self):
        outcomes = []
        for identity in ("X9", "X91suffix", "SyntheticSupport"):
            result = effects(catalog(), native_base_id=90017, prefix_rows=[row(identity, [24])])
            outcomes.append((result["rolledLines"], result["omissions"][0]["reason"]))
        self.assertEqual(outcomes, [([], "no_exact_definition")] * 3)

    def test_integer_native_ids_still_match_the_entire_catalog_identifier(self):
        record = catalog()
        record["tierProgression"][1]["lines"][0]["modifierId"] = "913721"
        result = effects(record, native_base_id=90017, prefix_rows=[row(913721, [24])])
        self.assertEqual((result["rolledLines"][0]["nativeId"], result["rolledLines"][0]["tier"]), ("913721", 1))

    def test_negative_additional_damage_preserves_its_sign_without_absolute_values(self):
        record = catalog()
        record["english"]["lineTemplates"]["X9"] = "#% additional damage for the supported skill"
        record["tierProgression"][1]["lines"][0]["values"] = [{"min": -29, "max": -23}]
        result = effects(record, native_base_id=90017, prefix_rows=[row("X91", ["-27.75"])])
        line = result["rolledLines"][0]
        self.assertEqual((line["role"], line["values"], result["additionalGroupIdentity"]), (
            "additional_damage", [{"exact": "-27.75", "fraction": "-0.2775", "range": {"min": "-29", "max": "-23"}}],
            "unresolved"))

    def test_conflicting_template_and_roll_signs_are_not_repaired(self):
        outcomes = []
        for template in ("+#% additional Hit Damage for the supported skill", "-#% additional damage for the supported skill"):
            record = catalog()
            record["english"]["lineTemplates"]["X9"] = template
            record["tierProgression"][1]["lines"][0]["values"] = [{"min": -29, "max": -23}]
            result = effects(record, native_base_id=90017, prefix_rows=[row("X91", [-24])])
            outcomes.append((result["rolledLines"], result["omissions"][0]["reason"]))
        self.assertEqual(outcomes, [([], "sign_convention_unresolved")] * 2)

    def test_conversion_is_a_catalog_literal_with_a_text_line_origin_and_no_native_roll(self):
        result = effects(catalog(), native_base_id=90017, prefix_rows=None)
        self.assertEqual([entry for entry in result["constants"] if entry["kind"] == "conversion"], [{
            "origin": "catalog_literal", "source": {"field": "templateDescription", "line": 2},
            "kind": "conversion", "parameters": {"from": "physical", "to": "cold", "percent": "100"},
            "status": "catalog_literal_unverified_runtime"}])

    def test_literal_and_rolled_additional_damage_remain_separate_candidates(self):
        result = effects(catalog(), native_base_id=90017, prefix_rows=[row("X91", [24])])
        self.assertEqual(([entry["origin"] for entry in result["rolledLines"]],
                          [(entry["origin"], entry["parameters"]) for entry in result["constants"]
                           if entry["kind"] == "additional_damage"], result["arithmeticReady"]),
                         (["native_prefix_row"], [("catalog_literal", {"percent": "20"})], False))

    def test_conversion_lookalikes_and_unbound_placeholders_remain_issues(self):
        outcomes = []
        for description in ("Converts 50% of the supported skill's Physical Damage to Cold Damage",
                            "Converts #% of the supported skill's Physical Damage to Cold Damage",
                            "Converts 100% of the supported skill's Physical Damage to Cold Damage\r"):
            record = catalog()
            record["english"]["templateDescription"] = description
            result = effects(record, native_base_id=90017, prefix_rows=[])
            outcomes.append((result["constants"], result["constantIssues"]))
        self.assertEqual(outcomes, [([], [{"source": {"field": "templateDescription", "line": 0}, "reason": reason}])
                                    for reason in ("unknown_constant", "placeholder_without_line", "unknown_constant")])

    def test_multiline_rolled_templates_are_not_reinterpreted_as_catalog_constants(self):
        record = catalog()
        record["english"]["lineTemplates"]["X9"] = "+#% additional Hit Damage for the supported skill\nCreates 1 additional Tangle"
        record["english"]["templateDescription"] = record["english"]["lineTemplates"]["X9"]
        result = effects(record, native_base_id=90017, prefix_rows=[])
        self.assertEqual((result["constants"], result["constantIssues"]), ([], []))

    def test_absent_prefix_is_distinct_from_an_explicit_empty_prefix(self):
        outcomes = []
        for prefix in (None, []):
            result = effects(catalog(), native_base_id=90017, prefix_rows=prefix)
            outcomes.append((result["prefix"], result["rolledLines"], result["omissions"]))
        self.assertEqual(outcomes, [({"status": "absent", "rows": None, "nullRows": None}, None, None),
                                    ({"status": "supplied", "rows": 0, "nullRows": 0}, [], [])])

    def test_missing_description_is_distinct_from_a_supplied_empty_description(self):
        outcomes = []
        for description in (None, ""):
            record = catalog()
            record["english"]["templateDescription"] = description
            result = effects(record, native_base_id=90017, prefix_rows=[])
            outcomes.append((result["constants"], result["constantIssues"]))
        self.assertEqual(outcomes, [(None, None), ([], [])])

    def test_null_padding_is_counted_without_becoming_a_roll_or_an_omission(self):
        result = effects(catalog(), native_base_id=90017, prefix_rows=[None, row("X91", [24]), None])
        self.assertEqual((result["prefix"], result["rolledLines"][0]["path"], result["omissions"]),
                         ({"status": "supplied", "rows": 3, "nullRows": 2}, "prefix[1]", []))

    def test_duplicate_identities_are_counted_before_invalid_peer_values(self):
        peers = ({"Id": "X91"}, row("X91", None), row("X91", [None]), row("X91", [24, 17]),
                 row("X91", [99]), row("X90", [39]))
        outcomes = []
        for peer in peers:
            result = effects(catalog(), native_base_id=90017, prefix_rows=[row("X91", [24]), peer])
            outcomes.append((result["rolledLines"], [(entry["path"], entry["reason"]) for entry in result["omissions"]]))
        self.assertEqual(outcomes, [([], [("prefix[0]", "duplicate_line"), ("prefix[1]", "duplicate_line")])] * len(peers))

    def test_duplicate_catalog_modifier_ids_are_ambiguous_without_a_first_match(self):
        record = catalog()
        record["tierProgression"].append({"tier": 9, "lines": [
            {"id": "Other", "modifierId": "X91", "values": [{"min": 23, "max": 29}]}]})
        result = effects(record, native_base_id=90017, prefix_rows=[row("X91", [24])])
        self.assertEqual((result["rolledLines"], result["omissions"][0]["reason"]), ([], "ambiguous_definition"))

    def test_a_tiered_line_must_also_be_declared_by_the_catalog_record(self):
        record = catalog()
        record["lines"] = [{"id": "Other"}]
        result = effects(record, native_base_id=90017, prefix_rows=[row("X91", [24])])
        self.assertEqual((result["rolledLines"], result["omissions"][0]["reason"]), ([], "line_not_declared"))

    def test_fraction_is_exact_under_a_small_caller_decimal_context_and_traps(self):
        with localcontext() as context:
            context.prec = 3
            context.traps[Inexact] = True
            context.traps[Rounded] = True
            context.Emax = 1
            context.Emin = -1
            result = effects(catalog(), native_base_id=90017, prefix_rows=[row("X91", ["24.1234001"])])
        self.assertEqual(result["rolledLines"][0]["values"][0]["fraction"], "0.241234001")

    def test_the_largest_supported_decimal_shape_keeps_every_digit(self):
        record = catalog()
        record["tierProgression"][1]["lines"][0]["values"] = [{"min": "999999999999.123456789", "max": "999999999999.123456789"}]
        result = effects(record, native_base_id=90017, prefix_rows=[row("X91", ["999999999999.123456789"])])
        self.assertEqual(result["rolledLines"][0]["values"][0], {
            "exact": "999999999999.123456789", "fraction": "9999999999.99123456789",
            "range": {"min": "999999999999.123456789", "max": "999999999999.123456789"}})

    def test_float_repr_and_lexical_decimal_text_are_not_rounded_to_integers(self):
        outcomes = []
        for value in (24.0, "00024.1250"):
            result = effects(catalog(), native_base_id=90017, prefix_rows=[row("X91", [value])])
            outcomes.append(result["rolledLines"][0]["values"][0]["exact"])
        self.assertEqual(outcomes, ["24.0", "00024.1250"])

    def test_values_outside_the_bounded_numeric_contract_are_explicit_omissions(self):
        outcomes = []
        for value in (True, float("nan"), float("inf"), 10 ** 30 + 37, 10 ** 5000,
                      2.4e-5, "24.1234567890", "1e2", "PRIVATE-SUPPORT-CANARY"):
            result = effects(catalog(), native_base_id=90017, prefix_rows=[row("X91", [value])])
            outcomes.append((result["rolledLines"], result["omissions"][0]["reason"]))
        self.assertEqual(outcomes, [([], "invalid_value")] * 9)

    def test_invalid_catalog_bounds_are_not_replaced_with_preview_or_native_values(self):
        outcomes = []
        for bounds in ({"min": 29, "max": 23}, {"min": 23, "max": 10 ** 30},
                       {"min": True, "max": 29}, {"min": None, "max": 29}):
            record = catalog()
            record["tierProgression"][1]["lines"][0]["values"] = [bounds]
            result = effects(record, native_base_id=90017, prefix_rows=[row("X91", [24])])
            outcomes.append((result["rolledLines"], result["omissions"][0]["reason"]))
        self.assertEqual(outcomes, [([], "invalid_range")] * 4)

    def test_parameter_count_and_exact_percent_template_are_required_without_a_spec_unit(self):
        outcomes = []
        for change in ("count", "unit"):
            record = catalog()
            values = [24, 13] if change == "count" else [24]
            if change == "unit":
                record["english"]["lineTemplates"]["X9"] = "+# additional Hit Damage for the supported skill"
            result = effects(record, native_base_id=90017, prefix_rows=[row("X91", values)])
            outcomes.append((result["rolledLines"], result["omissions"][0]["reason"]))
        self.assertEqual(outcomes, [([], "value_count_mismatch"), ([], "unsupported_template")])

    def test_malformed_catalog_containers_and_identity_leaves_are_controlled_gaps(self):
        outcomes = []
        for change in ("lines", "line_id", "tiers", "tier_lines", "modifier_id", "english", "templates", "description"):
            record = catalog()
            if change == "lines":
                record["lines"] = 17
            elif change == "line_id":
                record["lines"] = [{"id": []}]
            elif change == "tiers":
                record["tierProgression"] = 17
            elif change == "tier_lines":
                record["tierProgression"][1]["lines"] = 17
            elif change == "modifier_id":
                record["tierProgression"][1]["lines"][0]["modifierId"] = {}
            elif change == "english":
                record["english"] = []
            elif change == "templates":
                record["english"]["lineTemplates"] = {"X9": 5}
            else:
                record["english"]["templateDescription"] = 17
            result = effects(record, native_base_id=90017, prefix_rows=[row("X91", [24])])
            outcomes.append((result["catalogSchema"], [result[key] for key in
                                                       ("rolledLines", "omissions", "constants", "constantIssues")]))
        self.assertEqual(outcomes, [("invalid", [None] * 4)] * 8)

    def test_missing_catalog_definition_remains_an_omission_without_a_default_roll(self):
        record = catalog()
        del record["tierProgression"]
        result = effects(record, native_base_id=90017, prefix_rows=[row("X91", [24])])
        self.assertEqual((result["catalogSchema"], result["rolledLines"], result["omissions"][0]["reason"]),
                         ("ok", [], "no_exact_definition"))

    def test_base_identity_mismatches_and_wrong_catalog_types_cannot_attribute_effects(self):
        outcomes = []
        for identity in (90019, 90017.0, True, "90017", None):
            record = catalog()
            record["tlidbId"] = identity
            result = effects(record, native_base_id=90017, prefix_rows=[row("X91", [24])])
            outcomes.append((result["identity"]["status"], [result[key] for key in
                                                             ("catalogSchema", "rolledLines", "omissions", "constants", "constantIssues")]))
        self.assertEqual(outcomes, [("base_identity_mismatch", [None] * 5)] + [("catalog_identity_invalid", [None] * 5)] * 4)

    def test_bad_api_arguments_raise_fixed_errors_without_the_private_payload(self):
        outcomes = []
        for record, identity, prefix in (([], 90017, []), (catalog(), True, []), (catalog(), 90017.0, []),
                                         (catalog(), "PRIVATE-SUPPORT-CANARY", []), (catalog(), 90017, "PRIVATE-SUPPORT-CANARY")):
            with self.assertRaises(EffectsError) as caught:
                effects(record, native_base_id=identity, prefix_rows=prefix)
            outcomes.append(("PRIVATE-SUPPORT-CANARY" in str(caught.exception), str(caught.exception).endswith("."),
                             "\n" in str(caught.exception)))
        self.assertEqual(outcomes, [(False, False, False)] * 5)

    def test_opaque_source_fields_and_unknown_constants_never_enter_the_projection(self):
        record = catalog()
        record["id"] = {"accountId": "PRIVATE-SUPPORT-CANARY"}
        record["accountId"] = "PRIVATE-SUPPORT-CANARY"
        record["english"]["opaque"] = {"raw": "PRIVATE-SUPPORT-CANARY"}
        record["english"]["templateDescription"] += "\nPRIVATE-SUPPORT-CANARY"
        prefix = row("X91", [24])
        prefix["ItemId"] = "PRIVATE-SUPPORT-CANARY"
        prefix["_Raw_Data"] = {"account": "PRIVATE-SUPPORT-CANARY"}
        self.assertNotIn("PRIVATE-SUPPORT-CANARY", json.dumps(effects(record, native_base_id=90017, prefix_rows=[prefix])))

    def test_output_mutations_leave_the_caller_and_later_results_unchanged(self):
        record, prefix = catalog(), [row("X91", ["24.125"])]
        before = copy.deepcopy((record, prefix))
        result = effects(record, native_base_id=90017, prefix_rows=prefix)
        expected = copy.deepcopy(result)
        result["constants"][0]["parameters"]["changed"] = 13
        result["rolledLines"][0]["values"][0]["range"]["min"] = "1"
        result["identity"]["guid"] = "changed"
        self.assertEqual(((record, prefix), effects(record, native_base_id=90017, prefix_rows=prefix)), (before, expected))

    def test_input_mutations_cannot_change_an_already_returned_candidate(self):
        record, prefix = catalog(), [row("X91", ["24.125"])]
        result = effects(record, native_base_id=90017, prefix_rows=prefix)
        prefix[0]["DynArgs"][0] = "10"
        record["tierProgression"][1]["lines"][0]["values"][0]["min"] = 0
        record["id"] = "changed"
        self.assertEqual((result["identity"]["guid"], result["rolledLines"][0]["values"][0]), (
            "synthetic-support", {"exact": "24.125", "fraction": "0.24125", "range": {"min": "23", "max": "29"}}))

    def test_native_version_is_observed_metadata_and_invalid_types_are_not_ranks(self):
        prefix = row("X91", [24])
        prefix["Version"] = True
        result = effects(catalog(), native_base_id=90017, prefix_rows=[prefix])
        self.assertEqual((result["rolledLines"][0]["nativeVersion"], result["effectiveLevel"]), (None, "unknown"))

    def test_every_result_remains_diagnostic_with_unverified_arithmetic_and_runtime(self):
        result = effects(catalog(), native_base_id=90017, prefix_rows=[row("X91", [24])])
        self.assertEqual((result["format"], result["version"], result["arithmeticReady"], result["activation"],
                          result["effectiveLevel"], result["patch"], result["runtimeVerified"],
                          result["additionalGroupIdentity"], "dps" in result),
                         ("tli-support-effects-v0", "0.2.0", False, "unknown", "unknown", "unknown", False, "unresolved", False))
