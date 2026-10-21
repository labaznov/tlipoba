"""Render one conditional upgrade comparison without I/O or active content."""

from .report import items, measurement, text


def quantity(value, unit="damage/s"):
    return "Не рассчитывается" if value is None else text(measurement(value, unit)[0])


def price(value):
    if value is None:
        return "Цена не задана"
    return "Бесплатно (0)" if value == 0 else quantity(value, "cost")


def conditions(report):
    condition = report["scenario"]["condition"]
    combat = report["scenario"]["combat"]
    rows = [("Основа", text(condition["basis"]))]
    rows.extend((label, quantity(condition[key], unit)) for key, label, unit in (
        ("active", "Активные Tangle", "count"), ("hits", "Попаданий за каст", "count"),
        ("retention", "Остаток shotgun", "fraction"), ("resistance", "Сопротивление цели", "fraction"),
        ("taken", "Внешний taken", "fraction"), ("uptime", "Uptime", "fraction")))
    if condition["basis"] == "hit":
        rows.extend([("Lucky", "Да" if condition["lucky"] else "Нет"),
                     ("Критический more", quantity(condition["critical_more"], "fraction"))])
        rows.extend((label, quantity(report["scenario"]["panel"][key], unit)) for key, label, unit in (
            ("hit_min", "Минимальный hit", "damage"), ("hit_max", "Максимальный hit", "damage"),
            ("crit_chance", "Шанс крита панели", "fraction"), ("crit_multiplier", "Критический множитель", "multiplier")))
    rows.extend([
        ("Tick-гипотеза", "Не задана" if combat["tick_frequency"] is None else quantity(combat["tick_frequency"], "Hz") + " Hz"),
        ("Броня цели", quantity(combat["armor"], "armor")),
        ("Нефизический урон", "Да" if combat["nonphysical"] else "Нет"),
    ])
    metadata = report["baseline"]["combat"]
    rows.extend((label, quantity(metadata[key], "fraction")) for key, label in (
        ("armor_penetration", "Пробивание брони"), ("armor_effectiveness", "Эффективность брони")) if key in metadata)
    rows.extend((label, text(metadata[key])) for key, label in (
        ("armor_penetration_order", "Порядок брони (гипотеза)"), ("armor_penetration_source", "Источник пробивания")) if key in metadata)
    return "<table><tbody>" + "".join(f"<tr><th>{text(label)}</th><td>{value}</td></tr>" for label, value in rows) + "</tbody></table>"


def ranking(report):
    """Preserve supplied ordering after checking its existing eligibility claims."""
    candidates = {row["id"]: row for row in report["candidates"]}
    if len(candidates) != len(report["candidates"]):
        raise ValueError("Upgrade HTML requires unique candidate identities")
    for row in candidates.values():
        if any(row[key] is not True and row[key] is not False
               for key in ("eligible_for_ranking", "eligible_for_cost_ranking")):
            raise ValueError("Upgrade HTML eligibility must use explicit booleans")
        if row["status"] not in ("incomplete", "not_upgrade", "unpriced", "free", "upgrade"):
            raise ValueError("Upgrade HTML requires known conditional candidate statuses")
        if row["eligible_for_ranking"] and (row["gaps"] or row["delta"] <= 0 or row["status"] in ("incomplete", "not_upgrade")):
            raise ValueError("Upgrade HTML cannot rank incomplete or nonpositive candidates")
        if row["eligible_for_cost_ranking"] and (not row["eligible_for_ranking"] or row["cost"] is None
                                                 or row["status"] not in ("free", "upgrade")):
            raise ValueError("Upgrade HTML cost ranking requires a supported priced gain")
    order = report["ranking"]
    if (len(set(order)) != len(order)
            or any(identity not in candidates or candidates[identity]["eligible_for_cost_ranking"] is not True for identity in order)):
        raise ValueError("Upgrade HTML ranking requires distinct eligible candidate identities")
    return order


