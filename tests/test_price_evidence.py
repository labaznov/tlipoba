import contextlib
import copy
import html
import io
import json
import tempfile
import unittest
from pathlib import Path

from damage_lab.combatupgradecli import main
from damage_lab.combatupgradereport import render
from damage_lab.combatupgrades import evaluate, exact_deltas
from damage_lab.upgradegoal import evaluate as goal
from test_combatupgrades import unit

KNOWN = {"source": "SYNTH market <a>&\"", "observed_at": "2026-02-17T11:23:47.123400+03:30"}
UNKNOWN = {"source": None, "observed_at": None}


def entry(identity, target, cost, evidence):
    return {"id": identity, "name": "Synthetic " + identity, "scenario": target, "cost": cost, "missing": [],
            "price_evidence": copy.deepcopy(evidence)}


def blocked(amount):
    target = unit(amount)
    target["gates"]["hit_topology"] = {"status": "unknown", "evidence": []}
    return target


def document():
    """Every row status at once, each with distinct evidence; the blocked row would look best if computed."""
    return {"format": "tli-combat-upgrade-scenario-v2", "baseline": unit(100), "currency": "synthetic tokens",
            "candidates": [
                entry("blocked", blocked(900), 1, {"source": "blocked shop", "observed_at": "2026-01-01T00:00:00Z"}),
                entry("cheap", unit(130), 5, KNOWN),
                entry("same-cost", unit(120), 5, {"source": "second shop", "observed_at": None}),
                entry("unpriced", unit(150), None, {"source": "unpriced note", "observed_at": "2026-03-01T08:00:00-00:00"}),
                entry("free", unit(110), 0, {"source": None, "observed_at": "2026-04-01T09:30:00.5+05:45"}),
                entry("worse", unit(90), 2, UNKNOWN)]}


def legacy(v2):
    """The same comparison without evidence, as a v1 caller would send it."""
    v1 = copy.deepcopy(v2)
    v1["format"] = "tli-combat-upgrade-scenario-v1"
    for row in v1["candidates"]:
        del row["price_evidence"]
    return v1


def with_evidence(evidence):
    value = document()
    value["candidates"][1]["price_evidence"] = evidence
    return value


def label(value):
    return "неизвестно" if value is None else html.escape(value, quote=True)


def row_html(page, identity, identities):
    """The candidate-table row of one candidate: from its own first cell up to the next candidate's."""
    start = page.index("<tr><td>" + identity + "<br>")
    later = [page.index("<tr><td>" + other + "<br>") for other in identities
             if page.index("<tr><td>" + other + "<br>") > start]
    return page[start:min(later)] if later else page[start:page.index("</tbody></table></div></section>", start)]


