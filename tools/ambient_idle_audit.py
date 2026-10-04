#!/usr/bin/env python
"""The idle Pokemon's independent audit: the EMITTED pack (build/datapacks/cobblers_ambient_idle) read back and judged
against expectations this file derives itself -- never from tools/ambient_idle.py, its plan
(derived/ambient/idle_plan.json) or the rules it reads from data/ambient.json `idle`.

Written by an agent that did not build the idle Pokemon (2026-10-04). Where each expectation comes from:

  cap      30 Pokemon a town, working + idle, counted by POSITION inside the town's data/towns.json footprint over
           every pack's literal spawns (not by the builder's town label): the owner's cap from the frame-rate test,
           docs/HANDOVER_SESSION.md 2026-10-03 ("Cap to use: up to ~30 ambient Pokemon a town, spread ...").
  groups   groups of at most 3, spread: Pokemon closer than LINK = 3 blocks are one group (single linkage). 3 is the
           ring spacing of the layout that bent the frame rate (rings at 5/8/11 blocks: "everything close and in view
           at once", 65-70 FPS); the layout that held 100-130 FPS was "groups of 1-3". Measured over working AND idle
           Pokemon, since a client draws both.
  spot     each idler's cell in the BUILT town: tools/npc_spot_sweep.py's replay (another agent's tool) of every
           fill, setblock and `place template` the apply runs, on the canonical heightmap, round each spot; the spot
           must classify `outside` (floor under, two cells of room, open sky) -- not in a block, indoors (a building,
           a tent, a stall's roof), on a roof or with no floor. A bench sitter (y ends .5) stands on the seat: the
           cell under it must be a stair or slab.
  body     the species' own hitbox (the Cobblemon 1.8.0 jar: hitbox width/height x baseScale) clear of every solid
           replayed cell -- a Snorlax is 2.3 wide and 3.35 tall, not a 1x2 player.
  footprint, road, door, npc
           not inside a building footprint (derived/towns/<s>_placement.json, the placer's own record, and
           data/placements.json donors via tools/town_dressing.building_footprints); not on a street cell (the plan's
           paved cells and data/placements.json's polylines brushed at width/2); not in or orthogonally beside a
           door block of the replayed town; not within one cell of an NPC the apply places (tools/reapply.py's npc
           steps, data/markets.json keepers, data/npc_seats.json) nor on a plaza stall's customer cell.
  sleeper  only species that can fall asleep where and when they are placed, from the jar's behaviour.resting
           (defaults read from RestBehaviour's constructor: times night, light 0-15): canSleep, times any/day for a
           town by day, and the light at the spot in range. The light read is `method_8317(pos)` in
           PokemonEntity.canSleepAt (javap, 2026-10-04); no mappings on this machine say which method that is, so
           both readings are checked: total brightness (open sky by day = 15) and the emission of the block at the
           spot (air = 0). A species that fails either may never sleep where it is put.
  wake     the owner's 16: the dozer -> awake selector is @a[distance=..16] exactly; the re-sleep radius is larger
           (hysteresis); the awake list is the claim's sleeper list without cobblemon:pokemon_sleeps; the doze list
           is the claim's list; tags flip dozer <-> woken.
  merge    a `data merge` remakes a Pokemon's brain (the builder's own warning), so no line in ANY built pack may
           merge or modify an entity that could be an idle sleeper, except the idle pack's claim, wake and doze.
  flags    every idler carries every flag the WORKERS' claim carries (read from build/datapacks/cobblers_ambient),
           spawns `uncatchable` like the workers, NoAI 1b for the still ones and 0b for the AI kinds.
  buneary  4-6 round the snow house (the owner: "Buneary around the snow house"), checked against the house's own
           block plan (tools/lopunny_house.plan): inside its clear box, feet and head not its blocks, not on its path
           or door, and the night sleeper's block light (a flood from the plan's and replay's light sources) <= 4.
  follower its home (ScriptingConfig) is its spot, and an NPC lies within home_radius + 1 of it (the disc it potters
           in touches the NPC): "following a kid around".
  cost     the per-tick command lines counted from the emitted functions here, not from the builder's report.

Independence, proved by MUTATING THE GENERATOR with data/ambient.json untouched (tests/test_ambient_idle_audit.py):
the wake radius +1 inside functions(), the awake list written as the sleeper list, Unbattleable dropped from the
claim's flags, and the anchor-gap (spread) rule disabled inside place_town -- each is caught here.

Not covered: anything in a running game -- whether a sleeper sleeps, whether a woken one stands, whether a follower
stays by its NPC (AI-on kinds move: their leash circles are not checked), whether a sitter's tp holds; foliage the
export grows (the replay has no trees); entities other packs spawn by relative coordinates or at runtime; what a
player builds. The replay is of the packs as built: a pack prepare has not rebuilt yet is read as it stands.

  python tools/ambient_idle_audit.py [--packs build/datapacks] [--source-root R] [--json OUT]   exit 1 on a problem
"""
from __future__ import annotations

import argparse
import functools
import json
import math
import re
import sys
import zipfile
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

# The ground rule (tools/ground_rule.py): nothing here reads a world.
WORLD_READS: set = set()

PACKS = ROOT / "build" / "datapacks"
IDLE_PACK, WORK_PACK = "cobblers_ambient_idle", "cobblers_ambient"
FN = "data/cobblers/function"

