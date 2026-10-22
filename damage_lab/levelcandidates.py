"""Validate diagnostic level-grant candidates without deriving levels or reading sources."""

import math
import re
from decimal import Decimal


FORMAT = "tli-effective-level-candidates-v0"
CANONICAL_FORMAT = "tli-effective-level-candidates-canonical-v1"
VERSIONS = ("0.3.1", "0.4.0")
LIMITATIONS = (
    "source sha256 binds the caller-supplied document only; no bytes are read or verified",
    "catalog members are taken as supplied; no catalog bytes, currency or patch are verified",
    "eligibility is template wording against catalog tags only; no scope or stacking rule is verified",
    "talent identities are computed position/tier ids, not native ids",
    "no effective level is derived: candidates are never summed",
)
KEYS = dict(zip(
    "arithmetic_ready runtime_verified identity_verified import_complete effective_level uniquely_derivable skill_id "
    "gem_level skill_item_level scope_tokens all_tokens_in_skill_tags skill_category native_id tier_id tier_bounds "
    "node_type max_points server_point bound_level_candidates candidate_coverage placement_verified catalog_members catalog_level_mentions "
    "native_level_fields skills_row join_field level_equals_gem".split(),
    "arithmeticReady runtimeVerified identityVerified importComplete effectiveLevel uniquelyDerivable skillId "
    "gemLevel skillItemLevel scopeTokens allTokensInSkillTags skillCategory nativeId tierId tierBounds "
    "nodeType maxPoints serverPoint boundLevelCandidates candidateCoverage placementVerified catalogMembers catalogLevelMentions "
    "nativeLevelFields skillsRow joinField levelEqualsGem".split()))
DOMAINS = dict(zip(
    "gear talents divinity_slates pactspirits ethereal_prism supports hero_traits hero_memories sp_talent_tree "
    "other_wear_items jewel_items talent_jewelry_data_list hero_character_items".split(),
    "gear talents divinitySlates pactspirits etherealPrism supports heroTraits heroMemories spTalentTree "
    "OtherWearItems JewelItems TalentJewelryDataList HeroCharacterItems".split()))
STATUSES = "captured not_decoded not_available not_captured absent invalid unrecognized".split()
IDENTIFIER = r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}"
INDEX = r"(?:0|[1-9][0-9]{0,3})"
AFFIX = r"(?:BaseAttrInfoList|BAffixInfoList|PrefixInfoList|SuffixInfoList|EnchantAffixList|ChipAffixList|FixedBaseAffix)"
WEAR = rf"sections\.WearItems\.data\[{INDEX}\]"
TREE = rf"sections\.GeniusInfos\.data\.entries\[{INDEX}\]"
SLATE = rf"sections\.ServerSource\.data\.featuresInfo\.talentBlock\.dressingTalentBlocks\[{INDEX}\]"
PACT = rf"sections\.ServerSource\.data\.featuresInfo\.ContractInfosV2\.ContractDatas\[{INDEX}\]"
REASONS = {
    "gear": "invalid_section_data invalid_affix_list invalid_affix_container invalid_record item_unresolved unsupported_item_kind no_exact_definition ambiguous_exact_definition list_group_mismatch variant_template_unverified template_absent unsupported_level_template condition_unresolved value_count_mismatch unknown_unit invalid_numeric value_out_of_range catalog_member_invalid",
    "talents": "invalid_talent_map invalid_talent_map_key ambiguous_talent_tree catalog_member_missing tree_unknown invalid_node_key ambiguous_rank invalid_rank computed_identity_unresolved rank_exceeds_max unsupported_level_template invalid_numeric rank_scaling_unknown notable_not_in_tree ambiguous_exact_definition",
    "divinity_slates": "invalid_section_data slate_record_undecoded ambiguous_influence influence_unmapped no_exact_definition ambiguous_exact_definition unsupported_level_template invalid_numeric catalog_member_missing",
    "pactspirits": "invalid_section_data invalid_record auxiliary_absent no_exact_bridge ambiguous_bridge ambiguous_catalog_identity catalog_member_invalid bridge_requires_source_version bridge_target_changed invalid_area node_unknown ambiguous_node kismet_not_resolved unsupported_level_template invalid_numeric",
    "ethereal_prism": "invalid_section_data no_exact_definition ambiguous_exact_definition catalog_member_missing unstructured_level_text_in_catalog",
}


