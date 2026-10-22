"""Standalone Russian report built only from the public archive contract."""

import json
from decimal import Decimal, localcontext
from html import escape
from urllib.parse import urlsplit

from .combat import apply
from .engine import calculate
from .validation import compare


def text(value):
    return escape(str(value), quote=True)


def number(value):
    return f"{value:,.0f}".replace(",", " ")


def decimal(value):
    return f"{value:.8g}"


def measurement(value, unit):
    """Format imported numeric evidence without shortening its decimal digits."""
    quantity = Decimal(str(value))
    if unit == "fraction":
        with localcontext() as context:
            context.prec = max(context.prec, len(quantity.as_tuple().digits) + 2)
            quantity *= 100
    display = format(quantity, ",f").replace(",", " ")
    if unit == "fraction":
        display = (display.rstrip("0").rstrip(".") if "." in display else display) + "%"
        unit = "%"
    return display, unit


def tracing(step):
    """Format explicit trace units while keeping legacy damage totals rounded."""
    if "factor" in step:
        return "× " + decimal(step["factor"])
    if "unit" in step:
        value, unit = measurement(step["value"], step["unit"])
        return text(value if unit == "%" else f"{value} {unit}")
    return number(step["value"])


def items(values):
    return "<ul>" + "".join(f"<li>{text(value)}</li>" for value in values) + "</ul>"


def contents(record):
    return "".join(
        f"<h3>{label}</h3><div class=inventory>" + "".join(
            f"<article><h4>{text(entry['name'])}</h4>{items(entry.get('details', []))}</article>"
            for entry in record.get("inventory", {}).get(key, [])
        ) + "</div>"
        for key, label in (("gear", "Снаряжение"), ("skills", "Навыки и поддержки"),
                           ("talents", "Таланты"), ("memories", "Воспоминания"),
                           ("slates", "Плиты божественности"), ("traits", "Свойства героя"),
                           ("systems", "Покрытие систем"))
    )


def logdetails(record):
    """Display safe cohort provenance without promoting a numeric identity match."""
    if "panel_log" not in record:
        return ""
    data = record["panel_log"]
    if data["identity_verified"] is not False:
        raise ValueError("Panel log cannot verify build identity")
    return ("<section><h2>Лог панели</h2>"
            f"<p>Формат: {text(data['format'])}; статус: {text(data['status'])}<br>"
            f"Подтверждённых полей: {text(data['known'])}; неизвестных атрибутов: {text(data['unknown_attributes'])}<br>"
            f"Состояние: {text(data['cohort']['timestamp'])}; кадр: {text(data['cohort']['frame'])}<br>"
            f"SHA-256 лога: {text(data['source_sha256'])}<br>identity_verified: false</p>"
            "<p>Совпадение Spell DPS не подтверждает принадлежность лога персонажу</p></section>")


def provenance(row):
    """Show only mapped attribute coordinates, never raw log sections."""
    if "source" not in row:
        return ""
    data = {key: row["source"][key] for key in (
        "attr_id", "index", "raw_value", "timestamp", "frame", "line_numbers",
    )}
    if "raw_values" in row["source"]:
        data["raw_values"] = row["source"]["raw_values"]
    return "<br>" + text(json.dumps(data, ensure_ascii=False))


def skilldetails(record):
    """Keep level-table parameters visible independently of panel aggregates."""
    if "skill_values" not in record:
        return ""
    rows = "".join(
        f"<tr><td>{text(row['name'])}</td><td>{text(row['level'])}</td><td>{text(row['status'])}</td>"
        f"<td>{text(json.dumps(row['values'], ensure_ascii=False))}</td></tr>"
        for row in record["skill_values"]
    )
    return ("<section><h2>Параметры навыков по уровню</h2>"
            "<p>Значения сохранены из таблиц каталога и не применены повторно к агрегатам панели</p>"
            "<div class=scroll><table><thead><tr><th>Навык</th><th>Уровень</th><th>Статус</th>"
            f"<th>Значения</th></tr></thead><tbody>{rows}</tbody></table></div></section>")


