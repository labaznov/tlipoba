"""Pure damage arithmetic; all combat conditions are explicit inputs."""

import math

from .formulas import additional


def bounded(value, minimum, maximum, name):
    if not math.isfinite(value) or not minimum <= value <= maximum:
        raise ValueError(f"{name} must be between {minimum} and {maximum}")
    return value


def critical(chance, multiplier, *, lucky, more=0):
    if lucky is not True and lucky is not False:
        raise ValueError("Lucky must be a boolean")
    bounded(chance, 0, 1, "Critical chance")
    bounded(multiplier, 0, 100, "Critical multiplier")
    bounded(more, -1, 100, "Critical-only more damage")
    probability = 1 - (1 - chance) ** 2 if lucky else chance
    return (1 - probability) + probability * multiplier * (1 + more)


def topology(maximum, extra, active, hits, retention):
    bounded(maximum, 0, 4, "Supported Tangle maximum")
    for name, value in (("Tangle maximum", maximum), ("Additional attachments", extra),
                        ("Active tangles", active), ("Hits", hits)):
        bounded(value, 0, 1000, name)
        if value != math.floor(value):
            raise ValueError(f"{name} must be an integer")
    bounded(retention, 0, 1, "Shotgun retained fraction")
    if active > maximum:
        raise ValueError("Active tangles exceed the maximum")
    attached = min(maximum, 1 + extra, active)
    shotgun = 0 if hits == 0 else 1 + (hits - 1) * retention
    return {"attached": attached, "shotgun": shotgun, "factor": round(attached * shotgun, 12)}


def cold(base, physical, flat, effectiveness, increased, origin, destination, modifiers):
    """Calculate one noncritical hit after complete Physical to Cold conversion."""
    for name, value in (("Base damage", base), ("Added physical damage", physical),
                        ("Added cold damage", flat), ("Added effectiveness", effectiveness)):
        bounded(value, 0, 1e15, name)
    for name, value in (("Global increased", increased), ("Physical increased", origin),
                        ("Cold increased", destination)):
        bounded(value, -1, 1e6, name)
    pools = {"all": [], "physical": [], "cold": []}
    identities = set()
    for modifier in modifiers:
        if not all(field in modifier for field in ("id", "affix", "scope", "value", "stacks", "mode")):
            raise ValueError("Cold modifier requires id, affix, scope, value, stacks and mode")
        if modifier["id"] in identities:
            raise ValueError(f"Duplicate modifier {modifier['id']}")
        identities.add(modifier["id"])
        if modifier["scope"] not in pools:
            raise ValueError(f"Unknown damage scope {modifier['scope']}")
        pools[modifier["scope"]].append({
            "id": modifier["id"], "affix": modifier["affix"],
            "value": bounded(modifier["value"], -1, 1e6, "More damage"),
            "stacks": modifier["stacks"], "mode": modifier["mode"],
        })
    converted_factor = additional(pools["all"] + pools["physical"] + pools["cold"])
    native_factor = additional(pools["all"] + pools["cold"])
    converted = (base + physical * effectiveness) * max(0, 1 + increased + origin + destination)
    native = flat * effectiveness * max(0, 1 + increased + destination)
    result = converted * converted_factor + native * native_factor
    if not math.isfinite(result):
        raise ValueError("Cold hit must be finite")
    return result


def calculate(panel, condition):
    geometry = topology(panel["max_tangles"], panel["extra_attachments"], condition["active"],
                        condition["hits"], condition["retention"])
    if condition["basis"] == "panel":
        base = bounded(panel["spell_dps"], 0, 1e18, "Panel DPS")
        trace = [{"label": "Панельный Spell DPS, уже с учтёнными игрой бонусами", "value": base}]
    elif condition["basis"] == "hit":
        minimum = bounded(panel["hit_min"], 0, 1e18, "Minimum hit")
        maximum = bounded(panel["hit_max"], minimum, 1e18, "Maximum hit")
        rate = min(30, bounded(panel["cast_rate"], 0, 1e6, "Cast rate"))
        expectation = critical(panel["crit_chance"], panel["crit_multiplier"],
                               lucky=condition["lucky"], more=condition["critical_more"])
        base = (minimum + maximum) / 2 * rate * expectation
        trace = [{"label": "Средний некритический урон (допущение о панели)", "value": (minimum + maximum) / 2},
                 {"label": "Кастов в секунду, предел 30", "factor": rate},
                 {"label": "Ожидание крита, Lucky и критического more", "factor": expectation}]
    else:
        raise ValueError("Basis must be panel or hit")
    resistance = bounded(condition["resistance"], -10, 1, "Enemy cold resistance")
    penetration = bounded(panel["cold_penetration"], 0, 10, "Cold penetration")
    taken = bounded(condition["taken"], -1, 100, "External increased damage taken")
    uptime = bounded(condition["uptime"], 0, 1, "Effective uptime")
    defence = max(0, 1 - resistance + penetration)
    dps = base * geometry["factor"] * defence * (1 + taken) * uptime
    trace.extend([
        {"label": "Tangle на одной цели: min(максимум, 1 + дополнительные, активные)", "factor": geometry["attached"]},
        {"label": "Попадания: 1 + (N − 1) × оставшаяся доля", "factor": geometry["shotgun"]},
        {"label": "Сопротивление цели и пробивание: 1 − R + P", "factor": defence},
        {"label": "Внешний увеличенный получаемый урон: 1 + taken", "factor": 1 + taken},
        {"label": "Доля времени нанесения урона", "factor": uptime},
    ])
    return {"status": "conditional", "dps": dps, "single_projectile_dps": base,
            "attached": geometry["attached"], "trace": trace,
            "assumptions": [
                "Исходная величина трактуется как один снаряд одного Tangle; семантика Spell DPS не подтверждена",
                "Попадания, оставшаяся доля shotgun, сопротивление и время боя заданы сценарием",
                "Сопротивление цели задано после применимых ограничений; пробивание вычитается из эффективного значения",
                "Внешний taken применяется только если он ещё не учтён в исходной панели",
                "Число созданных Tangle и прикреплённых к цели Tangle различаются",
                "Баффы Heat Up, Burning Red, проклятие, Frostbite и Euphoria зависят от состояния боя",
                "Броня учитывается только при явном боевом контексте; пробивание брони не реализовано",
            ]}
