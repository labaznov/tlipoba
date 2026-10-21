"""Create fictional input data for a public, offline calculator example."""

import argparse
import hashlib
import json
from pathlib import Path


def fixture(output):
    guide = {"synthetic": True, "name": "Synthetic Carino",
             "capturedAt": "2026-10-21T00:00:00Z",
             "character": {"name": "Carino", "englishName": "Carino", "class": "Divineshot",
                           "trait": "Zealot of War"},
             "gear": [{"name": "Synthetic training wand", "slot": "mainHand",
                       "affixes": [{"text": "+17% Spell Damage"}]}],
             "skillGroups": [{"kind": "active", "main": {"name": "Chromatic Shot", "gameId": 7007, "level": 20},
                              "supports": []}],
             "talentTrees": [], "heroMemories": []}
    build = {"loadouts": {"currentLoadoutId": "synthetic", "loadouts": [
        {"id": "synthetic", "name": "Synthetic loadout",
         "skills": {"activeSkills": [], "passiveSkills": []}, "skillTree": {"slots": []}}]}}
    manifest = {"synthetic": True, "capturedAt": guide["capturedAt"], "status": "synthetic",
                "identity": {"title": "Synthetic Carino"},
                "buildSha256": hashlib.sha256(encode(build).encode("utf-8")).hexdigest()}
    observations = {"synthetic": True, "description": "Fictional arithmetic example; no game measurement",
                    "evidence": {"fixture": {"path": "synthetic:fixture"}},
                    "panel": [
                        {"key": key, "label": key, "value": value, "display": display,
                         "unit": unit, "evidence": "fixture"}
                        for key, value, display, unit in (
                            ("spell_dps", 31729, "31,729", "damage/s"),
                            ("hit_min", 913, "913", "damage"),
                            ("hit_max", 1437, "1,437", "damage"),
                            ("cast_rate", 4.73, "4.73/s", "casts/s"),
                            ("crit_chance", 0.4137, "41.37%", "fraction"),
                            ("crit_multiplier", 2.87, "287%", "multiplier"),
                            ("max_tangles", 2, "2", "count"),
                            ("extra_attachments", 1, "1", "count"),
                            ("cold_penetration", 0.07, "7%", "fraction"))],
                    "benchmark": {"label": "Synthetic benchmark; not a game measurement",
                                  "evidence": "fixture", "values": [
                                      {"key": key, "label": key, "value": value,
                                       "display": display, "unit": unit}
                                      for key, value, display, unit in (
                                          ("average_dps", 185319, "185,319", "damage/s"),
                                          ("duration", 17, "17s", "s"),
                                          ("highest_5s", 216011, "216,011", "damage/s"),
                                          ("average_5s", 179433, "179,433", "damage/s"),
                                          ("survival", 9127, "9,127", "survival"))]},
                    "notes": ["SYNTHETIC: all items, values and benchmark numbers are fictional",
                              "There are no player observations, account data or screenshots in this example",
                              "The benchmark is arbitrary independent test data; no multiplier is fitted to it"]}
    output.mkdir(parents=True, exist_ok=False)
    for name, data in (("guide-data.json", guide),
                       ("source.json", {"synthetic": True, "sections": {}}),
                       ("build.json", build), ("manifest.json", manifest),
                       ("transfer-report.json", {"synthetic": True, "complete": False,
                                                 "canClaimFullTransfer": False,
                                                 "issues": ["Synthetic input; no real transfer occurred"]}),
                       ("observations.json", observations)):
        (output / name).write_text(encode(data), encoding="utf-8", newline="\n")


def encode(data):
    return json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path, help="New directory for fictional input files")
    arguments = parser.parse_args(argv)
    try:
        fixture(arguments.output)
    except OSError as error:
        parser.exit(1, f"Cannot create synthetic example: {str(error).rstrip('.')}\n")
    print("Synthetic example created; every value is fictional")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
