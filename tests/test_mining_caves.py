"""The builder's own checks of tools/mining_caves.py (ECONOMY_OVERHAUL.md U3). Not the independent audit: that is
test-author's, and these share the generator's derivation. Every case runs on a synthetic flat ground, so none needs
the heightmap, a built pack or derived/."""
from __future__ import annotations

import copy
import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import mining_caves as MC  # noqa: E402
import mines as M  # noqa: E402

SPEC = MC.load()
FLAT = 140


def flat(_x, _z):
    return FLAT


def _plan(spec=None):
    """A plan for every cave of the real data, each moved to its own synthetic mouth on flat ground."""
    spec = copy.deepcopy(spec or SPEC)
    plan = []
    for i, cave in enumerate(spec["caves"]):
        cave["entry"] = {"anchor": [1000 + 400 * i, 1000], "front": ("north", "east")[i % 2]}
        gm = MC.geometry(spec, cave, flat)
        gals = [dict(g, variants=[MC.ore_cells(spec, cave, g, k, gm) for k in range(spec["restore"]["variants"])])
                for g in gm["galleries"]]
        plan.append({"cave": cave, "geometry": gm, "galleries": gals, "approach": [0, 0, 0, 1, 1, 1]})
    return spec, plan


def test_the_yields_hold_the_designs_means_exactly():
    assert MC.yield_problems(SPEC) == []
    nv = SPEC["restore"]["variants"]
    for name, yl in SPEC["yields"].items():
        for ore, y in yl["ores"].items():
            assert len(y["per_variant"]) == nv and sum(y["per_variant"]) == y["mean"] * nv, (name, ore)
    deep = SPEC["yields"]["deep"]["ores"]["minecraft:deepslate_diamond_ore"]["per_variant"]
    assert sum(1 for v in deep if v) == 3 and max(deep) == 1, "1 diamond in 3 of 8 variants"


def test_the_period_is_twenty_minutes_and_meets_the_floor():
    assert SPEC["restore"]["period_ticks"] == 20 * 60 * 20 >= 24000


def test_each_variant_places_exactly_the_datas_counts_inside_the_body():
    spec, plan = _plan()
    for e in plan:
        yl = MC.yields(spec, e["cave"])
        for g in e["galleries"]:
            body = {c[:3]: c[3] for c in g["body"]}
            for k, v in enumerate(g["variants"]):
                cells = [c for c, _o in v]
                assert len(cells) == len(set(cells)), (g["gallery"]["id"], k)
                assert all(c in body for c in cells)
                for ore, y in yl["ores"].items():
                    assert sum(1 for _c, o in v if o == ore) == y["per_variant"][k], (g["gallery"]["id"], k, ore)
                for c, o in v:
                    if o in (yl.get("hidden_only") or []):
                        assert body[c] >= 2, (g["gallery"]["id"], k, o, c)
                face = [c for c, _o in v if body[c] == 0]
                assert len(face) >= yl["visible_min"], (g["gallery"]["id"], k)


def test_the_build_is_deterministic():
    _s, a = _plan()
    _s, b = _plan()
    assert [MC.build_lines(SPEC, e) for e in a] == [MC.build_lines(SPEC, e) for e in b]
    assert MC.driver_files(SPEC, a) == MC.driver_files(SPEC, b)


def test_bodies_and_shells_never_overlap_the_hall_or_each_other():
    _s, plan = _plan()
    for e in plan:
        assert e["geometry"]["problems"] == [], e["geometry"]["problems"][:3]
        seen = set()
        for g in e["galleries"]:
            box = set(c[:3] for c in g["body"]) | set(g["shell"])
            assert not box & seen
            seen |= box
            for c in box:
                assert e["geometry"]["cells"][c] in ("body", "shell")


