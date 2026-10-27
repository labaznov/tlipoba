"""Evaluate a fully fictional spell and target through the raw combat stages."""

import json
from pathlib import Path

from damage_lab.rawcombat import evaluate


if __name__ == "__main__":
    scenario = json.loads(Path(__file__).with_name("raw_combat.json").read_text(encoding="utf-8"))
    print(json.dumps(evaluate(scenario), ensure_ascii=False, indent=2, allow_nan=False))
