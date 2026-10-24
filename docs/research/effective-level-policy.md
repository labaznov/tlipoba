# Policy итогового уровня: поведение планировщиков и границы доказательств

Проверено 2026-10-22. Ниже — поведение закреплённых версий сторонних
планировщиков, а не установленное правило текущего клиента. Политика и уровень
реального персонажа не выбираются. Найденные ранее кандидаты и неполное покрытие
описаны отдельно: [effective-level bindings](effective-level-bindings.md).

Первичные источники здесь — исходники самих моделей: TLIBuilder
`1454bd4f04d509d5819e19605dba34273c0b222a` от 2026-10-19 и TLIPoB
`1da3826ab5539536a83378fd4aea20ffb3559f98` от 2026-04-15. Их согласие не является
вторым независимым измерением игры; происхождение общих правил не установлено.

## Что именно сопоставляют и складывают

| Решение | TLIBuilder | TLIPoB |
|---|---|---|
| Обычные scopes | Пустое требование либо пересечение с набором тегов | Переданные BaseSkill.tags; для active/support/passive — type |
| Active | У active_skill_level нет отдельного tag/type-теста в таблице | Только type Active |
| Main | Отдельный is_main_skill, связанный с выбором планировщика | Совпадение имени с навыком в active slot 1, не instance/alias |
| Granted tags | Объединяются с обработанными тегами при наличии add_mod_tags | В проверенной функции отдельного granted-tag join нет |
| Сложение | Целое значение каждого подходящего stat, затем сумма и нижняя граница 1 | Сумма подходящих модификаторов, затем округление общей суммы |

