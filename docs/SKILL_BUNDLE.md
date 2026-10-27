# Пакет установленного состава навыков

`damage_lab.skillbundle.read(package, descriptor, source_sha256)` проверяет `manifest.installedSkills` и фиксированный файл `installed-skills.json`. Обычные команды импорта и условного расчёта подхватывают descriptor автоматически: ручные показатели и дополнительный шаг игрока не требуются. Никакие пути внутри artifact не открываются.

Диагностический artifact имеет format `tli-support-inventory-v0`, version `0.1.2`. Он проходит через `installedskills.project`, поэтому в результат попадает очищенная каноническая проекция. Версии с известной ошибкой определения уникальности не принимаются. `version` descriptor относится к inventory, а не к версии wrapper.

Descriptor требует `file`, `status`, `version`, `sha256`, `sourceSha256`, три ложных флага `runtimeVerified`, `identityVerified`, `importComplete`, а также `clientRows`, `serverReconciled`, `relationships`, `issues`. Фактические байты artifact должны совпасть с SHA256; его source hash и descriptor привязываются к переданному SHA сохранённого `source.json`. Это проверка согласованности байтов пакета, не подлинности ответа, выбранного персонажа или свежести игры.

Счётчики сверяются с проверенной проекцией. Ненаблюдаемый слой сохраняет `null` counts; число relationships также `null` без captured client. Известные нули остаются нулями. Bool не заменяет целое число. Отдельное значение `gem_level` не становится эффективным уровнем, а co-membership не подтверждает роль поддержки или её активацию.

Чтение ограничено 64 MiB. Явный `max_bytes` — положительный `int` до этого предела, без bool. JSON с повторными ключами, NaN/Infinity, переполнением float, неправильным UTF-8 или превышенной глубиной отклоняется. Неизвестные поля не копируются проекцией. Нарушение hash, схемы, флагов или счётчиков вызывает ошибку без текста payload.

Для `status=error` wrapper использует отдельный `tli-support-inventory-error-v1`, version `0.1.0`. Код должен совпасть с descriptor и входить в фиксированный набор: `source_missing`, `source_unreadable`, `source_too_large`, `source_not_json`, `source_duplicate_key`, `source_nonfinite_number`, `source_parse_limit`, `source_shape`, `inventory_failed`. Все counts descriptor — `null`, verification/completeness — `false`. Source hash может отсутствовать только при `source_missing` или `source_unreadable`; это явно непривязанная ошибка получения источника, не валидная пустая сборка. Если hash присутствует, он обязан совпасть с пакетом.

Reader возвращает `(inventory, origin)`: очищенные данные либо `None` для producer error, затем фактический путь artifact, SHA256, число прочитанных байтов и `stored=1|0`. Ошибка producer не выдаёт нулевой inventory; файл существует как источник диагностики, его raw содержимое не возвращается. Reader сам не пишет файлы или SQLite и не меняет DPS.

Проверка: `python -m unittest discover -s tests -p test_skillbundle.py -v`.

Очищенный inventory сохраняется в `documents.installed_skills`, `import.json` и `calculation.json`; таблица `sources` хранит фактический origin artifact. HTML показывает наблюдаемые камни и связи отдельно от неизвестной активации и effective level. Старый пакет без descriptor даёт явный coverage gap, producer error сохраняет origin со `stored=0`, без пустого inventory. Ни один вариант не меняет расчёт DPS.
