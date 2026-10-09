"""The Drowned Quarry under Lake Tilpey (tools/drowned_quarry.py, tools/drowned_quarry_audit.py, data/drowned_quarry.json).

Three things are tested, none of them by the generator's own derivation:

  the build     the committed pack passes the independent audit (which replays its fills into the natural lake and rock),
                and each GENERATOR mutation (a wider road, a thinner shell, a dry void, a shaft to the surface, an
                unwaterlogged lantern, a hall one block too tall, an unwritten pillar, a keeper that forgets the species
                or the guardian) fails a NAMED check with data/drowned_quarry.json untouched. A record-side mutation
                would move the expectation and the output together and prove nothing, so the few data mutations here
                (a short road, a wrong portal, a level over the cap) test the record's validators and the audit's reach
                and mouth checks, not independence.
  the keeper    the generated functions RUN on tests/gulch_sim.py's world model (the Ursaluna den's tests' harness):
                installed asleep on its spot, woken by a player inside the trigger and not outside it, lies down again
                when everyone has gone, comes back after its return clock only with nobody near and a player to meet it,
                never touches a guardian, and a restart never moves the clock.
  the wiring    the step, the pack lists, the probes and the prepare jobs in tools/reapply.py.
"""
from __future__ import annotations

import functools
import json
import os
import re
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tests"))

import drowned_quarry as D  # noqa: E402
import drowned_quarry_audit as A  # noqa: E402
import gulch_sim as GS  # noqa: E402
import nbt_sim as N  # noqa: E402

REC = json.loads((ROOT / "data" / "drowned_quarry.json").read_text(encoding="utf-8"))
MON = REC["monster"]
TAG, DORM, GUARD = MON["tag"], MON["dormant_tag"], MON["guardian_tag"]
OBJ = D.OBJ
COOL = MON["keeper"]["cooldown_ticks"]
PASS = MON["keeper"]["period_ticks"]
TRIGGER = MON["trigger_radius"]


def _ground():
    import ground as G
    import terrain as T
    try:
        return G.Ground(os.environ.get("COBBLERS_SOURCE_ROOT"))
    except T.TerrainUnavailable as e:
        pytest.skip("the canonical heightmap is unusable: %s" % e)


@pytest.fixture(scope="module")
def ground():
    return _ground()


def build(ground, out, doc=None):
    doc = doc or D.load()
    for rel, text in D.files(doc, ground).items():
        f = out / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(text, encoding="utf-8", newline="\n")
    return doc


def run_audit(ground, out, record=None):
    doc = build(ground, out)
    problems, _notes = A.audit(record or REC, ground, out, jar=True)
    return problems


def checks(problems):
    return sorted({p.split(":", 1)[0] for p in problems})


# ------------------------------------------------------------------ the build


def test_the_committed_place_is_clean(ground, tmp_path):
    assert run_audit(ground, tmp_path) == []


def test_the_pack_is_deterministic(ground, tmp_path):
    a, b = D.files(D.load(), ground), D.files(D.load(), ground)
    assert a == b and len(a) == 21


def _mutate_files(monkeypatch, fn):
    real = D.files

    def patched(doc, g):
        out = real(doc, g)
        fn(out)
        return out
    monkeypatch.setattr(D, "files", patched)


def _key(out, name):
    return "data/cobblers/function/drowned_quarry/%s.mcfunction" % name


def test_a_wider_road_is_not_the_planned_void(ground, tmp_path, monkeypatch):
    real = D.road_rects
    monkeypatch.setattr(D, "road_rects", lambda doc: [(a - 2, b - 2, c + 2, d + 2) for a, b, c, d in real(doc)])
    assert "void" in checks(run_audit(ground, tmp_path))


def test_a_hall_one_block_taller_is_not_the_planned_void(ground, tmp_path, monkeypatch):
    real = D.Model.__init__

    def taller(self, doc, g):
        real(self, doc, g)
        self.void = self.void | np.roll(self.void, 1, axis=0)

    monkeypatch.setattr(D.Model, "__init__", taller)
    assert "void" in checks(run_audit(ground, tmp_path))


