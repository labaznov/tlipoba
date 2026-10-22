"""Bind saved level-grant diagnostics without deriving effective levels or damage."""

import hashlib
import json
import math
from pathlib import Path
import re

from .supportbundle import _pairs, _float, _constant


FILE = "installed-level-candidates.json"
CONTRACTS = (("0.1.2", "0.3.1"), ("0.2.0", "0.4.0"))
FORMAT = "tli-installed-level-candidates-canonical-v1"
MAX_BYTES = 64 * 1024 * 1024
FLAGS = "arithmeticReady runtimeVerified identityVerified importComplete".split()
COUNTS = "catalogDocuments auxiliaryFiles requested targets candidates gaps ambiguousTargets".split()
ERRORS = set("""source_missing source_unreadable source_too_large source_not_json source_duplicate_key
source_nonfinite_number source_parse_limit source_shape inventory_failed catalog_location_invalid catalog_bytes_unavailable
catalog_mapping_missing catalog_mapping_invalid catalog_mapping_conflict catalog_limit cache_token_invalid
cache_file_missing cache_unreadable cache_not_object cache_not_json cache_duplicate_member cache_member_missing
cache_duplicate_key cache_nonfinite_number cache_parse_limit aux_missing aux_unreadable aux_too_large aux_not_json
aux_duplicate_key aux_nonfinite_number aux_parse_limit aux_shape resolver_version_unreviewed resolver_failed
resolver_ledger_mismatch output_limit artifact_limit source_number_precision source_number_limit
cache_number_precision cache_number_limit aux_number_precision aux_number_limit""".split())


def _require(condition):
    if not condition:
        raise ValueError("Installed level candidates contain an invalid or inconsistent contract")


def _name(value):
    return re.sub(r"([A-Z])", r"_\1", value).lower()


def _select(value, fields, canonical=False):
    _require(type(value) is dict)
    names = {_name(field) if canonical else field: _name(field) for field in fields.split()}
    _require(set(names).issubset(value))
    return {target: value[source] for source, target in names.items()}


def _pattern(value, pattern):
    _require(type(value) is str and re.fullmatch(pattern, value, re.ASCII) is not None)


def _hash(value):
    _pattern(value, r"[0-9a-f]{64}")


def _preflight(value):
    stack, seen, count = [(value, 0)], set(), 0
    while stack:
        item, depth = stack.pop()
        count += 1
        _require(count <= 1_000_000 and depth <= 64)
        if type(item) in (dict, list):
            _require(id(item) not in seen and len(item) <= 200_000)
            seen.add(id(item))
            if type(item) is dict:
                _require(all(type(key) is str and len(key) <= 4096 for key in item))
                stack.extend((key, depth + 1) for key in item)
            stack.extend((child, depth + 1) for child in (item.values() if type(item) is dict else item))
        elif type(item) is str:
            _require(len(item) <= 4096)
            try:
                item.encode("utf-8")
            except UnicodeError:
                raise ValueError("Installed level candidates require valid Unicode text") from None
        elif type(item) is int:
            _require(-10 ** 20 < item < 10 ** 20)
        elif type(item) is float:
            _require(math.isfinite(item))
        else:
            _require(item is None or type(item) is bool)


def _catalog(value, canonical):
    from .supportcatalog import _mappings

    result = _select(value, "status derivation networkBytesVerified currentPatchVerified mappingFiles documents", canonical)
    _require(result["derivation"] == "cache_member_exact_slice" and result["network_bytes_verified"] is False
             and result["current_patch_verified"] is False)
    mappings, rows = result["mapping_files"], result["documents"]
    _require(type(mappings) is list and 1 <= len(mappings) <= 2 and type(rows) is list and len(rows) <= 512)
    result["mapping_files"] = _mappings(mappings, canonical)
    _require(result["status"] == ("members_read" if rows else "no_allowlisted_members_mapped"))
    documents, paths, caches = [], set(), {}
    for raw in rows:
        row = _select(raw, "role domain logicalPath address cacheFile wrapperSha256 byteRange memberSha256 encoding", canonical)
        path = row["logical_path"]
        _pattern(path, r"(?:skill|gear|legendaries|talent-tree|divinity-slate|pactspirit|ethereal-prism|hero-trait|hero-memory)"
                 r"(?:/[A-Za-z0-9_-]{1,64}){0,5}/(?:master|i18n/en)")
        english = path.endswith("/i18n/en")
        _require(not english or path.startswith(("skill/", "ethereal-prism/", "hero-trait/", "hero-memory/")))
        _require(row["role"] == ("english" if english else "master") and row["domain"] == path.split("/")[0]
                 and row["address"] == f"/data/SS14/{path}.json" and row["encoding"] == "utf-8" and path not in paths)
        paths.add(path)
        _pattern(row["cache_file"], r"[0-9a-f]{16}\.json")
        _hash(row["wrapper_sha256"])
        _hash(row["member_sha256"])
        span = row["byte_range"]
        _require(type(span) is list and len(span) == 2 and all(type(number) is int for number in span)
                 and 0 <= span[0] < span[1] <= 32 * 1024 * 1024)
        cache = caches.setdefault(row["cache_file"], (row["wrapper_sha256"], []))
        _require(cache[0] == row["wrapper_sha256"]
                 and not any(span[0] < end and start < span[1] for start, end in cache[1]))
        cache[1].append(tuple(span))
        row["byte_range"] = list(span)
        documents.append(row)
    result["documents"] = documents
    return result


