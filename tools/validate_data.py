#!/usr/bin/env python
"""Validate the authored campaign data in data/.

Standalone CLI, standard library only. Designed to be useful before any
terrain exists: checks that cannot run without a verified heightmap are
reported as SKIPPED with a reason, never silently passed.

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
        ["id", "name", "kind", "anchor"],
        {"kind": {"rift", "mountain", "volcano", "island_chain", "coast", "lake", "pass"}},
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


def check_spatial(ctx: Context):
    rep = ctx.report
    if not ctx.terrain_available:
        rep.skip("spatial",
                 "terrain checks not run (%s). Anchors are NOT confirmed in bounds, "
                 "on land, above sea level, or non-overlapping." % ctx.terrain_reason)
        rep.skip("cell-terrain",
                 "cell terrain statistics not recomputed (%s)" % ctx.terrain_reason)
        return

    world = ctx.doc("world.json") or {}
    grid = world.get("grid") or {}
    ox, oz = grid.get("origin_x"), grid.get("origin_z")
    if ox is None or oz is None:
        rep.skip("spatial", "grid origin unset; coordinates cannot be placed on the map")
        return
    # Reaching here requires a verified heightmap and a known origin. The
    # measurement code lands in step 4 alongside the analysis toolkit.
    rep.skip("spatial",
             "terrain is available but the measurement backend arrives with the "
             "step 4 analysis toolkit")


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


CHECKS = [
    ("schema", check_schema),
    ("world", check_world_config),
    ("integrity", check_integrity),
    ("referential", check_referential),
    ("progression", check_progression),
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
