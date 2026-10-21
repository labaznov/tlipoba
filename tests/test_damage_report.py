import unittest

from damage_lab.report import render, render_import, scenarios, staticdetails


def static():
    """Return a source-bound fictional static ledger with one structural gap."""
    from damage_lab.staticcombat import project
    from test_staticcombat import document

    return project(document(), "a" * 64)


class StaticReportTests(unittest.TestCase):
    """Expose static inventory evidence without treating it as applied damage."""

    def test_both_reports_keep_critical_operation_unresolved_and_arithmetic_disabled(self):
        from damage_lab.staticcombat import project
        from test_staticcombat import critical

        data = project(critical("critical_damage_modifier", "spell"), "a" * 64)
        self.assertTrue(all(all(value in page for value in (
            "unresolved", "arithmetic_ready", "false", "Критических строк без арифметики: 1",
            "Аффиксы не применены к DPS",
        )) for page in pages({"static_combat": data})))

    def test_both_reports_show_partial_static_evidence_and_counts(self):
        self.assertTrue(all(all(value in page for value in (
            "Статические аффиксы вещей", "Наблюдаемых строк: 2", "Типизировано: 1",
            "Пропущено: 1", "Структурных пробелов: 1", "known_rows_only",
            "compiled_unverified_runtime", "Аффиксы не применены к DPS",
        )) for page in pages({"static_combat": static()})))

    def test_static_report_preserves_values_paths_and_input_catalog_hash(self):
        self.assertTrue(all(value in staticdetails({"static_combat": static()}) for value in (
            "11.0", "21.0", "sections.WearItems.data[0]", "b" * 64,
            "no_exact_definition", "invalid_affix_container", "gear[0]",
        )))

    def test_static_report_revalidates_verification_flags(self):
        data = static()
        data["runtime"]["verified"] = True
        with self.assertRaises(ValueError):
            staticdetails({"static_combat": data})

    def test_static_report_rejects_a_ledger_from_a_different_record_source(self):
        with self.assertRaises(ValueError):
            staticdetails({"source_sha256": "c" * 64, "static_combat": static()})

    def test_static_report_accepts_the_same_explicit_record_source(self):
        self.assertIn("Статические аффиксы вещей", staticdetails({
            "source_sha256": "a" * 64, "static_combat": static(),
        }))

    def test_static_report_drops_unknown_private_fields_at_every_level(self):
        data = static()
        for row in (data, data["runtime"], data["items"][0], data["modifiers"][0],
                    data["modifiers"][0]["values"][0], data["modifiers"][0]["definition"]):
            row["private"] = {"nested": "PRIVATE-STATIC-CANARY"}
        self.assertNotIn("PRIVATE-STATIC-CANARY", staticdetails({"static_combat": data}))

    def test_static_report_without_a_ledger_is_empty(self):
        self.assertEqual(staticdetails({}), "")


def ranks():
    """Return fictional unresolved ranks and memory coordinates without user data."""
    prefix = "sections.HeroCharacter.data.HeroJewels[2]._Raw_Data."
    return {
        "format": "tli-trait-rank-candidates-v1", "rule_status": "rank_rule_unverified",
        "source_sha256": "a" * 64,
        "traits": [{"trait_id": 9000731, "index": 0, "rank": None, "memory_position": 2,
                    "status": "rank_rule_unverified", "candidates_agree": False,
                    "candidates": [{"rule": "client_fixed", "formula": "C", "value": 3,
                                    "status": "rank_rule_unverified", "inputs": [prefix + "ReminiscenceFixedLevel"]},
                                   {"rule": "client_plus_enhance", "formula": "C + E", "value": 5,
                                    "status": "rank_rule_unverified", "inputs": []}]}],
        "memories": [{"position": 2, "base_id": 9000583,
                      "fields": {key: {"path": prefix + field, "status": "ok", "value": value}
                                 for key, field, value in (
                                     ("client_fixed", "ReminiscenceFixedLevel", 3),
                                     ("from_enhance", "ReminiscenceFixedLevelFromEnhance", 2),
                                     ("server_fixed", "ServerPlayerItem.ReminiscenceFixedLevel", 1),
                                     ("level", "ReminiscenceLevel", 37))},
                      "fixed_affix_contribution": 2, "fixed_affix_source": prefix + "ServerPlayerItem.BaseAffix",
                      "consistency": "consistent", "linkage": {"status": "index_match", "slot": 3}}],
        "memories_without_selected_trait": [], "assumptions": ["Синтетические кандидаты"],
        "gaps": ["Нет подтверждённого правила ранга"],
    }


