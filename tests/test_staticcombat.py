import copy
import json
import unittest
from decimal import localcontext

from damage_lab.staticcombat import project, summary


def document():
    """Return a fictional 0.3.2 compiler ledger without player identifiers."""
    path = "gear/one_handed/wand/master"
    base = "sections.WearItems.data[0]"
    return {
        "format": "tli-static-combat-modifiers-v1", "version": "0.3.2",
        "source": {"sha256": "a" * 64, "section": "captured"},
        "catalog": {"documents": {path: {"sha256": "b" * 64, "status": "ok", "issue": None,
                                          "seasonId": "SS14", "schemaVersion": 1}}, "flags": []},
        "runtime": {"verified": False, "selectionVerified": False, "sourcePatch": "unknown", "activation": "unverified"},
        "items": [{"alias": "gear[0]", "path": base,
                   "identity": {"status": "exact", "kind": "base", "catalog": path, "definition": "base-1", "tlidbId": "9001"}}],
        "modifiers": [{"item": "gear[0]", "path": base + ".sourceData.AffixList.PrefixInfoList[0]",
                       "list": "PrefixInfoList", "nativeId": 900000101, "family": "flat_added_damage",
                       "targets": ["cold"], "scope": "spell", "owner": "player", "appliesToPlayerSpell": True,
                       "unit": "flat", "values": [{"exact": "11.0", "source": "DynArgs[0]"},
                                                    {"exact": "21.0", "source": "DynArgs[1]"}],
                       "definition": {"catalog": path, "id": "P-cold", "tier": "1", "tierId": "P-cold-1",
                                      "templateSource": "descriptionTemplate"},
                       "pool": {"id": "P-cold", "status": "exact", "basis": "gear_entry"},
                       "templateSign": None, "status": "compiled_unverified_runtime"}],
        "omitted": [{"item": "gear[0]", "path": base + ".sourceData.AffixList.PrefixInfoList[2]",
                     "list": "PrefixInfoList", "nativeId": 900000199, "reason": "no_exact_definition"}],
        "structuralGaps": [{"item": "gear[0]", "path": base + ".sourceData.AffixList.SuffixInfoList",
                            "reason": "invalid_affix_container"}],
        "accounting": {"items": 1, "emptyRows": 1, "observed": 2, "compiled": 1, "omitted": 1,
                       "structuralGaps": 1, "reconciles": True, "scope": "known_rows_only"}}


def empty(section):
    data = document()
    data["source"]["section"] = section
    for key in ("items", "modifiers", "omitted", "structuralGaps"):
        data[key] = []
    data["accounting"] = {"items": 0, "emptyRows": 0, "observed": 0, "compiled": 0, "omitted": 0,
                          "structuralGaps": 0, "reconciles": True, "scope": "all_rows"}
    return data


