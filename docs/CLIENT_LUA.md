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

The diagnostic subset accepts contiguous byte buffers with at most 64 KiB of
actual storage per input, depth 16, 256 functions,
16,384 elements per list and 16,384 aggregate instructions. A two-second
processing checkpoint is a soft limit. Negative counts, invalid reduced string
sizes, unknown tags/opcodes, nonfinite float constants, excess upvalue names,
main-upvalue disagreement and trailing bytes are refused. Debug line count is
not required to equal instruction count. Source provenance and input stability
belong to the caller; successful parsing does not establish a live game snapshot.

Ten synthetic tests cover the data contract and refusal cases. Independent
review found excess-upvalue-name and caller-reported buffer-length admission
gaps, each reproduced before its repair.
Real inputs remain ignored: eight hash-verified saved candidates, totaling
124,209 bytes, parsed to the end as 275 functions and 7,563 instructions.
Those observations establish compatibility with the diagnostic framing for
these files, rather than current-client VM semantics or SS14 applicability.

## Findings for further calculation work

Static interpretation under the pinned decompiler's operand conventions found
that the inspected `SkillCalculateMgr.GetSkillDPS` selects another method.
`GetDpsEx` obtains an attribute-ID list, calls
`ExportAttrShow:GetValue(id, item)` and sums the first returned value for each
included record. Its ordinary branch applies
`tonumber(string.format(info.Appearance, value))` to each component before
addition. The raw branch adds those values directly. The selector sorts records
by ascending `Id` and uses the first record whose configured tags all match.

This is a presentation/delegation trace. The implementation of
`ExportAttrShow.GetValue`, the applicable attribute records and their relation
to Carino's observed panel remain open. Its name alone does not establish a
native implementation. These findings do not supply base damage, critical
aggregation, effective skill level or exact combat DPS.

## Findings for automatic import

The inspected build manager routes its share-code flow to `ReqGetBDContent`.
That method constructs a `bdId` request and invokes `ReqGameMessageA2` with
the `GetBDContent` operation and callbacks. The successful display callback
passes `bdContent.bdData` to `ViewPlayerMgr.CreateViewPlayerData`.
The neighboring `TransServerBDContentToClient` method concerns strategy
descriptors; it must not be mistaken for the equipment/build-data decoder.

This identifies a client request boundary. Wire types, transport framing,
authentication and an independently callable endpoint are unverified. No server
request was made. The ordinary player importer and exact DPS gates are unchanged.
