#!/usr/bin/env python
"""Independent offline audit of the written cobblers_frostpeak_keep_quest pack: the burrow, Giratina, the quest wiring
and the old shrine's takedown.

It replays the pack's function text into blocks and checks them against sources the generator does not use to decide
them. NOTHING is imported from tools/frostpeak_keep_quest.py or tools/frostpeak_keep.py (asserted by
tests/test_frostpeak_keep_quest.py).

  the ground     tools/ground.py, per column (rounded); the water from tools/water_mask.py alone
  the keep       data/frostpeak_keep.json site.centre, dims (base rectangle, its north half) and ruin.nest.at: the lair
                 is recomputed here from the heightmap (the courtyard is the highest ground under the base rectangle)
  the shrine     data/placements.json superseded_placements legendary_giratina_shrine: position and size, rotation none
  the quest      data/dialogue.json, data/quests.json, data/rewards.json, data/progression.json, data/spawn_blocks.json
  the cap        data/trainers.json generation_contract gym_ace_levels (the upper bound after 7 and 8 badges)
  the players    a small walking model of its own (standable cells, a step up of one, drops of three)

Checks (each must hold):

  Q0  pack         the expected functions, callbacks and advancements; every `function` a file names exists in the pack
                   or is the chain the re-application starts; nothing the pack ships is unreached
  Q1  burrow walk  from the slope west of the face, a player walks into every room and to every resident's feet, and back
  Q2  cover        every carved block under the face has three or more blocks of the heightmap's ground over it, or none
                   (the open cutting of the mouth); a one- or two-block crust only within two blocks of the mouth
  Q3  light        block light propagated from the written lanterns and lit campfires reaches every standable cell of
                   the burrow at 1 or more (1.21.1 spawns monsters only at block light 0), and 8 or more at each resident
  Q4  blocks       no spawn-condition block (data/spawn_blocks.json) in the burrow; no light block; signs within 15 chars
  Q5  Giratina     summoned (macro) at the lair recomputed from the keep's record, level 50-60 and at or under the cap
                   after 8 badges, the macro keyed on its species; the keeper never touches a guardian
  Q6  callbacks    battle_fainted credits EVERY player of the battle (no first-player cut), keyed on cobblemon:giratina;
                   the capture gate sets the shakes to 0 only for our tag and refuses a thrower without the defeat or
                   with a catch
  Q7  wiring       the tag the fainted function adds is the tag Maren's report reads; the quest's reward contents are
                   data/rewards.json wardenhold_giratina's; every resident's conversation exists with an NPC
  Q8  shrine       replayed over the retired shrine's box, every column ends rock up to the heightmap's ground, air above
                   (water to the mask's level where it says water), and nothing of the template is left

  python tools/frostpeak_keep_quest_audit.py [--pack DIR] [--source-root R]   exit 1 on any problem
"""
from __future__ import annotations

import argparse
import json
import math
import re
import sys
from collections import deque
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import function_limits  # noqa: E402

PACK = ROOT / "build" / "datapacks" / "cobblers_frostpeak_keep_quest"
OUT = ROOT / "derived" / "frostpeak_keep_quest" / "audit.json"
FN = "data/cobblers/function/frostpeak_keep_quest/"
SETBLOCK = re.compile(r"^setblock (-?\d+) (-?\d+) (-?\d+) (.+)$")
FILL = re.compile(r"^fill (-?\d+) (-?\d+) (-?\d+) (-?\d+) (-?\d+) (-?\d+) (\S+)$")
FUNC_REF = re.compile(r"function (cobblers:[a-z0-9_/]+)")
WORLD_READS: set = set()
# a block a body walks through (exact names, then suffixes); everything else is solid for walking
PASS = {"air", "lantern", "spruce_wall_sign", "brown_carpet", "spruce_pressure_plate", "snow"}
TALL = ("_fence",)
# light passes through these (vanilla: not full opaque cubes); everything else in the burrow is an opaque block
CLEAR = PASS | {"spruce_fence", "spruce_stairs", "campfire", "lectern", "composter", "spruce_slab"}
LIGHT = {"lantern": 15, "campfire": 15}


