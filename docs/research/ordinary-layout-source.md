# Printed skill layout and item references

Checked 2026-10-24 against the saved installed `ViewPlayerMgr` listing and
the partial descriptor projection described in [build-protocol-schema](build-protocol-schema.md).
These are static source facts under the inspected Lua operand conventions,
not a current character, selected build, active support group or SS14 runtime proof.
No game instructions or server requests were executed for this check.
Raw listings and descriptors remain private.

## Reference path

The descriptor declares `ViewFeaturesInfo.skillLayout` as `SkillSlotDTO`.
Its repeated `slots` contains `SlotsEntry`: int32 `key` and `SkillStatus`
`value`. The latter declares string `skillId` and an enum `status`.
`PlayerItem.Id` is also a declared string. Map-entry options and enum
semantics remain unresolved; names and compatible types alone do not prove a join.

The saved source supplies the reference:

1. `CreateSkills` constructs each item and assigns it to a dictionary keyed
   by that input `PlayerItem.Id`
2. `CreateViewPlayerData` passes the resulting dictionary as the second
   argument to `CreateSkillLayout`
3. That helper reads a slot's `value.skillId`; its lookup path reads
   `Skills[skillId]` and assigns the result to a struct's `SkillData`

Thus the inspected lookup uses an item-instance reference. It is separate
from `BaseId`, which identifies a catalog definition. The ordinary lexical
projection deliberately omits both instance fields. The within-event
observation layer emits coordinate aliases without exporting their raw tokens.
Such an observed token match must preserve missing and elided peers and
duplicate ambiguity; it cannot establish the selected installed item or a
complete support group. The printer's lexical classes are not original wire types.

The code also compares the reference with the string `"0"`. At PC 29–32,
the listing has `EQ`, `JMP` with signed offset 2, the dictionary lookup and
then the `SkillData` assignment. With ordinary `pc + 1 + offset` semantics,
the jump at PC 30 reaches PC 33, skipping both lookup and assignment. This
function then makes no such assignment on the string-sentinel path. The
initialization helper or struct defaults may already supply a value, and the
data inspector alone does not verify the game's custom control-flow semantics.
An empty or unequipped slot is therefore not established by the literal sentinel.

## Position and initializer

`CreateSkillLayout` passes the entry `key` unchanged into
`SkillConstantMgr:CalSkillTabIndex`. The two returned values index the
output dictionary. A follow-up checked this body and the initializer in two
exact installed-file scripts: 58,575 bytes including headers and the source
footer, followed by saved-data inspection at unchanged parser limits. Their
58,242 payload bytes parsed as 127 functions and 3,077 instructions without
executing game code. Both complete payload SHA-1 values matched their own
captured headers; equal file metadata observations do not prove atomicity or
current runtime selection.

The helper stores the return of `SkillMgr.InitSkillSlotItemData(struct, entry)`
before assigning `struct.SkillData`. The inspected initializer's successful
path returns its original R0 argument. No instruction reassigns R0, and its
only call writes results into R2 and R3. Thus the source path stores the same
struct that it subsequently mutates, conditional on successful execution and
the inspected method bindings. This is object identity, not immutability,
activation or snapshot coherence.

The coordinate helper captures locations initially holding 100, 1000 and 6.
Its companion position helper also captures a location initially holding 5.
Assuming those values remain unchanged, the mathematical reading below applies
to modest, exactly represented integer inputs under the inspected instruction
conventions; the primary check used int32 inputs. These captured locations do
not establish immutable values or current runtime binding.

```text
F(k) = CalSkillTabIndex(k)
k < 100:          (k, 1)
100 <= k < 1000:  (t, k - 100*t + 1), t = floor(k/100)
k >= 1000:        (floor((k-1001)/6) + 6, r),
                  r = (k-1000) mod 6, replacing r=0 with 6

G(a,b) = CalSkillPos(a,b)
a > 5:           1000 + 6*(a mod 6) + b
a <= 5, b = 1:   a
otherwise:       100*a + b - 1
```

The modulo in `G` is a literal source operation. These functions are not
global inverses: `F(1) = F(100) = (1,1)`, while `F(1000) = (5,6)` and
`G(5,6) = 505`. Another collision is `F(6) = F(1001) = (6,1)`.
These are mathematical examples, not player keys. The conditional coordinate layer
preserves visible collisions rather than merging records or inventing a winner.
Valid UI domains, slot roles, ordinary-log wire types and runtime binding
remain unverified; the lexical reference layer remains unchanged. A separate
candidate graph applies these formulas only to canonical int32 lexical keys.

