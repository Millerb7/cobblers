#!/usr/bin/env python
"""Hub waystones: one waystone at each main place that is not a town, set the way a town's is.

THE OWNER (2026-10-09): fast travel by waystone stays limited so travel remains part of the game. A gym town's waystone
is activated by its badge (data/progression.json); the places of that rank that are not gym towns -- "like ferry ports
or research centers, not like the Articuno research camp, but main areas" -- get one too, activated by a first visit
(the Waystones mod's own behaviour: a right-click on it, data/hub_waystones.json `unlock`). data/hub_waystones.json
records which places were chosen and which were turned down, with why.

RUNG (CLAUDE.md principle 6): existing functionality. The block is the Waystones mod's own `waystones:waystone`, set by
two `setblock` lines exactly as tools/place_town.py sets a town's (lower half at ground + 1, upper half above it, the
same `facing`), after a `fill ... air replace waystones:waystone` over the box so a re-run never stacks a second one.
Nothing new runs in the world: a block function and a re-apply step.

WHERE THE POSITION LIVES. In the place's own data file (`waystone: {at: [x, z], facing}`), not in a list of ours. The
research station's and Coldwater Station's builders refuse any column of theirs within a fixed clearance of an x/z that
another data/*.json authors (tools/coldwater_station.py siting), so a position in a file of its own would make the
station refuse its own build; the place's file is the one it skips. This file's registry (`hubs`) names, for each, the
file, the builder whose plan it must stand clear of, and the step that must have run first.

GROUND. tools/ground.py, rounded: the waystone's lower half is at round(ground) + 1, the paving or the grass top being
round(ground). Never a world save.

WHAT THIS DOES NOT COVER. Only the hubs data/hub_waystones.json lists. The towns' own waystones are tools/place_town.py's
(R8, R7); the gym-town flag sync is tools/progression_pack.py's; the wild waystones the mod may generate in new chunks
and the villages it seeds are config (base-pack/cobbleverse/config/waystones-common.toml), outside this file. A waystone
in the world is not necessarily one of ours.

  python tools/hub_waystones.py check              # the record, the positions, the ground, the clearance
  python tools/hub_waystones.py build [--out DIR]  # check, then write build/datapacks/cobblers_hub_waystones
  python tools/hub_waystones.py probes [--write]   # the presence probes (data/world_probes.json places.hub_waystones)

Ownership: the output is generated and lives in build/ (gitignored); data/hub_waystones.json is the source.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

DATA = ROOT / "data" / "hub_waystones.json"
WORLD = ROOT / "data" / "world.json"
PROBES = ROOT / "data" / "world_probes.json"
DEFAULT_OUT = ROOT / "build" / "datapacks" / "cobblers_hub_waystones"
SCHEMA = "cobblers.hub_waystones/1"
NS = "cobblers"
FN = "hub_waystones"
PACK_FORMAT = 48          # Minecraft 1.21.1
FACINGS = ("north", "south", "east", "west")
BLOCK = "waystones:waystone"
PAD = 1                   # the 3 x 3 round the stone that nothing may stand in above the ground
CLEAR = 2                 # columns round the stone swept of an older waystone before the new one is set
BOX_Y = (-2, 4)           # that sweep's reach below and above the stone's lower half


class HubError(ValueError):
    pass


def load(path=DATA):
    doc = json.loads(Path(path).read_text(encoding="utf-8"))
    if doc.get("schema") != SCHEMA:
        raise HubError("%s: schema %r, expected %r" % (path, doc.get("schema"), SCHEMA))
    return doc


def _json(name):
    return json.loads((ROOT / "data" / name).read_text(encoding="utf-8"))


def record(hub):
    """The place's own waystone record: {at, facing, ...}, read from its file by the registry's path."""
    node = _json(hub["source"])
    for step in hub["path"]:
        if isinstance(step, dict):                        # {"id": "northeast_landing"} picks a list entry by id
            (key, want), = step.items()
            node = next((e for e in node if e.get(key) == want), None)
        else:
            node = node[step] if node is not None else None
        if node is None:
            raise HubError("%s: %s %s has no such entry" % (hub["id"], hub["source"], hub["path"]))
    if not isinstance(node, dict) or "at" not in node or node.get("facing") not in FACINGS:
        raise HubError("%s: the record at %s %s needs `at` [x, z] and `facing` in %s"
                       % (hub["id"], hub["source"], hub["path"], "/".join(FACINGS)))
    return node


def sea_level():
    return int(_json("world.json")["vertical"]["sea_level"])


def stone(hub, g):
    """{id, x, y, z, facing}: the lower half's block, one above the heightmap ground."""
    r = record(hub)
    x, z = r["at"]
    return {"id": hub["id"], "x": int(x), "z": int(z), "y": int(g(int(x), int(z))) + 1, "facing": r["facing"]}


