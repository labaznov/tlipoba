# Соединение исходного spell и боевого сценария

Математический блок `damage_lab.rawcombat.evaluate`, вход `tli-raw-cold-combat-v1`, соединяет уже поддержанный полный обычный Physical→Cold spell с явно заданными Tangle/topology и защитой цели. Это отдельная модель, не панельный anchor. Статические аффиксы и наблюдаемый Spell DPS сюда не подставляются автоматически.

Контракт верхнего уровня строгий: `format`, `spell` (полный вход `rawspell`), `topology`, `target`, `uptime`, `gates`, `missing`, `notes`. Неизвестные поля, неполные числовые данные и неправильные типы дают ошибку, даже если один из gates заблокирован.

`topology` содержит `maximum`, `extra`, `active`, `hits`, `retention` для существующего `engine.topology`. Это явная гипотеза числа прикреплённых Tangle и принятых попаданий, не вывод из числа снарядов. `target` содержит `cold_resistance`, `cold_penetration`, `armor`, `armor_effectiveness`, `armor_penetration`, `armor_penetration_order`, `increased_taken`, `more_taken`. Все значения обязательны; порядок пробивания выбирается явно из двух существующих вариантов `formulas.armor`. `more_taken` — полные явные rows существующего `additional`, без неявного объединения источников. `uptime` — доля 0..1.

Три gate — `inheritance`, `hit_topology`, `target_state` — имеют `status: confirmed|unknown|conflict` и `evidence: [refs]`. Confirmed требует непустой список evidence. Это утверждения сценария, не автоматическая проверка runtime или клиента. Unknown/conflict, непустой `missing` или blocked исходного spell дают blocked и null итоговый DPS; конкретные причины сохраняются. Источник и skill gates самого `rawspell` продолжают действовать.

Владение стадиями фиксировано: `rawspell.expected_hit` уже включает крит; `rawspell.pre_defence_dps` уже включает крит и скорость, включая per-caster cap/tick. Следующий слой умножает его только на topology, холодную защиту `max(0, 1-R+P)`, долю после явной брони, `1+increased_taken`, `additional(more_taken)` и uptime. Он не применяет повторно crit, cast, damage pools или Heat. Совокупность нескольких caster не получает второй глобальный cap 30 casts/s. Обычная полная конверсия уже означает cold channel, поэтому броня вызывается с `nonphysical=True` и всеми явными armor policy полями.

При полном входе результат остаётся conditional. Нужны detached scenario, результат исходного spell, трасса факторов и стадий, gaps и ownership с явным перечислением включённых/неприменённых слоёв. Blocked сценарий не получает числовой полный DPS. Nonfinite/overflow или необъяснимый underflow положительного произведения в ноль отклоняются. Ни benchmark, ни отношение к нему не являются множителем.

Независимый синтетический oracle: noncritical hit 100; шанс крита .25 и полный multiplier 3 дают mean hit 150; два cast/s дают pre-defence 300. `maximum=3, extra=1, active=3, hits=3, retention=.25` дают два прикреплённых Tangle и topology factor 3. При R=.4, P=.1, armor=0, effectiveness=1, armor penetration=0, order=after_effectiveness, increased_taken=.2, одном more_taken=.1 и uptime=.5 итог равен **415.8**. Синтетический случай с одним caster rate40 и тремя прикреплёнными Tangle должен сохранить per-caster cap30 и совокупные90 cast/s; при hit100 и остальных факторах1 итог9000.

Этот контракт пока не решает наследование Tangle, shotgun semantics, время баффов и состояние цели реального Carino. Автоматический resolver обязан оставлять соответствующие gates неизвестными, пока нет независимых подтверждений.

Воспроизводимый полностью вымышленный пример: `python -m examples.calculate_raw_combat`. Он читает `examples/raw_combat.json`, сохраняет входной сценарий и трассу стадий и даёт conditional 415.8. Замена любого combat gate на unknown блокирует полный DPS.

## API и результат

