"""Exact gain at the upgrade API. Clause 4."""

import json
import sys
import unittest
from fractions import Fraction
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from damage_lab.upgradegoal import evaluate

BASE = 10 ** 15 - 100
INCREMENT = 0.578125


def variant(amount, multiplier=100):
    scenario = {
        "format": "tli-raw-cold-combat-v1",
        "spell": {
            "format": "tli-raw-cold-spell-v1",
            "context": {"source_sha256": "c" * 64, "catalog_sha256": "d" * 64,
                        "skill_id": "synthetic-cold-spell", "effective_level": 13,
                        "gates": {name: {"status": "confirmed", "evidence": ["synthetic:" + name]}
                                  for name in ("version", "level", "base", "conversion")}},
            "damage": {"base": {"min": amount, "max": amount}, "physical": {"min": 0, "max": 0},
                       "cold": {"min": 0, "max": 0}, "effectiveness": 1,
                       "increased": {"all": 0, "physical": 0, "cold": 0}, "more": [], "roll_model": "midpoint"},
            "critical": {"chance": 1, "multiplier": multiplier, "lucky": False, "more": 0},
            "casting": {"interval": 1, "increased": 0, "more": [], "frequency": None},
            "missing": [], "notes": ["Synthetic complete spell pools"]},
        "topology": {"maximum": 1, "extra": 0, "active": 1, "hits": 1, "retention": .25},
        "target": {"cold_resistance": 0, "cold_penetration": 0, "armor": 0,
                   "armor_effectiveness": 1, "armor_penetration": 0,
                   "armor_penetration_order": "after_effectiveness", "increased_taken": 0,
                   "more_taken": []},
        "uptime": 1,
        "gates": {name: {"status": "confirmed", "evidence": ["synthetic:" + name]}
                  for name in ("inheritance", "hit_topology", "target_state")},
        "missing": [], "notes": ["Synthetic topology and target assertions"],
    }
    return scenario


def document(cheap_amount, cheap_multiplier=100, dear_amount=None):
    if dear_amount is None:
        dear_amount = BASE + 2
    return {"format": "tli-combat-upgrade-scenario-v1", "baseline": variant(BASE),
            "currency": "synthetic tokens",
            "candidates": [
                {"id": "dear", "name": "Synthetic dear", "scenario": variant(dear_amount),
                 "cost": 5, "missing": []},
                {"id": "cheap", "name": "Synthetic cheap",
                 "scenario": variant(cheap_amount, cheap_multiplier), "cost": 1, "missing": []}]}


