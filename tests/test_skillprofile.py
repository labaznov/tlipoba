import copy
import json
import unittest

from damage_lab.skillprofile import profile


def catalog(**changes):
    data = {
        "id": "synthetic-guid", "tlidbId": 90017,
        "tags": ["Spell", "Projectile", "Cold", "Activation Medium"],
        "mainStat": ["Intelligence"], "castSpeed": "0.73 s", "effectivenessOfAddedDamage": "117.5%",
        "levelProgression": [{"level": 7, "value1Min": 11, "value1Max": 19, "value2": 3},
                             {"level": 20, "value1Min": 437, "value1Max": 719, "value2": 5}],
        "descriptionBindings": {"template": "templateDescription", "level": 20,
                                "bindings": ["value1Min", "value2"]},
        "english": {"templateDescription": "Synthetic:\nDeals #-# Spell Cold Damage.\nFires # Projectiles",
                    "description": "Synthetic:\nDeals 437-719 Spell Cold Damage.\nFires 5 Projectiles"},
    }
    data.update(changes)
    return {"90017": data}


class SkillProfileTests(unittest.TestCase):
    """Extract only exact catalog-level fields without promoting them to game facts."""

    def test_exact_requested_row_requires_the_complete_reference_render(self):
        self.assertEqual(profile(catalog(), 90017, 7)["hit"], {
            "status": "catalog_render_consistent", "type": "cold", "min": "11", "max": "19", "level": 7,
            "binding": {"min": "value1Min", "max": "value1Max"}, "checkedAtLevel": 20})

    def test_wrong_full_reference_description_blocks_the_hit_binding(self):
        data = catalog()
        data["90017"]["english"]["description"] += "\nDifferent literal"
        self.assertEqual(profile(data, 90017, 7)["hit"], {"status": "render_mismatch"})

    def test_one_range_token_uses_one_min_binding_and_its_max_pair(self):
        data = catalog(descriptionBindings={"template": "templateDescription", "level": 20,
                                            "bindings": ["value1Min"]},
                       english={"templateDescription": "Deals #-# Spell Physical Damage\nFires 5 Projectiles",
                                "description": "Deals 437-719 Spell Physical Damage\nFires 5 Projectiles"})
        self.assertEqual(profile(data, 90017, 7)["hit"], {
            "status": "catalog_render_consistent", "type": "physical", "min": "11", "max": "19", "level": 7,
            "binding": {"min": "value1Min", "max": "value1Max"}, "checkedAtLevel": 20})

    def test_missing_duplicate_and_rational_rows_do_not_get_numeric_fallbacks(self):
        for rows, level, expected in (([], 7, "render_mismatch"),
                                     (catalog()["90017"]["levelProgression"], 8, "level_not_in_table"),
                                     (catalog()["90017"]["levelProgression"] * 2, 7, "render_mismatch")):
            with self.subTest(expected=expected):
                self.assertEqual(profile(catalog(levelProgression=rows), 90017, level)["hit"]["status"], expected)
        data = catalog()
        data["90017"]["levelProgression"][0]["value1Min"] = "23/2"
        self.assertEqual(profile(data, 90017, 7)["hit"]["status"], "non_integer_value")

    def test_duplicate_requested_rows_are_ambiguous(self):
        data = catalog()
        data["90017"]["levelProgression"].append(copy.deepcopy(data["90017"]["levelProgression"][0]))
        self.assertEqual(profile(data, 90017, 7)["hit"]["status"], "level_not_in_table")

    def test_malformed_template_keys_are_controlled_gaps(self):
        for key in ([], {}, 13, None):
            with self.subTest(key=key):
                data = catalog()
                data["90017"]["descriptionBindings"]["template"] = key
                self.assertEqual(profile(data, 90017, 7)["hit"], {"status": "no_binding"})

    def test_negative_and_inverted_selected_ranges_are_invalid(self):
        for low, high in ((-3, 17), (29, 17)):
            with self.subTest(low=low):
                data = catalog()
                data["90017"]["levelProgression"][0].update(value1Min=low, value1Max=high)
                self.assertEqual(profile(data, 90017, 7)["hit"], {"status": "invalid_range"})

    def test_a_self_consistent_inverted_reference_is_still_invalid(self):
        data = catalog()
        data["90017"]["levelProgression"][1].update(value1Min=719, value1Max=437)
        data["90017"]["english"]["description"] = "Synthetic:\nDeals 719-437 Spell Cold Damage.\nFires 5 Projectiles"
        self.assertEqual(profile(data, 90017, 7)["hit"], {"status": "invalid_range"})

    def test_identity_requires_strict_integer_equality(self):
        for identity in (90017.0, True, "90017", None):
            with self.subTest(identity=identity):
                self.assertEqual(profile(catalog(tlidbId=identity), 90017, 7)["identity"]["status"], "no_exact_skill")

    def test_opaque_guids_are_never_copied_to_output(self):
        result = profile(catalog(id={"account": "private-marker"}), 90017, 7)
        self.assertEqual((result["identity"]["guid"], result["identity"]["guidStatus"],
                          "private-marker" in json.dumps(result)), (None, "invalid", False))

    def test_tag_collections_distinguish_absent_invalid_and_explicit_empty(self):
        for tags, expected in ((None, "absent"), ("Spell", "invalid"), (17, "invalid"),
                               (["Spell", 13], "invalid"), (["Spell", "!!!"], "invalid"), ([], "supplied")):
            with self.subTest(tags=tags):
                self.assertEqual(profile(catalog(tags=tags), 90017, 7)["tags"]["status"], expected)

    def test_damage_types_and_path_scopes_do_not_become_skill_tags(self):
        self.assertEqual(profile(catalog(tags=["Spell", "Cold", "Elemental", "Damage", "All"]), 90017, 7)["tags"], {
            "status": "supplied", "skill": ["spell"], "damageTypes": ["cold"],
            "reserved": ["all", "damage", "elemental"], "catalog": ["Spell", "Cold", "Elemental", "Damage", "All"]})

    def test_main_stat_requires_explicit_distinct_attribute_names(self):
        for stats, expected in ((None, "absent"), ([], "supplied"), ("Intelligence", "invalid"),
                                (["Wisdom"], "invalid"), (["intelligence"], "invalid"),
                                (["Strength", "Strength"], "invalid")):
            with self.subTest(stats=stats):
                self.assertEqual(profile(catalog(mainStat=stats), 90017, 7)["mainStat"]["status"], expected)

    def test_percent_and_seconds_are_distinct_stated_catalog_fields(self):
        result = profile(catalog(), 90017, 7)
        self.assertEqual((result["effectivenessOfAddedDamage"], result["castSpeedField"]), (
            {"status": "stated", "text": "117.5%", "value": "1.175"},
            {"status": "stated", "text": "0.73 s", "seconds": "0.73"}))

    def test_unstated_fields_are_not_zero_and_malformed_units_are_invalid(self):
        for value, field, expected in ((None, "castSpeed", "not_stated"), ("", "castSpeed", "not_stated"),
                                       ("2/s", "castSpeed", "invalid"), (True, "castSpeed", "invalid")):
            with self.subTest(value=value):
                self.assertEqual(profile(catalog(**{field: value}), 90017, 7)["castSpeedField"]["status"], expected)

    def test_a_binding_count_mismatch_does_not_infer_a_missing_constant(self):
        data = catalog()
        data["90017"]["descriptionBindings"]["bindings"] = ["value1Min"]
        self.assertEqual(profile(data, 90017, 7)["hit"], {"status": "binding_count_mismatch"})

    def test_runtime_remains_unverified_and_output_does_not_alias_input(self):
        data = catalog()
        result = profile(data, 90017, 7)
        result["tags"]["catalog"].append("Changed")
        result["mainStat"]["attributes"].clear()
        self.assertEqual((data, result["runtimeVerified"], "effectiveLevel" in result), (catalog(), False, False))

    def test_request_requires_positive_integer_identity_and_level(self):
        for identity, level in ((True, 7), (90017.0, 7), (0, 7), (90017, False), (90017, 0), (90017, -1)):
            with self.subTest(identity=identity, level=level), self.assertRaises(ValueError):
                profile(catalog(), identity, level)
