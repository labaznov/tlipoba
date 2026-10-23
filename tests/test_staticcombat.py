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


def critical(family, scope):
    """Return a fictional inventory-only critical row from compiler 0.4.0."""
    data = document()
    data["version"] = "0.4.0"
    row = data["modifiers"][0]
    row.update(family=family, targets=["critical_rating" if family == "critical_rating_increased" else "critical_damage"],
               scope=scope, unit="percent", templateSign="+",
               values=[{"exact": "11.0", "source": "DynArgs[0]", "fraction": "0.11"}],
               semantics={"operation": "rating_increase" if family == "critical_rating_increased" else "unresolved",
                          "valueRole": "non_additional_percent", "arithmeticReady": False})
    return data


def casted():
    """Retain a fictional omitted cast row without typing it as an applied modifier."""
    from test_castevidence import document as evidence

    data = document()
    data["version"] = "0.4.1"
    data["omitted"][0].update(reason="unsupported_family", evidence=evidence())
    return data


def fixed():
    """Bind a fictional wand implicit to its two declared catalog members without choosing a pool."""
    from test_fixedimplicit import document as proof

    data = document()
    data["version"] = "0.4.2"
    data["items"][0]["identity"].update(definition="synthetic-wand", tlidbId="9137")
    data["catalog"]["documents"]["gear/one_handed/wand/i18n/en"] = {
        "sha256": "c" * 64, "status": "ok", "issue": None, "seasonId": None, "schemaVersion": None, "role": "english"}
    data["modifiers"][0].update(
        path="sections.WearItems.data[0].sourceData.AffixList.FixedBaseAffix[0]", list="FixedBaseAffix", nativeId=520020,
        family="increased_damage", targets=["damage"], scope="spell", owner="player", appliesToPlayerSpell=True,
        unit="percent", values=[{"exact": "37.12500", "fraction": "0.3712500", "source": "DynArgs[0]"}],
        definition={"catalog": "gear/one_handed/wand/master", "id": "synthetic-wand", "implicit": True},
        pool={"id": None, "status": "unresolved", "basis": "fixed_implicit_identity_unresolved"},
        templateSign="+", fixedImplicit=proof())
    return data


def lucky():
    """Bind a fictional corroded glove row without activating either critical effect."""
    data = critical("critical_damage_modifier", "any")
    data["version"] = "0.4.3"
    path = "legendaries/gloves/dex_gloves/master"
    data["catalog"]["documents"][path] = data["catalog"]["documents"].pop("gear/one_handed/wand/master")
    data["items"][0]["identity"].update(kind="legendary", catalog=path, definition="synthetic-glove", tlidbId="9347")
    data["modifiers"][0].update(
        nativeId=51434430, family="lucky_critical_damage_modifier", templateSign=None,
        values=[{"exact": "23.75", "fraction": "0.2375", "source": "DynArgs[0]"}],
        definition={"catalog": path, "id": "synthetic-critical", "variant": "corroded",
                    "templateSource": "corrodedDescriptionTemplate"},
        pool={"id": None, "status": "unresolved", "basis": "variant_template_differs"},
        semantics={"operation": "unresolved", "valueRole": "non_additional_percent",
                   "luckyCriticalStrike": True, "arithmeticReady": False})
    return data


