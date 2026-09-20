#!/usr/bin/env python
"""Validate the authored campaign data in data/.

Standalone CLI. The structural checks use the standard library only; the
terrain checks (cell-terrain recomputation, spatial) load the heightmap
through tools/terrain.py and need numpy and Pillow. Checks that cannot run
without a verified heightmap are reported as SKIPPED with a reason, never
silently passed.

Exit codes: 0 = no errors, 1 = at least one ERROR, 2 = usage/internal failure.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

ERROR, WARNING, INFO, SKIPPED = "ERROR", "WARNING", "INFO", "SKIPPED"
SEVERITY_ORDER = {ERROR: 0, WARNING: 1, SKIPPED: 2, INFO: 3}

# ---------------------------------------------------------------- findings


class Finding:
    __slots__ = ("severity", "check", "file", "line", "message", "where")

    def __init__(self, severity, check, message, file=None, line=None, where=None):
        self.severity = severity
        self.check = check
        self.message = message
        self.file = file
        self.line = line
        self.where = where

    def as_dict(self):
        return {
            "severity": self.severity,
            "check": self.check,
            "file": self.file,
            "line": self.line,
            "where": self.where,
            "message": self.message,
        }


class Report:
    def __init__(self):
        self.findings = []

    def add(self, *a, **kw):
        self.findings.append(Finding(*a, **kw))

    def error(self, check, msg, **kw):
        self.add(ERROR, check, msg, **kw)

    def warn(self, check, msg, **kw):
        self.add(WARNING, check, msg, **kw)

    def info(self, check, msg, **kw):
        self.add(INFO, check, msg, **kw)

    def skip(self, check, msg, **kw):
        self.add(SKIPPED, check, msg, **kw)

    def count(self, severity):
        return sum(1 for f in self.findings if f.severity == severity)


# ------------------------------------------------------------ file loading


class DataFile:
    """A parsed data file that can map a record id back to a source line."""

    def __init__(self, path: Path, rel: str, raw: str, doc):
        self.path = path
        self.rel = rel
        self.raw = raw
        self.doc = doc
        self._lines = raw.splitlines()

    def line_of_id(self, value):
        """Best-effort line number for the record whose id is `value`."""
        if value is None:
            return None
        needle = json.dumps(str(value))
        for i, line in enumerate(self._lines, 1):
            if needle in line:
                return i
        return None

    def line_of_key(self, key):
        needle = '"%s"' % key
        for i, line in enumerate(self._lines, 1):
            if needle in line:
                return i
        return None


def load_file(path: Path, rel: str, report: Report):
    if not path.is_file():
        return None
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        report.error("schema", "cannot read file: %s" % exc, file=rel)
        return None
    try:
        doc = json.loads(raw)
    except json.JSONDecodeError as exc:
        report.error(
            "schema",
            "invalid JSON: %s" % exc.msg,
            file=rel,
            line=exc.lineno,
        )
        return None
    return DataFile(path, rel, raw, doc)


# ------------------------------------------------------------ schema model

# file -> (schema id, collection key, required record fields, enum fields)
SCHEMAS = {
    "world.json": ("cobblers.world/1", None, [], {}),
    "cells.json": (
        "cobblers.cells/1",
        "cells",
        ["id", "row", "column"],
        {"role": {"route", "town", "gym", "wilds", "optional"}},
    ),
    "landmarks.json": (
        "cobblers.landmarks/1",
        "landmarks",
        ["id", "name", "kind", "anchor", "status"],
        {
            "kind": {"rift", "mountain", "volcano", "island_chain", "coast", "lake", "pass", "installation",
                     "glacier", "moraine", "river", "basin", "marsh", "estuary", "ravine"},
            # built: in the terrain as intended; partial: present but under-delivered;
            # planned: a spec only. Nothing drops silently when terrain falls short.
            "status": {"built", "partial", "planned"},
            "water": {"allowed", "never"},
        },
    ),
    "events.json": (
        "cobblers.events/1",
        "events",
        ["id", "name", "cell", "kind", "anchor"],
        {
            "status": {"planned", "placed", "verified"},
            "claim_model": {"per_player", "shared", "once"},
        },
    ),
    "placements.json": (
        "cobblers.placements/1",
        "placements",
        ["id", "template", "cell", "position"],
        {
            "anchor_mode": {"corner", "center"},
            "y_mode": {"absolute", "surface", "surface_offset"},
            "rotation": {"none", "clockwise_90", "180", "counterclockwise_90"},
            "mirror": {"none", "left_right", "front_back"},
            "status": {"planned", "placed", "verified"},
        },
    ),
    "trainers.json": (
        "cobblers.trainers/1",
        "trainers",
        ["id", "display_name", "class", "team"],
        {
            "class": {
                "gym_leader", "elite_four", "champion", "rival",
                "admin", "grunt", "route",
            },
            "format": {"GEN_9_SINGLES", "GEN_9_DOUBLES"},
        },
    ),
    "spawns.json": (
        "cobblers.spawns/1",
        "entries",
        ["id", "species", "bucket", "level"],
        {"bucket": {"common", "uncommon", "rare", "ultra-rare"}},
    ),
    "gyms.json": (
        "cobblers.gyms/1",
        "gyms",
        ["id", "number", "name", "cell", "leader"],
        {},
    ),
    "progression.json": ("cobblers.progression/1", None, [], {}),
    "rivers.json": ("cobblers.rivers/1", "courses", ["id", "source", "valid", "verdict"], {}),
    "towns.json": (
        "cobblers.towns/1",
        "towns",
        ["id", "role", "tier", "status", "centre", "footprint", "waystone"],
        {"role": {"hometown", "gym_town", "league", "major_town", "rest_stop", "outpost"},
         "tier": {"critical", "major", "rest_stop", "outpost"}, "status": {"proposed", "accepted", "built"}},
    ),
    "routes.json": ("cobblers.routes/1", "routes", ["id", "from_town", "to_town"], {}),
    "visibility.json": (
        "cobblers.visibility/1", "claims",
        ["id", "claim", "recorded_in", "expect", "observers", "target", "surface", "measured", "fragile"],
        {"expect": {"visible", "not_visible"}, "surface": {"terrain", "canopy", "canopy_model"}},
    ),
    "habitat_blocks.json": (
        "cobblers.habitat-blocks/1", "blocks",
        ["id", "pool", "style", "replace_spawns", "range_of_influence", "position", "status"],
        {"style": {"natural"}, "status": {"planned", "placed", "verified"}},
    ),
    "dialogue.json": (
        "cobblers.dialogue/1", "conversations",
        ["id", "quest_id", "npc_id", "scope", "cursor", "entry_rules", "nodes"], {},
    ),
    "quests.json": (
        "cobblers.quests/1", "quests",
        ["id", "source", "scope", "optional", "progression_field_refs",
         "availability", "objectives", "transitions", "multiplayer"], {},
    ),
}

REQUIRED_FILES = {"world.json"}


# ----------------------------------------------------------------- context


class Context:
    def __init__(self, data_dir: Path, source_root, report: Report, world_save=None, spawn_pack=None):
        self.data_dir = data_dir
        self.source_root = source_root
        self.world_save = world_save
        self.spawn_pack = spawn_pack
        self.report = report
        self.files = {}
        self.world = None
        self.terrain_available = False
        self.terrain_reason = "not evaluated"

    def doc(self, name):
        f = self.files.get(name)
        return f.doc if f else None

    def records(self, name):
        """Return (DataFile, [records]) for a collection file, or (None, [])."""
        f = self.files.get(name)
        if not f:
            return None, []
        key = SCHEMAS[name][1]
        if not key:
            return f, []
        coll = f.doc.get(key)
        if not isinstance(coll, list):
            return f, []
        return f, [r for r in coll if isinstance(r, dict)]


# ------------------------------------------------------------------ checks


def check_schema(ctx: Context):
    rep = ctx.report
    for name, (schema_id, coll_key, required, enums) in SCHEMAS.items():
        path = ctx.data_dir / name
        if not path.is_file():
            if name in REQUIRED_FILES:
                rep.error("schema", "required file is missing", file="data/" + name)
            else:
                rep.info("schema", "not present yet", file="data/" + name)
            continue
        f = load_file(path, "data/" + name, rep)
        if not f:
            continue
        ctx.files[name] = f

        declared = f.doc.get("schema") if isinstance(f.doc, dict) else None
        if declared is None:
            rep.error("schema", "missing top-level \"schema\" field", file=f.rel, line=1)
        elif declared != schema_id:
            rep.error(
                "schema",
                'schema is "%s", expected "%s"' % (declared, schema_id),
                file=f.rel,
                line=f.line_of_key("schema"),
            )

        if not coll_key:
            continue
        coll = f.doc.get(coll_key)
        if coll is None:
            rep.error("schema", 'missing collection "%s"' % coll_key, file=f.rel, line=1)
            continue
        if not isinstance(coll, list):
            rep.error("schema", '"%s" must be a list' % coll_key, file=f.rel,
                      line=f.line_of_key(coll_key))
            continue
        for idx, rec in enumerate(coll):
            if not isinstance(rec, dict):
                rep.error("schema", "record %d is not an object" % idx, file=f.rel)
                continue
            line = f.line_of_id(rec.get("id"))
            for field in required:
                if field not in rec or rec[field] is None:
                    rep.error(
                        "schema",
                        'record "%s" is missing required field "%s"'
                        % (rec.get("id", "<no id>"), field),
                        file=f.rel, line=line, where=rec.get("id"),
                    )
            for field, allowed in enums.items():
                val = _deep_get(rec, field)
                if val is not None and val not in allowed:
                    rep.error(
                        "schema",
                        'record "%s" has %s="%s", not one of %s'
                        % (rec.get("id", "<no id>"), field, val,
                           ", ".join(sorted(allowed))),
                        file=f.rel, line=line, where=rec.get("id"),
                    )


def _deep_get(rec, field):
    if field in rec:
        return rec[field]
    for v in rec.values():
        if isinstance(v, dict):
            got = _deep_get(v, field)
            if got is not None:
                return got
    return None


def check_world_config(ctx: Context):
    rep = ctx.report
    f = ctx.files.get("world.json")
    if not f:
        return
    w = f.doc
    grid = w.get("grid") or {}

    if grid.get("kind") != "square":
        rep.error("schema", 'grid.kind must be "square"', file=f.rel,
                  line=f.line_of_key("kind"))
    for legacy in ("hex_flat_to_flat", "prototype_columns", "prototype_rows"):
        if legacy in grid:
            rep.error("schema", 'grid contains retired field "%s"' % legacy,
                      file=f.rel, line=f.line_of_key(legacy))

    cell = grid.get("cell_size")
    cols, rows = grid.get("columns"), grid.get("rows")
    hm = w.get("heightmap") or {}
    if cell and cols and hm.get("width") and cell * cols != hm["width"]:
        rep.error("schema",
                  "grid does not tile the heightmap: cell_size*columns=%s but width=%s"
                  % (cell * cols, hm["width"]), file=f.rel, line=f.line_of_key("cell_size"))
    if cell and rows and hm.get("height") and cell * rows != hm["height"]:
        rep.error("schema",
                  "grid does not tile the heightmap: cell_size*rows=%s but height=%s"
                  % (cell * rows, hm["height"]), file=f.rel, line=f.line_of_key("cell_size"))

    for axis in ("origin_x", "origin_z"):
        if grid.get(axis) is None:
            rep.error("origin",
                      "grid.%s is unset; the world origin must be confirmed in game "
                      "before any coordinate can be validated" % axis,
                      file=f.rel, line=f.line_of_key(axis))

    labels = grid.get("row_labels") or []
    if rows and len(labels) != rows:
        rep.error("schema", "row_labels has %d entries but rows=%s" % (len(labels), rows),
                  file=f.rel, line=f.line_of_key("row_labels"))
    cl = grid.get("column_labels") or []
    if cols and len(cl) != cols:
        rep.error("schema", "column_labels has %d entries but columns=%s" % (len(cl), cols),
                  file=f.rel, line=f.line_of_key("column_labels"))

    vert = w.get("vertical") or {}
    sea, lo, hi = vert.get("sea_level"), vert.get("min_y"), vert.get("max_y")
    if None not in (sea, lo, hi) and not lo <= sea <= hi:
        rep.error("schema", "sea_level %s outside vertical range %s..%s" % (sea, lo, hi),
                  file=f.rel, line=f.line_of_key("sea_level"))

    imp = w.get("import") or {}

    # Inputs are fractions of full scale so the mapping survives a bit-depth
    # change. Outputs are absolute Minecraft Y and never scale.
    if imp.get("input_units") != "fraction_of_full_scale":
        rep.error("schema",
                  'import.input_units must be "fraction_of_full_scale"; absolute '
                  "sample values silently break when the heightmap bit depth changes",
                  file=f.rel, line=f.line_of_key("input_units"))
    if "input_range" in imp:
        rep.error("schema",
                  "import.input_range is retired; low_in/high_in are fractions",
                  file=f.rel, line=f.line_of_key("input_range"))

    lo_in, hi_in = imp.get("low_in"), imp.get("high_in")
    for key, val in (("low_in", lo_in), ("high_in", hi_in)):
        if val is None:
            rep.error("schema", "import.%s is unset" % key, file=f.rel,
                      line=f.line_of_key(key))
        elif not isinstance(val, (int, float)) or isinstance(val, bool) \
                or not 0.0 <= float(val) <= 1.0:
            rep.error("schema",
                      "import.%s=%s must be a fraction of full scale between 0 and 1"
                      % (key, val), file=f.rel, line=f.line_of_key(key))
    if isinstance(lo_in, (int, float)) and isinstance(hi_in, (int, float)) \
            and float(lo_in) >= float(hi_in):
        rep.error("schema", "import.low_in (%s) must be below high_in (%s)"
                  % (lo_in, hi_in), file=f.rel, line=f.line_of_key("low_in"))

    for key in ("low_out", "high_out", "water_level"):
        val = imp.get(key)
        if val is None:
            rep.error("schema", "import.%s is unset" % key, file=f.rel,
                      line=f.line_of_key(key))
        elif None not in (lo, hi) and not lo <= val <= hi:
            rep.error("schema",
                      "import.%s=%s is outside the vertical band %s..%s"
                      % (key, val, lo, hi), file=f.rel, line=f.line_of_key(key))
    if imp.get("low_out") is not None and imp.get("high_out") is not None \
            and imp["low_out"] >= imp["high_out"]:
        rep.error("schema", "import.low_out (%s) must be below high_out (%s)"
                  % (imp["low_out"], imp["high_out"]),
                  file=f.rel, line=f.line_of_key("low_out"))
    if imp.get("water_level") is not None and sea is not None \
            and imp["water_level"] != sea:
        rep.warn("schema",
                 "import.water_level (%s) disagrees with vertical.sea_level (%s)"
                 % (imp["water_level"], sea),
                 file=f.rel, line=f.line_of_key("water_level"))


def check_integrity(ctx: Context):
    """Heightmap presence and hash. Fails closed."""
    rep = ctx.report
    f = ctx.files.get("world.json")
    if not f:
        ctx.terrain_reason = "world.json missing"
        return
    hm = f.doc.get("heightmap") or {}
    path, sha = hm.get("path"), hm.get("sha256")

    if not path:
        rep.error("integrity", "heightmap.path is null; cannot verify terrain",
                  file=f.rel, line=f.line_of_key("path"))
    if not sha:
        rep.error("integrity",
                  "heightmap.sha256 is null; terrain integrity is unverified "
                  "(failing closed)", file=f.rel, line=f.line_of_key("sha256"))
    if hm.get("status") and hm["status"] != "ok":
        rep.error("integrity", 'heightmap.status is "%s"' % hm["status"],
                  file=f.rel, line=f.line_of_key("status"))

    if not path or not sha:
        ctx.terrain_reason = "heightmap path or sha256 is null"
        return

    root = ctx.source_root
    if not root:
        rep.error("integrity",
                  "source_root is unset; set COBBLERS_SOURCE_ROOT or pass --source-root",
                  file=f.rel, line=f.line_of_key("source_root"))
        ctx.terrain_reason = "source_root unset"
        return

    full = Path(root) / path
    if not full.is_file():
        rep.error("integrity", "heightmap not found at %s" % full, file=f.rel)
        ctx.terrain_reason = "heightmap file missing"
        return

    h = hashlib.sha256()
    with open(full, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    actual = h.hexdigest()
    if actual != sha:
        rep.error("integrity",
                  "heightmap sha256 mismatch: recorded %s, actual %s" % (sha, actual),
                  file=f.rel, line=f.line_of_key("sha256"))
        ctx.terrain_reason = "heightmap hash mismatch"
        return

    ctx.terrain_available = True
    ctx.terrain_reason = "ok"


def check_referential(ctx: Context):
    rep = ctx.report
    ids = {}
    for name in SCHEMAS:
        f, recs = ctx.records(name)
        if not f:
            continue
        seen = {}
        for rec in recs:
            rid = rec.get("id")
            if rid is None:
                continue
            if rid in seen:
                rep.error("referential", 'duplicate id "%s" (first at line %s)'
                          % (rid, seen[rid]), file=f.rel,
                          line=f.line_of_id(rid), where=rid)
            else:
                seen[rid] = f.line_of_id(rid)
        ids[name] = set(seen)

    world = ctx.doc("world.json") or {}
    grid = world.get("grid") or {}
    rows = set(grid.get("row_labels") or [])
    cols = set(str(c) for c in (grid.get("column_labels") or []))

    cell_ids = ids.get("cells.json", set())

    def check_cell_ref(f, rec, value, field):
        if value is None:
            return
        s = str(value)
        if len(s) < 2 or s[0] not in rows or s[1:] not in cols:
            rep.error("referential",
                      'record "%s" %s="%s" is not a valid cell id for this grid'
                      % (rec.get("id"), field, s),
                      file=f.rel, line=f.line_of_id(rec.get("id")), where=rec.get("id"))
        elif cell_ids and s not in cell_ids:
            rep.error("referential",
                      'record "%s" references cell "%s" which is not in cells.json'
                      % (rec.get("id"), s),
                      file=f.rel, line=f.line_of_id(rec.get("id")), where=rec.get("id"))

    # cross-file id references: (file, field path, target file)
    refs = [
        ("events.json", ("structure", "placement_id"), "placements.json"),
        ("gyms.json", ("leader",), "trainers.json"),
        ("gyms.json", ("placement",), "placements.json"),
    ]
    for src, fieldpath, target in refs:
        f, recs = ctx.records(src)
        if not f:
            continue
        pool = ids.get(target)
        for rec in recs:
            val = rec
            for part in fieldpath:
                val = val.get(part) if isinstance(val, dict) else None
            if val is None:
                continue
            if pool is None:
                rep.error("referential",
                          'record "%s" references %s "%s" but %s does not exist'
                          % (rec.get("id"), ".".join(fieldpath), val, "data/" + target),
                          file=f.rel, line=f.line_of_id(rec.get("id")), where=rec.get("id"))
            elif val not in pool:
                rep.error("referential",
                          'record "%s" references unknown %s "%s"'
                          % (rec.get("id"), ".".join(fieldpath), val),
                          file=f.rel, line=f.line_of_id(rec.get("id")), where=rec.get("id"))

    for name in ("cells.json", "events.json", "placements.json", "trainers.json",
                 "spawns.json", "gyms.json"):
        f, recs = ctx.records(name)
        if not f:
            continue
        for rec in recs:
            if name == "cells.json":
                check_cell_ref(f, rec, rec.get("id"), "id")
            else:
                check_cell_ref(f, rec, rec.get("cell"), "cell")

    # landmark references from cells
    f, recs = ctx.records("cells.json")
    lm = ids.get("landmarks.json")
    if f:
        for rec in recs:
            for ref in rec.get("landmarks") or []:
                if lm is None or ref not in lm:
                    rep.error("referential",
                              'cell "%s" references unknown landmark "%s"'
                              % (rec.get("id"), ref),
                              file=f.rel, line=f.line_of_id(rec.get("id")),
                              where=rec.get("id"))


def check_quest_dialogue(ctx: Context):
    """Quest/dialogue contracts resolve through the authoritative quest-field registry."""
    rep = ctx.report
    pf = ctx.files.get("progression.json")
    qf = ctx.files.get("quests.json")
    df = ctx.files.get("dialogue.json")
    if not (pf and qf and df):
        return

    fields = {}
    for field in pf.doc.get("quest_fields") or []:
        if not isinstance(field, dict):
            continue
        fid = field.get("id")
        qid = field.get("quest_id")
        short = field.get("field")
        line = pf.line_of_id(fid)
        if not fid:
            rep.error("quest-dialogue", "quest field has no id", file=pf.rel)
            continue
        if fid in fields:
            rep.error("quest-dialogue", 'duplicate quest field "%s"' % fid,
                      file=pf.rel, line=line, where=fid)
        fields[fid] = field
        expected = "quest.%s.%s" % (qid, short)
        if fid != expected:
            rep.error("quest-dialogue", 'quest field "%s" must be named "%s"' % (fid, expected),
                      file=pf.rel, line=line, where=fid)
        if field.get("scope") not in ("player", "world"):
            rep.error("quest-dialogue", 'quest field "%s" has invalid scope' % fid,
                      file=pf.rel, line=line, where=fid)
        if field.get("type") not in ("boolean", "enum", "integer"):
            rep.error("quest-dialogue", 'quest field "%s" has invalid type' % fid,
                      file=pf.rel, line=line, where=fid)

    quests = {}
    transitions = {}
    rewards = {}
    for quest in qf.doc.get("quests") or []:
        if not isinstance(quest, dict):
            continue
        qid = quest.get("id")
        quests[qid] = quest
        line = qf.line_of_id(qid)
        refs = quest.get("progression_field_refs")
        if not isinstance(refs, list) or len(refs) != len(set(refs)):
            rep.error("quest-dialogue", 'quest "%s" needs unique progression_field_refs' % qid,
                      file=qf.rel, line=line, where=qid)
            refs = refs or []
        for fid in refs:
            field = fields.get(fid)
            if not field:
                rep.error("quest-dialogue", 'quest "%s" references undeclared field "%s"' % (qid, fid),
                          file=qf.rel, line=line, where=qid)
            elif field.get("quest_id") != qid:
                rep.error("quest-dialogue", 'quest "%s" references field owned by "%s"' %
                          (qid, field.get("quest_id")), file=qf.rel, line=line, where=qid)
        tlist = quest.get("transitions") or []
        tids = [t.get("id") for t in tlist if isinstance(t, dict)]
        if len(tids) != len(set(tids)):
            rep.error("quest-dialogue", 'quest "%s" has duplicate transition ids' % qid,
                      file=qf.rel, line=line, where=qid)
        transitions[qid] = set(tids)
        rewards[qid] = {r.get("id") for r in quest.get("rewards") or [] if isinstance(r, dict)}

        def walk_quest(value):
            if isinstance(value, dict):
                fid = value.get("field")
                if isinstance(fid, str) and fid.startswith("quest."):
                    if fid not in fields:
                        rep.error("quest-dialogue", 'quest "%s" uses undeclared field "%s"' % (qid, fid),
                                  file=qf.rel, line=line, where=qid)
                    elif fid not in refs:
                        rep.error("quest-dialogue", 'quest "%s" uses unlisted field "%s"' % (qid, fid),
                                  file=qf.rel, line=line, where=qid)
                if value.get("kind") == "grant_reward_once":
                    reward = value.get("reward")
                    claim = value.get("claim_field")
                    if reward not in rewards[qid]:
                        rep.error("quest-dialogue", 'quest "%s" grants unknown reward "%s"' % (qid, reward),
                                  file=qf.rel, line=line, where=qid)
                    claim_def = fields.get(claim)
                    if not claim_def or claim_def.get("type") != "boolean" or claim_def.get("scope") != "player":
                        rep.error("quest-dialogue", 'grant_reward_once in "%s" needs a player boolean claim_field' % qid,
                                  file=qf.rel, line=line, where=qid)
                    if not value.get("idempotency_key"):
                        rep.error("quest-dialogue", 'grant_reward_once in "%s" needs an idempotency_key' % qid,
                                  file=qf.rel, line=line, where=qid)
                for child in value.values():
                    walk_quest(child)
            elif isinstance(value, list):
                for child in value:
                    walk_quest(child)
        walk_quest(quest)

    for conv in df.doc.get("conversations") or []:
        if not isinstance(conv, dict):
            continue
        cid = conv.get("id")
        qid = conv.get("quest_id")
        line = df.line_of_id(cid)
        if qid not in quests:
            rep.error("quest-dialogue", 'conversation "%s" references unknown quest "%s"' % (cid, qid),
                      file=df.rel, line=line, where=cid)
            continue
        refs = set(quests[qid].get("progression_field_refs") or [])
        cursor = (conv.get("cursor") or {}).get("progression_field")
        cdef = fields.get(cursor)
        if not cdef or cdef.get("scope") != "player":
            rep.error("quest-dialogue", 'conversation "%s" needs a registered player cursor field' % cid,
                      file=df.rel, line=line, where=cid)
        elif cursor not in refs:
            rep.error("quest-dialogue", 'conversation "%s" cursor is not listed by quest "%s"' % (cid, qid),
                      file=df.rel, line=line, where=cid)
        nodes = [n for n in (conv.get("nodes") or []) if isinstance(n, dict)]
        node_ids = [n.get("id") for n in nodes]
        node_set = set(node_ids)
        if len(node_ids) != len(node_set):
            rep.error("quest-dialogue", 'conversation "%s" has duplicate node ids' % cid,
                      file=df.rel, line=line, where=cid)
        initial = (conv.get("cursor") or {}).get("initial_node")
        if initial not in node_set:
            rep.error("quest-dialogue", 'conversation "%s" has unknown initial node "%s"' % (cid, initial),
                      file=df.rel, line=line, where=cid)

        def walk_dialogue(value, key=None):
            if isinstance(value, dict):
                fid = value.get("field")
                if isinstance(fid, str) and fid.startswith("quest.") and fid not in fields:
                    rep.error("quest-dialogue", 'conversation "%s" uses undeclared field "%s"' % (cid, fid),
                              file=df.rel, line=line, where=cid)
                if value.get("kind") == "quest_transition":
                    tid = value.get("transition")
                    if tid not in transitions.get(qid, set()):
                        rep.error("quest-dialogue", 'conversation "%s" calls unknown transition "%s"' % (cid, tid),
                                  file=df.rel, line=line, where=cid)
                for child_key, child in value.items():
                    if child_key in ("next", "node") and isinstance(child, str) and child != "$cursor" and child not in node_set:
                        rep.error("quest-dialogue", 'conversation "%s" targets unknown node "%s"' % (cid, child),
                                  file=df.rel, line=line, where=cid)
                    walk_dialogue(child, child_key)
            elif isinstance(value, list):
                for child in value:
                    walk_dialogue(child, key)
        walk_dialogue(conv)


def check_progression(ctx: Context):
    rep = ctx.report
    f = ctx.files.get("progression.json")
    if not f:
        rep.info("progression", "not present yet", file="data/progression.json")
        return
    doc = f.doc
    chapters = doc.get("chapters") or []
    flags = doc.get("flags") or []

    declared = {fl.get("id") for fl in flags if isinstance(fl, dict)}
    set_by, read_by = set(), set()

    for fl in flags:
        if isinstance(fl, dict) and fl.get("set_by"):
            set_by.add(fl.get("id"))

    edges = {}
    for ch in chapters:
        if not isinstance(ch, dict):
            continue
        cid = ch.get("id")
        produced = set(ch.get("unlocks") or [])
        consumed = set(ch.get("unlocked_by") or [])
        read_by |= consumed
        set_by |= produced
        edges[cid] = consumed

    for name in ("events.json", "gyms.json"):
        _, recs = ctx.records(name)
        for rec in recs:
            prog = rec.get("progression") or rec
            read_by |= set(prog.get("requires") or [])
            set_by |= set(prog.get("unlocks") or [])

    for fid in sorted(declared - set_by):
        rep.error("progression", 'flag "%s" is never set by anything' % fid,
                  file=f.rel, line=f.line_of_id(fid), where=fid)
    for fid in sorted(declared - read_by):
        rep.warn("progression", 'flag "%s" is never read by anything' % fid,
                 file=f.rel, line=f.line_of_id(fid), where=fid)
    for fid in sorted((set_by | read_by) - declared):
        if fid:
            rep.error("progression", 'flag "%s" is used but not declared in flags[]' % fid,
                      file=f.rel, where=fid)

    # chapter graph acyclicity over unlocked_by
    colour = {}

    def visit(node, stack):
        if colour.get(node) == 2:
            return
        if colour.get(node) == 1:
            cycle = " -> ".join(stack + [str(node)])
            rep.error("progression", "chapter dependency cycle: %s" % cycle, file=f.rel)
            return
        colour[node] = 1
        for dep in edges.get(node, ()):  # dep is a flag, map to producing chapter
            for other in chapters:
                if isinstance(other, dict) and dep in (other.get("unlocks") or []):
                    visit(other.get("id"), stack + [str(node)])
        colour[node] = 2

    for ch in chapters:
        if isinstance(ch, dict):
            visit(ch.get("id"), [])

    ordered = sorted(
        [c for c in chapters if isinstance(c, dict) and c.get("order") is not None],
        key=lambda c: c["order"],
    )
    prev_cap, prev_id = None, None
    for ch in ordered:
        cap = ch.get("level_cap")
        if cap is None:
            continue
        if prev_cap is not None and cap < prev_cap:
            rep.error("progression",
                      'level cap decreases: chapter "%s" is %s after "%s" at %s'
                      % (ch.get("id"), cap, prev_id, prev_cap),
                      file=f.rel, line=f.line_of_id(ch.get("id")), where=ch.get("id"))
        prev_cap, prev_id = cap, ch.get("id")

    claimed = {}
    for ch in ordered:
        for cell in ch.get("unlocks_cells") or ch.get("unlocks_hexes") or []:
            if cell in claimed:
                rep.error("progression",
                          'cell "%s" is unlocked by "%s" and again by "%s"'
                          % (cell, claimed[cell], ch.get("id")),
                          file=f.rel, line=f.line_of_id(ch.get("id")), where=ch.get("id"))
            else:
                claimed[cell] = ch.get("id")


def load_terrain(ctx: Context):
    """Heights, world config and the landmark no-water mask, loaded once.

    Returns None (and sets ctx.terrain_reason) when the analysis modules or the
    heightmap cannot be loaded.
    """
    if getattr(ctx, "terrain_cache", None) is not None:
        return ctx.terrain_cache
    if not ctx.terrain_available:
        return None
    tools = str(Path(__file__).resolve().parent)
    if tools not in sys.path:
        sys.path.insert(0, tools)
    try:
        import terrain as T
        import landmarks as LM
        import cell_stats as CS
    except ImportError as exc:
        ctx.terrain_reason = "analysis modules unavailable (%s)" % exc
        return None
    try:
        heights, world = T.load(ctx.data_dir / "world.json", ctx.source_root)
    except T.TerrainUnavailable as exc:
        ctx.terrain_reason = str(exc)
        return None
    no_water = None
    lm_path = ctx.data_dir / "landmarks.json"
    landmarks = None
    if lm_path.is_file():
        landmarks = LM.load(lm_path)
        no_water = LM.no_water_mask(landmarks, heights.shape)
    ctx.terrain_cache = {"heights": heights, "world": world, "no_water": no_water,
                         "landmarks": landmarks, "T": T, "CS": CS}
    return ctx.terrain_cache


def _points(obj):
    """(label, x, z) for a landmark's anchor and named anchors."""
    out = []
    a = obj.get("anchor")
    if isinstance(a, dict) and "x" in a and "z" in a:
        out.append(("anchor", a["x"], a["z"]))
    for name, p in (obj.get("anchors") or {}).items():
        if isinstance(p, dict) and "x" in p and "z" in p:
            out.append(("anchors." + name, p["x"], p["z"]))
    return out


