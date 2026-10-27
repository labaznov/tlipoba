# Каталожные записи установленных навыков

`skillcatalogbundle.read(package, descriptor, source_sha256, installation)`
читает фиксированный `installed-skill-catalog.json` producer версии `0.1.0`.
Результат — `(profiles, origin)`, где origin хранит абсолютный путь, точный SHA256
прочитанных bytes, размер и признак хранения канонического документа.

Diagnostic artifact содержит собственный source hash, declared каталог,
`requestedIds` и map точных catalog records. Reader проверяет SHA artifact,
source hash и версии, четыре literal false flags и типизированные counts.
Requested IDs должны точно совпасть с отсортированными уникальными положительными
skill IDs из source-bound установленного состава. Records содержат только
запрошенные canonical decimal keys и настоящие объекты; отсутствующие записи
не заменяются соседними ID, названиями или пустыми объектами.
Subset записей не может превышать число resolved records полного каталога.

Установленный состав повторно проверяется через `installedskills.summary`,
каталожные metadata — через `supportcatalog.project`. Затем
`installedprofiles.project` заново вычисляет typed profile из supplied record
через `skillprofile.profile`; готовые числовые профили producer не принимаются.
Lookup выполняется на наблюдаемом gem level. Он не становится effective level,
подтверждением patch, активации либо основанием для точного DPS.

При неизвестном client layer `requestedIds`, `records` и counts
requested/records/missing равны `null`; количество загруженных каталоговых
документов известно отдельно. Захваченный пустой состав допускает `[]`, `{}` и
нулевые counts. Counts records описывают subset в artifact, а не все строки
полного каталога из metadata.

Проверенный error artifact возвращает `profiles=null`, origin со `stored=0` и
все четыре counts `null`. Code входит в фиксированный source/catalog/cache enum,
совпадает с descriptor, а semantic records запрещены. Только
`source_missing`/`source_unreadable` допускают отсутствующий source hash.
Diagnostic lookup требует канонический установленный состав того же источника.

Reader открывает только artifact, с лимитом 64 MiB и чтением не более limit+1.
Допустим положительный integer limit до 64 MiB. Строгий UTF-8 JSON исключает BOM,
повторные ключи, nonfinite, overflow и ненулевой float underflow. Source SHA
вычисляет вызывающая сторона; сам reader не перечитывает source или cache.
Hashes/диапазоны каталога остаются структурно проверенными заявлениями producer,
а не новой проверкой сетевого ответа или текущего клиента.

Обычные команды импорта и расчёта подхватывают descriptor
`manifest.installedSkillCatalog` автоматически. Полученный
`installed_skill_profiles` сохраняется в SQLite, JSON и обоих HTML. При отсутствии
descriptor старый пакет остаётся частичным с явным coverage gap; обычному игроку
не требуется переписывать параметры навыков. Source-bound lookup не разрешает
effective level и не добавляет каталожный hit поверх готовой панели.
