# Printed build-domain projection

`damage_lab.logbuild.project(snapshot, event_index, source_sha256)` is a pure consumer of
`damage_lab.buildlog.snapshot` version 0.1.2. It reads no files and does not choose or combine events.
The caller selects one accepted event by its zero-based index and supplies the expected ordinary-log
prefix SHA-256. The prefix hash is declared provenance, not proof of the tree's derivation or identity.

The selected event must contain table-shaped `bag.wearItems`, `heroCharacterv3OverView`, and
`skillLayout`. These are observed player-state candidate requirements, not a general game protocol.
An unfamiliar future event schema is explicitly refused; refusal does not mean that a build is absent.

`candidates(snapshot, source_sha256) -> list[int]` validates the saved envelope and parser trees, then
enumerates indexes satisfying the same structural requirements. It chooses no event, joins no values,
and returns an empty list when no accepted event matches. Each candidate must be projected independently.

## Output

The format is `tli-log-build-domains-v1`, with `scope: printed_subtree_only`, `import_complete: false`,
and `identity`, `runtime`, `freshness`, `selected_skill`, and `build_code` always `unknown`.
Safe source metadata includes SHA-256 and prefix bytes; event metadata includes its index, physical line
range, boundary, and the lexical client-log header. Header time has unknown timezone and is not data age.
The original source path and all `player` fields are excluded.

Each fixed domain has `path`, `status`, `node_kind`, `visible_entries`, `total_entries: null`, `rows`,
and `gaps`. Status is `complete`, `elided`, or `not_printed`: completeness describes the printed subtree
only. Root elision does not make an already printed child elided. A missing child is `not_printed`,
never proof of absence. Bare empty tables retain an explicit empty-container ambiguity gap.

Rows use coordinate aliases and source paths. Their `fields` are fixed names, each holding a coverage
status, lexical `values: [{path, text, class}]`, and explicit `missing_paths`, `elided_paths`, and
`empty_paths`. Classes are the parser's `bool`, `int`, `float`, or `text`; no scalar is converted to a
number or boolean. Missing fields do not become zero, false, or empty arrays. The `values` collection
enumerates observed tokens, not a reconstructed source array.

Top-level `counts` contains `domains`, `rows`, and `lexical_values`. Header keys are `logTimeText`,
`frame`, and `timezone`. All other projection property names use snake_case. Rows never contain rank,
compiled-modifier, or damage results.

| Domain | Exact tree path | Records / allowlisted fields |
|---|---|---|
| equipment | `bag.wearItems` | `PageId`, `Index`, `Item.{BaseId,Level,RareValue,Corrode,AffixNum}` and listed affix tokens |
| memories | `heroCharacterv3OverView.reminiscenceOverView.reminiscence` | `index`, `state`, `detail.{BaseId,Level,ReminiscenceFixedLevel,ReminiscenceFixedLevelFromEnhance,ReminiscenceLevel}` and listed affix tokens |
| traits | `heroCharacterv3OverView.pointOverView.activeId` | each printed scalar token; no rank |
| slates | `bag.dressingTalentBlocks` | `PageId`, `Index`, `Item.{BaseId,Level,RareValue,ShapeId,Direction,EnhanceId,EnhancedTimes,InfluenceId}`, `BaseTalentList`, `EnchantTalentList`, `talentSlotList.{color,talentId}` |
| influence | `talentBlockInfluence` | `value.{EffectTalentIds,TalentIdDevour,TalentIdInfluence}`; its instance-key join is excluded |
| pacts | `ContractInfosV2.ContractDatas` | `areaId`, `servantId`; no activation, star level, or chosen scheme inferred |
| skill_layout | `skillLayout.slots` | `key` as lexical `slot_key`; no slot role or skill reference inferred |
| skill_items | `skills.skills` | `BaseId`, `Level`, `SkillItemLevel`, `RareValue`; no instance IDs or effective level |
| dressed_skill_items | `bag.dressSkillItems` | `PageId`, `Index`, `Item.{BaseId,Level,SkillItemLevel,RareValue}`; no instance IDs or joins |

The equipment affix lists are exactly `BaseAttrAffix`, `FixedBaseAffix`, `Prefix`, `Suffix`, and
`EnchantAffixs`. Memories also allow `BaseAffix`. Only `.Id`, `.Version`, `.source`, and `.DynArgs`
tokens are retained. Nested arrays must have contiguous one-based coordinate keys; an elision is not
an invented extra record. Affix `Condition`, `Filter`, and `Behavior` remain `not_printed` or
`printed_unmapped`, never `[]`. No row is compiled as an unconditional effect.

The following paths are coverage diagnostics only, without rows or skill-instance joins:

| Domain | Path |
|---|---|
| pact_points | `ContractInfosV2.pointDatas` |
| pact_roster | `ServantInfos.servantData` |
| talents | `geniusInfos` |
| stats | `attrInfo` |
| season | `SP3Base.TalentTree` |

The two item-level fields remain separate lexical facts. A complete printed
field does not prove complete skill inventory, an active link, or an effective
level. Layout `value.skillId` and item `Id` are omitted; matching or interpreting
those references needs a separate source-bound contract.

## Gates and limits

The consumer validates the supported envelope, source hash, index, line bounds, declared reader limits,
fixed unknown flags, parser version, lexical classes, unique keys, table cap, elision placement, node
counts, and parser counts. Hard ceilings match the saved reader: 1 GiB prefix, 20 million physical lines,
512 events, 32 MiB retained event bytes, 20,000 event lines, 512-byte lines, depth 32, and 200,000 nodes
per selected event. Malformed known shapes or inconsistent metadata raise a fixed `ValueError` without
input text. Unknown extra properties are discarded; unknown instance/account fields are not projected.

`Item.Id`, `UniqueItmId`, player/account data, names, and raw influence keys are excluded. `BaseId` and
native affix IDs survive only as source-bound lexical tokens; catalog identity, units, precision of the
game's original printer, effective skill levels, trait ranks, activation, and combat effects stay unverified.
`Direction` is not defaulted to zero. No ServerSource, old ProBuild join, compiled modifier, panel multiplier,
or DPS result is produced. Snapshot-boundary events retain that boundary warning rather than claiming a
verified message terminator. The ordinary log hash and exact re-rendering do not prove missing-line freedom.
