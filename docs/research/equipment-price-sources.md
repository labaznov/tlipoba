# Цены конкретных предметов: опубликованные источники и границы

Проверено 2026-10-22 по публичным исходникам. TLI Lens содержит реализацию
локального чтения, связывающую цену отдельной строки рынка с данными её предмета.
Это полезный контракт для исследования приобретения вещей. Поведение текущего
клиента, свежесть объявления и готовый игровой HTTP API этим не подтверждены.
Скрипты, процессы игры и ценовые API при проверке не запускались.

## TLI Lens: цена и роллы одной строки

Источник — `deafwave/tli-lens`, commit
[`687f5a752a963963830f223bd435bdb510265451`](https://github.com/deafwave/tli-lens/commit/687f5a752a963963830f223bd435bdb510265451).
Номера ссылок ниже относятся к физическим строкам закреплённых файлов.

`scripts/market_listings.py` выбирает клиентский объект `_AuctionHouseShowGoodV2`
и читает `GoodDatas[i].GoodData._Raw_Data`. Из одной записи берутся `PriceNum`,
`PriceType` и `ItemData._Raw_Data`. Предмет сохраняет `ConfigBaseId`, `Level`,
`Type1`, а для аффиксов — `Id`, `TLv`, `DynArgs` и имя списка `AffixList`;
дополнительно читаются поля памяти и плит. Это связь **предмет → объявленная цена**
на уровне опубликованного кода, а не runtime-проверка точных значений.
[Декодирование предмета:29–45](https://github.com/deafwave/tli-lens/blob/687f5a752a963963830f223bd435bdb510265451/scripts/market_listings.py#L29-L45),
[связь строки с ценой:47–57](https://github.com/deafwave/tli-lens/blob/687f5a752a963963830f223bd435bdb510265451/scripts/market_listings.py#L47-L57).

Reader зависит от внешнего `dps-debug` (`Proc`, `Lua`, `LIST_ORDER`), а числовые
`DynArgs` переводит во float/TS number: наличие роллов не гарантирует сохранение
исходной точности. Текущий клиент и внешняя реализация здесь не проверены.
[Зависимости:8–14](https://github.com/deafwave/tli-lens/blob/687f5a752a963963830f223bd435bdb510265451/scripts/market_listings.py#L8-L14).
Выбирается непустой view с новейшим числовым префиксом имени; это не доказывает
текущий выбранный query/cohort или свежесть. Вывод не содержит season/server,
времени, source hash или стабильного auction ID. `n` — позиция, а создаваемый
`market-*` content hash служит идентификатором предмета модели.
[Listing и model ID:8–27](https://github.com/deafwave/tli-lens/blob/687f5a752a963963830f223bd435bdb510265451/packages/guide/src/listing.ts#L8-L27).

`market.ts` принимает сохранённый JSON либо вызывает локальный reader. Для обычной
оценки gear проверяется `PriceType` FE; плиты сохраняются с локальным `at`, базой,
формой, линиями и ценой. Одинаковая запись не получает новое время при каждом
повторном наблюдении; cache не гарантирует доступность покупки.
[Вход:38–44](https://github.com/deafwave/tli-lens/blob/687f5a752a963963830f223bd435bdb510265451/packages/guide/scripts/market.ts#L38-L44),
[cache:126–135](https://github.com/deafwave/tli-lens/blob/687f5a752a963963830f223bd435bdb510265451/packages/guide/scripts/market.ts#L126-L135),
[currency gate:162–165](https://github.com/deafwave/tli-lens/blob/687f5a752a963963830f223bd435bdb510265451/packages/guide/scripts/market.ts#L162-L165).

## Оценки базовых типов — другой источник

Документ ETor в том же pin описывает reverse-engineered snapshot/history по
season и item ID. Он прямо исключает rare/affixed gear и цены legendary по роллам.
Его исторические примеры не подтверждают текущий сезон или работу сервиса.
[Область ETor:76–78](https://github.com/deafwave/tli-lens/blob/687f5a752a963963830f223bd435bdb510265451/docs/etor-api.md#L76-L78).
TITrack хранит FE-оценки по `(config_base_id, season_id)`, а TLI Companion
агрегирует цены по item ID. Эти записи не содержат роллов конкретного объявления;
это reference prices, не подтверждённые продажи или ask выбранной вещи.
[TITrack schema:86–97](https://github.com/astockman99/TITrack/blob/7798e02db8cfc5fb3b5eb927e3600fef99815b5e/src/titrack/db/schema.py#L86-L97),
[Companion median:696–717](https://github.com/julien-szy/tli-companion/blob/33f1d091f3a7e4f71a0b177acf31c2e5e6d5ba83/server/server.js#L696-L717).

### TITrack: откуда берётся reference price

В том же pin TITrack parser читает напечатанные `XchgSearchPrice`, берёт первый
`refer` запроса и сопоставляет ответ по `SynId`. Parser пытается выделить FE
unit prices, преобразованные во `float`; записи объявлений и роллы не извлекаются.
Статический разбор ветвей обнаружил ограничение: в старом порядке
non-FE currency → prices → FE currency буфер предыдущей секции может попасть
в FE-массив. Это не выполненный эксперимент; универсальная корректность
фильтрации смешанных валют не подтверждена.
[Request:139–150](https://github.com/astockman99/TITrack/blob/7798e02db8cfc5fb3b5eb927e3600fef99815b5e/src/titrack/parser/exchange_parser.py#L139-L150),
[response:152–210](https://github.com/astockman99/TITrack/blob/7798e02db8cfc5fb3b5eb927e3600fef99815b5e/src/titrack/parser/exchange_parser.py#L152-L210).

Collector записывает reference price по типу и сезону. Метод `percentile_10`
выбирает индекс `max(0, int(n * 0.10) - 1)` и предполагает готовую сортировку,
сам её не выполняет. Настроенные 300 секунд не гарантируют freshness: очистка
запускается только при более чем 50 pending-запросах; при сопоставлении возраст
не проверяется.
[Индекс:213–238](https://github.com/astockman99/TITrack/blob/7798e02db8cfc5fb3b5eb927e3600fef99815b5e/src/titrack/parser/exchange_parser.py#L213-L238),
[сопоставление и cache:552–590](https://github.com/astockman99/TITrack/blob/7798e02db8cfc5fb3b5eb927e3600fef99815b5e/src/titrack/collector/collector.py#L552-L590).

Request parser не сохраняет остальные фильтры поиска: цена, записанная по базе,
может происходить из запроса конкретных роллов. Нет связи с отдельным listing,
его affix/rolls, регионом и полнотой страниц. Это не доказанная цена всей базы
или выбранной вещи. Следующий опыт должен сохранить полный коррелированный
запрос/ответ и проверить, печатает ли игра поля объявлений, которые этот parser
игнорирует. Код TITrack при исследовании не исполнялся; его local API/cloud
не являются игровым request-контрактом.

## Следующий необходимый witness

Нужен проверенный ограниченный снимок текущего разрешённого read-only адаптера:
цена и валюта связаны с тем же предметом, сохранены точные числовые лексемы,
полные native IDs, списки/tiers и координаты. Отдельно фиксируются источник/hash,
версия клиента и известные market context/time; неизвестные поля не выводятся
из page index. Ключ строки снимка идентифицирует наблюдение, не серверное объявление.
Отсутствие/truncation, смена страницы и повторное наблюдение требуют явной проверки.

Такой источник затем должен пройти существующую точную нормализацию эффектов:
неизвестные условия, единицы и эффекты остаются пробелами. Полная замена убирает
вклады старой вещи и добавляет новой при общих условиях; только после покрытия
пулов допустимы [сравнение](../RAW_UPGRADES.md) и цена прироста. Эта схема не закрывает
нынешние RAW-пробелы Carino и не подтверждает чужие DPS-модели. Нового калькулятора,
HTTP-контракта или числового рейтинга вещей эта заметка не реализует.
