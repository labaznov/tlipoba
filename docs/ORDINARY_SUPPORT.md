# Обычная поддержка: точный scalar-кандидат

`damage_lab.ordinarysupport.effect(record, *, catalog_id, level)` — чистый
адаптер трёх проверенных семей обычной поддержки, public catalog IDs `7420`,
`7401` и `8608`.
Он не читает файлы и не применяет урон. `summary(canonical)` повторно
проверяет безопасный proof-блок, удаляет неизвестные поля и возвращает
отделённую структуру.

Кандидат возможен только при точном `tlidbId`, категории `Support`, безопасном
GUID, одном объявленном поле `value[0-9]{1,2}`, уникальных строках reference и
запрошенного уровня и полном совпадении reference-description. GUID не зашит
в реестр: его связь с импортированным навыком проверяет вызывающий consumer.
Необязательный `catalogPath`, если передан, должен быть `skill/Support`.
Имя поддержки, native Prefix и похожая строка текста не служат привязкой.

Для `7420` поддерживается только целый двухстрочный English template:

```text
Supports skills that hit enemies.
+#% additional damage for the supported skill when it lands a Critical Strike
```

`descriptionBindings.template` должен быть `templateDescription`. Единственный
объявленный параметр используется вместо угадывания `value1`. Уровень reference
берётся из самой привязки, а наблюдаемый уровень передаётся явно; отсутствие или
дубликат строки даёт фиксированный gap без выбора первого элемента и fallback.
Весь reference-description должен совпасть с точным рендером template, включая
первую строку, пробелы и пунктуацию. Повторяющаяся дробь не округляется для
подгонки reference-description.

## Точные числа

Участвующая ячейка допускает неотрицательный `int`, точный `Decimal` или строку
целого, десятичного числа либо рациональной дроби. `float` даёт отдельный gap
`reference_cell_requires_exact_number` или `observed_cell_requires_exact_number`.
Каталожный JSON-loader должен сохранять десятичные числа через
`parse_float=Decimal`; `str(float)` не восстанавливает исходную точность.

Целая часть ограничена 12 цифрами, дробная — 9. Рациональная строка допускает
до 12 цифр в числителе и положительном знаменателе. Нет выражений, экспонент
в строках, пробелов и bool-coercion. Знак минус допускается для `7401` и `8608`.
Для `Decimal` проверяются
конечность, не более 21 цифры и exponent от −9 до 11 до форматирования; затем
действует та же plain-number грамматика. Десятичный контекст вызывающего кода
не меняет точные отношения.

`value.cell.text` — точное представление **разобранной ячейки**, а не обещание
сохранить исходную лексему JSON: форматирование `Decimal` может раскрыть
экспоненту. `value.percent` и `value.fraction` содержат сокращённые целые
`numerator`/`denominator`; второе отношение ровно в 100 раз меньше первого.
Повторяющиеся дроби сохраняются отношениями, а не усечёнными decimal-строками.

## Выход и границы доказательства

Формат — `tli-ordinary-support-effect-v1`. Новый `8608` получает версию `0.1.2`;
результаты `7401`, `7420` и остальных unsupported IDs сохраняют прежнюю `0.1.1`
без изменения payload. Legacy `0.1.0` и `0.1.1` повторно проверяются без изменения
версии. Projectile-кандидат нельзя передать под `0.1.0`, а Focus-кандидат — под
`0.1.0` или `0.1.1`. Legacy unresolved envelope `8608` остаётся unresolved.
Envelope содержит
`status`, `reason`, `gaps`, `identity`, `lookup` и nullable `candidate`.
При отсутствии доказательства `status=unresolved`, `candidate=null`, а `reason`
совпадает с единственным фиксированным кодом в `gaps`. Структурно неверный
вход или поддельный canonical-блок даёт `ValueError` с одним фиксированным
сообщением без входного payload.

Кандидат `7420` имеет `kind=critical_hit_additional_damage`,
`origin=catalog_level_table`, `owner=supported_skill`,
`target=supported_skill_critical_hit`, `unit=percent`. Его binding сохраняет
целый template, объявленное поле, reference level/cell/description и координаты
строки/токена: `line=1` — индекс второй строки с нуля, `token_index=0`.
Это дополнительный урон критического попадания поддержанного навыка;
он не является модификатором полного Critical Strike Damage multiplier,
ordinary increased, Lucky или глобальным уроном персонажа.

## Multiple Projectiles

Для `7401` целый template строго равен:

```text
Supports Projectile Skills.
Projectile Quantity of the supported skill
+2
#% additional damage for the supported skill
```

