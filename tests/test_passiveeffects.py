"""Bind fictional Ice Focus cells without applying its buff or separate skill damage."""

import copy
from decimal import Decimal, localcontext
import json
import unittest

from damage_lab.passiveeffects import effect, summary


def record():
    """Use irregular scalar/range fields and distinct fictional reference and observed rows."""
    template = ("Activates Focus and gains a buff:\n#% additional Cold Damage\n"
        "Gains 30 Focus Pts when dealing damage to Frostbitten enemies. Interval: 0.4 s.\n"
        "Upon reaching 100 Focus Pts, creates an Ice Storm that follows the character. When there are enemies inside the storm, consumes 45 Focus Pts every 0.5 s to generate Glacial Spikes that deal Spell Cold Damage to the enemies\n"
        "For every 1% Focus Speed, +1% Focus Pts gained, up to\n"
        "+200%. The Ice Storm ends when Focus Pts drop to 0.\n"
        "+4% additional damage for this skill\nGlacial Spike:\nDeals #-# Spell Cold Damage.")
    return {"tlidbId": 8318, "id": "fictional-ice-focus", "category": "Passive", "catalogPath": "skill/Passive",
        "descriptionBindings": {"template": "templateDescription", "level": 3, "bindings": ["value4", "value9Min"]},
        "levelProgression": [{"level": 3, "value4": Decimal("9.625"), "value9Min": 19, "value9Max": 31},
                             {"level": 17, "value4": "-13/8", "value9Min": 43, "value9Max": 67}],
        "english": {"templateDescription": template,
                    "description": template.replace("#-#", "19-31").replace("#", "9.625")}}


