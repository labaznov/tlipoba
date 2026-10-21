"""Standalone Russian report built only from the public archive contract."""

import json
from html import escape
from urllib.parse import urlsplit

from .engine import calculate


def text(value):
    return escape(str(value), quote=True)


def number(value):
    return f"{value:,.0f}".replace(",", " ")


def decimal(value):
    return f"{value:.8g}"


def items(values):
    return "<ul>" + "".join(f"<li>{text(value)}</li>" for value in values) + "</ul>"


def scenarios(record, condition):
    stats = record.get("stats", {})
    rows = []
    if not all(key in stats for key in ("max_tangles", "extra_attachments", "cold_penetration")):
        return "<p>Для таблицы сценариев не хватает подтверждённых показателей Tangle или пробивания</p>"
    for active in (1, 3):
        if active > stats["max_tangles"]:
            continue
        for hits in (1, 11, 13):
            for retention in (0.2, 0.8):
                result = calculate(stats, {**condition, "active": active, "hits": hits, "retention": retention})
                rows.append(f"<tr><td>{active}</td><td>{result['attached']}</td><td>{hits}</td>"
                            f"<td>{retention:.0%}</td><td>{number(result['dps'])}</td></tr>")
    return ("<div class=scroll><table><thead><tr><th>Активные Tangle</th><th>Прикреплены к цели</th>"
            "<th>Попаданий за каст</th><th>Остаток после первого попадания</th><th>Условный DPS</th>"
            "</tr></thead><tbody>" + "".join(rows) + "</tbody></table></div>")


