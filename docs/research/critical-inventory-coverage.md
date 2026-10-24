# Remaining critical-stat inventory gaps

Research observation, 2026-10-23. This audits one historical automatic-import
artifact; it does not establish current equipment, activation or a complete
critical pool. Private values and source files remain ignored.

The artifact accounts for 69 rows across 10 items: 21 typed rows, 48 omissions
and no structural gaps. Six typed rows concern critical stats: three critical
damage, two increased critical rating and one compound Lucky/critical damage.
Their presence does not resolve their arithmetic operators.

All 48 omissions were checked against eight exact, hash-verified declared
catalog slices. Item binding required both the exact catalog GUID and full
TLIDB ID to identify the same unique item within each inspected member.
Uniqueness outside these eight members was inherited from the compiler,
not independently rechecked.

| Initial omission classification | Rows | Limitation |
| --- | ---: | --- |
| Explicit critical wording | 1 | Tangle-specific rating, not a player-wide pool |
| Other wording | 33 | No Crit/Critical regex match, not proof of no indirect effect |
| Implicit without text keys | 8 | Absence checked only in the exact item/implicit key sets |
| Corroded template key absent | 1 | Normal template was not substituted |
| No definition in compiler lookup | 5 | Other catalog fields were not searched |

The explicit Tangle line is native modifier `51528541`, whose template is
`+# Tangle Critical Strike Rating`. Tangle scope/topology still needs binding.

A separate exact master/English-twin check resolved the wording of four
omitted wand rows. Native `750000` renders as `500 Critical Strike Rating`;
`750001` renders as `1.2 Attack Speed`. These are fixed catalog base attributes,
not verified character rolls. Their own native argument values were not read.
The text itself does not establish spell scope or an attack-speed unit.
The weapon's rating must not be substituted for a spell's base rating merely
because both catalog descriptions happen to mention 500.

An English-twin follow-up resolved two more rows. The historical artifact did
not declare that ring member, so a separately budgeted pass inspected one
1,525,554-byte public catalog wrapper and recorded new member coordinates and
hashes. Its span pass transiently decoded all top-level values; subsequent
field inspection selected only the ring member. Independent verification read
the exact 46,937-byte English and 82,272-byte master slices and checked their
complete hashes before binding both item identities and native IDs.

Ring implicit `680004` renders as `+11% Fire Resistance`, and `680005` as
`+12% Fire Resistance`. Their fixed catalog specs agree with that text; the
target rows' own roll fields were not inspected. Neither text explicitly
mentions critical stats, which does not prove the absence of an indirect interaction.

A similarly bounded follow-up resolved belt `660002` as `+35 Max Life` and
boots `600011` as `+146 gear Energy Shield`. Exact master/English identities
and fixed catalog bounds matched; one native implicit per member was observed
in that run. The whole typed artifact was decoded, but the two target rows'
own roll/DynArgs fields were not inspected or output and their rolls remain
unknown. These descriptions contain no explicit critical wording; indirect
effects and mechanical scope remain unresolved. Six omitted rows still have
unknown wording. Legendary base attributes and enchants also
require a lookup contract beyond the compiler's current fields.
Talents, hero traits, supports and temporary buffs remain separate coverage
dependencies. No row was promoted into the damage model by this research;
exact critical stats and total Carino DPS remain unresolved.
