"""Passive HTML for automatic candidate inputs, without damage arithmetic or source I/O."""

import json

from .report import items, text


def _known(value):
    return "неизвестно" if value is None else text(value)


def _exact(value):
    return ("<p>неизвестно</p>" if value is None else "<div class=scroll><pre>"
            + text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)) + "</pre></div>")


def _table(rows, headers):
    return ("<div class=scroll><table><thead><tr>" + "".join(f"<th>{text(value)}</th>" for value in headers)
            + "</tr></thead><tbody>" + "".join("<tr>" + "".join(f"<td>{value}</td>" for value in row) + "</tr>"
                                             for row in rows) + "</tbody></table></div>")


def _skill(member):
    if member is None:
        return "<p>Выбранный установленный камень неизвестен; соседний камень не подставляется</p>"
    rows = [(text(label), _known(member[key])) for key, label in (
        ("alias", "Alias"), ("skill_id", "Публичный skill ID"), ("group", "Группа"),
        ("slot", "Слот"), ("path", "Координаты источника"), ("gem_level", "Наблюдаемый gem level"),
        ("effective_level", "effective level"), ("catalog_category", "Категория каталога"),
        ("status", "Статус lookup"), ("reason", "Причина пробела"))]
    result = _table(rows, ("Поле", "Значение"))
    profile = member["profile"]
    if profile is None:
        return result + "<p>Каталожный профиль неизвестен</p>"
    hit = profile["hit"]
    interval = (f"<p>Кандидат базового диапазона lookup: {text(hit['min'])} – {text(hit['max'])} "
                f"({text(hit['type'])})</p>" if hit["status"] == "catalog_render_consistent"
                else "<p>Кандидат базового диапазона lookup: неизвестно</p>")
    return (result + interval + "<h3>Статус и binding каталожного hit</h3>" + _exact(hit)
            + "<h3>Эффективность добавленного урона: заявленное поле</h3>" + _exact(profile["effectivenessOfAddedDamage"])
            + "<h3>castSpeed: заявленные секунды</h3><p>Смысл поля и применение интервала неизвестны</p>"
            + _exact(profile["castSpeedField"]) + "<h3>Каталожные главные характеристики</h3>"
            "<p>Имена атрибутов не являются их итоговыми значениями</p>" + _exact(profile["mainStat"])
            + "<h3>Нормализованные теги</h3>" + _exact(profile["tags"]))


def _rows(title, rows):
    if not rows:
        return f"<h3>{text(title)}</h3><p>Наблюдаемых строк нет; полнота не подтверждена</p>"
    values = []
    for row in rows:
        details = {key: row[key] for key in ("item", "path", "definition", "pool", "status", "semantics",
                                            "type", "damage_scope", "attribute") if key in row}
        values.append((text(row["family"]), text(row["owner"]), text(row["scope"]), items(row["targets"]),
                       text(row["unit"]), _exact(row["values"]), _known(row.get("reason")),
                       "<details><summary>Источник и pool</summary>" + _exact(details) + "</details>"))
    return f"<h3>{text(title)}</h3>" + _table(values, ("Семейство", "Владелец", "Scope", "Targets", "Единица",
                                                    "Точные строки значений", "Причина исключения", "Происхождение"))


def _modifiers(data):
    if data is None:
        return "<p>Типизированные модификаторы неизвестны; пустые полные пулы не созданы</p>"
    rows = "".join(_rows(title, data[key]) for key, title in (
        ("added", "Добавленный урон"), ("increased", "Increased damage"), ("attributes", "Атрибуты"),
        ("speed", "Скорость: только инвентарь"), ("excluded", "Исключённые строки")))
    return ("<p>Строки не суммированы и не применены к панели или rawspell</p>"
            "<h3>Явный контекст тегов</h3>" + _exact(data["skill"]) + rows
            + "<h3>Пробелы модификаторов</h3>" + _exact(data["gaps"])
            + "<details><summary>Источник ledger и покрытие</summary>" + _exact(data["ledger"]) + "</details>")


def _installation(data):
    if data["members"] is None:
        return "<p>Состав группы неизвестен; поддержки соседней группы не подставляются</p>"
    rows, details = [], []
    for member in data["members"]:
        rows.append((text(member["alias"]), _known(member["slot"]), _known(member["base_id"]),
                     _known(member["gem_level"]["value"]), _known(member["category"]),
                     text(member["status"]) + "<br>" + _known(member["reason"]), _known(member["path"])))
        effects = member["effects"]
        if effects is not None:
            details.append(f"<details><summary>{text(member['alias'])}: собственные кандидаты эффектов</summary>"
                           "<h3>Нативные роллы</h3>" + _exact(effects["rolled_lines"])
                           + "<h3>Каталожные константы</h3>" + _exact(effects["constants"])
                           + "<h3>Пропуски и неизвестные константы</h3>" + _exact(effects["omissions"])
                           + _exact(effects["constant_issues"]) + "<h3>Неподтверждённая интерпретация</h3>"
                           + _exact({key: effects[key] for key in ("prefix", "activation", "effective_level", "patch",
                                                                   "additional_group_identity", "arithmetic_ready", "runtime_verified")})
                           + "</details>")
    return ((_table(rows, ("Alias", "Слот", "Публичный base ID", "Уровень камня", "Категория", "Статус", "Источник"))
             if rows else "<p>В наблюдаемой группе нет строк</p>") + "".join(details))


