import copy
import json
import unittest
from html.parser import HTMLParser

from damage_lab.combatupgrades import evaluate
from damage_lab.combatupgradereport import render
from test_combatupgrades import candidate, scenario, unit


class Surface(HTMLParser):
    """Collect actual document tags independently of escaped text shown to a reader."""

    def __init__(self, tags):
        super().__init__()
        self.tags = tags

    def handle_starttag(self, tag, attrs):
        self.tags.append((tag, attrs))


class CombatUpgradeReportTests(unittest.TestCase):
    """Present complete conditional combat comparisons without introducing damage arithmetic."""

    def test_unknown_spell_policies_are_visible_without_zero_or_empty_policy_defaults(self):
        document = scenario()
        document["baseline"]["spell"].update(damage=None, critical=None, casting=None)
        for item in document["candidates"]:
            item["scenario"]["spell"].update(damage=None, critical=None, casting=None)
        page = render(evaluate(document))
        self.assertTrue("Модель броска</td><td>Неизвестна" in page
                        and "Tick-гипотеза</td><td>Неизвестна" in page
                        and "damage: unavailable" in page and "casting: unavailable" in page
                        and "Нет допущенных вариантов" in page)

    def test_full_combat_comparison_shows_the_independent_delta_and_caller_price(self):
        document = scenario()
        document["baseline"] = unit(173)
        document["candidates"] = [candidate("replacement", unit(211), 19)]
        result = render(evaluate(document))
        self.assertTrue(all(value in result for value in (
            "<!doctype html>", 'lang="ru"', "Условное сравнение боевого DPS",
            "Базовый DPS: <strong>173.0</strong>", "<td>211.0</td>", "<td>38.0</td>",
            "<td>19</td>", "<td>2.0</td>", "synthetic tokens", "Цены заданы вызывающей стороной",
        )))

    def test_forged_values_statuses_traces_and_rankings_cannot_replace_a_recalculated_report(self):
        for path, value in ((("format",), "other"), (("status",), "verified"),
                            (("price_source",), "market"), (("quantity_scope",), "actual_dps"),
                            (("baseline", "dps"), 17), (("baseline", "trace", 0, "factor"), 17),
                            (("baseline", "spell", "expected_hit"), 17),
                            (("candidates", 0, "delta"), 17), (("candidates", 0, "per_cost"), 17),
                            (("candidates", 0, "eligible_for_ranking"), 1),
                            (("ranking",), ["forged"]), (("scenario", "currency"), "changed")):
            with self.subTest(path=path):
                report = evaluate(scenario())
                node = report
                for field in path[:-1]:
                    node = node[field]
                node[path[-1]] = value
                with self.assertRaises(ValueError):
                    render(report)

    def test_blocked_baseline_and_candidates_remain_visible_without_numeric_comparison(self):
        document = scenario()
        document["baseline"]["gates"]["inheritance"]["status"] = "unknown"
        document["baseline"]["missing"] = ["Synthetic baseline coverage gap"]
        document["candidates"][1]["missing"] = ["Synthetic candidate coverage gap"]
        result = render(evaluate(document))
        self.assertTrue(all(value in result for value in (
            "Базовый DPS: <strong>Не рассчитывается</strong>", "Статус baseline: blocked",
            "Synthetic baseline coverage gap", "Synthetic candidate coverage gap", "inheritance: unknown",
            "Нет допущенных вариантов", "<td>blocked</td>", "<td>Не рассчитывается</td>",
        )))

    def test_free_unpriced_and_losing_variants_keep_distinct_ranking_meanings(self):
        document = scenario()
        document["baseline"] = unit(100)
        document["candidates"] = [candidate("paid", unit(140), 5), candidate("free", unit(130), 0),
                                  candidate("unpriced", unit(170), None), candidate("loss", unit(90), 2)]
        result = render(evaluate(document))
        self.assertTrue(all(value in result for value in (
            "Бесплатно (0)", "Цена не задана", "<td>unpriced</td>", "<td>not_upgrade</td>",
            '<ol id=ranking><li>free</li><li>paid</li></ol>', "Бесплатные улучшения",
            "Без известной цены", "Деление на нулевую цену не выполняется",
        )) and "Infinity" not in result)

    def test_complete_target_uptime_and_shared_skill_context_are_visible(self):
        result = render(evaluate(scenario()))
        self.assertTrue(all(value in result for value in (
            "Общие условия", "Навык", "synthetic-cold-spell", "SHA каталога", "d" * 64,
            "Модель броска", "midpoint", "Tick-гипотеза", "Сопротивление Cold", "40%",
            "Пробивание Cold", "10%", "Броня цели", "100 000", "Эффективность брони", "50%",
            "Пробивание брони", "after_effectiveness", "Increased taken", "20%", "Uptime",
            "Полный пул more taken", "target-more", "exposure", "add",
        )))

    def test_spell_and_combat_traces_keep_variant_notes_gates_and_topology_visible(self):
        document = scenario()
        document["baseline"]["notes"] = ["Synthetic baseline combat assertion"]
        document["baseline"]["spell"]["notes"] = ["Synthetic baseline spell assertion"]
        document["candidates"][1]["scenario"]["notes"] = ["Synthetic replacement topology assertion"]
        result = render(evaluate(document))
        self.assertTrue(all(value in result for value in (
            "Трасса spell", "Трасса combat", "Converted Physical range", "Critical expectation",
            "topology", "cold_defence", "armor", "more_taken", "uptime", "Вход", "Выход",
            "Synthetic baseline combat assertion", "Synthetic baseline spell assertion",
            "Synthetic replacement topology assertion", "synthetic:inheritance", "synthetic:conversion",
            "SHA источника сценария", "c" * 64, "Уровень сценария", "Топология варианта",
            "Максимум Tangle", "Дополнительные Tangle", "Допущения spell", "Допущения combat",
            "Gate confirmations are caller assertions", "Нет повторного применения crit, cast или defence",
        )))

    def test_columns_and_limits_describe_a_conditional_model_without_purchase_claims(self):
        result = render(evaluate(scenario()))
        self.assertTrue(all(value in result for value in (
            "<th>Кандидат</th>", "<th>DPS</th>", "<th>Δ DPS</th>", "<th>Изменение</th>",
            "<th>Цена</th>", "<th>Δ DPS / цену</th>", "<th>Статус</th>", "<th>Пробелы и трассы</th>",
            "Рыночные цены не запрашивались", "Не является рекомендацией купить предмет",
            "Пустой список пробелов не подтверждает полноту модели или фактический DPS",
        )))

    def test_all_displayed_caller_text_is_escaped_and_the_document_has_no_active_content(self):
        document = scenario()
        document["currency"] = '<script>currency()</script>'
        document["candidates"][0].update(id='<a href="https://invalid.test">id</a>',
                                          name='<img src=x onerror="candidate()">')
        for model in [document["baseline"], *(row["scenario"] for row in document["candidates"])]:
            model["spell"]["context"]["skill_id"] = '<script>skill()</script>'
            model["notes"] = ['<iframe src="https://invalid.test">note</iframe>']
            model["spell"]["notes"] = ['<b>spell-note</b>']
            model["gates"]["inheritance"]["evidence"] = ['<em>evidence</em>']
            model["target"]["more_taken"][0].update(id='<strong>modifier-id</strong>', affix='<i>affix</i>')
        document["candidates"][1]["missing"] = ['<form action="https://invalid.test">gap</form>']
        result = render(evaluate(document))
        tags = []
        Surface(tags).feed(result)
        self.assertTrue(all(value in result for value in (
            "&lt;script&gt;currency()&lt;/script&gt;", "&lt;script&gt;skill()&lt;/script&gt;",
            "&lt;img src=x onerror=&quot;candidate()&quot;&gt;", "&lt;em&gt;evidence&lt;/em&gt;",
            "&lt;b&gt;spell-note&lt;/b&gt;", "&lt;i&gt;affix&lt;/i&gt;", "&lt;strong&gt;modifier-id&lt;/strong&gt;",
            "&lt;form action=&quot;https://invalid.test&quot;&gt;gap&lt;/form&gt;",
        )) and not any(tag in ("script", "img", "iframe", "form", "link", "a")
                       or any(name.startswith("on") or name in ("src", "href", "action") for name, _ in attrs)
                       for tag, attrs in tags) and '"scenario":' not in result)

    def test_malformed_reports_raise_one_controlled_error_without_payloads(self):
        reports = [None, [], {}, {"scenario": None}, {"scenario": "PRIVATE-REPORT-CANARY"}]
        for field, value in (("extra", {"PRIVATE-REPORT-CANARY"}), ("extra", "PRIVATE-REPORT-CANARY")):
            report = evaluate(scenario())
            report[field] = value
            reports.append(report)
        for value in (float("nan"), float("inf")):
            report = evaluate(scenario())
            report["baseline"]["dps"] = value
            reports.append(report)
        errors = []
        for report in reports:
            with self.subTest(kind=type(report).__name__), self.assertRaises(ValueError) as caught:
                render(report)
            errors.append(str(caught.exception))
        self.assertEqual(set(errors), {"Combat upgrade HTML requires an unchanged evaluated report"})

    def test_json_validation_does_not_confuse_booleans_integers_and_float_results(self):
        document = scenario()
        document["baseline"] = unit(1)
        document["candidates"] = []
        for value in (True, 1):
            with self.subTest(value=value):
                report = evaluate(document)
                report["baseline"]["dps"] = value
                with self.assertRaises(ValueError):
                    render(report)

    def test_rendering_is_deterministic_and_preserves_the_supplied_report(self):
        report = evaluate(scenario())
        original = copy.deepcopy(report)
        first = render(report)
        self.assertEqual((report, render(json.loads(json.dumps(report)))), (original, first))

    def test_zero_baseline_is_known_zero_with_an_undefined_relative_gain(self):
        document = scenario()
        document["baseline"] = unit(0)
        document["candidates"] = [candidate("first-damage", unit(19), 0)]
        result = render(evaluate(document))
        self.assertTrue(all(value in result for value in (
            "Базовый DPS: <strong>0.0</strong>", "<td>19.0</td>", "<td>Не рассчитывается</td>",
            "При нулевом baseline относительное изменение не определено", "<td>free</td>",
        )) and "Infinity" not in result)

    def test_a_blocked_candidate_does_not_promote_or_block_the_independent_baseline(self):
        document = scenario()
        document["baseline"] = unit(173)
        document["candidates"] = [candidate("unknown-effect", unit(211), 19)]
        document["candidates"][0]["missing"] = ["Synthetic unresolved effect"]
        result = render(evaluate(document))
        self.assertTrue(all(value in result for value in (
            "Статус baseline: conditional", "<td>blocked</td>", "Synthetic unresolved effect",
            "<td>Не рассчитывается</td>", "Нет допущенных вариантов",
        )))
