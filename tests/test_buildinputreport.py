import copy
from pathlib import Path
import tempfile
import unittest
from html.parser import HTMLParser
from unittest.mock import patch

from damage_lab.buildinputreport import render


def report():
    """Assemble synthetic imported evidence through the public input contract."""
    from damage_lab.buildinputs import assemble
    from test_buildinputs import record

    return assemble(record(), skill_alias="gem[1]")


def castreport(alias):
    """Assemble fictional own cast-row evidence through the canonical ledger contract."""
    from damage_lab.buildinputs import assemble
    from damage_lab.staticcombat import project
    from test_buildinputs import record
    from test_staticcombat import casted

    value = record()
    value["static_combat"] = project(casted(), "a" * 64)
    return assemble(value, skill_alias=alias)


class Surface(HTMLParser):
    """Record actual HTML tags and resource attributes independently of displayed text."""

    def __init__(self, tags):
        super().__init__()
        self.tags = tags

    def handle_starttag(self, tag, attrs):
        self.tags.append((tag, dict(attrs)))


class BuildInputReportTests(unittest.TestCase):
    """Show automatic candidate inputs without resolving unknown effects or computing damage."""

    def test_a_standalone_russian_report_keeps_blocked_inputs_separate_from_damage(self):
        page = render(report())
        self.assertTrue(all(value in page for value in (
            "<!doctype html>", 'lang="ru"', "Автоматические входы расчёта DPS", "DPS пока не рассчитывается",
            "Явный выбор камня", "gem[1]", "Каталожные поля на уровне камня", "Кандидаты модификаторов",
            "Наблюдаемая группа", "Пробелы расчёта", "effective level", "неизвестно",
        )))

    def test_the_real_blocked_raw_model_shows_context_unavailable_groups_and_evaluator_gaps(self):
        page = render(report())
        self.assertTrue(all(value in page for value in (
            "Модель rawspell и evaluator", "Статус evaluator: blocked", "synthetic-guid", "c" * 64,
            "damage: unavailable", "critical: unavailable", "casting: unavailable", "version: unknown",
            "level: unknown", "base: unknown", "conversion: unknown", "damage</td><td>неизвестно",
            "Числовой DPS: неизвестно", "Сценарий rawspell передан evaluator и заблокирован",
        )) and "Сценарий rawspell не создан" not in page)

    def test_a_missing_raw_context_is_visible_without_borrowing_the_first_profiles_identity(self):
        from damage_lab.buildinputs import assemble
        from test_buildinputs import record

        value = record()
        value["installed_skill_profiles"]["members"][0]["profile"]["identity"].update(guid=None, guidStatus="absent")
        page = render(assemble(value, skill_alias="gem[1]"))
        self.assertTrue("Контекст rawspell не создан" in page and "raw_spell_context_unavailable" in page
                        and "Статус evaluator: blocked" not in page and "synthetic-guid" not in page)

    def test_derived_raw_inputs_and_results_cannot_be_forged_after_assembly(self):
        for path, value in ((("raw_spell",), None), (("raw_result",), None), (("raw_result", "status"), "conditional"),
                            (("raw_result", "pre_defence_dps"), 731), (("raw_result", "gaps"), []),
                            (("raw_spell", "context", "catalog_sha256"), "b" * 64),
                            (("raw_spell", "casting"), {"interval": 1, "increased": 0, "more": [], "frequency": None})):
            with self.subTest(path=path):
                data = report()
                node = data
                for name in path[:-1]:
                    node = node[name]
                node[path[-1]] = value
                with self.assertRaisesRegex(ValueError, "^Build input HTML requires an unchanged assembled report$"):
                    render(data)

    def test_full_gear_cast_evidence_is_displayed_separately_from_applied_modifiers(self):
        page = render(castreport("gem[1]"))
        self.assertTrue(all(value in page for value in (
            "Значения скорости без арифметики", "17.8750", "7.1250 … 41.625%", "Собственные значения",
            "Specs каталога", "+#% Minion Cast Speed", "value_role: unresolved", "activation: unknown",
            "соответствие эффектам не выбрано", "строки не добавлены в cast speed или DPS",
        )))

    def test_gear_observations_are_not_filtered_by_an_unobserved_skill_alias(self):
        value = castreport("gem[999]")
        page = render(value)
        self.assertTrue("Значения скорости без арифметики" in page and "17.8750" in page
                        and value["modifiers"] is None and value["raw_spell"] is None and value["status"] == "blocked")

    def test_legacy_ledgers_and_missing_static_inventory_do_not_create_cast_evidence_sections(self):
        from damage_lab.buildinputs import assemble
        from test_buildinputs import record

        value = record()
        value.pop("static_combat")
        self.assertTrue(all("Значения скорости без арифметики" not in render(candidate)
                            for candidate in (report(), assemble(value, skill_alias="gem[1]"))))

    def test_cast_renderer_errors_use_the_existing_fixed_report_error_without_private_echo(self):
        def unavailable(record):
            raise ValueError("PRIVATE-CAST-INPUT-CANARY")

        with patch("damage_lab.report.castdetails", unavailable), self.assertRaisesRegex(
                ValueError, "^Build input HTML requires an unchanged assembled report$"):
            render(castreport("gem[1]"))

    def test_cast_evidence_keeps_the_existing_missing_inputs_and_raw_spell_blocked(self):
        from damage_lab.buildinputs import assemble
        from damage_lab.staticcombat import project
        from test_buildinputs import record
        from test_staticcombat import casted

        raw = casted()
        raw["version"] = "0.4.0"
        del raw["omitted"][0]["evidence"]
        value = record()
        value["static_combat"] = project(raw, "a" * 64)
        before = assemble(value, skill_alias="gem[1]")
        after = castreport("gem[1]")
        self.assertEqual((after["gaps"], after["raw_spell"], after["status"], after["arithmetic_ready"]),
                         (before["gaps"], before["raw_spell"], before["status"], False))

    def test_cast_evidence_html_drops_opaque_payloads_and_remains_passive(self):
        from damage_lab.buildinputs import assemble
        from damage_lab.staticcombat import project
        from test_buildinputs import record
        from test_staticcombat import casted

        raw = casted()
        raw["omitted"][0]["evidence"]["opaque"] = '<img src=x onerror="PRIVATE-CAST-INPUT-CANARY">'
        value = record()
        value["static_combat"] = project(raw, "a" * 64)
        page = render(assemble(value, skill_alias="gem[1]"))
        tags = []
        Surface(tags).feed(page)
        self.assertTrue("PRIVATE-CAST-INPUT-CANARY" not in page
                        and not any(tag in {"script", "img", "iframe", "object", "embed", "link", "form", "input"}
                                    or any(name.startswith("on") or name in {"src", "href", "action"} for name in attributes)
                                    for tag, attributes in tags))

    def test_source_bound_level_candidates_are_displayed_without_deriving_inputs_or_damage(self):
        from damage_lab.buildinputs import assemble
        from test_importer import leveled

        value = assemble(leveled(), skill_alias="gem[1]")
        original = copy.deepcopy(value)
        page = render(value)
        self.assertTrue(all(text in page for text in (
            "Кандидаты прибавок к уровню навыков", "Effective level: неизвестно", "Кандидаты не складываются",
            "DPS не рассчитан", "91437", "2.70", "Собственные роллы предметов", "Каталожные литералы",
            "network_bytes_verified: false", "current_patch_verified: false", "rank_scaling_unknown",
        )) and value == original and value["status"] == "blocked" and value["raw_spell"] is None)

    def test_legacy_reports_have_no_level_candidate_section(self):
        self.assertNotIn("Кандидаты прибавок к уровню навыков", render(report()))

    def test_the_level_section_keeps_every_target_even_when_the_requested_alias_is_unobserved(self):
        from damage_lab.archive import archive
        from damage_lab.buildinputs import assemble
        from test_damage_archive import attachedlevels, facts, package

        with tempfile.TemporaryDirectory() as folder:
            directory = Path(folder)
            path = package(directory)
            attachedlevels(path)
            record = archive(path, None, facts(directory), directory / "out.sqlite")
            value = assemble(record, skill_alias="gem[999]")
            page = render(value)
            self.assertTrue(all("<h3>Цель " + str(identity) + "</h3>" in page for identity in (90017, 90029, 90041, 90053))
                            and value["skill"] is None and value["raw_spell"] is None)

    def test_null_forged_or_extra_level_evidence_cannot_bypass_the_existing_report_guard(self):
        from damage_lab.buildinputs import assemble
        from test_importer import leveled

        for change in ("null", "level", "flag", "count", "extra"):
            with self.subTest(change=change):
                value = assemble(leveled(), skill_alias="gem[1]")
                bundle = value["record"]["installed_level_candidates"]
                if change == "null":
                    value["record"]["installed_level_candidates"] = None
                elif change == "level":
                    bundle["targets"]["91437"]["effective_level"] = 37
                elif change == "flag":
                    bundle["runtime_verified"] = True
                elif change == "count":
                    bundle["accounting"]["candidates"] += 1
                else:
                    bundle["opaque"] = "PRIVATE-LEVEL-INPUT-CANARY"
                with self.assertRaisesRegex(ValueError, "^Build input HTML requires an unchanged assembled report$"):
                    render(value)

    def test_the_level_candidate_section_remains_passive_without_external_resources(self):
        from damage_lab.buildinputs import assemble
        from test_importer import leveled

        tags = []
        Surface(tags).feed(render(assemble(leveled(), skill_alias="gem[1]")))
        self.assertFalse(any(tag in {"script", "img", "iframe", "object", "embed", "link", "form", "input"}
                             or any(name.startswith("on") or name in {"src", "href", "action"} for name in attributes)
                             for tag, attributes in tags))

    def test_malformed_reports_fail_without_echoing_private_payloads(self):
        for value in (None, [], True, {}, {"record": {}}, {"record": {}, "selection": None},
                      {"record": {}, "selection": {"opaque": "PRIVATE-BUILD-INPUT-CANARY"}}):
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, "^Build input HTML requires an unchanged assembled report$"):
                render(value)

    def test_forged_gates_selection_source_values_and_extra_properties_are_refused(self):
        for path, value in ((("status",), "conditional"), (("arithmetic_ready",), 0),
                            (("runtime_verified",), True), (("identity_verified",), True), (("import_complete",), True),
                            (("source_sha256",), "b" * 64), (("selection", "basis"), "automatic_main_skill"),
                            (("selection", "alias"), "gem[999]"), (("raw_spell",), {}),
                            (("gaps",), []), (("opaque",), "PRIVATE-BUILD-INPUT-CANARY")):
            with self.subTest(path=path):
                value_report = report()
                node = value_report
                for name in path[:-1]:
                    node = node[name]
                node[path[-1]] = value
                with self.assertRaises(ValueError):
                    render(value_report)

    def test_passive_html_contains_no_scripts_requests_or_active_elements(self):
        tags = []
        Surface(tags).feed(render(report()))
        self.assertFalse(any(tag in {"script", "img", "iframe", "object", "embed", "link", "form", "input"}
                             or any(name.startswith("on") or name in {"src", "href", "action"} for name in attributes)
                             for tag, attributes in tags))

    def test_rendering_is_deterministic_without_changing_assembled_inputs(self):
        value = report()
        original = copy.deepcopy(value)
        page = render(value)
        self.assertEqual((value, render(value)), (original, page))

    def test_catalog_fields_keep_lexical_values_source_identity_and_unknown_effective_level(self):
        page = render(report())
        self.assertTrue(all(value in page for value in (
            "90017", "a" * 64, "11 – 19", "catalog_render_consistent", "117.5%", "1.175", "0.73 s",
            "intelligence", "activation_medium", "projectile", "spell", "Имена атрибутов не являются их итоговыми значениями",
            "arithmetic_ready: false", "runtime_verified: false", "identity_verified: false", "import_complete: false",
            "effective_level_unknown", "critical_pools_unresolved", "cast_pools_unresolved", "conversion_unverified",
        )))

    def test_modifier_rows_keep_each_family_scope_exact_value_source_and_exclusion(self):
        from damage_lab.buildinputs import assemble
        from test_buildinputs import record
        from test_ledgerinputs import ledger, percent

        value = record()
        value["static_combat"] = ledger({},
            {"family": "increased_damage", "scope": "any", "targets": ["damage"], "unit": "percent",
             "values": percent("17.30", "0.1730")},
            {"family": "flat_attribute", "scope": "any", "targets": ["intelligence"], "unit": "flat",
             "values": [{"exact": "37.0", "source": "DynArgs[0]"}]},
            {"family": "increased_speed", "scope": "any", "targets": ["cast_speed"], "unit": "percent",
             "values": percent("23.70", "0.2370")},
            {"scope": "attack", "appliesToPlayerSpell": False},
            {"family": "increased_damage", "owner": "minion", "scope": "any", "targets": ["damage"],
             "unit": "percent", "values": percent("13.70", "0.1370"), "appliesToPlayerSpell": False})
        page = render(assemble(value, skill_alias="gem[1]"))
        self.assertTrue(all(value in page for value in (
            "Добавленный урон", "Increased damage", "Атрибуты", "Скорость: только инвентарь", "Исключённые строки",
            "11.0", "21.0", "17.30", "0.1730", "37.0", "23.70", "0.2370", "13.70", "0.1370",
            "source_path", "DynArgs[0]", "scope_not_skill_tag", "owner_not_player", "damage_scope", "unresolved",
            "Строки не суммированы", "omitted_rows", "structural_gaps",
        )))

    def test_support_rolls_and_catalog_literals_have_separate_origins_without_activation_claims(self):
        page = render(report())
        self.assertTrue(all(value in page for value in (
            "Нативные роллы", "Каталожные константы", "24.125", "0.24125", "native_prefix_row", "catalog_literal",
            "Пропуски и неизвестные константы", "additional_group_identity", "unresolved", "observed_group_only",
            "Совместное размещение не доказывает активацию или применимость поддержки",
        )) and page.index("Нативные роллы") < page.index("native_prefix_row") < page.index("Каталожные константы"))

    def test_unavailable_profile_modifiers_and_supports_remain_unknown_instead_of_zero(self):
        from damage_lab.buildinputs import assemble
        from test_buildinputs import record

        value = record()
        for key in ("installed_skill_profiles", "static_combat", "installed_support_effects", "installed_support_catalog"):
            value.pop(key)
        page = render(assemble(value, skill_alias="gem[1]"))
        self.assertTrue(all(value in page for value in (
            "unavailable", "Выбранный установленный камень неизвестен", "Типизированные модификаторы неизвестны",
            "Состав группы неизвестен", "profile_catalog_unavailable", "static_ledger_unavailable",
            "support_inventory_unavailable", "неизвестные значения не заменены нулями",
        )) and "11 – 19" not in page and "24.125" not in page)

    def test_an_unobserved_selection_cannot_display_the_first_gems_catalog_or_supports(self):
        from damage_lab.buildinputs import assemble
        from test_buildinputs import record

        page = render(assemble(record(), skill_alias="gem[999]"))
        self.assertTrue(all(value in page for value in ("gem[999]", "not_observed", "skill_not_observed"))
                        and "90017" not in page and "24.125" not in page and "11 – 19" not in page)

    def test_catalog_field_gaps_are_visible_without_numeric_fallbacks(self):
        from damage_lab.buildinputs import assemble
        from test_buildinputs import record

        value = record()
        profile = value["installed_skill_profiles"]["members"][0]["profile"]
        profile["hit"] = {"status": "level_not_in_table"}
        profile["effectivenessOfAddedDamage"] = {"status": "not_stated", "text": None, "value": None}
        profile["castSpeedField"] = {"status": "invalid", "text": None, "seconds": None}
        page = render(assemble(value, skill_alias="gem[1]"))
        self.assertTrue(all(value in page for value in (
            "Кандидат базового диапазона lookup: неизвестно", "level_not_in_table", "not_stated", "invalid",
        )) and "11 – 19" not in page and "117.5%" not in page and "0.73 s" not in page)

    def test_malformed_record_containers_are_refused_with_the_static_error(self):
        value = report()
        value["record"]["stats"] = []
        with self.assertRaisesRegex(ValueError, "^Build input HTML requires an unchanged assembled report$"):
            render(value)

    def test_nonfinite_and_cyclic_extra_payloads_cannot_be_serialized_into_html(self):
        for change in ("nonfinite", "cycle"):
            with self.subTest(change=change):
                value = report()
                value["opaque"] = float("nan") if change == "nonfinite" else value
                with self.assertRaises(ValueError):
                    render(value)

    def test_unused_record_text_and_inventory_trees_are_not_dumped_into_the_report(self):
        from damage_lab.buildinputs import assemble
        from test_buildinputs import record

        value = record()
        value["name"] = '<script>PRIVATE-UNUSED-INPUT-CANARY</script>'
        value["inventory"]["gear"][0]["details"] = ['<img src=x onerror="PRIVATE-UNUSED-INPUT-CANARY">']
        self.assertNotIn("PRIVATE-UNUSED-INPUT-CANARY", render(assemble(value, skill_alias="gem[1]")))
