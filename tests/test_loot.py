import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from damage_lab import loot


def _run(source, target):
    return subprocess.run([sys.executable, "-X", "utf8", "-m", "damage_lab.loot",
                           "--input", str(source), "--output", str(target)],
                          cwd=Path(__file__).resolve().parents[1], capture_output=True,
                          text=True, encoding="utf-8", timeout=15)


class QuantityTests(unittest.TestCase):
    """Check expected base loot quantities from explicit modifier pools."""

    def test_quantity_combines_the_three_documented_pools(self):
        self.assertEqual(loot.quantity(
            3, ordinary=[0.25, 0.5], additional=[0.5, 1], typed=[0.25, 0.75],
            eligible={"general": True, "type": True},
        )["expected"], 31.5)

    def test_quantity_rejects_invalid_expected_inputs(self):
        for value in (-0.25, True, False, float("nan"), float("inf"), "2", None):
            with self.subTest(value=value), self.assertRaises(ValueError):
                loot.quantity(value, ordinary=[], additional=[], typed=[],
                              eligible={"general": True, "type": True})

    def test_quantity_requires_exact_boolean_eligibility_scopes(self):
        for value in (None, True, {}, {"general": True}, {"general": 1, "type": True},
                      {"general": True, "type": None}, {"general": True, "type": True, "rarity": True}):
            with self.subTest(value=value), self.assertRaises(ValueError):
                loot.quantity(7, ordinary=[], additional=[], typed=[], eligible=value)

    def test_quantity_validates_pools_even_when_they_are_ineligible(self):
        for key in ("ordinary", "additional", "typed"):
            for value in (None, {}, [True], [float("nan")], [float("inf")], [".2"], [-2]):
                pools = {"ordinary": [], "additional": [], "typed": [], key: value}
                with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                    loot.quantity(3, **pools, eligible={"general": False, "type": False})

    def test_quantity_rejects_unrepresentable_nonzero_results(self):
        for base, bonus in ((5e-324, -0.5), (1e308, 1)):
            with self.subTest(base=base), self.assertRaises(ValueError):
                loot.quantity(base, ordinary=[], additional=[bonus], typed=[],
                              eligible={"general": True, "type": True})

    def test_quantity_preserves_ignored_modifier_scopes_in_the_trace(self):
        result = loot.quantity(7.5, ordinary=[0.25], additional=[0.75], typed=[1],
                               eligible={"general": False, "type": False})
        self.assertEqual((result["expected"], result["trace"][0]["ignored"],
                          result["trace"][0]["modifiers"], result["trace"][1]["ignored"]),
                         (7.5, True, {"ordinary": [0.25], "additional": [0.75]}, True))

    def test_quantity_supports_documented_reductions_without_rounding(self):
        self.assertEqual(loot.quantity(7.5, ordinary=[-0.5], additional=[], typed=[],
                         eligible={"general": True, "type": True})["expected"], 3.75)

    def test_quantity_allows_a_zero_factor(self):
        self.assertEqual(loot.quantity(7.5, ordinary=[], additional=[-1], typed=[],
                         eligible={"general": True, "type": True})["expected"], 0)


class ConversionTests(unittest.TestCase):
    """Check simultaneous conversion of original item expectations."""

    def test_conversion_normalizes_competing_chances(self):
        self.assertEqual(loot.conversion({"gear": 7.5}, chances={
            "gear": {"fuel": 1, "ember": 0.5},
        })["expected"], {"gear": 0, "fuel": 5, "ember": 2.5})

    def test_conversion_rejects_invalid_individual_probabilities(self):
        for value in (-0.25, 1.25, True, float("nan"), float("inf"), "0.5", None):
            with self.subTest(value=value), self.assertRaises(ValueError):
                loot.conversion({"gear": 3}, chances={"gear": {"fuel": value}})

    def test_conversion_requires_exact_original_source_rules(self):
        for value in ({}, {"gear": {}, "absent": {}}, {"gear": None}, None, []):
            with self.subTest(value=value), self.assertRaises(ValueError):
                loot.conversion({"gear": 3}, chances=value)

    def test_conversion_conserves_expected_slots_with_fractional_residuals(self):
        result = loot.conversion({"gear": 7.5, "fuel": 2.25}, chances={
            "gear": {"fuel": 0.5, "gem": 0.25}, "fuel": {"gear": 0.5},
        })
        self.assertEqual((result["expected"], result["input_total"], result["output_total"]),
                         ({"gear": 3, "fuel": 4.875, "gem": 1.875}, 9.75, 9.75))

    def test_conversion_does_not_cascade_through_a_destination(self):
        self.assertEqual(loot.conversion({"gear": 2, "fuel": 3}, chances={
            "gear": {"fuel": 1}, "fuel": {"ember": 1},
        })["expected"], {"gear": 0, "fuel": 2, "ember": 3})

    def test_conversion_rejects_unknown_item_labels(self):
        for amounts, chances in (({True: 3}, {True: {}}), ({"": 3}, {"": {}}),
                                 ({"gear": 3}, {"gear": {None: 0.5}}), ([], {})):
            with self.subTest(amounts=amounts), self.assertRaises(ValueError):
                loot.conversion(amounts, chances=chances)

    def test_conversion_rejects_nonzero_output_underflow(self):
        with self.assertRaises(ValueError):
            loot.conversion({"gear": 5e-324}, chances={"gear": {"fuel": 0.5}})