def check_spatial(ctx: Context):
    rep = ctx.report
    if not ctx.terrain_available:
        rep.skip("spatial",
                 "terrain checks not run (%s). Anchors are NOT confirmed in bounds, "
                 "on land, above sea level, or non-overlapping." % ctx.terrain_reason)
        return
    world = ctx.doc("world.json") or {}
    grid = world.get("grid") or {}
    if grid.get("origin_x") is None or grid.get("origin_z") is None:
        rep.skip("spatial", "grid origin unset; coordinates cannot be placed on the map")
        return
    t = load_terrain(ctx)
    if t is None:
        rep.skip("spatial", "terrain could not be loaded (%s)" % ctx.terrain_reason)
        return
    heights, T = t["heights"], t["T"]
    sea = T.sea_level(t["world"])
    b = world.get("bounds") or {}
    f_world = ctx.files.get("world.json")

    def inside(x, z, box, tol=0):
        return box["min_x"] - tol <= x <= box["max_x"] + tol and box["min_z"] - tol <= z <= box["max_z"] + tol

    # world geometry: landmass inside the border, border inside the exported canvas
    exp = world.get("export") or {}
    border, canvas = exp.get("border"), exp.get("canvas")
    if border and canvas:
        for name, inner, outer in (("bounds", b, border), ("export.border", border, canvas)):
            if not (inside(inner["min_x"], inner["min_z"], outer) and inside(inner["max_x"], inner["max_z"], outer)):
                rep.error("spatial", "%s is not inside %s" % (name, "export.border" if outer is border else "export.canvas"),
                          file=f_world.rel if f_world else None)
        size = border.get("size")
        if size is not None and (border["max_x"] - border["min_x"] + 1 != size or border["max_z"] - border["min_z"] + 1 != size):
            rep.error("spatial", "export.border extent does not match its size %s" % size,
                      file=f_world.rel if f_world else None)
        centre = border.get("centre")
        if centre is not None and (border["min_x"] + border["max_x"] + 1) / 2 != centre:
            rep.error("spatial", "export.border is not centred on %s" % centre,
                      file=f_world.rel if f_world else None)

    # landmark anchors: in bounds, distinct, and their ground height recorded
    checked, low, high, seen = 0, None, None, {}
    f_lm, lm_recs = ctx.records("landmarks.json")
    for rec in lm_recs:
        for label, x, z in _points(rec):
            checked += 1
            where = "%s.%s" % (rec.get("id"), label)
            if not inside(x, z, b):
                rep.error("spatial", "%s (%s, %s) is outside the landmass bounds" % (where, x, z),
                          file=f_lm.rel, line=f_lm.line_of_id(rec.get("id")), where=rec.get("id"))
                continue
            y = float(heights[z - int(grid["origin_z"]), x - int(grid["origin_x"])])
            low = y if low is None else min(low, y)
            high = y if high is None else max(high, y)
            # a landmark's anchor may coincide with one of its own named anchors, never with another landmark's
            other = seen.get((x, z))
            if other and other[0] != rec.get("id"):
                rep.error("spatial", "%s shares its position with %s" % (where, other[1]),
                          file=f_lm.rel, line=f_lm.line_of_id(rec.get("id")), where=rec.get("id"))
            seen.setdefault((x, z), (rec.get("id"), where))
            if rec.get("water") == "never" and label == "anchor" and y >= sea and rec.get("kind") == "rift":
                rep.warn("spatial", "%s is a no-water hollow but its anchor ground y%.1f is above sea level" % (where, y),
                         file=f_lm.rel, line=f_lm.line_of_id(rec.get("id")), where=rec.get("id"))

    # region polygons inside the landmass (within polygon tolerance), marine geometry inside the border
    polys = 0
    reg_path = ctx.data_dir / "regions.json"
    if reg_path.is_file():
        reg = json.loads(reg_path.read_text(encoding="utf-8"))
        tol = int(((reg.get("geometry") or {}).get("polygon_tolerance_blocks")) or 0)
        for r in reg.get("regions") or []:
            for ring in r.get("polygons") or []:
                polys += 1
                bad = [p for p in ring if not inside(p[0], p[1], b, tol)]
                if bad:
                    rep.error("spatial", 'region "%s" polygon has %d vertices outside the landmass bounds, first %s'
                              % (r.get("id"), len(bad), bad[0]), file="data/regions.json", where=r.get("id"))
        for r in reg.get("marine_regions") or []:
            box = border or b
            for ring in r.get("polygons") or []:
                polys += 1
                bad = [p for p in ring if not inside(p[0], p[1], box, tol)]
                if bad:
                    rep.error("spatial", 'marine region "%s" polygon has %d vertices outside the border, first %s'
                              % (r.get("id"), len(bad), bad[0]), file="data/regions.json", where=r.get("id"))
            geo = r.get("geometry") or {}
            if geo.get("kind") == "ring" and border:
                o = geo.get("outer") or []
                if len(o) == 4 and not (inside(o[0], o[1], border) and inside(o[2], o[3], border)):
                    rep.error("spatial", 'marine region "%s" ring extends past the border' % r.get("id"),
                              file="data/regions.json", where=r.get("id"))
    rep.info("spatial", "checked %d landmark anchors (ground y%s-y%s) and %d region polygons against bounds%s"
             % (checked, "%.0f" % low if low is not None else "?", "%.0f" % high if high is not None else "?",
                polys, " and the export border" if border else ""))


