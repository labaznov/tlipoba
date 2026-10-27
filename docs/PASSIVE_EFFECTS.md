# Каталожный кандидат Ice Focus

`damage_lab.passiveeffects.effect(record, *, catalog_id, level)` — чистый leaf
для public Passive ID `8318` (Precise: Ice Focus). Он связывает наблюдаемый уровень
с одним scalar-параметром Cold Damage buff и сохраняет полный proof reference
description. `summary(canonical)` восстанавливает известные ячейки, повторяет
проверку и возвращает отделённую проекцию без неизвестных полей.

Модуль не читает source/catalog bytes и не применяет эффекты. Внешний importer
проверяет artifact/source SHA и согласованность объявленных catalog coordinates,
alias и GUID с исходной установкой. Master/English member hashes остаются
declared provenance; независимая проверка cache bytes выполняется отдельным
offline proof. Безопасный GUID сам по себе не является такой проверкой.
Интеграция с профилями и HTML — отдельный слой.

## Требуемый proof

Реестр содержит только точный девятистрочный `templateDescription` для `8318`,
LF only. Первое связывание — scalar `#% additional Cold Damage` на строке 1;
второе — целый range-токен `#-#` в `Deals #-# Spell Cold Damage.` на строке 8.
Строки и tokens нумеруются с нуля. Два символа `#` range-токена не становятся
двумя отдельными bindings.

`descriptionBindings` обязан объявить ровно два поля в этом порядке:
`value[0-9]{1,2}` и `value[0-9]{1,2}Min`; соответствующий Max выводится только
из явно объявленного Min. `value1` и `value7Min` не угадываются.
Категория строго `Passive`; переданный `catalogPath` — `skill/Passive`.
Catalog ID должен совпадать с `record.tlidbId`, а GUID — иметь безопасную
ASCII-форму `[A-Za-z0-9][A-Za-z0-9_-]{0,63}`. Имя, tags и native Prefix не
подменяют identity или binding.

Reference и наблюдаемый level — strict integers `1..40`. Progression содержит
не более 40 строк; оба запрошенных уровня должны существовать ровно по одному
разу. Нет interpolation, reference/L1/L20 fallback или выбора первого дубликата.
Весь reference-description должен точно воспроизводиться из signed scalar и
неотрицательного упорядоченного integer-range, включая все остальные строки.
Даже изменение неприменяемой буквальной строки `+4%` нарушает этот proof.
Повторяющаяся reference-дробь не округляется, чтобы принудительно получить текст.

## Точные ячейки

Scalar допускает signed integer, точный `Decimal` или ASCII-строку:
не более 12 integer и 9 fractional digits либо рациональную `p/q` с максимум
12 цифрами в числителе и положительном знаменателе. Bool, float, выражения,
пробелы, знак `+`, экспоненциальные строки и Unicode-цифры не coercируются.
Участвующий float даёт фиксированный `*_cell_requires_exact_number`: нужен
JSON-loader с `parse_float=Decimal`, а не `str(float)`.

У `Decimal` до форматирования проверяются конечность, максимум 21 цифра и
exponent от −9 до 11; затем действует та же plain-number грамматика. Точный
Fraction-расчёт не зависит от caller Decimal context. Поля `value.percent` и
`value.fraction` — сокращённые целочисленные `numerator/denominator`; последнее
отношение ровно в 100 раз меньше первого. Никакие бесконечные decimal expansions
не усекаются. Десятичная запись наблюдаемой рациональной ячейки может быть
бесконечной периодической: такая ячейка сохраняется точной дробью.

`value.cell.text` сохраняет точное представление **разобранной** ячейки, не
обещая исходную лексему JSON. Range-cells Glacial Spike допускают только
неотрицательные strict integers меньше `10^12`; они сохраняются строками
с `kind=integer`, только как proof, отдельно от buff scalar.

## Выход

Envelope — `tli-passive-effect-v1`, версия `0.1.0`:

```text
{format, version, status, reason, gaps,
 identity:{catalog_id,guid,category},
 lookup:{level,meaning:observed_gem_level_not_effective}, candidate, ...unknowns}
```

При успехе `candidate` содержит `kind=additional_damage`, `owner=player`,
`target=cold_damage`, `scope=focus_buff`, `unit=percent`, `value` и `binding`.
Это дополнительный Cold Damage buff, не собственный spell hit Ice Focus и
не общая итоговая damage-величина персонажа.

`binding` сохраняет весь template и reference-description, scalar field,
его line/token coordinates, пару Min/Max полей и их coordinates,
`reference_level`, `reference_scalar_cell`, `reference_range_cells`,
`observed_range_cells`, `status=whole_reference_render_consistent`.
Если reference level равен lookup level, scalar и range обеих сторон должны
совпасть. Summary реконструирует фактический полный reference proof, а не только
арифметику конечной доли. Все известные integer coordinates/ratios имеют строгие
типы; `0` не заменяет `false`, а `1.0` не заменяет индекс 1.

Три строки `unmodelled_effects` фиксированы:

- `focus_resource_and_ice_storm_mechanics`;
- `self_skill_additional_damage_literal_4_percent`;
- `glacial_spike_damage`.

Буквальные 4% относятся к самому навыку и остаются неприменённой отдельной
строкой полного template. Они не смешиваются с Cold Damage buff. Диапазон
Glacial Spike, Focus gain/consumption, Ice Storm и его интервалы не участвуют
в damage/cast/topology модели этого leaf.

Во всех состояниях четыре flags `arithmetic_ready`, `runtime_verified`,
`identity_verified`, `import_complete` строго `false`; `effective_level=null`,
`activation=unknown`, `eligibility=unverified`,
`additional_group_identity=unresolved`, `patch=unknown`.
Не подтверждаются effective level, current patch, активация Focus, additional
pool, полный модификатор Cold Damage, mainstats или DPS. Гейты rawspell не
закрываются.

## Неизвестные и пределы

Unsupported Passive IDs (включая `7112`, `8301`, `8309`) дают
`status=unresolved`, `candidate=null`, один фиксированный `reason` и тот же код
в `gaps`; отсутствие tables/bindings не становится пустым поддержанным эффектом.
Ошибки identity, template, bindings, уникальности строк, scalar/range и полного
reference-render также сохраняют фиксированный gap. Некорректный API-вход или
поддельный canonical proof отклоняется фиксированным `ValueError` без payload.

Preflight: depth ≤32, ≤20 000 узлов, ≤4096 entries контейнера и ≤4096 characters
строки, valid UTF-8, без циклов и повторных ссылок на контейнеры. Raw integers
имеют максимум 20 цифр, canonical integers — 21; это пределы приёма, а не
игровые caps. Ячейки и уровни дополнительно ограничены своей грамматикой.

```powershell
C:/Python313/python.exe -m unittest discover -s tests -p test_passiveeffects.py -v
```