class ReplicationTests(unittest.TestCase):
    """Check only guaranteed ordinary and additional loot copy counts."""

    def test_replication_adds_within_classes_and_multiplies_between_classes(self):
        self.assertEqual(loot.replication({"fuel": 2.5},
                         ordinary={"fuel": [2, 3]}, additional={"fuel": [1, 2]})["expected"],
                         {"fuel": 60})

    def test_replication_requires_both_explicit_pools_for_every_type(self):
        for ordinary, additional in (({}, {"fuel": []}), ({"fuel": []}, {}),
                                     ({"fuel": [], "absent": []}, {"fuel": []})):
            with self.subTest(ordinary=ordinary, additional=additional), self.assertRaises(ValueError):
                loot.replication({"fuel": 2.5}, ordinary=ordinary, additional=additional)

    def test_replication_rejects_random_or_negative_copy_counts(self):
        for value in (-1, True, 1.0, 0.25, float("nan"), float("inf"), "2", None):
            with self.subTest(value=value), self.assertRaises(ValueError):
                loot.replication({"fuel": 2.5}, ordinary={"fuel": [value]}, additional={"fuel": []})

    def test_replication_rejects_overflow(self):
        with self.assertRaises(ValueError):
            loot.replication({"fuel": 1e308}, ordinary={"fuel": [3]}, additional={"fuel": []})


class ScenarioTests(unittest.TestCase):
    """Check explicit stage ordering without guessing loot table probabilities."""

    def test_scenario_bypasses_quantity_for_extra_drops_before_conversion_and_replication(self):
        self.assertEqual(loot.scenario({
            "format": "tli-loot-scenario-v1",
            "base": [
                {"type": "gear", "expected": 2, "ordinary": [1], "additional": [0.5], "typed": [1],
                 "eligible": {"general": True, "type": True}},
                {"type": "fuel", "expected": 1, "ordinary": [1], "additional": [], "typed": [9],
                 "eligible": {"general": False, "type": False}},
            ],
            "extra": [{"type": "gear", "expected": 0.5, "eligible": True},
                      {"type": "fuel", "expected": 99, "eligible": False}],
            "conversion": {"gear": {"fuel": 1}, "fuel": {}},
            "replication": {"ordinary": {"gear": [], "fuel": [1]},
                            "additional": {"gear": [], "fuel": [2]}},
        })["expected"], {"gear": 0, "fuel": 81})

    def test_scenario_requires_additional_drop_eligibility(self):
        for extra in ({"type": "fuel", "expected": 3},
                      {"type": "fuel", "expected": 3, "eligible": None}):
            with self.subTest(extra=extra), self.assertRaises(ValueError):
                loot.scenario({"format": "tli-loot-scenario-v1", "base": [], "extra": [extra],
                               "conversion": {"fuel": {}},
                               "replication": {"ordinary": {"fuel": []}, "additional": {"fuel": []}}})

    def test_scenario_rejects_unmodeled_properties(self):
        with self.assertRaises(ValueError):
            loot.scenario({"format": "tli-loot-scenario-v1", "base": [], "extra": [],
                           "conversion": {}, "replication": {"ordinary": {}, "additional": {}},
                           "rarity": 0.75})


class CliTests(unittest.TestCase):
    """Check local file reports through the actual Windows module entry point."""

    def test_cli_publishes_a_report_in_a_new_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "scenario.json"
            source.write_text(json.dumps({
                "format": "tli-loot-scenario-v1",
                "base": [{"type": "gear", "expected": 7.5, "ordinary": [-0.5],
                          "additional": [], "typed": [], "eligible": {"general": True, "type": True}}],
                "extra": [], "conversion": {"gear": {}},
                "replication": {"ordinary": {"gear": []}, "additional": {"gear": []}},
            }), encoding="utf-8")
            result = _run(source, Path(directory) / "result")
            self.assertEqual((result.returncode, json.loads((Path(directory) / "result/report.json").read_text(
                encoding="utf-8"))["expected"]), (0, {"gear": 3.75}))

    def test_cli_rejects_duplicate_fields_without_publishing(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "scenario.json"
            source.write_text('{"format":"unknown","format":"tli-loot-scenario-v1",'
                              '"base":[],"extra":[],"conversion":{},'
                              '"replication":{"ordinary":{},"additional":{}}}', encoding="utf-8")
            result = _run(source, Path(directory) / "result")
            self.assertEqual((result.returncode, (Path(directory) / "result").exists()), (1, False))

    def test_cli_cannot_overwrite_an_existing_output_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "scenario.json"
            source.write_text(json.dumps({"format": "tli-loot-scenario-v1", "base": [], "extra": [],
                                         "conversion": {}, "replication": {"ordinary": {}, "additional": {}}}),
                              encoding="utf-8")
            target = Path(directory) / "result"
            target.mkdir()
            (target / "report.json").write_text("preserved", encoding="utf-8")
            result = _run(source, target)
            self.assertEqual((result.returncode, (target / "report.json").read_text(encoding="utf-8")),
                             (1, "preserved"))

    def test_cli_cannot_round_tiny_json_inputs_to_zero(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "scenario.json"
            source.write_text('{"format":"tli-loot-scenario-v1",'
                              '"base":[{"type":"gear","expected":1e-400,"ordinary":[],"additional":[],"typed":[], '
                              '"eligible":{"general":true,"type":true}}],"extra":[],"conversion":{"gear":{}},'
                              '"replication":{"ordinary":{"gear":[]},"additional":{"gear":[]}}}', encoding="utf-8")
            result = _run(source, Path(directory) / "result")
            self.assertEqual((result.returncode, (Path(directory) / "result").exists()), (1, False))
