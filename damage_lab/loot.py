"""Calculate conditional loot expectations from explicit normalized scenarios."""

import argparse
from decimal import Decimal
import json
import math
import operator
from fractions import Fraction
from pathlib import Path
import sys
import tempfile


def _number(value, label):
    if value is True or value is False:
        raise ValueError(f"{label} must be a finite number")
    try:
        numerator, denominator = value.as_integer_ratio()
        return Fraction(numerator, denominator)
    except (AttributeError, OverflowError, TypeError, ValueError) as error:
        raise ValueError(f"{label} must be a finite number") from error


def _amount(value):
    value = _number(value, "Expected quantity")
    if value < 0:
        raise ValueError("Expected quantity cannot be negative")
    return value


def _keys(value, keys, label):
    try:
        if set(dict.keys(value)) != set(keys):
            raise ValueError(f"{label} requires exactly {', '.join(sorted(keys))}")
    except TypeError as error:
        raise ValueError(f"{label} must be an object") from error


def _boolean(value, label):
    if value is not True and value is not False:
        raise ValueError(f"{label} must be an explicit boolean")
    return value


def _array(value, label):
    try:
        return list.__iter__(value)
    except TypeError as error:
        raise ValueError(f"{label} must be an array") from error


def _pool(value):
    return [_number(item, "Quantity modifier") for item in _array(value, "Quantity modifiers")]


def _factor(value):
    if value < 0:
        raise ValueError("Quantity modifiers cannot produce a negative factor")
    return value


def _value(value):
    try:
        result = float(value)
    except OverflowError as error:
        raise ValueError("Loot arithmetic exceeds finite output precision") from error
    if not math.isfinite(result) or (value != 0 and result == 0):
        raise ValueError("Loot arithmetic exceeds finite output precision")
    return result


def _mapping(value, label):
    try:
        keys = dict.keys(value)
        for key in keys:
            _text(key, label)
    except TypeError as error:
        raise ValueError(f"{label} must be an object with text item types") from error
    return value


def _text(value, label):
    try:
        if not str.strip(value) or str.strip(value) != value:
            raise ValueError(f"{label} requires nonempty trimmed item types")
    except TypeError as error:
        raise ValueError(f"{label} requires text item types") from error
    return value


def quantity(base, *, ordinary, additional, typed, eligible):
    """Apply quantity pools to one original item type, before extra drops."""
    base = _amount(base)
    _keys(eligible, ("general", "type"), "Quantity eligibility")
    for value in eligible.values():
        _boolean(value, "Quantity eligibility")
    ordinary, additional, typed = _pool(ordinary), _pool(additional), _pool(typed)
    pooled = _factor(1 + sum(ordinary))
    factors = [_factor(1 + value) for value in additional]
    factor = _factor(1 + sum(typed))
    general = (pooled * math.prod(factors)
               if eligible["general"] else 1)
    factor = factor if eligible["type"] else 1
    return {
        "status": "conditional_expectation",
        "expected": _value(base * general * factor),
        "trace": [
            {"stage": "general_quantity", "factor": _value(general),
             "modifiers": {"ordinary": [_value(value) for value in ordinary],
                           "additional": [_value(value) for value in additional]},
             "ignored": not eligible["general"], "expected": _value(base * general),
             "source": "https://tlidb.com/en/Drop_quantity#DropquantityManualRule"},
            {"stage": "type_quantity", "factor": _value(factor),
             "modifiers": [_value(value) for value in typed],
             "ignored": not eligible["type"], "expected": _value(base * general * factor),
             "source": "https://tlidb.com/en/Drop_Quantity_Bonuses_for_Certain_Item_Types"},
        ],
    }


def conversion(amounts, *, chances):
    """Convert original drop slots simultaneously, never destination quantities."""
    _mapping(amounts, "Conversion inputs")
    _keys(chances, amounts, "Conversion chances")
    amounts = {key: _amount(value) for key, value in amounts.items()}
    result = {key: Fraction(0) for key in amounts}
    trace = []
    for source, amount in amounts.items():
        _mapping(chances[source], "Conversion destinations")
        probabilities = {key: _number(value, "Conversion chance")
                         for key, value in chances[source].items()}
        if any(not 0 <= value <= 1 for value in probabilities.values()):
            raise ValueError("Each conversion chance must be between zero and one")
        divisor = max(1, sum(probabilities.values()))
        probabilities = {key: value / divisor for key, value in probabilities.items()}
        retained = amount * (1 - sum(probabilities.values()))
        result[source] += retained
        for target, probability in probabilities.items():
            result[target] = result.get(target, 0) + amount * probability
        trace.append({"stage": "conversion", "type": source, "input": _value(amount),
                      "retained": _value(retained),
                      "probabilities": {key: _value(value) for key, value in probabilities.items()},
                      "source": "https://tlidb.com/en/Type_Conversion"})
    return {"status": "conditional_expectation",
            "expected": {key: _value(value) for key, value in result.items()},
            "input_total": _value(sum(amounts.values())),
            "output_total": _value(sum(result.values())), "trace": trace}


