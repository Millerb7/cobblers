#!/usr/bin/env python
"""Does a working Pokemon's work have anything to act on?  data/ambient.json `work` records, from data only.

The owner, 2026-10-16: "pokemon can stay, but make them look relaxed if not doing anything." A `work` job stands at its
station, hops towards its `face` cell and sets off an effect (particles, a sound) there every few seconds. When there is
nothing at the face -- Viltri Quay's Corphish, picking knots out of nets "hung on the cottage's back wall" on open grass
-- it swings at air. Gym 2's town was rebuilt in the gym overhaul and its ambient spots were not moved.

The rule (data/ambient.json rules.targets): in an AUDITED settlement every `work` record that is not `relaxed` must have
a target at its face, within `reach` blocks of the face cell (the effect is set off at that cell's centre, and the hop
reaches 0.12 of the way to it, so a target is the face cell or the one beside it). What counts, all from data and
never from a world save (CLAUDE.md, "Ground comes from the heightmap"):

  structure   a block of a placed building's template above its foundation layer (y >= 1; not air, fluid, seagrass or
              kelp), exactly as tools/place_town.py seats it: position = the building's minimum corner, turned by the
              record's rotation (the same footprint rule as place_donor.footprint). Coarse, rectangle-level evidence for
              what carries no template file here: a placement without a `file` (its footprint), an anchor with a
              `template` (its lot), an earthwork's fill/setblock columns, the town dressing's pieces, the square's pieces.
              An anchor with NO template is a lot a human composes in Axiom ("composition in Axiom, no prep"): nothing in
              data builds it, so it is not evidence (Viltri Quay's two piers).
  paving      a street or plaza cell of the town's plan under the face; counts only when the record says
              `"target": "paving"` (a Wooper mopping the promenade needs paving, a net-picker does not).
  water       the face is under the surface: ground(face) < surface_y; only when the record says
              `"target": {"water": <surface y>, "source": "<where that level is stated>"}`.

What this is NOT: a finding that a target exists in a running world (the evidence is the plan and the templates), nor a
check of an unaudited settlement (rules.targets.audited lists the ones that were measured; the rest are reported as not
audited, never as passing). A coarse rectangle is generous, so a record it fails is certainly aimed at nothing, and
one it passes is only not contradicted.

  python tools/ambient_targets.py audit [--town <settlement>] [--json <out>]
  exit 0 = every audited work record has a target or is relaxed; 1 = a work job is aimed at nothing; 2 = a town could
  not be modelled here (a missing derived plan or template: NOT_EXECUTED, never a pass).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

# blocks that are not a thing to work on: the foundation layer is skipped by y, and these anywhere
NOT_A_TARGET = {"minecraft:air", "minecraft:cave_air", "minecraft:void_air", "minecraft:structure_void",
                "minecraft:water", "minecraft:lava", "minecraft:bubble_column", "minecraft:seagrass",
                "minecraft:tall_seagrass", "minecraft:kelp", "minecraft:kelp_plant", "minecraft:jigsaw"}


class Unmodelled(Exception):
    """A settlement cannot be modelled here (a derived plan or a template file is missing): not a pass."""


def targets_rules(data):
    return data["rules"]["targets"]


def _turn(x, z, rot):
    import place_town as PT
    return PT.rotate(x, z, rot or "none")


def template_columns(rec, doc_root=ROOT):
    """{(x, z): block name} the above-foundation target blocks of one `file` placement as place_town seats it, or raises
    Unmodelled when its template is not here."""
    import nbt
    f = rec.get("file")
    path = Path(doc_root) / f if f else None
    if path is None or not path.is_file():
        raise Unmodelled("%s: template file %r is not here (python tools/local_inputs.py hydrate --store <store>)"
                         % (rec["id"], f))
    if (rec.get("mirror") or "none") != "none":
        raise Unmodelled("%s: place_town places no mirror, so a mirrored record has no known blocks" % rec["id"])
    _, t = nbt.load(path)
    sx, _sy, sz = t["size"]
    rot = rec.get("rotation") or "none"
    corners = [_turn(x, z, rot) for x in (0, sx - 1) for z in (0, sz - 1)]
    mnx, mnz = min(c[0] for c in corners), min(c[1] for c in corners)
    px, pz = int(rec["position"]["x"]), int(rec["position"]["z"])
    pal = t["palette"]
    out = {}
    for b in t["blocks"]:
        tx, ty, tz = b["pos"]
        name = pal[b["state"]]["Name"]
        if ty < 1 or name in NOT_A_TARGET:
            continue
        rx, rz = _turn(tx, tz, rot)
        out[(px + rx - mnx, pz + rz - mnz)] = name
    return out


class Model:
    """What a settlement has at each column, from its plan and templates (never a world)."""

    def __init__(self, settlement, doc=None, doc_root=ROOT):
        import town_dressing as TD
        self.settlement = settlement
        doc = doc or json.loads((ROOT / "data" / "placements.json").read_text(encoding="utf-8"))
        self.structure = {}        # (x, z) -> label, exact template blocks
        self.coarse = {}           # (x, z) -> label, rectangle-level
        self.paving = {}           # (x, z) -> label
        try:
            plan = TD.town_plan(settlement)
        except SystemExit as e:
            raise Unmodelled("%s: %s" % (settlement, e))
        for name, st in (plan.get("streets") or {}).items():
            for z, _y, xa, xb in st.get("cells") or []:
                for x in range(xa, xb + 1):
                    self.paving.setdefault((x, z), "street " + name)
        if plan.get("plaza"):
            for c in TD.rect_cells(plan["plaza"]["rect"]):
                self.paving.setdefault(c, "plaza")
        for an in plan.get("anchors") or []:
            if an.get("template"):                    # built by a tool; a null template is a human's lot
                for c in TD.rect_cells(an["rect"]):
                    self.coarse.setdefault(c, "anchor %s (lot)" % an["id"])
        try:
            rects = TD.building_footprints(settlement, doc)
        except SystemExit as e:
            raise Unmodelled("%s: %s" % (settlement, e))
        for q in doc["placements"]:
            if q.get("settlement") != settlement:
                continue
            if q.get("kind") == "earthwork":
                for c in TD.command_columns(q.get("commands")):
                    self.coarse.setdefault(c, "earthwork %s" % q["id"])
            elif q.get("position") and q.get("file") and (ROOT / q["file"]).is_file():
                for c, name in template_columns(q, doc_root).items():
                    self.structure.setdefault(c, "%s %s" % (q["id"], name.replace("minecraft:", "")))
            elif q.get("position"):
                if q["id"] not in rects:
                    raise Unmodelled("%s: no footprint" % q["id"])
                for c in TD.rect_cells(rects[q["id"]]):
                    self.coarse.setdefault(c, "building %s (footprint)" % q["id"])
            if q.get("position") and q.get("file") and not (ROOT / q["file"]).is_file():
                raise Unmodelled("%s: template file %r is not here" % (q["id"], q["file"]))
        dressing = json.loads((ROOT / "data" / "town_dressing.json").read_text(encoding="utf-8"))
        if (dressing.get("towns") or {}).get(settlement):
            # the dressing's pieces seat on the ground and the plan's mask: read through ambient.Site, which already does
            import ambient as A
            import ground as G
            data = A.load()
            try:
                site = A.Site(settlement, A.settlement_ground(settlement, G.Ground(None), doc, None), doc, dressing, None,
                              data["rules"])
            except SystemExit as e:
                raise Unmodelled("%s: %s" % (settlement, e))
            for c, why in site.why.items():
                if why.startswith("dressing") or why.startswith("plaza piece"):
                    self.coarse.setdefault(c, why)

    def near(self, table, fx, fz, reach):
        best = None
        for dx in range(-reach, reach + 1):
            for dz in range(-reach, reach + 1):
                lab = table.get((fx + dx, fz + dz))
                if lab is not None:
                    d = max(abs(dx), abs(dz))
                    if best is None or d < best[0]:
                        best = (d, lab)
        return best


def evidence(w, model, ground, reach):
    """(kind, label, distance) the record's work has at its face, or None. `ground` is tools/ground.py's callable."""
    fx, fz = w["face"]
    tgt = w.get("target")
    if tgt == "paving":
        hit = model.near(model.paving, fx, fz, 0)
        return ("paving", hit[1], hit[0]) if hit else None
    if isinstance(tgt, dict) and "water" in tgt:
        if not isinstance(tgt.get("source"), str) or not tgt["source"].strip():
            raise SystemExit("ambient_targets/%s: a water target names where its surface level is stated (source)" % w["id"])
        g = int(round(ground(fx, fz)))
        return ("water", "ground y%d under surface y%d" % (g, int(tgt["water"])), 0) if g < int(tgt["water"]) else None
    if tgt is not None:
        raise SystemExit("ambient_targets/%s: target %r is neither \"paving\" nor {\"water\": y, \"source\": ...}"
                         % (w["id"], tgt))
    for kind, table in (("structure", model.structure), ("coarse", model.coarse)):
        hit = model.near(table, fx, fz, reach)
        if hit:
            return (kind, hit[1], hit[0])
    return None


def audit(towns=None, data=None, ground=None, workers=None):
    """{"records": [...], "problems": [...], "unmodelled": [...], "not_audited": [...]} over the audited settlements."""
    import ambient as A
    import ground as G
    data = data or A.load()
    rules = targets_rules(data)
    if workers is None:
        workers, _ = A.workers_of(data, A.town_files(None, data))
    audited = [s for s in rules["audited"] if not towns or s in towns]
    out = {"records": [], "problems": [], "unmodelled": [],
           "not_audited": sorted({w["settlement"] for w in workers if w["job"] == "work"} - set(rules["audited"]))}
    ground = ground or G.Ground(None)
    doc = json.loads((ROOT / "data" / "placements.json").read_text(encoding="utf-8"))
    for s in audited:
        try:
            model = Model(s, doc)
        except Unmodelled as e:
            out["unmodelled"].append("%s: %s" % (s, e))
            continue
        for w in [x for x in workers if x["settlement"] == s and x["job"] == "work"]:
            if w.get("relaxed"):
                if not isinstance(w.get("relaxed_why"), str) or not w["relaxed_why"].strip():
                    out["problems"].append("%s: relaxed without relaxed_why (say what is missing at the face)" % w["id"])
                out["records"].append({"id": w["id"], "settlement": s, "state": "relaxed"})
                continue
            ev = evidence(w, model, ground, int(rules["reach"]))
            out["records"].append({"id": w["id"], "settlement": s, "state": "target" if ev else "NONE",
                                   "evidence": ev})
            if ev is None:
                out["problems"].append(
                    "%s (%s): a work job aimed at nothing -- no target within %d of its face %s%s; make it relaxed "
                    "(relaxed: true, relaxed_why) or give it a target that exists"
                    % (w["id"], s, int(rules["reach"]), w["face"], " (declared target %r)" % (w["target"],) if w.get("target") else ""))
    return out


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("cmd", choices=["audit"])
    p.add_argument("--town", action="append")
    p.add_argument("--json")
    a = p.parse_args(argv)
    res = audit(a.town)
    if a.json:
        Path(a.json).write_text(json.dumps(res, indent=1, default=str), encoding="utf-8")
    for r in res["records"]:
        print("%-9s %-28s %s" % (r["state"], r["id"], r.get("evidence") or ""))
    for m in res["problems"]:
        print("PROBLEM", m)
    for m in res["unmodelled"]:
        print("NOT_EXECUTED", m)
    print("not audited (rules.targets.audited): %s" % ", ".join(res["not_audited"]))
    return 1 if res["problems"] else (2 if res["unmodelled"] else 0)


if __name__ == "__main__":
    sys.exit(main())
