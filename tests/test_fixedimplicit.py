"""Validate a fictional fixed implicit proof without authenticating catalog bytes."""

import copy
import unittest
from decimal import localcontext

from damage_lab.fixedimplicit import project, summary


def document():
    """Keep synthetic own rolls distinct from the fixed master and English statements."""
    return {
        "kind": "fixed_base_implicit", "binding": "exact_item_guid_and_native_id", "modifierId": "520020",
        "master": {"catalog": "gear/one_handed/wand/master", "sha256": "b" * 64,
                   "itemGuid": "synthetic-wand", "tlidbId": "9137",
                   "spec": {"minExact": "37.125", "maxExact": "37.1250", "sign": "+", "unit": "%"}},
        "english": {"catalog": "gear/one_handed/wand/i18n/en", "sha256": "c" * 64,
                    "itemGuid": "synthetic-wand", "rawText": "+37.125% Spell Damage",
                    "numberExact": "37.125", "phrase": "% Spell Damage"},
        "ownValue": {"exact": "37.12500", "source": "DynArgs[0]"},
        "equality": "own_value_equals_min_equals_max_equals_raw_text_number", "registryTemplate": "+#% Spell Damage",
        "poolIdentity": "unresolved", "runtimeVerified": False, "arithmeticReady": False}


