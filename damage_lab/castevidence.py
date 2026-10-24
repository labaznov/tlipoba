"""Project exact cast-row evidence without resolving value roles or combat effects.

The parent ledger must bind the source, native affix, item and catalog bytes.
This leaf only validates the reviewed additive diagnostic contract for compiler
0.4.1; its own values and catalog specs never become paired effect values.
"""

from decimal import Decimal
import math
import re


COMPOSITE = "+#% Cast Speed\n+#% Minion Cast Speed"
HASTEN = "Has Hasten\n+#% Attack Speed, Cast Speed, and Movement Speed when having Hasten"
ERROR = "Cast evidence contains an invalid diagnostic contract"


def _require(condition):
    if not condition:
        raise ValueError(ERROR)


def _preflight(value):
    stack, seen, count = [(value, 0)], set(), 0
    while stack:
        node, depth = stack.pop()
        count += 1
        _require(count <= 10_000 and depth <= 64)
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


def _name(value):
    return re.sub(r"([A-Z])", r"_\1", value).lower().lstrip("_")


def _select(value, fields, canonical):
    _require(type(value) is dict)
    names = {_name(field) if canonical else field: _name(field) for field in fields.split()}
    _require(set(names).issubset(value))
    return {target: value[source] for source, target in names.items()}


def _pattern(value, pattern):
    _require(type(value) is str and re.fullmatch(pattern, value, re.ASCII) is not None)


def _decimal(value):
    _pattern(value, r"-?[0-9]{1,12}(?:\.[0-9]{1,9})?")
    return Decimal(value)


def _definition(value, canonical):
    result = _select(value, "catalog id tier tierId templateSource", canonical)
    _pattern(result["catalog"], r"gear/[a-z0-9_-]{1,64}(?:/[a-z0-9_-]{1,64}){0,4}/master")
    for field in ("id", "tier_id"):
        _pattern(result[field], r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}")
    if result["tier"] is not None:
        _pattern(result["tier"], r"[0-9]{1,3}\+?")
    _require(result["template_source"] == "descriptionTemplate")
    return result


def _project(value, canonical):
    _preflight(value)
    result = _select(value, "kind binding definition template specs ownValues nativeConditions templateCondition "
                     "valueRole activation arithmeticReady", canonical)
    _require(result["kind"] == "cast_input_candidate" and result["binding"] == "exact_native_affix_definition"
             and result["value_role"] == "unresolved" and result["activation"] == "unknown"
             and result["arithmetic_ready"] is False)
    template = result["template"]
    _require(type(template) is str and template in (COMPOSITE, HASTEN))
    _require(result["template_condition"] == ("none" if template == COMPOSITE else "hasten"))
    result["definition"] = _definition(result["definition"], canonical)
    specs = result["specs"]
    _require(type(specs) is list and len(specs) == (2 if template == COMPOSITE else 1))
    rows = []
    for index, value in enumerate(specs):
        row = _select(value, "index minExact maxExact unit", canonical)
        _require(type(row["index"]) is int and row["index"] == index and row["unit"] == "%")
        _require(_decimal(row["min_exact"]) <= _decimal(row["max_exact"]))
        rows.append(row)
    result["specs"] = rows
    values = result["own_values"]
    _require(type(values) is list and len(values) == 1)
    row = _select(values[0], "index exact source", canonical)
    _require(type(row["index"]) is int and row["index"] == 0 and row["source"] == "DynArgs[0]")
    _decimal(row["exact"])
    result["own_values"] = [row]
    conditions = _select(result["native_conditions"], "Condition Filter Behavior", canonical)
    for status in conditions.values():
        _require(type(status) is str and status in ("empty", "present", "missing", "invalid"))
    result["native_conditions"] = conditions
    return result


def project(raw):
    """Return detached snake_case evidence while leaving every effect value unresolved."""
    return _project(raw, False)


def summary(canonical):
    """Revalidate a canonical leaf without performing source or catalog I/O."""
    return _project(canonical, True)
