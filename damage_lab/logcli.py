"""Save separate character-state projections from an ordinary local game log."""

import argparse
import hashlib
import html
import json
import sys
import tempfile
from pathlib import Path


def _text(value):
    return html.escape(str(value), quote=True)


def _json(value):
    return _text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False))


def render(data):
    """Show printed-subtree coverage and lexical values without active page content."""
    parts = [
        '<!doctype html><html lang="ru"><meta charset="utf-8"><meta name="viewport" content="width=device-width">',
        '<title>Диагностика импорта журнала TLI</title>',
        '<style>body{font:16px system-ui;max-width:1100px;margin:2rem auto;padding:0 1rem;background:#111827;color:#e5e7eb}',
        'pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#1f2937;padding:1rem}details{margin:.5rem 0}',
        'summary{cursor:pointer}section{border-top:1px solid #475569;margin-top:2rem}code{overflow-wrap:anywhere}',
        'table{border-collapse:collapse;width:100%}th,td{border:1px solid #475569;padding:.5rem;text-align:left;vertical-align:top}</style>',
        '<h1>Состав из напечатанных таблиц журнала</h1>',
        '<p>События не объединены. Идентичность персонажа, код билда, свежесть и действие эффектов не подтверждены.</p>',
        '<p>Complete домена означает полноту напечатанного поддерева, а не полный импорт персонажа. DPS не рассчитывается.</p>',
        f'<p>SHA256 снимка: <code>{_text(data["source"]["sha256"])}</code></p>',
        f'<p>Прочитано байт: {_text(data["source"]["bytes_read"])}; таблиц: {_text(data["acquisition"]["parsed_events"])}; ',
        f'отклонено таблиц: {_text(data["acquisition"]["rejected_events"])}</p>']
    for gap in data["gaps"]:
        parts.append(f'<p>{_text(gap)}</p>')
    if data.get("skill_catalog_source") is not None:
        parts.extend(['<h2>Сохранённый каталог навыков</h2>',
                      f'<pre>{_json(data["skill_catalog_source"])}</pre>',
                      '<p>Хеш локального файла не подтверждает актуальную версию игры или персонажа.</p>'])
    if "context" in data:
        parts.extend(['<p>Complete контекста означает сохранение запрошенных окон строк, включая отклонённые деревья; это не полнота разбора или импорта.</p>',
                      f'<p>Контекст сохранён локально: {_text(data["context"]["status"])}; '
                      f'строк: {_text(data["context"]["retained_lines"])}; '
                      f'пропусков: {_text(data["context"]["omitted_lines"] + data["context"]["unretained_lines"])}</p>'])
    for partial, event in ([(False, event) for event in data["events"]] +
                           [(True, event) for event in data.get("partial_events", [])]):
        context = event["event"]
        label = "Частично напечатанное состояние" if partial else "Событие"
        parts.extend([f'<section><h2>{label} {_text(context["index"])}</h2>',
                      f'<p>Строки {_text(context["start_line"])}–{_text(context["end_line"])}</p>'])
        if "message" in context:
            parts.extend(['<p>Источник сообщения:</p>', f'<pre>{_json(context["message"])}</pre>'])
        if partial:
            parts.extend(['<p>bag elided: экипировка неизвестна, а не пуста</p>',
                          f'<pre>{_json(event["structure"])}</pre>'])
        if "skill_catalog" in event:
            parts.extend(_catalog(event["skill_catalog"]))
        for name, domain in event["domains"].items():
            parts.extend([f'<h3>{_text(name)}: {_text(domain["status"])}</h3>',
                          f'<p>Видимых записей: {_text(domain["visible_entries"] if domain["visible_entries"] is not None else "—")}; общее число неизвестно</p>'])
            for gap in domain["gaps"]:
                parts.append(f'<p>{_text(gap)}</p>')
            for row in domain["rows"]:
                parts.append(f'<details id="event-{_text(context["index"])}-{_text(row["alias"])}">'
                             f'<summary>{_text(row["alias"])}</summary><pre>{_json(row)}</pre></details>')
        references = event["skill_references"]
        parts.extend(['<h3>Ссылки навыков: напечатанные значения одного события</h3>',
                      '<p>Совпадение токенов не подтверждает установку, активацию, выбранную связку или эффективный уровень.</p>',
                      f'<pre>{_json({key: references[key] for key in ("layout_side", "items_side", "format", "evidence", "installation", "activation", "effective_level", "inventory_completeness", "coordinate_binding", "record_binding", "counts")})}</pre>',
                      '<table><tr><th>Слот</th><th>Статус</th><th>Строка камня</th><th>Однозначность</th>'
                      '<th>Видимых совпадений</th><th>Пути</th></tr>'])
        for reference in references["references"]:
            target = (f'<a href="#event-{_text(context["index"])}-{_text(reference["skill_items_alias"])}">'
                      f'{_text(reference["skill_items_alias"])}</a>' if reference["skill_items_alias"] is not None else '—')
            paths = {key: reference[key] for key in ("layout_path", "reference_path", "skill_items_path")}
            parts.append(f'<tr><td>{_text(reference["layout_alias"])}</td><td>{_text(reference["status"])}</td>'
                         f'<td>{target}</td><td>{_text(reference["uniqueness"] if reference["uniqueness"] is not None else "—")}</td>'
                         f'<td>{_text(reference["visible_match_count"] if reference["visible_match_count"] is not None else "—")}</td>'
                         f'<td><details><summary>Пути</summary><pre>{_json(paths)}</pre></details></td></tr>')
        parts.append('</table>')
        if "installation_graph" in event:
            parts.extend(_installation(event["installation_graph"], context["index"]))
        else:
            parts.append('<p>Кандидаты позиций недоступны в этом отчёте</p>')
        parts.append('</section>')
    return "\n".join(parts) + "\n</html>\n"


