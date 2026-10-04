"""The idle Pokemon in the towns (tools/ambient_idle.py -> build/datapacks/cobblers_ambient_idle, data/ambient.json
`idle`, reapply.py R16C).

Written by the builder of the pack (2026-10-04), so these are the builder's own checks; an independent audit comes
after. Three layers:
  the data       every sleeper can sleep in a lit town by day, the behaviour lists are what was measured, the owner's
                 16-block wake; against the Cobblemon 1.8.0 jar where one is on this machine (else SKIP)
  the plan       counts per town against the data and the cap, groups of at most three, positions off buildings and
                 plaza pieces (read from derived/towns and derived/plaza_centres, not from the tool's site model),
                 the y the ground, plaza or bench gives
  the pack       run in tests/mcfunction_sim.py: the keeper spawns each idler once, protects it, holds it, wakes and
                 settles a sleeper, and costs four lines a tick with nobody near
Needs the pack built (python tools/ambient_idle.py build, or tools/ambient.py build); without it those tests SKIP
(NOT_EXECUTED), and a skip is not a pass. Not covered: anything in a running Minecraft -- whether a sleeper sleeps,
whether the wake swap clears the pose, whether ScriptingConfig reaches the home walk (all UNPROVEN, docstring).
"""
from __future__ import annotations

import json
import math
import re
import sys
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tests"))

import ambient_idle as AI  # noqa: E402
import function_limits  # noqa: E402
import mcfunction_sim as M  # noqa: E402

DATA = json.loads((ROOT / "data" / "ambient.json").read_text(encoding="utf-8"))
IDLE = DATA["idle"]
RULES = IDLE["rules"]
WORKERS = DATA["workers"]
F = "cobblers:ambient_idle"
FNDIR = AI.OUT / "data" / "cobblers" / "function" / "ambient_idle"


# ------------------------------------------------------------------------------------------------ the data

def jar():
    try:
        import battle_sim
        return zipfile.ZipFile(battle_sim.find_jar())
    except BaseException:
        pytest.skip("NOT_EXECUTED: no Cobblemon 1.8 jar on this machine")


def species_doc(z, name):
    hits = [n for n in z.namelist() if n.startswith("data/cobblemon/species/") and n.endswith("/%s.json" % name)]
    return json.loads(z.read(hits[0])) if hits else None


def all_species():
    out = set()
    for spec in IDLE["towns"].values():
        for k in AI.KINDS:
            out |= set(spec.get(k) or [])
    return out | {IDLE["buneary"]["species"]}


# Without it a sleeper could be a species that never sleeps under a town's lanterns by day (a night sleeper in light
# 0-4), and the town would hold a Pokemon standing where a sleeping one was meant to be.
def test_every_town_sleeper_can_sleep_by_day_in_light():
    day = RULES["sleeps_by_day"]["species"]
    for town, spec in IDLE["towns"].items():
        for s in spec.get("sleeper") or []:
            assert s in day, (town, s)


def test_the_day_sleeper_table_is_the_jars():
    z = jar()
    day = set(RULES["sleeps_by_day"]["species"])
    found = set()
    for n in z.namelist():
        if n.startswith("data/cobblemon/species/") and n.endswith(".json"):
            r = (json.loads(z.read(n)).get("behaviour") or {}).get("resting") or {}
            if not r.get("canSleep"):
                continue
            hi = int(str(r.get("light", "0-15")).split("-")[-1])
            if hi >= 11 and any(t in ("day", "any") for t in r.get("times", ["night"])):
                found.add(n.rsplit("/", 1)[1][:-5])
    assert found == day
    r = (species_doc(z, "buneary").get("behaviour") or {}).get("resting") or {}
    assert r.get("canSleep") and r.get("light") == "0-4" and "times" not in r, "Buneary: a night sleeper in the dark"


def test_every_species_is_implemented_in_the_jar():
    z = jar()
    for s in sorted(all_species()):
        d = species_doc(z, s)
        assert d is not None and d.get("implemented"), s


