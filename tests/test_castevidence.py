"""Check fictional cast evidence without assigning rolls to effects or computing speed."""

import copy
from decimal import localcontext
import json
import unittest

from damage_lab.castevidence import project, summary


def document(*, composite=True):
    """Keep own source values independent of two unresolved catalog specifications."""
    return {
        "kind": "cast_input_candidate", "binding": "exact_native_affix_definition",
        "definition": {"catalog": "gear/one_handed/wand/master", "id": "synthetic-cast-row",
                       "tier": "4+", "tierId": "synthetic-cast-tier", "templateSource": "descriptionTemplate"},
        "template": ("+#% Cast Speed\n+#% Minion Cast Speed" if composite else
                     "Has Hasten\n+#% Attack Speed, Cast Speed, and Movement Speed when having Hasten"),
        "specs": [{"index": index, "minExact": "7.1250", "maxExact": "41.625", "unit": "%"}
                  for index in range(2 if composite else 1)],
        "ownValues": [{"index": 0, "exact": "17.8750", "source": "DynArgs[0]"}],
        "nativeConditions": {"Condition": "empty", "Filter": "empty", "Behavior": "empty"},
        "templateCondition": "none" if composite else "hasten", "valueRole": "unresolved",
        "activation": "unknown", "arithmeticReady": False,
    }