class ExactUpgradeGainTests(unittest.TestCase):
    def test_minimum_63_selects_dear_and_reports_the_operand_gains(self):
        report = evaluate(document(BASE + INCREMENT), minimum=63, budget=10)
        deltas = {row["id"]: row["delta"] for row in report["candidates"]}
        self.assertEqual(deltas, {"dear": 200, "cheap": 62.5})
        self.assertEqual(report["goal"]["selected"], "dear")
        self.assertEqual(report["goal"]["excluded"], [{"id": "cheap", "reasons": ["below_minimum"]}])

    def test_minimum_60_and_the_exact_boundary_keep_cheap(self):
        low = evaluate(document(BASE + INCREMENT), minimum=60, budget=10)
        edge = evaluate(document(BASE + INCREMENT), minimum=62.5, budget=10)
        self.assertEqual(low["goal"]["selected"], "cheap")
        self.assertEqual(edge["goal"]["selected"], "cheap")

    def test_json_replay_uses_the_same_admitted_float(self):
        original = document(BASE + INCREMENT)
        replayed = json.loads(json.dumps(original))
        first = evaluate(original, minimum=63, budget=10)
        second = evaluate(replayed, minimum=63, budget=10)
        self.assertEqual(first["goal"]["selected"], second["goal"]["selected"])
        deltas = {row["id"]: row["delta"] for row in first["candidates"]}
        self.assertEqual(deltas, {row["id"]: row["delta"] for row in second["candidates"]})
        self.assertEqual(deltas, {"dear": 200, "cheap": 62.5})

    def test_a_critical_multiplier_change_is_not_a_base_shortcut(self):
        payload = document(BASE, cheap_multiplier=2, dear_amount=BASE)
        payload["baseline"]["spell"]["critical"]["multiplier"] = 1
        payload["candidates"][0]["scenario"]["spell"]["critical"]["multiplier"] = 1
        report = evaluate(payload, minimum=1, budget=10)
        deltas = {row["id"]: row["delta"] for row in report["candidates"]}
        self.assertEqual(deltas["cheap"], BASE)
        self.assertEqual(deltas["dear"], 0)

    def test_zero_and_negative_gains_are_not_upgrades(self):
        same = evaluate(document(BASE, dear_amount=BASE), minimum=1, budget=10)
        lower = evaluate(document(BASE - 1), minimum=1, budget=10)
        self.assertEqual({row["id"]: row["delta"] for row in same["candidates"]}, {"dear": 0, "cheap": 0})
        self.assertIsNone(same["goal"]["selected"])
        cheap = {row["id"]: row["delta"] for row in lower["candidates"]}["cheap"]
        self.assertLess(cheap, 0)
        reasons = {row["id"]: row["reasons"] for row in lower["goal"]["excluded"]}
        self.assertEqual(reasons["cheap"], ["not_upgrade"])

    def test_a_missing_gate_blocks_the_delta(self):
        payload = document(BASE + INCREMENT)
        payload["baseline"]["gates"]["inheritance"]["status"] = "unknown"
        report = evaluate(payload, minimum=63, budget=10)
        self.assertIsNone(report["candidates"][0]["delta"])
        self.assertEqual(report["goal"]["selected"], None)

    def test_a_separate_physical_addend_keeps_37_64ths(self):
        payload = document(float(BASE))
        for scenario in (payload["baseline"], payload["candidates"][0]["scenario"], payload["candidates"][1]["scenario"]):
            scenario["spell"]["damage"]["base"]["min"] = float(BASE)
            scenario["spell"]["damage"]["base"]["max"] = float(BASE)
        payload["candidates"][0]["scenario"]["spell"]["damage"]["base"]["min"] = float(BASE) + 2
        payload["candidates"][0]["scenario"]["spell"]["damage"]["base"]["max"] = float(BASE) + 2
        physical = payload["candidates"][1]["scenario"]["spell"]["damage"]["physical"]
        physical["min"] = physical["max"] = 0.578125
        report = evaluate(payload, minimum=60, budget=10)
        deltas = {row["id"]: row["delta"] for row in report["candidates"]}
        self.assertEqual(deltas["cheap"], 57.8125)
        self.assertEqual(deltas["dear"], 200)
        self.assertEqual(report["goal"]["selected"], "dear")
        reasons = {row["id"]: row["reasons"] for row in report["goal"]["excluded"]}
        self.assertEqual(reasons["cheap"], ["below_minimum"])

    def test_a_float_critical_chance_uses_the_admitted_probability(self):
        payload = document(BASE, cheap_multiplier=3, dear_amount=BASE)
        for scenario, multiplier in (
                (payload["baseline"], 1),
                (payload["candidates"][0]["scenario"], 1),
                (payload["candidates"][1]["scenario"], 3)):
            scenario["spell"]["critical"].update(chance=0.1, multiplier=multiplier, lucky=True)
        report = evaluate(payload, minimum=1, budget=10)
        deltas = {row["id"]: row["delta"] for row in report["candidates"]}
        self.assertEqual(deltas["cheap"], 379999999999962.0)
        self.assertEqual(deltas["dear"], 0)

    def test_a_cast_rate_below_its_float_misses_that_minimum(self):
        minimum = float((1 + Fraction(0.1)) / Fraction(0.3) * 10)
        payload = document(10, cheap_multiplier=1, dear_amount=0)
        for scenario in (payload["baseline"], payload["candidates"][0]["scenario"]):
            scenario["spell"]["damage"]["base"]["min"] = scenario["spell"]["damage"]["base"]["max"] = 0
            scenario["spell"]["critical"].update(chance=0, multiplier=1, lucky=False)
        cheap = payload["candidates"][1]["scenario"]
        cheap["spell"]["damage"]["base"]["min"] = cheap["spell"]["damage"]["base"]["max"] = 10
        cheap["spell"]["critical"].update(chance=0, multiplier=1, lucky=False)
        cheap["spell"]["casting"].update(interval=0.3, increased=0.1)
        report = evaluate(payload, minimum=minimum, budget=10)
        cheap_row = {row["id"]: row for row in report["candidates"]}["cheap"]
        self.assertEqual(cheap_row["delta"], minimum)
        self.assertIsNone(report["goal"]["selected"])
        reasons = {row["id"]: row["reasons"] for row in report["goal"]["excluded"]}
        self.assertEqual(reasons["cheap"], ["below_minimum"])

    def test_a_cast_rate_division_keeps_the_admitted_operands(self):
        payload = document(10, cheap_multiplier=1, dear_amount=0)
        for scenario in (payload["baseline"], payload["candidates"][0]["scenario"]):
            scenario["spell"]["damage"]["base"]["min"] = scenario["spell"]["damage"]["base"]["max"] = 0
            scenario["spell"]["critical"].update(chance=0, multiplier=1, lucky=False)
        cheap = payload["candidates"][1]["scenario"]
        cheap["spell"]["damage"]["base"]["min"] = cheap["spell"]["damage"]["base"]["max"] = 10
        cheap["spell"]["critical"].update(chance=0, multiplier=1, lucky=False)
        cheap["spell"]["casting"].update(interval=0.9, increased=0.1)
        report = evaluate(payload, minimum=1, budget=10)
        deltas = {row["id"]: row["delta"] for row in report["candidates"]}
        self.assertEqual(deltas["cheap"], 12.222222222222221)

    def test_equal_published_floats_rank_by_the_exact_gain(self):
        number = float((1 + Fraction(0.1)) / Fraction(0.3) * 10)
        low = variant(10, multiplier=1)
        low["spell"]["critical"].update(chance=0, lucky=False)
        low["spell"]["casting"].update(interval=0.3, increased=0.1)
        high = variant(number, multiplier=1)
        high["spell"]["critical"].update(chance=0, lucky=False)
        baseline = variant(0, multiplier=1)
        baseline["spell"]["critical"].update(chance=0, lucky=False)
        payload = {"format": "tli-combat-upgrade-scenario-v1", "baseline": baseline,
                   "currency": "synthetic tokens", "candidates": [
                       {"id": "a", "name": "Synthetic low", "scenario": low, "cost": 1, "missing": []},
                       {"id": "z", "name": "Synthetic high", "scenario": high, "cost": 1, "missing": []}]}
        report = evaluate(payload, minimum=1, budget=10)
        self.assertEqual(report["goal"]["ranking"], ["z", "a"])
        self.assertEqual({row["id"]: row["delta"] for row in report["candidates"]}, {"a": number, "z": number})

    def stacked(self, mode):
        cheap = variant(BASE)
        cheap["spell"]["damage"]["more"] = [
            {"id": "m", "affix": "a", "value": 0.1, "stacks": 3, "mode": mode, "scope": "all"}]
        return {"format": "tli-combat-upgrade-scenario-v1", "baseline": variant(BASE),
                "currency": "synthetic tokens", "candidates": [
                    {"id": "cheap", "name": "Synthetic cheap", "scenario": cheap, "cost": 1, "missing": []}]}

    def test_added_stacks_stay_below_the_float_product_minimum(self):
        truth = Fraction(BASE) * 100 * (3 * Fraction(0.1))
        minimum = 2.9999999999997004e16
        self.assertLess(truth, Fraction(minimum))
        report = evaluate(self.stacked("add"), minimum=minimum, budget=10)
        self.assertEqual(report["candidates"][0]["delta"], float(truth))
        self.assertIsNone(report["goal"]["selected"])

    def test_multiplied_stacks_stay_below_the_float_power_minimum(self):
        truth = Fraction(BASE) * 100 * ((1 + Fraction(0.1)) ** 3 - 1)
        minimum = 3.309999999999671e16
        self.assertLess(truth, Fraction(minimum))
        report = evaluate(self.stacked("multiply"), minimum=minimum, budget=10)
        self.assertEqual(report["candidates"][0]["delta"], float(truth))
        self.assertIsNone(report["goal"]["selected"])

    def test_a_tiny_multiply_row_is_not_lost_in_one_plus_value(self):
        cheap = variant(1, multiplier=1)
        cheap["spell"]["damage"]["more"] = [
            {"id": "m", "affix": "a", "value": 2**-54, "stacks": 1, "mode": "multiply", "scope": "all"}]
        payload = {"format": "tli-combat-upgrade-scenario-v1", "baseline": variant(1, multiplier=1),
                   "currency": "synthetic tokens", "candidates": [
                       {"id": "cheap", "name": "Synthetic cheap", "scenario": cheap, "cost": 1, "missing": []}]}
        report = evaluate(payload, minimum=2**-60, budget=10)
        self.assertEqual(report["candidates"][0]["delta"], 2**-54)


if __name__ == "__main__":
    unittest.main()
