import copy
import unittest

from damage_lab.supportcatalog import project, summary


def document():
    """Synthetic cache metadata with shared wrappers and fewer withheld IDs than rows."""
    rows = []
    for role, category, span in (("master", "Active", [19, 87]), ("english", "Active", [101, 211]),
                                  ("master", "Noble_Support", [241, 381])):
        path = f"skill/{category}/" + ("master" if role == "master" else "i18n/en")
        rows.append({"role": role, "category": category, "logicalPath": path,
                     "address": f"/data/SS14/{path}.json", "cacheFile": "a19e73bc52d08f46.json",
                     "wrapperSha256": "b" * 64, "member": path, "byteRange": span,
                     "memberSha256": ("c" if role == "master" else "d") * 64, "encoding": "utf-8"})
    return {"derivation": "cache_member_exact_slice", "networkBytesVerified": False,
            "currentPatchVerified": False, "identityBridges": "none_applied",
            "mappingFiles": [{"file": "needed-bundles.json", "sha256": "e" * 64, "bytes": 387},
                             {"file": "endgame-bundles.json", "sha256": "f" * 64, "bytes": 73}],
            "documents": rows,
            "categories": {"Active": {"master": "present", "english": "present"},
                           "Noble_Support": {"master": "present", "english": "missing"},
                           "Ignored_English": {"master": "missing", "english": "missing"}},
            "records": 17, "skills": 9, "invalidRecords": 2, "withheldRecords": 6,
            "reconciles": True, "recordsWithoutEnglish": 5, "withheldRecordIds": [3169, 9023, 7108]}