def _catalog(catalog):
    parts = ['<h3>Кандидаты каталога навыков</h3>',
             '<p>Наблюдаемые уровни не выбирают gem level или effective level; активация и установка неизвестны.</p>',
             '<table><tr><th>Строка</th><th>GUID</th><th>Категория</th><th>Статус</th><th>Пробел</th><th>Уровень</th></tr>']
    for row in catalog["rows"]:
        identity = row["identity"]
        parts.append(f'<tr><td>{_text(row["alias"])}</td>'
                     f'<td>{_text(identity["guid"] if identity else "—")}</td>'
                     f'<td>{_text(identity["category"] if identity else "—")}</td>'
                     f'<td>{_text(row["status"])}</td><td>{_text(row["reason"] if row["reason"] else "—")}</td>'
                     '<td>неизвестен</td></tr>')
    parts.append('</table>')
    return parts


def _installation(graph, index):
    parts = ['<h3>Условные позиции навыков</h3>',
             '<p>Кандидаты по сохранённому коду и предполагаемым константам; роли, установка, активация и уровни не подтверждены.</p>',
             f'<details><summary>Допущения</summary><pre>{_json(graph["derivation"])}</pre></details>',
             '<table><tr><th>Слот</th><th>Кандидат вкладки</th><th>Кандидат позиции</th><th>Статус ключа</th></tr>']
    for slot in graph["slots"]:
        parts.append(f'<tr><td><a href="#event-{_text(index)}-{_text(slot["layout_alias"])}">{_text(slot["layout_alias"])}</a></td>'
                     f'<td>{_text(slot["tab_candidate"] if slot["tab_candidate"] is not None else "—")}</td>'
                     f'<td>{_text(slot["position_candidate"] if slot["position_candidate"] is not None else "—")}</td>'
                     f'<td>{_text(slot["slot_key_status"])}</td></tr>')
    parts.extend(['</table>', '<details><summary>Группы и видимые коллизии; победитель неизвестен</summary>',
                  f'<pre>{_json(graph["tabs"])}</pre></details>'])
    return parts


def parser():
    interface = argparse.ArgumentParser(description="Отдельные состояния персонажа из обычного журнала TLI")
    interface.add_argument("--game-log", required=True, type=Path, help="Обычный локальный UE_game.log")
    interface.add_argument("--output", required=True, type=Path, help="Новый каталог результата")
    interface.add_argument("--event", type=int, help="Необязательный индекс одного подходящего события; по умолчанию все отдельно")
    interface.add_argument("--context", action="store_true", help="Сохранить ограниченный приватный контекст всех напечатанных событий")
    interface.add_argument("--skill-catalog", type=Path, help="Явный сохранённый каталог для отдельных напечатанных навыков")
    return interface