Наблюдаемый уровень, reference level и все строки таблицы ограничены `1..40`;
таблица содержит не более 40 строк. Нет extrapolation или fallback. Уровень
41 даёт `observed_level_invalid`, неверный reference — `binding_level_invalid`,
а неподдержанный ряд или размер таблицы — `level_table_invalid`.

Только последний `#` связывается с единственным объявленным полем. Signed
scalar сохраняется в обычном `value` с exact percent/fraction; `kind=additional_damage`,
`target=supported_skill`, `scope=projectile`. Binding указывает `line=3` и хранит
reference cell и полный reference-description. Отрицательные дроби рендерятся
со знаком перед абсолютной величиной; результат не зависит от Decimal context.
Если reference и observed level совпадают, их клетки обязаны совпадать.

Отдельный `projectile_quantity` содержит `origin=catalog_literal`,
`lines=[1,2]`, `text=+2`, `value=2`, literal `bound=false` и
`hit_semantics=unknown`. Это каталожная прибавка количества, а не итоговое число
снарядов или попаданий. Не вычисляются shotgun, hit topology или урон цели.
Числовые координаты и literal values нельзя подменять float или bool.

## Focus: эффект поддержанного баффа

Для `8608` целый template строго равен:

```text
Supports Focus Skills.
#% buff effect for the supported skill
-18% Sealed Mana Compensation for the supported skill
```

Уровни observed/reference и все строки таблицы ограничены `1..40`, размер
таблицы — 40 строками. Единственный `#` второй строки связывается с одним
объявленным `value[0-9]{1,2}`; field не угадывается по имени поддержки или по
`value1`. Проверяются уникальные reference/observed rows и полный точный
reference-description, включая последнюю строку с literal `-18%`. Допустимы
signed scalar и точная рациональная дробь; repeating reference не округляется
для совпадения с description. При одном reference/observed level клетки
canonical proof должны совпадать.

Кандидат имеет `kind=buff_effect`, `origin=catalog_level_table`,
`owner=supported_skill`, `target=supported_skill_buff`, `scope=focus`,
`unit=percent`. В `value` сохраняются точная parsed cell и отношения
percent/fraction. Binding имеет `line=1`, `token_index=0`, объявленное поле,
reference cell/level и полный template/description. Фиксированный список
`unmodelled_effects=[sealed_mana_compensation_literal_minus18_percent]`
отделяет компенсацию маны: literal проверяется как часть текста и не применяется.

Это кандидат изменения эффекта поддержанного Focus-баффа, не damage multiplier
и не урон triggered hit Focus. Он не умножается на Passive `8318`, не изменяет
Glacial Spike, sealed mana или pools. Eligibility, активация, effective level
и принадлежность к группе дополнительных эффектов остаются неизвестными.
`summary` восстанавливает и проверяет весь proof, включая роль, literal marker,
ratio и версионный барьер; unknown extras не копируются.

`lookup.meaning=observed_gem_level_not_effective`. Во всех состояниях
`effective_level=null`, `activation=unknown`, `eligibility=unverified`,
`additional_group_identity=unresolved`, `patch=unknown`, а четыре флага
`arithmetic_ready`, `runtime_verified`, `identity_verified`, `import_complete`
строго `false`. Нет выбора effective level, пост-20 профиля, суммы пулов,
активной поддержки или готовности DPS.

`summary` проверяет внутреннюю согласованность proof-блока, а не подлинность
каталога. Вызывающий importer должен отдельно связать catalog ID/GUID/category,
alias, группу, путь и наблюдаемый уровень с установкой, а master и English —
с точными member SHA и source provenance. Наличие co-member связи не доказывает
активацию. Сам leaf не добавляет новый artifact и не интегрирует специальные
поддержки, `criticalstats`, rawspell или панель.

Защитные границы pure-входа: не более 20 000 посещённых узлов, глубина 32,
4096 элементов контейнера, 4096 символов строки, до 1000 строк progression и
уровни `1..1000` для `7420`; `7401` и `8608` имеют более узкий предел 40.
Повторные ссылки на один контейнер отклоняются.
Исходные integer nodes ограничены 20 цифрами; canonical derived ratios
допускают 21 цифру, чтобы сохранить всю разрешённую клетку с 12 целыми и
9 дробными цифрами. Identity IDs остаются в собственном пределе 20 цифр.
Неизвестные поля не копируются в результат.

Проверка локально:

```powershell
C:/Python313/python.exe -m unittest discover -s tests -p test_ordinarysupport.py -v
```
