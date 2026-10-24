"""Check explicit critical pools using synthetic source assertions."""

import copy
import unittest

from damage_lab.criticalstats import evaluate


def scenario():
    """Provide fictional complete pools with every choice asserted by the caller."""
    return {
        "format": "tli-critical-stat-scenario-v1",
        "context": {"source_sha256": "a" * 64, "skill_alias": "gem[7]"},
        "gates": {name: {"status": "confirmed", "evidence": ["synthetic:" + name]} for name in (
            "version", "base", "scope", "activation", "completeness", "operator")},
        "rating": {"base": [113, 37], "increased": [0.2, 0.3], "more": [], "divisor": 1000, "cap": 0.9},
        "damage": {"base": 1.5, "increased": [0.4], "policy": "percentage_points", "more": []},
    }


class CriticalStatsTests(unittest.TestCase):
    """Resolve caller-owned rating and full critical damage without hit expectation or game claims."""

    def test_explicit_ordinary_damage_policies_produce_distinct_full_multipliers(self):
        outcomes = []
        for policy in ("percentage_points", "relative_to_base"):
            document = scenario()
            document["damage"]["policy"] = policy
            outcomes.append(round(evaluate(document)["multiplier"], 12))
        self.assertEqual(outcomes, [1.9, 2.1])

    def test_grouped_rating_more_scales_the_complete_increased_rating_once(self):
        document = scenario()
        document["rating"]["more"] = [
            {"id": "rating-a", "affix": "one", "value": 0.1, "stacks": 2, "mode": "add"},
            {"id": "rating-b", "affix": "one", "value": 0.05, "stacks": 1, "mode": "add"},
            {"id": "rating-c", "affix": "two", "value": 0.2, "stacks": 2, "mode": "multiply"},
        ]
        report = evaluate(document)
        self.assertEqual((round(report["rating"], 12), round(report["chance"], 12)), (405.0, 0.405))

    def test_damage_more_modifies_the_full_stat_after_the_explicit_ordinary_policy(self):
        document = scenario()
        document["damage"]["more"] = [
            {"id": "damage-a", "affix": "full-stat", "value": 0.2, "stacks": 1, "mode": "add"},
        ]
        self.assertEqual(round(evaluate(document)["multiplier"], 12), 2.28)

    def test_an_explicit_divisor_and_cap_replace_every_implied_game_constant(self):
        document = scenario()
        document["rating"].update(base=[231], increased=[], divisor=700, cap=0.19)
        report = evaluate(document)
        self.assertEqual((report["rating"], report["chance"], next(row["value"] for row in report["trace"]
                                                                  if row["label"] == "Uncapped critical chance")),
                         (231, 0.19, 0.33))

    def test_explicit_zero_rating_cap_and_multiplier_remain_known_zeros(self):
        document = scenario()
        document["rating"].update(base=[], increased=[], divisor=17, cap=0)
        document["damage"].update(base=0, increased=[], more=[])
        report = evaluate(document)
        self.assertEqual((report["status"], report["rating"], report["chance"], report["multiplier"]),
                         ("conditional", 0, 0, 0))

    def test_unknown_conflicting_and_absent_gates_block_all_numeric_outputs_and_trace(self):
        outcomes = []
        for name in ("version", "base", "scope", "activation", "completeness", "operator"):
            for status in ("unknown", "conflict", "missing"):
                document = scenario()
                if status == "missing":
                    document["gates"].pop(name)
                else:
                    document["gates"][name] = {"status": status, "evidence": []}
                report = evaluate(document)
                outcomes.append((report["status"], report["rating"], report["chance"], report["multiplier"],
                                 report["trace"], name + ": " + status in report["gaps"]))
        self.assertEqual(outcomes, [("blocked", None, None, None, [], True)] * 18)

    def test_each_unknown_pool_input_blocks_even_when_other_numeric_inputs_are_known(self):
        outcomes = []
        for pool, fields in (("rating", ("base", "increased", "more", "divisor", "cap")),
                             ("damage", ("base", "increased", "policy", "more"))):
            for field in fields:
                document = scenario()
                document[pool][field] = None
                report = evaluate(document)
                outcomes.append((report["status"], report["rating"], report["chance"], report["multiplier"],
                                 report["trace"], pool + "." + field + ": unknown" in report["gaps"],
                                 report["scenario"][pool][field]))
        self.assertEqual(outcomes, [("blocked", None, None, None, [], True, None)] * 9)

    def test_malformed_nonnull_values_are_not_hidden_by_unknown_gates_or_other_inputs(self):
        outcomes = []
        for path, value in ((("rating", "base"), [True]), (("rating", "increased"), ["0.3"]),
                            (("rating", "divisor"), False), (("rating", "cap"), 1.01),
                            (("damage", "base"), -0.1), (("damage", "increased"), [None]),
                            (("damage", "policy"), "PRIVATE-CRITICAL-CANARY"),
                            (("damage", "more"), {})):
            document = scenario()
            document["gates"]["operator"] = {"status": "unknown", "evidence": []}
            document["rating"]["more"] = None
            document[path[0]][path[1]] = value
            try:
                evaluate(document)
            except ValueError as error:
                outcomes.append(("PRIVATE-CRITICAL-CANARY" in str(error), str(error).endswith(".")))
        self.assertEqual(outcomes, [(False, False)] * 8)

    def test_negative_combined_rating_or_full_damage_is_refused_before_blocked_return(self):
        outcomes = []
        for pool, policy in (("rating", "percentage_points"), ("damage", "percentage_points"),
                             ("damage", "relative_to_base")):
            document = scenario()
            document["gates"].pop("activation")
            document[pool]["increased"] = [-0.8, -0.8]
            document["damage"].update(base=1.5, policy=policy)
            try:
                evaluate(document)
            except ValueError:
                outcomes.append(True)
        self.assertEqual(outcomes, [True] * 3)

    def test_a_report_is_deterministic_detached_and_records_the_selected_policy(self):
        document = scenario()
        original = copy.deepcopy(document)
        report = evaluate(document)
        repeated = evaluate(document)
        report["scenario"]["gates"]["operator"]["evidence"].append("changed")
        self.assertEqual((document, repeated == evaluate(document), report["format"],
                          next(row["policy"] for row in report["trace"] if "policy" in row),
                          "changed" in document["gates"]["operator"]["evidence"]),
                         (original, True, "tli-critical-stat-report-v1", "percentage_points", False))

    def test_finite_sum_product_and_quotient_overflows_are_controlled_even_when_a_gate_is_unknown(self):
        outcomes = []
        for change in ("sum", "rating", "rating-more", "relative", "damage-more", "quotient"):
            document = scenario()
            document["gates"]["operator"] = {"status": "unknown", "evidence": []}
            if change == "sum":
                document["rating"]["base"] = [1e308, 1e308]
            elif change == "rating":
                document["rating"].update(base=[1e308], increased=[1])
            elif change == "rating-more":
                document["rating"]["more"] = [{"id": "huge", "affix": "huge", "value": 1e6, "stacks": 1000, "mode": "multiply"}]
            elif change == "relative":
                document["damage"].update(base=1e308, increased=[1], policy="relative_to_base")
            elif change == "damage-more":
                document["damage"].update(base=1e308, increased=[], more=[
                    {"id": "huge", "affix": "huge", "value": 1, "stacks": 1, "mode": "add"}])
            else:
                document["rating"].update(base=[1], divisor=5e-324)
            try:
                evaluate(document)
            except ValueError as error:
                outcomes.append(str(error).endswith("."))
        self.assertEqual(outcomes, [False] * 6)

    def test_positive_products_and_quotients_cannot_silently_underflow_to_zero(self):
        outcomes = []
        for change in ("rating", "rating-more", "relative", "damage-more", "quotient"):
            document = scenario()
            if change == "rating":
                document["rating"].update(base=[5e-324], increased=[-0.5])
            elif change == "rating-more":
                document["rating"]["more"] = [{"id": "small", "affix": "small", "value": -0.9, "stacks": 400, "mode": "multiply"}]
            elif change == "relative":
                document["damage"].update(base=5e-324, increased=[-0.5], policy="relative_to_base")
            elif change == "damage-more":
                document["damage"].update(base=5e-324, increased=[], more=[
                    {"id": "small", "affix": "small", "value": -0.5, "stacks": 1, "mode": "add"}])
            else:
                document["rating"].update(base=[5e-324], increased=[], divisor=2, cap=0)
            try:
                evaluate(document)
            except ValueError as error:
                outcomes.append("underflow" in str(error))
        self.assertEqual(outcomes, [True] * 5)

    def test_more_instances_cannot_repeat_or_disagree_on_the_same_affix_mode(self):
        outcomes = []
        for pool in ("rating", "damage"):
            for change in ("duplicate", "mode"):
                document = scenario()
                document["gates"].pop("completeness")
                document[pool]["more"] = [
                    {"id": "one", "affix": "group", "value": 0.17, "stacks": 1, "mode": "add"},
                    {"id": "one" if change == "duplicate" else "two", "affix": "group", "value": 0.23,
                     "stacks": 1, "mode": "add" if change == "duplicate" else "multiply"},
                ]
                try:
                    evaluate(document)
                except ValueError:
                    outcomes.append(True)
        self.assertEqual(outcomes, [True] * 4)

    def test_more_rows_require_strict_integer_stacks_and_all_known_fields(self):
        outcomes = []
        row = {"id": "effect", "affix": "stat", "value": 0.17, "stacks": 1, "mode": "add"}
        for field, value in (("stacks", True), ("stacks", 1.0), ("stacks", -1), ("stacks", 1001),
                             ("value", True), ("value", -1.01), ("value", 1000001), ("value", float("inf")),
                             ("mode", "unknown"), ("id", ""), ("id", "effect\nPRIVATE-CRITICAL-CANARY"),
                             ("affix", " group"), ("scope", "critical_only")):
            document = scenario()
            document["damage"]["more"] = [{**row, field: value}]
            try:
                evaluate(document)
            except ValueError as error:
                outcomes.append("PRIVATE-CRITICAL-CANARY" in str(error))
        document = scenario()
        document["damage"]["more"] = [{key: value for key, value in row.items() if key != "mode"}]
        try:
            evaluate(document)
        except ValueError:
            outcomes.append(False)
        self.assertEqual(outcomes, [False] * 14)

    def test_unknown_keys_and_missing_structural_fields_do_not_become_defaults(self):
        outcomes = []
        for path in ((), ("context",), ("rating",), ("damage",), ("gates",), ("gates", "version")):
            document = scenario()
            node = document
            for field in path:
                node = node[field]
            node["PRIVATE-CRITICAL-CANARY"] = "extra"
            try:
                evaluate(document)
            except ValueError as error:
                outcomes.append("PRIVATE-CRITICAL-CANARY" in str(error))
        for pool, field in ((None, "damage"), ("context", "source_sha256"), ("rating", "divisor"), ("damage", "policy")):
            document = scenario()
            (document if pool is None else document[pool]).pop(field)
            try:
                evaluate(document)
            except ValueError:
                outcomes.append(False)
        self.assertEqual(outcomes, [False] * 10)

    def test_source_and_skill_alias_are_required_typed_context_without_coercion(self):
        outcomes = []
        for field, value in (("source_sha256", "A" * 64), ("source_sha256", "a" * 63),
                             ("source_sha256", None), ("source_sha256", True),
                             ("skill_alias", "gem[0]"), ("skill_alias", "gem[01]"),
                             ("skill_alias", "gem[1000000000]"), ("skill_alias", "gem[١]"),
                             ("skill_alias", 7), ("skill_alias", "PRIVATE-CRITICAL-CANARY")):
            document = scenario()
            document["context"][field] = value
            try:
                evaluate(document)
            except ValueError as error:
                outcomes.append("PRIVATE-CRITICAL-CANARY" in str(error))
        self.assertEqual(outcomes, [False] * 10)

    def test_evidence_and_collection_limits_apply_before_numeric_results_are_returned(self):
        outcomes = []
        for change in ("confirmed-empty", "status", "evidence-shape", "evidence-nontext", "evidence-control", "evidence-long",
                       "evidence-count", "base-count", "increased-count", "more-count"):
            document = scenario()
            gate = document["gates"]["version"]
            if change == "confirmed-empty":
                gate["evidence"] = []
            elif change == "status":
                gate["status"] = "PRIVATE-CRITICAL-CANARY"
            elif change == "evidence-shape":
                gate["evidence"] = "PRIVATE-CRITICAL-CANARY"
            elif change == "evidence-nontext":
                gate["evidence"] = [False]
            elif change == "evidence-control":
                gate["evidence"] = ["synthetic\x00PRIVATE-CRITICAL-CANARY"]
            elif change == "evidence-long":
                gate["evidence"] = ["x" * 1025]
            elif change == "evidence-count":
                gate["evidence"] = ["synthetic"] * 1001
            elif change == "base-count":
                document["rating"]["base"] = [0] * 1001
            elif change == "increased-count":
                document["damage"]["increased"] = [0] * 1001
            else:
                document["rating"]["more"] = [{}] * 1001
            try:
                evaluate(document)
            except ValueError as error:
                outcomes.append("PRIVATE-CRITICAL-CANARY" in str(error))
        self.assertEqual(outcomes, [False] * 10)

    def test_nonfinite_overlarge_or_wrong_numeric_types_are_never_accepted_as_pool_numbers(self):
        outcomes = []
        for value in (float("nan"), float("inf"), -float("inf"), 10 ** 400, "0.3", True):
            for pool, field in (("rating", "base"), ("rating", "increased"), ("rating", "divisor"),
                                ("rating", "cap"), ("damage", "base"), ("damage", "increased")):
                document = scenario()
                document[pool][field] = [value] if field == "increased" or (pool == "rating" and field == "base") else value
                try:
                    evaluate(document)
                except ValueError:
                    outcomes.append(True)
        self.assertEqual(outcomes, [True] * 36)

    def test_lucky_critical_only_hit_and_damage_scope_inputs_have_no_place_in_these_pools(self):
        outcomes = []
        for field in ("lucky", "lucky_damage", "critical_only_more", "support_7420", "panel_multiplier"):
            document = scenario()
            document["damage"][field] = 0.355
            try:
                evaluate(document)
            except ValueError:
                outcomes.append(True)
        self.assertEqual(outcomes, [True] * 5)