CAP = 30                 # docs/HANDOVER_SESSION.md, frame-rate test 2026-10-03: "up to ~30 ambient Pokemon a town"
LINK = 3.0               # the ring spacing (5/8/11) of the layout that bent the frame rate
GROUP_MAX = 3            # "spread in small groups (1-3)"
WAKE = 16                # the owner: "sleeping ones that wake at 16 blocks"
DAY_SKY = 15             # open sky at noon
NIGHT_SKY = 4            # 15 - 11, the sky's darkening at midnight
DAY_TIMES = {"any", "day"}
NIGHT_TIMES = {"any", "night"}
SLEEPS = "cobblemon:pokemon_sleeps"
BUNEARY_RANGE = (4, 6)
TAG = "cobblers.amb"
IDLE_TAGS = {"cobblers.amb", "cobblers.amb.idle", "cobblers.amb.dozer", "cobblers.amb.woken"}

EMIT = {"lantern": 15, "soul_lantern": 10, "torch": 14, "wall_torch": 14, "soul_torch": 10, "soul_wall_torch": 10,
        "glowstone": 15, "sea_lantern": 15, "jack_o_lantern": 15, "campfire": 15, "soul_campfire": 10,
        "shroomlight": 15, "end_rod": 14, "redstone_lamp": 15, "beacon": 15, "lava": 15, "ochre_froglight": 15,
        "verdant_froglight": 15, "pearlescent_froglight": 15, "candle": 12, "magma_block": 3, "light": 15}
CLEAR_LIGHT = ("glass", "pane", "fence", "lantern", "chain", "leaves", "slab", "stairs", "door", "bars", "candle",
               "torch", "wall", "carpet", "sign", "banner", "rod")

# KNOWN defects: the problem list must equal this set exactly (a new one fails; a fixed one fails until removed).
# (check, key) -> why it is recorded rather than fixed. Filled from the first run, 2026-10-04 (the auditor does not fix
# the builder; each is a defect in tools/ambient_idle.py's siting or data/ambient.json's species, for its owner).
# 2026-10-04: all 42 first-run entries (25 road, 3 spot, 1 npc, 6 follower, 7 sleeper) were fixed in the generator
# and data/ambient.json and removed here; the list is empty until a new defect is recorded rather than fixed.
KNOWN: dict = {}


class AuditError(SystemExit):
    pass


# ------------------------------------------------------------------------------------------------ reading the pack

def read_pack(pack_dir):
    """{function name under cobblers:ambient_idle/: [lines]} of a built pack."""
    base = Path(pack_dir) / FN / "ambient_idle"
    if not base.is_dir():
        raise AuditError("no %s: run python tools/ambient_idle.py build" % base)
    return {str(p.relative_to(base).with_suffix("")).replace("\\", "/"): p.read_text(encoding="utf-8").splitlines()
            for p in sorted(base.rglob("*.mcfunction"))}


def code(lines):
    return [l for l in lines if l.strip() and not l.lstrip().startswith("#")]


NUM = r"(-?\d+(?:\.\d+)?)"
RE_SPAWN = re.compile(r'spawn_at \{x:"?%s"?,y:"?%s"?,z:"?%s"?,species:"([a-z0-9_]+)",level:(\d+)\}' % (NUM, NUM, NUM))
RE_TAGSEL = re.compile(r"tag=cobblers\.amb\.([a-z0-9_]+)\]")
RE_LIST = re.compile(r"Behaviours:\[([^\]]*)\]")


def blist(s):
    m = RE_LIST.search(s)
    return [x.strip().strip('"') for x in m.group(1).split(",") if x.strip()] if m else None


def parse(fns):
    """The idlers and the keeper as the functions say them: {"idlers": {id: {...}}, "towns": {town: [ids]}, ...}."""
    towns, idlers = {}, {}
    for name, lines in fns.items():
        m = re.fullmatch(r"t/([a-z0-9_]+)/keep", name)
        if not m:
            continue
        ids = []
        for l in code(lines):
            t = RE_TAGSEL.search(l)
            if t and t.group(1) not in ids:
                ids.append(t.group(1))
        towns[m.group(1)] = ids
        for iid in ids:
            sel = "tag=cobblers.amb.%s]" % iid
            mine = [l for l in code(lines) if sel in l]
            rec = {"id": iid, "town": m.group(1), "keep": mine}
            sp = code(fns.get("i/%s/spawn" % iid, []))
            hit = RE_SPAWN.search(" ".join(sp))
            if hit:
                rec["at"] = (float(hit.group(1)), float(hit.group(2)), float(hit.group(3)))
                rec["species"], rec["level"] = hit.group(4), int(hit.group(5))
            cd = re.search(r"distance=\.\.(\d+(?:\.\d+)?)", " ".join(sp))
            rec["claim_distance"] = float(cd.group(1)) if cd else None
            claim = code(fns.get("i/%s/claim" % iid, []))
            rec["claim"] = claim
            merge = " ".join(l for l in claim if l.startswith("data merge entity @s"))
            rec["noai"] = (re.search(r"NoAI:(\d)b", merge) or [None, None])[1]
            rec["behaviours"] = blist(merge)
            rec["flags"] = set(re.findall(r"([A-Za-z]+):1b", merge)) | (
                {"DeathLootTable:empty"} if 'DeathLootTable:"minecraft:empty"' in merge else set())
            hm = re.search(r"ScriptingConfig:\{home_x:%sd,home_y:%sd,home_z:%sd,home_radius:%sd\}" % (NUM, NUM, NUM, NUM),
                           merge)
            rec["home"] = tuple(float(hm.group(i)) for i in (1, 2, 3)) if hm else None
            rec["home_radius"] = float(hm.group(4)) if hm else None
            rec["tags"] = [l.split()[-1] for l in claim if l.startswith("tag @s add ")]
            beh = rec["behaviours"] or []
            rec["kind"] = ("still" if rec["noai"] == "1" else "sleeper" if SLEEPS in beh
                           else "follower" if "cobblemon:stationary" in beh else "other")
            lm = [re.search(r"unless entity @s\[distance=\.\.(\d+)\]", l) for l in mine]
            rec["leash"] = next((int(x.group(1)) for x in lm if x), None)
            idlers[iid] = rec
    return {"idlers": idlers, "towns": towns, "fns": fns}


