# Plan

1. Review the requirements independently before production changes.
2. Preserve the exporter working tree and prepare its local task branch. Check
   producer baseline, reproduce false catalog conflicts, and implement 0.1.1.
3. Prepare the frozen consumer and its paired tests inside the exporter handoff
   workspace; reproduce version/consistency failures before editing its code.
4. Review both proposals independently, including real proof-command reruns.
5. Integrate the consumer into branch 1, run focused checks and the full Windows
   suite plus configured linters, and run ordinary import on unchanged legacy and
   producer-regenerated private fixtures. Preserve contract provenance through
   snapshot, JSON, SQLite and HTML with a serialized metadata task.
6. Check privacy, commit the focused producer and planner changes separately,
   push the planner branch and verify draft PR2's head. Update the private
   frontier without claiming a complete Carino model.

Only one test or heavy job runs at a time. The shared coordination directory is
`C:/Repos/tli-build-exporter/handoff`. New feature jobs use an exclusive `heavy`
directory there, record owner/command/process receipts, and release only their
own lease after the child ends. A contested lease is bounded to 60 seconds and
reported to the leader; it never authorizes another worker or restart.
