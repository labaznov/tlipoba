# Исходные pools критических характеристик

`damage_lab.criticalstats.evaluate(document)` — чистая условная арифметика
рейтинга крита и полного множителя Critical Strike Damage. Функция ничего не
читает, не импортирует персонажа и не применяет результат к панели или DPS.
Источник и gates являются утверждениями вызывающей стороны. Текущий игровой
оператор обычного crit damage остаётся неизвестным:
[граница доказательств](research/critical-operator-evidence.md).

Вход `tli-critical-stat-scenario-v1` имеет ровно пять полей:

```text
{
  format: "tli-critical-stat-scenario-v1",
  context: {source_sha256, skill_alias},
  gates: {version, base, scope, activation, completeness, operator},
  rating: {base, increased, more, divisor, cap},
  damage: {base, increased, policy, more}
}
```

`context.source_sha256` — обязательная строка из 64 lowercase hex символов;
`skill_alias` — явный `gem[n]`, где n содержит от одной до девяти ASCII цифр,
начиная с ненулевой. SHA — аннотация контекста, а не проверка байтов. Каталожные
записи, native IDs, версия клиента и идентичность персонажа здесь не разрешаются.

Каждый из шести gates имеет ровно `{status, evidence}`:

- `status`: `confirmed`, `unknown` или `conflict`
- `evidence`: список максимум 1000 текстовых ссылок; `confirmed` требует хотя бы
  одну. Текст длиной 1–1024 символа не имеет краевых пробелов, C0 controls или DEL;
  содержание ссылок не открывается и не проверяется

Пропущенный ключ gate становится явным gap; его объект не выдумывается.
Посторонние ключи gates и неправильные объекты отклоняются. Для корня, context,
rating, damage и отдельных gate/row все перечисленные структурные поля обязательны,
неизвестные ключи запрещены.

## Числа и неизвестность

Каждое поле rating и damage допускает `null` как явно неизвестный вход. Остальные
значения имеют следующий контракт:

| Поле | Значение |
|---|---|
| `rating.base` | Список конечных неотрицательных base rating values |
| `rating.increased` | Список ordinary increased fractions |
| `rating.more` | Список grouped more строк полного rating stat |
| `rating.divisor` | Явный конечный положительный делитель rating → probability |
| `rating.cap` | Явная конечная вероятность от 0 до 1 |
| `damage.base` | Явный конечный неотрицательный полный базовый crit multiplier |
| `damage.increased` | Список ordinary crit-damage fractions |
| `damage.policy` | `percentage_points` либо `relative_to_base` |
| `damage.more` | Список grouped more строк полного crit-damage stat |

Все числовые списки и списки more ограничены 1000 элементами. Принимаются только
Python `int`/`float`, без bool, строк, Decimal и преобразований типов.
Ordinary fractions и more fractions имеют поддерживаемые границы `-1..1e6`;
это ограничения потребителя, не установленные игровые caps. Пустой список —
явно заданный пустой pool, а не замена `null`. Полнота такого pool всё равно
требует отдельного gate.

More row имеет ровно `{id, affix, value, stacks, mode}`. `id` и `affix` используют
те же ограничения текста, что evidence. `stacks` — строго integer `0..1000`,
`mode` — `add` или `multiply`. Семантика совпадает с `formulas.additional`:
`add` складывает `value × stacks` внутри одного affix, `multiply` применяет
`(1 + value)^stacks`; полученные factors перемножаются. ID уникальны внутри
каждого отдельного stat pool, а mode одного affix не может конфликтовать.
Scope, crit-only hit и поддержка 7420 в этом формате не задаются.

## Условная арифметика

```text
B = sum(rating.base)
I = sum(rating.increased)
R = B × (1 + I) × additional(rating.more)
q = R / rating.divisor
p = min(rating.cap, q)

J = sum(damage.increased)
percentage_points: C0 = damage.base + J
relative_to_base:  C0 = damage.base × (1 + J)
C = C0 × additional(damage.more)
```

More изменяет **полный stat**, включая его base. Это отдельный оператор от
дополнительного урона критического попадания. При базе 1.5 и ordinary бонусе 0.4
две политики дают 1.9 и 2.1; full-stat more 0.2 после первой политики даёт 2.28.
Выбор политики — условие сценария, не доказательство механики текущей игры.

Нет defaults для base rating, делителя, cap либо полного crit multiplier.
Все суммы, factors, произведения и quotient должны быть конечными. Rating,
вероятность, C0, C и factors неотрицательны; ordinary суммы могут быть отрицательными,
но `1 + I < 0` и отрицательный C0 запрещены. Положительное произведение или quotient
не может незаметно превратиться в ноль из-за underflow. Явные нули base, factor
или cap допустимы. Недопустимый quotient отклоняется до cap, даже если cap равен
нулю. Некорректные не-null входы проверяются также при неизвестных gates.

## Результат и следующий consumer

`tli-critical-stat-report-v1` сохраняет `status`, `rating`, `chance`, `multiplier`,
`gaps`, detached `scenario`, `trace` и `assumptions`. Неподтверждённый или
пропущенный gate и любой `null` во входных pools дают `status="blocked"`, все три
числовых выхода `null` и `trace=[]`. Известная часть не становится частично
вычисленным критом. Структурные, числовые и арифметические нарушения вызывают
контролируемый `ValueError` без текста входного payload.

При полностью заданных согласованных входах результат имеет
`status="conditional"`. Trace сохраняет base rating, ordinary/more factors,
делитель, uncapped chance, явный cap, полный base C, выбранную policy и её
результат до/после full-stat more. Gate `confirmed` не подтверждает runtime,
актуальность capture, содержимое источника или игровой оператор.

Возможный будущий caller должен отдельно проверить соответствие source SHA и
выбранного alias своему rawspell-контексту и ограничениям этого ядра. Одного
совпадения этих двух полей недостаточно: требуется точная привязка выбранного
профиля к catalog, skill ID, группе и уровню. Gates version/level/base/conversion
и missing-эффекты самого rawspell проверяются независимо; результат этого
резолвера их не подтверждает и не очищает. Передаваться могут только chance и
полный C. Lucky crit, Lucky damage и crit-only hit more остаются отдельными входами,
а ожидание попадания и DPS принадлежат последующим стадиям.

Здесь нет автоматического адаптера, установки gates или интеграции с импортом.
Функция не использует панель, benchmark или остаточный коэффициент и не
сопоставляет native эффект 7420.

Проверка: `python -m unittest discover -s tests -p test_criticalstats.py -v`.
