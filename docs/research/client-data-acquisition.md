# Installed client data as a formula source

Research observation, 2026-10-23. This route reads installed asset files; it
does not establish the selected character, current build or calculated DPS.

The public [tli-extract instructions](https://github.com/Sembiance/tli-extract/blob/f88a6e9e7a26a3da380a6fed77b1c243c200d42e/README.md)
describe encrypted Unreal containers, compiled Lua under `Content/Script/Luac`
and game tables under `Content/Script/Data`. They report that SS8 replaced
distributed CSV tables with serialized binary files. This is an extraction
lead, not evidence that an old-season table describes SS14. Its programs,
archives and decompiler were not executed or installed in this observation.

The pinned [CUE4Parse footer reader](https://github.com/FabianFG/CUE4Parse/blob/7353666098ece8ed8799fe467a33e7f68b11d688/CUE4Parse/UE4/Pak/Objects/FPakInfo.cs)
has a Torchlight-specific 225-byte footer layout with magic `0x6B2A56B8`,
three prefix bytes and an extra byte after the version. The numeric version
alone is not proof of the game's engine version. A standard-only parser's
failure therefore does not show that a file is not a pak container.

One bounded directory observation found 44 containers at the location derived
from an earlier observed image path. Reading 512 bytes from each consumed
22,528 bytes. All saved tails fit the source-defined Torchlight footer variant:
one matching magic per tail, numeric version 12, encrypted-index byte 1 and
index intervals inside the corresponding file bounds. Their index sizes range
from 2,144 to 1,203,312 bytes. Header interpretation alone does not validate an
index or its contents.

The separate offline tail analysis, including its final hash pass, consumed
141,480 bytes against a 128 KiB budget, exceeding it by 10,408 bytes. This
overrun did not add game-file reads; the 22,528-byte figure above counts only
the original game tails.

One subsequent read selected the smallest declared index. Its freshly read
225-byte footer matched the saved footer, and file size/mtime observations
agreed before and after reading the 2,144-byte encrypted index. These equal
observations do not prove atomicity or current-process identity.

A single historical [public asset-key report](https://www.gildor.org/smf/index.php?topic=8083.0)
supplied a candidate for an offline check. The already installed Node crypto
provider passed the AES-256 example vector from
[NIST FIPS 197 Appendix C.3](https://nvlpubs.nist.gov/nistpubs/FIPS/NIST.FIPS.197.pdf),
then decrypted the
saved copy. SHA-1 of the complete plaintext equalled the index hash in the
matched footer. This validates the candidate for this captured index; it does
not establish every container's key or authenticate any game session. Key
material and raw captured bytes remain in ignored local directories.
The crypto script checked its 64 KiB limit after loading the saved file;
the observed input was 2,144 bytes, so this is not a general enforced read cap.

The saved primary index declares 130 files and a separate 6,032-byte directory
index. Its range ends three bytes into the footer reader's skipped prefix;
the original 225-byte footer check was preserved. One bounded acquisition
consumed 6,257 game-file bytes for that directory interval and the fresh footer.
After decryption,
SHA-1 of the entire directory matched its reference in the verified primary
index. This supports the narrow overlap without inventing a general 222-byte
footer format.

A bounded names-only parse then found 130 unique names in 23 directories:
65 `.uasset` and 65 `.uexp` files. Relative names had no `Script/Luac/*.out`
or `Script/Data/*.bin` matches; the mount point was not applied to those counters.
Two remaining directory bytes are unclassified. Encoded entry offsets were
bounded but not decoded, and no payload was read. Another declared container
is the next candidate for README-style standalone script/table filenames;
embedded contents of the inspected assets were not examined.
The primary-index analysis also disclosed an extra diagnostic process without
a recorded PID; its entire process ledger cannot be independently confirmed.

A subsequent, separately bounded observation selected one declared base
container. Its 636,176-byte primary index and 1,774,272-byte directory index
both passed their complete plaintext SHA-1 checks. The two acquisitions,
including fresh matching footers, consumed 2,410,898 game-file bytes.
They opened no game process and made no UI calls.

The verified directory produced 39,705 unique names in 3,859 directories.
Relative-name matches included 3,659 `Script/Luac/*.out` files, 27,594
`Script/Data/*.bin` files and 79 files with the `.pb` extension. Eight trailing
directory bytes remain unclassified. These are names, not decoded contents.
Examples worth inspecting are `RoleCalculateMgr.out`,
`config_attributes_show_cal.out`, `config_attributes_ChunkA0.bin`, and
`proto/bd.pb`, `proto/bd_data.pb` and `proto/api.pb`. The last three are schema
candidates; filenames alone do not establish protobuf descriptors, an endpoint
contract, access rights or a working build-code import.

Some filenames refer to later seasons. Neither their presence nor the installed
container proves that a particular table or formula applies to SS14. A selected
entry still needs verified byte ranges, encryption/compression handling and
content interpretation before it can become a calculation source.

Nine selected compact entries were subsequently decoded against the pinned
directory query and primary-index hash. Five declared no compression or
encryption. A bounded read acquired their 22,031 payload bytes plus headers and
a fresh footer, consuming 22,526 game-file bytes. Each complete payload SHA-1
occurred at offset 29 in its own captured header. This is an observation of
these entries, not a general proof of header semantics or an atomic capture.

The three `.out` payloads were transformed using the XOR operation in the
pinned [extractor source](https://github.com/Sembiance/tli-extract/blob/f88a6e9e7a26a3da380a6fed77b1c243c200d42e/outToLua.py), without executing that tool or the resulting
bytes. They share a custom `01 XDI 11` prefix rather than a standard Lua
signature. Readable fragments include `RoleCalculateMgr`, `SkillCalculateMgr`
and `GetSkillDPS`. Fragments locate promising code; they do not establish a
function's behavior or its calculation formula.

Two further exact entries, `AttributeMgr.out` and `SkillCalculateMgr.out`,
were then read separately. Their combined payload size was 62,680 bytes;
headers and the fresh footer brought this acquisition to 63,013 game-file
bytes. Both complete payload SHA-1 values matched their own captured headers.
The same candidate transform produced the custom prefix and fragments
including `GetDpsEx`, `GetSkillDamageAttr` and `FSkillDamageData`. These remain
interpretation leads, with no game-code execution or recovered formula.

One saved 88-byte table payload contained a Zstandard frame beginning at
offset 16. The existing Git distribution's Zstandard library decompressed
that 72-byte frame into 148 bytes, matching the observed size field. No
library was installed. The [Zstandard API declaration](https://github.com/facebook/zstd/blob/v1.5.7/lib/zstd.h)
guided the bounded call. The result remains binary: column meanings, types
and game semantics have not been established.

The [bounded bytecode inspector](../CLIENT_LUA.md) subsequently parsed eight
saved script candidates to the end. It preserves data and instruction fields;
static interpretation located a presentation/delegation trace and a build
request boundary. The complete damage formula, protobuf schema, skill level
rule and stat aggregation operators remain unresolved. The public extractor's
archived decompiler was inspected as metadata without execution.
It complements the existing memory and log adapters; automatic build acquisition
and exact Carino DPS remain incomplete.

Two additional plain transport modules were acquired within an 11,460-byte
game-file budget, including headers and a fresh footer. Their own-header hashes
matched, and the public inspector parsed their 11,127 payload bytes without
execution. The inspected [NetObject wrapper](../CLIENT_LUA.md#findings-for-automatic-import)
forwards to `NetGameMgr.ReqMessageA2`; its lookup binding for the build manager,
the lower transport implementation and endpoint remain unresolved. This was file inspection,
without process-memory reads, UI input or server requests.
