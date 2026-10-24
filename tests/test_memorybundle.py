"""Synthetic byte envelopes keep memory definitions diagnostic and source-bound."""

import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from damage_lab.memorybundle import read, summary


def persisted(directory, artifact, descriptor):
    """Write a fictional artifact and bind its exact bytes in a descriptor."""
    raw = json.dumps(artifact, ensure_ascii=False, allow_nan=False).encode("utf-8")
    (Path(directory) / "memory-definition-ledger.json").write_bytes(raw)
    descriptor["sha256"] = hashlib.sha256(raw).hexdigest()


def failure(directory, code="catalog_mapping_missing", *, unbound=False):
    """Preserve existing synthetic source bytes while describing an acquisition gap."""
    directory = Path(directory)
    path = directory / "source.json"
    if not path.exists():
        path.write_bytes(b"{}")
    source = hashlib.sha256(path.read_bytes()).hexdigest()
    flags = {field: False for field in ("arithmeticReady", "runtimeVerified", "identityVerified", "importComplete")}
    artifact = {"format": "tli-memory-definition-ledger-error-v1", "version": "0.1.0",
                "compilerVersion": "0.1.1", "status": "error", "error": code,
                "source": {"file": "source.json", "sha256": None if unbound else source}, **flags}
    descriptor = {"file": "memory-definition-ledger.json", "version": "0.1.0", "compilerVersion": "0.1.1",
                  "status": "error", "error": code, "sourceSha256": artifact["source"]["sha256"], **flags,
                  **{field: None for field in ("catalogDocuments", "jewels", "rows", "candidates", "omitted", "structuralGaps")}}
    persisted(directory, artifact, descriptor)
    return artifact, descriptor, source


def diagnostic(directory):
    """Describe unrelated fictional native and catalog rows without combat semantics."""
    from test_memorydefinitions import document

    artifact, descriptor, source = failure(directory)
    ledger = document()
    ledger["source"]["sha256"] = source
    artifact.pop("error")
    descriptor.pop("error")
    artifact.update(format="tli-memory-definition-ledger-bundle-v1", status="diagnostic", ledger=ledger,
        catalog={"derivation": "cache_member_exact_slice", "networkBytesVerified": False,
            "currentPatchVerified": False, "documents": [
                {"logicalPath": path, "address": f"/data/SS14/{path}.json", "cacheFile": "1234567890abcdef.json",
                 "wrapperSha256": "b" * 64, "member": path, "byteRange": [37 + index * 150, 139 + index * 150],
                 "memberSha256": ("c" if index == 0 else "d") * 64, "encoding": "utf-8"}
                for index, path in enumerate(("hero-memory/i18n/en", "hero-memory/master"))]})
    descriptor.update(status="diagnostic", catalogDocuments=2, jewels=3, rows=2, candidates=1, omitted=1, structuralGaps=1)
    persisted(directory, artifact, descriptor)
    return artifact, descriptor, source