def _auxiliary(value, canonical):
    result = _select(value, "endgameIdBridge verifiedNativeMappings", canonical)
    for key, raw in result.items():
        row = _select(raw, "status sha256 bytes", canonical)
        if row["status"] == "supplied":
            _hash(row["sha256"])
            _require(type(row["bytes"]) is int and 1 <= row["bytes"] <= 16 * 1024 * 1024)
        else:
            _require(row["status"] == "absent" and row["sha256"] is None and row["bytes"] is None)
        result[key] = row
    return result


def _bundle(document, installation, canonical):
    from .installedskills import summary as installation_summary
    from .levelcandidates import project as project_target, summary as summarize_target

    _preflight(document)
    result = _select(document, "format version resolverFormat resolverVersion source catalog auxiliary selection requestedIds targets "
                     + " ".join(FLAGS), canonical)
    _require(result["format"] == (FORMAT if canonical else "tli-installed-level-candidates-v1")
             and (result["version"], result["resolver_version"]) in CONTRACTS
             and result["resolver_format"] == "tli-effective-level-candidates-v0"
             and all(result[_name(field)] is False for field in FLAGS))
    result["format"] = FORMAT
    source = _select(result["source"], "file sha256", canonical)
    _hash(source["sha256"])
    _require(source["file"] == "source.json")
    result["source"] = source
    observed = installation_summary(installation)
    _require(observed["source"]["sha256"] == source["sha256"])
    result["catalog"] = _catalog(result["catalog"], canonical)
    result["auxiliary"] = _auxiliary(result["auxiliary"], canonical)
    selection = _select(result["selection"], "policy clientLayer observedMembers invalidSkillIds", canonical)
    client = observed["domains"]["client"]["status"]
    members = [member for group in observed["groups"] for member in group["members"]]
    expected = {"policy": "distinct_observed_config_base_ids", "client_layer": client,
                "observed_members": len(members) if client == "captured" else None,
                "invalid_skill_ids": sum(member["skill_id"] is None for member in members) if client == "captured" else None}
    _require(all(type(selection[key]) is type(value) and selection[key] == value for key, value in expected.items()))
    result["selection"] = selection
    requested = sorted({member["skill_id"] for member in members if member["skill_id"] is not None}) if client == "captured" else None
    targets = result["targets"]
    if requested is None:
        _require(result["requested_ids"] is None and targets is None)
        counts = (None,) * 5
    else:
        ids = result["requested_ids"]
        _require(type(ids) is list and len(ids) <= 4096 and all(type(number) is int for number in ids)
                 and ids == requested and type(targets) is dict and set(targets) == {str(number) for number in requested})
        result["requested_ids"] = list(ids)
        validated = {}
        masters = {row["logical_path"] for row in result["catalog"]["documents"] if row["role"] == "master"}
        for identity in ids:
            target = summarize_target(targets[str(identity)]) if canonical else project_target(targets[str(identity)], source["sha256"])
            _require(target["version"] == result["resolver_version"]
                     and target["source"]["sha256"] == source["sha256"] and target["target"]["skill_id"] == identity)
            matches = [member for member in members if member["skill_id"] == identity]
            observation = target["target"]
            _require(observation["catalog"]["path"] is None or observation["catalog"]["path"] in masters)
            _require(all(candidate["binding"]["catalog"] in masters for candidate in target["candidates"]))
            _require(not any(candidate["domain"] == "pactspirit" for candidate in target["candidates"])
                     or any(row["status"] == "supplied" for row in result["auxiliary"].values()))
            for domain, prefix in (("supports", "skill/"), ("hero_traits", "hero-trait/"), ("hero_memories", "hero-memory/")):
                census = target["domains"][domain]
                if census["status"] != "collection_limit":
                    _require(census["catalog_members"] == sum(row["logical_path"].startswith(prefix)
                             for row in result["catalog"]["documents"]))
            supports = target["domains"]["supports"]
            _require(supports["status"] == "collection_limit" or supports["observed"] == len(members))
            if len(matches) == 1:
                _require(observation["status"] == "observed" and observation["path"] == matches[0]["path"]
                         and observation["gem_level"]["value"] == matches[0]["gem_level"])
            else:
                _require(observation["status"] == "ambiguous_installation" and observation["path"] is None
                         and observation["gem_level"] is None)
            validated[str(identity)] = target
        result["targets"] = validated
        counts = (len(ids), len(validated), sum(len(target["candidates"]) for target in validated.values()),
                  sum(len(target["gaps"]) for target in validated.values()),
                  sum(target["target"]["status"] == "ambiguous_installation" for target in validated.values()))
        _require(counts[2] <= 100_000 and counts[3] <= 200_000)
    values = (len(result["catalog"]["documents"]),
              sum(row["status"] == "supplied" for row in result["auxiliary"].values()), *counts)
    accounting = {_name(field): value for field, value in zip(COUNTS, values)}
    if canonical:
        claimed = _select(document, "accounting", True)["accounting"]
        claimed = _select(claimed, " ".join(COUNTS), True)
        _require(all(type(claimed[key]) is type(value) and claimed[key] == value for key, value in accounting.items()))
    result["accounting"] = accounting
    return result


