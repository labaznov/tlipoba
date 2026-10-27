# Plan

1. Independently review the numbered requirements and inspect exact consumers
   before production changes
2. Freeze the smallest public dependency snapshot inside the exporter workspace
   for one external author; no external agent edits the planner directly
3. Use vertical RED/GREEN steps in paired tests for the topology helper, raw
   combat validation, and exact composition/report consumers
4. Independently review the proposal with proof reruns under the shared heavy
   lease; integrate only the approved files and reproduce the core RED locally
5. Run the full local Windows suite on the final integration candidate, review
   privacy, commit and push branch1, and verify draft PR2

Use the accepted shared resource pool in `handoff/runtime-state`: bounded jobs
with explicit CPU/memory requests and exclusive keys for shared resources.
No game, memory, UI, network capture or external runner is needed for this block.
