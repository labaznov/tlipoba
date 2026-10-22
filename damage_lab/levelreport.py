"""Render passive level-grant diagnostics without deriving levels or damage."""

from html import escape
import json


def _text(value):
    return escape(str(value), quote=True)


def _known(value):
    return "неизвестно" if value is None else _text(value)


def _exact(value):
    return ("<p>неизвестно</p>" if value is None else "<div class=scroll><pre>"
            + _text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)) + "</pre></div>")


def _table(rows, headers):
    return ("<div class=scroll><table><thead><tr>" + "".join("<th>" + _text(value) + "</th>" for value in headers)
            + "</tr></thead><tbody>" + "".join("<tr>" + "".join("<td>" + value + "</td>" for value in row)
                                               + "</tr>" for row in rows) + "</tbody></table></div>")


def _candidates(ledger):
    groups = ("Собственные роллы предметов", "Таланты: вычисленная привязка", "Каталожные литералы")
    rows = {name: [] for name in groups}
    for candidate in ledger["candidates"]:
        group = (groups[0] if candidate["domain"] == "gear" else groups[1]
                 if candidate["domain"] == "talent" and candidate["binding"]["status"] == "computed" else groups[2])
        amount = candidate["amount"]
        detail = {key: candidate[key] for key in ("binding", "eligibility", "rank", "native_id", "slot", "area", "installation")
                  if key in candidate}
        rows[group].append((
            _text(candidate["domain"]), _text(candidate["template"]),
            _known(None if amount is None else amount["exact"]),
            _known(None if amount is None else amount["origin"]) + "<br>" + _known(None if amount is None else amount["source"]),
            "<code>" + _text(candidate["path"]) + "</code>",
            "<details><summary>Привязка, scope и rank</summary>" + _exact(detail) + "</details>"))
    return "".join("<h4>" + _text(name) + "</h4>" + (
        _table(rows[name], ("Домен", "Полный шаблон", "Точное amount", "Происхождение", "Путь", "Evidence"))
        if rows[name] else "<p>Кандидатов этой категории не получено; полнота не подтверждена</p>") for name in groups)


def _target(ledger):
    target = ledger["target"]
    gem = target["gem_level"]
    rows = [(_text(label), _known(value)) for label, value in (
        ("Публичный skill ID", target["skill_id"]), ("Статус цели", target["status"]),
        ("Путь наблюдения", target["path"]), ("Наблюдаемый gem level", None if gem is None else gem["value"]),
        ("Статус gem level", None if gem is None else gem["status"]), ("Effective level", ledger["effective_level"]),
        ("Статус каталога", target["catalog"]["status"]), ("Каталожная категория", target["catalog"]["category"]))]
    ambiguity = ("<p>Одинаковый ID установлен несколько раз; экземпляр и уровень не выбраны</p>"
                 if target["status"] == "ambiguous_installation" else "")
    domains = [(_text(name), _text(value["status"]), _known(value["observed"]), _known(value["bound"]),
                 _known(value["bound_level_candidates"]), _text(value["candidate_coverage"]))
               for name, value in ledger["domains"].items()]
    gaps = [(_text(row["domain"]), _known(row["path"]), _text(row["reason"])) for row in ledger["gaps"]]
    return ("<article><h3>Цель " + _text(target["skill_id"]) + "</h3>" + ambiguity
            + _table(rows, ("Наблюдение", "Значение"))
            + "<p>Вычисленная привязка таланта не является native ID. Eligibility остаётся unverified; "
            "совпадение слов с tags не доказывает применимость. Amount неизвестного rank не заменяется нулём.</p>"
            + "<details><summary>Каталог и SkillItemLevel: семантика неизвестна</summary>"
            + _exact({"catalog": target["catalog"], "skill_item_level": target["skill_item_level"]}) + "</details>"
            + _candidates(ledger) + "<h4>Покрытие доменов</h4>"
            + _table(domains, ("Домен", "Статус", "Наблюдается", "Привязано", "Кандидатов", "Coverage"))
            + "<details><summary>Подробные счётчики и ограничения</summary>" + _exact(ledger["domains"])
            + _exact(ledger["limitations"]) + "</details><h4>Gaps цели</h4>"
            + (_table(gaps, ("Домен", "Путь", "Причина")) if gaps else
               "<p>Диагностических gaps нет; полнота импорта не подтверждена</p>") + "</article>")


