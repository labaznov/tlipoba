# Installed build-request schema findings

Status: 2026-10-23, static source research. This supplies field declarations for
the automatic-import investigation; it is not a callable API or a fresh build.

The [saved client trace](../CLIENT_LUA.md#findings-for-automatic-import) selects
`GetBDContent`, protocol `30001`, and `rpc.GetBDContentReq/Ack`. Four exact
installed descriptor candidates were subsequently inspected: `api.pb`, `bd.pb`,
`bd_data.pb` and `data.pb`. Their compressed payloads matched SHA-1 values in
their own captured headers. Fixed ranges, headers and footer totaled 98,028
file bytes, without game-memory reads or UI input. Matching file metadata
observations do not establish an atomic read or current runtime selection.

An isolated [Windows decoder](https://pypi.org/project/kraken-decompressor/0.2.1/)
produced 404,180 saved bytes across five bounded compression blocks. It was
not installed into the application's environment or added as a dependency.
Raw inputs, binaries and generated projections remain private. No game code
or server request was executed.

The saved bytes have a `FileDescriptorSet`-shaped envelope with `proto3` files
in package `rpc`. A partial diagnostic projected message and field declarations
using the official [descriptor field definitions](https://github.com/protocolbuffers/protobuf/blob/v29.3/src/google/protobuf/descriptor.proto).
It checked enclosing byte boundaries and bounded wire records; it does not
validate every descriptor rule or resolve all dependencies and options.

| Message | Field | Declared type |
|---|---|---|
| `GetBDContentReq` | `bdId`, 1 | string |
| `GetBDContentAck` | `errCode`, 1 | `ErrCode` message |
| `GetBDContentAck` | `bdContent`, 2 | `BDContent` message |
| `BDContent` | `bdData`, 1 | `ViewPlayerData` message |
| `GetBDContentV2Req` | `type`, 1; `bdId`, 2 | `BDType` enum; string |

The V2 request has a different field layout. Neither schema establishes how a
share code becomes `bdId`, how transport flags and frames work, or how to
authenticate an independent request.

The four-file message-reference projection reached 84 definitions. Five message
references were unresolved: `ErrCode`, `GPlayerInfo`, `GSkillPosRequirement`,
`MercenaryOverViewDTO` and `SP3`. Enum definitions and map-entry options were
not resolved. This is a partial graph, not a usable complete schema bundle.

A subsequent exact `cApi.pb` dependency read used another 22,127 file bytes
and produced 103,638 saved bytes through the same isolated decoder. A separate
seven-message projection supplies `GPlayerInfo`, `GSkillPosRequirement` and
their selected message references. `GPlayerInfo` declares player state and
aura entries; the referenced `GSkillReserved` declares an `IsActive` boolean.
Declarations alone do not establish actual aura activation or absence defaults.
`ErrCode`, `MercenaryOverViewDTO` and `SP3`, plus enum/map options and complete
schema semantics, remain unresolved for the larger build investigation.

## Build and stat paths

`ViewPlayerData` declares `baseInfo` at field 5 and `featuresInfo` at field 6.
`ViewFeaturesInfo` links equipment, jewels, skills, skill layout, talents and
hero overview messages. `SkillDTO.skills`, field 12, repeats `PlayerItem`.
That item declares separate int32 fields `Level` (15) and `SkillItemLevel`
(75); their names do not determine effective skill level or stacking rules.

The stat path is `ViewPlayerData.attrInfo` (12), then
`ViewPlayerAttrInfo.playerAttr` (1), then `CPlayerData`.
`CPlayerData.attrs` (9) repeats an entry with int32 `key` (1) and double
`value` (2). `CPlayerData.DPS` (10) is uint64. A field named `DPS` does not
establish a per-skill damage formula or a relationship to a panel measurement.
Attribute-ID meanings and combat aggregation remain unverified.

The inspected Lua constructor retains its supplied value as `ServerSource`.
A historical source contains an explicitly named `rpc.ViewPlayerAttrInfo`
byte wrapper. A bounded, value-free diagnostic compared its 622 saved bytes
against ten selected message declarations: all 114 observed wire occurrences
matched their declared field numbers and wire types. This establishes structural
compatibility for those observations, without checking full protobuf semantics,
defaults, attribute-ID meanings or applicability to the current runtime.
Missing fields must not become invented zero-valued character stats.

The inspected `CreateSkills` body traverses `Skills.skills`, places each entire
`PlayerItem` in a wrapper with a page type and index, calls
`ItemMgr:CreateItem(wrapper, nil, true)`, and keys the result by `PlayerItem.Id`.
It does not directly read `Level` or `SkillItemLevel`; whether the item
constructor uses either field, and how, is unknown. The wrapper is reused across iterations;
the item constructor's copy/alias behavior is also unverified.

The next import boundary is lower transport discovery or a verified saved
response with a bounded decoder. These findings do not change ordinary import
completeness, selected-player identity, Carino's effective level or exact DPS.
