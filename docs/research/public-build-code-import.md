# Что публичные инструменты импортируют по «build code»

Проверено 2026-10-22. В перечисленных ниже опубликованных цепочках не найден
контракт **игровой Pro Build code → полный игровой билд**. Найдены работающие
форматы документов планировщиков, их собственные share services и локальные
адаптеры. Это ограниченный результат проверки конкретных entrypoints, не
утверждение об отсутствии любых частных API.

Исходники читались без установки или исполнения. Запросы шли только к публичным
GitHub source/metadata; игровые endpoints, credentials и реальные коды не использовались.
Физические номера строк проверены по raw blobs, не по нумерации web-renderer.

## Проверенные версии

На момент проверки GitHub HEAD совпал с указанным pin. Даты — committer UTC.

| Проект | Commit | Дата |
|---|---|---|
| TLIBuilder | [`1454bd4f04d509d5819e19605dba34273c0b222a`](https://github.com/Tyrayla/TLIBuilder/commit/1454bd4f04d509d5819e19605dba34273c0b222a) | 2026-10-19 |
| TLIPoB | [`1da3826ab5539536a83378fd4aea20ffb3559f98`](https://github.com/aclinia/torchlight-of-building/commit/1da3826ab5539536a83378fd4aea20ffb3559f98) | 2026-04-15 |
| TITrack | [`7798e02db8cfc5fb3b5eb927e3600fef99815b5e`](https://github.com/astockman99/TITrack/commit/7798e02db8cfc5fb3b5eb927e3600fef99815b5e) | 2026-10-18 |
| TLI Lens | [`687f5a752a963963830f223bd435bdb510265451`](https://github.com/deafwave/tli-lens/commit/687f5a752a963963830f223bd435bdb510265451) | 2026-10-19 |
| TLI Companion, опубликованный код | [`604e05e0ae0c88798abfbedac5998a288848c768`](https://github.com/julien-szy/tli-companion/commit/604e05e0ae0c88798abfbedac5998a288848c768) | 2026-10-22 |

## TLIBuilder: декодирование своего документа

Desktop handler `POST /api/build-code/decode` принимает `{code}` и возвращает
`{build}`. Он вызывает локальный codec и загружает legendary definitions выбранного
сезона для rehydration. Codec требует `tli1_`, декодирует Base64URL, распаковывает
zlib и читает JSON со schema marker `v=2` либо поддержанной миграцией. Он не
выполняет game lookup. [Handler:654–684](https://github.com/Tyrayla/TLIBuilder/blob/1454bd4f04d509d5819e19605dba34273c0b222a/backend/server.py#L654-L684),
[format:12–32](https://github.com/Tyrayla/TLIBuilder/blob/1454bd4f04d509d5819e19605dba34273c0b222a/backend/build_code.py#L12-L32),
[decoder:175–209](https://github.com/Tyrayla/TLIBuilder/blob/1454bd4f04d509d5819e19605dba34273c0b222a/backend/build_code.py#L175-L209).

Share URL `/b/<id>` сначала получает текст кода с собственного
`api.tlibuilder.com`; resolver проверяет префикс `tli1_` и передаёт его тому же
декодеру. Следовательно, наличие HTTP fetch здесь подтверждает обмен planner
documents. [Resolver:27–49](https://github.com/Tyrayla/TLIBuilder/blob/1454bd4f04d509d5819e19605dba34273c0b222a/src/renderer/src/utils/resolveImportInput.ts#L27-L49),
[share transport:100–130](https://github.com/Tyrayla/TLIBuilder/blob/1454bd4f04d509d5819e19605dba34273c0b222a/src/renderer/src/api/share.ts#L100-L130).
Browser worker также отправляет вызов в собственное ASGI-приложение внутри
Pyodide. Это не новый игровой transport. [Worker:104–123](https://github.com/Tyrayla/TLIBuilder/blob/1454bd4f04d509d5819e19605dba34273c0b222a/src/renderer/src/web/computeWorker.ts#L104-L123).

## TLIPoB: прослежена ветка после modal

Это новая детализация относительно прежнего обзора: `handleImportBuild` вызывает
`decodeBuildCode`, затем `importBuild`. URL `/import/$code` использует ту же цепочку.
Decoder распаковывает Base64URL через `inflateSync`, разбирает JSON и проверяет
versioned SaveData schema `{v:1,d:...}`. Здесь нет запроса за игровым payload.
[UI handler:295–309](https://github.com/aclinia/torchlight-of-building/blob/1da3826ab5539536a83378fd4aea20ffb3559f98/src/routes/index.tsx#L295-L309),
[URL handler:5–17](https://github.com/aclinia/torchlight-of-building/blob/1da3826ab5539536a83378fd4aea20ffb3559f98/src/routes/import.%24code.tsx#L5-L17),
[codec:32–58](https://github.com/aclinia/torchlight-of-building/blob/1da3826ab5539536a83378fd4aea20ffb3559f98/src/lib/build-code.ts#L32-L58),
[schema:106–132](https://github.com/aclinia/torchlight-of-building/blob/1da3826ab5539536a83378fd4aea20ffb3559f98/src/lib/schemas/save-data.schema.ts#L106-L132).

`importBuild` создаёт новый save ID и сохраняет документ/индекс. ID генерируется
через `crypto.randomUUID`; сохранение использует localStorage. Такой UUID относится
к локальному документу, а Base64URL содержит его данные, не игровой BDID.
[Import:21–43](https://github.com/aclinia/torchlight-of-building/blob/1da3826ab5539536a83378fd4aea20ffb3559f98/src/lib/import-utils.ts#L21-L43),
[storage:29–49, 69–81](https://github.com/aclinia/torchlight-of-building/blob/1da3826ab5539536a83378fd4aea20ffb3559f98/src/lib/saves.ts#L29-L81).

## TITrack, Companion и Lens: другие источники входа

TITrack `GET /api/player` возвращает уже переданный приложению PlayerInfo из
log stream. `GET /api/inventory` читает slot states собственного repository и
агрегирует количества по ConfigBaseId. Его просмотренный `parse_line` разбирает
bag/context/zone/player события журнала. Эти endpoints не принимают Pro Build
code и не возвращают полный состав навыков, талантов и роллов по такому коду.
[Player:145–163](https://github.com/astockman99/TITrack/blob/7798e02db8cfc5fb3b5eb927e3600fef99815b5e/src/titrack/api/app.py#L145-L163),
[inventory:68–86](https://github.com/astockman99/TITrack/blob/7798e02db8cfc5fb3b5eb927e3600fef99815b5e/src/titrack/api/routes/inventory.py#L68-L86),
[parser:23–125](https://github.com/astockman99/TITrack/blob/7798e02db8cfc5fb3b5eb927e3600fef99815b5e/src/titrack/parser/log_parser.py#L23-L125).

У актуального Companion действительно есть `/api/builds`: POST принимает
пользовательский JSON version 1 с собственным ID, шагами покупки и loadout;
GET по 36-символьному ID возвращает JSON из своей SQLite. Это конкретный
проверенный API документов, не game-code resolver. Он не устанавливает XD session
или соответствие документа игровому Pro Build. [POST/GET:424–457](https://github.com/julien-szy/tli-companion/blob/604e05e0ae0c88798abfbedac5998a288848c768/server/server.js#L424-L457),
[принимаемая schema:107–136](https://github.com/julien-szy/tli-companion/blob/604e05e0ae0c88798abfbedac5998a288848c768/server/sanitize.js#L107-L136).

Просмотренный Lens `state.mjs` запускает локальный `tli_dump --portable-json`
либо читает последний сохранённый dump при `--reuse`. Это адаптер открытой
страницы клиента. Запускать его для настоящего исследования не требовалось.
[Entrypoint:1–17](https://github.com/deafwave/tli-lens/blob/687f5a752a963963830f223bd435bdb510265451/.claude/skills/tli-game/state.mjs#L1-L17).

## Что это меняет для tlipoba

В просмотренных цепочках нет новых данных для игрового request message,
transport/framing, XD authorization/session, response envelope или code→response
binding. Доступность planner share endpoints эти пробелы не закрывает. Private
extensions, закрытые сервисы, shipped binaries и иные ревизии сюда не входят.

Практическая граница остаётся прежней: автоматически принимать сохранённый
source-bound export/локальный adapter output, сохраняя unknown identity/freshness.
Возможный импорт planner document должен иметь отдельный тип происхождения;
его schema defaults, каталожная rehydration и локальный save UUID не становятся
наблюдаемыми игровыми значениями. Новый HTTP resolver игрового кода на основании
этих исходников реализовать нельзя; придумывать route или отправлять код в чужой
planner service оснований нет.