def test_a_thinner_shell_breaks_the_seal(ground, tmp_path, monkeypatch):
    real = D._dilate
    monkeypatch.setattr(D, "_dilate", lambda mask, m: real(mask, m - 1))
    assert "seal" in checks(run_audit(ground, tmp_path))


def test_a_dry_void_is_refused(ground, tmp_path, monkeypatch):
    def dry(out):
        out[_key(out, "carve_void")] = out[_key(out, "carve_void")].replace("minecraft:water", "minecraft:air")
    _mutate_files(monkeypatch, dry)
    assert "flooded" in checks(run_audit(ground, tmp_path))


def test_a_shaft_into_the_rock_is_not_the_planned_void_and_one_out_of_the_box_is_refused(ground, tmp_path, monkeypatch):
    cx, cz = REC["geometry"]["pit"]["centre"]
    real = D.files

    def shaft(top):
        def patched(doc, g):
            out = real(doc, g)
            out[_key(out, "carve_void")] += "fill %d 53 %d %d %d %d minecraft:water\n" % (cx - 3, cz - 3, cx - 3, top, cz - 3)
            return out
        return patched
    monkeypatch.setattr(D, "files", shaft(76))
    assert "void" in checks(run_audit(ground, tmp_path))
    monkeypatch.setattr(D, "files", shaft(130))
    assert "footprint" in checks(run_audit(ground, tmp_path / "b"))


def test_a_pillar_dissolved_after_the_floor_is_caught(ground, tmp_path, monkeypatch):
    px = REC["geometry"]["hall"]["pillars"]["xs"][0]
    pz = REC["geometry"]["hall"]["pillars"]["zs"][0]

    def lose(out):
        out[_key(out, "carve_dress")] += "fill %d 53 %d %d 68 %d minecraft:water\n" % (px - 1, pz - 1, px + 1, pz + 1)
    _mutate_files(monkeypatch, lose)
    assert "void" in checks(run_audit(ground, tmp_path))


def test_an_unwaterlogged_lantern_is_refused(ground, tmp_path, monkeypatch):
    def dry_lanterns(out):
        key = _key(out, "carve_dress")
        out[key] = out[key].replace("lantern[hanging=true,waterlogged=true]", "lantern[hanging=true]")
    _mutate_files(monkeypatch, dry_lanterns)
    assert "waterlog" in checks(run_audit(ground, tmp_path))


def test_a_block_outside_the_plan_is_refused(ground, tmp_path, monkeypatch):
    def stray(out):
        out[_key(out, "carve_dress")] += "setblock 6460 120 4100 minecraft:stone replace\n"
    _mutate_files(monkeypatch, stray)
    assert "footprint" in checks(run_audit(ground, tmp_path))


@pytest.mark.parametrize("block", ["minecraft:white_concrete", "minecraft:rail", "minecraft:barrier"])
def test_a_forbidden_block_is_refused(ground, tmp_path, monkeypatch, block):
    def bad(out):
        key = _key(out, "carve_dress")
        out[key] += "setblock 6500 53 4132 %s replace\n" % block
    _mutate_files(monkeypatch, bad)
    assert "palette" in checks(run_audit(ground, tmp_path))


@pytest.mark.parametrize("name,old,new", [
    ("keep", 'nbt={Pokemon:{Species:"cobblemon:gyarados"}}', ""),
    ("keep", ",tag=!cobblers.guardian", ""),
    ("hold", "tag=!cobblers.dq_dormant", "tag=cobblers.dq_dormant"),
    ("wake", "Unbattleable:0b", "Unbattleable:1b"),
    ("keeper", "time query gametime", "time query day"),
])
def test_a_keeper_that_breaks_a_rule_is_refused(ground, tmp_path, monkeypatch, name, old, new):
    def patch(out):
        key = _key(out, name)
        assert old in out[key], (name, old)
        out[key] = out[key].replace(old, new)
    _mutate_files(monkeypatch, patch)
    got = checks(run_audit(ground, tmp_path))
    assert "keeper" in got or "functions" in got, got


