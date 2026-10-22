# Базовый бонус основных атрибутов

`damage_lab.mainstats.evaluate(document)` вычисляет только сумму вкладов явно
подходящих основных атрибутов. Основание правила и его ограничения приведены в
[исследовании](research/main-attribute-damage.md). Это самостоятельная арифметика,
без чтения игры, импортёра и применения результата к panel, rawspell или DPS.

Вход `tli-main-stat-scenario-v1` содержит обязательные поля:

- `context`: точные lowercase SHA256 `source_sha256`, `catalog_sha256` и непустой
  `skill_id`
- `attributes`: `strength`, `dexterity`, `intelligence`, каждое — конечное
  неотрицательное число либо `null` для неизвестного значения
- `eligible`: отдельный список уникальных имён этих атрибутов; это main-stat
  binding навыка, а не damage/skill tags; пустой список допустим только как явный
  набор вызывающей стороны с теми же gates
- `per_point`: обязательная конечная неотрицательная доля бонуса за point; значения
  по умолчанию нет, в частности `0.005` автоматически не выбирается
- `ratio`: `selection: "none" | "unknown"`, `evidence: [строки]`; `none` требует
  ссылки, подтверждающей утверждение вызывающей стороны об отсутствии влияющих
  ratio/disable/replacement modifiers
- `gates`: `patch`, `main_stat_binding`, `activation`, каждый имеет
  `status: "confirmed" | "unknown" | "conflict"` и `evidence: [строки]`;
  `confirmed` требует непустого evidence

`attributes` — **полные итоговые totals**, уже после применимых изменений
атрибутов. Отдельные flat/increased attribute строки таким входом не являются.
SHA и evidence сохраняют контекст утверждений; функция не проверяет содержимое
ссылок, версию клиента, актуальность захвата или идентичность персонажа.

При подтверждённых gates, `ratio.selection="none"` и известных eligible totals:

```text
contribution[a] = attributes[a] × per_point
bonus = Σ(a ∈ eligible) contribution[a]
factor = 1 + bonus
```

Вклады складываются один раз; отдельные attribute factors не перемножаются.
Неизвестный eligible total, неизвестный ratio или неподтверждённый gate дают
`status="blocked"`, `bonus=null`, `factor=null` и конкретные `gaps`.
Неизвестный unselected total не блокирует сумму; trace показывает его исключение.
Известный ноль остаётся нулём, а неизвестность не заменяется нулём.

Результат `tli-main-stat-report-v1` сохраняет detached `scenario`, `trace`, `gaps`
и `assumptions`. Даже полностью заданная арифметика имеет `status="conditional"`:
gates являются утверждениями вызывающей стороны. Неправильная структура, bool,
отрицательные/неконечные числа, дубликаты eligible и непредставимые числовые
произведения/переполнение суммы вызывают контролируемый `ValueError`, включая malformed unselected
totals. Неизвестность не скрывает неправильный числовой вход.

Первые три строки trace имеют `attribute`, `selected`, исходное `value` и
`contribution`. У excluded contribution всегда `null`; при blocked все
contributions `null`, без частично рассчитанной суммы. У conditional следуют
строки итогового bonus (fraction) и factor. Вклады сначала масштабируются по
`per_point`, затем суммируются, без лишней промежуточной суммы исходных totals.
Evidence — список максимум 1000 непустых строк длиной максимум 1024 символа без
краевых пробелов; для `skill_id` действуют те же границы текста.

Lightchaser ratio не реализован. Нет сопоставления native IDs, вывода eligible из
tags, восстановления фактических totals или автоматического умножения готовой
панели. Совместимость bonus с конкретной стадией урона остаётся отдельным gate
будущего resolver.
