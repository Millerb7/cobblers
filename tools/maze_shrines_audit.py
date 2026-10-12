#!/usr/bin/env python
"""The maze forest's glade shrines against the maze plan, the heightmap, the legendaries and the finds: offline, fail-closed.

tools/maze_shrines.py writes `cobblers:maze_shrines/<id>` from data/maze_shrines.json. This audit reads those written
functions (the output) and checks every write against data it reads and computes on its own. It imports none of the
generator's geometry (no piece, no clearance, no glade or fit function): what it takes from tools/maze_forest.py is the
PLAN itself (NETWORK, CLEARINGS, BOX) and the forest's own lantern-post pass (path_dressing), which the generator did not
write either; every distance below is its own pure-python arithmetic, not maze_forest.polyline_distance.

  present   one function per shrine data/maze_shrines.json lists, the pack's index names exactly them, each writes between
            12 and 80 blocks, and the run holds its chunks (tools/function_limits.py check_lines)
  glades    the shrines' glades are exactly the plan's openings of kind "glade" and "secret" (derived here from the plan,
            not from the data), one shrine each; no write inside the sapling clearing or the mansion clearing
  disc      every written column lies within the glade's radius less the data's disc margin of its centre, and the
            piece's footprint is at most 5 wide and 4 deep
  path      no written or cleared column is within `path_clearance` of any corridor's walkable edge (every NETWORK corridor
            brushed at half its width: the braids, the 3-wide dead ends and the 2-wide hidden paths included), and none
            within `post_clearance` of a lantern post the forest sets at a fork
  ground    every column's lowest block stands exactly one over the heightmap's ground (tools/ground.py, rounded) at the
            column's highest-ground neighbour or its own; the ground under a piece varies by at most 1; nothing floats
  blocks    every block is in data/maze_shrines.json `blocks`, exists in the Minecraft 1.21.1 client jar's blockstates, and
            is no spawn condition in data/spawn_blocks.json; no light block; a lantern stands on a fence post; fills only
            ever write air (the clearing), only over columns the piece writes
  hints     each tablet's legendary is an encounter in data/legendaries.json with the species, site and a status
            (sited / gate_only) the record claims; the upper tablet's first line is the species; a compass word on a
            tablet is declared in the data and true of the bearing from the shrine to that encounter's mouth or portal
            (north is -z), and a tablet says no direction the data does not declare; lines are at most 14 characters
  finds     a stele holds exactly one barrel, at its data/rewards.json record's container, whose trigger is the 3 by 3
            box round it, with early consumables only (a short allow-list) and a handful of items; an old shrine holds no
            barrel and writes nothing in the trigger box of the find route_events.py already placed in its glade

Not covered: the routed leg of Route 1 (derived/routes is gitignored and absent in a worktree; the corridors are the
walk line here and are held clear on their own), painted trees in a glade (build/paint), and anything about the live world.

  python tools/maze_shrines_audit.py [--pack build/datapacks/cobblers_maze_shrines]
"""
from __future__ import annotations

import argparse
import json
import math
import re
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
from terrain import env_source_root  # noqa: E402  (the env var, else .claude/settings.json)

PACK = ROOT / "build" / "datapacks" / "cobblers_maze_shrines"
FOLDER = "maze_shrines"
FIND_ITEMS = {"cobblemon:oran_berry", "cobblemon:pecha_berry", "cobblemon:cheri_berry", "cobblemon:chesto_berry",
              "cobblemon:rawst_berry", "cobblemon:aspear_berry", "cobblemon:potion", "cobblemon:poke_ball",
              "cobblemon:antidote", "cobblemon:great_ball"}
COMPASS = ("north", "south", "east", "west")
CLEAR_FILL = re.compile(r"^fill (-?\d+) (-?\d+) (-?\d+) (-?\d+) (-?\d+) (-?\d+) minecraft:air replace (#minecraft:\w+)$")
STATUS_OK = ("sited", "gate_only")


