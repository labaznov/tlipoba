# Gates для привязки loot-аффиксов

Проверено **22 октября 2026** по семи сохранённым телам Help и исследовательской таблице `tli-loot-affix-bindings-v2`. Нового игрового захвата не было. Help взят из неофициального TLIDB-зеркала игровых текстов; соответствие текущему клиенту не подтверждено. Полная таблица и длинные исходные тексты сюда не перенесены.

## Формулы совместимы, привязки ещё условны

[Effect Priority](https://tlidb.com/en/Effect_Priority) ставит общие quantity/rarity, type quantity, дополнительные предметы, conversion и replication последовательно. Это совпадает с порядком [текущего loot-модуля](../../damage_lab/loot.py); библиотека не рассчитывает rarity и неизвестный состав наборов.

[General quantity](https://tlidb.com/en/Drop_quantity#DropquantityManualRule) складывает обычные bonuses и перемножает отдельные additional bonuses. Help не определяет соответствие одной каталожной строки одному фактору. Список исключённых источников приведён как примеры, а не исчерпывающая таблица. [Type quantity](https://tlidb.com/en/Drop_Quantity_Bonuses_for_Certain_Item_Types) образует общий additive pool соответствующего типа; слово additional в названии типа не переносит строку в general additional pool.

[Additional Drops](https://tlidb.com/en/Additional_Drops) обходят quantity и rarity, но участвуют в conversion/replication; показанная категория относится к способным дропать монстрам. Нельзя автоматически переносить это правило на открытие контейнера или выдачу награды. [Conversion](https://tlidb.com/en/Type_Conversion) использует source-type quantity до замены, без повторного destination quantity; competing chances выше единицы нормируются.

[Replication](https://tlidb.com/en/Replicate#ReplicateManualRule) различает два класса: внутри класса копии складываются, между классами множатся. Гарантированный пример даёт 8 итоговых копий. Вероятностные, chained, reopen и settlement строки не являются гарантированными целыми счётчиками `loot.replication()`. [Rarity](https://tlidb.com/en/Drop_rarity#DroprarityManualRule) относится к gear и Hero Memory; формулы вероятностей качества нет.

В v2 правильно разделены `mechanicStatus` и `bindingStatus`: документированная общая механика не подтверждает конкретную каталожную привязку, установленный слот или ранг. `binding_verified` отсутствуют. `binding_conditional` с `verification.open.status = unresolved` остаётся заблокированным для вычисления, даже если его текст и числа удалось извлечь.

## Что обязан проверять нормализатор

- **Identity и установка:** точная запись каталога, наблюдаемый native bridge, активный Drop-слот и режим; presence не равно activation
- **Ранг:** lookup по явной метке progression, а не позиции массива. У записей с метками 2–6 первый элемент не является рангом 1. Связь метки со StarRank остаётся отдельным неподтверждённым правилом
- **Rank conflict:** `null` рядом с `rank1DescriptionArgs` нельзя превращать ни в нулевой эффект, ни в выбранное без доказательства число; сохраняется `rank_conflict`/`rank_value_missing`
- **Применимость:** exact item-type mapping, источник награды, eligibility, число триггеров и зависимости; неизвестное нельзя заменять универсальным yes
- **Арифметика:** general additional требует явной группировки; случайная replication не округляется до гарантированных копий; диапазон extra drops не заменяется серединой без распределения
- **Trace:** source hashes/paths, status и все open gates сохраняются; observed, normalized, unresolved и excluded считаются отдельно

## Безопасный ближайший шаг

Первый адаптер должен быть чистым **диагностическим нормализатором без агрегации и вызова loot engine**: exact record/node, наблюдаемый rank и installation evidence → typed modifiers либо omissions с причинами. Для каждого ранга сохраняются и исходная метка, и фактический индекс/путь; конфликтующие источники остаются раздельными. Устаревшие подсказки v1 «один фактор на строку» и `levelProgression[rank−1]` не должны определять поведение.

Синтетические проверки: progression 2–6, rank-1 conflict, два general additional источника с неизвестной группировкой, несовпадение item type, неподтверждённый контейнерный trigger и неполный native bridge. Лишь после закрытия всех необходимых gates числовой адаптер может передавать подтверждённые значения в [существующий ограниченный API](../LOOT.md). Новые базовые drop chances, редкость, доход за карту и цены из этой таблицы не следуют.
