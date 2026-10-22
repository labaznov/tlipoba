# Частичные статические аффиксы вещей

Новые пакеты Windows-экспортера могут содержать `static-combat-modifiers.json` и descriptor `manifest.staticCombat`. `damage_lab.staticbundle.read` принимает bundle 0.1.0/0.1.1/0.1.2 с ledger compiler 0.3.2/0.4.0/0.4.1/0.4.2. Версия compiler в manifest должна совпадать с ledger. Обычные команды `import` и условного расчёта подхватывают его автоматически: дополнительный файл с вручную переписанными параметрами не требуется.

Архив сохраняет безопасную проекцию в `documents.static_combat`, а координаты исходных документов — в `documents.static_combat_provenance`. В `sources.static_combat` остаются фактические SHA256 и размер artifact. Проекции также входят в `import.json` и `calculation.json`; HTML показывает распознанные строки, пропуски, структурные пробелы и хеши каталогов. Неизвестные дополнительные поля artifact не копируются в результат.

Проверяются фиксированное имя artifact, его точные байты и хеш descriptor, SHA сохранённого `source.json`, версии схемы, ложные флаги runtime/completeness/identity/freshness и согласованность счётчиков. Чтение artifact ограничено 64 MiB; JSON с повторными ключами и нечисловыми токенами NaN/Infinity отклоняется. Несогласованный пакет не создаёт базу или частичный каталог результата.

Происхождение каталога — `cache_member_exact_slice`: exporter передал compiler точный UTF-8 slice члена локального JSON wrapper, сохранив числовые токены. Для каждого compiler input требуется отдельная запись с logical path, SS14 address, именем cache wrapper, SHA wrapper и member, byte range и encoding. Повторные члены, пересечения ranges одного wrapper, несовпадающие хеши wrapper и неполный набор координат отклоняются. Consumer проверяет согласованность сохранённых заявлений; он не открывает cache по переданным путям и не сверяет отсутствующие в пакете байты wrapper. `network_bytes_verified=false` сохраняется: локальный cache не становится подтверждением исходного сетевого ответа или текущего патча игры.

Типизированный ledger сохраняет лексические rolls, точные привязки к статическим определениям, семью, scope, владельца и pooling status. `compiled_unverified_runtime` означает, что строка разобрана по поддержанному шаблону. Это не подтверждает, что эффект действует в текущем бою, не решает неизвестные условия и не означает полного покрытия предметов. `all_rows` относится к учёту доступных строк; структурные пропуски переводят scope в `known_rows_only`.

Compiler 0.4.0 добавляет только три exact crit templates со знаком `+`: обычный increased Critical Strike Rating, обычный Critical Strike Damage и Spell Critical Strike Damage. Они сохраняются с `semantics.arithmetic_ready=false`. У рейтинга operation равен `rating_increase`; у critical damage — `unresolved`: consumer не выбирает между прибавлением процентных пунктов и относительным масштабированием. Лексическая fraction = exact/100 не определяет этот оператор. Пределы family/targets/scope/owner, версия и фиксированная семантика проверяются снова при выводе JSON и HTML; true или 0 вместо false отклоняются. HTML показывает число таких строк и запрет арифметики. Lucky composite, additional crit, weapon-local и Tangle-only строки не становятся обычными crit-модификаторами.

## Фиксированный implicit wand

Compiler `0.4.2` дополнительно сохраняет ровно одну поддержанную семью:
full native modifier ID `520020`, base wand из
`gear/one_handed/wand/master`, список `FixedBaseAffix`, строка
`increased_damage / damage / spell / player`. Это диагностическое распознавание
фиксированного Spell Damage implicit, а не применение его к панели или raw DPS.
Обычные строки, critical semantics и cast evidence прежних версий сохраняются.

Строка содержит `definition={catalog,id,implicit:true}` без tier или
template-source metadata и
`pool={id:null,status:unresolved,basis:fixed_implicit_identity_unresolved}`.
Implicit GUID совпадает с GUID самого предмета. Он не объявляется identity
общего пула Spell Damage.

`fixedImplicit` становится canonical `fixed_implicit`. Чистые
`damage_lab.fixedimplicit.project(raw)` и `summary(canonical)` проверяют:

- фиксированные `kind=fixed_base_implicit`, `binding=exact_item_guid_and_native_id`,
  полный modifier ID и `registry_template=+#% Spell Damage`;
- master catalog/member SHA, item GUID/public ID и единственный spec
  `min_exact`, `max_exact`, `sign=+`, `unit=%`;
- paired English `gear/one_handed/wand/i18n/en`, его member SHA и тот же GUID;
- целый `raw_text=+N% Spell Damage` с одной точной ASCII decimal и отдельным
  `number_exact`, без suffix, дополнительного условия или нечёткого сравнения;
- собственный `own_value` с `source=DynArgs[0]` и точное равенство собственное
  значение = min = max = число из English-текста.

Лексемы min/max, English и собственного значения сохраняются отдельно; равные
числа могут иметь разные хвостовые нули. Числовые строки ограничены 12 целыми
и 9 дробными цифрами. Нет coercion из bool/float, экспонент, рациональных строк
или округления. Сравнение не зависит от Decimal precision/exponent limits/traps
вызывающего кода. Fraction в родительской строке обязана точно равняться
собственному percent/100.

Родительский `staticcombat` повторно связывает proof с точными source item,
list/path, family/scope/owner, GUID/public ID, собственной лексемой и обоими
валидными catalog documents/member SHA. Proof нельзя перенести на другую
семью, список, omitted row или compiler до `0.4.2`. Поддельные известные поля
отклоняются; неизвестные extras удаляются. Результаты отделены от входа.

Только точный English wand document в `0.4.2` может иметь `role=english`.
Он исключён из проверки смешанных сезонов и не может идентифицировать предмет
как master. Неверный English document остаётся явным catalog gap и не может
подтвердить fixed proof. Сохранённые master/English SHA — внутренне согласованные
заявления producer о байтах: pure consumer не открывает cache и не подтверждает
актуальность патча или сетевой ответ.

В proof `pool_identity=unresolved`, `runtime_verified=false`,
`arithmetic_ready=false`; outer runtime остаётся unverified. Не выполняются
суммы, включение в действующие pools или перерасчёт агрегатов панели.
Защитные пределы leaf: 10 000 узлов, глубина 32, контейнер до 4096 элементов,
UTF-8 строка до 4096 символов, integer nodes до 20 цифр; циклы и повторные ссылки
на контейнеры отклоняются. При ошибке leaf выдаёт фиксированный `ValueError`
без входного payload.

Ошибка producer сохраняется как coverage gap с `stored=0`, без ledger и без нулевых счётчиков эффектов. Старый пакет без descriptor остаётся доступен с явным пробелом приобретения данных. Ни один из этих случаев не меняет observed stats, уровни героя, eligible upgrades или DPS.

Автоматическое применение аффиксов к агрегированной панели запрещено: панель уже может включать их. Для самостоятельной сборки урона ещё нужны привязки версии и effective level, подтверждённые skill parameter roles, условия активации и полное покрытие участвующих эффектов.
