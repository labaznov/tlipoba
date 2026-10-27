"""Preserve level-specific catalog parameters separately from applied damage modifiers."""

import copy
import math
import re
from fractions import Fraction

STATUSES = {"resolved", "missing_level", "duplicate_level", "invalid_value",
            "unverified_flat_tail", "not_level_scaled"}
SOURCE = ("catalogPath", "seasonId", "tlidbId", "guid", "field")
CELL = re.compile(r"-?\d+(?:\.\d+)?|-?\d+/[1-9]\d*")


def number(value):
    if type(value) not in (int, float):
        raise ValueError("Skill parameter must be a finite number")
    try:
        if math.isfinite(value):
            return value
    except OverflowError:
        pass
    raise ValueError("Skill parameter must be a finite number")


def cell(value):
    if type(value) in (int, float):
        return number(value)
    if type(value) is not str or not CELL.fullmatch(value.strip()):
        raise ValueError("Skill cell must contain a number or integer ratio")
    try:
        fraction = Fraction(value.strip())
        result = number(float(fraction))
        if fraction != 0 and result == 0:
            raise ValueError("Skill cell is below supported range")
        return result
    except (OverflowError, ZeroDivisionError):
        raise ValueError("Skill cell must contain a finite number") from None


def parameters(skill):
    data = skill.get("levelValues")
    if data is None:
        return {"status": "unavailable", "values": {}, "cells": {}, "source": {},
                "issues": ["Export has no level-specific parameters"]}
    if data.get("status") not in STATUSES:
        raise ValueError("Unknown skill parameter status")
    if type(data.get("level")) is not int or data["level"] != skill.get("level"):
        raise ValueError("Skill parameter level differs from the exported skill level")
    values, cells = data.get("values", {}), data.get("cells", {})
    if data["status"] != "resolved" and (values or cells):
        raise ValueError("An unresolved skill cannot expose numeric values")
    if set(values) != set(cells):
        raise ValueError("Resolved skill values and raw cells differ")
    for key, value in values.items():
        if number(value) != cell(cells[key]):
            raise ValueError(f"Skill cell {key} differs from its normalized value")
    return {"status": data["status"], "values": copy.deepcopy(values),
            "cells": copy.deepcopy(cells), "issues": list(data.get("issues", [])),
            "source": {key: data.get("source", {}).get(key) for key in SOURCE}}


def extract(guide):
    result = []
    for group, entry in enumerate(guide["skillGroups"], 1):
        for position, skill in enumerate([entry["main"], *entry["supports"]]):
            result.append({"group": group, "position": position,
                           "role": "main" if position == 0 else "support", "name": skill["name"],
                           "level": skill.get("level"),
                           "description_status": skill.get("descriptionStatus", "unverified"),
                           "description_level": skill.get("descriptionLevel"), **parameters(skill)})
    return result
