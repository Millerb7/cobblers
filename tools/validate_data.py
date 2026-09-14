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
            "kind": {"rift", "mountain", "volcano", "island_chain", "coast", "lake", "pass",
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
        ["id", "order", "role", "status", "centre", "footprint"],
        {"role": {"hometown", "gym_town", "league", "town"}, "status": {"proposed", "accepted", "built"}},
    ),
    "routes.json": ("cobblers.routes/1", "routes", ["id", "from", "to"], {}),
}

REQUIRED_FILES = {"world.json"}


# ----------------------------------------------------------------- context


class Context:
    def __init__(self, data_dir: Path, source_root, report: Report):
        self.data_dir = data_dir
        self.source_root = source_root
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
    if derived:
        out_sha = ((f.doc.get("cut") or {}).get("output") or {}).get("sha256")
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


def check_towns(ctx: Context):
    """Town placements: unique ids and orders, footprints inside the border and around their centre, and every
    town a progression flag names exists."""
    rep = ctx.report
    f, towns = ctx.records("towns.json")
    if not f:
        return
    world = ctx.doc("world.json") or {}
    border = (world.get("export") or {}).get("border") or {}
    seen, orders = set(), set()
    for t in towns:
        tid = t.get("id")
        line = f.line_of_id(tid)
        if tid in seen:
            rep.error("towns", 'duplicate town "%s"' % tid, file=f.rel, line=line, where=tid)
        seen.add(tid)
        if t.get("order") in orders:
            rep.error("towns", 'town "%s" repeats order %s' % (tid, t.get("order")), file=f.rel, line=line, where=tid)
        orders.add(t.get("order"))
        fp, c = t.get("footprint") or {}, t.get("centre") or {}
        try:
            if not (fp["min_x"] <= c["x"] <= fp["max_x"] and fp["min_z"] <= c["z"] <= fp["max_z"]):
                rep.error("towns", 'town "%s" centre lies outside its footprint' % tid, file=f.rel, line=line, where=tid)
            if border and not (border["min_x"] <= fp["min_x"] and fp["max_x"] <= border["max_x"]
                               and border["min_z"] <= fp["min_z"] and fp["max_z"] <= border["max_z"]):
                rep.error("towns", 'town "%s" footprint crosses the world border' % tid, file=f.rel, line=line, where=tid)
        except (KeyError, TypeError):
            rep.error("towns", 'town "%s" needs centre x/z and footprint min/max x/z' % tid, file=f.rel, line=line, where=tid)
    prog = ctx.doc("progression.json") or {}
    for flag in prog.get("flags") or []:
        town = (flag.get("waystone") or {}).get("town")
        if town and town not in seen:
            rep.error("towns", 'progression flag "%s" names town "%s", which is not in towns.json'
                      % (flag.get("id"), town), file="data/progression.json", where=flag.get("id"))


CHECKS = [
    ("schema", check_schema),
    ("world", check_world_config),
    ("integrity", check_integrity),
    ("referential", check_referential),
    ("progression", check_progression),
    ("rivers", check_rivers),
    ("towns", check_towns),
    ("cell-terrain", check_cell_terrain_recorded),
    ("spatial", check_spatial),
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
    ctx = Context(data_dir, args.source_root, report)

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
