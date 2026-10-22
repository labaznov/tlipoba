# Происхождение каталога поддержек

`damage_lab.supportcatalog` проверяет только метаданные локального каталога из
`catalog` в `installed-support-effects.json`. Контракт соответствует helper
`support_effect_inventory_bundle` 0.2.0: это диагностическое происхождение
сохранённых SS14 cache members, а не проверка текущей версии игры.

Модуль чистый: он не открывает файлы, не следует путям и адресам, не загружает
каталог, не вычисляет SHA и не применяет эффекты к DPS. Проверку байтов bundle,
его SHA и привязки к `source.json` выполняет отдельный файловый адаптер.

## API и безопасная проекция

```python
from damage_lab.supportcatalog import project, summary

canonical = project(raw_catalog)
checked = summary(canonical)
```

`project(raw)` принимает helper-поля camelCase; `summary(canonical)` повторяет
все проверки для snake_case. Оба возвращают новую вложенную структуру только с
известными полями. Неизвестные свойства удаляются, а недостающие обязательные
поля и противоречия дают `ValueError` без исходных путей, текста или payload.
Подобъект каталога не получает вымышленный `format` или `version`.

| Поля canonical | Смысл |
| --- | --- |
| `derivation` | Только `cache_member_exact_slice` |
| `network_bytes_verified`, `current_patch_verified` | Строго `false`, без числовых замен |
| `identity_bridges` | Только `none_applied` |
| `mapping_files` | `{file, sha256, bytes}` для фиксированных карт адресов |
| `documents` | Метаданные каждого master или English member |
| `categories` | `{category: {master, english}}`, статусы `present` или `missing` |
| `records`, `skills`, `invalid_records`, `withheld_records` | Общее число строк и результат их классификации |
| `reconciles` | Строго `true` вместе с проверенным равенством counts |
| `records_without_english` | Число валидных строк без привязанной English entry, включая удержанные строки |
| `withheld_record_ids` | Уникальные положительные ID каталога; не идентификаторы персонажа |

Каждый `documents` содержит только:

```text
role, category, logical_path, address, cache_file, wrapper_sha256,
member, byte_range, member_sha256, encoding
```

## Координаты и хеши

Допустимы роли `master` и `english`. Категория соответствует ASCII-шаблону
`[A-Za-z][A-Za-z_]{0,63}`. Для неё точный путь —
`skill/<category>/master` либо `skill/<category>/i18n/en`; `member` совпадает с
ним, `address` равен `/data/SS14/<logical_path>.json`, `encoding` — `utf-8`.
Пути уникальны. Загруженная English entry требует master той же категории;
хотя бы один master обязателен.

Имя wrapper строго соответствует `[0-9a-f]{16}.json`. Каждый SHA — 64 строчных
hex-символа. `wrapper_sha256` относится ко всему wrapper, `member_sha256` — к
объявленному диапазону его байтов. Эти хеши имеют разную область и не обязаны
совпадать. Для одного `cache_file` wrapper-хеш должен быть одинаковым, а диапазоны
members не должны пересекаться; соседние диапазоны разрешены.

Проверка согласованности метаданных не подтверждает совпадение хешей с байтами:
модуль не читает wrapper и не удостоверяет сетевой ответ, patch, runtime,
активацию поддержки или выбранный навык.

## Учёт и пределы поддержки

Все counts — настоящие неотрицательные `int`; `bool`, float и строки не
приводятся к числам. Проверяется:

```text
records = skills + invalid_records + withheld_records
records_without_english <= skills + withheld_records
len(withheld_record_ids) <= withheld_records
```

При ненулевом `withheld_records` список ID непустой. Число ID может быть меньше
числа удержанных строк: несколько строк могут нести один и тот же ID. Даже одна
валидная удержанная строка допустима, если её peer с тем же ID невалиден.
При пустых master-таблицах нулевые counts сохраняются как известные нули.

Поддержанные пределы потребителя, не игровые максимумы:

- от 1 до 64 документов и от 1 до 128 категорий;
- от 1 до 2 карт адресов: уникальные `needed-bundles.json` и опциональная
  `endgame-bundles.json`, причём первая обязательна;
- объявленный размер каждой карты от 1 байта до 32 MiB включительно;
- `byte_range` — JSON-список `[start, end]` с целыми
  `0 <= start < end <= 32 MiB`.

Статусы категорий точно соответствуют загруженным документам. Допускается
категория с `master: missing, english: missing`: helper может перечислить
не загруженную категорию из карты адресов. Это не доказательство, что English
документа не существует; `missing` описывает только этот набор входов.

Синтетические тесты проверяют разделение областей SHA, противоречия диапазонов,
типы и counts, неполные категории, точные границы, повторную валидацию,
удаление неизвестных свойств и независимость вложенных результатов от входа.
