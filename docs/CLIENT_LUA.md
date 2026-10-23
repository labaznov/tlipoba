# Saved client bytecode inspection

`damage_lab.clientlua.decode` reads already decoded XLUA11 bytes into a
diagnostic function tree. It preserves string bytes, binary64/int64 bits,
constants, debug fields and instruction words. Opcode labels and operand
fields follow the inspected archived parser. It does not execute instructions.

The framing was derived from fixed class metadata in the public
[tli-extract decompiler archive](https://github.com/Sembiance/tli-extract/blob/f88a6e9e7a26a3da380a6fed77b1c243c200d42e/unluac.jar):
custom signature/version, little-endian counts, string lengths, constant tags,
function lists, upvalues and locals. Our implementation uses Python's standard
library. The archived program was inspected as data without running Java.

By default, the diagnostic subset accepts contiguous byte buffers with at most
64 KiB of actual storage per input, depth 16, 256 functions, 16,384 elements per
list and 16,384 aggregate instructions. Callers inspecting larger saved tables
can explicitly pass `maximum` (1–524,288 bytes) and `limit` (1–32,768 records).
The record budget applies to every list and aggregate instructions; raising
the byte budget alone does not raise it. Both budgets require exact integers,
excluding booleans. The 64 KiB individual-string cap, tree limits and framing
checks stay fixed. A two-second
processing checkpoint is a soft limit. Negative counts, invalid reduced string
sizes, unknown tags/opcodes, nonfinite float constants, excess upvalue names,
main-upvalue disagreement and trailing bytes are refused. Debug line count is
not required to equal instruction count. Source provenance and input stability
belong to the caller; successful parsing does not establish a live game snapshot.

Sixteen synthetic tests cover the data contract and refusal cases. Independent
review found excess-upvalue-name and caller-reported buffer-length admission
gaps, each reproduced before its repair.
Real inputs remain ignored: nineteen hash-verified saved candidates, totaling
730,243 bytes, parsed to the end as 706 functions and 50,257 instructions.
Those observations establish compatibility with the diagnostic framing for
these files, rather than current-client VM semantics or SS14 applicability.

Larger function trees can instead use the separate
[outline inspector](CLIENT_OUTLINE.md). It preserves function spans and data
while validating instruction opcodes, without expanding instruction dictionaries.
Its independent budgets do not change `decode` or its defaults.

## Findings for further calculation work

Static interpretation under the pinned decompiler's operand conventions found
that the inspected `SkillCalculateMgr.GetSkillDPS` selects another method.
`GetDpsEx` obtains an attribute-ID list, calls
`ExportAttrShow:GetValue(id, item)` and sums the first returned value for each
included record. Its ordinary branch applies
`tonumber(string.format(info.Appearance, value))` to each component before
addition. The raw branch adds those values directly. The selector sorts records
by ascending `Id` and uses the first record whose configured tags all match.

This is a presentation/delegation trace. A later
[outline inspection](CLIENT_OUTLINE.md) identifies an installed Lua definition
of `ExportAttrShow.GetValue`. Its constructor assigns the global `AttrUtils`
to `self.Utils` and builds callback tables. `GetValue` selects
`self.FuncList[requestedId]`, calls `Utils:_SetCalcType(requestedId)`,
`:SetStoneItemId(secondArgument)` and `:_BeginCache()`, then invokes the selected
callback without arguments. The normal return path calls `:_EndCache()` and
`:_SetCalcType(nil)`. Those helper names do not establish their state effects.
If the callback is absent, the source returns `{0}`; that fallback does not
establish an observed zero-valued character stat.

A subsequent [attribute calculation trace](research/attribute-calculation-source.md)
checks helper selection, cache effects and six callback bindings. The installed
`10103` getter sums five component queries and applies a rate and critical
expectation. Substitution of displayed damage and chance values for those
queries remains unverified. Native helper implementations, selected runtime
context, base-damage aggregation and effective level remain open; exact combat
DPS is not established.

## Findings for automatic import

The inspected build manager routes its share-code flow to `ReqGetBDContent`.
That method constructs a `bdId` request and invokes `ReqGameMessageA2` with
the `GetBDContent` operation and callbacks. The successful display callback
passes `bdContent.bdData` to `ViewPlayerMgr.CreateViewPlayerData`.
The neighboring `TransServerBDContentToClient` method concerns strategy
descriptors; it must not be mistaken for the equipment/build-data decoder.

Two further saved modules, `NetObject` and `NetMsgMgr`, totaled 11,127 payload
bytes. Their complete SHA-1 values matched their own captured headers; the
public inspector parsed them as 30 functions and 564 instructions without
execution. In `NetObject`, `ReqGameMessageA2` obtains a result callback through
`NetDispatchMgr.DispatchMsg`, then delegates to `NetGameMgr.ReqMessageA2`.
The inspected `NetMsgMgr` coordinates child managers and does not supply that
method's implementation. Separate HTTP wrappers also exist; their URL helpers
do not establish the transport used by the build request.
The lookup binding from the build manager's inherited method to this
`NetObject` body also remains unverified.

Three further scripts, `NetGameMgr`, `NetDispatchMgr` and `MgrObject`, supplied
36,918 hash-verified payload bytes. They parsed separately as 78 functions and
2,185 instructions. The inspected `NetGameMgr.ReqMessageA2` resolves an operation
name through `ProtoEnum.ProtoId`, then calls `protobuf.encode` with the selected
record's `req` schema name and the original parameters. It places those bytes
and their length in a `game.ProtoMsg`, calls `self.NetGame:SendLua_A_2` with a
flag, protocol ID and callbacks, and retains the returned sequence ID.

The saved registration declarations name `MgrObject` as the build manager's
base and `NetObject` as `MgrObject`'s base. This narrows the static lookup lead;
registry semantics and actual runtime method selection remain unverified.
The descriptor, flag meanings and the implementation below `SendLua_A_2`
are still missing.

The larger saved `ProtoEnum` table used explicit 512 KiB / 32,768-record
budgets. Its 392,928 bytes parsed to the end as one function with 29,802
instructions and 8,850 constants. Static inspection of its straight-line
initializer binds `ProtoEnum.ProtoId["GetBDContent"]` to `30001`, and that
numeric entry to `name="GetBDContent"`, `req="rpc.GetBDContentReq"` and
`ack="rpc.GetBDContentAck"`. Register lifetimes and all uses of the two
operation constants were checked through the table assignment. A separate
`GetBDContentV2` entry exists; these names must not be interchanged. This is
an installed source declaration, not proof of the current runtime table or
the server's accepted schema. A later
[partial descriptor projection](research/build-protocol-schema.md) supplies
field declarations, with dependency and runtime gaps preserved.

The saved `ViewPlayerMgr` parsed as 39 functions and 1,030 instructions.
Its `CreateViewPlayerData` constructor reads the supplied value's `baseInfo`
and `featuresInfo`, delegates equipment, skills, layout, hero and talent
conversions to helpers, then assigns `result.ServerSource = RecvData`.
The body does not decode protobuf bytes. This identifies a source-preserving
page field, but does not establish `bdData`'s wire type, helper semantics,
effective skill level, completeness or selected-player identity.

Three further modules trace the item-level constructor, upgrade-state query
and `table.readonly` proxy. The constructor assigns `PlayerItem.Level or 1`;
the proxy retains its input as `_Raw_Data` rather than copying it. The
[skill-level source trace](research/skill-level-source.md) distinguishes this
observed item level from effective level and experience requirements, with
uninspected dependencies and runtime selection left open.

This identifies a client request boundary. Wire types, transport framing,
authentication and an independently callable endpoint are unverified. No server
request was made. The ordinary player importer and exact DPS gates are unchanged.
