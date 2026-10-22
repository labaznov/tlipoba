import copy
import json
import unittest

from damage_lab.installedskills import project, summary


def member(number, tab, offset, slot, skill, level, server, key):
    """A fictional installed gem with public definition and source coordinates only."""
    return {"alias": f"gem[{number}]", "slot": slot, "skillId": skill, "gemLevel": level,
            "levelStatus": "ok" if level is not None else "invalid_level",
            "clientFlags": {"valid": True, "isActive": False},
            "path": f"sections.SkillLayout.data[{tab}][{offset}]", "membership": "exact_instance",
            "serverKey": key, "serverStatus": "Activating" if number == 1 else None,
            "serverPath": f"sections.ServerSource.data.featuresInfo.skillLayout.slots[{server}]"}


def document():
    """A source-bound synthetic inventory with gaps, null entries and two separate groups."""
    return {
        "format": "tli-support-inventory-v0", "version": "0.1.2",
        "source": {"sha256": "a" * 64, "binding": "caller_supplied"},
        "runtime": {"verified": False, "identityVerified": False, "freshness": "unknown",
                    "activation": "unknown", "panelSkill": "unverified"},
        "domains": {"client": {"status": "captured", "tabs": 4, "nullTabs": 1, "rows": 4, "nullRows": 1},
                    "server": {"status": "captured", "slots": 7, "nullSlots": 1, "reconciled": 4, "unmatched": 1}},
        "groups": [
            {"alias": "group[1]", "tabPosition": 0, "tabIdx": 1, "status": "ok", "members": [
                member(1, 0, 0, 1, 90017, 7, 0, 17), member(2, 0, 2, 4, 90029, 13, 2, 231)]},
            {"alias": "group[2]", "tabPosition": 2, "tabIdx": 3, "status": "ok", "members": [
                member(3, 2, 0, 1, 90041, 19, 3, 59), member(4, 2, 1, 6, 90053, None, 4, 401)]}],
        "relationships": [
            {"group": f"group[{group}]", "primary": f"gem[{primary}]", "secondary": f"gem[{secondary}]",
             "status": "installed_observed", "basis": "client_tab_co_membership", "activation": "unknown",
             "effectiveLevel": None, "effectiveLevelReason": "gem_level_is_not_effective_level",
             "panelSkill": "unverified"} for group, primary, secondary in ((1, 1, 2), (2, 3, 4))],
        "unmatchedServerSlots": [{"path": "sections.ServerSource.data.featuresInfo.skillLayout.slots[5]",
                                  "reason": "no_exact_instance_match"}],
        "issues": [{"path": "sections.SkillLayout.data[0][1]", "reason": "null_row"},
                   {"path": "sections.ServerSource.data.featuresInfo.skillLayout.slots[6]", "reason": "invalid_server_slot"}]}


def absent(domain, status):
    """Represent a missing observed layer with null counts instead of an empty installation."""
    data = document()
    data["domains"][domain] = {key: status if key == "status" else None for key in data["domains"][domain]}
    if domain == "server":
        for group in data["groups"]:
            for row in group["members"]:
                row.update(membership="server_layer_" + status, serverKey=None, serverStatus=None, serverPath=None)
        data["unmatchedServerSlots"] = []
        data["issues"] = [row for row in data["issues"] if row["path"].startswith("sections.SkillLayout")]
    else:
        data["groups"], data["relationships"] = [], []
        data["domains"]["server"].update(reconciled=0, unmatched=5)
        data["unmatchedServerSlots"] = [{"path": f"sections.ServerSource.data.featuresInfo.skillLayout.slots[{index}]",
                                         "reason": "client_layer_absent"} for index in (0, 2, 3, 4, 5)]
        data["issues"] = [row for row in data["issues"] if row["path"].startswith("sections.ServerSource")]
    return data


