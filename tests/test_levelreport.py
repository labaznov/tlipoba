"""Check the passive level-candidate section with fictional source-bound diagnostics."""

import copy
import contextlib
from html.parser import HTMLParser
from pathlib import Path
import sys
import tempfile
from types import ModuleType
import unittest
from unittest.mock import patch

from damage_lab.levelreport import section


def bundle():
    """Keep one fictional canonical target and declared byte metadata."""
    from damage_lab.levelcandidates import project
    from test_levelcandidates import document

    ledger = project(document(), "a" * 64)
    return {
        "format": "tli-installed-level-candidates-canonical-v1", "version": "0.1.2",
        "resolver_format": "tli-effective-level-candidates-v0", "resolver_version": "0.3.1",
        "source": {"file": "source.json", "sha256": "a" * 64},
        "arithmetic_ready": False, "runtime_verified": False, "identity_verified": False, "import_complete": False,
        "catalog": {"status": "members_read", "derivation": "cache_member_exact_slice",
                    "network_bytes_verified": False, "current_patch_verified": False,
                    "mapping_files": [{"file": "needed-bundles.json", "sha256": "b" * 64, "bytes": 137}],
                    "documents": [{"role": "master", "domain": "skill", "logical_path": "skill/Active/master",
                                   "address": "/data/SS14/skill/Active/master.json", "cache_file": "00000000000000a1.json",
                                   "wrapper_sha256": "c" * 64, "byte_range": [23, 113],
                                   "member_sha256": "d" * 64, "encoding": "utf-8"}]},
        "auxiliary": {"endgame_id_bridge": {"status": "supplied", "sha256": "e" * 64, "bytes": 173},
                      "verified_native_mappings": {"status": "absent", "sha256": None, "bytes": None}},
        "selection": {"policy": "distinct_observed_config_base_ids", "client_layer": "captured",
                      "observed_members": 1, "invalid_skill_ids": 0},
        "requested_ids": [91437], "targets": {"91437": ledger},
        "accounting": {"catalog_documents": 1, "auxiliary_files": 1, "requested": 1, "targets": 1,
                       "candidates": 6, "gaps": 1, "ambiguous_targets": 0},
    }


@contextlib.contextmanager
def validation(expected):
    """Isolate section formatting while the independently owned byte binder is in development."""
    module = ModuleType("damage_lab.levelbundle")

    def summary(value, installation):
        return copy.deepcopy(expected)

    module.summary = summary
    with patch.dict(sys.modules, {module.__name__: module}):
        yield


class Surface(HTMLParser):
    """Collect actual page tags and attributes without treating escaped evidence as markup."""

    def __init__(self, tags):
        super().__init__()
        self.tags = tags

    def handle_starttag(self, tag, attrs):
        self.tags.append((tag, dict(attrs)))


