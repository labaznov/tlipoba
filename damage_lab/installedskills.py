"""Validate source-bound installed gem observations without claiming effective supports."""

import re


FORMAT = "tli-support-inventory-v0"
VERSION = "0.1.2"
RUNTIME = {"verified": False, "identity_verified": False, "freshness": "unknown", "activation": "unknown",
           "panel_skill": "unverified"}
CLIENT = "sections.SkillLayout.data"
SERVER = "sections.ServerSource.data.featuresInfo.skillLayout.slots"
MEMBERSHIPS = ("exact_instance", "no_client_instance", "instance_conflict", "ambiguous_instance",
               "ambiguous_server_key", "no_valid_server_entry", "no_server_match")
SERVER_ISSUES = ("invalid_server_slot", "duplicate_server_key")
TAB_ISSUES = ("invalid_tab", "duplicate_slot")
ROW_ISSUES = ("null_row", "invalid_row", "invalid_skill_id", "invalid_slot", "tab_index_mismatch")


def _name(value):
    return re.sub(r"([A-Z])", r"_\1", value).lower()


def _select(row, fields, canonical):
    names = {_name(field) if canonical else field: _name(field) for field in fields.split()}
    if type(row) is not dict or not set(names).issubset(row):
        raise ValueError("Installed skills require all named object fields")
    return {target: row[source] for source, target in names.items()}


def _list(value):
    if type(value) is not list:
        raise ValueError("Installed skills require JSON lists")
    return value


def _enum(value, choices):
    if type(value) is not str or value not in choices:
        raise ValueError("Installed skills contain an unsupported contract status")


def _hash(value):
    if type(value) is not str or not re.fullmatch(r"[0-9a-f]{64}", value, re.ASCII):
        raise ValueError("Installed skills require a lowercase source SHA-256")


def _integer(value, minimum, nullable):
    if nullable and value is None:
        return
    if type(value) is not int or (minimum is not None and value < minimum):
        raise ValueError("Installed skills require typed integers within the contract range")


def _fixed(row, expected):
    for key, value in expected.items():
        if value is None or value is False:
            if row[key] is not value:
                raise ValueError("Installed skills cannot promote fixed unknown or false claims")
        else:
            _enum(row[key], (value,))


def _domains(domains):
    for row in domains.values():
        _enum(row["status"], ("captured", "absent", "invalid", "not_captured"))
        for key, value in row.items():
            if key == "status":
                continue
            if row["status"] == "captured":
                _integer(value, 0, False)
            elif value is not None:
                raise ValueError("Installed skills absent domains require null counts")


def _coordinates(path, root, dimensions):
    if type(path) is not str:
        raise ValueError("Installed skills require fixed source-coordinate paths")
    match = re.fullmatch(re.escape(root) + r"\[(0|[1-9][0-9]*)\]" * dimensions, path, re.ASCII)
    if match is None:
        raise ValueError("Installed skills require fixed source-coordinate paths")
    try:
        return tuple(int(value) for value in match.groups())
    except ValueError:
        raise ValueError("Installed skills source coordinates exceed the integer representation limit") from None


def _member(row, server):
    for key in ("slot", "skill_id", "gem_level"):
        _integer(row[key], 1, True)
    _fixed(row, {"level_status": "ok" if row["gem_level"] is not None else "invalid_level"})
    for value in row["client_flags"].values():
        if value is not None and type(value) is not bool:
            raise ValueError("Installed skills client flags require booleans or null")
    choices = MEMBERSHIPS if server["status"] == "captured" else ("server_layer_" + server["status"],)
    _enum(row["membership"], choices)
    if row["membership"] == "exact_instance":
        _integer(row["server_key"], None, False)
        if _coordinates(row["server_path"], SERVER, 1)[0] >= server["slots"]:
            raise ValueError("Installed skills server coordinates exceed the captured domain")
        if row["server_status"] is not None:
            _enum(row["server_status"], ("Activating", "other"))
    elif any(row[key] is not None for key in ("server_key", "server_status", "server_path")):
        raise ValueError("Installed skills nonexact membership requires null server fields")