class InstalledSkillsTests(unittest.TestCase):
    """Preserve observed installation without inferring active supports or effective levels."""

    def test_projection_preserves_safe_snake_case_installation_and_unknown_effective_level(self):
        result = summary(project(document(), "a" * 64))
        self.assertEqual((result["groups"][0]["members"][1]["skill_id"],
                          result["groups"][1]["members"][1]["gem_level"], result["relationships"][0]), (
            90029, None, {"group": "group[1]", "primary": "gem[1]", "secondary": "gem[2]",
                          "status": "installed_observed", "basis": "client_tab_co_membership", "activation": "unknown",
                          "effective_level": None, "effective_level_reason": "gem_level_is_not_effective_level",
                          "panel_skill": "unverified"}))

    def test_format_version_and_source_binding_are_exact(self):
        for field, value in (("format", "tli-support-inventory-error-v1"), ("version", "0.1.1"),
                              ("version", None), ("sha256", "b" * 64), ("sha256", "A" * 64),
                              ("sha256", None), ("binding", "identity_verified")):
            data = document()
            (data if field in ("format", "version") else data["source"])[field] = value
            with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                project(data, "a" * 64)
        for digest in (None, False, "A" * 64, "unbound"):
            with self.subTest(digest=digest), self.assertRaises(ValueError):
                project(document(), digest)

    def test_runtime_cannot_be_promoted_or_replaced_with_boolean_like_numbers(self):
        for field, values in (("verified", (True, 0, None)), ("identityVerified", (True, 0)),
                               ("freshness", ("verified", False)), ("activation", ("active", None)),
                               ("panelSkill", ("verified", True))):
            for value in values:
                data = document()
                data["runtime"][field] = value
                with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                    project(data, "a" * 64)

    def test_domain_counts_require_nonnegative_integers_and_absent_counts_are_null(self):
        for domain, field, value in (("client", "rows", True), ("server", "slots", -1),
                                      ("client", "nullRows", 1.0), ("server", "reconciled", None),
                                      ("client", "status", "complete"), ("server", "status", "absent")):
            data = document()
            data["domains"][domain][field] = value
            with self.subTest(domain=domain, field=field), self.assertRaises(ValueError):
                project(data, "a" * 64)

    def test_member_numbers_flags_and_statuses_use_only_the_released_types(self):
        for field, value in (("slot", True), ("slot", 0), ("skillId", False), ("skillId", 1.5),
                              ("gemLevel", "13"), ("gemLevel", 0), ("levelStatus", "effective"),
                              ("clientFlags", {"valid": 0, "isActive": True}), ("membership", "slot_formula"),
                              ("serverKey", True), ("serverStatus", "PRIVATE-PAYLOAD"), ("serverPath", "opaque")):
            data = document()
            data["groups"][0]["members"][0][field] = value
            with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                project(data, "a" * 64)

    def test_group_and_gem_aliases_and_coordinates_are_unique_and_source_ordered(self):
        for change in ("group_alias", "gem_alias", "tab_bool", "tab_duplicate", "tab_outside", "path_tab", "path_duplicate",
                       "tab_idx_bool", "empty_group"):
            data = document()
            if change == "group_alias":
                data["groups"][1]["alias"] = "group[1]"
            elif change == "gem_alias":
                data["groups"][1]["members"][0]["alias"] = "gem[1]"
            elif change in ("tab_bool", "tab_duplicate", "tab_outside"):
                data["groups"][1]["tabPosition"] = {"tab_bool": True, "tab_duplicate": 0, "tab_outside": 4}[change]
            elif change in ("path_tab", "path_duplicate"):
                data["groups"][0]["members"][1]["path"] = ("sections.SkillLayout.data[1][2]" if change == "path_tab"
                                                            else "sections.SkillLayout.data[0][0]")
            elif change == "tab_idx_bool":
                data["groups"][0]["tabIdx"] = False
            else:
                data["groups"][0]["members"] = []
            with self.subTest(change=change), self.assertRaises(ValueError):
                project(data, "a" * 64)

    def test_only_exact_instance_members_can_keep_server_fields(self):
        for membership in ("no_client_instance", "instance_conflict", "ambiguous_instance", "ambiguous_server_key",
                            "no_server_match", "no_valid_server_entry", "server_layer_absent"):
            data = document()
            data["groups"][0]["members"][0]["membership"] = membership
            with self.subTest(membership=membership), self.assertRaises(ValueError):
                project(data, "a" * 64)
        for field in ("serverKey", "serverPath"):
            data = document()
            data["groups"][0]["members"][0][field] = None
            with self.subTest(field=field), self.assertRaises(ValueError):
                project(data, "a" * 64)

    def test_exact_instance_members_cannot_share_server_key_or_path(self):
        for field in ("serverKey", "serverPath"):
            data = document()
            data["groups"][1]["members"][0][field] = data["groups"][0]["members"][0][field]
            with self.subTest(field=field), self.assertRaises(ValueError):
                project(data, "a" * 64)

    def test_group_status_cannot_hide_duplicate_slots_or_missing_primary(self):
        for slot in (1, 2):
            data = document()
            data["groups"][0]["members"][0]["slot"] = slot
            data["groups"][0]["members"][1]["slot"] = slot
            with self.subTest(slot=slot), self.assertRaises(ValueError):
                project(data, "a" * 64)

    def test_relationships_only_join_primary_and_secondary_of_the_same_valid_group(self):
        for field, value in (("primary", "gem[2]"), ("secondary", "gem[3]"), ("group", "group[2]"),
                              ("secondary", "gem[1]"), ("primary", "gem[99]")):
            data = document()
            data["relationships"][0][field] = value
            with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                project(data, "a" * 64)

    def test_relationships_never_upgrade_activation_effective_level_or_panel_identity(self):
        for field, value in (("status", "active"), ("basis", "server_key_formula"), ("activation", True),
                              ("effectiveLevel", 13), ("effectiveLevelReason", "verified"), ("panelSkill", "verified")):
            data = document()
            data["relationships"][0][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                project(data, "a" * 64)

    def test_duplicate_missing_or_invalid_member_relationships_cannot_claim_a_complete_inventory(self):
        for change in ("duplicate", "missing", "invalid_primary", "invalid_secondary", "ambiguous"):
            data = document()
            if change == "duplicate":
                data["relationships"].append(copy.deepcopy(data["relationships"][0]))
            elif change == "missing":
                data["relationships"].pop()
            elif change in ("invalid_primary", "invalid_secondary"):
                data["groups"][0]["members"][0 if change == "invalid_primary" else 1]["skillId"] = None
            else:
                data["groups"][0]["members"][1]["slot"] = 1
                data["groups"][0]["status"] = "ambiguous_slot"
            with self.subTest(change=change), self.assertRaises(ValueError):
                project(data, "a" * 64)

    def test_counts_must_reconcile_with_members_null_rows_and_server_disposition(self):
        for domain, field, value in (("client", "rows", 3), ("client", "nullRows", 0), ("client", "nullTabs", 4),
                                      ("server", "reconciled", 3), ("server", "unmatched", 0),
                                      ("server", "nullSlots", 0), ("server", "slots", 8)):
            data = document()
            data["domains"][domain][field] = value
            with self.subTest(domain=domain, field=field), self.assertRaises(ValueError):
                project(data, "a" * 64)

    def test_unavailable_domains_preserve_null_counts_and_observed_client_relationships(self):
        for domain in ("client", "server"):
            for status in ("absent", "invalid", "not_captured"):
                result = summary(project(absent(domain, status), "a" * 64))
                with self.subTest(domain=domain, status=status):
                    self.assertEqual((result["domains"][domain]["status"], result["domains"][domain].get("rows", None),
                                      len(result["relationships"]), result["runtime"]["activation"]),
                                     (status, None, 2 if domain == "server" else 0, "unknown"))

    def test_issues_and_unmatched_slots_accept_only_fixed_vocabulary_and_coordinates(self):
        for change in ("issue_reason", "issue_path", "issue_outside", "issue_member", "unmatched_reason", "unmatched_path",
                       "unmatched_outside", "unmatched_exact", "unmatched_duplicate"):
            data = document()
            if change == "issue_reason":
                data["issues"].append({"path": "sections.SkillLayout.data[0]", "reason": {"private": "PAYLOAD"}})
            elif change == "issue_path":
                data["issues"][1]["path"] = "PRIVATE-PAYLOAD"
            elif change == "issue_outside":
                data["issues"][1]["path"] = "sections.ServerSource.data.featuresInfo.skillLayout.slots[7]"
            elif change == "issue_member":
                data["issues"][0]["path"] = "sections.SkillLayout.data[0][0]"
            elif change == "unmatched_reason":
                data["unmatchedServerSlots"][0]["reason"] = "identity_verified"
            elif change == "unmatched_path":
                data["unmatchedServerSlots"][0]["path"] = "PRIVATE-PAYLOAD"
            elif change == "unmatched_outside":
                data["unmatchedServerSlots"][0]["path"] = "sections.ServerSource.data.featuresInfo.skillLayout.slots[7]"
            elif change == "unmatched_exact":
                data["unmatchedServerSlots"][0]["path"] = "sections.ServerSource.data.featuresInfo.skillLayout.slots[0]"
            else:
                data["unmatchedServerSlots"].append(copy.deepcopy(data["unmatchedServerSlots"][0]))
                data["domains"]["server"].update(slots=8, unmatched=2)
            with self.subTest(change=change), self.assertRaises(ValueError):
                project(data, "a" * 64)

    def test_duplicate_or_contradictory_issues_cannot_hide_impossible_rows(self):
        for change in ("duplicate", "invalid_skill", "invalid_slot", "invalid_tab", "duplicate_slot", "tab_mismatch"):
            data = document()
            if change == "duplicate":
                data["issues"].append(copy.deepcopy(data["issues"][0]))
                data["domains"]["client"]["nullRows"] = 2
            else:
                reason = {"invalid_skill": "invalid_skill_id", "invalid_slot": "invalid_slot", "invalid_tab": "invalid_tab",
                          "duplicate_slot": "duplicate_slot", "tab_mismatch": "tab_index_mismatch"}[change]
                path = "sections.SkillLayout.data[0]" if change in ("invalid_tab", "duplicate_slot") else "sections.SkillLayout.data[0][0]"
                data["issues"].append({"path": path, "reason": reason})
            with self.subTest(change=change), self.assertRaises(ValueError):
                project(data, "a" * 64)

    def test_nonexact_membership_retains_only_a_reason_with_all_server_fields_null(self):
        for membership in ("no_client_instance", "instance_conflict", "ambiguous_instance", "ambiguous_server_key",
                            "no_valid_server_entry", "no_server_match"):
            data = document()
            data["groups"][0]["members"][1].update(membership=membership, serverKey=None, serverStatus=None, serverPath=None)
            data["domains"]["server"].update(reconciled=3, unmatched=2)
            data["unmatchedServerSlots"].insert(0, {"path": "sections.ServerSource.data.featuresInfo.skillLayout.slots[2]",
                                                   "reason": "no_exact_instance_match"})
            with self.subTest(membership=membership):
                self.assertEqual(project(data, "a" * 64)["groups"][0]["members"][1]["server_key"], None)

    def test_ambiguous_or_primaryless_groups_have_no_relationships(self):
        for status in ("ambiguous_slot", "no_primary_slot"):
            data = document()
            data["groups"][0]["status"] = status
            if status == "ambiguous_slot":
                data["groups"][0]["members"][1]["slot"] = 1
                data["issues"].append({"path": "sections.SkillLayout.data[0]", "reason": "duplicate_slot"})
            else:
                data["groups"][0]["members"][0]["slot"] = 2
            data["relationships"].pop(0)
            with self.subTest(status=status):
                self.assertEqual(len(project(data, "a" * 64)["relationships"]), 1)

    def test_invalid_member_fields_and_tab_index_disagreements_remain_explicit(self):
        for change in ("skill", "slot", "tab", "mixed_tab"):
            data = document()
            if change in ("skill", "slot"):
                data["groups"][0]["members"][1]["skillId" if change == "skill" else "slot"] = None
                data["issues"].append({"path": "sections.SkillLayout.data[0][2]",
                                       "reason": "invalid_skill_id" if change == "skill" else "invalid_slot"})
                data["relationships"].pop(0)
            else:
                data["groups"][0]["tabIdx"] = -7 if change == "tab" else None
                for offset in ((0, 2) if change == "tab" else (2,)):
                    data["issues"].append({"path": f"sections.SkillLayout.data[0][{offset}]", "reason": "tab_index_mismatch"})
            with self.subTest(change=change):
                self.assertEqual(project(data, "a" * 64)["runtime"]["activation"], "unknown")

    def test_duplicate_server_key_issues_cannot_coexist_with_unique_membership_claims(self):
        data = document()
        data["issues"].append({"path": "sections.ServerSource.data.featuresInfo.skillLayout.slots[0]",
                               "reason": "duplicate_server_key"})
        with self.assertRaises(ValueError):
            project(data, "a" * 64)

    def test_ambiguous_unmatched_server_slots_can_share_duplicate_key_issues(self):
        data = document()
        data["unmatchedServerSlots"][0]["reason"] = "ambiguous_server_slot"
        data["issues"].append({"path": "sections.ServerSource.data.featuresInfo.skillLayout.slots[5]",
                               "reason": "duplicate_server_key"})
        self.assertEqual(project(data, "a" * 64)["unmatched_server_slots"][0]["reason"], "ambiguous_server_slot")

    def test_canonical_summary_rechecks_members_relationships_counts_and_fixed_unknowns(self):
        for change in ("runtime", "alias", "membership", "level", "edge", "count", "hash"):
            data = project(document(), "a" * 64)
            if change == "runtime":
                data["runtime"]["identity_verified"] = 0
            elif change == "alias":
                data["groups"][1]["members"][0]["alias"] = "gem[1]"
            elif change == "membership":
                data["groups"][0]["members"][0]["membership"] = "no_server_match"
            elif change == "level":
                data["relationships"][0]["effective_level"] = 7
            elif change == "edge":
                data["relationships"][0]["secondary"] = "gem[4]"
            elif change == "count":
                data["domains"]["server"]["reconciled"] = 0
            else:
                data["source"]["sha256"] = "PRIVATE-MARKER"
            with self.subTest(change=change), self.assertRaises(ValueError):
                summary(data)

    def test_unknown_raw_identifiers_and_nested_payloads_are_discarded_at_every_depth(self):
        def mark(value):
            if type(value) is dict:
                for entry in list(value.values()):
                    mark(entry)
                value["accountId"] = {"raw_tree": "PRIVATE-INSTALLED-MARKER"}
            elif type(value) is list:
                for entry in value:
                    mark(entry)

        data = document()
        mark(data)
        result = project(data, "a" * 64)
        mark(result)
        self.assertNotIn("PRIVATE-INSTALLED-MARKER", json.dumps(summary(result)))

    def test_result_mutations_leave_all_input_fields_unchanged(self):
        data = document()
        before = copy.deepcopy(data)
        result = project(data, "a" * 64)
        result["groups"][0]["members"][0]["client_flags"]["valid"] = None
        result["relationships"][0]["effective_level"] = 99
        result["issues"][0]["reason"] = "changed"
        self.assertEqual(data, before)

    def test_input_mutations_cannot_change_the_canonical_summary(self):
        data = document()
        normalized = summary(project(data, "a" * 64))
        data["groups"][0]["members"][0]["skillId"] = 99999
        data["groups"][0]["members"][0]["clientFlags"]["valid"] = None
        self.assertEqual((normalized["groups"][0]["members"][0]["skill_id"],
                          normalized["groups"][0]["members"][0]["client_flags"]["valid"]), (90017, True))

    def test_bad_containers_and_errors_are_controlled_without_private_payload(self):
        for data in (None, [], {}, {"source": {"sha256": "PRIVATE-INSTALLED-MARKER"}}):
            with self.subTest(data=data), self.assertRaises(ValueError) as caught:
                project(data, "a" * 64)
            self.assertNotIn("PRIVATE-INSTALLED-MARKER", str(caught.exception))