def pages(record):
    """Render both public report entry points with a neutral synthetic calculation."""
    return [render_import(record), render(record, {"dps": 127319, "trace": [], "assumptions": []}, {
        "basis": "panel", "active": 2, "hits": 3, "retention": 0.2, "resistance": 0.23,
        "taken": 0.11, "uptime": 0.87,
    })]


def coverage():
    """Return fictional import evidence without asserting combat activation."""
    return {
        "format": "tli-import-coverage-v1", "version": "0.2.0", "tool": "synthetic-coverage", "import_complete": False,
        "source": {"sha256": "c" * 64, "captured_at": "2026-02-19T08:37:11Z", "captured_at_status": "observed"},
        "guide": {"supplied": True, "sha256": "d" * 64, "binding": "unverified"},
        "domains": {name: {"composition": "observed", "effective": "unverified", "paths": [], "counts": {}}
                    for name in ("equipment", "skill_layout", "hero_traits", "talents", "slates", "pactspirits",
                                 "native_stats", "panel_skill_identity", "support_activation")},
        "gaps": [{"domain": "support_activation", "composition": "observed", "gap": "Synthetic activation gap",
                  "next": "Synthetic next evidence"}], "rules": [],
    }


def resolution():
    """Return a validated synthetic saved-controller assessment."""
    from damage_lab.buildresolution import project
    from test_buildresolution import document

    return project(document(), "a" * 64)


class BuildResolutionReportTests(unittest.TestCase):
    """Saved-code comparisons remain distinct from verified build identity."""

    def test_both_reports_show_the_saved_claim_without_promoting_identity(self):
        self.assertTrue(all(all(value in result for value in (
            "Проверка сохранённого снимка", "matched_saved_code", "совпадение с сохранённым полем",
            "transport.verified: false", "payload_self_identifies: false", "freshness.status: unknown",
            "Сравнение кода не подтверждает идентичность пэйлоада или свежесть",
        )) for result in pages({"build_resolution": resolution()})))

    def test_both_reports_show_redacted_source_and_candidate_metadata(self):
        data = resolution()
        data["identity"].update(descriptor_match="candidate_match", capture_verified_flag=True)
        self.assertTrue(all(all(value in result for value in (
            "tli-build-resolution-v0", "0.1.1", "a" * 64, "sha256:0b73e19a", "saved_controller_code",
            "descriptor_match: candidate_match", "Кандидатная сверка дескриптора",
            "capture_verified_flag: true", "Флаг захвата не является уровнем верификации",
        )) for result in pages({"build_resolution": data})))

    def test_both_reports_show_gate_coverage_paths_and_unestablished_freshness(self):
        self.assertTrue(all(all(value in result for value in (
            "Статус доступа: allowed", "feature_status: Feature_CanView", "real_feature_status: Feature_CanView",
            "data_version.first: 7", "data_version.second: 113", "Сравнений версий аффиксов: 11",
            "Расхождений версий: 0", "WearItems", "captured", "required_missing: нет",
            "2026-02-04T07:08:09+03:00", "captured_at_status: valid", "2026-02-03T04:05:06+00:00",
            "payload_generated_at: не установлено", "is_old_data: not_captured",
            "buildIdentity.buildCode", "sections.ServerSource.data.**.Version (affix records)",
        )) for result in pages({"build_resolution": resolution()})))

    def test_reports_reject_transport_identity_or_freshness_proof_claims(self):
        for section, key, value in (("transport", "verified", True), ("transport", "verified", 0),
                                    ("identity", "payload_self_identifies", True), ("identity", "payload_self_identifies", 0),
                                    ("freshness", "status", "fresh")):
            data = resolution()
            data[section][key] = value
            with self.subTest(section=section, key=key), self.assertRaises(ValueError):
                pages({"build_resolution": data})

    def test_both_reports_ignore_unknown_private_resolution_properties(self):
        data = resolution()
        for row in (data, data["source"], data["transport"], data["identity"], data["gate"], data["freshness"],
                    data["coverage"], data["coverage"]["data_version"], data["coverage"]["affix_versions"], data["coverage"]["sections"]):
            row["rawAccount"] = {"private": "PRIVATE-RESOLUTION-CANARY"}
        self.assertTrue(all("PRIVATE-RESOLUTION-CANARY" not in result for result in pages({"build_resolution": data})))

    def test_raw_codes_and_markup_cannot_enter_the_redacted_resolution_fields(self):
        for section, key, value in (("identity", "code_fingerprint", "AAECAwQFBgcICQoLDA0ODw=="),
                                    ("source", "sha256", "<script>raw()</script>"),
                                    ("identity", "basis", "<script>raw()</script>")):
            data = resolution()
            data[section][key] = value
            with self.subTest(section=section, key=key), self.assertRaises(ValueError):
                pages({"build_resolution": data})

    def test_legacy_reports_without_resolution_remain_optional(self):
        self.assertTrue(all("Проверка сохранённого снимка" not in result for result in pages({})))

    def test_unbound_claims_remain_visible_with_a_candidate_descriptor(self):
        data = resolution()
        data["status"] = "unbound"
        data["identity"].update(expected_code_matched=None, descriptor_match="candidate_match", capture_verified_flag=True)
        self.assertTrue(all(all(value in result for value in (
            "Статус сохранённого снимка: unbound", "совпадение с сохранённым полем: null",
            "descriptor_match: candidate_match", "freshness.status: unknown",
        )) for result in pages({"build_resolution": data})))