def _groups(result):
    client, server = result["domains"]["client"], result["domains"]["server"]
    if result["groups"] and client["status"] != "captured":
        raise ValueError("Installed skills groups require a captured client domain")
    position, number, keys, paths = -1, 0, set(), set()
    for index, group in enumerate(result["groups"], 1):
        _integer(group["tab_position"], 0, False)
        _integer(group["tab_idx"], None, True)
        if (group["alias"] != f"group[{index}]" or not group["members"]
                or not position < group["tab_position"] < client["tabs"]):
            raise ValueError("Installed skills groups require ordered source coordinates and aliases")
        position, offset = group["tab_position"], -1
        for row in group["members"]:
            number += 1
            coordinates = _coordinates(row["path"], CLIENT, 2)
            if row["alias"] != f"gem[{number}]" or coordinates[0] != position or coordinates[1] <= offset:
                raise ValueError("Installed skills members require distinct ordered aliases and coordinates")
            offset = coordinates[1]
            _member(row, server)
            if row["membership"] == "exact_instance":
                if row["server_key"] in keys or row["server_path"] in paths:
                    raise ValueError("Installed skills exact memberships require distinct server keys and paths")
                keys.add(row["server_key"])
                paths.add(row["server_path"])
        slots = [row["slot"] for row in group["members"] if row["slot"] is not None]
        status = "ambiguous_slot" if len(slots) != len(set(slots)) else "no_primary_slot" if 1 not in slots else "ok"
        _fixed(group, {"status": status})


def _relationships(result):
    expected = []
    for group in result["groups"]:
        if group["status"] != "ok":
            continue
        primary = next(row for row in group["members"] if row["slot"] == 1)
        if primary["skill_id"] is not None:
            expected.extend((group["alias"], primary["alias"], row["alias"]) for row in group["members"]
                            if row is not primary and row["skill_id"] is not None and row["slot"] is not None)
    for row in result["relationships"]:
        _fixed(row, {"status": "installed_observed", "basis": "client_tab_co_membership", "activation": "unknown",
                     "effective_level": None, "effective_level_reason": "gem_level_is_not_effective_level",
                     "panel_skill": "unverified"})
    actual = [(row["group"], row["primary"], row["secondary"]) for row in result["relationships"]]
    if actual != expected:
        raise ValueError("Installed skills relationships must cover valid primary and secondary co-membership exactly")


def _issues(result):
    buckets = {reason: set() for reason in SERVER_ISSUES + TAB_ISSUES + ROW_ISSUES}
    client, server = result["domains"]["client"], result["domains"]["server"]
    members = {row["path"]: row for group in result["groups"] for row in group["members"]}
    used = {group["tab_position"] for group in result["groups"]}
    invalid = set()
    for row in result["issues"]:
        reason, path = row["reason"], row["path"]
        _enum(reason, tuple(buckets))
        domain = server if reason in SERVER_ISSUES else client
        root, dimensions, count = (SERVER, 1, "slots") if reason in SERVER_ISSUES else (
            CLIENT, 1 if reason in TAB_ISSUES else 2, "tabs")
        coordinates = _coordinates(path, root, dimensions)
        if domain["status"] != "captured" or coordinates[0] >= domain[count] or path in buckets[reason]:
            raise ValueError("Installed skills issues require distinct captured source coordinates")
        buckets[reason].add(path)
        if reason == "invalid_tab":
            invalid.add(coordinates[0])
        elif reason in ROW_ISSUES:
            used.add(coordinates[0])
            if (reason in ("null_row", "invalid_row")) == (path in members):
                raise ValueError("Installed skills row issues must agree with retained member coordinates")
    if (invalid & used or buckets["null_row"] & buckets["invalid_row"]
            or (client["status"] == "captured" and len(used | invalid) + client["null_tabs"] > client["tabs"])):
        raise ValueError("Installed skills malformed or null tabs cannot contain retained rows")
    for path, row in members.items():
        for field, reason in (("skill_id", "invalid_skill_id"), ("slot", "invalid_slot")):
            if (row[field] is None) != (path in buckets[reason]):
                raise ValueError("Installed skills invalid fields require matching explicit issues")
    expected = {f"{CLIENT}[{group['tab_position']}]" for group in result["groups"] if group["status"] == "ambiguous_slot"}
    if buckets["duplicate_slot"] != expected:
        raise ValueError("Installed skills duplicate-slot issues must agree with group status")
    for group in result["groups"]:
        paths = {row["path"] for row in group["members"]}
        mismatches = paths & buckets["tab_index_mismatch"]
        if ((group["tab_idx"] is None and not mismatches) or (group["tab_idx"] is not None
                and mismatches != (paths if group["tab_idx"] != group["tab_position"] + 1 else set()))):
            raise ValueError("Installed skills tab-index issues must agree with the reported common index")
    return buckets


