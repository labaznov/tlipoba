"""Validate declared local skill-catalog provenance without reading or authenticating its bytes."""

import re


FIELDS = ("derivation networkBytesVerified currentPatchVerified identityBridges mappingFiles documents categories "
          "records skills invalidRecords withheldRecords reconciles recordsWithoutEnglish withheldRecordIds")
DOCUMENT = "role category logicalPath address cacheFile wrapperSha256 member byteRange memberSha256 encoding"
MAX_BYTES = 32 * 1024 * 1024
CATEGORY = r"[A-Za-z][A-Za-z_]{0,63}"


def _name(value):
    return re.sub(r"([A-Z])", r"_\1", value).lower()


def _select(value, fields, canonical):
    names = {_name(field) if canonical else field: _name(field) for field in fields.split()}
    if type(value) is not dict or not set(names).issubset(value):
        raise ValueError("Support catalog requires all named metadata fields")
    return {target: value[source] for source, target in names.items()}


def _pattern(value, pattern):
    if type(value) is not str or re.fullmatch(pattern, value, re.ASCII) is None:
        raise ValueError("Support catalog has an invalid provenance coordinate")


def _integer(value, minimum):
    if type(value) is not int or value < minimum:
        raise ValueError("Support catalog requires typed nonnegative or positive integers")


def _mappings(rows, canonical):
    result, names = [], set()
    for raw in rows:
        row = _select(raw, "file sha256 bytes", canonical)
        _pattern(row["file"], r"(?:needed|endgame)-bundles\.json")
        _pattern(row["sha256"], r"[0-9a-f]{64}")
        _integer(row["bytes"], 1)
        if row["file"] in names or row["bytes"] > MAX_BYTES:
            raise ValueError("Support catalog mapping names must be unique and their bytes bounded")
        names.add(row["file"])
        result.append(row)
    if "needed-bundles.json" not in names:
        raise ValueError("Support catalog requires the needed bundles mapping")
    return result


def _documents(rows, canonical):
    result, paths, caches = [], set(), {}
    for raw in rows:
        row = _select(raw, DOCUMENT, canonical)
        if row["role"] not in ("master", "english"):
            raise ValueError("Support catalog document requires a master or English role")
        _pattern(row["category"], CATEGORY)
        path = f"skill/{row['category']}/" + ("master" if row["role"] == "master" else "i18n/en")
        if (row["logical_path"] != path or row["member"] != path or row["address"] != f"/data/SS14/{path}.json"
                or row["encoding"] != "utf-8" or path in paths):
            raise ValueError("Support catalog document coordinates must agree and be unique")
        paths.add(path)
        _pattern(row["cache_file"], r"[0-9a-f]{16}\.json")
        _pattern(row["wrapper_sha256"], r"[0-9a-f]{64}")
        _pattern(row["member_sha256"], r"[0-9a-f]{64}")
        span = row["byte_range"]
        if type(span) is not list or len(span) != 2:
            raise ValueError("Support catalog member range requires two byte offsets")
        for value in span:
            _integer(value, 0)
        if not span[0] < span[1] <= MAX_BYTES:
            raise ValueError("Support catalog member range must be ordered and bounded")
        cache = caches.setdefault(row["cache_file"], {"sha256": row["wrapper_sha256"], "ranges": []})
        if cache["sha256"] != row["wrapper_sha256"] or any(
                span[0] < end and start < span[1] for start, end in cache["ranges"]):
            raise ValueError("Support catalog shared wrapper hashes or member ranges disagree")
        cache["ranges"].append(tuple(span))
        row["byte_range"] = list(span)
        result.append(row)
    return result


def _categories(rows, documents, canonical):
    observed = {(row["category"], row["role"]) for row in documents}
    if (not any(role == "master" for _, role in observed)
            or any((category, "master") not in observed for category, _ in observed)
            or not {category for category, _ in observed}.issubset(rows)):
        raise ValueError("Support catalog loaded members require their declared category master")
    result = {}
    for category, raw in rows.items():
        _pattern(category, CATEGORY)
        row = _select(raw, "master english", canonical)
        if row != {role: "present" if (category, role) in observed else "missing" for role in ("master", "english")}:
            raise ValueError("Support catalog category presence differs from its loaded members")
        result[category] = row
    return result


def _accounting(data):
    for field in ("records", "skills", "invalid_records", "withheld_records", "records_without_english"):
        _integer(data[field], 0)
    if (data["records"] != data["skills"] + data["invalid_records"] + data["withheld_records"]
            or data["records_without_english"] > data["skills"] + data["withheld_records"]):
        raise ValueError("Support catalog record counts do not reconcile")
    identities = data["withheld_record_ids"]
    if len(identities) > data["withheld_records"] or (not identities and data["withheld_records"] != 0):
        raise ValueError("Support catalog withheld identities must account for withheld rows")
    for identity in identities:
        _integer(identity, 1)
    if len(set(identities)) != len(identities):
        raise ValueError("Support catalog withheld identities must be unique")


def _catalog(document, canonical):
    result = _select(document, FIELDS, canonical)
    if (result["derivation"] != "cache_member_exact_slice" or result["identity_bridges"] != "none_applied"
            or result["network_bytes_verified"] is not False or result["current_patch_verified"] is not False
            or result["reconciles"] is not True):
        raise ValueError("Support catalog requires unverified local slices without identity bridges")
    for field, maximum in (("mapping_files", 2), ("documents", 64)):
        if type(result[field]) is not list or not 1 <= len(result[field]) <= maximum:
            raise ValueError("Support catalog requires bounded nonempty metadata lists")
    if type(result["categories"]) is not dict or not 1 <= len(result["categories"]) <= 128:
        raise ValueError("Support catalog requires a bounded category mapping")
    if type(result["withheld_record_ids"]) is not list:
        raise ValueError("Support catalog withheld identities require a JSON list")
    result["mapping_files"] = _mappings(result["mapping_files"], canonical)
    result["documents"] = _documents(result["documents"], canonical)
    result["categories"] = _categories(result["categories"], result["documents"], canonical)
    _accounting(result)
    result["withheld_record_ids"] = list(result["withheld_record_ids"])
    return result


def project(raw):
    """Return a detached metadata projection from the helper's camelCase catalog subobject."""
    return _catalog(raw, False)


def summary(canonical):
    """Revalidate a canonical catalog and discard every unknown property without opening paths."""
    return _catalog(canonical, True)