class ImportCoverageReportTests(unittest.TestCase):
    """Show composition evidence separately from unresolved effective mechanics."""

    def test_both_reports_show_import_coverage_as_incomplete_evidence(self):
        self.assertTrue(all(all(value in result for value in (
            "Покрытие импорта", "import_complete: false", "Импорт остаётся неполным",
            "Состав", "Эффекты", "support_activation", "observed", "unverified",
            "Наблюдение не подтверждает активацию", "Synthetic activation gap", "Synthetic next evidence",
        )) for result in pages({"import_coverage": coverage()})))

    def test_import_coverage_cannot_claim_a_complete_or_unspecified_import(self):
        for value in (True, None, 0, "false"):
            with self.subTest(value=value):
                data = coverage()
                data["import_complete"] = value
                with self.assertRaisesRegex(ValueError, "incomplete"):
                    pages({"import_coverage": data})

    def test_both_reports_keep_import_source_and_guide_provenance(self):
        self.assertTrue(all(all(value in result for value in (
            "tli-import-coverage-v1", "Версия: 0.2.0", "c" * 64, "2026-02-19T08:37:11Z",
            "Статус времени: observed", "Сопроводительные данные: предоставлены", "d" * 64,
            "Связь с источником: unverified",
        )) for result in pages({"import_coverage": coverage()})))

    def test_both_reports_escape_import_coverage_text(self):
        data = coverage()
        data["gaps"][0]["gap"] = "<script>coverage()</script>"
        data["rules"] = ["<em>coverage rule</em>"]
        data["domains"]["equipment"]["paths"] = ["<b>coverage path</b>"]
        self.assertTrue(all(all(value in result for value in (
            "&lt;script&gt;coverage()&lt;/script&gt;", "&lt;em&gt;coverage rule&lt;/em&gt;", "&lt;b&gt;coverage path&lt;/b&gt;",
        )) and "<script>coverage()</script>" not in result
                            for result in pages({"import_coverage": data})))

    def test_both_reports_show_domain_provenance_without_turning_gaps_into_zeroes(self):
        data = coverage()
        data["domains"]["equipment"]["paths"] = ["sections.SyntheticEquipment.data"]
        data["domains"]["skill_layout"].update(composition="empty", effective="unknown")
        data["domains"]["talents"].update(composition="invalid", effective="unknown")
        data["domains"]["pactspirits"].update(composition="absent", effective="unknown")
        self.assertTrue(all(all(value in result for value in (
            "Пути источника", "sections.SyntheticEquipment.data", "empty", "invalid", "absent", "unknown",
            "Не извлечено",
        )) for result in pages({"import_coverage": data})))

    def test_both_reports_show_named_counts_and_coverage_rules(self):
        data = coverage()
        data["domains"]["equipment"]["counts"] = {"items": 7, "affixes_without_rolls": 13, "invalid_affixes": 0}
        data["domains"]["support_activation"]["counts"] = {"installed_supports": 19}
        data["rules"] = ["Synthetic installed skills never imply activation"]
        self.assertTrue(all(all(value in result for value in (
            "synthetic-coverage", "Количество", "items: 7", "affixes_without_rolls: 13", "invalid_affixes: 0",
            "installed_supports: 19", "Synthetic installed skills never imply activation",
        )) for result in pages({"import_coverage": data})))

    def test_both_reports_keep_known_domain_limits_separate_from_activation(self):
        data = coverage()
        data["domains"]["skill_layout"]["guide_support_level_values"] = {"resolved": 5, "missing_level": 11}
        data["domains"]["hero_traits"].update(rank_status="rank_rule_unverified", base_trait_rank="no_verified_source",
                                              rank_source="trait_ranks.candidates (trait-ranks.json)")
        data["domains"]["native_stats"].update(semantics="named_fields_corroborated_only; unnamed_ids_unmapped",
                                               protocol_verified=False)
        data["domains"]["panel_skill_identity"]["identity"] = "chosen_skill_unverified"
        data["domains"]["support_activation"].update(activation="unknown", reason="Synthetic layout flags are not activation")
        self.assertTrue(all(all(value in result for value in (
            "guide_support_level_values", "resolved: 5", "missing_level: 11", "rank_rule_unverified",
            "no_verified_source", "trait_ranks.candidates (trait-ranks.json)", "protocol_verified: false",
            "named_fields_corroborated_only; unnamed_ids_unmapped", "chosen_skill_unverified",
            "Synthetic layout flags are not activation",
        )) for result in pages({"import_coverage": data})))

    def test_both_reports_ignore_unknown_private_coverage_fields(self):
        data = coverage()
        for row in (data, data["source"], data["guide"], data["domains"]["equipment"],
                    data["domains"]["equipment"]["counts"], data["gaps"][0]):
            row["private"] = "PRIVATE-COVERAGE-CANARY"
        data["domains"]["skill_layout"]["guide_support_level_values"] = {"resolved": 3, "private": "PRIVATE-COVERAGE-CANARY"}
        data["domains"]["private"] = "PRIVATE-COVERAGE-CANARY"
        self.assertTrue(all("PRIVATE-COVERAGE-CANARY" not in result
                            for result in pages({"import_coverage": data})))

    def test_legacy_reports_without_import_coverage_remain_valid(self):
        self.assertTrue(all("Покрытие импорта" not in result for result in pages({})))

    def test_unavailable_coverage_provenance_remains_unknown(self):
        data = coverage()
        data["source"].update(captured_at=None, captured_at_status="absent")
        data["guide"].update(supplied=False, sha256=None, binding="not_supplied")
        data["domains"]["skill_layout"]["guide_support_level_values"] = None
        self.assertTrue(all(all(value in result for value in (
            "Время источника: Не установлено", "Статус времени: absent", "Сопроводительные данные: не предоставлены",
            "SHA-256 сопроводительных данных: Не указан", "guide_support_level_values: Не извлечено",
        )) for result in pages({"import_coverage": data})))


