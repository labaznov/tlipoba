"""Synthetic upgrade HTML without player inputs or market services."""

import copy
import unittest

from damage_lab.upgrades import evaluate
from damage_lab.upgradereport import render
from test_upgrades import candidate, scenario


class UpgradeReportTests(unittest.TestCase):
    """Display conditional comparisons without promoting them to purchase advice."""

    def test_ranked_report_shows_explicit_prices_and_supported_delta(self):
        document = scenario()
        document["candidates"] = [candidate("paid", 0.25, 17)]
        result = render(evaluate(document))
        self.assertTrue(all(value in result for value in (
            "<!doctype html>", 'lang="ru"', "Условное сравнение улучшений", "Цены заданы вызывающим кодом",
            "synthetic token", "Базовый DPS", "1 000", "1 250", "250", "25%", "paid",
            "Рейтинг по заданной стоимости", "Не является подтверждённой рекомендацией купить предмет",
        )))

    def test_report_cannot_promote_conditional_results_or_caller_prices(self):
        for path, value in ((("format",), "other-v1"), (("status",), "verified"), (("price_source",), "market"),
                            (("baseline", "status"), "exact"), (("candidates", 0, "result", "status"), "exact")):
            document = scenario()
            document["candidates"] = [candidate("priced", 0.25, 17)]
            report = evaluate(document)
            row = report
            for field in path[:-1]:
                row = row[field]
            row[path[-1]] = value
            with self.subTest(path=path), self.assertRaises(ValueError):
                render(report)

    def test_free_unknown_and_incomplete_candidates_keep_distinct_cost_meanings(self):
        document = scenario()
        document["candidates"] = [candidate("no-charge", 0.5, 0), candidate("unknown-price", 0.75, None),
                                  candidate("blocked-effect", 0.9, 3)]
        document["candidates"][2]["missing"] = ["Unmapped synthetic activation"]
        result = render(evaluate(document))
        self.assertTrue(all(value in result for value in (
            "Бесплатно (0)", "Цена не задана", "Не рассчитывается", "free", "unpriced", "incomplete",
            "Unmapped synthetic activation", '<ol id=ranking><li>no-charge</li></ol>',
        )))

    def test_report_displays_shared_conditions_without_candidate_overrides(self):
        document = scenario()
        document["combat"].update(tick_frequency=30, armor=50000)
        result = render(evaluate(document))
        self.assertTrue(all(value in result for value in (
            "Панель, reference и условия общие для всех вариантов", "Основа", "panel", "Активные Tangle",
            "Попаданий за каст", "Остаток shotgun", "25%", "Сопротивление цели", "Внешний taken", "Uptime",
            "100%", "Tick-гипотеза", "30 Hz", "Броня цели", "50 000", "Нефизический урон",
        )))

    def test_ranking_cannot_include_ineligible_unknown_or_duplicate_ids(self):
        for identities in (["blocked"], ["unknown"], ["paid", "paid"]):
            document = scenario()
            document["candidates"] = [candidate("paid", 0.25, 17), candidate("blocked", 0.75, 3)]
            document["candidates"][1]["missing"] = ["Unknown synthetic interaction"]
            report = evaluate(document)
            report["ranking"] = identities
            with self.subTest(identities=identities), self.assertRaises(ValueError):
                render(report)

    def test_eligibility_flags_must_be_strict_booleans_without_incomplete_claims(self):
        for field, value in (("eligible_for_ranking", 1), ("eligible_for_cost_ranking", "true"),
                             ("status", "incomplete"), ("status", "verified")):
            document = scenario()
            document["candidates"] = [candidate("paid", 0.25, 17)]
            report = evaluate(document)
            report["candidates"][0][field] = value
            with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                render(report)

    def test_shared_gaps_and_calculation_evidence_remain_visible_when_ranking_is_blocked(self):
        document = scenario()
        document["combat"].update(missing=["Shared synthetic gap"], notes=["Shared synthetic assumption"])
        document["candidates"] = [candidate("blocked", 0.25, 17)]
        result = render(evaluate(document))
        self.assertTrue(all(value in result for value in (
            "Общие пробелы", "Shared synthetic gap", "Трассировка и допущения", "Shared synthetic assumption",
            "Панельный Spell DPS", "Нет допущенных вариантов", "Не учтено: Shared synthetic gap",
            "<ol id=ranking></ol>",
        )))

    def test_html_escapes_caller_text_and_keeps_the_document_passive(self):
        document = scenario()
        document["currency"] = "<script>currency()</script>"
        document["candidates"] = [candidate("markup", 0.25, 17)]
        document["candidates"][0]["name"] = '<img src=x onerror="candidate()">'
        document["combat"]["notes"] = ["<em>assumption</em>"]
        result = render(evaluate(document))
        self.assertTrue(all(value in result for value in (
            "&lt;script&gt;currency()&lt;/script&gt;", "&lt;img src=x onerror=&quot;candidate()&quot;&gt;",
            "&lt;em&gt;assumption&lt;/em&gt;",
        )) and "<script" not in result and "<img" not in result and "<form" not in result)

    def test_unknown_private_fields_and_unrecognised_verified_flags_are_not_rendered(self):
        document = scenario()
        document["candidates"] = [candidate("paid", 0.25, 17)]
        report = evaluate(document)
        for row in (report, report["baseline"], report["baseline"]["trace"][0], report["candidates"][0],
                    report["candidates"][0]["result"], report["scenario"], report["scenario"]["panel"],
                    report["scenario"]["condition"], report["scenario"]["combat"]):
            row["sourceSections"] = {"accountId": "PRIVATE-UPGRADE-CANARY"}
            row["market_verified"] = "PRIVATE-UPGRADE-CANARY"
        report["verified"] = True
        self.assertNotIn("PRIVATE-UPGRADE-CANARY", render(report))

    def test_hit_mode_discloses_its_shared_critical_assumptions(self):
        document = scenario()
        document["condition"].update(basis="hit", lucky=True, critical_more=0.26)
        document["panel"].update(hit_min=137, hit_max=173, crit_chance=0.4137, crit_multiplier=2.87)
        result = render(evaluate(document))
        self.assertTrue(all(value in result for value in (
            "Lucky", "Критический more", "26%", "Минимальный hit", "137", "Максимальный hit", "173",
            "Шанс крита панели", "41.37%", "Критический множитель", "2.87",
        )))

    def test_zero_baseline_and_zero_price_do_not_become_unknown_zeroes_or_infinity(self):
        document = scenario()
        document["panel"]["spell_dps"] = 0
        document["candidates"] = [candidate("zero", 0.25, 0)]
        result = render(evaluate(document))
        self.assertTrue(result.count("Не рассчитывается") >= 2 and "Бесплатно (0)" in result
                        and "not_upgrade" in result and "Infinity" not in result and "None" not in result)

    def test_rendering_does_not_mutate_the_comparison_or_scenario(self):
        document = scenario()
        document["candidates"] = [candidate("paid", 0.25, 17)]
        report = evaluate(document)
        previous = copy.deepcopy(report)
        render(report)
        self.assertEqual(report, previous)

    def test_selected_shared_armor_hypothesis_keeps_its_true_units(self):
        document = scenario()
        document["panel"]["armor_penetration"] = 0.08
        document["combat"].update(armor=50000, armor_penetration="panel", armor_effectiveness=0.6,
                                  armor_penetration_order="after_effectiveness")
        result = render(evaluate(document))
        self.assertTrue(all(value in result for value in (
            "Пробивание брони", "8%", "Эффективность брони", "60%", "Порядок брони (гипотеза)",
            "after_effectiveness", "Источник пробивания", "panel",
        )))