def load(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def block_name(state):
    return state.split("[", 1)[0].split("{", 1)[0]


def parse(lines):
    """(setblocks, fills): [(x, y, z, state, nbt)] and [(x0, y0, z0, x1, y1, z1, filter)]; anything else is returned as odd."""
    sets, fills, odd = [], [], []
    for raw in lines:
        line = raw.strip()
        if not line or line.startswith("#") or line.startswith("forceload"):
            continue
        if line.startswith("setblock "):
            _, x, y, z, rest = line.split(" ", 4)
            i = rest.find("{")
            sets.append((int(x), int(y), int(z), rest if i < 0 else rest[:i], "" if i < 0 else rest[i:]))
            continue
        m = CLEAR_FILL.match(line)
        if m:
            fills.append(tuple(int(v) for v in m.groups()[:6]) + (m.group(7),))
            continue
        odd.append(line)
    return sets, fills, odd


def sign_lines(nbt):
    """The four lines of a sign's front text, read back from the written NBT."""
    m = re.search(r"messages:\[(.*?)\]\}", nbt)
    if not m:
        return None
    out = []
    for s in re.finditer(r"'((?:[^'\\]|\\.)*)'", m.group(1)):
        out.append(json.loads(s.group(1).replace("\\'", "'")))
    return out


def seg_edge_distance(x, z, nodes, width):
    """Blocks from (x, z) to the walkable edge of a corridor polyline (negative inside): plain arithmetic."""
    best = 1e18
    for (ax, az), (bx, bz) in zip(nodes, nodes[1:]):
        vx, vz = bx - ax, bz - az
        L = vx * vx + vz * vz
        t = 0.0 if L == 0 else max(0.0, min(1.0, ((x - ax) * vx + (z - az) * vz) / L))
        best = min(best, math.hypot(x - (ax + t * vx), z - (az + t * vz)))
    return best - width / 2.0


def vanilla_blocks():
    import town_character as TC
    jar = TC.default_vanilla_jar()
    if jar is None or not Path(jar).is_file():
        return None
    with zipfile.ZipFile(jar) as z:
        return {"minecraft:" + n.rsplit("/", 1)[1][:-5] for n in z.namelist()
                if n.startswith("assets/minecraft/blockstates/") and n.endswith(".json")}


def encounter_point(enc, celebi_cfg):
    """(x, z) of an encounter's mouth or portal, or the sleeping Celebi's position."""
    for k in ("mouth", "portal"):
        if isinstance(enc.get(k), list) and len(enc[k]) >= 2:
            return enc[k][0], enc[k][-1]
    if enc.get("species") == "celebi":
        return celebi_cfg["position"][0], celebi_cfg["position"][2]
    return None


def audit(pack=PACK, source_root=None):
    """(problems, number of writes checked)."""
    import ground as G
    import function_limits as FL
    import maze_forest as MF

    problems = []
    data = load(ROOT / "data" / "maze_shrines.json")
    shrines = data.get("shrines") or []
    rules = data.get("rules") or {}
    if not shrines:
        return ["data/maze_shrines.json lists no shrine: nothing to audit is not a clean audit"], 0
    fdir = Path(pack) / "data" / "cobblers" / "function" / FOLDER
    if not fdir.is_dir():
        return ["no %s: run python tools/maze_shrines.py build" % fdir], 0
    ids = [s["id"] for s in shrines]
    index = fdir / "index.txt"
    listed = [x for x in index.read_text(encoding="utf-8").split("\n") if x.strip()] if index.is_file() else None
    if listed != ids:
        problems.append("index.txt lists %r, not the data's %r" % (listed, ids))
    on_disk = sorted(p.stem for p in fdir.glob("*.mcfunction"))
    if on_disk != sorted(ids):
        problems.append("functions on disk %r are not the data's shrines %r" % (on_disk, sorted(ids)))

    # the plan's openings, derived here
    plan = {c["id"]: c for c in MF.CLEARINGS}
    want = sorted(c["id"] for c in MF.CLEARINGS if c["kind"] in ("glade", "secret"))
    got = sorted(s["glade"] for s in shrines)
    if got != want:
        problems.append("the shrines' glades %r are not the plan's glades and secret glades %r" % (got, want))
    ground = G.Ground(source_root)
    posts = []
    import re as _re
    tiles, _ = MF.path_dressing(G.load(source_root).box(*MF.BOX), MF.BOX)
    for cmds in tiles.values():
        for c in cmds:
            m = _re.match(r"^setblock (-?\d+) -?\d+ (-?\d+) minecraft:oak_fence", c)
            if m:
                posts.append((int(m.group(1)), int(m.group(2))))

    allowed = set((data.get("blocks") or {}).get("ids") or [])
    vanilla = vanilla_blocks()
    spawn = set(load(ROOT / "data" / "spawn_blocks.json")["blocks"])
    legs = {e["id"]: e for e in load(ROOT / "data" / "legendaries.json")["encounters"]}
    celebi_cfg = load(ROOT / "data" / "sapling_celebi.json")
    rewards = {r["id"]: r for r in load(ROOT / "data" / "rewards.json")["rewards"]}
    total, claimed = 0, {}

    for spec in shrines:
        sid = spec["id"]
        f = fdir / ("%s.mcfunction" % sid)
        if not f.is_file():
            problems.append("%s: no function" % sid)
            continue
        lines = f.read_text(encoding="utf-8").splitlines()
        for _n, cmd, why in FL.check_lines(lines, sid):
            problems.append("%s: %s (%s)" % (sid, why, cmd[:60]))
        sets, fills, odd = parse(lines)
        for o in odd:
            problems.append("%s: a line that is neither a setblock, an air clearing nor a forceload: %s" % (sid, o[:70]))
        total += len(sets)
        if not (12 <= len(sets) <= 80):
            problems.append("%s: writes %d blocks (a small shrine is 12 to 80)" % (sid, len(sets)))
        if not any(l.startswith("forceload add") for l in lines):
            problems.append("%s: the function does not force-load the chunks it writes" % sid)
        glade = plan.get(spec["glade"])
        if glade is None:
            problems.append("%s: glade %r is not in the maze plan" % (sid, spec["glade"]))
            continue
        cx, cz = glade["at"]
        cols = {}
        for x, y, z, state, _nbt in sets:
            cols.setdefault((x, z), []).append((y, state))
        fcols = {(x, z) for x0, _y0, z0, x1, _y1, z1, _t in fills for x in range(x0, x1 + 1) for z in range(z0, z1 + 1)}
        if not fcols <= set(cols):
            problems.append("%s: the clearing fills reach columns the piece does not write, e.g. %s"
                            % (sid, sorted(fcols - set(cols))[:3]))
        for (x, z), cl in cols.items():
            if claimed.setdefault((x, z), sid) != sid:
                problems.append("%s overlaps %s at (%d, %d)" % (sid, claimed[(x, z)], x, z))
        xs, zs = [c[0] for c in cols], [c[1] for c in cols]
        w, d = max(xs) - min(xs) + 1, max(zs) - min(zs) + 1
        if max(w, d) > 5 or min(w, d) > 4:
            problems.append("%s: footprint %d by %d (at most 5 by 4)" % (sid, w, d))
        for (x, z), cl in sorted(cols.items()):
            dist = math.hypot(x - cx, z - cz)
            if dist > glade["r"] - rules.get("disc_margin", 0.5):
                problems.append("%s: (%d, %d) is %.1f from the %s centre, outside r%d less the margin"
                                % (sid, x, z, dist, spec["glade"], glade["r"]))
            for other in ("sapling", "mansion"):
                o = plan[other]
                if math.hypot(x - o["at"][0], z - o["at"][1]) <= o["r"]:
                    problems.append("%s: (%d, %d) is inside the %s clearing, which stays as it is" % (sid, x, z, other))
            for c in MF.NETWORK:
                e = seg_edge_distance(x, z, c["nodes"], c["width"])
                if e < rules.get("path_clearance", 1):
                    problems.append("%s: (%d, %d) is %.1f from the edge of corridor %s (needs %s)"
                                    % (sid, x, z, e, c["id"], rules.get("path_clearance", 1)))
                    break
            for px, pz in posts:
                if max(abs(x - px), abs(z - pz)) <= rules.get("post_clearance", 1):
                    problems.append("%s: (%d, %d) is beside the lantern post at (%d, %d)" % (sid, x, z, px, pz))
        gs = {c: ground(*c) for c in cols}
        if max(gs.values()) - min(gs.values()) > 1:
            problems.append("%s: the heightmap's ground varies by %d under it" % (sid, max(gs.values()) - min(gs.values())))
        floor = max(gs.values()) + 1
        for (x, z), cl in cols.items():
            low = min(y for y, _s in cl)
            if low not in (gs[(x, z)] + 1, floor):
                problems.append("%s: column (%d, %d) starts at y%d; the ground there is y%d (floor y%d): floating or buried"
                                % (sid, x, z, low, gs[(x, z)], floor))
        for x0, y0, z0, x1, y1, z1, tag in fills:
            if y0 < min(gs.values()) or tag not in ("#minecraft:replaceable", "#minecraft:logs", "#minecraft:leaves"):
                problems.append("%s: a clearing fill that reaches below the ground or filters on %s" % (sid, tag))
        by_pos = {(x, y, z): s for x, y, z, s, _n in sets}
        for x, y, z, state, nbt in sets:
            name = block_name(state)
            if name not in allowed:
                problems.append("%s: %s is not in data/maze_shrines.json `blocks`" % (sid, name))
            if vanilla is not None and name not in vanilla:
                problems.append("%s: %s is not a Minecraft 1.21.1 block" % (sid, name))
            if name in spawn:
                problems.append("%s: %s is a spawn condition (data/spawn_blocks.json)" % (sid, name))
            if name in ("minecraft:light", "minecraft:air", "minecraft:barrier"):
                problems.append("%s: %s written at (%d, %d, %d)" % (sid, name, x, y, z))
            if name == "minecraft:lantern" and block_name(by_pos.get((x, y - 1, z), "")) not in ("minecraft:oak_fence",):
                problems.append("%s: the lantern at (%d, %d, %d) is not on a fence post" % (sid, x, y, z))

        # the tablets
        leg = spec["legendary"]
        enc = legs.get(leg["id"])
        signs = [(x, y, z, nbt) for x, y, z, s, nbt in sets if block_name(s).endswith("_wall_sign")]
        if len(signs) != 2:
            problems.append("%s: %d tablets, not 2" % (sid, len(signs)))
        texts = [sign_lines(n) for *_p, n in signs]
        want_texts = [spec["signs"]["lower"], spec["signs"]["upper"]]
        for t in texts:
            if t is None or len(t) != 4:
                problems.append("%s: a tablet's text did not parse back" % sid)
        said = [[(l or "") for l in t] for t in texts if t]
        for ws in want_texts:
            if [(l or "") for l in (list(ws) + [""] * 4)[:4]] not in said:
                problems.append("%s: a tablet in the data (%s) is not what the function writes" % (sid, ws[0]))
        for t in said:
            for l in t:
                if len(l) > rules.get("max_line_chars", 14):
                    problems.append("%s: tablet line %r is %d characters (at most %d)" % (sid, l, len(l), rules.get("max_line_chars", 14)))
        if enc is None:
            problems.append("%s: no encounter %r in data/legendaries.json" % (sid, leg["id"]))
        else:
            if enc.get("species") != leg["species"] or enc.get("site") != leg["site"]:
                problems.append("%s: the data/legendaries.json record says species %r site %r, not %r %r"
                                % (sid, enc.get("species"), enc.get("site"), leg["species"], leg["site"]))
            if enc.get("status") not in STATUS_OK:
                problems.append("%s: the encounter's status is %r; a hint toward it is not yet true" % (sid, enc.get("status")))
            upper = spec["signs"]["upper"][0].replace(" ", "").lower()
            if upper != enc["species"]:
                problems.append("%s: the upper tablet says %r, the species is %r" % (sid, spec["signs"]["upper"][0], enc["species"]))
            alltext = " ".join(l for t in said for l in t).lower()
            words = [w for w in COMPASS if re.search(r"\b%s\b" % w, alltext)]
            declared = leg.get("direction")
            if (words or declared) and words != ([declared] if declared else []):
                problems.append("%s: tablets say %r, the data declares %r" % (sid, words, declared))
            pt = encounter_point(enc, celebi_cfg)
            if declared and pt is None:
                problems.append("%s: no mouth or portal to take a bearing to" % sid)
            elif declared:
                dx, dz = pt[0] - spec["at"][0], pt[1] - spec["at"][1]
                real = ("east" if dx > 0 else "west") if abs(dx) >= abs(dz) else ("south" if dz > 0 else "north")
                if real != declared:
                    problems.append("%s: the tablet says %s, but %s lies %s of it (dx %d, dz %d)"
                                    % (sid, declared, leg["id"], real, dx, dz))

        # the finds
        barrels = [(x, y, z) for x, y, z, s, _n in sets if block_name(s) == "minecraft:barrel"]
        if spec["kind"] == "stele":
            r = rewards.get(spec.get("reward"))
            if r is None or r.get("kind") != "cache":
                problems.append("%s: no cache record %r in data/rewards.json" % (sid, spec.get("reward")))
            elif len(barrels) != 1:
                problems.append("%s: %d barrels, not 1" % (sid, len(barrels)))
            else:
                bx, by, bz = barrels[0]
                if r["container"]["at"] != [bx, by, bz]:
                    problems.append("%s: %s container %s is not the barrel at %s" % (sid, r["id"], r["container"]["at"], [bx, by, bz]))
                if r["trigger"] != {"min": [bx - 1, by - 1, bz - 1], "max": [bx + 1, by + 2, bz + 1]}:
                    problems.append("%s: %s trigger %s is not the 3 by 3 box round the barrel" % (sid, r["id"], r["trigger"]))
                items = r.get("contents") or []
                if sum(c["count"] for c in items) > rules.get("max_find_items", 6):
                    problems.append("%s: %s holds %d items (at most %d)" % (sid, r["id"], sum(c["count"] for c in items), rules.get("max_find_items", 6)))
                for c in items:
                    if c["item"] not in FIND_ITEMS or c.get("components"):
                        problems.append("%s: %s gives %s, which is not an early consumable" % (sid, r["id"], c["item"]))
                if not r.get("message"):
                    problems.append("%s: %s has no message" % (sid, r["id"]))
        else:
            if barrels:
                problems.append("%s: an old shrine holds no barrel of its own (the glade's find is route_events.py's)" % sid)
            ex = rewards.get(spec.get("existing_find"))
            if ex is None:
                problems.append("%s: no record %r in data/rewards.json" % (sid, spec.get("existing_find")))
            else:
                lo, hi = ex["trigger"]["min"], ex["trigger"]["max"]
                for (x, z) in cols:
                    if lo[0] <= x <= hi[0] and lo[2] <= z <= hi[2]:
                        problems.append("%s: (%d, %d) is inside the trigger box of %s" % (sid, x, z, ex["id"]))
    if vanilla is None:
        problems.append("the Minecraft 1.21.1 client jar was not found: block names were not checked against it")
    return problems, total


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--pack", default=str(PACK))
    p.add_argument("source_root", nargs="?", default=None)
    p.add_argument("--source-root", dest="sr", default=None)
    a = p.parse_args(argv)
    problems, n = audit(a.pack, a.sr or a.source_root or env_source_root())
    for m in problems:
        print("PROBLEM %s" % m)
    print("maze_shrines_audit: %d problem(s); %d block writes checked in %s" % (len(problems), n, a.pack))
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