def main(argv=None, *, reader=None, builder=None):
    """Write diagnostics atomically without native trees, state merging or game access."""
    arguments = parser().parse_args(argv)
    try:
        if arguments.output.exists():
            raise FileExistsError("Output already exists")
        catalog_source = None
        if arguments.skill_catalog is not None:
            from . import logcatalog
            from .logcatalogfile import read

            records, catalog, catalog_source = read(arguments.skill_catalog)
        if reader is None:
            from .buildlog import snapshot
            reader = snapshot
        if builder is None:
            from . import logbuild
            builder = logbuild
        snapshot = reader(arguments.game_log)
        source = snapshot["source"]
        candidates = builder.candidates(snapshot, source["sha256"])
        partials = builder.partial_candidates(snapshot, source["sha256"])
        selected = list(candidates) if arguments.event is None else [arguments.event]
        if any(index not in candidates for index in selected):
            raise ValueError("Selected event does not match the supported character-state structure")
        events = []
        for index in selected:
            graph = builder.installation_graph(snapshot, index, source["sha256"])
            events.append({**builder.project(snapshot, index, source["sha256"]),
                           "skill_references": graph["skill_references"], "installation_graph": graph})
        partial_selected = partials if arguments.event is None else []
        partial_events = []
        for index in partial_selected:
            graph = builder.partial_installation_graph(snapshot, index, source["sha256"])
            partial_events.append({**builder.project_partial(snapshot, index, source["sha256"]),
                                   "skill_references": graph["skill_references"], "installation_graph": graph})
        if catalog_source is not None:
            for event in events:
                event["skill_catalog"] = logcatalog.project(snapshot, event["event"]["index"],
                    source["sha256"], records, catalog)
            for event in partial_events:
                event["skill_catalog"] = logcatalog.project(snapshot, event["event"]["index"],
                    source["sha256"], records, catalog, partial=True)
        data = {
            "format": "tli-log-import-v1", "version": "0.3.1", "status": "diagnostic", "scope": "separate_printed_events",
            "skill_catalog_source": catalog_source,
            "import_complete": False, "identity": "unknown", "runtime": "unknown", "freshness": "unknown",
            "selected_skill": "unknown", "build_code": "unknown",
            "source": {"kind": "ordinary_log", "path": str(arguments.game_log.resolve()), "sha256": source["sha256"],
                       "snapshot_bytes": source["snapshotBytes"], "bytes_read": source["bytesRead"], "lines": source["lines"]},
            "selection": {"mode": "all_candidates" if arguments.event is None else "explicit_event",
                          "candidates": candidates, "selected": selected, "merged": False},
            "partial_selection": {"mode": "all_partial_shapes" if arguments.event is None else
                                  "not_requested_for_explicit_full_event", "candidates": partials,
                                  "selected": partial_selected, "merged": False},
            "acquisition": {"parsed_events": len(snapshot["events"]), "rejected_events": len(snapshot["rejected"]),
                            "ignored_lines": source["ignoredLines"], "oversized_lines": source["oversizedLines"],
                            "incomplete_final_line": source["incompleteFinalLine"]},
            "events": events,
            "partial_events": partial_events,
            "gaps": (["Строгие полные состояния не напечатаны; доступны отдельные частичные состояния с неизвестной экипировкой"
                      if partials else "В снимке нет таблиц поддерживаемой структуры; отсутствие билда этим не установлено"]
                     if not candidates else [])}
        packet = None
        if arguments.context:
            from .logcontext import collect, serialize
            context = collect(arguments.game_log, snapshot)
            packet = serialize(context)
            data["context"] = {"file": "log-context.json", "sha256": hashlib.sha256(packet).hexdigest(),
                               "bytes": len(packet), "status": context["status"],
                               "events": len(context["events"]), "omitted_events": context["omitted_events"],
                               "retained_lines": len(context["lines"]), "omitted_lines": context["omitted_lines"],
                               "unretained_lines": context["unretained_lines"]}
        raw = json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
        page = render(data)
        arguments.output.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix=".tli-log-", dir=arguments.output.parent) as directory:
            stage = Path(directory)
            (stage / "log-import.json").write_text(raw, encoding="utf-8")
            (stage / "index.html").write_text(page, encoding="utf-8")
            if packet is not None:
                (stage / "log-context.json").write_bytes(packet)
            if arguments.output.exists():
                raise FileExistsError("Output already exists")
            stage.rename(arguments.output)
    except (OSError, ValueError, TypeError, KeyError, RecursionError):
        print("Ошибка импорта журнала: файл или выбранное событие не соответствуют поддерживаемому контракту либо каталог результата недоступен", file=sys.stderr)
        return 1
    print(f"Диагностика журнала сохранена: {arguments.output}; строгих событий: {len(events)}; частичных: {len(partial_events)}; полный импорт не подтверждён")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
