"""Compare fictional complete combat replacements at explicitly invented prices."""

import copy
import json
from pathlib import Path

from damage_lab.combatupgrades import evaluate


if __name__ == "__main__":
    baseline = json.loads(Path(__file__).with_name("raw_combat.json").read_text(encoding="utf-8"))
    baseline["target"].update(armor=100000, armor_effectiveness=.5, armor_penetration=.1)
    hit = copy.deepcopy(baseline)
    hit["spell"]["damage"]["base"] = {"min": 200, "max": 200}
    topology = copy.deepcopy(baseline)
    topology["topology"]["extra"] = 2
    scenario = {"format": "tli-combat-upgrade-scenario-v1", "baseline": baseline, "currency": "synthetic tokens",
                "candidates": [
                    {"id": "hit", "name": "Synthetic base hit replacement", "scenario": hit, "cost": 17, "missing": []},
                    {"id": "topology", "name": "Synthetic topology replacement", "scenario": topology,
                     "cost": 11, "missing": []}]}
    print(json.dumps(evaluate(scenario), ensure_ascii=False, indent=2, allow_nan=False))
