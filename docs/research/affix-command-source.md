# Installed affix command conversion

Checked 2026-10-24 against three exact source-named files in the previously
verified saved directory index. The three acquisitions read 129,977 installed
file bytes including headers and footers; all complete payload SHA-1 values
matched their own headers. Extracted source, listings and player files remain
private. No game instructions, process memory, UI input or server requests were
executed for this work.

The 85,466-byte `AffixLinkerMgr` module exceeded the diagnostic parser's default
65,536-byte admission. One independently reviewed call admitted exactly the
pinned length within the existing hard ceiling. Other parser limits and public
defaults stayed unchanged. The smaller component and factory parsed at defaults.
Together these captures contain 187 functions and 7,378 instructions; only the
specific bodies below support these findings. Soft processing deadlines and
post-generation output limits do not establish a hard peak-memory bound.

These are conditional static facts under the inspected Lua operand convention.
Matching file metadata is not atomicity, runtime registration, current player
identity or SS14 applicability.

## The forwarding chain

The previously inspected `AttributeMgr` collectors pass whole affix rows to
`AffixLinkerMgr.CreateAffixDynArgs`. Their general collector visits `BaseAffix`,
`Prefix`, `Suffix`, `SlotAffix`, `EnchantAffixs` and `ChipAffix` using `ipairs`;
base-attribute and fixed lists have separate collectors. A non-nil returned
value is retained; this alone does not establish an active modifier or its units.

`AffixLinkerMgr.CreateAffixDynArgs` obtains `self:GetMiddleComponent()`, calls
that value's `Equip_CreateAffixDynArgs` with the original argument, and returns
one result. Its seven instructions do not read affix fields or perform numeric
mapping.

The component getter calls its captured validation function on
`self.AffixMiddleComponent`. A truthy result returns the cached field. Otherwise
it assigns the result of `LuaObjectMgr:SmartNewLuaObject(self:GetObjectId(),
'AffixMiddleComponent')` and returns the field without a second validation.
A separate pinned projection of closure descriptors binds the getter's first
upvalue to root register zero, which holds the local validation closure in the
inspected root body. The environment and object factory remain runtime unknowns.

The saved `AffixMiddleComponent.Equip_CreateAffixDynArgs` asks
`self:_NewAFactory('AffixDataFactory')`, forwards the original argument to that
object's method of the same name, calls `_FreeAFactory`, and returns its saved
result. The inspected factory helper caches by the original factory-name key
and creates only when that entry is nil. Its `_FreeAFactory` body contains only
a return; calling it does not prove cleanup or a fresh object on the next call.
The class-registration and object-factory implementations are not verified here.

## The factory body

`AffixDataFactory.Equip_CreateAffixDynArgs` has 42 instructions:

1. Read the argument's `Id`; when it equals nil, return nil
2. Otherwise call `wolf.FModifierDynArgs()` with no arguments
3. Read `Id` again and assign it to the result's field named `ModifierId`
4. Iterate `pairs(argument.DynArgs)` into a new local table
5. For a value whose `type` equals `table`, iterate one additional `pairs` and
   insert those values; otherwise insert the original value
6. Assign that table to the result's `DynArgs` field and return the result

The constructor and setters are external. Their concrete types, conversions,
validation and side effects remain unknown. The nil gate is not a general row
validator: indexing an invalid argument can fail before it. Under ordinary Lua
`pairs`, a nil `DynArgs` fails at the iterator-creation call, after construction
and the first output assignment.

This body flattens one table level, not recursively. It does not establish
the order of `pairs`, map argument positions to numeric meanings, or choose a
duplicate winner. It directly reads only `Id` and `DynArgs`; that limited
observation does not rule out other fields or context reaching external code.

There is no direct arithmetic, catalog lookup or decimal-restoration helper
call in these 42 instructions. Such helpers elsewhere in the module must not
be applied to this path without a traced binding. Copying a property into a
field named `ModifierId` does not equate an affix ID with the native attribute
IDs used by stat queries or the keys in the imported raw attribute block.

## Import and calculation consequence

The [ordinary log projection](../LOG_BUILD.md) now retains the previously
omitted equipment base/slot/chip lists and six skill/dressed-skill families as
lexical evidence. It keeps source paths, separate occurrences and explicit
missing/elided states; it does not execute this factory or compile effects.
Its current flat-array subset deliberately refuses broader nested/non-array
shapes rather than guessing how to flatten them.

One pinned historical printed log contains visible equipment `BaseAffix` and
skill/dressed `Prefix` rows omitted by the earlier allowlists. The inspected
visible arguments were flat arrays; hidden rows and future schemas remain
unknown. This is evidence for extending acquisition, not a complete character
or current-runtime claim.

Before numbers become damage inputs, the resolver still needs positive
bindings from modifier definitions and argument positions to attribute identity,
units, grouping and the actual consumer. The traced command arguments alone
do not resolve activation, effective skill level or exact Carino DPS.

## Primary check locations

Paths and PCs below refer to the private saved source listings, not executed
runtime observations. The pinned parsed-module SHA-256 values identify the
primary projections used by the review.

| Module | Parsed-module SHA-256 | Function / zero-based PCs |
|---|---|---|
| `AffixLinkerMgr` | `a6e2f63ba0fdc1a1ef8e55f7d5d8ab4939c3f16c60d889028066783a1624b941` | Root 23–25 binds getter child 8; 236–238 binds conversion child 79; child 79 0–5 forwards |
| `AffixLinkerMgr` | Same projection | Ctor child 3 0–8; local validation child 0 0–9; getter child 8 0–13; root 317–328 registration/return |
| `AffixMiddleComponent` | `f83beeefafec7af9341e32852b7c68e7026fe9c0a0d858e80d7689bb2bf97a5c` | Root 42–43 binds child 21; child 21 0–9 forwards |
| `AffixMiddleComponent` | Same projection | Root 62–63 binds factory child 31; 64–65 binds child 32; child 31 0–16 cache/create; child 32 0 returns |
| `AffixDataFactory` | `ffb6932e3c6d109b53aa1ef5e9231da98f551ba3675d0a2622cd05c59631781a` | Root 39–40 binds child 19, 55–61 registration/return; child 19 0–2/39–40 nil gate, 3–7 constructor/ID, 8–38 argument collection/return |

The closure-capture selection is SHA-256
`f8b23c288f2108f562a221c3858a55ff47443926b9897b6b17a03b8f36a43967`.
For the upstream collector, `AttributeMgr` child 10 contains the six general
list loops, and children 11/12 contain separate base/fixed loops. The
[support-source note](support-selection-source.md) documents that module's
shared acquisition and runtime limitations.