def keeper(fns):
    """The clocks and the wake step: {"keep_every", "wake_every", "wake_r", "rest_r", "wake_list", "doze_list", ...}."""
    out = {}
    for l in code(fns.get("tick", [])):
        m = re.search(r"matches (\d+)\.\. run function cobblers:ambient_idle/(keep_all|wakes)$", l)
        if m:
            out["keep_every" if m.group(2) == "keep_all" else "wake_every"] = int(m.group(1))
    for l in code(fns.get("wakes", [])):
        m = re.search(r"tag=([a-z0-9_.]+)\] at @s (if|unless) entity @a\[distance=\.\.(\d+)\] run function "
                      r"cobblers:ambient_idle/(wake|doze)$", l)
        if m:
            out[m.group(4)] = {"tag": m.group(1), "cond": m.group(2), "r": int(m.group(3))}
    for step in ("wake", "doze"):
        ls = code(fns.get(step, []))
        out[step + "_list"] = blist(" ".join(ls))
        out[step + "_tags"] = ([l.split()[-1] for l in ls if l.startswith("tag @s remove")],
                               [l.split()[-1] for l in ls if l.startswith("tag @s add")])
    return out


def worker_pack(packs):
    """The workers' spawn positions, claim flags and spawn macro (build/datapacks/cobblers_ambient)."""
    base = Path(packs) / WORK_PACK / FN
    pos, flags, macro = [], set(), ""
    for p in sorted(base.rglob("*.mcfunction")) if base.is_dir() else []:
        for l in p.read_text(encoding="utf-8").splitlines():
            m = RE_SPAWN.search(l)
            if m:
                pos.append((float(m.group(1)), float(m.group(2)), float(m.group(3)), m.group(4)))
            if l.startswith("data merge entity @s {") and "Persistence" in l:
                flags |= set(re.findall(r"([A-Za-z]+):1b", l))
                if 'DeathLootTable:"minecraft:empty"' in l:
                    flags.add("DeathLootTable:empty")
            if l.startswith("$spawnpokemonat"):
                macro = l
    return pos, flags, macro


def other_spawns(packs):
    """Literal Pokemon spawns in every other pack: [(x, y, z, species, pack)]."""
    out = []
    lit = re.compile(r"spawnpokemonat %s %s %s ([a-z0-9_]+)" % (NUM, NUM, NUM))
    for p in sorted(Path(packs).glob("*/data/*/function/**/*.mcfunction")):
        pack = p.relative_to(packs).parts[0]
        if pack in (IDLE_PACK, WORK_PACK):
            continue
        t = p.read_text(encoding="utf-8", errors="replace")
        if "spawn" not in t:
            continue
        for rx in (lit, RE_SPAWN):
            for m in rx.finditer(t):
                out.append((float(m.group(1)), float(m.group(2)), float(m.group(3)), m.group(4), pack))
    return out


# ------------------------------------------------------------------------------------------------ the checks

def clusters(points, link=LINK):
    """Single-linkage groups of [(x, z, label)] at `link` blocks (inclusive)."""
    n = len(points)
    parent = list(range(n))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i
    for i in range(n):
        for j in range(i + 1, n):
            if math.dist(points[i][:2], points[j][:2]) <= link:
                parent[find(i)] = find(j)
    g = defaultdict(list)
    for i in range(n):
        g[find(i)].append(points[i])
    return sorted(g.values(), key=lambda c: (-len(c), c[0][2]))


def check_groups(points_by_town):
    P = []
    for town, pts in sorted(points_by_town.items()):
        for c in clusters(pts):
            if len(c) > GROUP_MAX:
                P.append(("groups", "%s:%s" % (town, c[0][2]), "%s: %d Pokemon within %.0f blocks of each other (%s), "
                          "more than a group of %d" % (town, len(c), LINK, ", ".join(p[2] for p in c), GROUP_MAX)))
    return P


def check_cap(counts):
    return [("cap", t, "%s: %d Pokemon inside the town's footprint (%s), over the cap of %d" % (t, n, why, CAP))
            for t, (n, why) in sorted(counts.items()) if n > CAP]


