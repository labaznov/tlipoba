# Пакет эффектов поддержек

`damage_lab.supportbundle.read(package, descriptor, source_sha256, *, max_bytes)`
читает фиксированный `installed-support-effects.json`. Поддерживаются wrapper и
inventory producer версии `0.2.0`; старые экспериментальные версии не подменяются
текущими. Descriptor находится в `manifest.installedSupportEffects`.

Результат — `(inventory, catalog, origin)`: безопасные канонические проекции и
`origin=(absolute_path, artifact_sha256, bytes, stored)`. Нормальный diagnostic
artifact имеет `stored=1`. Проверенная ошибка producer даёт обе проекции `null`
и `stored=0`, сохраняя хеш реального artifact. Это пробел получения данных, не
пустой состав и не нулевой эффект.

Проверяются фиксированное имя, версии, status, точный SHA256 прочитанных bytes,
совпадение переданного source hash с descriptor/artifact/inventory, literal false
для arithmetic/runtime/identity/import claims и счётчики descriptor. Каталог и
inventory проходят отдельные чистые validators. Неизвестные поля не копируются в
канонические документы; semantic data запрещены в error artifact.

Пара дополнительно проверяется совместно: числовые rolled lines и catalog
constants требуют объявленных master и English members своей категории, а
withheld ID не может стать resolved candidate. Отсутствие типизированных эффектов
остаётся диагностическим пробелом и само по себе не требует English member.
`summary(inventory, catalog)` повторяет эту проверку для канонической пары без I/O.

Reader открывает **только artifact**, а не произвольные пути из JSON. Вызывающая
сторона обязана передать вычисленный hash настоящего package source. Сам reader
не перечитывает `source.json` и не проверяет повторно cache files: происхождение
каталога — проверенные по структуре заявления producer о локальных bytes, а не
новая проверка сетевого ответа или текущего клиента. Все runtime, activation,
effective level, полнота и применимость к DPS остаются неподтверждёнными.

Лимит по умолчанию — 64 MiB; явный лимит должен быть положительным integer не
больше этого значения. Чтение ограничено `limit+1`. JSON должен быть UTF-8 без
BOM, duplicate keys, nonfinite/overflow numbers и ненулевого float underflow.
Неверные структуры, hashes, counts и версии вызывают `ValueError` без payload;
ошибки открытия файла остаются обычными filesystem errors.

У producer error все counts равны `null`, code входит в фиксированный enum и
совпадает в descriptor/artifact. Source hash может быть `null` только для
`source_missing`/`source_unreadable`; такой отказ явно не связывает содержание
источника. При остальных ошибках требуется точный переданный source hash.
`catalog_bytes_unavailable` обозначает отказ обычного exporter получить собственный
сохранённый cache каталога; он также сохраняется как явный пробел.

Это слой будущего обычного импорта, без вызова модели урона. Полнота acquisition
и совпадение hashes не подтверждают активацию поддержки или текущего персонажа.
