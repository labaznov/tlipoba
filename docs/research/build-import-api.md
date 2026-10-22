# Импорт полного билда по игровому share code / ID

Дополнение от 2026-10-22: [исследование клиентского и сетевого пути](game-client-transport.md)
проверяет рыночные парсеры, азиатские планировщики и официальный web-клиент XD.
Найдено сопоставление печатных сообщений по `SynId`; подготовлен
[план наблюдения на Windows](windows-transport-plan.md). Полный игровой
code→build request-контракт по-прежнему не установлен.

Проверено 2026-10-21. Вопрос: можно ли получить полный билд непосредственно с серверов Torchlight: Infinite по коду или ID, без запущенной игры? Исследованы публичные исходники и первичные страницы; пользовательские коды, аккаунты и экспорты на сторонние сервисы не отправлялись. Чужие приложения не запускались.

## Результат

**Публичный документированный игровой endpoint полного билда не найден.** Не установлены URL, request/response schema, способ авторизации, правила регионов и срока действия игрового share code. Поэтому реализовать сейчас честный рабочий HTTP-загрузчик по игровому ID на основании найденного нельзя. Это результат ограниченного исследования, а не доказательство отсутствия внутреннего API игры.

TLI Hero Rank прямо сообщает, что публичного Hero Ranking API нет, данные собираются из клиента, а доступный ranking-cache не содержит всех деталей вещей и slates. Импорт/экспорт персонажа у них пока отсутствует. Это первичное сообщение разработчика инструмента, не официальная спецификация XD. [FAQ, разделы про API, gear и import](https://tliherorank.com/about/).

Обнаруженные HTTP `/b/<id>` и `build-code/decode` относятся к **TLI Builder**, а не игровому серверу. Его `tli1_` — самодостаточный сжатый JSON собственного планировщика. Поддержка этого формата полезна отдельно, но не решает загрузку игрового build code. [Контракт формата и схема обмена](https://github.com/Tyrayla/TLIBuilder/blob/1454bd4f04d509d5819e19605dba34273c0b222a/docs/architecture/build-codes-and-sharing.md#L4-L15).

## Проверенные пути импорта

| Источник | Вход и операция | Что подтверждено | Чего не даёт |
| --- | --- | --- | --- |
| TLI Builder codec | `tli1_` + Base64 URL encoding от zlib(JSON); schema version 2 | Код содержит состояние самого планировщика; backend локально декодирует и восстанавливает часть производных полей из своего сезонного каталога. [Python encoder](https://github.com/Tyrayla/TLIBuilder/blob/1454bd4f04d509d5819e19605dba34273c0b222a/backend/build_code.py#L1-L32), [rehydration contract](https://github.com/Tyrayla/TLIBuilder/blob/1454bd4f04d509d5819e19605dba34273c0b222a/docs/architecture/build-codes-and-sharing.md#L41-L45) | Не декодирует обычный игровой share code и не обращается к аккаунту игрока |
| TLI Builder share service | `GET https://api.tlibuilder.com/b/<id>` | Возвращает сохранённую строку кода планировщика; browser затем проверяет префикс `tli1_`. [Fetch](https://github.com/Tyrayla/TLIBuilder/blob/1454bd4f04d509d5819e19605dba34273c0b222a/src/renderer/src/api/share.ts#L88-L130), [prefix validation](https://github.com/Tyrayla/TLIBuilder/blob/1454bd4f04d509d5819e19605dba34273c0b222a/src/renderer/src/utils/resolveImportInput.ts#L27-L49) | ID сервиса TLI Builder не равен игровому ID/BDID |
| TLI Lens текущий importer | Локальный JSON из `dps-debug reader/export.py` | `start.ts` принимает уже имеющийся export, содержит file-based start state; инструментарий описывает чтение уже открытой build page `ViewPlayerBDReference`. [start.ts](https://github.com/deafwave/tli-lens/blob/687f5a752a963963830f223bd435bdb510265451/packages/guide/src/start.ts#L1-L22), [источник страницы](https://github.com/deafwave/tli-lens/blob/687f5a752a963963830f223bd435bdb510265451/.claude/skills/tli-game/SKILL.md#L19-L23) | В просмотренных публичных entrypoints нет resolver по игровому ID; нужен захват клиента/сохранённый export |
| TLI Hero Rank | Периодически захваченные ranking-cache и OCR leaderboard | Разработчик прямо описывает capture из клиента, ограничения полноты и отсутствие character import/export. [FAQ](https://tliherorank.com/about/) | Не полный актуальный билд произвольного персонажа |
| TLI Companion | Локальный `HeroRanking…` JSON, созданный просмотром рейтинга в игре | `meta.js` читает cache с диска и агрегирует класс/скиллы/экипировку рейтинга; README явно описывает этот путь. [Исходник](https://github.com/julien-szy/tli-companion/blob/main/src/meta.js#L1-L16), [README](https://github.com/julien-szy/tli-companion#is-it-safe) | Это локальный кэш, не игровой публичный API; точные полные rolls всех предметов/систем не обещаны |

## Реально найденный HTTP-контракт — только TLI Builder

Ниже описание чужого публичного клиента для различения форматов. Вызовы сервиса в рамках исследования не выполнялись, работоспособность endpoint не проверялась.

| Операция | Request | Response по исходнику | Авторизация / границы |
| --- | --- | --- | --- |
| Создать share | `POST https://api.tlibuilder.com/b`, JSON `{code, preview?}` | JSON `{id, url}` | Открытый клиент не добавляет Authorization; это не подтверждает бессрочность или отсутствие серверных ограничений. Операция публикует на сторонний сервис и нам для игрового импорта не нужна. [POST и тип](https://github.com/Tyrayla/TLIBuilder/blob/1454bd4f04d509d5819e19605dba34273c0b222a/src/renderer/src/api/share.ts#L59-L85), [payload](https://github.com/Tyrayla/TLIBuilder/blob/1454bd4f04d509d5819e19605dba34273c0b222a/src/renderer/src/api/share.ts#L123-L130) |
| Прочитать share | `GET https://api.tlibuilder.com/b/<id>` | Текст `tli1_…`, ограничение клиента 512 KiB, timeout 15 секунд | Клиент без добавленного Authorization; GET извлекает уже опубликованный planner code. [Код чтения](https://github.com/Tyrayla/TLIBuilder/blob/1454bd4f04d509d5819e19605dba34273c0b222a/src/renderer/src/api/share.ts#L88-L130) |
| Декодировать planner code | Локальный backend `POST /api/build-code/decode` | Декодированный build object, миграция schema и rehydration из сезонного каталога | Это endpoint локального приложения, не универсальный публичный host игры. [Архитектура](https://github.com/Tyrayla/TLIBuilder/blob/1454bd4f04d509d5819e19605dba34273c0b222a/docs/architecture/build-codes-and-sharing.md#L41-L49) |

TLI Builder код доступен под MIT, но его compiled game dataset имеет отдельные ограничения; клонирование engine-кода само по себе не даёт необходимых seasonal catalogs и права зеркалировать их. [LICENSE](https://github.com/Tyrayla/TLIBuilder/blob/1454bd4f04d509d5819e19605dba34273c0b222a/LICENSE), [DATA-LICENSE](https://github.com/Tyrayla/TLIBuilder/blob/1454bd4f04d509d5819e19605dba34273c0b222a/DATA-LICENSE.md#L19-L29).

## Что известно о самом игровом коде

Автор TLI Builder в обсуждении запуска описывал игровые коды как ссылку/ID серверных данных и сообщал, что рабочего декодирования или импорта у него нет. Это авторское наблюдение мая 2026, а не доказанный формат игрового протокола. [Первичное обсуждение автора](https://www.reddit.com/r/TorchlightInfinite/comments/1tmtkdd/tli_builder_a_tli_build_planner_with_calculations/).

Поэтому недопустимы выводы «Base64 декодировался, значит весь билд внутри» и «planner share API примет игровой код». Нужна отдельная подтверждённая связь: входной игровой code → идентификатор запроса → ответ с build graph → правила доступа. Этой цепочки найденные публичные источники не дают.

## Что нужно для следующего шага

Это предлагаемый план, не известная спецификация XD.

1. Проверить уже разрешённые локальные read-only captures: связаны ли BDID/share code и конкретный response; фиксировать исходное имя RPC/схему, регион и версию клиента без раскрытия токенов.
2. Искать публичную документацию или исходник клиента именно подтверждённого запроса; не подбирать endpoints на боевых серверах и не отправлять игровые коды случайным сторонним сервисам.
3. Если понадобится authenticated game session, сначала установить поддерживаемый способ получения доступа и жизненный цикл сессии. Пароль игры или извлечение произвольных токенов не являются автоматически допустимым контрактом импортёра.
4. Пока нет сетевого контракта, развивать **offline importer сохранённого полного захвата**: файл можно повторно читать и считать при выключенной игре. Создание нового захвата остаётся обязанностью внешнего read-only exporter.
5. Разделить интерфейсы: `game_reference` (пока unresolved), `native_capture` (локально), `compendium_json`, `tlibuilder_code`. Проверять completeness и provenance каждого варианта, не обещая одинаковую точность.

## Не установлено

- URL и транспорт игрового build resolver: HTTP, WebSocket или игровой RPC нельзя выбрать по имеющимся данным
- Поля запроса/ответа и соответствие share code, BDID, character ID и account ID
- Наличие публичного режима, необходимость входа, региональные server IDs и ограничения приватных профилей
- Срок жизни, отзыв и изменяемость build-reference, полнота memories/prisms/pacts/skills/роллов
- Условия публичного API и rate limits

Отсутствующие поля не заполняются правдоподобными предположениями. Ближайший проверенный путь к полному билду — локальный экспорт и последующий офлайн-расчёт; кэш рейтинга является дополнительным неполным источником.
