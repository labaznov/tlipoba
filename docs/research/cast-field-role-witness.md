# Один roll и два speed effects: граница доказательства

Проверено 2026-10-22. Найден явный shared-roll механизм в TLIBuilder, однако
он не устанавливает привязку игрового `DynArgs[0]` к двум specs нашего каталога.
В проверенных цепочках импорта нет нового game-format witness. Две composite
строки сохраняют неизвестный field-role binding и запрет арифметики.

Это проверка исходников программ, не подтверждение механики SS14. В 21
закреплённом source/doc файле двух planners проверены поисковые совпадения и
относящиеся к вопросу участки; программы не запускались,
compiled datasets и реальные билды не загружались. Отрицательный результат
ограничен этими entrypoints, не всеми существующими импортёрами.

## TLIBuilder: явное соглашение редактора

Pin: [`1454bd4f04d509d5819e19605dba34273c0b222a`](https://github.com/Tyrayla/TLIBuilder/commit/1454bd4f04d509d5819e19605dba34273c0b222a).

`sharedRollGroups` группирует числовые индексы одного affix по одинаковым
sign/min/max и нормализованному stat text. Нормализация удаляет Minion qualifier
и trailing conditions; без raw text остаётся range-only compatibility mode.
Fixed values не группируются. Это эвристика представления текста.
[Реализация, L51–113](https://github.com/Tyrayla/TLIBuilder/blob/1454bd4f04d509d5819e19605dba34273c0b222a/src/renderer/src/utils/affixText.ts#L51-L113).

Редактор действительно передаёт одну величину всем индексам группы в
`chosen_values`. Синтетические тесты различают player/minion mirror и разные
stats со случайно совпавшим range. Это прямое доказательство поведения planner,
а не только похожее описание.
[Запись, L771–781](https://github.com/Tyrayla/TLIBuilder/blob/1454bd4f04d509d5819e19605dba34273c0b222a/src/renderer/src/screens/GearScreen.tsx#L771-L781),
[вызов редактора, L1119–1149](https://github.com/Tyrayla/TLIBuilder/blob/1454bd4f04d509d5819e19605dba34273c0b222a/src/renderer/src/screens/GearScreen.tsx#L1119-L1149),
[тесты, L41–65](https://github.com/Tyrayla/TLIBuilder/blob/1454bd4f04d509d5819e19605dba34273c0b222a/src/renderer/src/__tests__/sharedRollGroups.test.ts#L41-L65).

Их verification note помечена автором Confirmed и ссылается на owner domain
knowledge от 2026-08-09 и проверку текстов SS13. Сам документ называет правило
text heuristic и edit-time only; существующие saves не переписываются при
загрузке. Опубликованного native parameter trace в этом свидетельстве нет.
Классификация для нас: owner-reported corroboration и planner convention.
[Основание и ограничения, L8–32](https://github.com/Tyrayla/TLIBuilder/blob/1454bd4f04d509d5819e19605dba34273c0b222a/docs/verification/affix-combined-line-shared-roll.md#L8-L32).

В соответствующем catalog importer `numeric_values` создаются последовательным
regex-разбором числовых токенов текста. Craft importer передаёт ему текст
модификатора. Это другое происхождение индексов, чем native DynArgs.
[Text parser, L19–52](https://github.com/Tyrayla/TLIBuilder/blob/1454bd4f04d509d5819e19605dba34273c0b222a/backend/tools/legendary_gear_importer.py#L19-L52),
[craft, L8–13](https://github.com/Tyrayla/TLIBuilder/blob/1454bd4f04d509d5819e19605dba34273c0b222a/backend/tools/craft_base_type_importer.py#L8-L13).

Есть и явный `dual_stat_groups.value_index`: engine payload выбирает по нему
элемент `numeric_values`, затем выдаёт его значение каждому `stat_key` группы.
Это полезный пример machine contract, но namespace индекса здесь — массив
planner, а не native DynArgs.
[Payload binding, L333–346](https://github.com/Tyrayla/TLIBuilder/blob/1454bd4f04d509d5819e19605dba34273c0b222a/src/renderer/src/utils/statsPayload.ts#L333-L346).

## TLIPoB: импорт уже сформированного текста

Pin: [`1da3826ab5539536a83378fd4aea20ffb3559f98`](https://github.com/aclinia/torchlight-of-building/commit/1da3826ab5539536a83378fd4aea20ffb3559f98).

Item importer принимает `affixes: string[]`, фильтрует строки и сохраняет их в
`customAffixes`; gear schema также хранит affixes как строки. Catalog generator
извлекает modifier text из HTML. Эти просмотренные цепочки не сопоставляют
native parameters и specs. Они не дают нового правила `values_count` или
native parameter index.
[Вход, L15–20](https://github.com/aclinia/torchlight-of-building/blob/1da3826ab5539536a83378fd4aea20ffb3559f98/src/components/equipment/ImportItemsModal.tsx#L15-L20),
[сохранение, L90–134](https://github.com/aclinia/torchlight-of-building/blob/1da3826ab5539536a83378fd4aea20ffb3559f98/src/components/equipment/ImportItemsModal.tsx#L90-L134),
[schema, L21–39](https://github.com/aclinia/torchlight-of-building/blob/1da3826ab5539536a83378fd4aea20ffb3559f98/src/lib/schemas/gear.schema.ts#L21-L39),
[catalog extraction, L327–338](https://github.com/aclinia/torchlight-of-building/blob/1da3826ab5539536a83378fd4aea20ffb3559f98/src/scripts/generate-gear-affix-data.ts#L327-L338).

## Что можно использовать

Синтетический пример: planner может записать `{0: 11, 1: 11}` для двух текстовых
ranges `(7–13)% Cast Speed` и `(7–13)% Minion Cast Speed`. Из этой записи не
следует, что native `[11]` имеет parameter map `[0, 0]`. Это отдельный контракт.
Совпадающий Simple render остаётся дополнительным наблюдением из
[предыдущего исследования](cast-input-coverage.md).

Безопасное применение найденного — прикрепить к diagnostic omission ссылку на
planner convention, сохранив неизвестное binding. Не дублировать DynArg и не
считать полный cast-speed pool подтверждённым.

Минимальный недостающий witness: первичная схема или код преобразования
native full affix ID → exact own-tier definition, где обе specs явно читают
один parameter index, с версией и byte provenance. Даже такое правило сначала
ограничивается подтверждённым определением; его нельзя распространять на все
совпадающие ranges. Scope player/minion, условия и activation проверяются
отдельно. Новое обращение к игре для этой заметки не выполнялось.

## Воспроизводимость

Ссылки используют физические строки raw blobs. Для всех 21 файла Git blob SHA
сверен с ранее сохранёнными pinned trees; metadata с SHA-256 и точным перечнем
путей сохранены в ignored `local-data/research/cast-field-role-witness-20261022/`.
Ключевые Git blob SHA-1:

| Файл | Blob SHA-1 |
| --- | --- |
| TLIBuilder `affixText.ts` | `674ada1d2648e9dd6ca610f8da04b8816b3e7270` |
| TLIBuilder `GearScreen.tsx` | `4af13e1b901cf69f387ebdb57f3ee15a133132ec` |
| TLIBuilder `sharedRollGroups.test.ts` | `d57a88f7707f9072f7f7a3bee23c08e29d01da38` |
| TLIBuilder `affix-combined-line-shared-roll.md` | `b8b50f687bd290de44aefaae134e29f28a9eebab` |
| TLIBuilder `legendary_gear_importer.py` | `36d167a8395606c8a46ab8d0b598cde258f6d0f0` |
| TLIPoB `ImportItemsModal.tsx` | `9d9e04251201017f710da7120393cf30ee100f1f` |
| TLIPoB `gear.schema.ts` | `746f46bd2ab68dd3983dc26fb40d0fe30076f045` |
| TLIPoB `generate-gear-affix-data.ts` | `09c43247a09e4b4f309afdfd744c16c8dc6f3d93` |

Реальные значения персонажа, native instance IDs и исходные игровые деревья
здесь отсутствуют. Математический или importer код не менялся.
