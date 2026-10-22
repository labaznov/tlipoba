"""Validate one fixed wand implicit proof without resolving its pool or authenticating bytes."""

from decimal import Decimal
import math
import re


MASTER = "gear/one_handed/wand/master"
ENGLISH = "gear/one_handed/wand/i18n/en"
TEMPLATE = "+#% Spell Damage"
PHRASE = "% Spell Damage"
ERROR = "Fixed implicit contains an invalid catalog proof"


def _require(condition):
    if not condition:
        raise ValueError(ERROR)


def _preflight(value):
    stack, seen, count = [(value, 0)], set(), 0
    while stack:
        node, depth = stack.pop()
        count += 1
        _require(count <= 10_000 and depth <= 32)
        if type(node) in (dict, list):
            _require(id(node) not in seen and len(node) <= 4096)
            seen.add(id(node))
            if type(node) is dict:
                _require(all(type(key) is str for key in node))
                stack.extend((key, depth + 1) for key in node)
            stack.extend((child, depth + 1) for child in (node.values() if type(node) is dict else node))
        elif type(node) is str:
            _require(len(node) <= 4096)
            try:
                node.encode("utf-8")
            except UnicodeError:
                raise ValueError(ERROR) from None
        elif type(node) is int:
            _require(-10 ** 20 < node < 10 ** 20)
        elif type(node) is float:
            _require(math.isfinite(node))
        else:
            _require(node is None or type(node) is bool)


def _select(value, fields, canonical):
    _require(type(value) is dict)
    names = {re.sub(r"([A-Z])", r"_\1", field).lower(): field for field in fields.split()}
    _require(all((name if canonical else field) in value for name, field in names.items()))
    return {name: value[name if canonical else field] for name, field in names.items()}


def _pattern(value, pattern):
    _require(type(value) is str and re.fullmatch(pattern, value, re.ASCII) is not None)


def _decimal(value, *, signed=True):
    _pattern(value, (r"-?" if signed else "") + r"[0-9]{1,12}(?:\.[0-9]{1,9})?")
    return Decimal(value)


def _project(value, canonical):
    _preflight(value)
    result = _select(value, "kind binding modifierId master english ownValue equality registryTemplate "
                     "poolIdentity runtimeVerified arithmeticReady", canonical)
    _require(result["kind"] == "fixed_base_implicit" and result["binding"] == "exact_item_guid_and_native_id"
             and result["modifier_id"] == "520020" and result["pool_identity"] == "unresolved"
             and result["registry_template"] == TEMPLATE and result["runtime_verified"] is False
             and result["arithmetic_ready"] is False
             and result["equality"] == "own_value_equals_min_equals_max_equals_raw_text_number")
    master = _select(result["master"], "catalog sha256 itemGuid tlidbId spec", canonical)
    english = _select(result["english"], "catalog sha256 itemGuid rawText numberExact phrase", canonical)
    _require(master["catalog"] == MASTER and english["catalog"] == ENGLISH)
    for row in (master, english):
        _pattern(row["sha256"], r"[0-9a-f]{64}")
        _pattern(row["item_guid"], r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}")
    _pattern(master["tlidb_id"], r"[1-9][0-9]{0,19}")
    _require(master["item_guid"] == english["item_guid"] and english["phrase"] == PHRASE)
    spec = _select(master["spec"], "minExact maxExact sign unit", canonical)
    _require(spec["sign"] == "+" and spec["unit"] == "%")
    own = _select(result["own_value"], "exact source", canonical)
    _require(own["source"] == "DynArgs[0]")
    number = _decimal(english["number_exact"], signed=False)
    _require(english["raw_text"] == "+" + english["number_exact"] + PHRASE
             and _decimal(own["exact"]) == _decimal(spec["min_exact"]) == _decimal(spec["max_exact"]) == number)
    master["spec"] = spec
    result.update(master=master, english=english, own_value=own)
    return result


def project(raw):
    """Return exact, detached proof fields while leaving pooling and runtime unverified."""
    return _project(raw, False)


def summary(canonical):
    """Revalidate retained proof fields without reading source or catalog bytes."""
    return _project(canonical, True)