def test_every_check_function_carries_the_occupancy_guard_before_it_restores():
    spec, plan = _plan()
    fn = MC.driver_files(spec, plan)
    for e in plan:
        for g in e["galleries"]:
            gid = g["gallery"]["id"]
            body = fn["galleries/check_%s" % gid]
            cmds = [l for l in body if not l.startswith("#")]
            assert cmds[-1] == "function cobblers:mining_caves/galleries/restore_%s" % gid
            gx0, gy0, gz0, gx1, gy1, gz1 = g["guard"]
            vol = "x=%d,y=%d,z=%d,dx=%d,dy=%d,dz=%d" % (gx0, gy0, gz0, gx1 - gx0, gy1 - gy0, gz1 - gz0)
            assert "execute if entity @a[%s] run return 0" % vol in cmds
            assert "execute if entity @e[type=cobblemon:pokemon,%s] run return 0" % vol in cmds
            assert sum(1 for l in cmds if l.startswith("execute unless loaded ")) == 4
            assert any(l.startswith("execute if score #d mcv.t < #period mcv.t run return 0") for l in cmds)
            # the guard box holds the gallery's whole formation, grown by one
            xs = [c[0] for c in g["body"]] + [c[0] for c in g["shell"]]
            assert gx0 == min(xs) - 1 and gx1 == max(xs) + 1


def test_the_restore_fills_only_over_the_tag_and_sets_ore_only_into_its_own_rock():
    spec, plan = _plan()
    fn = MC.driver_files(spec, plan)
    for e in plan:
        hb = MC.host(spec, e["cave"])
        for g in e["galleries"]:
            gid = g["gallery"]["id"]
            rock = [l for l in fn["galleries/%s_rock" % gid] if not l.startswith("#")]
            assert rock and all(re.fullmatch(r"fill( -?\d+){6} \S+ replace #cobblers:cave_resettable", l) for l in rock)
            for k in range(spec["restore"]["variants"]):
                v = [l for l in fn["galleries/%s_v%d" % (gid, k)] if not l.startswith("#")]
                assert all(l.startswith("execute if block ") and (" %s run setblock " % hb) in l for l in v)
                assert len(v) == len(g["variants"][k])


def test_the_tag_is_the_stone_faces_list_plus_the_vanilla_ores_and_holds_no_container():
    tag = MC.resettable(SPEC)
    assert set(M.load()["restore"]["resettable"]) <= set(tag)
    for ore in ("coal", "iron", "copper", "lapis", "gold", "redstone", "diamond"):
        assert "minecraft:%s_ore" % ore in tag and "minecraft:deepslate_%s_ore" % ore in tag
    assert not [b for b in tag if any(c in b for c in MC.CONTAINERS)]


def test_a_spawn_condition_without_a_policy_entry_for_the_caves_is_refused(monkeypatch):
    spec, plan = _plan()
    assert MC.pack_problems(spec, plan) == []
    monkeypatch.setattr(MC, "POLICY_SCOPE", "no_such_place")
    bad = MC.pack_problems(spec, plan)
    assert any("minecraft:iron_ore" in p for p in bad) and any("deepslate_diamond_ore" in p for p in bad)


def test_the_policy_entry_names_the_caves_and_both_places():
    pol = json.loads((ROOT / "data" / "spawn_block_policy.json").read_text(encoding="utf-8"))
    ent = [w for w in pol["whitelist"] if MC.POLICY_SCOPE in (w.get("scope") or "")]
    assert ent and all(p in ent[0]["scope"] for p in ("route1_old_mine", "mining_town"))


def test_the_step_and_the_pack_are_wired():
    import reapply
    assert "cobblers_mining_caves" in reapply.SERVER_PACKS and "cobblers_mining_caves" in reapply.WORLD_LOCAL
    assert MC.build_functions(SPEC) == ["cobblers:mining_caves/build_%s" % c["id"] for c in SPEC["caves"]]
    src = (ROOT / "tools" / "reapply.py").read_text(encoding="utf-8")
    assert 'add("mining_caves:build", "mining_caves.py", "build", *src)' in src
    assert '("R9OC",' in src and "mining_caves.build_functions()" in src


def test_the_authored_mouths_are_recorded():
    for cave in SPEC["caves"]:
        e = cave.get("entry") or {}
        assert e.get("front") in M.FRONTS and len(e.get("anchor") or []) == 2, cave["id"]