def check_wake(k, idlers):
    P = []
    wk, dz = k.get("wake"), k.get("doze")
    if not wk or wk["cond"] != "if" or wk["tag"] != "cobblers.amb.dozer":
        P.append(("wake", "wake", "no `as dozer ... if entity @a[distance=..R] run wake` line in wakes"))
    elif wk["r"] != WAKE:
        P.append(("wake", "wake", "the wake radius is %d, the owner's is %d" % (wk["r"], WAKE)))
    if not dz or dz["cond"] != "unless" or dz["tag"] != "cobblers.amb.woken":
        P.append(("wake", "doze", "no `as woken ... unless entity @a[distance=..R] run doze` line in wakes"))
    elif wk and dz["r"] <= wk["r"]:
        P.append(("wake", "doze", "the re-sleep radius %d is not larger than the wake radius %d" % (dz["r"], wk["r"])))
    sl = [i["behaviours"] for i in idlers.values() if i["kind"] == "sleeper"]
    claim_list = sl[0] if sl else None
    if any(x != claim_list for x in sl):
        P.append(("wake", "lists", "the sleepers' claim lists differ"))
    if claim_list is not None:
        want_awake = [b for b in claim_list if b != SLEEPS]
        if k.get("wake_list") != want_awake:
            P.append(("wake", "awake_list", "the wake step writes %s, not the sleeper list without %s"
                      % (k.get("wake_list"), SLEEPS)))
        if k.get("doze_list") != claim_list:
            P.append(("wake", "doze_list", "the doze step writes %s, not the claim's sleeper list" % k.get("doze_list")))
    if k.get("wake_tags") != (["cobblers.amb.dozer"], ["cobblers.amb.woken"]):
        P.append(("wake", "wake_tags", "wake does not swap dozer for woken: %s" % (k.get("wake_tags"),)))
    if k.get("doze_tags") != (["cobblers.amb.woken"], ["cobblers.amb.dozer"]):
        P.append(("wake", "doze_tags", "doze does not swap woken for dozer: %s" % (k.get("doze_tags"),)))
    for i in idlers.values():
        if i["kind"] == "sleeper" and "cobblers.amb.dozer" not in i["tags"]:
            P.append(("wake", i["id"], "%s: a sleeper the claim does not tag dozer, so it never wakes" % i["id"]))
    if "wake_every" not in k:
        P.append(("wake", "clock", "no clock runs wakes"))
    return P


def check_merges(packs, fns_idle):
    """No entity merge that could reach an idle sleeper outside the idle pack's claim, wake and doze."""
    P = []
    allowed = re.compile(r"^(i/[a-z0-9_]+/claim|wake|doze)$")
    for name, lines in fns_idle.items():
        if any(re.search(r"data (merge|modify) entity", l) for l in code(lines)) and not allowed.match(name):
            P.append(("merge", "idle:%s" % name, "cobblers:ambient_idle/%s merges an entity: a merge remakes a "
                      "sleeper's brain" % name))
    for p in sorted(Path(packs).glob("*/data/*/function/**/*.mcfunction")):
        pack = p.relative_to(packs).parts[0]
        if pack == IDLE_PACK:
            continue
        for l in p.read_text(encoding="utf-8", errors="replace").splitlines():
            if not re.search(r"data (merge|modify) entity", l):
                continue
            for s in re.findall(r"@e(?:\[[^\]]*\])?", l):
                tags = re.findall(r"tag=([^,\]]+)", s)
                pos = [t for t in tags if not t.startswith("!")]
                hit = (not pos and "nbt=" not in s and "name=" not in s
                       and ("type=" not in s or "cobblemon:pokemon" in s)) or any(t in IDLE_TAGS or
                                                                                  t.startswith("cobblers.amb.idle_")
                                                                                  for t in pos)
                if hit:
                    P.append(("merge", "%s:%s" % (pack, s[:80]), "%s (%s) merges into %s, which can match an idle "
                              "sleeper" % (pack, p.name, s)))
    return P


def check_flags(idlers, wflags, wmacro, imacro):
    P = []
    if "uncatchable" in wmacro and "uncatchable" not in imacro:
        P.append(("flags", "spawn_at", "the idle spawn macro lacks `uncatchable`, which the workers' carries"))
    for i in idlers.values():
        miss = sorted(wflags - i["flags"])
        if miss:
            P.append(("flags", i["id"], "%s lacks the workers' flags %s" % (i["id"], miss)))
        want = "1" if i["kind"] == "still" else "0"
        if i["noai"] != want:
            P.append(("flags", "noai:" + i["id"], "%s (%s): NoAI %sb" % (i["id"], i["kind"], i["noai"])))
    return P


def resting(jar):
    """{species: {canSleep, times, light, hitbox, baseScale}} from the jar, with RestBehaviour's defaults."""
    z = zipfile.ZipFile(jar)
    out = {}
    for n in z.namelist():
        if n.startswith("data/cobblemon/species/") and n.endswith(".json"):
            d = json.loads(z.read(n))
            r = (d.get("behaviour") or {}).get("resting") or {}
            lm = re.fullmatch(r"\s*(\d+)\s*-\s*(\d+)\s*", str(r.get("light", "0-15")))
            lo, hi = (int(lm.group(1)), int(lm.group(2))) if lm else (0, 15)
            hb = d.get("hitbox") or {"width": 1.0, "height": 1.0}
            out[n.rsplit("/", 1)[1][:-5]] = {"canSleep": bool(r.get("canSleep", False)),
                                            "times": set(r.get("times") or ["night"]), "light": (lo, hi),
                                            "width": float(hb["width"]) * float(d.get("baseScale", 1)),
                                            "height": float(hb["height"]) * float(d.get("baseScale", 1))}
    return out


