# Существующие калькуляторы Torchlight: Infinite

Проверено 2026-10-21. Область: публичные инструменты и исходники, полезные для SS14 Carino / Zealot of War / Cold Chromatic Shot / Tangle. Сторонние приложения не устанавливались, их код и тесты не запускались; прочитаны первичные страницы, документы и исходники. Реальные данные персонажа здесь не используются.

## Вывод

Калькуляторы уже существуют. Наиболее полезный для нашего среза — **TLI Builder**: есть Python-движок, Chromatic Shot, Condensed Cold, Tangle, формулы и отдельные записи игровых проверок. Однако его собственная запись считает современный Chromatic Shot **не проверенным в игре**, а готовый проверенный расчёт полного Zealot of War с Heat в просмотренных исходниках не обнаружен. Поэтому проект полезен как независимая модель и источник проверяемых гипотез, а не как эталон точного DPS. [Chromatic: статус и границы](https://github.com/Tyrayla/TLIBuilder/blob/1454bd4f04d509d5819e19605dba34273c0b222a/docs/verification/chromatic-shot.md#L4-L18), [реестр специальных модулей героев](https://github.com/Tyrayla/TLIBuilder/blob/1454bd4f04d509d5819e19605dba34273c0b222a/backend/engine/hero_traits/__init__.py#L9-L18).

Рекомендация: продолжать независимое узкое ядро tlipoba, сверяя механики с открытыми моделями и игровыми измерениями. Не строить полную базу заново до проверки уже опубликованных источников; не подменять проверку совпадением двух калькуляторов.

## Сравнение кандидатов

| Инструмент | Активность / SS14 | Что реально найдено | Где проверять формулы | Лицензия и практическая польза |
| --- | --- | --- | --- | --- |
| [TLI Builder](https://github.com/Tyrayla/TLIBuilder), [сайт](https://tlibuilder.com/) | Релиз 0.6.13 от 19 октября; 0.6.12 от 16 октября описывает импорт SS14 и исправление support scaling. [Changelog](https://github.com/Tyrayla/TLIBuilder/blob/1454bd4f04d509d5819e19605dba34273c0b222a/CHANGELOG.md#L5-L22) | Настоящий движок, не только редактор. Chromatic, Condensed, Tangle и источник каждого вклада. Современный Chromatic отмечен unverified. | [`offense.py`](https://github.com/Tyrayla/TLIBuilder/blob/1454bd4f04d509d5819e19605dba34273c0b222a/backend/engine/offense.py), [`skill_effects/chromatic_shot.py`](https://github.com/Tyrayla/TLIBuilder/blob/1454bd4f04d509d5819e19605dba34273c0b222a/backend/engine/skill_effects/chromatic_shot.py), [`test_tangle.py`](https://github.com/Tyrayla/TLIBuilder/blob/1454bd4f04d509d5819e19605dba34273c0b222a/backend/tests/test_tangle.py) | [Код MIT](https://github.com/Tyrayla/TLIBuilder/blob/1454bd4f04d509d5819e19605dba34273c0b222a/LICENSE); [собранные игровые данные отдельно](https://github.com/Tyrayla/TLIBuilder/blob/1454bd4f04d509d5819e19605dba34273c0b222a/DATA-LICENSE.md#L19-L29). Полезны архитектура, арифметические контракты и протоколы проверки; compiled dataset не переносим. |
| [Torchlight of Building / TLIPoB](https://github.com/aclinia/torchlight-of-building), [сайт](https://tlipob.com/) | Просмотренный main от 15 апреля 2026; подтверждения актуализации SS14 не найдено. [Commit](https://github.com/aclinia/torchlight-of-building/commit/1da3826ab5539536a83378fd4aea20ffb3559f98) | Настоящий TypeScript DPS-движок, но spell-hit whitelist содержит только тестовый spell, Chain Lightning и Ice Lances; Chromatic в него не входит. | [`damage-calc.ts`: crit/Lucky](https://github.com/aclinia/torchlight-of-building/blob/1da3826ab5539536a83378fd4aea20ffb3559f98/src/tli/calcs/damage-calc.ts#L775-L815), [`offense.ts`: whitelist](https://github.com/aclinia/torchlight-of-building/blob/1da3826ab5539536a83378fd4aea20ffb3559f98/src/tli/calcs/offense.ts#L3321-L3327), [spell DPS](https://github.com/aclinia/torchlight-of-building/blob/1da3826ab5539536a83378fd4aea20ffb3559f98/src/tli/calcs/offense.ts#L3396-L3410) | [MIT](https://github.com/aclinia/torchlight-of-building/blob/1da3826ab5539536a83378fd4aea20ffb3559f98/LICENSE.txt). Полезны типизированные модификаторы, фильтрация по тегам и независимая проверка критов; готового расчёта нашего навыка нет. |
| [TLI Lens](https://github.com/deafwave/tli-lens) — прежний адрес rehan-torchlight перенаправляет сюда | Main от 19 октября 2026; текущий pin описывает Hammer of Ash и проверку попаданий. [Commit](https://github.com/deafwave/tli-lens/commit/687f5a752a963963830f223bd435bdb510265451) | Текущий README описывает планировщик прогрессии поверх отдельного `dps-debug`, а не самодостаточную библиотеку урона. | [`CLAUDE.md`: отдельный pinned engine](https://github.com/deafwave/tli-lens/blob/687f5a752a963963830f223bd435bdb510265451/CLAUDE.md#L1-L17), [`pin.ts`](https://github.com/deafwave/tli-lens/blob/687f5a752a963963830f223bd435bdb510265451/packages/guide/src/pin.ts), [`engine/worker.ts`](https://github.com/deafwave/tli-lens/blob/687f5a752a963963830f223bd435bdb510265451/packages/guide/src/engine/worker.ts) | В просмотренном дереве нет LICENSE; публичный адрес необходимого dps-debug не установлен. Код не переносим. Полезны идеи привязки отчёта к версии модели и отказа от неподдерживаемых сравнений. |
| [TLI Compendium](https://tlicompendium.com/en/build-planner) | Автор в сентябре 2026 описывает расчёт базовых и условных статов, оставляя сложные traits/skills и damage последующим этапам. Октябрьское полное DPS-покрытие не проверено. [Сообщение автора](https://www.reddit.com/r/TorchlightInfinite/comments/1w61y2f/tlicompendium_update_basic_stats_page/) | Планировщик, сохранение/обмен билдами и развиваемая панель статов. Нельзя заключать, что нынешний сервис уже считает или не считает наш полный DPS, по одному старому сообщению. | Открытый исходник именно расчётного ядра не найден; [публичный репозиторий локализации](https://github.com/R3plic/TLI-Compendium-Localization) не является движком. | Лицензия расчётного ядра не установлена. Полезен формат обмена и ручная сверка состава билда; код/базу не заимствуем. |
| [TorchCodex](https://torchcodex.com/), [индекс JSON](https://torchcodex.com/json/) | Живая страница сообщает SS14 и дату обновления 20 октября 2026; индекс отдельно датирует skill 15 октября и talent 20 октября. Старые сообщения о перерыве сайта не характеризуют текущую версию. | База фактов и текстов, не найдено самостоятельного DPS-движка. Есть опубликованные skill, heroTrait, etherealPrism и другие JSON. | [Первичная страница](https://torchcodex.com/), [индекс опубликованных таблиц](https://torchcodex.com/json/). Текст Chromatic содержит текущую физическую основу и falloff 80%; это описание, не доказательство уравнения shotgun. | Лицензия на переиспользование компиляции не установлена. Полезен независимый от TLIDB источник сверки отдельных фактов; наличие JSON само по себе не разрешает зеркалировать всю базу. |
| [Tli-Utils](https://github.com/nextkaki/Tli-Utils) | Последний main от 5 мая 2025; подтверждение SS14 не найдено. [Commit](https://github.com/nextkaki/Tli-Utils/commit/026ee225e41e2664a3906488c4aea6e9173c8482) | Набор отдельных калькуляторов C#: cooldown, duration, Wind Rhythm, armor, Selena, damage; не полный импортируемый билд. [README](https://github.com/nextkaki/Tli-Utils/blob/026ee225e41e2664a3906488c4aea6e9173c8482/README.md) | [`Main.cs`: calcWindRhythm](https://github.com/nextkaki/Tli-Utils/blob/026ee225e41e2664a3906488c4aea6e9173c8482/Tli-Utils/Main.cs#L686), [damage](https://github.com/nextkaki/Tli-Utils/blob/026ee225e41e2664a3906488c4aea6e9173c8482/Tli-Utils/Main.cs#L1031), [`Common.cs`](https://github.com/nextkaki/Tli-Utils/blob/026ee225e41e2664a3906488c4aea6e9173c8482/Tli-Utils/Common.cs) | [MIT](https://github.com/nextkaki/Tli-Utils/blob/026ee225e41e2664a3906488c4aea6e9173c8482/LICENSE). Резервный источник старых гипотез; не основание SS14-коэффициентов. |

## Проверенные свойства моделей, полезные для tlipoba

Здесь «проверено» означает прочитано в исходнике/первичной записи, а не самостоятельно подтверждено в клиенте.

### 1. Источник, область действия и идентичность модификатора

TLI Builder сохраняет у числового вклада исходный текст, источник, skill scope, slot и pooling identity. Перед расчётом конкретного навыка применимые глобальные и локальные вклады материализуются отдельно. Это удобная схема для устранения двойного учёта и отчёта покрытия. [Текущая архитектура, L12–20, L55–69](https://github.com/Tyrayla/TLIBuilder/blob/1454bd4f04d509d5819e19605dba34273c0b222a/docs/architecture/engine-pipeline.md#L12-L69).

В hit-модели additional группируется по идентичности: одинаковые положительные вклады суммируются в одном факторе, различающиеся факторы перемножаются; у Damage Enhancement отдельная суммируемая группа. Это тоньше, чем просто перемножить каждый экземпляр любого `more`. Статус игровой проверки и исключения необходимо сохранять отдельно. [Pooling: аргументация и история](https://github.com/Tyrayla/TLIBuilder/blob/1454bd4f04d509d5819e19605dba34273c0b222a/docs/ADDITIONAL_DAMAGE_POOLING.md#L8-L35), [реализация L362–486](https://github.com/Tyrayla/TLIBuilder/blob/1454bd4f04d509d5819e19605dba34273c0b222a/backend/engine/offense.py#L362-L486).

### 2. Доставка попаданий отделена от размера одного попадания

У TLI Builder shotgun и число Tangle не увеличивают показываемый размер одиночного попадания: они влияют на частоту/количество доставленных попаданий и итоговый DPS. Tangle Damage Enhancement уже входит в damage pool, поэтому не умножается повторно вместе с числом Tangle. [Поля результата](https://github.com/Tyrayla/TLIBuilder/blob/1454bd4f04d509d5819e19605dba34273c0b222a/backend/engine/offense.py#L1186-L1208), [доставка L2517–2538](https://github.com/Tyrayla/TLIBuilder/blob/1454bd4f04d509d5819e19605dba34273c0b222a/backend/engine/offense.py#L2517-L2538).

### 3. Встроенная арифметика Lucky не требует нового изобретения

TLIPoB кодирует Lucky Crit как `2p − p²`, после определения и ограничения обычного шанса. Ожидаемый критический множитель затем применяется к среднему попаданию до частоты. Это независимая реализация для проверки наших синтетических случаев, а не основание автоматически считать, что Lucky уже отсутствует/присутствует в игровой панели. [Lucky](https://github.com/aclinia/torchlight-of-building/blob/1da3826ab5539536a83378fd4aea20ffb3559f98/src/tli/calcs/damage-calc.ts#L803-L815), [spell expectation](https://github.com/aclinia/torchlight-of-building/blob/1da3826ab5539536a83378fd4aea20ffb3559f98/src/tli/calcs/offense.ts#L3396-L3410).

### 4. Поддерживаемый навык и наличие записи о навыке — разные вещи

TLIPoB явно проверяет фабрику; Activation Medium не считается реализованным по одному наличию записи каталога. TLI Builder выдаёт unresolved вместо произвольного числового вклада для нераспознанного модификатора. Аналогичную границу нужно сохранить у импорта tlipoba. [is-implemented.ts](https://github.com/aclinia/torchlight-of-building/blob/1da3826ab5539536a83378fd4aea20ffb3559f98/src/tli/skills/is-implemented.ts#L9-L39), [разрешение вкладов](https://github.com/Tyrayla/TLIBuilder/blob/1454bd4f04d509d5819e19605dba34273c0b222a/docs/architecture/engine-pipeline.md#L47-L53).

## Экспериментальные сведения: не объявлять доказанными для нашего SS14

| Механика | Что утверждает первичный проект | Предел доказательства |
| --- | --- | --- |
| Tangle tick rounding | Автор TLI Builder записывает одинаковый игровой DPS при 6.04 и 7.44 casts/s и модель `ticks = ceil(cast_time × 30)`, `rate = 30/ticks`. [Запись](https://github.com/Tyrayla/TLIBuilder/blob/1454bd4f04d509d5819e19605dba34273c0b222a/docs/verification/tangle.md#L12-L26), [тесты](https://github.com/Tyrayla/TLIBuilder/blob/1454bd4f04d509d5819e19605dba34273c0b222a/backend/tests/test_tangle.py#L111-L140) | Дата проверки 19 июня; сырые независимые захваты и повторение в SS14 здесь не предъявлены. Это полезная измеренная гипотеза о порогах, не официальный контракт сервера. |
| Shotgun | Модель использует `1 + (n−1) × (1−falloff)`. [Код для projectile form](https://github.com/Tyrayla/TLIBuilder/blob/1454bd4f04d509d5819e19605dba34273c0b222a/backend/engine/offense.py#L2438), [запись эксперимента](https://github.com/Tyrayla/TLIBuilder/blob/1454bd4f04d509d5819e19605dba34273c0b222a/docs/verification/shotgun.md#L15-L29) | Запись относится к Chain Lightning Merge/Web: видели число попаданий, числовой DPS ещё pending. Она не подтверждает сама по себе Chromatic SS14. |
| Condensed Cold и Lightchaser | Есть отдельный модуль, конверсия Physical→Cold использует общий conversion pool; +20% special support применяется в support resolver отдельно от rolled line. [Модуль](https://github.com/Tyrayla/TLIBuilder/blob/1454bd4f04d509d5819e19605dba34273c0b222a/backend/engine/skill_effects/chromatic_shot.py#L129-L170), [conversion](https://github.com/Tyrayla/TLIBuilder/blob/1454bd4f04d509d5819e19605dba34273c0b222a/backend/engine/skill_effects/chromatic_shot.py#L210-L231) | Verification note оставляет SS13 rework/Condensed unverified. Наличие теста доказывает контракт программы, а не соответствие игре. [Оговорка](https://github.com/Tyrayla/TLIBuilder/blob/1454bd4f04d509d5819e19605dba34273c0b222a/docs/verification/chromatic-shot.md#L6-L14) |
| Уровни выше опубликованной таблицы | Chromatic note описывает стандартное правило ×1.10 за уровень выше максимума таблицы. [Запись](https://github.com/Tyrayla/TLIBuilder/blob/1454bd4f04d509d5819e19605dba34273c0b222a/docs/verification/chromatic-shot.md#L14) | В записи это модель/решение автора, не предъявленный замер нашего навыка SS14. Не заменяет повреждённый хвост таблицы TLIDB без отдельной проверки. |

## Конкретные ограничения найденного

- **Carino Heat / Burning Red / reload:** в просмотренном реестре специальных TLI Builder trait-модулей Zealot отсутствует; в просмотренных `compute.py`/`offense.py` не найдено собственного цикла Heat. Общий parser может разрешать отдельные статические строки, поэтому отсутствие модуля не доказывает отсутствие любых эффектов героя. Полное покрытие остаётся unresolved. [Реестр](https://github.com/Tyrayla/TLIBuilder/blob/1454bd4f04d509d5819e19605dba34273c0b222a/backend/engine/hero_traits/__init__.py#L1-L18).
- **Frostbite:** наличие программного холодного debuff pool не устанавливает, как его величина соотносится с показателями профиля, состоянием манекена и уже учтёнными бонусами; это проверяется источниками игры и отдельным опытом. [Пример отдельного поля Frostbite](https://github.com/Tyrayla/TLIBuilder/blob/1454bd4f04d509d5819e19605dba34273c0b222a/backend/engine/offense.py#L818-L822).
- **Тексты против актуального кода:** `docs/damage-pipeline.md` сам помечен устаревшим, а Tangle note всё ещё называет часть множителей NYI, хотя в текущем коде и тестах они уже присутствуют. Читаем pinned code вместе с verification status; не используем один документ как безусловную спецификацию. [Старая страница](https://github.com/Tyrayla/TLIBuilder/blob/1454bd4f04d509d5819e19605dba34273c0b222a/docs/damage-pipeline.md#L1-L4), [актуальные Tangle тесты](https://github.com/Tyrayla/TLIBuilder/blob/1454bd4f04d509d5819e19605dba34273c0b222a/backend/tests/test_tangle.py#L65-L108).
- **Lens:** отдельный pinned dps-debug и его данные не включены в сам просмотренный проект; публичность и условия распространения этого движка не установлены. Автоматически переносить его модель или результаты нельзя. [Контракт pin](https://github.com/deafwave/tli-lens/blob/687f5a752a963963830f223bd435bdb510265451/packages/guide/src/pin.ts#L7-L25).

## Уточнение импорта TLI Lens: 2026-10-23

В четырёх исходных файлах того же pinned tree наблюдается потребитель экспорта
`tli-lens-export/1`: `hero.level`, предметы и `loadout`. Тип `Loadout` остаётся
`Record<string, unknown>`, а интерфейс `Evaluator.run` допускает передачу полного
loadout внешнему evaluator; фактический вызов в этом срезе не изучен. Отсутствие
прямого обращения к raw damage, crit или `SkillItemLevel` в этих файлах не
доказывает отсутствие таких полей в полном экспорте или расчёте.
Список обращений потребителя не устанавливает схему недоступного производителя.
[Типы](https://github.com/deafwave/tli-lens/blob/687f5a752a963963830f223bd435bdb510265451/packages/guide/src/types.ts),
[чтение экспорта](https://github.com/deafwave/tli-lens/blob/687f5a752a963963830f223bd435bdb510265451/packages/guide/src/start.ts).

Код кандидатов навыков читает авторскую таблицу `config_skill_stone`, включая
`a100`. Его алгоритм оставляет пары с первой координатой не меньше запрошенного
уровня и берёт минимум второй координаты, иначе `Infinity`. Толкование координат
как уровня камня и требуемого уровня героя принадлежит авторской модели:
игровая строка каталога и связь с нашим `SkillItemLevel` здесь не проверены.
Это направление исследования, без нового binding или формулы DPS.
[Обработка навыков](https://github.com/deafwave/tli-lens/blob/687f5a752a963963830f223bd435bdb510265451/packages/guide/src/candidates/gems.ts).

Непустое значение `DPS_DEBUG_PIN` возвращается без проверки существования; fallback ищет
существующий локальный checkout и отказывает, если его не нашёл. Ошибка 404
при обращении к предполагаемому отдельному репозиторию не устанавливает её причину
или доступность источника для других пользователей. Производитель и вычислительное
ядро здесь не изучены; сторонний код не переносился и не запускался.
[Разрешение pin](https://github.com/deafwave/tli-lens/blob/687f5a752a963963830f223bd435bdb510265451/packages/guide/src/pin.ts).

## Предлагаемая библиотека расчётов

Это рекомендация для tlipoba, не утверждение о внутреннем устройстве игры.

1. **Чистая арифметика:** ranges, increased pools, factors grouped by identity, conversion ancestry, crit/Lucky, resistance/penetration; каждое правило с источником, сезоном и статусом.
2. **Доставка:** один hit → projectile group → один Tangle → число attached Tangle → временной интервал боя. Smooth rate и tick hypothesis должны задаваться явно и давать разные trace labels.
3. **Адаптер навыка:** Chromatic и два support roll добавляют только собственные проверенные операции; показанная панель и реконструкция из вещей остаются разными входными путями.
4. **Динамическое состояние:** Heat, reload, Frozen/Frostbite, curse и временные buffs; неизвестные uptime/ранги задаются пользователем или остаются условными.
5. **Независимая проверка:** синтетические арифметические тесты, затем контролируемые игровые A/B для одной механики. Совпадение с другим калькулятором — differential check, не игровое подтверждение.

При возможном дальнейшем переносе MIT-кода сохраняются upstream attribution и условия лицензии; в этом исследовании код не переносился. Отдельные игровые факты получаем из первичного описания или собственных разрешённых чтений, без копирования закрытого compiled dataset.