def test_a_plain_spawn_line_is_refused(ground, tmp_path, monkeypatch):
    def plain(out):
        key = _key(out, "spawn")
        out[key] += "spawnpokemonat 6528.5 47 4132.5 gyarados level=60\n"
    _mutate_files(monkeypatch, plain)
    assert "keeper" in checks(run_audit(ground, tmp_path))


# the record's own validators and the audit's reach and mouth checks (data mutations: they test the checks, not independence)


def _rec(**edits):
    doc = json.loads(json.dumps(REC))
    for path, value in edits.items():
        cur = doc
        keys = path.split("__")
        for k in keys[:-1]:
            cur = cur[k]
        cur[keys[-1]] = value
    return doc


def _write(tmp_path, doc):
    p = tmp_path / "rec.json"
    p.write_text(json.dumps(doc), encoding="utf-8")
    return p


@pytest.mark.parametrize("edits", [
    {"monster__level": 61},
    {"geometry__road__points": [[6340, 4108], [6430, 4120], [6488, 4132]]},
    {"monster__keeper__absent_passes": 1},
    {"monster__keeper__cooldown_ticks": 600},
    {"monster__awake_nbt": {"Unbattleable": "1b"}},
    {"monster__trigger_radius": 70},
])
def test_the_loader_refuses_a_record_that_breaks_a_rule(tmp_path, edits):
    with pytest.raises(D.QuarryError):
        D.load(_write(tmp_path, _rec(**edits)))


def test_a_short_road_gates_nothing_and_the_audit_says_so(ground, tmp_path):
    # the hall pulled 60 blocks toward the mouth: a Surf swimmer could go there and back
    rec = _rec(geometry__road__points=[[6340, 4108], [6410, 4108], [6410, 4132], [6430, 4132]],
               geometry__hall__x=[6430, 6482], geometry__pit__centre=[6470, 4132], monster__spot=[6470.5, 47, 4132.5],
               geometry__hall__pillars={"xs": [6442, 6454], "zs": [4122, 4142], "half": 1})
    rec["geometry"]["dressing"]["crane"]["mast"] = [6434, 4120]
    rec["geometry"]["dressing"]["stacks"] = [[6438, 4146], [6479, 4118], [6479, 4147]]
    rec["geometry"]["dressing"]["wreck"] = [[6458, 53, 4128, "minecraft:spruce_planks"]]
    rec["geometry"]["hall_lanterns"] = {"xs": [6436, 6448, 6460, 6474], "zs": [4118, 4132, 4146]}
    rec["geometry"]["road"]["portal_x"] = REC["geometry"]["road"]["portal_x"]
    doc = D.load(_write(tmp_path, rec))
    out = tmp_path / "pack"
    build(ground, out, doc)
    problems, _n = A.audit(rec, ground, out)
    assert "reach" in checks(problems), problems


def test_a_portal_declared_too_far_in_is_caught(ground, tmp_path):
    rec = _rec(geometry__road__portal_x=REC["geometry"]["road"]["portal_x"] + 6)
    out = tmp_path / "pack"
    build(ground, out)
    problems, _n = A.audit(rec, ground, out)
    assert "mouth" in checks(problems), problems


def test_the_mouth_is_under_painted_lake_water_and_deep(ground):
    import water_mask as W
    g = REC["geometry"]
    cols = [(x, z) for x in range(g["road"]["points"][0][0], g["road"]["portal_x"])
            for z in range(g["road"]["points"][0][1] - 3, g["road"]["points"][0][1] + 4)]
    assert W.claim(REC["water_body"], cols, ground, min_submersion=0) == []
    level = W.bodies()[REC["water_body"]]["level_y"]
    assert level - g["floor_y"] >= 20


# ------------------------------------------------------------------ the level and the gate


