# Кандидаты эффектов специальных поддержек

`damage_lab.supporteffects.effects(record, *, native_base_id, prefix_rows)` —
чистый офлайн-адаптер одной переданной записи каталога и native Prefix одного
установленного камня. Формат результата — `tli-support-effects-v0`, версия
`0.3.0`. Модуль не читает файлы, игру или сеть. Его кандидаты сохраняются обычным
импортом через [inventory](SUPPORT_INVENTORY.md) и [bundle](SUPPORT_BUNDLE.md),
но не применяются к панели, rawspell либо DPS. Основание точных шаблонов и ограничения источников
описаны в [исследовании привязок](research/special-support-bindings.md).

Это перенос reviewed helper `support_effects` 0.3.0 с SHA256
`654a96f5db0904715791a4d4fcc99a28bed9dde5e6d96ba4ed903f3cb1e05fd0`.
Production-код отличается только ссылкой на эту документацию. API, схема,
шаблоны, числовые ограничения и статусы сохранены.

## Создание Tangle

Новая отдельная ветка `mediumTrigger` содержит только фиксированную привязку
Activation Medium: Tangle `8030`, строка `77103277`, точный English template.
Слоты идут в порядке радиус подсчёта (`metre`), интервал создания (`second`).
Они сохраняют decimal text и свой диапазон; процентная `fraction` не создаётся.
`tierMeaning=catalog_line_tier` не означает уровень камня или effective level;
`runtime=unverified`, `rateDerived=false`. Полный native ID сопоставляется с
объявленным modifier ID, его суффикс не используется для восстановления tier.

Неоднозначная строка, отсутствующий/изменившийся шаблон, неподходящие значения
или неизвестный соседний prefix удерживают результат как явный gap. При
неизвестном соседе подходящая строка получает omission `unresolved_prefix_peer`:
кандидат не выбирается из потенциально неполного набора. Остальные bases имеют
`not_applicable`; отсутствие данных и ошибки identity/schema не становятся
подтверждённым отсутствием medium.

Эта ветка не задаёт частоту атак уже созданного Tangle, uptime, число попаданий
или участие в Spell Burst. Обратная величина интервала не вычисляется.
Основание и ограничения: [исследование создания Tangle](research/tangle-medium-creation.md).

## Вход и граница привязки

- `record` — объект master-записи с объединённым `english`. Используются
  `tlidbId`, `id`, `category`, `lines[].id`,
  `tierProgression[].{tier, lines[].{id, modifierId, values}}`,
  `english.lineTemplates` и `english.templateDescription`
- `native_base_id` — целочисленный `ConfigBaseId` без bool
- `prefix_rows` — переданный список `ServerPlayerItem.Prefix` либо `None`, если
  поддерево отсутствует

`identity.status=supplied_data_exact` означает только строгое совпадение
целочисленного `record.tlidbId` и переданного native base ID. Несовпадение даёт
`base_identity_mismatch`, нецелочисленная catalog identity —
`catalog_identity_invalid`. При таком gap `catalogSchema`, `rolledLines`,
`omissions`, `constants`, `constantIssues` равны `null`.

Это не проверка источника, выбранного персонажа, установленной связи, текущего
клиента или свежести. Отдельному binder ещё нужны source/catalog hashes и точная
привязка master и английского документа. Имя поддержки и native `Version` такую
проверку не заменяют.

Неверный тип аргумента API вызывает `EffectsError` с фиксированным сообщением.
Неверные catalog containers или типы line ID/modifier ID/tier дают `catalogSchema=invalid` и
те же четыре null-раздела эффектов. Отсутствующие containers разрешены; известный
native row без точного определения остаётся omission. Невалидная схема не
выдаётся за пустой полный inventory.

## Роллируемые строки

Полный native `Id` сопоставляется ровно с одной
`tierProgression[t].lines[].modifierId`, а line ID должен присутствовать в
`lines[]`. Никакого отрезания цифр, поиска по имени или ближайшему tier нет.
Дубликат catalog definition даёт `ambiguous_definition`.

`DynArgs` должен быть списком с тем же количеством значений, что у `values`
своего tier и placeholders точного шаблона. `values` содержит `min` и `max`;
отдельное поле `unit` не требуется. Процент определяется двумя поддержанными
шаблонами:

