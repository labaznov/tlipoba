"""Passive HTML for a complete conditional combat comparison, without I/O or new math."""

import json

from .combatupgrades import evaluate
from .report import items, text
from .upgradereport import price, quantity


def _table(rows, headers):
    return ("<div class=scroll><table><thead><tr>"
            + "".join(f"<th>{text(value)}</th>" for value in headers) + "</tr></thead><tbody>"
            + "".join("<tr>" + "".join(f"<td>{value}</td>" for value in row) + "</tr>" for row in rows)
            + "</tbody></table></div>")


def _conditions(report):
    scenario = report["baseline"]["scenario"]
    spell = scenario["spell"]
    target = scenario["target"]
    rows = [("Навык", text(spell["context"]["skill_id"])),
            ("SHA каталога", text(spell["context"]["catalog_sha256"])),
            ("Модель броска", text(spell["damage"]["roll_model"])),
            ("Tick-гипотеза", "Не задана" if spell["casting"]["frequency"] is None
             else quantity(spell["casting"]["frequency"], "Hz") + " Hz"),
            ("Uptime", quantity(scenario["uptime"], "fraction"))]
    rows.extend((label, quantity(target[key], unit)) for key, label, unit in (
        ("cold_resistance", "Сопротивление Cold", "fraction"),
        ("cold_penetration", "Пробивание Cold", "fraction"), ("armor", "Броня цели", "armor"),
        ("armor_effectiveness", "Эффективность брони", "fraction"),
        ("armor_penetration", "Пробивание брони", "fraction"), ("increased_taken", "Increased taken", "fraction")))
    rows.append(("Порядок пробивания брони", text(target["armor_penetration_order"])))
    modifiers = [(text(row["id"]), text(row["affix"]), quantity(row["value"], "fraction"),
                  quantity(row["stacks"], "count"), text(row["mode"])) for row in target["more_taken"]]
    return (_table(rows, ("Параметр", "Значение")) + "<h3>Полный пул more taken</h3>"
            + (_table(modifiers, ("ID", "Affix", "Величина", "Stacks", "Mode")) if modifiers else "<p>Явно пустой пул</p>"))


def _spelltrace(result):
    rows = []
    for step in result["trace"]:
        if "min" in step:
            value = quantity(step["min"], "damage") + " – " + quantity(step["max"], "damage")
        elif "factor" in step:
            value = "× " + quantity(step["factor"], "multiplier")
        else:
            value = quantity(step["value"], step.get("unit", "value"))
        rows.append((text(step["label"]), value))
    return _table(rows, ("Этап", "Значение")) if rows else "<p>Числовая трасса заблокирована</p>"


def _evidence(result):
    scenario = result["scenario"]
    spell = result["spell"]
    context = spell["scenario"]["context"]
    metadata = [("Статус расчёта варианта", text(result["status"])), ("Статус spell", text(spell["status"])),
                ("SHA источника сценария", text(context["source_sha256"])),
                ("Уровень сценария", quantity(context["effective_level"], "count"))]
    topology = [(label, quantity(scenario["topology"][key], unit)) for key, label, unit in (
        ("maximum", "Максимум Tangle", "count"), ("extra", "Дополнительные Tangle", "count"),
        ("active", "Активные Tangle", "count"), ("hits", "Попаданий за каст", "count"),
        ("retention", "Остаток shotgun", "fraction"))]
    gates = [(text(scope + ": " + name), text(gate["status"]), items(gate["evidence"]))
             for scope, values in (("spell", context["gates"]), ("combat", scenario["gates"]))
             for name, gate in values.items()]
    trace = [(text(step["stage"]), quantity(step["input"]), "× " + quantity(step["factor"], "multiplier"),
              quantity(step["output"])) for step in result["trace"]]
    return ("<details><summary>Трассы и условия варианта</summary>"
            + _table(metadata, ("Контекст", "Значение")) + "<h3>Топология варианта</h3>"
            + _table(topology, ("Параметр", "Значение")) + "<h3>Свидетельства gates</h3>"
            + _table(gates, ("Gate", "Статус", "Evidence"))
            + "<h3>Примечания сценария spell</h3>" + items(spell["scenario"]["notes"])
            + "<h3>Примечания сценария combat</h3>" + items(scenario["notes"])
            + "<h3>Допущения spell</h3>" + items(spell["assumptions"])
            + "<h3>Пробелы spell</h3>" + items(spell["gaps"])
            + "<h3>Трасса spell</h3>" + _spelltrace(spell)
            + "<h3>Допущения combat</h3>" + items(result["assumptions"])
            + "<h3>Трасса combat</h3>"
            + (_table(trace, ("Этап", "Вход", "Множитель", "Выход")) if trace else "<p>Числовая трасса заблокирована</p>")
            + "<p>Нет повторного применения crit, cast или defence</p></details>")