def check_sleepers(idlers, rest, night_light):
    """Day sleepers in the towns, night sleepers at the snow house. night_light: {id: block light upper bound}."""
    P, by = [], defaultdict(list)
    for i in idlers.values():
        if i["kind"] == "sleeper":
            by[(i["species"], i["town"] == "lopunny_house")].append(i)
    for (sp, night), group in sorted(by.items()):
        r = rest.get(sp)
        ids = ", ".join(i["id"] for i in group)
        if r is None or not r["canSleep"]:
            P.append(("sleeper", sp, "%s cannot sleep at all (jar canSleep false or no species): %s" % (sp, ids)))
            continue
        lo, hi = r["light"]
        if not night:
            if not r["times"] & DAY_TIMES:
                P.append(("sleeper", sp, "%s sleeps only at %s; placed in a town by day: %s" % (sp, sorted(r["times"]), ids)))
            if not lo <= DAY_SKY <= hi:
                P.append(("sleeper", sp + ":brightness", "%s sleeps in light %d-%d, and open sky by day is %d (if "
                          "canSleepAt reads total brightness): %s" % (sp, lo, hi, DAY_SKY, ids)))
            if not lo <= 0 <= hi:
                P.append(("sleeper", sp + ":emission", "%s sleeps in light %d-%d, and air emits 0 (if canSleepAt's "
                          "method_8317 is the block's own emission): %s" % (sp, lo, hi, ids)))
        else:
            if not r["times"] & NIGHT_TIMES:
                P.append(("sleeper", sp, "%s never sleeps at night: %s" % (sp, ids)))
            for i in group:
                lum = max(NIGHT_SKY, night_light.get(i["id"], 0))
                if not lo <= lum <= hi:
                    P.append(("sleeper", i["id"] + ":brightness", "%s (%s) needs light %d-%d at night; the spot reads "
                              "up to %d (sky %d, block light %d)" % (i["id"], sp, lo, hi, lum, NIGHT_SKY,
                                                                      night_light.get(i["id"], 0))))
    return P


def check_followers(idlers, npcs):
    P = []
    for i in idlers.values():
        if i["kind"] != "follower" or i["town"] == "lopunny_house":   # the yard's Buneary wanders by design
            continue
        x, y, z = i["at"]
        if i["home"] is None or math.dist(i["home"], (x, y, z)) > 0.01:
            P.append(("follower", i["id"], "%s: home %s is not its spot %s" % (i["id"], i["home"], i["at"])))
            continue
        reach = (i["home_radius"] or 0) + 1
        near = [n for n in npcs if math.dist((n[1], n[3]), (x, z)) <= reach]
        if not near:
            d = min((math.dist((n[1], n[3]), (x, z)), n[0]) for n in npcs) if npcs else (None, None)
            P.append(("follower", i["id"], "%s follows nobody: no NPC within %.0f of its home %s (nearest %s at %s)"
                      % (i["id"], reach, i["at"], d[1], "%.1f" % d[0] if d[0] is not None else "-")))
    return P


def cost(k, fns):
    keep_all = len(code(fns.get("keep_all", [])))
    wakes = len(code(fns.get("wakes", [])))
    tick = len(code(fns.get("tick", [])))
    out = {"tick": tick, "keep_all": keep_all, "wakes": wakes, "keep_every": k.get("keep_every"),
           "wake_every": k.get("wake_every")}
    out["always_per_tick"] = round(tick + keep_all / k.get("keep_every", 1) + wakes / k.get("wake_every", 1), 3)
    out["towns"] = {name[2:-5]: round(len(code(v)) / k.get("keep_every", 1), 3)
                    for name, v in fns.items() if name.startswith("t/") and name.endswith("/keep")}
    out["wake_or_doze_event"] = max(len(code(fns.get("wake", []))), len(code(fns.get("doze", []))))
    return out


# ------------------------------------------------------------------------------------------------ the built town

def town_footprints():
    d = json.loads((ROOT / "data" / "towns.json").read_text(encoding="utf-8"))
    return {t["id"]: (t["footprint"]["min_x"], t["footprint"]["min_z"], t["footprint"]["max_x"], t["footprint"]["max_z"])
            for t in d["towns"] if isinstance(t.get("footprint"), dict) and "min_x" in t["footprint"]}


def town_extents():
    """{town: (x0, z0, x1, z1)} the box round everything the town is: its data/towns.json footprint, its plan's
    footprint, plaza and lots, and every building it places. Built towns overrun their declared footprint (Celadon's
    Mart and gym; the rim stop's footprint lies 150 blocks from its buildings), and a Pokemon by a building that
    sticks out is still in the town."""
    out = {}
    for t, r in town_footprints().items():
        xs, zs = [r[0], r[2]], [r[1], r[3]]
        pp = ROOT / "derived" / "towns" / ("%s_plan.json" % t)
        plan = json.loads(pp.read_text(encoding="utf-8")) if pp.is_file() else {}
        rects = [plan.get("footprint"), (plan.get("plaza") or {}).get("rect")] + [l["rect"] for l in plan.get("lots") or []]
        rects += list(buildings(t).values()) if pp.is_file() else []
        for q in rects:
            if q:
                xs += [q[0], q[2]]
                zs += [q[1], q[3]]
        out[t] = (min(xs), min(zs), max(xs), max(zs))
    return out


def inside(r, x, z):
    return r[0] <= x <= r[2] and r[1] <= z <= r[3]


@functools.lru_cache(maxsize=None)
def buildings(town):
    out = {}
    pp = ROOT / "derived" / "towns" / ("%s_placement.json" % town)
    if pp.is_file():
        for b in json.loads(pp.read_text(encoding="utf-8")).get("buildings") or []:
            out[b["id"]] = tuple(b["footprint"])
    try:
        import town_dressing as TD
        doc = json.loads((ROOT / "data" / "placements.json").read_text(encoding="utf-8"))
        for bid, r in TD.building_footprints(town, doc).items():
            out.setdefault(bid, tuple(r))
    except SystemExit:
        pass
    return out