class FixedImplicitTests(unittest.TestCase):
    """Keep fixed spell-damage evidence exact while all pooling and runtime claims stay unverified."""

    def test_own_and_catalog_lexemes_remain_separate_in_a_revalidated_proof(self):
        result = summary(project(document()))
        self.assertEqual((result["modifier_id"], result["own_value"], result["master"]["spec"], result["pool_identity"]),
                         ("520020", {"exact": "37.12500", "source": "DynArgs[0]"},
                          {"min_exact": "37.125", "max_exact": "37.1250", "sign": "+", "unit": "%"}, "unresolved"))

    def test_exact_comparisons_are_independent_of_precision_exponents_and_traps(self):
        with localcontext() as context:
            context.prec = 1
            context.Emax = 0
            context.Emin = 0
            for signal in context.traps:
                context.traps[signal] = True
            result = summary(project(document()))
        self.assertEqual(result["own_value"]["exact"], "37.12500")

    def test_a_fixed_spec_cannot_disagree_with_its_own_value_or_english_number(self):
        for path, invalid in ((("master", "spec", "minExact"), "37.124"),
                               (("master", "spec", "maxExact"), "37.126"),
                               (("ownValue", "exact"), "37.126"), (("english", "numberExact"), "37.126")):
            with self.subTest(path=path):
                data = document()
                node = data
                for field in path[:-1]:
                    node = node[field]
                node[path[-1]] = invalid
                with self.assertRaisesRegex(ValueError, "^Fixed implicit contains an invalid catalog proof$"):
                    project(data)

    def test_the_whole_english_phrase_cannot_be_fuzzy_or_contain_an_extra_condition(self):
        for text in ("37.125% Spell Damage", "+37.125 % Spell Damage", "+37.125% Attack Damage",
                     "+37.125% spell damage", "+37.125% Spell Damage\n", "+37.125% Spell Damage per 9 Intelligence",
                     "+٣٧.١٢٥% Spell Damage"):
            with self.subTest(text=text):
                data = document()
                data["english"]["rawText"] = text
                with self.assertRaises(ValueError):
                    project(data)

    def test_the_registry_requires_exact_paths_full_modifier_identity_and_semantics(self):
        for path, invalid in ((("modifierId",), "5200200"), (("modifierId",), 520020),
                               (("binding",), "native_prefix"), (("kind",), "gear_entry"),
                               (("registryTemplate",), "+#% Attack Damage"), (("poolIdentity",), "exact"),
                               (("master", "catalog"), "gear/one_handed/staff/master"),
                               (("english", "catalog"), "gear/one_handed/staff/i18n/en"),
                               (("english", "phrase"), "% Spell Damage per 9 Intelligence"),
                               (("equality",), "approximately_equal"), (("ownValue", "source"), "DynArgs[1]"),
                               (("master", "spec", "sign"), "-"), (("master", "spec", "unit"), "flat")):
            with self.subTest(path=path):
                data = document()
                node = data
                for field in path[:-1]:
                    node = node[field]
                node[path[-1]] = invalid
                with self.assertRaises(ValueError):
                    project(data)

    def test_item_guids_public_ids_and_member_hashes_are_strict_and_bounded(self):
        for block, field, invalid in (("english", "itemGuid", "other-wand"), ("master", "itemGuid", "invalid guid"),
                                      ("master", "tlidbId", 9137), ("master", "tlidbId", "0"),
                                      ("master", "tlidbId", "1" * 21), ("english", "sha256", "C" * 64),
                                      ("master", "sha256", {"account": "PRIVATE-FIXED-CANARY"})):
            with self.subTest(block=block, field=field):
                data = document()
                data[block][field] = invalid
                with self.assertRaisesRegex(ValueError, "^Fixed implicit contains an invalid catalog proof$"):
                    project(data)

    def test_only_bounded_exact_ascii_decimal_strings_are_accepted(self):
        for invalid in (True, 37, 37.125, None, [], {}, "NaN", "Infinity", "1e9", "1/8", " 37.125",
                        "1" * 13, "0.1234567890", "٣٧.١٢٥"):
            with self.subTest(invalid=invalid):
                data = document()
                data["ownValue"]["exact"] = invalid
                with self.assertRaises(ValueError):
                    project(data)

    def test_the_full_supported_decimal_boundary_roundtrips_without_rounding(self):
        data = document()
        for row, field in ((data["master"]["spec"], "minExact"), (data["master"]["spec"], "maxExact"),
                           (data["english"], "numberExact"), (data["ownValue"], "exact")):
            row[field] = "123456789012.123456789"
        data["english"]["rawText"] = "+123456789012.123456789% Spell Damage"
        self.assertEqual(summary(project(data))["own_value"]["exact"], "123456789012.123456789")

    def test_lexically_signed_zero_can_match_an_explicit_positive_zero_text(self):
        data = document()
        data["master"]["spec"].update(minExact="-0.0", maxExact="0")
        data["ownValue"]["exact"] = "-0"
        data["english"].update(numberExact="0.00", rawText="+0.00% Spell Damage")
        self.assertEqual(summary(project(data))["own_value"]["exact"], "-0")

    def test_runtime_and_arithmetic_claims_are_literal_false(self):
        for field in ("runtimeVerified", "arithmeticReady"):
            for invalid in (0, True, None):
                with self.subTest(field=field, invalid=invalid):
                    data = document()
                    data[field] = invalid
                    with self.assertRaises(ValueError):
                        project(data)

    def test_canonical_numbers_and_fixed_claims_are_revalidated(self):
        for block, field, invalid in (("master", "tlidb_id", True), ("own_value", "source", "DynArgs[true]"),
                                      ("english", "number_exact", "37.124"), ("master", "sha256", None)):
            with self.subTest(block=block, field=field):
                data = project(document())
                data[block][field] = invalid
                with self.assertRaises(ValueError):
                    summary(data)

    def test_unknown_private_properties_are_dropped_at_every_object_depth(self):
        expected = project(document())
        data = document()
        for row in (data, data["master"], data["english"], data["master"]["spec"], data["ownValue"]):
            row["opaque"] = {"account": "PRIVATE-FIXED-CANARY"}
        normalized = project(data)
        for row in (normalized, normalized["master"], normalized["english"], normalized["master"]["spec"], normalized["own_value"]):
            row["opaque"] = {"account": "PRIVATE-FIXED-CANARY"}
        self.assertEqual(summary(normalized), expected)

    def test_raw_and_canonical_inputs_are_not_aliased_or_mutated(self):
        data = document()
        before = copy.deepcopy(data)
        result = project(data)
        normalized = summary(result)
        normalized["master"]["spec"]["min_exact"] = "changed"
        self.assertEqual((data, result["master"]["spec"]["min_exact"]), (before, "37.125"))

    def test_malformed_shapes_fail_without_echoing_private_payloads(self):
        for invalid in (None, [], True, {"opaque": "PRIVATE-FIXED-CANARY"}):
            with self.subTest(invalid=invalid), self.assertRaisesRegex(ValueError, "^Fixed implicit contains an invalid catalog proof$"):
                project(invalid)

    def test_invalid_utf8_oversized_text_containers_and_numbers_fail_before_projection(self):
        for invalid in ("\ud800", "x" * 4097, [None] * 4097, 10 ** 20, float("nan")):
            with self.subTest(invalid=type(invalid).__name__):
                data = document()
                data["opaque"] = invalid
                with self.assertRaises(ValueError):
                    project(data)

    def test_repeated_containers_and_cycles_are_not_treated_as_independent_proof(self):
        for cycle in (False, True):
            with self.subTest(cycle=cycle):
                data = document()
                data["opaque"] = data if cycle else data["ownValue"]
                with self.assertRaises(ValueError):
                    project(data)

    def test_depth_and_total_node_budgets_are_enforced(self):
        for shape in ("depth", "nodes"):
            with self.subTest(shape=shape):
                data = document()
                node = []
                if shape == "depth":
                    for _ in range(33):
                        node = [node]
                else:
                    node = [[None] * 4096 for _ in range(3)]
                data["opaque"] = node
                with self.assertRaises(ValueError):
                    project(data)