def _provenance(data):
    catalog = data["catalog"]
    auxiliary = [(_text(name), _text(value["status"]), _known(value["sha256"]), _known(value["bytes"]))
                 for name, value in data["auxiliary"].items()]
    documents = [{key: row[key] for key in ("role", "domain", "logical_path", "address", "cache_file", "wrapper_sha256",
                                           "byte_range", "member_sha256", "encoding")} for row in catalog["documents"]]
    mappings = [{key: row[key] for key in ("file", "sha256", "bytes")} for row in catalog["mapping_files"]]
    return ("<h3>Заявленное происхождение каталогов и auxiliary</h3><p>Статус каталога: " + _text(catalog["status"])
            + "; derivation: " + _text(catalog["derivation"]) + "<br>network_bytes_verified: "
            + _text(json.dumps(catalog["network_bytes_verified"])) + "; current_patch_verified: "
            + _text(json.dumps(catalog["current_patch_verified"])) + "</p>"
            "<p>SHA wrapper относится к полным сохранённым bytes, SHA member — к точному byte range. "
            "Эти заявления producer здесь не перечитывают cache и не подтверждают сеть или текущий patch. "
            "Auxiliary переданы явно; hashed bridge не подтверждает runtime или активацию.</p>"
            + _table(auxiliary, ("Auxiliary", "Статус", "SHA-256", "Bytes"))
            + "<details><summary>Mapping files и точные member slices</summary>" + _exact(mappings)
            + _exact(documents) + "</details>")


def section(bundle, installation):
    """Revalidate a canonical bundle and show only unchanged diagnostic candidates."""
    try:
        from .levelbundle import summary

        data = summary(bundle, installation)
        if json.dumps(bundle, sort_keys=True, allow_nan=False) != json.dumps(data, sort_keys=True, allow_nan=False):
            raise ValueError
    except (ValueError, KeyError, TypeError, AttributeError, OverflowError, RecursionError):
        raise ValueError("Level report requires an unchanged canonical diagnostic bundle") from None
    flags = "; ".join(name + ": " + json.dumps(data[name]) for name in (
        "arithmetic_ready", "runtime_verified", "identity_verified", "import_complete"))
    selection = data["selection"]
    counts = [(_text(name), _known(value)) for name, value in data["accounting"].items()]
    targets = ("<p>Состав целей неизвестен; это не пустой список</p>" if data["targets"] is None else
               "<p>Допустимых наблюдаемых skill IDs нет; неизвестные IDs не заменены соседними</p>" if not data["requested_ids"] else
               "".join(_target(data["targets"][str(identity)]) for identity in data["requested_ids"]))
    return ("<section><h2>Кандидаты прибавок к уровню навыков</h2>"
            "<div class=notice>Effective level: неизвестно<br>Кандидаты не складываются<br>DPS не рассчитан</div>"
            "<p>" + _text(flags) + "<br>SHA-256 source.json: <code>" + _text(data["source"]["sha256"])
            + "</code><br>Resolver: " + _text(data["resolver_format"]) + " / " + _text(data["resolver_version"]) + "</p>"
            "<h3>Явно наблюдаемые ID</h3><p>Policy: " + _text(selection["policy"]) + "<br>Client layer: "
            + _text(selection["client_layer"]) + "<br>Наблюдаемых members: " + _known(selection["observed_members"])
            + "<br>Невалидных skill IDs: " + _known(selection["invalid_skill_ids"]) + "</p>"
            + _exact(data["requested_ids"]) + _table(counts, ("Счётчик", "Значение")) + targets
            + _provenance(data) + "<p>Установка, scope, rank и каталог не подтверждают текущую активацию. "
            "Ни уровень камня, ни SkillItemLevel не подставляются как effective level.</p></section>")
