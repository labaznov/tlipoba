# Диагностический inventory эффектов установленных поддержек

`supportinventory.project(raw, source_sha256)` принимает только вложенный результат
helper `support_effect_inventory` 0.2.0 (`tli-installed-support-effects-v0`),
`inventoryVersion=0.1.2`, `effectsVersion=0.2.0`. Функция не читает source,
каталоги, manifest, файлы или игру. Она проверяет утверждения артефакта и строит
отделённую проекцию; исходный matcher повторно не запускается.

Канонический `format` — `tli-installed-support-effects-canonical-v1`. Поля имеют
snake_case, `version=0.2.0` сохраняет версию producer. `summary(canonical)` повторяет
валидацию и удаляет неизвестные свойства на каждом уровне.

Верхние поля: `format`, `version`, `inventory_version`, `effects_version`,
`source {sha256, binding}`, `arithmetic_ready`, `runtime_verified`,
`identity_verified`, `import_complete`, `activation`, `patch`, `effective_level`,
`client_layer`, `server_layer`, `members`, `accounting`, `limitations`.
SHA должен быть lowercase hex и точно совпадать с аргументом. Binding остаётся
`caller_supplied_document_only`: совпадение не доказывает, что producer прочитал
именно эти bytes. Верхние flags всегда false, activation/patch unknown,
effective_level null. Неизвестный client layer сохраняет members и counts как null.

Член содержит `alias`, `group`, `tab_position`, `group_status`, `slot`, `path`,
`base_id`, `gem_level {value, meaning}`, `category`, `status`, `reason`, `effects`.
Безопасные aliases и координаты сохраняют порядок client tabs; повторяющиеся
слоты запрещают affected eligible member стать candidate. Остальные уникальные
слоты того же конфликтного tab могут оставаться candidates с видимым group_status.
Accounting проверяет `members = effect_candidates + excluded + gaps` и literal
`reconciles=true`; bool не является числовым count.

Только `noble_support`, `magnificent_support`, `activation_medium` могут иметь
`status=effect_candidates`. У gap/excluded `effects=null`; неизвестные или
неподдержанные эффекты не превращаются в полный пустой набор.

Вложенный формат — `tli-support-effects-canonical-v1`, версия 0.2.0. Сохраняются
known identity, prefix accounting, rolled_lines, omissions, catalog constants и
constant_issues. Identity/base/category должны совпадать с member, catalog_schema
должен быть ok. Все runtime/arithmetic утверждения остаются false/unknown, а
additional_group_identity unresolved. Catalog literals и native rolls не смешиваются.

Вложенные known поля: `identity {status, catalog_tlidb_id, native_base_id, category,
guid}`, `prefix {status, rows, null_rows}`, `rolled_lines`, `omissions`, `constants`,
`constant_issues`, `catalog_schema` и диагностические flags. Rolled line:
`origin, path, line_id, native_id, tier, role, unit, template, values, native_version,
status`; value: `exact, fraction, range {min, max}`. Omission:
`origin, path, reason`; constant: `origin, source {field, line}, kind, parameters,
status`; constant issue: `source {field, line}, reason`.

Роллы сохраняют lexical exact/fraction/range, полный public native ID, line ID,
заявленный tier, относительный prefix path и unverified native_version. Проверяются
два известных точных templates, их role/unit, диапазон и точная fraction. Это
валидация переданного результата, **не повторный join с исходным tier definition**.
Constants принимаются только из фиксированного набора `supporteffects.CONSTANTS`,
с field `templateDescription` и индексом LF-строки с нуля. Missing prefix отличается
от `[]`; null padding учитывается отдельно. Unknown text остаётся fixed issue.
`duplicate_line` требует минимум двух пропусков: producer удаляет всех peers
дубликата. Это проверка числа строк, без восстановления скрытого ID или matching.

Consumer limits для public GUID/line ID — 64 ASCII символа, для native_id — 32;
неподдержанная metadata отклоняется, а не копируется как opaque payload. Это
ограничения интерфейса, не новая схема игры. Instance/account IDs, raw sections,
описания неизвестных строк и лишние вложенные свойства не копируются.

Полнота импорта, фактическая активация, версия клиента, effective level, panel
inclusion и общий additional pool не подтверждаются. Проекция не применяется к
panel, rawspell или DPS и не использует ID bridges.
