import copy
import json
import unittest

from damage_lab.ledgerinputs import inputs
from damage_lab.staticcombat import project
from test_staticcombat import critical, document, empty


def ledger(*changes):
    """Build independent fictional rows under one exact catalog identity."""
    data = document()
    rows = []
    for index, change in enumerate(changes):
        row = copy.deepcopy(data["modifiers"][0])
        row.update(change)
        row["path"] = f"sections.WearItems.data[0].sourceData.AffixList.PrefixInfoList[{index + 10}]"
        rows.append(row)
    data["modifiers"] = rows
    data["accounting"].update(compiled=len(rows), observed=len(rows) + 1)
    return project(data, "a" * 64)


def percent(exact, fraction):
    return [{"exact": exact, "fraction": fraction, "source": "DynArgs[0]"}]


class LedgerInputsTests(unittest.TestCase):
    """Keep candidate rolls separate from effective character arithmetic."""

    def test_the_compound_stays_whole_in_excluded_without_entering_any_numeric_pool(self):
        from test_staticcombat import lucky

        result = inputs(project(lucky(), "a" * 64), skill_tags=["spell"])
        self.assertEqual((result["added"], result["increased"], result["attributes"], result["speed"],
                          [(row["family"], row["reason"], row["semantics"]["lucky_critical_strike"],
                            row["values"][0]["exact"]) for row in result["excluded"]], result["arithmetic_ready"]),
                         ([], [], [], [], [("lucky_critical_damage_modifier", "family_not_mapped", True, "23.75")], False))

    def test_fixed_implicit_enters_spell_increased_inventory_with_proof_and_an_unresolved_pool(self):
        from test_staticcombat import fixed

        result = inputs(project(fixed(), "a" * 64), skill_tags=["spell"])
        row = result["increased"][0]
        self.assertEqual((row["values"][0]["exact"], row["values"][0]["fraction"], row["damage_scope"],
                          row["fixed_implicit"]["own_value"]["exact"], row["pool"]["status"], result["arithmetic_ready"]),
                         ("37.12500", "0.3712500", "spell", "37.12500", "unresolved", False))

    def test_spell_added_damage_retains_lexical_values_and_source_coordinates(self):
        result = inputs(project(document(), "a" * 64), skill_tags=["spell", "projectile"])
        self.assertEqual((result["format"], result["added"][0]["type"], result["added"][0]["values"]), (
            "tli-ledger-inputs-v1", "cold", [
                {"exact": "11.0", "source": "DynArgs[0]",
                 "source_path": "sections.WearItems.data[0].sourceData.AffixList.PrefixInfoList[0].DynArgs[0]"},
                {"exact": "21.0", "source": "DynArgs[1]",
                 "source_path": "sections.WearItems.data[0].sourceData.AffixList.PrefixInfoList[0].DynArgs[1]"}]))

    def test_skill_tags_require_bounded_distinct_words_without_damage_types(self):
        for tags in (None, [], ("spell",), ["spell", "spell"], ["Cold"], [True], ["a" * 33],
                     ["physical"], ["cold"], ["fire"], ["lightning"], ["erosion"], ["elemental"],
                     ["damage"], ["all"], ["spell-speed"], ["t" + chr(97 + index // 26) + chr(97 + index % 26)
                                                            for index in range(33)]):
            with self.subTest(tags=tags), self.assertRaises(ValueError):
                inputs(project(document(), "a" * 64), skill_tags=tags)

    def test_context_keeps_exact_source_catalog_runtime_and_upstream_gaps(self):
        ledger = project(document(), "a" * 64)
        self.assertEqual(inputs(ledger, skill_tags=["spell"])["ledger"], {
            key: ledger[key] for key in ("format", "version", "source", "catalog", "runtime", "accounting",
                                         "omitted", "structural_gaps")})

    def test_inventory_never_claims_arithmetic_identity_runtime_or_completeness(self):
        result = inputs(project(document(), "a" * 64), skill_tags=["spell", "projectile"])
        self.assertEqual((result["status"], result["arithmetic_ready"], result["runtime_verified"],
                          result["identity_verified"], result["import_complete"], result["skill"], result["gaps"]), (
            "inventory_unverified", False, False, False, False,
            {"tags": ["projectile", "spell"], "inferred": False}, [
                {"kind": "runtime_unverified"}, {"kind": "selection_unverified"},
                {"kind": "source_patch_unknown"}, {"kind": "activation_unverified"},
                {"kind": "omitted_rows", "count": 1}, {"kind": "structural_gaps", "count": 1}]))

    def test_increased_damage_maps_types_elemental_global_and_explicit_skill_scopes(self):
        for target, scope, expected in (("physical", "any", "physical"), ("cold", "any", "cold"),
                                        ("fire", "any", "fire"), ("lightning", "any", "lightning"),
                                        ("erosion", "any", "erosion"), ("elemental", "any", "elemental"),
                                        ("damage", "any", "all"), ("damage", "spell", "spell"),
                                        ("damage", "attack", "attack"), ("damage", "projectile", "projectile"),
                                        ("damage", "melee", "melee"), ("damage", "deterioration", "deterioration")):
            data = ledger({"family": "increased_damage", "targets": [target], "scope": scope, "unit": "percent",
                           "values": percent("17.30", "0.1730"), "appliesToPlayerSpell": None if scope in
                           ("projectile", "melee", "deterioration") else scope != "attack"})
            result = inputs(data, skill_tags=["spell", "attack", "projectile", "melee", "deterioration"])
            with self.subTest(target=target, scope=scope):
                self.assertEqual((result["increased"][0]["damage_scope"],
                                  result["increased"][0]["values"][0]["fraction"]), (expected, "0.1730"))

    def test_scope_mismatch_excludes_spell_attack_and_other_skill_scopes(self):
        for family, scope, tags in (("flat_added_damage", "spell", ["attack"]),
                                     ("flat_added_damage", "attack", ["spell"]),
                                     ("increased_damage", "spell", ["attack"]),
                                     ("increased_damage", "attack", ["spell"]),
                                     ("increased_damage", "projectile", ["spell"])):
            change = {"family": family, "scope": scope, "appliesToPlayerSpell":
                      None if scope == "projectile" else scope == "spell"}
            if family == "increased_damage":
                change.update(targets=["damage"], unit="percent", values=percent("7.90", "0.0790"))
            result = inputs(ledger(change), skill_tags=tags)
            with self.subTest(family=family, scope=scope):
                self.assertEqual((result["added"], result["increased"], result["excluded"][0]["reason"]),
                                 ([], [], "scope_not_skill_tag"))

    def test_non_player_rows_are_excluded_before_candidate_mapping(self):
        for family, targets in (("increased_damage", ["damage"]), ("increased_speed", ["attack_speed", "cast_speed"])):
            data = ledger({"family": family, "targets": targets, "scope": "any", "owner": "minion",
                           "appliesToPlayerSpell": False, "unit": "percent", "values": percent("23.10", "0.2310")})
            result = inputs(data, skill_tags=["spell"])
            with self.subTest(family=family):
                self.assertEqual((result["added"], result["increased"], result["excluded"][0]["reason"]),
                                 ([], [], "owner_not_player"))

    def test_attributes_preserve_points_or_percent_without_deriving_other_stats(self):
        data = ledger({"family": "flat_attribute", "targets": ["intelligence"], "scope": "any",
                       "values": [{"exact": "13.070", "source": "DynArgs[0]"}]},
                      {"family": "increased_attribute", "targets": ["dexterity"], "scope": "any", "unit": "percent",
                       "values": percent("73.0900", "0.730900")})
        result = inputs(data, skill_tags=["spell"])
        self.assertEqual([(row["attribute"], row["unit"], row["values"][0]["exact"])
                          for row in result["attributes"]],
                         [("intelligence", "flat", "13.070"), ("dexterity", "percent", "73.0900")])

    def test_speed_keeps_one_inventory_row_with_both_targets_and_lexical_roll(self):
        data = ledger({"family": "increased_speed", "targets": ["attack_speed", "cast_speed"], "scope": "any",
                       "unit": "percent", "values": percent("19.070", "0.19070")})
        result = inputs(data, skill_tags=["spell"])
        self.assertEqual((len(result["speed"]), result["speed"][0]["targets"], result["speed"][0]["values"][0]["fraction"]),
                         (1, ["attack_speed", "cast_speed"], "0.19070"))

    def test_critical_inventory_is_never_mapped_to_damage_inputs(self):
        for family, scope in (("critical_rating_increased", "any"), ("critical_damage_modifier", "any"),
                              ("critical_damage_modifier", "spell")):
            result = inputs(project(critical(family, scope), "a" * 64), skill_tags=["attack"])
            with self.subTest(family=family, scope=scope):
                self.assertEqual((result["added"], result["increased"], result["attributes"], result["speed"],
                                  result["excluded"][0]["reason"], result["excluded"][0]["semantics"]["arithmetic_ready"],
                                  result["gaps"][-1]),
                                 ([], [], [], [], "family_not_mapped", False, {"kind": "family_not_mapped", "count": 1}))

    def test_catalog_flags_remain_explicit_gaps(self):
        data = document()
        data["catalog"]["documents"]["gear/helmet/int/master"] = {
            "sha256": "c" * 64, "status": "ok", "issue": None, "seasonId": "SS13", "schemaVersion": 1}
        data["catalog"]["flags"] = ["catalog_season_mixed"]
        self.assertIn({"kind": "catalog_flags", "flags": ["catalog_season_mixed"]},
                      inputs(project(data, "a" * 64), skill_tags=["spell"])["gaps"])

    def test_absent_invalid_or_empty_sections_never_become_complete_zero_pools(self):
        for section in ("absent", "invalid", "empty"):
            result = inputs(project(empty(section), "a" * 64), skill_tags=["spell"])
            with self.subTest(section=section):
                self.assertEqual((result["added"], result["increased"], result["import_complete"], result["gaps"][-1]),
                                 ([], [], False, {"kind": "source_section_not_captured", "section": section}))

    def test_unresolved_pool_is_preserved_as_a_gap_without_choosing_an_identity(self):
        data = document()
        path = "legendaries/helmet/int/master"
        data["catalog"]["documents"][path] = data["catalog"]["documents"].pop(next(iter(data["catalog"]["documents"])))
        data["items"][0]["identity"].update(kind="legendary", catalog=path)
        row = data["modifiers"][0]
        row["definition"] = {"catalog": path, "id": "L-fictional", "variant": "corroded",
                             "templateSource": "corrodedDescriptionTemplate"}
        row["pool"] = {"id": None, "status": "unresolved", "basis": "variant_template_differs"}
        result = inputs(project(data, "a" * 64), skill_tags=["spell"])
        self.assertEqual((result["added"][0]["pool"], result["gaps"][-1]),
                         ({"id": None, "status": "unresolved", "basis": "variant_template_differs"},
                          {"kind": "unresolved_pool", "path": row["path"]}))

    def test_equal_rolls_remain_separate_rows_with_their_original_pools_and_paths(self):
        result = inputs(ledger({}, {}), skill_tags=["spell"])
        self.assertEqual([(row["values"][0]["exact"], row["path"], row["pool"]["id"], row["status"])
                          for row in result["added"]], [
            ("11.0", "sections.WearItems.data[0].sourceData.AffixList.PrefixInfoList[10]", "P-cold", "compiled_unverified_runtime"),
            ("11.0", "sections.WearItems.data[0].sourceData.AffixList.PrefixInfoList[11]", "P-cold", "compiled_unverified_runtime")])

    def test_canonical_ledger_is_revalidated_instead_of_trusting_verification_claims(self):
        for change in ("runtime", "count", "source", "semantics"):
            data = project(critical("critical_damage_modifier", "spell"), "a" * 64)
            if change == "runtime":
                data["runtime"]["verified"] = True
            elif change == "count":
                data["accounting"]["compiled"] = True
            elif change == "source":
                data["source"]["sha256"] = "unbound"
            else:
                data["modifiers"][0]["semantics"]["arithmetic_ready"] = True
            with self.subTest(change=change), self.assertRaises(ValueError):
                inputs(data, skill_tags=["spell"])

    def test_raw_ledger_or_malformed_containers_are_not_canonical_inputs(self):
        for data in (None, [], document(), {"source": None}):
            with self.subTest(data=data), self.assertRaises(ValueError):
                inputs(data, skill_tags=["spell"])

    def test_unknown_properties_are_removed_from_mapped_rows_context_and_exclusions(self):
        for data in (project(document(), "a" * 64), project(critical("critical_damage_modifier", "spell"), "a" * 64)):
            row = data["modifiers"][0]
            for entry in (data, data["source"], data["catalog"], next(iter(data["catalog"]["documents"].values())),
                          data["runtime"], row, row["values"][0], row["pool"], row["definition"],
                          data["omitted"][0], data["structural_gaps"][0], data["accounting"]):
                entry["account_id"] = {"raw": "PRIVATE-LEDGER-MARKER"}
            if "semantics" in row:
                row["semantics"]["account_id"] = "PRIVATE-LEDGER-MARKER"
            with self.subTest(family=row["family"]):
                self.assertNotIn("PRIVATE-LEDGER-MARKER", json.dumps(inputs(data, skill_tags=["spell"])))

    def test_projection_and_result_mutations_leave_ledger_and_tags_unchanged(self):
        data = project(document(), "a" * 64)
        tags = ["spell", "projectile"]
        before = copy.deepcopy((data, tags))
        result = inputs(data, skill_tags=tags)
        result["added"][0]["values"][0]["exact"] = "99"
        result["added"][0]["definition"]["id"] = "changed"
        result["ledger"]["catalog"]["documents"].clear()
        result["ledger"]["omitted"][0]["reason"] = "changed"
        result["skill"]["tags"].append("changed")
        self.assertEqual((data, tags), before)

    def test_input_mutations_cannot_change_a_projected_value(self):
        data = project(document(), "a" * 64)
        result = inputs(data, skill_tags=["spell"])
        data["modifiers"][0]["values"][0]["exact"] = "97"
        self.assertEqual(result["added"][0]["values"][0]["exact"], "11.0")