# Without it the lists could name a behaviour the jar does not have (the brain would be built without it), or the
# awake list could keep the sleep, or the follower could have no wander or no home walk.
def test_the_behaviour_lists():
    b = RULES["behaviours"]
    assert "cobblemon:pokemon_sleeps" in b["sleeper"]
    assert b["awake"] == [x for x in b["sleeper"] if x != "cobblemon:pokemon_sleeps"]
    assert "cobblemon:wanders" in b["follower"] and "cobblemon:stationary" in b["follower"]
    assert "cobblemon:pokemon_sleeps" not in b["follower"]
    z = jar()
    names = set(z.namelist())
    for ident in set(b["sleeper"] + b["follower"]):
        ns, path = ident.split(":")
        assert any(("data/%s/behaviours/%s%s.json" % (ns, sub, path)) in names
                   for sub in ("", "pokemon/", "pokemon/auto/")), ident


# The owner's rule, and the hysteresis that stops a sleeper flickering at the edge of it.
def test_the_wake_rule_is_the_owners():
    assert RULES["wake_radius"] == 16
    assert RULES["rest_radius"] > RULES["wake_radius"]


# ------------------------------------------------------------------------------------------------ the plan

def plan():
    idx = FNDIR / "index.txt"
    if not AI.PLAN.is_file() or not idx.is_file():
        pytest.skip("NOT_EXECUTED: the idle pack is not built (python tools/ambient_idle.py build)")
    pl = json.loads(AI.PLAN.read_text(encoding="utf-8"))
    for town, spec in IDLE["towns"].items():
        want = sorted(s for k in pl["kinds_on"] for s in spec.get(k) or [])
        got = sorted(i["species"] for i in pl["towns"].get(town, []))
        if want != got:
            pytest.skip("NOT_EXECUTED: the built plan is not data/ambient.json's (%s); rebuild" % town)
    return pl


def everyone(pl):
    return [i for v in pl["towns"].values() for i in v]


def test_each_town_holds_what_its_data_says_by_kind_and_stays_under_the_cap():
    pl = plan()
    nw = {}
    for w in WORKERS:
        nw[w["settlement"]] = nw.get(w["settlement"], 0) + 1
    for town, spec in IDLE["towns"].items():
        idlers = pl["towns"][town]
        for k in pl["kinds_on"]:
            assert sorted(i["species"] for i in idlers if i["kind"] == k) == sorted(spec.get(k) or []), (town, k)
        assert len(idlers) + nw.get(town, 0) <= RULES["cap_per_town"], town
    assert len(pl["towns"][AI.BUNEARY_TOWN]) == len(IDLE["buneary"]["spots"])


# Without it a "group of 1-3" could be a crowd: the frame-rate test found the cost is everything close and in view.
def test_no_crowd_of_more_than_three():
    pl = plan()
    for town, idlers in pl["towns"].items():
        for a in idlers:
            near = [b for b in idlers if math.dist((a["at"][0], a["at"][2]), (b["at"][0], b["at"][2])) < RULES["group_gap"] / 2.0]
            assert len(near) <= 3, (town, a["id"], [b["id"] for b in near])


def test_ids_are_unique_and_never_a_workers():
    pl = plan()
    ids = [i["id"] for i in everyone(pl)]
    assert len(ids) == len(set(ids))
    assert not set(ids) & {w["id"] for w in WORKERS}
    assert all(re.fullmatch(r"idle_[a-z0-9_]+_\d\d", i) for i in ids)


def footprints(town):
    p = ROOT / "derived" / "towns" / ("%s_placement.json" % town)
    if not p.is_file():
        return []
    return [tuple(b["footprint"]) for b in json.loads(p.read_text(encoding="utf-8"))["buildings"]]


def plaza(town):
    p = ROOT / "derived" / "plaza_centres" / ("%s.json" % town)
    return json.loads(p.read_text(encoding="utf-8")) if p.is_file() else None


