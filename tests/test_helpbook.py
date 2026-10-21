import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from damage_lab.helpbook import merge, search


def index():
    return {"format": "tli-help-index-v1", "patch": "synthetic", "checkedAt": "2026-01-13",
            "sourceClassification": "unofficial-game-help-datamine-mirror",
            "index": {"url": "https://tlidb.com/en/Help", "advertisedCounts": {"Help": 2, "Help_Handbook": 1},
                      "actualCounts": {"Help": 2, "Help_Handbook": 1}, "entryCount": 3, "uniqueCount": 2,
                      "verifiedAt": "2026-01-13", "categoryBasis": "Synthetic memberships"},
            "articles": [{"url": "https://tlidb.com/en/Synthetic_Drop", "title": "Synthetic Drop",
                          "categories": ["Help", "Help_Handbook"], "memberships": [
                              {"section": "Help", "position": 1, "title": "Synthetic Drop"},
                              {"section": "Help_Handbook", "position": 1, "title": "Synthetic Drop"}],
                          "status": "index_discovered", "checkedAt": None,
                          "sourceClassification": "game-help-text-mirror", "findings": [], "unknowns": []},
                         {"url": "https://tlidb.com/en/Synthetic_Cast", "title": "Synthetic Cast",
                          "categories": ["Help"], "memberships": [{"section": "Help", "position": 2, "title": "Synthetic Cast"}],
                          "status": "index_discovered", "checkedAt": None,
                          "sourceClassification": "game-help-text-mirror", "findings": [], "unknowns": []}]}


def chunk():
    return {"format": "tli-help-review-chunk-v1", "checkedAt": "2026-01-17",
            "articles": [{"url": "https://tlidb.com/en/Synthetic_Drop", "title": "Synthetic Drop",
                          "status": "body_reviewed", "checkedAt": "2026-01-17", "summary": "Synthetic drop rule",
                          "findings": ["Independent pools"], "unknowns": ["Version unverified"],
                          "formulas": [{"expression": "loot = 7 * pools", "domain": "Synthetic only",
                                        "assumptions": ["No real game rule"], "status": "derived"}]}]}


