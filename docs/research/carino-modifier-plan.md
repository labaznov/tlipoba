# План сборки модификаторов Carino с нуля

Проверено **22 октября 2026** по сохранённому пакету и локальному каталогу, без нового захвата, сети, игрового UI или процесса. Публичная заметка содержит только семейства и границы реализации; построчный инвентарь, исходные ID, роллы и hashes остаются в ignored-аудите.

## Что доказал просмотр файлов

Сохранённый пакет содержит структурированные строки предметов, навыков, распределённых талантов, воспоминаний, декодированных эффектов плит и частичные данные других систем. В native-аффиксах доступны `Id`, `Node`, `DynArgs`, `TLv`, `Condition`, `Filter`, `Behavior`. Наличие последних трёх полей не раскрывает их семантику и не подтверждает активацию эффекта.

Для части аффиксов найдено единственное совпадение **полного modifier ID и каталожного предмета** в локальных таблицах. Это делает узкий адаптер возможным без нового захвата. Другие записи требуют отдельного mapping: существующий transfer допускает fallback по node/части ID; такой fallback нельзя автоматически повышать до точного соответствия для математики. Разные tiers одного affix должны получать подтверждённый общий pool key, а не случайно разделяться по полному ID тира; обрезание цифр также не доказывает общий pool.

Пересборка пакета не обновляет время захвата. У сохранённых source и guide совпадает историческое время, но `sourcePatch` остаётся unknown, а флаги выбора — false. Отдельные hashes подтверждают байты файлов, не правильность выбранного персонажа/панельного навыка или семантическую связь guide с source. Успешный composition audit не подтверждает completeness либо effective effects.

Важный конфликт: каталог даёт `resolved` для числовых параметров основного spell на экспортированном уровне, но его базовый диапазон расходится с уже проверенным официальным обновлением SS14. `resolved` означает извлечение ячейки, не проверку актуальности версии, эффективного уровня или активации поддержки. Старый вывод helper о Lucky из сопоставления панели также не является правилом для компилятора; [контрольные наблюдения](panel-formula-evidence.md) и [пробелы Tangle](carino-damage-gates.md) сохраняют свои ограничения.

## Математика и автоматические входы

«В панели» ниже означает, что статический бонус **может уже входить в агрегат** и его нельзя повторно применять. Это не утверждение, что панель отражает каждое условие и каждую ветвь урона.

| Семейство | Уже поддержанная математика | Доступный источник / пробел | Панель и расчёт с нуля |
| --- | --- | --- | --- |
| База spell, added effectiveness, теги | `cold()` принимает явные base и effectiveness; min/max можно рассчитывать отдельно | Таблицы уровня и catalog tags доступны; нужен приоритет актуальных фактов, смысл полей и подтверждённый effective level | Панельную базу не умножать повторно; с нуля брать проверенную строку таблицы |
| Flat physical/cold к spells | Effectiveness применяется к добавленному урону | Есть native rolls и часть точных catalog bindings; нужно отличать spell от attack, player от minion и local weapon stat | Flat уже участвует в panel hit; с нуля собрать отдельно origin и native destination |
| Increased damage | Для полного Physical→Cold пути `1 + Iall + Iphysical + Icold`; native cold не получает physical scope | Строки предметов и распределённые узлы доступны; нет общего проверенного family/unit/scope registry | Panel increased не накладывать поверх hit; с нуля суммировать только подходящие scope |
| Additional damage | `formulas.additional()` складывает один affix в режиме add, разные группы перемножает; multiply только при явной семантике | Нужны canonical affix identity, line index, вариант и границы pool; описание и похожее имя не являются identity | Для panel delta — полный target/reference; с нуля применить pool один раз |
| Critical rating, multiplier, crit-only more, Lucky | `critical()` вычисляет ожидание из готовых chance/multiplier/more и явного Lucky; формула rating→chance записана в [Help о крите](help-damage-critical.md) | Есть строки rating/damage и установленной поддержки; base rating, применимость Tangle-only rating и inclusion в панели не сведены | С нуля отдельно собрать rating и crit damage; crit-only more не прибавлять к multiplier; панель не корректировать выбранной по совпадению гипотезой |
| Increased/more cast speed | Общая формула скорости, предел 30; tick-режим остаётся явной гипотезой | Есть base cast metadata, rolls и талантные ранги; неполны aura/Heat/grant условия и полный pool | `combat.apply()` использует отношение к reference и реальный cap; с нуля нужен полный pool |
| Main attributes и main-stat multiplier | Help связывает подходящие main stats с more damage; это пока не автоматическая ветка engine | Видны отдельные прибавки и теги; полной подтверждённой базы и итоговых Strength/Dexterity/Intelligence нет | Частичные суммы не считать итоговыми и не заменять отсутствующую базу нулём |
| Skill levels, supports, auras, grants | `skillvalues` сохраняет таблицу именно экспортированного уровня; не компилирует effect | Есть gem level и часть level-bonus строк; effective level, enabled support и aura effect требуют отдельных правил; special supports имеют native line rolls | Поддержки уже могут входить в panel. Preview tier и level-one description не заменяют roll/level table |
| Heat и герой | `carino.heat()` компилирует фиксированные heat/rank/effect в damage/cast rows | Выбранные traits и кандидаты rank сохранены; rank остаётся null, нет автоматического heat/effect/rotation binding | Не выводить rank из threshold, Heat из магазина или эффективность из имени состояния; Tangle inheritance не подтверждено |
| Tangle, projectile, shotgun | Сценарные population/attachment/hit/retention и частота | Capacity и некоторые projectile stats доступны; attachment history, hit group, retention и interval scope неизвестны | Число бонусных снарядов не равно числу принятых попаданий; не умножать panel DPS на все доступные счётчики |
| Enemy resistance, armor, damage taken | Resistance penetration, armor и два явных условных порядка проникновения уже реализованы | Character penetration доступен; защита цели, stacks, curse/Frail/Frostbite application и uptime не следуют из состава билда | Ни target state, ни порядок брони не восстанавливать по benchmark; не смешивать received и dealt damage |
| Призма, плиты, pactspirits, procs, ограничения урона | Только отдельные низкоуровневые kernels; общего grant/replacement evaluator нет | Есть decoded records и частичные mappings; неизвестны отдельные эффекты, board placement, replacement/activation и caps | Сначала разрешить grants и замены, затем считать; on-kill explosions и minion damage не добавлять как постоянный more основного hit |

