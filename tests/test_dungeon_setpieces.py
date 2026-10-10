"""Parkour v2 (tools/dungeon_parkour.py) and the three set pieces (tools/dungeon_setpieces.py, data/dungeon_setpieces.json).

The builder's own tests (the independent audit is another agent's). What they prove and how:

  parkour   from the BUILT BLOCKS, not from the planner's records: the standable islands are found on the room's grid, the
            jumps between them are derived again here from the written rule (an axis-aligned jump of a flat gap of up to 3
            air blocks, or a rise or fall of one over up to 2, three clear above), and the route is asked to be long,
            bending, climbing, forked and checkpointed. The fork is proved by deleting each branch in turn. Mutations
            change the GENERATOR (hop sizes, the run-up rule), never the data, and must make a check fail.
  setpieces each piece's functions are REPLAYED state by state onto the room's block grid (the tick lines are parsed from
            the generated text, not read from the generator's records) and the grid is walked in every state: the span of
            a collapse, the water of a flood, the sheet of a lights-out room. "Never a trap" is the statement that in
            every state a player standing anywhere standable can walk to an exit, or is on a catch floor that teleports
            them to a ledge; the three mutations (a collapse with no head start, water one layer too high, a sheet laid
            under the player) must each fail.
  runtime   the generated functions driven on tests/pocket_sim.py through the engine's own keeper.

Not covered: anything in a running Minecraft. Whether a jump of 3 blocks feels fair, whether water attenuates the lights as
modelled, whether a sprinting player outruns the collapse are the owner's look and the experiments named in the report.
"""
from __future__ import annotations

import collections
import copy
import json
import re
import sys
import zipfile
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tests"))

import dungeon as D  # noqa: E402
import dungeon_grid as G  # noqa: E402
import dungeon_parkour as P  # noqa: E402
import dungeon_rooms as R  # noqa: E402
import dungeon_setpieces as S  # noqa: E402
import function_limits as FL  # noqa: E402
import test_dungeon_rooms as TR  # noqa: E402

BASE = D.load()
DEMO = {r["id"]: r for r in json.loads((ROOT / "tests" / "fixtures" / "dungeon_demo_rooms.json").read_text(encoding="utf-8"))["rooms"]}
POCKET = BASE["engine"]["pocket"]["dimension"]

CASES = {
    "collapse": ("mine", {"id": "sp", "kind": "setpiece", "length": 90, "width": 25, "height": 11, "params": {"piece": "collapse"}}),
    "flood": ("flooded_ruin", {"id": "sp", "kind": "setpiece", "length": 64, "width": 31, "height": 14,
                               "params": {"piece": "flood", "pit": 10}}),
    "lights_out": ("jungle", {"id": "sp", "kind": "setpiece", "length": 100, "width": 33, "height": 12,
                              "params": {"piece": "lights_out", "pit": 0, "no_deploy": False}}),
}


def doc_with(theme, extra, per_dungeon=1):
    doc = copy.deepcopy(BASE)
    d = doc["dungeons"][0]
    d["theme"] = theme
    d["rooms"] = [copy.deepcopy(DEMO[k]) for k in ("entry", "d1")] + [copy.deepcopy(r) for r in extra] + \
                 [copy.deepcopy(DEMO[k]) for k in ("d5", "arena", "exit")]
    d.pop("spine", None)
    d.pop("clock_s_by_band", None)
    d.pop("variants", None)        # the Night Shift's variants name its own rooms and re-roll per slot (as demo_doc does)
    d.pop("shape_mix", None)
    doc["dungeons"] = [d]
    doc["engine"]["sigils"]["free_first_entry"]["dungeons"] = [d["id"]]
    doc["engine"]["slots"]["per_dungeon"] = per_dungeon
    return doc


def case(name, **params):
    theme, room = CASES[name]
    room = copy.deepcopy(room)
    room["params"].update(params)
    return doc_with(theme, [room])


def slot1(doc):
    return D.slots(doc)[0]


def built(doc, rid="sp", slot=None):
    s = slot or slot1(doc)
    return next(b for b in R.slot_build(doc, doc["dungeons"][0], s) if b.room["id"] == rid)


@pytest.fixture(autouse=True)
def fresh_cache():
    R._BUILT.clear()
    yield
    R._BUILT.clear()


def parse_op(line):
    t = line.split()
    if t[0] == "setblock":
        return ("set", (int(t[1]), int(t[2]), int(t[3])), t[4])
    assert t[0] == "fill", line
    box = tuple(int(v) for v in t[1:7])
    mode = " ".join(t[8:]) or None
    return ("fill", box, t[7], mode) if mode else ("fill", box, t[7])


def replay(b, lines, g=None):
    """A copy of the room's grid with the fill and setblock lines applied (the other lines are not blocks)."""
    g = copy.deepcopy(b.grid) if g is None else g
    for ln in lines:
        if ln.startswith(("fill ", "setblock ")):
            g.apply(parse_op(ln))
    return g


def room_lines(doc, b, name, slot=None):
    """The generated function's lines (R.runtime_functions: no validation, so a mutated generator can be read)."""
    s = slot or slot1(doc)
    fns = R.runtime_functions(doc, doc["dungeons"][0], [s])
    return list(fns["room/night_shift/%s/s%d/%s" % (b.room["id"], s["g"], name)])


def start_cell(g, r):
    return g.local(r["ix0"], r["floor_in"], r["z_in"])


def end_cell(g, r):
    return g.local(r["ix1"], r["floor_out"], r["z_out"])


# ================================================================================================= parkour

def parkour_rooms(every_slot=False):
    """The real parkour rooms: each dungeon's first slot, or (every_slot) every slot, since pass 2's variants re-roll per
    slot and a quality that holds in slot 1 says nothing about slot 3."""
    out = []
    doc = D.load()
    for d in doc["dungeons"]:
        sls = [s for s in D.slots(doc) if s["dungeon"]["id"] == d["id"]]
        for sl in (sls if every_slot else sls[:1]):
            for b in R.slot_build(doc, d, sl):
                if b.room["kind"] == "parkour":
                    out.append((doc, d, sl, b))
    return out


