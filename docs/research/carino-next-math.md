# Следующий математический срез: исходное попадание

Проверено 2026-10-22 офлайн по текущим `engine.py`, `combat.py`, локальному контрольному расчёту и уже собранным источникам. Новых игровых наблюдений и внешних проверок не было. Числа ниже полностью синтетические.

**Приоритет — самостоятельная сборка одного попадания до защиты цели.** Контрольный расчёт идёт через `basis=panel`: он проверяет сценарную топологию поверх готового агрегата, но не собирает его из базы навыка и вещей. `basis=hit` тоже начинает с готового диапазона. Переключение между ними не закрывает происхождение исходного урона.

## Две границы с наибольшим влиянием

1. **Нет source-bound исходного hit.** `cold()` уже считает узкий обычный Physical→Cold путь, однако извлечённая ячейка `resolved` не подтверждает актуальность базы, effective level или применимость модификатора. Конфликт каталога и первичной версии, post-20 profile, условные/локальные строки и неизвестная конверсия должны блокировать автоматическую сборку, а не давать нулевой вклад или профиль по умолчанию. См. [план компилятора](carino-modifier-plan.md), [уровни навыка](help-skill-levels.md), [правила конверсии](help-defense-conversion.md).
2. **Не установлена связь исходного hit с агрегатом Spell DPS и событиями Tangle.** Даже правильный single-caster hit не подтверждает число принятых попаданий, наследование, shotgun group или боевой uptime. Эти слои должны оставаться отдельно от базового hit. Сохранённые контрольные изменения поддержек не разрешают автоматически добавлять critical-only more к панели. См. [панельные опыты](panel-formula-evidence.md), [границы Tangle](carino-damage-gates.md).

## Конкретный tracer

Следующий production tracer — `damage_lab/rawspell.py`, формат `tli-raw-cold-spell-v1`. Не менять текущий panel-калькулятор. Не принимать `spell_dps`, панельный `hit_min/hit_max`, benchmark либо измеренное отношение в качестве базы/множителя.

**Вход — явные примитивы, не агрегаты:**

- `context`: source/catalog SHA-256, `skill_id`, `effective_level` и четыре явных gate: version, level, base, conversion. У каждого `status: confirmed|unknown|conflict` и `evidence: [refs]`; confirmed требует непустой evidence. Это утверждения источника для выбранной модели, а не новая гарантия runtime identity
- `damage`: базовый **physical** диапазон `base`, добавленные диапазоны `physical`/`cold`, `effectiveness`, increased `all/physical/cold`, `more` rows с `id/affix/scope/value/stacks/mode`, явный `roll_model: midpoint`. Среднее min/max — указанная модель ожидания, не вывод из одного существования границ
- Родной cold не получает physical scope. Собранные из атрибутов или уровня бонусы появляются ровно один раз с собственной provenance
- `critical`: готовые chance и полный multiplier, явный `lucky` **крита** и critical-only `more`; Lucky Damage этим флагом не включается. Поддержка в layout сама по себе не подтверждает её активацию
- `casting`: base `interval`, `increased`, `more` rows и `frequency: null|30`; обязательные `missing` и `notes`

Первая версия поддерживает только **обычную полную Physical→Cold конверсию**. Partial/compulsory/другие damage channels не подтверждают conversion gate. Gate unknown/conflict либо непустой `missing` даёт `blocked`, `null` DPS и список причин. Числовые поля всё равно проверяются строго: malformed числа/контейнеры или отсутствие обязательного поля — ошибка, без нулевого fallback. Числа post-20 не выбирать из конфликтующих профилей: сначала требуется отдельный source-bound resolver, иначе блокировка.

**Выход реализованного API:** `noncritical.components.converted/native`, итоговые `noncritical.min/max/mean`, `critical_factor`, `expected_hit`, `rate.smooth/capped/effective/frequency`, `pre_defence_dps`, detached `scenario` с provenance, trace и gaps. При полных входах статус всё равно `conditional`. Это ожидание одного источника до защиты; Tangle/projectile multiplicity, сопротивление, броня и состояние цели сюда не входят. Контракт описан в [RAW_DAMAGE](../RAW_DAMAGE.md).

Скорость: `smooth = (1/base_interval) * (1+increased_cast) * additional(cast_rows)`; cap/tick выполняет существующий `tangle_rate`. Damage endpoints считает существующий `cold`, ожидание крита — `critical`. Отдельные origin/destination вклады можно получать тем же kernel с обнулённым другим каналом; не создавать вторую формулу pooling.

**Владение стадиями:** `expected_hit` уже содержит крит; `pre_defence_dps` уже содержит крит и скорость. Последний нельзя снова подать в `basis=hit`. Нельзя применять compiler pools ещё раз через пустой reference и полный target. Перед будущим соединением с combat нужен отдельный контракт стадий и отношения только к реально включённому исходному состоянию. Простейший первый выпуск возвращает самостоятельный диагностический результат без автоматического подключения к CLI расчёта персонажа.

## Синтетический независимый oracle

База physical `[100,200]`; добавленные physical `[10,30]`, cold `[5,15]`; effectiveness `2`; increased `all=.5`, physical `.25`, cold `.75`. Два additional damage экземпляра одного affix: `all=.2`, `physical=.3`, режим add. Converted factor `1.5`, native-cold factor `1.2`.

| Проверка | Ожидаемый результат |
| --- | --- |
| Два канала до крита | Converted `[450,975]`, native cold `[27,81]`, итог `[477,1056]` |
| Явное midpoint expectation, chance `.25`, полный crit `3`, critical-only more `.2`, Lucky false | Средний noncrit `766.5`; crit expectation `1.65`; средний hit `1264.725` |
| Base interval `.5`, increased cast `.5`, один cast-affix со строками `.2` и `.3`, add | Smooth rate `4.5`; continuous pre-defence DPS `5691.2625` |
| Тот же вход, явная гипотеза 30 Hz | Rate `30/7`; pre-defence DPS `5420.25` |
| Added effectiveness `0` | Остаётся base-derived диапазон `[375,750]`; flat-вклады нулевые, база не умножена на effectiveness |
| Изменение physical increased | Меняется только converted ветвь; native `[27,81]` сохраняется |
| Неизвестный уровень/версия, конфликт conversion gate, непустой missing | Blocked с причиной и `null`, без подстановки level 20/нулей/подобранного множителя |
| Повторный instance ID, bool как число, неупорядоченный диапазон, nonfinite/overflow, panel/benchmark field | Явная ошибка; вход и предыдущий результат не мутируют |

Эти тесты доказывают композицию выбранной модели, а не фактический DPS игры. Совпадение нового результата с панелью или манекеном остаётся независимой диагностикой и не меняет source gates.
