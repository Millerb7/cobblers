"""Composed towns in the ambient generators (tools/ambient.py, tools/ambient_idle.py; data/ambient.json `composition`).

Written by the generator's builder (2026-10-05), so these are the builder's own checks, not the independent audit
(tools/ambient_composition_audit.py, another agent's). Run against the FIXTURE town tests/fixtures/ambient_towns/
gorge_hamlet.json through `towns=` / `--towns-dir`, never data/ambient_towns. Needs the heightmap (tools/ground.py), the
hydrated kits (the building templates) and the Cobblemon jar (the species' sizes); without one of them a test SKIPs
(NOT_EXECUTED), and a skip is not a pass. Not covered: anything in a running Minecraft, and the replay of the built
packs (`build` only).
"""
from __future__ import annotations

import copy
import json
import math
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tests"))

import ambient as A  # noqa: E402
import ambient_idle as AI  # noqa: E402
import function_limits  # noqa: E402
import mcfunction_sim as M  # noqa: E402

FIXDIR = ROOT / "tests" / "fixtures" / "ambient_towns"
TOWN = "gorge_hamlet"
FIX = json.loads((FIXDIR / ("%s.json" % TOWN)).read_text(encoding="utf-8"))
DATA = json.loads((ROOT / "data" / "ambient.json").read_text(encoding="utf-8"))
COMP = DATA["composition"]
_GOT = {}


def compose(town=None, comp=None):
    if "inputs" not in _GOT:
        try:
            import ground as G
            G.Ground(None)
            _GOT["inputs"] = None if AI.species_sizes() is not None else "no Cobblemon jar here"
        except BaseException as e:      # noqa: BLE001  (a missing heightmap is a SystemExit)
            _GOT["inputs"] = "no heightmap here (%s)" % e
    if _GOT["inputs"]:
        pytest.skip("NOT_EXECUTED: " + _GOT["inputs"])
    return AI.compose(towns={TOWN: town or FIX}, comp=comp)[TOWN]


def fixture_town():
    if "base" not in _GOT:
        _GOT["base"] = compose()
    return _GOT["base"]


def refused(town=None, comp=None):
    with pytest.raises(SystemExit) as e:
        compose(town, comp)
    return str(e.value)


# ------------------------------------------------------------------------------------------------ the count rules

def test_town_files_are_read_and_their_workers_supersede_the_towns():
    towns = A.town_files(FIXDIR)
    assert set(towns) == {TOWN}
    data = copy.deepcopy(DATA)
    sample = (data["workers"] or data["superseded_workers"]["workers"])[0]
    data["workers"].append(dict(sample, id="old_gorge_worker", settlement=TOWN))
    ws, sup = A.workers_of(data, towns)
    assert sup == ["old_gorge_worker"]
    assert {w["id"] for w in ws if w["settlement"] == TOWN} == {w["id"] for w in FIX["workers"]}
    assert len(ws) == len(DATA["workers"]) + len(FIX["workers"])


def test_the_fixture_meets_the_count_rules():
    assert A.composition_problems(TOWN, FIX, COMP) == []
    assert A.town_counts(FIX) == FIX["counts"]


@pytest.mark.parametrize("mutate,needle", [
    (lambda t: t.update(target=11), "target 11, but its records make 12"),
    (lambda t: t.update(target=30), "outside the hamlet band"),
    (lambda t: t["counts"].update(pets=3), "counts disagree"),
    (lambda t: t.update(workers=t["workers"][:1], target=9, counts=None), "working share 0.11"),
])
def test_each_count_rule_fails_closed_naming_the_town(mutate, needle):
    t = copy.deepcopy(FIX)
    mutate(t)
    bad = A.composition_problems(TOWN, t, COMP)
    assert any(needle in b and b.startswith(TOWN) for b in bad), bad


def test_a_mining_town_needs_half_working():
    t = copy.deepcopy(FIX)
    assert any("mining town" in b for b in A.composition_problems("mining_town", t, COMP))


# ------------------------------------------------------------------------------------------------ the placement

