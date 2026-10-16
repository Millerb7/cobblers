"""A working Pokemon with nothing to act on stands relaxed instead of swinging at air (tools/ambient.py `relaxed`,
tools/ambient_targets.py, data/ambient.json rules.targets, data/ambient_towns/gym2_town.json).

The owner, 2026-10-16: "pokemon can stay, but make them look relaxed if not doing anything." Viltri Quay's Corphish
stood on open grass picking knots out of nets that are not there.

Written by the session that built the check (the builder's own tests, not an independent audit: say so when grading).
Offline: the pure tests use a synthetic site and a synthetic model and always run. The real-data tests need the
heightmap (tools/ground.py), the hydrated kits (the cottage's template) and derived/towns/gym2_town_plan.json
(python tools/town_plan.py gym2_town); without one they SKIP (NOT_EXECUTED), and a skip is not a pass.
Not covered: anything in a running Minecraft. Whether a still NoAI Pokemon that turns its head every eight seconds LOOKS
relaxed in game is not observed; only that it does nothing else.
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tests"))

import ambient as A  # noqa: E402
import ambient_targets as T  # noqa: E402
import mcfunction_sim as M  # noqa: E402

DATA = json.loads((ROOT / "data" / "ambient.json").read_text(encoding="utf-8"))
RULES = DATA["rules"]
TOWN = json.loads((ROOT / "data" / "ambient_towns" / "gym2_town.json").read_text(encoding="utf-8"))
TOWN_WORKS = [w for w in TOWN["workers"] if w["job"] == "work"]
F = A.F


class FlatSite:
    """The two things plan_worker asks of a Site, over flat free ground."""

    def y(self, x, z):
        return 64

    def blocked(self, x, z):
        return None


def record(**kw):
    w = {"id": "syn_corphish", "settlement": "syn", "species": "corphish", "level": 20, "job": "work",
         "at": [100, 100], "face": [103, 100], "every": 32,
         "effect": {"block": "minecraft:cobweb", "count": 8, "sound": "minecraft:entity.sheep.shear", "pitch": 1.1},
         "interact": "It sits there."}
    w.update(kw)
    return w


def functions_of(*workers):
    pl = {"rules": RULES, "workers": [A.plan_worker(w, FlatSite(), RULES) for w in workers]}
    fns = {"%s/%s" % (F, k): v for k, v in A.functions(pl).items()}
    return fns


def world(*workers):
    w = M.World(functions_of(*workers), spawn=(100.0, 64.0, 100.0))
    w.tags = {"load": ["%s/load" % F], "tick": ["%s/tick" % F]}
    w.add_player((100.5, 65.0, 100.5))
    w.run_load()
    w.tick(RULES["keep_every"])
    return w


# ------------------------------------------------------------------------------------------------ the generator

# Without it a "relaxed" worker would still hop and set off its effect: the flag would be a label and nothing more.
def test_a_relaxed_worker_sets_off_no_effect_and_no_sound_and_never_hops():
    live = record(id="syn_working")
    still = record(id="syn_relaxed", relaxed=True, relaxed_why="no wall at the face", look_around=[100, 110])
    w = world(live, still)
    w.tick(8 * RULES["relaxed"]["look_every"])
    mine = "%s/w/syn_relaxed/" % F
    assert not w.logged("particle", mine), "a relaxed worker set off a particle"
    assert not w.logged("playsound", mine), "a relaxed worker made a sound"
    # the control: the working one, in the same world, does strike (so the checks above are not vacuous)
    assert w.logged("particle", "%s/w/syn_working/" % F), "the working control never struck"
    (poke,) = w.living("cobblemon:pokemon", "%s.syn_relaxed" % A.TAG)
    moves = [e[2] for e in w.log if e[1] == "tp" and e[2][0] is poke]
    assert moves
    for _e, pos, _rot in moves:
        assert (pos[0], pos[2]) == (100.5, 100.5), "a relaxed worker left its station: %s" % (pos,)
        assert pos[1] == 64, "a relaxed worker hopped: %s" % (pos,)
    assert not w.errors, w.errors


# Without it a relaxed worker with a look_around would never move at all (a statue), or turn every few ticks (a fidget).
def test_a_relaxed_worker_turns_to_look_round_once_per_look_every_and_back():
    look_every = RULES["relaxed"]["look_every"]
    still = record(id="syn_relaxed", relaxed=True, relaxed_why="no wall", look_around=[100, 110])
    w = world(still)
    w.log.clear()
    w.tick(4 * look_every)
    (poke,) = w.living("cobblemon:pokemon", "%s.syn_relaxed" % A.TAG)
    yaws = [round(e[2][2][0], 1) for e in w.log if e[1] == "tp" and e[2][0] is poke
            and e[2][1][0] == 100.5 and e[2][1][2] == 100.5]
    assert len(set(yaws)) == 2, yaws                                      # the face yaw and the look-round yaw, nothing else
    turns = sum(1 for a, b in zip(yaws, yaws[1:]) if a != b)
    assert 6 <= turns <= 9, (turns, yaws)                                 # 4 periods, two turns each, +-1 at the window edge


# Without it the plan accepts an unexplained relaxed worker, and the next author cannot tell why it stands idle.
def test_a_relaxed_worker_must_say_what_is_missing():
    with pytest.raises(SystemExit) as e:
        A.plan_worker(record(relaxed=True), FlatSite(), RULES)
    assert "relaxed_why" in str(e.value)


# Without it a worker could drop its effect and still claim to work (a work job that does nothing, unnoticed).
def test_a_work_job_without_an_effect_is_refused_unless_relaxed():
    bad = record()
    del bad["effect"]
    with pytest.raises(SystemExit):
        A.plan_worker(bad, FlatSite(), RULES)
    ok = dict(bad, relaxed=True, relaxed_why="nothing there")
    assert A.plan_worker(ok, FlatSite(), RULES)["relaxed"] is True


# ------------------------------------------------------------------------------------------------ the check

def model(structure=(), coarse=(), paving=()):
    m = T.Model.__new__(T.Model)
    m.settlement = "syn"
    m.structure = {c: "wall" for c in structure}
    m.coarse = {c: "lot" for c in coarse}
    m.paving = {c: "street" for c in paving}
    return m


def ground_at(y):
    return lambda x, z: y


# Without it a face two blocks from the only wall would pass, and the Corphish's case (a wall near, not at) is the bug.
def test_a_target_must_be_within_reach_of_the_face_cell():
    face = record()["face"]                                              # [103, 100]
    assert T.evidence(record(), model(structure=[(104, 101)]), ground_at(64), 1)[0] == "structure"
    assert T.evidence(record(), model(structure=[(105, 100)]), ground_at(64), 1) is None
    assert T.evidence(record(), model(structure=[(105, 100)]), ground_at(64), 2)[0] == "structure"
    assert face == [103, 100]


# Without it a net-picker on a street would count the paving as its nets.
def test_paving_counts_only_for_a_record_that_says_it_works_paving():
    street = [(103, 100)]
    assert T.evidence(record(), model(paving=street), ground_at(64), 1) is None
    got = T.evidence(record(target="paving"), model(paving=street), ground_at(64), 1)
    assert got and got[0] == "paving"
    assert T.evidence(record(target="paving"), model(paving=[(104, 100)]), ground_at(64), 1) is None   # the face cell itself


# Without it a water job on dry land (the Quagsire's shallows, 12 blocks from the water) would pass.
def test_water_counts_only_where_the_ground_is_under_the_stated_surface():
    wet = record(target={"water": 104, "source": "data/gym_arenas/gym2.json exit.why"})
    assert T.evidence(wet, model(), ground_at(103), 1)[0] == "water"
    assert T.evidence(wet, model(), ground_at(105), 1) is None
    with pytest.raises(SystemExit):
        T.evidence(record(target={"water": 104}), model(), ground_at(103), 1)        # a level with no source
    with pytest.raises(SystemExit):
        T.evidence(record(target="nets"), model(), ground_at(103), 1)                # an unknown kind is not a pass


# ------------------------------------------------------------------------------------------------ the real town

_GOT = {}


def gym2():
    """(model, ground) for gym2_town, or SKIP."""
    if "m" not in _GOT:
        try:
            import ground as G
            _GOT["g"] = G.Ground(None)
            _GOT["m"] = T.Model("gym2_town")
            _GOT["err"] = None
        except BaseException as e:      # noqa: BLE001  (a missing heightmap is a SystemExit)
            _GOT["err"] = "%s: %s" % (type(e).__name__, e)
    if _GOT["err"]:
        pytest.skip("NOT_EXECUTED: gym2_town cannot be modelled here (%s)" % _GOT["err"])
    return _GOT["m"], _GOT["g"]


# Without it a record could be aimed at nothing in the shipped town and nothing would say so.
def test_every_work_job_in_the_audited_towns_has_a_target_or_is_relaxed():
    gym2()
    res = T.audit()
    assert not res["unmodelled"], res["unmodelled"]
    assert not res["problems"], res["problems"]
    assert {r["id"] for r in res["records"]} == {w["id"] for w in TOWN_WORKS}


# The regression itself. Without it the Corphish could be put back to work at its air.
def test_the_corphish_nets_are_not_where_its_face_is_and_it_is_relaxed():
    m, g = gym2()
    c = next(w for w in TOWN_WORKS if w["id"] == "viltri_nets_corphish")
    assert c.get("relaxed") is True and c["relaxed_why"].strip()
    plain = {k: v for k, v in c.items() if k not in ("relaxed", "relaxed_why")}
    assert T.evidence(plain, m, g, int(RULES["targets"]["reach"])) is None
    # the cottage is there, just not at the face: the nearest template block above the foundation is within 5
    fx, fz = c["face"]
    near = m.near(m.structure, fx, fz, 5)
    assert near and near[1].startswith("gym2_house_01"), near
    assert near[0] > int(RULES["targets"]["reach"])


# Without it the check bites nothing: unrelax the real records and the audit must name every one that has no target.
def test_the_audit_fails_a_real_work_job_aimed_at_nothing():
    gym2()
    workers = [dict(w, settlement="gym2_town") for w in copy.deepcopy(TOWN["workers"])]
    relaxed = [w["id"] for w in workers if w.get("relaxed")]
    assert relaxed, "no relaxed record in the town"
    for w in workers:
        w.pop("relaxed", None)
    res = T.audit(workers=workers)
    flagged = {p.split(" ")[0] for p in res["problems"]}
    assert flagged == set(relaxed), (sorted(flagged), sorted(relaxed))


# Without it a lot nobody builds (the piers: "composition in Axiom, no prep") would count as the thing being worked.
def test_an_unbuilt_lot_is_not_a_target_and_a_built_one_is():
    m, g = gym2()
    assert T.evidence(record(face=[1652, 2866]), m, g, 1) is None            # inside gym2_pier_east's rect
    built = next(c for c, lab in m.structure.items() if lab.startswith("gym2_pokecenter"))
    assert T.evidence(record(face=list(built)), m, g, 1)[0] == "structure"


# Without it relaxing a record could delete the Pokemon, move it, or drop its line: the owner asked for the Pokemon to stay.
def test_relaxed_records_keep_their_pokemon_place_and_line():
    head = TOWN
    ids = {w["id"] for w in head["workers"]}
    assert {"viltri_nets_corphish", "viltri_dredge_quagsire", "viltri_keel_scyther", "viltri_lifeguard_floatzel",
            "viltri_bilge_mudkip", "viltri_winch_poliwhirl"} <= ids
    for w in head["workers"]:
        if w.get("relaxed"):
            assert w["species"] and w["at"] and w["face"] and w["interact"].strip()
            assert w["effect"], "the effect stays in the record, for when its target is built"
    comp = DATA["composition"]
    assert A.composition_problems("gym2_town", head, comp) == [], "relaxing a record changed the town's tally"