def installeddetails(record):
    """Display observed co-membership without claiming enabled supports or effective levels."""
    if "installed_skills" not in record:
        return ""
    from .installedskills import summary

    data = summary(record["installed_skills"])
    if "source_sha256" in record and record["source_sha256"] != data["source"]["sha256"]:
        raise ValueError("Installed skills report differs from the record source hash")
    rows = []
    for group in data["groups"]:
        for member in group["members"]:
            level = "неизвестно" if member["gem_level"] is None else member["gem_level"]
            identity = "неизвестно" if member["skill_id"] is None else member["skill_id"]
            rows.append(f"<tr><td>{text(group['alias'])}</td><td>{text(member['alias'])}</td>"
                        f"<td>{text(identity)}</td><td>{text(level)}</td><td>{text(member['membership'])}</td>"
                        f"<td>{text(member['path'])}</td></tr>")
    links = "".join(f"<tr><td>{text(row['group'])}</td><td>{text(row['primary'])}</td>"
                    f"<td>{text(row['secondary'])}</td><td>{text(row['basis'])}</td></tr>"
                    for row in data["relationships"])
    count = len(data["relationships"]) if data["domains"]["client"]["status"] == "captured" else "неизвестно"
    return ("<section><h2>Установленные навыки и связи</h2>"
            f"<p>Установленных связей: {text(count)}<br>Активация неизвестна<br>Эффективные уровни неизвестны</p>"
            "<p>Размещение в одной группе не подтверждает роль поддержки, выбранный навык панели или действие эффекта"
            "<br>Уровень камня — наблюдение установки<br>Установленные связи не применены к DPS</p>"
            "<div class=scroll><table><thead><tr><th>Группа</th><th>Камень</th><th>ID навыка</th>"
            "<th>Уровень камня</th><th>Сопоставление</th><th>Источник</th></tr></thead>"
            f"<tbody>{''.join(rows)}</tbody></table></div>"
            "<h3>Совместное размещение</h3><div class=scroll><table><thead><tr><th>Группа</th>"
            "<th>Камень в слоте 1</th><th>Другой камень</th><th>Основание</th></tr></thead>"
            f"<tbody>{links}</tbody></table></div><details><summary>Полнота и наблюдения источника</summary>"
            f"<pre>{text(json.dumps({'domains': data['domains'], 'issues': data['issues'],
                                   'unmatched_server_slots': data['unmatched_server_slots']}, ensure_ascii=False, indent=2))}</pre>"
            f"</details><p>SHA-256 исходного снимка: {text(data['source']['sha256'])}</p></section>")


def supportdetails(record):
    """Display validated installed candidates and declared catalog slices without applying damage."""
    from .importer import supportsummary

    projected = supportsummary(record)
    if not projected:
        return ""
    inventory = projected["installed_support_effects"]
    catalog = projected["installed_support_catalog"]

    def known(value):
        return "неизвестно" if value is None else text(value)

    def exact(value):
        return ("<p>Неизвестно</p>" if value is None else "<div class=scroll><pre>"
                + text(json.dumps(value, ensure_ascii=False, indent=2)) + "</pre></div>")

    rows, details = [], []
    if inventory["members"] is None:
        members = "<p>Состав поддержек неизвестен; это не пустой список</p>"
    else:
        for member in inventory["members"]:
            rows.append(f"<tr><td>{text(member['alias'])}<br>{known(member['group'])}</td>"
                        f"<td>{known(member['slot'])}<br>{known(member['path'])}</td>"
                        f"<td>{known(member['gem_level']['value'])}</td><td>{known(member['category'])}</td>"
                        f"<td>{text(member['status'])}<br>{known(member['reason'])}<br>{text(member['group_status'])}</td></tr>")
            effect = member["effects"]
            if effect is not None:
                metadata = {field: effect[field] for field in (
                    "arithmetic_ready", "runtime_verified", "activation", "effective_level", "patch",
                    "additional_group_identity", "prefix", "catalog_schema",
                )}
                details.append(f"<details><summary>{text(member['alias'])}: кандидаты эффектов</summary>"
                               "<h3>Нативные роллы</h3>" + exact(effect["rolled_lines"])
                               + "<h3>Каталожные константы</h3>" + exact(effect["constants"])
                               + "<h3>Пропуски строк и пробелы констант</h3>" + exact(effect["omissions"])
                               + exact(effect["constant_issues"]) + "<h3>Статусы интерпретации</h3>"
                               + exact(metadata) + "</details>")
        members = ("<div class=scroll><table><thead><tr><th>Камень и группа</th><th>Слот и источник</th>"
                   "<th>Наблюдаемый уровень камня</th><th>Категория</th><th>Статус и причина</th></tr></thead>"
                   f"<tbody>{''.join(rows)}</tbody></table></div>"
                   if rows else "<p>В захваченном слое нет записей</p>")
    counts = inventory["accounting"]
    flags = "; ".join(field + ": " + json.dumps(inventory[field]) for field in (
        "arithmetic_ready", "runtime_verified", "identity_verified", "import_complete",
    ))
    return ("<section><h2>Эффекты установленных поддержек</h2>"
            "<p>Активация неизвестна<br>Эффективный уровень неизвестен<br>"
            "Уровень камня — наблюдаемое поле, а не эффективный уровень<br>Эффекты поддержек не применены к DPS</p>"
            f"<p>{text(flags)}<br>Patch: {text(inventory['patch'])}<br>"
            f"Слой клиента: {text(inventory['client_layer'])}; слой сервера: {text(inventory['server_layer'])}</p>"
            f"<p>Записей: {known(counts['members'])}; Кандидаты эффектов: {known(counts['effect_candidates'])}; "
            f"Исключено: {known(counts['excluded'])}; Пробелов: {known(counts['gaps'])}</p>"
            + members + "".join(details)
            + "<h3>Ограничения доказательств</h3>" + items(inventory["limitations"])
            + f"<p>SHA-256 исходного снимка: {text(inventory['source']['sha256'])}</p>"
            "<h3>Объявленное происхождение каталога</h3>"
            "<p>Хеши относятся к сохранённым локальным байтам и здесь повторно не вычисляются<br>"
            "network_bytes_verified: false; current_patch_verified: false<br>"
            "wrapper_sha256 — весь wrapper; member_sha256 — диапазон byte_range</p>"
            f"<p>Документов каталога: {len(catalog['documents'])}; категорий: {len(catalog['categories'])}<br>"
            f"Строк каталога: {catalog['records']}; сохранённых записей: {catalog['skills']}; "
            f"невалидных: {catalog['invalid_records']}; удержанных строк: {catalog['withheld_records']}; "
            f"без English entry: {catalog['records_without_english']}</p>"
            "<details><summary>Координаты, области SHA и карты адресов</summary>"
            + exact({field: catalog[field] for field in ("derivation", "identity_bridges", "mapping_files", "documents", "categories")})
            + "</details></section>")