CELL_TERRAIN_KEYS = ("min_y", "max_y", "mean_y", "land_fraction", "water_fraction", "void_fraction",
                     "mean_slope", "max_slope")


def check_cell_terrain_recorded(ctx: Context):
    rep = ctx.report
    f, recs = ctx.records("cells.json")
    if not f:
        rep.info("cell-terrain", "not present yet", file="data/cells.json")
        return
    for rec in recs:
        line = f.line_of_id(rec.get("id"))
        terrain = rec.get("terrain")
        if not terrain or all(v is None for v in terrain.values()):
            rep.error("cell-terrain",
                      'cell "%s" has no terrain statistics (failing closed)'
                      % rec.get("id"), file=f.rel, line=line, where=rec.get("id"))
            continue
        if not terrain.get("computed_from_sha256"):
            rep.error("cell-terrain",
                      'cell "%s" terrain has null computed_from_sha256; the numbers '
                      'cannot be traced to a heightmap' % rec.get("id"),
                      file=f.rel, line=line, where=rec.get("id"))

    if not ctx.terrain_available:
        rep.skip("cell-terrain", "cell terrain statistics not recomputed (%s)" % ctx.terrain_reason)
        return
    t = load_terrain(ctx)
    if t is None:
        rep.skip("cell-terrain", "cell terrain statistics not recomputed (%s)" % ctx.terrain_reason)
        return
    world = t["world"]
    sha = (world.get("heightmap") or {}).get("sha256")
    imp_digest = import_digest(world)
    now, _ = t["CS"].measure(t["heights"], world, 8, t["no_water"])
    by_id = {c["id"]: c["terrain"] for c in now}
    recorded = {rec.get("id"): rec for rec in recs}
    drift = 0
    for cid in sorted(set(by_id) - set(recorded)):
        rep.error("cell-terrain", 'grid cell "%s" is missing from cells.json' % cid, file=f.rel)
    for cid, rec in recorded.items():
        line = f.line_of_id(cid)
        terrain = rec.get("terrain") or {}
        if cid not in by_id:
            rep.error("cell-terrain", 'cell "%s" is not in the grid' % cid, file=f.rel, line=line, where=cid)
            continue
        if terrain.get("computed_from_sha256") and terrain["computed_from_sha256"] != sha:
            rep.error("cell-terrain", 'cell "%s" was computed from heightmap %s, not %s'
                      % (cid, terrain["computed_from_sha256"][:12], (sha or "")[:12]), file=f.rel, line=line, where=cid)
        if terrain.get("computed_from_import") and terrain["computed_from_import"] != imp_digest:
            rep.error("cell-terrain", 'cell "%s" was computed with a different import mapping' % cid,
                      file=f.rel, line=line, where=cid)
        for key in CELL_TERRAIN_KEYS:
            want, got = terrain.get(key), by_id[cid].get(key)
            if want is None or got is None:
                continue
            tol = 0.0015 if key.endswith("fraction") else 0.02
            if abs(float(want) - float(got)) > tol:
                drift += 1
                rep.error("cell-terrain", 'cell "%s" %s drifted: recorded %s, heightmap gives %s'
                          % (cid, key, want, got), file=f.rel, line=line, where=cid)
    rep.info("cell-terrain", "recomputed %d cells from heightmap %s at the current import mapping: %s"
             % (len(by_id), (sha or "")[:12], "no drift" if not drift else "%d values drifted" % drift))


def import_digest(world):
    """Stable digest of the import mapping, so recorded statistics can be tied to it."""
    imp = world.get("import") or {}
    keys = ("input_units", "low_in", "high_in", "low_out", "high_out", "water_level", "clamp_low", "clamp_high")
    text = json.dumps({k: imp.get(k) for k in keys}, sort_keys=True)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def check_rivers(ctx: Context):
    """Graded river courses: traced to the current heightmap, and every graded bed descends."""
    rep = ctx.report
    f, courses = ctx.records("rivers.json")
    if not f:
        return
    world = ctx.doc("world.json") or {}
    hm = world.get("heightmap") or {}
    imported = hm.get("sha256")
    derived = hm.get("derived_from") or {}
    sha = derived.get("sha256") or imported      # rivers are planned on the authored heightmap
    sea = float((world.get("vertical") or {}).get("sea_level", 62))
    if f.doc.get("computed_from_sha256") != sha:
        rep.error("rivers", "rivers.json was computed from heightmap %s, not %s; rerun tools/grade_rivers.py plan"
                  % ((f.doc.get("computed_from_sha256") or "")[:12], (sha or "")[:12]),
                  file=f.rel, line=f.line_of_key("computed_from_sha256"))
    # the chain: authored (derived_from) -> river cut (rivers.json cut.output) -> sculpt (sculpted_from) -> import.
    # With a sculpt the cut is the sculpt's input; without one the cut is the import itself.
    sculpted = hm.get("sculpted_from")
    out_sha = ((f.doc.get("cut") or {}).get("output") or {}).get("sha256")
    if sculpted is not None:
        want = sculpted.get("sha256") if isinstance(sculpted, dict) else None
        if not want or out_sha != want:
            rep.error("rivers", "the sculpt input %s (world.json heightmap.sculpted_from) is not the river cut recorded "
                      "in rivers.json (%s); rerun tools/grade_rivers.py cut, then tools/sculpt.py apply, and update "
                      "world.json" % ((want or "")[:12], (out_sha or "")[:12]),
                      file=f.rel, line=f.line_of_key("cut"))
    elif derived:
        if out_sha != imported:
            rep.error("rivers", "the imported heightmap %s is not the river cut recorded in rivers.json (%s); rerun "
                      "tools/grade_rivers.py cut and update world.json" % ((imported or "")[:12], (out_sha or "")[:12]),
                      file=f.rel, line=f.line_of_key("cut"))
    for c in courses:
        line = f.line_of_id(c.get("id"))
        poly = c.get("graded_polyline")
        if not c.get("valid"):
            if poly:
                rep.error("rivers", 'course "%s" is not valid but carries a graded polyline' % c.get("id"),
                          file=f.rel, line=line, where=c.get("id"))
            continue
        if not poly or len(poly) < 2:
            rep.error("rivers", 'valid course "%s" has no graded polyline' % c.get("id"),
                      file=f.rel, line=line, where=c.get("id"))
            continue
        for (_, _, s0, f0), (_, _, s1, f1) in zip(poly, poly[1:]):
            if s1 > s0 + 1e-6 or f1 > f0 + 1e-6:
                rep.error("rivers", 'course "%s" rises from %.2f to %.2f' % (c.get("id"), f0, f1),
                          file=f.rel, line=line, where=c.get("id"))
                break
        if min(p[2] for p in poly) < sea - 1e-6:
            rep.error("rivers", 'course "%s" has a water surface below sea level' % c.get("id"),
                      file=f.rel, line=line, where=c.get("id"))
    cut = f.doc.get("cut")
    if cut and (cut.get("from_heightmap") or {}).get("sha256") != sha:
        rep.warn("rivers", "the cut heightmap %s was made from a different heightmap; rerun the cut"
                 % (cut.get("output") or {}).get("path"), file=f.rel, line=f.line_of_key("cut"))
    _check_major_head(rep, f, courses)


GRADE_RIVERS = Path(__file__).resolve().parent / "grade_rivers.py"      # WALL_RISE, WALL_REACH, WALL_RUN, WALL_STEP, FACTOR
# head_rule key -> (tools/grade_rivers.py constant, parameters.valley_head key)
HEAD_RULE_CONSTANTS = {"wall_rise_blocks": ("WALL_RISE", "wall_rise"), "wall_reach_blocks": ("WALL_REACH", "wall_reach"),
                       "consecutive_stations": ("WALL_RUN", "run"), "station_spacing_blocks": ("WALL_STEP", "step")}


def _local_only_template(repo_root, rel):
    """True when kits/PROVENANCE.json marks this template local_only: its licence forbids committing it."""
    import re
    prov = Path(repo_root) / "kits" / "PROVENANCE.json"
    if not prov.is_file():
        return False
    for rec in json.loads(prov.read_text(encoding="utf-8")).get("records") or []:
        if not rec.get("local_only"):
            continue
        for g in rec.get("paths") or []:
            rx = re.escape(g).replace(r"\*\*/", "(?:.*/)?").replace(r"\*", "[^/]*")
            if re.fullmatch(rx, rel):
                return True
    return False


def _module_constant(path, name):
    """A module-level numeric literal read with ast (no import), or None when the file or name is absent."""
    import ast
    path = Path(path)
    if not path.is_file():
        return None
    for node in ast.parse(path.read_text(encoding="utf-8")).body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name)                 and node.targets[0].id == name:
            return ast.literal_eval(node.value)
    return None


def _check_major_head(rep, f, courses):
    """The major river's trunk starts where its path first runs between valley walls (tools/grade_rivers.py
    valley_head): the rule is recorded with the code's WALL_* values (and parameters.valley_head agrees), the head
    moved a non-negative distance along the path, the trunk's recorded source is its first graded station, and the
    survey of the rule on other courses is well formed."""
    major = f.doc.get("major_river")
    if major is None:
        return
    line = f.line_of_key("head_rule") or f.line_of_key("major_river")

    def err(msg, where=None, ln=None):
        rep.error("rivers", msg, file=f.rel, line=ln or line, where=where)

    if not isinstance(major, dict):
        err("major_river must be an object")
        return
    hr = major.get("head_rule")
    if not isinstance(hr, dict):
        err("major_river.head_rule is missing: the plan does not record where the trunk starts or why; rerun "
            "tools/grade_rivers.py plan")
        return
    if hr.get("rule") != "valley_walls":
        err('major_river.head_rule.rule is %r, not "valley_walls"; rerun tools/grade_rivers.py plan' % (hr.get("rule"),))
        return
    try:
        code = {k: _module_constant(GRADE_RIVERS, c) for k, (c, _) in HEAD_RULE_CONSTANTS.items()}
        grid = _module_constant(GRADE_RIVERS, "FACTOR")
    except (SyntaxError, ValueError) as exc:
        err("cannot read the head rule constants from %s: %s" % (GRADE_RIVERS, exc))
        code, grid = {}, None
    vh = (f.doc.get("parameters") or {}).get("valley_head")
    for key, (const, pkey) in HEAD_RULE_CONSTANTS.items():
        v = hr.get(key)
        if not _num(v) or v <= 0:
            err("major_river.head_rule.%s must be a number > 0, got %r" % (key, v))
            continue
        if code.get(key) is not None and v != code[key]:
            err("major_river.head_rule.%s %s is not tools/grade_rivers.py %s %s; rerun tools/grade_rivers.py plan"
                % (key, v, const, code[key]))
        if isinstance(vh, dict) and vh.get(pkey) != v:
            err("major_river.head_rule.%s %s is not parameters.valley_head.%s %s" % (key, v, pkey, vh.get(pkey)))
    if not isinstance(vh, dict):
        err("parameters.valley_head is missing; rerun tools/grade_rivers.py plan", ln=f.line_of_key("parameters"))
    ph = hr.get("path_head")
    if not (isinstance(ph, dict) and _num(ph.get("x")) and _num(ph.get("z"))):
        err("major_river.head_rule.path_head needs x and z")
    moved = hr.get("moved_blocks_along_path")
    if moved is None:
        rep.warn("rivers", "major_river.head_rule found no walled stretch (moved_blocks_along_path is null): the trunk "
                 "starts at the path head", file=f.rel, line=line)
    elif not _num(moved) or moved < 0:
        err("major_river.head_rule.moved_blocks_along_path must be a number >= 0, got %r" % (moved,))
    ids = major.get("courses") or []
    by_id = {c.get("id"): c for c in courses}
    trunk = by_id.get(ids[0]) if ids else None
    if trunk is None:
        err("major_river.courses does not name a trunk course in courses")
        return
    src, poly = trunk.get("source") or {}, trunk.get("graded_polyline") or []
    cell = (f.doc.get("parameters") or {}).get("grid_blocks") or grid or 4
    if trunk.get("valid") and poly:
        gx, gz = poly[0][0], poly[0][1]
        if not (_num(src.get("x")) and _num(src.get("z")) and abs(src["x"] - gx) < cell and abs(src["z"] - gz) < cell):
            err('the major river trunk "%s" source (%s, %s) is not its first graded station (%s, %s) within one %s-block '
                "grid cell" % (trunk.get("id"), src.get("x"), src.get("z"), gx, gz, cell), where=trunk.get("id"),
                ln=f.line_of_id(trunk.get("id")))
    if _num(moved) and moved > 0 and isinstance(ph, dict) and (src.get("x"), src.get("z")) == (ph.get("x"), ph.get("z")):
        err("the head rule moved the trunk %s blocks along its path, but the trunk still starts at the path head (%s, %s)"
            % (moved, ph.get("x"), ph.get("z")))
    survey = major.get("head_rule_survey_other_courses")
    if survey is None:
        return
    if not isinstance(survey, list):
        err("major_river.head_rule_survey_other_courses must be a list")
        return
    seen = set()
    for i, row in enumerate(survey):
        w = "major_river.head_rule_survey_other_courses[%d]" % i
        if not isinstance(row, dict):
            err("%s must be an object" % w)
            continue
        cid = row.get("course")
        if cid not in by_id:
            err('%s names course %r, which is not in courses' % (w, cid))
        elif cid == trunk.get("id"):
            err("%s surveys the trunk itself; the survey covers the other courses" % w)
        elif (by_id[cid].get("source") or {}).get("kind") == "lake_outflow":
            err('%s surveys "%s", a lake outflow; the survey covers courses whose head is not a lake' % (w, cid))
        if cid in seen:
            err('%s lists "%s" twice' % (w, cid))
        seen.add(cid)
        if not isinstance(row.get("walled_from_start"), bool):
            err("%s.walled_from_start must be true or false" % w)
        mv = row.get("rule_would_move_head_blocks")
        if mv is not None and (not _num(mv) or mv < 0):
            err("%s.rule_would_move_head_blocks must be null or a number >= 0, got %r" % (w, mv))
        n, k = row.get("samples"), row.get("walled_samples")
        if not (_int(n) and _int(k) and 0 <= k <= n):
            err("%s needs integer samples >= walled_samples >= 0, got %r and %r" % (w, n, k))
        elif row.get("walled_from_start") is True and mv not in (0, None):
            err("%s is walled from its start but the rule would move its head %s blocks" % (w, mv))


CRITICAL_ROLES = {"hometown": 1, "gym_town": 8, "league": 1}
OFF_PATH_RANGE = {"rest_stop": (100, 450), "major_town": (250, None), "outpost": (250, None)}
# Landmark trees are outposts sited to be SEEN from a leg (data/foliage.json landmark_trees seen_from); the climb to them is the
# discovery, so they may stand closer to the path than a settlement. The Patriarch is 247 blocks from Victory Road, painted into
# the exported world, and sited on its Wedge crest for the Rift skyline: the rule relaxes rather than the tree moving.
OFF_PATH_RANGE_BY_KIND = {"landmark_tree": (200, None)}
SPACING = {"settlement": 600, "outpost": 300}
OFF_PATH_STALE_BLOCKS = 2     # a recorded off-path distance further than this from the measured one is stale


def _route_segments(routes_doc):
    """Every (x0, z0, x1, z1) segment of every route polyline in data/routes.json, or None when there are none."""
    segs = []
    for r in (routes_doc or {}).get("routes") or []:
        pts = [(p.get("x"), p.get("z")) for p in ((r.get("corridor") or {}).get("polyline") or [])
               if isinstance(p, dict) and _num(p.get("x")) and _num(p.get("z"))]
        segs += [(a[0], a[1], b[0], b[1]) for a, b in zip(pts, pts[1:])]
    return segs or None


