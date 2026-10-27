# Ранг обычного таланта: модели сторонних движков

Проверено 2026-10-22. Прочитаны закреплённые исходники и тесты; код не запускался,
compiled datasets не загружались. Это первичные источники **об устройстве этих
программ**, а не официальный контракт игры или Compendium. Персонаж и его значения
в исследовании не используются.

Все GitHub line anchors сверены по физическим строкам закреплённых blobs:
обычный raw GET совпал с Contents API, а Git blob SHA проверен по байтам.
Нумерация нормализованного текстового ответа web-tool для этих ссылок не используется.

Вывод: оба просмотренных движка используют значение за первое очко и линейное
масштабирование. Они не доказывают, что `mods[].value` нашего Compendium-кэша имеет
тот же смысл. Для multi-point узлов `rank_scaling` остаётся неизвестным.

## Закреплённые версии

| Проект | Commit и дата UTC | Область доказательства |
|---|---|---|
| TLIBuilder | [`1454bd4f04d509d5819e19605dba34273c0b222a`](https://github.com/Tyrayla/TLIBuilder/commit/1454bd4f04d509d5819e19605dba34273c0b222a), 2026-10-19 06:32:05 | Контракт Python resolver и его тестов; не игровая проверка rank scaling |
| torchlight-of-building / TLIPoB | [`1da3826ab5539536a83378fd4aea20ffb3559f98`](https://github.com/aclinia/torchlight-of-building/commit/1da3826ab5539536a83378fd4aea20ffb3559f98), 2026-04-15 03:50:47 | Контракт TypeScript planner; актуальность для SS14 не установлена |

## Что проверено в TLIBuilder

`resolve_nodes` читает `slots[].nodeStates[node_id]`, находит запись среди
`season_trees[*].nodes`, выбирает `effects[]` и пропускает невыделенные узлы.
`_resolve_node` разбирает эффект и умножает каждый числовой contribution на points.
Комментарий явно называет исходный amount значением rank 1.
[Контракт, L5–8](https://github.com/Tyrayla/TLIBuilder/blob/1454bd4f04d509d5819e19605dba34273c0b222a/backend/engine/node_resolver.py#L5-L8),
[resolver, L75–100](https://github.com/Tyrayla/TLIBuilder/blob/1454bd4f04d509d5819e19605dba34273c0b222a/backend/engine/node_resolver.py#L75-L100),
[выбор узла, L164–184](https://github.com/Tyrayla/TLIBuilder/blob/1454bd4f04d509d5819e19605dba34273c0b222a/backend/engine/node_resolver.py#L164-L184).

Тесты задают искусственные micro и medium effects и ожидают последовательности
`0.09, 0.18, 0.27` и `0.18, 0.36, 0.54` при 1–3 points; legendary проверяется при
одном point. Отдельная parity-проверка сравнивает результат со старыми SS12 recipes
для ограниченного набора без conditional/per-scaling recipes. Это внутренняя
согласованность реализаций, не независимое наблюдение клиента.
[Rank tests, L32–52](https://github.com/Tyrayla/TLIBuilder/blob/1454bd4f04d509d5819e19605dba34273c0b222a/backend/tests/test_node_resolution.py#L32-L52),
[recipe parity, L266–296](https://github.com/Tyrayla/TLIBuilder/blob/1454bd4f04d509d5819e19605dba34273c0b222a/backend/tests/test_node_resolution.py#L266-L296).

## Что проверено в TLIPoB

Импортёр дерева извлекает `rawAffix` из tooltip SVG image, а `maxPoints` — из
отдельного SVG text. В этом участке нет деления affix на maxPoints.
[Извлечение текста, L81–97](https://github.com/aclinia/torchlight-of-building/blob/1da3826ab5539536a83378fd4aea20ffb3559f98/src/scripts/generate-talent-tree-data.ts#L81-L97),
[парсер дерева, L124–154](https://github.com/aclinia/torchlight-of-building/blob/1da3826ab5539536a83378fd4aea20ffb3559f98/src/scripts/generate-talent-tree-data.ts#L124-L154).

При построении allocated node `rawAffix` передаётся в `scaleTalentAffix` с points.
Функция масштабирует числовой текст на `max(1, points)` перед разбором модификаторов;
два шаблона cooldown исключены из масштабирования. Это не универсальная схема
ролей всех чисел в игровом тексте. [Вызов, L363–367](https://github.com/aclinia/torchlight-of-building/blob/1da3826ab5539536a83378fd4aea20ffb3559f98/src/tli/storage/load-save.ts#L363-L367),
[реализация, L40–84](https://github.com/aclinia/torchlight-of-building/blob/1da3826ab5539536a83378fd4aea20ffb3559f98/src/tli/talent-affix-utils.ts#L40-L84),
[публичная функция, L140–146](https://github.com/aclinia/torchlight-of-building/blob/1da3826ab5539536a83378fd4aea20ffb3559f98/src/tli/talent-affix-utils.ts#L140-L146).

Тесты фиксируют `8% × 2 → 16%`, `0.09 × 3 → 0.27` и исключения cooldown.
Путь расчёта собирает node affix только при `points > 0`: поведение helper при
нуле не означает эффект невыделенного узла. [Tests, L5–51](https://github.com/aclinia/torchlight-of-building/blob/1da3826ab5539536a83378fd4aea20ffb3559f98/src/tli/talent-affix-utils.test.ts#L5-L51),
[collector, L46–64](https://github.com/aclinia/torchlight-of-building/blob/1da3826ab5539536a83378fd4aea20ffb3559f98/src/tli/calcs/affix-collectors.ts#L46-L64).

## Что говорит TLIDB и чего это не устанавливает

Разделы Talent/Talents Help и Talent Node Related объясняют получение и расход
points, активацию узлов и prerequisites. Просмотренные абзацы не определяют, к какому rank относится число
каталога, и не задают уравнение изменения эффекта с rank. На той же странице
различаются версии отдельных правил сброса; доступность сегодня не датирует
каждый абзац. TLIDB обозначает себя неофициальным зеркалом beta data.
[Talent Help](https://tlidb.com/en/Talent),
[Talents Help](https://tlidb.com/en/Talents),
[Talent Node Related](https://tlidb.com/en/Talent_Node_Related).

## Точная граница для нашего кэша

`effects[]` первого движка и `rawAffix` второго — исходный текст их собственного
pipeline. Они не являются схемой Compendium `nodes[].mods[]{value, unit, text}`.
Наличие отдельного `maxPoints`, совпадение описания со структурным render и
одинаковая арифметика двух программ не устанавливают нормализацию `value`.

Следующий недостающий binding: для точной версии Compendium catalog связать
конкретный `mods[].value` с **rank-1 effect**, **effect при max rank** или отдельной
таблицей rank. Нужен источник преобразования каталога либо первичное наблюдение
того же точно идентифицированного узла при известных rank с сохранёнными
координатами и происхождением. Вычисленный native ID остаётся отдельной
неподтверждённой привязкой; сравнение только описаний её не заменяет.

Если линейность отдельно подтверждена, две разные гипотезы дают `r × v` и
`r × v / M`, где `r` — allocated rank, `M` — maxPoints. Само слово max не
доказывает линейность. При `M=1, r=1` эти гипотезы совпадают, но identity,
conditions и версия всё равно требуют проверки. Ни одна гипотеза не выбрана по
DPS или по совпадению сторонних результатов.

Отдельная [проверка сохранённых клиентского и серверного payload](talent-rank-witness.md)
подтвердила число очков, но не нашла объявленной нормализации в исследованных
объектах. Там же исправлен дизайн будущей проверки: нужны абсолютные разницы
с baseline, поскольку отношение rank 3/1 одинаково у обеих линейных гипотез.

До этого binding допустим диагностический инвентарь с наблюдённым rank,
лексическим value, provenance, явным unknown rank scaling и запретом арифметики.
Ранг не домножается автоматически и не считается нулём при отсутствии данных.
