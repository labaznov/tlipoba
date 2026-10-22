# Main attribute: базовое правило и Lightchaser ratio

Проверено 2026-10-22 по сохранённым телам Help, свежим публичным страницам TLIDB и
исходникам моделей. Нового доступа к игре, процессу, UI или журналам не было;
значения атрибутов персонажа не использовались. TLIDB — неофициальное зеркало;
наличие SS14 на странице не подтверждает версию клиента.

## Факты источников

Статьи Strength, Dexterity и Intelligence описывают по 0.5% дополнительного урона
за point **подходящего основного атрибута навыка**. Для нескольких main stats
складываются их вклады перед итоговым бонусом. Упомянуты собственный урон навыка,
непосредственно нанесённые им ailments и урон призванных им minions. Это не правило
перемножения отдельных STR/DEX/INT factors.
[Strength](https://tlidb.com/en/Strength), [Dexterity](https://tlidb.com/en/Dexterity),
[Intelligence](https://tlidb.com/en/Intelligence), собственные одноимённые Help-разделы.

У публичного Chromatic Shot поле **Main Stat** перечисляет Strength, Dexterity и
Intelligence. Это отдельное поле навыка: вывод `Spell → Intelligence`, damage tags
или числовые native IDs не заменяют его. Изменение Cold Tag само по себе не
доказывает изменение списка основных атрибутов.
[Chromatic Shot, Main Stat](https://tlidb.com/en/Chromatic_Shot).

Страница Lightchaser отдельно перечисляет обычный +20% additional damage и +25%
damage **ratio** от основного атрибута. Она не содержит уравнения для этого ratio,
порядка его объединения с другими ratio modifiers или числового примера.
Повтор строк в Simple-блоке не доказывает два независимых эффекта.
[Lightchaser, Simple](https://tlidb.com/en/Chromatic_Shot_Lightchaser_Magnificent).

## Воспроизводимость локальных источников

`local-data/research/help-basic-20261021/help-stats.txt` — сохранённое текстовое
представление web-tool, SHA256
`e9bb694f0e203d912d2095a0f0645714b782884f7c138e154e7163123e241dcf`.
Это не HTML и не оригинальные HTTP/client bytes. Координаты ниже относятся к этому
представлению; body SHA вычислен по UTF-8 выделенного среза.

| Тело | Координаты | Body SHA256 |
|---|---|---|
| Strength | L332–336, decoded span `[4099,4534)` | `e95b4cf27621598b89750ce62f7e5537e0eeec989c174f9ca350639e1b83bc17` |
| Dexterity | L297–300, decoded span `[13794,14225)` | `5cdfe69b6097ed71d607ccdccd05b5c5a152eb8cce6f8e80a627977e951b100f` |

Intelligence body повторно прочитан на публичной странице: L695–698 ответа
web-tool. Короткие разрешённые цитаты Intelligence и Lightchaser сохранены в
ignored `local-data/research/main-attribute-damage-20261022-032822/` с URLs,
координатами и representation в `sources.json`:

- `intelligence-excerpt.txt`, SHA256 `8e9f52cbf1c53d184cb068f4245afdd54dc2b3a32bc177305fab2e4e3f34641d`;
- `lightchaser-excerpts.txt`, SHA256 `eb674ee8cf7e97ad16334c9761dc7f5a2129801d95063d94bf6f4f212e743fe0`.

Это хеши выбранных excerpt-файлов, не полного ответа сервера. В Help-тексте
процентный суффикс напечатан как `%%`; в модели ниже 0.5% записано долей `0.005`.

## Математическое следствие без ratio modifiers

Пусть `E` — подтверждённый набор main stats навыка, а `A[a]` — полные итоговые
значения соответствующих атрибутов. Тогда для неизменённого правила:

```text
bonus B = 0.005 × Σ(a∈E) A[a]
factor F = 1 + B
```

Это вывод из процентной нормы и суммирования, а не отдельное измерение клиента.
Известные нулевые атрибуты дают нулевой вклад; неизвестные значения не становятся
нулём. Статические flat/increased attribute строки не являются итоговым `A[a]`.
Совместимость этого factor с конкретной стадией, исключениями и версией должна
быть задана явно; к уже собранной панели его повторно не добавляют.

## Ratio: проверенная реализация модели, неподтверждённый оператор игры

TLIBuilder в закреплённом `1454bd4f04d509d5819e19605dba34273c0b222a` от 2026-10-19
моделирует Lightchaser как относительное увеличение коэффициента за point:
`0.005 → 0.00625`. Он использует `skill.main_stat`, суммирует итоговые атрибуты,
увеличивает **bonus**, затем прибавляет единицу. Это первичный источник о программе,
не доказательство игрового оператора.
[Emission, L199–203](https://github.com/Tyrayla/TLIBuilder/blob/1454bd4f04d509d5819e19605dba34273c0b222a/backend/engine/skill_effects/chromatic_shot.py#L199-L203),
[calculation, L2028–2036](https://github.com/Tyrayla/TLIBuilder/blob/1454bd4f04d509d5819e19605dba34273c0b222a/backend/engine/offense.py#L2028-L2036).

Локальный helper `damage_rules.py::main_attribute_factor` (прочитан 2026-10-22,
SHA256 `d4c486647e500a2da92ad2902f8611793cb40113e4add2b21c82dd605d52c660`)
реализует ту же кандидатную модель. Его синтетические тесты подтверждают арифметику
функции, а не смысл Lightchaser в клиенте. Замечание 0315 устанавливает отдельную
catalog-literal строку ratio, но не её оператор или активацию.

Только **при явно выбранной гипотезе** relative coefficient, `q=0.25` даёт:

```text
F(q) = 1 + 0.005 × (1 + q) × Σ A[a]
relative change = F(q) / F(0)
```

Например, при полностью вымышленной сумме `160`: `F(0)=1.8`, `F(0.25)=2`,
отношение `10/9`. В этой модели +25% ratio не означает общий factor `1.25` к DPS.
Это не основание автоматически выбрать гипотезу. Оператор ratio, pooling нескольких
ratio sources и отключающие/заменяющие main-stat bonus эффекты остаются gates.

## Минимальный следующий kernel

Без автоматической интеграции с билдом можно сделать чистый baseline kernel:

- Явные полные `attributes`, подтверждённый `eligible` список имён и `per_point`
  в долях; источник версии и привязка main-stat поля обязательны
- Явный режим без ratio modifiers либо отдельно названная ratio hypothesis с
  evidence/status; неизвестный оператор или activation дают blocked с null factor
- Результат `bonus`, `factor`, trace и gaps; даже известная арифметика conditional,
  без расчёта DPS, вывода support role и автоматического применения к panel/rawspell

Тесты: сумма нескольких подходящих атрибутов; исключение неподходящего; отличие
суммы от per-attribute product; explicit zero; missing/duplicate names; bool,
negative и nonfinite; неизвестные значения/activation; сохранение source context.
Пример-оракул: подходящие `90+30` дают factor `1.6`, а не `1.45×1.15=1.6675`.
Вектора ratio допустимы только с явной гипотезой; они не закрывают игровую проверку.

Для реального автоматического расчёта ещё нужны точные текущие attribute totals,
main-stat binding выбранного навыка, версия и доказанная активация. STR/DEX/INT из
native IDs 1/2/3 здесь не сопоставлялись; фактические значения остаются неизвестными.
