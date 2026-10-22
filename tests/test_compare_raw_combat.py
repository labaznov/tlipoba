import json
import subprocess
import sys
import unittest
from pathlib import Path


class CombatExampleTest(unittest.TestCase):
    """Verify the public example runs offline through its documented module entry point."""

    def test_runnable_comparison_matches_the_independent_combat_oracle(self):
        result = subprocess.run([sys.executable, "-X", "utf8", "-m", "examples.compare_raw_combat"],
                                cwd=Path(__file__).resolve().parents[1], capture_output=True,
                                text=True, encoding="utf-8", timeout=30, check=True)
        data = json.loads(result.stdout)
        self.assertEqual((data["status"], round(data["baseline"]["dps"], 6), data["ranking"],
                          [round(row["delta"], 6) for row in data["candidates"]], data["price_source"]),
                         ("conditional", 291.06, ["hit", "topology"], [291.06, 145.53], "caller"))