def render(report):
    """Display caller-priced combat results without promoting scenario assertions to runtime facts."""
    try:
        if type(report) is not dict:
            raise ValueError
        canonical = evaluate(report["scenario"])
        if json.dumps(report, sort_keys=True, allow_nan=False) != json.dumps(canonical, sort_keys=True, allow_nan=False):
            raise ValueError
    except (KeyError, TypeError, ValueError, OverflowError, RecursionError):
        raise ValueError("Combat upgrade HTML requires an unchanged evaluated report") from None
    report = canonical
    rows = "".join(
        f"<tr><td>{text(row['id'])}<br>{text(row['name'])}</td><td>{quantity(row['dps'])}</td>"
        f"<td>{quantity(row['delta'])}</td><td>{quantity(row['relative'], 'fraction')}</td>"
        f"<td>{price(row['cost'])}</td><td>{quantity(row['per_cost'], 'rate')}</td>"
        f"<td>{text(row['status'])}</td><td>{items(row['gaps'])}{_evidence(row['result'])}</td></tr>"
        for row in report["candidates"])
    order = "".join(f"<li>{text(identity)}</li>" for identity in report["ranking"])
    free = [row["id"] for row in report["candidates"] if row["status"] == "free"]
    unpriced = [row["id"] for row in report["candidates"] if row["status"] == "unpriced"]
    return f"""<!doctype html>
<html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Условное сравнение боевого DPS</title><style>
:root{{color-scheme:dark}}body{{margin:0;background:#101824;color:#edf3fa;font:16px/1.55 system-ui,sans-serif}}
main{{max-width:1280px;margin:auto;padding:28px 20px 60px}}section,.notice{{background:#192536;padding:20px;margin:20px 0;border-radius:10px}}
.notice{{border-left:4px solid #e5b45d}}.scroll{{overflow:auto}}table{{border-collapse:collapse;width:100%;font-size:14px}}
th,td{{text-align:left;padding:9px;border-bottom:1px solid #35475c;vertical-align:top;overflow-wrap:anywhere}}
details{{min-width:280px;margin:12px 0}}summary{{cursor:pointer;color:#9de1d1}}footer{{color:#a9bacd}}
@media(max-width:700px){{main{{padding:18px 12px}}section{{padding:12px}}}}
</style></head><body><main><h1>Условное сравнение боевого DPS</h1>
<div class=notice>Не является рекомендацией купить предмет<br>
Gates — утверждения сценария, а не проверка актуального состояния персонажа</div>
<section><h2>Baseline</h2>
<p>Базовый DPS: <strong>{quantity(report['baseline']['dps'])}</strong></p>
<p>Статус baseline: {text(report['baseline']['status'])}</p>{items(report['gaps'])}
{_evidence(report['baseline'])}
<h2>Общие условия</h2>{_conditions(report)}</section>
<section><h2>Полные замены сценария</h2>
<p>Цены заданы вызывающей стороной; валюта: {text(report['currency'])}</p>
<p>Рыночные цены не запрашивались</p><p>При нулевом baseline относительное изменение не определено</p>
<div class=scroll><table><thead><tr>
<th>Кандидат</th><th>DPS</th><th>Δ DPS</th><th>Изменение</th><th>Цена</th><th>Δ DPS / цену</th><th>Статус</th><th>Пробелы и трассы</th>
</tr></thead><tbody>{rows}</tbody></table></div></section>
<section><h2>Рейтинг по заданной стоимости</h2><ol id=ranking>{order}</ol>
{'' if order else '<p>Нет допущенных вариантов</p>'}
<h3>Бесплатные улучшения</h3>{items(free) if free else '<p>Нет</p>'}
<p>Деление на нулевую цену не выполняется</p><h3>Без известной цены</h3>
{items(unpriced) if unpriced else '<p>Нет</p>'}<p>Без известной цены вариант не входит в ценовой рейтинг</p>
</section><footer>Пустой список пробелов не подтверждает полноту модели или фактический DPS</footer>
</main></body></html>"""
