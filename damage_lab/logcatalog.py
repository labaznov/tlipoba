"""Resolve declared catalog identities from printed skill rows without level inference."""

import copy
import re

from . import logbuild
from .skillprofile import GUID
from .supportcatalog import project as provenance

FORMAT = "tli-log-skill-catalog-candidates-v1"


def _records(records, catalog):
    if (type(records) is not dict or len(records) > catalog["records"]
            or sum(value is not None for value in records.values()) > catalog["skills"]):
        raise ValueError("Printed catalog candidates require a bounded declared record map")
    for key, record in records.items():
        if type(key) is not str or re.fullmatch(r"[1-9][0-9]*", key, re.ASCII) is None:
            raise ValueError("Printed catalog record keys must be canonical positive decimal IDs")
        if record is None:
            continue
        if (type(record) is not dict or type(record.get("tlidbId")) is not int
                or str(record["tlidbId"]) != key):
            raise ValueError("Printed catalog records must match their exact integer IDs")
        category = record.get("category")
        if (type(category) is not str or category not in catalog["categories"]
                or catalog["categories"][category]["master"] != "present"):
            raise ValueError("Printed catalog records require a declared category master")
        if record["tlidbId"] in catalog["withheld_record_ids"]:
            raise ValueError("Printed catalog records cannot resolve withheld identities")
        if "catalogPath" in record and record["catalogPath"] != f"skill/{category}":
            raise ValueError("Printed catalog record paths must match their category")
        english = record.get("english")
        if english is not None and type(english) is not dict:
            raise ValueError("Printed catalog English records must be objects or absent")
        if english and catalog["categories"][category]["english"] != "present":
            raise ValueError("Printed catalog English payloads require a declared member")


def project(snapshot, event_index, source_sha256, records, catalog, *, partial=False):
    """Return source-distinct catalog candidates, never installed or level-specific skills."""
    if type(partial) is not bool:
        raise ValueError("Printed catalog selection requires an explicit boolean partial mode")
    projection = (logbuild.project_partial if partial else logbuild.project)(snapshot, event_index, source_sha256)
    catalog = provenance(catalog)
    _records(records, catalog)
    domain = projection["domains"]["skill_items"]
    rows = []
    for observed in domain["rows"]:
        fields = {name: copy.deepcopy(observed["fields"][name])
                  for name in ("base_id", "level", "skill_item_level")}
        field = fields["base_id"]
        identity, reason = None, "base_id_unavailable"
        if field["status"] == "complete" and len(field["values"]) == 1:
            scalar = field["values"][0]
            if scalar["class"] != "int" or re.fullmatch(r"[1-9][0-9]*", scalar["text"], re.ASCII) is None:
                reason = "base_id_noncanonical"
            else:
                record = records.get(scalar["text"])
                reason = ("withheld_identity" if scalar["text"] in
                          {str(identity) for identity in catalog["withheld_record_ids"]} else "catalog_record_missing")
                if record is not None:
                    guid = record.get("id")
                    reason = "catalog_guid_unavailable"
                    if type(guid) is str and GUID.fullmatch(guid):
                        identity = {"tlidb_id": record["tlidbId"], "guid": guid, "category": record["category"]}
                        reason = None
        rows.append({"alias": observed["alias"], "path": list(observed["path"]), "fields": fields,
                     "status": "catalog_identity" if identity is not None else "gap", "reason": reason,
                     "identity": identity, "profile": None, "gem_level": None, "effective_level": None,
                     "installation": "unknown", "activation": "unknown"})
    return {"format": FORMAT, "scope": "separate_printed_catalog_candidates", "source": projection["source"],
            "event": projection["event"], "catalog": catalog,
            "structure": projection.get("structure", {"kind": "strict_character_shape"}),
            "coverage": {key: copy.deepcopy(domain[key]) for key in
                         ("path", "status", "node_kind", "visible_entries", "total_entries", "gaps")},
            "rows": rows, "profile": None, "gem_level": None, "effective_level": None,
            "runtime": "unknown", "identity": "unknown", "activation": "unknown", "installation": "unknown",
            "freshness": "unknown", "selected_skill": "unknown", "build_code": "unknown",
            "import_complete": False, "arithmetic_ready": False, "level_specific_lookup": False,
            "counts": {"rows": len(rows), "resolved": sum(row["identity"] is not None for row in rows),
                       "gaps": sum(row["identity"] is None for row in rows)}}