def islands(g, r):
    """Standable cells grouped by walking (steps of one, no jumps): the platforms as the grid sees them."""
    cls = g.cls()
    st, _p = G.standable(cls)
    seen, out = {}, []
    for c in zip(*st.nonzero()):
        c = (int(c[0]), int(c[1]), int(c[2]))
        if c in seen:
            continue
        comp = G.walk(g, [c], jumps=False, cls=cls)
        for k in comp:
            seen[k] = len(out)
        out.append(comp)
    return out, seen, cls, st


def island_edges(g, isl, seen, cls, st):
    """Jump edges between islands, derived HERE from the written rule: along an axis, over n-1 air cells (n <= 4 flat, n <= 3
    with a rise or fall of one), the landing standable, two clear above the take-off and the gap cells. Returns
    {(a, b): (n_min, axis, dir)} with n_min the easiest cell pair of the two islands."""
    p = (cls == G.PASS) | (cls == G.WATER)
    nx, ny, nz = st.shape
    best = {}
    for ia, comp in enumerate(isl):
        for (x, y, z) in comp:
            for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                for n in range(2, 5):
                    tx, tz = x + dx * n, z + dz * n
                    if not (0 <= tx < nx and 0 <= tz < nz):
                        break
                    for dy in (0, 1, -1):
                        if dy and n > 3:
                            continue
                        ty = y + dy
                        if not (0 < ty < ny - 3) or not st[tx, ty, tz]:
                            continue
                        top = max(y, ty)
                        if not all(p[x + dx * k, top + 1, z + dz * k] and p[x + dx * k, top + 2, z + dz * k] for k in range(1, n)):
                            continue
                        if dy == 1 and not (p[x, y + 2, z] and p[x, y + 3, z]):
                            continue
                        ib = seen.get((tx, ty, tz))
                        if ib is None or ib == ia:
                            continue
                        key = (ia, ib)
                        if key not in best or n < best[key][0]:
                            best[key] = (n, "x" if dx else "z", dx + dz)
    return best


def route_stats(g, r):
    isl, seen, cls, st = islands(g, r)
    edges = island_edges(g, isl, seen, cls, st)
    start = seen[start_cell(g, r)]
    goal = seen[end_cell(g, r)]
    adj = collections.defaultdict(list)
    for (a, b), (n, ax, sg) in edges.items():
        adj[a].append((b, n, ax, sg))
    prev, dist = {start: None}, {start: 0}
    dq = collections.deque([start])
    while dq:
        u = dq.popleft()
        for v, n, ax, sg in adj[u]:
            if v not in prev:
                prev[v] = (u, ax, sg, n)
                dq.append(v)
    assert goal in prev, "the exit is not reachable by the islands graph"
    path, node = [], goal
    while prev[node]:
        u, ax, sg, n = prev[node]
        path.append((ax, sg, n))
        node = u
    path.reverse()
    turns = sum(1 for a, b in zip(path, path[1:]) if a[:2] != b[:2])
    levels = sorted({max(y for (_x, y, _z) in isl[i]) for i in prev})
    return {"islands": len(isl), "edges": edges, "path": path, "turns": turns, "levels": levels, "isl": isl, "seen": seen,
            "start": start, "goal": goal, "adj": adj}


def test_every_real_parkour_room_is_long_winding_climbing_and_has_hard_jumps_from_its_blocks():
    rooms = parkour_rooms(every_slot=True)
    assert len(rooms) == 12, "one parkour per dungeon, in each of its four slots (variants)"
    for doc, d, sl, b in rooms:
        r, g = b.room, b.grid
        st = route_stats(g, r)
        lab = "%s/%s s%d" % (d["id"], r["id"], sl["g"])
        long_hops = [k for k, e in st["edges"].items() if e[0] == 4 and k[0] < k[1]]
        assert len(long_hops) >= 4, (lab, "hops of 4 cells (a gap of 3 blocks)", len(long_hops))
        assert st["turns"] >= 4, (lab, "bends on the shortest route", st["turns"])
        assert st["levels"][-1] - st["levels"][0] >= 3, (lab, "levels the route climbs", st["levels"])
        assert len(b.anchors["checkpoints"]) >= 3, lab
        assert len(b.anchors["platforms"]) >= 20, lab
        # no jump on the whole route is beyond the rule: the planner's records, re-checked on the blocks
        for e in st["edges"].values():
            assert e[0] <= 4
        spread = max(c[2] for c in b.anchors["platforms"]) - min(c[2] for c in b.anchors["platforms"])
        assert spread >= (r["iz1"] - r["iz0"]) * 0.5, (lab, "the route uses the room's width", spread)


def test_parkour_hops_in_the_plan_agree_with_the_blocks_and_the_run_up_rule_holds():
    for doc, d, sl, b in parkour_rooms():
        g = b.grid
        cls = g.cls()
        st, _p = G.standable(cls)
        for h in b.meta["hops"]:
            ax, sg, n, dy = h["axis"], h["dir"], h["n"], h["dy"]
            assert 2 <= n <= 4 and (n <= 3 or dy == 0), h
            # the take-off cell is the edge of the platform jumped from along the jump, the landing cell the near edge of the next
            fx0, fx1, fz0, fz1, fy_ = h["from"]
            tx0, tx1, tz0, tz1, ty_ = h["to"]
            lat = h["lat"]
            if ax == "x":
                take = ((fx1 if sg > 0 else fx0), fy_, lat)
                land = (take[0] + sg * n, ty_, lat)
                run = fx1 - fx0 + 1
            else:
                take = (lat, fy_, (fz1 if sg > 0 else fz0))
                land = (lat, ty_, take[2] + sg * n)
                run = fz1 - fz0 + 1
            assert st[g.local(*take)] and st[g.local(*land)], (h, "take-off and landing are standable on the built blocks")
            if n == 4:
                assert run >= 3, (h, "a 4-cell hop needs a run-up of 3 cells")


