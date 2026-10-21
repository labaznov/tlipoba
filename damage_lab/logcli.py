"""Save separate character-state projections from an ordinary local game log."""

import argparse
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
        'summary{cursor:pointer}section{border-top:1px solid #475569;margin-top:2rem}code{overflow-wrap:anywhere}</style>',
        '<h1>Состав из напечатанных таблиц журнала</h1>',
        '<p>События не объединены. Идентичность персонажа, код билда, свежесть и действие эффектов не подтверждены.</p>',
        '<p>Complete означает полноту напечатанного поддерева, а не полный импорт персонажа. DPS не рассчитывается.</p>',
        f'<p>SHA256 снимка: <code>{_text(data["source"]["sha256"])}</code></p>',
        f'<p>Прочитано байт: {_text(data["source"]["bytes_read"])}; таблиц: {_text(data["acquisition"]["parsed_events"])}; ',
        f'отклонено таблиц: {_text(data["acquisition"]["rejected_events"])}</p>']
    for gap in data["gaps"]:
        parts.append(f'<p>{_text(gap)}</p>')
    for event in data["events"]:
        context = event["event"]
        parts.extend([f'<section><h2>Событие {_text(context["index"])}</h2>',
                      f'<p>Строки {_text(context["start_line"])}–{_text(context["end_line"])}</p>'])
        for name, domain in event["domains"].items():
            parts.extend([f'<h3>{_text(name)}: {_text(domain["status"])}</h3>',
                          f'<p>Видимых записей: {_text(domain["visible_entries"])}; общее число неизвестно</p>'])
            for gap in domain["gaps"]:
                parts.append(f'<p>{_text(gap)}</p>')
            for row in domain["rows"]:
                parts.append(f'<details><summary>{_text(row["alias"])}</summary><pre>{_json(row)}</pre></details>')
        parts.append('</section>')
    return "\n".join(parts) + "\n</html>\n"


def parser():
    interface = argparse.ArgumentParser(description="Отдельные состояния персонажа из обычного журнала TLI")
    interface.add_argument("--game-log", required=True, type=Path, help="Обычный локальный UE_game.log")
    interface.add_argument("--output", required=True, type=Path, help="Новый каталог результата")
    interface.add_argument("--event", type=int, help="Необязательный индекс одного подходящего события; по умолчанию все отдельно")
    return interface


def main(argv=None, *, reader=None, builder=None):
    """Write diagnostics atomically without native trees, state merging or game access."""
    arguments = parser().parse_args(argv)
    try:
        if arguments.output.exists():
            raise FileExistsError("Output already exists")
        if reader is None:
            from .buildlog import snapshot
            reader = snapshot
        if builder is None:
            from . import logbuild
            builder = logbuild
        snapshot = reader(arguments.game_log)
        source = snapshot["source"]
        candidates = builder.candidates(snapshot, source["sha256"])
        selected = list(candidates) if arguments.event is None else [arguments.event]
        if any(index not in candidates for index in selected):
            raise ValueError("Selected event does not match the supported character-state structure")
        events = [builder.project(snapshot, index, source["sha256"]) for index in selected]
        data = {
            "format": "tli-log-import-v1", "version": "0.1.0", "status": "diagnostic", "scope": "separate_printed_events",
            "import_complete": False, "identity": "unknown", "runtime": "unknown", "freshness": "unknown",
            "selected_skill": "unknown", "build_code": "unknown",
            "source": {"kind": "ordinary_log", "path": str(arguments.game_log.resolve()), "sha256": source["sha256"],
                       "snapshot_bytes": source["snapshotBytes"], "bytes_read": source["bytesRead"], "lines": source["lines"]},
            "selection": {"mode": "all_candidates" if arguments.event is None else "explicit_event",
                          "candidates": candidates, "selected": selected, "merged": False},
            "acquisition": {"parsed_events": len(snapshot["events"]), "rejected_events": len(snapshot["rejected"]),
                            "ignored_lines": source["ignoredLines"], "oversized_lines": source["oversizedLines"],
                            "incomplete_final_line": source["incompleteFinalLine"]},
            "events": events,
            "gaps": (["В снимке нет таблиц поддерживаемой структуры; отсутствие билда этим не установлено"]
                     if not candidates else [])}
        raw = json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
        page = render(data)
        arguments.output.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix=".tli-log-", dir=arguments.output.parent) as directory:
            stage = Path(directory)
            (stage / "log-import.json").write_text(raw, encoding="utf-8")
            (stage / "index.html").write_text(page, encoding="utf-8")
            if arguments.output.exists():
                raise FileExistsError("Output already exists")
            stage.rename(arguments.output)
    except (OSError, ValueError, TypeError, KeyError, RecursionError):
        print("Ошибка импорта журнала: файл или выбранное событие не соответствуют поддерживаемому контракту либо каталог результата недоступен", file=sys.stderr)
        return 1
    print(f"Диагностика журнала сохранена: {arguments.output}; событий: {len(events)}; полный импорт не подтверждён")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
