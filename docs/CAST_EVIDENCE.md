# Неподдержанные строки cast speed

Проверено 2026-10-22 на сохранённых данных SS14; runtime и текущая версия игры не подтверждены.

Compiler `0.4.1` добавляет diagnostic evidence к существующим `omitted` строкам
static combat ledger. Wrapper и artifact остаются прежними. Старые compiler
`0.3.2` и `0.4.0` поддерживаются, но новые поля evidence на этих версиях
отклоняются. Типизированные модификаторы, причины пропусков и accounting
не меняются; строки не становятся входами суммирования скорости.

`castevidence.project(raw)` и `summary(canonical)` проверяют detached DTO без
чтения файлов или арифметики. Допускаются только два полных шаблона:

| Шаблон | Specs каталога | Собственные значения |
| --- | --- | --- |
| Cast Speed / Minion Cast Speed | 2 | 1 |
| Has Hasten / Attack Speed, Cast Speed, and Movement Speed when having Hasten | 1 | 1 |

Specs и own values — отдельные упорядоченные списки. Например, synthetic own
value `17.8750` сохраняет своё написание и `DynArgs[0]`; он не копируется в два
эффекта. Проверка числовой строки не устанавливает соответствие диапазону
какой-либо spec. Даже один spec и один own value сохраняют `value_role:
unresolved`, `activation: unknown`, `arithmetic_ready: false`.

Hasten остаётся условием полного шаблона при пустых native condition arrays.
От исходных `Condition`, `Filter`, `Behavior` сохраняется только состояние
`empty`, `present`, `missing` или `invalid`, без содержимого массивов.
Идентификаторы definition, tier и template source сохраняются отдельно от
собственного значения. Допустимы ограниченные ASCII decimal lexemes с 12
целыми и 9 дробными цифрами; неизвестные поля удаляются, некорректные известные
поля отклоняются. Минимум и максимум spec упорядочены; own value ей не назначается.

Parent `staticcombat` дополнительно проверяет версию, существующий item alias,
list/source path, положительный bounded native ID, exact base-item identity,
собственный catalog и причину `unsupported_family`. Reader `staticbundle`
проверяет artifact/source hashes и координаты точных catalog members. Это
проверка согласованности DTO и происхождения пакета. Сам consumer повторно
не сопоставляет native ID с исходным каталогом; это выполняет compiler.

Если producer не может сохранить полный diagnostic, исходная omission остаётся
с одним фиксированным `evidence_issue`, без частичного evidence:

- `evidence_definition_shape`
- `evidence_spec_invalid`
- `evidence_value_invalid`

Issue не становится новым typed modifier или дополнительным счётчиком. Нельзя
одновременно передать evidence и issue. Старые пропуски остаются видимыми,
а неизвестные значения не заменяются нулями.

SQLite и JSON сохраняют этот блок внутри существующего ledger. HTML показывает
собственные значения отдельно от specs, с неизвестным применением. Расчёт
`rawspell`, панельный DPS и benchmark не получают новых множителей.

Основание: helper task `20261022-0702-cast-omission-evidence`, compiler SHA-256
`0d78929c8ace143ae082662136a323f60c804109b39fac0aab029c6981024394`;
saved-source verification сохраняет полный before-map и проверяет source,
artifact и 73 catalog slices. Это не проверка свежести или runtime правил.
Частные снимки и реальные роллы остаются вне Git.

[Аудит входов](research/cast-input-coverage.md) описывает оставшиеся пробелы.
[Shared-roll witness](research/cast-field-role-witness.md) отделяет правила
стороннего planner от отсутствующего native field-role contract.
[Raw spell](RAW_DAMAGE.md) уже содержит арифметику для явно заданных полных pools;
полный автоматический cast-rate pool персонажа пока не получен.