def staticdetails(record):
    """Show source-bound catalog interpretations separately from applied damage."""
    if "static_combat" not in record:
        return ""
    from .staticcombat import summary

    data = summary(record["static_combat"])
    if "source_sha256" in record and record["source_sha256"] != data["source"]["sha256"]:
        raise ValueError("Static combat ledger differs from the report source")
    counts = data["accounting"]
    catalogs = "".join(
        f"<tr><td>{text(path)}</td><td>{text(row['status'])}<br>{text(row['issue'])}</td><td>{text(row['sha256'])}</td></tr>"
        for path, row in data["catalog"]["documents"].items())
    modifiers = "".join(
        f"<tr><td>{text(row['item'])}<br>{text(row['path'])}</td><td>{text(row['family'])}<br>"
        f"{text(', '.join(row['targets']))}"
        f"{('<br>' + text(json.dumps(row['semantics'], ensure_ascii=False))) if 'semantics' in row else ''}</td>"
        f"<td>{text(row['owner'])} / {text(row['scope'])}</td>"
        f"<td>{text(row['unit'])}<br>{text(json.dumps(row['values'], ensure_ascii=False))}</td>"
        f"<td>{text(json.dumps(row['definition'], ensure_ascii=False))}<br>"
        f"pool: {text(json.dumps(row['pool'], ensure_ascii=False))}<br>{text(row['status'])}</td></tr>"
        for row in data["modifiers"])
    omissions = "".join(f"<tr><td>{text(row['item'])}</td><td>{text(row['path'])}</td>"
                         f"<td>{text(row['reason'])}</td></tr>"
                         for row in data["omitted"] + data["structural_gaps"])
    pending = sum("semantics" in row for row in data["modifiers"])
    return ("<section><h2>Статические аффиксы вещей</h2>"
            "<p>Частичный реестр каталожных интерпретаций</p><p>Аффиксы не применены к DPS</p>"
            f"{f'<p>Критических строк без арифметики: {pending}</p>' if pending else ''}"
            f"<p>Формат: {text(data['format'])}; версия: {text(data['version'])}<br>"
            f"Источник: {text(data['source']['section'])}; SHA-256: {text(data['source']['sha256'])}<br>"
            "runtime.verified: false; selection_verified: false; source_patch: unknown; activation: unverified</p>"
            f"<p>Предметов: {text(counts['items'])}; пустых слотов: {text(counts['empty_rows'])}<br>"
            f"Наблюдаемых строк: {text(counts['observed'])}; Типизировано: {text(counts['compiled'])}; "
            f"Пропущено: {text(counts['omitted'])}; Структурных пробелов: {text(counts['structural_gaps'])}<br>"
            f"Область сверки: {text(counts['scope'])}; reconciles: true</p>"
            "<p>Сверка счётчиков не подтверждает полноту билда, активацию или версию клиента</p>"
            f"<p>Флаги каталога: {text(', '.join(data['catalog']['flags'])) if data['catalog']['flags'] else 'нет'}</p>"
            "<details><summary>Входные документы каталога</summary><div class=scroll><table><thead>"
            "<tr><th>Документ</th><th>Статус</th><th>SHA-256 входа компилятора</th></tr></thead>"
            f"<tbody>{catalogs}</tbody></table></div></details>"
            "<details><summary>Типизированные строки</summary><div class=scroll><table><thead>"
            "<tr><th>Предмет и источник</th><th>Семейство</th><th>Владелец и scope</th>"
            f"<th>Значения</th><th>Определение и pool</th></tr></thead><tbody>{modifiers}</tbody></table></div></details>"
            "<details><summary>Пропуски и структурные пробелы</summary><div class=scroll><table><thead>"
            "<tr><th>Предмет</th><th>Источник</th><th>Причина</th></tr></thead>"
            f"<tbody>{omissions}</tbody></table></div></details></section>")


