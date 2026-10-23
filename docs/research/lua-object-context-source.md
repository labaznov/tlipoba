# Object construction behind the attribute context

Checked 2026-10-23 from saved installed source, without game-code execution,
new process-memory reads or UI input. Three additional modules, `LuaClass`,
`LuaObject` and `LuaObjectMgr`, supplied 28,899 payload bytes. Each complete
payload matched the SHA-1 in its own captured header. At unchanged default
limits, the diagnostic inspector parsed them to the end as 48 functions and
1,876 instructions. This checks saved framing, not live VM bindings.

## Registration and construction

The inspected `LuaClass` initializer assigns its local functions to environment
names `RegistClass` and `NewObject`. `RegistClass` writes `__ClassName` on the
supplied class table and conditionally installs the superclass as its metatable.
It returns that class; the caller makes the environment assignment.

`NewObject` calls `table.deepcopy(class)`, enables declaration writes on the
copy, invokes constructors, disables declaration writes and returns the same
copy. Constructor return values do not replace it. The separately inspected
`Table` implementation allocates a new Lua table for a table input, recursively
copies entries, and recursively copies and installs its metatable. A non-table
input is returned unchanged. Normal completion is a premise: this body does
not establish cycle-safe copying for arbitrary table graphs.

Under these bindings and successful completion, construction from the inspected
AttrUtils class returns a **Lua table with a copied metatable chain**. It does
not establish a userdata root. Fields of that table may still contain native
userdata or functions. The proof supplies neither a live address nor the
current runtime environment, table ABI or selected-player identity.

## Field lookup is a separate boundary

Declaration toggling walks the copied metatable chain and selects function
values for `__index` and `__newindex`. The read helpers use `rawget` on the
object, then on successive metatables. The write helpers update an existing
own or inherited slot; the constructor's allow-write path creates an own slot
when none exists. Consequently an ordinary field lookup cannot generally be
replaced by following a table-valued `__index`. An inspector must not execute
these functions to obtain a value.

Constructors traverse the copied ancestor chain before the leaf constructor.
They can mutate fields and metatables or fail. Root table construction does
not by itself identify which copied table owns a particular field.

## The AttrUtils caller creates two contexts

The already inspected `AttrUtils` initializer retains the result of
`RegistClass('AttrUtils', methods, LuaObject)` in a local register. Its factory
captures precisely that class and tailcalls environment `NewObject` with it.
The initializer calls the factory once for environment `AttrUtils`, then again
for the first context's `MercenaryContext` field. Under the normal allocation
path, these are distinct tables with the same copied class-name profile.

The constructor assigns helper, player and stone placeholders and allocates
caches. Those initial placeholders are not observed live values. Class-name
agreement alone cannot distinguish the primary context, secondary context,
prototype or another copy, or prove helper readiness and cache freshness.

`LuaObjectMgr.SmartNewLuaObject` has a separate map-retention path after calling
`NewObject`. The inspected AttrUtils factory does not call that manager method;
the manager's map is therefore not a demonstrated owner of AttrUtils.

The source supports investigating a validated named-key/table-owner route.
Such a route still needs bounded complete acquisition, native layout checks,
explicit ambiguity and read-gap handling, and a verified reference to the
correct environment. No global uniqueness, atomic snapshot, current character,
active helper or raw DPS gate is established by these source bodies.

## Static check locations

| Script | Function | Checked source |
|---|---|---|
| `LuaClass` | `main` | PC 69–72: environment helper bindings |
| `LuaClass` | `main.10` | PC 28–37 and 117: class name, superclass metatable and return |
| `LuaClass` | `main.11` | PC 22–41: deepcopy, declaration phases, constructor and retained return |
| `Table` | `main`; `main.18` | PC 54–56: deepcopy binding; PC 0–34: allocation, recursion and returns |
| `LuaClass` | `main.7`; `main.3`–`main.6` | Declaration toggles and functional raw lookup/write paths |
| `LuaClass` | `main.8` | Ancestor and leaf constructor calls |
| `AttrUtils` | `main`; `main.42`; `main.0` | PC 128–140: two factory calls; captured class; PC 0–35: constructor |
| `LuaObjectMgr` | `main.5` | PC 25–51: separate smart-construction and map retention |

This extends the [attribute source trace](attribute-calculation-source.md).
The ordinary import contract and all exact-calculation gates remain unchanged.
