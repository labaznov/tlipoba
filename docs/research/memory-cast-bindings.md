# Привязки скорости в памяти героя

Проверено 2026-10-22 по сохранённому снимку и локальному каталогу. Из четырёх
строк со speed wording три имеют уникальное полное совпадение native `Id` с
catalog `modifierId`. Одна base-stat строка такой привязки не имеет. Это
результат исследования источника, не новая сумма скорости или готовый DPS.

## Что подтверждают сохранённые данные

| Строка | Каталожная привязка | Граница |
| --- | --- | --- |
| Fixed affix, Origin | Один полный ID в `fixedAffixes`, один tier | Отдельные catalog literal и собственное значение |
| Fixed affix, Progress | Один полный ID в `fixedAffixes`, текст minion cast speed | Не считать player cast speed |
| Random affix, Progress | Один полный ID в `randomAffixes`, composite template | Одно собственное значение не назначает роли двум строкам |
| Base stat, Progress | Нет полного ID в master | Не подбирать запись по тексту, tier или префиксу |

В `hero-memory/master` проверены 1299 modifier IDs без коллизий. Master и English
извлечены как точные byte slices; SHA-256 членов соответственно
`a5b337e2fb22738c410cdf9cd53bc74cb190f2b7a5479e9a31dc5523e4e6687d` и
`b307c35385638418d1ff20ae7d7a6dbe3ef5ff3338acd92caf4afe697db89e2e`.
Нативные строки расположены в
`sections.HeroCharacter.data.HeroJewels[]._Raw_Data.AffixList`; server mirror
содержит собственные ID и DynArgs. Четыре mirror-сравнения совпали при точном
Decimal; три каталожных литерала также согласованы с собственными значениями.
Совпадение чисел не устанавливает increased/more operator или rank scaling.

Проверка memory type условна: перевод native `BaseId` в имя типа использует
существующий `hero_memory.TYPES` экспортёра. Сам master не даёт native type-ID
контракта. Empty Condition/Filter/Behavior не подтверждают активацию эффекта.

## Где отсутствует следующий источник

Отдельный поиск проверил все 117 сохранённых cache files: 360 logical members
в 42 wrappers, ещё 16 JSON и 59 raw/binary files. Полные native base-stat IDs
не найдены. В сохранённом HeroCharacter остаются только собственные строки,
server mirrors и их копии native graph; ссылки на canonical catalog record
или level-table key нет. Compressed/encoded content отдельно не декодировался;
отрицательный результат ограничен этими файлами и одним сохранённым разделом.

Для следующей привязки нужна таблица, содержащая полный native base-stat ID и
смысл его level/tier, либо явно именованный catalog key в исходных данных.
Префиксная замена и matching текста такой таблицей не являются. Активация,
оператор, состав полного пула и актуальность patch остаются неизвестными.

## Исправление точности и воспроизводимость

В первом исследовательском скрипте обнаружена потеря точности при сравнении
через float. Новая версия сохраняет JSON number lexemes и сравнивает bounded
ASCII decimal через Decimal: до 12 integer и 9 fraction digits. Некорректный
вход даёт fixed unknown/issue. Исторические файлы сохранены; повторный точный
прогон четырёх отношений не изменил фактических выводов. Синтетические тесты
прошли путь RED → GREEN. Этот код пока не перенесён в production importer.

Evidence IDs отдельного экспортёра: `20261022-0725-memory-cast-bindings`,
`20261022-0730-memory-id-witness`, `20261022-0735-memory-mirror-exactness`.
Их `handoff/reports/<ID>.md` и `captures/<ID>/` содержат локальные input hashes,
byte ranges, сохранённые before maps, скрипты и отчёты проверок. Данные игрока
остаются локальными. Проверяемые SHA-256:

| Артефакт | SHA-256 |
| --- | --- |
| 0725 summary | `659e235e56d5779aaa320f7021dffe20ce99fba990b6ad176a4ed0a2789aa49c` |
| 0730 summary | `5a37686aae215857afff3cae993823ad9a78c50d3e8d8646f4e0b9b43eba92f3` |
| 0735 `mirror_exact.py` | `c36eaf5cbb0375e4685254abdee3e2752adb56c93a9f5e5047fdd18fe2f9c045` |
| 0735 verification | `f1ac4f9b1d31f489ceab5183770cb0495b6cdd16fef88f2f7cbea1a5a465a22c` |

Следующая реализация может сохранять точные definition joins и отдельные
own/catalog observations. Она не должна автоматически превращать их в полный
cast pool. Связанные границы: [cast inputs](cast-input-coverage.md),
[composite field roles](cast-field-role-witness.md), [ранги памяти](hero-memory-ranks.md).