def _distance_to_routes(segs, centre):
    """Whole blocks from a centre to the nearest route polyline segment, or None when either is missing."""
    if not segs or not isinstance(centre, dict) or not (_num(centre.get("x")) and _num(centre.get("z"))):
        return None
    x, z = centre["x"], centre["z"]
    best = float("inf")
    for ax, az, bx, bz in segs:
        dx, dz = bx - ax, bz - az
        den = dx * dx + dz * dz
        t = 0.0 if not den else max(0.0, min(1.0, ((x - ax) * dx + (z - az) * dz) / den))
        best = min(best, math.hypot(x - ax - t * dx, z - az - t * dz))
    return round(best)


NEAREST_LEG_ALONG_BLOCKS = 4  # plus half a thousandth of the leg: at_fraction is stored to three decimals


def _route_lines(routes_doc):
    """[(route, [(x, z, at_distance_blocks)], length)] in file order, for routes with a usable polyline."""
    out = []
    for r in (routes_doc or {}).get("routes") or []:
        pts = [(p["x"], p["z"], p["at_distance_blocks"]) for p in ((r.get("corridor") or {}).get("polyline") or [])
               if isinstance(p, dict) and _num(p.get("x")) and _num(p.get("z")) and _num(p.get("at_distance_blocks"))]
        if len(pts) >= 2 and pts[-1][2] > 0:
            out.append((r, pts, pts[-1][2]))
    return out


def _project(pts, x, z):
    """(distance, along, qx, qz): the nearest point on one polyline to (x, z) and how far along the polyline it lies."""
    best = None
    for (ax, az, aa), (bx, bz, ba) in zip(pts, pts[1:]):
        dx, dz = bx - ax, bz - az
        den = dx * dx + dz * dz
        t = 0.0 if not den else max(0.0, min(1.0, ((x - ax) * dx + (z - az) * dz) / den))
        qx, qz = ax + t * dx, az + t * dz
        d = math.hypot(x - qx, z - qz)
        if best is None or d < best[0]:
            best = (d, aa + t * (ba - aa), qx, qz)
    return best


def measure_nearest_leg(routes_doc, centre):
    """(distance, nearest_leg record) for the route point nearest a centre, measured on data/routes.json polylines.

    A tie (a town shared by two legs) goes to the first route in file order. None when either input is missing."""
    lines = _route_lines(routes_doc)
    if not lines or not isinstance(centre, dict) or not (_num(centre.get("x")) and _num(centre.get("z"))):
        return None
    best = None
    for r, pts, length in lines:
        d, along, qx, qz = _project(pts, centre["x"], centre["z"])
        if best is None or d < best[0] - 1e-9:
            best = (d, r, along, length, qx, qz)
    d, r, along, length, qx, qz = best
    return d, {"route_id": r.get("id"), "from": r.get("from_town"), "to": r.get("to_town"),
               "at_fraction": round(along / length, 3), "nearest_point": {"x": round(qx), "z": round(qz)}}


def _nearest_leg_problems(routes_doc, centre, recorded):
    """Why a recorded nearest_leg disagrees with data/routes.json, as a list of strings (empty when it agrees).

    A record agrees when its route is one of the nearest (within OFF_PATH_STALE_BLOCKS of the measured distance), its
    from/to are that route's towns, its nearest_point lies on that route at that distance, and its at_fraction puts
    the point where the nearest_point projects along the route."""
    m = measure_nearest_leg(routes_doc, centre)
    if m is None:
        return []
    dist, _ = m
    if not isinstance(recorded, dict):
        return ["has no nearest_leg record"]
    route = next(((r, pts, length) for r, pts, length in _route_lines(routes_doc) if r.get("id") == recorded.get("route_id")),
                 None)
    if route is None:
        return ["names route %r, which has no polyline in data/routes.json" % recorded.get("route_id")]
    r, pts, length = route
    out = []
    if (recorded.get("from"), recorded.get("to")) != (r.get("from_town"), r.get("to_town")):
        out.append("records %s->%s but %s runs %s->%s" % (recorded.get("from"), recorded.get("to"), r.get("id"),
                                                         r.get("from_town"), r.get("to_town")))
    d_route = _project(pts, centre["x"], centre["z"])[0]
    if d_route - dist > OFF_PATH_STALE_BLOCKS:
        out.append("names %s, %d blocks away, but the nearest leg is %d blocks away" % (r.get("id"), round(d_route), round(dist)))
        return out
    p = recorded.get("nearest_point") or {}
    frac = recorded.get("at_fraction")
    if not (_num(p.get("x")) and _num(p.get("z"))) or not _num(frac):
        return out + ["needs nearest_point x/z and a numeric at_fraction"]
    on_route, along, _, _ = _project(pts, p["x"], p["z"])
    if on_route > OFF_PATH_STALE_BLOCKS or abs(math.hypot(centre["x"] - p["x"], centre["z"] - p["z"]) - dist) > OFF_PATH_STALE_BLOCKS:
        m_point = _project(pts, centre["x"], centre["z"])
        out.append("nearest_point (%s, %s) is not the nearest point on %s; measured (%d, %d)"
                   % (p["x"], p["z"], r.get("id"), round(m_point[2]), round(m_point[3])))
    elif abs(frac * length - along) > NEAREST_LEG_ALONG_BLOCKS + 0.0005 * length:
        out.append("at_fraction %s puts the point %d blocks along %s, but nearest_point lies %d along (fraction %.3f)"
                   % (frac, round(frac * length), r.get("id"), round(along), along / length))
    return out


def measure_nearest_settlement(towns, town):
    """{id, distance_blocks} of the nearest other place in towns.json by centre distance, or None."""
    c = town.get("centre") or {}
    if not (_num(c.get("x")) and _num(c.get("z"))):
        return None
    best = None
    for o in towns:
        oc = o.get("centre") or {}
        if o is town or o.get("id") == town.get("id") or not (_num(oc.get("x")) and _num(oc.get("z"))):
            continue
        d = math.hypot(oc["x"] - c["x"], oc["z"] - c["z"])
        if best is None or d < best[0]:
            best = (d, o.get("id"))
    return None if best is None else {"id": best[1], "distance_blocks": round(best[0])}


def check_towns(ctx: Context):
    """Settlements: unique ids; exactly ten on the critical path (hometown, eight gym towns, the League) with
    unique orders; everything else off the path, ungated and named by no progression flag; footprints inside
    the border and around their centre; spacing between places."""
    rep = ctx.report
    f, towns = ctx.records("towns.json")
    if not f:
        return
    world = ctx.doc("world.json") or {}
    border = (world.get("export") or {}).get("border") or {}
    if not border:
        rep.skip("towns", "world.json has no export.border; town footprints were not checked against the border",
                 file=f.rel)
    seen, orders, counts = set(), set(), {}
    route_segments = _route_segments(ctx.doc("routes.json"))
    if route_segments is None:
        rep.skip("towns", "data/routes.json has no route polylines; off-path distances were read from their records, not measured",
                 file=f.rel)
    for t in towns:
        tid = t.get("id")
        line = f.line_of_id(tid)
        if tid in seen:
            rep.error("towns", 'duplicate town "%s"' % tid, file=f.rel, line=line, where=tid)
        seen.add(tid)
        role = t.get("role")
        critical = role in CRITICAL_ROLES
        counts[role] = counts.get(role, 0) + 1
        if bool(t.get("critical_path")) != critical:
            rep.error("towns", '"%s" (%s) has critical_path %s; only the hometown, gym towns and the League are on '
                      "the critical path" % (tid, role, t.get("critical_path")), file=f.rel, line=line, where=tid)
        if critical:
            if t.get("order") is None or t.get("order") in orders:
                rep.error("towns", 'critical town "%s" needs a unique order' % tid, file=f.rel, line=line, where=tid)
            orders.add(t.get("order"))
        else:
            if t.get("order") is not None:
                rep.error("towns", 'off-path "%s" must not have a route order' % tid, file=f.rel, line=line, where=tid)
            if t.get("gates"):
                rep.error("towns", 'off-path "%s" gates progression (%s)' % (tid, t.get("gates")),
                          file=f.rel, line=line, where=tid)
            lo, hi = OFF_PATH_RANGE_BY_KIND.get(t.get("kind"), OFF_PATH_RANGE.get(role, (250, None)))
            recorded = t.get("distance_from_critical_path_blocks")
            measured = _distance_to_routes(route_segments, t.get("centre"))
            d = measured if measured is not None else recorded
            if not isinstance(d, (int, float)) or isinstance(d, bool) or d < lo or (hi is not None and d > hi):
                rep.error("towns", '"%s" (%s) is %s blocks from the critical path (%s); expected %s'
                          % (tid, role, d, "measured on data/routes.json" if measured is not None else "recorded",
                             "%d-%d" % (lo, hi) if hi else "at least %d" % lo),
                          file=f.rel, line=line, where=tid)
            if measured is not None and (not isinstance(recorded, (int, float)) or abs(recorded - measured) > OFF_PATH_STALE_BLOCKS):
                rep.error("towns", '"%s" records distance_from_critical_path_blocks %s but measures %s on data/routes.json: the '
                          "record is stale" % (tid, recorded, measured), file=f.rel, line=line, where=tid)
            if measured is not None and "nearest_leg" in t:
                for why in _nearest_leg_problems(ctx.doc("routes.json"), t.get("centre"), t.get("nearest_leg")):
                    rep.error("towns", '"%s" nearest_leg is stale: %s (tools/measure_towns.py --write refreshes it)'
                              % (tid, why), file=f.rel, line=line, where=tid)
        if "nearest_settlement" in t:
            m = measure_nearest_settlement(towns, t)
            rec = t.get("nearest_settlement") or {}
            if m is not None and (rec.get("id") != m["id"] or not _num(rec.get("distance_blocks"))
                                  or abs(rec["distance_blocks"] - m["distance_blocks"]) > OFF_PATH_STALE_BLOCKS):
                rep.error("towns", '"%s" nearest_settlement is stale: records %s %s, measures %s %s (tools/measure_towns.py '
                          "--write refreshes it)" % (tid, rec.get("id"), rec.get("distance_blocks"), m["id"], m["distance_blocks"]),
                          file=f.rel, line=line, where=tid)
        fp, c = t.get("footprint") or {}, t.get("centre") or {}
        try:
            if not (fp["min_x"] <= c["x"] <= fp["max_x"] and fp["min_z"] <= c["z"] <= fp["max_z"]):
                rep.error("towns", 'town "%s" centre lies outside its footprint' % tid, file=f.rel, line=line, where=tid)
            if border and not (border["min_x"] <= fp["min_x"] and fp["max_x"] <= border["max_x"]
                               and border["min_z"] <= fp["min_z"] and fp["max_z"] <= border["max_z"]):
                rep.error("towns", 'town "%s" footprint crosses the world border' % tid, file=f.rel, line=line, where=tid)
        except (KeyError, TypeError):
            rep.error("towns", 'town "%s" needs centre x/z and footprint min/max x/z' % tid,
                      file=f.rel, line=line, where=tid)
    for role, n in CRITICAL_ROLES.items():
        if counts.get(role, 0) != n:
            rep.error("towns", "the critical path needs %d %s, found %d" % (n, role, counts.get(role, 0)), file=f.rel)
    placed = [t for t in towns if isinstance(t.get("centre"), dict)
              and all(isinstance(t["centre"].get(k), (int, float)) for k in ("x", "z"))]
    for i, a in enumerate(placed):
        for b in placed[i + 1:]:
            dist = math.hypot(a["centre"]["x"] - b["centre"]["x"], a["centre"]["z"] - b["centre"]["z"])
            need = SPACING["outpost"] if "outpost" in (a.get("role"), b.get("role")) else SPACING["settlement"]
            if dist < need:
                rep.error("towns", '"%s" and "%s" are %d blocks apart; at least %d' % (a.get("id"), b.get("id"), dist, need),
                          file=f.rel, line=f.line_of_id(b.get("id")), where=b.get("id"))
    prog = ctx.doc("progression.json") or {}
    critical_ids = {t.get("id") for t in towns if t.get("role") in CRITICAL_ROLES}
    for flag in prog.get("flags") or []:
        if not isinstance(flag, dict):
            continue
        town = (flag.get("waystone") or {}).get("town") if isinstance(flag.get("waystone"), dict) else None
        if town and town not in seen:
            rep.error("towns", 'progression flag "%s" names town "%s", which is not in towns.json'
                      % (flag.get("id"), town), file="data/progression.json", where=flag.get("id"))
        elif town and town not in critical_ids:
            rep.error("towns", 'progression flag "%s" names off-path "%s"; nothing off the path may be tied to '
                      "progression" % (flag.get("id"), town), file="data/progression.json", where=flag.get("id"))


FOLIAGE_SCHEMA = "cobblers.foliage/1"
FOLIAGE_LIBRARY = ("kits", "structures", "foliage", "library.json")    # relative to the data directory's parent
PAINT_MAPS = Path(__file__).resolve().parent / "paint_maps.py"          # PLANT_SETS, TERRAIN_CODES, WP_BIOMES
UNDERSTORY_ZONES = {"core", "mid", "edge"}
DEBRIS_ZONES = {"core", "any"}
SEEN_FROM_KINDS = {"legs", "ring", "points"}


def _num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _int(v):
    return isinstance(v, int) and not isinstance(v, bool)


def _paint_tables(path):
    """PLANT_SETS, TERRAIN_CODES and WP_BIOMES read from tools/paint_maps.py as literals, so this check stays
    standard-library only (importing paint_maps would pull in numpy and Pillow)."""
    import ast
    tree = ast.parse(Path(path).read_text(encoding="utf-8"))
    want = {"PLANT_SETS", "TERRAIN_CODES", "WP_BIOMES"}
    out = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name) \
                and node.targets[0].id in want:
            out[node.targets[0].id] = ast.literal_eval(node.value)
    missing = want - set(out)
    if missing:
        raise ValueError("no literal %s in %s" % (", ".join(sorted(missing)), path))
    return out


def _load_json_for(check, path, rel, rep):
    """DataFile or None; unreadable or invalid JSON is an ERROR under this check (fail closed)."""
    try:
        raw = path.read_text(encoding="utf-8")
        return DataFile(path, rel, raw, json.loads(raw))
    except (OSError, UnicodeDecodeError) as exc:
        rep.error(check, "cannot read file: %s" % exc, file=rel)
    except json.JSONDecodeError as exc:
        rep.error(check, "invalid JSON: %s" % exc.msg, file=rel, line=exc.lineno)
    return None


