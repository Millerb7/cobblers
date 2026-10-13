"""The Kyogre cave's builder tests (tools/kyogre_cave.py, data/kyogre_cave.json).

Written by the builder, as the builder's own checks: the INDEPENDENT audit (tools/kyogre_cave_audit.py,
docs/world-building/KYOGRE_CAVE.md section 7) is another agent's and must not import the builder. Model tests need no
heightmap; the pack tests build into tmp_path and skip, with the reason, when the canonical heightmap is unavailable.
"""
from __future__ import annotations

import copy
import json
import re
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import kyogre_cave as K  # noqa: E402


def _j(p):
    return json.loads((ROOT / p).read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def doc():
    return K.load()


@pytest.fixture(scope="module")
def models(doc):
    M = K.build_model(doc)
    return M, K.open_model(doc, M)


@pytest.fixture(scope="module")
def built(doc, tmp_path_factory):
    try:
        import ground as G
        g = G.Ground()
        p = K.plan(doc, g)
    except (FileNotFoundError, OSError) as e:      # no canonical heightmap in this checkout
        pytest.skip("the heightmap is unavailable: %s" % e)
    out = tmp_path_factory.mktemp("kc") / K.PACK
    res = K.build(doc, p, out)
    return {"plan": p, "out": out, "build": Path(res["build_pack"]), "steps": res["steps"]}


def _fn(pack, name):
    return (pack / "data" / "cobblers" / "function" / "kyogre_cave" / (name + ".mcfunction")).read_text(encoding="utf-8")


def _commands(text):
    return [ln for ln in text.splitlines() if ln.strip() and not ln.startswith("#")]


# Without it the cave could sit in a dungeon's slot rows or the portals' rescue box, and another keeper's sweep would
# throw a player out of the cave mid-dive (KC5). The boxes are recomputed here from each owner's file.
def test_the_cave_reserve_meets_no_other_pocket_user(doc):
    rv = doc["pocket"]["reserve"]
    pp = _j("data/portals.json")["pocket"]
    rescue_z = (min(pp["bands"].values()) - pp["rescue_margin"], max(pp["bands"].values()) + pp["rescue_margin"])
    assert rv[3] < rescue_z[0] or rv[1] > rescue_z[1]
    pr = _j("data/dungeon_probes.json")["row"]
    assert rv[3] < pr["z_min"] or rv[1] > pr["z_max"]
    ep = _j("data/entei_boss.json")
    half = ep["room"]["half"]
    ex = [ep["pocket"]["origin"][0] + k * ep["pocket"]["spacing"] for k in range(ep["pocket"]["slots"])]
    entei = (min(ex) - half - 64, ep["pocket"]["origin"][1] - half - 64, max(ex) + half + 64, ep["pocket"]["origin"][1] + half + 64)
    assert not K._meets(tuple(rv), entei)
    dg = _j("data/dungeons.json")
    s = dg["engine"]["slots"]
    rows = len(dg["dungeons"]) * s["per_dungeon"]
    strips = (s["origin_x"], s["rows_from_z"], s["origin_x"] + s["strip_length"] - 1,
              s["rows_from_z"] + (rows - 1) * s["row_spacing"] + s["strip_width_max"] - 1)
    assert not K._meets(tuple(rv), strips)
    lo, hi = ep["pocket"]["border"]
    m = ep["pocket"]["border_margin"]
    assert lo + m <= rv[0] and lo + m <= rv[1] and rv[2] <= hi - m and rv[3] <= hi - m
    assert K.static_problems(doc) == []


# Without it a move of the reserve into the dungeon rows (the design's own (0, 2048)) would pass silently.
def test_a_reserve_in_the_dungeon_rows_is_refused(doc):
    d = copy.deepcopy(doc)
    d["pocket"]["reserve"] = [0, 2048, 300, 2350]
    assert any("dungeon" in p for p in K.static_problems(d))


# Without it the cave's blocks drift out of the model's box or a world write misses it.
def test_every_carved_cell_is_inside_the_reserve(doc, models):
    M, _O = models
    I, _J, Kk = np.nonzero(M.inside)
    rv = doc["pocket"]["reserve"]
    assert I.min() + M.o[0] >= rv[0] and I.max() + M.o[0] <= rv[2]
    assert Kk.min() + M.o[2] >= rv[1] and Kk.max() + M.o[2] <= rv[3]
    # and outside the overworld map, so no waystone or checkpoint coordinate can coincide with one
    assert I.min() + M.o[0] > _j("data/world.json")["bounds"]["max_x"]


# Without it a source would sit beside air and flow: a drained Tide Gate refilling from a neighbour, a gallery
# emptying into the hub. Only the Race's declared sources may (its current).
def test_water_never_stands_beside_or_over_air_in_either_state(doc, models):
    M, O = models
    assert K.stability_problems(doc, M, "built") == []
    assert K.stability_problems(doc, O, "solved") == []


def test_a_hole_beside_water_is_caught(doc, models):
    M, _O = models
    B = M.copy()
    tg = doc["rooms"]["tide_gate"]["box"]
    B.st[B.sl((tg[3] + 1, tg[1] + 3, tg[2] + 3, tg[3] + 1, tg[1] + 3, tg[2] + 3))] = K.AIR
    assert K.stability_problems(doc, B, "mutated")


# Without it a carved cell could open onto the void of the pocket dimension.
def test_every_carved_cell_has_the_shell_margin(doc, models):
    M, _O = models
    assert K.seal_problems(doc, M) == []


# KC2. Without it a flooded passage under a low roof would be vanilla air for a Dive player: the ladder counts depth only
# with deep_blocks of water above the eyes (tools/blackout_pack.py water/tick).
def test_every_flooded_passage_holds_the_ladders_depth(doc, models):
    M, _O = models
    deep = _j("data/blackout.json")["water"]["deep_blocks"]
    for g in doc["rooms"]["galleries"]:
        # walk the path's middle line: the water column is at least deep + 2 cells everywhere along it
        for a, b in zip(g["path"], g["path"][1:]):
            for t in np.linspace(0, 1, 9):
                x, z = int(round(a[0] + t * (b[0] - a[0]))), int(round(a[1] + t * (b[1] - a[1])))
                col = [M.at(x, y, z)[0] for y in range(g["water_y"][0], g["water_y"][1] + 1)]
                assert col.count(K.WATER) >= deep + 2, (g["id"], x, z)
    for bx in doc["rooms"]["ubend"]["boxes"]:
        assert bx[4] - bx[1] + 1 >= deep + 2
    assert K.depth_problems(doc, M) == []


# Without it the Tide Gate is not a gate (the Trench reachable unsolved), the Basin cannot be reached solved, or a
# player can reach a cell with no way back to a return click (REVIEW 87).
def test_reachability_in_both_states(doc, models):
    M, O = models
    assert K.reach_problems(doc, M, O) == []


def test_a_cave_without_the_basins_return_strands_the_trench(doc, models):
    d = copy.deepcopy(doc)
    d["arches"]["list"] = [a for a in d["arches"]["list"] if a["id"] != "f"] + [d["arches"]["list"][0]]
    M, O = models
    assert any("reach no return click" in p for p in K.reach_problems(d, M, O))


# KC3. Without it a player who falls into the Trench's water would have to swim further than fatigue allows.
def test_every_surface_swim_ends_before_fatigue_warns(doc, models):
    _M, O = models
    s = _j("data/blackout.json")["surface"]
    limit = s["warn_ticks"] / s["gain_deep_per_tick"] / 20.0 * 5.0
    st = O.st
    surf = (st == K.WATER)
    surf[:, :-1, :] &= st[:, 1:, :] == K.AIR
    surf[:, -1, :] = False
    # an exit: a surface cell beside a column a player can stand on at the water's level or one above
    stand = (st == K.SOLID)[:, :-2, :] & (st[:, 1:-1, :] == K.AIR) & (st[:, 2:, :] == K.AIR)
    exits = np.zeros_like(surf)
    for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        for dy in (0, 1):
            sh = np.zeros_like(surf)
            src = stand[max(0, dx):stand.shape[0] + min(0, dx), :, max(0, dz):stand.shape[2] + min(0, dz)]
            if dy == 0:
                sh[max(0, -dx):sh.shape[0] + min(0, -dx), 1:-1, max(0, -dz):sh.shape[2] + min(0, -dz)] = src
            else:
                sh[max(0, -dx):sh.shape[0] + min(0, -dx), :-2, max(0, -dz):sh.shape[2] + min(0, -dz)] = src
            exits |= surf & sh
    cells = set(zip(*np.nonzero(surf)))
    frontier = list(zip(*np.nonzero(exits)))
    dist = {c: 0 for c in frontier}
    while frontier:
        nxt = []
        for i, j, k in frontier:
            for di, dk in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                n = (i + di, j, k + dk)
                if n in cells and n not in dist:
                    dist[n] = dist[(i, j, k)] + 1
                    nxt.append(n)
        frontier = nxt
    far = [c for c in cells if dist.get(c, 10 ** 6) > limit]
    assert not far, (len(far), [(i + O.o[0], j + O.o[1], k + O.o[2]) for i, j, k in far[:3]])


# Without it a click entity or a set piece would be summoned inside rock.
def test_clicks_and_set_pieces_stand_in_open_cells(doc, models):
    M, _O = models
    assert K.placement_cells(doc, M) == []


# Without it the cage could be barrier in water (a visible hole) or miss the dais.
def test_the_cage_is_barrier_over_the_dais(doc, models):
    M, O = models
    cg = doc["kyogre"]["cage"]
    assert (M.st[M.sl(cg)] == K.SOLID).all()
    assert {M.palette[i] for i in np.unique(M.bk[M.sl(cg)])} == {K.BARRIER}
    d = doc["rooms"]["basin"]["dais"]
    assert cg[1] == d[4] + 1
    assert (O.st[O.sl(cg)] == K.AIR).all()


# Without it the level could leave the gate's bound and Kyogre would break free from every ball at eight badges.
def test_the_kyogre_level_is_the_eight_badge_bound(doc):
    caps = _j("data/legendaries.json")
    text = json.dumps(caps)
    m = re.search(r'"8": (\d+), "champion"', text)
    assert m and doc["kyogre"]["level"] <= int(m.group(1))
    assert doc["gate"]["flags"] == ["gym8_cleared"]


# Without it the probes in data/world_probes.json would check blocks the build no longer writes.
def test_world_probes_match_the_model(doc, built):
    p = built["plan"]
    want = K.probe_records(doc, p["M"], p["arch"], p["reef"])
    assert _j("data/world_probes.json")["places"]["kyogre_cave"] == want


# KC4. Without it the arch would not reach the cave, or the crossing would let in a player without the dive tag,
# gym8_cleared or the attunement.
def test_the_arch_hands_a_diver_to_the_cave_and_the_crossing_carries_the_gate(doc, built):
    import coldwater_station as C
    cw = C.load()
    fns, _adv = C.arch_functions(cw, {"blocks": [], "click": (0, 60, 0), "pdoc": _j("data/portals.json")})
    dive = _j("data/portals.json")["gates"]["dive"]["tag"]
    touch = _commands("\n".join(fns["portal/touch"]))
    refuse = [i for i, c in enumerate(touch) if "unless entity @s[tag=%s] run return" % dive in c]
    call = [i for i, c in enumerate(touch) if c == "function %s" % cw["portal"]["hook"]["destination_function"]]
    assert refuse and call and refuse[0] < call[0]
    assert _commands("\n".join(fns["portal/destination"])) == ["function %s" % cw["portal"]["hook"]["cave_function"]]
    enter = _commands(_fn(built["out"], "enter"))
    tps = [c for c in enter if " tp @s " in c]
    assert len(tps) == 1
    for need in ("tag=%s" % dive, "cobblers:flag/gym8_cleared=true", "%s=true" % doc["gate"]["advancement"], "in cobblers:pocket"):
        assert need in tps[0], need


# Without it a player who has caught Kyogre could wake another, or the catcher's pedestal would give the orb uncaught.
def test_the_wake_and_the_pedestal_carry_the_catch(doc, built):
    ky = doc["kyogre"]["caught_advancement"]
    shrine = _commands(_fn(built["out"], "click/shrine"))
    call = [c for c in shrine if c.endswith("kyogre_cave/ky/wake")]
    assert call and "%s=false" % ky in call[0]
    assert "%s=true" % ky in _commands(_fn(built["out"], "ky/wake"))[0]
    ped = _fn(built["out"], "click/pedestal_catchers")
    assert "unless entity @s[advancements={%s=true}] run return" % ky in ped


# The Rayquaza gate reads cobblers:legendary/kyogre/met (the orchestrator, 2026-10-13): without it a player who met
# Kyogre could never open the sky arch. Granted on meeting in the Basin, on waking and on a catch.
def test_meeting_waking_and_catching_grant_the_met_advancement(doc, built):
    met = "advancement grant @s only cobblers:legendary/kyogre/met"
    for name in ("ky/met", "ky/wake", "ky/caught"):
        assert met in _fn(built["out"], name), name
    assert "function cobblers:kyogre_cave/ky/met" in _fn(built["out"], "ky/pass")
    assert (built["out"] / "data/cobblers/advancement/legendary/kyogre/met.json").is_file()


# KC1. Without it a loss to Kyogre would hand the player's items to a guardian the keeper then moves or kills.
def test_kyogre_is_bound_with_the_blackouts_exempt_tag(doc, built):
    exempt = _j("data/blackout.json")["claims"]["exempt_tag"]
    assert "tag @s add %s" % exempt in _commands(_fn(built["out"], "ky/bind"))
    for f in (built["out"] / "data/cobblers/function/kyogre_cave/sp_bind").glob("*.mcfunction"):
        assert exempt not in f.read_text(encoding="utf-8")


def test_no_kill_in_the_pack_can_reach_a_guardian_or_a_set_piece(built):
    for f in (built["out"] / "data").rglob("*.mcfunction"):
        for c in _commands(f.read_text(encoding="utf-8")):
            if re.search(r"\bkill @e\[type=cobblemon:pokemon", c):
                assert "tag=!cobblers.guardian" in c and "cobblers.kc.kyogre" in c, (f.name, c)
                assert "cobblers.kc.sp" not in c


# Without it the puzzles could reset around a player (REVIEW 87): the reset is reached only from `empty`, which runs
# only when no player is in the cave's box.
def test_the_reset_runs_only_when_the_cave_is_empty(built):
    out = built["out"]
    callers = [f.name for f in (out / "data").rglob("*.mcfunction") if "kyogre_cave/reset\n" in f.read_text(encoding="utf-8")
               or re.search(r"function cobblers:kyogre_cave/reset$", f.read_text(encoding="utf-8"), re.M)]
    assert callers == ["empty.mcfunction"]
    tick = _commands(_fn(out, "tick"))
    assert any(c.startswith("execute unless entity @a[tag=cobblers.kc.here] run return run function cobblers:kyogre_cave/empty")
               for c in tick)
    writes = _commands(_fn(out, "reset_writes"))
    order = [i for i, c in enumerate(writes) if "minecraft:glass replace minecraft:air" in c]
    flood = [i for i, c in enumerate(writes) if "minecraft:water replace minecraft:air" in c]
    assert order and flood and max(order) < min(flood)


# Without it the cage could close on a player.
def test_the_cage_closes_only_with_nobody_beside_it(doc, built):
    p = _commands(_fn(built["out"], "ky/pass"))
    close = [c for c in p if c.endswith("kyogre_cave/ky/close")]
    cg = doc["kyogre"]["cage"]
    sel = "@a[x=%d,y=%d,z=%d,dx=%d,dy=%d,dz=%d]" % (cg[0] - 1, cg[1] - 1, cg[2] - 1, cg[3] - cg[0] + 2, cg[4] - cg[1] + 2, cg[5] - cg[2] + 2)
    assert close and ("unless entity %s" % sel) in close[0]


# The memory rule (2026-10-12): the geometry is a build pack `reapply.py strip` can remove; the runtime stays small.
def test_the_geometry_is_a_build_pack_and_the_runtime_is_small(built):
    import pack_roles as PR
    rep = PR.classify([(K.PACK, built["out"]), (built["build"].name, built["build"])], None, config_dirs=())
    assert rep["packs"][built["build"].name]["role"] == "build"
    assert rep["packs"][K.PACK]["role"] == "runtime"
    assert rep["packs"][K.PACK]["lines"] < 1000
    assert not list((built["out"] / "data/cobblers/function/kyogre_cave/build").glob("*")) if \
        (built["out"] / "data/cobblers/function/kyogre_cave/build").exists() else True


# Without it the server would refuse a fill or write into an unloaded chunk and say nothing.
def test_every_function_passes_function_limits(built):
    import function_limits as FL
    for pack in (built["out"], built["build"]):
        for f in pack.rglob("*.mcfunction"):
            assert FL.check_file(f) == [], f.name


# Without it a re-apply would run the water before the solids round it, or skip the build state.
def test_the_step_runs_solids_then_air_then_water_then_the_state(built):
    fns = [v for k, v in built["steps"] if k == "fn"]
    parts = [f for f in fns if "/build/p_" in f]
    phases = []
    for f in parts:
        body = _fn(built["build"], f.split("kyogre_cave/")[1].replace("/p_", "/b_"))
        phases.append(re.search(r"\((solid|air|water)\)", body).group(1))
    assert phases == sorted(phases, key=["solid", "air", "water"].index)
    assert fns[-1].endswith("/build/state")


# Without it the reef could cover the arch, its click, or the approach, or rise to the lintel.
def test_the_reef_stays_off_the_arch_and_below_the_lintel(doc, built):
    import portals as P
    a = built["plan"]["arch"]
    reef = built["plan"]["reef"]
    cols = {(x, z) for x, _y, z, _b in reef}
    assert not cols & set(map(tuple, a["columns"]))
    assert (a["click"][0], a["click"][2]) not in cols and (a["stand"][0], a["stand"][2]) not in cols
    assert max(y for _x, y, _z, _b in reef) < a["apron_y"] + P.ARCH_HEIGHT
    spawn = set(_j("data/spawn_blocks.json")["blocks"])
    assert not {b for *_xyz, b in reef} & spawn