def streets(town):
    cells = set()
    pp = ROOT / "derived" / "towns" / ("%s_plan.json" % town)
    plan = json.loads(pp.read_text(encoding="utf-8")) if pp.is_file() else {}
    for st in (plan.get("streets") or {}).values():
        for z, _y, x0, x1 in st.get("cells") or []:
            cells |= {(x, z) for x in range(x0, x1 + 1)}
    doc = json.loads((ROOT / "data" / "placements.json").read_text(encoding="utf-8"))
    pdata = (doc["settlements"].get(town) or {}).get("plan") or {}
    for st in pdata.get("streets") or []:
        half = int(st.get("width", 1)) // 2
        pts = st.get("polyline") or []
        for (ax, az), (bx, bz) in zip(pts, pts[1:]):
            n = int(max(abs(bx - ax), abs(bz - az))) + 1
            for i in range(n + 1):
                t = i / n
                cx, cz = round(ax + (bx - ax) * t), round(az + (bz - az) * t)
                cells |= {(cx + dx, cz + dz) for dx in range(-half, half + 1) for dz in range(-half, half + 1)}
    sq = (plan.get("plaza") or {}).get("rect")
    if sq:
        cells = {c for c in cells if not inside((min(sq[0], sq[2]), min(sq[1], sq[3]), max(sq[0], sq[2]),
                                                 max(sq[1], sq[3])), *c)}
    return cells


def stalls(town):
    """[(piece id, keeper (x, z) or None, customer (x, z) or None)] from the plaza builder's output."""
    pc = ROOT / "derived" / "plaza_centres" / ("%s.json" % town)
    if not pc.is_file():
        return []
    out = []
    for p in json.loads(pc.read_text(encoding="utf-8")).get("pieces") or []:
        k = (p["keeper_at"][0], p["keeper_at"][2]) if p.get("keeper_at") else None
        c = tuple(p["customer"][:1] + p["customer"][-1:]) if p.get("customer") else None
        if k or c:
            out.append((p["id"], k, c))
    return out


def npcs_placed(steps):
    out = []
    for _sid, _d, items in steps:
        for it in items:
            if it[0] in ("npc", "trainer"):
                v = it[1]
                out.append((v[0], float(v[1][0]), float(v[1][1]), float(v[1][2])))
    for name in ("markets.json",):
        d = json.loads((ROOT / "data" / name).read_text(encoding="utf-8"))
        for r in (d.get("counters") or []) + (d.get("stalls") or []):
            if r.get("at"):
                out.append((r["id"], float(r["at"][0]), float(r["at"][1]), float(r["at"][2])))
    seats = json.loads((ROOT / "data" / "npc_seats.json").read_text(encoding="utf-8"))
    for s in seats.get("seats") or []:
        if s.get("at"):
            out.append((s["id"], float(s["at"][0]), float(s["at"][1]), float(s["at"][2])))
    return out


def feet_cell(m, SW, x, y, z):
    """(feet y, seat?) -- a y ending .5 stands on a seat block's top half."""
    fy = math.floor(y)
    if y - fy > 0.25:
        st = SW.short(m.at(math.floor(x), fy, math.floor(z)))
        return fy + 1, st.endswith(("_stairs", "_slab")), st
    return fy, None, None


def check_spots(idlers, m, SW, rest, town_data):
    P = []
    for i in sorted(idlers.values(), key=lambda r: r["id"]):
        if "at" not in i:
            P.append(("spot", i["id"], "%s: no spawn position in its spawn function" % i["id"]))
            continue
        x, y, z = i["at"]
        bx, bz = math.floor(x), math.floor(z)
        fy, seat, seat_state = feet_cell(m, SW, x, y, z)
        if seat is False:
            P.append(("spot", i["id"], "%s at %s: y ends .5 but the block under it is %s, not a seat"
                      % (i["id"], i["at"], seat_state)))
        cls, detail = SW.classify(m, bx, fy, bz)
        if seat and cls == "pedestal":
            cls = "outside"               # a bench seat stands one above the paving round it: that is a bench
        if cls != "outside":
            P.append(("spot", i["id"], "%s (%s, %s) at %s: %s -- %s" % (i["id"], i["kind"], i["species"], i["at"], cls,
                                                                      detail)))
        r = rest.get(i["species"])
        if r and i["kind"] == "still":   # NoAI: no physics pushes it out of a block, so the overlap is what is seen
            hw = r["width"] / 2.0
            hit = None
            for cx in range(math.floor(x - hw + 1e-6), math.floor(x + hw - 1e-6) + 1):
                for cz in range(math.floor(z - hw + 1e-6), math.floor(z + hw - 1e-6) + 1):
                    for cy in range(math.floor(y), math.floor(y + r["height"] - 1e-6) + 1):
                        if seat and cy == fy - 1:
                            continue
                        st = m.at(cx, cy, cz)
                        if SW.solid(st):
                            hit = hit or (cx, cy, cz, SW.short(st))
            if hit and cls == "outside":
                P.append(("body", i["id"], "%s (%s, %.1f wide x %.2f tall) at %s overlaps %s at %s"
                          % (i["id"], i["species"], r["width"], r["height"], i["at"], hit[3], hit[:3])))
        td = town_data.get(i["town"])
        if not td:
            continue
        for bid, rr in td["buildings"].items():
            if inside((min(rr[0], rr[2]), min(rr[1], rr[3]), max(rr[0], rr[2]), max(rr[1], rr[3])), bx, bz):
                P.append(("footprint", i["id"], "%s at %s is inside building %s's footprint" % (i["id"], i["at"], bid)))
                break
        if (bx, bz) in td["streets"]:
            P.append(("road", i["id"], "%s (%s) at %s stands on a street" % (i["id"], i["kind"], i["at"])))
        doors = [(dx, dy, dz) for dx in range(-1, 2) for dz in range(-1, 2) for dy in (-1, 0, 1)
                 if abs(dx) + abs(dz) <= 1 and "_door" in SW.short(m.at(bx + dx, fy + dy, bz + dz))
                 and "trapdoor" not in SW.short(m.at(bx + dx, fy + dy, bz + dz))]
        if doors:
            P.append(("door", i["id"], "%s at %s is in or beside a door (%s)" % (i["id"], i["at"], doors[0])))
        for nid, nx, _ny, nz in td["npcs"]:
            if max(abs(math.floor(nx) - bx), abs(math.floor(nz) - bz)) <= 1:
                P.append(("npc", i["id"], "%s at %s is on or beside %s at %s" % (i["id"], i["at"], nid, (nx, nz))))
                break
        for sid, k, c in td["stalls"]:
            if c and (math.floor(c[0]), math.floor(c[1])) == (bx, bz):
                P.append(("npc", i["id"], "%s at %s is on stall %s's customer cell" % (i["id"], i["at"], sid)))
            if k and max(abs(math.floor(k[0]) - bx), abs(math.floor(k[1]) - bz)) <= 1:
                P.append(("npc", i["id"], "%s at %s is on or beside stall %s's keeper" % (i["id"], i["at"], sid)))
    return P