| Шаблон | `role` |
| --- | --- |
| `+#% additional Hit Damage for the supported skill` | `additional_hit_damage` |
| `#% additional damage for the supported skill` | `additional_damage` |

Ролл проверяется только по диапазону найденного tier: `min <= roll <= max` и
`min <= max`. Отрицательный damage roll сохраняется отрицательным. Явный минус
шаблона вместе с отрицательным roll либо плюс шаблона с отрицательным roll/range
дают `sign_convention_unresolved`; `abs()` и смены знака нет.

У rolls и bounds один инженерный числовой контракт: максимум 12 integer digits
и 9 fraction digits. Принимаются int с модулем меньше `10**12`, конечный float
с plain decimal `repr` или такой decimal text. Bool, exponent form, лишние digits,
нечисловой текст и огромные int не округляются: это `invalid_value` для roll или
`invalid_range` для bound. Float сохраняется через `repr`; исходный decimal
lexeme, потерянный до вызова функции, не восстанавливается.

`fraction = roll / 100` вычисляется в отдельном 50-digit Decimal context.
Контекст вызывающей стороны не меняет результат. Сохраняются `exact`, `fraction`
и lexical `range.min/max`. Например, искусственное `24.125` даёт `0.24125`.

Успешная строка содержит `origin=native_prefix_row`, относительный `path=prefix[i]`,
`lineId`, `nativeId`, `tier`, `role`, `unit=percent`, `template`, `values`,
`nativeVersion` и `status=native_roll_exact`. Integer native Version сохраняется
только как `{value, meaning: unverified}`; нецелочисленный — как `null`.
Это не effective rank или normal/corroded rule.

Identity всех известных строк подсчитывается до проверки значений. Если несколько
native rows относятся к одной line, все они дают `duplicate_line`, включая peers
с отсутствующим `DynArgs`, неверным count или out-of-range roll. Успешный сосед не
выбирается за весь дубликат. Null padding считается отдельно в `prefix.nullRows`.

Другие omissions сохраняют только origin/path/reason: `invalid_row`,
`no_exact_definition`, `line_not_declared`, `value_count_mismatch`,
`unsupported_template` и перечисленные выше отказы. Raw payload в них не копируется.

## Каталожные константы

`english.templateDescription` — одна JSON string. После decoding её координата
`{field: templateDescription, line: k}` — индекс с нуля в `text.split('\n')`,
LF only. Это текстовая строка, а не JSON array. Шаблоны роллируемых строк,
включая каждую строку multiline template, не разбираются повторно как constants.

Распознаётся только фиксированный набор точных literals: конверсия 100%
Physical → Cold, damage 20%, main-attribute ratio 25%, Projectile Speed 30%,
Cold Tag, Frostbite trigger, tracking и ограничения установки. Это публичные
catalog literals. Их параметры отделены от native rolls; другая формулировка,
процент или destination не подбираются по сходству.

Каждая constant имеет `origin=catalog_literal`, текстовую координату, `kind`,
фиксированные `parameters` и `status=catalog_literal_unverified_runtime`.
Неизвестный текст не копируется: остаётся `unknown_constant` либо
`placeholder_without_line` и координата в `constantIssues`.

## Неизвестность и дальнейшие gates

У любого результата `arithmeticReady=false`, `runtimeVerified=false`,
`activation=unknown`, `effectiveLevel=unknown`, `patch=unknown`,
`additionalGroupIdentity=unresolved`. Constants и rolls не объединяются в суммы,
не перемножаются между поддержками и не становятся модификаторами панели.
Lightchaser ratio operator, общий additional pool, inheritance, shotgun и
runtime order не выводятся из текста.

Отсутствующий `prefix_rows` даёт null counts/rolledLines/omissions. Явный `[]`
означает переданный пустой список; это не fallback. Аналогично отсутствующий
templateDescription даёт `constants=null`, а явно пустая строка — `[]`.
Входы и результаты отделены друг от друга; opaque дополнительные поля не нужны
проекции. Все публичные тестовые fixtures вымышлены, реальные роллы не включены.

Проверка: `python -m unittest discover -s tests -p test_supporteffects.py -v`.