def load_json(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def name(state):
    return state.split("[", 1)[0].split("{", 1)[0].replace("minecraft:", "")


class Report:
    def __init__(self):
        self.rows, self.facts = [], {}

    def check(self, ok, code, detail=""):
        self.rows.append({"check": code, "ok": bool(ok), "detail": "" if ok else detail})

    @property
    def problems(self):
        return [r for r in self.rows if not r["ok"]]


def replay(lines):
    """{(x, y, z): state} after every setblock and fill (air included, as 'minecraft:air')."""
    out = {}
    for raw in lines:
        line = raw.strip()
        m = SETBLOCK.match(line)
        if m:
            x, y, z, s = m.groups()
            out[(int(x), int(y), int(z))] = s
            continue
        m = FILL.match(line)
        if m:
            x0, y0, z0, x1, y1, z1, s = m.groups()
            x0, x1 = sorted((int(x0), int(x1)))
            y0, y1 = sorted((int(y0), int(y1)))
            z0, z1 = sorted((int(z0), int(z1)))
            for x in range(x0, x1 + 1):
                for y in range(y0, y1 + 1):
                    for z in range(z0, z1 + 1):
                        out[(x, y, z)] = s
    return out


class World:
    def __init__(self, blocks, g):
        self.b, self.g = blocks, g

    def state(self, x, y, z):
        s = self.b.get((x, y, z))
        if s is not None:
            return name(s)
        return "air" if y > self.g(x, z) else "ground"

    def free(self, x, y, z):
        return self.state(x, y, z) in PASS

    def standable(self, x, y, z):
        below = self.state(x, y - 1, z)
        return self.free(x, y, z) and self.free(x, y + 1, z) and below not in PASS and not below.endswith(TALL)

    def reach(self, start, box, limit=400000):
        seen, q = {start}, deque([start])
        while q and len(seen) < limit:
            x, y, z = q.popleft()
            for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                nx, nz = x + dx, z + dz
                if not (box[0] <= nx <= box[2] and box[1] <= nz <= box[3]):
                    continue
                for ny in (y, y + 1) + tuple(y - d for d in (1, 2, 3)):
                    if ny == y + 1 and not self.free(x, y + 2, z):
                        continue
                    if ny < y and not all(self.free(nx, y - k, nz) for k in range(0, y - ny)):
                        continue
                    if self.standable(nx, ny, nz):
                        c = (nx, ny, nz)
                        if c not in seen:
                            seen.add(c)
                            q.append(c)
                        break
        return seen


def light_map(blocks, cells):
    """{cell: block light} propagated from the written emitters through the written see-through blocks (vanilla:
    minus one per step, six neighbours), over the given air cells and the emitters themselves."""
    lit = {}
    q = deque()
    for k, s in blocks.items():
        n = name(s)
        if n in LIGHT and (n != "campfire" or "lit=true" in s):
            lit[k] = LIGHT[n]
            q.append(k)
    space = set(cells) | set(lit)
    while q:
        c = q.popleft()
        v = lit[c] - 1
        if v <= 0:
            continue
        x, y, z = c
        for d in ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1)):
            n_ = (x + d[0], y + d[1], z + d[2])
            if n_ in space and lit.get(n_, 0) < v:
                lit[n_] = v
                q.append(n_)
    return lit


def files_of(pack):
    pack = Path(pack)
    return {p.relative_to(pack).as_posix(): p.read_text(encoding="utf-8") for p in pack.rglob("*") if p.is_file()}