def replication(amounts, *, ordinary, additional):
    """Replicate expected slots using two classes of guaranteed copy counts."""
    _mapping(amounts, "Replication inputs")
    _keys(ordinary, amounts, "Ordinary replication")
    _keys(additional, amounts, "Additional replication")
    result = {}
    trace = []
    for item, amount in amounts.items():
        counts = []
        for pool in (ordinary[item], additional[item]):
            values = []
            for value in _array(pool, "Replication counts"):
                try:
                    count = operator.index(value)
                except TypeError as error:
                    raise ValueError("Guaranteed replication requires integer copy counts") from error
                if value is True or value is False or count < 0:
                    raise ValueError("Guaranteed replication requires nonnegative integer copy counts")
                values.append(count)
            counts.append(values)
        factor = (1 + sum(counts[0])) * (1 + sum(counts[1]))
        result[item] = _value(_amount(amount) * factor)
        trace.append({"stage": "replication", "type": item, "ordinary": counts[0],
                      "additional": counts[1], "factor": _value(factor),
                      "expected": result[item],
                      "source": "https://tlidb.com/en/Replicate#ReplicateManualRule"})
    return {"status": "conditional_expectation", "expected": result, "trace": trace}


def scenario(document):
    """Run explicitly normalized quantity, extra, conversion and copy stages."""
    _keys(document, ("format", "base", "extra", "conversion", "replication"), "Loot scenario")
    if document["format"] != "tli-loot-scenario-v1":
        raise ValueError("Loot scenario format must be tli-loot-scenario-v1")
    amounts = {}
    trace = [{"stage": "effect_priority", "source": "https://tlidb.com/en/Effect_Priority",
              "order": ["quantity", "type_quantity", "additional_drops", "conversion", "replication"]}]
    for row in _array(document["base"], "Base drops"):
        _keys(row, ("type", "expected", "ordinary", "additional", "typed", "eligible"), "Base drop")
        item = _text(row["type"], "Base drop")
        result = quantity(row["expected"], ordinary=row["ordinary"], additional=row["additional"],
                          typed=row["typed"], eligible=row["eligible"])
        amounts[item] = amounts.get(item, 0) + _amount(result["expected"])
        trace.extend({"type": item, **step} for step in result["trace"])
    for row in _array(document["extra"], "Additional drops"):
        _keys(row, ("type", "expected", "eligible"), "Additional drop")
        item = _text(row["type"], "Additional drop")
        amount = _amount(row["expected"])
        eligible = _boolean(row["eligible"], "Additional drop eligibility")
        amounts[item] = amounts.get(item, 0) + (amount if eligible else 0)
        trace.append({"stage": "additional_drops", "type": item, "input": _value(amount),
                      "ignored": not eligible, "contribution": _value(amount if eligible else 0),
                      "expected": _value(amounts[item]),
                      "source": "https://tlidb.com/en/Additional_Drops"})
    result = conversion(amounts, chances=document["conversion"])
    trace.extend(result["trace"])
    _keys(document["replication"], ("ordinary", "additional"), "Replication classes")
    result = replication(result["expected"], ordinary=document["replication"]["ordinary"],
                         additional=document["replication"]["additional"])
    trace.extend(result["trace"])
    return {
        "format": "tli-loot-report-v1", "patch": "SS14", "status": "conditional_expectation",
        "expected": result["expected"], "trace": trace,
        "assumptions": ["Inputs are explicit scenario expectations, not automatically imported character modifiers",
                        "Conversion conserves drop slots or sets, not unknown units inside each set",
                        "Replication counts are guaranteed and class bindings are supplied explicitly"],
        "gaps": ["Base drop probabilities and loot table weights are not inferred",
                 "Rarity probabilities and reward prices are not modeled",
                 "Fractional expectations do not specify actual drops or a universal rounding distribution",
                 "TLIDB Help is an unofficial mirror whose individual paragraphs are not release-pinned"],
    }


def _unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate loot input field: {key}")
        result[key] = value
    return result


def main(argv=None):
    """Publish one report directory atomically on the supported Windows runtime."""
    parser = argparse.ArgumentParser(description="Calculate conditional expected loot quantities")
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    arguments = parser.parse_args(argv)
    try:
        with arguments.input.open(encoding="utf-8") as handle:
            result = scenario(json.load(handle, parse_float=Decimal, object_pairs_hook=_unique))
        target = arguments.output.resolve()
        if target.exists():
            raise FileExistsError(f"Output directory already exists: {target}")
        with tempfile.TemporaryDirectory(prefix=".loot-", dir=target.parent) as directory:
            folder = Path(directory)
            with (folder / "report.json").open("x", encoding="utf-8") as handle:
                json.dump(result, handle, ensure_ascii=False, indent=2, allow_nan=False)
                handle.write("\n")
            folder.rename(target)
        print(target / "report.json")
        return 0
    except (OSError, ValueError) as error:
        print(f"Loot report failed: {str(error).rstrip('.')}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
