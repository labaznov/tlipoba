"""Project saved-controller evidence without verifying a network or build identity."""

import re
from datetime import datetime


FIELDS = {
    "transport": ("kind", "verified"),
    "identity": ("basis", "codeFingerprint", "expectedCodeMatched", "descriptorMatch", "payloadSelfIdentifies",
                 "captureVerifiedFlag", "authorConsistency", "playerIdConsistency", "codeStructure", "codeMintedAt"),
    "gate": ("status", "featureStatus", "realFeatureStatus"),
    "freshness": ("status", "capturedAt", "capturedAtStatus", "codeMintedAt", "payloadGeneratedAt", "isOldData"),}
SECTIONS = ("PlayeBaseInfo", "WearItems", "SkillLayout", "GeniusInfos", "HeroCharacter")
STATUSES = ("invalid_payload", "invalid_code", "planner_code", "code_mismatch", "not_viewable", "inconsistent",
            "incomplete", "matched_saved_code", "unbound")
PATHS = ("buildIdentity.buildCode", "buildIdentity.buildCodeVerified", "capturedAt",
         "sections.ServerSource.data.featureStatus", "sections.ServerSource.data.realFeatureStatus",
         "sections.ServerSource.data.playerId", "sections.ServerSource.data.baseInfo",
         "sections.ServerSource.data.version", "sections.ServerSource.data.**.Version (affix records)")
WARNINGS = ("code_structure_other", "code_minted_after_capture", "data_version_invalid")


def _name(value):
    return re.sub(r"([A-Z])", r"_\1", value).lower()


def _object(value, fields):
    if type(value) is not dict or not set(fields).issubset(value):
        raise ValueError("Build resolution requires all named contract fields")


def _select(row, fields):
    _object(row, fields)
    return {_name(key): row[key] for key in fields}


def _enum(value, choices):
    if type(value) is not str or value not in choices:
        raise ValueError("Build resolution has an unknown contract status")


def _list(value):
    if type(value) is not list:
        raise ValueError("Build resolution requires JSON lists")
    return list(value)


def _identity(row):
    _enum(row["basis"], ("none", "saved_controller_code"))
    _enum(row["descriptor_match"], ("not_supplied", "candidate_match", "mismatch", "invalid", "not_comparable"))
    for field in ("author_consistency", "player_id_consistency"):
        _enum(row[field], ("consistent", "inconsistent", "unknown"))
    for field in ("expected_code_matched", "capture_verified_flag"):
        if row[field] is not None and type(row[field]) is not bool:
            raise ValueError("Build resolution match and capture flags require booleans or null")
    if row["code_structure"] is not None:
        _enum(row["code_structure"], ("uuid_v1", "other"))
    value = row["code_fingerprint"]
    if value is not None and (type(value) is not str or not re.fullmatch("sha256:[0-9a-f]{8}", value)):
        raise ValueError("Build resolution code fingerprint must be redacted")
    saved = row["basis"] == "saved_controller_code"
    if (saved != (value is not None) or saved != (row["code_structure"] is not None)
            or (row["code_structure"] == "uuid_v1") != (row["code_minted_at"] is not None)
            or (not saved and row["expected_code_matched"] is not None)):
        raise ValueError("Build resolution identity claims require consistent saved-code evidence")


def _timestamp(value):
    if type(value) is not str or not re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d{6})?[+-]\d\d:\d\d", value):
        raise ValueError("Build resolution timestamps require normalized zoned ISO dates")
    try:
        moment = datetime.fromisoformat(value)
    except ValueError:
        raise ValueError("Build resolution timestamp is not a valid date") from None
    if moment.isoformat() != value:
        raise ValueError("Build resolution timestamps must retain their normalized form")
    return moment


def _times(identity, freshness):
    _enum(freshness["captured_at_status"], ("valid", "invalid", "absent"))
    if freshness["captured_at_status"] == "valid":
        _timestamp(freshness["captured_at"])
    elif freshness["captured_at"] is not None:
        raise ValueError("Unestablished build resolution timestamps must be null")
    if identity["code_minted_at"] is not None:
        _timestamp(identity["code_minted_at"])
    if freshness["code_minted_at"] != identity["code_minted_at"]:
        raise ValueError("Build resolution minted timestamps must agree")


def _gate(row):
    for field in ("feature_status", "real_feature_status"):
        _enum(row[field], ("Feature_CanView", "other", "missing"))
    values = (row["feature_status"], row["real_feature_status"])
    status = "denied" if "other" in values else "missing" if "missing" in values else "allowed"
    if row["status"] != status:
        raise ValueError("Build resolution gate status must agree with its recorded values")


def _coverage(row, status):
    for value in row["data_version"].values():
        if value is not None and type(value) is not int:
            raise ValueError("Build resolution data versions require integers or null")
    counts = row["affix_versions"]
    if any(type(value) is not int or value < 0 for value in counts.values()):
        raise ValueError("Build resolution counts must be nonnegative integers")
    if counts["mismatched"] > counts["checked"] or (row["data_version"]["second"] is None and counts["checked"]):
        raise ValueError("Build resolution affix counts contradict their version evidence")
    if status != "invalid_payload" and set(row["sections"]) != set(SECTIONS):
        raise ValueError("Build resolution requires a state for all five page sections")
    for value in row["sections"].values():
        _enum(value, ("captured", "absent", "invalid"))
    missing = [name for name in SECTIONS if row["sections"].get(name) != "captured"]
    if row["required_missing"] != missing:
        raise ValueError("Build resolution missing sections must agree with their captured states")