def _unmatched(result, issues):
    server, client = result["domains"]["server"], result["domains"]["client"]
    exact = {row["server_path"] for group in result["groups"] for row in group["members"]
             if row["membership"] == "exact_instance"}
    unmatched, index = {}, -1
    for row in result["unmatched_server_slots"]:
        _enum(row["reason"], ("ambiguous_server_slot", "client_layer_absent", "no_exact_instance_match"))
        position = _coordinates(row["path"], SERVER, 1)[0]
        if (server["status"] != "captured" or not index < position < server["slots"] or row["path"] in exact
                or row["path"] in issues["invalid_server_slot"]):
            raise ValueError("Installed skills unmatched slots require separate ordered captured coordinates")
        if ((row["reason"] == "client_layer_absent" and client["status"] == "captured")
                or (row["reason"] == "no_exact_instance_match" and client["status"] != "captured")):
            raise ValueError("Installed skills unmatched reason must agree with the client domain")
        index = position
        unmatched[row["path"]] = row["reason"]
    if exact & issues["invalid_server_slot"]:
        raise ValueError("Installed skills exact memberships cannot reference malformed server slots")
    for path in issues["duplicate_server_key"]:
        if path not in issues["invalid_server_slot"] and unmatched.get(path) != "ambiguous_server_slot":
            raise ValueError("Installed skills duplicate server keys cannot reconcile as unique memberships")


def _counts(result):
    client, server = result["domains"]["client"], result["domains"]["server"]
    members = [row for group in result["groups"] for row in group["members"]]
    if client["status"] == "captured" and (
            client["rows"] != len(members) or client["null_tabs"] + len(result["groups"]) > client["tabs"]
            or client["null_rows"] != sum(row["reason"] == "null_row" for row in result["issues"])):
        raise ValueError("Installed skills client counts must reconcile with retained rows and gaps")
    if server["status"] == "captured" and (
            server["reconciled"] != sum(row["membership"] == "exact_instance" for row in members)
            or server["unmatched"] != len(result["unmatched_server_slots"])
            or server["slots"] != server["null_slots"] + server["reconciled"] + server["unmatched"]
            + sum(row["reason"] == "invalid_server_slot" for row in result["issues"])):
        raise ValueError("Installed skills server counts must reconcile with every slot disposition")


def _project(document, source_sha256, canonical):
    result = _select(document, "format version source runtime domains groups relationships unmatchedServerSlots issues", canonical)
    result["source"] = _select(result["source"], "sha256 binding", canonical)
    result["runtime"] = _select(result["runtime"], "verified identityVerified freshness activation panelSkill", canonical)
    domains = _select(result["domains"], "client server", canonical)
    result["domains"] = {
        "client": _select(domains["client"], "status tabs nullTabs rows nullRows", canonical),
        "server": _select(domains["server"], "status slots nullSlots reconciled unmatched", canonical)}
    _hash(source_sha256)
    _hash(result["source"]["sha256"])
    _fixed(result, {"format": FORMAT, "version": VERSION})
    _fixed(result["source"], {"sha256": source_sha256, "binding": "caller_supplied"})
    _fixed(result["runtime"], RUNTIME)
    _domains(result["domains"])
    groups = []
    for row in _list(result["groups"]):
        group = _select(row, "alias tabPosition tabIdx status members", canonical)
        members = []
        for entry in _list(group["members"]):
            member = _select(entry, "alias slot skillId gemLevel levelStatus clientFlags path membership "
                             "serverKey serverStatus serverPath", canonical)
            member["client_flags"] = _select(member["client_flags"], "valid isActive", canonical)
            members.append(member)
        group["members"] = members
        groups.append(group)
    result["groups"] = groups
    result["relationships"] = [_select(row, "group primary secondary status basis activation effectiveLevel "
                                        "effectiveLevelReason panelSkill", canonical)
                               for row in _list(result["relationships"])]
    for field in ("unmatched_server_slots", "issues"):
        result[field] = [_select(row, "path reason", canonical) for row in _list(result[field])]
    _groups(result)
    _relationships(result)
    _unmatched(result, _issues(result))
    _counts(result)
    return result


def project(document, source_sha256):
    """Return a detached snake_case inventory bound to the caller's exact source hash."""
    return _project(document, source_sha256, False)


def summary(canonical):
    """Revalidate already projected observations without retaining unknown properties."""
    source = _select(canonical, "source", True)["source"]
    source = _select(source, "sha256", True)
    return _project(canonical, source["sha256"], True)