`evaluate(document) -> dict` — чистая функция без чтения файлов, доступа к игре, CLI или автоматического импорта. Все обязательные поля передаются явно; defaults и неизвестных полей нет. Ошибки формы и поддержанных чисел дают `ValueError` с фиксированным сообщением без текста входа и завершающей точки.

Формат результата — `tli-raw-cold-combat-report-v1`. Поля:

| Поле | Содержание |
| --- | --- |
| `status` | `conditional` либо `blocked` |
| `dps` | Итог заданного сценария; null при blocked |
| `spell` | Полный результат `rawspell.evaluate`, с собственным статусом, trace, gaps и копией исходного spell |
| `topology` | `attached`, `shotgun`, `factor` из `engine.topology`; null при blocked |
| `factors` | Множители `topology`, `cold_defence`, `armor`, `increased_taken`, `more_taken`, `uptime`; null при blocked |
| `armor_mitigation` | Результат явной policy `formulas.armor`; null при blocked; отрицательная редукция не обрезается |
| `scenario` | Отдельная глубокая копия полного входного сценария |
| `trace` | Шесть downstream-стадий; каждая содержит `stage`, `input`, `factor`, `output`; пуст при blocked |
| `gaps` | Неподтверждённые combat gates, gaps spell с префиксом `spell: ` и явно переданный combat `missing` |
| `ownership` | Фиксированные списки стадий `spell`, `combat`, `not_applied` |
| `assumptions` | Явные ограничения этой условной модели |

Трасса spell остаётся вложенной, её частичные данные не выдаются за полный боевой результат. При unknown combat gate исходный spell может сам иметь conditional числа; downstream поля всё равно null. Копии `scenario` и `spell.scenario` не разделяют изменяемые данные с входом или другим вызовом.

Шесть downstream-стадий идут строго в порядке topology → cold_defence → armor → increased_taken → more_taken → uptime. Первый `input` уже равен однокастерному `spell.pre_defence_dps`. Общая функция `formulas.product` отклоняет нечисловой/бесконечный результат и underflow положительного произведения в ноль; явный нулевой фактор допустим. Исходные damage/cast pools рассчитывает только `rawspell` и общее ядро: downstream не повторяет их pooling или crit/cast scaling.

## Поддержанные типы и пределы

Это границы математического адаптера, а не доказанные пределы характеристик игры. Булевы не принимаются как числа. Кроме явных целых topology/stacks, числовые поля — finite int/float; строки, NaN и Infinity отклоняются.

| Вход | Требование |
| --- | --- |
| `topology.maximum` | Строго int 0..4 |
| `topology.extra`, `active`, `hits` | Строго int 0..1000; active не превосходит maximum |
| `topology.retention` | Доля 0..1 |
| `target.cold_resistance` | −10..1 |
| `target.cold_penetration` | 0..10 |
| `target.armor` | Любое поддерживаемое finite число ≥0, без добавленного верхнего game cap |
| `target.armor_effectiveness`, `armor_penetration` | Доля 0..1; null и selector `panel` не принимаются |
| `target.increased_taken` | −1..100 |
| `uptime` | Доля 0..1 |

Каждая строка `target.more_taken` имеет **ровно** `id`, `affix`, `value`, `stacks`, `mode`. Поля scope/damage/cast не принимаются. `value` лежит в −1..1e6; stacks — строго int 0..1000; mode — `add` либо `multiply`. Список содержит не более 1000 строк. `formulas.additional` сохраняет pooling по полному affix, отклоняет повтор экземпляра id, несовместимые modes, отрицательный фактор и нечисловой результат. Никакого reference pool или вычитания baseline здесь нет.

Gate имеет ровно `status` и `evidence`. `missing`, `notes` и evidence — явно переданные списки до 1000 непустых строк длиной до 1024 без пробелов по краям. Такая же граница текста действует для modifier id/affix. Confirmed с пустым evidence недопустим; unknown/conflict не превращаются в confirmed по наличию корректных чисел. Target gate также не подтверждает фактический runtime-порядок пробивания брони.