class MemoryBundleTests(unittest.TestCase):
    """Exact artifact bytes constrain a passive definition ledger and its provenance."""

    def test_diagnostic_bytes_preserve_exact_values_and_unresolved_roles(self):
        with tempfile.TemporaryDirectory() as folder:
            _, descriptor, source = diagnostic(folder)
            pair, origin = read(folder, descriptor, source)
            self.assertEqual((pair["ledger"]["candidates"][0]["own_values"][0]["exact"],
                              pair["ledger"]["candidates"][0]["operator"],
                              pair["catalog"]["documents"][0]["logical_path"], origin[1], origin[-1]),
                             ("7.312500", "unresolved", "hero-memory/i18n/en", descriptor["sha256"], 1))

    def test_each_reviewed_producer_failure_retains_only_a_hashed_unstored_origin(self):
        from damage_lab.memorybundle import ERRORS

        for code in ERRORS:
            with self.subTest(code=code), tempfile.TemporaryDirectory() as folder:
                _, descriptor, source = failure(folder, code)
                pair, origin = read(folder, descriptor, source)
                self.assertEqual((pair, origin), (None, (str((Path(folder) / "memory-definition-ledger.json").resolve()),
                                                          descriptor["sha256"], (Path(folder) / "memory-definition-ledger.json").stat().st_size, 0)))

    def test_only_unread_source_errors_may_leave_the_source_hash_unknown(self):
        for code in ("source_missing", "source_unreadable"):
            with self.subTest(code=code), tempfile.TemporaryDirectory() as folder:
                _, descriptor, source = failure(folder, code, unbound=True)
                self.assertIsNone(read(folder, descriptor, source)[0])

    def test_a_catalog_error_cannot_drop_its_source_binding(self):
        with tempfile.TemporaryDirectory() as folder:
            _, descriptor, source = failure(folder, unbound=True)
            with self.assertRaises(ValueError):
                read(folder, descriptor, source)

    def test_summary_drops_unknowns_without_changing_or_aliasing_known_data(self):
        with tempfile.TemporaryDirectory() as folder:
            _, descriptor, source = diagnostic(folder)
            pair, _ = read(folder, descriptor, source)
            expected = copy.deepcopy(pair)
            for row in (pair, pair["ledger"], pair["ledger"]["source"], pair["ledger"]["candidates"][0],
                        pair["catalog"], pair["catalog"]["documents"][0]):
                row["account_canary"] = "private-unknown-value"
            before = copy.deepcopy(pair)
            result = summary(pair)
            result["catalog"]["documents"][0]["byte_range"][0] = 19
            expected["catalog"]["documents"][0]["byte_range"][0] = 19
            self.assertEqual((result, pair), (expected, before))

    def test_read_does_not_modify_descriptor_or_source_bytes(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "source.json"
            path.write_bytes(b'{"synthetic":"preserved-byte-order"}\n')
            _, descriptor, source = diagnostic(folder)
            before = copy.deepcopy(descriptor)
            read(folder, descriptor, source)
            self.assertEqual((descriptor, path.read_bytes()), (before, b'{"synthetic":"preserved-byte-order"}\n'))

    def test_the_fixed_artifact_path_and_both_versions_are_required(self):
        for field, invalid in (("file", "../memory-definition-ledger.json"), ("version", "0.1.1"),
                               ("compilerVersion", "0.1.0"), ("status", "complete")):
            with self.subTest(field=field), tempfile.TemporaryDirectory() as folder:
                _, descriptor, source = diagnostic(folder)
                descriptor[field] = invalid
                with self.assertRaises(ValueError):
                    read(folder, descriptor, source)

    def test_all_false_descriptor_and_artifact_flags_are_literal_booleans(self):
        for boundary in ("descriptor", "artifact"):
            for field in ("arithmeticReady", "runtimeVerified", "identityVerified", "importComplete"):
                for invalid in (True, 0, None):
                    with self.subTest(boundary=boundary, field=field, invalid=invalid), tempfile.TemporaryDirectory() as folder:
                        artifact, descriptor, source = diagnostic(folder)
                        (descriptor if boundary == "descriptor" else artifact)[field] = invalid
                        persisted(folder, artifact, descriptor)
                        with self.assertRaises(ValueError):
                            read(folder, descriptor, source)

    def test_source_binding_is_required_at_descriptor_artifact_and_leaf(self):
        for boundary in ("descriptor", "artifact", "leaf"):
            with self.subTest(boundary=boundary), tempfile.TemporaryDirectory() as folder:
                artifact, descriptor, source = diagnostic(folder)
                if boundary == "descriptor":
                    descriptor["sourceSha256"] = "e" * 64
                else:
                    (artifact if boundary == "artifact" else artifact["ledger"])["source"]["sha256"] = "e" * 64
                persisted(folder, artifact, descriptor)
                with self.assertRaises(ValueError):
                    read(folder, descriptor, source)

    def test_exact_artifact_hash_is_checked_before_parsing(self):
        with tempfile.TemporaryDirectory() as folder:
            _, descriptor, source = diagnostic(folder)
            with (Path(folder) / "memory-definition-ledger.json").open("ab") as stream:
                stream.write(b" ")
            with self.assertRaises(ValueError):
                read(folder, descriptor, source)

    def test_every_descriptor_count_matches_the_validated_leaf_with_exact_types(self):
        for field in ("catalogDocuments", "jewels", "rows", "candidates", "omitted", "structuralGaps"):
            for invalid in (True, None, 4.0, 19):
                with self.subTest(field=field, invalid=invalid), tempfile.TemporaryDirectory() as folder:
                    _, descriptor, source = diagnostic(folder)
                    descriptor[field] = invalid
                    with self.assertRaises(ValueError):
                        read(folder, descriptor, source)

    def test_producer_error_cannot_retain_semantic_data_or_nonnull_counts(self):
        for change in ("count", "ledger", "catalog", "code"):
            with self.subTest(change=change), tempfile.TemporaryDirectory() as folder:
                artifact, descriptor, source = failure(folder)
                if change == "count":
                    descriptor["rows"] = 0
                elif change == "code":
                    artifact["error"] = "compiler_failed"
                else:
                    artifact[change] = None
                persisted(folder, artifact, descriptor)
                with self.assertRaises(ValueError):
                    read(folder, descriptor, source)

    def test_unknown_errors_and_diagnostic_error_claims_are_rejected(self):
        for status in ("diagnostic", "error"):
            with self.subTest(status=status), tempfile.TemporaryDirectory() as folder:
                artifact, descriptor, source = diagnostic(folder) if status == "diagnostic" else failure(folder)
                artifact["error"] = descriptor["error"] = "account-canary-not-an-error"
                persisted(folder, artifact, descriptor)
                with self.assertRaises(ValueError):
                    read(folder, descriptor, source)

    def test_absent_descriptors_or_pairs_do_not_become_empty_legacy_ledgers(self):
        with tempfile.TemporaryDirectory() as folder:
            for value in (None, {}, []):
                with self.subTest(value=value), self.assertRaises(ValueError):
                    read(folder, value, "a" * 64)
                with self.subTest(value=value), self.assertRaises(ValueError):
                    summary(value)

    def test_uncaptured_domains_keep_null_counts_and_explicit_empty_domains_keep_zero(self):
        for status in ("absent", "not_captured", "invalid", "captured"):
            with self.subTest(status=status), tempfile.TemporaryDirectory() as folder:
                artifact, descriptor, source = diagnostic(folder)
                ledger = artifact["ledger"]
                ledger["domain"]["status"] = status
                for field in ("candidates", "omitted", "structuralGaps"):
                    ledger[field] = [] if status == "captured" else None
                ledger["accounting"] = {field: (True if field == "reconciles" else 0) if status == "captured" else None
                                        for field in ledger["accounting"]}
                for field in ("jewels", "rows", "candidates", "omitted", "structuralGaps"):
                    descriptor[field] = 0 if status == "captured" else None
                persisted(folder, artifact, descriptor)
                pair, _ = read(folder, descriptor, source)
                self.assertEqual((pair["ledger"]["candidates"], pair["ledger"]["accounting"]["rows"]),
                                 ([], 0) if status == "captured" else (None, None))

    def test_declared_catalog_coordinates_and_hashes_are_narrowly_validated(self):
        invalids = (("logicalPath", "gear/master"), ("address", "/data/SS13/hero-memory/i18n/en.json"),
                    ("cacheFile", "../1234567890abcdef.json"), ("cacheFile", "1234567890ABCDEF.json"),
                    ("wrapperSha256", "B" * 64), ("member", "hero-memory/master"), ("encoding", "UTF-8"),
                    ("memberSha256", "e" * 63), ("byteRange", [True, 139]), ("byteRange", [37.0, 139]),
                    ("byteRange", [-1, 139]), ("byteRange", [139, 139]), ("byteRange", [37, 32 * 1024 * 1024 + 1]))
        for field, invalid in invalids:
            with self.subTest(field=field, invalid=invalid), tempfile.TemporaryDirectory() as folder:
                artifact, descriptor, source = diagnostic(folder)
                artifact["catalog"]["documents"][0][field] = invalid
                persisted(folder, artifact, descriptor)
                with self.assertRaises(ValueError):
                    read(folder, descriptor, source)

    def test_exactly_two_unique_catalog_members_are_required_without_verified_claims(self):
        for change in ("missing", "extra", "duplicate", "derivation", "network", "patch"):
            with self.subTest(change=change), tempfile.TemporaryDirectory() as folder:
                artifact, descriptor, source = diagnostic(folder)
                catalog = artifact["catalog"]
                if change == "missing":
                    catalog["documents"].pop()
                elif change == "extra":
                    catalog["documents"].append(copy.deepcopy(catalog["documents"][0]))
                elif change == "duplicate":
                    catalog["documents"][1] = copy.deepcopy(catalog["documents"][0])
                elif change == "derivation":
                    catalog["derivation"] = "network_verified"
                else:
                    catalog["networkBytesVerified" if change == "network" else "currentPatchVerified"] = True
                persisted(folder, artifact, descriptor)
                with self.assertRaises(ValueError):
                    read(folder, descriptor, source)

    def test_shared_cache_members_cannot_overlap_or_disagree_on_wrapper_hash(self):
        for change in ("overlap", "wrapper"):
            with self.subTest(change=change), tempfile.TemporaryDirectory() as folder:
                artifact, descriptor, source = diagnostic(folder)
                row = artifact["catalog"]["documents"][1]
                row["byteRange" if change == "overlap" else "wrapperSha256"] = [138, 287] if change == "overlap" else "f" * 64
                persisted(folder, artifact, descriptor)
                with self.assertRaises(ValueError):
                    read(folder, descriptor, source)

    def test_adjacent_slices_and_independent_wrapper_offsets_are_both_legal(self):
        for independent in (False, True):
            with self.subTest(independent=independent), tempfile.TemporaryDirectory() as folder:
                artifact, descriptor, source = diagnostic(folder)
                row = artifact["catalog"]["documents"][1]
                row["byteRange"] = [37, 139] if independent else [139, 287]
                if independent:
                    row.update(cacheFile="fedcba0987654321.json", wrapperSha256="f" * 64)
                persisted(folder, artifact, descriptor)
                self.assertEqual(read(folder, descriptor, source)[0]["catalog"]["documents"][1]["byte_range"], row["byteRange"])

    def test_summary_repeats_catalog_leaf_and_fixed_false_guards(self):
        for change in ("catalog", "leaf", "flags", "range", "overlap"):
            with self.subTest(change=change), tempfile.TemporaryDirectory() as folder:
                _, descriptor, source = diagnostic(folder)
                pair, _ = read(folder, descriptor, source)
                if change == "catalog":
                    pair["catalog"]["documents"][0]["member"] = "gear/master"
                elif change == "leaf":
                    pair["ledger"]["candidates"][0]["operator"] = "multiply"
                elif change == "flags":
                    pair["ledger"]["runtime_verified"] = True
                elif change == "range":
                    pair["catalog"]["documents"][0]["byte_range"][0] = False
                else:
                    pair["catalog"]["documents"][1]["byte_range"] = [38, 139]
                with self.assertRaises(ValueError):
                    summary(pair)

    def test_envelope_and_leaf_compiler_versions_cannot_disagree(self):
        for field, invalid in (("format", "tli-memory-definition-ledger-error-v1"), ("version", "0.1.1"),
                               ("compilerVersion", "0.1.0"), ("status", "error"), ("source_file", "another.json"),
                               ("leaf", "0.1.0")):
            with self.subTest(field=field), tempfile.TemporaryDirectory() as folder:
                artifact, descriptor, source = diagnostic(folder)
                if field == "leaf":
                    artifact["ledger"]["version"] = invalid
                elif field == "source_file":
                    artifact["source"]["file"] = invalid
                else:
                    artifact[field] = invalid
                persisted(folder, artifact, descriptor)
                with self.assertRaises(ValueError):
                    read(folder, descriptor, source)

    def test_byte_limits_are_strict_integers_and_enforced_before_parsing(self):
        for limit in (True, 0, -1, 17.0, 64 * 1024 * 1024 + 1, 17):
            with self.subTest(limit=limit), tempfile.TemporaryDirectory() as folder:
                _, descriptor, source = diagnostic(folder)
                with self.assertRaises(ValueError):
                    read(folder, descriptor, source, max_bytes=limit)

    def test_the_exact_artifact_byte_limit_is_inclusive(self):
        with tempfile.TemporaryDirectory() as folder:
            _, descriptor, source = diagnostic(folder)
            self.assertEqual(read(folder, descriptor, source,
                                  max_bytes=(Path(folder) / "memory-definition-ledger.json").stat().st_size)[1][-1], 1)

    def test_json_duplicates_nonfinite_overflow_underflow_invalid_utf8_and_recursion_are_refused(self):
        invalids = (b'{"account_canary":1,"account_canary":2}', b'{"a":NaN}', b'{"a":Infinity}',
                    b'{"a":1e9999}', b'{"a":1e-9999}', b'\xff',
                    b'\xef\xbb\xbf{}', b'{not-json}')
        for raw in invalids:
            with self.subTest(raw=raw[:30]), tempfile.TemporaryDirectory() as folder:
                _, descriptor, source = diagnostic(folder)
                (Path(folder) / "memory-definition-ledger.json").write_bytes(raw)
                descriptor["sha256"] = hashlib.sha256(raw).hexdigest()
                with self.assertRaisesRegex(ValueError, "^Memory definition artifact requires strict bounded UTF-8 JSON$"):
                    read(folder, descriptor, source)

    def test_excessively_nested_unknown_json_does_not_bypass_the_envelope_limit(self):
        with tempfile.TemporaryDirectory() as folder:
            artifact, descriptor, source = diagnostic(folder)
            raw = json.dumps(artifact).encode("utf-8")[:-1] + b',"unreviewed":' + b'[' * 80 + b'0' + b']' * 80 + b'}'
            (Path(folder) / "memory-definition-ledger.json").write_bytes(raw)
            descriptor["sha256"] = hashlib.sha256(raw).hexdigest()
            with self.assertRaises(ValueError):
                read(folder, descriptor, source)

    def test_caller_and_descriptor_hashes_require_lowercase_sha256(self):
        for invalid in (True, None, "a" * 63, "A" * 64, "x" * 64):
            with self.subTest(invalid=invalid), tempfile.TemporaryDirectory() as folder:
                _, descriptor, source = diagnostic(folder)
                with self.assertRaises(ValueError):
                    read(folder, descriptor, invalid)
                descriptor["sha256"] = invalid
                with self.assertRaises(ValueError):
                    read(folder, descriptor, source)