class HelpbookTest(unittest.TestCase):
    """Offline Help keeps review evidence separate from index discovery."""

    def test_merging_one_review_preserves_memberships_and_counts_unique_articles(self):
        result = merge(index(), [chunk()])
        self.assertEqual((len(result["articles"][0]["memberships"]), result["reviewCoverage"]["byStatus"]),
                         (2, {"index_discovered": 1, "blocked": 0, "body_reviewed": 1}))

    def test_declared_counts_must_match_actual_memberships(self):
        for key in ("advertisedCounts", "actualCounts"):
            with self.subTest(key=key):
                data = index()
                data["index"][key]["Help"] = 3
                with self.assertRaises(ValueError):
                    merge(data, [])

    def test_two_urls_cannot_claim_the_same_section_position(self):
        data = index()
        data["articles"][1]["memberships"][0]["position"] = 1
        with self.assertRaises(ValueError):
            merge(data, [])

    def test_reviews_cannot_introduce_urls_absent_from_the_index(self):
        review = chunk()
        review["articles"][0]["url"] = "https://tlidb.com/en/Synthetic_Unknown"
        with self.assertRaises(ValueError):
            merge(index(), [review])

    def test_successful_body_review_is_stronger_than_a_later_blocked_attempt(self):
        blocked = chunk()
        blocked["articles"][0].update(status="blocked", summary="Synthetic access denied")
        self.assertEqual(merge(index(), [chunk(), blocked])["articles"][0]["status"], "body_reviewed")

    def test_repeated_reviews_keep_all_findings_in_history_and_mark_variants(self):
        other = chunk()
        other["articles"][0].update(summary="Different synthetic interpretation", findings=["Separate rolls"])
        result = merge(index(), [chunk(), other])["articles"][0]
        self.assertEqual(({value for row in result["reviewHistory"] for value in row["findings"]},
                          len(result["reviewHistory"]), {"summary", "findings"}.issubset(result["reviewConflicts"])),
                         ({"Independent pools", "Separate rolls"}, 2, True))

    def test_unknown_service_payloads_are_discarded_at_every_depth(self):
        data, review = index(), chunk()
        for row in (data, data["index"], data["articles"][0], data["articles"][0]["memberships"][0],
                    review, review["articles"][0], review["articles"][0]["formulas"][0]):
            row["service"] = {"account": "private-canary"}
        self.assertNotIn("private-canary", json.dumps(merge(data, [review])))

    def test_malformed_reviews_cannot_claim_body_coverage(self):
        for key, value in (("status", "index_discovered"), ("checkedAt", None),
                           ("findings", [{"raw": "nested"}]), ("sourceClassification", "official")):
            with self.subTest(key=key):
                review = chunk()
                review["articles"][0][key] = value
                with self.assertRaises(ValueError):
                    merge(index(), [review])

    def test_section_coverage_counts_memberships_without_duplicating_article_totals(self):
        result = merge(index(), [chunk()])["reviewCoverage"]
        self.assertEqual((result["uniqueCount"], result["entryCount"],
                          result["bySection"]["Help_Handbook"]["byStatus"]["body_reviewed"]), (2, 3, 1))

    def test_saved_review_history_cannot_be_attached_to_another_url(self):
        data = merge(index(), [chunk()])
        data["articles"][0]["reviewHistory"][0]["url"] = data["articles"][1]["url"]
        with self.assertRaises(ValueError):
            merge(data, [])

    def test_search_finds_formula_text_without_executing_it(self):
        self.assertEqual([row["title"] for row in search(merge(index(), [chunk()]), "LOOT = 7")], ["Synthetic Drop"])

    def test_cli_merge_writes_a_new_json_file(self):
        with tempfile.TemporaryDirectory() as folder:
            source, review, output = [Path(folder) / name for name in ("index.json", "review.json", "merged.json")]
            source.write_text(json.dumps(index()), encoding="utf-8")
            review.write_text(json.dumps(chunk()), encoding="utf-8")
            process = subprocess.run([sys.executable, "-X", "utf8", "-m", "damage_lab.helpbook", "merge",
                                      "--index", str(source), "--review", str(review), "--output", str(output)],
                                     cwd=Path(__file__).resolve().parents[1], capture_output=True, text=True, encoding="utf-8", timeout=10)
            self.assertEqual((process.returncode, json.loads(output.read_text(encoding="utf-8"))["reviewCoverage"]["byStatus"]["body_reviewed"]), (0, 1))

    def test_cli_search_returns_safe_json_results(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / "index.json"
            source.write_text(json.dumps(index()), encoding="utf-8")
            process = subprocess.run([sys.executable, "-X", "utf8", "-m", "damage_lab.helpbook", "search", "drop", "--index", str(source)],
                                     cwd=Path(__file__).resolve().parents[1], capture_output=True, text=True, encoding="utf-8", timeout=10)
            self.assertEqual((process.returncode, [row["title"] for row in json.loads(process.stdout)]), (0, ["Synthetic Drop"]))

    def test_zero_count_sections_remain_valid_empty_library_sections(self):
        data = index()
        data["articles"] = []
        data["index"].update(advertisedCounts={"Help": 0, "Help_Handbook": 0}, actualCounts={"Help": 0, "Help_Handbook": 0},
                             entryCount=0, uniqueCount=0)
        self.assertEqual(merge(data, [])["reviewCoverage"]["uniqueCount"], 0)

    def test_search_also_finds_a_preserved_alternative_review_summary(self):
        other = chunk()
        other["articles"][0]["summary"] = "Zebra alternative interpretation"
        self.assertEqual(len(search(merge(index(), [chunk(), other]), "Zebra")), 1)

    def test_saved_history_status_must_match_the_article_claim(self):
        data = merge(index(), [chunk()])
        data["articles"][0]["status"] = "blocked"
        with self.assertRaises(ValueError):
            merge(data, [])

    def test_changed_review_titles_are_visible_as_variants(self):
        review = chunk()
        review["articles"][0]["title"] = "Changed synthetic title"
        self.assertIn("title", merge(index(), [review])["articles"][0]["reviewConflicts"])

    def test_remerging_identical_evidence_is_idempotent(self):
        result = merge(index(), [chunk()])
        self.assertEqual(merge(result, [chunk()]), result)

    def test_mixed_source_classifications_do_not_grow_history_on_repeat(self):
        reviewed, blocked = chunk(), chunk()
        reviewed["articles"][0]["sourceClassification"] = "unofficial-game-help-datamine-mirror"
        blocked["articles"][0].update(status="blocked", summary="Synthetic blocked attempt")
        result = merge(index(), [reviewed, blocked])
        self.assertEqual(merge(result, [reviewed, blocked]), result)

    def test_compact_card_keeps_one_complete_review_within_its_word_budget(self):
        alpha, zeta = chunk(), chunk()
        for review, name in ((alpha, "Alpha"), (zeta, "Zeta")):
            review["articles"][0].update(summary=name + " synthetic overview", findings=[" ".join([name] * 67)])
        result = merge(index(), [zeta, alpha])["articles"][0]
        self.assertTrue(len((result["summary"] + " " + " ".join(result["findings"])).split()) <= 80
                        and any((result["summary"], result["findings"]) == (row["summary"], row["findings"])
                                for row in result["reviewHistory"]))

    def test_search_finds_findings_outside_the_compact_card(self):
        alpha, zeta = chunk(), chunk()
        alpha["articles"][0].update(summary="Alpha view", findings=["Alpha-only evidence"])
        zeta["articles"][0].update(summary="Zeta view", findings=["Zeta-only evidence"])
        result = merge(index(), [alpha, zeta])
        self.assertEqual(len(search(result, "Zeta-only evidence")), 1)

    def test_project_version_scope_and_limits_survive_safe_projection(self):
        data = index()
        data.update(versionScope="Synthetic SS14 project scope, not release proof",
                    limits=["Synthetic mirror only", "Formulas are not executed"])
        result = merge(data, [chunk()])
        self.assertEqual((result["versionScope"], result["limits"]),
                         ("Synthetic SS14 project scope, not release proof", ["Synthetic mirror only", "Formulas are not executed"]))

    def test_incremental_and_batch_merges_have_identical_field_order(self):
        zeta, alpha = chunk(), chunk()
        for review, name in ((zeta, "Zeta"), (alpha, "Alpha")):
            row = review["articles"][0]
            row.update(summary=name, findings=[name + " observation"], unknowns=[name + " gap"])
            row["formulas"][0].update(expression=name + " = 7", assumptions=[name + " premise"])
        self.assertEqual(merge(merge(index(), [zeta]), [alpha]), merge(index(), [zeta, alpha]))

    def test_version_scope_and_limits_require_safe_known_types(self):
        for key, value in (("versionScope", {"raw": "private-canary"}), ("versionScope", True),
                           ("limits", "not a list"), ("limits", [{"raw": "private-canary"}])):
            with self.subTest(key=key, value=value):
                data = index()
                data[key] = value
                with self.assertRaises(ValueError):
                    merge(data, [])

    def test_preserved_limits_are_detached_from_the_source(self):
        data = index()
        data["limits"] = ["Synthetic mirror warning"]
        result = merge(data, [])
        result["limits"].append("Synthetic edit")
        self.assertEqual(data["limits"], ["Synthetic mirror warning"])

    def test_formulas_with_conflicting_assumptions_remain_separate(self):
        other = chunk()
        other["articles"][0]["formulas"][0]["assumptions"] = ["Different synthetic premise"]
        result = merge(index(), [chunk(), other])["articles"][0]
        self.assertEqual((len(result["formulas"]), "formula:loot = 7 * pools" in result["reviewConflicts"]), (2, True))

    def test_discovery_alone_never_claims_reviewed_bodies(self):
        self.assertEqual(merge(index(), [])["reviewCoverage"]["byStatus"]["body_reviewed"], 0)

    def test_query_must_be_nonempty_text(self):
        for value in ("", "  ", None, [], True):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    search(index(), value)

    def test_bad_json_shapes_fail_as_contract_errors(self):
        for value in (None, [], True, "index"):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    merge(value, [])

    def test_counts_cannot_be_booleans(self):
        data = index()
        data["index"]["actualCounts"]["Help_Handbook"] = True
        with self.assertRaises(ValueError):
            merge(data, [])

    def test_source_projection_is_detached_from_inputs(self):
        data, review = index(), chunk()
        original = copy.deepcopy((data, review))
        result = merge(data, [review])
        result["articles"][0]["reviewHistory"][0]["formulas"][0]["assumptions"].append("Synthetic edit")
        self.assertEqual((data, review), original)

    def test_cli_merge_cannot_overwrite_an_existing_file(self):
        with tempfile.TemporaryDirectory() as folder:
            source, review, output = [Path(folder) / name for name in ("index.json", "review.json", "merged.json")]
            source.write_text(json.dumps(index()), encoding="utf-8")
            review.write_text(json.dumps(chunk()), encoding="utf-8")
            output.write_text("preserve synthetic artifact", encoding="utf-8")
            process = subprocess.run([sys.executable, "-X", "utf8", "-m", "damage_lab.helpbook", "merge",
                                      "--index", str(source), "--review", str(review), "--output", str(output)],
                                     cwd=Path(__file__).resolve().parents[1], capture_output=True, text=True, encoding="utf-8", timeout=10)
            self.assertEqual((process.returncode, output.read_text(encoding="utf-8")), (1, "preserve synthetic artifact"))

    def test_cli_malformed_review_does_not_create_output(self):
        with tempfile.TemporaryDirectory() as folder:
            source, review, output = [Path(folder) / name for name in ("index.json", "review.json", "merged.json")]
            source.write_text(json.dumps(index()), encoding="utf-8")
            review.write_text("{broken", encoding="utf-8")
            process = subprocess.run([sys.executable, "-X", "utf8", "-m", "damage_lab.helpbook", "merge",
                                      "--index", str(source), "--review", str(review), "--output", str(output)],
                                     cwd=Path(__file__).resolve().parents[1], capture_output=True, text=True, encoding="utf-8", timeout=10)
            self.assertEqual((process.returncode, output.exists(), "Traceback" in process.stderr), (1, False, False))