# Without it an idler could stand inside a house, on a stall or a lamp, or on a bench's neighbour block.
def test_no_idler_stands_in_a_building_or_on_a_plaza_piece_other_than_its_bench():
    pl = plan()
    for town, idlers in pl["towns"].items():
        if town == AI.BUNEARY_TOWN:
            continue
        rects = footprints(town)
        pz = plaza(town)
        pieces = {}
        if pz:
            for p in pz["pieces"]:
                for c in p.get("columns") or []:
                    pieces[tuple(c)] = p
        for i in idlers:
            x, z = math.floor(i["at"][0]), math.floor(i["at"][2])
            for r in rects:
                assert not (r[0] - 1 <= x <= r[2] + 1 and r[1] - 1 <= z <= r[3] + 1), (i["id"], r)
            p = pieces.get((x, z))
            if p is not None:
                assert p["kind"] == "bench" and i["kind"] == "sitter" and i["at"][1] == p["floor_y"] + 0.5, (i["id"], p["id"])


def test_no_idler_stands_on_a_workers_cells():
    pl = plan()
    for wid, cells in AI.worker_cells().items():
        for i in everyone(pl):
            c = (math.floor(i["at"][0]), math.floor(i["at"][2]))
            assert min(math.dist(c, w) for w in cells) > 1.5, (i["id"], wid)


# Without it an idler could hang in the air over a plaza graded below the heightmap, or stand in the ground.
def test_every_idler_stands_on_the_ground_the_plaza_or_its_bench():
    pl = plan()
    import ground as G
    try:
        g = G.Ground(None)
    except BaseException:
        pytest.skip("NOT_EXECUTED: no canonical heightmap here")
    for town, idlers in pl["towns"].items():
        pz = plaza(town)
        tp = ROOT / "derived" / "towns" / ("%s_plan.json" % town)
        streets = {}
        tplan = json.loads(tp.read_text(encoding="utf-8")) if tp.is_file() else {}
        if not pz and tplan.get("plaza"):
            # no plaza dressing: the town plan's own graded plaza (tools/place_town.py paves it at that y)
            pz = {"square": {"rect": tplan["plaza"]["rect"], "y": tplan["plaza"]["y"]}}
        if tplan:
            for st in (tplan.get("streets") or {}).values():
                for zz, y, xa, xb in st.get("cells") or []:
                    for xx in range(xa, xb + 1):
                        streets[(xx, zz)] = y
        for i in idlers:
            x, y, z = i["at"]
            cx, cz = math.floor(x), math.floor(z)
            if i["where"] == "bench":
                continue        # the seat: checked above against the bench's own floor_y
            if pz:
                r = pz["square"]["rect"]
                if min(r[0], r[2]) <= cx <= max(r[0], r[2]) and min(r[1], r[3]) <= cz <= max(r[1], r[3]):
                    assert y == pz["square"]["y"] + 1, i["id"]
                    continue
            assert y in (g(cx, cz) + 1, streets.get((cx, cz), -999) + 1), (i["id"], y, g(cx, cz))


def test_the_buneary_are_round_the_snow_house_and_off_it():
    pl = plan()
    bun = pl["towns"][AI.BUNEARY_TOWN]
    cx, cz = json.loads((ROOT / "data" / "lopunny_house.json").read_text(encoding="utf-8"))["site"]["centre"]
    assert 4 <= len(bun) <= 6
    assert {i["species"] for i in bun} == {"buneary"}
    for i in bun:
        d = max(abs(i["at"][0] - cx), abs(i["at"][2] - cz))
        assert 7 < d <= 16, (i["id"], d)          # outside the walls and eaves (half 5, overhang 1), still round it


# ------------------------------------------------------------------------------------------------ the pack

def pack():
    plan()
    return {p.relative_to(FNDIR).with_suffix("").as_posix(): p.read_text(encoding="utf-8").splitlines()
            for p in FNDIR.rglob("*.mcfunction")}


def test_every_function_passes_the_function_limits():
    fns = pack()
    bad = {n: function_limits.check_lines(l, n) for n, l in fns.items()}
    assert not {n: b for n, b in bad.items() if b}


# Without it a spawn could be a plain line (inert after a restart, EXP-046) or go unclaimed (despawned in a minute).
def test_every_spawn_is_the_macro_and_is_claimed_in_the_same_function():
    fns = pack()
    for name, lines in fns.items():
        for l in lines:
            if "spawnpokemonat" in l and not l.startswith("#"):
                assert name == "spawn_at" and l.startswith("$spawnpokemonat ") and l.endswith("uncatchable no_ai")
    pl = plan()
    for i in everyone(pl):
        s = fns["i/%s/spawn" % i["id"]]
        assert s[0].startswith("function %s/spawn_at " % F)
        assert "tag=!cobblers.amb," in s[1] and "nbt={NoAI:1b}" in s[1] and s[1].endswith("/i/%s/claim" % i["id"])