def _require(condition):
    if not condition:
        raise ValueError("Level candidates contain an invalid or inconsistent diagnostic contract")


def _preflight(value):
    stack, seen, count = [(value, 0)], set(), 0
    while stack:
        item, depth = stack.pop()
        count += 1
        _require(count <= 200_000 and depth <= 64)
        if type(item) in (dict, list):
            _require(id(item) not in seen and len(item) <= 4096)
            seen.add(id(item))
            if type(item) is dict:
                _require(all(type(key) is str and len(key) <= 4096 for key in item))
                for key in item:
                    _text(key)
                stack.extend((child, depth + 1) for child in item.values())
            else:
                stack.extend((child, depth + 1) for child in item)
        elif type(item) is str:
            _require(len(item) <= 4096)
            _text(item)
        elif type(item) is int:
            _require(-10 ** 20 < item < 10 ** 20)
        elif type(item) is float:
            _require(math.isfinite(item))
        else:
            _require(item is None or type(item) is bool)


def _text(value):
    try:
        value.encode("utf-8")
    except UnicodeError:
        raise ValueError("Level candidates require valid Unicode text") from None


def _object(value, fields, canonical):
    _require(type(value) is dict)
    keys = {key: key if canonical else KEYS.get(key, key) for key in fields.split()}
    _require(all(source in value for source in keys.values()))
    return {key: value[source] for key, source in keys.items()}


def _list(value):
    _require(type(value) is list and len(value) <= 4096)
    return value


def _pattern(value, expression, nullable=False):
    if nullable and value is None:
        return value
    _require(type(value) is str and re.fullmatch(expression, value, re.ASCII) is not None)
    return value


def _integer(value, minimum=0, maximum=10 ** 12, nullable=False):
    _require(nullable and value is None or type(value) is int and minimum <= value < maximum)
    return value


def _enum(value, choices):
    _require(type(value) is str and value in choices)
    return value


def _fixed(value, expected):
    _require(type(value) is type(expected) and value == expected)


def _path(value, expression, nullable=False):
    _pattern(value, expression, nullable)
    if value is not None:
        _require(all(int(index) < 4096 for index in re.findall(r"\[([0-9]+)\]", value)))
    return value


def _lexeme(value):
    return _pattern(value, r"-?[0-9]{1,12}(?:\.[0-9]{1,9})?")


def _native(value, target, canonical):
    result = _object(value, "skills_row fields level_equals_gem semantics arithmetic_ready effective_level", canonical)
    row = _object(result["skills_row"], "join path join_field", canonical)
    _enum(row["join"], ("exact_instance", "target_unavailable", "no_instance", "ambiguous_instance",
                        "no_skills_row", "collection_limit")
          + tuple("section_" + status for status in STATUSES if status != "captured"))
    _fixed(row["join_field"], "Id")
    _require((row["join"] == "target_unavailable") == (target["status"] != "observed"))
    exact = row["join"] == "exact_instance"
    if exact:
        _path(row["path"], rf"sections\.ServerSource\.data\.featuresInfo\.skills\.skills\[{INDEX}\]")
    else:
        _fixed(row["path"], None)
    fields = _object(result["fields"], "Level SkillItemLevel", canonical)
    for name, field in fields.items():
        field = _object(field, "value type", canonical)
        _enum(field["type"], ("int", "missing", "invalid") if exact else ("unavailable",))
        if field["type"] == "int":
            _integer(field["value"], -10 ** 20 + 1, 10 ** 20)
        else:
            _fixed(field["value"], None)
        fields[name] = field
    gem = target["gem_level"]
    equality = (fields["Level"]["value"] == gem["value"]
                if exact and fields["Level"]["type"] == "int" and gem["status"] == "ok" else None)
    _fixed(result["level_equals_gem"], equality)
    semantics = _object(result["semantics"], "Level SkillItemLevel", canonical)
    _fixed(semantics, {"Level": "unknown", "SkillItemLevel": "unknown"})
    _fixed(result["arithmetic_ready"], False)
    _fixed(result["effective_level"], None)
    result.update(skills_row=row, fields=fields, semantics=semantics)
    return result