def _status(result):
    status = result["status"]
    if status == "invalid_payload":
        identity, coverage, freshness, gate = (result[name] for name in ("identity", "coverage", "freshness", "gate"))
        if (identity["basis"] != "none" or identity["descriptor_match"] != "not_supplied"
                or identity["capture_verified_flag"] is not None
                or (identity["author_consistency"], identity["player_id_consistency"]) != ("unknown", "unknown")
                or (gate["feature_status"], gate["real_feature_status"]) != ("missing", "missing")
                or any(value is not None for value in coverage["data_version"].values())
                or any(coverage["affix_versions"].values()) or coverage["sections"]
                or freshness["captured_at_status"] != "absent" or result["warnings"]):
            raise ValueError("Invalid build payloads cannot retain identity, time or coverage claims")
        return
    identity, coverage = result["identity"], result["coverage"]
    if status in ("invalid_code", "planner_code"):
        if identity["expected_code_matched"] is not None or identity["descriptor_match"] != "not_supplied":
            raise ValueError("Invalid expected codes cannot expose a completed code or descriptor comparison")
        return
    if identity["expected_code_matched"] is False or identity["descriptor_match"] == "mismatch":
        expected = "code_mismatch"
    elif result["gate"]["status"] == "denied":
        expected = "not_viewable"
    elif ("inconsistent" in (identity["author_consistency"], identity["player_id_consistency"])
          or coverage["affix_versions"]["mismatched"]):
        expected = "inconsistent"
    elif coverage["required_missing"] or result["gate"]["status"] == "missing":
        expected = "incomplete"
    else:
        expected = "matched_saved_code" if identity["expected_code_matched"] is True else "unbound"
    if status != expected:
        raise ValueError("Build resolution status contradicts the recorded evidence and precedence")


def _warnings(result):
    if result["status"] == "invalid_payload":
        return
    identity, freshness = result["identity"], result["freshness"]
    future = bool(freshness["captured_at"] and identity["code_minted_at"]
                  and _timestamp(identity["code_minted_at"]) > _timestamp(freshness["captured_at"]))
    invalid = None in result["coverage"]["data_version"].values()
    if (("code_minted_after_capture" in result["warnings"]) != future
            or ("data_version_invalid" in result["warnings"]) != invalid
            or (identity["code_structure"] == "other" and "code_structure_other" not in result["warnings"])):
        raise ValueError("Build resolution warnings must agree with the recorded observations")


def project(document, source_sha256):
    """Return detached source-bound saved evidence, preserving its unverified status."""
    _object(document, ("format", "version", "status", "source", "transport", "identity", "gate", "coverage",
                       "freshness", "warnings", "sourcePaths"))
    result = _select(document, ("format", "version", "status"))
    result["source"] = _select(document["source"], ("sha256",))
    if (document["format"] != "tli-build-resolution-v0" or document["version"] != "0.1.1"
            or type(source_sha256) is not str or not re.fullmatch("[0-9a-f]{64}", source_sha256)
            or document["source"]["sha256"] != source_sha256):
        raise ValueError("Build resolution format, version and source hash must match the package contract")
    _enum(document["status"], STATUSES)
    for name, fields in FIELDS.items():
        result[name] = _select(document[name], fields)
    if (result["transport"]["kind"] != "saved_client_snapshot" or result["transport"]["verified"] is not False
            or result["identity"]["payload_self_identifies"] is not False
            or result["freshness"]["status"] != "unknown" or result["freshness"]["payload_generated_at"] is not None
            or result["freshness"]["is_old_data"] != "not_captured"):
        raise ValueError("Build resolution cannot verify transport, payload identity or freshness")
    _identity(result["identity"])
    _times(result["identity"], result["freshness"])
    _gate(result["gate"])
    coverage = document["coverage"]
    _object(coverage, ("dataVersion", "affixVersions", "sections", "requiredMissing"))
    _object(coverage["sections"], ())
    result["coverage"] = {
        "data_version": _select(coverage["dataVersion"], ("first", "second")),
        "affix_versions": _select(coverage["affixVersions"], ("checked", "mismatched")),
        "sections": {key: coverage["sections"][key] for key in SECTIONS if key in coverage["sections"]},
        "required_missing": _list(coverage["requiredMissing"])}
    _coverage(result["coverage"], result["status"])
    result["warnings"] = _list(document["warnings"])
    result["source_paths"] = _list(document["sourcePaths"])
    for warning in result["warnings"]:
        _enum(warning, WARNINGS)
    if len(set(result["warnings"])) != len(result["warnings"]) or tuple(result["source_paths"]) != PATHS:
        raise ValueError("Build resolution requires distinct known warnings and fixed source paths")
    _status(result)
    _warnings(result)
    return result


def summary(data):
    """Revalidate an already source-bound projection without a second schema."""
    _object(data, ("format", "version", "status", "source", "transport", "identity", "gate", "coverage",
                   "freshness", "warnings", "source_paths"))
    _object(data["source"], ("sha256",))
    document = {key: data[key] for key in ("format", "version", "status", "source", "warnings")}
    for name, fields in FIELDS.items():
        _object(data[name], tuple(_name(field) for field in fields))
        document[name] = {field: data[name][_name(field)] for field in fields}
    coverage = data["coverage"]
    _object(coverage, ("data_version", "affix_versions", "sections", "required_missing"))
    document["coverage"] = {"dataVersion": coverage["data_version"], "affixVersions": coverage["affix_versions"],
                            "sections": coverage["sections"], "requiredMissing": coverage["required_missing"]}
    document["sourcePaths"] = data["source_paths"]
    return project(document, data["source"]["sha256"])