# Any `data merge` remakes a Pokemon's brain (PokemonEntity.remakeBrain after an NBT load), which wakes a sleeper: the
# keeper may never merge one; only the claim, the wake and the settle do.
def test_nothing_that_runs_every_keep_merges_an_idlers_nbt():
    fns = pack()
    for name, lines in fns.items():
        if name.startswith("t/") or name in ("keep_all", "tick", "wakes"):
            assert not any("data merge" in l for l in lines), name


def test_the_claims_set_each_kinds_flags():
    fns, pl = pack(), plan()
    beh = RULES["behaviours"]
    for i in everyone(pl):
        c = "\n".join(fns["i/%s/claim" % i["id"]])
        for flag in ("PersistenceRequired:1b", "Invulnerable:1b", "Unbattleable:1b", "tag @s add cobblers.amb.idle",
                     "tag @s add cobblers.amb.%s" % i["id"]):
            assert flag in c, (i["id"], flag)
        if i["kind"] in ("sitter", "loafer"):
            assert "NoAI:1b" in c and "Behaviours" not in c
        else:
            assert "NoAI:0b" in c and "BehavioursAreCustom:1b" in c
            want = beh["sleeper"] if i["kind"] == "sleeper" else beh["follower"]
            assert "Behaviours:[%s]" % ",".join('"%s"' % b for b in want) in c
        if i["kind"] == "sleeper":
            assert "tag @s add cobblers.amb.dozer" in c
        if i["kind"] == "follower":
            x, y, z = i["at"]
            assert "home_x:%sd,home_y:%sd,home_z:%sd" % (AI.num(x), AI.num(y), AI.num(z)) in c