class CastEvidenceTests(unittest.TestCase):
    """Keep exact diagnostic bindings distinct from resolved cast inputs and runtime activation."""

    def test_a_composite_keeps_two_specs_and_one_own_roll_without_inventing_two_effect_values(self):
        result = project(document())
        self.assertEqual((len(result["specs"]), result["own_values"], result["value_role"],
                          result["arithmetic_ready"], set(result)),
            (2, [{"index": 0, "exact": "17.8750", "source": "DynArgs[0]"}], "unresolved", False,
             {"kind", "binding", "definition", "template", "specs", "own_values", "native_conditions",
              "template_condition", "value_role", "activation", "arithmetic_ready"}))

    def test_hasten_remains_unknown_when_every_native_condition_array_is_empty(self):
        result = project(document(composite=False))
        self.assertEqual((result["template_condition"], result["activation"], result["native_conditions"],
                          len(result["specs"]), len(result["own_values"])),
                         ("hasten", "unknown", {"condition": "empty", "filter": "empty", "behavior": "empty"}, 1, 1))

    def test_exact_numeric_lexemes_and_definition_coordinates_are_preserved(self):
        result = project(document())
        self.assertEqual((result["specs"][0], result["definition"]),
            ({"index": 0, "min_exact": "7.1250", "max_exact": "41.625", "unit": "%"},
             {"catalog": "gear/one_handed/wand/master", "id": "synthetic-cast-row", "tier": "4+",
              "tier_id": "synthetic-cast-tier", "template_source": "descriptionTemplate"}))

    def test_independent_spec_ranges_do_not_assign_the_single_roll_to_a_player_or_minion(self):
        value = document()
        value["specs"][1].update(minExact="9.5", maxExact="31.75")
        result = project(value)
        self.assertEqual((result["specs"][1]["min_exact"], result["own_values"], result["value_role"]),
                         ("9.5", [{"index": 0, "exact": "17.8750", "source": "DynArgs[0]"}], "unresolved"))

    def test_unknown_properties_are_dropped_at_each_known_boundary(self):
        value = document()
        for row in (value, value["definition"], value["specs"][0], value["ownValues"][0], value["nativeConditions"]):
            row["opaque"] = {"account": "PRIVATE-CAST-CANARY"}
        self.assertEqual(project(value), project(document()))

    def test_summary_revalidates_canonical_fields_without_retaining_unknown_extras(self):
        value = project(document())
        for row in (value, value["definition"], value["specs"][0], value["own_values"][0], value["native_conditions"]):
            row["opaque"] = "PRIVATE-CAST-CANARY"
        self.assertEqual(summary(value), project(document()))

    def test_summary_does_not_trust_forged_canonical_claims_or_native_sources(self):
        for path, invalid in ((("arithmetic_ready",), 0), (("value_role",), "cast_speed"),
                               (("template_condition",), "hasten"), (("definition", "template_source"), "Simple"),
                               (("own_values", 0, "source"), "DynArgs[1]"), (("specs", 1, "index"), True)):
            with self.subTest(path=path):
                value = project(document())
                node = value
                for field in path[:-1]:
                    node = node[field]
                node[path[-1]] = invalid
                with self.assertRaisesRegex(ValueError, "^Cast evidence contains an invalid diagnostic contract$"):
                    summary(value)

    def test_unknown_native_condition_fields_and_nullable_tier_do_not_fabricate_defaults(self):
        value = document()
        value["nativeConditions"].update(Condition="missing", Filter="invalid", Behavior="present")
        value["definition"]["tier"] = None
        result = project(value)
        self.assertEqual((result["native_conditions"], result["definition"]["tier"], result["activation"]),
                         ({"condition": "missing", "filter": "invalid", "behavior": "present"}, None, "unknown"))

    def test_results_are_deterministic_detached_and_independent_of_caller_decimal_precision(self):
        value = document()
        expected = project(copy.deepcopy(value))
        with localcontext() as context:
            context.prec = 1
            result = summary(project(value))
        unchanged = result == expected
        value["ownValues"][0]["exact"] = "27.125"
        result["specs"][0]["min_exact"] = "8.5"
        self.assertEqual((unchanged, result["own_values"][0]["exact"], value["specs"][0]["minExact"]),
                         (True, "17.8750", "7.1250"))

    def test_known_containers_and_required_fields_cannot_be_missing_or_replaced(self):
        for field in ("definition", "specs", "ownValues", "nativeConditions", "template"):
            for replacement in (None, True, [], "PRIVATE-CAST-CANARY"):
                with self.subTest(field=field, replacement=replacement):
                    value = document()
                    value[field] = replacement
                    with self.assertRaisesRegex(ValueError, "^Cast evidence contains an invalid diagnostic contract$"):
                        project(value)
        value = document()
        del value["valueRole"]
        with self.assertRaises(ValueError):
            project(value)

    def test_numeric_values_require_bounded_exact_decimal_strings(self):
        for field, location in (("minExact", "specs"), ("maxExact", "specs"), ("exact", "ownValues")):
            for invalid in (True, 1, 1.5, "", "NaN", "Infinity", "1e-999999", "+17.875", "17%",
                            "1" * 13, "0." + "1" * 10, "１７.８７５"):
                with self.subTest(field=field, invalid=invalid):
                    value = document()
                    value[location][0][field] = invalid
                    with self.assertRaises(ValueError):
                        project(value)

    def test_specs_cannot_have_inverted_ranges_or_an_inferred_unit(self):
        for field, invalid in (("minExact", "77.25"), ("unit", None), ("unit", "percent"), ("unit", "s")):
            with self.subTest(field=field, invalid=invalid):
                value = document()
                value["specs"][0][field] = invalid
                with self.assertRaises(ValueError):
                    project(value)

    def test_indices_sources_and_cardinality_cannot_duplicate_or_reassign_own_values(self):
        for change in ("duplicate_spec", "reorder", "bool", "float", "own_index", "source", "two_rolls", "no_roll", "one_spec"):
            with self.subTest(change=change):
                value = document()
                if change == "duplicate_spec":
                    value["specs"][1]["index"] = 0
                elif change == "reorder":
                    value["specs"].reverse()
                elif change in ("bool", "float"):
                    value["specs"][0]["index"] = False if change == "bool" else 0.0
                elif change == "own_index":
                    value["ownValues"][0]["index"] = 1
                elif change == "source":
                    value["ownValues"][0]["source"] = "DynArgs[1]"
                elif change == "two_rolls":
                    value["ownValues"].append({"index": 1, "exact": "19.375", "source": "DynArgs[1]"})
                elif change == "no_roll":
                    value["ownValues"] = []
                else:
                    value["specs"].pop()
                with self.assertRaises(ValueError):
                    project(value)

    def test_only_the_two_full_templates_and_their_literal_conditions_are_supported(self):
        for field, invalid in (("template", "+#% Cast Speed"), ("template", document()["template"] + " "),
                               ("template", document()["template"].replace("\n", "\r\n")),
                               ("templateCondition", "hasten"), ("templateCondition", None)):
            with self.subTest(field=field, invalid=invalid):
                value = document()
                value[field] = invalid
                with self.assertRaises(ValueError):
                    project(value)

    def test_claims_and_condition_statuses_cannot_be_promoted_or_coerced(self):
        for field, invalid in (("kind", "speed_modifier"), ("binding", "name_match"), ("valueRole", "player_cast"),
                               ("activation", "active"), ("arithmeticReady", 0), ("arithmeticReady", True)):
            with self.subTest(field=field, invalid=invalid):
                value = document()
                value[field] = invalid
                with self.assertRaises(ValueError):
                    project(value)
        for invalid in (None, [], True, "active", "unknown"):
            with self.subTest(invalid=invalid):
                value = document()
                value["nativeConditions"]["Condition"] = invalid
                with self.assertRaises(ValueError):
                    project(value)

    def test_definition_coordinates_require_safe_base_catalog_tier_and_template_source(self):
        for field, invalid in (("catalog", "../private.json"), ("catalog", "legendaries/wand/master"),
                               ("catalog", "gear/wand/i18n/en"), ("id", ""), ("id", "raw id"),
                               ("tier", 4), ("tier", "Tier 4"), ("tierId", None),
                               ("templateSource", "Simple"), ("templateSource", "corrodedDescriptionTemplate")):
            with self.subTest(field=field, invalid=invalid):
                value = document()
                value["definition"][field] = invalid
                with self.assertRaises(ValueError):
                    project(value)

    def test_bounded_json_shape_rejects_cycles_excessive_containers_depth_and_invalid_unicode(self):
        for change in ("cycle", "width", "depth", "text", "unicode", "nonfinite"):
            with self.subTest(change=change):
                value = document()
                if change == "cycle":
                    value["opaque"] = value
                elif change == "width":
                    value["opaque"] = [None] * 4097
                elif change == "depth":
                    node = value
                    for _ in range(65):
                        node["opaque"] = {}
                        node = node["opaque"]
                else:
                    value["opaque"] = "x" * 4097 if change == "text" else "\ud800" if change == "unicode" else float("nan")
                with self.assertRaisesRegex(ValueError, "^Cast evidence contains an invalid diagnostic contract$"):
                    project(value)

    def test_the_safe_projection_has_no_raw_private_or_arithmetic_fields(self):
        value = document()
        value.update(Simple="PRIVATE-CAST-CANARY", raw={"castRate": 173, "account": "PRIVATE-CAST-CANARY"})
        self.assertFalse(any(text in json.dumps(project(value)) for text in ("PRIVATE-CAST-CANARY", "castRate", '"family"', '"fraction"')))
