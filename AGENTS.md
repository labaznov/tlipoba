# Project purpose

Build an independent local Torchlight Infinite planner, inspired by the capabilities of Path of Building Community. Start with Carino / Zealot of War / Cold Chromatic Shot / Tangle in SS14. Read `docs/VISION.md` and `docs/ROADMAP.md` before substantial work. Keep replies short and direct.

## Planning and parallel work

- Decompose substantial work into concrete tasks with dependencies, acceptance criteria and separate file ownership before editing
- Use the Codex subagents authorized by the user for independent tasks; keep a useful task for the coordinating agent
- Begin independent work immediately after delegation and wait only at a real dependency
- Check delegated results, run relevant verification and integrate them before claiming completion
- Never edit a file owned by an active agent; coordinate scope changes explicitly
- On ambiguity, state the interpretation and resolve material unknowns; do not hide assumptions

## External Claude helper

The user provides Claude Code Opus 5.5 Extra through the file queue in the separate exporter repository. The protocol is `C:/Repos/tli-build-exporter/handoff/README.md`; read it before first use and follow its exact templates and permission boundaries.

- Before substantial work, check the modification time of `C:/Repos/tli-build-exporter/handoff/.claude-alive`
- When the heartbeat is no older than 2 minutes, actively delegate as much useful independent work as possible, including difficult research, implementation, diagnosis and review
- Supply complete tasks with exact paths, context, expected outputs, ownership and verification commands
- Keep ready independent tasks queued when useful; the external watcher processes its queue serially, so order tasks by dependency and priority
- Continue local work while Claude runs; read reports at dependency boundaries and verify their claims
- Claude operates only inside `C:/Repos/tli-build-exporter`; do not ask it to edit this project or another directory
- Request results or proposed changes inside the helper's repository, then have the coordinating agent review and integrate them here
- If the heartbeat is stale or missing, tell the user and continue available work locally instead of waiting
- This rule does not expand the helper's permissions or authorize publishing, uploads or changes to its protocol

## Git and scope

- Pull from the configured remote before making changes; inspect and preserve existing work first
- Name a task branch after an existing GitHub issue integer; do not invent an issue number
- When no issue exists, resolve the tracking choice explicitly before creating a task branch
- Keep changes focused; do not refactor unrelated code
- Preserve user artifacts and existing captures; never delete or overwrite them as cleanup
- Do not select a license on the owner's behalf; licensing is pending

## Implementation and tests

- Use Python 3.13 or newer and the standard library unless a dependency is justified and authorized
- Follow TDD for functional changes: first demonstrate the behavior with a failing test, then implement the smallest passing change
- Run `python -m unittest discover -s tests -v` before reporting a functional change complete
- Keep tests deterministic and independent of the game, Internet and user exports; use synthetic inputs and temporary directories
- Map test files to feature files, keep each test focused on one behavior, and prefer short tests with one assertion
- Prefer fakes over mocks and real temporary filesystem inputs over filesystem mocking
- Bound waits, use ephemeral ports when testing local services, and keep logging disabled in tests
- Explain new classes with a plain docstring about their purpose; keep commands and queries separate
- Prefer composition and explicit data contracts; avoid reflection and hidden fallbacks

## Calculation integrity

- Separate observed character values, source facts and scenario assumptions
- Keep season, source URL and verification date with facts; preserve conflicting evidence instead of silently choosing it
- Unknown mappings or mechanics must produce an explicit omission, conditional result or error
- Never fabricate rolls, identifiers, skill levels, combat rotations, effect uptime or unsupported formula semantics
- Do not apply item or support multipliers again when a panel aggregate already includes them
- Never fit a hidden coefficient to reproduce a benchmark; measurements validate the model
- Show modifier coverage and a calculation trace; do not claim exact total DPS while material effects remain unsupported

## Private data

- Never commit real `source.json`, native captures, exports, account identifiers, private screenshots, secrets or generated player reports
- Keep all real game inputs and runtime databases under ignored local directories or outside this repository
- Public examples and test fixtures must be synthetic and contain no user account data
- Review staged files and diffs for private data before each commit and publication
- Game access belongs to the external read-only exporter; this project must not write to the game process