class StaticCombatTest(unittest.TestCase):
    """Validate inventory evidence without applying it to a character or damage model."""

    def test_source_bound_ledger_preserves_lexical_rolls_and_unverified_flags(self):
        result = project(document(), "a" * 64)
        self.assertEqual((result["modifiers"][0]["values"], result["runtime"], result["accounting"]["scope"]),
                         ([{"exact": "11.0", "source": "DynArgs[0]"}, {"exact": "21.0", "source": "DynArgs[1]"}],
                          {"verified": False, "selection_verified": False, "source_patch": "unknown", "activation": "unverified"},
                          "known_rows_only"))

    def test_source_hash_version_and_runtime_claims_are_strict(self):
        cases = [("format", "other"), ("version", "0.3.1"), ("source", {"sha256": "b" * 64, "section": "captured"}),
                 ("runtime", {"verified": 0, "selectionVerified": False, "sourcePatch": "unknown", "activation": "unverified"}),
                 ("runtime", {"verified": False, "selectionVerified": True, "sourcePatch": "unknown", "activation": "unverified"})]
        for key, value in cases:
            data = document()
            data[key] = value
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                project(data, "a" * 64)
        for digest in (None, True, "A" * 64, "a" * 63):
            with self.subTest(digest=digest), self.assertRaises(ValueError):
                project(document(), digest)

    def test_catalog_metadata_paths_hashes_statuses_and_flags_are_typed(self):
        path = "gear/one_handed/wand/master"
        for key, value in (("sha256", "private"), ("status", "verified"), ("issue", "identity_leaf"),
                           ("seasonId", {"account": "CANARY"}), ("schemaVersion", True), ("schemaVersion", 1000000)):
            data = document()
            data["catalog"]["documents"][path][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                project(data, "a" * 64)
        for name in ("C:/Users/CANARY/master", "gear/" + "x" * 260):
            data = document()
            data["catalog"]["documents"][name] = data["catalog"]["documents"].pop(path)
            with self.subTest(path=name), self.assertRaises(ValueError):
                project(data, "a" * 64)
        data = document()
        data["catalog"]["flags"] = ["catalog_season_mixed"]
        with self.assertRaises(ValueError):
            project(data, "a" * 64)

    def test_accounting_and_source_states_cannot_claim_unobserved_completeness(self):
        for key, value in (("items", 2), ("emptyRows", True), ("observed", 1), ("compiled", -1),
                           ("omitted", 1.0), ("structuralGaps", 0), ("reconciles", 1), ("scope", "all_rows")):
            data = document()
            data["accounting"][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                project(data, "a" * 64)
        for state in ("empty", "absent", "invalid"):
            data = document()
            data["source"]["section"] = state
            with self.subTest(state=state), self.assertRaises(ValueError):
                project(data, "a" * 64)

    def test_item_aliases_paths_and_public_catalog_identities_are_strict(self):
        for field, value in (("status", "verified"), ("kind", "weapon"), ("catalog", "gear/not-supplied/master"),
                             ("definition", {"account": "CANARY"}), ("tlidbId", 9001)):
            data = document()
            data["items"][0]["identity"][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                project(data, "a" * 64)
        for field, value in (("alias", "gear[1]"), ("path", "sections.WearItems.data[1]")):
            data = document()
            data["items"][0][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                project(data, "a" * 64)

    def test_modifier_vocabulary_typed_values_and_fraction_consistency_are_required(self):
        for key, value in (("nativeId", True), ("family", "more_damage"), ("targets", [{"account": "CANARY"}]),
                           ("scope", "verified"), ("owner", "account"), ("appliesToPlayerSpell", 1),
                           ("unit", "ratio"), ("templateSign", {}), ("status", "effective")):
            data = document()
            data["modifiers"][0][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                project(data, "a" * 64)
        for value in ({"exact": {"account": "CANARY"}, "source": "DynArgs[0]"},
                      {"exact": "NaN", "source": "DynArgs[0]"}, {"exact": "11", "source": "DynArgs[1]"},
                      {"exact": "11.0000000001", "source": "DynArgs[0]"}):
            data = document()
            data["modifiers"][0]["values"][0] = value
            with self.subTest(value=value), self.assertRaises(ValueError):
                project(data, "a" * 64)
        data = document()
        row = data["modifiers"][0]
        row.update(family="increased_speed", targets=["cast_speed"], scope="any", unit="percent", templateSign="+",
                   values=[{"exact": "11.50", "fraction": "0.12", "source": "DynArgs[0]"}])
        with self.assertRaises(ValueError):
            project(data, "a" * 64)

    def test_definitions_and_pool_identity_cannot_embed_objects_or_change_item_catalog(self):
        for block, key, value in (("definition", "id", {"account": "CANARY"}), ("definition", "tier", {"account": "CANARY"}),
                                  ("definition", "tierId", None), ("definition", "catalog", "gear/other/master"),
                                  ("definition", "templateSource", "guessed"), ("pool", "id", {"account": "CANARY"}),
                                  ("pool", "id", "other"), ("pool", "status", "verified"), ("pool", "basis", "guessed")):
            data = document()
            data["modifiers"][0][block][key] = value
            with self.subTest(block=block, key=key), self.assertRaises(ValueError):
                project(data, "a" * 64)

    def test_all_rows_reference_one_source_item_and_have_distinct_canonical_paths(self):
        for block, key, value in (("modifiers", "item", "gear[9]"), ("modifiers", "path", "sections.WearItems.data[9]"),
                                  ("modifiers", "list", "UnknownList"), ("omitted", "reason", "CANARY"),
                                  ("omitted", "nativeId", False), ("structuralGaps", "reason", "CANARY"),
                                  ("structuralGaps", "path", "C:/private/CANARY")):
            data = document()
            data[block][0][key] = value
            with self.subTest(block=block, key=key), self.assertRaises(ValueError):
                project(data, "a" * 64)
        data = document()
        data["omitted"][0]["path"] = data["modifiers"][0]["path"]
        with self.assertRaises(ValueError):
            project(data, "a" * 64)

    def test_inverted_flat_intervals_are_rejected_without_sorting(self):
        data = document()
        data["modifiers"][0]["values"][0]["exact"] = "29"
        with self.assertRaises(ValueError):
            project(data, "a" * 64)

    def test_absent_invalid_and_empty_sources_preserve_only_their_catalog_evidence(self):
        for state in ("absent", "invalid", "empty"):
            data = empty(state)
            path = next(iter(data["catalog"]["documents"]))
            data["catalog"]["documents"][path].update(status="invalid", issue="parse_limit")
            data["catalog"]["flags"] = ["catalog_document_invalid"]
            with self.subTest(state=state):
                self.assertEqual((project(data, "a" * 64)["source"]["section"], project(data, "a" * 64)["items"]),
                                 (state, []))

    def test_captured_invalid_records_remain_explicit_structural_gaps(self):
        data = empty("captured")
        data["items"] = [{"alias": "gear[0]", "path": "sections.WearItems.data[0]", "identity": {"status": "invalid_record"}}]
        data["structuralGaps"] = [{"item": "gear[0]", "path": "sections.WearItems.data[0]", "reason": "invalid_record"}]
        data["accounting"].update(items=1, structuralGaps=1, scope="known_rows_only")
        self.assertEqual(project(data, "a" * 64)["accounting"],
                         {"items": 1, "empty_rows": 0, "observed": 0, "compiled": 0, "omitted": 0,
                          "structural_gaps": 1, "reconciles": True, "scope": "known_rows_only"})

    def test_legendary_variants_preserve_exact_or_unresolved_pools(self):
        for variant, basis, status in (("normal", "legendary_mod", "exact"),
                                        ("corroded", "legendary_mod_same_template", "exact"),
                                        ("corroded", "variant_template_differs", "unresolved")):
            data = document()
            old = next(iter(data["catalog"]["documents"]))
            path = "legendaries/helmet/int_helmet/master"
            data["catalog"]["documents"][path] = data["catalog"]["documents"].pop(old)
            data["items"][0]["identity"].update(kind="legendary", catalog=path, definition="leg-1", tlidbId="9100")
            row = data["modifiers"][0]
            row["definition"] = {"catalog": path, "id": "L-cast", "variant": variant,
                                 "templateSource": "descriptionTemplate" if variant == "normal" else "corrodedDescriptionTemplate"}
            row["pool"] = {"id": "L-cast" if status == "exact" else None, "status": status, "basis": basis}
            with self.subTest(variant=variant, basis=basis):
                self.assertEqual(project(data, "a" * 64)["modifiers"][0]["pool"], row["pool"])

    def test_fractional_values_preserve_lexical_tokens_and_do_not_apply_player_scope(self):
        for scope, owner, applies in (("any", "player", True), ("attack", "player", False), ("any", "minion", False),
                                      ("projectile", "player", None)):
            data = document()
            row = data["modifiers"][0]
            row.update(family="increased_damage", targets=["damage"], scope=scope, owner=owner, appliesToPlayerSpell=applies,
                       unit="percent", templateSign="+", values=[{"exact": "11.50", "fraction": "0.115", "source": "DynArgs[0]"}])
            with self.subTest(scope=scope, owner=owner):
                self.assertEqual((project(data, "a" * 64)["modifiers"][0]["values"],
                                  project(data, "a" * 64)["modifiers"][0]["applies_to_player_spell"]),
                                 ([{"exact": "11.50", "fraction": "0.115", "source": "DynArgs[0]"}], applies))

    def test_projection_and_summary_strip_unknown_properties_at_every_depth(self):
        data = document()
        def mark(value):
            if type(value) is dict:
                for child in list(value.values()):
                    mark(child)
                value["accountId"] = {"private": "CANARY"}
            elif type(value) is list:
                for child in value:
                    mark(child)
        # A catalog document map has contract path keys rather than arbitrary object properties.
        documents = data["catalog"]["documents"]
        data["catalog"]["documents"] = {}
        mark(data)
        data["catalog"]["documents"] = documents
        for row in documents.values():
            mark(row)
        result = project(data, "a" * 64)
        mark(result)
        result["catalog"]["documents"].pop("accountId")
        self.assertNotIn("CANARY", json.dumps(summary(result)))

    def test_results_and_inputs_are_detached(self):
        data = document()
        before = copy.deepcopy(data)
        result = project(data, "a" * 64)
        normalized = summary(result)
        normalized["modifiers"][0]["values"][0]["exact"] = "999"
        normalized["catalog"]["flags"].append("extra")
        self.assertEqual((data, result["modifiers"][0]["values"][0]["exact"], result["catalog"]["flags"]), (before, "11.0", []))

    def test_summary_rejects_tampered_canonical_verification_and_counts(self):
        data = project(document(), "a" * 64)
        data["runtime"]["verified"] = True
        with self.assertRaises(ValueError):
            summary(data)
        data = project(document(), "a" * 64)
        data["accounting"]["compiled"] = True
        with self.assertRaises(ValueError):
            summary(data)

    def test_fraction_validation_is_independent_of_the_callers_decimal_context(self):
        data = document()
        data["modifiers"][0].update(family="increased_damage", targets=["damage"], scope="any", unit="percent",
                                    values=[{"exact": "100000000000", "fraction": "1E+9", "source": "DynArgs[0]"}])
        with localcontext() as context:
            context.Emax = 0
            self.assertEqual(project(data, "a" * 64)["modifiers"][0]["values"][0]["fraction"], "1E+9")

    def test_malformed_json_containers_raise_controlled_contract_errors(self):
        for field, value in (("source", None), ("catalog", []), ("runtime", True), ("items", {}),
                             ("modifiers", [None]), ("omitted", [False]), ("structuralGaps", None), ("accounting", [])):
            data = document()
            data[field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                project(data, "a" * 64)

    def test_invalid_containers_cannot_also_contain_observed_affixes(self):
        data = document()
        data["structuralGaps"][0]["path"] = "sections.WearItems.data[0].sourceData.AffixList.PrefixInfoList"
        with self.assertRaises(ValueError):
            project(data, "a" * 64)

    def test_cross_family_vocabulary_cannot_invent_producer_interpretations(self):
        cases = (("flat_attribute", ["physical"], "projectile", "minion", False),
                 ("flat_added_damage", ["damage"], "spell", "player", True),
                 ("increased_attribute", ["strength"], "spell", "player", True),
                 ("increased_damage", ["strength"], "any", "player", True),
                 ("increased_damage", ["cold"], "projectile", "player", None),
                 ("increased_damage", ["elemental"], "any", "minion", False),
                 ("increased_speed", ["cast_speed", "attack_speed"], "any", "player", True),
                 ("increased_speed", ["cast_speed"], "any", "minion", False))
        for family, targets, scope, owner, applies in cases:
            data = document()
            row = data["modifiers"][0]
            unit = "flat" if family in ("flat_attribute", "flat_added_damage") else "percent"
            values = [{"exact": "11.0", "source": "DynArgs[0]"}]
            if unit == "percent":
                values[0]["fraction"] = "0.11"
            elif family == "flat_added_damage":
                values.append({"exact": "21.0", "source": "DynArgs[1]"})
            row.update(family=family, targets=targets, scope=scope, owner=owner, appliesToPlayerSpell=applies,
                       values=values, unit=unit)
            with self.subTest(family=family, scope=scope, targets=targets), self.assertRaises(ValueError):
                project(data, "a" * 64)
            normalized = project(document(), "a" * 64)
            normalized["modifiers"][0].update(family=family, targets=targets, scope=scope, owner=owner,
                                             applies_to_player_spell=applies, values=values, unit=unit)
            with self.subTest(canonical=family), self.assertRaises(ValueError):
                summary(normalized)

    def test_every_current_producer_family_variant_remains_supported(self):
        elements = ("physical", "cold", "fire", "lightning", "erosion")
        attributes = ("strength", "dexterity", "intelligence")
        cases = [("flat_added_damage", [element], scope, "player") for element in elements for scope in ("spell", "attack")]
        cases += [("increased_damage", [target], "any", "player") for target in elements + ("damage", "elemental")]
        cases += [("increased_damage", ["damage"], scope, "player") for scope in ("spell", "attack", "projectile", "melee", "deterioration")]
        cases += [(family, [attribute], "any", "player") for family in ("flat_attribute", "increased_attribute") for attribute in attributes]
        cases += [("increased_damage", ["damage"], "any", "minion"),
                  ("increased_speed", ["cast_speed"], "any", "player"),
                  ("increased_speed", ["attack_speed", "cast_speed"], "any", "player"),
                  ("increased_speed", ["attack_speed", "cast_speed"], "any", "minion")]
        for family, targets, scope, owner in cases:
            data = document()
            row = data["modifiers"][0]
            values = [{"exact": "11.0", "source": "DynArgs[0]"}]
            unit = "flat" if family in ("flat_attribute", "flat_added_damage") else "percent"
            if unit == "percent":
                values[0]["fraction"] = "0.11"
            elif family == "flat_added_damage":
                values.append({"exact": "21.0", "source": "DynArgs[1]"})
            applies = False if scope == "attack" or owner == "minion" else True if scope in ("any", "spell") else None
            row.update(family=family, targets=targets, scope=scope, owner=owner, appliesToPlayerSpell=applies,
                       values=values, unit=unit)
            with self.subTest(family=family, targets=targets, scope=scope, owner=owner):
                self.assertEqual(summary(project(data, "a" * 64))["modifiers"][0]["targets"], targets)


if __name__ == "__main__":
    unittest.main()
