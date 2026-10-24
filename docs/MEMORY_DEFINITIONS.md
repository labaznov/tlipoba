# Определения аффиксов памяти

`damage_lab.memorydefinitions.project(raw, source_sha256)` — чистый consumer
`tli-memory-definition-ledger-v1` версии `0.1.1`. Он проверяет DTO замороженного
compiler 0807, сравнивает объявленный source SHA с аргументом и возвращает
отделённую snake_case-проекцию. `summary(canonical)` повторяет те же проверки
canonical-входа и удаляет неизвестные поля. Файлы, каталог и source bytes этот
модуль не открывает; helper-модуль не импортируется.

`source.binding=caller_supplied` означает именно заявление caller. Само
совпадение хеша не аутентифицирует source, каталог или текущую версию игры.
Внешний byte-wrapper должен отдельно проверить точные source/artifact bytes,
а также master и English member provenance.

## Canonical-проекция

Формат и версия сохраняются. Верхние поля:

- `source`: `sha256`, `binding`;
- `arithmetic_ready`, `runtime_verified`, `identity_verified`, `import_complete`:
  строго `false`;
- `catalog`: `logical_paths`, `modifier_ids`, `collisions`, `invalid_entries`,
  `invalid_groups`;
- `domain`: `status`, фиксированный `path`;
- `candidates`, `omitted`, `structural_gaps`, `accounting`.

Оба logical paths фиксированы: `hero-memory/master` и
`hero-memory/i18n/en`. Имена пяти catalog groups остаются точными строками
источника: `baseStats`, `fixedAffixes`, `randomAffixes`, `revivedAffixes`,
`specialRandomAffixes`. Недопустимая группа не может одновременно предоставлять
кандидат. Счётчик collisions не превышает число modifier IDs; сведения об
ambiguous IDs и выбранных definitions не могут противоречить друг другу.

Каждый кандидат содержит только:

- `alias`, `path`, `native_id`, `disposition=exact_definition`;
- `definition`: `logical_path`, `group`, `id`, `modifier_id`, `memory_type`;
- `template`: `text`, `source`;
- `catalog_tier`: `tier`, `level`, `literal`, `range`, `sign`, `unit`;
- `own_values`: `index`, `exact`, `source`;
- `server_mirror`: `status`, `issue`;
- `native_conditions`: `condition`, `filter`, `behavior`;
- `memory_type`: `catalog`, `helper`, `status`, `basis`;
- `operator`, `activation`, `rank_scaling`, `line_roles`, `runtime_pool_identity`.

`definition.modifier_id` должен точно совпадать со строковой формой полного
положительного `native_id`, без префиксного поиска. Catalog record ID допускает
только `[A-Za-z0-9][A-Za-z0-9_-]{0,63}`. Этот consumer проверяет переданную связь;
он не выполняет повторный join исходных каталогов и не выбирает первый peer.
Все candidates с одним полным native ID обязаны иметь одинаковые `definition`,
`template` и `catalog_tier`: producer получает их из одного уникального catalog
peer. Собственные значения, conditions, mirror и helper type отдельных
экземпляров при этом могут различаться.

`operator`, `line_roles`, `runtime_pool_identity` остаются `unresolved`,
`activation` и `rank_scaling` — `unknown`. Полный native ID и совпавшая definition
не становятся runtime pool key. Значения не получают damage scope, owner,
оператор increased/more, номер строки эффекта или роль в расчёте.

## Координаты и точность

Domain path фиксирован: `sections.HeroCharacter.data.HeroJewels`.
Строка обязана иметь согласованные координаты:

```text
heroMemory[j].PrefixInfoList[k]
sections.HeroCharacter.data.HeroJewels[j]._Raw_Data.AffixList.PrefixInfoList[k]
```

Допускаются только семь известных affix lists. Jewel position должен входить
в заявленный captured domain; позиции и row indices ограничены `0..4095`.
Строки candidates/omitted уникальны. Structural gap имеет точную форму пути
для причины `jewel_invalid`, `affix_list_invalid`, `affix_container_invalid`
или `row_invalid`; он не может перекрывать принятый ряд или другой gap.

Catalog literal и собственные DynArgs сохраняются отдельно, даже при равенстве.
В tier требуется ровно одно: `literal` либо упорядоченный `range={min,max}`.
Значения — точные ASCII-строки `-?[0-9]{1,12}(?:\.[0-9]{1,9})?`, без float,
выражений, рациональных/экспоненциальных строк, Unicode-цифр и coercion.
Знак tier допускает ASCII `+`, `-` или `null`; unit — `%` или `null`.
`tier` и известный `level` — strict integers `0 <= n < 10^18`; неизвестный
level остаётся `null`. Native ID — strict integer `0 < n < 10^20`.
Own-values indices непрерывны с нуля, а `source` точно равен `DynArgs[index]`.
Template — UTF-8, 1–1024 символа; из ASCII control characters разрешён только LF.

## Неизвестные связи

Catalog memory type — `Origin`, `Discipline`, `Progress` или `Any`.
Helper type — первые три либо `null`; его basis всегда
`helper_TYPES_convention`. Совпадение известных типов даёт `consistent` только
в рамках этой helper-конвенции, а отсутствие helper — `unknown`.
Catalog `Any` всегда имеет `status=catalog_any`, включая известный helper.
Несовпадение известных конкретных типов не может оставаться exact-кандидатом.

Три native condition fields хранят только состояния `empty`, `present`,
`missing`, `invalid`; они не доказывают активацию.

Для четырёх отображённых server lists допустимы пары:

| Status | Issue |
|---|---|
| `same`, `absent` | `null` |
| `different` | `null` или `length_mismatch` |
| `unknown` | `mirror_value_invalid`, `mirror_ambiguous`, `mirror_container_invalid`, `mirror_row_invalid` |

Для трёх остальных lists допустимо только
`unknown / mirror_list_unmapped`. Повреждённый mirror не выдаётся за отсутствие
или равенство. `same` сохраняет результат lexical comparison producer; этот
consumer не получает скрытые server values и не повторяет сравнение.

## Покрытие и отказы

При `domain.status=captured` три lists обязательны; их длины совпадают с
`accounting.candidates/omitted/structural_gaps`, а `rows=candidates+omitted`
и `reconciles=true`. Captured zero остаётся наблюдаемым нулём.
`jewels=0` требует нулевых остальных counts, включая `empty_slots`; общего
ограничения числа affix slots числом jewels нет. При `absent`, `not_captured`,
`invalid` все три lists и все accounting fields строго `null`.
Неизвестный состав не заменяется пустым полным составом.

Omission сохраняет только alias/path/native ID/disposition. `native_id=null`
допустим ровно для `native_id_invalid`; остальные фиксированные dispositions
сохраняют известный ID. Ни одна omission не создаёт частичный кандидат.

Pure-вход ограничен глубиной 32, 20 000 узлами, 4096 элементами контейнера и
4096 символами строки. Циклы, повторно использованные контейнеры, nonfinite,
невалидный UTF-8, неподдержанная версия и противоречивые известные поля
отклоняются одним фиксированным `ValueError` без исходного payload.
Никакие значения не применяются к rank, уровню навыка, панели или DPS.

```powershell
C:/Python313/python.exe -m unittest discover -s tests -p test_memorydefinitions.py -v
```
