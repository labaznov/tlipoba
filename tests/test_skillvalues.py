import unittest

from damage_lab.skillvalues import extract


def guide():
    return {"skillGroups": [{"main": {"name": "Synthetic spell", "level": 17}, "supports": [{
        "name": "Synthetic support", "guid": "synthetic-support", "level": 13,
        "descriptionStatus": "rendered", "descriptionLevel": 13,
        "levelValues": {"status": "resolved", "level": 13, "values": {"value1": 7.4},
                        "cells": {"value1": "37/5"}, "issues": [],
                        "source": {"catalogPath": "skill/Support", "seasonId": "SS14",
                                   "tlidbId": 9876, "guid": "synthetic-support",
                                   "field": "levelProgression[level=13]"}}}]}]}


class SkillValuesTest(unittest.TestCase):
    """Imported skill parameters preserve exact level provenance without compiling damage."""

    def test_resolved_values_keep_raw_rational_cells(self):
        self.assertEqual(extract(guide())[1]["cells"], {"value1": "37/5"})

    def test_missing_level_data_remains_unavailable(self):
        self.assertEqual(extract(guide())[0]["status"], "unavailable")

    def test_unresolved_parameters_cannot_enter_the_numeric_model(self):
        data = guide()
        data["skillGroups"][0]["supports"][0]["levelValues"]["status"] = "unverified_flat_tail"
        with self.assertRaisesRegex(ValueError, "unresolved.*values"):
            extract(data)

    def test_level_mismatch_is_rejected(self):
        data = guide()
        data["skillGroups"][0]["supports"][0]["levelValues"]["level"] = 11
        with self.assertRaisesRegex(ValueError, "level"):
            extract(data)

    def test_raw_cells_must_match_resolved_values(self):
        data = guide()
        data["skillGroups"][0]["supports"][0]["levelValues"]["values"]["value1"] = 8.7
        with self.assertRaisesRegex(ValueError, "cell"):
            extract(data)

    def test_nonzero_rational_cannot_underflow_to_a_resolved_zero(self):
        data = guide()
        parameters = data["skillGroups"][0]["supports"][0]["levelValues"]
        parameters["values"]["value1"] = 0
        parameters["cells"]["value1"] = "1/1" + "0" * 400
        with self.assertRaisesRegex(ValueError, "range"):
            extract(data)

    def test_unsupported_source_fields_are_not_published(self):
        data = guide()
        data["skillGroups"][0]["supports"][0]["levelValues"]["source"]["account"] = "private-marker"
        self.assertNotIn("private-marker", str(extract(data)))

    def test_nonfinite_and_boolean_parameters_are_rejected(self):
        for value in (float("nan"), float("inf"), True):
            with self.subTest(value=value):
                data = guide()
                data["skillGroups"][0]["supports"][0]["levelValues"]["values"]["value1"] = value
                with self.assertRaises(ValueError):
                    extract(data)

    def test_export_is_independent_of_the_input(self):
        data = guide()
        result = extract(data)
        result[1]["cells"]["value1"] = "1/3"
        self.assertEqual(data, guide())
