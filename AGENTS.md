# Project purpose

Build an independent local Torchlight Infinite planner, inspired by the capabilities of Path of Building Community. Start with Carino / Zealot of War / Cold Chromatic Shot / Tangle in SS14. Read `docs/VISION.md` and `docs/ROADMAP.md` before substantial work. Keep replies short and direct.

## Planning and parallel work

- Decompose substantial work into concrete tasks with dependencies, acceptance criteria and separate file ownership before editing
- Use the Codex subagents authorized by the user for independent tasks; keep a useful task for the coordinating agent
- Begin independent work immediately after delegation and wait only at a real dependency
- Check delegated results, run relevant verification and integrate them before claiming completion
- Never edit a file owned by an active agent; coordinate scope changes explicitly
- On ambiguity, state the interpretation and resolve material unknowns; do not hide assumptions

## Local resource budget

The owner reported severe slowdown and rebooted after accumulated worker processes. Keep parallel reasoning within this shared Windows budget

- Use the coordinator, one Claude queue worker, one DeepSeek queue worker and at most one Codex subagent at a time; keep each external queue serial and do not nest delegation
- Run at most one heavy local job across both repositories: a test suite, capture, catalog scan, bulk download or build
- The coordinator owns this shared slot and explicitly assigns it in the helper task before launch, including previously queued work; unassigned tasks may only do small scoped reads or edits
- While an assigned job runs, the coordinator edits or reads small scoped files instead of starting another heavy job
- Reuse returned terminal session IDs and existing verified watchers/servers; do not start replacement loops or servers while an earlier instance may still run
- Keep commands in the foreground with bounded timeouts; account for owned children when a command fails or times out
- Before starting and after finishing a long job, check that its owned processes ended; identify them by PID, start time and task ownership, never just an image name
- Never kill all Python, Node, shell or Claude processes; preserve unrelated applications and needed helper sessions
- Hash only the task's declared inputs and outputs; do not recursively inventory historical captures, catalogs, caches or Git objects for routine edits
- If the owner reports slowdown or workers accumulate, stop launching jobs and inspect ownership before continuing

## Game experiment windows

- Control the game UI only during a user-authorized window when the owner is not playing; input inactivity alone is not authorization
- The owner permits passive read-only memory acquisition while playing; keep it bounded within the shared resource budget and never take mouse or keyboard focus
- Prefer saved inputs for development; a new passive scan must answer a concrete missing-data question rather than run continuously
- Map character/build roots, field types, links and relocation/validation rules; do not treat a cached address or completed reads as proof of global uniqueness or an atomic live snapshot
- Start with read-only navigation and stat acquisition; reversible build changes need a saved baseline, one changed variable and verified restoration
- Pause on user return, focus loss, ambiguity or unexpected dialogs; record incomplete restoration instead of silently assuming success
- Do not buy, sell, craft, spend currency or delete items as part of a routine experiment
- Use ordinary UI and the existing read-only exporter; do not write to game memory

## External Claude helper

The user provides Claude Code Opus 5.5 Extra through the file queue in the separate exporter repository. The protocol is `C:/Repos/tli-build-exporter/handoff/README.md`; read it before first use and follow its exact templates and permission boundaries.

- Before substantial work, check the modification time of `C:/Repos/tli-build-exporter/handoff/.claude-alive`
- When the heartbeat is no older than 2 minutes, delegate useful independent work, including difficult research, implementation, diagnosis and review, within the local resource budget
- Supply complete tasks with exact paths, context, expected outputs, ownership and verification commands
- Keep ready independent tasks queued when useful; the external watcher processes its queue serially, so order tasks by dependency and priority
- Continue local work while Claude runs; read reports at dependency boundaries and verify their claims
- Claude operates only inside `C:/Repos/tli-build-exporter`; do not ask it to edit this project or another directory
- Request results or proposed changes inside the helper's repository, then have the coordinating agent review and integrate them here
- If the heartbeat is stale or missing, tell the user and continue available work locally instead of waiting
- This rule does not expand the helper's permissions or authorize publishing, uploads or changes to its protocol

## DeepSeek implementation and independent review

