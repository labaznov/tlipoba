"""Offline Help with compact winning-review cards and complete searchable review history."""

import argparse
from datetime import datetime
import json
from pathlib import Path
import re
import sys
from urllib.parse import urlsplit


STATUSES = ("index_discovered", "blocked", "body_reviewed")
CLASSIFICATIONS = ("game-help-text-mirror", "unofficial-game-help-datamine-mirror")


def _object(value, fields):
    if type(value) is not dict or not set(fields).issubset(value):
        raise ValueError("Help requires a JSON object with all contract fields")


def _list(value):
    if type(value) is not list:
        raise ValueError("Help requires JSON lists")
    return value


def _text(value, empty=False):
    if type(value) is not str or (not empty and not value.strip()):
        raise ValueError("Help text fields must contain text")
    return value


def _texts(value):
    return [_text(row) for row in _list(value)]


def _count(value):
    if type(value) is not int or value < 0:
        raise ValueError("Help counts and positions must be nonnegative integers")
    return value


def _date(value, nullable=False):
    if value is None and nullable:
        return None
    try:
        datetime.fromisoformat(_text(value).replace("Z", "+00:00"))
    except ValueError:
        raise ValueError("Help dates must use ISO format") from None
    return value


def _url(value):
    parts = urlsplit(_text(value))
    if (parts.scheme != "https" or parts.netloc != "tlidb.com" or not parts.path.startswith("/en/")
            or parts.path == "/en/" or parts.query or parts.fragment or any(char.isspace() for char in value)):
        raise ValueError("Help URLs must be English TLIDB HTTPS article URLs")
    return value


def _formula(row):
    _object(row, ("expression", "domain", "assumptions", "status"))
    if _text(row["status"]) not in ("documented", "derived", "unresolved"):
        raise ValueError("Unknown Help formula status")
    return {"expression": _text(row["expression"]), "domain": _text(row["domain"]),
            "assumptions": _texts(row["assumptions"]), "status": row["status"]}


def _data(row, classification, review=False):
    _object(row, ("url", "title", "status", "checkedAt", "findings", "unknowns"))
    if review:
        _object(row, ("summary", "formulas"))
    status = _text(row["status"])
    if status not in (STATUSES[1:] if review else STATUSES):
        raise ValueError("Unknown Help review status")
    classification = _text(row.get("sourceClassification", classification))
    if classification not in CLASSIFICATIONS:
        raise ValueError("Help articles must retain their unofficial mirror classification")
    result = {"url": _url(row["url"]), "title": _text(row["title"]), "status": status,
              "checkedAt": _date(row["checkedAt"], nullable=status == "index_discovered"),
              "sourceClassification": classification,
              "summary": _text(row.get("summary", ""), empty=status == "index_discovered"),
              "findings": _texts(row["findings"]), "unknowns": _texts(row["unknowns"]),
              "formulas": [_formula(value) for value in _list(row.get("formulas", []))]}
    for key in ("indexDiscoveredAt", "bodyReviewedAt"):
        if key in row:
            result[key] = _date(row[key])
    if "reviewScope" in row:
        result["reviewScope"] = _text(row["reviewScope"])
    if "reviewSections" in row:
        result["reviewSections"] = _texts(row["reviewSections"])
    if "sourceSha256" in row:
        if not re.fullmatch("[0-9a-f]{64}", _text(row["sourceSha256"])):
            raise ValueError("Help source hash must be a lowercase SHA256")
        result["sourceSha256"] = row["sourceSha256"]
    return result


def _review(row, classification, origin, stamp):
    result = _data(row, classification, review=True)
    if _text(origin) not in ("index", "review_chunk"):
        raise ValueError("Unknown Help review origin")
    result.update(origin=origin, chunkCheckedAt=_date(stamp, nullable=origin == "index"))
    return result


def _unique(rows):
    values = {json.dumps(row, sort_keys=True, ensure_ascii=False): row for row in rows}
    return [values[key] for key in sorted(values)]