class TraitRankReportTests(unittest.TestCase):
    """Show candidate ranks as unresolved evidence without applying them to damage."""

    def test_import_report_displays_unverified_candidates_without_selecting_a_rank(self):
        result = render_import({"trait_ranks": ranks()})
        self.assertTrue(all(value in result for value in (
            "Ранги свойств героя", "Правило ранга не подтверждено", "9000731", "Ранг не установлен",
            "Кандидаты ранга", "client_fixed", "C + E", "<td>3</td>", "<td>5</td>",
            "HeroJewels[2]", "a" * 64, "Нет подтверждённого правила ранга",
        )))

    def test_calculation_report_shows_candidates_without_changing_damage(self):
        calculation = {"dps": 127319, "trace": [], "assumptions": []}
        result = render({"stats": {}, "trait_ranks": ranks()}, calculation, {
            "basis": "panel", "active": 2, "hits": 3, "retention": 0.2, "resistance": 0.23,
            "taken": 0.11, "uptime": 0.87,
        })
        self.assertEqual(("Ранги свойств героя" in result, "127 319" in result, calculation),
                         (True, True, {"dps": 127319, "trace": [], "assumptions": []}))

    def test_report_keeps_memory_field_paths_and_linkage_separate_from_the_rank(self):
        result = render_import({"trait_ranks": ranks()})
        self.assertTrue(all(value in result for value in (
            "Поля воспоминаний", "9000583", "ReminiscenceFixedLevelFromEnhance",
            "ServerPlayerItem.ReminiscenceFixedLevel", "ReminiscenceLevel", "ServerPlayerItem.BaseAffix",
            "consistent", "index_match", "Вклад fixed affix", "Ранг не установлен",
        )))

    def test_report_cannot_promote_a_candidate_to_a_resolved_rank(self):
        data = ranks()
        data["traits"][0]["rank"] = 3
        with self.assertRaisesRegex(ValueError, "unverified ranks unresolved"):
            render_import({"trait_ranks": data})

    def test_unlinked_base_trait_stays_unknown_without_a_default_rank(self):
        data = ranks()
        data["traits"][0].update(trait_id=None, memory_position=None, status="base_trait_slot_unverified",
                                 candidates=[], candidates_agree=None)
        data["memories_without_selected_trait"] = [3]
        result = render_import({"trait_ranks": data})
        self.assertTrue(all(value in result for value in (
            "ID не установлен", "Ранг не установлен", "base_trait_slot_unverified", "Не сравнены",
            "ранг 1 по умолчанию не назначается", "Слоты памяти без выбранного свойства (нумерация с 1): 3",
        )))

    def test_both_report_types_escape_candidate_markup(self):
        data = ranks()
        data["traits"][0]["candidates"][0]["formula"] = "<script>fixture()</script>"
        self.assertTrue(all("&lt;script&gt;fixture()&lt;/script&gt;" in result
                            and "<script>fixture()</script>" not in result
                            for result in pages({"trait_ranks": data})))

    def test_both_report_types_ignore_unknown_private_projection_fields(self):
        data = ranks()
        for entry in (data, data["traits"][0], data["traits"][0]["candidates"][0], data["memories"][0],
                      data["memories"][0]["fields"]["client_fixed"], data["memories"][0]["linkage"]):
            entry["private"] = "PRIVATE-RANK-CANARY"
        data["memories"][0]["fields"]["unknown"] = {"value": "PRIVATE-RANK-CANARY"}
        self.assertTrue(all("PRIVATE-RANK-CANARY" not in result for result in pages({"trait_ranks": data})))

    def test_legacy_records_without_rank_projection_remain_valid(self):
        self.assertTrue(all("Ранги свойств героя" not in result for result in pages({"stats": {}})))

    def test_report_cannot_claim_that_a_rank_rule_is_verified(self):
        data = ranks()
        data["rule_status"] = "verified"
        with self.assertRaisesRegex(ValueError, "unverified ranks unresolved"):
            render_import({"trait_ranks": data})