def test_a_fork_has_two_ways_and_either_alone_gets_through():
    for doc, d, sl, b in parkour_rooms(every_slot=True):
        r, g = b.room, b.grid
        fork = b.meta["fork"]
        assert fork is not None, (d["id"], "every real parkour here is long enough for a fork")
        cls0 = g.cls()
        full = G.walk(g, [start_cell(g, r)], jumps=True, cls=cls0)
        assert end_cell(g, r) in full
        fy = r["floor_in"]
        by_branch = collections.defaultdict(list)
        for h in b.meta["hops"]:
            if h["branch"]:
                by_branch[h["branch"]].append(h)
        assert set(by_branch) == {"hard", "safe"}
        # the branches are told apart by what they build: the hard chain's tier-3 hops (gap 3) vs the safe chain's short ones
        assert max(h["n"] for h in by_branch["hard"]) == 4 and max(h["n"] for h in by_branch["safe"]) <= 3
        assert len(by_branch["safe"]) > len(by_branch["hard"]) + 3, "the safe way is the long way"
        for name in ("hard", "safe"):
            g2 = copy.deepcopy(g)
            other = "safe" if name == "hard" else "hard"
            seen_rects = set()
            for h in by_branch[other]:
                for key in ("from", "to"):
                    x0, x1, z0, z1, top = h[key]
                    if (x1 - x0 >= 5 and z1 - z0 >= 5):
                        continue        # a ledge (the fork's own ends), never deleted
                    if (x0, x1, z0, z1, top) in seen_rects:
                        continue
                    seen_rects.add((x0, x1, z0, z1, top))
                    cx, cz = (x0 + x1) // 2, (z0 + z1) // 2
                    g2.apply(("fill", (x0, top - 1, z0, x1, top - 1, z1), "minecraft:air"))
                    g2.apply(("fill", (cx, r["y_lo"], cz, cx, top - 2, cz), "minecraft:air"))
            c2 = g2.cls()
            reach = G.walk(g2, [start_cell(g2, r)], jumps=True, cls=c2)
            assert end_cell(g2, r) in reach, (d["id"], "the %s way alone must get through" % name)
            assert len(reach) < len(full)
        # control: with both ways deleted the exit is cut off (the checks can fail)
        g3 = copy.deepcopy(g)
        for name in ("hard", "safe"):
            for h in by_branch[name]:
                for key in ("from", "to"):
                    x0, x1, z0, z1, top = h[key]
                    if not (x1 - x0 >= 5 and z1 - z0 >= 5):
                        g3.apply(("fill", (x0, top - 1, z0, x1, top - 1, z1), "minecraft:air"))
        assert end_cell(g3, r) not in G.walk(g3, [start_cell(g3, r)], jumps=True, cls=g3.cls())


def test_no_platform_pair_is_a_short_cut_on_the_blocks():
    """Every island-to-island jump the blocks allow is one of the plan's hops, and every hop is one the blocks allow: the
    route has no short cut and no hop the rule does not grant."""
    for doc, d, sl, b in parkour_rooms():
        r, g = b.room, b.grid
        st = route_stats(g, r)
        x0, y0, z0 = g.box[:3]

        def rect(i):
            comp = st["isl"][i]
            xs = [min(max(c[0] + x0, r["ix0"]), r["ix1"]) for c in comp]       # a ledge's island runs on through the door
            zs = [c[2] + z0 for c in comp]
            return (min(xs), max(xs), min(zs), max(zs), max(c[1] for c in comp) + y0)
        grid_pairs = {frozenset((rect(a), rect(c))) for (a, c) in st["edges"] if (c, a) in st["edges"]
                      and rect(a)[4] > r["y_lo"] and rect(c)[4] > r["y_lo"]}
        plan_pairs = {frozenset((tuple(h["from"]), tuple(h["to"]))) for h in b.meta["hops"]}
        assert grid_pairs == plan_pairs, (d["id"], len(grid_pairs), len(plan_pairs), sorted(map(sorted, grid_pairs ^ plan_pairs))[:2])


def test_parkour_checkpoints_and_catch_floor_follow_the_kits_protocol():
    for doc, d, sl, b in parkour_rooms():
        r = b.room
        files = D.build(doc)
        tick = files["data/cobblers/function/dungeons/room/%s/%s/s%d/tick.mcfunction" % (d["id"], r["id"], sl["g"])]
        fall = files["data/cobblers/function/dungeons/room/%s/%s/s%d/fall.mcfunction" % (d["id"], r["id"], sl["g"])]
        n = len(b.anchors["checkpoints"])
        assert len(re.findall(r"scoreboard players set @s dg\.ck \d+", tick)) == n
        assert len(re.findall(r"execute if score @s dg\.ck matches \d+ run tp @s", fall)) == n
        assert "execute unless score @s dg.ck matches 0..%d run scoreboard players set @s dg.ck 0" % (n - 1) in fall
        # a catch floor under every column
        g = b.grid
        cls = g.cls()
        x0, y0, z0 = g.box[:3]
        for x in range(r["ix0"], r["ix1"] + 1):
            for z in range(r["iz0"], r["iz1"] + 1):
                assert cls[x - x0, r["y_lo"] - 1 - y0, z - z0] == G.SOLID
        # every checkpoint teleport lands on a standable cell
        st, _p = G.standable(cls)
        for c in b.anchors["checkpoints"]:
            assert st[g.local(c[0], c[1], c[2])]


def test_a_parkour_is_the_same_dungeon_in_every_slot_of_its_variant():
    """Pass 2 gives each slot its own variant (DUNGEON_ROOMS.md 1a: slot k builds variants[(k - 1) % n], `seed` re-rolls),
    so slot 1 and slot 4 are no longer one plan. What still holds: the plan is a function of the VARIANT, never of where the
    slot lies. Slot 4's strip asked to build slot 1's variant (its `k` set to slot 1's) plans slot 1's hops exactly."""
    doc = D.load()
    d = doc["dungeons"][2]
    slots = [s for s in D.slots(doc) if s["dungeon"]["id"] == d["id"]]
    moved = dict(slots[3], k=slots[0]["k"])
    assert moved["z0"] != slots[0]["z0"]
    a = next(b for b in R.slot_build(doc, d, slots[0]) if b.room["kind"] == "parkour")
    c = next(b for b in R.slot_build(doc, d, moved) if b.room["kind"] == "parkour")
    ka = [(h["axis"], h["dir"], h["n"], h["dy"], h["branch"]) for h in a.meta["hops"]]
    kc = [(h["axis"], h["dir"], h["n"], h["dy"], h["branch"]) for h in c.meta["hops"]]
    assert ka == kc and len(ka) > 20
    # and the variants that re-roll (a `seed`) really do plan another route: the replayability is not a label
    k4 = [(h["axis"], h["dir"], h["n"], h["dy"], h["branch"]) for h in
          next(b for b in R.slot_build(doc, d, slots[2]) if b.room["kind"] == "parkour").meta["hops"]]
    assert R.variant_of(doc, d, slots[2]).get("seed") and k4 != ka