def _index(index):
    _object(index, ("format", "patch", "checkedAt", "sourceClassification", "index", "articles"))
    if index["format"] != "tli-help-index-v1" or index["sourceClassification"] not in CLASSIFICATIONS:
        raise ValueError("Help index must identify the unofficial mirror format")
    _date(index["checkedAt"])
    _text(index["patch"])
    metadata = index["index"]
    _object(metadata, ("url", "advertisedCounts", "actualCounts", "entryCount", "uniqueCount"))
    _url(metadata["url"])
    _object(metadata["actualCounts"], ())
    counts = {_text(section): 0 for section in metadata["actualCounts"]}
    positions = set()
    urls = set()
    articles = []
    for article in _list(index["articles"]):
        _object(article, ("url", "title", "categories", "memberships", "status", "checkedAt",
                          "sourceClassification", "findings", "unknowns"))
        result = _data(article, article["sourceClassification"])
        if result["url"] in urls:
            raise ValueError("Help index article URLs must be unique")
        urls.add(result["url"])
        sections = set()
        for membership in _list(article["memberships"]):
            _object(membership, ("section", "position", "title"))
            section = _text(membership["section"])
            position = _count(membership["position"])
            _text(membership["title"])
            if not position or (section, position) in positions:
                raise ValueError("Help section positions must be positive and unique")
            positions.add((section, position))
            counts[section] = counts.get(section, 0) + 1
            sections.add(section)
        categories = _texts(article["categories"])
        if not sections or set(categories) != sections or len(set(categories)) != len(categories):
            raise ValueError("Help categories must match their nonempty memberships")
        result.update(categories=list(categories), memberships=[
            {key: row[key] for key in ("section", "position", "title")} for row in article["memberships"]])
        if "reviewHistory" in article:
            result["reviewHistory"] = []
            for row in _list(article["reviewHistory"]):
                _object(row, ("origin", "chunkCheckedAt"))
                review = _review(row, result["sourceClassification"], row["origin"], row["chunkCheckedAt"])
                if review["url"] != result["url"]:
                    raise ValueError("Saved Help review URL differs from its article")
                result["reviewHistory"].append(review)
            if (result["reviewHistory"] and result["status"] != max(
                    result["reviewHistory"], key=lambda row: STATUSES.index(row["status"]))["status"]):
                raise ValueError("Saved Help history status differs from its article claim")
        articles.append(result)
    for key in ("advertisedCounts", "actualCounts"):
        _object(metadata[key], counts)
        if {key: _count(value) for key, value in metadata[key].items()} != counts:
            raise ValueError("Help declared section counts differ from actual memberships")
    if (_count(metadata["entryCount"]) != len(positions) or _count(metadata["uniqueCount"]) != len(urls)
            or positions != {(section, position) for section, count in counts.items() for position in range(1, count + 1)}):
        raise ValueError("Help totals or contiguous section positions differ from memberships")
    result = {key: metadata[key] for key in ("url", "entryCount", "uniqueCount")}
    result.update({key: dict(metadata[key]) for key in ("advertisedCounts", "actualCounts")})
    if "verifiedAt" in metadata:
        result["verifiedAt"] = _date(metadata["verifiedAt"])
    if "categoryBasis" in metadata:
        result["categoryBasis"] = _text(metadata["categoryBasis"])
    result = {"format": index["format"], "patch": index["patch"], "checkedAt": index["checkedAt"],
              "sourceClassification": index["sourceClassification"], "index": result, "articles": articles}
    if "versionScope" in index:
        result["versionScope"] = _text(index["versionScope"])
    if "limits" in index:
        result["limits"] = _texts(index["limits"])
    return result