def block_light(m, SW, x, y, z, reach=15):
    """An estimate of the block light at (x, y, z): every emitter in the model within reach flooded through cells
    light passes (air, glass, fences, slabs, ...). The model's boxes must cover the reach."""
    best = 0
    seeds = []
    for cx in range(x - reach, x + reach + 1):
        for cy in range(y - reach, y + reach + 1):
            for cz in range(z - reach, z + reach + 1):
                st = m.cells.get((cx, cy, cz))
                if not st:
                    continue
                n = SW.short(st[0])
                e = EMIT.get(n) or (EMIT["candle"] if n.endswith("candle") and "lit=true" in st[0] else 0)
                if n.endswith("candle") and "lit=false" in st[0]:
                    e = 0
                if e > abs(cx - x) + abs(cy - y) + abs(cz - z):
                    seeds.append((e, (cx, cy, cz)))
    for e, s in seeds:
        seen = {s: e}
        frontier = [s]
        while frontier:
            nxt = []
            for c in frontier:
                lv = seen[c] - 1
                if lv <= 0:
                    continue
                for d in ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1)):
                    q = (c[0] + d[0], c[1] + d[1], c[2] + d[2])
                    if seen.get(q, -1) >= lv:
                        continue
                    st = m.at(*q)
                    if SW.solid(st) and not any(k in SW.short(st) for k in CLEAR_LIGHT):
                        continue
                    seen[q] = lv
                    nxt.append(q)
            frontier = nxt
        best = max(best, seen.get((x, y, z), 0))
    return best


def check_buneary(idlers, m, SW, ground):
    """The snow house's Buneary against the house's own block plan."""
    import lopunny_house as LH
    P, light = [], {}
    bun = [i for i in idlers.values() if i["town"] == "lopunny_house"]
    if not BUNEARY_RANGE[0] <= len(bun) <= BUNEARY_RANGE[1]:
        P.append(("buneary", "count", "%d Pokemon round the snow house, wanted %d-%d" % ((len(bun),) + BUNEARY_RANGE)))
    pl = LH.plan(LH.load(), ground)
    blocks = pl["blocks"]
    x0, z0, x1, z1 = pl["clear"]
    doors = {(k[0], k[2]) for k, _st in pl["plan"].doors}
    path = {(k[0], k[2]) for k, st in blocks.items() if "dirt_path" in st}
    for i in bun:
        x, y, z = i["at"]
        bx, by, bz = math.floor(x), math.floor(y), math.floor(z)
        if i["species"] != "buneary":
            P.append(("buneary", i["id"], "%s is a %s" % (i["id"], i["species"])))
        if not inside((x0, z0, x1, z1), bx, bz):
            P.append(("buneary", i["id"], "%s at %s is outside the house's cleared box %s" % (i["id"], i["at"], pl["clear"])))
        for dy in (0, 1):
            st = blocks.get((bx, by + dy, bz))
            if st and st != "minecraft:air" and SW.solid(st):
                P.append(("buneary", i["id"], "%s at %s: the house plan puts %s in its %s" % (
                    i["id"], i["at"], st, "feet" if dy == 0 else "head")))
        under = blocks.get((bx, by - 1, bz))
        if not ((under and SW.solid(under)) or by - 1 <= ground(bx, bz)):
            P.append(("buneary", i["id"], "%s at %s has nothing under it" % (i["id"], i["at"])))
        if by - 1 < ground(bx, bz):
            P.append(("buneary", i["id"], "%s at %s is below the ground (y%d)" % (i["id"], i["at"], ground(bx, bz))))
        near_door = [d for d in doors if abs(d[0] - bx) + abs(d[1] - bz) <= 1]
        if near_door or (bx, bz) in path:
            P.append(("buneary", i["id"], "%s at %s is on the house's path or door" % (i["id"], i["at"])))
        if i["kind"] == "sleeper":
            light[i["id"]] = block_light(m, SW, bx, by, bz)
    return P, light


