import unittest

from damage_lab.logcatalog import project
from test_logbuild import reference_document
from test_supportcatalog import document as metadata


def document(identity="9001"):
    """Print fictional skill levels with deliberately distinct meanings."""
    return reference_document([("1", [("BaseId", identity), ("Level", "17"), ("SkillItemLevel", "23")])], None)


def records():
    """Declare one exact catalog identity without level or descriptive payload."""
    return {"9001": {"tlidbId": 9001, "id": "synthetic-spell", "category": "Active", "catalogPath": "skill/Active"}}


class LogCatalogTests(unittest.TestCase):
    """Bind printed catalog IDs while retaining uncertain levels and installation."""

    def test_exact_catalog_candidate_preserves_two_levels_without_selecting_either(self):
        result = project(document(), 0, "a" * 64, records(), metadata())
        self.assertEqual([row["identity"] for row in result["rows"]],
                         [{"tlidb_id": 9001, "guid": "synthetic-spell", "category": "Active"}])

    def test_distinct_printed_levels_remain_lexical_and_all_inferences_unknown(self):
        result = project(document(), 0, "a" * 64, records(), metadata())
        row = result["rows"][0]
        self.assertEqual((row["fields"]["level"]["values"][0]["text"],
                          row["fields"]["skill_item_level"]["values"][0]["text"],
                          row["profile"], row["gem_level"], row["effective_level"],
                          result["identity"], result["runtime"], result["activation"], result["installation"],
                          result["import_complete"], result["arithmetic_ready"], result["level_specific_lookup"]),
                         ("17", "23", None, None, None, "unknown", "unknown", "unknown", "unknown", False, False, False))

    def test_duplicate_catalog_ids_do_not_merge_rows_or_source_aliases(self):
        data = reference_document([("1", [("BaseId", "9001")]), ("2", [("BaseId", "9001")])], None)
        result = project(data, 0, "a" * 64, records(), metadata())
        self.assertEqual([(row["alias"], row["path"], row["identity"]["tlidb_id"]) for row in result["rows"]],
                         [("skill_items[0]", ["skills", "skills", "1"], 9001),
                          ("skill_items[1]", ["skills", "skills", "2"], 9001)])

    def test_noncanonical_or_float_ids_never_normalize_into_catalog_keys(self):
        results = [project(document(value), 0, "a" * 64, records(), metadata())["rows"][0]
                   for value in ("9001.0", "09001", "-9001", "0")]
        self.assertEqual([(row["identity"], row["reason"]) for row in results],
                         [(None, "base_id_noncanonical")] * 4)

    def test_missing_records_and_unprinted_ids_remain_explicit_gaps(self):
        missing = project(document(), 0, "a" * 64, {}, metadata())["rows"][0]
        data = reference_document([("1", [("Level", "17")])], None)
        unprinted = project(data, 0, "a" * 64, records(), metadata())["rows"][0]
        self.assertEqual((missing["reason"], unprinted["reason"], missing["identity"], unprinted["identity"]),
                         ("catalog_record_missing", "base_id_unavailable", None, None))

    def test_record_identity_category_withheld_and_path_disagreements_refuse(self):
        for field, value in (("tlidbId", 9002), ("tlidbId", True), ("category", "Ignored_English"),
                             ("catalogPath", "skill/Support")):
            supplied = records()
            supplied["9001"][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                project(document(), 0, "a" * 64, supplied, metadata())
        declared = metadata()
        declared["withheldRecordIds"].append(9001)
        with self.assertRaisesRegex(ValueError, "withheld"):
            project(document(), 0, "a" * 64, records(), declared)

    def test_raw_provenance_cannot_promote_verification_flags(self):
        for field in ("networkBytesVerified", "currentPatchVerified"):
            declared = metadata()
            declared[field] = True
            with self.subTest(field=field), self.assertRaises(ValueError):
                project(document(), 0, "a" * 64, records(), declared)
        data = document()
        data["identity"] = "confirmed"
        with self.assertRaises(ValueError):
            project(data, 0, "a" * 64, records(), metadata())

    def test_partial_mode_requires_its_separate_fingerprint_and_keeps_hidden_inventory(self):
        from test_logbuild import partial_document

        data = partial_document()
        result = project(data, 0, "a" * 64, records(), metadata(), partial=True)
        self.assertEqual((result["coverage"]["status"], result["coverage"]["total_entries"],
                          result["structure"]["kind"], result["rows"][0]["path"]),
                         ("complete", None, "bag_elided_character_shape", ["skills", "skills", "1"]))
        with self.assertRaises(ValueError):
            project(data, 0, "a" * 64, records(), metadata())
        with self.assertRaises(ValueError):
            project(document(), 0, "a" * 64, records(), metadata(), partial=True)
        with self.assertRaises(ValueError):
            project(document(), 0, "a" * 64, records(), metadata(), partial=1)

    def test_opaque_record_payload_is_discarded_and_results_are_detached(self):
        supplied = records()
        supplied["9001"]["description"] = "PRIVATE-CANARY"
        result = project(document(), 0, "a" * 64, supplied, metadata())
        import json
        self.assertEqual(("PRIVATE-CANARY" in json.dumps(result), result["rows"][0]["alias"]),
                         (False, "skill_items[0]"))
        result["rows"][0]["identity"]["guid"] = "changed"
        self.assertEqual(supplied["9001"]["id"], "synthetic-spell")

    def test_absent_withheld_identity_is_distinct_from_an_ordinary_missing_record(self):
        declared = metadata()
        declared["withheldRecordIds"].append(9001)
        row = project(document(), 0, "a" * 64, {}, declared)["rows"][0]
        self.assertEqual((row["identity"], row["reason"]), (None, "withheld_identity"))

    def test_total_catalog_keys_are_bounded_even_when_all_records_are_null(self):
        supplied = {str(index + 1): None for index in range(metadata()["records"] + 1)}
        with self.assertRaisesRegex(ValueError, "bounded"):
            project(document(), 0, "a" * 64, supplied, metadata())

    def test_elided_inventory_retains_unknown_total_and_separate_visible_rows(self):
        from test_logtables import ELIDED

        items = [(str(index + 1), [("BaseId", "9001")]) for index in range(30)] + [("31", ELIDED)]
        result = project(reference_document(items, None), 0, "a" * 64, records(), metadata())
        self.assertEqual((result["coverage"]["status"], result["coverage"]["visible_entries"],
                          result["coverage"]["total_entries"], result["counts"]["rows"]),
                         ("elided", 30, None, 30))
