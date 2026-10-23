import copy
import unittest
from decimal import Inexact, Rounded, localcontext

from damage_lab.supportmedium import project
from test_supportinventory import medium_document


def medium():
    """One fictional producer subtree with separate distance and creation-time slots."""
    return medium_document()["members"][1]["effects"]["mediumTrigger"]


class SupportMediumTests(unittest.TestCase):
    """Validate declared catalog candidates without deriving rates or confirming the source join."""

    def test_a_bound_creation_interval_is_text_with_a_declared_catalog_claim(self):
        result = project(medium(), base_id=8030, category="Activation_Medium",
                         prefix={"status": "supplied", "rows": 1, "null_rows": 0}, omissions=[])
        self.assertEqual((result["line"]["slots"], result["line"]["catalog_claims"],
                          result["line"]["rate_derived"], result["line"]["tier_meaning"]), ([
            {"slot": 1, "quantity": "tangle_count_radius", "unit": "metre", "exact": "10",
             "range": {"min": "10", "max": "10"}},
            {"slot": 2, "quantity": "creation_trigger_interval", "unit": "second", "exact": "0.4",
             "range": {"min": "0.4", "max": "0.4"}},
        ], "producer_reported", False, "catalog_line_tier"))

    def test_a_canonical_round_trip_and_nested_source_mutation_are_independent(self):
        raw = medium()
        result = project(raw, base_id=8030, category="Activation_Medium",
                         prefix={"status": "supplied", "rows": 1, "null_rows": 0}, omissions=[])
        again = project(result, base_id=8030, category="Activation_Medium",
                        prefix={"status": "supplied", "rows": 1, "null_rows": 0}, omissions=[], canonical=True)
        expected = copy.deepcopy(result)
        raw["line"]["slots"][1]["exact"] = "PRIVATE-MEDIUM-CANARY"
        result["line"]["slots"][1]["range"]["max"] = "99"
        self.assertEqual(again, expected)

    def test_new_units_flags_and_extra_source_claims_are_refused(self):
        cases = (("unit", "millisecond"), ("quantity", "emission_interval"), ("slot", True),
                 ("exact", 0.4), ("exact", "1e2"), ("exact", "0.5"))
        for key, value in cases:
            with self.subTest(key=key, value=value):
                raw = medium()
                raw["line"]["slots"][1][key] = value
                with self.assertRaises(ValueError):
                    project(raw, base_id=8030, category="Activation_Medium",
                            prefix={"status": "supplied", "rows": 1, "null_rows": 0}, omissions=[])
        for key, value in (("rateDerived", 0), ("runtime", "verified"), ("catalog_claims", "verified"),
                           ("fraction", "0.004"), ("unit", "percent")):
            with self.subTest(key=key):
                raw = medium()
                raw["line"][key] = value
                with self.assertRaises(ValueError):
                    project(raw, base_id=8030, category="Activation_Medium",
                            prefix={"status": "supplied", "rows": 1, "null_rows": 0}, omissions=[])

    def test_a_count_preserving_omission_collision_cannot_reuse_the_bound_path(self):
        with self.assertRaises(ValueError):
            project(medium(), base_id=8030, category="Activation_Medium",
                    prefix={"status": "supplied", "rows": 2, "null_rows": 0}, omissions=[
                        {"origin": "native_prefix_row", "path": "prefix[0]", "reason": "unsupported_template"}])

    def test_a_declared_null_count_does_not_reinterpret_a_bound_path(self):
        raw = medium()
        raw["paths"] = ["prefix[1]"]
        raw["line"]["path"] = "prefix[1]"
        result = project(raw, base_id=8030, category="Activation_Medium",
                         prefix={"status": "supplied", "rows": 3, "null_rows": 2}, omissions=[])
        self.assertEqual(result["paths"], ["prefix[1]"])

    def test_an_unresolved_peer_requires_the_held_row_and_both_paths(self):
        raw = medium()
        raw.update(status="gap", reason="line_unresolved_rows_present", paths=["prefix[0]", "prefix[1]"], line=None)
        result = project(raw, base_id=8030, category="Activation_Medium",
                         prefix={"status": "supplied", "rows": 2, "null_rows": 0}, omissions=[
                             {"origin": "native_prefix_row", "path": "prefix[0]", "reason": "unresolved_prefix_peer"},
                             {"origin": "native_prefix_row", "path": "prefix[1]", "reason": "no_exact_definition"}])
        self.assertEqual((result["status"], result["line"], result["paths"]),
                         ("gap", None, ["prefix[0]", "prefix[1]"]))

    def test_an_absent_prefix_keeps_its_unknown_omissions_context(self):
        raw = medium()
        raw.update(status="gap", reason="prefix_absent", paths=[], line=None)
        self.assertEqual(project(raw, base_id=8030, category="Activation_Medium",
                                 prefix={"status": "absent", "rows": None, "null_rows": None}, omissions=None)["reason"],
                         "prefix_absent")

    def test_a_catalog_line_tier_is_not_reconstructed_from_the_native_id_suffix(self):
        raw = medium()
        raw["line"]["tier"] = 12
        result = project(raw, base_id=8030, category="Activation_Medium",
                         prefix={"status": "supplied", "rows": 1, "null_rows": 0}, omissions=[])
        self.assertEqual((result["line"]["tier"], result["line"]["native_id"]), (12, "771032771"))

    def test_exact_slot_comparison_ignores_the_callers_decimal_precision(self):
        with localcontext() as context:
            context.prec = 1
            context.traps[Inexact] = True
            context.traps[Rounded] = True
            raw = medium()
            raw["line"]["slots"][1].update(exact="0.41275", range={"min": "0.41274", "max": "0.41276"})
            result = project(raw, base_id=8030, category="Activation_Medium",
                             prefix={"status": "supplied", "rows": 1, "null_rows": 0}, omissions=[])
        self.assertEqual(result["line"]["slots"][1]["exact"], "0.41275")
