# Кандидаты входов из статического ledger

`damage_lab.ledgerinputs.inputs(ledger, *, skill_tags)` принимает **канонический**
snake_case ledger и повторно проверяет его через `staticcombat.summary`.
Это чистый офлайн-адаптер: он не открывает файлы, не вычисляет суммы и не подключён
к панели или `rawspell`. Формат результата — `tli-ledger-inputs-v1`, статус —
`inventory_unverified`; `arithmetic_ready`, `runtime_verified`, `identity_verified`
и `import_complete` всегда `false`.

`skill_tags` — явный непустой список максимум из 32 различных строк вида
`[a-z][a-z_]{0,31}`. Теги сортируются. Типы урона `physical`, `cold`, `fire`,
`lightning`, `erosion` и служебные scopes `elemental`, `damage`, `all` запрещены:
тип урона навыка не делает модификатор применимым к каждому пути конверсии.
Навык, теги, активация и effective level не восстанавливаются адаптером.

| Семейство ledger | Раздел результата | Метаданные кандидата |
|---|---|---|
| `flat_added_damage` | `added` | `type`; два `values` в порядке minimum/maximum, только для совпавшего spell/attack scope |
| `increased_damage` | `increased` | `damage_scope`: тип урона, `elemental`, `all` для общего damage или совпавший skill tag |
| `flat_attribute`, `increased_attribute` | `attributes` | `attribute`; без преобразования атрибута в урон или скорость |
| `increased_speed` | `speed` | исходные `targets`; только инвентарь, без расчёта скорости |
| другое поддержанное семейство, включая crit | `excluded` | `reason=family_not_mapped` |

Владелец не `player` исключается с `owner_not_player`; несовпавший scope —
с `scope_not_skill_tag`. Все разделы сохраняют отдельные исходные строки, включая
их `item`, `path`, `family`, `scope`, `owner`, `status`, `pool`, `definition`,
`template_sign`, `unit` и лексические `values`. У каждого value остаются `exact`,
`source`, при наличии `fraction`, а также полный `source_path` к соответствующему
`DynArgs[index]`. Равные значения разных строк не объединяются. Строки crit
сохраняют запрет арифметики и не попадают в обычный increased.

`ledger` сохраняет проверенные format/version/source/catalog/runtime/accounting,
omitted и structural_gaps; SHA относится к уже проверенному входному ledger.
Сам адаптер не сверяет его с отдельными байтами пакета. `gaps` явно перечисляет
непроверенные runtime/selection/patch/activation, отсутствующий captured section,
upstream omissions, structural gaps, флаги каталога, неразрешённые pools и
неподдержанные семейства. Даже пустые разделы не означают полных нулевых pools.

Результат отделён от входных объектов. Инвентарь кандидатов не подтверждает
активацию, полноту, применимость к конкретному hit, pooling arithmetic, версию
игры или точный DPS. Нужен отдельный source-bound resolver до применения этих
строк к самостоятельной модели урона; повторное применение к панели запрещено.