def _rawmodel(report):
    spell, result = report["raw_spell"], report["raw_result"]
    if spell is None:
        return "<section><h2>Модель rawspell и evaluator</h2><p>Контекст rawspell не создан; параметры не подставлены</p></section>"
    context = spell["context"]
    rows = [(text(name), _known(context[name])) for name in ("source_sha256", "catalog_sha256", "skill_id", "effective_level")]
    groups = [(text(name), "неизвестно" if spell[name] is None else "задана") for name in ("damage", "critical", "casting")]
    return ("<section><h2>Модель rawspell и evaluator</h2><p>Статус evaluator: " + text(result["status"])
            + "<br>Числовой DPS: " + _known(result["pre_defence_dps"]) + "</p>"
            + _table(rows, ("Контекст", "Значение"))
            + "<p>SHA каталога относится к выбранному master member; это не wrapper hash или runtime verification</p>"
            + _table(groups, ("Группа", "Состояние")) + "<h3>Gaps evaluator</h3>" + items(result["gaps"])
            + "<p>Частичные кандидаты не превращены в полные pools; Lucky, roll model и tick policy не выбраны</p></section>")


def render(report):
    """Reassemble an unchanged diagnostic before displaying its source-bound inputs."""
    try:
        if type(report) is not dict:
            raise ValueError
        record, alias = report["record"], report["selection"]["alias"]
        from .buildinputs import assemble

        canonical = assemble(record, skill_alias=alias)
        if json.dumps(report, sort_keys=True, allow_nan=False) != json.dumps(canonical, sort_keys=True, allow_nan=False):
            raise ValueError
        from .report import castdetails, ordinarydetails, memorydetails

        cast = castdetails(canonical["record"])
        ordinary = ordinarydetails(canonical["record"])
        memories = memorydetails(canonical["record"])
        levels = ""
        if "installed_level_candidates" in canonical["record"]:
            from .levelreport import section

            levels = section(canonical["record"]["installed_level_candidates"], canonical["record"]["installed_skills"])
    except (KeyError, TypeError, ValueError, AttributeError, OverflowError, RecursionError):
        raise ValueError("Build input HTML requires an unchanged assembled report") from None
    report = canonical
    flags = "; ".join(field + ": " + json.dumps(report[field]) for field in (
        "arithmetic_ready", "runtime_verified", "identity_verified", "import_complete"))
    return f"""<!doctype html>
<html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Автоматические входы расчёта DPS</title><style>
:root{{color-scheme:dark}}body{{margin:0;background:#101824;color:#edf3fa;font:16px/1.55 system-ui,sans-serif}}
main{{max-width:1200px;margin:auto;padding:28px 20px 60px}}section,.notice{{background:#192536;padding:20px;margin:20px 0;border-radius:10px}}
.notice{{border-left:4px solid #e5b45d}}.scroll{{overflow:auto}}table{{border-collapse:collapse;width:100%;font-size:14px}}
th,td{{text-align:left;padding:9px;border-bottom:1px solid #35475c;vertical-align:top;overflow-wrap:anywhere}}
pre{{font:13px/1.5 monospace}}summary{{cursor:pointer;color:#9de1d1}}details{{margin:12px 0}}footer{{color:#a9bacd}}
@media(max-width:700px){{main{{padding:18px 12px}}section{{padding:12px}}}}
</style></head><body><main><h1>Автоматические входы расчёта DPS</h1>
<div class=notice>DPS пока не рассчитывается<br>effective level: неизвестно<br>
Каталожные значения на уровне камня не являются фактическим уроном персонажа</div>
<section><h2>Явный выбор камня</h2><p>Alias: {text(report['selection']['alias'])}<br>
Основание: {text(report['selection']['basis'])}; статус: {text(report['selection']['status'])}<br>
Статус отчёта: {text(report['status'])}<br>{text(flags)}<br>SHA-256 источника: {_known(report['source_sha256'])}</p>
<p>Основной навык и соответствие панели не определяются автоматически</p></section>
<section><h2>Каталожные поля на уровне камня</h2>{_skill(report['skill'])}
<p>Нет подтверждения текущего patch, effective level и роста после 20</p></section>
<section><h2>Кандидаты модификаторов</h2>{_modifiers(report['modifiers'])}{cast}</section>
<section><h2>Наблюдаемая группа</h2><p>Статус: {text(report['installation']['status'])}<br>
Совместное размещение не доказывает активацию или применимость поддержки</p>{_installation(report['installation'])}</section>
{levels}
{ordinary}
{memories}
{_rawmodel(report)}
<section><h2>Пробелы расчёта</h2>{items(report['gaps'])}<h3>Допущения и границы</h3>{items(report['assumptions'])}</section>
<footer>{'Сценарий rawspell передан evaluator и заблокирован' if report['raw_spell'] is not None else 'Контекст rawspell не создан'}; неизвестные значения не заменены нулями</footer>
</main></body></html>"""