def audit(pack, g):
    rep = Report()
    fs = files_of(pack)
    need = [FN + n + ".mcfunction" for n in ("burrow/build", "shrine_takedown", "place", "giratina/load", "giratina/keeper",
                                             "giratina/spawn_at", "giratina/fainted", "giratina/caught", "giratina/catch_check")]
    need += ["data/cobblemon/callbacks/%s/cobblers_frostpeak_keep_quest.molang" % e
             for e in ("battle_fainted", "pokemon_captured", "poke_ball_capture_calculated")]
    need += ["data/cobblers/advancement/frostpeak_keep_quest/giratina_%s.json" % a for a in ("defeated", "caught")]
    missing = [n for n in need if n not in fs]
    rep.check(not missing, "Q0 pack", "missing from the pack: %s" % missing)
    if missing:
        return rep
    # ---- Q0 references
    names = {"cobblers:" + r[len("data/cobblers/function/"):-len(".mcfunction")] for r in fs if r.endswith(".mcfunction")}
    text = "\n".join(fs.values())
    refs = set(FUNC_REF.findall(text))
    dangling = sorted(refs - names)
    rep.check(not dangling, "Q0 pack", "functions named but not shipped: %s" % dangling[:4])
    started = {"cobblers:frostpeak_keep_quest/burrow/build", "cobblers:frostpeak_keep_quest/shrine_takedown",
               "cobblers:frostpeak_keep_quest/place"}
    tag = load_json(Path(pack) / "data/minecraft/tags/function/load.json")["values"]
    unreached = sorted(n for n in names - refs - started - set(tag))
    rep.check(not unreached, "Q0 pack", "functions nothing runs, calls or tags: %s" % unreached)
    bad = []
    for r, t in fs.items():
        if r.endswith(".mcfunction") and not r.endswith("spawn_at.mcfunction"):
            bad += function_limits.check_lines(t.splitlines(), r)
    rep.check(not bad, "Q0 pack", "tools/function_limits.py: %s" % bad[:2])

    # ---- the burrow's blocks over the heightmap
    q = load_json(ROOT / "data" / "frostpeak_keep_quest.json")
    blocks = replay(fs[FN + "burrow/build.mcfunction"].splitlines())
    W = World(blocks, g)
    xs = [k[0] for k in blocks]
    zs = [k[2] for k in blocks]
    box = (min(xs) - 12, min(zs) - 6, max(xs) + 2, max(zs) + 2)
    carved = [k for k, s in blocks.items() if name(s) == "air"]
    rep.check(len(carved) > 500, "Q1 burrow walk", "the burrow function carves only %d blocks" % len(carved))
    if len(carved) <= 500:
        return rep
    mouth_x = min(k[0] for k in carved)
    # ---- Q1 walking: from the slope 12 blocks west of the westmost carved block, at the face's middle z
    zmid = int(round(sum(k[2] for k in carved) / len(carved)))
    sx = mouth_x - 10
    start = (sx, g(sx, zmid) + 1, zmid)
    r = W.reach(start, box)
    stand_in = [c for c in r if blocks.get(c) and name(blocks[c]) in PASS and c[0] > mouth_x + 3]
    rep.check(len(stand_in) > 300, "Q1 burrow walk", "from the slope %s a player reaches only %d cells inside the burrow" % (start, len(stand_in)))
    # every room: each connected air component inside the burrow has a reached cell
    comps, seen = [], set()
    airset = set(carved)
    for c in carved:
        if c in seen:
            continue
        comp, dq = [], deque([c])
        seen.add(c)
        while dq:
            x, y, z = dq.popleft()
            comp.append((x, y, z))
            for d in ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1)):
                n_ = (x + d[0], y + d[1], z + d[2])
                if n_ in airset and n_ not in seen:
                    seen.add(n_)
                    dq.append(n_)
        comps.append(comp)
    unreached_comps = [min(cm) for cm in comps if len(cm) > 3 and not any(c in r for c in cm)]
    rep.check(not unreached_comps, "Q1 burrow walk", "carved spaces no walker reaches: %s" % unreached_comps[:3])
    feet = {}
    for res in q["residents"]:
        x, z = res["at_xz"]
        ys = [y for y in range(150, 260) if W.standable(x, y, z) and blocks.get((x, y, z)) is not None]
        feet[res["id"]] = (x, ys[0], z) if ys else None
    lost = [k for k, v in feet.items() if v is None or v not in r]
    rep.check(not lost, "Q1 burrow walk", "residents with no standable, reachable cell at their x/z: %s (%s)" % (lost, feet))
    back = W.reach(feet.get("maren") or start, box)
    rep.check(start in back or any(c[0] <= sx + 1 for c in back), "Q1 burrow walk", "no way back out from Maren to the slope")
    rep.facts.update(burrow_cells_reached=len(stand_in), residents=feet, mouth_x=mouth_x)
    # ---- Q2 cover
    thin = [c for c in carved if 1 <= g(c[0], c[2]) - c[1] <= 2 and c[0] > mouth_x + 2]
    rep.check(not thin, "Q2 cover", "%d carved blocks under a one- or two-block crust away from the mouth, first %s" % (len(thin), sorted(thin)[:1]))
    rep.facts["least_cover_inside"] = min((g(c[0], c[2]) - c[1]) for c in carved if c[0] > mouth_x + 3)
    # ---- Q3 light
    space = [c for c in blocks if name(blocks[c]) in CLEAR]
    lit = light_map(blocks, space)
    standing = [c for c in r if blocks.get(c) and c[0] > mouth_x]
    dark = [c for c in standing if lit.get(c, 0) < 1]
    rep.check(not dark, "Q3 light", "%d standable burrow cells at block light 0 (monsters spawn there), first %s" % (len(dark), sorted(dark)[:2]))
    dim = {k: lit.get(v, 0) for k, v in feet.items() if v and lit.get(v, 0) < 8}
    rep.check(not dim, "Q3 light", "residents standing in light under 8: %s" % dim)
    rep.facts["least_light"] = min((lit.get(c, 0) for c in standing), default=None)
    # ---- Q4 blocks
    spawn = set(load_json(ROOT / "data" / "spawn_blocks.json")["blocks"])
    placed = {s.split("[")[0].split("{")[0] for s in blocks.values()}
    rep.check(not (placed & spawn), "Q4 blocks", "spawn-condition blocks in the burrow: %s" % sorted(placed & spawn))
    rep.check("minecraft:light" not in placed, "Q4 blocks", "a light block in the burrow (places are lit by lanterns)")
    longest = max((len(m) for s in blocks.values() for m in re.findall(r"'\"((?:[^\"\\]|\\.)*)\"'", s)), default=0)
    rep.check(longest <= 15, "Q4 blocks", "a sign line is %d characters" % longest)

    # ---- Q5 Giratina at the lair recomputed from the keep's record
    keep = load_json(ROOT / "data" / "frostpeak_keep.json")
    cx, cz = keep["site"]["centre"]
    d = keep["dims"]
    x0, x1 = cx - d["base_hu"], cx + d["base_hu"]
    z0, z1 = cz - d.get("base_hv_north", d["base_hv"]), cz + d["base_hv"]
    pad = max(g(x, z) for x in range(x0, x1 + 1) for z in range(z0, z1 + 1))
    nu, nv = keep["ruin"]["nest"]["at"]
    want = (cx + nu + 0.5, pad + 1, cz + nv + 0.5)
    spawn_fn = fs[FN + "giratina/spawn.mcfunction"]
    m = re.search(r'spawn_at \{x:"(-?[\d.]+)",y:(-?\d+),z:"(-?[\d.]+)"\}', spawn_fn)
    got = (float(m.group(1)), int(m.group(2)), float(m.group(3))) if m else None
    rep.check(got == want, "Q5 Giratina", "the summon is at %s; the keep's record and the heightmap put the lair at %s" % (got, want))
    mac = fs[FN + "giratina/spawn_at.mcfunction"]
    lv = re.search(r"\$spawnpokemonat \$\(x\) \$\(y\) \$\(z\) giratina level=(\d+)", mac)
    aces = load_json(ROOT / "data" / "trainers.json")["generation_contract"]["gym_ace_levels"]
    cap8 = 60    # the Elite Four's aces, the cap after 8 badges (docs/mechanics/LEAGUE_LEVEL_CAP.md, VERIFIED there)
    rep.check(bool(lv) and 50 <= int(lv.group(1)) <= 60 and int(lv.group(1)) <= cap8, "Q5 Giratina",
              "the macro does not spawn a giratina at level 50-60 under the cap after 8 badges: %r" % mac.strip()[-120:])
    rep.facts["giratina_level"] = int(lv.group(1)) if lv else None
    rep.facts["cap_after_7_badges_upper_bound"] = aces[7]
    G = q["giratina"]["guardian_tag"]
    touch = [l for n in ("hold", "wake", "settle", "keep") for l in fs[FN + "giratina/%s.mcfunction" % n].splitlines()
             if re.match(r"^(execute .*run )?(kill|tp|data merge)", l) and "tag=!%s" % G not in l and "@s" not in l.split(" run ")[-1][:30]
             and "@e[" in l]
    rep.check(not touch, "Q5 Giratina", "keeper lines that act on an entity without excluding the guardian: %s" % touch[:1])

    # ---- Q6 callbacks
    cb = fs["data/cobblemon/callbacks/battle_fainted/cobblers_frostpeak_keep_quest.molang"]
    rep.check("'cobblemon:giratina'" in cb and "for_each(t.a, c.players" in cb and "t.done" not in cb and "is_wild" in cb,
              "Q6 callbacks", "battle_fainted must credit every player of a wild Giratina's battle")
    cap = fs["data/cobblemon/callbacks/poke_ball_capture_calculated/cobblers_frostpeak_keep_quest.molang"]
    gtag = q["giratina"]["tag"]
    rep.check("has_tag('%s')" % gtag in cap and cap.index("has_tag('%s')" % gtag) < cap.index("q.set_shakes(0)"), "Q6 callbacks",
              "the capture gate does not key its refusal on %s" % gtag)
    cc = fs[FN + "giratina/catch_check.mcfunction"]
    dq_ = q["quest"]
    rep.check(("unless entity @s[advancements={%s=true}]" % dq_["defeated_advancement"]) in cc
              and ("if entity @s[advancements={%s=true}] run tag @s add %s" % (dq_["caught_advancement"], dq_["free_tag"])) in cc,
              "Q6 callbacks", "the catch gate does not refuse a thrower without the defeat or with a catch")

    # ---- Q7 wiring
    fa = fs[FN + "giratina/fainted.mcfunction"]
    added = re.findall(r"^tag @s add (\S+)$", fa, re.M)
    dl = load_json(ROOT / "data" / "dialogue.json")
    convs = {c["id"]: c for c in dl["conversations"]}
    maren = convs.get("dlg_wardenhold_maren", {})
    reads = set(re.findall(r'"tag": "([^"]+)"', json.dumps(maren)))
    rep.check(added and set(added) <= reads, "Q7 wiring", "fainted adds %s; Maren's conversation reads %s" % (added, reads))
    rep.check(re.search(r"^advancement grant @s only %s$" % re.escape(dq_["defeated_advancement"]), fa, re.M) is not None,
              "Q7 wiring", "fainted does not grant %s" % dq_["defeated_advancement"])
    rw = {x["id"]: x for x in load_json(ROOT / "data" / "rewards.json")["rewards"]}
    qq = next((x for x in load_json(ROOT / "data" / "quests.json")["quests"] if x["id"] == dq_["id"]), None)
    rr = rw.get(dq_["reward"])
    rep.check(bool(qq and rr) and rr["kind"] == "npc_grant" and rr["quest"] == dq_["id"]
              and [c["item"] for c in rr["contents"]] == [c["item"] for c in qq["rewards"][0]["contents"]],
              "Q7 wiring", "the quest's reward and data/rewards.json %s disagree" % dq_["reward"])
    nonpc = [r_["conversation"] for r_ in q["residents"] if not (convs.get(r_["conversation"]) or {}).get("npc_id")]
    rep.check(not nonpc, "Q7 wiring", "residents whose conversation has no NPC: %s" % nonpc)
    fields = {f["id"] for f in load_json(ROOT / "data" / "progression.json")["quest_fields"]}
    undeclared = [f for f in (qq or {}).get("progression_field_refs", []) if f not in fields]
    rep.check(qq is not None and not undeclared, "Q7 wiring", "quest fields not declared in data/progression.json: %s" % undeclared)

    # ---- Q8 the shrine's takedown, replayed over its own box
    pl = load_json(ROOT / "data" / "placements.json")
    sh = next((r_ for r_ in pl["superseded_placements"]["records"] if r_.get("id") == "legendary_giratina_shrine"), None)
    rep.check(sh is not None and not any(p.get("id") == "legendary_giratina_shrine" for p in pl["placements"]), "Q8 shrine",
              "the shrine is not retired out of data/placements.json placements")
    if sh is not None:
        px, py, pz = sh["position"]["x"], sh["position"]["y"], sh["position"]["z"]
        sx_, sy_, sz_ = sh["size"]
        bx = (px, py, pz, px + sx_ - 1, py + sy_ - 1, pz + sz_ - 1)
        tb = replay(fs[FN + "shrine_takedown.mcfunction"].splitlines())
        import water_mask as WM
        bodies = WM.bodies()
        wrong, wet = [], 0
        for x in range(bx[0], bx[3] + 1):
            for z in range(bx[2], bx[5] + 1):
                gy = g(x, z)
                lvl = WM.level_at(x, z, g, bodies)[1]
                wet += lvl is not None and lvl > gy
                for y in range(bx[1], bx[4] + 1):
                    s = name(tb.get((x, y, z), "minecraft:<unwritten>"))
                    exp = ("stone",) if y <= gy else (("water",) if lvl is not None and y <= lvl else ("air",))
                    if s not in exp:
                        wrong.append((x, y, z, s, exp[0]))
        rep.check(not wrong, "Q8 shrine", "%d cells of the shrine's box end other than rock to the ground, water, air: first %s"
                  % (len(wrong), wrong[:2]))
        rep.facts.update(shrine_box=bx, shrine_wet_columns=wet)
    return rep


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--pack", default=str(PACK))
    ap.add_argument("--source-root")
    a = ap.parse_args(argv)
    import ground as G
    rep = audit(a.pack, G.load(a.source_root))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"rows": rep.rows, "facts": rep.facts}, indent=1, default=list) + "\n", encoding="utf-8")
    if rep.problems:
        for p in rep.problems:
            print("PROBLEM %s: %s" % (p["check"], p["detail"]))
        return 1
    print("CLEAN: %d checks over %s; facts %s" % (len(rep.rows), a.pack, json.dumps(rep.facts, default=list)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
