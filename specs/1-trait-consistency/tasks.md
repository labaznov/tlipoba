# Tasks

The Codex coordinator owns this file and target-branch integration.

- Spec review: Claude; only a new review report and proof notes.
- Producer and frozen consumer proposal: DeepSeek, after checking ZCode's stale
  presence; owns exporter `trait_ranks.py`, its paired tests, and the declared
  private consumer proposal. No executor commits or main-repository edits.
- Independent implementation review: Claude after author DONE; rerun proof
  commands under the shared heavy lease and report Spec/Standards separately.
- Planner metadata task and integration: Codex; owns planner `importer.py`,
  `report.py`, their existing paired tests, necessary import documentation and
  these spec files. It integrates the separate `traitranks.py` proposal after
  independent review. No concurrent executor owns these actual shared files.
- Shared constant provision: Codex serially adds the spec's exact
  `LEGACY_ASSUMPTION` to the actual planner `traitranks.py` for metadata reuse.
  This is its own metadata dependency; no unreviewed consumer implementation is
  copied. The later reviewed proposal contains the same constant.
- Private CLI fixtures: Codex regenerates the leaf with the actual producer and
  recorded local catalog inputs. Other source and user changes stay untouched.

The old optional descriptor-enum job is deferred before claim to prioritize this
source-backed defect. It remains visible in the handoff history.