def resolutiondetails(record):
    """Display a saved-controller claim without promoting identity or freshness."""
    if "build_resolution" not in record:
        return ""
    from .buildresolution import summary

    data = summary(record["build_resolution"])
    identity = data["identity"]
    coverage, gate, freshness = (data[name] for name in ("coverage", "gate", "freshness"))
    sections = "".join(f"<tr><td>{text(name)}</td><td>{text(status)}</td></tr>"
                       for name, status in coverage["sections"].items())
    return ("<section><h2>Проверка сохранённого снимка</h2>"
            f"<p>Формат: {text(data['format'])}; версия: {text(data['version'])}<br>"
            f"SHA-256 исходного снимка: {text(data['source']['sha256'])}<br>"
            f"Статус сохранённого снимка: {text(data['status'])}<br>"
            f"Основание сравнения: {text(identity['basis'])}<br>"
            f"Сокращённый отпечаток кода: {text(identity['code_fingerprint']) if identity['code_fingerprint'] is not None else 'Не установлен'}<br>"
            f"expected_code_matched — совпадение с сохранённым полем: {text(json.dumps(identity['expected_code_matched']))}</p>"
            f"<p>Кандидатная сверка дескриптора — descriptor_match: {text(identity['descriptor_match'])}<br>"
            f"capture_verified_flag: {text(json.dumps(identity['capture_verified_flag']))}<br>"
            "Флаг захвата не является уровнем верификации<br>"
            f"Согласованность автора: {text(identity['author_consistency'])}; "
            f"согласованность идентификатора игрока: {text(identity['player_id_consistency'])}</p>"
            "<p>transport.verified: false<br>payload_self_identifies: false<br>freshness.status: unknown</p>"
            "<p>Сравнение кода не подтверждает идентичность пэйлоада или свежесть</p>"
            f"<p>Вид источника: {text(data['transport']['kind'])}<br>Статус доступа: {text(gate['status'])}<br>"
            f"feature_status: {text(gate['feature_status'])}<br>real_feature_status: {text(gate['real_feature_status'])}</p>"
            f"<p>data_version.first: {text(coverage['data_version']['first']) if coverage['data_version']['first'] is not None else 'Не установлено'}<br>"
            f"data_version.second: {text(coverage['data_version']['second']) if coverage['data_version']['second'] is not None else 'Не установлено'}<br>"
            f"Сравнений версий аффиксов: {text(coverage['affix_versions']['checked'])}<br>"
            f"Расхождений версий: {text(coverage['affix_versions']['mismatched'])}</p>"
            "<h3>Сохранённые секции</h3><div class=scroll><table><thead><tr><th>Секция</th><th>Статус</th></tr></thead>"
            f"<tbody>{sections}</tbody></table></div>"
            f"<p>required_missing: {'нет' if not coverage['required_missing'] else ''}</p>"
            f"{items(coverage['required_missing']) if coverage['required_missing'] else ''}"
            f"<p>Время захвата: {text(freshness['captured_at']) if freshness['captured_at'] is not None else 'Не установлено'}<br>"
            f"captured_at_status: {text(freshness['captured_at_status'])}<br>"
            f"Структура кода: {text(identity['code_structure']) if identity['code_structure'] is not None else 'Не установлена'}<br>"
            f"Время UUID кода (кандидат): {text(freshness['code_minted_at']) if freshness['code_minted_at'] is not None else 'Не установлено'}<br>"
            f"payload_generated_at: не установлено<br>is_old_data: {text(freshness['is_old_data'])}</p>"
            "<p>Время UUID и версии данных не подтверждают свежесть содержимого</p>"
            f"<h3>Предупреждения</h3>{items(data['warnings']) if data['warnings'] else '<p>Предупреждений нет</p>'}"
            f"<h3>Пути источника диагностики</h3>{items(data['source_paths'])}</section>")