class PassiveEffectsTests(unittest.TestCase):
    """Keep the player Cold buff distinct from Glacial Spike and the self-skill literal."""

    def test_the_declared_observed_scalar_is_a_signed_player_cold_buff_candidate(self):
        result = effect(record(), catalog_id=8318, level=17)
        row = result["candidate"]
        self.assertEqual((result["status"], row["kind"], row["owner"], row["target"], row["scope"], row["value"]),
            ("candidate", "additional_damage", "player", "cold_damage", "focus_buff",
             {"cell": {"text": "-13/8", "kind": "rational"}, "percent": {"numerator": -13, "denominator": 8},
              "fraction": {"numerator": -13, "denominator": 800}}))

    def test_both_declared_fields_are_followed_without_guessing_value1_or_value7(self):
        value = record()
        for row in value["levelProgression"]:
            row.update(value1=937, value7Min=103, value7Max=197)
        binding = effect(value, catalog_id=8318, level=17)["candidate"]["binding"]
        self.assertEqual((binding["field"], binding["range"], binding["reference_scalar_cell"], binding["observed_range_cells"]),
            ("value4", {"min_field": "value9Min", "max_field": "value9Max", "line": 8, "token_index": 1},
             {"text": "9.625", "kind": "decimal"}, {"min": {"text": "43", "kind": "integer"}, "max": {"text": "67", "kind": "integer"}}))

    def test_the_complete_nine_line_reference_including_both_placeholders_is_retained(self):
        value = record()
        result = effect(value, catalog_id=8318, level=17)
        binding = result["candidate"]["binding"]
        self.assertEqual((binding["template"], binding["reference_description"], binding["line"], binding["token_index"], binding["status"]),
                         (value["english"]["templateDescription"], value["english"]["description"], 1, 0, "whole_reference_render_consistent"))

    def test_reference_text_drift_on_any_modeled_or_unmodeled_line_is_unresolved(self):
        for change in ("Activates Focus", "9.625%", "Frostbitten", "+4%", "19-31"):
            with self.subTest(change=change):
                value = record()
                value["english"]["description"] = value["english"]["description"].replace(change, change + " ")
                result = effect(value, catalog_id=8318, level=17)
                self.assertEqual((result["reason"], result["candidate"]), ("reference_render_unresolved", None))

    def test_the_exact_whole_template_cannot_be_replaced_with_similar_cold_damage_text(self):
        for change in ("#% additional Cold Damage", "+4% additional damage for this skill", "Deals #-# Spell Cold Damage."):
            with self.subTest(change=change):
                value = record()
                value["english"]["templateDescription"] = value["english"]["templateDescription"].replace(change, change + " ")
                self.assertEqual(effect(value, catalog_id=8318, level=17)["reason"], "template_unbound")

    def test_identity_category_and_catalog_path_are_exact_without_name_or_prefix_fallback(self):
        for field, invalid in (("tlidbId", "8318"), ("tlidbId", True), ("tlidbId", 8319),
                               ("id", None), ("id", "private identity"), ("category", "Active"), ("catalogPath", "skill/Support")):
            with self.subTest(field=field):
                value = record()
                value[field] = invalid
                value["english"]["name"] = "Precise: Ice Focus"
                value["nativePrefix"] = {"unknown": "PRIVATE-PASSIVE-CANARY"}
                self.assertIsNone(effect(value, catalog_id=8318, level=17)["candidate"])

    def test_unsupported_passives_never_become_an_empty_supported_effect(self):
        for identity in (7112, 8301, 8309):
            with self.subTest(identity=identity):
                value = record()
                value["tlidbId"] = identity
                value.pop("descriptionBindings")
                value.pop("levelProgression")
                result = effect(value, catalog_id=identity, level=17)
                self.assertEqual((result["status"], result["reason"], result["gaps"], result["candidate"]),
                                 ("unresolved", "unsupported_catalog_id", ["unsupported_catalog_id"], None))

    def test_binding_arity_scalar_range_order_and_exact_field_grammar_are_required(self):
        for fields in ([], ["value4"], ["value4", "value9Min", "value3"], ["value9Min", "value4"],
                       ["value4", "value9Max"], ["payload", "value9Min"], ["value4", {}]):
            with self.subTest(fields=fields):
                value = record()
                value["descriptionBindings"]["bindings"] = fields
                self.assertIsNone(effect(value, catalog_id=8318, level=17)["candidate"])

    def test_reference_and_observed_rows_must_be_unique_without_interpolation(self):
        for index, duplicate, reason in ((0, False, "reference_level_missing"), (0, True, "reference_level_ambiguous"),
                                         (1, False, "observed_level_missing"), (1, True, "observed_level_ambiguous")):
            with self.subTest(index=index, duplicate=duplicate):
                value = record()
                if duplicate:
                    value["levelProgression"].append(copy.deepcopy(value["levelProgression"][index]))
                else:
                    value["levelProgression"].pop(index)
                self.assertEqual(effect(value, catalog_id=8318, level=17)["reason"], reason)

    def test_levels_and_tables_cannot_be_coerced_or_extended_past_the_pinned_catalog(self):
        for field, invalid in (("reference", True), ("reference", 0), ("reference", 41),
                               ("row", 3.0), ("row", True), ("row", 41), ("table", [None]), ("table", [])):
            with self.subTest(field=field, invalid=invalid):
                value = record()
                if field == "reference":
                    value["descriptionBindings"]["level"] = invalid
                elif field == "row":
                    value["levelProgression"][0]["level"] = invalid
                else:
                    value["levelProgression"] = invalid
                self.assertIsNone(effect(value, catalog_id=8318, level=17)["candidate"])

    def test_the_reference_scalar_cannot_be_rounded_to_force_an_exact_render(self):
        value = record()
        value["levelProgression"][0]["value4"] = "1/3"
        value["english"]["description"] = value["english"]["description"].replace("9.625", "0.333")
        self.assertEqual(effect(value, catalog_id=8318, level=17)["reason"], "reference_render_unresolved")

    def test_a_nonterminating_observed_scalar_keeps_an_exact_rational_fraction(self):
        value = record()
        value["levelProgression"][1]["value4"] = "-1/3"
        result = effect(value, catalog_id=8318, level=17)
        self.assertEqual((result["candidate"]["value"]["fraction"], summary(result)),
                         ({"numerator": -1, "denominator": 300}, result))

    def test_reference_and_observed_glacial_ranges_require_nonnegative_ordered_integer_cells(self):
        for index in (0, 1):
            for field, invalid in (("value9Min", -1), ("value9Min", 100), ("value9Min", 19.0),
                                   ("value9Min", True), ("value9Min", "19"), ("value9Max", None), ("value9Max", 10 ** 12)):
                with self.subTest(index=index, field=field, invalid=invalid):
                    value = record()
                    value["levelProgression"][index][field] = invalid
                    self.assertEqual(effect(value, catalog_id=8318, level=17)["reason"],
                                     ("reference" if index == 0 else "observed") + "_range_invalid")

    def test_glacial_range_changes_do_not_become_player_cold_buff_damage(self):
        value = record()
        value["levelProgression"][1].update(value9Min=113, value9Max=197)
        before = effect(record(), catalog_id=8318, level=17)["candidate"]
        after = effect(value, catalog_id=8318, level=17)["candidate"]
        self.assertEqual((before["value"], before["unmodelled_effects"]), (after["value"], after["unmodelled_effects"]))

    def test_float_scalars_require_exact_loading_instead_of_reconstructed_source_lexemes(self):
        for index, reason in ((0, "reference_cell_requires_exact_number"), (1, "observed_cell_requires_exact_number")):
            with self.subTest(index=index):
                value = record()
                value["levelProgression"][index]["value4"] = 9.625
                self.assertEqual(effect(value, catalog_id=8318, level=17)["reason"], reason)

    def test_scalar_cells_are_signed_exact_and_bounded_without_evaluating_expressions(self):
        for invalid in (True, None, {}, [], "1/0", "1+2", " 7.3", "+7.3", "1e3", "٣", "1" * 13,
                        "0." + "1" * 10, Decimal("1E+999999"), Decimal("1E-999999")):
            with self.subTest(kind=type(invalid).__name__):
                value = record()
                value["levelProgression"][1]["value4"] = invalid
                self.assertEqual(effect(value, catalog_id=8318, level=17)["reason"], "observed_cell_invalid")

    def test_exact_large_decimal_ratios_survive_tiny_caller_context_and_the_canonical_digit_bound(self):
        value = record()
        value["levelProgression"][1]["value4"] = Decimal("-999999999999.999999999")
        with localcontext() as context:
            context.prec = 1
            for signal in context.traps:
                context.traps[signal] = True
            result = effect(value, catalog_id=8318, level=17)
            restored = summary(result)
        self.assertEqual((result["candidate"]["value"]["percent"], restored),
                         ({"numerator": -999999999999999999999, "denominator": 1000000000}, result))

    def test_explicit_zero_and_valid_rational_cells_are_not_missing_or_rounded(self):
        for cell, expected in ((0, {"numerator": 0, "denominator": 1}),
                               ("1/1024", {"numerator": 1, "denominator": 102400}),
                               ("-999999999999/999999999998", {"numerator": -999999999999, "denominator": 99999999999800})):
            with self.subTest(cell=cell):
                value = record()
                value["levelProgression"][1]["value4"] = cell
                result = effect(value, catalog_id=8318, level=17)
                self.assertEqual((result["candidate"]["value"]["fraction"], summary(result)), (expected, result))

    def test_same_level_reference_and_observation_use_one_scalar_and_one_range(self):
        result = effect(record(), catalog_id=8318, level=3)
        binding = result["candidate"]["binding"]
        self.assertEqual((summary(result), result["candidate"]["value"]["fraction"], binding["reference_range_cells"]),
                         (result, {"numerator": 77, "denominator": 800}, binding["observed_range_cells"]))

    def test_same_level_scalar_and_range_proof_disagreements_are_rejected(self):
        for part in ("scalar", "range"):
            with self.subTest(part=part):
                value = effect(record(), catalog_id=8318, level=3)
                if part == "scalar":
                    value["candidate"]["value"] = {"cell": {"text": "9.75", "kind": "decimal"},
                        "percent": {"numerator": 39, "denominator": 4}, "fraction": {"numerator": 39, "denominator": 400}}
                else:
                    value["candidate"]["binding"]["observed_range_cells"]["min"]["text"] = "20"
                with self.assertRaisesRegex(ValueError, "^Passive effects contain an invalid catalog candidate contract$"):
                    summary(value)

    def test_full_proof_reconstruction_drops_unknowns_and_detaches_nested_cells(self):
        expected = effect(record(), catalog_id=8318, level=17)
        value = copy.deepcopy(expected)
        for row in (value, value["identity"], value["lookup"], value["candidate"], value["candidate"]["value"],
                    value["candidate"]["value"]["cell"], value["candidate"]["value"]["percent"], value["candidate"]["binding"],
                    value["candidate"]["binding"]["range"], value["candidate"]["binding"]["reference_range_cells"],
                    value["candidate"]["binding"]["observed_range_cells"]["max"]):
            row["opaque"] = {"account": "PRIVATE-PASSIVE-CANARY"}
        restored = summary(value)
        restored["candidate"]["binding"]["reference_scalar_cell"]["text"] = "0"
        expected["candidate"]["binding"]["reference_scalar_cell"]["text"] = "0"
        self.assertEqual((restored, value["candidate"]["binding"]["reference_scalar_cell"]["text"]), (expected, "9.625"))

    def test_canonical_claims_roles_types_and_reference_render_cannot_be_forged(self):
        for path, invalid in ((("arithmetic_ready",), True), (("runtime_verified",), 0), (("effective_level",), 17),
                               (("activation",), "active"), (("candidate", "owner"), "skill"),
                               (("candidate", "scope"), "global"), (("candidate", "value", "fraction", "numerator"), True),
                               (("candidate", "binding", "field"), []), (("candidate", "binding", "line"), 1.0),
                               (("candidate", "binding", "range", "min_field"), {}),
                               (("candidate", "binding", "range", "max_field"), "value7Max"),
                               (("candidate", "binding", "range", "token_index"), True),
                               (("candidate", "binding", "reference_description"), "PRIVATE-PASSIVE-CANARY"),
                               (("candidate", "binding", "reference_range_cells", "min", "text"), "-1"),
                               (("candidate", "unmodelled_effects"), [])):
            with self.subTest(path=path):
                value = effect(record(), catalog_id=8318, level=17)
                node = value
                for field in path[:-1]:
                    node = node[field]
                node[path[-1]] = invalid
                with self.assertRaisesRegex(ValueError, "^Passive effects contain an invalid catalog candidate contract$"):
                    summary(value)

    def test_unmodeled_literal_and_all_runtime_claims_stay_separate_from_the_buff_scalar(self):
        result = effect(record(), catalog_id=8318, level=17)
        self.assertEqual((result["candidate"]["unmodelled_effects"], result["effective_level"], result["activation"],
                          result["eligibility"], result["additional_group_identity"], result["patch"],
                          [result[key] for key in ("arithmetic_ready", "runtime_verified", "identity_verified", "import_complete")]),
                         (["focus_resource_and_ice_storm_mechanics", "self_skill_additional_damage_literal_4_percent", "glacial_spike_damage"],
                          None, "unknown", "unverified", "unresolved", "unknown", [False] * 4))

    def test_raw_payloads_are_neither_mutated_nor_copied_into_the_candidate(self):
        value = record()
        value["native"] = {"account": "PRIVATE-PASSIVE-CANARY"}
        before = copy.deepcopy(value)
        result = effect(value, catalog_id=8318, level=17)
        result["candidate"]["binding"]["observed_range_cells"]["min"]["text"] = "0"
        self.assertEqual((value, "PRIVATE-PASSIVE-CANARY" in json.dumps(result)), (before, False))

    def test_unresolved_capsules_keep_their_fixed_gap_and_unknown_identity_metadata(self):
        value = record()
        value["id"] = None
        result = effect(value, catalog_id=8318, level=17)
        self.assertEqual((summary(result), result["reason"], result["candidate"]), (result, "catalog_identity_unbound", None))

    def test_api_levels_and_source_catalog_ids_require_strict_bounded_integers(self):
        for level in (True, 0, -1, 41, 17.0, "17", None):
            with self.subTest(level=level), self.assertRaises(ValueError):
                effect(record(), catalog_id=8318, level=level)
        for identity in (True, 0, 8318.0, "8318", 10 ** 20):
            with self.subTest(identity=identity), self.assertRaises(ValueError):
                effect(record(), catalog_id=identity, level=17)

    def test_preflight_refuses_unbounded_nonjson_cyclic_and_unencodable_inputs_privately(self):
        shared = []
        cycle = {}
        cycle["self"] = cycle
        nested = None
        for _ in range(33):
            nested = [nested]
        for label, invalid in (("cycle", cycle), ("shared", [shared, shared]), ("utf8", "\ud800"),
                               ("width", [None] * 4097), ("depth", nested), ("nodes", [[None] * 4096 for _ in range(5)]),
                               ("huge_integer", 10 ** 5000), ("nonfinite", float("inf"))):
            with self.subTest(label=label):
                value = record()
                value["opaque"] = invalid
                with self.assertRaisesRegex(ValueError, "^Passive effects contain an invalid catalog candidate contract$"):
                    effect(value, catalog_id=8318, level=17)
