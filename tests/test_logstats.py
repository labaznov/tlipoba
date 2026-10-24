"""Synthetic panel-log observations without player captures."""

import unittest
from copy import deepcopy
from decimal import Inexact, InvalidOperation, Rounded, localcontext


def document():
    attributes = []
    for index, (identity, name, tokens) in enumerate((
        (10103, "Spell DPS", ["3217.4"]),
        (11800, "Total Spell Damage", ["83.125", "137.625"]),
        (21000, "Spells cast per second", ["4.8125"]),
        (21212, "Spell Critical Strike Chance", ["31.75"]),
        (21400, "Spell Critical Strike Damage", ["287.5"]),
        (21714, "Max Tangle Quantity", ["5"]),
        (21715, "Additional Tangle Attach Quantity", ["3"]),
        (11000, "Cold Penetration", ["17.25"]),
    )):
        attributes.append({"id": str(identity), "name": name, "status": "resolved",
                           "values": [float(token) for token in tokens],
                           "raw_values": tokens, "line_numbers": [11 + index * 2, 12 + index * 2]})
    return {"format": "tli-panel-log-v1", "source": {"sha256": "a" * 64},
            "cohorts": [{"timestamp": "2026-10-19T13:17:38.731Z", "frame": 731,
                         "attributes": attributes, "issues": [], "status": "resolved"}], "gaps": []}