class LevelReportTests(unittest.TestCase):
    """Keep level grants as unverified candidates without selecting or adding effective levels."""

    def test_the_russian_section_keeps_effective_level_and_damage_unknown(self):
        value = bundle()
        with validation(value):
            page = section(value, {"synthetic": True})
        self.assertTrue(all(text in page for text in (
            "Кандидаты прибавок к уровню навыков", "Effective level: неизвестно", "Кандидаты не складываются",
            "DPS не рассчитан", "91437", "gem level", "17", "runtime_verified: false",
            "Явно наблюдаемые ID", "distinct_observed_config_base_ids",
        )))

    def test_saved_diagnostic_bytes_render_through_the_real_source_bound_binder(self):
        from damage_lab.levelbundle import read, summary
        from test_levelbundle import diagnostic

        with tempfile.TemporaryDirectory() as folder:
            directory = Path(folder)
            _, descriptor, source, installation = diagnostic(directory)
            value, _ = read(directory, descriptor, source, installation)
            page = section(value, installation)
            self.assertTrue(all(text in page for text in (
                source, "Кандидаты прибавок к уровню навыков", "2.70", "sections.SkillLayout.data[0][0]",
                "Effective level: неизвестно", "runtime_verified: false", "identity_verified: false",
            )) and summary(value, installation) == value)

    def test_native_fields_render_as_observations_with_unknown_semantics(self):
        from damage_lab.levelbundle import read
        from test_levelbundle import native

        with tempfile.TemporaryDirectory() as folder:
            directory = Path(folder)
            _, descriptor, source, installation = native(directory)
            value, _ = read(directory, descriptor, source, installation)
            page = section(value, installation)
            self.assertTrue(all(text in page for text in (
                "Нативные поля уровней", "sections.ServerSource.data.featuresInfo.skills.skills[9]",
                "SkillItemLevel", "63", "level_equals_gem", "unknown", "Effective level: неизвестно",
            )))

    def test_real_validation_refuses_unknown_payloads_instead_of_dumping_them(self):
        from damage_lab.levelbundle import read
        from test_levelbundle import diagnostic

        with tempfile.TemporaryDirectory() as folder:
            directory = Path(folder)
            _, descriptor, source, installation = diagnostic(directory)
            value, _ = read(directory, descriptor, source, installation)
            value["targets"]["91437"]["opaque"] = {"account": "PRIVATE-LEVEL-CANARY"}
            with self.assertRaisesRegex(ValueError, "^Level report requires an unchanged canonical diagnostic bundle$"):
                section(value, installation)

    def test_real_validation_refuses_a_different_installation_source(self):
        from damage_lab.levelbundle import read
        from test_levelbundle import diagnostic

        with tempfile.TemporaryDirectory() as folder:
            directory = Path(folder)
            _, descriptor, source, installation = diagnostic(directory)
            value, _ = read(directory, descriptor, source, installation)
            installation["source"]["sha256"] = "f" * 64
            with self.assertRaisesRegex(ValueError, "^Level report requires an unchanged canonical diagnostic bundle$"):
                section(value, installation)

    def test_own_rolls_computed_rank_and_catalog_literals_have_separate_display_origins(self):
        value = bundle()
        with validation(value):
            page = section(value, {"synthetic": True})
        self.assertTrue(all(text in page for text in (
            "Собственные роллы предметов", "Таланты: вычисленная привязка", "Каталожные литералы", "2.70",
            "DynArgs[0]", "native_roll", "catalog_literal", "computed_position_tier_id", "per_point_or_total_unknown",
            "rank_scaling_unknown", "unverified", "tier_bounds", "listed_in_dressing_blocks_placement_unverified",
            "third_party_bridge_unhashed", "Amount неизвестного rank не заменяется нулём",
        )) and page.index("Собственные роллы предметов") < page.index("Таланты: вычисленная привязка")
                        < page.index("Каталожные литералы"))

    def test_ambiguous_installation_keeps_the_target_without_selecting_an_instance_or_level(self):
        value = bundle()
        value["targets"]["91437"]["target"].update(status="ambiguous_installation", path=None, gem_level=None)
        value["accounting"]["ambiguous_targets"] = 1
        with validation(value):
            page = section(value, {"synthetic": True})
        self.assertTrue(all(text in page for text in (
            "91437", "ambiguous_installation", "Одинаковый ID установлен несколько раз",
            "экземпляр и уровень не выбраны", "Effective level: неизвестно",
        )) and "sections.SkillLayout.data[3][1]" not in page and ">None<" not in page)

    def test_unknown_target_collection_and_counts_are_not_rendered_as_an_empty_success(self):
        value = bundle()
        value["selection"].update(client_layer="absent", observed_members=None, invalid_skill_ids=None)
        value.update(requested_ids=None, targets=None)
        value["accounting"].update({key: None for key in ("requested", "targets", "candidates", "gaps", "ambiguous_targets")})
        with validation(value):
            page = section(value, {"synthetic": True})
        self.assertTrue("Состав целей неизвестен; это не пустой список" in page
                        and "Наблюдаемых members: неизвестно" in page and "<td>requested</td><td>неизвестно</td>" in page
                        and "<h3>Цель " not in page and ">None<" not in page)

    def test_captured_empty_requests_keep_known_zero_counts_without_an_inferred_level(self):
        value = bundle()
        value["selection"].update(observed_members=0)
        value.update(requested_ids=[], targets={})
        value["accounting"].update({key: 0 for key in ("requested", "targets", "candidates", "gaps", "ambiguous_targets")})
        with validation(value):
            page = section(value, {"synthetic": True})
        self.assertTrue("Допустимых наблюдаемых skill IDs нет" in page and "<td>requested</td><td>0</td>" in page
                        and "Effective level: неизвестно" in page and "Состав целей неизвестен" not in page)

    def test_catalog_and_auxiliary_hashes_remain_declared_byte_metadata_without_patch_claims(self):
        value = bundle()
        with validation(value):
            page = section(value, {"synthetic": True})
        self.assertTrue(all(text in page for text in (
            "a" * 64, "b" * 64, "c" * 64, "d" * 64, "e" * 64,
            "network_bytes_verified: false", "current_patch_verified: false", "cache_member_exact_slice",
            "wrapper_sha256", "member_sha256", "byte_range", "needed-bundles.json", "verified_native_mappings",
            "не перечитывают cache", "не подтверждают сеть или текущий patch", "hashed bridge не подтверждает runtime",
        )) and "<td>absent</td><td>неизвестно</td><td>неизвестно</td>" in page)

    def test_domains_and_structural_gap_coordinates_are_visible_without_applying_candidates(self):
        value = bundle()
        with validation(value):
            page = section(value, {"synthetic": True})
        self.assertTrue(all(text in page for text in (
            "Покрытие доменов", "Gaps цели", "rank_scaling_unknown", "catalog_level_mentions", "unknown_section_absent",
            "sections.GeniusInfos.data.entries[3].value.GeniusList.entries[5]", "per_point_or_total_unknown",
            "Ни уровень камня, ни SkillItemLevel не подставляются как effective level",
        )))

    def test_the_section_is_passive_and_escapes_known_evidence_text(self):
        value = bundle()
        value["targets"]["91437"]["candidates"][0]["template"] = '<img src=x onerror="synthetic()"> & literal'
        tags = []
        with validation(value):
            page = section(value, {"synthetic": True})
        Surface(tags).feed(page)
        self.assertTrue("&lt;img src=x onerror=&quot;synthetic()&quot;&gt; &amp; literal" in page
                        and not any(tag in {"script", "img", "iframe", "object", "embed", "link", "form", "input"}
                                    or any(name.startswith("on") or name in {"src", "href", "action"} for name in attributes)
                                    for tag, attributes in tags))

    def test_forged_claims_counts_gaps_and_unknown_payloads_cannot_replace_the_canonical_bundle(self):
        expected = bundle()
        outcomes = []
        for path, replacement in ((("runtime_verified",), True), (("import_complete",), True),
                                  (("accounting", "candidates"), 137), (("targets", "91437", "gaps"), []),
                                  (("targets", "91437", "effective_level"), 37), (("opaque",), "PRIVATE-LEVEL-CANARY")):
            value = copy.deepcopy(expected)
            node = value
            for field in path[:-1]:
                node = node[field]
            node[path[-1]] = replacement
            with validation(expected):
                try:
                    section(value, {"synthetic": True})
                except ValueError as error:
                    outcomes.append(str(error))
        self.assertEqual(outcomes, ["Level report requires an unchanged canonical diagnostic bundle"] * 6)

    def test_root_binder_errors_are_fixed_and_do_not_echo_private_inputs(self):
        module = ModuleType("damage_lab.levelbundle")

        def unavailable(value, installation):
            raise ValueError("PRIVATE-LEVEL-CANARY")

        module.summary = unavailable
        with patch.dict(sys.modules, {module.__name__: module}), self.assertRaisesRegex(
                ValueError, "^Level report requires an unchanged canonical diagnostic bundle$"):
            section({"opaque": "PRIVATE-LEVEL-CANARY"}, None)

    def test_rendering_is_deterministic_and_leaves_both_inputs_unchanged(self):
        value, installation = bundle(), {"synthetic": ["private source context"]}
        original = copy.deepcopy((value, installation))
        with validation(value):
            page = section(value, installation)
            repeated = section(value, installation)
        self.assertEqual(((value, installation), page, "private source context" in page), (original, repeated, False))

    def test_nonfinite_cyclic_or_unserializable_payloads_fail_before_rendering(self):
        expected = bundle()
        outcomes = []
        for change in ("nonfinite", "cycle", "set", "null"):
            value = copy.deepcopy(expected)
            if change == "null":
                value = None
            else:
                value["opaque"] = float("nan") if change == "nonfinite" else value if change == "cycle" else {"private"}
            with validation(expected):
                try:
                    section(value, None)
                except ValueError as error:
                    outcomes.append(str(error))
        self.assertEqual(outcomes, ["Level report requires an unchanged canonical diagnostic bundle"] * 4)
