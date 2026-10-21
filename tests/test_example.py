import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


class ExampleTests(unittest.TestCase):
    """Check the public example without player data or external services."""

    def test_creates_an_explicitly_synthetic_package(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "example"
            subprocess.run([sys.executable, "examples/make_fixture.py", str(output)],
                           check=True, capture_output=True, text=True, timeout=10)
            guide = json.loads((output / "guide-data.json").read_text(encoding="utf-8"))
            source = json.loads((output / "source.json").read_text(encoding="utf-8"))
            observations = json.loads((output / "observations.json").read_text(encoding="utf-8"))
            self.assertEqual((guide["synthetic"], guide["name"], source["synthetic"],
                              observations["synthetic"],
                              json.loads((output / "build.json").read_text(encoding="utf-8"))
                              ["loadouts"]["currentLoadoutId"]),
                             (True, "Synthetic Carino", True, True, "synthetic"))

    def test_cannot_overwrite_an_existing_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "example"
            output.mkdir()
            source = output / "source.json"
            source.write_text("preserve me", encoding="utf-8")
            result = subprocess.run([sys.executable, "examples/make_fixture.py", str(output)],
                                    capture_output=True, text=True, timeout=10)
            self.assertEqual((result.returncode, source.read_text(encoding="utf-8")),
                             (1, "preserve me"))

    def test_exposes_fictional_values_in_the_archive_input_format(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "example"
            subprocess.run([sys.executable, "examples/make_fixture.py", str(output)],
                           check=True, capture_output=True, text=True, timeout=10)
            observations = json.loads((output / "observations.json").read_text(encoding="utf-8"))
            self.assertEqual((observations["panel"][0]["key"], observations["panel"][0]["display"],
                              observations["benchmark"]["label"]),
                             ("spell_dps", "31,729", "Synthetic benchmark; not a game measurement"))
