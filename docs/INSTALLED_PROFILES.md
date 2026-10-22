# Каталожные профили установленных камней

`damage_lab.installedprofiles.project(records, installation, catalog)` — чистый
адаптер без файлов, сети и доступа к игре. `installation` уже имеет канонический
формат `installedskills`, а `catalog` — `supportcatalog`; оба повторно проверяются
их собственными `summary`. `summary(canonical)` повторяет проверки результата,
отбрасывает неизвестные свойства на каждом уровне и возвращает независимые данные.

`records` — объект с положительными canonical decimal ID в строковых ключах.
Допустимы только ID, наблюдаемые в installation. Значение — точная запись master
с объединённым `english` либо `null`; отсутствие ключа также означает пробел.
Ненулевая запись требует целочисленного `tlidbId`, равного ключу, и объявленного
загруженного master своей `category`. Если имеется `catalogPath`, он должен быть
`skill/<category>`. Удержанный каталогом ID не может стать разрешённой записью.
Имена, GUID и server instance не используются для поиска замены.
Число ненулевых records и число различных profiled ID не могут превышать
объявленный catalog.skills; повторные lookup одного ID не считаются разными
каталожными записями. Это сверка внутреннего accounting, не проверка bytes записи.

Непустой English payload требует объявленного English member той же категории.
При отсутствии English master-поля, например tags и эффективность added damage,
остаются доступными, но `hit.status=no_binding`. Здесь не пересчитываются SHA
каталога и не доказывается соответствие master/English bytes: их происхождение —
структурно проверенные заявления producer. Проверка artifact bytes и равенства
реальному package source относится к внешнему reader.

Формат результата — `tli-installed-skill-profiles-v1`, версия `0.1.0`,
`profile_version=0.2.1`. Верхние поля:

- `source {sha256, binding: caller_supplied}` и безопасная каноническая `catalog`
- `arithmetic_ready`, `runtime_verified`, `identity_verified`, `import_complete` —
  строго false; `activation`, `patch` — unknown; `effective_level` — null
- `client_layer`: captured, absent, invalid либо not_captured
- `members` и `accounting {members, profiled, gaps, reconciles}`

Незахваченный клиент требует `records=null` и даёт неизвестные members и все
counts, включая reconciles: `null`, а не пустой состав. Захваченный пустой слой
даёт `members=[]`, нулевые counts и reconciles=true; полнота импорта остаётся false.
Захваченный слой с `records={}` сохраняет наблюдаемые камни как отдельные пробелы.

Каждый member содержит `alias, group, tab_position, slot, path, skill_id, gem_level,
catalog_category, status, reason, profile`, а также `effective_level=null` и
`lookup_level_meaning=observed_gem_level_not_effective`. Порядок alias и source
координат проверяется повторно. `status=gap` с profile=null имеет фиксированную
причину invalid_skill_id, invalid_gem_level или catalog_record_missing.

`status=profiled` означает только вызов `skillprofile.profile` для точного ID на
наблюдаемом `gem_level`. Два экземпляра одного навыка на разных уровнях получают
отдельные lookup. Неизвестный уровень не заменяется единицей, reference level или
уровнем соседнего камня. Slot, membership и client flags не разрешают активацию.

Внутри `profile` сохранены существующие имена camelCase модели `skillprofile`
0.2.1: format, version, runtimeVerified, level, identity, tags, mainStat,
effectivenessOfAddedDamage, castSpeedField, hit. `tags` содержит только status,
skill, damageTypes и reserved; исходный tags.catalog удаляется. GUID ограничен
публичным ASCII token; неизвестные GUID, English description, instance/account
поля и произвольные вложенные объекты не копируются.

Числовые stated-поля сохраняют точный текст и единицы без float-преобразования.
Кандидат hit проверяется по типу урона, целочисленному lexical диапазону, уровню
lookup и парному binding. Известные field-level gaps сохраняются внутри profile,
поэтому profiled не означает, что hit существует или пригоден к арифметике.
`catalog_render_consistent` доказывает только согласованность каталожного render.

Нет вывода effective level, текущей версии клиента, post-20 роста, main-stat
привязки, работы поддержек или соответствия текущему panel skill. Этот адаптер
не строит сценарий rawspell, не умножает панель и не вычисляет DPS.

Проверка: `python -m unittest discover -s tests -p test_installedprofiles.py -v`.
