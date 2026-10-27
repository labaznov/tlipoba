# XLUA11 function outline

`damage_lab.clientoutline.outline(data, *, functions=2048)` is a separate,
data-only diagnostic for
the source-derived XLUA11 subset described in [CLIENT_LUA.md](CLIENT_LUA.md).
It accepts an already supplied contiguous buffer and returns a function index.
It does not read files, contact services, execute instructions or change
`clientlua.decode` and its defaults. It is not wired into ordinary build import.

```python
from damage_lab.clientoutline import outline

result = outline(captured_bytes)
```

The default function budget remains 2,048. A caller may explicitly choose
`outline(captured_bytes, functions=4096)`. The keyword accepts only an exact
integer from 1 through 8,192; booleans are refused before input admission.
8,192 is a fixed opt-in ceiling, not automatic adaptation to an input. A larger
function budget changes no other limits or `clientlua.decode` defaults and does
not guarantee that an input fits the remaining budgets or processing deadline.

The result has `format="xlua11-outline"`, `version="0.1.0"`, `bytes`,
`functions`, `instructions`, `executed=False` and `index`. Records appear in
deterministic preorder: `main`, `main.0`, its descendants, then `main.1`.

Each record contains:

- `path`, `begin` and `end`: a half-open function byte span, starting at its
  source-string length prefix and ending after its upvalue-name list
- `codeOffset` and `codeCount`: the byte offset of the first instruction word
  and the number of four-byte little-endian instruction words
- `source`, `lineBegin`, `lineEnd`, `parameters`, `vararg` and `stack`
- `constants`, `upvalues`, `upvalueNames` and direct `children` paths
- `debugLines` and `debugLocals`: counts of consumed debug records

Offsets are relative to byte zero of the supplied buffer view, not an enclosing
allocation or process address. A parent's span encloses its descendants; sibling
spans are disjoint. Every instruction opcode is checked against the existing
47-label map, but instructions are not retained as expanded dictionaries.
Debug line integers and local names/boundaries are consumed without retaining
their arrays. This does not validate VM operand semantics, register lifetimes,
local-variable ranges or relationships between debug and instruction counts.

Strings remain detached raw bytes, without decoding, source-name inheritance or
path interpretation. Finite floating-point and signed integer constants retain
their original eight-byte `bits` as lowercase hex. Upvalues preserve `raw` and
`index` bytes as well as the diagnostic `instack=bool(raw)` projection; this does
not narrow the reference grammar to raw bytes zero and one. Upvalue names may
be fewer than their records, but cannot exceed them. The header's main-upvalue
count must equal the main function's record count. Trailing bytes are refused.

| Limit | Admission |
|---|---:|
| Actual input view storage | 2,097,152 bytes |
| Function depth, main at zero | 16 |
| Functions | 2,048 by default; explicit exact integer 1–8,192 |
| Records in each encoded list | 65,536 |
| Aggregate instructions | 131,072 |
| Aggregate constants plus upvalue records | 131,072 |
| Bytes in one reduced string | 65,536 |
| Aggregate retained source/constant/upvalue-name string bytes | 2,097,152 |

Counts and aggregate reservations are checked before the corresponding loops or
allocations. The byte cap uses the buffer's actual `nbytes`, including contiguous
multibyte views; a misleading Python `len` does not change admission.
Unsupported and noncontiguous buffers are refused. Byte/string limits are not
limits on total Python object memory or a serialized report's size. Increasing
the explicit function budget can retain more function metadata and child paths.

Each retained wire string is copied once. Consequently, exceeding the aggregate
retained-string cap is already excluded by the equal input byte cap and framing
overhead; the explicit counter preserves that limit. Discarded debug strings
still pass the per-string and input-boundary checks.

A shared monotonic deadline is checked before field spans, during opcode
validation and after constructing the final result. It allows two seconds of
processing after buffer admission and is a soft checkpoint budget, not a hard
wall-clock interruption. Rejected input raises `ValueError` and returns no
partial index. The caller must keep a mutable input stable during inspection;
this parser does not provide an atomic snapshot.

The public tests use only generated synthetic buffers. They cover literal
offsets, retained metadata and numeric bits, nested functions, actual storage,
large admitted inputs, fixed limits, malformed framing and deadline refusals.
A small differential control checks compatibility with `clientlua.decode`.
These checks do not establish applicability to any particular installed game,
current runtime, character, formula or effective skill level.

One private hash-verified saved candidate subsequently passed this framing
inspection to the end: 1,191,689 bytes, 2,756 functions and 106,937 instructions,
with an explicit `functions=8192` budget. Its earlier default-budget attempt
was refused at 2,048 functions; that partial index was not accepted. The caller
separately pinned acquisition, decoding and saved-input hashes. This observation
establishes diagnostic framing compatibility, not runtime method selection,
SS14 applicability or a recovered damage formula.