def test_parkour_refuses_what_it_cannot_build():
    doc = TR.demo_doc("mine")
    d = doc["dungeons"][0]
    short = copy.deepcopy(TR.DEMO)
    next(r for r in short if r["id"] == "jump")["length"] = 36
    p = R.problems(TR.demo_doc("mine", short))
    assert any("a parkour is at least" in x or "no parkour route" in x for x in p), p[:3]
    for bad_params in ({"sections": 9}, {"tiers": [4]}):
        rooms = copy.deepcopy(TR.DEMO)
        next(r for r in rooms if r["id"] == "jump")["params"] = bad_params
        try:
            p = R.problems(TR.demo_doc("mine", rooms))
        except (KeyError, R.RoomError) as e:      # an unknown tier is a KeyError out of the tier table: refused, not built
            p = [str(e)]
        assert p, bad_params


# ---- mutations: change the generator, leave the data alone ----------------------------------------------------------


def test_mutating_the_generator_to_hop_five_cells_makes_the_walk_check_fail(monkeypatch):
    orig = P._tier_opts

    def longer(tier, relaxed):
        N, W = orig(tier, relaxed)
        return [n + 1 for n in N], W
    monkeypatch.setattr(P, "_tier_opts", longer)
    R._BUILT.clear()
    p = R.problems(TR.demo_doc("jungle"))
    assert any("cannot be walked" in x or "no parkour route" in x for x in p), p[:3]


def test_mutating_the_generator_to_drop_the_run_up_rule_makes_the_blocks_check_fail(monkeypatch):
    monkeypatch.setattr(P, "RUN_UP", 0)       # the run-up rule is gone
    R._BUILT.clear()
    doc = D.load()
    bad = []
    # every real parkour in every slot (pass 2's variants re-roll per slot: no one slot is the whole of the dungeon)
    for sl in D.slots(doc):
        for b in R.slot_build(doc, sl["dungeon"], sl):
            if b.room["kind"] != "parkour":
                continue
            for h in b.meta["hops"]:
                run = (h["from"][1] - h["from"][0] + 1) if h["axis"] == "x" else (h["from"][3] - h["from"][2] + 1)
                if h["n"] == 4 and run < 3:
                    bad.append(h)
    assert bad, "with the rule removed a hop of 4 cells is taken from a platform shorter than 3"


# ================================================================================================= palette data


def vanilla_ids():
    return TR.vanilla_ids()


def walk_values(v, out):
    if isinstance(v, str) and v.startswith("minecraft:"):
        out.add(v)
    elif isinstance(v, dict):
        for x in v.values():
            walk_values(x, out)
    elif isinstance(v, list):
        for x in v:
            walk_values(x, out)


def test_setpiece_palette_is_legal_and_every_id_exists_in_the_jar():
    d = S.data()
    assert d["schema"] == S.SCHEMA
    ids = set()
    walk_values({k: v for k, v in d.items() if k not in ("why", "schema")}, ids)
    jar = vanilla_ids()
    blocks = set()
    for piece in S.PIECES:
        for theme, entry in d[piece].items():
            if theme == "why":
                continue
            for k, v in entry.items():
                if isinstance(v, str) and v.startswith("minecraft:") and not k.startswith(("sound", "particle", "effect")):
                    blocks.add(v)
    for b in blocks:
        assert not G.forbidden(b), b
        assert G.classify(b) != G.HAZARD, b
        assert G.base(b) not in BASE["engine"]["rift_pick"]["can_break"], b
        if jar is not None:
            assert G.base(b) in jar, b
    z = zipfile.ZipFile(__import__("town_character").default_vanilla_jar()) if jar is not None else None
    if z is not None:
        names = set(z.namelist())
        lang = json.loads(z.read("assets/minecraft/lang/en_us.json"))
        for piece in S.PIECES:
            for theme, entry in d[piece].items():
                for k, v in (entry.items() if theme != "why" else ()):
                    if k.startswith("particle"):
                        assert "assets/minecraft/particles/%s.json" % v.split(":")[1] in names, v
                    if k.startswith("effect"):
                        assert "effect.minecraft.%s" % v.split(":")[1] in lang, v


# ================================================================================================= set pieces: static


@pytest.mark.parametrize("name", list(CASES))
def test_each_piece_builds_clean_and_every_function_obeys_the_command_limits(name):
    doc = case(name)
    assert R.problems(doc) == []
    b = built(doc)
    files = D.build(doc)
    pref = "data/cobblers/function/dungeons/room/night_shift/sp/s1/"
    mine = {k: v for k, v in files.items() if k.startswith(pref)}
    assert {"tick", "enter", "reset"} <= {k[len(pref):-len(".mcfunction")] for k in mine}
    for k, v in mine.items():
        assert FL.check_lines(v.splitlines(), k) == [], k
        for ln in v.splitlines():
            if ln.startswith("fill "):
                assert R.op_volume(parse_op(ln)) <= FL.FILL_LIMIT, ln
    # a piece is not a quiet kit room: it is flagged as the kit's no-deploy / catch protocol says
    assert b.room["kind"] == "setpiece" and b.meta["piece"] == name


@pytest.mark.parametrize("name", list(CASES))
def test_every_function_a_piece_generates_is_called_by_another(name):
    """prepare refuses an orphan function (one no step, pack or function runs): a piece's `arm`, `restore`, `fall`, `sweep`,
    `drain` and `close<k>` must each be called from its tick or from each other."""
    doc = case(name)
    files = D.build(doc)
    pref = "data/cobblers/function/dungeons/room/night_shift/sp/s1/"
    mine = {k[len(pref):-len(".mcfunction")]: v for k, v in files.items() if k.startswith(pref)}
    hooks = {"enter", "tick", "reset", "clear"}
    called = "\n".join(mine.values()) + "\n"
    for fn in mine:
        if fn not in hooks:
            assert "function cobblers:dungeons/room/night_shift/sp/s1/%s\n" % fn in called, (name, fn, "is never called")


def test_a_basin_too_shallow_to_sweep_from_is_refused_before_it_makes_an_orphan():
    assert any("orphan" in x for x in R.problems(case("flood", pit=6)))