def check_foliage(ctx: Context):
    """Forest types, their object groups and the landmark trees (data/foliage.json) against the paint presets and
    sub-regions (data/regions.json), the object library (kits/structures/foliage/library.json, including each
    file's sha256), the plant sets, terrain codes and biomes tools/paint_maps.py knows, the world bounds, and the
    landmark-tree outposts in data/towns.json. A needed file that is absent makes that part SKIPPED; a present
    file that is malformed is an ERROR."""
    rep = ctx.report
    C = "foliage"
    rel = "data/foliage.json"
    path = ctx.data_dir / "foliage.json"
    if not path.is_file():
        rep.skip(C, "data/foliage.json is absent; forest types, object groups and landmark trees were not checked",
                 file=rel)
        return
    f = _load_json_for(C, path, rel, rep)
    if not f:
        return
    doc = f.doc
    if not isinstance(doc, dict):
        rep.error(C, "top level must be an object", file=rel, line=1)
        return

    def err(msg, key=None, where=None):
        rep.error(C, msg, file=rel, line=f.line_of_key(key) if key else None, where=where)

    if doc.get("schema") != FOLIAGE_SCHEMA:
        err('schema is "%s", expected "%s"' % (doc.get("schema"), FOLIAGE_SCHEMA), "schema")

    # tables from tools/paint_maps.py
    tables = None
    if not Path(PAINT_MAPS).is_file():
        rep.skip(C, "%s is absent; plant sets, floor terrains and biomes were not checked" % PAINT_MAPS, file=rel)
    else:
        try:
            tables = _paint_tables(PAINT_MAPS)
        except (SyntaxError, ValueError) as exc:
            rep.error(C, "cannot read the paint tables: %s" % exc, file=str(PAINT_MAPS))

    # density model
    dm = doc.get("density_model")
    if not isinstance(dm, dict):
        err("density_model must be an object", "density_model")
    else:
        noise = dm.get("noise")
        if not isinstance(noise, dict):
            err("density_model.noise must be an object", "noise")
        else:
            for k in ("ragged_scale", "glade_scale", "clump_scale"):
                if not _num(noise.get(k)) or noise[k] <= 0:
                    err("density_model.noise.%s must be a positive number, got %r" % (k, noise.get(k)), k)
        for k in ("water_clearance_blocks", "settlement_clearance_blocks"):
            if not _num(dm.get(k)) or dm[k] < 0:
                err("density_model.%s must be a number >= 0, got %r" % (k, dm.get(k)), k)

    # types
    types = doc.get("types")
    if not isinstance(types, dict) or not types:
        err("types must be a non-empty object", "types")
        types = {}
    groups_used = {}          # group -> first place it is referenced

    def use(group, where):
        if not isinstance(group, str) or not group:
            err("%s: group must be a non-empty string, got %r" % (where, group), where=where)
            return
        groups_used.setdefault(group, where)

    def unit(v):
        return _num(v) and 0 <= v <= 1

    for tid, t in types.items():
        w = "types.%s" % tid
        if not isinstance(t, dict):
            err("%s must be an object" % w, tid, tid)
            continue

        def terr(msg, t_id=tid):
            err("%s: %s" % ("types.%s" % t_id, msg), t_id, t_id)

        for k in ("identity", "from_inside"):
            if not isinstance(t.get(k), str) or not t[k].strip():
                terr("%s must be a non-empty string" % k)
        if not _num(t.get("stems_per_ha")) or t["stems_per_ha"] < 0:
            terr("stems_per_ha must be a number >= 0, got %r" % t.get("stems_per_ha"))
        for k in ("edge_width", "ragged"):
            if k in t and (not _num(t[k]) or t[k] < 0):
                terr("%s must be a number >= 0, got %r" % (k, t[k]))
        for k in ("glade_share", "clumping"):
            if k in t and not unit(t[k]):
                terr("%s must be between 0 and 1, got %r" % (k, t[k]))
        for k in ("slope_lo", "slope_hi"):
            if k in t and not _num(t[k]):
                terr("%s must be a number, got %r" % (k, t[k]))
        if _num(t.get("slope_lo", 20)) and _num(t.get("slope_hi", 34)) and t.get("slope_lo", 20) > t.get("slope_hi", 34):
            terr("slope_lo %s is above slope_hi %s" % (t.get("slope_lo", 20), t.get("slope_hi", 34)))
        if "open" in t and not isinstance(t["open"], bool):
            terr("open must be true or false")
        es = t.get("elevation_sort")
        if es is not None and not (isinstance(es, dict) and _num(es.get("radius")) and es["radius"] > 0
                                   and _num(es.get("span")) and es["span"] > 0):
            terr("elevation_sort needs a positive radius and span")
        classes = t.get("classes")
        if not isinstance(classes, list) or not classes:
            terr("classes must be a non-empty list")
            classes = []
        for i, c in enumerate(classes):
            cw = "%s.classes[%d]" % (w, i)
            if not isinstance(c, dict):
                err("%s must be an object" % cw, tid, tid)
                continue
            use(c.get("group"), cw)
            if not _num(c.get("spacing")) or c["spacing"] <= 0:
                err("%s: spacing must be a positive number, got %r" % (cw, c.get("spacing")), tid, tid)
            by_height = "low" in c or "high" in c
            by_edge = "core" in c or "edge" in c
            if es is not None and not by_height:
                err("%s: the type sorts classes by elevation, so the class needs low/high weights (core/edge are "
                    "ignored and it would never be placed)" % cw, tid, tid)
            if es is None and by_height:
                err("%s: low/high weights need the type's elevation_sort; without it they are ignored" % cw, tid, tid)
            if es is not None and by_edge:
                err("%s: core/edge weights are ignored when the type has elevation_sort" % cw, tid, tid)
            for k in ("core", "edge", "low", "high"):
                if k in c and (not _num(c[k]) or c[k] < 0):
                    err("%s: %s must be a number >= 0, got %r" % (cw, k, c[k]), tid, tid)
        lone = t.get("lone")
        if lone is not None:
            if not isinstance(lone, dict):
                terr("lone must be an object")
            else:
                if not _num(lone.get("per_ha")) or lone["per_ha"] < 0:
                    terr("lone.per_ha must be a number >= 0")
                if not _num(lone.get("reach")) or lone["reach"] <= 0:
                    terr("lone.reach must be a positive number")
                if not isinstance(lone.get("groups"), list) or not lone["groups"]:
                    terr("lone.groups must be a non-empty list")
                else:
                    for g in lone["groups"]:
                        use(g, "%s.lone" % w)
                if t.get("open"):
                    rep.warn(C, "%s: lone trees are never placed for an open type" % w, file=rel,
                             line=f.line_of_key(tid), where=tid)
        debris = t.get("debris")
        if debris is not None and not isinstance(debris, list):
            terr("debris must be a list")
            debris = []
        for i, db in enumerate(debris or []):
            dw = "%s.debris[%d]" % (w, i)
            if not isinstance(db, dict):
                err("%s must be an object" % dw, tid, tid)
                continue
            use(db.get("group"), dw)
            if not _num(db.get("per_ha")) or db["per_ha"] < 0:
                err("%s: per_ha must be a number >= 0, got %r" % (dw, db.get("per_ha")), tid, tid)
            if db.get("zone") not in DEBRIS_ZONES:
                err("%s: zone %r is not one of %s" % (dw, db.get("zone"), ", ".join(sorted(DEBRIS_ZONES))), tid, tid)
            if "max_slope" in db and not _num(db["max_slope"]):
                err("%s: max_slope must be a number" % dw, tid, tid)
            if "vertical_offset" in db and not _int(db["vertical_offset"]):
                err("%s: vertical_offset must be an integer" % dw, tid, tid)
        fl = t.get("floor")
        if fl is not None:
            mix = fl.get("mix") if isinstance(fl, dict) else None
            if not isinstance(fl, dict) or not unit(fl.get("threshold")) or not isinstance(mix, list) or not mix:
                terr("floor needs a threshold between 0 and 1 and a non-empty mix")
            else:
                shares = []
                for entry in mix:
                    if not (isinstance(entry, list) and len(entry) == 2 and isinstance(entry[0], str) and unit(entry[1])):
                        terr("floor.mix entry %r must be [TERRAIN, share between 0 and 1]" % (entry,))
                        continue
                    shares.append(entry[1])
                    if tables and entry[0] not in tables["TERRAIN_CODES"]:
                        terr("floor terrain %s is not in tools/paint_maps.py TERRAIN_CODES" % entry[0])
                if shares and len(shares) == len(mix) and abs(sum(shares) - 1.0) > 1e-6:
                    terr("floor.mix shares sum to %s, not 1 (the last terrain silently takes the difference)"
                         % round(sum(shares), 6))
        us = t.get("understory")
        if us is not None:
            if not isinstance(us, dict):
                terr("understory must be an object")
            else:
                for zone, z in us.items():
                    if zone not in UNDERSTORY_ZONES:
                        terr("understory zone %s is not one of %s" % (zone, ", ".join(sorted(UNDERSTORY_ZONES))))
                        continue
                    if not isinstance(z, dict) or not isinstance(z.get("set"), str) or not unit(z.get("coverage")):
                        terr("understory.%s needs a plant set name and a coverage between 0 and 1" % zone)
                        continue
                    if "clear" in z and not isinstance(z["clear"], bool):
                        terr("understory.%s.clear must be true or false" % zone)
                    if tables and z["set"] not in tables["PLANT_SETS"]:
                        terr("understory.%s plant set %s is not in tools/paint_maps.py PLANT_SETS" % (zone, z["set"]))
        if "biome" in t:
            if not isinstance(t["biome"], str):
                terr("biome must be a string")
            elif tables and t["biome"] not in tables["WP_BIOMES"]:
                terr("biome %s is not in tools/paint_maps.py WP_BIOMES" % t["biome"])
        wb = t.get("water_boost")
        if wb is not None and not (isinstance(wb, dict) and _num(wb.get("factor")) and wb["factor"] > 0
                                   and _num(wb.get("reach")) and wb["reach"] > 0):
            terr("water_boost needs a positive factor and reach")

    # preset_defaults and assign against data/regions.json
    pdefs = doc.get("preset_defaults")
    if not isinstance(pdefs, dict):
        err("preset_defaults must be an object", "preset_defaults")
        pdefs = {}
    assign = doc.get("assign")
    if not isinstance(assign, dict):
        err("assign must be an object", "assign")
        assign = {}
    for preset, tid in pdefs.items():
        if tid not in types:
            err('preset_defaults.%s names type "%s", which is not defined' % (preset, tid), preset, preset)
    for sid, a in assign.items():
        if not isinstance(a, dict):
            err("assign.%s must be an object" % sid, sid, sid)
            continue
        if a.get("type") not in types:
            err('assign.%s names type "%s", which is not defined' % (sid, a.get("type")), sid, sid)
        if "density_scale" in a and (not _num(a["density_scale"]) or a["density_scale"] < 0):
            err("assign.%s.density_scale must be a number >= 0" % sid, sid, sid)
    reg_path = ctx.data_dir / "regions.json"
    if not reg_path.is_file():
        rep.skip(C, "data/regions.json is absent; preset_defaults and assign keys were not checked", file=rel)
    else:
        rf = _load_json_for(C, reg_path, "data/regions.json", rep)
        if rf:
            presets = set((rf.doc.get("paint_presets") or {}) if isinstance(rf.doc, dict) else {})
            subs = {s.get("id") for s in (rf.doc.get("subregions") or []) if isinstance(s, dict)} \
                if isinstance(rf.doc, dict) else set()
            for preset in pdefs:
                if preset not in presets:
                    err('preset_defaults key "%s" is not a paint preset in data/regions.json' % preset, preset, preset)
            for sid in assign:
                if sid not in subs:
                    err('assign key "%s" is not a sub-region in data/regions.json' % sid, sid, sid)

    # landmark trees
    lts = doc.get("landmark_trees", [])
    if not isinstance(lts, list):
        err("landmark_trees must be a list", "landmark_trees")
        lts = []
    lt_ids, bad_sites = {}, set()
    for i, lt in enumerate(lts):
        if not isinstance(lt, dict):
            err("landmark_trees[%d] must be an object" % i, "landmark_trees")
            continue
        lid = lt.get("id")
        lw = "landmark_trees.%s" % lid
        line_id = f.line_of_id(lid)
        if not isinstance(lid, str) or not lid:
            err("landmark_trees[%d] needs an id" % i, "landmark_trees")
            continue
        if lid in lt_ids:
            rep.error(C, 'duplicate landmark tree "%s"' % lid, file=rel, line=line_id, where=lid)
        lt_ids[lid] = lt
        if not isinstance(lt.get("object"), str) or not lt["object"]:
            rep.error(C, "%s needs an object name" % lw, file=rel, line=line_id, where=lid)
        site = lt.get("site")
        if not (isinstance(site, list) and len(site) == 2 and all(_int(v) for v in site)):
            rep.error(C, "%s site must be [x, z] integers, got %r" % (lw, site), file=rel, line=line_id, where=lid)
            bad_sites.add(lid)
        if not _num(lt.get("glade_radius")) or lt["glade_radius"] <= 0:
            rep.error(C, "%s glade_radius must be a positive number" % lw, file=rel, line=line_id, where=lid)
        if not isinstance(lt.get("kind"), str) or not lt["kind"]:
            rep.error(C, "%s needs a kind" % lw, file=rel, line=line_id, where=lid)
        seen = lt.get("seen_from")
        if lt.get("landmark", True) is False:
            # a demoted giant: still painted with its glade, but no landmark, no outpost, no viewpoint claim
            if seen:
                rep.error(C, "%s has landmark false, so it makes no seen_from claim" % lw, file=rel, line=line_id, where=lid)
            if not isinstance(lt.get("demoted"), dict) or not lt["demoted"].get("why"):
                rep.error(C, "%s has landmark false and needs a demoted record with a why" % lw, file=rel, line=line_id,
                          where=lid)
            seen = []
        elif not isinstance(seen, list) or not seen:
            rep.error(C, "%s seen_from must be a non-empty list" % lw, file=rel, line=line_id, where=lid)
            seen = []
        for o in seen:
            kind = o.get("kind") if isinstance(o, dict) else None
            if kind not in SEEN_FROM_KINDS:
                rep.error(C, "%s seen_from kind %r is not one of %s" % (lw, kind, ", ".join(sorted(SEEN_FROM_KINDS))),
                          file=rel, line=line_id, where=lid)
            elif kind == "legs" and not (isinstance(o.get("legs"), list) and o["legs"]
                                         and all(isinstance(x, str) and "->" in x for x in o["legs"])):
                rep.error(C, '%s seen_from legs needs a non-empty list of "from->to" names' % lw,
                          file=rel, line=line_id, where=lid)
            elif kind == "ring" and not (_num(o.get("radius")) and o["radius"] > 0):
                rep.error(C, "%s seen_from ring needs a positive radius" % lw, file=rel, line=line_id, where=lid)
            elif kind == "points" and not (isinstance(o.get("points"), list) and o["points"] and all(
                    isinstance(p, list) and len(p) == 2 and all(_num(v) for v in p) for p in o["points"])):
                rep.error(C, "%s seen_from points needs a non-empty list of [x, z]" % lw,
                          file=rel, line=line_id, where=lid)

    # object library: every referenced group and landmark object exists; every row's file matches its sha256
    lib_path = ctx.data_dir.parent.joinpath(*FOLIAGE_LIBRARY)
    lib_rel = "/".join(FOLIAGE_LIBRARY)
    n_objects = 0
    if not lib_path.is_file():
        rep.skip(C, "%s is absent; object groups, landmark objects and object hashes were not checked" % lib_rel,
                 file=rel)
    else:
        lf = _load_json_for(C, lib_path, lib_rel, rep)
        rows = lf.doc.get("objects") if lf and isinstance(lf.doc, dict) else None
        if lf and not isinstance(rows, list):
            rep.error(C, "the library has no objects list", file=lib_rel)
        if isinstance(rows, list):
            groups, names = set(), set()
            for r in rows:
                if not isinstance(r, dict) or not isinstance(r.get("name"), str) or not isinstance(r.get("group"), str):
                    rep.error(C, "library row %r needs a name and a group" % (r,), file=lib_rel)
                    continue
                n_objects += 1
                names.add(r["name"])
                groups.add(r["group"])
                if not _int(r.get("ground_radius")) or r["ground_radius"] < 0:
                    rep.error(C, 'library object "%s" needs ground_radius as an integer >= 0 (placement keeps that '
                              "square of ground clear), got %r; rerun tools/foliage_objects.py index"
                              % (r["name"], r.get("ground_radius")),
                              file=lib_rel, line=lf.line_of_id(r["name"]), where=r["name"])
                fn = r.get("file")
                if not isinstance(fn, str) or not fn or Path(fn).name != fn:
                    rep.error(C, 'library object "%s" file must be a bare file name, got %r' % (r["name"], fn),
                              file=lib_rel, line=lf.line_of_id(r["name"]), where=r["name"])
                    continue
                obj = lib_path.parent / fn
                if not obj.is_file():
                    rep.error(C, 'library object "%s" file %s is missing' % (r["name"], fn),
                              file=lib_rel, line=lf.line_of_id(r["name"]), where=r["name"])
                    continue
                actual = hashlib.sha256(obj.read_bytes()).hexdigest()
                if r.get("sha256") != actual:
                    rep.error(C, 'library object "%s" sha256 is %s but %s hashes to %s; rerun tools/foliage_objects.py '
                              "index" % (r["name"], r.get("sha256"), fn, actual),
                              file=lib_rel, line=lf.line_of_id(r["name"]), where=r["name"])
            for g, where in sorted(groups_used.items()):
                if g not in groups:
                    err('%s uses object group "%s", which has no objects in %s' % (where, g, lib_rel),
                        where.split(".")[1] if where.startswith("types.") else None, g)
            for lid, lt in lt_ids.items():
                obj = lt.get("object")
                if isinstance(obj, str) and obj and (obj not in names or obj not in groups):
                    rep.error(C, 'landmark tree "%s" object "%s" must be both an object name and a group in %s '
                              "(placement keys it by group, the sightline check by name)" % (lid, obj, lib_rel),
                              file=rel, line=f.line_of_id(lid), where=lid)

    # sites inside the world bounds
    world = ctx.doc("world.json")
    if world is None and (ctx.data_dir / "world.json").is_file():
        wf = _load_json_for(C, ctx.data_dir / "world.json", "data/world.json", rep)
        world = wf.doc if wf else None
    bounds = (world or {}).get("bounds") if isinstance(world, dict) else None
    if not (isinstance(bounds, dict) and all(_num(bounds.get(k)) for k in ("min_x", "min_z", "max_x", "max_z"))):
        rep.skip(C, "data/world.json has no bounds; landmark tree sites were not checked against the map", file=rel)
    else:
        for lid, lt in lt_ids.items():
            if lid in bad_sites:
                continue
            x, z = lt["site"]
            if not (bounds["min_x"] <= x <= bounds["max_x"] and bounds["min_z"] <= z <= bounds["max_z"]):
                rep.error(C, 'landmark tree "%s" site (%s, %s) is outside the world bounds' % (lid, x, z),
                          file=rel, line=f.line_of_id(lid), where=lid)

    # landmark trees <-> data/towns.json outposts with kind landmark_tree; leg names name consecutive critical towns
    towns_path = ctx.data_dir / "towns.json"
    if not towns_path.is_file():
        rep.skip(C, "data/towns.json is absent; landmark trees were not paired with outposts", file=rel)
    else:
        tf = _load_json_for(C, towns_path, "data/towns.json", rep)
        towns = [t for t in ((tf.doc.get("towns") or []) if tf and isinstance(tf.doc, dict) else [])
                 if isinstance(t, dict)]
        if tf:
            by_id = {t.get("id"): t for t in towns}
            for lid, lt in lt_ids.items():
                t = by_id.get(lid)
                line = f.line_of_id(lid)
                if lt.get("landmark", True) is False:
                    if t is not None:
                        rep.error(C, 'demoted tree "%s" (landmark false) must not be a place in data/towns.json' % lid,
                                  file=rel, line=line, where=lid)
                    continue
                if t is None:
                    rep.error(C, 'landmark tree "%s" has no outpost in data/towns.json' % lid, file=rel, line=line,
                              where=lid)
                    continue
                if t.get("role") != "outpost" or t.get("kind") != "landmark_tree":
                    rep.error(C, 'data/towns.json "%s" must be role outpost with kind landmark_tree (is %s / %s)'
                              % (lid, t.get("role"), t.get("kind")), file=rel, line=line, where=lid)
                c = t.get("centre") or {}
                if lid not in bad_sites and [c.get("x"), c.get("z")] != list(lt["site"]):
                    rep.error(C, 'landmark tree "%s" site %s is not its outpost centre (%s, %s)'
                              % (lid, lt["site"], c.get("x"), c.get("z")), file=rel, line=line, where=lid)
            for t in towns:
                if t.get("kind") == "landmark_tree" and t.get("id") not in lt_ids:
                    rep.error(C, 'data/towns.json "%s" is a landmark_tree outpost with no entry in landmark_trees'
                              % t.get("id"), file="data/towns.json", where=t.get("id"))
            crit = sorted([t for t in towns if t.get("tier") == "critical" and _num(t.get("order"))],
                          key=lambda t: t["order"])
            legs = {"%s->%s" % (a.get("id"), b.get("id")) for a, b in zip(crit, crit[1:])}
            for lid, lt in lt_ids.items():
                for o in lt.get("seen_from") or []:
                    if isinstance(o, dict) and o.get("kind") == "legs" and isinstance(o.get("legs"), list):
                        for name in o["legs"]:
                            if name not in legs:
                                rep.error(C, 'landmark tree "%s" is seen from leg "%s", which is not a pair of '
                                          "consecutive critical towns" % (lid, name),
                                          file=rel, line=f.line_of_id(lid), where=lid)

    rep.info(C, "checked %d forest types, %d object groups, %d library objects and %d landmark trees"
             % (len(types), len(groups_used), n_objects, len(lt_ids)), file=rel)