def _target(value, canonical, version):
    result = _object(value, "skill_id status path gem_level catalog skill_item_level", canonical)
    _integer(result["skill_id"], 1, 10 ** 20)
    _enum(result["status"], ["observed", "not_installed", "ambiguous_installation", "collection_limit"]
          + ["client_layer_" + status for status in STATUSES if status != "captured"])
    if result["status"] == "observed":
        _path(result["path"], rf"sections\.SkillLayout\.data\[{INDEX}\]\[{INDEX}\]")
        level = _object(result["gem_level"], "value status meaning", canonical)
        _fixed(level["meaning"], "observed_gem_level_not_effective")
        _enum(level["status"], ("ok", "invalid_level"))
        if level["status"] == "ok":
            _integer(level["value"], 1, 10 ** 20)
        else:
            _fixed(level["value"], None)
        result["gem_level"] = level
    else:
        _fixed(result["path"], None)
        _fixed(result["gem_level"], None)
    catalog = _object(result["catalog"], "status path category tags", canonical)
    _enum(catalog["status"], ("bound", "catalog_record_missing", "catalog_identity_ambiguous",
                              "catalog_record_invalid", "catalog_collection_limit"))
    if catalog["status"] == "bound":
        _pattern(catalog["category"], r"[A-Za-z][A-Za-z_]{0,63}")
        _fixed(catalog["path"], "skill/" + catalog["category"] + "/master")
        catalog["tags"] = [_pattern(tag, r"[A-Z][A-Za-z]{0,31}(?: [A-Z][A-Za-z]{0,31}){0,2}")
                           for tag in _list(catalog["tags"])]
    else:
        for key in ("path", "category", "tags"):
            _fixed(catalog[key], None)
    result["catalog"] = catalog
    counts = _object(result["skill_item_level"], "total equal different missing invalid semantics", canonical)
    _fixed(counts["semantics"], "unknown")
    for key in ("total", "equal", "different", "missing", "invalid"):
        _integer(counts[key], maximum=4097, nullable=True)
    _require(all(counts[key] is None for key in ("total", "equal", "different", "missing", "invalid"))
             or all(counts[key] is not None for key in ("total", "equal", "different", "missing", "invalid"))
             and counts["total"] == sum(counts[key] for key in ("equal", "different", "missing", "invalid")))
    result["skill_item_level"] = counts
    if version == "0.4.0":
        native = _object(value, "native_level_fields", canonical)["native_level_fields"]
        result["native_level_fields"] = _native(native, result, canonical)
    return result


def _amount(value, origin, expression, canonical):
    result = _object(value, "exact origin source", canonical)
    _lexeme(result["exact"])
    _fixed(result["origin"], origin)
    _path(result["source"], expression)
    return result