class LogstatsTests(unittest.TestCase):
    """Verify exact ID bindings and conservative state selection."""

    def test_displayed_double_damage_chance_cannot_exceed_one_hundred_percent(self):
        from damage_lab.logstats import select

        payload = document()
        payload["cohorts"][0]["attributes"].append({
            "id": "21401", "name": "Double Damage Chance", "status": "resolved",
            "values": [100.375], "raw_values": ["100.375"], "line_numbers": [55, 56],
        })
        with self.assertRaisesRegex(ValueError, "double damage chance"):
            select(payload, 3217)

    def test_absent_displayed_double_damage_chance_does_not_invent_zero(self):
        from damage_lab.logstats import select

        self.assertNotIn("double_damage_chance", [row["key"] for row in select(document(), 3217)["rows"]])

    def test_observed_double_damage_zero_keeps_its_printed_token(self):
        from damage_lab.logstats import select

        payload = document()
        payload["cohorts"][0]["attributes"].append({
            "id": "21401", "name": "Double Damage Chance", "status": "resolved",
            "values": [0], "raw_values": ["0.000"], "line_numbers": [55, 56],
        })
        self.assertEqual([(row["value"], row["source"]["raw_value"]) for row in select(payload, 3217)["rows"]
                          if row["key"] == "double_damage_chance"], [(0, "0.000")])

    def test_displayed_double_damage_chance_accepts_exactly_one_hundred_percent(self):
        from damage_lab.logstats import select

        payload = document()
        payload["cohorts"][0]["attributes"].append({
            "id": "21401", "name": "Double Damage Chance", "status": "resolved",
            "values": [100], "raw_values": ["100.000"], "line_numbers": [55, 56],
        })
        self.assertEqual([(row["value"], row["source"]["raw_value"]) for row in select(payload, 3217)["rows"]
                          if row["key"] == "double_damage_chance"], [(1, "100.000")])

    def test_displayed_double_damage_chance_requires_its_exact_label_and_one_nonnegative_value(self):
        from damage_lab.logstats import select

        for name, tokens in (("Cold Double Damage Chance", ["37.125"]),
                             ("Double Damage Chance", ["37.125", "43"]),
                             ("Double Damage Chance", ["-7.375"])):
            payload = document()
            payload["cohorts"][0]["attributes"].append({
                "id": "21401", "name": name, "status": "resolved", "values": [float(token) for token in tokens],
                "raw_values": tokens, "line_numbers": [55, 56],
            })
            with self.subTest(name=name, tokens=tokens), self.assertRaises(ValueError):
                select(payload, 3217)

    def test_displayed_double_damage_chance_preserves_the_exact_upper_bound_under_decimal_traps(self):
        from damage_lab.logstats import select

        payload = document()
        payload["cohorts"][0]["attributes"].append({
            "id": "21401", "name": "Double Damage Chance", "status": "resolved",
            "values": [100.0], "raw_values": ["100.000000000000000000000000001"], "line_numbers": [55, 56],
        })
        with localcontext() as context:
            context.prec = 2
            context.traps[Inexact] = context.traps[Rounded] = True
            with self.assertRaisesRegex(ValueError, "double damage chance"):
                select(payload, 3217)

    def test_normalization_is_independent_of_caller_decimal_precision_and_traps(self):
        from damage_lab.logstats import select

        expected = select(document(), 3217)
        with localcontext() as context:
            context.prec, context.Emax, context.Emin = 3, 2, -2
            context.traps[Inexact] = context.traps[Rounded] = True
            result = select(document(), 3217)
        self.assertEqual(result, expected)

    def test_chance_above_one_hundred_percent_cannot_round_into_the_valid_domain(self):
        from damage_lab.logstats import select

        payload = document()
        payload["cohorts"][0]["attributes"][3].update(values=[100.1], raw_values=["100.1"])
        with localcontext() as context:
            context.prec = 1
            with self.assertRaisesRegex(ValueError, "critical chance"):
                select(payload, 3217)

    def test_a_token_above_the_anchor_boundary_cannot_round_into_the_matching_window(self):
        from damage_lab.logstats import select

        payload = document()
        payload["cohorts"][0]["attributes"][0].update(values=[3217.5], raw_values=["3217.5000000000001"])
        with localcontext() as context:
            context.prec = 3
            with self.assertRaisesRegex(ValueError, "no cohort matching"):
                select(payload, 3217)

    def test_anchor_comparison_preserves_digits_beyond_the_default_decimal_precision(self):
        from damage_lab.logstats import select

        payload = document()
        payload["cohorts"][0]["attributes"][0].update(values=[0.5], raw_values=["0.50000000000000000000000000001"])
        with localcontext() as context:
            context.prec = 28
            with self.assertRaisesRegex(ValueError, "no cohort matching"):
                select(payload, 0)

    def test_chance_validation_preserves_digits_beyond_the_default_decimal_precision(self):
        from damage_lab.logstats import select

        payload = document()
        payload["cohorts"][0]["attributes"][3].update(values=[100.0], raw_values=["100.000000000000000000000000001"])
        with localcontext() as context:
            context.prec = 28
            with self.assertRaisesRegex(ValueError, "critical chance"):
                select(payload, 3217)

    def test_exact_anchor_half_boundaries_still_match(self):
        from damage_lab.logstats import select

        for token in ("3216.5", "3217.5", "3217.4999999999999"):
            payload = document()
            payload["cohorts"][0]["attributes"][0].update(values=[float(token)], raw_values=[token])
            with self.subTest(token=token), localcontext() as context:
                context.prec = 2
                self.assertEqual(select(payload, 3217)["summary"]["status"], "corroborated")

    def test_normalization_does_not_set_caller_decimal_flags(self):
        from damage_lab.logstats import select

        with localcontext() as context:
            context.prec = 3
            context.clear_flags()
            select(document(), 3217)
            self.assertFalse(any(context.flags.values()))

    def test_printed_tokens_do_not_claim_a_known_rounding_precision(self):
        from damage_lab.logstats import select

        self.assertEqual({row["precision"] for row in select(document(), 3217)["rows"]},
                         {"printed token; rounding unknown; corroborated; identity_verified=false"})

    def test_numeric_token_resource_bounds_are_checked_before_exact_arithmetic(self):
        from damage_lab.logstats import select

        for token in ("0" * 129, "0e999999999999999999", "0e-513"):
            payload = document()
            payload["cohorts"][0]["attributes"][3].update(values=[0], raw_values=[token])
            with self.subTest(token=token), self.assertRaises(ValueError):
                select(payload, 3217)

    def test_extreme_explicit_exponents_are_refused_without_changing_caller_flags(self):
        from damage_lab.logstats import select

        for token in ("0e" + "9" * 19, "1e" + "9" * 100):
            for trapped in (True, False):
                payload = document()
                payload["cohorts"][0]["attributes"][3].update(values=[0], raw_values=[token])
                with self.subTest(trapped=trapped, token=token), localcontext() as context:
                    context.traps[InvalidOperation] = trapped
                    context.clear_flags()
                    try:
                        select(payload, 3217)
                    except ValueError:
                        result = ("refused", any(context.flags.values()))
                    else:
                        result = ("accepted", any(context.flags.values()))
                    self.assertEqual(result, ("refused", False))

    def test_a_fractional_count_cannot_round_into_an_integer(self):
        from damage_lab.logstats import select

        payload = document()
        payload["cohorts"][0]["attributes"][5].update(values=[5.0], raw_values=["5.0000000000000000000001"])
        with localcontext() as context:
            context.prec = 3
            with self.assertRaisesRegex(ValueError, "integral counts"):
                select(payload, 3217)

    def test_canonical_integer_display_keeps_significant_trailing_zeros(self):
        from damage_lab.logstats import select

        payload = document()
        payload["cohorts"][0]["attributes"][2].update(values=[1e20], raw_values=["1e20"])
        self.assertEqual(next(row["display"] for row in select(payload, 3217)["rows"] if row["key"] == "cast_rate"),
                         "100000000000000000000 /s")

    def test_admitted_zero_tokens_reach_the_numeric_resource_boundaries(self):
        from damage_lab.logstats import select

        for token in ("0" * 128, "0e512", "0e-512"):
            payload = document()
            payload["cohorts"][0]["attributes"][3].update(values=[0], raw_values=[token])
            with self.subTest(token=token):
                self.assertEqual(next(row["value"] for row in select(payload, 3217)["rows"]
                                      if row["key"] == "crit_chance"), 0.0)

    def test_newer_unmatched_states_warn_that_the_selected_state_is_historical(self):
        from damage_lab.logstats import select

        payload = document()
        payload["cohorts"].append(deepcopy(payload["cohorts"][0]))
        payload["cohorts"][1]["timestamp"] = "2026-10-19T13:18:39.743Z"
        payload["cohorts"][1]["attributes"][0].update(values=[4759.2], raw_values=["4759.2"])
        self.assertIn("Newer panel states do not match the native Spell DPS anchor; "
                      "the selected historical state does not verify the current state",
                      select(payload, 3217)["issues"])

    def test_a_later_restored_matching_state_does_not_warn_about_older_changes(self):
        from damage_lab.logstats import select

        payload = document()
        payload["cohorts"].extend([deepcopy(payload["cohorts"][0]), deepcopy(payload["cohorts"][0])])
        payload["cohorts"][1]["timestamp"] = "2026-10-19T13:18:39.743Z"
        payload["cohorts"][1]["attributes"][0].update(values=[4759.2], raw_values=["4759.2"])
        payload["cohorts"][2]["timestamp"] = "2026-10-19T13:19:41.757Z"
        self.assertEqual(select(payload, 3217)["issues"], [])

    def test_a_newer_panel_without_spell_dps_does_not_claim_an_anchor_mismatch(self):
        from damage_lab.logstats import select

        payload = document()
        payload["cohorts"].append(deepcopy(payload["cohorts"][0]))
        payload["cohorts"][1]["timestamp"] = "2026-10-19T13:18:39.743Z"
        payload["cohorts"][1]["attributes"].pop(0)
        self.assertEqual(select(payload, 3217)["issues"], [])

    def test_optional_armor_penetration_is_normalized_from_the_exact_log_id(self):
        from damage_lab.logstats import select

        payload = document()
        payload["cohorts"][0]["attributes"].append({
            "id": "11201", "name": "Armor DMG Mitigation Penetration", "status": "resolved",
            "values": [7.375], "raw_values": ["7.375"], "line_numbers": [51, 52],
        })
        self.assertEqual(next(row["value"] for row in select(payload, 3217)["rows"]
                              if row["key"] == "armor_penetration"), 0.07375)

    def test_absent_armor_penetration_does_not_invent_a_zero(self):
        from damage_lab.logstats import select

        self.assertNotIn("armor_penetration", [row["key"] for row in select(document(), 3217)["rows"]])

    def test_optional_spell_burst_count_preserves_its_token_and_cohort_without_identity(self):
        from damage_lab.logstats import select

        payload = document()
        payload["cohorts"][0]["attributes"].append({
            "id": "21604", "name": "Max Spell Burst", "status": "resolved",
            "values": [3], "raw_values": ["3.000"], "line_numbers": [53, 54],
        })
        result = select(payload, 3217)
        row = next((row for row in result["rows"] if row["key"] == "max_spell_burst"), {})
        self.assertEqual((row.get("value"), row.get("unit"), row.get("source"),
                          result["summary"]["known"], result["summary"]["unknown_attributes"],
                          result["summary"]["identity_verified"]),
                         (3, "count", {"attr_id": "21604", "index": 1, "raw_value": "3.000",
                                       "raw_values": ["3.000"], "line_numbers": [53, 54],
                                       "timestamp": "2026-10-19T13:17:38.731Z", "frame": 731}, 10, 0, False))

    def test_observed_spell_burst_zero_is_preserved(self):
        from damage_lab.logstats import select

        payload = document()
        payload["cohorts"][0]["attributes"].append({
            "id": "21604", "name": "Max Spell Burst", "status": "resolved",
            "values": [0], "raw_values": ["0.00"], "line_numbers": [53, 54],
        })
        self.assertEqual([(row["value"], row["source"]["raw_value"]) for row in select(payload, 3217)["rows"]
                          if row["key"] == "max_spell_burst"], [(0, "0.00")])

    def test_absent_spell_burst_count_does_not_invent_zero(self):
        from damage_lab.logstats import select

        self.assertNotIn("max_spell_burst", [row["key"] for row in select(document(), 3217)["rows"]])

    def test_optional_spell_burst_requires_its_exact_label_and_one_integral_nonnegative_value(self):
        from damage_lab.logstats import select

        for name, tokens in (("Spell Burst", ["3"]), ("Max Spell Burst", ["3", "7"]),
                             ("Max Spell Burst", ["2.75"]), ("Max Spell Burst", ["-3"]),
                             ("Max Spell Burst", ["nan"])):
            payload = document()
            payload["cohorts"][0]["attributes"].append({
                "id": "21604", "name": name, "status": "resolved", "values": [float(token) for token in tokens],
                "raw_values": tokens, "line_numbers": [53, 54],
            })
            with self.subTest(name=name, tokens=tokens), self.assertRaises(ValueError):
                select(payload, 3217)

    def test_optional_known_armor_field_requires_its_exact_label_and_cardinality(self):
        from damage_lab.logstats import select

        for name, tokens in (("Armor", ["7.375"]), ("Armor DMG Mitigation Penetration", ["7.375", "8"]),
                             ("Armor DMG Mitigation Penetration", ["-7.375"])):
            payload = document()
            payload["cohorts"][0]["attributes"].append({
                "id": "11201", "name": name, "status": "resolved", "values": [float(token) for token in tokens],
                "raw_values": tokens, "line_numbers": [51, 52],
            })
            with self.subTest(name=name, tokens=tokens), self.assertRaises(ValueError):
                select(payload, 3217)

    def test_optional_known_armor_field_is_counted_as_named_instead_of_unknown(self):
        from damage_lab.logstats import select

        payload = document()
        payload["cohorts"][0]["attributes"].append({
            "id": "11201", "name": "Armor DMG Mitigation Penetration", "status": "resolved",
            "values": [7.375], "raw_values": ["7.375"], "line_numbers": [51, 52],
        })
        self.assertEqual((select(payload, 3217)["summary"]["known"],
                          select(payload, 3217)["summary"]["unknown_attributes"]), (10, 0))

    def test_percent_tokens_become_exact_fraction_with_log_provenance(self):
        from damage_lab.logstats import select

        self.assertEqual(next(row for row in select(document(), 3217)["rows"]
                              if row["key"] == "crit_chance"), {
            "key": "crit_chance", "label": "Spell Critical Strike Chance",
            "value": 0.3175, "display": "31.75%", "unit": "fraction",
            "precision": "printed token; rounding unknown; corroborated; identity_verified=false",
            "source": {"attr_id": "21212", "index": 1, "raw_value": "31.75", "raw_values": ["31.75"],
                       "timestamp": "2026-10-19T13:17:38.731Z", "frame": 731,
                       "line_numbers": [17, 18]},
        })

    def test_native_anchor_selects_a_matching_cohort_instead_of_the_first(self):
        from damage_lab.logstats import select

        payload = document()
        payload["cohorts"].append(deepcopy(payload["cohorts"][0]))
        payload["cohorts"][0]["attributes"][0].update(values=[7189.2], raw_values=["7189.2"])
        payload["cohorts"][1]["frame"] = 739
        self.assertEqual(select(payload, 3217)["summary"]["cohort"]["frame"], 739)

    def test_matching_states_that_differ_only_in_unknown_attributes_are_ambiguous(self):
        from damage_lab.logstats import select

        payload = document()
        payload["cohorts"][0]["attributes"].append({"id": "98765", "name": "Unmapped field", "status": "resolved",
                                                  "values": [13], "raw_values": ["13"], "line_numbers": [51, 52]})
        payload["cohorts"].append(deepcopy(payload["cohorts"][0]))
        payload["cohorts"][1]["attributes"][-1].update(values=[17], raw_values=["17"])
        with self.assertRaisesRegex(ValueError, "ambiguous"):
            select(payload, 3217)

    def test_identical_states_select_the_latest_timestamp_independent_of_input_order(self):
        from damage_lab.logstats import select

        payload = document()
        payload["cohorts"].append(deepcopy(payload["cohorts"][0]))
        payload["cohorts"][1].update(timestamp="2026-10-20T11:07:38.113Z", frame=19)
        payload["cohorts"][1]["attributes"].reverse()
        self.assertEqual(select(payload, 3217)["summary"]["cohort"],
                         {"timestamp": "2026-10-20T11:07:38.113Z", "frame": 19})

    def test_known_identity_requires_the_exact_label_and_cardinality(self):
        from damage_lab.logstats import select

        for changes in ({"name": "Attack DPS"}, {"name": 10103}, {"id": True},
                        {"id": 10103}, {"values": [3217.4, 17], "raw_values": ["3217.4", "17"]}):
            payload = document()
            payload["cohorts"][0]["attributes"][0].update(changes)
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                select(payload, 3217)

    def test_raw_numeric_tokens_must_match_finite_json_numbers(self):
        from damage_lab.logstats import select

        for number, token in ((True, "1"), ("3217.4", "3217.4"), (float("inf"), "1e999"),
                              (float("nan"), "NaN"), (3217.4, "3217.3"), (3217.4, 3217.4),
                              (3217.4, "3.2174K"), (3217.4, " 3217.4 "), (3217.4, "__import__('os')")):
            payload = document()
            payload["cohorts"][0]["attributes"][0].update(values=[number], raw_values=[token])
            with self.subTest(number=number, token=token), self.assertRaises(ValueError):
                select(payload, 3217)

    def test_envelope_requires_format_hash_and_typed_cohort_metadata(self):
        from damage_lab.logstats import select

        for path, value in ((["format"], "other"), (["source", "sha256"], "z" * 64),
                            (["source", "sha256"], 19), (["gaps"], "none"),
                            (["cohorts", 0, "frame"], True), (["cohorts", 0, "frame"], "731"),
                            (["cohorts", 0, "timestamp"], "yesterday"),
                            (["cohorts", 0, "status"], "complete"),
                            (["cohorts", 0, "issues"], "fine")):
            payload = document()
            destination = payload
            for key in path[:-1]:
                destination = destination[key]
            destination[path[-1]] = value
            with self.subTest(path=path, value=value), self.assertRaises(ValueError):
                select(payload, 3217)

    def test_partial_unresolved_states_cannot_mask_a_complete_cohort(self):
        from damage_lab.logstats import select

        payload = document()
        payload["cohorts"].append(deepcopy(payload["cohorts"][0]))
        payload["cohorts"][1].update(timestamp="2026-10-20T11:07:38.113Z", status="partial",
                                     issues=["missing values"])
        payload["cohorts"][1]["attributes"][0].update(status="unresolved", values=None, raw_values=[])
        self.assertEqual(select(payload, 3217)["summary"]["cohort"]["timestamp"],
                         "2026-10-19T13:17:38.731Z")

    def test_resolved_cohorts_cannot_repeat_even_an_unknown_attribute_id(self):
        from damage_lab.logstats import select

        for identity in ("10103", "98765"):
            payload = document()
            attribute = deepcopy(payload["cohorts"][0]["attributes"][0])
            attribute["id"] = identity
            payload["cohorts"][0]["attributes"].extend([attribute, deepcopy(attribute)])
            with self.subTest(identity=identity), self.assertRaisesRegex(ValueError, "Duplicate"):
                select(payload, 3217)

    def test_matching_cohort_requires_all_nine_bound_observations(self):
        from damage_lab.logstats import select

        payload = document()
        payload["cohorts"][0]["attributes"].pop()
        with self.assertRaisesRegex(ValueError, "required"):
            select(payload, 3217)

    def test_known_observations_enforce_nonnegative_counts_chance_and_damage_ranges(self):
        from damage_lab.logstats import select

        for index, tokens in ((1, ["138", "137"]), (2, ["-1"]), (3, ["100.1"]),
                              (4, ["-3"]), (5, ["2.5"]), (6, ["-1"]), (7, ["-17"])):
            payload = document()
            payload["cohorts"][0]["attributes"][index].update(
                values=[float(token) for token in tokens], raw_values=tokens)
            with self.subTest(index=index, tokens=tokens), self.assertRaises(ValueError):
                select(payload, 3217)

    def test_native_anchor_must_be_an_explicit_nonnegative_integer(self):
        from damage_lab.logstats import select

        for anchor in (True, False, -1, 3217.0, 3217.4, "3217", None, float("inf")):
            with self.subTest(anchor=anchor), self.assertRaises(ValueError):
                select(document(), anchor)

    def test_summary_counts_unknown_attributes_without_exposing_raw_objects(self):
        from damage_lab.logstats import select

        payload = document()
        payload["cohorts"][0]["attributes"].append({"id": "98765", "name": "Unmapped field",
                                                  "status": "resolved", "values": [-17],
                                                  "raw_values": ["-17"], "line_numbers": [51, 52]})
        self.assertEqual(select(payload, 3217)["summary"], {
            "format": "tli-panel-log-v1", "status": "corroborated", "known": 9,
            "unknown_attributes": 1, "cohort": {"timestamp": "2026-10-19T13:17:38.731Z", "frame": 731},
            "identity_verified": False, "source_sha256": "a" * 64,
            "numeric_policy": {"printer_precision": "unknown", "stored_numbers": "binary64", "raw_tokens": "preserved",
                               "native_anchor": {"operator": "absolute_difference_lte", "tolerance": "0.5", "unit": "damage/s",
                                                 "meaning": "selection_heuristic", "rounding_verified": False}},
        })

    def test_resolved_attributes_require_typed_lists_status_and_ordered_source_lines(self):
        from damage_lab.logstats import select

        for changes in ({"status": "unresolved"}, {"values": None}, {"values": "3217.4"},
                        {"raw_values": "3217.4"}, {"line_numbers": [True, 12]},
                        {"line_numbers": [12, 11]}, {"line_numbers": []}, {"line_numbers": [11]}):
            payload = document()
            payload["cohorts"][0]["attributes"][0].update(changes)
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                select(payload, 3217)

    def test_cast_display_preserves_the_numeric_token_with_its_per_second_unit(self):
        from damage_lab.logstats import select

        self.assertEqual(next(row["display"] for row in select(document(), 3217)["rows"]
                              if row["key"] == "cast_rate"), "4.8125 /s")

    def test_equal_dual_critical_chances_preserve_both_tokens_and_use_the_first_index(self):
        from damage_lab.logstats import select

        payload = document()
        payload["cohorts"][0]["attributes"][3].update(values=[31.75, 31.75], raw_values=["31.75", "31.750"])
        self.assertEqual(next(row["source"] for row in select(payload, 3217)["rows"]
                              if row["key"] == "crit_chance"), {
            "attr_id": "21212", "index": 1, "raw_value": "31.75", "raw_values": ["31.75", "31.750"],
            "timestamp": "2026-10-19T13:17:38.731Z", "frame": 731, "line_numbers": [17, 18],
        })

    def test_unequal_dual_critical_chances_cannot_choose_an_unverified_index(self):
        from damage_lab.logstats import select

        payload = document()
        payload["cohorts"][0]["attributes"][3].update(values=[31.75, 37.25], raw_values=["31.75", "37.25"])
        with self.assertRaisesRegex(ValueError, "unknown dual crit chance semantics"):
            select(payload, 3217)

    def test_token_or_percent_conversion_cannot_silently_underflow_to_zero(self):
        from damage_lab.logstats import select

        for number, token in ((0, "1e-999"), (1e-322, "1e-322")):
            payload = document()
            payload["cohorts"][0]["attributes"][3].update(values=[number], raw_values=[token])
            with self.subTest(token=token), self.assertRaises(ValueError):
                select(payload, 3217)

    def test_display_agrees_with_float_storage_when_raw_tokens_have_extra_decimal_places(self):
        from damage_lab.logstats import select

        payload = document()
        for index, token in ((2, "4.8125000000000000001"), (3, "31.750000000000000001"),
                             (4, "287.50000000000000001")):
            payload["cohorts"][0]["attributes"][index].update(values=[float(token)], raw_values=[token])
        self.assertEqual({row["key"]: row["display"] for row in select(payload, 3217)["rows"]
                          if row["key"] in ("cast_rate", "crit_chance", "crit_multiplier")},
                         {"cast_rate": "4.8125 /s", "crit_chance": "31.75%", "crit_multiplier": "287.5%"})