SCULPT_SCHEMA = "cobblers.sculpt/1"
COAST_CLASSES = ("beach", "estuary", "shore", "rocky", "cliff")
CONE_FORMS = {"stratovolcano", "lava_dome", "cinder_cone", "caldera"}
# what tools/sculpt.py reads, and the constraint that keeps its arithmetic finite: "num" any number, "pos" > 0,
# "nonneg" >= 0, "unit" in [0, 1], "range" [lo, hi] with lo <= hi, "range_pos" with 0 < lo <= hi, "range_open"
# with lo < hi (passed to a smoothstep, which divides by hi - lo), "int_nonneg"
SCULPT_PROTECT = {"settlement_margin_blocks": "nonneg", "landmark_tree_margin_blocks": "nonneg",
                  "river_margin_blocks": "nonneg", "lake_margin_blocks": "nonneg", "feather_blocks": "pos",
                  "terrain_feather_blocks": "pos"}
SCULPT_COAST = {"band_blocks": "pos", "spacing_blocks": "pos", "concavity_radius_blocks": "pos",
                "fetch_cap_blocks": "pos", "estuary_mouth_radius_blocks": "nonneg",
                "class_smoothing_radius_blocks": "nonneg", "micro_relief_scale_blocks": "pos"}
_BEACHLIKE = {"grade": "range_pos", "berm_blocks": "range", "top_above_sea": "range", "back_blocks": "range_pos",
              "shelf_grade": "range_pos", "shelf_depth": "range", "micro_relief": "nonneg"}
SCULPT_CLASS_KEYS = {
    "beach": _BEACHLIKE,
    "estuary": _BEACHLIKE,
    "shore": {k: v for k, v in _BEACHLIKE.items() if k != "berm_blocks"},
    "rocky": {"bank_grade": "pos", "bank_top_above_sea": "num", "back_blocks": "pos", "drop_grade": "pos",
              "drop_depth": "nonneg", "rugged": "nonneg", "micro_relief": "nonneg"},
    "cliff": {"height": "range", "relief_share": "nonneg", "face_blocks": "range_open", "back_blocks": "range_open",
              "talus_blocks": "pos", "drop_grade": "pos", "drop_depth": "nonneg", "micro_relief": "nonneg"},
}
SCULPT_MASSIF = {"steep_faces_deg": "num", "shift_blocks": "nonneg", "shift_taper_blocks": "pos", "shift_from_y": "num"}
SCULPT_SUMMITS = {"rise": "nonneg", "ridge_scale_blocks": "pos", "secondary_cap": "unit"}
SCULPT_STRATA = {"from_y": "num", "cliff_slope_deg": "num", "cliff_band": "range_pos", "cliff_strength": "nonneg",
                 "bench_slope_deg": "range", "bench_band": "range_pos", "bench_strength": "nonneg"}
SCULPT_VOLCANO = {"steep_faces_deg": "num", "shift_blocks": "nonneg", "shift_taper_blocks": "pos", "shift_from_y": "num"}
SCULPT_CONE = {
    "stratovolcano": {"crater_radius": "pos", "crater_floor_y": "num", "rim_y": "num", "rim_width": "nonneg",
                      "flank_to_radius": "pos", "flank_drop": "num", "breach_bearing_deg": "num",
                      "breach_half_angle_deg": "pos", "breach_floor_y": "num", "breach_grade": "nonneg"},
    "lava_dome": {"dome_radius": "pos", "dome_top_y": "num", "dome_drop": "num", "spines": "int_nonneg",
                  "spine_radius": "pos"},
    "cinder_cone": {"top_y": "num", "slope": "nonneg", "radius": "pos", "crater_radius": "pos",
                    "crater_floor_y": "num", "strength": "unit", "plain_y": "num"},
    "caldera": {"floor_radius": "pos", "floor_y": "num", "wall_to_radius": "pos", "rim_to_radius": "pos",
                "rim_y": "num", "rim_noise": "nonneg", "flank_to_radius": "pos", "flank_grade": "nonneg"},
}


def _kind_ok(v, kind):
    if kind == "num":
        return _num(v)
    if kind == "pos":
        return _num(v) and v > 0
    if kind == "nonneg":
        return _num(v) and v >= 0
    if kind == "unit":
        return _num(v) and 0 <= v <= 1
    if kind == "int_nonneg":
        return _int(v) and v >= 0
    if kind == "int_pos":
        return _int(v) and v >= 1
    if kind == "int_two":
        return _int(v) and v >= 2
    if not (isinstance(v, list) and len(v) == 2 and all(_num(x) for x in v)):
        return False
    lo, hi = v
    return {"range": lo <= hi, "range_pos": 0 < lo <= hi, "range_open": lo < hi}[kind]


_KIND_TEXT = {"num": "a number", "pos": "a number > 0", "nonneg": "a number >= 0", "unit": "a number in [0, 1]",
              "int_nonneg": "an integer >= 0", "int_pos": "an integer >= 1", "int_two": "an integer >= 2",
              "range": "[lo, hi] with lo <= hi", "range_pos": "[lo, hi] with 0 < lo <= hi",
              "range_open": "[lo, hi] with lo < hi"}
# hillside relief (tools/sculpt.py sculpt_relief): smooth(sigma) and the fall-line average need positive sizes and at
# least two taps; the soft clip divides by its sigma; both fades and the protection feather are smoothsteps
SCULPT_RELIEF = {"regional_sigma_blocks": "pos", "fall_line_stretch_blocks": "nonneg", "fall_line_taps": "int_two",
                 "amplitude_per_grade": "nonneg", "max_amplitude_blocks": "nonneg", "noise_soft_clip_sigma": "pos",
                 "low_fade_above_sea": "range_open", "steep_fade_grade": "range_open", "protect_feather_blocks": "pos"}
SCULPT_RELIEF_OCTAVE = {"spacing_blocks": "int_pos", "weight": "nonneg"}


def check_sculpt(ctx: Context):
    """The terrain sculpt stage: data/sculpt.json essentials and references (regions, sub-regions, pad sites, world
    bounds), and the import chain in world.json (heightmap.sculpted_from is the river cut recorded in rivers.json and
    is not the imported file). A needed file that is absent makes that part SKIPPED; a present file that is malformed
    or inconsistent is an ERROR."""
    rep = ctx.report
    C = "sculpt"
    rel = "data/sculpt.json"
    path = ctx.data_dir / "sculpt.json"
    world = ctx.doc("world.json")
    hm = (world or {}).get("heightmap") if isinstance(world, dict) else None
    hm = hm if isinstance(hm, dict) else {}
    if not path.is_file():
        if hm.get("sculpted_from") is not None:
            rep.error(C, "world.json heightmap.sculpted_from records a sculpt but data/sculpt.json is absent",
                      file="data/world.json")
        rep.skip(C, "data/sculpt.json is absent; the sculpt configuration was not checked", file=rel)
        return
    f = _load_json_for(C, path, rel, rep)
    if not f:
        return
    doc = f.doc
    if not isinstance(doc, dict):
        rep.error(C, "top level must be an object", file=rel, line=1)
        return

    def err(msg, key=None, where=None):
        rep.error(C, msg, file=rel, line=f.line_of_key(key) if key else None, where=where)

    def need(obj, spec, where, key_for_line=None):
        if not isinstance(obj, dict):
            err("%s must be an object" % where, key_for_line)
            return False
        ok = True
        for k, kind in spec.items():
            if not _kind_ok(obj.get(k), kind):
                err("%s.%s must be %s, got %r" % (where, k, _KIND_TEXT[kind], obj.get(k)), key_for_line or k, where)
                ok = False
        return ok

    if doc.get("schema") != SCULPT_SCHEMA:
        err('schema is "%s", expected "%s"' % (doc.get("schema"), SCULPT_SCHEMA), "schema")
    wind = doc.get("prevailing_wind_from_deg")
    if not (_num(wind) and 0 <= wind < 360):
        err("prevailing_wind_from_deg must be a bearing in [0, 360), got %r" % (wind,), "prevailing_wind_from_deg")
    need(doc.get("protect"), SCULPT_PROTECT, "protect", "protect")

    # the import chain in world.json
    sf = hm.get("sculpted_from")
    if world is None:
        rep.skip(C, "data/world.json is absent or unreadable; heightmap.sculpted_from was not checked", file=rel)
    elif sf is None:
        rep.error(C, "data/sculpt.json exists but world.json heightmap.sculpted_from is absent, so the import does not "
                  "record which river cut it was sculpted from", file="data/world.json")
    elif not isinstance(sf, dict) or not isinstance(sf.get("path"), str) or not sf["path"] \
            or not (isinstance(sf.get("sha256"), str) and len(sf["sha256"]) == 64):
        rep.error(C, "world.json heightmap.sculpted_from needs a path and a 64-hex sha256", file="data/world.json")
    else:
        if sf["path"] == hm.get("path"):
            rep.error(C, "world.json heightmap.path %s is also its sculpted_from path: the sculpt must write a new "
                      "file, not overwrite the river cut" % sf["path"], file="data/world.json")
        if sf["sha256"] == hm.get("sha256"):
            rep.warn(C, "world.json heightmap.sha256 equals sculpted_from.sha256: the sculpt changed nothing",
                     file="data/world.json")
        riv = ctx.data_dir / "rivers.json"
        if not riv.is_file():
            rep.skip(C, "data/rivers.json is absent; sculpted_from was not compared with the river cut", file=rel)
        else:
            rf = _load_json_for(C, riv, "data/rivers.json", rep)
            out = ((rf.doc.get("cut") or {}).get("output") or {}) if rf and isinstance(rf.doc, dict) else {}
            if rf and out.get("sha256") != sf["sha256"]:
                rep.error(C, "world.json heightmap.sculpted_from.sha256 %s is not the river cut output %s in "
                          "data/rivers.json" % (sf["sha256"][:12], (out.get("sha256") or "")[:12]),
                          file="data/world.json")
            if rf and out.get("path") and out["path"] != sf["path"]:
                rep.error(C, "world.json heightmap.sculpted_from.path %s is not the river cut output path %s"
                          % (sf["path"], out["path"]), file="data/world.json")

    # coast
    coast = doc.get("coast")
    hard, soft = [], []
    if need(coast, SCULPT_COAST, "coast", "coast"):
        for key in ("hard_regions", "soft_regions"):
            v = coast.get(key)
            if not (isinstance(v, list) and all(isinstance(x, str) for x in v)):
                err("coast.%s must be a list of region ids" % key, key)
            else:
                (hard if key == "hard_regions" else soft).extend(v)
        for rid in sorted(set(hard) & set(soft)):
            err('region "%s" is both a hard and a soft coast region' % rid, "soft_regions", rid)
        classes = coast.get("classes")
        if not isinstance(classes, dict) or set(classes) != set(COAST_CLASSES):
            err("coast.classes must define exactly %s, got %s"
                % (", ".join(COAST_CLASSES), sorted(classes) if isinstance(classes, dict) else classes), "classes")
        else:
            for cls in COAST_CLASSES:
                need(classes[cls], SCULPT_CLASS_KEYS[cls], "coast.classes.%s" % cls, cls)
    elif isinstance(coast, dict):
        for key in ("hard_regions", "soft_regions"):
            if isinstance(coast.get(key), list):
                (hard if key == "hard_regions" else soft).extend(x for x in coast[key] if isinstance(x, str))

    # massifs
    massifs = doc.get("massifs")
    if not isinstance(massifs, list):
        err("massifs must be a list", "massifs")
        massifs = []
    points = []               # (where, [x, z]) to place inside the world bounds
    sub_refs = []             # (massif id, sub-region id)
    seen = set()
    for i, m in enumerate(massifs):
        mid = m.get("id") if isinstance(m, dict) else None
        w = "massifs.%s" % (mid or i)
        if not isinstance(mid, str) or not mid:
            err("massifs[%d] needs an id" % i, "massifs")
        elif mid in seen:
            err('duplicate massif "%s"' % mid, None, mid)
        seen.add(mid)
        if not need(m, SCULPT_MASSIF, w, mid):
            if not isinstance(m, dict):
                continue
        subs = m.get("subregions")
        if not (isinstance(subs, list) and subs and all(isinstance(s, str) for s in subs)):
            err("%s.subregions must be a non-empty list of sub-region ids" % w, mid, mid)
        else:
            sub_refs.extend((w, s) for s in subs)
        s = m.get("summits")
        if need(s, SCULPT_SUMMITS, w + ".summits", mid):
            hi = s.get("highest")
            if not (isinstance(hi, list) and len(hi) == 2 and all(_num(v) for v in hi)):
                err("%s.summits.highest must be [x, z], got %r" % (w, hi), mid, mid)
            else:
                points.append(("%s.summits.highest" % w, hi))
        need(m.get("strata"), SCULPT_STRATA, w + ".strata", mid)

    # volcano
    v = doc.get("volcano")
    if need(v, SCULPT_VOLCANO, "volcano", "volcano"):
        cones = v.get("cones")
        if not isinstance(cones, list) or not cones:
            err("volcano.cones must be a non-empty list (tools/sculpt.py run boxes the volcano from its cones)", "cones")
            cones = []
        cone_ids = set()
        for i, c in enumerate(cones):
            cid = c.get("id") if isinstance(c, dict) else None
            w = "volcano.cones.%s" % (cid or i)
            if not isinstance(c, dict):
                err("%s must be an object" % w, "cones")
                continue
            if not isinstance(cid, str) or not cid:
                err("volcano.cones[%d] needs an id" % i, "cones")
            elif cid in cone_ids:
                err('duplicate cone "%s"' % cid, None, cid)
            cone_ids.add(cid)
            ctr = c.get("centre")
            if not (isinstance(ctr, list) and len(ctr) == 2 and all(_num(x) for x in ctr)):
                err("%s.centre must be [x, z], got %r" % (w, ctr), cid, cid)
            else:
                points.append(("%s.centre" % w, ctr))
            form = c.get("form")
            if form not in CONE_FORMS:
                err("%s.form %r is not one of %s" % (w, form, ", ".join(sorted(CONE_FORMS))), cid, cid)
                continue
            if not need(c, SCULPT_CONE[form], w, cid):
                continue
            if form == "stratovolcano" and not c["flank_to_radius"] > c["crater_radius"] + c["rim_width"]:
                err("%s: flank_to_radius must exceed crater_radius + rim_width" % w, cid, cid)
            if form == "cinder_cone" and not c["crater_radius"] < c["radius"]:
                err("%s: crater_radius must be below radius" % w, cid, cid)
            if form == "caldera" and not (c["floor_radius"] < c["wall_to_radius"] <= c["rim_to_radius"]
                                          <= c["flank_to_radius"]):
                err("%s: radii must satisfy floor_radius < wall_to_radius <= rim_to_radius <= flank_to_radius" % w,
                    cid, cid)

    # hillside relief (optional: tools/sculpt.py run applies it only when the block is present)
    relief = doc.get("relief")
    if relief is not None and need(relief, SCULPT_RELIEF, "relief", "relief"):
        octaves = relief.get("octaves")
        if not isinstance(octaves, list) or not octaves:
            err("relief.octaves must be a non-empty list", "octaves")
        else:
            for i, o in enumerate(octaves):
                need(o, SCULPT_RELIEF_OCTAVE, "relief.octaves[%d]" % i, "octaves")
            if all(isinstance(o, dict) and _num(o.get("weight")) for o in octaves) \
                    and not any(o["weight"] > 0 for o in octaves):
                err("relief.octaves weights are all 0: the relief noise would be zero", "octaves")
        lo = relief.get("low_fade_above_sea")
        if _kind_ok(lo, "range_open") and lo[0] < 0:
            err("relief.low_fade_above_sea must start at or above sea level, got %r" % (lo,), "low_fade_above_sea")
        st = relief.get("steep_fade_grade")
        if _kind_ok(st, "range_open") and st[0] <= 0:
            err("relief.steep_fade_grade must be above grade 0, got %r" % (st,), "steep_fade_grade")

    # pads
    pads = doc.get("pads", [])
    if not isinstance(pads, list):
        err("pads must be a list", "pads")
        pads = []
    pad_sites = []
    for i, pd in enumerate(pads):
        w = "pads[%d]" % i
        if not isinstance(pd, dict) or not isinstance(pd.get("site"), str) or not pd["site"]:
            err("%s needs a site (a data/towns.json id)" % w, "pads")
            continue
        # a pad is either pre-rescale (y, pressed by sculpt.py and carried through the rescale by press_pads.py) or
        # post-rescale (pressed_y, pressed only by press_pads.py); exactly one of the two
        level_key = "pressed_y" if pd.get("pressed_y") is not None else "y"
        if pd.get("pressed_y") is not None and pd.get("y") is not None:
            err("pads.%s has both y and pressed_y; a pad is either pre-rescale (y) or post-rescale (pressed_y)" % pd["site"], pd["site"], pd["site"])
        need(pd, {level_key: "num", "radius": "nonneg", "feather": "pos"}, "pads.%s" % pd["site"], pd["site"])
        if pd["site"] in pad_sites:
            err('pad site "%s" is listed twice' % pd["site"], None, pd["site"])
        pad_sites.append(pd["site"])
        imp = (world or {}).get("import") if isinstance(world, dict) else None
        if isinstance(imp, dict) and _num(pd.get(level_key)) and _num(imp.get("low_out")) and _num(imp.get("high_out")) \
                and not imp["low_out"] <= pd[level_key] <= imp["high_out"]:
            err("pads.%s.%s %s is outside the import range %s..%s" % (pd["site"], level_key, pd[level_key], imp["low_out"],
                                                                      imp["high_out"]), pd["site"], pd["site"])

    # references: regions and sub-regions
    reg_path = ctx.data_dir / "regions.json"
    if not reg_path.is_file():
        rep.skip(C, "data/regions.json is absent; coast regions and massif sub-regions were not checked", file=rel)
    else:
        rf = _load_json_for(C, reg_path, "data/regions.json", rep)
        if rf and isinstance(rf.doc, dict):
            region_ids = {r.get("id") for r in rf.doc.get("regions") or [] if isinstance(r, dict)}
            sub_ids = {s.get("id") for s in rf.doc.get("subregions") or [] if isinstance(s, dict)}
            for key, ids in (("hard_regions", hard), ("soft_regions", soft)):
                for rid in ids:
                    if rid not in region_ids:
                        err('coast.%s names "%s", which is not a region in data/regions.json' % (key, rid), key, rid)
            for w, sid in sub_refs:
                if sid not in sub_ids:
                    err('%s.subregions names "%s", which is not a sub-region in data/regions.json' % (w, sid),
                        sid, sid)

    # references: pad sites
    towns_path = ctx.data_dir / "towns.json"
    if not towns_path.is_file():
        if pad_sites:
            rep.skip(C, "data/towns.json is absent; pad sites were not checked", file=rel)
    else:
        tf = _load_json_for(C, towns_path, "data/towns.json", rep)
        if tf and isinstance(tf.doc, dict):
            by_id = {t.get("id"): t for t in tf.doc.get("towns") or [] if isinstance(t, dict)}
            for site in pad_sites:
                t = by_id.get(site)
                if t is None:
                    err('pad site "%s" is not in data/towns.json' % site, site, site)
                elif not (isinstance(t.get("centre"), dict) and _num(t["centre"].get("x")) and _num(t["centre"].get("z"))):
                    err('pad site "%s" has no centre x/z in data/towns.json (the pad is pressed around it)' % site,
                        site, site)

    # points inside the world bounds
    bounds = (world or {}).get("bounds") if isinstance(world, dict) else None
    if not (isinstance(bounds, dict) and all(_num(bounds.get(k)) for k in ("min_x", "min_z", "max_x", "max_z"))):
        if points:
            rep.skip(C, "data/world.json has no bounds; summit and cone positions were not checked", file=rel)
    else:
        for w, (x, z) in points:
            if not (bounds["min_x"] <= x <= bounds["max_x"] and bounds["min_z"] <= z <= bounds["max_z"]):
                err("%s (%s, %s) is outside the world bounds" % (w, x, z), None, w)

    rep.info(C, "checked %d massifs, %d volcano cones and %d pads" % (
        len(massifs), len((v or {}).get("cones") or []) if isinstance(v, dict) else 0, len(pads)), file=rel)


