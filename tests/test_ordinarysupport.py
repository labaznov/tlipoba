"""Check a fictional ordinary-support table without enabling gameplay effects."""

import copy
from decimal import Decimal, localcontext
import json
import unittest

from damage_lab.ordinarysupport import effect, summary


def record():
    """Bind one scalar at an irregular observed level to a complete synthetic description."""
    return {"tlidbId": 7420, "id": "synthetic-critical-support", "category": "Support",
            "tags": ["Support"], "cannotSupport": [],
            "descriptionBindings": {"template": "templateDescription", "level": 3, "bindings": ["value7"]},
            "levelProgression": [{"level": 3, "value7": Decimal("12.500")}, {"level": 17, "value7": "113/7"}],
            "english": {"templateDescription": "Supports skills that hit enemies.\n+#% additional damage for the supported skill when it lands a Critical Strike",
                        "description": "Supports skills that hit enemies.\n+12.5% additional damage for the supported skill when it lands a Critical Strike"}}


def projectiles():
    """Keep a fictional signed table separate from a fixed projectile literal."""
    template = ("Supports Projectile Skills.\nProjectile Quantity of the supported skill\n+2\n"
                "#% additional damage for the supported skill")
    return {"tlidbId": 7401, "id": "synthetic-projectile-support", "category": "Support",
        "descriptionBindings": {"template": "templateDescription", "level": 3, "bindings": ["value9"]},
        "levelProgression": [{"level": 3, "value9": Decimal("-12.125")}, {"level": 17, "value9": "-113/7"}],
        "english": {"templateDescription": template, "description": template.replace("#", "-12.125")}}


class ProjectileSupportTests(unittest.TestCase):
    """Keep observed projectile support scalars distinct from hit topology and count totals."""

    def test_signed_damage_and_the_unbound_projectile_literal_are_separate(self):
        value = effect(projectiles(), catalog_id=7401, level=17)
        self.assertEqual((value["status"], value["candidate"]["kind"], value["candidate"]["target"],
                          value["candidate"]["scope"], value["candidate"]["value"]["fraction"],
                          value["candidate"]["projectile_quantity"]),
                         ("candidate", "additional_damage", "supported_skill", "projectile",
                          {"numerator": -113, "denominator": 700},
                          {"origin": "catalog_literal", "lines": [1, 2], "text": "+2", "value": 2,
                           "bound": False, "hit_semantics": "unknown"}))

    def test_a_signed_decimal_reference_is_rendered_exactly_under_any_caller_context(self):
        with localcontext() as context:
            context.prec = 1
            for signal in context.traps:
                context.traps[signal] = True
            value = effect(projectiles(), catalog_id=7401, level=17)
        self.assertEqual(value["candidate"]["binding"]["reference_description"], projectiles()["english"]["description"])

    def test_the_whole_four_line_template_and_separate_literal_must_match(self):
        for field, replacement in (("templateDescription", "+3"), ("description", "+3")):
            with self.subTest(field=field):
                data = projectiles()
                data["english"][field] = data["english"][field].replace("+2", replacement)
                self.assertIsNone(effect(data, catalog_id=7401, level=17)["candidate"])

    def test_projectile_table_and_reference_levels_cannot_exceed_the_observed_catalog_domain(self):
        for change, reason in (("selected", "observed_level_invalid"), ("reference", "binding_level_invalid"),
                               ("row", "level_table_invalid"), ("length", "level_table_invalid")):
            with self.subTest(change=change):
                data = projectiles()
                level = 41 if change == "selected" else 17
                if change == "reference":
                    data["descriptionBindings"]["level"] = 41
                elif change == "row":
                    data["levelProgression"][0]["level"] = 41
                elif change == "length":
                    data["levelProgression"] = [{"level": 1, "value9": 7} for _ in range(41)]
                self.assertEqual(effect(data, catalog_id=7401, level=level)["reason"], reason)

    def test_a_same_level_reference_cannot_disagree_with_the_observed_cell(self):
        data = effect(projectiles(), catalog_id=7401, level=17)
        data["candidate"]["binding"]["reference_level"] = 17
        with self.assertRaises(ValueError):
            summary(data)

    def test_a_forged_same_level_repeating_reference_cannot_claim_an_exact_render(self):
        data = effect(projectiles(), catalog_id=7401, level=17)
        data["candidate"]["binding"].update(reference_level=17, reference_cell={"text": "-113/7", "kind": "rational"})
        with self.assertRaises(ValueError):
            summary(data)

    def test_literal_values_and_line_coordinates_cannot_be_coerced_or_promoted(self):
        for field, invalid in (("value", 2.0), ("value", True), ("lines", [True, 2]), ("bound", 0),
                               ("bound", True), ("hit_semantics", "all_hit")):
            with self.subTest(field=field):
                data = effect(projectiles(), catalog_id=7401, level=17)
                data["candidate"]["projectile_quantity"][field] = invalid
                with self.assertRaises(ValueError):
                    summary(data)

    def test_the_new_candidate_cannot_be_smuggled_into_a_legacy_leaf_version(self):
        data = effect(projectiles(), catalog_id=7401, level=17)
        data["version"] = "0.1.0"
        with self.assertRaises(ValueError):
            summary(data)

    def test_legacy_critical_candidates_remain_byte_equivalent_after_revalidation(self):
        data = effect(record(), catalog_id=7420, level=17)
        data["version"] = "0.1.0"
        self.assertEqual(summary(data), data)

    def test_projectile_candidates_drop_opaque_fields_without_aliasing_or_changing_inputs(self):
        data = effect(projectiles(), catalog_id=7401, level=17)
        original = copy.deepcopy(data)
        data["candidate"]["projectile_quantity"]["opaque"] = "PRIVATE-PROJECTILE-CANARY"
        result = summary(data)
        self.assertEqual((result, original), (original, original))

    def test_the_documented_decimal_boundary_survives_both_family_roundtrips(self):
        for catalog, data, field in ((7401, projectiles(), "value9"), (7420, record(), "value7")):
            with self.subTest(catalog=catalog):
                data["levelProgression"][1][field] = Decimal("123456789012.123456789")
                result = effect(data, catalog_id=catalog, level=17)
                self.assertEqual(summary(result), result)