def render(record, calculation, condition):
    synthetic = record.get("synthetic") is True
    stats = record.get("stats", {})
    benchmark = record.get("benchmark", {})
    measured = number(benchmark["average_dps"]) if "average_dps" in benchmark else "Нет замера"
    panel = number(stats["spell_dps"]) if "spell_dps" in stats else "Нет данных"
    trace = "".join(
        f"<tr><td>{text(step['label'])}</td><td>"
        + ("× " + decimal(step["factor"]) if "factor" in step else number(step["value"]))
        + "</td></tr>" for step in calculation.get("trace", [])
    )
    conditions = "".join(f"<tr><td>{text(label)}</td><td>{text(value)}</td></tr>" for label, value in (
        ("Основа", condition["basis"]), ("Активные Tangle", condition["active"]),
        ("Попаданий за один каст", condition["hits"]),
        ("Оставшаяся доля каждого следующего попадания", decimal(condition["retention"])),
        ("Сопротивление холоду цели, доля", decimal(condition["resistance"])),
        ("Внешний increased damage taken, доля", decimal(condition["taken"])),
        ("Доля времени нанесения урона", decimal(condition["uptime"])),
    ))
    if condition["basis"] == "hit":
        conditions += (f"<tr><td>Lucky</td><td>{'Да' if condition['lucky'] else 'Нет'}</td></tr>"
                       f"<tr><td>Критический more, доля</td><td>{decimal(condition['critical_more'])}</td></tr>")
    observations = "".join(
        f"<tr><td>{text(row.get('label', row['key']))}</td><td>{text(row['value'])} {text(row.get('unit', ''))}</td>"
        f"<td>{text(row.get('precision', 'не указана'))}</td>"
        f"<td>{text(json.dumps(row.get('evidence', ''), ensure_ascii=False))}</td></tr>"
        for row in record.get("observations", [])
    )
    inventory = "".join(
        f"<h3>{label}</h3><div class=inventory>" + "".join(
            f"<article><h4>{text(entry['name'])}</h4>{items(entry.get('details', []))}</article>"
            for entry in record.get("inventory", {}).get(key, [])
        ) + "</div>"
        for key, label in (("gear", "Снаряжение"), ("skills", "Навыки и поддержки"),
                           ("talents", "Таланты"), ("memories", "Воспоминания"))
    )
    sources = []
    for label, url in record.get("facts", {}).get("sources", {}).items():
        address = urlsplit(url)
        if address.scheme in ("https", "http") and address.netloc:
            sources.append(f'<li><a href="{text(url)}" rel="noreferrer">{text(label)}</a></li>')
    command = ("python -m damage_lab --package ПАКЕТ --observations ПОКАЗАТЕЛИ.json "
               "--facts ФАКТЫ.json --output НОВАЯ_ПАПКА "
               f"--basis {condition['basis']} --active {condition['active']} --hits {condition['hits']} "
               f"--retention {decimal(condition['retention'])} --resistance {decimal(condition['resistance'])} "
               f"--taken {decimal(condition['taken'])} --uptime {decimal(condition['uptime'])}")
    if condition["basis"] == "hit":
        command += (" --lucky" if condition["lucky"] else " --no-lucky")
        command += f" --critical-more {decimal(condition['critical_more'])}"
    benchmarkrows = "".join(
        f"<tr><td>{label}</td><td>{number(benchmark[key])}{unit}</td></tr>"
        for key, label, unit in (("duration", "Длительность замера", " с"),
                                 ("highest_5s", "Максимальный DPS за 5 с", ""),
                                 ("average_5s", "Средний DPS за 5 с", "")) if key in benchmark
    )
    origin = "Синтетический пример" if synthetic else "Локальная база"
    snapshot = "пакет примера" if synthetic else "снимок"
    notice = ("Синтетический пример: все значения вымышлены<br>"
              "Значения заданы для проверки арифметики, игрового измерения здесь нет"
              if synthetic else "Это условная модель, точный реальный DPS пока не восстановлен<br>"
              "Измерение служит независимой проверкой и не используется для подгонки множителя<br>"
              "Состояние боя и трактовка панели требуют подтверждения")
    measurement = "Вымышленный бенчмарк" if synthetic else "Измерено в игре"
    reference = "Независимое контрольное число примера" if synthetic else "Средний DPS контрольного замера"
    panelnote = "Вымышленный вход для проверки математики" if synthetic else "Наблюдение из игры, другая семантика"
    heading = "Входные показатели примера" if synthetic else "Наблюдаемые показатели"
    benchmarkheading = "Вымышленный бенчмарк" if synthetic else "Контрольный замер"
    inventorynote = ("Инвентарь ниже задаёт вымышленный состав для развития модели" if synthetic
                     else "Инвентарь ниже — доказательная база для дальнейшей модели отдельных модификаторов")
    return f"""<!doctype html>
<html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{text(record.get('name', 'TLI'))} · Damage Lab</title>
<style>
:root{{color-scheme:dark;--bg:#0d1422;--panel:#182336;--muted:#a4b4cc;--line:#304158;--accent:#83d5ce}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:#edf3fa;font:16px/1.55 system-ui,sans-serif}}
main{{max-width:1180px;margin:auto;padding:42px 24px 72px}}h1{{font-size:clamp(28px,4vw,44px);line-height:1.15;margin:10px 0}}
h2{{font-size:24px;margin:0 0 14px}}h3{{font-size:19px;margin:25px 0 10px}}h4{{margin:0 0 8px;font-size:16px}}
p{{margin:8px 0 14px}}.eyebrow,.muted{{color:var(--muted)}}.eyebrow{{letter-spacing:.12em;text-transform:uppercase;font-size:13px}}
.notice{{border-left:4px solid #f2bf6e;background:#302a20;padding:16px 20px;margin:24px 0}}
.cards{{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:14px;margin:24px 0}}
.card,section{{background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:22px}}
.card strong{{display:block;font-size:clamp(22px,2.5vw,32px);margin:10px 0;color:var(--accent);font-variant-numeric:tabular-nums}}
.card small{{color:var(--muted)}}section{{margin:20px 0}}table{{border-collapse:collapse;width:100%;font-size:14px}}
th,td{{text-align:left;border-bottom:1px solid var(--line);padding:11px 12px;vertical-align:top}}th{{color:var(--muted)}}
td{{overflow-wrap:anywhere}}.scroll{{overflow:auto}}.scroll table{{min-width:700px}}a{{color:var(--accent)}}
ul{{margin:8px 0;padding-left:23px}}li{{margin:5px 0}}pre{{background:var(--bg);padding:16px;border-radius:8px;overflow:auto;font-size:13px}}
.inventory{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}}article{{border:1px solid var(--line);border-radius:8px;padding:15px}}
footer{{font-size:12px;color:var(--muted);overflow-wrap:anywhere;margin-top:24px}}@media(max-width:760px){{.cards,.inventory{{grid-template-columns:1fr}}main{{padding:26px 14px}}section{{padding:17px}}}}
</style></head><body><main>
<div class=eyebrow>Torchlight Infinite · SS14 · {origin}</div>
<h1>{text(record.get('name', 'Damage Lab'))}</h1>
<p class=muted>{text(record.get('character', 'Carino · Zealot of War'))} · {snapshot} {text(record.get('capturedAt', 'время не указано'))}</p>
<div class=notice>{notice}</div>
<div class=cards>
<div class=card>{measurement}<strong>{measured}</strong><small>{reference}</small></div>
<div class=card>Панельный Spell DPS<strong>{panel}</strong><small>{panelnote}</small></div>
<div class=card>Условный расчёт<strong>{number(calculation['dps'])}</strong><small>Только при перечисленных ниже допущениях</small></div>
</div>
<section><h2>Условия расчёта</h2><p>Проценты задаются долями: 13% = 0.13
Остаток 0.8 означает 80% урона первого попадания у каждого последующего попадания</p>
<table><tbody>{conditions}</tbody></table></section>
<section><h2>Математика сценария</h2><table><thead><tr><th>Величина или множитель</th><th>Значение</th></tr></thead>
<tbody>{trace}<tr><td><b>Условный итог</b></td><td><b>{number(calculation['dps'])} DPS</b></td></tr></tbody></table>
{items(calculation.get('assumptions', []))}</section>
<section><h2>Сценарии, а не подтверждённые границы</h2>
<p>Сравнение 1 и 3 Tangle, 1 / 11 / 13 попаданий, 20% и 80% остатка shotgun
Два варианта остатка показывают неопределённость трактовки коэффициента
Остальные условия совпадают с выбранным расчётом</p>{scenarios(record, condition)}</section>
<section><h2>Что ещё требуется подтвердить</h2>{items(record.get('coverage', []))}
<p>Суммарные бонусы панели уже содержат эффекты вещей и поддержек: повторно перемножать их нельзя
{inventorynote}</p></section>
<section><h2>{heading}</h2><div class=scroll><table><thead><tr><th>Показатель</th><th>Значение</th>
<th>Точность / округление</th><th>Доказательство</th></tr></thead><tbody>{observations}</tbody></table></div>
<h3>{benchmarkheading}</h3><table><tbody>{benchmarkrows}</tbody></table></section>
<section><h2>Состав билда</h2>{inventory}</section>
<section><h2>Повторить расчёт локально</h2><p>Каждый запуск создаёт новый каталог с SQLite, JSON и этим отчётом
Путь к существующему каталогу отклоняется</p><pre>{text(command)}</pre></section>
<section><h2>Источники правил</h2><ul>{''.join(sources)}</ul>
<p class=muted>Дата проверки базы: {text(record.get('facts', {}).get('checkedAt', 'не указана'))}</p></section>
<footer>SHA-256 исходного снимка: {text(record.get('source_sha256', 'не указан'))}<br>
Отчёт содержит выбранные факты и наблюдения; исходные native sections и идентификаторы аккаунта сюда не включаются</footer>
</main></body></html>"""