def importdetails(record):
    """Display observed composition without promoting it to effective mechanics."""
    if "import_coverage" not in record:
        return ""
    data = record["import_coverage"]
    if data["import_complete"] is not False:
        raise ValueError("Import coverage must remain incomplete")
    rows = []
    for name, label, keys in (
        ("equipment", "Снаряжение", ("items", "invalid_records", "affixes", "affixes_with_rolls", "affixes_without_rolls", "invalid_affixes")),
        ("skill_layout", "Навыки и поддержки", ("groups", "main_skills", "supports", "integer_levels", "invalid_levels", "invalid_records", "empty_slots")),
        ("hero_traits", "Свойства героя", ("selected_traits", "memories", "invalid_records")),
        ("talents", "Таланты", ("trees", "nodes_with_points", "invalid_records")),
        ("slates", "Плиты божественности", ("slates", "empty_slots", "invalid_records")),
        ("pactspirits", "Духи пакта", ("pactspirits", "empty_slots", "invalid_records")),
        ("native_stats", "Характеристики из пакета", ("named", "unnamed_stat_pairs", "other_unnamed_fields")),
        ("panel_skill_identity", "Принадлежность панели навыку", ()),
        ("support_activation", "Активация поддержек", ("installed_supports",)),
    ):
        domain = data["domains"][name]
        counts = [f"{key}: {domain['counts'][key]}" for key in keys if key in domain["counts"]]
        details = [f"{key}: {json.dumps(domain[key], ensure_ascii=False)}" for key in {
            "hero_traits": ("rank_status", "base_trait_rank", "rank_source"),
            "native_stats": ("semantics", "protocol_verified"),
            "panel_skill_identity": ("identity",),
            "support_activation": ("activation", "reason"),
        }.get(name, ()) if key in domain]
        if name == "skill_layout" and "guide_support_level_values" in domain:
            values = domain["guide_support_level_values"]
            details.append("guide_support_level_values: " + ("Не извлечено" if values is None else "; ".join(
                f"{key}: {values[key]}" for key in ("resolved", "missing_level", "duplicate_level", "invalid_value",
                                                  "unverified_flat_tail", "not_level_scaled", "absent", "unknown_status", "invalid")
                if key in values)))
        rows.append(f"<tr><td>{text(label)}<br>{text(name)}</td><td>{text(domain['composition'])}</td>"
                    f"<td>{text(domain['effective'])}{items(details) if details else ''}</td>"
                    f"<td>{items(counts) if counts else 'Не извлечено'}</td>"
                    f"<td>{items(domain['paths']) if domain['paths'] else 'Не извлечено'}</td></tr>")
    gaps = "".join(
        f"<tr><td>{text(row['domain'])}</td><td>{text(row['composition'])}</td>"
        f"<td>{text(row['gap'])}</td><td>{text(row['next'])}</td></tr>"
        for row in data["gaps"]
    )
    source = data["source"]
    guide = data["guide"]
    return ("<section><h2>Покрытие импорта</h2><p>Импорт остаётся неполным<br>import_complete: false</p>"
            "<p>Наблюдение не подтверждает активацию: состав, эффективные значения и условия срабатывания проверяются отдельно</p>"
            f"<p>Формат: {text(data['format'])}; Версия: {text(data['version'])}; источник: {text(data['tool'])}<br>"
            f"SHA-256 источника: {text(source['sha256'])}<br>"
            f"Время источника: {text(source['captured_at']) if source['captured_at'] is not None else 'Не установлено'}<br>"
            f"Статус времени: {text(source['captured_at_status'])}<br>"
            f"Сопроводительные данные: {'предоставлены' if guide['supplied'] else 'не предоставлены'}<br>"
            f"SHA-256 сопроводительных данных: {text(guide['sha256']) if guide['sha256'] is not None else 'Не указан'}<br>"
            f"Связь с источником: {text(guide['binding'])}</p>"
            "<div class=scroll><table><thead><tr><th>Область</th><th>Состав</th><th>Эффекты</th><th>Количество</th><th>Пути источника</th></tr></thead>"
            f"<tbody>{''.join(rows)}</tbody></table></div><h3>Пробелы и следующие проверки</h3>"
            "<div class=scroll><table><thead><tr><th>Область</th><th>Состав</th><th>Пробел</th><th>Следующая проверка</th>"
            f"</tr></thead><tbody>{gaps}</tbody></table></div><h3>Границы покрытия</h3>{items(data['rules'])}</section>")