class OrdinarySupportTests(unittest.TestCase):
    """Keep exact level-table critical-hit candidates separate from full critical stats and activation."""

    def test_the_exact_observed_row_produces_a_critical_hit_candidate_with_an_exact_rational_fraction(self):
        result = effect(record(), catalog_id=7420, level=17)
        candidate = result["candidate"]
        self.assertEqual((result["status"], candidate["kind"], candidate["value"], result["lookup"], result["effective_level"]),
            ("candidate", "critical_hit_additional_damage",
             {"cell": {"text": "113/7", "kind": "rational"}, "percent": {"numerator": 113, "denominator": 7},
              "fraction": {"numerator": 113, "denominator": 700}},
             {"level": 17, "meaning": "observed_gem_level_not_effective"}, None))

    def test_the_declared_field_is_followed_instead_of_guessing_value1(self):
        value = record()
        for row in value["levelProgression"]:
            row["value1"] = 931
        result = effect(value, catalog_id=7420, level=17)
        self.assertEqual((result["candidate"]["binding"]["field"], result["candidate"]["value"]["cell"]["text"]),
                         ("value7", "113/7"))

    def test_full_reference_render_and_binding_arity_must_match_exactly(self):
        for change in ("first_line", "punctuation", "extra_token", "extra_binding", "missing_field", "wrong_key"):
            with self.subTest(change=change):
                value = record()
                if change == "first_line":
                    value["english"]["description"] = value["english"]["description"].replace("hit enemies", "hit a target")
                elif change == "punctuation":
                    value["english"]["description"] += "."
                elif change == "extra_token":
                    value["english"]["templateDescription"] += " #"
                elif change == "extra_binding":
                    value["descriptionBindings"]["bindings"].append("value1")
                elif change == "missing_field":
                    del value["levelProgression"][0]["value7"]
                else:
                    value["descriptionBindings"]["template"] = "name"
                result = effect(value, catalog_id=7420, level=17)
                self.assertEqual((result["status"], result["candidate"], len(result["gaps"])), ("unresolved", None, 1))

    def test_missing_or_duplicate_observed_and_reference_rows_have_no_fallback(self):
        for change, expected in (("selected_missing", "observed_level_missing"), ("selected_duplicate", "observed_level_ambiguous"),
                                  ("reference_missing", "reference_level_missing"), ("reference_duplicate", "reference_level_ambiguous")):
            with self.subTest(change=change):
                value = record()
                index = 1 if change.startswith("selected") else 0
                if change.endswith("missing"):
                    value["levelProgression"].pop(index)
                else:
                    value["levelProgression"].append(copy.deepcopy(value["levelProgression"][index]))
                self.assertEqual(effect(value, catalog_id=7420, level=17)["reason"], expected)

    def test_identity_and_category_are_exact_and_the_name_is_never_a_binding(self):
        for field, invalid in (("tlidbId", 7401), ("tlidbId", True), ("id", None), ("id", "private identity"),
                               ("category", "Noble_Support")):
            with self.subTest(field=field):
                value = record()
                value[field] = invalid
                value["english"]["name"] = "Critical Strike Damage Increase"
                self.assertIsNone(effect(value, catalog_id=7420, level=17)["candidate"])
        self.assertEqual(effect(record(), catalog_id=7421, level=17)["reason"], "unsupported_catalog_id")

    def test_only_the_whole_demonstrated_template_identifies_the_hit_only_role(self):
        for template in ("+#% Critical Strike Damage", "+#% additional Hit Damage for the supported skill",
                         record()["english"]["templateDescription"] + " ", record()["english"]["templateDescription"].replace("\n", "\r\n")):
            with self.subTest(template=template):
                value = record()
                value["english"]["templateDescription"] = template
                self.assertEqual(effect(value, catalog_id=7420, level=17)["reason"], "template_unbound")

    def test_float_cells_require_exact_json_loading_instead_of_claiming_source_lexemes(self):
        for index, reason in ((0, "reference_cell_requires_exact_number"), (1, "observed_cell_requires_exact_number")):
            with self.subTest(index=index):
                value = record()
                value["levelProgression"][index]["value7"] = 17.375
                self.assertEqual((effect(value, catalog_id=7420, level=17)["reason"],
                                  effect(value, catalog_id=7420, level=17)["candidate"]), (reason, None))

    def test_invalid_cells_are_not_evaluated_rounded_or_coerced(self):
        for invalid in (True, None, {}, [], "1/0", "1+2", " 7.3 ", "1e99999", "1" * 13,
                        "0." + "1" * 10, "-1", "٣٤", Decimal("1E-999999")):
            with self.subTest(invalid=invalid):
                value = record()
                value["levelProgression"][1]["value7"] = invalid
                self.assertEqual(effect(value, catalog_id=7420, level=17)["reason"], "observed_cell_invalid")

    def test_a_repeating_reference_fraction_cannot_be_rounded_to_force_the_description(self):
        value = record()
        value["levelProgression"][0]["value7"] = "1/3"
        value["english"]["description"] = value["english"]["description"].replace("12.5", "0.333")
        self.assertEqual(effect(value, catalog_id=7420, level=17)["reason"], "reference_render_unresolved")

    def test_same_reference_and_observed_level_uses_the_single_actual_row(self):
        result = effect(record(), catalog_id=7420, level=3)
        self.assertEqual(result["candidate"]["value"]["fraction"], {"numerator": 1, "denominator": 8})

    def test_exact_decimal_parsing_is_independent_of_caller_context(self):
        value = record()
        value["levelProgression"][1]["value7"] = Decimal("17.37500")
        with localcontext() as context:
            context.prec = 1
            result = effect(value, catalog_id=7420, level=17)
        self.assertEqual((result["candidate"]["value"]["cell"], result["candidate"]["value"]["fraction"]),
                         ({"text": "17.37500", "kind": "decimal"}, {"numerator": 139, "denominator": 800}))

    def test_owner_activation_and_critical_stat_readiness_are_never_inferred(self):
        result = effect(record(), catalog_id=7420, level=17)
        self.assertEqual((result["candidate"]["owner"], result["candidate"]["target"], result["activation"],
                          result["eligibility"], result["additional_group_identity"], result["arithmetic_ready"],
                          result["runtime_verified"], result["identity_verified"], result["import_complete"]),
                         ("supported_skill", "supported_skill_critical_hit", "unknown", "unverified", "unresolved",
                          False, False, False, False))

    def test_summary_revalidates_the_complete_candidate_proof_and_drops_unknown_fields(self):
        expected = effect(record(), catalog_id=7420, level=17)
        value = copy.deepcopy(expected)
        for row in (value, value["identity"], value["lookup"], value["candidate"], value["candidate"]["value"],
                    value["candidate"]["value"]["cell"], value["candidate"]["binding"], value["candidate"]["value"]["fraction"]):
            row["opaque"] = "PRIVATE-ORDINARY-CANARY"
        self.assertEqual(summary(value), expected)

    def test_canonical_false_claims_cell_math_render_and_semantics_cannot_be_forged(self):
        for path, invalid in ((("arithmetic_ready",), True), (("runtime_verified",), 0), (("effective_level",), 17),
                               (("activation",), "active"), (("candidate", "kind"), "full_critical_multiplier"),
                               (("candidate", "value", "fraction", "numerator"), 117),
                               (("candidate", "binding", "line"), True),
                               (("candidate", "binding", "reference_description"), "PRIVATE-ORDINARY-CANARY")):
            with self.subTest(path=path):
                value = effect(record(), catalog_id=7420, level=17)
                node = value
                for field in path[:-1]:
                    node = node[field]
                node[path[-1]] = invalid
                with self.assertRaisesRegex(ValueError, "^Ordinary support contains an invalid catalog candidate contract$"):
                    summary(value)

    def test_results_are_detached_and_do_not_copy_raw_private_payloads(self):
        value = record()
        value["native"] = {"account": "PRIVATE-ORDINARY-CANARY"}
        original = copy.deepcopy(value)
        result = effect(value, catalog_id=7420, level=17)
        result["candidate"]["binding"]["reference_cell"]["text"] = "29"
        self.assertEqual((value, "PRIVATE-ORDINARY-CANARY" in json.dumps(result)), (original, False))

    def test_malformed_canonical_binding_fields_fail_with_the_fixed_contract_error(self):
        for invalid in ([], {}, None, True, 7, "PRIVATE-ORDINARY-CANARY"):
            with self.subTest(invalid=invalid):
                value = effect(record(), catalog_id=7420, level=17)
                value["candidate"]["binding"]["field"] = invalid
                with self.assertRaisesRegex(ValueError, "^Ordinary support contains an invalid catalog candidate contract$"):
                    summary(value)

    def test_unresolved_results_roundtrip_without_becoming_empty_successes(self):
        value = record()
        value["levelProgression"] = []
        result = effect(value, catalog_id=7420, level=17)
        self.assertEqual((summary(result), result["status"], result["candidate"]), (result, "unresolved", None))

    def test_invalid_top_arguments_and_excessive_or_nonjson_inputs_fail_privately(self):
        for level in (True, 0, -1, 1001, 17.0, "17"):
            with self.subTest(level=level), self.assertRaisesRegex(ValueError, "^Ordinary support contains an invalid catalog candidate contract$"):
                effect(record(), catalog_id=7420, level=level)
        for invalid in (None, [], {"opaque": "\ud800"}, {"opaque": [None] * 4097}):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                effect(invalid, catalog_id=7420, level=17)