def _candidate(value, target, canonical):
    result = _object(value, "domain path template binding amount eligibility", canonical)
    _enum(result["domain"], ("gear", "talent", "slate", "pactspirit"))
    _pattern(result["template"], r"\+# (?:to )?[A-Z][a-z]+(?: [A-Z][a-z]+)? Skill Level")
    scope = result["template"].removeprefix("+# ").removeprefix("to ").removesuffix(" Skill Level")
    eligibility = _object(result["eligibility"], "scope scope_tokens all_tokens_in_skill_tags skill_category status", canonical)
    _fixed(eligibility["scope"], scope)
    _fixed(eligibility["scope_tokens"], scope.split(" "))
    _fixed(eligibility["status"], "unverified")
    tags = target["catalog"]["tags"]
    _fixed(eligibility["all_tokens_in_skill_tags"], None if tags is None else all(token in tags for token in scope.split(" ")))
    _fixed(eligibility["skill_category"], target["catalog"]["category"])
    result["eligibility"] = {**eligibility, "scope_tokens": list(eligibility["scope_tokens"])}
    kind = result["domain"]
    if kind == "gear":
        result.update(_object(value, "native_id slot", canonical))
        _integer(result["native_id"], 1, 10 ** 20)
        _integer(result["slot"], 0, 10 ** 6, True)
        _path(result["path"], WEAR + rf"\.sourceData\.AffixList\.{AFFIX}\[{INDEX}\]")
        binding = _object(result["binding"], "status kind catalog definition tier tier_id tier_bounds", canonical)
        _fixed(binding["status"], "exact")
        _fixed(binding["kind"], "native_id_in_item_document")
        _pattern(binding["catalog"], r"(?:gear|legendaries)/(?:[A-Za-z0-9_][A-Za-z0-9_-]{0,63}/){1,5}master")
        _pattern(binding["definition"], IDENTIFIER, True)
        _pattern(binding["tier"], r"[0-9]{1,3}\+?", True)
        _pattern(binding["tier_id"], IDENTIFIER, True)
        bounds = _object(binding["tier_bounds"], "min max", canonical)
        for key in bounds:
            _lexeme(bounds[key])
        binding["tier_bounds"] = bounds
        amount = _amount(result["amount"], "native_roll", r"DynArgs\[0\]", canonical)
        _require(Decimal(bounds["min"]) <= Decimal(amount["exact"]) <= Decimal(bounds["max"]))
    elif kind == "talent":
        result.update(_object(value, "rank", canonical))
        binding = _object(result["binding"], "status kind catalog node node_type", canonical)
        _pattern(binding["catalog"], rf"talent-tree/{IDENTIFIER}/master")
        _pattern(binding["node"], IDENTIFIER, True)
        rank = _object(result["rank"], "rank max_points server_point semantics", canonical)
        if binding["kind"] == "computed_position_tier_id":
            _fixed(binding["status"], "computed")
            _require(binding["node_type"] is None or binding["node_type"] in ("micro", "medium", "legendary"))
            _path(result["path"], TREE + rf"\.value\.GeniusList\.entries\[{INDEX}\]")
            _integer(rank["rank"], 1, 10 ** 4)
            _integer(rank["max_points"], 1, 10 ** 4, True)
            _integer(rank["server_point"], nullable=True)
            _require(rank["max_points"] is None or rank["rank"] <= rank["max_points"])
            single = rank["rank"] == rank["max_points"] == 1
            _fixed(rank["semantics"], "single_point_node" if single else "per_point_or_total_unknown")
            if single:
                amount = _amount(result["amount"], "catalog_literal", rf"node\.mods\[{INDEX}\]\.value", canonical)
            else:
                _fixed(result["amount"], None)
                amount = None
        else:
            _fixed(binding["kind"], "notable_tlidb_id_in_tree")
            _fixed(binding["status"], "exact")
            _fixed(binding["node_type"], "notable")
            _path(result["path"], TREE + r"\.value\.BonusTalents")
            for key in ("rank", "max_points", "server_point"):
                _fixed(rank[key], None)
            _fixed(rank["semantics"], "selected_core_talent")
            amount = _amount(result["amount"], "catalog_literal", rf"notable\.mods\[{INDEX}\]\.value", canonical)
        result["rank"] = rank
    elif kind == "slate":
        result.update(_object(value, "installation", canonical))
        _fixed(result["installation"], "listed_in_dressing_blocks_placement_unverified")
        _path(result["path"], SLATE)
        binding = _object(result["binding"], "status kind catalog definition", canonical)
        _fixed(binding["status"], "exact")
        _fixed(binding["kind"], "slate_mod_tlidb_id")
        _fixed(binding["catalog"], "divinity-slate/master")
        _pattern(binding["definition"], IDENTIFIER, True)
        amount = _amount(result["amount"], "catalog_literal", rf"slateMod\.effects\[{INDEX}\]\.value", canonical)
    else:
        result.update(_object(value, "area", canonical))
        _integer(result["area"], 0, 10 ** 4)
        _path(result["path"], PACT)
        binding = _object(result["binding"], "status kind catalog definition node", canonical)
        _fixed(binding["status"], "bridged")
        _enum(binding["kind"], ("third_party_bridge_hashed", "third_party_bridge_unhashed"))
        _fixed(binding["catalog"], "pactspirit/master")
        _pattern(binding["definition"], IDENTIFIER, True)
        _integer(binding["node"], 0, 100)
        amount = _amount(result["amount"], "catalog_literal", rf"node\.effects\[{INDEX}\]\.value", canonical)
    result.update(binding=binding, amount=amount)
    return result