def test_the_level_is_the_cap_of_eight_badges_and_far_over_the_lake():
    caps = json.loads((ROOT / "data" / "legendaries.json").read_text(encoding="utf-8"))["level_caps"]["upper_bound_by_badges"]
    band = next(s for s in json.loads((ROOT / "data" / "spawns.json").read_text(encoding="utf-8"))["subregions"]
                if s["id"] == "tilpey_waters")["level_band"]
    assert MON["level"] == caps["8"] > caps["7"]
    assert MON["level"] >= caps["6"] + 10 and MON["level"] >= band["maximum"] + 10
    flags = {f["id"] for f in json.loads((ROOT / "data" / "progression.json").read_text(encoding="utf-8"))["flags"]}
    assert MON["catch_gate"] in flags and REC["gate"]["dive_flag"] in flags


def test_no_tilpey_spawn_entry_is_edited_or_added_by_this_place():
    sp = (ROOT / "data" / "spawns.json").read_text(encoding="utf-8")
    assert "drowned_quarry" not in sp and "cobblers.dq" not in sp


def test_the_lair_is_not_the_uxie_grotto_or_another_place():
    leg = json.loads((ROOT / "data" / "legendaries.json").read_text(encoding="utf-8"))
    uxie = next(e for e in leg["encounters"] if e["id"] == "uxie") if "encounters" in leg else None
    sx, sz = MON["spot"][0], MON["spot"][2]
    if uxie:
        ux, uz = uxie["mouth"]
        assert ((sx - ux) ** 2 + (sz - uz) ** 2) ** 0.5 > 500
    # the dive gate's arch is 620 blocks from Uxie's reserved grotto; the lair must not be on the arch
    ax, az = next(p for p in json.loads((ROOT / "data" / "portals.json").read_text(encoding="utf-8"))["portals"]
                  if p["id"] == "dive_tilpey_gate")["at"]
    assert ((sx - ax) ** 2 + (sz - az) ** 2) ** 0.5 > 150


# ------------------------------------------------------------------ the keeper, run


class Lake(GS.World):
    """tests/gulch_sim.py's world plus what Cobblemon adds that the pack reads: `nbt=` selector filters and a spawned
    Pokemon's Species, Level and NoAI (the Ursaluna den's tests' harness, with a spawn at a fractional position)."""

    def command(self, cmd):
        t = cmd.split(" ")
        if t[0] in ("tellraw", "playsound"):
            self.log.append(cmd)
            return None
        if t[0] == "spawnpokemonat":
            x, y, z = (float(v) for v in t[1:4])
            e = self.pokemon((x, y, z), species=t[4])
            props = t[5:]
            e["nbt"]["Pokemon"]["Species"] = "cobblemon:%s" % t[4]
            e["nbt"]["Pokemon"]["Level"] = int(next(p for p in props if p.startswith("level="))[len("level="):])
            if "no_ai" in props:
                e["nbt"]["NoAI"] = N.Byte(1)
            e["props"] = props
            self.log.append(cmd)
            return None
        return super().command(cmd)

    def select(self, sel, origin=None):
        m = re.fullmatch(r"(@[aes])\[(.*)\]", sel)
        if not m or "nbt=" not in m.group(2):
            return super().select(sel, origin)
        f = GS.split_filters(m.group(2))
        pats = [N.parse_snbt(v) for k, v in f if k == "nbt"]
        rest = ",".join("=".join(kv) for kv in f if kv[0] not in ("nbt", "limit", "sort"))
        out = [e for e in super().select("%s[%s]" % (m.group(1), rest), origin)
               if all(N.matches(p, e.get("nbt", {})) for p in pats)]
        o = origin or self.pos
        sort = [v for k, v in f if k == "sort"]
        if sort:
            out.sort(key=lambda e: GS.math.dist(e["pos"], o), reverse=sort[0] == "furthest")
        lim = [int(v) for k, v in f if k == "limit"]
        return out[:lim[0]] if lim else out


@functools.lru_cache(maxsize=None)
def _fns():
    files = D.files(D.load(), _ground())
    return {rel[len("data/cobblers/function/"):-len(".mcfunction")]: text.splitlines()
            for rel, text in files.items() if rel.endswith(".mcfunction")}


SPOT = tuple(MON["spot"])
FOLDER = REC["folder"]