def test_a_setpiece_with_the_wrong_params_is_refused_with_the_exact_fix():
    bad = case("lights_out", pit=8)
    assert any("params.pit 0" in x for x in R.problems(bad))
    assert any("one of" in x or "piece" in x for x in R.problems(case("collapse", piece="rubble")))
    assert any("under five segments" in x for x in R.problems(case("collapse", ledge=40)))
    tiny = case("flood")
    tiny["dungeons"][0]["rooms"][2]["length"] = 36
    assert any("length" in x for x in R.problems(tiny))


def test_a_setpiece_is_the_same_dungeon_in_every_slot():
    doc = doc_with(CASES["flood"][0], [CASES["flood"][1]], per_dungeon=4)
    sl = D.slots(doc)
    a, c = built(doc, slot=sl[0]), built(doc, slot=sl[3])
    off = sl[3]["z0"] - sl[0]["z0"]
    assert len(a.ops) == len(c.ops) and a.meta["when"] == c.meta["when"]
    assert a.meta["pillars"] == [(x, z - off) for x, z in c.meta["pillars"]]


# ================================================================================================= collapse


def collapse_events(lines, H):
    """Parsed from the generated tick text: {pass count: [op lines]} for the rows `execute if score H dg.rs matches N run fill`."""
    ev = collections.defaultdict(list)
    for ln in lines:
        m = re.match(r"execute if score %s dg\.rs matches (\d+) run (fill .*)$" % re.escape(H), ln)
        if m:
            ev[int(m.group(1))].append(m.group(2))
    return ev


def collapse_states(doc):
    """[(H, grid)] for H = 0 .. END: the room's blocks after the tick of pass H, replayed from the generated text."""
    b = built(doc)
    lines = room_lines(doc, b, "tick")
    ev = collapse_events(lines, b.meta["holder"])
    g = copy.deepcopy(b.grid)
    out = [(0, copy.deepcopy(g))]
    for h in range(1, b.meta["end"] + 1):
        for ln in ev.get(h, []):
            g.apply(parse_op(ln))
        out.append((h, copy.deepcopy(g)))
    return b, ev, out


def test_collapse_in_every_state_a_player_on_the_surviving_floor_can_always_run_to_the_far_ledge():
    """The trap statement: at every pass, every standable cell above the catch floor reaches the east ledge on foot (the
    floor ahead of the front is whole and connected), and the cells that fell are exactly the span behind the front."""
    doc = case("collapse")
    b, ev, states = collapse_states(doc)
    r = b.room
    east_door, west_door = end_cell(b.grid, r), start_cell(b.grid, r)
    sx0, sx1 = b.meta["span"]
    for h, g in states:
        cls = g.cls()
        st, _p = G.standable(cls)
        reach = G.walk(g, [east_door, west_door], jumps=False, cls=cls)
        x0, y0, z0 = g.box[:3]
        for (lx, ly, lz) in zip(*st.nonzero()):
            x, y, z = int(lx) + x0, int(ly) + y0, int(lz) + z0
            if not (r["ix0"] <= x <= r["ix1"] and r["iz0"] <= z <= r["iz1"]) or y != r["floor_in"]:
                continue        # the catch floor's cells are another statement (teleported out); a timber beam 6 up is out of reach
            assert (int(lx), int(ly), int(lz)) in reach, (h, x, y, z, "a floor cell with no walk to either ledge")
    # the span is gone at the end, whole at the start, and the ledges never go
    g0, gE = states[0][1], states[-1][1]
    fy = r["floor_in"]
    zm = (r["iz0"] + r["iz1"]) // 2
    assert all(g0.block_at(x, fy - 1, zm) != "minecraft:air" for x in range(sx0, sx1 + 1))
    assert all(gE.block_at(x, fy - 1, zm) == "minecraft:air" for x in range(sx0, sx1 + 1))
    for x in list(range(r["ix0"], sx0)) + list(range(sx1 + 1, r["ix1"] + 1)):
        assert gE.block_at(x, fy - 1, zm) != "minecraft:air", x
    assert g0.block_at(sx0 + 3, fy - 1, r["iz0"]) == "minecraft:air", "a strip of pit along each wall: the audit can see a fall"


def test_collapse_a_walker_at_walking_pace_stays_ahead_of_the_front_and_a_stander_is_caught():
    """From the generated text: when does each x fall? A player who steps onto the span at pass 1 and walks at the vanilla
    walking speed (4.317 blocks/s, one pass a second) is always ahead of the first cell that has fallen, and the span's
    far end falls only after they have crossed. One who stands still at the first segment falls."""
    doc = case("collapse")
    b, ev, states = collapse_states(doc)
    r = b.room
    fy = r["floor_in"]
    sx0, sx1 = b.meta["span"]
    fall_pass = {}
    for h, lines in ev.items():
        for ln in lines:
            op = parse_op(ln)
            if op[2] == "minecraft:air":
                for x in range(op[1][0], op[1][3] + 1):
                    fall_pass[x] = h
    assert set(fall_pass) == set(range(sx0, sx1 + 1))
    WALK, SPRINT = 4.317, 5.612
    for speed in (WALK, SPRINT):
        x = sx0 + 0.5
        for t in range(1, b.meta["end"] + 1):
            x_t = sx0 + speed * (t - 1) + 0.5        # at the t-th pass after the arming pass
            if x_t > sx1 + 1:
                break
            assert fall_pass[min(int(x_t), sx1)] > t, (speed, t, x_t, "the floor under a walker fell")
    standing = fall_pass[sx0]
    assert standing <= b.meta["lead"] + b.meta["warn"] + 1, "a player who stops at the start is caught within a few seconds"
    assert max(fall_pass.values()) >= (sx1 - sx0) / WALK, "the far end outlasts a walker"


def test_collapse_ledges_restore_the_span_whole_and_the_reset_does_too():
    doc = case("collapse")
    b, ev, states = collapse_states(doc)
    for name in ("restore", "reset"):
        lines = room_lines(doc, b, name)
        g = replay(b, lines, copy.deepcopy(states[-1][1]))
        assert (g.a == b.grid.a).all(), "%s puts the span back exactly" % name
    tick = room_lines(doc, b, "tick")
    H = b.meta["holder"]
    for ledge in ("west", "east"):
        pass
    restores = [ln for ln in tick if "run function" in ln and ln.endswith("/restore")]
    assert len(restores) == 2 and all(("if score %s dg.rs matches 0.." % H) in ln for ln in restores)
    fall = room_lines(doc, b, "fall")
    assert any(ln.startswith("function ") and ln.endswith("/restore") for ln in fall), "a fall restores the span first"


