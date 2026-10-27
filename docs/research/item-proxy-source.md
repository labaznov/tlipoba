# Item proxy and input-record boundaries

Checked 2026-10-25 against saved installed `Table`, `Struct` and `ItemMgr`
scripts and the local exporter's projection code. This is static evidence.
Module resolution, hotfixes, current actor, selected build and atomicity remain
unverified. Raw sources and player captures stay private.

## What `_Raw_Data` identifies

The exporter requires `_Raw_Data` as a decoded string key with a table reference;
it does not manufacture that key. Missing or unsupported references fail the
item projection. This describes the producer's behavior, conditional on its
native Lua layout and decoder identifying the real objects correctly.

In the inspected `table.readonly`, the fresh-proxy branch stores the supplied
table directly in `Proxy._Raw_Data`. It does not copy that table. Non-table
inputs and tables with an already truthy raw `_Raw_Data` field pass through
unchanged, so the alias conclusion is conditional on taking the fresh branch.
Nested table reads use cached child wrappers; the cache compares the cached
wrapper's `_Raw_Data` with the current table using Lua equality. A possible
`__eq` metamethod prevents treating that as an unconditional pointer check.
`_ReadOnlyTa` and the wrapper methods are not item
statistics.

`NewStruct` returns a new Lua table, fills non-function defaults through the
global `Clone` helper and assigns a shared prototype as its metatable.
The inspected helper does not itself introduce `_Raw_Data`; the `FItemData`
defaults and the global clone behavior are still separate unknowns. A table
return type alone does not establish the fresh readonly branch.

## Normalized fields and the input item

`ItemMgr.CreateItem` supplies its newly constructed record to `_UpdateItemData`,
then to `table.readonly`. The inspected update path assigns `ServerPlayerItem`
from the supplied warehouse wrapper's `Item` reference. It also assigns `Level`
from `Item.Level or 1`. Missing or false input can therefore become one; Lua
zero is truthy and is retained by that expression. A normalized level of one
alone does not prove that the input explicitly contained one.

Keep these namespaces separate:

| Field | Inspected source relation |
|---|---|
| `ItemData.ItemId` | Copied from the input item's `Id` |
| `ItemData.ConfigBaseId` | `tonumber` of input `BaseId`, with zero fallback |
| `ItemData.Level` | Input `Level`, with the fallback described above |
| `ItemData.ServerPlayerItem` | Input item reference at the update assignment |
| `ItemData.SpecialInfo.SkillId` | Config `ItemBaseInfo.Skill.Key` |

These relations do not identify the current runtime object or establish an
effective combat level. The proxy field name alone is not server provenance.
An original-record reader must inspect the actually available nested record
and retain absent, conflicting or unsupported evidence explicitly.

## Mutation and copies

The factory's update closure keeps the underlying record and passes it back to
`_UpdateItemData`; the proxy is not an immutable snapshot. Readonly's `Update`
and `Add` methods also write to the underlying table.

The factory-specific `DeepCopy` temporarily sets the original record's
`ServerPlayerItem` to `-1`, calls a copy helper, restores the input reference on
both records and wraps the copy. That reference is shared, not independently
copied. Restoration is not protected against intervening errors. A future
original-record reader must treat `-1` as a non-data marker, not an item or a
zero-valued fallback.

Equal input references or equal values across copies do not prove currentness,
selection or atomicity. These source relations improve acquisition provenance;
they do not close the [runtime attribute and DPS boundaries](attribute-calculation-source.md).