def world(fns=None, gt=5_000_000):
    w = Lake(fns or dict(_fns()))
    w.gt = gt
    w.call("%s/load" % FOLDER)
    return w


def install(w):
    """What R18DQ's chain does once a look has passed: the act, then (100 ticks later) the de-duplication."""
    w.call("%s/place_act" % FOLDER)
    w.call("%s/place_done" % FOLDER)
    return gyarados(w)[0]


def gyarados(w):
    return [e for e in w.entities if TAG in e["tags"]]


def score(w, h):
    return w.score.get((h, OBJ))


def passes(w, n):
    out = []
    for _ in range(n):
        w.gt += PASS
        w.call("%s/keeper" % FOLDER)
        out.append(len(gyarados(w)))
    return out


def player_at(w, dx, dz, dy=0.0):
    return w.player((SPOT[0] + dx, SPOT[1] + dy, SPOT[2] + dz))


def test_the_install_leaves_one_sleeping_gyarados_on_its_spot_at_its_level():
    w = world()
    g = install(w)
    n = g["nbt"]
    assert len(gyarados(w)) == 1 and DORM in g["tags"] and g["pos"] == SPOT
    assert n["Unbattleable"] == N.Byte(1) and n["NoAI"] == N.Byte(1) and n["NoGravity"] == N.Byte(1) and n["PoseType"] == "SLEEP"
    assert n["Pokemon"]["Level"] == MON["level"] and n["Pokemon"]["Species"] == "cobblemon:gyarados"
    assert any("scale_modifier=%s" % MON["scale_modifier"] in c and "level=%d" % MON["level"] in c for c in w.log)
    assert score(w, "#gone") == D.PRESENT


def test_a_second_install_makes_no_second_gyarados():
    w = world()
    install(w)
    install(w)
    assert len(gyarados(w)) == 1


def test_it_wakes_for_a_player_inside_the_trigger_and_not_outside_it():
    w = world()
    g = install(w)
    p = player_at(w, TRIGGER + 6, 0)
    passes(w, 3)
    assert DORM in g["tags"] and g["nbt"]["Unbattleable"] == N.Byte(1)
    p["pos"] = (SPOT[0] + TRIGGER - 2, SPOT[1], SPOT[2])
    passes(w, 1)
    assert DORM not in g["tags"]
    n = g["nbt"]
    assert n["Unbattleable"] == N.Byte(0) and n["NoAI"] == N.Byte(1) and n["NoGravity"] == N.Byte(1) and n["PoseType"] == "SLEEP"
    assert any("tellraw" in c for c in w.log) and any("playsound" in c for c in w.log)


def test_a_spectator_never_wakes_it():
    w = world()
    g = install(w)
    s = player_at(w, 3, 0)
    s["mode"] = "spectator"
    passes(w, 3)
    assert DORM in g["tags"]


def test_an_awake_one_is_not_dragged_home_through_the_fight_and_lies_down_when_everyone_has_gone():
    w = world()
    g = install(w)
    p = player_at(w, 5, 0)
    passes(w, 1)
    assert DORM not in g["tags"]
    g["pos"] = (SPOT[0] + 2.0, SPOT[1], SPOT[2])             # the fight moved it
    passes(w, 3)
    assert g["pos"] == (SPOT[0] + 2.0, SPOT[1], SPOT[2]) and DORM not in g["tags"]
    p["pos"] = (SPOT[0] + MON["keeper"]["settle_radius"] + 30, SPOT[1], SPOT[2])
    passes(w, 1)
    assert DORM in g["tags"] and g["pos"] == SPOT and g["nbt"]["Unbattleable"] == N.Byte(1)


def test_a_sleeping_one_moved_off_its_spot_is_put_back():
    w = world()
    g = install(w)
    g["pos"] = (SPOT[0] + 4.0, SPOT[1] + 3.0, SPOT[2])
    passes(w, 1)
    assert g["pos"] == SPOT


def _gone(w, g):
    w.entities.remove(g)                                      # beaten, caught or killed: all one thing here


