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

No formula, protobuf schema, skill level rule or stat aggregation operator has
yet been recovered by this route.
It complements the existing memory and log adapters; automatic build acquisition
and exact Carino DPS remain incomplete.