class DamageReportTests(unittest.TestCase):
    """Check report evidence and safe rendering without native snapshot leakage."""

    def test_fractional_penetration_trace_displays_eight_percent_instead_of_zero(self):
        self.assertIn("<td>Пробивание редукции брони из панели</td><td>8%</td>", render(
            {"stats": {}},
            {"dps": 108, "trace": [{"label": "Пробивание редукции брони из панели",
                                     "value": 0.08, "unit": "fraction"}], "assumptions": []},
            {"basis": "panel", "active": 2, "hits": 3, "retention": 0.2, "resistance": 0.23,
             "taken": 0.11, "uptime": 0.87},
        ))

    def test_raw_log_report_reproduction_does_not_require_an_intermediate_json(self):
        result = render(
            {"stats": {}, "panel_log": {
                "format": "tli-panel-log-v1", "status": "corroborated", "known": 9, "unknown_attributes": 17,
                "cohort": {"timestamp": "2001.02.03-04.05.06", "frame": 271},
                "identity_verified": False, "source_sha256": "b" * 64, "input_kind": "game_log",
            }},
            {"dps": 123, "trace": [], "assumptions": []},
            {"basis": "panel", "active": 2, "hits": 3, "retention": 0.2, "resistance": 0.23,
             "taken": 0.11, "uptime": 0.87, "observations_provided": False},
        )
        self.assertTrue("--game-log ИГРОВОЙ_ЖУРНАЛ.log" in result and "--panel-log" not in result
                        and "--observations" not in result and "identity_verified: false" in result)

    def test_import_report_preserves_level_parameters_without_applying_them_again(self):
        result = render_import({"skill_values": [{
            "name": "Fictional <skill>", "level": 17, "status": "resolved",
            "values": {"damage": 139.5},
        }]})
        self.assertTrue(all(value in result for value in (
            "Параметры навыков по уровню", "Fictional &lt;skill&gt;", "17", "resolved", "139.5",
            "не применены повторно к агрегатам панели",
        )))

    def test_import_report_explains_panel_log_provenance_without_an_identity_claim(self):
        result = render_import({"panel_log": {
            "format": "tli-panel-log-v1", "status": "corroborated", "known": 9, "unknown_attributes": 17,
            "cohort": {"timestamp": "2001.02.03-04.05.06", "frame": 271, "raw": "PRIVATE-MARKER"},
            "identity_verified": False, "source_sha256": "b" * 64, "raw": "PRIVATE-MARKER",
        }})
        self.assertTrue(all(value in result for value in (
            "Лог панели", "2001.02.03-04.05.06", "271", "b" * 64, "identity_verified: false",
            "Совпадение Spell DPS не подтверждает принадлежность лога персонажу",
        )) and "PRIVATE-MARKER" not in result)

    def test_import_report_preserves_safe_panel_row_source_coordinates(self):
        result = render_import({"stats": {"spell_dps": 71423}, "observations": [{
            "key": "spell_dps", "unit": "damage/s", "source": {
                "attr_id": "10103", "index": 1, "raw_value": "71423.25",
                "raw_values": ["71423.25", "71423.2500"],
                "timestamp": "2001.02.03-04.05.06", "frame": 271, "line_numbers": [17, 23],
                "raw": "PRIVATE-MARKER",
            },
        }]})
        self.assertTrue(all(value in result for value in (
            "10103", "71423.2500", "2001.02.03-04.05.06", "271", "[17, 23]",
        )) and "PRIVATE-MARKER" not in result)

    def test_automatic_report_reproduction_uses_the_panel_log_without_manual_observations(self):
        result = render(
            {"stats": {}, "panel_log": {
                "format": "tli-panel-log-v1", "status": "corroborated", "known": 9, "unknown_attributes": 17,
                "cohort": {"timestamp": "2001.02.03-04.05.06", "frame": 271},
                "identity_verified": False, "source_sha256": "b" * 64,
            }},
            {"dps": 123, "trace": [], "assumptions": []},
            {"basis": "panel", "active": 2, "hits": 3, "retention": 0.2, "resistance": 0.23,
             "taken": 0.11, "uptime": 0.87, "observations_provided": False},
        )
        self.assertTrue("--panel-log ПАНЕЛЬ_СТАТОВ.json" in result and "--observations" not in result
                        and "identity_verified: false" in result)

    def test_import_report_accepts_sparse_stats_without_a_damage_calculation(self):
        self.assertIn("Боевой DPS пока недоступен", render_import({
            "name": "Sparse fixture", "stats": {"spell_dps": 84317}, "benchmark": {},
            "inventory": {"gear": [{"name": "Fictional wand", "details": ["Fictional effect"]}]},
            "coverage": ["Unknown effect"], "missing_stats": ["cast_rate"], "import_status": "partial",
        }))

    def test_import_report_preserves_each_available_inventory_section(self):
        self.assertTrue(all(f"Fictional {section}" in render_import({
            "inventory": {name: [{"name": f"Fictional {name}", "details": [f"Effect {name}"]}]
                          for name in ("gear", "skills", "talents", "memories", "slates", "traits", "systems")},
            "stats": {}, "benchmark": {}, "missing_stats": ["cast_rate"], "coverage": ["Unknown layout"],
        }) for section in ("gear", "skills", "talents", "memories", "slates", "traits", "systems")))

    def test_import_report_does_not_render_private_native_payloads(self):
        self.assertNotIn("PRIVATE-MARKER", render_import({
            "accountId": "PRIVATE-MARKER", "sourceSections": {"payload": "PRIVATE-MARKER"},
            "native_stats": {"known": 2, "raw": "PRIVATE-MARKER"}, "stats": {}, "benchmark": {},
        }))

    def test_import_report_escapes_inventory_markup(self):
        self.assertIn("&lt;script&gt;fixture&lt;/script&gt;", render_import({
            "inventory": {"gear": [{"name": "<script>fixture</script>", "details": []}]},
            "stats": {}, "benchmark": {},
        }))

    def test_import_report_keeps_automatic_field_provenance(self):
        self.assertTrue(all(value in render_import({
            "stats": {"spell_dps": 84317}, "benchmark": {"survival": 9217},
            "native_stats": {"known": 2, "unknown_stat_ids": 17},
            "observations": [{"key": "spell_dps", "label": "Spell DPS", "unit": "damage/s",
                              "precision": "wire 1.10; exact integer", "evidence": "synthetic-native.json"}],
        }) for value in ("84 317", "9 217", "wire 1.10", "synthetic-native.json", "неизвестных stat ID: 17")))

    def test_import_report_keeps_fractional_values_and_displays_their_true_units(self):
        result = render_import({
            "stats": {"crit_chance": 0.4137, "cast_rate": 4.73, "crit_multiplier": 2.87},
            "observations": [{"key": key, "unit": unit, "precision": "exact synthetic value"}
                             for key, unit in (("crit_chance", "fraction"), ("cast_rate", "casts/s"),
                                               ("crit_multiplier", "multiplier"))],
        })
        self.assertTrue(all(row in result for row in (
            "<td>crit_chance</td><td>41.37%</td><td>%</td>",
            "<td>cast_rate</td><td>4.73</td><td>casts/s</td>",
            "<td>crit_multiplier</td><td>2.87</td><td>multiplier</td>",
        )))

    def test_import_report_preserves_round_trip_digits_and_large_native_integers(self):
        result = render_import({
            "stats": {"cast_rate": 1.2345678901234567, "crit_chance": 0.12345678901234566,
                      "spell_dps": 9223372036854775807},
            "observations": [{"key": key, "unit": unit, "precision": "exact synthetic value"}
                             for key, unit in (("cast_rate", "casts/s"), ("crit_chance", "fraction"),
                                               ("spell_dps", "damage/s"))],
        })
        self.assertTrue(all(row in result for row in (
            "<td>cast_rate</td><td>1.2345678901234567</td>",
            "<td>crit_chance</td><td>12.345678901234566%</td>",
            "<td>spell_dps</td><td>9 223 372 036 854 775 807</td>",
        )))

    def test_import_report_does_not_offer_manual_stats_or_a_scenario_total(self):
        result = render_import({"stats": {}, "benchmark": {}, "missing_stats": ["cast_rate"]})
        self.assertTrue("cast_rate" in result and "ручной ввод характеристик не требуется" in result
                        and "Условный расчёт" not in result and "--observations" not in result)

    def test_scenario_grid_applies_the_same_combat_context(self):
        self.assertIn("<td>587</td>", scenarios(
            {"stats": {"spell_dps": 379, "cast_rate": 6.3, "max_tangles": 3,
                       "extra_attachments": 2, "cold_penetration": 0.13}},
            {"basis": "panel", "active": 3, "hits": 11, "retention": 0.8,
             "resistance": 0, "taken": 0, "uptime": 1,
             "combat": {"reference": {"damage": [], "cast": [], "taken": []},
                        "target": {"damage": [{"id": "test", "affix": "test", "value": 0.37,
                                              "stacks": 1, "mode": "add"}], "cast": [], "taken": []},
                        "tick_frequency": None, "armor": 0, "nonphysical": True,
                        "missing": [], "notes": []}},
        ))

    def test_report_renders_decoded_slates_even_when_layout_is_unknown(self):
        self.assertIn("Fictional slate effect", render(
            {"name": "Fixture", "stats": {},
             "inventory": {"slates": [{"name": "Fixture slate", "details": ["Fictional slate effect"]}]}},
            {"dps": 123, "trace": [], "assumptions": []},
            {"basis": "panel", "active": 3, "hits": 11, "retention": 0.8,
             "resistance": 0, "taken": 0, "uptime": 1},
        ))

    def test_synthetic_report_does_not_claim_game_measurement(self):
        self.assertTrue(all(value in render(
            {"synthetic": True, "name": "Fictional", "character": "Carino", "stats": {},
             "benchmark": {"average_dps": 179}},
            {"dps": 123, "trace": [], "assumptions": []},
            {"basis": "panel", "active": 3, "hits": 11, "retention": 0.8,
             "resistance": 0, "taken": 0, "uptime": 1},
        ) for value in ("Синтетический пример", "Вымышленный бенчмарк", "Значения заданы для проверки арифметики")))

    def test_synthetic_report_avoids_observed_game_labels(self):
        self.assertNotIn("Измерено в игре", render(
            {"synthetic": True, "name": "Fictional", "character": "Carino", "stats": {}},
            {"dps": 123, "trace": [], "assumptions": []},
            {"basis": "panel", "active": 3, "hits": 11, "retention": 0.8,
             "resistance": 0, "taken": 0, "uptime": 1},
        ))

    def test_report_escapes_inventory_markup(self):
        self.assertIn("&lt;script&gt;alert(7)&lt;/script&gt;", render(
            {"name": "Fixture", "character": "Carino", "stats": {},
             "inventory": {"gear": [{"name": "<script>alert(7)</script>", "details": []}]}},
            {"dps": 123, "trace": [], "assumptions": []},
            {"basis": "panel", "active": 3, "hits": 11, "retention": 0.8,
             "resistance": 0, "taken": 0, "uptime": 1},
        ))

    def test_report_distinguishes_observed_and_conditional_values(self):
        self.assertTrue(all(text in render(
            {"name": "Fixture", "character": "Carino", "stats": {"spell_dps": 31729},
             "benchmark": {"average_dps": 185319}},
            {"dps": 909, "trace": [], "assumptions": []},
            {"basis": "panel", "active": 3, "hits": 11, "retention": 0.8,
             "resistance": 0, "taken": 0, "uptime": 1},
        ) for text in ("Измерено в игре", "185 319", "Панельный Spell DPS", "31 729", "Условный расчёт", "909")))

    def test_report_does_not_render_native_sections_or_account_ids(self):
        self.assertNotIn("NATIVE-SECRET", render(
            {"name": "Fixture", "character": "Carino", "stats": {},
             "sourceSections": {"payload": "NATIVE-SECRET"}, "accountId": "NATIVE-SECRET"},
            {"dps": 123, "trace": [], "assumptions": []},
            {"basis": "panel", "active": 3, "hits": 11, "retention": 0.8,
             "resistance": 0, "taken": 0, "uptime": 1},
        ))

    def test_report_drops_unsafe_source_urls(self):
        self.assertNotIn('href="javascript:', render(
            {"name": "Fixture", "character": "Carino", "stats": {},
             "facts": {"sources": {"bad": "javascript:alert(7)"}}},
            {"dps": 123, "trace": [], "assumptions": []},
            {"basis": "panel", "active": 3, "hits": 11, "retention": 0.8,
             "resistance": 0, "taken": 0, "uptime": 1},
        ))

    def test_report_marks_shotgun_rows_as_scenarios(self):
        self.assertTrue(all(text in render(
            {"name": "Fixture", "character": "Carino", "stats": {
                "spell_dps": 379, "max_tangles": 3, "extra_attachments": 2,
                "cold_penetration": 0.13}},
            {"dps": 123, "trace": [], "assumptions": []},
            {"basis": "panel", "active": 3, "hits": 11, "retention": 0.8,
             "resistance": 0, "taken": 0, "uptime": 1},
        ) for text in ("Сценарии, а не подтверждённые границы", "20%", "80%", "13")))