def rankdetails(record):
    """Display unresolved trait candidates separately from applied combat parameters."""
    if "trait_ranks" not in record:
        return ""
    data = record["trait_ranks"]
    if data["rule_status"] != "rank_rule_unverified" or any(row["rank"] is not None for row in data["traits"]):
        raise ValueError("Trait rank projection must keep unverified ranks unresolved")
    traits, candidates, memories = [], [], []
    for row in data["traits"]:
        traits.append(f"<tr><td>{text(row['trait_id']) if row['trait_id'] is not None else 'ID не установлен'}</td><td>{text(row['index'])}</td>"
                      f"<td>Ранг не установлен</td><td>{text(row['status'])}</td>"
                      f"<td>{text(row['memory_position']) if row['memory_position'] is not None else 'Не установлена'}</td>"
                      f"<td>{'Не сравнены' if row['candidates_agree'] is None else 'Да' if row['candidates_agree'] else 'Нет'}</td></tr>")
        for candidate in row["candidates"]:
            candidates.append(f"<tr><td>{text(row['trait_id'])}</td><td>{text(candidate['rule'])}</td>"
                              f"<td>{text(candidate['formula'])}</td>"
                              f"<td>{text(candidate['value']) if candidate['value'] is not None else 'Не вычислен'}</td>"
                              f"<td>{text(candidate['status'])}</td><td>{items(candidate['inputs'])}</td></tr>")
    for memory in data["memories"]:
        rows = "".join(
            f"<tr><td>{text(label)}</td>"
            f"<td>{text(memory['fields'][key]['value']) if memory['fields'][key]['value'] is not None else 'Не извлечено'}</td>"
            f"<td>{text(memory['fields'][key]['status'])}</td><td>{text(memory['fields'][key]['path'])}</td></tr>"
            for key, label in (("client_fixed", "Клиентский fixed"), ("from_enhance", "Прибавка усиления"),
                               ("server_fixed", "Серверный fixed"), ("level", "Уровень воспоминания"))
        )
        linkage = "; ".join(f"{text(key)}: {text(memory['linkage'][key])}"
                            for key in ("status", "slot", "server_index") if key in memory["linkage"])
        memories.append(f"<article><h4>Позиция памяти в источнике: {text(memory['position'])}; "
                        f"base ID: {text(memory['base_id']) if memory['base_id'] is not None else 'Не извлечён'}</h4>"
                        f"<p>Вклад fixed affix: {text(memory['fixed_affix_contribution']) if memory['fixed_affix_contribution'] is not None else 'Не извлечён'}"
                        f"<br>Источник: {text(memory['fixed_affix_source'])}<br>Согласованность: {text(memory['consistency'])}"
                        f"<br>Связь с выбранным свойством: {linkage}</p>"
                        "<div class=scroll><table><thead><tr><th>Поле</th><th>Значение</th><th>Статус</th><th>Путь источника</th>"
                        f"</tr></thead><tbody>{rows}</tbody></table></div></article>")
    unlinked = ("<p>Слоты памяти без выбранного свойства (нумерация с 1): "
                + ", ".join(text(slot) for slot in data["memories_without_selected_trait"]) + "</p>"
                if data["memories_without_selected_trait"] else "")
    return ("<section><h2>Ранги свойств героя</h2>"
            "<p>Правило ранга не подтверждено; кандидаты не выбираются автоматически и не применяются к DPS</p>"
            "<p>Неизвестное базовое свойство остаётся без ранга: ранг 1 по умолчанию не назначается<br>"
            "Совпадение кандидатов не подтверждает правило</p>"
            f"<p>Формат: {text(data['format'])}; правило: {text(data['rule_status'])}<br>"
            f"SHA-256 исходного снимка: {text(data['source_sha256'])}</p>"
            "<div class=scroll><table><thead><tr><th>ID свойства</th><th>Индекс</th><th>Итоговый ранг</th>"
            f"<th>Статус</th><th>Позиция памяти в источнике</th><th>Кандидаты совпадают</th></tr></thead><tbody>{''.join(traits)}</tbody></table></div>"
            "<h3>Кандидаты ранга</h3><div class=scroll><table><thead><tr><th>ID свойства</th><th>Правило</th>"
            f"<th>Формула</th><th>Значение</th><th>Статус</th><th>Источники</th></tr></thead><tbody>{''.join(candidates)}"
            f"</tbody></table></div><h3>Поля воспоминаний</h3>{''.join(memories)}{unlinked}<h3>Допущения и пробелы</h3>"
            f"{items(data['assumptions'])}{items(data['gaps'])}</section>")