def _gap(value, canonical):
    result = _object(value, "domain path reason", canonical)
    if not canonical:
        _require(result["domain"] in DOMAINS.values())
        result["domain"] = next(key for key in DOMAINS if DOMAINS[key] == result["domain"])
    _enum(result["domain"], DOMAINS)
    _enum(result["reason"], REASONS.get(result["domain"], "").split() + ["collection_limit"])
    name, reason = result["domain"], result["reason"]
    if reason == "collection_limit":
        if name == "sp_talent_tree":
            _fixed(result["path"], "sections.ServerSource.data.spTalentTree")
        else:
            _fixed(result["path"], None)
    elif (name, reason) in (("gear", "catalog_member_invalid"), ("divinity_slates", "catalog_member_missing"),
                            ("ethereal_prism", "catalog_member_missing"), ("ethereal_prism", "unstructured_level_text_in_catalog")):
        _fixed(result["path"], None)
    else:
        if name == "gear":
            expression = (r"sections\.WearItems\.data" if reason == "invalid_section_data" else WEAR if reason == "invalid_affix_list" else
                          WEAR + rf"\.sourceData\.AffixList\.{AFFIX}" if reason == "invalid_affix_container" else
                          WEAR + rf"\.sourceData\.AffixList\.{AFFIX}\[{INDEX}\]")
        elif name == "talents":
            node = TREE + rf"\.value\.GeniusList\.entries\[{INDEX}\]"
            notable = TREE + r"\.value\.BonusTalents"
            expression = (rf"sections\.GeniusInfos\.data|{TREE}\.value\.GeniusList" if reason == "invalid_talent_map" else
                          TREE if reason in ("invalid_talent_map_key", "ambiguous_talent_tree", "catalog_member_missing", "tree_unknown") else
                          notable if reason in ("notable_not_in_tree", "ambiguous_exact_definition") else
                          node + "|" + notable if reason in ("unsupported_level_template", "invalid_numeric") else node)
        elif name == "divinity_slates":
            expression = r"featuresInfo\.talentBlock" if reason == "invalid_section_data" else SLATE
        elif name == "pactspirits":
            expression = r"featuresInfo\.ContractInfosV2" if reason == "invalid_section_data" else PACT
        else:
            expression = (r"featuresInfo\.geniusInfos\.info" if reason == "invalid_section_data" else
                          rf"sections\.ServerSource\.data\.featuresInfo\.geniusInfos\.info\[{INDEX}\]\.prismInfo\.item\.(?:BaseAffix|Prefix|Suffix|BaseAttrAffix|FixedBaseAffix)\[{INDEX}\]")
        _path(result["path"], expression)
    return result


