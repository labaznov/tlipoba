# Формулы Carino / Cold Chromatic Shot / Tangle, SS14

Проверено 21 октября 2026 года. Заметка содержит публичные механики, без захватов и показателей игрока. Машиночитаемые правила находятся в `damage_lab/data/combat-ss14.json`; строки `formula` описывают знания и не предназначены для `eval`.

`verified` означает, что утверждение явно присутствует в указанном источнике. Это не означает независимую проверку в клиенте SS14. `inferred` — вывод с указанными предпосылками; `unresolved` — формулу нельзя автоматически использовать как установленный факт.

## Источники и сезон

Официальные изменения имеют приоритет над кэшем прошлых сезонов. TLIDB публикует извлечённые описания игры и Help, но предупреждает о тестовых данных. Поэтому совпадение TLIDB и старого каталога само по себе не подтверждает актуальность. В частности, агрегатная страница Character Build содержит старую модель Frostbite, противоречащую отдельным текущим Help-страницам.

Официальное дополнение от 14 октября, раздел «技能调整 · 五彩魔矢», фиксирует для Chromatic Shot уровень 20: **498–831**, shotgun coefficient **80%**, вместо 529–881 и 70%. Для этой проверки сервер вернул китайскую страницу даже с `lang=en`. [Официальный SS14, строки 100–103 снимка страницы](https://torchlight.xd.com/ss14pn/?lang=en)

## Дополнительные бонусы: граница группы — affix

Общая схема: `base × (1 + Σ increased) × Π additional_factors`. Повторы **одного affix** складываются внутри фактора; специально отмеченный `multiplies` использует произведение по стекам. Это не разрешает объединять разные affix только из-за общего `cold_damage` или другого stat key. [Damage Calculation, строки 33–37](https://tlidb.com/en/Damage_Calculation), [Stacks and Multiplication Rules, строки 33–38](https://tlidb.com/en/Stacks_and_Multiplication_Rules)

Для библиотеки нужен явный `affix_identity`, область действия и режим стеков. Нормализованный текст — возможный способ сопоставления, но его универсальная эквивалентность внутреннему ID не доказана. Имена навыка, условия и различия «supported skill» / «your damage» нельзя стирать.

TLIBuilder описывает сходный выбор, но называет подтверждение идентичности текста устным, а игровые spot checks — ожидающими проверки. Его текущий damage-taken путь ещё группирует по stat key. Это полезный первичный отчёт авторов о своей реализации, а не экспериментальное доказательство всех правил SS14. Данные его каталога не переносились. [TLIBuilder: Additional-Damage Pooling, разделы 1, 5b, 7](https://github.com/Tyrayla/TLIBuilder/blob/main/docs/ADDITIONAL_DAMAGE_POOLING.md)

## Tangle и частота

Отдельный Help описывает базовые **2 Tangle**, обычный предел **4**, длительность **8 s**, радиус **8 m** и замену самого старого при достижении лимита. Интервал триггера равен интервалу соответствующего заклинания. Прикреплённый Tangle активен; без подходящей цели он неактивен. [Tangle, нижний раздел Help, строки 270–283](https://tlidb.com/en/Tangle)

Отсюда для одной цели условно `attached = min(created, per_target_limit)`. Глобальный максимум и дополнительные прикрепления — разные ограничения; складывать их как число действующих источников урона нельзя. Базовое прикрепление **1** и полное наследование панельного DPS, крита, Lucky и Heat в найденном Help явно не определены. Эффект `Tangle Damage Enhancement` встречается в affix, но отдельное описание его формулы не найдено. Даже правдоподобное `1 + Σ enhancement` пока является гипотезой.

Гладкая скорость заклинания следует обычной схеме increased/more; агрегатный Help указывает предел **30 casts/s**. Это предел скорости навыка, а не доказанный лимит суммы попаданий всех Tangle и снарядов. [Skill Speed, строки 33–40](https://tlidb.com/en/Skill_Speed), [Character Build → Cast Speed, строки 397–403](https://tlidb.com/en/Character_Build)

Авторы TLIBuilder сообщают два наблюдения: 6.04 и 7.44 casts/s приводят к 6.0; их модель `30 / ceil(30 / smooth_rate)` округляет интервалы вверх до тиков 30 Hz. Дата проверки — 19 июня 2026 года; сырые события/видео в заметке отсутствуют. Это кандидат на отдельный режим расчёта, требующий повторения в SS14. Проверки множителей Tangle в том же документе помечены незавершёнными. [TLIBuilder: Tangle, строки 8–26](https://github.com/Tyrayla/TLIBuilder/blob/main/docs/verification/tangle.md)

## Снаряды и shotgun

Первое попадание наносит полный урон; последующие уменьшаются. [Shotgun Effect, строки 34–38](https://tlidb.com/en/Shotgun_Effect)

Описание Chromatic Shot разделяет **base 1** и **intrinsic +2**; уровень 20 даёт added effectiveness **123%**. Но UI-поле `Projectile Quantity Bonus` не определено этими строками: оно может уже включать intrinsic и support quantity. Нельзя автоматически прибавить ещё 2 или 3. [Chromatic Shot, Details и уровень 20](https://tlidb.com/en/Chromatic_Shot)

Связь названия `falloff coefficient 80%` с retained damage 20% в найденных первичных игровых текстах не записана формулой. TLIBuilder использует `1 + (hits−1) × (1−falloff)` для Chain Lightning; автор прямо отмечает отсутствие числовой проверки DPS. Это гипотеза для Chromatic, не факт о его итоговом DPS. Следует хранить `falloff = 0.8` отдельно от явно выбранного `subsequent_retention`. [TLIBuilder: Shotgun, строки 5–27](https://github.com/Tyrayla/TLIBuilder/blob/main/docs/verification/shotgun.md)

## Frostbite, Frail, проклятие

Текущий отдельный Help сообщает default rating **10**, обычный максимум **120**, Frostbite только после успешного наложения, Freeze при **более 100**. Порог 100 в краткой вводной и >100 в подробностях различается; для границы нужен клиентский тест. Глоссарий дополнительно говорит о фиксированном rating при наложении и **+1% more Cold Damage taken на 1 rating**. Это не модель накопления по 10 за каждый hit. [Frostbite and Freeze, строки 35–60](https://tlidb.com/en/Frostbite_and_Freeze), [Frostbite, строки 34–36 и 1016–1020](https://tlidb.com/en/Frostbite)

Точные связи `Frostbite Effect`, rating, отображаемого `Max Frostbite Rating` и итогового received damage не найдены. Формулу `1 + rating/100 × (1+effect)` можно проверять экспериментом, но нельзя объявить установленной. Старый Character Build с вычислением rating из доли жизни цели здесь конфликтует с новым Help и исключён как основание текущей модели.

Frail даёт **15% more Spell Damage taken**. Biting Cold уровня 20 даёт **39% more Cold Damage taken**, длительность **5 s**, cooldown **8 s**. Curse Effect изменяет величины дебаффа обычным произведением increased/more. [Frail, строки 34–36](https://tlidb.com/en/Frail), [Biting Cold, строки 38–60](https://tlidb.com/en/Biting_Cold), [Curse → Curse Effect, строки 90–92](https://tlidb.com/en/Curse)

Для холодного spell hit все три области потенциально подходят, но итоговое произведение предполагает, что это разные affix pools. До проверки статусов и их identity считать комбинацию установленным числом нельзя. Curse uptime определяется реальным способом применения и длительностью, а не наличием камня в экспорте.

Ice Bond уровня 20 даёт другим навыкам **24% more Cold Damage против Frostbitten**, если активен Euphoria; sentry живёт **8 s**. Это исходящий условный бонус, не тот же источник, что Cold Damage taken проклятия. [Ice Bond, строки 58–70](https://tlidb.com/en/Ice_Bond)

## Сопротивление и броня цели

Сопротивление пробивается в расчёте: `effective_resistance − penetration`; само значение resistance не меняется. [Resistance Penetration, строки 35–39](https://tlidb.com/en/Resistance_Penetration)

Для монстра `armor_reduction = min(0.8, armor/(0.9×armor + 30000))`; для non-Physical применяется **60%** этой редукции. Поэтому Cold hit нельзя автоматически исключать из брони. У игрока другая зависимость знаменателя от уровня врага; её нельзя использовать для манекена. [Armor, строки 40–55](https://tlidb.com/en/Armor)

Armor DMG Mitigation Penetration вычитается из редукции при Hit Damage и может сделать её отрицательной. Порядок относительно non-Physical коэффициента 0.6 в тексте не указан. До проверки нельзя молча выбрать между `0.6×reduction−penetration` и `0.6×(reduction−penetration)`. [Armor DMG Mitigation Penetration, строки 35–38](https://tlidb.com/en/Armor_DMG_Mitigation_Penetration)

## Heat Up и выбранные свойства Carino

Zealot of War: magazine начинается с **6**, глобальные +projectiles/+splits дают по **3** ёмкости; intrinsic и linked supports исключены, base reload **0.8 s**. Incinerated Glory получает по **1 Heat на потраченный ammo**; damage/stack по уровням 1–5: **1.6/2/2.3/2.6/3%**. После reload Heat сбрасывается. Eternal Flames добавляет **0.4% more Attack/Cast Speed на Heat**. [Zealot of War, соответствующие свойства, строки 52–141 и 245–272](https://tlidb.com/en/Zealot_of_War)

При **Extreme Heat** максимальный Heat включает Burning Red, затем reload; убийства elite продлевают режим на **3/4/5/5/5 s** по уровню свойства. Это не Ceasefire: нельзя начинать бой с полного Heat на основании другого выбора. Ни максимальный Heat = magazine, ни расход ammo каждым Tangle cast явно не доказаны найденным текстом. Уровни свойств должны быть входными данными. [Extreme Heat, строки 180–215](https://tlidb.com/en/Zealot_of_War)

Burning Red длится **10 s**, запрещает trigger Empower/Curse/Warcry, после него reload. Текущий английский глоссарий указывает Heat Up effect bonus **100%**, а старая локализованная Hyperlink-страница — **160%**. Число 160 нельзя брать из старой страницы. Интерпретация 100% как `effect ×2` правдоподобна, но требует клиентского подтверждения. Полный цикл требует времени набора Heat, времени Burning Red, reload и реальной работы Tangle в этих фазах. [Burning Red, строки 34–38](https://tlidb.com/en/Burning_Red), [конфликтующий старый Hyperlink](https://tlidb.com/vi/Hyperlink)

## Короткие проверки, которые закроют неизвестное

1. Одно и два прикрепления: чистое заклинание, одинаковая цель и скорость; проверить частоту событий и удвоение без изменения панели
2. Несколько значений Cast Speed вокруг 6 и 7.5: записать достаточно попаданий для проверки 30 Hz и отличия панельной скорости от частоты Tangle
3. Два числа снарядов при неизменных hit damage/crit/скорости: установить UI count и retained damage shotgun
4. Раздельно включать Frostbite, Frail и Biting Cold; фиксировать дебаффы и броню/сопротивление манекена, затем проверять сочетания
5. Начать с пустой цели и полного magazine: записать ammo, Heat, Burning Red и события reload одновременно с Tangle hits

Эти проверки нужны для выбора между конкретными формулами; измеренный DPS не используется как коэффициент подгонки.