def render_import(record):
    """Display available imported evidence without computing a combat scenario."""
    evidence = {row["key"]: row for row in record.get("observations", [])}
    values = list(record.get("stats", {}).items()) + [
        (f"benchmark_{key}", value) for key, value in record.get("benchmark", {}).items()
    ]
    rows = []
    for key, value in values:
        entry = evidence.get(key, {})
        display, unit = measurement(value, entry.get("unit", "не указана"))
        rows.append(f"<tr><td>{text(entry.get('label', key))}</td><td>{text(display)}</td>"
                    f"<td>{text(unit)}</td><td>{text(entry.get('precision', 'не указана'))}</td>"
                    f"<td>{text(entry.get('evidence', 'не указано'))}{provenance(entry)}</td></tr>")
    rows = "".join(rows)
    native = record.get("native_stats", {})
    origin = "Синтетический пакет: показатели вымышлены" if record.get("synthetic") is True else "Локальный пакет экспорта"
    coverage = items(record.get("coverage", []))
    missing = items(record.get("missing_stats", []))
    return f"""<!doctype html>
<html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{text(record.get('name', 'TLI'))} · Частичный импорт</title>
<style>
:root{{color-scheme:dark}}body{{margin:0;background:#0d1422;color:#edf3fa;font:16px/1.55 system-ui,sans-serif}}
main{{max-width:1100px;margin:auto;padding:32px 22px 64px}}h1{{font-size:clamp(28px,4vw,42px)}}
section,.notice{{background:#182336;border:1px solid #304158;border-radius:12px;padding:20px;margin:20px 0}}
.notice{{border-left:4px solid #f2bf6e}}.muted,footer{{color:#a4b4cc}}.scroll{{overflow:auto}}
table{{border-collapse:collapse;width:100%;font-size:14px}}th,td{{text-align:left;padding:10px;border-bottom:1px solid #304158}}
td,footer{{overflow-wrap:anywhere}}.inventory{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}}
article{{border:1px solid #304158;border-radius:8px;padding:14px}}h4{{margin:0 0 8px}}footer{{font-size:12px}}
@media(max-width:700px){{.inventory{{grid-template-columns:1fr}}main{{padding:20px 14px}}}}
</style></head><body><main>
<p class=muted>Torchlight Infinite · {text(origin)}</p>
<h1>{text(record.get('name', 'TLI'))}</h1><p>{text(record.get('character', 'Герой не указан'))}</p>
<div class=notice><b>Частичный импорт</b><br>Боевой DPS пока недоступен: не хватает подтверждённых характеристик или механик
<p>Состав и доступные показатели перенесены из пакета; неизвестные значения не заменяются нулями
Панельный Spell DPS — перенесённый показатель, а не вычисленный боевой DPS</p></div>
<section><h2>Автоматически извлечённые показатели</h2>
<p>Именованных полей: {text(native.get('known', 0))}; неизвестных stat ID: {text(native.get('unknown_stat_ids', 'не указано'))}
<br>Универсальная схема протокола не подтверждена</p>
<div class=scroll><table><thead><tr><th>Показатель</th><th>Значение</th><th>Единица</th><th>Точность</th><th>Происхождение</th></tr></thead>
<tbody>{rows}</tbody></table></div>{'' if rows else '<p>Подтверждённые показатели пока недоступны</p>'}</section>
{logdetails(record)}
{skilldetails(record)}
{rankdetails(record)}
{importdetails(record)}
{resolutiondetails(record)}
{staticdetails(record)}
{installeddetails(record)}
{supportdetails(record)}
<section><h2>Пробелы автоматического импорта</h2>{missing}{coverage}
<p>Недостающие данные предстоит извлечь автоматически; ручной ввод характеристик не требуется</p></section>
<section><h2>Доступный состав билда</h2>{contents(record)}</section>
<footer>Время снимка: {text(record.get('capturedAt', 'не указано'))}<br>
SHA-256 исходного снимка: {text(record.get('source_sha256', 'не указан'))}<br>
Этот отчёт не содержит исходные native sections и идентификаторы аккаунта</footer>
</main></body></html>"""


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
                if "combat" in condition:
                    result = apply(stats, result, condition["combat"])
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
        + tracing(step)
        + "</td></tr>" for step in calculation.get("trace", [])
    )
    conditions = "".join(f"<tr><td>{text(label)}</td><td>{text(value)}</td></tr>" for label, value in (
        ("Основа", condition["basis"]), ("Активные Tangle", condition["active"]),
        ("Попаданий за один каст", condition["hits"]),
        ("Оставшаяся доля каждого следующего попадания", decimal(condition["retention"])),
        ("Эффективное сопротивление холоду цели, доля", decimal(condition["resistance"])),
        ("Внешний increased damage taken, доля", decimal(condition["taken"])),
        ("Доля времени нанесения урона", decimal(condition["uptime"])),
    ))
    if condition["basis"] == "hit":
        conditions += (f"<tr><td>Lucky</td><td>{'Да' if condition['lucky'] else 'Нет'}</td></tr>"
                       f"<tr><td>Критический more, доля</td><td>{decimal(condition['critical_more'])}</td></tr>")
    observations = "".join(
        f"<tr><td>{text(row.get('label', row['key']))}</td><td>{text(row['value'])} {text(row.get('unit', ''))}</td>"
        f"<td>{text(row.get('precision', 'не указана'))}</td>"
        f"<td>{text(json.dumps(row.get('evidence', ''), ensure_ascii=False))}{provenance(row)}</td></tr>"
        for row in record.get("observations", [])
    )
    inventory = contents(record)
    sources = []
    for label, url in record.get("facts", {}).get("sources", {}).items():
        address = urlsplit(url)
        if address.scheme in ("https", "http") and address.netloc:
            sources.append(f'<li><a href="{text(url)}" rel="noreferrer">{text(label)}</a></li>')
    command = "python -m damage_lab --package ПАКЕТ "
    if condition.get("observations_provided", True):
        command += "--observations ПОКАЗАТЕЛИ.json "
    command += ("--facts ФАКТЫ.json --output НОВАЯ_ПАПКА "
               f"--basis {condition['basis']} --active {condition['active']} --hits {condition['hits']} "
               f"--retention {decimal(condition['retention'])} --resistance {decimal(condition['resistance'])} "
               f"--taken {decimal(condition['taken'])} --uptime {decimal(condition['uptime'])}")
    if condition["basis"] == "hit":
        command += (" --lucky" if condition["lucky"] else " --no-lucky")
        command += f" --critical-more {decimal(condition['critical_more'])}"
    if "native_stats" in record:
        command += " --native-stats АВТОМАТИЧЕСКИЕ_СТАТЫ.json"
    if "panel_log" in record:
        command += (" --game-log ИГРОВОЙ_ЖУРНАЛ.log" if record["panel_log"].get("input_kind") == "game_log"
                    else " --panel-log ПАНЕЛЬ_СТАТОВ.json")
    combat = ""
    if "combat" in condition:
        command += " --combat combat.json"
        combat = ("<h3>Боевой контекст</h3><p>Исходное состояние относится к панели, целевое — к бою; "
                  "расчёт использует отношение их множителей<br>JSON сохранён рядом с отчётом как combat.json</p>"
                  f"<details><summary>Показать входные данные</summary><pre>"
                  f"{text(json.dumps(condition['combat'], ensure_ascii=False, indent=2))}</pre></details>")
    validation = ""
    if "average_dps" in benchmark:
        comparison = compare(calculation["dps"], benchmark["average_dps"])
        error = (f"{comparison['relative_error']:+.2%}" if comparison["relative_error"] is not None
                 else "не определено при нулевом замере")
        ratio = (decimal(comparison["measured_to_predicted"]) if comparison["measured_to_predicted"] is not None
                 else "не определено при нулевом расчёте")
        validation = (f"<p>Отклонение расчёта от контрольного замера: <b>{text(error)}</b><br>"
                      f"Отношение замера к расчёту: {text(ratio)}</p>"
                      "<p>Это диагностика расхождения; отношение не применяется к урону<br>"
                      "Совпадение чисел само по себе не доказывает полноту модели</p>")
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
<table><tbody>{conditions}</tbody></table>{combat}</section>
<section><h2>Математика сценария</h2><table><thead><tr><th>Величина или множитель</th><th>Значение</th></tr></thead>
<tbody>{trace}<tr><td><b>Условный итог</b></td><td><b>{number(calculation['dps'])} DPS</b></td></tr></tbody></table>
{items(calculation.get('assumptions', []))}{validation}</section>
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
{logdetails(record)}
<section><h2>Состав билда</h2>{inventory}</section>
{rankdetails(record)}
{importdetails(record)}
{resolutiondetails(record)}
{staticdetails(record)}
{installeddetails(record)}
{supportdetails(record)}
<section><h2>Повторить расчёт локально</h2><p>Каждый запуск создаёт новый каталог с SQLite, JSON и этим отчётом
Путь к существующему каталогу отклоняется</p><pre>{text(command)}</pre></section>
<section><h2>Источники правил</h2><ul>{''.join(sources)}</ul>
<p class=muted>Дата проверки базы: {text(record.get('facts', {}).get('checkedAt', 'не указана'))}</p></section>
<footer>SHA-256 исходного снимка: {text(record.get('source_sha256', 'не указан'))}<br>
Отчёт содержит выбранные факты и наблюдения; исходные native sections и идентификаторы аккаунта сюда не включаются</footer>
</main></body></html>"""