KITS = ("kits", "structures")                       # relative to the data directory's parent
PREFABS = KITS + ("prefabs",)
SPAWN_BLOCKS = "spawn_blocks.json"
SPAWN_POLICY = "spawn_block_policy.json"


TOWN_GROUND_TOLERANCE = 0.1  # recorded heights and slopes are rounded to one decimal


def _islet_ground(win, x0, z0, world):
    """Lay tools/islet.py's Relic Island surface over a height window whose [0, 0] is block (x0, z0), in place."""
    import numpy as np
    import terrain as T
    import islet
    cx, cz = islet.CENTRE
    r = islet.RADIUS
    top, _ = islet.island_top(None, int(T.sea_level(world)))
    for j in range(top.shape[0]):
        for i in range(top.shape[1]):
            wz, wx = cz - r + j - z0, cx - r + i - x0
            if not np.isnan(top[j, i]) and 0 <= wz < win.shape[0] and 0 <= wx < win.shape[1]:
                win[wz, wx] = max(win[wz, wx], top[j, i])


# built_ground names a tool that raises terrain in the world that the heightmap does not carry; the town's recorded
# heights are measured on the heightmap with that tool's surface laid over it
BUILT_GROUND = {"tools/islet.py": _islet_ground}


def measure_town_ground(heights, world, town, tools_dir=None):
    """{centre_ground_y, footprint_ground_y, slope_mean, slope_max} for a town, on the canonical heightmap plus any
    declared built ground; slope is find_sites' (terrain.slope_degrees) over the footprint. Raises KeyError for an
    unknown built_ground."""
    import numpy as np
    tools_dir = Path(tools_dir or Path(__file__).resolve().parent)
    if str(tools_dir) not in sys.path:
        sys.path.insert(0, str(tools_dir))
    import terrain as T
    fp, c = town["footprint"], town["centre"]
    pad = 2
    z0, z1 = max(0, fp["min_z"] - pad), min(heights.shape[0], fp["max_z"] + 1 + pad)
    x0, x1 = max(0, fp["min_x"] - pad), min(heights.shape[1], fp["max_x"] + 1 + pad)
    lo_z, lo_x = min(z0, c["z"]), min(x0, c["x"])
    hi_z, hi_x = max(z1, c["z"] + 1), max(x1, c["x"] + 1)
    win = np.array(heights[lo_z:hi_z, lo_x:hi_x], dtype=np.float64)
    if town.get("built_ground"):
        BUILT_GROUND[town["built_ground"]](win, lo_x, lo_z, world)
    sl = T.slope_degrees(win)
    fz0, fz1 = fp["min_z"] - lo_z, fp["max_z"] + 1 - lo_z
    fx0, fx1 = fp["min_x"] - lo_x, fp["max_x"] + 1 - lo_x
    ground, slope = win[fz0:fz1, fx0:fx1], sl[fz0:fz1, fx0:fx1]
    return {"centre_ground_y": float(win[c["z"] - lo_z, c["x"] - lo_x]),
            "footprint_ground_y": [float(ground.min()), float(ground.max())],
            "slope_mean": float(slope.mean()), "slope_max": float(slope.max())}


def check_town_ground(ctx: Context):
    """Every town's recorded centre.ground_y, footprint.ground_y and footprint.slope_degrees against the canonical
    heightmap (plus any built_ground), so a re-press, rescale or build cannot leave them stale silently."""
    rep = ctx.report
    f, towns = ctx.records("towns.json")
    if not f:
        return
    terrain = load_terrain(ctx)
    if terrain is None:
        rep.skip("town-ground", "town heights not measured (%s)" % (ctx.terrain_reason or "terrain unavailable"), file=f.rel)
        return
    heights, world = terrain["heights"], terrain["world"]
    tol = TOWN_GROUND_TOLERANCE + 1e-6
    checked = 0
    for t in towns:
        tid = t.get("id")
        line = f.line_of_id(tid)
        fp, c = t.get("footprint") or {}, t.get("centre") or {}
        if not all(_int(fp.get(k)) for k in ("min_x", "max_x", "min_z", "max_z")) or not (_int(c.get("x")) and _int(c.get("z"))):
            continue
        if t.get("built_ground") and t["built_ground"] not in BUILT_GROUND:
            rep.error("town-ground", '"%s" built_ground %r is not a known builder (%s)'
                      % (tid, t["built_ground"], ", ".join(sorted(BUILT_GROUND))), file=f.rel, line=line, where=tid)
            continue
        m = measure_town_ground(heights, world, t)
        checked += 1
        stale = []
        if _num(c.get("ground_y")) and abs(c["ground_y"] - m["centre_ground_y"]) > tol:
            stale.append("centre.ground_y %s, measured %.1f" % (c["ground_y"], m["centre_ground_y"]))
        g = fp.get("ground_y")
        if isinstance(g, list) and len(g) == 2 and all(_num(v) for v in g):
            if abs(g[0] - m["footprint_ground_y"][0]) > tol or abs(g[1] - m["footprint_ground_y"][1]) > tol:
                stale.append("footprint.ground_y %s, measured [%.1f, %.1f]" % (g, *m["footprint_ground_y"]))
        s = fp.get("slope_degrees") or {}
        if _num(s.get("mean")) and _num(s.get("max")):
            if abs(s["mean"] - m["slope_mean"]) > tol or abs(s["max"] - m["slope_max"]) > tol:
                stale.append("footprint.slope_degrees mean %s max %s, measured mean %.1f max %.1f"
                             % (s["mean"], s["max"], m["slope_mean"], m["slope_max"]))
        if stale:
            rep.error("town-ground", '"%s" records stale heights: %s (tools/measure_towns.py --write refreshes them)'
                      % (tid, "; ".join(stale)), file=f.rel, line=line, where=tid)
    rep.info("town-ground", "measured %d town centres and footprints on heightmap %s"
             % (checked, str((world.get("heightmap") or {}).get("sha256") or "")[:12]), file=f.rel)


def _resolve_field(record, field):
    """A dotted field path into a record; a list step picks the item whose id is that segment."""
    cur = record
    for seg in field.split("."):
        if isinstance(cur, list):
            cur = next((x for x in cur if isinstance(x, dict) and x.get("id") == seg), None)
        elif isinstance(cur, dict):
            cur = cur.get(seg)
        else:
            return None
        if cur is None:
            return None
    return cur


def _records_by_id(doc):
    for key in ("towns", "routes", "landmarks", "landmark_trees"):
        if isinstance(doc, dict) and isinstance(doc.get(key), list):
            return {r.get("id"): r for r in doc[key] if isinstance(r, dict)}
    return {}


def check_visibility(ctx: Context):
    """Every visibility claim in data/visibility.json re-measured on the canonical heightmap (and the planned canopy):
    fails when a count drifts from its record, a claim measures false, a fragility flag does not match the rule, the
    record that states a claim does not cite it (or hides that it is fragile), or a landmark tree's seen_from has no
    claim. Nothing about what can be seen is trusted from a record."""
    C = "visibility"
    rep = ctx.report
    f, claims = ctx.records("visibility.json")
    if not f:
        return
    terrain = load_terrain(ctx)
    if terrain is None:
        rep.skip(C, "visibility claims not measured (%s)" % (ctx.terrain_reason or "terrain unavailable"), file=f.rel)
        return
    tools = str(Path(__file__).resolve().parent)
    if tools not in sys.path:
        sys.path.insert(0, tools)
    import visibility_claims as VC
    doc = f.doc
    repo = ctx.data_dir.parent
    heights, world = terrain["heights"], terrain["world"]
    if doc.get("heightmap_sha256") != (world.get("heightmap") or {}).get("sha256"):
        rep.error(C, "claims were measured on heightmap %s, not the canonical %s; re-measure with tools/visibility_claims.py "
                  "--write" % (doc.get("heightmap_sha256"), (world.get("heightmap") or {}).get("sha256")), file=f.rel)
    canopy_rec = doc.get("canopy") or {}
    canopy_path = repo / (canopy_rec.get("path") or "build/paint/canopy.npz")
    inp = VC.Inputs(ctx.data_dir, heights, world, canopy_path)
    canopy_ok = inp.canopy_sha256 is not None and inp.canopy_sha256 == canopy_rec.get("sha256")
    if inp.canopy_sha256 is None:
        rep.skip(C, "%s is absent (python tools/paint_maps.py --out build/paint); canopy claims were not measured"
                 % canopy_path, file=f.rel)
    elif not canopy_ok:
        rep.error(C, "the planned canopy changed (sha256 %s, claims measured on %s): a foliage or paint change can break "
                  "canopy claims; re-measure with tools/visibility_claims.py --write and review every change"
                  % (inp.canopy_sha256[:12], str(canopy_rec.get("sha256"))[:12]), file=f.rel)
    rules = doc.get("rules") or {}
    if (rules.get("fragile_max_seen"), rules.get("fragile_max_share"), rules.get("fragile_min_margin_blocks")) != (
            VC.FRAGILE_MAX_SEEN, VC.FRAGILE_MAX_SHARE, VC.FRAGILE_MIN_MARGIN):
        rep.error(C, "rules in visibility.json do not match tools/visibility_claims.py's fragility rule", file=f.rel)
    loaded, seen_ids, measured_n, fragile_n = {}, set(), 0, 0
    for c in claims:
        cid = c.get("id")
        line = f.line_of_id(cid)
        if cid in seen_ids:
            rep.error(C, 'duplicate claim "%s"' % cid, file=f.rel, line=line, where=cid)
        seen_ids.add(cid)
        rin = c.get("recorded_in") or {}
        rel = rin.get("file")
        stated = None
        if not rel or not (repo / rel).is_file():
            rep.error(C, 'claim "%s" is recorded in %r, which does not exist' % (cid, rel), file=f.rel, line=line, where=cid)
        elif rel.endswith(".json"):
            if rel not in loaded:
                loaded[rel] = json.loads((repo / rel).read_text(encoding="utf-8"))
            rec = _records_by_id(loaded[rel]).get(rin.get("record"))
            val = _resolve_field(rec, rin.get("field") or "") if rec is not None else None
            if val is None:
                rep.error(C, 'claim "%s" names %s %s.%s, which does not exist' % (cid, rel, rin.get("record"), rin.get("field")),
                          file=f.rel, line=line, where=cid)
            elif isinstance(val, str):
                stated = [val]
        else:
            stated = [ln for ln in (repo / rel).read_text(encoding="utf-8").splitlines() if "visibility:%s" % cid in ln]
            if not stated:
                rep.error(C, 'claim "%s" is recorded in %s, but no line there cites visibility:%s' % (cid, rel, cid),
                          file=f.rel, line=line, where=cid)
                stated = None
        if stated is not None and not any("visibility:%s" % cid in t for t in stated):
            rep.error(C, 'claim "%s": the stating text in %s does not cite visibility:%s' % (cid, rel, cid),
                      file=f.rel, line=line, where=cid)
        if c.get("surface") == "canopy" and not canopy_ok:
            continue
        try:
            m = VC.measure(c, inp)
        except Exception as exc:  # a malformed claim must not hide the others
            rep.error(C, 'claim "%s" could not be measured: %s: %s' % (cid, type(exc).__name__, exc), file=f.rel, line=line, where=cid)
            continue
        measured_n += 1
        fr = bool(VC.is_fragile(c, m))
        fragile_n += fr
        if not VC.holds(c, m):
            rep.error(C, 'claim "%s" is false: expects %s, measures %s' % (cid, c.get("expect"), json.dumps(m)),
                      file=f.rel, line=line, where=cid)
        if c.get("measured") != m:
            rep.error(C, 'claim "%s" drifted: records %s, measures %s (tools/visibility_claims.py --write, then review)'
                      % (cid, json.dumps(c.get("measured")), json.dumps(m)), file=f.rel, line=line, where=cid)
        if c.get("fragile") is not fr:
            rep.error(C, 'claim "%s" fragile is %s but the rule gives %s for %s' % (cid, c.get("fragile"), fr, json.dumps(m)),
                      file=f.rel, line=line, where=cid)
        if fr and stated is not None and not any("fragile" in t.lower() for t in stated):
            rep.error(C, 'claim "%s" is fragile (%s) but the text that states it in %s does not say so'
                      % (cid, json.dumps(m), rel), file=f.rel, line=line, where=cid)
    # every landmark tree's seen_from entry is a measured claim
    fol = ctx.doc("foliage.json") or {}
    for lt in fol.get("landmark_trees") or []:
        if not isinstance(lt, dict) or lt.get("landmark", True) is False:
            continue
        mine = [c for c in claims if (c.get("target") or {}).get("type") == "landmark_tree" and c["target"].get("id") == lt.get("id")]
        for o in lt.get("seen_from") or []:
            if o.get("kind") == "legs":
                for leg in o.get("legs") or []:
                    if not any(c["observers"].get("type") == "leg" and c["observers"].get("leg") == leg
                               and c["observers"].get("spacing", 48) == o.get("spacing", 48) for c in mine):
                        rep.error(C, 'landmark tree "%s" claims leg %s in data/foliage.json with no measured claim'
                                  % (lt.get("id"), leg), file=f.rel, where=lt.get("id"))
            elif o.get("kind") == "ring":
                if not any(c["observers"].get("type") == "ring" and c["observers"].get("radius") == o.get("radius") for c in mine):
                    rep.error(C, 'landmark tree "%s" claims a %s-block ring with no measured claim' % (lt.get("id"), o.get("radius")),
                              file=f.rel, where=lt.get("id"))
            elif o.get("kind") == "points":
                if not any(c["observers"].get("type") == "points" and c["observers"].get("points") == o.get("points") for c in mine):
                    rep.error(C, 'landmark tree "%s" claims seen_from points with no measured claim' % lt.get("id"),
                              file=f.rel, where=lt.get("id"))
            else:
                rep.error(C, 'landmark tree "%s" seen_from kind %r has no claim type' % (lt.get("id"), o.get("kind")),
                          file=f.rel, where=lt.get("id"))
    rep.info(C, "measured %d of %d visibility claims (%d fragile)" % (measured_n, len(claims), fragile_n), file=f.rel)


def _palette(path):
    """Block names in a structure template's palette (tools/nbt.py is standard library only)."""
    tools = str(Path(__file__).resolve().parent)
    if tools not in sys.path:
        sys.path.insert(0, tools)
    import nbt
    _, doc = nbt.load(path)
    return [p.get("Name") for p in (doc.get("palette") or []) if isinstance(p, dict)]