class SupportCatalogTests(unittest.TestCase):
    """Preserve declared local catalog metadata without turning its hashes into verified bytes."""

    def test_catalog_metadata_is_projected_with_distinct_wrapper_and_member_hashes(self):
        result = project(document())
        self.assertEqual((result["derivation"], result["network_bytes_verified"], result["current_patch_verified"],
                          result["identity_bridges"], result["mapping_files"][0], result["documents"][1],
                          result["records"], result["skills"], result["invalid_records"],
                          result["withheld_records"], result["withheld_record_ids"], result["reconciles"]),
                         ("cache_member_exact_slice", False, False, "none_applied",
                          {"file": "needed-bundles.json", "sha256": "e" * 64, "bytes": 387},
                          {"role": "english", "category": "Active", "logical_path": "skill/Active/i18n/en",
                           "address": "/data/SS14/skill/Active/i18n/en.json", "cache_file": "a19e73bc52d08f46.json",
                           "wrapper_sha256": "b" * 64, "member": "skill/Active/i18n/en", "byte_range": [101, 211],
                           "member_sha256": "d" * 64, "encoding": "utf-8"}, 17, 9, 2, 6, [3169, 9023, 7108], True))

    def test_declared_provenance_cannot_promote_byte_patch_or_identity_verification(self):
        for field, value in (("derivation", "network_response"), ("identityBridges", "automatic"),
                             ("networkBytesVerified", True), ("networkBytesVerified", 0),
                             ("currentPatchVerified", None), ("currentPatchVerified", "false"),
                             ("reconciles", 1), ("reconciles", False)):
            with self.subTest(field=field, value=value):
                raw = document()
                raw[field] = value
                with self.assertRaises(ValueError):
                    project(raw)

    def test_member_ranges_require_ordered_bounded_bytes_without_coercing_booleans(self):
        for span in (None, "19:87", (19, 87), [], [19], [19, 87, 99], [-1, 87], [87, 19], [19, 19],
                     [0, 32 * 1024 * 1024 + 1], [False, 87], [19, 87.0]):
            with self.subTest(span=span):
                raw = document()
                raw["documents"][0]["byteRange"] = span
                with self.assertRaises(ValueError):
                    project(raw)

    def test_shared_wrapper_hashes_and_member_ranges_cannot_disagree_or_overlap(self):
        for field, value in (("wrapperSha256", "a" * 64), ("byteRange", [86, 211]), ("byteRange", [19, 87])):
            with self.subTest(field=field):
                raw = document()
                raw["documents"][1][field] = value
                with self.assertRaises(ValueError):
                    project(raw)

    def test_each_document_requires_exact_skill_role_category_and_cache_coordinates(self):
        for field, value in (("role", "russian"), ("role", "english"), ("role", None),
                             ("category", "../Active"), ("category", "Active2"), ("category", "Аctive"),
                             ("category", "a" * 65), ("category", []),
                             ("logicalPath", "skill/Active/i18n/en"), ("logicalPath", "skill/../master"),
                             ("address", "https://invalid.test/catalog.json"), ("address", None),
                             ("member", "skill/Noble_Support/master"), ("cacheFile", "../a19e73bc52d08f46.json"),
                             ("cacheFile", "A19e73bc52d08f46.json"), ("wrapperSha256", "wrong"),
                             ("memberSha256", None), ("encoding", "utf-16")):
            with self.subTest(field=field, value=value):
                raw = document()
                raw["documents"][0][field] = value
                with self.assertRaises(ValueError):
                    project(raw)
        for row in (None, [], {}, document()["documents"][0]):
            with self.subTest(row=row):
                raw = document()
                raw["documents"].append(row)
                with self.assertRaises(ValueError):
                    project(raw)

    def test_metadata_requires_bounded_json_collections_and_named_objects(self):
        for field, value in (("mappingFiles", None), ("mappingFiles", {}), ("mappingFiles", []),
                             ("mappingFiles", document()["mappingFiles"] * 2), ("documents", None),
                             ("documents", {}), ("documents", []), ("documents", document()["documents"] * 22),
                             ("categories", []), ("categories", None), ("categories", {}),
                             ("categories", {"Category" + "_" * index: {"master": "missing", "english": "missing"}
                                             for index in range(129)}),
                             ("withheldRecordIds", None), ("withheldRecordIds", "3169")):
            with self.subTest(field=field):
                raw = document()
                raw[field] = value
                with self.assertRaises(ValueError):
                    project(raw)
        for raw in (None, [], {}, {"PRIVATE-CATALOG-CANARY": 17}):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                project(raw)

    def test_mapping_files_require_unique_fixed_names_hashes_and_bounded_byte_counts(self):
        for field, value in (("file", "../needed-bundles.json"), ("file", "other.json"),
                             ("sha256", "A" * 64), ("sha256", "a" * 63), ("sha256", None),
                             ("bytes", True), ("bytes", 0), ("bytes", -1), ("bytes", 1.5),
                             ("bytes", "387"), ("bytes", 32 * 1024 * 1024 + 1)):
            with self.subTest(field=field, value=value):
                raw = document()
                raw["mappingFiles"][0][field] = value
                with self.assertRaises(ValueError):
                    project(raw)

    def test_category_presence_requires_exact_roles_for_every_loaded_document(self):
        for category, value in (("Active", {"master": "present", "english": "missing"}),
                                ("Noble_Support", {"master": "present", "english": "present"}),
                                ("Ignored_English", {"master": "present", "english": "missing"}),
                                ("Active", {"master": True, "english": "present"}),
                                ("Active", {"master": "present", "english": []}), ("Active", None),
                                ("Active", {}), ("../private", {"master": "missing", "english": "missing"})):
            with self.subTest(category=category, value=value):
                raw = document()
                raw["categories"][category] = value
                with self.assertRaises(ValueError):
                    project(raw)
        raw = document()
        del raw["categories"]["Active"]
        with self.assertRaises(ValueError):
            project(raw)

    def test_loaded_english_requires_its_category_master_and_at_least_one_master(self):
        raw = document()
        raw["documents"] = [raw["documents"][1]]
        raw["categories"] = {"Active": {"master": "missing", "english": "present"}}
        with self.assertRaises(ValueError):
            project(raw)

    def test_catalog_accounting_requires_exact_nonnegative_integer_counts_and_row_conservation(self):
        for field in ("records", "skills", "invalidRecords", "withheldRecords", "recordsWithoutEnglish"):
            for value in (True, None, "17", -1, 1.5):
                with self.subTest(field=field, value=value):
                    raw = document()
                    raw[field] = value
                    with self.assertRaises(ValueError):
                        project(raw)
        for field, value in (("records", 18), ("skills", 8), ("invalidRecords", 3),
                             ("withheldRecords", 5), ("recordsWithoutEnglish", 16)):
            with self.subTest(field=field):
                raw = document()
                raw[field] = value
                with self.assertRaises(ValueError):
                    project(raw)

    def test_withheld_identities_are_unique_positive_integers_and_cannot_outnumber_withheld_rows(self):
        for identities in ([], [3169, 3169], [True], [0], [-7], [3169.0], ["3169"], [{}], list(range(1, 8))):
            with self.subTest(identities=identities):
                raw = document()
                raw["withheldRecordIds"] = identities
                with self.assertRaises(ValueError):
                    project(raw)

    def test_unknown_properties_are_removed_at_every_metadata_level(self):
        raw = document()
        raw["opaque"] = {"PRIVATE-CATALOG-CANARY"}
        raw["mappingFiles"][0]["rawBytes"] = "PRIVATE-CATALOG-CANARY"
        raw["documents"][0]["rawText"] = {"PRIVATE-CATALOG-CANARY"}
        raw["categories"]["Active"]["private"] = "PRIVATE-CATALOG-CANARY"
        result = project(raw)
        result["opaque"] = "PRIVATE-CATALOG-CANARY"
        result["documents"][0]["raw_text"] = "PRIVATE-CATALOG-CANARY"
        self.assertEqual(summary(result), project(document()))

    def test_project_and_summary_results_do_not_share_nested_mutable_metadata(self):
        raw = document()
        original = copy.deepcopy(raw)
        projected = project(raw)
        canonical = summary(projected)
        canonical["documents"][0]["byte_range"][0] = 1
        canonical["mapping_files"][0]["bytes"] = 1
        canonical["categories"]["Active"]["english"] = "missing"
        canonical["withheld_record_ids"].append(9917)
        self.assertEqual((raw, projected), (original, project(original)))

    def test_summary_revalidates_canonical_claims_paths_and_accounting(self):
        for path, value in ((("current_patch_verified",), True), (("records",), 23),
                            (("documents", 0, "member"), "PRIVATE-CATALOG-CANARY"),
                            (("documents", 1, "wrapper_sha256"), "a" * 64),
                            (("mapping_files", 0, "file"), "../private.json"),
                            (("categories", "Active", "english"), "missing"),
                            (("withheld_record_ids",), [True])):
            with self.subTest(path=path):
                canonical = project(document())
                node = canonical
                for field in path[:-1]:
                    node = node[field]
                node[path[-1]] = value
                with self.assertRaises(ValueError):
                    summary(canonical)

    def test_optional_endgame_mapping_adjacent_members_and_unloaded_categories_remain_diagnostic(self):
        raw = document()
        raw["mappingFiles"] = raw["mappingFiles"][:1]
        raw["documents"][1]["byteRange"][0] = 87
        result = project(raw)
        self.assertEqual((len(result["mapping_files"]), result["documents"][1]["byte_range"],
                          result["categories"]["Ignored_English"], summary(result)),
                         (1, [87, 211], {"master": "missing", "english": "missing"}, result))

    def test_empty_master_records_preserve_known_zero_counts_without_fabricating_skills(self):
        raw = document()
        raw.update(records=0, skills=0, invalidRecords=0, withheldRecords=0, recordsWithoutEnglish=0, withheldRecordIds=[])
        result = project(raw)
        self.assertEqual((result["records"], result["skills"], result["withheld_record_ids"], result["reconciles"]),
                         (0, 0, [], True))

    def test_supported_collection_and_byte_limits_include_their_exact_upper_boundaries(self):
        raw = document()
        prototype = raw["documents"][0]
        raw["documents"], raw["categories"] = [], {}
        for index in range(64):
            category = "Category" + chr(65 + index // 26) + chr(65 + index % 26)
            path = f"skill/{category}/master"
            raw["documents"].append({**prototype, "category": category, "logicalPath": path, "member": path,
                                     "address": f"/data/SS14/{path}.json", "byteRange": [index * 17, index * 17 + 11]})
            raw["categories"][category] = {"master": "present", "english": "missing"}
            raw["categories"][category + "Orphan"] = {"master": "missing", "english": "missing"}
        raw["documents"][-1]["byteRange"] = [32 * 1024 * 1024 - 3, 32 * 1024 * 1024]
        raw["mappingFiles"][0]["bytes"] = 32 * 1024 * 1024
        raw.update(records=0, skills=0, invalidRecords=0, withheldRecords=0, recordsWithoutEnglish=0, withheldRecordIds=[])
        result = project(raw)
        self.assertEqual((len(result["documents"]), len(result["categories"]), result["mapping_files"][0]["bytes"],
                          result["documents"][-1]["byte_range"][-1]), (64, 128, 32 * 1024 * 1024, 32 * 1024 * 1024))

    def test_one_valid_withheld_row_can_share_its_identity_with_an_invalid_peer(self):
        raw = document()
        raw.update(records=11, invalidRecords=1, withheldRecords=1, withheldRecordIds=[3169])
        result = project(raw)
        self.assertEqual((result["records"], result["skills"], result["invalid_records"],
                          result["withheld_records"], result["withheld_record_ids"]), (11, 9, 1, 1, [3169]))

    def test_missing_named_fields_cannot_be_recovered_from_unknown_aliases(self):
        canonical = project(document())
        for field in tuple(canonical):
            with self.subTest(field=field):
                altered = copy.deepcopy(canonical)
                altered.pop(field)
                altered["PRIVATE-CATALOG-CANARY"] = 17
                with self.assertRaises(ValueError):
                    summary(altered)

    def test_errors_are_fixed_single_sentences_without_private_coordinates(self):
        errors = []
        for path in (("derivation",), ("documents", 0, "address"), ("mappingFiles", 0, "file")):
            raw = document()
            node = raw
            for field in path[:-1]:
                node = node[field]
            node[path[-1]] = "PRIVATE-CATALOG-CANARY"
            with self.assertRaises(ValueError) as caught:
                project(raw)
            errors.append(("PRIVATE-CATALOG-CANARY" in str(caught.exception), "\n" in str(caught.exception),
                           str(caught.exception).endswith(".")))
        self.assertEqual(errors, [(False, False, False)] * 3)
        for rows in ([document()["mappingFiles"][1]], [document()["mappingFiles"][0]] * 2, [None], [{}]):
            with self.subTest(rows=rows):
                raw = document()
                raw["mappingFiles"] = rows
                with self.assertRaises(ValueError):
                    project(raw)
