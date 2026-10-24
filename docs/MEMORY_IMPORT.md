# Автоматический импорт памяти героя

Обычный `export_open.build_package` внешнего Windows exporter, manifest 0.7.0,
сохраняет `memoryDefinitionLedger`. Ручное добавление artifact в старый пакет
не считается проверкой обычного экспорта. Проверки выполняются на сохранённом
снимке; свежесть данных игры и полнота билда ими не подтверждаются.

Reader [`memorybundle`](MEMORY_BUNDLE.md) связывает descriptor с точными bytes
`memory-definition-ledger.json`, source SHA и pinned compiler 0.1.1. Чистая
проекция [`memorydefinitions`](MEMORY_DEFINITIONS.md) сохраняет определения
каталога, собственные lexical values, native condition states, mirror status,
пропуски и структурные gaps. Два catalog member описаны отдельными координатами
и SHA. Эти объявленные координаты не означают повторного чтения cache в tlipoba,
сетевого подтверждения или доказательства актуального patch.

`archive` вызывает reader до создания SQLite. Успешная диагностика сохраняется
как `memory_definitions = {ledger, catalog}` в record и documents. Sources
сохраняет путь artifact, его SHA, размер и `stored=1`. Проверенная producer error
сохраняет source-bound gap и artifact origin с `stored=0`, без пустого ledger.
Отсутствующий descriptor старого пакета оставляет legacy gap и не создаёт origin.
Повреждённые bytes, несовместимые версии и неверные counts отклоняются.

`importer.memorysummary` заново проверяет canonical pair и совпадение source SHA
со всем record. Snapshot удаляет неизвестные поля, возвращает независимые
вложенные структуры и сохраняет прежние stats и benchmark. Present null
неприемлем: он не заменяет отсутствие диагностического документа.

Import, calculation и inputs HTML показывают одну проверенную проекцию. Выбор
неизвестного skill alias не скрывает данные памяти. Текст экранирован, отчёты
не содержат исполняемых элементов. Ошибка fragment в inputs проходит через
существующее фиксированное сообщение без входного payload.

Точная привязка к определению не определяет оператор, порядок conversion,
эффективный ранг, activation, line roles или additional pool. Собственные
значения и catalog tiers не взаимозаменяемы и не суммируются. Четыре флага
arithmetic/runtime/identity/completeness остаются false. Этот блок не меняет
панель, typed damage inputs, rawspell или итоговый DPS.

Проверки: `test_memorydefinitions.py`, `test_memorybundle.py` и соответствующие
memory-классы в `test_damage_archive.py`, `test_importer.py`,
`test_damage_report.py`, `test_buildinputreport.py`. Все fixtures синтетические;
реальные пакеты, SQLite и сквозные proofs остаются в ignored local directories.