class PriceEvidenceTests(unittest.TestCase):
    """Caller price source and time stay attached to their own candidate and never change the comparison."""

    def test_clause_1_legacy_documents_are_unchanged_and_never_read_as_v2(self):
        v1 = legacy(document())
        report = evaluate(v1)
        self.assertEqual(report["format"], "tli-combat-upgrade-report-v1")
        self.assertTrue(all("price_evidence" not in row for row in report["candidates"]))
        page = render(report)
        self.assertNotIn("Источник цены", page)
        self.assertNotIn("Время получения цены", page)
        self.assertEqual(goal(v1, minimum=10, budget=5)["format"], "tli-combat-upgrade-report-v1")
        mixed = copy.deepcopy(v1)
        mixed["candidates"][0]["price_evidence"] = copy.deepcopy(UNKNOWN)
        complete = copy.deepcopy(v1)
        for row in complete["candidates"]:
            row["price_evidence"] = copy.deepcopy(UNKNOWN)
        for case in (mixed, complete):
            with self.assertRaises(ValueError):
                evaluate(case)

    def test_clause_2_v2_requires_exactly_source_and_observed_at(self):
        missing = document()
        del missing["candidates"][0]["price_evidence"]
        cases = [missing, with_evidence(None), with_evidence([None, None]), with_evidence({"source": None}),
                 with_evidence({"observed_at": None}), with_evidence(dict(UNKNOWN, currency="x")),
                 with_evidence({"source": True, "observed_at": None}), with_evidence({"source": 1, "observed_at": None}),
                 with_evidence({"source": None, "observed_at": False}),
                 with_evidence({"source": None, "observed_at": 1793034700})]
        for index, case in enumerate(cases):
            with self.subTest(case=index):
                with self.assertRaises(ValueError):
                    evaluate(case)
                with self.assertRaises(ValueError):
                    goal(case, minimum=10, budget=5)
        unsupported = document()
        unsupported["format"] = "tli-combat-upgrade-scenario-v3"
        with self.assertRaises(ValueError):
            evaluate(unsupported)

    def test_clause_3_source_uses_the_bounded_trimmed_label_policy(self):
        for source in ("", " shop", "shop ", "\tshop", "x" * 1025):
            with self.subTest(source=source[:12]), self.assertRaises(ValueError):
                evaluate(with_evidence({"source": source, "observed_at": None}))
        report = evaluate(with_evidence({"source": "x" * 1024, "observed_at": None}))
        self.assertEqual(report["candidates"][1]["price_evidence"], {"source": "x" * 1024, "observed_at": None})

    def test_clause_4_admitted_timestamps_are_preserved_verbatim(self):
        for stamp in ("2026-02-17T11:23:47Z", "2026-02-17T11:23:47.1Z", "2026-02-17T11:23:47.123456Z",
                      "2026-02-17T11:23:47+23:59", "2026-02-17T11:23:47-00:00", "2024-02-29T23:59:59-12:30",
                      "0001-01-01T00:00:00Z", "9999-12-31T23:59:59.000000+00:00", "2026-02-17T11:23:47.120000+03:30"):
            with self.subTest(stamp=stamp):
                report = evaluate(with_evidence({"source": None, "observed_at": stamp}))
                self.assertEqual(report["candidates"][1]["price_evidence"]["observed_at"], stamp)

    def test_clause_4_invalid_or_naive_timestamps_are_refused(self):
        for stamp in ("2026-02-17T11:23:47", "2026-02-17t11:23:47Z", "2026-02-17T11:23:47z", "2026-02-17 11:23:47Z",
                      "2026-02-17T11:23:60Z", "0000-01-01T00:00:00Z", "2026-02-17T11:23:47+24:00",
                      "2026-02-17T11:23:47+05:60", "2023-02-29T00:00:00Z", "2026-13-01T00:00:00Z",
                      "2026-00-10T00:00:00Z", "2026-04-31T00:00:00Z", "2026-02-17T24:00:00Z", "2026-02-17T11:60:00Z",
                      "2026-02-17T11:23:47.Z", "2026-02-17T11:23:47.1234567Z", "2026-02-17T11:23Z",
                      "2026-02-17T11:23:47+0530", "2026-02-17T11:23:47+05", "26-02-17T11:23:47Z",
                      "+2026-02-17T11:23:47Z", "20260217T112347Z", "2026-02-17T11:23:47Z\n", " 2026-02-17T11:23:47Z",
                      "2026-02-17T11:23:47ZZ", "2026-02-17T11:23:47,5Z", "٢026-02-17T11:23:47Z",
                      "２026-02-17T11:23:47Z", "2026-02-17T11:23:47Z+00:00", "", "now"):
            with self.subTest(stamp=stamp), self.assertRaises(ValueError):
                evaluate(with_evidence({"source": None, "observed_at": stamp}))

    def test_clause_5_report_keeps_each_candidates_own_evidence_without_aliasing(self):
        source = document()
        report = evaluate(source)
        self.assertEqual(report["format"], "tli-combat-upgrade-report-v2")
        self.assertEqual(report["price_source"], "caller")
        self.assertEqual(report["scenario"], document())
        rows = {row["id"]: row for row in report["candidates"]}
        for row in document()["candidates"]:
            self.assertEqual(rows[row["id"]]["price_evidence"], row["price_evidence"])
        self.assertEqual(json.loads(json.dumps(report)), report)
        source["candidates"][1]["price_evidence"]["source"] = "edited caller"
        self.assertEqual(rows["cheap"]["price_evidence"], KNOWN)
        self.assertEqual(report["scenario"]["candidates"][1]["price_evidence"], KNOWN)
        rows["cheap"]["price_evidence"]["source"] = "edited report"
        self.assertEqual(report["scenario"]["candidates"][1]["price_evidence"], KNOWN)
        self.assertIsNot(rows["cheap"]["price_evidence"], report["scenario"]["candidates"][1]["price_evidence"])

    def test_clause_6_html_shows_own_escaped_evidence_and_explicit_unknowns(self):
        value = document()
        identities = [row["id"] for row in value["candidates"]]
        for order in (identities, list(reversed(identities))):
            with self.subTest(order=order[0]):
                value["candidates"].sort(key=lambda row: order.index(row["id"]))
                for report in (evaluate(value), goal(value, minimum=10, budget=5)):
                    page = render(report)
                    self.assertNotIn(KNOWN["source"], page)
                    for row in value["candidates"]:
                        own = row_html(page, row["id"], identities)
                        evidence = row["price_evidence"]
                        self.assertIn("Источник цены: " + label(evidence["source"]), own)
                        self.assertIn("Время получения цены: " + label(evidence["observed_at"]), own)
                        for other in value["candidates"]:
                            for field in ("source", "observed_at"):
                                if other["price_evidence"][field] not in (None, evidence[field]):
                                    self.assertNotIn(label(other["price_evidence"][field]), own)
                    self.assertIn("Источник и время цены заданы вызывающей стороной и не проверялись", page)

    def test_clause_7_evidence_changes_no_number_status_ranking_or_goal(self):
        v2 = document()
        v1 = legacy(v2)
        new, old = evaluate(v2), evaluate(v1)
        strip = [{key: value for key, value in row.items() if key != "price_evidence"} for row in new["candidates"]]
        self.assertEqual(strip, old["candidates"])
        self.assertEqual(new["ranking"], old["ranking"])
        self.assertEqual(new["ranking"], ["free", "cheap", "same-cost"])
        self.assertEqual(exact_deltas(v2), exact_deltas(v1))
        rows = {row["id"]: row for row in new["candidates"]}
        self.assertEqual([rows[name]["status"] for name in ("blocked", "unpriced", "free", "worse")],
                         ["blocked", "unpriced", "free", "not_upgrade"])
        self.assertEqual((rows["blocked"]["delta"], rows["blocked"]["per_cost"]), (None, None))
        self.assertFalse(rows["unpriced"]["eligible_for_cost_ranking"])
        self.assertIsNone(rows["unpriced"]["cost"])
        for minimum, budget in ((10, 5), (25, 5), (10, 0), (1000, 1000)):
            with self.subTest(minimum=minimum, budget=budget):
                self.assertEqual(goal(v2, minimum=minimum, budget=budget)["goal"],
                                 goal(v1, minimum=minimum, budget=budget)["goal"])
        swapped = copy.deepcopy(v2)
        swapped["candidates"][1]["price_evidence"], swapped["candidates"][2]["price_evidence"] = (
            swapped["candidates"][2]["price_evidence"], swapped["candidates"][1]["price_evidence"])
        self.assertEqual(goal(swapped, minimum=10, budget=5)["goal"], goal(v2, minimum=10, budget=5)["goal"])

    def test_clause_8_replay_refuses_modified_evidence_costs_ranking_or_status(self):
        for report in (evaluate(document()), goal(document(), minimum=10, budget=5)):
            self.assertEqual(render(json.loads(json.dumps(report))), render(report))
            edits = [lambda r: r["candidates"][1]["price_evidence"].update(source="forged"),
                     lambda r: r["candidates"][1]["price_evidence"].update(observed_at="2027-01-01T00:00:00Z"),
                     lambda r: r["scenario"]["candidates"][1]["price_evidence"].update(source="forged"),
                     lambda r: r["candidates"][1].update(cost=1),
                     lambda r: r["ranking"].reverse(),
                     lambda r: r["candidates"][0].update(status="upgrade"),
                     lambda r: r.update(format="tli-combat-upgrade-report-v1")]
            for index, edit in enumerate(edits):
                with self.subTest(goal="goal" in report, edit=index):
                    forged = copy.deepcopy(report)
                    edit(forged)
                    with self.assertRaises(ValueError):
                        render(forged)

    def test_clause_8_cli_publishes_v2_in_both_modes_and_nothing_for_invalid_evidence(self):
        invalid = with_evidence({"source": None, "observed_at": "2026-02-17T11:23:60Z"})
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            for name, value, extra, status in (("plain", document(), [], 0),
                                               ("goal", document(), ["--minimum-gain", "10", "--budget", "5"], 0),
                                               ("invalid", invalid, [], 1),
                                               ("invalid-goal", invalid, ["--minimum-gain", "10", "--budget", "5"], 1)):
                with self.subTest(mode=name):
                    source, target = root / (name + ".json"), root / name
                    source.write_text(json.dumps(value), encoding="utf-8")
                    errors = io.StringIO()
                    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(errors):
                        self.assertEqual(main(["--scenario", str(source), "--output", str(target)] + extra), status)
                    if status:
                        self.assertFalse(target.exists())
                        self.assertNotIn("Traceback", errors.getvalue())
                        continue
                    report = json.loads((target / "comparison.json").read_text(encoding="utf-8"))
                    self.assertEqual(report["format"], "tli-combat-upgrade-report-v2")
                    self.assertEqual({row["id"]: row["price_evidence"] for row in report["candidates"]},
                                     {row["id"]: row["price_evidence"] for row in value["candidates"]})
                    self.assertEqual((target / "index.html").read_text(encoding="utf-8"), render(report))
            self.assertEqual(sorted(path.name for path in root.iterdir() if path.is_dir()), ["goal", "plain"])


if __name__ == "__main__":
    unittest.main()
