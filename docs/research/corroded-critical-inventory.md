# Corroded Lucky Critical Strike and critical damage

Verified 2026-10-23 against saved SS14 catalog and native-source evidence.
Compiler `0.4.3` and bundle `0.1.3` preserve one compound affix as one row;
the consumer also retains the earlier supported contracts.

The admitted case is native modifier `51434430` in
`legendaries/gloves/dex_gloves/master`, through the corroded template
`Lucky Critical Strike\n+#% Critical Strike Damage`. The checked catalog member
has SHA-256 `5ed5f6dcd02e335e93130d6fc10ce0ad40d9b865c252ccefe7d5b14d48ba89cc`.
The normal template contains only Lucky Critical Strike and supplies no numeric
value for this compound.

The producer requires an exact item and unique native definition, PrefixInfoList,
the exact corroded template, one own value in the declared range, one literal
`+`/`%` specification and empty native Condition, Filter and Behavior containers.
Other templates, lists, resolved variant pools and malformed specifications are
refused. Earlier modifier rules are unchanged.

The row's family is `lucky_critical_damage_modifier`. Its one numeric percent
value belongs to critical damage; the separate `lucky_critical_strike: true`
semantic preserves the Lucky Critical Strike literal. It is neither a chance
percentage nor evidence of activation. The template sign is null because the
whole template starts with Lucky; its numeric second line carries the plus sign.
The stacking operation and variant pool remain unresolved, and
`arithmetic_ready` remains false.

The consumer checks the paired versions, source/catalog binding and mandatory
literal bool, including canonical revalidation. Old critical rows cannot silently
discard a Lucky flag. Ordinary critical, cast evidence and the paired wand
master/English fixed-implicit proof remain supported under compiler `0.4.3`.

The compound survives automatic import, SQLite, JSON and all three HTML views.
The input assembler keeps the entire row in `excluded` with `family_not_mapped`;
it does not create a complete critical pool, effective level or calculated DPS.

An offline copy of a historical Carino package passed 18 checks through the
ordinary import, inputs and calculation CLI routes. Exactly one prior omission
became this compound; the other modifiers and omissions were preserved, and the
previous conditional calculation was unchanged. The original package was not
modified. This verifies saved-source integration, not a fresh capture, current
character selection, atomicity or activation. Complete raw damage, critical and
casting groups remain unavailable.
