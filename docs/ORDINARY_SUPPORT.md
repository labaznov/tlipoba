# Обычная поддержка: точный scalar-кандидат

`damage_lab.ordinarysupport.effect(record, *, catalog_id, level)` — чистый
адаптер одной проверенной семьи обычной поддержки, public catalog ID `7420`.
Он не читает файлы и не применяет урон. `summary(canonical)` повторно
проверяет безопасный proof-блок, удаляет неизвестные поля и возвращает
отделённую структуру.

Кандидат возможен только при точном `tlidbId`, категории `Support`, безопасном
GUID, одном объявленном поле `value[0-9]{1,2}`, уникальных строках reference и
запрошенного уровня и полном совпадении reference-description. GUID не зашит
в реестр: его связь с импортированным навыком проверяет вызывающий consumer.
Необязательный `catalogPath`, если передан, должен быть `skill/Support`.
Имя поддержки, native Prefix и похожая строка текста не служат привязкой.

Поддерживается только целый двухстрочный English template:

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
в строках, пробелов, знака минус и bool-coercion. Для `Decimal` проверяются
конечность, не более 21 цифры и exponent от −9 до 11 до форматирования; затем
действует та же plain-number грамматика. Десятичный контекст вызывающего кода
не меняет точные отношения.

`value.cell.text` — точное представление **разобранной ячейки**, а не обещание
сохранить исходную лексему JSON: форматирование `Decimal` может раскрыть
экспоненту. `value.percent` и `value.fraction` содержат сокращённые целые
`numerator`/`denominator`; второе отношение ровно в 100 раз меньше первого.
Повторяющиеся дроби сохраняются отношениями, а не усечёнными decimal-строками.

## Выход и границы доказательства

Формат — `tli-ordinary-support-effect-v1`, версия `0.1.0`. Envelope содержит
`status`, `reason`, `gaps`, `identity`, `lookup` и nullable `candidate`.
При отсутствии доказательства `status=unresolved`, `candidate=null`, а `reason`
совпадает с единственным фиксированным кодом в `gaps`. Структурно неверный
вход или поддельный canonical-блок даёт `ValueError` с одним фиксированным
сообщением без входного payload.

Кандидат имеет `kind=critical_hit_additional_damage`,
`origin=catalog_level_table`, `owner=supported_skill`,
`target=supported_skill_critical_hit`, `unit=percent`. Его binding сохраняет
целый template, объявленное поле, reference level/cell/description и координаты
строки/токена: `line=1` — индекс второй строки с нуля, `token_index=0`.
Это дополнительный урон критического попадания поддержанного навыка;
он не является модификатором полного Critical Strike Damage multiplier,
ordinary increased, Lucky или глобальным уроном персонажа.

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
4096 элементов контейнера, 4096 символов строки, 1000 строк progression и
уровни `1..1000`; повторные ссылки на один контейнер отклоняются.
Неизвестные поля не копируются в результат.

Проверка локально:

```powershell
C:/Python313/python.exe -m unittest discover -s tests -p test_ordinarysupport.py -v
```
