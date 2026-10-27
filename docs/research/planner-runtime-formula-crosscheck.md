# Расчётные пути planners: критический event и средний урон

Проверено 2026-10-22. Новое свидетельство относится к устройству двух программ,
не к runtime SS14. Оно не разрешает неизвестные входы Carino. UI shared-roll,
обычный crit-damage operator и post-20 policy здесь повторно не выбираются.

## Новое различие: crit-only bonus нельзя независимо усреднить

В TLIBuilder pin `1454bd4f04d509d5819e19605dba34273c0b222a` stat
`dmg_additional_on_crit` преобразуется в generic additional factor с величиной
`m*p`, где `p` — уже вычисленная вероятность крита. Этот factor попадает в
generic damage; затем средний урон отдельно умножается на crit expectation.
В изолированном случае получается `H*(1+p*(C-1))*(1+m*p)`.
[Взвешивание, L1978–1984](https://github.com/Tyrayla/TLIBuilder/blob/1454bd4f04d509d5819e19605dba34273c0b222a/backend/engine/offense.py#L1978-L1984),
[generic factor, L2095–2098](https://github.com/Tyrayla/TLIBuilder/blob/1454bd4f04d509d5819e19605dba34273c0b222a/backend/engine/offense.py#L2095-L2098),
[crit stage, L2367–2370](https://github.com/Tyrayla/TLIBuilder/blob/1454bd4f04d509d5819e19605dba34273c0b222a/backend/engine/offense.py#L2367-L2370).
В metadata для этого stat не указан `pipeline_stage`, чей default — пустая строка;
обычный additional builder его не выбирает, поэтому выше рассматривается один
вручную добавленный factor.
[Default, L7–13](https://github.com/Tyrayla/TLIBuilder/blob/1454bd4f04d509d5819e19605dba34273c0b222a/backend/models/stat_meta.py#L7-L13),
[Metadata, L2239–2243](https://github.com/Tyrayla/TLIBuilder/blob/1454bd4f04d509d5819e19605dba34273c0b222a/backend/models/stat_meta.py#L2239-L2243),
[отбор, L119–128](https://github.com/Tyrayla/TLIBuilder/blob/1454bd4f04d509d5819e19605dba34273c0b222a/backend/engine/offense.py#L119-L128).

При **явной гипотезе**, что bonus действует только на то же самое критическое
попадание, математическое ожидание другое:
`H*((1-p)+p*C*(1+m))`. Его превышение над первым выражением равно
`H*m*p*(1-p)*(C-1)`. Вероятность и критическая величина здесь относятся к одному
event; независимое перемножение средних теряет эту связь. Это алгебраический
контрпример данной интерпретации, не измерение игры и не доказательство
фактического результата всей программы на конкретном support.

## Почему имя поддержки в комментарии недостаточно

TLIBuilder emitter действительно выдаёт `dmg_additional_on_crit` для подходящего
progression key, но эта ветка пропускает standard supports. Её eligible types —
Noble/Magnificent. Standard supports идут через другой parser/mapper. Поэтому
упоминание Critical Strike Damage Increase в комментарии offense не доказывает,
что обычная игровая поддержка 7420 проходит именно этот путь.
[Types, L124–125](https://github.com/Tyrayla/TLIBuilder/blob/1454bd4f04d509d5819e19605dba34273c0b222a/backend/engine/support_resolver.py#L124-L125),
[guard и emitter, L314–339](https://github.com/Tyrayla/TLIBuilder/blob/1454bd4f04d509d5819e19605dba34273c0b222a/backend/engine/support_resolver.py#L314-L339),
[standard route, L567–604](https://github.com/Tyrayla/TLIBuilder/blob/1454bd4f04d509d5819e19605dba34273c0b222a/backend/engine/support_resolver.py#L567-L604),
[mapper call, L627–648](https://github.com/Tyrayla/TLIBuilder/blob/1454bd4f04d509d5819e19605dba34273c0b222a/backend/engine/support_resolver.py#L627-L648).

TLIPoB pin `1da3826ab5539536a83378fd4aea20ffb3559f98` явно преобразует текст
additional damage on critical strike в `CritDmgPct` с `addn`. Этот тип проходит
через полный критический множитель, затем отдельное ожидание normal/critical
spell hits. Это другая convention; native 7420 mapping, установка и активация
из неё не следуют.
[Text mapping, L669–674](https://github.com/aclinia/torchlight-of-building/blob/1da3826ab5539536a83378fd4aea20ffb3559f98/src/tli/mod-parser/templates.ts#L669-L674),
[full C, L848–854](https://github.com/aclinia/torchlight-of-building/blob/1da3826ab5539536a83378fd4aea20ffb3559f98/src/tli/calcs/damage-calc.ts#L848-L854),
[spell expectation, L3396–3409](https://github.com/aclinia/torchlight-of-building/blob/1da3826ab5539536a83378fd4aea20ffb3559f98/src/tli/calcs/offense.ts#L3396-L3409).

## Независимый синтетический check и следующий шаг

Придуманы `H=80`, `p=3/12`, полный `C=2.4`, crit-only `m=.32`, rate `5/s`.
Прямое перечисление девяти normal и трёх critical outcomes даёт hit `123.36`,
или DPS `616.8`. Независимо усреднённый generic bonus даёт `116.64` и `583.2`.
Разница hit `6.72` совпадает с алгебраическим выражением выше. При `p=0`, `p=1`,
`C=1` либо `m=0` различие исчезает: такие случаи не различают модели.
Это не значения персонажа и не новая игровая drop/crit distribution.

Воспроизводящий собственный `Fraction` check:
`C:/Python313/python.exe local-data/research/planner-runtime-formula-crosscheck-20261022/oracle.py`.
Чужой код и datasets не исполнялись. Raw blobs, SHA-256 и Git blob SHA-1
сохранены рядом в ignored metadata; физические anchors проверены по байтам.

Конкретный автоматический model input не разблокирован. Speed и effective-level
пути не дали нового runtime witness сверх уже описанных
[cast gaps](cast-input-coverage.md) и [level policy](effective-level-policy.md).
Следующая полезная проверка адаптера — сохранять crit-only hit modifier отдельно
от full-C modifier и обычного global additional pool, с точными installation,
level, scope и activation gates. [Raw spell](../RAW_DAMAGE.md) уже разделяет эти
входы; нового арифметического kernel не требуется. Ни коэффициент, ни оператор,
ни arithmetic readiness по результату planners не повышаются.