def _templates_naming(root, names):
    """name -> [template paths whose bytes hold it as an NBT string]. Matching the length-prefixed string is exact
    (no prefix hits: red_concrete does not match red_concrete_powder) and costs a decompression, not a full parse."""
    import gzip
    import struct
    needles = {n: struct.pack(">H", len(n.encode("utf-8"))) + n.encode("utf-8") for n in names}
    out = {n: [] for n in names}
    for path in sorted(Path(root).rglob("*.nbt")):
        try:
            raw = path.read_bytes()
            body = gzip.decompress(raw) if raw[:2] == bytes([0x1f, 0x8b]) else raw
        except (OSError, EOFError, gzip.BadGzipFile):
            continue
        for n, needle in needles.items():
            if needle in body:
                out[n].append(path)
    return out


def _resolve_template_id(tid, kits_dir):
    """cobblers:kits/trees/tree_town/oak -> kits/structures/prefabs/trees/tree_town/oak.nbt;
    cobblers:f4/services/pokecenter -> kits/structures/campaign/f4/services/pokecenter.nbt. None when nothing matches."""
    if not isinstance(tid, str) or not tid:
        return None
    rel = tid.split(":", 1)[1] if ":" in tid else tid
    parts = rel.split("/")
    cands = [Path(kits_dir, *(("prefabs",) + tuple(parts[1:])) if parts[0] == "kits" else ("campaign",) + tuple(parts))]
    cands.append(Path(kits_dir, *parts))
    for c in cands:
        p = c.with_suffix(".nbt")
        if p.is_file():
            return p
    hits = [p for p in Path(kits_dir).rglob(parts[-1] + ".nbt") if str(p).replace("\\", "/").endswith(rel + ".nbt")]
    return hits[0] if len(hits) == 1 else None


def check_spawn_blocks(ctx: Context):
    """No placed template decides encounters by accident: a template a placement or plan names, and every prefab, may
    contain a block from data/spawn_blocks.json only when data/spawn_block_policy.json whitelists it with a reason.
    Substitutions must replace triggers with non-triggers, must be gone from the kits, and must match the files on
    disk. A missing or empty spawn-block list makes the check SKIPPED, never a pass."""
    rep = ctx.report
    C = "spawn-blocks"
    rel_b, rel_p = "data/" + SPAWN_BLOCKS, "data/" + SPAWN_POLICY
    kits_dir = ctx.data_dir.parent.joinpath(*KITS)
    bpath, ppath = ctx.data_dir / SPAWN_BLOCKS, ctx.data_dir / SPAWN_POLICY
    if not bpath.is_file():
        rep.skip(C, "%s is absent; placed templates were not checked for spawn-triggering blocks (rerun "
                 "tools/spawn_blocks.py blocks)" % rel_b, file=rel_b)
        return
    bf = _load_json_for(C, bpath, rel_b, rep)
    if not bf:
        return
    triggers = bf.doc.get("blocks") if isinstance(bf.doc, dict) else None
    if not isinstance(triggers, dict) or not triggers:
        rep.skip(C, "%s lists no blocks, so nothing could be checked against it; rerun tools/spawn_blocks.py blocks "
                 "against the server" % rel_b, file=rel_b)
        return
    if not ppath.is_file():
        rep.error(C, "%s is absent, so no template may be checked against the %d spawn-triggering blocks"
                  % (rel_p, len(triggers)), file=rel_b)
        return
    pf = _load_json_for(C, ppath, rel_p, rep)
    if not pf or not isinstance(pf.doc, dict):
        if pf:
            rep.error(C, "top level must be an object", file=rel_p, line=1)
        return
    policy = pf.doc

    def perr(msg, key=None, where=None):
        rep.error(C, msg, file=rel_p, line=pf.line_of_key(key) if key else None, where=where)

    # whitelist
    allowed = set()
    wl = policy.get("whitelist")
    if not isinstance(wl, list):
        perr("whitelist must be a list", "whitelist")
        wl = []
    for i, w in enumerate(wl):
        if not isinstance(w, dict):
            perr("whitelist[%d] must be an object" % i, "whitelist")
            continue
        blocks = w.get("blocks")
        if not (isinstance(blocks, list) and blocks and all(isinstance(b, str) and b for b in blocks)):
            perr("whitelist[%d] needs a non-empty blocks list, got %r" % (i, blocks), "whitelist")
            continue
        if not (isinstance(w.get("why"), str) and w["why"].strip()):
            perr("whitelist entry %s needs a why: an allowed trigger block is a deliberate encounter"
                 % ", ".join(blocks[:3]), "whitelist", blocks[0])
            continue
        allowed.update(blocks)

    if not kits_dir.is_dir():
        rep.skip(C, "%s is absent; no template could be read" % "/".join(KITS), file=rel_p)
        return

    # substitutions
    subs = policy.get("substitutions")
    if not isinstance(subs, list):
        perr("substitutions must be a list", "substitutions")
        subs = []
    froms = []
    for i, s in enumerate(subs):
        if not isinstance(s, dict) or not isinstance(s.get("from"), str) or not isinstance(s.get("to"), str):
            perr("substitutions[%d] needs from and to block names" % i, "substitutions")
            continue
        if s["to"] in triggers:
            perr('substitution %s -> %s replaces a spawn-triggering block with another one (%s)'
                 % (s["from"], s["to"], _spawn_example(triggers, s["to"])), "substitutions", s["to"])
        froms.append(s["from"])
    for name, left in sorted(_templates_naming(kits_dir, froms).items()):
        if left:
            to = next(s["to"] for s in subs if isinstance(s, dict) and s.get("from") == name)
            perr("substitution %s -> %s is not applied: %s still contains %s (%d template(s) under %s)"
                 % (name, to, left[0].name, name, len(left), "/".join(KITS)), "substitutions", name)

    applied = (policy.get("applied") or {}).get("templates")
    if applied is not None and not isinstance(applied, list):
        perr("applied.templates must be a list", "applied")
        applied = []
    for i, row in enumerate(applied or []):
        if not isinstance(row, dict) or not isinstance(row.get("template"), str):
            perr("applied.templates[%d] needs a template path" % i, "applied")
            continue
        path = ctx.data_dir.parent / row["template"]
        if not path.is_file():
            if _local_only_template(ctx.data_dir.parent, row["template"]):
                continue  # licence forbids committing it (kits/PROVENANCE.json local_only); checked where it exists
            perr("applied.templates %s is not in the repository" % row["template"], "applied", row["template"])
            continue
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if row.get("sha256_after") != digest:
            perr("applied.templates %s hashes to %s, not the recorded sha256_after %s: the template changed after the "
                 "substitution, or it was never applied"
                 % (row["template"], digest[:12], str(row.get("sha256_after"))[:12]), "applied", row["template"])

    # the templates a placement or plan names, plus every prefab
    placed, skipped = {}, []
    plf = ctx.files.get("placements.json")
    doc = plf.doc if plf else None
    if doc is None and (ctx.data_dir / "placements.json").is_file():
        f = _load_json_for(C, ctx.data_dir / "placements.json", "data/placements.json", rep)
        doc = f.doc if f else None
    if doc is None:
        rep.skip(C, "data/placements.json is absent; only the prefabs were checked", file=rel_p)
    elif isinstance(doc, dict):
        for p in doc.get("placements") or []:
            if not isinstance(p, dict):
                continue
            if p.get("pack_template") and not p.get("file"):
                # a donor structure placed by resource id from an installed pack: the template is never in the
                # repository (licence), so its blocks cannot be checked here. tools/place_donor.py verifies it in a world.
                skipped.append("%s (placement %s, placed from the installed pack)" % (p["pack_template"], p.get("id")))
                continue
            path = ctx.data_dir.parent / p["file"] if isinstance(p.get("file"), str) else None
            if path is None or not path.is_file():
                rep.error(C, 'placement "%s" names template file %r, which is not in the repository'
                          % (p.get("id"), p.get("file")), file="data/placements.json", where=p.get("id"))
                continue
            placed.setdefault(path.resolve(), []).append("placement %s" % p.get("id"))
        for sid, s in (doc.get("settlements") or {}).items():
            anchors = ((s or {}).get("plan") or {}).get("anchors") or []
            for a in anchors if isinstance(anchors, list) else []:
                tid = a.get("template") if isinstance(a, dict) else None
                if tid is None:
                    continue
                path = _resolve_template_id(tid, kits_dir)
                if path is None:
                    skipped.append("%s (%s)" % (tid, sid))
                    continue
                placed.setdefault(path.resolve(), []).append("%s anchor %s" % (sid, a.get("id", tid)))
    if skipped:
        rep.skip(C, "template ids that do not resolve to a file under %s were not checked: %s"
                 % ("/".join(KITS), ", ".join(sorted(set(skipped)))), file=rel_p)
    for path in sorted(ctx.data_dir.parent.joinpath(*PREFABS).rglob("*.nbt")):
        placed.setdefault(path.resolve(), []).append("prefab")
    kits_resolved = kits_dir.resolve()
    checked = 0
    for path, why in sorted(placed.items()):
        if kits_resolved not in path.parents:
            rep.error(C, "%s (%s) is outside %s, so its palette was not checked"
                      % (path.name, why[0], "/".join(KITS)), file=rel_p)
            continue
        try:
            pal = _palette(path)
        except Exception as exc:                 # a template that cannot be read is not a template without triggers
            rep.error(C, "cannot read template %s (%s): %s: %s" % (path.name, why[0], type(exc).__name__, exc),
                      file=rel_p)
            continue
        checked += 1
        for block in sorted({b for b in pal if b in triggers and b not in allowed}):
            rep.error(C, '%s (%s) contains %s, which decides encounters wherever it is placed: %s. Substitute it '
                      "(tools/spawn_blocks.py substitute) or whitelist it with a reason in %s"
                      % (path.name, why[0], block, _spawn_example(triggers, block), rel_p),
                      file=str(Path(*path.parts[-4:])), where=block)
    rep.info(C, "checked %d placed templates and prefabs against %d spawn-triggering blocks (%d whitelisted)"
             % (checked, len(triggers), len(allowed)), file=rel_p)


def _spawn_example(triggers, block):
    """One spawn that names the block, as data/spawn_blocks.json records it."""
    uses = triggers.get(block)
    if isinstance(uses, list) and uses:
        return "%s%s" % (uses[0], "" if len(uses) == 1 else " and %d more" % (len(uses) - 1))
    return "a loaded spawn condition"


def check_habitat_blocks(ctx: Context):
    """Every Habitat Block in data/habitat_blocks.json can be re-applied after a re-export: its pool exists, its style
    is the proven natural one, and no two ReplaceSpawns ranges overlap (EXP-021). With --world-save (a stopped world
    copy, never the live world) every placed or verified block must be present in that world with its recorded
    settings; without it, presence is SKIPPED, never passed."""
    rep = ctx.report
    C = "habitat-blocks"
    f = ctx.files.get("habitat_blocks.json")
    if not f:
        return
    import habitat_blocks as HB
    for bid, msg in HB.static_problems(f.doc, ctx.doc("spawns.json")):
        rep.error(C, msg, file=f.rel, line=f.line_of_id(bid) if bid else None, where=bid)
    blocks = [b for b in f.doc.get("blocks") or [] if isinstance(b, dict)]
    placed = [b for b in blocks if b.get("status") in HB.PLACED]
    if not placed:
        rep.info(C, "%d blocks recorded, none placed; nothing to find in a world" % len(blocks), file=f.rel)
        return
    if not ctx.world_save:
        rep.skip(C, "%d placed blocks were not checked against a world; pass --world-save <stopped world copy> "
                 "(or tools/habitat_blocks.py verify --rcon on a running server)" % len(placed), file=f.rel)
        return
    try:
        problems = HB.world_problems(f.doc, ctx.world_save)
    except SystemExit as exc:
        rep.error(C, str(exc), file=f.rel)
        return
    for bid, msg in problems:
        rep.error(C, msg, file=f.rel, line=f.line_of_id(bid), where=bid)
    if not problems:
        rep.info(C, "%d placed blocks present in %s" % (len(placed), ctx.world_save), file=f.rel)


def check_spawn_pack(ctx: Context):
    """Every spawn detail in a compiled pack has an id of its own.

    A Cobblemon spawn file whose details share an id parses, loads without a word in the log, and is
    impossible to tell from a working one by reading it. On 2026-09-18 the sub-region files carried
    14,366 details under 439 ids and the waterway file 320 under 132, because the generator put the
    sub-region or segment in the id but not the box. It cost a five-minute in-game test run to find.

    Pass --pack <compiled dir> to check one; without it this is SKIPPED, never passed.
    """
    C = "spawn-pack"
    rep = ctx.report
    pack = getattr(ctx, "spawn_pack", None)
    if not pack:
        rep.skip(C, "no compiled pack checked; pass --pack <dir> (build/datapacks/cobblers_spawns)")
        return
    root = Path(pack)
    if not root.is_dir():
        rep.error(C, "not a directory: %s" % pack)
        return
    files = sorted(root.glob("data/*/spawn_pool_world/**/*.json"))
    if not files:
        rep.error(C, "no spawn_pool_world files under %s" % pack)
        return
    total = dupes = 0
    for f in files:
        try:
            doc = json.loads(f.read_text(encoding="utf-8"))
        except ValueError as exc:
            rep.error(C, "does not parse: %s" % exc, file=f.name)
            continue
        seen = {}
        for entry in (doc.get("spawns") or []):
            total += 1
            sid = entry.get("id")
            if sid is None:
                rep.error(C, "a spawn detail has no id", file=f.name)
                continue
            seen[sid] = seen.get(sid, 0) + 1
        repeated = {k: v for k, v in seen.items() if v > 1}
        if repeated:
            dupes += sum(v - 1 for v in repeated.values())
            worst = max(repeated.items(), key=lambda kv: kv[1])
            rep.error(C, "%d spawn ids are used more than once (%s appears %d times); a detail's id must "
                         "identify its box" % (len(repeated), worst[0], worst[1]), file=f.name)
    if not dupes:
        rep.info(C, "%d spawn details across %d files, every id its own" % (total, len(files)))


CHECKS = [
    ("schema", check_schema),
    ("world", check_world_config),
    ("integrity", check_integrity),
    ("referential", check_referential),
    ("progression", check_progression),
    ("quest-dialogue", check_quest_dialogue),
    ("rivers", check_rivers),
    ("towns", check_towns),
    ("foliage", check_foliage),
    ("sculpt", check_sculpt),
    ("spawn-blocks", check_spawn_blocks),
    ("cell-terrain", check_cell_terrain_recorded),
    ("spatial", check_spatial),
    ("town-ground", check_town_ground),
    ("visibility", check_visibility),
    ("habitat-blocks", check_habitat_blocks),
    ("spawn-pack", check_spawn_pack),
]


# --------------------------------------------------------------------- cli


def render_text(report: Report, ctx: Context):
    out = []
    groups = {}
    for f in report.findings:
        groups.setdefault(f.severity, []).append(f)

    for sev in (ERROR, WARNING, SKIPPED, INFO):
        items = groups.get(sev) or []
        if not items:
            continue
        out.append("%s (%d)" % (sev, len(items)))
        for f in items:
            loc = f.file or "-"
            if f.line:
                loc += ":%d" % f.line
            out.append("  [%-12s] %-34s %s" % (f.check, loc, f.message))
        out.append("")

    out.append("terrain: %s" % ("available" if ctx.terrain_available
                                else "UNAVAILABLE (%s)" % ctx.terrain_reason))
    out.append("%d error(s), %d warning(s), %d skipped, %d info"
               % (report.count(ERROR), report.count(WARNING),
                  report.count(SKIPPED), report.count(INFO)))
    return "\n".join(out)


def main(argv=None):
    p = argparse.ArgumentParser(description="Validate authored campaign data.")
    p.add_argument("--data", default=str(ROOT / "data"), help="data directory")
    p.add_argument("--source-root", default=os.environ.get("COBBLERS_SOURCE_ROOT"),
                   help="root of the out-of-repo source/ tree")
    p.add_argument("--world-save", default=os.environ.get("COBBLERS_WORLD_SAVE"),
                   help="a stopped world copy to check placed Habitat Blocks against (never the live world)")
    p.add_argument("--pack", default=os.environ.get("COBBLERS_SPAWN_PACK"),
                   help="a compiled spawn pack (build/datapacks/cobblers_spawns) to check for duplicate spawn ids")
    p.add_argument("--only", nargs="*", metavar="CHECK", help="run only these checks")
    p.add_argument("--list", action="store_true", help="list checks and exit")
    p.add_argument("--json", action="store_true", dest="as_json", help="JSON output")
    args = p.parse_args(argv)

    if args.list:
        for name, _ in CHECKS:
            print(name)
        return 0

    data_dir = Path(args.data)
    report = Report()
    ctx = Context(data_dir, args.source_root, report, args.world_save, args.pack)

    if not data_dir.is_dir():
        report.error("schema", "data directory not found: %s" % data_dir)
    else:
        selected = set(args.only) if args.only else None
        # schema and integrity always run; other checks depend on them
        for name, fn in CHECKS:
            if selected and name not in selected and name not in ("schema", "integrity"):
                continue
            try:
                fn(ctx)
            except Exception as exc:  # a broken check must not hide the others
                report.error(name, "check raised %s: %s" % (type(exc).__name__, exc))

    if args.as_json:
        print(json.dumps({
            "terrain_available": ctx.terrain_available,
            "terrain_reason": ctx.terrain_reason,
            "counts": {
                "error": report.count(ERROR),
                "warning": report.count(WARNING),
                "skipped": report.count(SKIPPED),
                "info": report.count(INFO),
            },
            "findings": [f.as_dict() for f in report.findings],
        }, indent=2))
    else:
        print(render_text(report, ctx))

    return 1 if report.count(ERROR) else 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(2)