def test_reapply_settles_every_town_and_checks_the_idlers():
    pl = plan()
    steps = AI.placement_steps()
    keeps = [v for k, v in steps if k == "fn"]
    assert keeps == ["%s/t/%s/keep" % (F, s) for s in sorted(pl["towns"]) if pl["towns"][s] for _ in (0, 1)]
    for k, v in steps:
        if k == "cmd" and v.startswith("forceload add"):
            x0, z0, x1, z1 = (int(t) for t in v.split()[2:])
            assert ((x1 // 16 - x0 // 16) + 1) * ((z1 // 16 - z0 // 16) + 1) <= 256, v
    import ambient
    assert ambient.placement_steps()[-len(steps):] == steps, "R16C's steps (ambient.placement_steps) end with the idlers'"
    src = (ROOT / "tools" / "reapply.py").read_text(encoding="utf-8")
    assert src.count('"cobblers_ambient_idle"') == 2, "in SERVER_PACKS and WORLD_LOCAL"
    assert '("check", "ambient_idle")' in src and 'v == "ambient_idle"' in src


# ------------------------------------------------------------------------------------------------ the pack, run

_W = {}


def sim_pack():
    pack()
    if not _W:
        w = M.World.from_pack(AI.OUT)
        _W.update(functions=w.functions, tags=w.tags)
    return _W


def world():
    p = sim_pack()
    w = M.World(p["functions"])
    w.tags = p["tags"]
    w.run_load()
    return w


def idlers_of(w, iid):
    return w.living("cobblemon:pokemon", "cobblers.amb.%s" % iid)


def town_with_sleeper(pl):
    for s in sorted(pl["towns"]):
        sl = [i for i in pl["towns"][s] if i["kind"] == "sleeper"]
        if sl and s != AI.BUNEARY_TOWN:
            return s, sl[0]
    pytest.skip("no sleeper built")


# Without it the four lines a tick this pack costs with nobody near could grow with every idler, the workers' driver's
# 24-line mistake (docs/mechanics/TOWN_TICK_BUDGET.md 2.4).
def test_the_tick_is_four_lines_whatever_the_count():
    fns = pack()
    assert len([l for l in fns["tick"] if not l.startswith("#")]) == 4


def test_a_town_settles_each_idler_once_held_and_protected():
    pl = plan()
    w = world()
    s = "gym1_town" if pl["towns"].get("gym1_town") else sorted(k for k, v in pl["towns"].items() if v)[0]
    cx, cy, cz = pl["gates"][s]["centre"]
    w.add_player((cx, cy, cz))
    w.tick(RULES["keep_every"])
    for i in pl["towns"][s]:
        got = idlers_of(w, i["id"])
        assert len(got) == 1, i["id"]
        e = got[0]
        assert e.nbt["Pokemon"]["Species"] == i["species"]
        assert e.nbt.get("Invulnerable") == 1 and e.nbt.get("PersistenceRequired") == 1 and e.nbt.get("Unbattleable") == 1
        assert e.nbt.get("NoAI") == (1 if i["kind"] in ("sitter", "loafer") else 0), i["id"]
        assert math.dist(e.pos, i["at"]) < 0.01
        if i["kind"] in ("sitter", "loafer"):
            assert abs(e.rot[0] - i["yaw"]) < 0.01
    # a second keep spawns nothing more; a duplicate is removed
    n = len(w.living("cobblemon:pokemon"))
    first = pl["towns"][s][0]
    w.add(M.Entity("cobblemon:pokemon", [first["at"][0] + 5, first["at"][1], first["at"][2]],
                   tags=("cobblers.amb", "cobblers.amb.%s" % first["id"])))
    w.tick(RULES["keep_every"])
    assert len(w.living("cobblemon:pokemon")) == n and len(idlers_of(w, first["id"])) == 1
    assert math.dist(idlers_of(w, first["id"])[0].pos, first["at"]) < 0.01, "the one kept is the one on its spot"


def test_nobody_near_nothing_spawns():
    pl = plan()
    w = world()
    w.add_player((0.0, 64.0, 0.0))
    w.tick(3 * RULES["keep_every"])
    assert not w.living("cobblemon:pokemon")


def test_a_sleeper_is_woken_at_sixteen_and_settled_again_past_rest_radius():
    pl = plan()
    s, sl = town_with_sleeper(pl)
    w = world()
    x, y, z = sl["at"]
    # a player inside the town's gate but well away from this sleeper and every other one
    far = (x + RULES["rest_radius"] + 10, y, z)
    p = w.add_player(far)
    w.tick(RULES["keep_every"])
    e = idlers_of(w, sl["id"])[0]
    others = [i for i in pl["towns"][s] if i["kind"] == "sleeper" and math.dist(i["at"], far) <= RULES["wake_radius"]]
    if others:
        pytest.skip("NOT_EXECUTED: no spot clear of the other sleepers for this check")
    assert "cobblers.amb.dozer" in e.tags and "cobblemon:pokemon_sleeps" in e.nbt["Behaviours"]
    p.pos = [x + RULES["wake_radius"] - 1, y, z]
    w.tick(RULES["wake_every"])
    assert "cobblers.amb.woken" in e.tags and "cobblers.amb.dozer" not in e.tags
    assert e.nbt["Behaviours"] == RULES["behaviours"]["awake"]
    p.pos = [x + RULES["wake_radius"] + 4, y, z]             # between the radii: stays awake
    w.tick(RULES["wake_every"])
    assert "cobblers.amb.woken" in e.tags
    p.pos = list(far)
    w.tick(RULES["wake_every"])
    assert "cobblers.amb.dozer" in e.tags and e.nbt["Behaviours"] == RULES["behaviours"]["sleeper"]


def test_an_ai_idler_that_strays_is_put_back_and_one_inside_its_leash_is_not():
    pl = plan()
    s, sl = town_with_sleeper(pl)
    w = world()
    w.add_player(pl["gates"][s]["centre"])
    w.tick(RULES["keep_every"])
    e = idlers_of(w, sl["id"])[0]
    x, y, z = sl["at"]
    e.pos = [x + RULES["sleeper_leash"] - 1, y, z]
    w.tick(RULES["keep_every"])
    assert e.pos[0] == x + RULES["sleeper_leash"] - 1, "inside its leash it is left alone"
    e.pos = [x + RULES["sleeper_leash"] + 5, y, z]
    w.tick(RULES["keep_every"])
    assert math.dist(e.pos, sl["at"]) < 0.01