def test_mutating_the_generator_to_drop_the_head_start_makes_the_walker_check_fail(monkeypatch):
    monkeypatch.setattr(S, "DEFAULT_LEAD", 0)
    monkeypatch.setattr(S, "DEFAULT_WARN", 0)
    R._BUILT.clear()
    doc = case("collapse")
    b, ev, states = collapse_states(doc)
    sx0, sx1 = b.meta["span"]
    fall_pass = {}
    for h, lines in ev.items():
        for ln in lines:
            op = parse_op(ln)
            if op[2] == "minecraft:air":
                for x in range(op[1][0], op[1][3] + 1):
                    fall_pass[x] = h
    caught = [t for t in range(1, b.meta["end"] + 1) if fall_pass.get(min(int(sx0 + 4.317 * (t - 1) + 0.5), sx1), 99) <= t]
    assert caught, "with no head start the floor falls under a walker: the check must be able to see it"


@pytest.fixture(scope="module")
def collapse_pack(tmp_path_factory):
    doc = case("collapse")
    out = tmp_path_factory.mktemp("cobblers_setpiece_collapse")
    D.write(D.build(doc), out)
    return doc, out


def test_collapse_runtime_arms_cracks_falls_on_schedule_and_the_far_ledge_restores(collapse_pack):
    doc, w = TR.rooms_world(collapse_pack)
    p, s = TR.enter_run(doc, w)
    b = built(doc, slot=s)
    r, m = b.room, b.meta
    H, fy = m["holder"], r["floor_in"]
    sx0, sx1 = m["span"]
    z = r["z_in"]
    p.pos = [m["ledges"][0][0] + 2.5, fy, z + 0.5]
    w.passes(1)
    assert w.get(p.name, "dg.ck") == 0 and (w.get(H, "dg.rs") in (None, -1))
    p.pos = [sx0 + 0.5, fy, z + 0.5]
    w.passes(1)
    assert w.get(H, "dg.rs") == 1, "stepping onto the span arms the countdown (and the same pass advances it)"
    before = len(w.block_writes)
    seen_air = []
    for t in range(2, 2 + m["lead"] + m["warn"] + 2):
        n0 = len(w.block_writes)
        w.passes(1)
        for _d, c in w.block_writes[n0:]:
            if c.startswith("fill") and c.endswith("minecraft:air"):
                seen_air.append((t, int(c.split()[1])))
    assert seen_air and seen_air[0][1] == sx0 and seen_air[0][0] == m["lead"] + m["warn"], seen_air
    # the member stands still: they fall; the catch floor teleports them to the west ledge and the span is restored
    clock = w.get(p.name, "dg.clock")
    p.pos = [sx0 + 1.5, r["y_lo"], z + 0.5]
    n0 = len(w.block_writes)
    w.passes(1)
    pen = doc["engine"]["clock"]["fall_penalty_s"] * 80
    assert w.get(p.name, "dg.clock") == clock - 80 - pen, "one pass of the clock and the fall's penalty"
    assert int(p.pos[0]) == m["ledges"][0][0] + 2 and int(p.pos[1]) == fy, p.pos
    assert w.get(H, "dg.rs") == -1
    assert any(c.startswith("fill") and c.endswith("minecraft:deepslate_tiles") for _d, c in w.block_writes[n0:])
    # run it clean: walk at sprint pace, never fall, and on the far ledge the span comes back
    p.pos = [sx0 + 0.5, fy, z + 0.5]
    w.passes(1)
    x = sx0 + 0.5
    for _ in range(40):
        x += 5.6
        if x >= m["ledges"][1][0]:
            break
        p.pos = [x, fy, z + 0.5]
        w.passes(1)
        assert p.pos[1] == fy, "never teleported while ahead of the front"
    p.pos = [m["ledges"][1][0] + 2.5, fy, r["z_out"] + 0.5]
    n0 = len(w.block_writes)
    w.passes(1)
    assert w.get(H, "dg.rs") == -1 and w.get(p.name, "dg.ck") == 1
    assert any(c.startswith("fill") and "deepslate_tiles" in c for _d, c in w.block_writes[n0:])


# ================================================================================================= flood


def flood_states(doc):
    b = built(doc)
    lines = room_lines(doc, b, "tick")
    H = b.meta["holder"]
    ev = collapse_events(lines, H)
    g = copy.deepcopy(b.grid)
    out = [(0, copy.deepcopy(g))]
    for h in range(1, b.meta["end"] + 1):
        for ln in ev.get(h, []):
            g.apply(parse_op(ln))
        out.append((h, copy.deepcopy(g)))
    return b, ev, out


def water_cells(g, r):
    wid = g.idx.get("minecraft:water")
    if wid is None:
        return np.zeros((0, 3), dtype=int)
    return np.argwhere(g.a == wid)


def test_flood_never_reaches_a_ledge_a_door_or_leaks_and_every_water_column_opens_to_air():
    doc = case("flood")
    b, ev, states = flood_states(doc)
    r = b.room
    fy, y_lo = r["floor_in"], r["y_lo"]
    x0, y0, z0 = b.grid.box[:3]
    top_seen = 0
    for h, g in states:
        wc = water_cells(g, r)
        if not len(wc):
            continue
        xs, ys, zs = wc[:, 0] + x0, wc[:, 1] + y0, wc[:, 2] + z0
        assert ys.max() <= fy - 2, (h, "water above the ledges' top blocks")
        assert xs.min() >= r["ix0"] and xs.max() <= r["ix1"] and zs.min() >= r["iz0"] and zs.max() <= r["iz1"], "water outside the hall"
        top_seen = max(top_seen, int(ys.max()))
        cls = g.cls()
        for (x, y, z) in set(zip(xs.tolist(), ys.tolist(), zs.tolist())):
            col = [cls[x - x0, yy - y0, z - z0] for yy in range(y + 1, r["ceil_y"])]
            assert G.SOLID not in col, (h, x, y, z, "a swimmer under a solid roof: no way to the air")
        # the doors, the ledge tops and the exit cell stay dry
        for key in ("door_in", "door_out"):
            bx = r[key]
            for xx in range(bx[0], bx[3] + 1):
                for yy in range(bx[1], bx[4] + 1):
                    for zz in range(bx[2], bx[5] + 1):
                        if g.inside(xx, yy, zz):
                            assert g.block_at(xx, yy, zz) != "minecraft:water", (h, key)
    assert top_seen == fy - 2 == b.meta["water_top"], "the hall fills to one under the ledge top block, no further"