Поддержка полного Physical→Cold пути в `cold()` — ограничение интерфейса, а не доказательство conversion в импортируемом билде. Compulsory conversion, порядок разных conversion и damage restriction должны получить свои source-bound правила. Вне основной ветви остаются защитные и utility эффекты; их нужно явно учитывать в coverage, а не выдавать за offensive modifiers.

## Два ближайших адаптера без нового захвата

**1. Native effect ledger → узкий compiler статических строк.** Начать с exact-ID аффиксов предметов для flat spell damage и increased global/physical/cold/spell damage; сохранять owner, skill/tag scope, unit, origin file/hash/path, native ID, variant, roll и canonical definition/line/pool. Неизвестные, неоднозначные, условные и weapon-local строки выдавать отдельными omissions. Затем отдельным маленьким расширением подключить распределённые обычные talent nodes по exact catalog GUID и наблюдаемому rank. Preview text не должен участвовать в извлечении числа или определении оператора.

Критерии: один синтетический item с несколькими строками, разные tiers одного affix, атака рядом со spell-строкой, normal/corroded вариант, отсутствующий exact ID, неоднозначная связь и неизвестная unit. Число observed/compiled/excluded должно сходиться; одинаковый affix не должен перемножаться случайно. На saved package результат — автоматический **частичный** ledger/pool, без обещания полного hit либо рекомендации купить предмет.

**2. Typed skill context с проверкой версии и уровня.** Поверх `skillvalues.parameters()` связать точный skill/catalog identity с полями base range, added effectiveness, base cast speed, tags и main-stat tags. Хранить отдельно exported gem level, effective level и version/profile status. При конфликте актуальной первичной таблицы и кэша возвращать конфликт с обоими источниками; при неизвестном effective level не подставлять gem level. Для special supports отдельный adapter использует точные native line ID/roll/tier и сохраняет неизвестную activation. Это можно сделать офлайн на текущих файлах, не изменяя действующий DPS.

Критерии: resolved-but-stale table, отсутствующий effective level, рациональная ячейка, flat base tail с отдельным post-20 multiplier и неизвестная special-support строка. Лишь после выполнения этих gates можно соединять typed skill context и скомпилированные pools через существующий `cold()`; полные main stats, crit/cast pools, grants, conversion и combat state остаются отдельными prerequisites.

## Связь с улучшениями

[Модуль upgrades](../UPGRADES.md) сравнивает уже нормализованные полные target pools при общих reference/условиях. Он не декодирует предметы и не меняет flat damage, increased pools, skill level, topology или панель кандидата. Следовательно, flat/increased compiler сначала создаёт входы для будущего расчёта с нуля; подключать его строки как arbitrary additional multiplier к panel DPS нельзя. Пока нормализатор не покрывает все изменяемые эффекты, реальный кандидат должен оставаться incomplete и не попадать в рейтинг.

## Проверенные локальные границы

- [engine](../../damage_lab/engine.py): `cold`, `critical`, `topology`, `calculate`
- [combat](../../damage_lab/combat.py): общие reference/target ratios, armor hypothesis и фиксированный hero context
- [carino](../../damage_lab/carino.py), [formulas](../../damage_lab/formulas.py), [skillvalues](../../damage_lab/skillvalues.py)
- [Проверенные и неизвестные формулы](carino-combat-formulas.md), [import-state provenance](import-state-provenance.md), [ограничения Help skill levels](help-skill-levels.md)

Старый helper-дизайн семейства/компилятора использован только как карта вопросов: его поддержка не означает реализованную поддержку в этом репозитории. Никакой benchmark не использован для family mapping, выбора версии, уровня, pool или коэффициента.
