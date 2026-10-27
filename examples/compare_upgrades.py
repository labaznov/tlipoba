"""Run a fictional upgrade comparison without game or market inputs."""

import json
from pathlib import Path

from damage_lab.upgrades import evaluate


def main():
    document = json.loads(Path(__file__).with_name("upgrades.json").read_text(encoding="utf-8"))
    print(json.dumps(evaluate(document), ensure_ascii=False, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
