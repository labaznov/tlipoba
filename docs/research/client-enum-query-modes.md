# Installed query-mode enum bindings

Checked 2026-10-24 using retained, hash-bound installed frames and data-only
inspection. No game instruction or enum constructor was executed. This is
source evidence; a shared current environment, runtime selection and SS14
applicability remain unverified.

The saved `GameEnum` frame is 185839 bytes, SHA-256
`b54b3864ac3d32c9e6e4eef70d0c381c6922281afa5ad67842708e37af72b316`.
It parsed to strict EOF as one function and 14834 instructions under the
existing explicit 512 KiB / 32768-record profile used for the protocol enum.
The public parser defaults were unchanged. Three smaller enum modules parsed
at defaults: 20296 bytes, six functions and 1162 instructions. A separate
412679-byte transformed candidate remains unparsed in that batch. The later
bounded Wolf inspection is recorded separately below.

## Mode and filter declarations

`GameEnum` main PCs 2600–2614 construct and assign these exact entries:

| `EParamIncreaseType` member | Literal value |
|---|---|
| `EBase` | `B` |
| `EIncrease` | `X` |
| `EMore` | `E` |
| `EValue` | `V` |

Main PCs 2548–2564 construct `EFilterType`:

| Member | Literal value |
|---|---|
| `ENoneType` | integer `0` |
| `EMinType` | `[min]` |
| `EMaxType` | `[max]` |
| `EInitType` | `[init]` |
| `EAbsType` | `[abs]` |

The declarations are followed by wrapping through the environment's `Enum`
function and reassignment to the same environment key: PCs 2615–2621 and
2565–2571 respectively. The register lifetimes preserve the declared table
through that call; the member names are not inferred from neighboring text.

## Constructor boundary

The separately inspected small `Enum` module exports child `main.2` as `Enum`.
That body creates an empty proxy, installs its retained read/write functions
into the supplied enum table and uses that table as the proxy's metatable.
It records the proxy's name in a private local registry and returns the proxy.
The read function uses raw lookup in that metatable. Thus the shown source
construction preserves the declared member values through functional lookup;
they need not be own raw fields of the returned proxy.

This conclusion requires the inspected constructor and ordinary helper
bindings at the call site. It does not prove that separate live modules share
that environment, that later code never replaces a binding, or that an
arbitrary native table pointer is this enum.

## Consequence for the calculation trace

Under those bindings, the mode literals in the
[attribute query trace](attribute-calculation-source.md) select its named
base, increase, more and value branches. This ties `X` and `E` to the source's
increase/more operations rather than guessing letters from English names.
It does not establish native pool membership, actual helper fields, effective
level or current character values.

An empty-string filter argument is **not** the declared integer `ENoneType`.
Do not replace it with zero or infer identical behavior without inspecting
the caller and branch path. Likewise, the filter names alone do not prove
the complete semantics of every getter. No imported value, engine formula
or DPS gate changes with this note.

## Attribute and damage declarations in Wolf

A later exact saved-entry read acquired the unencrypted `ExportWolfEnum`
payload, using 128436 installed-file bytes including its header and the checked
footer. The previously pinned isolated codec produced 134289 bytes; no global
installation or game instruction execution occurred. The transformed candidate
has SHA-256
`cfca817df6bf46aaeb377f29fad3f6c13d4879d03ec98c46952663bae728d809`.
After independent admission review, one data-only parse at that exact byte
budget and the unchanged 16384 instruction/list limit reached strict EOF:
one function, 8669 instructions and 4337 constants. Public defaults were
unchanged. Generated sources remain private.

The following seven complete constructor windows were independently checked
against their actual constant operands. PCs are zero-based positions in the
saved main-function listing. Each window constructs a fresh member table and
assigns it under the looked-up `wolf` value; none of these windows calls the
`Enum` constructor described above.

| Table | PCs | Literal member assignments |
|---|---|---|
| `EAttrType` | 1540–1551 | `EAttrType_none=0`, `EAttrType_attribute=1`, `EAttrType_field=2`, `EAttrType_label=3` |
| `EAttrModType` | 1552–1567 | `EAttrMod_none=0`, `EAttrMod_base=1`, `EAttrMod_floating=2`, `EAttrMod_incr=3`, `EAttrMod_incr_ext=4`, `EAttrMod_value=5` |
| `EAttrDataType` | 1568–1587 | `EAttrDataType_none=0`, `EAttrDataType_default=1`, `EAttrDataType_floating=2`, `EAttrDataType_increase=3`, `EAttrDataType_negetive=4`, `EAttrDataType_default_percent=5`, `EAttrDataType_increase_percent=6`, `EAttrDataType_only_base=11` |
| `EAttrArgsModType` | 1588–1596 | `E_none=0`, `E_additional=1`, `E_override=2` |
| `EDamageType` | 1470–1481 | `EDamage_attack=0`, `EDamage_spell=1`, `EDamage_over_time=2`, `EDamage_indirect=3` |
| `EDamageActionType` | 1482–1493 | `EDamageAction_melee=0`, `EDamageAction_projectile=1`, `EDamageAction_reflect=2`, `EDamageAction_abnormal=3` |
| `EDamageRangeType` | 1494–1501 | `EDamageRange_single=0`, `EDamageRange_area=1` |

The spelling `negetive` and the nonsequential `only_base=11` are literal source
facts. Name ordering and equal integers across tables do not establish equal
roles. These conditional assignments do not prove the actual environment,
destination-table behavior, later writes, runtime loading or SS14 applicability.

These declarations supply type names for further caller traces. They do not
map the numeric keys of
[`CPlayerData.attrs`](build-protocol-schema.md#build-and-stat-paths) to character
stats or establish units, modifier pooling, scope, conversion or floor rules.
In particular, `E_additional=1` is not evidence for the arithmetic of
`formulas.additional`, and `EDamageType` supplies no Physical/Cold element-ID
binding. No importer key or raw-DPS gate is promoted from this inspection.