def _domain(value, name, canonical):
    result = _object(value, "status observed bound bound_level_candidates candidate_coverage", canonical)
    _enum(result["status"], STATUSES + ["collection_limit"] + (["captured_opaque"] if name == "sp_talent_tree" else []))
    for key in ("observed", "bound", "bound_level_candidates"):
        _integer(result[key], nullable=True)
    status, observed, bound = result["status"], result["observed"], result["bound"]
    _require(observed is None or bound is None or bound <= observed)
    if status == "captured" and observed is not None and name in ("gear", "pactspirits", "ethereal_prism"):
        _integer(result["bound_level_candidates"])
    extras = {"gear": "items", "talents": "notables", "divinity_slates": "slates placement_verified",
              "supports": "catalog_members catalog_level_mentions", "hero_traits": "catalog_members catalog_level_mentions",
              "hero_memories": "catalog_members catalog_level_mentions", "sp_talent_tree": "pairs"}
    fields = extras.get(name, "")
    if (status == "captured" and observed is not None
            or name in ("supports", "hero_traits", "hero_memories") and status != "collection_limit"
            or name == "sp_talent_tree"):
        result.update(_object(value, fields, canonical))
    for key in ("items", "slates", "catalog_members", "catalog_level_mentions", "pairs"):
        if key in result:
            _integer(result[key], nullable=key == "pairs")
    if "placement_verified" in result:
        _fixed(result["placement_verified"], False)
    if "notables" in result:
        result["notables"] = _object(result["notables"], "observed bound", canonical)
        for key in result["notables"]:
            _integer(result["notables"][key])
        _require(result["notables"]["bound"] <= result["notables"]["observed"])
    coverage = result["candidate_coverage"]
    if status == "collection_limit":
        _fixed(coverage, "unknown_collection_limit")
        _require(observed is bound is result["bound_level_candidates"] is None)
        if "pairs" in result:
            _fixed(result["pairs"], None)
    elif name in ("supports", "hero_traits", "hero_memories"):
        _fixed(status, "absent" if observed is None else "captured")
        _require(bound is result["bound_level_candidates"] is None)
        _integer(result["catalog_members"], maximum=4097)
        _require(result["catalog_members"] != 0 or result["catalog_level_mentions"] == 0)
        _fixed(coverage, "unknown_section_absent" if observed is None else "nothing_observed" if observed == 0 else
               "saved_catalog_domain_has_no_level_text" if result["catalog_members"] and result["catalog_level_mentions"] == 0 else "unknown_not_resolved")
    elif name == "sp_talent_tree":
        _enum(status, ("absent", "captured_opaque"))
        _fixed(result["pairs"], observed)
        _fixed(result["bound_level_candidates"], None)
        _fixed(bound, None if status == "absent" else 0)
        _fixed(coverage, "unknown_section_absent" if status == "absent" else "unknown_no_catalog_domain")
        if status == "absent":
            _fixed(observed, None)
    elif name in ("other_wear_items", "jewel_items", "talent_jewelry_data_list", "hero_character_items"):
        if status == "captured" and observed is not None:
            _fixed(bound, 0)
            _fixed(result["bound_level_candidates"], 0 if observed == 0 else None)
            _fixed(coverage, "nothing_observed" if observed == 0 else "unknown_not_resolved")
        else:
            _require(observed is bound is result["bound_level_candidates"] is None)
            _fixed(coverage, "unknown_section_" + status)
    elif status != "captured":
        _require(observed is bound is result["bound_level_candidates"] is None)
        _fixed(coverage, "unknown_section_" + status)
    elif observed == 0:
        _fixed(bound, 0)
        _fixed(coverage, "nothing_observed")
    elif observed is None or result["bound_level_candidates"] is None:
        if observed is None:
            _require(bound is result["bound_level_candidates"] is None)
        else:
            _integer(bound)
        _fixed(coverage, "unknown_for_unresolved_rows")
    else:
        _integer(bound)
        _enum(coverage, ("unknown_for_unresolved_rows", "all_observed_rows_bound"))
        if coverage == "all_observed_rows_bound":
            _fixed(bound, observed)
    return result


