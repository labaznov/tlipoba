"""Print an explicit synthetic raw spell expectation without reading a player export."""

import json
from pathlib import Path

from damage_lab.rawspell import evaluate


if __name__ == "__main__":
    document = json.loads(Path(__file__).with_name("raw_spell.json").read_text(encoding="utf-8"))
    print(json.dumps(evaluate(document), ensure_ascii=False, indent=2, allow_nan=False))