- Use the shared roster and addressed queue in `C:/Repos/tli-build-exporter/handoff/README.md` sections 9-10 for Claude and DeepSeek availability, ownership and stopped-task records
- Prefer available DeepSeek for scoped implementation and ordinary unfinished technical tasks; provide exact inputs, acceptance criteria, file ownership and the heavy-slot assignment
- After DeepSeek reports `done`, assign Claude an independent review of the requirements and resulting diff; the author cannot approve its own work
- The coordinator verifies source hashes, failing/passing test evidence and owned-process completion, resolves review findings, and integrates only the reviewed result
- Keep unfinished tasks visible and check completed successors before reassignment; record permission and safety stops for review rather than silently losing or automatically retrying them
- A missing permission is requested from the human by the agent that needs it; a model change or user approval does not override system or provider restrictions
- External agents remain inside the exporter repository; transfer reviewed proposals here through the coordinator, preserving the single heavy-job budget and Windows-only validation

## Git and scope

- Pull from the configured remote before making changes; inspect and preserve existing work first
- Name a task branch after an existing GitHub issue integer; do not invent an issue number
- When no issue exists, resolve the tracking choice explicitly before creating a task branch
- Keep changes focused; do not refactor unrelated code
- Preserve user artifacts and existing captures; never delete or overwrite them as cleanup
- Do not select a license on the owner's behalf; licensing is pending

## Implementation and tests

- Run checks locally on the user's Windows machine; do not configure or trigger GitHub Actions runners or Linux/macOS checks unless the user changes this preference
- Run `python scripts/test.py` once with the configured Python executable for the full local test suite; it invokes `python -m unittest discover -s tests -v`, so do not repeat discovery separately without a new change or failure
- Use Python 3.13 or newer and the standard library unless a dependency is justified and authorized
- Follow TDD for functional changes: first demonstrate the behavior with a failing test, then implement the smallest passing change
- Complete that full suite before reporting a functional change complete; do not install a self-hosted runner service as a substitute
- Keep tests deterministic and independent of the game, Internet and user exports; use synthetic inputs and temporary directories
- Map test files to feature files, keep each test focused on one behavior, and prefer short tests with one assertion
- Prefer fakes over mocks and real temporary filesystem inputs over filesystem mocking
- Bound waits, use ephemeral ports when testing local services, and keep logging disabled in tests
- Explain new classes with a plain docstring about their purpose; keep commands and queries separate
- Prefer composition and explicit data contracts; avoid reflection and hidden fallbacks

## Calculation integrity

- Automatic import is a product requirement: acquire the complete build and available stats through a verified game API, build export or local read-only game adapter
- Never make screenshots or manually transcribed character values a required player workflow; optional development evidence does not replace an importer
- Treat missing hero ranks, rolls and stats as importer coverage gaps to investigate; do not declare the feature complete by asking players to fill them in
- Investigate code/ID import first and verify the actual endpoint contract; do not invent server routes or send real build codes to unrelated services

- Separate observed character values, source facts and scenario assumptions
- Keep season, source URL and verification date with facts; preserve conflicting evidence instead of silently choosing it
- Unknown mappings or mechanics must produce an explicit omission, conditional result or error
- Never fabricate rolls, identifiers, skill levels, combat rotations, effect uptime or unsupported formula semantics
- Resolve skill values from the exact level/rank table and verified parameter bindings; rendered descriptions can contain level-one or stale numbers
- Parse catalog rational cells as numbers without evaluating expressions; preserve unresolved levels and flat progression tails as explicit gaps
- Do not apply item or support multipliers again when a panel aggregate already includes them
- Never fit a hidden coefficient to reproduce a benchmark; measurements validate the model
- Show modifier coverage and a calculation trace; do not claim exact total DPS while material effects remain unsupported

## Private data

- Never commit real `source.json`, native captures, exports, account identifiers, private screenshots, secrets or generated player reports
- Keep all real game inputs and runtime databases under ignored local directories or outside this repository
- Public examples and test fixtures must be synthetic and contain no user account data
- Review staged files and diffs for private data before each commit and publication
- Game access belongs to the external read-only exporter; this project must not write to the game process