TLIBuilder: [таблица требований, 262–279](https://github.com/Tyrayla/TLIBuilder/blob/1454bd4f04d509d5819e19605dba34273c0b222a/backend/engine/offense.py#L262-L279),
[отбор и сумма, 1584–1602](https://github.com/Tyrayla/TLIBuilder/blob/1454bd4f04d509d5819e19605dba34273c0b222a/backend/engine/offense.py#L1584-L1602),
[нижняя граница, 1649–1655](https://github.com/Tyrayla/TLIBuilder/blob/1454bd4f04d509d5819e19605dba34273c0b222a/backend/engine/offense.py#L1649-L1655).
Granted-tag ветка видна в [1879–1886](https://github.com/Tyrayla/TLIBuilder/blob/1454bd4f04d509d5819e19605dba34273c0b222a/backend/engine/offense.py#L1879-L1886).
Автор прямо отмечает, что это его решение без измерения в игре:
[verification note, 12–14](https://github.com/Tyrayla/TLIBuilder/blob/1454bd4f04d509d5819e19605dba34273c0b222a/docs/verification/chromatic-shot.md#L12-L14).

TLIPoB: [Main, фильтры и сумма, 1527–1579](https://github.com/aclinia/torchlight-of-building/blob/1da3826ab5539536a83378fd4aea20ffb3559f98/src/tli/calcs/offense.ts#L1527-L1579).
Его [тест сложения, 4287–4298](https://github.com/aclinia/torchlight-of-building/blob/1da3826ab5539536a83378fd4aea20ffb3559f98/src/tli/calcs/offense.test.ts#L4287-L4298)
подтверждает контракт модели, а не результат игрового эксперимента.

## Defaults, оружие и точка отсчёта роста

| Решение | TLIBuilder | TLIPoB |
|---|---|---|
| Неуказанный базовый уровень | В slot payload подставляется 1 | Для проверенного skill path подставляется 20, также вместо 0; у поддержки nullish-default 20 |
| Рост выше таблицы | Отсчёт от skill.max_level; lookup ограничивается этим максимумом | Проверенная функция роста отсчитывает от 20; table clamp здесь не прослежен |

Источники defaults: [TLIBuilder UI selection/slot, 171–176](https://github.com/Tyrayla/TLIBuilder/blob/1454bd4f04d509d5819e19605dba34273c0b222a/src/renderer/src/utils/statsPayload.ts#L171-L176),
[TLIPoB skill, 1113–1115](https://github.com/aclinia/torchlight-of-building/blob/1da3826ab5539536a83378fd4aea20ffb3559f98/src/tli/calcs/offense.ts#L1113-L1115),
[его support path, 1247–1249](https://github.com/aclinia/torchlight-of-building/blob/1da3826ab5539536a83378fd4aea20ffb3559f98/src/tli/calcs/offense.ts#L1247-L1249).
Источники точки отсчёта: [TLIBuilder growth, 1554–1571](https://github.com/Tyrayla/TLIBuilder/blob/1454bd4f04d509d5819e19605dba34273c0b222a/backend/engine/offense.py#L1554-L1571)
и [lookup, 1884–1886](https://github.com/Tyrayla/TLIBuilder/blob/1454bd4f04d509d5819e19605dba34273c0b222a/backend/engine/offense.py#L1884-L1886),
[TLIPoB growth, 1582–1617](https://github.com/aclinia/torchlight-of-building/blob/1da3826ab5539536a83378fd4aea20ffb3559f98/src/tli/calcs/offense.ts#L1582-L1617).
Эти defaults и reference points не становятся наблюдаемыми полями импорта.
Различия версии Help и собственно оператор роста разобраны в
[help-skill-levels](help-skill-levels.md) и [SKILL_GROWTH](../SKILL_GROWTH.md).

Обе модели собирают global affixes с двух оружейных slots. TLIBuilder отдельно
различает weapon-specific base и global contributions:
[комментарий, 413–418](https://github.com/Tyrayla/TLIBuilder/blob/1454bd4f04d509d5819e19605dba34273c0b222a/src/renderer/src/utils/statsPayload.ts#L413-L418),
[обработка slots, 586–637](https://github.com/Tyrayla/TLIBuilder/blob/1454bd4f04d509d5819e19605dba34273c0b222a/src/renderer/src/utils/statsPayload.ts#L586-L637).
У TLIPoB оба оружия входят в [collector, 230–248](https://github.com/aclinia/torchlight-of-building/blob/1da3826ab5539536a83378fd4aea20ffb3559f98/src/tli/calcs/affix-collectors.ts#L230-L248);
[215–225](https://github.com/aclinia/torchlight-of-building/blob/1da3826ab5539536a83378fd4aea20ffb3559f98/src/tli/calcs/affix-collectors.ts#L215-L225)
удаляет повторы только при наличии specialName. Это не игровая проверка действия
двух конкретных оружейных строк. Готовые stat_key во frontend TLIBuilder — также
другой входной формат, а не доказанная привязка наших native affix IDs:
[312–379](https://github.com/Tyrayla/TLIBuilder/blob/1454bd4f04d509d5819e19605dba34273c0b222a/src/renderer/src/utils/statsPayload.ts#L312-L379).

## Чего Help не разрешает

Сохранённое тело [Skill Level на TLIDB](https://tlidb.com/en/Skill_Level) говорит,
что другие эффекты могут повысить уровень выше обычного предела. Оно не задаёт
matching scoped bonuses по tags/type, их суммирование, granted-tag eligibility,
Main/Active semantics или действие одинаковой строки на двух оружиях.
В исследовании 0524 просмотрены 125 сохранённых файлов по выражению `skill level`;
в выделенных прозаических совпадениях явного общего правила не найдено.
Это ограниченная область поиска; TLIDB — зеркало с beta-data
оговоркой, а не доказательство текущей версии клиента или отсутствия иных правил.
Representation и SHA тела уже зафиксированы в [help-skill-levels](help-skill-levels.md).

## Граница будущей policy

Можно сохранить перечисленные решения как явно выбранную вызывающей стороной
экспериментальную convention. Отдельно нужны: базовые/granted tags, определение
Active и Main, применимость оружейных slots, исключающие эффекты, способ сложения
и округления, нижняя граница, table cap и reference роста. Одного названия
«как в планировщике» недостаточно: их варианты различаются.

Такая convention не подтверждает игровой operator, текущую версию, активацию или
полноту кандидатов. Без их доказательств effective level остаётся null и rawspell
остаётся blocked; неизвестные прибавки не заменяются нулём. Подгонка к панели,
выбор уровня Carino и автоматическое применение роста к панельному DPS отсюда
не следуют. Нового арифметического kernel или bridge эта заметка не добавляет.

Проверка provenance: metadata helper 0524 имеют SHA256
`sources.json=05a04fbd515d8d6fbc4a4a29e42963f20da56c28b53673f9c1d29946498a5829`
и `anchors.json=e23decc39fc9f3b4b70fc6e1a15fdefec298d61c390969ce18a19ae9a0dd983f`.
Использованные raw blobs сверены с SHA256 и git blob SHA1 metadata; anchors —
физические строки исходных файлов, без схлопывания пустых строк web-renderer.
Чужой код не исполнялся, compiled datasets и данные игрока не переносились.