# ------------------------------------------------------------------------------------------------- the builders' plans
def _columns_research(g):
    """Columns in which Shrew Station's plan writes anything above the paving, and the water test."""
    import research_station as RS
    doc = RS.load()
    p = RS.plan(doc, g)
    above = set()
    for zone in RS.ZONES:
        for (x, y, z) in list(p.solid[zone]) + list(p.hung[zone]) + [k for k, _ in p.doors[zone]]:
            if y >= g(x, z) + 1:
                above.add((x, z))
    return above, (lambda x, z: p.w.depth(x, z) is not None)


def _columns_coldwater(g):
    """Every column Coldwater Station's plan writes a block in (foundations included)."""
    import coldwater_station as CS
    doc = CS.load()
    pl = CS.plan(doc, g)
    return {(x, z) for (x, _y, z) in pl["blocks"]}, (lambda x, z: False)


def _columns_dock(dock_id):
    def f(g):
        import ferry_docks as FD
        doc = FD.load(FD.DOCKS)
        rec = next(r for r in doc["docks"] if r["id"] == dock_id)
        level = int(_json("world.json")["vertical"]["sea_level"])
        e, geo = FD.build_one(rec, g, level)
        cols = {(x, z) for (x, _y, z) in e.cells}
        for part in ("ferryman", "landing"):
            ferries = _json("ferries.json")
            d = next(q for q in ferries["docks"] if q["id"] == dock_id)
            cols.add((d[part]["at"][0], d[part]["at"][2]))
        for b in next(q for q in _json("ferries.json")["docks"] if q["id"] == dock_id).get("keep_clear") or []:
            cols |= {(x, z) for x in range(b[0], b[2] + 1) for z in range(b[1], b[3] + 1)}
        return cols, (lambda x, z: g(x, z) < level)
    return f


BUILDERS = {"research_station": _columns_research, "coldwater_station": _columns_coldwater}


def builder_columns(hub, g):
    key = hub["builder"]
    if key.startswith("dock:"):
        return _columns_dock(key.split(":", 1)[1])(g)
    if key not in BUILDERS:
        raise HubError("%s: builder %r is not one of %s or dock:<id>" % (hub["id"], key, sorted(BUILDERS)))
    return BUILDERS[key](g)


# ----------------------------------------------------------------------------------------------------------- checking
def problems(doc, g=None):
    """[problem] in the registry, the positions, the ground and the clearance. Fail closed."""
    import ground as G
    g = g or G.load()
    bad = []
    ids = [h.get("id") for h in doc.get("hubs") or []]
    if not ids:
        return ["no hubs"]
    if len(set(ids)) != len(ids):
        bad.append("duplicate hub ids %s" % sorted({i for i in ids if ids.count(i) > 1}))
    rejected = {r.get("id") for r in doc.get("rejected") or []}
    if rejected & set(ids):
        bad.append("both chosen and rejected: %s" % sorted(rejected & set(ids)))
    for r in doc.get("rejected") or []:
        if not r.get("reason"):
            bad.append("rejected %s carries no reason" % r.get("id"))
    sea = sea_level()
    seen = {}
    for hub in doc["hubs"]:
        try:
            s = stone(hub, g)
        except HubError as e:
            bad.append(str(e))
            continue
        except Exception as e:                            # a missing file or key is a refusal, not a crash
            bad.append("%s: %s: %s" % (hub["id"], type(e).__name__, e))
            continue
        # dry: one above the sea at least, as the research station's own land_above_level
        if s["y"] - 1 < sea + 1:
            bad.append("%s: ground y%d is not at least one above the sea (y%d)" % (hub["id"], s["y"] - 1, sea))
        # the pad, 3 x 3 round the stone, level with it: a stone on a slope would stand half in the air
        for dx in range(-PAD, PAD + 1):
            for dz in range(-PAD, PAD + 1):
                gy = int(g(s["x"] + dx, s["z"] + dz))
                if abs(gy - (s["y"] - 1)) > 1:
                    bad.append("%s: ground at (%d, %d) is y%d, more than one from the stone's y%d"
                               % (hub["id"], s["x"] + dx, s["z"] + dz, gy, s["y"] - 1))
        try:
            cols, wet = builder_columns(hub, g)
        except HubError as e:
            bad.append(str(e))
            continue
        for dx in range(-PAD, PAD + 1):
            for dz in range(-PAD, PAD + 1):
                c = (s["x"] + dx, s["z"] + dz)
                if c in cols:
                    bad.append("%s: (%d, %d) is a column %s writes (the stone needs its 3 x 3 clear)"
                               % (hub["id"], c[0], c[1], hub["builder"]))
                if wet(*c):
                    bad.append("%s: (%d, %d) is wet" % (hub["id"], c[0], c[1]))
        if (s["x"], s["z"]) in seen:
            bad.append("%s and %s share the column (%d, %d)" % (hub["id"], seen[(s["x"], s["z"])], s["x"], s["z"]))
        seen[(s["x"], s["z"])] = hub["id"]
    return bad