def test_a_gone_one_returns_after_the_clock_only_with_nobody_near_and_a_player_to_meet_it():
    w = world()
    g = install(w)
    passes(w, 1)
    _gone(w, g)
    seen = passes(w, 2)
    assert seen == [0, 0]
    t_gone = score(w, "#gone")
    assert t_gone != D.PRESENT
    p = player_at(w, 70, 0)                                   # inside the 96, outside the 48
    while w.gt + PASS - t_gone < COOL:
        assert passes(w, 1) == [0], "it came back before its clock"
    assert passes(w, 1) == [1]
    (new,) = gyarados(w)
    assert new is not g and new["pos"] == SPOT and DORM in new["tags"] and new["nbt"]["PoseType"] == "SLEEP"
    assert score(w, "#gone") == D.PRESENT


def test_it_does_not_return_in_front_of_anyone_nor_for_nobody():
    w = world()
    g = install(w)
    passes(w, 1)
    _gone(w, g)
    passes(w, 2)
    t_gone = score(w, "#gone")
    w.gt = t_gone + COOL + 1000
    near = player_at(w, MON["keeper"]["spawn_clear"] - 5, 0)
    assert passes(w, 3) == [0, 0, 0]
    near["pos"] = (SPOT[0] + 500, SPOT[1], SPOT[2])
    assert passes(w, 3) == [0, 0, 0]                          # nobody within 96 either: nothing to meet it
    near["pos"] = (SPOT[0] + 70, SPOT[1], SPOT[2])
    assert passes(w, 1) == [1]


def test_a_chunk_that_is_not_loaded_never_starts_the_clock():
    w = world()
    g = install(w)
    w.loaded = lambda x, y, z: False
    w.entities.remove(g)
    passes(w, 6)
    assert score(w, "#gone") == D.PRESENT


def test_a_restart_never_moves_a_started_clock():
    w = world()
    g = install(w)
    passes(w, 1)
    _gone(w, g)
    passes(w, 2)
    t_gone = score(w, "#gone")
    w.call("%s/load" % FOLDER)
    assert score(w, "#gone") == t_gone


def test_a_guardian_is_never_held_woken_settled_or_killed():
    w = world()
    g = install(w)
    g["tags"].add(GUARD)
    g["pos"] = (SPOT[0] + 9.0, SPOT[1], SPOT[2])
    player_at(w, 5, 0)
    passes(w, 5)
    assert g in w.entities and g["pos"] == (SPOT[0] + 9.0, SPOT[1], SPOT[2]) and DORM in g["tags"]
    assert g["nbt"]["Unbattleable"] == N.Byte(1)


def test_a_guardian_the_blackout_rebuilt_counts_as_present_and_no_second_one_spawns():
    w = world()
    g = install(w)
    passes(w, 1)
    w.entities.remove(g)
    rebuilt = w.pokemon((SPOT[0] + 6.0, SPOT[1], SPOT[2]), tags=(GUARD,), species="gyarados")
    rebuilt["nbt"]["Pokemon"]["Species"] = "cobblemon:gyarados"
    passes(w, 3)
    assert score(w, "#gone") == D.PRESENT
    w.gt = 10 ** 8
    player_at(w, 70, 0)
    assert passes(w, 3) == [0, 0, 0] and len([e for e in w.entities if e["kind"] == "pokemon"]) == 1


def test_a_duplicate_is_removed_and_never_a_guardian():
    w = world()
    g = install(w)
    second = w.pokemon((SPOT[0] + 1.0, SPOT[1], SPOT[2]), tags=(TAG,), species="gyarados")
    second["nbt"]["Pokemon"]["Species"] = "cobblemon:gyarados"
    passes(w, 1)
    assert len(gyarados(w)) == 1
    guard = w.pokemon((SPOT[0] + 1.0, SPOT[1], SPOT[2]), tags=(TAG, GUARD), species="gyarados")
    guard["nbt"]["Pokemon"]["Species"] = "cobblemon:gyarados"
    passes(w, 2)
    assert guard in w.entities


def test_the_return_clock_is_an_hour_of_game_time():
    assert COOL == 72000 and MON["keeper"]["cooldown_ticks"] == 20 * 60 * 60