The initializer writes literal `IsActive=true`, including for the sentinel
reference. That constant is initialization, not evidence that an effect is
active. Neither inspected layout body explicitly reads `value.status`.
Struct defaults, metatable behavior, enum values and later readers remain
external dependencies. In particular, the string-sentinel path still does
not prove a missing `SkillData` value or an unequipped slot.

The source iterates with `pairs`. Duplicate item IDs and duplicate output
coordinates overwrite in traversal order, which a printed list does not
establish. A conservative importer must preserve ambiguity rather than select
the first or last visible record. An absent lookup yields nil under ordinary
table semantics; this is not permission to treat a missing printed item as absent.
Global lookup, helper implementations, metatables, rebinding and current
runtime selection remain prerequisites of the static interpretation.

## Check locations

Function paths and zero-based PCs refer to the saved diagnostic listing.

| Binding | Location |
|---|---|
| `CreateSkills` and `CreateSkillLayout` method assignments | main PC 36–40 |
| Constructor calls and dictionary argument flow | `main.5` PC 33–43 |
| Item dictionary key from `PlayerItem.Id` | `main.11` PC 26–27 |
| Key passed to external coordinate helper | `main.12` PC 8–11 |
| Initialized object stored at returned coordinates | `main.12` PC 20–26 |
| String sentinel and dictionary lookup | `main.12` PC 27–32 |

The follow-up helper listings use independent function-tree coordinates:

| Binding | Location |
|---|---|
| Coordinate/position method assignments | `SkillConstantMgr` main PC 24–29 |
| Captured initial constants | `SkillConstantMgr` main PC 20–23 and `main.6` / `main.7` upvalue descriptors |
| Key-to-coordinate branches | `SkillConstantMgr` `main.6`, 42 words |
| Position helper, including literal modulo | `SkillConstantMgr` `main.7`, 21 words |
| Initializer method assignment | `SkillMgr` main PC 45–47 |
| Direct return of original R0 | `SkillMgr` `main.14` PC 38 |

The [support-selection trace](support-selection-source.md) identifies the
native check and the later readers of these initialized fields. Effective skill level, activation and the unresolved
[raw damage calculation](attribute-calculation-source.md) remain separate
requirements; this trace supplies no numeric DPS.

## Ordinary import candidate graph

`logbuild.installation_graph` validates one saved event through the existing
reference projection, retains that exact projection and groups its visible
slot aliases by conditional `F(key)` coordinates. The normal log CLI includes
the graph in JSON version 0.1.1 and shows candidates, collisions and assumptions
in HTML. Events remain separate; missing graph data in older reports is shown
as unavailable.

The accepted arithmetic domain is the full int32 interval, including negative
keys and zero. This is a descriptor-based input bound, not a valid UI-slot
domain. Float, boolean, text, leading-zero and out-of-range lexical keys give
unavailable coordinates; missing, printed-empty and elided keys remain distinct.
Empty, missing or wholly elided collections do not invent rows. Visible
coordinate collisions retain every alias with an unknown winner. No inverse
helper, first/last choice or role inference resolves them.

The derivation assumes the captured initial constants remain 100, 1000 and 6,
the inspected operand conventions and method bindings apply, and the supplied
snapshot is unchanged during the call. The source's successful initializer
return establishes only its argument's identity, not runtime installation or
activation. Neither identical observations nor the graph prove atomicity.

Coordinates can reveal the numeric slot key; noninjectivity is not
anonymization. Their inclusion depends on the existing explicit `slot_key`
allowlist for `skillLayout.slots`. Revoking that path or field prevents
coordinate output. Raw item-instance `Id` and reference `skillId` tokens are
not exported by the graph. Reports remain local and private.

Numeric positions alone do not establish main, support or passive roles.
The inspected local-player readers use a separate `SlotType` configuration
and external support selection; those are not bound to this ordinary-log
view-player graph. Installation, activation, effective level, completeness,
currentness and raw-stat binding remain unknown. No Carino DPS gate is changed.

The [slot identity and reader trace](skill-slot-bindings.md) records the
distinct empty-string and `"0"` paths, the view-player readers and the
separate local-player configuration contract.