def test_every_record_is_placed_with_what_the_audit_reads():
    got = fixture_town()
    ids = {i["id"] for i in got["idlers"]}
    assert len(got["idlers"]) == FIX["counts"]["total"] - FIX["counts"]["working"]
    for r in FIX["pets"] + FIX["placed"]:
        assert "%s_%s" % (TOWN, r["id"]) in ids
    for i in got["idlers"]:
        assert i["town"] == TOWN and i["species"] and len(i["at"]) == 3
        assert i["role"] in ("pet", "placed", "situation")
        if i["role"] == "situation":
            assert i["situation"] in {x["id"] for x in FIX["situations"]}
    kinds = {i["id"].split(TOWN + "_", 1)[1]: i["kind"] for i in got["idlers"]}
    assert kinds["fx_elder_hippopotas"] == "follower" and kinds["fx_elder_sandshrew"] == "still"
    assert kinds["fx_center_roof_baltoy"] == "still" and kinds["fx_lunatone_nap_1"] == "sleeper"
    assert got["summary"]["counts"]["total"] == 12 and got["summary"]["unique_situations"] == ["fx_diglett_queue"]


def test_situation_members_and_props_are_at_their_anchor_offsets():
    got = fixture_town()
    q = [x for x in FIX["situations"] if x["id"] == "fx_diglett_queue"][0]
    ax, ay, az = q["at"]
    members = sorted((i for i in got["idlers"] if i.get("situation") == q["id"]), key=lambda i: i["id"])
    assert [(i["at"][0] - 0.5 - ax, i["at"][1] - ay, i["at"][2] - 0.5 - az) for i in members] == \
        [tuple(o) for o in q["members"][0]["offsets"]]
    props = {tuple(p["at"]): p["block"] for p in got["props"]}
    assert props[(ax + 1, ay, az)] == "minecraft:barrel[facing=up]"


def test_a_roof_spot_is_on_its_buildings_highest_roof_read_from_the_template_not_the_tool():
    # read independently here: the template's blocks rotated as tools/place_town.py rotates them
    import nbt
    import place_town as PT
    got = fixture_town()
    i = [i for i in got["idlers"] if i["id"].endswith("fx_center_roof_baltoy")][0]
    rec = [b for b in json.loads((ROOT / "derived" / "towns" / ("%s_placement.json" % TOWN)).read_text())["buildings"]
           if b["id"] == "gorge_hamlet_pokecenter"][0]
    f = [q for q in json.loads((ROOT / "data" / "placements.json").read_text(encoding="utf-8"))["placements"]
         if q["id"] == rec["id"]][0]["file"]
    _, t = nbt.load(ROOT / f)
    top = {}
    for b in t["blocks"]:
        name = t["palette"][b["state"]]["Name"]
        if name in ("minecraft:air", "minecraft:structure_void"):
            continue
        rx, rz = PT.rotate(b["pos"][0], b["pos"][2], rec["rotation"])
        c = (rec["command_position"][0] + rx, rec["command_position"][2] + rz)
        top[c] = max(top.get(c, -999), rec["origin_y"] + b["pos"][1])
    x, z = math.floor(i["at"][0]), math.floor(i["at"][2])
    assert top[(x, z)] == max(top.values())
    assert top[(x, z)] < i["at"][1] <= top[(x, z)] + 1


@pytest.mark.parametrize("mutate,needle", [
    (lambda t: t["placed"][0].update(species="snorlax"), "does not fit a roof spot"),
    (lambda t: t["placed"][0].update(building="no_such_house"), "no building 'no_such_house'"),
    (lambda t: t["placed"][1].pop("at"), "names neither a building nor an `at`"),
    (lambda t: t["placed"][0].update(spot="window"), "no free window spot"),
    (lambda t: t["placed"][0].update(spot="attic"), "spot 'attic'"),
    (lambda t: t["situations"][1]["members"][0].update(species="diglett"), "may never sleep"),
    (lambda t: t["situations"][0].update(at=[6820, 130, 4355]), "is not the plan's ground"),
    (lambda t: t["placed"][1].update(at=[6560, 107, 4358], allow=[]), "on street (allow it with"),
    (lambda t: t["pets"][0].update(owner="nobody"), "owner 'nobody'"),
    (lambda t: t["pets"][0].update(mode="carry"), "mode 'carry'"),
    (lambda t: t["situations"][0]["members"][0].update(count=2), "count 2 with 3 offsets"),
    (lambda t: t["placed"][1]["props"].append({"block": "minecraft:stone", "at": [0, 0, 0]}), "its own prop"),
])
def test_each_placement_rule_fails_closed_naming_the_town(mutate, needle):
    t = copy.deepcopy(FIX)
    mutate(t)
    msg = refused(t)
    assert TOWN in msg and needle in msg, msg