class StaticCombatTest(unittest.TestCase):
    """Validate inventory evidence without applying it to a character or damage model."""

    def test_a_corroded_critical_row_preserves_one_scalar_and_a_separate_lucky_literal(self):
        result = summary(project(lucky(), "a" * 64))
        self.assertEqual((result["accounting"]["compiled"], result["modifiers"][0]["values"],
                          result["modifiers"][0]["semantics"]),
                         (1, [{"exact": "23.75", "fraction": "0.2375", "source": "DynArgs[0]"}],
                          {"operation": "unresolved", "value_role": "non_additional_percent",
                           "lucky_critical_strike": True, "arithmetic_ready": False}))

    def test_the_compound_requires_its_pinned_corroded_native_catalog_list_and_pool(self):
        for change in ("native", "catalog", "list", "variant", "pool", "version"):
            with self.subTest(change=change):
                data = lucky()
                row = data["modifiers"][0]
                if change == "native":
                    row["nativeId"] = 51434431
                elif change == "catalog":
                    path = "legendaries/gloves/str_gloves/master"
                    data["catalog"]["documents"][path] = data["catalog"]["documents"].pop(row["definition"]["catalog"])
                    data["items"][0]["identity"]["catalog"] = row["definition"]["catalog"] = path
                elif change == "list":
                    row.update(list="BAffixInfoList", path="sections.WearItems.data[0].sourceData.AffixList.BAffixInfoList[0]")
                elif change == "variant":
                    row["definition"].update(variant="normal", templateSource="descriptionTemplate")
                    row["pool"].update(id="synthetic-critical", status="exact", basis="legendary_mod")
                elif change == "pool":
                    row["pool"].update(id="synthetic-critical", status="exact", basis="legendary_mod_same_template")
                else:
                    data["version"] = "0.4.2"
                with self.assertRaises(ValueError):
                    project(data, "a" * 64)

    def test_the_lucky_literal_cannot_be_silently_dropped_from_an_ordinary_critical_row(self):
        for canonical in (False, True):
            for key in ("luckyCriticalStrike", "lucky_critical_strike"):
                with self.subTest(canonical=canonical, key=key):
                    data = critical("critical_damage_modifier", "any")
                    if canonical:
                        data = project(data, "a" * 64)
                    data["modifiers"][0]["semantics"][key] = True
                    with self.assertRaises(ValueError):
                        summary(data) if canonical else project(data, "a" * 64)

    def test_compiler_043_preserves_ordinary_critical_cast_and_fixed_implicit_evidence(self):
        for data in (document(), critical("critical_damage_modifier", "spell"), casted(), fixed()):
            with self.subTest(version=data["version"]):
                expected = summary(project(data, "a" * 64))
                data["version"] = expected["version"] = "0.4.3"
                self.assertEqual(summary(project(data, "a" * 64)), expected)

    def test_the_compound_requires_a_literal_true_lucky_flag_in_both_representations(self):
        for canonical in (False, True):
            for invalid in (None, False, 1, "true", "missing"):
                with self.subTest(canonical=canonical, invalid=invalid):
                    data = project(lucky(), "a" * 64) if canonical else lucky()
                    semantics = data["modifiers"][0]["semantics"]
                    key = "lucky_critical_strike" if canonical else "luckyCriticalStrike"
                    if invalid == "missing":
                        del semantics[key]
                    else:
                        semantics[key] = invalid
                    with self.assertRaises(ValueError):
                        summary(data) if canonical else project(data, "a" * 64)

    def test_canonical_compound_bindings_cannot_move_to_a_different_native_source(self):
        for key, invalid in (("native_id", 51434431), ("template_sign", "+"), ("scope", "spell"),
                             ("unit", "flat"), ("targets", ["critical_rating"]), ("owner", "minion")):
            with self.subTest(key=key):
                data = project(lucky(), "a" * 64)
                data["modifiers"][0][key] = invalid
                with self.assertRaises(ValueError):
                    summary(data)

    def test_malformed_ordinary_critical_semantics_keep_a_controlled_contract_error(self):
        for canonical in (False, True):
            for invalid in (None, 17, []):
                with self.subTest(canonical=canonical, invalid=invalid):
                    data = critical("critical_damage_modifier", "any")
                    if canonical:
                        data = project(data, "a" * 64)
                    data["modifiers"][0]["semantics"] = invalid
                    with self.assertRaises(ValueError):
                        summary(data) if canonical else project(data, "a" * 64)

    def test_a_fixed_wand_implicit_retains_its_exact_proof_and_unresolved_pool(self):
        result = summary(project(fixed(), "a" * 64))
        self.assertEqual((result["modifiers"][0]["fixed_implicit"]["own_value"], result["modifiers"][0]["pool"],
                          result["catalog"]["flags"]),
                         ({"exact": "37.12500", "source": "DynArgs[0]"},
                          {"id": None, "status": "unresolved", "basis": "fixed_implicit_identity_unresolved"}, []))

    def test_the_new_version_preserves_all_legacy_ordinary_critical_and_cast_payloads(self):
        for data in (document(), critical("critical_damage_modifier", "spell"), casted()):
            with self.subTest(version=data["version"]):
                expected = summary(project(data, "a" * 64))
                data["version"] = "0.4.2"
                expected["version"] = "0.4.2"
                self.assertEqual(summary(project(data, "a" * 64)), expected)

    def test_fixed_proofs_cannot_be_attached_to_legacy_compiler_versions(self):
        for version in ("0.3.2", "0.4.0", "0.4.1"):
            with self.subTest(version=version):
                data = fixed()
                del data["catalog"]["documents"]["gear/one_handed/wand/i18n/en"]
                data["version"] = version
                with self.assertRaises(ValueError):
                    project(data, "a" * 64)

    def test_canonical_fixed_proofs_cannot_be_promoted_to_legacy_versions(self):
        for version in ("0.3.2", "0.4.0", "0.4.1"):
            with self.subTest(version=version):
                data = project(fixed(), "a" * 64)
                del data["catalog"]["documents"]["gear/one_handed/wand/i18n/en"]
                data["version"] = version
                with self.assertRaises(ValueError):
                    summary(data)

    def test_fixed_proofs_require_the_registered_native_id_family_scope_and_owner(self):
        for field, invalid in (("nativeId", 520021), ("nativeId", True), ("family", "increased_attribute"),
                               ("targets", ["cold"]), ("scope", "any"), ("owner", "minion"),
                               ("appliesToPlayerSpell", 1), ("templateSign", "-")):
            with self.subTest(field=field):
                data = fixed()
                data["modifiers"][0][field] = invalid
                with self.assertRaises(ValueError):
                    project(data, "a" * 64)

    def test_a_fixed_proof_cannot_move_to_another_affix_list(self):
        data = fixed()
        data["modifiers"][0].update(list="PrefixInfoList", path="sections.WearItems.data[0].sourceData.AffixList.PrefixInfoList[0]")
        with self.assertRaises(ValueError):
            project(data, "a" * 64)

    def test_implicit_definitions_cannot_claim_tiers_templates_or_a_resolved_pool(self):
        for block, field, invalid in (("definition", "implicit", 1), ("definition", "implicit", False),
                                      ("definition", "tier", "1"), ("definition", "templateSource", "descriptionTemplate"),
                                      ("definition", "variant", "normal"), ("pool", "id", "synthetic-wand"),
                                      ("pool", "status", "exact"), ("pool", "basis", "gear_entry")):
            with self.subTest(block=block, field=field):
                data = fixed()
                data["modifiers"][0][block][field] = invalid
                with self.assertRaises(ValueError):
                    project(data, "a" * 64)

    def test_an_implicit_definition_without_its_fixed_proof_is_not_a_tier_definition(self):
        data = fixed()
        del data["modifiers"][0]["fixedImplicit"]
        with self.assertRaises(ValueError):
            project(data, "a" * 64)

    def test_a_self_consistent_proof_still_requires_its_exact_parent_item(self):
        for field, invalid in (("definition", "other-wand"), ("tlidbId", "9138")):
            with self.subTest(field=field):
                data = fixed()
                data["items"][0]["identity"][field] = invalid
                if field == "definition":
                    data["modifiers"][0]["definition"]["id"] = invalid
                with self.assertRaises(ValueError):
                    project(data, "a" * 64)

    def test_declared_member_hashes_bind_the_proof_to_both_catalog_documents(self):
        for block in ("master", "english"):
            with self.subTest(block=block):
                data = fixed()
                data["modifiers"][0]["fixedImplicit"][block]["sha256"] = "d" * 64
                with self.assertRaises(ValueError):
                    project(data, "a" * 64)

    def test_the_own_lexeme_must_equal_the_source_row_even_when_its_number_is_equal(self):
        data = fixed()
        data["modifiers"][0]["fixedImplicit"]["ownValue"]["exact"] = "37.125"
        with self.assertRaises(ValueError):
            project(data, "a" * 64)

    def test_fixed_fraction_validation_rejects_rounding_and_ignores_the_callers_context(self):
        data = fixed()
        with localcontext() as context:
            context.prec = 1
            context.Emax = 0
            for signal in context.traps:
                context.traps[signal] = True
            result = summary(project(data, "a" * 64))
        self.assertEqual(result["modifiers"][0]["values"][0]["fraction"], "0.3712500")

    def test_a_rounded_fraction_cannot_replace_the_exact_fixed_percent(self):
        data = fixed()
        data["modifiers"][0]["values"][0]["fraction"] = "0.4"
        with self.assertRaises(ValueError):
            project(data, "a" * 64)

    def test_the_supported_english_role_is_not_a_master_or_a_season_source(self):
        data = fixed()
        data["catalog"]["documents"]["gear/one_handed/wand/i18n/en"]["seasonId"] = "SS13"
        result = summary(project(data, "a" * 64))
        self.assertEqual((result["catalog"]["flags"], result["catalog"]["documents"]["gear/one_handed/wand/i18n/en"]["role"]),
                         ([], "english"))

    def test_english_members_cannot_identify_source_items(self):
        data = fixed()
        data["items"][0]["identity"]["catalog"] = "gear/one_handed/wand/i18n/en"
        with self.assertRaises(ValueError):
            project(data, "a" * 64)

    def test_english_role_requires_the_exact_path_and_new_compiler(self):
        for change in ("version", "path", "role", "master", "missing"):
            with self.subTest(change=change):
                data = fixed()
                documents = data["catalog"]["documents"]
                if change == "version":
                    data["version"] = "0.4.1"
                elif change == "path":
                    documents["gear/one_handed/staff/i18n/en"] = documents.pop("gear/one_handed/wand/i18n/en")
                elif change == "master":
                    documents["gear/one_handed/wand/master"]["role"] = "english"
                elif change == "missing":
                    del documents["gear/one_handed/wand/i18n/en"]["role"]
                else:
                    documents["gear/one_handed/wand/i18n/en"]["role"] = True
                with self.assertRaises(ValueError):
                    project(data, "a" * 64)

    def test_missing_or_invalid_english_documents_cannot_support_fixed_proofs(self):
        for missing in (True, False):
            with self.subTest(missing=missing):
                data = fixed()
                if missing:
                    del data["catalog"]["documents"]["gear/one_handed/wand/i18n/en"]
                else:
                    data["catalog"]["documents"]["gear/one_handed/wand/i18n/en"].update(status="invalid", issue="identity_leaf")
                    data["catalog"]["flags"] = ["catalog_document_invalid"]
                with self.assertRaises(ValueError):
                    project(data, "a" * 64)

    def test_a_fixed_proof_cannot_be_hidden_on_an_omitted_row(self):
        data = fixed()
        data["omitted"][0]["fixedImplicit"] = data["modifiers"][0].pop("fixedImplicit")
        with self.assertRaises(ValueError):
            project(data, "a" * 64)

    def test_summary_rechecks_parent_identity_hash_and_row_value_bindings(self):
        for block, field, invalid in (("master", "tlidb_id", "9138"), ("master", "sha256", "e" * 64),
                                      ("english", "sha256", "e" * 64), ("own_value", "exact", "37.125")):
            with self.subTest(block=block, field=field):
                data = project(fixed(), "a" * 64)
                data["modifiers"][0]["fixed_implicit"][block][field] = invalid
                with self.assertRaises(ValueError):
                    summary(data)

    def test_fixed_proof_properties_are_projected_detached_and_private_extras_are_dropped(self):
        data = fixed()
        original = copy.deepcopy(data)
        data["modifiers"][0]["fixedImplicit"]["english"]["opaque"] = "PRIVATE-FIXED-CANARY"
        result = summary(project(data, "a" * 64))
        result["modifiers"][0]["fixed_implicit"]["own_value"]["exact"] = "changed"
        self.assertEqual((original["modifiers"][0]["fixedImplicit"]["ownValue"]["exact"], "PRIVATE-FIXED-CANARY" in json.dumps(result)),
                         ("37.12500", False))

    def test_cast_evidence_version_keeps_ordinary_and_critical_rows_unchanged(self):
        for data in (document(), critical("critical_damage_modifier", "spell")):
            expected = project(data, "a" * 64)["modifiers"]
            data["version"] = "0.4.1"
            with self.subTest(family=data["modifiers"][0]["family"]):
                self.assertEqual(summary(project(data, "a" * 64))["modifiers"], expected)

    def test_omitted_cast_evidence_keeps_one_own_roll_without_becoming_a_modifier(self):
        result = summary(project(casted(), "a" * 64))
        self.assertEqual((result["omitted"][0]["evidence"]["own_values"][0]["exact"],
                          result["omitted"][0]["evidence"]["arithmetic_ready"],
                          result["modifiers"], result["accounting"]),
                         ("17.8750", False, project(document(), "a" * 64)["modifiers"],
                          project(document(), "a" * 64)["accounting"]))

    def test_cast_evidence_requires_its_reviewed_version_and_own_omitted_item_binding(self):
        for field, value in (("version", "0.4.0"), ("version", "0.3.2"), ("nativeId", None),
                             ("nativeId", -31), ("nativeId", True), ("reason", "no_exact_definition"),
                             ("catalog", "gear/one_handed/staff/master"), ("evidence", None)):
            data = casted()
            row = data["omitted"][0]
            if field == "version":
                data[field] = value
            elif field == "catalog":
                row["evidence"]["definition"][field] = value
            else:
                row[field] = value
            with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                project(data, "a" * 64)

    def test_cast_evidence_summary_rejects_forged_activation_and_detaches_exact_values(self):
        data = summary(project(casted(), "a" * 64))
        copy = summary(data)
        copy["omitted"][0]["evidence"]["activation"] = "enabled"
        with self.assertRaises(ValueError):
            summary(copy)
        copy["omitted"][0]["evidence"]["own_values"][0]["exact"] = "9"
        self.assertEqual(data["omitted"][0]["evidence"]["own_values"][0]["exact"], "17.8750")

    def test_a_cast_evidence_issue_preserves_the_original_omission_without_partial_evidence(self):
        data = casted()
        del data["omitted"][0]["evidence"]
        data["omitted"][0]["evidenceIssue"] = "evidence_value_invalid"
        result = summary(project(data, "a" * 64))
        self.assertEqual((result["omitted"][0]["evidence_issue"], result["omitted"][0]["reason"],
                          "evidence" in result["omitted"][0], result["accounting"]),
                         ("evidence_value_invalid", "unsupported_family", False, project(document(), "a" * 64)["accounting"]))

    def test_cast_evidence_issues_cannot_be_unknown_combined_or_attached_to_legacy_versions(self):
        for version, issue, evidence in (("0.4.0", "evidence_value_invalid", False),
                                          ("0.4.1", "private-issue", False), ("0.4.1", None, False),
                                          ("0.4.1", "evidence_spec_invalid", True)):
            data = casted()
            data["version"] = version
            data["omitted"][0]["evidenceIssue"] = issue
            if not evidence:
                del data["omitted"][0]["evidence"]
            with self.subTest(version=version, issue=issue, evidence=evidence), self.assertRaises(ValueError):
                project(data, "a" * 64)

    def test_critical_inventory_preserves_fixed_non_arithmetic_semantics(self):
        for family, scope in (("critical_rating_increased", "any"), ("critical_damage_modifier", "any"),
                              ("critical_damage_modifier", "spell")):
            result = summary(project(critical(family, scope), "a" * 64))
            with self.subTest(family=family, scope=scope):
                self.assertEqual(result["modifiers"][0]["semantics"], {
                    "operation": "rating_increase" if family == "critical_rating_increased" else "unresolved",
                    "value_role": "non_additional_percent", "arithmetic_ready": False})

    def test_critical_semantics_cannot_choose_an_operator_or_enable_arithmetic(self):
        for key, value in (("operation", "relative_increase"), ("valueRole", "additional"),
                           ("arithmeticReady", True), ("arithmeticReady", 0)):
            data = critical("critical_damage_modifier", "spell")
            data["modifiers"][0]["semantics"][key] = value
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                project(data, "a" * 64)

    def test_critical_inventory_requires_the_exact_positive_template_sign(self):
        for sign in (None, "-"):
            data = critical("critical_damage_modifier", "spell")
            data["modifiers"][0]["templateSign"] = sign
            with self.subTest(sign=sign), self.assertRaises(ValueError):
                project(data, "a" * 64)
            result = project(critical("critical_damage_modifier", "spell"), "a" * 64)
            result["modifiers"][0]["template_sign"] = sign
            with self.subTest(canonical=sign), self.assertRaises(ValueError):
                summary(result)

    def test_new_critical_families_require_the_new_version_and_supported_scope(self):
        for family, scope, owner, version in (("critical_damage_modifier", "attack", "player", "0.4.0"),
                                              ("critical_rating_increased", "spell", "player", "0.4.0"),
                                              ("critical_damage_modifier", "any", "minion", "0.4.0"),
                                              ("critical_damage_modifier", "spell", "player", "0.3.2")):
            data = critical(family, scope)
            data["version"] = version
            data["modifiers"][0]["owner"] = owner
            with self.subTest(family=family, scope=scope, owner=owner, version=version), self.assertRaises(ValueError):
                project(data, "a" * 64)

    def test_critical_semantics_are_required_and_only_attached_to_critical_families(self):
        for change in ("missing", "noncritical"):
            data = critical("critical_damage_modifier", "spell")
            if change == "missing":
                del data["modifiers"][0]["semantics"]
            else:
                data["modifiers"][0].update(family="increased_damage", targets=["damage"])
            with self.subTest(change=change), self.assertRaises(ValueError):
                project(data, "a" * 64)

    def test_critical_summary_revalidates_flags_and_drops_unknown_semantic_properties(self):
        data = critical("critical_damage_modifier", "spell")
        data["modifiers"][0]["semantics"]["raw"] = "PRIVATE-CRITICAL-MARKER"
        result = project(data, "a" * 64)
        self.assertNotIn("PRIVATE-CRITICAL-MARKER", json.dumps(summary(result)))
        result["modifiers"][0]["semantics"]["arithmetic_ready"] = 0
        with self.assertRaises(ValueError):
            summary(result)

    def test_new_version_preserves_ordinary_rows_without_critical_semantics(self):
        data = document()
        data["version"] = "0.4.0"
        self.assertEqual(project(data, "a" * 64)["modifiers"], project(document(), "a" * 64)["modifiers"])

    def test_invalid_family_containers_have_a_controlled_contract_error(self):
        for family in ({}, [], None):
            data = document()
            data["modifiers"][0]["family"] = family
            with self.subTest(family=family), self.assertRaises(ValueError):
                project(data, "a" * 64)

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
