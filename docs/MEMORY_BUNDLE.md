# Source-bound пакет определений памяти

`damage_lab.memorybundle.read(package, descriptor, source_sha256,
max_bytes=64*1024*1024)` читает только фиксированный файл
`memory-definition-ledger.json` из переданного package. Аргумент `max_bytes`
передаётся по имени. Reader поддерживает envelope
`tli-memory-definition-ledger-bundle-v1` версии `0.1.0` и compiler
`tli-memory-definition-ledger-v1` версии `0.1.1`.

Reader сравнивает SHA256 **точных artifact bytes** с descriptor. SHA256 source
в descriptor, envelope и ledger должен совпадать с аргументом caller.
Сам `source.json` reader не открывает: проверка его bytes — обязанность
вызывающего импортера. Ledger проходит чистую валидацию
[memorydefinitions](MEMORY_DEFINITIONS.md); helper-код не импортируется.

Результат — `(pair, origin)`, где:

```text
pair = {ledger: canonical_memorydefinitions, catalog: canonical_provenance}
origin = (absolute_artifact_path, artifact_sha256, byte_length, stored)
```

У diagnostic-результата `stored=1`. `summary(pair)` повторно валидирует оба
canonical-компонента, возвращает отделённую проекцию и удаляет неизвестные
поля. Она не читает файлы и не переизвлекает definitions из каталога.

## Объявленные catalog bytes

Canonical `catalog` содержит только `derivation=cache_member_exact_slice`,
`network_bytes_verified=false`, `current_patch_verified=false` и `documents`.
Ровно два уникальных logical paths должны совпадать с ledger:
`hero-memory/master`, `hero-memory/i18n/en`.

Каждый document сохраняет восемь полей:

- `logical_path`, `member`: один и тот же фиксированный logical path;
- `address`: строго `/data/SS14/<logical_path>.json`;
- `cache_file`: 16 lowercase hex characters и `.json`;
- `wrapper_sha256`, `member_sha256`: lowercase SHA256;
- `byte_range`: strict integer `[start,end]`, `0 <= start < end <= 32 MiB`;
- `encoding`: точная producer-строка `utf-8`.

Два slices одного cache file должны иметь одинаковый wrapper SHA и не
пересекаться; соседние slices допустимы. Это проверка согласованности
**объявленного локального provenance**. Reader не открывает cache files,
не подтверждает network bytes, подлинность каталога или текущий patch.

## Ошибки и отсутствие слоя

Producer error имеет фиксированный format
`tli-memory-definition-ledger-error-v1`, поддерживаемый code, те же версии
и четыре literal-false flags. Все шесть descriptor counts равны `null`;
семантических `ledger`/`catalog` в error artifact нет. Reader возвращает
`(None, origin)` с `stored=0`, сохраняя SHA и размер error artifact.
Source SHA может быть `null` только для `source_missing`/`source_unreadable`.

Legacy-отсутствие descriptor обрабатывает вызывающий importer: reader не ищет
artifact автоматически. Переданные `descriptor=None` или `summary(None)`
недопустимы. Неизвестный domain не превращается в пустой: у diagnostic ledger
`absent`, `not_captured`, `invalid` сохраняются null rows/counts; явно captured
пустой domain сохраняет нули. Descriptor counts сверяются с валидированным
ledger с точным совпадением типов; `bool` не считается integer.

## Пределы и смысл

`max_bytes` — strict integer `1..64 MiB`. JSON обязан быть UTF-8 без BOM,
duplicate keys и nonfinite/unrepresentable floating tokens. До проекции
проверяются depth <= 64, <= 25 000 nodes, <= 4096 entries на контейнер и
<= 4096 characters на строку, включая неизвестные поля. Циклы, повторно
использованные контейнеры и невалидный UTF-8 в строках отклоняются.
Внутренний ledger дополнительно имеет собственные более узкие пределы.

Все arithmetic/runtime/identity/import flags остаются `false`. Точные own
lexemes, catalog tier, template и mirror хранятся раздельно. Определение не
получает operator, activation, rank scaling или runtime pool identity.
Этот reader не рассчитывает DPS и не применяет effects к панели или raw model.
