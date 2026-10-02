#!/usr/bin/env python
"""Clear what the drowned Jungle Isle left standing in a world (decision B15, 2026-10-02).

The water export put the Jungle Isle under the sea, but two things built on its old ground stayed in the world:

  elders   the four jungle elders that data/elder_trees.json moved to Long Isle south on 2026-10-02. Each old tree
           still stands on its pre-water ground (`superseded_site`), 17-68 blocks over the sea, with its four bird
           Habitat Blocks in the trunk. Cleared: the prefab's own blocks (jungle_log, jungle_leaves; read from the
           elder prefabs) plus the Habitat Block, vines and cocoa, in the prefab's reach round the old trunk, and
           only above sea level, so the seabed is never touched.
  ruins    the retired `jungle_ruins` settlement (data/placements.json settlements.jungle_ruins.retired). Its
           ruin_great_hall cluster stood at its pre-2026-09-30 seat of y126 on a dirt column down to stone,
           measured in staging-2026-10-01 on 2026-10-02 at x5140-5180, z7470-7500, dirt y56-128 under an
           underwater-ruin template. Cleared: everything above sea level in that box, and the dirt between the
           heightmap's ground (tools/ground.py, rounded) and sea level becomes water again.

What it does NOT cover: anything else the Jungle Isle carried that a later look in game finds; the box list here
is exactly the two kinds above. Ground comes from the heightmap; the world is only written, never read to decide.

  python tools/clear_jungle_residue.py plan            print every command
  python tools/clear_jungle_residue.py run --server-dir <dir>   send them over RCON (needs the coordination lock)
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TOOLS = ROOT / "tools"
sys.path.insert(0, str(TOOLS))

SEA = 62                                  # data/world.json sea_level: the water's top layer
FILL_MAX = 32768                          # /fill's block limit
REACH = 42                                # elder prefab: crown radius 19 + limb reach 17, plus the 7x7 trunk's half
TREE_UP = 86                              # prefab height 84 plus its 2-layer root origin
TREE_DOWN = 4
TREE_BLOCKS = ("minecraft:jungle_log", "minecraft:jungle_leaves", "cobblemon:habitat_block",
               "minecraft:vine", "minecraft:cocoa")
RUIN_BOX = (5136, 7466, 5184, 7504)       # the measured column x5140-5180, z7470-7500, plus 4 blocks of margin
RUIN_TOP = 150                            # an underwater_ruin template is 16 tall on the y129 cap


def elder_boxes():
    doc = json.loads((ROOT / "data" / "elder_trees.json").read_text(encoding="utf-8"))
    out = []
    for e in doc["elders"]:
        s = e.get("superseded_site")
        if not s:
            continue
        g = s["pre_water_ground_y"]
        out.append((e["id"], s["x"] - REACH, max(SEA + 1, g - TREE_DOWN), s["z"] - REACH,
                    s["x"] + REACH, g + TREE_UP, s["z"] + REACH))
    return out


def protected():
    """[(x0, z0, x1, z1)] never written: Pacifidlog's fishing stations and the row they stand on
    (data/sea_town.json stations; the raft town is built partly of jungle_log, one of the blocks an elder clear
    removes). The Current Gate raft's stations at (4970, 7373-7383) stand inside the old elder_jungle_west_2's reach."""
    st = json.loads((ROOT / "data" / "sea_town.json").read_text(encoding="utf-8"))["stations"]
    out = []
    for run in st.get("runs", []):
        # the row runs along x and ends in its T-head, whose stations are the ones nearest the row's far end; its
        # z band is theirs (the T-head spans the 5-wide pier). Stations elsewhere (the Current Gate's raft) are
        # protected one by one below, not by widening this band
        end = min(st["at"], key=lambda s: abs(s["at"][0] - run["to"]))["at"]
        head = [s["at"] for s in st["at"] if abs(s["at"][0] - end[0]) <= 8 and abs(s["at"][1] - end[1]) <= 16]
        zs = [q[1] for q in head]
        out.append((min(min(q[0] for q in head), run["to"]) - 8, min(zs) - 8,
                    max(run["from"], run["to"]) + 8, max(zs) + 8))
    for s in st["at"]:                       # 16 round a lone station: its raft is not sized in the data
        out.append((s["at"][0] - 16, s["at"][1] - 16, s["at"][0] + 16, s["at"][1] + 16))
    return out


def minus(box, cuts):
    """box (x0, z0, x1, z1) with every cut rectangle removed, as disjoint rectangles."""
    parts = [box]
    for cx0, cz0, cx1, cz1 in cuts:
        nxt = []
        for x0, z0, x1, z1 in parts:
            if cx1 < x0 or cx0 > x1 or cz1 < z0 or cz0 > z1:
                nxt.append((x0, z0, x1, z1))
                continue
            if z0 < cz0:
                nxt.append((x0, z0, x1, cz0 - 1))
            if cz1 < z1:
                nxt.append((x0, cz1 + 1, x1, z1))
            mz0, mz1 = max(z0, cz0), min(z1, cz1)
            if x0 < cx0:
                nxt.append((x0, mz0, cx0 - 1, mz1))
            if cx1 < x1:
                nxt.append((cx1 + 1, mz0, x1, mz1))
        parts = nxt
    return parts


def slabs(x0, y0, z0, x1, y1, z1):
    """[(x0, ya, z0, x1, yb, z1)] in y slabs no larger than /fill allows."""
    per = max(1, FILL_MAX // ((x1 - x0 + 1) * (z1 - z0 + 1)))
    y = y0
    while y <= y1:
        yield x0, y, z0, x1, min(y1, y + per - 1), z1
        y += per


def commands():
    """[(label, forceload box, [command])]"""
    out = []
    for eid, x0, y0, z0, x1, y1, z1 in elder_boxes():
        cmds = ["fill %d %d %d %d %d %d minecraft:air replace %s" % (a + (b,))
                for px0, pz0, px1, pz1 in minus((x0, z0, x1, z1), protected())
                for a in slabs(px0, y0, pz0, px1, y1, pz1) for b in TREE_BLOCKS]
        out.append(("the old %s" % eid, (x0, z0, x1, z1), cmds))
    doc = json.loads((ROOT / "data" / "placements.json").read_text(encoding="utf-8"))
    if doc["settlements"].get("jungle_ruins", {}).get("retired"):
        import ground as G
        gr = G.load()
        x0, z0, x1, z1 = RUIN_BOX
        cmds = ["fill %d %d %d %d %d %d minecraft:air" % s for s in slabs(x0, SEA + 1, z0, x1, RUIN_TOP, z1)]
        for x in range(x0, x1 + 1):
            for z in range(z0, z1 + 1):
                g = int(round(gr(x, z)))
                if g + 1 <= SEA:
                    cmds.append("fill %d %d %d %d %d %d minecraft:water replace minecraft:dirt" % (x, g + 1, z, x, SEA, z))
        out.append(("the retired jungle_ruins' old y126 seat", (x0, z0, x1, z1), cmds))
    return out


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("mode", choices=("plan", "run"))
    p.add_argument("--server-dir", default="C:/Users/wnd/Documents/github/cobblers-server")
    a = p.parse_args(argv)
    work = commands()
    if a.mode == "plan":
        for label, box, cmds in work:
            print("# %s: forceload %s, %d commands" % (label, box, len(cmds)))
            for c in cmds:
                print(c)
        return
    import reapply
    rc = reapply.Rcon(a.server_dir)
    for label, (x0, z0, x1, z1), cmds in work:
        print(rc("forceload add %d %d %d %d" % (x0, z0, x1, z1)).strip())
        changed = 0
        for c in cmds:
            for _ in range(20):
                r = rc(c)
                if "not loaded" not in r:
                    break
                time.sleep(0.5)
            else:
                raise SystemExit("%s: still not loaded after 10 s: %s" % (label, c))
            if r.startswith("Successfully filled"):
                changed += int(r.split()[2])
            elif "No blocks were filled" not in r and r.strip():
                raise SystemExit("%s: %s -> %s" % (label, c, r.strip()))
        print(rc("forceload remove %d %d %d %d" % (x0, z0, x1, z1)).strip())
        print("%s: %d blocks changed" % (label, changed))


if __name__ == "__main__":
    main()