# ------------------------------------------------------------------------------------------------------------- output
def hold(s):
    """The forceload box a step holds while the function runs: the sweep's reach, a chunk each way."""
    return (s["x"] - CLEAR - 1, s["z"] - CLEAR - 1, s["x"] + CLEAR + 1, s["z"] + CLEAR + 1)


def function_lines(s):
    """The commands for one hub, as tools/place_town.py sets a town's waystone, after the older one is swept."""
    x, y, z, f = s["x"], s["y"], s["z"], s["facing"]
    return [
        "# Generated by tools/hub_waystones.py from data/hub_waystones.json (%s). Re-run to rebuild." % s["id"],
        "# chunks-loaded-by: tools/reapply.py R18W (forceload add over the stone's box, then a wait, before this runs)",
        "# the hub waystone: the lower half one above the heightmap ground, the same facing as the place's record",
        "fill %d %d %d %d %d %d minecraft:air replace %s"
        % (x - CLEAR, y + BOX_Y[0], z - CLEAR, x + CLEAR, y + BOX_Y[1], z + CLEAR, BLOCK),
        "setblock %d %d %d %s[half=lower,facing=%s]" % (x, y, z, BLOCK, f),
        "setblock %d %d %d %s[half=upper,facing=%s]" % (x, y + 1, z, BLOCK, f),
    ]


def plan(doc=None, g=None):
    """[{id, x, y, z, facing, lines, hold}] for every hub, after the checks pass."""
    import ground as G
    doc = doc or load()
    g = g or G.load()
    bad = problems(doc, g)
    if bad:
        raise HubError("data/hub_waystones.json: " + "; ".join(bad))
    out = []
    for hub in doc["hubs"]:
        s = stone(hub, g)
        s["lines"] = function_lines(s)
        s["hold"] = hold(s)
        out.append(s)
    return out


def files(doc=None, g=None):
    import function_limits
    out = {"pack.mcmeta": json.dumps({"pack": {"pack_format": PACK_FORMAT, "description":
                                               "Cobblers: the hub waystones (tools/hub_waystones.py)"}}, indent=2) + "\n"}
    for s in plan(doc, g):
        rel = "data/%s/function/%s/%s.mcfunction" % (NS, FN, s["id"])
        refusals = function_limits.check_lines(s["lines"], rel)
        if refusals:
            raise HubError("%s: %d command(s) the server would refuse: %s" % (rel, len(refusals), refusals))
        out[rel] = "\n".join(s["lines"]) + "\n"
    return out


def write(out_files, out):
    out = Path(out)
    if out.exists():
        shutil.rmtree(out)
    for rel, text in out_files.items():
        f = out / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(text, encoding="utf-8", newline="\n")


def placement_steps(doc=None, g=None):
    """For tools/reapply.py, step R18W: per hub, hold its chunks, set the stone, release (drovers_hollow's shape)."""
    out = []
    for s in plan(doc, g):
        box = "%d %d %d %d" % s["hold"]
        out += [("cmd", "forceload add " + box), ("wait", 3), ("fn", "%s:%s/%s" % (NS, FN, s["id"])),
                ("cmd", "forceload remove " + box)]
    return out


def probes(doc=None, g=None):
    """data/world_probes.json places.hub_waystones: both halves of every stone, with the facing it was set with."""
    out = []
    for s in plan(doc, g):
        for half, dy in (("lower", 0), ("upper", 1)):
            st = "%s[half=%s,facing=%s]" % (BLOCK, half, s["facing"])
            out.append({"what": "%s: the hub waystone, %s half" % (s["id"], half),
                        "block": [s["x"], s["y"] + dy, s["z"], st], "expect": True})
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("check")
    b = sub.add_parser("build")
    b.add_argument("--out", default=str(DEFAULT_OUT))
    q = sub.add_parser("probes")
    q.add_argument("--write", action="store_true")
    for s in (c, b, q):
        s.add_argument("--source-root", default=None)
    a = ap.parse_args(argv)
    if a.source_root:
        os.environ["COBBLERS_SOURCE_ROOT"] = a.source_root
    try:
        doc = load()
        if a.cmd == "check":
            pl = plan(doc)
            for s in pl:
                print("%-20s waystone at (%d, %d, %d) facing %s" % (s["id"], s["x"], s["y"], s["z"], s["facing"]))
            print("%d hub waystone(s) checked, no problem" % len(pl))
        elif a.cmd == "build":
            fl = files(doc)
            write(fl, a.out)
            print("wrote %s (%d function(s))" % (a.out, len(fl) - 1))
        else:
            pr = probes(doc)
            if a.write:
                w = json.loads(PROBES.read_text(encoding="utf-8"))
                w["places"]["hub_waystones"] = pr
                PROBES.write_text(json.dumps(w, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
                print("wrote %d probe(s) into data/world_probes.json places.hub_waystones" % len(pr))
            else:
                print(json.dumps(pr, indent=2))
    except HubError as e:
        print("hub_waystones: %s" % e, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