def evidence(result):
    """Display named trace values and assumptions without dumping nested payloads."""
    rows = []
    for step in result["trace"]:
        if "factor" in step:
            value = "× " + quantity(step["factor"], "multiplier")
        else:
            unit = step.get("unit", "damage/s")
            value = quantity(step["value"], unit) + (" " + text(unit) if unit not in ("fraction", "damage/s") else "")
        rows.append(f"<tr><td>{text(step['label'])}</td><td>{value}</td></tr>")
    return ("<details><summary>Трассировка и допущения</summary><div class=scroll><table><thead><tr>"
            "<th>Величина</th><th>Значение</th></tr></thead>"
            f"<tbody>{''.join(rows)}</tbody></table></div>{items(result['assumptions'])}</details>")


def render(report):
    """Display caller-priced candidates inside the supplied conditional model."""
    if (report["format"] != "tli-upgrade-report-v1" or report["status"] != "conditional"
            or report["price_source"] != "caller" or report["baseline"]["status"] != "conditional"
            or any(row["result"]["status"] != "conditional" for row in report["candidates"])):
        raise ValueError("Upgrade HTML requires conditional results with caller prices")
    order = ranking(report)
    rows = "".join(
        f"<tr><td>{text(row['id'])}<br>{text(row['name'])}</td><td>{quantity(row['dps'])}</td>"
        f"<td>{quantity(row['delta'])}</td><td>{quantity(row['relative'], 'fraction')}</td>"
        f"<td>{price(row['cost'])}</td><td>{quantity(row['per_cost'], 'rate')}</td>"
        f"<td>{text(row['status'])}</td><td>{items(row['gaps']) if row['gaps'] else 'Нет заявленных пробелов'}"
        f"{evidence(row['result'])}</td></tr>"
        for row in report["candidates"]
    )
    return f"""<!doctype html>
<html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Условное сравнение улучшений · TLI</title>
<style>
:root{{color-scheme:dark}}body{{margin:0;background:#0d1422;color:#edf3fa;font:16px/1.55 system-ui,sans-serif}}
main{{max-width:1180px;margin:auto;padding:32px 22px 64px}}h1{{font-size:clamp(28px,4vw,42px)}}
section,.notice{{background:#182336;border:1px solid #304158;border-radius:12px;padding:20px;margin:20px 0}}
.notice{{border-left:4px solid #f2bf6e}}.muted,footer{{color:#a4b4cc}}.scroll{{overflow:auto}}
table{{border-collapse:collapse;width:100%;font-size:14px}}th,td{{text-align:left;padding:10px;border-bottom:1px solid #304158}}
td{{overflow-wrap:anywhere;vertical-align:top}}strong{{color:#83d5ce}}footer{{font-size:12px}}
@media(max-width:700px){{main{{padding:20px 14px}}section{{padding:14px}}}}
</style></head><body><main>
<p class=muted>Torchlight Infinite · условная модель</p><h1>Условное сравнение улучшений</h1>
<div class=notice>Не является подтверждённой рекомендацией купить предмет<br>
Результат зависит от поддержанных эффектов и общих условий модели</div>
<section><h2>Общий исходный сценарий</h2><p>Базовый DPS: <strong>{quantity(report['baseline']['dps'])}</strong></p>
<p>Панель, reference и условия общие для всех вариантов; заменяется только полный target-пул</p>{conditions(report)}
<h3>Общие пробелы</h3>{items(report['gaps']) if report['gaps'] else '<p>Нет заявленных общих пробелов</p>'}{evidence(report['baseline'])}
<p>Цены заданы вызывающим кодом; валюта: {text(report['currency'])}<br>Рыночные цены не запрашивались</p></section>
<section><h2>Варианты</h2><div class=scroll><table><thead><tr><th>Кандидат</th><th>DPS</th><th>Δ DPS</th>
<th>Изменение</th><th>Цена</th><th>Δ DPS / единица цены</th><th>Статус</th><th>Пробелы</th></tr></thead><tbody>{rows}</tbody></table></div></section>
<section><h2>Рейтинг по заданной стоимости</h2><ol id=ranking>{''.join(f'<li>{text(identity)}</li>' for identity in order)}</ol>
{'' if order else '<p>Нет допущенных вариантов</p>'}
<p>Бесплатные положительные варианты указаны отдельно от отношения Δ DPS к цене; неизвестная цена не равна нулю</p></section>
<footer>Все результаты условны; пустой список пробелов не доказывает полноту расчёта</footer>
</main></body></html>"""