def _project(document, source_sha256, canonical):
    _preflight(document)
    _pattern(source_sha256, r"[0-9a-f]{64}")
    result = _object(document, "format version source arithmetic_ready runtime_verified identity_verified import_complete effective_level uniquely_derivable target candidates domains gaps limitations", canonical)
    _fixed(result["format"], CANONICAL_FORMAT if canonical else FORMAT)
    _enum(result["version"], VERSIONS)
    result["format"] = CANONICAL_FORMAT
    result["source"] = _object(result["source"], "sha256 binding", canonical)
    _fixed(result["source"]["sha256"], source_sha256)
    _fixed(result["source"]["binding"], "caller_supplied_document_only")
    for key in ("arithmetic_ready", "runtime_verified", "identity_verified", "import_complete", "uniquely_derivable"):
        _fixed(result[key], False)
    _fixed(result["effective_level"], None)
    _fixed(result["limitations"], list(LIMITATIONS))
    result["limitations"] = list(LIMITATIONS)
    result["target"] = _target(result["target"], canonical, result["version"])
    result["candidates"] = [_candidate(row, result["target"], canonical) for row in _list(result["candidates"])]
    result["gaps"] = [_gap(row, canonical) for row in _list(result["gaps"])]
    domains = _object(result["domains"], " ".join(DOMAINS), True) if canonical else _object(result["domains"], " ".join(DOMAINS.values()), True)
    result["domains"] = {key: _domain(domains[key if canonical else source], key, canonical) for key, source in DOMAINS.items()}
    for kind, name in (("gear", "gear"), ("talent", "talents"), ("slate", "divinity_slates"), ("pactspirit", "pactspirits")):
        rows = [row for row in result["candidates"] if row["domain"] == kind]
        count = len(rows)
        domain = result["domains"][name]
        _require(domain["bound_level_candidates"] is None or domain["bound_level_candidates"] == count)
        _require(count == 0 or domain["status"] == "captured" and domain["observed"] is not None)
        if rows:
            if kind in ("gear", "pactspirit"):
                _require(domain["bound"] is not None and len({row["path"] for row in rows}) <= domain["bound"])
                if kind == "gear":
                    _require(len({row["path"] for row in rows}) == count)
                    _require(all(int(re.search(r"data\[([0-9]+)\]", row["path"]).group(1)) < domain["items"] for row in rows))
            elif kind == "slate":
                _require(domain["bound"] is not None and domain["bound"] > 0
                         and len({row["path"] for row in rows}) <= domain["slates"])
            else:
                computed = {row["path"] for row in rows if row["binding"]["status"] == "computed"}
                _require(not computed or domain["bound"] is not None and len(computed) <= domain["bound"])
                _require(not any(row["binding"]["status"] == "exact" for row in rows) or domain["notables"]["bound"] > 0)
    for name, domain in result["domains"].items():
        if name == "ethereal_prism" and domain["status"] == "captured" and domain["observed"] is not None:
            _fixed(domain["bound_level_candidates"], 0)
        if name in ("gear", "talents", "divinity_slates", "pactspirits", "ethereal_prism"):
            if domain["status"] == "captured" and domain["observed"] not in (None, 0) and domain["bound_level_candidates"] is not None:
                unresolved = any(row["domain"] == name and (name, row["reason"]) not in
                                 (("gear", "catalog_member_invalid"), ("talents", "rank_scaling_unknown"))
                                 for row in result["gaps"])
                _fixed(domain["candidate_coverage"], "unknown_for_unresolved_rows" if unresolved else "all_observed_rows_bound")
        if domain["status"] == "collection_limit":
            gaps = [row for row in result["gaps"] if row["domain"] == name]
            _require(len(gaps) == 1 and gaps[0]["reason"] == "collection_limit")
        else:
            _require(not any(row["domain"] == name and row["reason"] == "collection_limit" for row in result["gaps"]))
    for row in result["candidates"]:
        if row["domain"] == "talent" and row["amount"] is None:
            _require(any(gap["domain"] == "talents" and gap["reason"] == "rank_scaling_unknown" and gap["path"] == row["path"] for gap in result["gaps"]))
    return result


def project(document, source_sha256):
    """Return a detached safe ledger bound to the caller's expected source annotation."""
    return _project(document, source_sha256, False)


def summary(canonical):
    """Revalidate and project an existing canonical ledger without reading source bytes."""
    _preflight(canonical)
    source = _object(canonical, "source", True)["source"]
    return _project(canonical, _object(source, "sha256", True)["sha256"], True)