def _aggregate(article, reviews):
    """Keep one complete summary/findings card; preserve alternate evidence without truncation."""
    history = sorted(_unique(reviews), key=lambda row: json.dumps(row, sort_keys=True, ensure_ascii=False))
    if not history:
        return article
    winner = max(history, key=lambda row: STATUSES.index(row["status"]))
    for key in ("status", "checkedAt", "summary", "sourceClassification"):
        article[key] = winner[key]
    article["findings"] = list(winner["findings"])
    for key in ("bodyReviewedAt", "reviewScope", "reviewSections", "sourceSha256"):
        article.pop(key, None)
        if key in winner:
            article[key] = winner[key]
    for key in ("unknowns", "formulas"):
        article[key] = _unique([*article[key], *[value for row in history for value in row[key]]])
    article["reviewHistory"] = history
    article["reviewConflicts"] = [key for key in ("status", "title", "summary")
                                  if len({row[key] for row in history} | ({article["title"]} if key == "title" else set())) > 1]
    if len({tuple(row["findings"]) for row in history}) > 1:
        article["reviewConflicts"].append("findings")
    expressions = {row["expression"] for row in article["formulas"]}
    article["reviewConflicts"].extend("formula:" + expression for expression in sorted(expressions)
                                    if sum(row["expression"] == expression for row in article["formulas"]) > 1)
    return article


def merge(index, chunks):
    """Combine review records without treating index discovery as body review."""
    result = _index(index)
    articles = {row["url"]: row for row in result["articles"]}
    reviews = {}
    for url, article in articles.items():
        reviews[url] = article.pop("reviewHistory", [])
        if not reviews[url] and article["status"] != "index_discovered":
            reviews[url].append(_review(article, article["sourceClassification"], "index", None))
    for chunk in _list(chunks):
        _object(chunk, ("format", "checkedAt", "articles"))
        if chunk["format"] != "tli-help-review-chunk-v1":
            raise ValueError("Unknown Help review chunk format")
        _date(chunk["checkedAt"])
        for review in _list(chunk["articles"]):
            _object(review, ("url",))
            url = _url(review["url"])
            if url not in articles:
                raise ValueError("Help review URL is absent from the index")
            reviews[url].append(_review(review, result["sourceClassification"], "review_chunk", chunk["checkedAt"]))
    result["articles"] = [_aggregate(article, reviews[url]) for url, article in articles.items()]
    coverage = {"uniqueCount": len(articles), "entryCount": result["index"]["entryCount"],
                "byStatus": {status: sum(row["status"] == status for row in result["articles"]) for status in STATUSES},
                "bySection": {}}
    for section, count in result["index"]["actualCounts"].items():
        coverage["bySection"][section] = {"entryCount": count, "byStatus": {
            status: sum(row["status"] == status for row in result["articles"] for membership in row["memberships"]
                        if membership["section"] == section) for status in STATUSES}}
    result["reviewCoverage"] = coverage
    return result


def search(index, query):
    """Search compact cards, complete review summaries/findings and unioned formula text."""
    query = _text(query).strip().casefold()
    articles = merge(index, [])["articles"]
    return [row for row in articles if query in " ".join([
        row["title"], row["url"], row["summary"], *row["findings"],
        *[review["summary"] for review in row.get("reviewHistory", [])],
        *[finding for review in row.get("reviewHistory", []) for finding in review["findings"]],
        *[" ".join([formula["expression"], formula["domain"], *formula["assumptions"]])
          for formula in row["formulas"]]]).casefold()]


def main(argv=None):
    """Search or merge saved Help data without retrieving URLs or evaluating formulas."""
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    lookup = commands.add_parser("search", help="Search literal text in the offline Help library")
    lookup.add_argument("query")
    lookup.add_argument("--index", type=Path, default=Path(__file__).with_name("data") / "help-index-ss14.json")
    combine = commands.add_parser("merge", help="Merge review evidence into a new index file")
    combine.add_argument("--index", type=Path, required=True)
    combine.add_argument("--review", type=Path, action="append", required=True)
    combine.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        document = json.loads(args.index.read_text(encoding="utf-8"))
        if args.command == "search":
            print(json.dumps(search(document, args.query), ensure_ascii=False, indent=2, allow_nan=False))
        else:
            result = merge(document, [json.loads(path.read_text(encoding="utf-8")) for path in args.review])
            serialized = json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
            with args.output.open("x", encoding="utf-8") as handle:
                handle.write(serialized)
            print(json.dumps({"reviewCoverage": result["reviewCoverage"]}))
        return 0
    except (OSError, ValueError) as error:
        print(f"helpbook: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