def test_flood_in_every_state_the_exit_is_walkable_to_and_from_the_entry_and_every_standable_cell_reaches_a_ledge():
    doc = case("flood")
    b, ev, states = flood_states(doc)
    r = b.room
    fy = r["floor_in"]
    for h, g in states:
        cls = g.cls()
        a, z = start_cell(g, r), end_cell(g, r)
        fwd = G.walk(g, [a], jumps=False, cls=cls)
        assert z in fwd and a in G.walk(g, [z], jumps=False, cls=cls), (h, "entry to exit and back")
        st, _p = G.standable(cls)
        x0, y0, z0 = g.box[:3]
        ledge_cells = {c for c in fwd if c[1] + y0 >= fy and (c[0] + x0 <= r["ix0"] + 5 or c[0] + x0 >= r["ix1"] - 5)}
        for (lx, ly, lz) in zip(*st.nonzero()):
            x, y, zz = int(lx) + x0, int(ly) + y0, int(lz) + z0
            if r["ix0"] <= x <= r["ix1"] and r["iz0"] <= zz <= r["iz1"] and y >= r["y_lo"]:
                assert (int(lx), int(ly), int(lz)) in fwd, (h, x, y, zz, "a standable cell the walk never reaches (a hole in the hall)")
    drain = room_lines(doc, b, "drain")
    g = replay(b, drain, copy.deepcopy(states[-1][1]))
    assert (g.a == b.grid.a).all(), "the drain empties the hall exactly"
    reset = room_lines(doc, b, "reset")
    g = replay(b, reset, copy.deepcopy(states[-1][1]))
    assert (g.a == b.grid.a).all()


def test_mutating_the_generator_to_flood_one_layer_too_high_makes_the_ledge_check_fail(monkeypatch):
    monkeypatch.setattr(S, "TOP_BELOW_LEDGE", 0)
    R._BUILT.clear()
    doc = case("flood")
    b, ev, states = flood_states(doc)
    fy = b.room["floor_in"]
    x0, y0, z0 = b.grid.box[:3]
    top = max(int(water_cells(g, b.room)[:, 1].max()) + y0 for _h, g in states if len(water_cells(g, b.room)))
    assert top > fy - 2, "the mutated water reaches the ledge level: the check above would fail"


@pytest.fixture(scope="module")
def flood_pack(tmp_path_factory):
    doc = case("flood")
    out = tmp_path_factory.mktemp("cobblers_setpiece_flood")
    D.write(D.build(doc), out)
    return doc, out


def test_flood_drains_and_sweeps_by_the_generated_rules(flood_pack):
    doc, w = TR.rooms_world(flood_pack)
    p, s = TR.enter_run(doc, w)
    b = built(doc, slot=s)
    r, m = b.room, b.meta
    H, fy, y_lo = m["holder"], r["floor_in"], r["y_lo"]
    p.pos = [r["ix0"] + 2.5, fy, r["z_in"] + 0.5]
    w.passes(1)
    assert w.get(p.name, "dg.ck") == 0 and w.get(H, "dg.rs") == -1
    p.pos = [(r["ix0"] + r["ix1"]) / 2, y_lo, (r["iz0"] + r["iz1"]) / 2]       # the basin floor: arms the water
    w.passes(1)
    assert w.get(H, "dg.rs") == 1
    assert any(e[0] == "minecraft:water_breathing" for e in p.effects) and any(e[0] == "minecraft:resistance" for e in p.effects)
    for _ in range(m["end"] + 2):
        w.passes(1)
        if int(p.pos[1]) != y_lo:
            break
    waters = [int(c.split()[2]) for _d, c in w.block_writes if c.endswith("minecraft:water replace minecraft:air")]
    ys = sorted(set(waters))
    assert ys == list(range(y_lo, y_lo + int(len(ys)))) and ys[0] == y_lo and len(ys) >= m["deep"], ys
    # swept: standing on the floor with `deep` layers over their feet -> back to the ledge, hall drained, clock charged
    assert p.pos[1] == fy and int(p.pos[0]) == r["ix0"] + 2, p.pos
    assert w.get(H, "dg.rs") == -1
    drained = [c for _d, c in w.block_writes if c.endswith("minecraft:air replace minecraft:water")]
    assert len(drained) >= m["layers"]


# ================================================================================================= lights out


def light_levels(g, r, extra_sources=()):
    """Block light by the vanilla rule at the precision the check needs: a source emits its level, every non-opaque cell
    passes on one less; SOLID blocks stop light (a luminous block lights its neighbours at level - 1). Sources: the
    hull's light blocks and the guides."""
    cls = g.cls()
    opaque = cls == G.SOLID
    lvl = np.zeros(g.shape, dtype=np.int8)
    src = {"minecraft:verdant_froglight": 15, "minecraft:sea_lantern": 15, "minecraft:shroomlight": 15, "minecraft:lantern": 15,
           "minecraft:light": 4}
    dq = collections.deque()
    for name, i in g.idx.items():
        base = G.base(name)
        if base in src:
            level = src[base]
            if base == "minecraft:light":
                m = re.search(r"level=(\d+)", name)
                level = int(m.group(1)) if m else 15
            for c in np.argwhere(g.a == i):
                c = tuple(int(v) for v in c)
                lvl[c] = max(lvl[c], level)
                dq.append(c)
    while dq:
        c = dq.popleft()
        v = lvl[c]
        if v <= 1:
            continue
        for d in ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1)):
            n = (c[0] + d[0], c[1] + d[1], c[2] + d[2])
            if not (0 <= n[0] < g.shape[0] and 0 <= n[1] < g.shape[1] and 0 <= n[2] < g.shape[2]) or opaque[n]:
                continue
            if lvl[n] < v - 1:
                lvl[n] = v - 1
                dq.append(n)
    return lvl