def model_for(idlers, packs, source_root=None):
    import ground as G
    import npc_spot_sweep as SW
    steps = SW.load_steps(packs)
    g = G.load(source_root)
    boxes = []
    for i in idlers.values():
        if "at" not in i:
            continue
        x, y, z = (math.floor(c) for c in i["at"])
        r = 16 if (i["town"] == "lopunny_house" and i["kind"] == "sleeper") else 6
        boxes.append((x - r, y - max(r, 4), z - r, x + r, y + max(r, 8), z + r))
    m = SW.Model(g, boxes)
    SW.replay(m, SW.Function(packs), SW.Templates(packs), steps)
    return m, steps, g


def audit(packs=PACKS, source_root=None, jar=None):
    packs = Path(packs)
    fns = read_pack(packs / IDLE_PACK)
    doc = parse(fns)
    idlers = doc["idlers"]
    k = keeper(fns)
    P = []
    wpos, wflags, wmacro = worker_pack(packs)
    P += check_flags(idlers, wflags, wmacro, " ".join(fns.get("spawn_at", [])))
    P += check_wake(k, idlers)
    P += check_merges(packs, fns)
    # cap and groups, by position over every pack's Pokemon
    feet = town_extents()
    pts, counts = defaultdict(list), {}
    others = other_spawns(packs)
    for t, r in feet.items():
        mine = [(i["at"][0], i["at"][2], i["id"]) for i in idlers.values() if "at" in i and inside(r, i["at"][0], i["at"][2])]
        work = [(w[0], w[2], "worker:%s" % w[3]) for w in wpos if inside(r, w[0], w[2])]
        oth = [(o[0], o[2], "%s:%s" % (o[4], o[3])) for o in others if inside(r, o[0], o[2])]
        if mine or work:
            pts[t] = mine + work
            counts[t] = (len(mine) + len(work) + len(oth), "idle %d, working %d, other packs %d" % (len(mine), len(work),
                                                                                                    len(oth)))
    bun = [(i["at"][0], i["at"][2], i["id"]) for i in idlers.values() if i["town"] == "lopunny_house" and "at" in i]
    if bun:
        pts["lopunny_house"] = bun
    unplaced = sorted(i["id"] for i in idlers.values() if "at" in i and i["town"] != "lopunny_house"
                      and not any(inside(r, i["at"][0], i["at"][2]) for r in feet.values()))
    for u in unplaced:
        P.append(("cap", "outside:" + u, "%s at %s is in no town's footprint" % (u, idlers[u]["at"])))
    P += check_cap(counts)
    P += check_groups(pts)
    # the built town
    import battle_sim
    rest = resting(jar or battle_sim.find_jar())
    m, steps, g = model_for(idlers, packs, source_root)
    import npc_spot_sweep as SW
    npcs = npcs_placed(steps)
    town_data = {t: {"buildings": buildings(t), "streets": streets(t), "stalls": stalls(t),
                     "npcs": [n for n in npcs if inside(feet[t], n[1], n[3])]}
                 for t in doc["towns"] if t in feet}
    P += check_spots(idlers, m, SW, rest, town_data)
    bp, night = check_buneary(idlers, m, SW, g)
    P += bp
    P += check_sleepers(idlers, rest, night)
    P += check_followers(idlers, npcs)
    known = [p for p in P if (p[0], p[1]) in KNOWN]
    problems = [p for p in P if (p[0], p[1]) not in KNOWN]
    fixed = sorted(set(KNOWN) - {(p[0], p[1]) for p in known})
    kinds = defaultdict(int)
    for i in idlers.values():
        kinds[i["kind"]] += 1
    return {"problems": problems, "known": known, "known_fixed": fixed, "idlers": len(idlers),
            "kinds": dict(kinds), "counts": {t: v[0] for t, v in counts.items()}, "cost": cost(k, fns),
            "groups": {t: max(len(c) for c in clusters(p)) for t, p in pts.items()},
            "night_light": night}


def main(argv=None):
    from terrain import env_source_root
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--packs", default=str(PACKS))
    ap.add_argument("--source-root", default=env_source_root())
    ap.add_argument("--jar")
    ap.add_argument("--json")
    a = ap.parse_args(argv)
    res = audit(Path(a.packs), a.source_root, a.jar)
    c = res["cost"]
    print("idle Pokemon: %d (%s); per town (all packs, by footprint): %s" % (
        res["idlers"], ", ".join("%s %d" % kv for kv in sorted(res["kinds"].items())),
        ", ".join("%s %d" % kv for kv in sorted(res["counts"].items()))))
    print("largest group per place: %s" % ", ".join("%s %d" % kv for kv in sorted(res["groups"].items())))
    print("keeper cost: %s command lines/tick with nobody near (tick %d every tick + keep_all %d every %s ticks + wakes "
          "%d every %s); a player's town adds up to %s lines/tick; a wake or doze %d lines once" % (
              c["always_per_tick"], c["tick"], c["keep_all"], c.get("keep_every"), c["wakes"], c.get("wake_every"),
              max(c["towns"].values() or [0]), c["wake_or_doze_event"]))
    for ck, key, msg in res["known"]:
        print("KNOWN   %-9s %s" % (ck, msg))
    for key in res["known_fixed"]:
        print("FIXED? a KNOWN entry no longer found (remove it from KNOWN): %s" % (key,))
    for ck, key, msg in res["problems"]:
        print("PROBLEM %-9s %s" % (ck, msg))
    if a.json:
        Path(a.json).write_text(json.dumps(res, indent=1, default=list), encoding="utf-8")
    print("ambient idle audit: %d problem(s), %d known, %d known no longer found" % (
        len(res["problems"]), len(res["known"]), len(res["known_fixed"])))
    return 1 if res["problems"] or res["known_fixed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