# ------------------------------------------------------------------ the wiring


def _reapply_text():
    return (ROOT / "tools" / "reapply.py").read_text(encoding="utf-8")


def test_reapply_names_the_step_the_pack_and_the_prepare_jobs():
    t = _reapply_text()
    assert t.count('"R18DQ"') == 1
    assert '"cobblers_drowned_quarry"' in t[t.index("SERVER_PACKS = ("):t.index("EXCLUDED = {")]
    assert '"cobblers_drowned_quarry"' in t[t.index("WORLD_LOCAL = ("):]
    assert 'add("drowned_quarry", "drowned_quarry.py", *src)' in t
    assert 'add("drowned_quarry_audit", "drowned_quarry_audit.py", *src)' in t
    import reapply
    assert "cobblers_drowned_quarry" in reapply.SERVER_PACKS and "cobblers_drowned_quarry" in reapply.WORLD_LOCAL
    assert "cobblers_drowned_quarry" not in reapply.EXCLUDED


def test_the_step_covers_every_function_of_the_pack(ground, tmp_path):
    import reapply
    doc = build(ground, tmp_path)
    steps = [("R18DQ", "t", D.placement_steps(doc, ground))]
    saved = reapply.PACKS
    try:
        reapply.PACKS = tmp_path / "packs_dq"
        target = reapply.PACKS / "cobblers_drowned_quarry"
        target.mkdir(parents=True)
        for f in tmp_path.rglob("*"):
            if f.is_file() and "packs_dq" not in f.parts:
                dest = target / f.relative_to(tmp_path)
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(f.read_bytes())
        assert reapply.uncovered(steps) == [] and reapply.unreferenced(steps) == []
    finally:
        reapply.PACKS = saved


def test_the_step_holds_carves_releases_then_runs_the_chain_and_reads_it_back(ground):
    steps = D.placement_steps(D.load(), ground)
    assert [s[0] for s in steps] == ["cmd", "wait", "fn", "cmd", "fn", "wait", "check"]
    assert steps[0][1].startswith("forceload add ") and steps[3][1] == steps[0][1].replace("add", "remove", 1)
    assert steps[2][1] == "cobblers:drowned_quarry/carve" and steps[4][1] == "cobblers:drowned_quarry/place"
    assert steps[6][1][:3] == ("chunk_look", "dq_gyarados", 1)
    # the held box covers every block the carve writes
    x0, z0, x1, z1 = (int(v) for v in steps[0][1].split()[2:])
    out = D.files(D.load(), ground)
    for rel, text in out.items():
        for line in text.splitlines():
            m = re.match(r"fill (-?\d+) (-?\d+) (-?\d+) (-?\d+) (-?\d+) (-?\d+) ", line)
            if m:
                a = [int(v) for v in m.groups()]
                assert x0 <= min(a[0], a[3]) and max(a[0], a[3]) <= x1 and z0 <= min(a[2], a[5]) and max(a[2], a[5]) <= z1, line


def test_the_probes_are_committed_and_match_the_generator(ground):
    committed = json.loads((ROOT / "data" / "world_probes.json").read_text(encoding="utf-8"))["places"]["drowned_quarry"]
    assert committed == D.probes(D.load(), ground)["drowned_quarry"]
    assert sum(1 for p in committed if "block" in p) >= 6 and sum(1 for p in committed if "entity" in p) == 1


def test_the_pack_has_no_concrete_and_no_barrier(ground):
    for rel, text in D.files(D.load(), ground).items():
        assert "concrete" not in text and "barrier" not in text, rel


def test_the_cell_label_is_read_from_the_cells_and_holds_every_write(ground):
    cells = json.loads((ROOT / "data" / "cells.json").read_text(encoding="utf-8"))["cells"]
    b = next(c for c in cells if c["id"] == REC["place"]["cell"])["bounds"]
    M = D.Model(D.load(), ground)
    assert b["min_x"] <= M.x0 and M.x1 <= b["max_x"] and b["min_z"] <= M.z0 and M.z1 <= b["max_z"]