def test_lights_out_puts_the_lights_out_and_changes_nothing_a_player_stands_on():
    doc = case("lights_out")
    b = built(doc)
    r, m = b.room, b.meta
    g0 = b.grid
    cls0 = g0.cls()
    st0, _p = G.standable(cls0)
    x0, y0, z0 = g0.box[:3]
    ys = [int(i[1]) + y0 for i in np.argwhere(st0) if r["ix0"] <= int(i[0]) + x0 <= r["ix1"] and r["iz0"] <= int(i[2]) + z0 <= r["iz1"]]
    assert m["sheet_y"] - max(ys) >= 4, "the sheet is at least 4 over every standable cell (a jump's head room)"
    lit0 = light_levels(g0, r)
    zones = m["zones"]
    # close every zone but the last, in order, replaying the generated close functions
    g = copy.deepcopy(g0)
    for k in range(len(zones) - 1):
        lines = room_lines(doc, b, "close%d" % k)
        fills = [ln for ln in lines if ln.startswith("fill ")]
        assert len(fills) == 1
        op = parse_op(fills[0])
        assert op[1][1] == op[1][4] == m["sheet_y"] and op[3] == "replace minecraft:air" and G.classify(op[2]) == G.SOLID
        replay(b, fills, g)
    cls = g.cls()
    assert (np.array(cls == G.SOLID) & ~np.array(cls0 == G.SOLID)).sum() > 0
    changed = (cls != cls0)
    ys_changed = np.argwhere(changed)[:, 1] + y0
    assert (ys_changed == m["sheet_y"]).all(), "only the sheet's layer changed"
    st, _p = G.standable(cls)
    low = m["sheet_y"] - y0
    assert (st[:, :low, :] == st0[:, :low, :]).all(), "below the sheet the standable cells are the same in every state"
    reach0 = G.walk(g0, [start_cell(g0, r)], jumps=False, cls=cls0)
    reach = G.walk(g, [start_cell(g, r)], jumps=False, cls=cls)
    assert reach == reach0 and end_cell(g, r) in reach
    # the light really goes out: inside the closed zones (away from the open last zone) every cell is at most the guides' 4
    lit = light_levels(g, r)
    a_end = zones[-2][1]
    cells = [(int(i[0]), int(i[1]), int(i[2])) for i in np.argwhere(st0)]
    dark = [c for c in cells if r["ix0"] <= c[0] + x0 <= zones[-2][1] - 16]
    assert dark and all(lit[c] <= 4 for c in dark), "closed zones are dark but for the guides"
    assert sum(1 for c in dark if lit[c] == 0) > len(dark) * 0.5, "and most of it is black"
    assert sum(1 for c in cells if lit0[c] >= 1) > len(cells) * 0.9, "before: the room is lit (a trunk's shadow aside)"
    # the guides keep a path: every closed-zone cell on the trail line is at least 1 (findable)
    guide_ok = all(lit[(x - x0, y - 1 - y0, zz - z0)] >= 3 for (x, y, zz) in m["guides"] if x <= zones[-2][1] - 16)
    assert guide_ok


def test_lights_out_reset_reopens_every_zone_and_the_kind_changes_no_other_block():
    doc = case("lights_out")
    b = built(doc)
    g = copy.deepcopy(b.grid)
    for k in range(len(b.meta["zones"]) - 1):
        replay(b, [ln for ln in room_lines(doc, b, "close%d" % k) if ln.startswith("fill ")], g)
    assert not (g.a == b.grid.a).all()
    reset = room_lines(doc, b, "reset")
    replay(b, reset, g)
    assert (g.a == b.grid.a).all()


def test_mutating_the_generator_to_lay_the_sheet_under_the_player_makes_the_check_fail(monkeypatch):
    orig = S.lights_out

    def low(doc, d, slot, room, theme):
        room = dict(room, ceil_y=room["floor_in"] + 4)      # the sheet at ceil - 3 = 1 over the floor
        return orig(doc, d, slot, room, theme)
    monkeypatch.setitem(R.KINDS, "setpiece", lambda doc, d, slot, room, theme: low(doc, d, slot, room, theme) if room["params"]["piece"] == "lights_out" else S.kind_setpiece(doc, d, slot, room, theme))
    R._BUILT.clear()
    doc = case("lights_out")
    b = built(doc)
    fills = [ln for ln in room_lines(doc, b, "close0") if ln.startswith("fill ")]
    assert parse_op(fills[0])[1][1] - b.room["floor_in"] < 4, "the mutated sheet is within a jump of the floor: the 4-over check would fail"


@pytest.fixture(scope="module")
def lights_pack(tmp_path_factory):
    doc = case("lights_out")
    out = tmp_path_factory.mktemp("cobblers_setpiece_lights")
    D.write(D.build(doc), out)
    return doc, out


def test_lights_out_runtime_closes_a_zone_lag_blocks_behind_the_member_once(lights_pack):
    doc, w = TR.rooms_world(lights_pack)
    p, s = TR.enter_run(doc, w)
    b = built(doc, slot=s)
    r, m = b.room, b.meta
    fy = r["floor_in"]
    z0 = m["zones"][0]
    p.pos = [r["ix0"] + 3.5, fy, r["z_in"] + 0.5]
    w.passes(1)
    n0 = len(w.block_writes)
    p.pos = [z0[1] + m["lag"] - 2 + 0.5, fy, r["z_in"] + 0.5]
    w.passes(1)
    assert not [c for _d, c in w.block_writes[n0:] if "replace minecraft:air" in c], "not yet: the zone is less than lag behind"
    p.pos = [z0[1] + m["lag"] + 0.5, fy, r["z_in"] + 0.5]
    n0 = len(w.block_writes)
    w.passes(1)
    sheet = [c for _d, c in w.block_writes[n0:] if "replace minecraft:air" in c]
    assert len(sheet) == 1 and sheet[0].split()[2] == str(m["sheet_y"])
    n0 = len(w.block_writes)
    w.passes(2)
    assert not [c for _d, c in w.block_writes[n0:] if "replace minecraft:air" in c], "a zone closes once"
    # a member under a closed zone is given the vanilla darkness effect, nothing else
    p.pos = [z0[0] + 5.5, fy, r["z_in"] + 0.5]
    w.passes(1)
    assert any(e[0] == "minecraft:darkness" for e in p.effects)
    assert not any(e[0] in ("minecraft:slowness", "minecraft:blindness", "minecraft:wither", "minecraft:poison") for e in p.effects)