def test_one_species_bunched_outside_a_situation_is_refused_and_inside_one_is_not():
    q = [x for x in FIX["situations"] if x["id"] == "fx_diglett_queue"][0]
    t = copy.deepcopy(FIX)
    ax, ay, az = q["at"]
    t["placed"][1].update(species="diglett", at=[ax - 2, ay, az + 3], props=[])
    msg = refused(t)
    assert "two diglett within" in msg and "same_species_group_radius" in msg, msg


def test_too_many_in_view_is_refused():
    comp = copy.deepcopy(COMP)
    comp["ceiling"]["in_view_max"] = 5
    msg = refused(comp=comp)
    assert TOWN in msg and "over composition.ceiling.in_view_max 5" in msg, msg


# ------------------------------------------------------------------------------------------------ the pack

def composed_pack():
    got = fixture_town()
    rules = dict(DATA["idle"]["rules"], water_changed_margin=DATA["rules"]["water_changed_margin"])
    towns = {TOWN: got["idlers"]}
    pl = {"rules": rules, "towns": towns, "gates": AI.gates_of(towns, rules), "props": {TOWN: got["props"]},
          "composed": {TOWN: got["summary"]}}
    return pl, AI.functions(pl)


def test_the_composed_functions_pass_the_function_limits():
    _pl, fns = composed_pack()
    bad = {n: function_limits.check_lines(l, n) for n, l in fns.items()}
    assert not {n: b for n, b in bad.items() if b}


def test_props_are_set_and_cleaned_up_only_where_still_theirs():
    pl, fns = composed_pack()
    sets = [l for l in fns["t/%s/props" % TOWN] if l.startswith("setblock")]
    assert len(sets) == len(pl["props"][TOWN])
    clean = fns["t/%s/cleanup" % TOWN]
    for p in pl["props"][TOWN]:
        x, y, z = p["at"]
        assert "execute if block %d %d %d %s run setblock %d %d %d minecraft:air" % (x, y, z, p["block"], x, y, z) in clean
    assert sum(1 for l in clean if l.startswith("kill ")) == len(pl["towns"][TOWN])


def test_the_keeper_spawns_each_composed_pokemon_once_with_its_kinds_flags_and_home():
    pl, fns = composed_pack()
    w = M.World({"%s:%s" % (AI.NS, k) if ":" not in k else k: v for k, v in
                 {("%s/%s" % (AI.FOLDER, n)): l for n, l in fns.items()}.items()})
    w.tags = {"load": ["%s/load" % AI.F], "tick": ["%s/tick" % AI.F]}
    w.run_load()
    cx, cy, cz = pl["gates"][TOWN]["centre"]
    w.add_player((cx, cy, cz))
    w.tick(pl["rules"]["keep_every"])
    for i in pl["towns"][TOWN]:
        got = w.living("cobblemon:pokemon", "cobblers.amb.%s" % i["id"])
        assert len(got) == 1, i["id"]
        e = got[0]
        assert e.nbt["Pokemon"]["Species"] == i["species"]
        assert e.nbt.get("NoAI") == (1 if i["kind"] in AI.STILL else 0), i["id"]
        assert math.dist(e.pos, i["at"]) < 0.01
        if i.get("home"):
            sc = e.nbt["ScriptingConfig"]
            assert [sc["home_x"], sc["home_y"], sc["home_z"]] == pytest.approx(i["home"]), i["id"]


def test_reapply_sets_a_composed_towns_props_before_it_settles_it(tmp_path, monkeypatch):
    pl, _fns = composed_pack()
    p = tmp_path / "idle_plan.json"
    p.write_text(json.dumps(pl), encoding="utf-8")
    monkeypatch.setattr(AI, "PLAN", p)
    steps = AI.placement_steps()
    fns = [v for k, v in steps if k == "fn"]
    assert fns == ["%s/t/%s/props" % (AI.F, TOWN)] + ["%s/t/%s/keep" % (AI.F, TOWN)] * 2
    first_load = next(n for n, (k, v) in enumerate(steps) if k == "cmd" and v.startswith("forceload add"))
    assert steps.index(("fn", "%s/t/%s/props" % (AI.F, TOWN))) < first_load