def read(package, descriptor, source_sha256, installation, *, max_bytes=MAX_BYTES):
    """Read exact artifact bytes and return canonical evidence or a hashed producer failure."""
    _require(type(max_bytes) is int and 1 <= max_bytes <= MAX_BYTES)
    _hash(source_sha256)
    _select(descriptor, "file version resolverVersion status sha256 sourceSha256 " + " ".join(FLAGS + COUNTS))
    _require(descriptor["file"] == FILE
             and type(descriptor["version"]) is str and type(descriptor["resolverVersion"]) is str
             and (descriptor["version"], descriptor["resolverVersion"]) in CONTRACTS
             and descriptor["status"] in ("diagnostic", "error"))
    _require(all(descriptor[field] is False for field in FLAGS))
    _hash(descriptor["sha256"])
    code = descriptor.get("error")
    _require(type(code) is str and code in ERRORS if descriptor["status"] == "error" else code is None)
    source = descriptor["sourceSha256"]
    if source is None:
        _require(descriptor["status"] == "error" and code in ("source_missing", "source_unreadable"))
    else:
        _hash(source)
        _require(source == source_sha256)
    path = Path(package) / FILE
    with path.open("rb") as stream:
        raw = stream.read(max_bytes + 1)
    _require(len(raw) <= max_bytes and hashlib.sha256(raw).hexdigest() == descriptor["sha256"])
    try:
        artifact = json.loads(raw.decode("utf-8"), object_pairs_hook=_pairs, parse_float=_float, parse_constant=_constant)
    except (ValueError, UnicodeError, RecursionError):
        raise ValueError("Installed level candidates require bounded strict UTF-8 JSON") from None
    _preflight(artifact)
    _select(artifact, "format version resolverFormat resolverVersion status source " + " ".join(FLAGS))
    _select(artifact["source"], "file sha256")
    _require(artifact["version"] == descriptor["version"] and artifact["resolverVersion"] == descriptor["resolverVersion"]
             and artifact["resolverFormat"] == "tli-effective-level-candidates-v0"
             and artifact["status"] == descriptor["status"] and artifact["source"]["file"] == "source.json"
             and artifact["source"]["sha256"] == source and all(artifact[field] is False for field in FLAGS))
    origin = (str(path.resolve()), descriptor["sha256"], len(raw), int(descriptor["status"] == "diagnostic"))
    if descriptor["status"] == "error":
        _require(artifact["format"] == "tli-installed-level-candidates-error-v1" and artifact.get("error") == code
                 and all(descriptor[field] is None for field in COUNTS)
                 and not any(field in artifact for field in ("catalog", "auxiliary", "selection", "requestedIds", "targets")))
        return None, origin
    _require(artifact["format"] == "tli-installed-level-candidates-v1" and "error" not in artifact)
    result = _bundle(artifact, installation, False)
    _require(all(type(descriptor[field]) is type(result["accounting"][_name(field)])
                 and descriptor[field] == result["accounting"][_name(field)] for field in COUNTS))
    return result, origin


def summary(canonical, installation):
    """Revalidate canonical evidence against its source-bound observed installation."""
    return _bundle(canonical, installation, True)
