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
412679-byte transformed candidate remains unparsed in this batch; the
compressed Wolf enum was not acquired.

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
