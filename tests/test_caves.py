"""The cave kit and its six caves, K1-K6 (tools/caves.py, tools/caves_audit.py, data/caves.json). The keeper tests run once per area
boss (Miraidon, Dialga, Koraidon) through the `boss_ctx` fixture; K4's Tapu Fini and Nihilego are a rare-spawn chamber.

Written by the same session that wrote the generator and the audit (the owner's brief, 2026-10-12: one unit built the kit, its
audit and its tests; CLAUDE.md principle 16 wants different agents, so a second agent should grade this file). What keeps it from
being a mirror of the generator:

  the build     the committed pack passes the audit, which derives every cell from data/caves.json's rules text and replays the
                pack both ways; and each GENERATOR mutation (the oval's width, a roof cell of the shell, a door cell, a lantern
                turned into a light block, a keeper that forgets the guardian, a gate that shuts people in, wrong clocks, a spawn
                that asks for no flag) makes the audit fail a NAMED check with data/caves.json untouched. A record-side mutation
                would move the expectation and the output together and prove nothing; the few data mutations here (a boss gated
                below the Champion, a wrong clock, a pool over the cap) test the record's validators, not independence.
  the keeper    the generated functions RUN on tests/gulch_sim.py's world model (the Drowned Quarry's harness): nothing spawns for a
                player without the gate flag, in front of anyone or for nobody; one dormant alpha at the chamber's centre for a
                champion; the clock is 24,000 ticks after a faint and 72,000 after a catch; a guardian is never held, woken,
                settled or killed and counts as present; a restart never moves a started clock.
  the gate      the barrier door opens for a flagged player in the antechamber, never for an unflagged one, and never closes on
                anyone inside.
  the wiring    the step, the pack lists and the prepare jobs in tools/reapply.py, every function reached, no spawn-condition block.
"""
from __future__ import annotations

import copy
import functools
import json
import os
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tests"))

import caves as C  # noqa: E402
import caves_audit as A  # noqa: E402
import gulch_sim as GS  # noqa: E402
import nbt_sim as N  # noqa: E402

SPEC = json.loads((ROOT / "data" / "caves.json").read_text(encoding="utf-8"))
CAVES = {c["id"]: c for c in SPEC["caves"]}
KITTED = [c for c in SPEC["caves"] if c.get("mode") != "natural"]      # K1-K6: an occupant, a Habitat Block, usually a gate
NATURALS = [c for c in SPEC["caves"] if c.get("mode") == "natural"]    # N1-N3: a mouth, a winding passage and a hall, nothing in them
BOSSES = [c for c in KITTED if c["occupant"]["mode"] == "area_boss"]
BOSS_IDS = [c["id"] for c in BOSSES]
OBJ = SPEC["gate"]["objective"]
CHAMPION = "cobblers:flag/champion_cleared"
GYM6 = "cobblers:flag/gym6_cleared"
GYM8 = "cobblers:flag/gym8_cleared"
GATED = [("cave_singing_hollow", GYM6), ("cave_strait_grotto", GYM8), ("cave_relay_fault", CHAMPION), ("cave_clock_cellar", CHAMPION), ("cave_sunscar", CHAMPION)]


def _ground():
    import ground as G
    import terrain as T
    try:
        return G.Ground(os.environ.get("COBBLERS_SOURCE_ROOT"))
    except T.TerrainUnavailable as e:
        pytest.skip("the canonical heightmap is unusable: %s" % e)


@pytest.fixture(scope="module")
def ground():
    return A.cached(_ground())


@functools.lru_cache(maxsize=None)
def _raw_ground():
    return _ground()


def make_pack(g, spec=None):
    """(fns, callback, plan) of the pack the generator makes from the committed record: geometry only, no clearance inputs."""
    spec = spec or SPEC
    plan = [{"cave": c, "geometry": C.geometry(spec, c, g)} for c in spec["caves"]]
    files = C.pack_files(spec, plan)
    pre = "data/cobblers/function/caves/"
    fns = {k[len(pre):-len(".mcfunction")]: v.splitlines() for k, v in files.items() if k.endswith(".mcfunction")}
    return fns, files.get("data/cobblemon/callbacks/pokemon_captured/cobblers_caves.molang", ""), plan


@pytest.fixture(scope="module")
def pack(ground):
    return make_pack(_raw_ground())


def audit(g, fns, cb, **kw):
    probs, _w = A.audit(SPEC, fns, cb, g, **kw)
    return probs


# ------------------------------------------------------------------ the record

def test_the_committed_record_is_valid():
    # without it a cave with a gate no flag opens, an unknown feature or a level over its gate's cap reaches the builder
    assert C.static_problems(SPEC) == []


def test_the_first_three_caves_are_the_designs_k1_k2_k3():
    # docs/mechanics/LEGENDARY_HOMES.md section 4 and the owner's decisions of 2026-10-12
    k1, k2, k3 = (CAVES[i] for i in ("cave_stoneford_cut", "cave_singing_hollow", "cave_relay_fault"))
    assert [c["kind"] for c in (k1, k2, k3)] == ["K1", "K2", "K3"]
    assert k1["gate"]["kind"] == "none" and k1["occupant"]["mode"] == "power_line" and k1["occupant"]["species"] == "gible"
    assert k2["gate"] == {"kind": "partition", "flags": ["gym6_cleared"]}
    assert (k2["occupant"]["mode"], k2["occupant"]["species"], k2["occupant"]["level"]) == ("rare_spawn", "meloetta", 50)
    assert k3["gate"] == {"kind": "partition", "flags": ["champion_cleared"]}
    assert (k3["occupant"]["mode"], k3["occupant"]["species"]) == ("area_boss", "miraidon")
    assert "alpha=true" in k3["occupant"]["properties"] and k3["occupant"]["level"] == 70
    assert (KEEP["cooldown_faint_ticks"], KEEP["cooldown_catch_ticks"]) == (24000, 72000)


def test_the_next_three_caves_are_the_designs_k4_k5_k6():
    # LEGENDARY_HOMES.md section 4 and the owner's / orchestrator's decisions of 2026-10-12; without it a gate flag, a level or a
    # boss slot could drift from what was decided (Tapu Fini at badge 8, Dialga and Koraidon after the Champion)
    k4, k5, k6 = (CAVES[i] for i in ("cave_strait_grotto", "cave_clock_cellar", "cave_sunscar"))
    assert [c["kind"] for c in (k4, k5, k6)] == ["K4", "K5", "K6"]
    assert k4["gate"] == {"kind": "partition", "flags": ["gym8_cleared"]}
    assert (k4["occupant"]["mode"], k4["occupant"]["species"], k4["occupant"]["level"]) == ("rare_spawn", "tapufini", 60)
    assert k4["occupant"]["co_occupants"] == ["nihilego"]
    for c, sp in ((k5, "dialga"), (k6, "koraidon")):
        assert c["gate"] == {"kind": "partition", "flags": ["champion_cleared"]}, c["id"]
        assert (c["occupant"]["mode"], c["occupant"]["species"], c["occupant"]["level"]) == ("area_boss", sp, 70), c["id"]
        assert "alpha=true" in c["occupant"]["properties"]
    assert set(BOSS_IDS) == {"cave_relay_fault", "cave_clock_cellar", "cave_sunscar"}


def test_every_boss_has_its_own_tags_and_the_same_respawn_clocks():
    # one keeper per boss: shared tags would make one boss's keeper count, hold or remove another's
    tags = [c["occupant"][k] for c in BOSSES for k in ("tag", "dormant_tag")]
    assert len(tags) == len(set(tags)) == 2 * len(BOSSES)
    for c in BOSSES:
        k = c["occupant"]["keeper"]
        assert (k["cooldown_faint_ticks"], k["cooldown_catch_ticks"]) == (24000, 72000), c["id"]
        assert c["occupant"]["guardian_tag"] == "cobblers.guardian", c["id"]


def test_every_cave_is_sited_with_its_site_recorded():
    for c in SPEC["caves"]:
        assert c["mouth"]["front"] in C.FRONTS and len(c["mouth"]["anchor"]) == 2, c["id"]
        assert c["site"]["subregion"] and c["site"]["subregion_band"][0] <= c["site"]["subregion_band"][1], c["id"]


def _edit(spec, cave, f):
    s = copy.deepcopy(spec)
    f(next(c for c in s["caves"] if c["id"] == cave))
    return s


@pytest.mark.parametrize("name,cave,edit,needle", [
    ("first passage is not an incline", "cave_stoneford_cut", lambda c: c["passages"][0].update(kind="drift"), "must be an incline"),
    ("an even width", "cave_stoneford_cut", lambda c: c["passages"][1].update(width=4), "must be odd"),
    ("a boss gated below the Champion", "cave_relay_fault", lambda c: c["gate"].update(flags=["gym8_cleared"]), "champion_cleared"),
    ("a boss that is not an alpha", "cave_relay_fault", lambda c: c["occupant"]["properties"].remove("alpha=true"), "native alpha"),
    ("the wrong respawn clock", "cave_relay_fault", lambda c: c["occupant"]["keeper"].update(cooldown_faint_ticks=12000), "24,000"),
    ("a guardian tag that is not the blackout's", "cave_relay_fault", lambda c: c["occupant"].update(guardian_tag="x"), "guardian_tag"),
    ("a flag no progression declares", "cave_singing_hollow", lambda c: c["gate"].update(flags=["gym6_cleared_typo"]), "not declared"),
    ("a partition with no antechamber", "cave_singing_hollow", lambda c: c.update(antechamber=None), "antechamber"),
    ("the pool feature is not built", "cave_singing_hollow", lambda c: c["chamber"].update(feature="pool"), "not built"),
    ("a chamber pool over the gate's cap", "cave_singing_hollow",
     lambda c: c["habitat"][1]["pool"]["entries"][0].update(level="51-60"), "over the gate's cap 50"),
    ("a rare-spawn occupant that is not ultra-rare", "cave_singing_hollow",
     lambda c: c["habitat"][1]["pool"]["entries"][-1].update(bucket="rare"), "ultra-rare"),
    ("a power line that is not a rare entry", "cave_stoneford_cut",
     lambda c: c["habitat"][0]["pool"]["entries"][-1].update(bucket="common"), "rare entry"),
    ("a co-occupant that is not ultra-rare", "cave_strait_grotto",
     lambda c: next(e for e in c["habitat"][1]["pool"]["entries"] if e["species"] == "Nihilego").update(bucket="rare"), "co-occupant nihilego"),
    ("a co-occupant that is not in the chamber's pool", "cave_strait_grotto",
     lambda c: c["occupant"].update(co_occupants=["buzzwole"]), "co-occupant buzzwole"),
    ("co-occupants on a boss cave", "cave_clock_cellar", lambda c: c["occupant"].update(co_occupants=["nihilego"]), "rare-spawn chamber only"),
    ("a chamber pool over the badge-8 cap", "cave_strait_grotto",
     lambda c: c["habitat"][1]["pool"]["entries"][0].update(level="55-61"), "over the gate's cap 60"),
    ("a boss slot gated below the Champion at the east dunes", "cave_sunscar", lambda c: c["gate"].update(flags=["gym8_cleared"]), "champion_cleared"),
])
def test_the_loader_refuses_a_record_that_breaks_a_rule(name, cave, edit, needle):
    # without it the kit would build a trap or an unwinnable boss from a record nobody could tell was wrong
    probs = C.static_problems(_edit(SPEC, cave, edit))
    assert any(needle in p for p in probs), (name, probs)


# ------------------------------------------------------------------ the build

def test_the_committed_pack_passes_the_independent_audit(pack, ground):
    fns, cb, _plan = pack
    assert audit(ground, fns, cb) == []


def test_the_pack_the_generator_makes_is_deterministic(ground):
    a = make_pack(_raw_ground())
    b = make_pack(_raw_ground())
    assert a[0] == b[0] and a[1] == b[1]


def _mutated(monkeypatch, ground, patch):
    patch(monkeypatch)
    fns, cb, _p = make_pack(_raw_ground())
    return audit(ground, fns, cb)


def _wrap_geometry(monkeypatch, fix):
    real = C.geometry

    def geometry(spec, cave, g, anchor=None, front=None, **kw):
        gm = real(spec, cave, g, anchor, front, **kw)
        if not kw.get("legacy"):                       # the retired mouth's cells (the restore) are not the cave a mutation is about
            fix(cave, gm)
        return gm
    monkeypatch.setattr(C, "geometry", geometry)


def _wrap_files(monkeypatch, name, fix):
    real = getattr(C, name)

    def wrapped(*a, **k):
        out = real(*a, **k)
        fix(out)
        return out
    monkeypatch.setattr(C, name, wrapped)


def test_a_wider_oval_is_caught_as_cells_outside_the_rules(monkeypatch, ground):
    # the audit's expectation is its own: widening the chamber inside the GENERATOR (rx + 2), the record untouched, must fail
    real = C.in_oval
    probs = _mutated(monkeypatch, ground, lambda mp: mp.setattr(C, "in_oval", lambda u, d, dc, rx, rz: real(u, d, dc, rx + 2, rz)))
    assert any("not in the rules" in p or "differ from the rules" in p for p in probs), probs


def test_a_roof_cell_of_the_shell_left_out_breaks_the_seal(monkeypatch, ground):
    def fix(cave, gm):
        if cave["id"] == "cave_singing_hollow":
            x, _y, z = gm["centre"]
            del gm["cells"][(x, gm["yh"] + cave["chamber"]["h"] + 1, z)]       # the cell over the middle of the chamber's roof
    probs = _mutated(monkeypatch, ground, lambda mp: _wrap_geometry(mp, fix))
    assert any("shell does not seal it" in p for p in probs) and any("not written" in p for p in probs), probs


def test_a_missing_door_cell_leaves_a_gap_the_gate_check_names(monkeypatch, ground):
    def fix(cave, gm):
        doors = [c for c, r in sorted(gm["cells"].items()) if r == "barrier"]
        if doors:
            gm["cells"][doors[0]] = "air"
    probs = _mutated(monkeypatch, ground, lambda mp: _wrap_geometry(mp, fix))
    assert any("door cell" in p or "barrier" in p for p in probs), probs


def test_a_door_that_is_never_built_lets_the_chamber_be_walked_to_with_the_door_closed(monkeypatch, ground):
    def fix(cave, gm):
        for c in [c for c, r in gm["cells"].items() if r == "barrier"]:
            gm["cells"][c] = "air"
    probs = _mutated(monkeypatch, ground, lambda mp: _wrap_geometry(mp, fix))
    assert any("reachable with the door closed" in p for p in probs), probs


def test_a_lantern_turned_into_a_light_block_is_refused(monkeypatch, ground):
    real = C.block_of
    probs = _mutated(monkeypatch, ground, lambda mp: mp.setattr(
        C, "block_of", lambda cave, role, front: "minecraft:light[level=15]" if role == "lantern" else real(cave, role, front)))
    assert any("light source" in p or "outside the palette" in p for p in probs), probs


def test_a_keeper_that_can_kill_a_guardian_is_refused(monkeypatch, ground):
    def fix(fn):
        for k, v in fn.items():
            fn[k] = [l.replace(",tag=!cobblers.guardian", "") if " kill " in l else l for l in v]
    probs = _mutated(monkeypatch, ground, lambda mp: _wrap_files(mp, "boss_files", fix))
    assert any("can reach a guardian" in p for p in probs), probs


def test_a_keeper_that_holds_a_guardian_is_refused(monkeypatch, ground):
    def fix(fn):
        for k, v in fn.items():
            fn[k] = [l.replace(",tag=!cobblers.guardian] run function", "] run function") for l in v]
    probs = _mutated(monkeypatch, ground, lambda mp: _wrap_files(mp, "boss_files", fix))
    assert any("can reach a guardian" in p for p in probs), probs


@pytest.mark.parametrize("bid", BOSS_IDS)
def test_a_keeper_that_adds_the_guardian_tag_is_refused(monkeypatch, ground, bid):
    # one mutation per boss keeper (the generator's output for THAT boss only), so each generated keeper is shown to be checked
    def fix(fn):
        k = "boss/%s/bind" % bid
        if k in fn:
            fn[k] = fn[k] + ["tag @s add cobblers.guardian"]
    probs = _mutated(monkeypatch, ground, lambda mp: _wrap_files(mp, "boss_files", fix))
    assert any("adds or removes cobblers.guardian" in p for p in probs), probs


@pytest.mark.parametrize("bid", BOSS_IDS)
def test_a_wrong_respawn_clock_is_refused(monkeypatch, ground, bid):
    def fix(fn):
        k = "boss/%s/keep" % bid
        if k in fn:
            fn[k] = [l.replace("24000", "12000") for l in fn[k]]
    probs = _mutated(monkeypatch, ground, lambda mp: _wrap_files(mp, "boss_files", fix))
    assert any("clocks" in p and bid in p for p in probs), probs


@pytest.mark.parametrize("bid", BOSS_IDS)
def test_a_spawn_that_asks_for_no_flag_is_refused(monkeypatch, ground, bid):
    def fix(fn):
        k = "boss/%s/keep" % bid
        if k in fn:
            fn[k] = [re.sub(r",advancements=\{[^}]*\}", "", l) for l in fn[k]]
    probs = _mutated(monkeypatch, ground, lambda mp: _wrap_files(mp, "boss_files", fix))
    assert any("holding" in p and bid in p for p in probs), probs


def test_a_gate_that_shuts_people_in_is_refused(monkeypatch, ground):
    def fix(fn):
        for k in list(fn):
            if k.endswith("/near"):
                fn[k] = [re.sub(r" unless entity @a\[[^\]]*gamemode=!spectator\]", "", l) for l in fn[k]]
    probs = _mutated(monkeypatch, ground, lambda mp: _wrap_files(mp, "gate_files", fix))
    assert any("inside zone" in p for p in probs), probs


def test_a_gate_opened_by_the_wrong_flag_is_refused(monkeypatch, ground):
    def fix(fn):
        for k in list(fn):
            if k.endswith("/near"):
                fn[k] = [l.replace("gym6_cleared", "gym5_cleared") for l in fn[k]]
    probs = _mutated(monkeypatch, ground, lambda mp: _wrap_files(mp, "gate_files", fix))
    assert any("exactly the flags" in p for p in probs), probs


def test_a_habitat_block_moved_from_its_floor_cell_is_refused(monkeypatch, ground, pack):
    fns, cb, _p = pack
    real = A.jload

    def jload(name):
        doc = real(name)
        if name == "habitat_blocks.json":
            doc = copy.deepcopy(doc)
            for b in doc["blocks"]:
                if b["id"] == "cave_relay_fault_chamber_ward":
                    b["position"]["x"] += 1
        return doc
    monkeypatch.setattr(A, "jload", jload)
    assert any("the rules put it at" in p for p in audit(ground, fns, cb)), "the moved block was not seen"


def test_a_pool_that_names_the_boss_is_refused(monkeypatch, ground, pack):
    fns, cb, _p = pack
    real = A.jload

    def jload(name):
        doc = real(name)
        if name == "spawns.json":
            doc = copy.deepcopy(doc)
            doc["entries"].append({"id": "habitat.cave_relay_fault_chamber.miraidon", "species": "miraidon", "bucket": "ultra-rare", "level": "70",
                                   "weight": 1.0, "ambient": True, "scope": "cave_relay_fault_chamber", "mechanism": "habitat_block",
                                   "conditions": {}, "eligibility_reason": "x", "spawnable_position": "grounded"})
        return doc
    monkeypatch.setattr(A, "jload", jload)
    probs = audit(ground, fns, cb)
    assert any("names a boss species" in p or "entries in data/spawns.json" in p for p in probs), probs


# ------------------------------------------------------------------ the records in the shared files

def test_the_derived_records_match_the_geometry(pack):
    # drift between the cave and the Habitat Blocks / pools / probes it keeps in other files is a fault (python tools/caves.py author)
    _fns, _cb, plan = pack
    assert C.record_problems(SPEC, plan) == []


def test_the_cave_records_in_the_shared_files_are_ours_only_and_complete():
    ours = {h["id"] for c in KITTED for h in c["habitat"]}
    blocks = {b["id"]: b for b in json.loads((ROOT / "data" / "habitat_blocks.json").read_text(encoding="utf-8"))["blocks"]}
    assert ours <= set(blocks) and all(blocks[i].get("generated_by") == "tools/caves.py" for i in ours)
    gen = {b["id"] for b in blocks.values() if b.get("generated_by") == "tools/caves.py"}
    assert gen == ours, "a generated Habitat Block the record no longer names: %s" % sorted(gen - ours)
    sp = json.loads((ROOT / "data" / "spawns.json").read_text(encoding="utf-8"))
    pools = {c["id"]: [h["pool"]["id"] for h in c["habitat"]] for c in KITTED}
    have = {h["id"] for h in sp["habitats"]}
    assert {p for ps in pools.values() for p in ps} <= have
    scopes = {e.get("scope") for e in sp["entries"]}
    assert {p for ps in pools.values() for p in ps} <= scopes


def test_the_occupants_levels_sit_under_their_gates_caps():
    caps = json.loads((ROOT / "data" / "legendaries.json").read_text(encoding="utf-8"))["level_caps"]["upper_bound_by_badges"]
    k2 = CAVES["cave_singing_hollow"]
    assert k2["occupant"]["level"] <= int(caps["6"])
    sp = json.loads((ROOT / "data" / "spawns.json").read_text(encoding="utf-8"))
    mel = next(e for e in sp["entries"] if e["id"] == "habitat.cave_singing_hollow_chamber.meloetta")
    assert mel["bucket"] == "ultra-rare" and mel["level"] == "50" and int(mel["level"]) <= int(caps["6"])
    gib = next(e for e in sp["entries"] if e["id"] == "habitat.cave_stoneford_cut_chamber.gible")
    assert gib["bucket"] == "rare" and gib["level"] == "9-14" and CAVES["cave_stoneford_cut"]["site"]["subregion_band"] == [9, 14]
    # K4: Tapu Fini and Nihilego are the chamber's only ultra-rare entries, both at the badge-8 cap, 1.0 weight each
    ents = [e for e in sp["entries"] if e.get("scope") == "cave_strait_grotto_chamber" and e["bucket"] == "ultra-rare"]
    assert sorted(e["species"] for e in ents) == ["nihilego", "tapufini"]
    assert all(e["level"] == "60" and int(e["level"]) <= int(caps["8"]) and e["weight"] == 1.0 for e in ents)


def test_no_pool_names_a_species_which_only_a_keeper_brings():
    # Miraidon, Dialga and Koraidon are the keepers' alone: a pool entry would be a second home for the same Pokemon
    sp = json.loads((ROOT / "data" / "spawns.json").read_text(encoding="utf-8"))
    mine = {h["pool"]["id"] for c in KITTED for h in c["habitat"]}
    bosses = {c["occupant"]["species"] for c in BOSSES}
    assert bosses == {"miraidon", "dialga", "koraidon"}
    assert not [e for e in sp["entries"] if e.get("scope") in mine and e["species"] in bosses]


def test_the_roster_gives_each_cave_occupant_exactly_that_cave_as_its_home_and_no_dungeon_pool_keeps_it():
    # data/dungeon_prize_roster.json is the 'one home each' record (LEGENDARY_HOMES.md section 1): the occupant of a cave must not
    # also be a dungeon's catch, and the roster must say where it lives. Dialga left the Temple Calendar's boss slot, Koraidon the
    # Zero Dig's pool, Tapu Fini the Temple Calendar's and Nihilego the Cistern's (their ub_boss FIGHT lines stay: not a catch).
    roster = json.loads((ROOT / "data" / "dungeon_prize_roster.json").read_text(encoding="utf-8"))
    placed = {}
    for c in KITTED:
        o = c["occupant"]
        if o["mode"] in ("rare_spawn", "area_boss"):
            placed[o["species"]] = c["id"]
            for co in o.get("co_occupants") or []:
                placed[co] = c["id"]
    assert {"miraidon", "dialga", "koraidon", "meloetta", "tapufini", "nihilego"} <= set(placed)
    for sp, cid in placed.items():
        rec = roster["species"][sp]
        assert rec["status"] == "to_world" and rec["home"].startswith(cid), (sp, rec)
        for d in roster["dungeons"]:
            pooled = {s for band in (d.get("legendary_pool_by_band") or {}).values() for s in band}
            pooled |= {s for band in (d.get("rare_pool_by_band") or {}).values() for s in band}
            assert sp not in pooled, "%s is still in %s's pool" % (sp, d["id"])
            bl = d.get("boss_legendary")
            assert not (bl and bl.get("species") == sp), "%s is still %s's boss legendary" % (sp, d["id"])
    assert roster["species"]["nihilego"]["model_gate"] == "atm_subset"


def test_the_inherited_spawns_of_the_cave_beasts_stay_off():
    # K4's two beasts are given a home by the cave; an inherited wild spawn beside it would be a second, uncatchable one (finding 2)
    sup = json.loads((ROOT / "data" / "spawn_suppression.json").read_text(encoding="utf-8"))
    off = set(sup["managed_species"]["species"]) | set(sup["removed_species"]["species"])
    assert {"tapufini", "nihilego", "koraidon", "miraidon"} <= off


# ------------------------------------------------------------------ the wiring

def test_no_block_the_pack_places_is_a_spawn_condition(pack):
    _f, _c, plan = pack
    assert C.pack_problems(SPEC, plan) == []


def _reapply():
    return (ROOT / "tools" / "reapply.py").read_text(encoding="utf-8")


def test_reapply_names_the_pack_the_step_and_the_prepare_jobs():
    src = _reapply()
    assert src.count('"cobblers_caves"') >= 2                    # SERVER_PACKS and WORLD_LOCAL
    assert 'add("caves:build", "caves.py", "build", *src)' in src and '"caves_audit.py"' in src
    assert '("R9CK",' in src and "caves.placement_steps()" in src
    assert src.index('("R9CK",') < src.index('("R9E",')        # the Habitat Blocks stand on cells the caves write
    assert src.index('("R9OC",') < src.index('("R9CK",')


def test_the_step_holds_builds_and_releases_each_cave(ground):
    steps = C.placement_steps(SPEC, _raw_ground())
    assert [s[0] for s in steps] == ["cmd", "wait", "fn", "cmd"] * len(SPEC["caves"])
    assert [s[1] for s in steps if s[0] == "fn"] == C.build_functions(SPEC)
    for (k1, v1), (k2, v2) in zip(steps[0::4], steps[3::4]):
        assert v1.startswith("forceload add ") and v2 == v1.replace("forceload add ", "forceload remove ")


def test_every_function_of_the_pack_is_run_by_a_step_or_named_by_another_file(pack):
    # tools/reapply.py unreferenced(): a function nothing calls is a silent loss. Re-derived here from the pack's own text
    fns, cb, _p = pack
    text = "\n".join("\n".join(v) for v in fns.values()) + "\n" + cb + json.dumps({"values": ["cobblers:caves/load"]})
    refs = set(re.findall(r"([a-z0-9_.-]+:[a-z0-9_./-]+)", text))
    run = set(C.build_functions(SPEC))
    lost = [n for n in fns if "cobblers:caves/%s" % n not in refs and "cobblers:caves/%s" % n not in run]
    assert lost == []


def test_the_load_tag_and_the_callback_are_in_the_pack(ground):
    spec = SPEC
    plan = [{"cave": c, "geometry": C.geometry(spec, c, _raw_ground())} for c in spec["caves"]]
    files = C.pack_files(spec, plan)
    assert json.loads(files["data/minecraft/tags/function/load.json"])["values"] == ["cobblers:caves/load"]
    cb = files["data/cobblemon/callbacks/pokemon_captured/cobblers_caves.molang"]
    for b in BOSSES:
        assert "cobblemon:%s" % b["occupant"]["species"] in cb and "cobblers:caves/boss/%s/caught" % b["id"] in cb, b["id"]
    for other in ("meloetta", "gible", "tapufini", "nihilego"):
        assert "cobblemon:%s" % other not in cb, other                # only a keeper's boss has a catch clock
    assert cb.count("'") % 2 == 0


# ------------------------------------------------------------------ the keeper and the gate, run

class Lake(GS.World):
    """tests/gulch_sim.py's world plus what Cobblemon adds that the pack reads: `nbt=` selector filters, a spawned Pokemon's Species
    and Level (the Drowned Quarry's harness), and `fill ... replace <block>` with a plain block filter."""

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
        if t[0] == "fill" and len(t) > 9 and t[8] == "replace" and not t[9].startswith("#"):
            x0, y0, z0, x1, y1, z1 = (int(v) for v in t[1:7])
            for x in range(min(x0, x1), max(x0, x1) + 1):
                for y in range(min(y0, y1), max(y0, y1) + 1):
                    for z in range(min(z0, z1), max(z0, z1) + 1):
                        if self.blocks.get((x, y, z), "minecraft:air") == t[9]:
                            self.blocks[(x, y, z)] = t[7]
            self.log.append(cmd)
            return None
        return super().command(cmd)

    def select(self, sel, origin=None):
        import re as _re
        m = _re.fullmatch(r"(@[aes])\[(.*)\]", sel)
        if not m or "nbt=" not in m.group(2):
            return super().select(sel, origin)
        f = GS.split_filters(m.group(2))
        pats = [N.parse_snbt(v) for k, v in f if k == "nbt"]
        rest = ",".join("=".join(kv) for kv in f if kv[0] not in ("nbt", "limit", "sort"))
        out = [e for e in super().select("%s[%s]" % (m.group(1), rest), origin) if all(N.matches(p, e.get("nbt", {})) for p in pats)]
        o = origin or self.pos
        sort = [v for k, v in f if k == "sort"]
        if sort:
            out.sort(key=lambda e: GS.math.dist(e["pos"], o), reverse=sort[0] == "furthest")
        lim = [int(v) for k, v in f if k == "limit"]
        return out[:lim[0]] if lim else out


@functools.lru_cache(maxsize=None)
def _fns_cached():
    fns, cb, plan = make_pack(_raw_ground())
    return fns, plan


def spot_of():
    fns, plan = _fns_cached()
    gm = next(p["geometry"] for p in plan if p["cave"]["id"] == BOSS["id"])
    return gm, (gm["centre"][0] + 0.5, gm["centre"][1] + 1, gm["centre"][2] + 0.5)


def world(gt=5_000_000):
    fns, _plan = _fns_cached()
    w = Lake({"caves/" + k: v for k, v in fns.items()})
    w.gt = gt
    w.call("caves/load")
    return w


def _bind(bid):
    """Point the module's boss globals at one area boss. The keeper tests run once per boss (Miraidon, Dialga, Koraidon): each
    cave has its own tags, clocks and spot, and a test that read only the first would leave the others unproved."""
    g = globals()
    g["BOSS"] = next(c for c in SPEC["caves"] if c["id"] == bid)
    g["OCC"] = g["BOSS"]["occupant"]
    g["KEEP"] = g["OCC"]["keeper"]
    g["BID"] = bid
    g["TAG"], g["DORM"], g["GUARD"] = g["OCC"]["tag"], g["OCC"]["dormant_tag"], g["OCC"]["guardian_tag"]
    g["PASS"] = g["KEEP"]["period_ticks"]
    g["GONE"], g["RESP"], g["CAUGHT"] = ("#%s_%s" % (bid, x) for x in ("gone", "resp", "caught"))


_bind(BOSS_IDS[0])


class as_boss:
    """`with as_boss(id):` runs a block against that boss and restores the previous one (tests/test_system_contracts.py C25)."""

    def __init__(self, bid):
        self.bid, self.prev = bid, None

    def __enter__(self):
        self.prev = BID
        _bind(self.bid)

    def __exit__(self, *exc):
        _bind(self.prev)


@pytest.fixture(params=BOSS_IDS)
def boss_ctx(request):
    with as_boss(request.param):
        yield request.param


KEEPER = pytest.mark.usefixtures("boss_ctx")


def bosses(w):
    return [e for e in w.entities if TAG in e["tags"]]


def score(w, holder):
    return w.score.get((holder, OBJ))


def passes(w, n):
    out = []
    for _ in range(n):
        w.gt += PASS
        w.call("caves/boss/%s/keeper" % BID)
        out.append(len(bosses(w)))
    return out


def player_at(w, dx, dz, dy=0.0, flags=(CHAMPION,), mode="survival"):
    _gm, spot = spot_of()
    return w.player((spot[0] + dx, spot[1] + dy, spot[2] + dz), flags=flags, mode=mode)


def summoned(w):
    """A boss on its spot, after one champion's approach."""
    p = player_at(w, KEEP["spawn_clear"] + 8, 0)
    # absent_passes loaded passes in a row before a missing one counts as missing (entities load a moment after their chunk)
    assert passes(w, KEEP["absent_passes"]) == [0] * (KEEP["absent_passes"] - 1) + [1]
    return bosses(w)[0], p


@KEEPER
def test_nothing_exists_at_load_and_the_clock_is_the_never_value():
    w = world()
    assert bosses(w) == [] and score(w, GONE) == C.NEVER


@KEEPER
def test_a_champion_who_comes_near_brings_one_dormant_alpha_boss_to_the_chamber_centre():
    w = world()
    _gm, spot = spot_of()
    b, _p = summoned(w)
    assert b["pos"] == spot and DORM in b["tags"] and b["nbt"]["PoseType"] == "SLEEP" and b["nbt"]["PersistenceRequired"] == N.Byte(1)
    assert b["nbt"]["Pokemon"]["Species"] == "cobblemon:%s" % OCC["species"] and b["nbt"]["Pokemon"]["Level"] == OCC["level"] == 70
    assert "alpha=true" in b["props"] and "no_ai" in b["props"] and any(p.startswith("moves=") for p in b["props"])
    assert score(w, GONE) == C.PRESENT


@KEEPER
def test_a_player_without_the_flag_never_brings_it_in():
    w = world()
    player_at(w, 20, 0, flags=())
    player_at(w, 22, 0, flags=(GYM6,))
    assert passes(w, 5) == [0] * 5


@KEEPER
def test_nobody_near_brings_nothing_and_a_spectator_champion_counts_for_nothing():
    w = world()
    player_at(w, KEEP["spawn_radius"] + 30, 0)
    player_at(w, 20, 0, mode="spectator")
    assert passes(w, 4) == [0] * 4


@KEEPER
def test_it_does_not_come_in_front_of_anyone():
    w = world()
    near = player_at(w, KEEP["spawn_clear"] - 4, 0)
    assert passes(w, 3) == [0, 0, 0]
    near["pos"] = (near["pos"][0] + 40, near["pos"][1], near["pos"][2])
    assert passes(w, 1) == [1]


@KEEPER
def test_a_second_summons_never_makes_a_second_one():
    w = world()
    summoned(w)
    assert passes(w, 6) == [1] * 6


@KEEPER
def test_it_wakes_for_a_player_in_the_chamber_and_not_for_one_outside_it():
    w = world()
    gm, spot = spot_of()
    b, p = summoned(w)
    assert DORM in b["tags"]
    p["pos"] = (spot[0] + 3.0, spot[1], spot[2] + 40.0)           # in the passage, outside the chamber's box
    passes(w, 2)
    assert DORM in b["tags"] and b["nbt"]["Unbattleable"] == N.Byte(1)
    p["pos"] = (spot[0] + 3.0, spot[1], spot[2])                  # inside the chamber's box
    zone = gm["chamber_zone"]
    p["pos"] = ((zone[0] + zone[3]) / 2 + 0.5, zone[1], (zone[2] + zone[5]) / 2 + 0.5)
    passes(w, 1)
    assert DORM not in b["tags"] and b["nbt"]["Unbattleable"] == N.Byte(0) and b["nbt"]["NoAI"] == N.Byte(1)


@KEEPER
def test_an_awake_one_is_not_dragged_home_through_the_fight_and_lies_down_when_everyone_has_gone():
    w = world()
    gm, spot = spot_of()
    b, p = summoned(w)
    zone = gm["chamber_zone"]
    p["pos"] = ((zone[0] + zone[3]) / 2 + 0.5, zone[1], (zone[2] + zone[5]) / 2 + 0.5)
    passes(w, 1)
    b["pos"] = (spot[0] + 2.0, spot[1], spot[2])
    passes(w, 3)
    assert b["pos"] == (spot[0] + 2.0, spot[1], spot[2]) and DORM not in b["tags"]
    p["pos"] = (spot[0] + KEEP["settle_radius"] + 30, spot[1], spot[2])
    passes(w, 1)
    assert DORM in b["tags"] and b["pos"] == spot and b["nbt"]["Unbattleable"] == N.Byte(1)


@KEEPER
def test_a_sleeping_one_moved_off_its_spot_is_put_back():
    w = world()
    _gm, spot = spot_of()
    b, _p = summoned(w)
    b["pos"] = (spot[0] + 4.0, spot[1] + 3.0, spot[2])
    passes(w, 1)
    assert b["pos"] == spot


def _gone_for(w, b, n=2):
    w.entities.remove(b)
    passes(w, n)                                                   # absent_passes loaded passes in a row


@KEEPER
def test_after_a_faint_it_returns_in_24000_ticks_and_not_before():
    w = world()
    b, p = summoned(w)
    _gone_for(w, b)
    t_gone = score(w, GONE)
    assert t_gone not in (C.PRESENT, C.NEVER) and score(w, RESP) == 24000
    p["pos"] = (p["pos"][0], p["pos"][1], p["pos"][2])
    while w.gt + PASS - t_gone < 24000:
        assert passes(w, 1) == [0], "it came back before its clock"
    assert passes(w, 1) == [1]
    assert score(w, GONE) == C.PRESENT


@KEEPER
def test_after_a_catch_it_returns_in_72000_ticks_and_not_before():
    w = world()
    b, p = summoned(w)
    # the pokemon_captured callback runs this as the catcher, near the spot, before the entity leaves the world
    w.me = p
    w.call("caves/boss/%s/caught" % BID)
    w.me = None
    assert score(w, CAUGHT) == 1
    # a faint-length wait is not enough
    _gone_for(w, b)
    t_gone = score(w, GONE)
    assert score(w, RESP) == 72000 and score(w, CAUGHT) == 0
    w.gt = t_gone + 24000 + 5 * PASS
    assert passes(w, 1) == [0], "a catch was treated as a faint"
    w.gt = t_gone + 72000 - PASS - 1
    assert passes(w, 1) == [0]
    w.gt = t_gone + 72000
    assert passes(w, 1) == [1]


@KEEPER
def test_a_catch_flag_left_while_the_boss_lives_is_cleared_and_never_stretches_the_next_clock():
    w = world()
    b, p = summoned(w)
    w.me = p
    w.call("caves/boss/%s/caught" % BID)                           # a released one caught again near the spot
    w.me = None
    passes(w, 1)
    assert score(w, CAUGHT) == 0
    _gone_for(w, b)
    assert score(w, RESP) == 24000


@KEEPER
def test_a_chunk_that_is_not_loaded_never_starts_the_clock():
    w = world()
    b, _p = summoned(w)
    w.loaded = lambda x, y, z: False
    w.entities.remove(b)
    passes(w, 6)
    assert score(w, GONE) == C.PRESENT


@KEEPER
def test_a_restart_never_moves_a_started_clock_or_the_never_value():
    w = world()
    assert score(w, GONE) == C.NEVER
    w.call("caves/load")
    assert score(w, GONE) == C.NEVER
    b, _p = summoned(w)
    _gone_for(w, b)
    t = score(w, GONE)
    w.call("caves/load")
    assert score(w, GONE) == t


@KEEPER
def test_a_guardian_is_never_held_woken_settled_or_killed():
    # C25: the boss that blacks a player out becomes the claim's guardian (tag cobblers.guardian); the keeper only counts it
    w = world()
    _gm, spot = spot_of()
    b, p = summoned(w)
    b["tags"].add(GUARD)
    b["pos"] = (spot[0] + 5.0, spot[1], spot[2])
    zone = _gm["chamber_zone"]
    p["pos"] = ((zone[0] + zone[3]) / 2 + 0.5, zone[1], (zone[2] + zone[5]) / 2 + 0.5)
    passes(w, 5)
    assert b in w.entities and b["pos"] == (spot[0] + 5.0, spot[1], spot[2]) and DORM in b["tags"]
    assert b["nbt"]["Unbattleable"] == N.Byte(1)
    p["pos"] = (spot[0] + 900, spot[1], spot[2])
    passes(w, 5)
    assert b in w.entities and b["pos"] == (spot[0] + 5.0, spot[1], spot[2])


@KEEPER
def test_a_guardian_the_blackout_rebuilt_counts_as_present_and_no_second_boss_spawns():
    w = world()
    _gm, spot = spot_of()
    b, p = summoned(w)
    w.entities.remove(b)
    rebuilt = w.pokemon((spot[0] + 6.0, spot[1], spot[2]), tags=(GUARD,), species=OCC["species"])
    rebuilt["nbt"]["Pokemon"]["Species"] = "cobblemon:%s" % OCC["species"]
    passes(w, 3)
    assert score(w, GONE) == C.PRESENT
    w.gt = 10 ** 8
    player_at(w, 30, 0)
    assert passes(w, 3) == [0, 0, 0] and len([e for e in w.entities if e["kind"] == "pokemon"]) == 1


@KEEPER
def test_a_duplicate_is_removed_and_never_a_guardian():
    w = world()
    _gm, spot = spot_of()
    b, _p = summoned(w)
    second = w.pokemon((spot[0] + 1.0, spot[1], spot[2]), tags=(TAG,), species=OCC["species"])
    second["nbt"]["Pokemon"]["Species"] = "cobblemon:%s" % OCC["species"]
    passes(w, 1)
    assert len(bosses(w)) == 1
    guard = w.pokemon((spot[0] + 1.0, spot[1], spot[2]), tags=(TAG, GUARD), species=OCC["species"])
    guard["nbt"]["Pokemon"]["Species"] = "cobblemon:%s" % OCC["species"]
    passes(w, 2)
    assert guard in w.entities


def test_the_keeper_never_names_the_blackouts_exempt_tag_or_changes_the_guardian_tag():
    fns, _plan = _fns_cached()
    text = "\n".join(l for n, v in fns.items() if n.startswith("boss/") for l in v if not l.startswith("#"))
    assert re.search(r"tag @s (add|remove) cobblers\.guardian", text) is None
    blackout = json.loads((ROOT / "data" / "blackout.json").read_text(encoding="utf-8"))
    exempt = blackout["claims"]["exempt_tag"]
    assert exempt not in text and exempt not in {TAG, DORM}


def _gate_world():
    fns, plan = _fns_cached()
    w = Lake({"caves/" + k: v for k, v in fns.items()})
    w.gt = 5_000_000
    w.call("caves/load")
    return w


@pytest.mark.parametrize("cid,flag", GATED)
def test_the_door_opens_for_a_flagged_player_in_the_antechamber_and_not_for_anyone_else(cid, flag):
    fns, plan = _fns_cached()
    gm = next(p["geometry"] for p in plan if p["cave"]["id"] == cid)
    w = _gate_world()
    door = [c for c, r in gm["cells"].items() if r == "barrier"]
    assert door
    for c in door:
        w.blocks[c] = "minecraft:barrier"
    z = gm["ante_zone"]
    mid = ((z[0] + z[3]) / 2 + 0.5, z[1], (z[2] + z[5]) / 2 + 0.5)
    other = {GYM6: "cobblers:flag/gym5_cleared", GYM8: "cobblers:flag/gym7_cleared"}.get(flag, GYM6)
    stranger = w.player(mid, flags=(other,))
    for _ in range(3):
        w.call("caves/tick")
    assert all(w.blocks[c] == "minecraft:barrier" for c in door), "the door opened for a player without the flag"
    stranger["pos"] = (mid[0] + 900, mid[1], mid[2])
    p = w.player(mid, flags=(flag,))
    w.call("caves/tick")
    assert all(w.blocks[c] == "minecraft:air" for c in door), "the door did not open for a flagged player in the antechamber"
    assert w.score.get(("#%s_open" % cid, OBJ)) == 1
    # walks out: it closes
    p["pos"] = (mid[0] + 900, mid[1], mid[2])
    w.call("caves/tick")


@pytest.mark.parametrize("cid,flag", GATED)
def test_the_door_never_closes_on_a_player_inside_and_closes_when_the_last_has_gone(cid, flag):
    fns, plan = _fns_cached()
    gm = next(p["geometry"] for p in plan if p["cave"]["id"] == cid)
    w = _gate_world()
    door = [c for c, r in gm["cells"].items() if r == "barrier"]
    for c in door:
        w.blocks[c] = "minecraft:barrier"
    z, ch = gm["ante_zone"], gm["chamber_zone"]
    ante = ((z[0] + z[3]) / 2 + 0.5, z[1], (z[2] + z[5]) / 2 + 0.5)
    inside = ((ch[0] + ch[3]) / 2 + 0.5, ch[1], (ch[2] + ch[5]) / 2 + 0.5)
    p = w.player(ante, flags=(flag,))
    w.call("caves/tick")
    assert all(w.blocks[c] == "minecraft:air" for c in door)
    p["pos"] = inside                                                # through the door, into the chamber
    for _ in range(3):
        w.call("caves/tick")
    assert all(w.blocks[c] == "minecraft:air" for c in door), "the door shut on a player inside"
    p["pos"] = (inside[0] + 25.0, inside[1], inside[2] + 25.0)       # wholly outside both zones, still within the driver's 48
    w.call("caves/tick")
    # the player is far enough that neither the antechamber nor the inside zone holds them: the driver (within 48) closes it
    assert all(w.blocks[c] == "minecraft:barrier" for c in door), "the door stayed open with nobody left"


def test_the_gates_driver_runs_only_while_somebody_is_near_the_chamber():
    fns, _plan = _fns_cached()
    tick = fns["tick"]
    gated = [c for c in KITTED if c["gate"]["kind"] == "partition"]
    for c in gated:
        line = next(l for l in tick if "/gate/%s/near" % c["id"] in l)
        assert re.search(r"if entity @a\[distance=\.\.%d\]" % SPEC["gate"]["reach"], line), line
    assert any("schedule function cobblers:caves/tick" in l for l in tick)


# ------------------------------------------------------------------ keeping clear of what the siting reads from other files

def _gm_stub(cave_id, x, z):
    gm = _fns_cached()[1]
    real = next(p["geometry"] for p in gm if p["cave"]["id"] == cave_id)
    return dict(real, columns=[(x, z)], centre=[x, real["centre"][1], z], ante_centre=[x, real["centre"][1], z])


def test_a_cave_inside_a_spawn_free_zone_is_refused():
    # without it a cave could be sited inside the League's precinct or a gym lot, where nothing may spawn: its Habitat Block
    # would be dead and its keeper would bring a wild alpha into a precinct the owner closed to wild Pokemon
    zones = json.loads((ROOT / "data" / "spawn_suppression.json").read_text(encoding="utf-8"))["spawn_free_zones"]
    z = zones[0]
    x0, z0, x1, z1 = z["box"]
    cave = CAVES["cave_stoneford_cut"]
    probs = C.foreign_problems(SPEC, cave, _gm_stub("cave_stoneford_cut", (x0 + x1) // 2, (z0 + z1) // 2))
    assert any("spawn-free zone %s" % z["id"] in p for p in probs), probs
    assert not C.foreign_problems(SPEC, cave, _gm_stub("cave_stoneford_cut", x0 - 400, z0 - 400))


def test_a_habitat_block_whose_reach_meets_a_natural_blocks_influence_is_refused(monkeypatch):
    # EXP-021: overlapping ReplaceSpawns influence spawns nothing; an activated block next to a natural one would starve or be starved
    cave = CAVES["cave_singing_hollow"]
    stub = _gm_stub("cave_singing_hollow", 100, 100)
    real = C.load

    def load(path=C.SPEC):
        doc = real(path)
        if Path(path) == C.HABITATS:
            doc = copy.deepcopy(doc)
            doc["blocks"].append({"id": "natural_neighbour", "style": "natural", "replace_spawns": True, "range_of_influence": 12,
                                  "position": {"x": 105, "y": stub["centre"][1], "z": 100}, "pool": "cobblers:x", "status": "planned"})
        return doc
    monkeypatch.setattr(C, "load", load)
    probs = C.foreign_problems(SPEC, cave, stub)
    assert any("natural_neighbour" in p for p in probs), probs


def test_the_audit_refuses_a_cave_inside_a_spawn_free_zone_too(monkeypatch, ground, pack):
    fns, cb, plan = pack
    k1 = next(p["geometry"] for p in plan if p["cave"]["id"] == "cave_stoneford_cut")
    x, _y, z = k1["centre"]
    real = A.jload

    def jload(name):
        doc = real(name)
        if name == "spawn_suppression.json":
            doc = copy.deepcopy(doc)
            doc["spawn_free_zones"].append({"id": "test_zone", "box": [x - 3, z - 3, x + 3, z + 3]})
        return doc
    monkeypatch.setattr(A, "jload", jload)
    assert any("spawn-free zone test_zone" in p for p in audit(ground, fns, cb)), "the audit did not see the zone"


def test_only_the_files_own_habitat_points_are_exempt_from_the_other_pack_rule():
    # breaks if: the exemption swallows a real neighbour (a write one column off an own point must still count),
    # or the caves' own Habitat Blocks in cobblers_habitats fail the build (2026-10-12 prepare, K1)
    import caves as CV
    pts = CV.own_habitat_points(CV.load() if hasattr(CV, "load") else __import__("json").loads(CV.SPEC.read_text(encoding="utf-8")))
    assert (1574, 3628) in pts and (1575, 3628) not in pts and (1574, 3629) not in pts


# ------------------------------------------------------------------ the natural caves (the owner, 2026-10-12)
# "We need to have caves on Northlight, Long Isle, and Sunset. They don't have to go anywhere or have a reward; just a cave would
# seem natural." A `natural` cave: a mouth, a winding passage, a dead-end hall; no gate, occupant, Habitat Block, reward or keeper.

NATURAL_IDS = {"cave_hoarfrost_hollow": ("N1", "south_pine_isle"), "cave_greenwither_cleft": ("N2", "long_isle_south"),
               "cave_dusk_burrow": ("N3", "sunset_west")}


def test_the_three_natural_caves_stand_on_the_three_islands_the_owner_named():
    # without it a natural cave could be sited on another island, or one of the three could be missing
    assert {c["id"] for c in NATURALS} == set(NATURAL_IDS)
    for c in NATURALS:
        kind, sub = NATURAL_IDS[c["id"]]
        assert c["kind"] == kind and c["site"]["subregion"] == sub, c["id"]
    assert {CAVES[i]["near"] for i in NATURAL_IDS} == {"pine_isles", "long_isle_south", "sunset_isle"}


def test_the_natural_caves_differ_in_size_and_each_one_winds():
    # "vary sizes so the three feel different": three distinct hall volumes and lengths, and a bend in each
    sizes = {(c["chamber"]["rx"], c["chamber"]["rz"], c["chamber"]["h"]) for c in NATURALS}
    lengths = {C.layout(SPEC, c)["total"] for c in NATURALS}
    assert len(sizes) == 3 and len(lengths) == 3, (sizes, lengths)
    for c in NATURALS:
        assert any(p.get("bend") for p in c["passages"][1:]), c["id"]
        assert C.layout(SPEC, c)["chamber"]["uc"] == sum(p.get("bend", 0) for p in c["passages"])


def test_a_natural_cave_carries_none_of_occupant_gate_habitat_antechamber_reward_keeper():
    # the committed record: a dead end with nothing in it (the owner: no reward, no occupant)
    for c in NATURALS:
        assert not set(C.NATURAL_FORBIDDEN) & set(c), c["id"]
        assert c["mode"] == "natural" and c["light"]["dark_by_design"] is True


@pytest.mark.parametrize("field,value", [
    ("occupant", {"mode": "power_line", "species": "gible"}), ("gate", {"kind": "none"}), ("habitat", []),
    ("antechamber", {"length": 4, "half_width": 3, "height": 5}), ("reward", {"item": "x"}), ("keeper", {})])
def test_a_natural_cave_with_a_forbidden_field_is_refused(field, value):
    # breaks if: a natural cave quietly grows an occupant, a gate or a reward; the loader must name the field
    probs = C.static_problems(_edit(SPEC, "cave_hoarfrost_hollow", lambda c: c.update({field: value})))
    assert any("a natural cave carries no %s" % field in p for p in probs), probs


@pytest.mark.parametrize("name,edit,needle", [
    ("no bend at all", lambda c: [p.pop("bend", None) for p in c["passages"]], "must carry a bend"),
    ("a bend longer than its passage", lambda c: c["passages"][1].update(bend=40), "moves at most one step"),
    ("a narrow bending passage", lambda c: c["passages"][1].update(width=1), "width >= 3"),
    ("lit by design", lambda c: c["light"].update(dark_by_design=False), "dark by design"),
    ("a mouth frame's timber in the palette", lambda c: c["palette"].update(timber="minecraft:spruce_log"), "no mouth frame"),
    ("no ore in the walls", lambda c: c["palette"].pop("vein"), "palette lacks vein"),
    ("a chamber feature of the kitted caves", lambda c: c["chamber"].update(feature="crystal"), "none or knobs"),
    ("an incline that bends", lambda c: c["passages"][0].update(bend=1), "incline does not bend"),
])
def test_the_loader_refuses_a_natural_cave_that_does_not_wind_or_is_lit(name, edit, needle):
    probs = C.static_problems(_edit(SPEC, "cave_greenwither_cleft", edit))
    assert any(needle in p for p in probs), (name, probs)


def test_a_kitted_cave_may_not_bend_or_take_the_natural_mode():
    # the antechamber and gate zones are straight boxes; a bend there would move the door from its zone
    probs = C.static_problems(_edit(SPEC, "cave_stoneford_cut", lambda c: c["passages"][1].update(bend=3)))
    assert any("only a natural cave may bend" in p for p in probs), probs
    probs = C.static_problems(_edit(SPEC, "cave_stoneford_cut", lambda c: c.update(mode="mystery")))
    assert any("is not 'natural'" in p for p in probs), probs


def test_nothing_in_the_shared_files_or_the_pack_names_a_natural_cave(pack):
    # no Habitat Block, no spawn pool or entry, no gate or boss function, no probe for a boss: a natural cave is a hole in the rock
    fns, cb, _p = pack
    hb = (ROOT / "data" / "habitat_blocks.json").read_text(encoding="utf-8")
    sp = (ROOT / "data" / "spawns.json").read_text(encoding="utf-8")
    for cid in NATURAL_IDS:
        assert cid not in hb and cid not in sp, cid
        own = {"build_%s" % cid, "restore_%s" % cid}                    # the build and the retired mouth's restore, and nothing else
        assert sorted(n for n in fns if cid in n) == sorted(own), [n for n in fns if cid in n]
        assert not any(cid in l for n, ls in fns.items() if n not in own for l in ls), cid
        assert cid not in cb
        assert "scoreboard players set #%s_open" % cid not in "\n".join(fns["build_%s" % cid])


def test_the_natural_caves_write_only_their_palette_and_air_and_no_light(pack):
    # dark by design: not a lantern, a post, a beam, a column, a door or a crystal; and every written block is the cave's own palette
    fns, _cb, _p = pack
    for c in NATURALS:
        written = A.replay(fns["build_%s" % c["id"]])
        used = {A.base(v) for v in written.values()}
        mouth = {A.base(b) for k in ("scree", "rubble") for b in c["hillside"][k]} | {A.base(c["terrain"]["surface"]), "minecraft:vine"}
        assert used <= set(A.base(v) for v in c["palette"].values()) | mouth | {"minecraft:air"}, (c["id"], used)
        assert not [b for b in used if any(w in b for w in A.LIGHT)], c["id"]


def test_the_natural_caves_dressing_is_present_and_shows(pack):
    # nonempty on purpose: ore only where it shows (an air neighbour), patches on floors, knobs standing on the hall's floor
    fns, _cb, plan = pack
    for e in plan:
        c = e["cave"]
        if c.get("mode") != "natural":
            continue
        w = A.replay(fns["build_%s" % c["id"]])
        vein, patch, knob = (A.base(c["palette"][k]) for k in ("vein", "patch", "knob"))
        cells = e["geometry"]["cells"]
        veins = [p for p, r in cells.items() if r == "vein"]
        assert veins and all(A.base(w[p]) == vein for p in veins), c["id"]
        for (x, y, z) in veins:
            assert any(w.get((x + a, y + b, z + d)) in A.PASS for a, b, d in ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1))), (c["id"], x, y, z)
        assert [p for p, r in cells.items() if r == "patch"], c["id"]
        knobs = [p for p, r in cells.items() if r == "knob"]
        assert 1 <= len(knobs) <= c["chamber"]["knob_count"] and all(p[1] == e["geometry"]["yh"] + 1 for p in knobs), c["id"]


def test_the_natural_caves_probes_are_in_the_probe_file_for_r9ck():
    # tools/presence_audit.py reads places.caves; R9CK builds the caves and the probes come from the same record
    probes = json.loads((ROOT / "data" / "world_probes.json").read_text(encoding="utf-8"))["places"]["caves"]
    for cid in NATURAL_IDS:
        mine = [p for p in probes if p["what"].startswith(cid + ":")]
        assert len(mine) == 8, (cid, len(mine))                           # stand, hall, two bends, floor, roof, and the mouth's lid and arch
        assert not [p for p in mine if "boss" in p["what"] or "Habitat" in p["what"] or "beam" in p["what"] or "door" in p["what"]]
    assert 'caves.placement_steps()' in _reapply()


def _natural_only(fix):
    def wrapped(cave, gm):
        if cave.get("mode") == "natural":
            fix(cave, gm)
    return wrapped


def test_a_generator_that_straightens_the_passage_is_caught(monkeypatch, ground):
    # mutate the GENERATOR (the bend is dropped from every row inside caves.layout), the record untouched: the audit's own
    # derivation of the offset rows must disagree, and its read of the written air must see a passage that does not wind
    real = C.layout

    def layout(spec, cave):
        lay = real(spec, cave)
        if C.is_natural(cave):
            for r in lay["rows"]:
                r["c"] = 0
            lay["chamber"]["uc"] = 0
        return lay
    probs = _mutated(monkeypatch, ground, lambda mp: mp.setattr(C, "layout", layout))
    assert any("not in the rules" in p or "differ from the rules" in p for p in probs), probs
    assert any("does not wind" in p or "never turns back" in p for p in probs), probs


def test_a_generator_that_changes_the_dressing_rule_is_caught(monkeypatch, ground):
    # mutate the hash the dressing keys on (inside tools/mines.h32 as caves.py calls it): ore and patches land on other cells
    real = C.M.h32

    def h32(*vals):
        return real(*vals) + (1 if len(vals) == 5 else 0)
    probs = _mutated(monkeypatch, ground, lambda mp: mp.setattr(C.M, "h32", h32))
    assert any("not in the rules" in p or "differ from the rules" in p or "not written" in p for p in probs), probs


def test_a_generator_that_hangs_a_lantern_in_a_natural_cave_is_caught(monkeypatch, ground):
    def fix(cave, gm):
        x, _y, z = gm["centre"]
        gm["cells"][(x, gm["yh"] + 3, z)] = "lantern"
    probs = _mutated(monkeypatch, ground, lambda mp: _wrap_geometry(mp, _natural_only(fix)))
    assert any("writes minecraft:lantern" in p for p in probs) and any("not in the rules" in p or "differ from the rules" in p for p in probs), probs


def test_a_generator_that_blocks_the_passage_is_caught_by_the_walk(monkeypatch, ground):
    # one whole row of a winding passage turned to rock: the hall can no longer be walked to from outside the mouth
    def fix(cave, gm):
        if cave["id"] != "cave_greenwither_cleft":
            return
        lay = gm["layout"]
        row = [r for r in lay["rows"] if r["kind"] == "level"][6]
        cells = gm["cells"]
        xz = C.M.frame(tuple(gm["anchor"]), gm["front"])
        for u in range(row["c"] - row["hw"], row["c"] + row["hw"] + 1):
            x, z = xz(u, row["d"])
            for y in range(row["ft"] + 1, row["ft"] + row["h"] + 1):
                cells[(x, y, z)] = "shell"
    probs = _mutated(monkeypatch, ground, lambda mp: _wrap_geometry(mp, fix))
    assert any("not walkable" in p for p in probs), probs


def test_a_generator_that_gives_a_natural_cave_a_keeper_is_caught(monkeypatch, ground):
    # a boss function for a cave that has no boss: the audit refuses it by name, whatever the record says
    def wrapped(*a, **k):
        out = real(*a, **k)
        out["data/cobblers/function/caves/boss/cave_dusk_burrow/keep.mcfunction"] = "say hello\n"
        return out
    real = C.pack_files
    monkeypatch.setattr(C, "pack_files", wrapped)
    fns, cb, _p = make_pack(_raw_ground())
    probs = audit(ground, fns, cb)
    assert any("boss functions exist for a natural cave" in p for p in probs), probs


def test_a_natural_cave_given_a_habitat_block_record_is_caught_by_the_audit(monkeypatch, ground, pack):
    fns, cb, _p = pack
    real = A.jload

    def jload(name):
        doc = real(name)
        if name == "habitat_blocks.json":
            doc = copy.deepcopy(doc)
            doc["blocks"].append({"id": "x", "place": "Dusk Burrow (cave_dusk_burrow, N3) in data/caves.json", "style": "activated"})
        return doc
    monkeypatch.setattr(A, "jload", jload)
    assert any("Habitat Block x names a natural cave" in p for p in audit(ground, fns, cb))


# ------------------------------------------------------------------ the hillside mouths (the owner, 2026-10-12)
# "I hate the cave look, it feels out of place": the first natural mouths were an open stone cutting in meadow. Now each is an opening in
# a grown hillside (lid, arch, mound, scree apron), the retired cutting is restored from the heightmap first (restore_<id>, run by
# build_<id>), and the audit reads the properties off the written cells: no air open to the sky, no cut or timber block, a walk to the hall.

LEGACY_CUTS = {"cave_hoarfrost_hollow": 7, "cave_greenwither_cleft": 7, "cave_dusk_burrow": 6}     # the applied cuttings, measured before the rework


def _natural_plan(pack):
    return [e for e in pack[2] if e["cave"].get("mode") == "natural"]


def test_each_natural_mouth_opens_no_cutting_and_is_roofed_over_its_opening(pack):
    # the generator's own cells: no cutting row, and the cell over the middle of the mouth's top air is rock, not sky
    for e in _natural_plan(pack):
        gm, c = e["geometry"], e["cave"]
        assert gm["cutting_rows"] == 0 and not any(r["cut"] for r in gm["layout"]["rows"]), c["id"]
        xz = C.M.frame(tuple(gm["anchor"]), gm["front"])
        h0 = gm["layout"]["rows"][0]["h"]
        x, z = xz(0, 0)
        assert gm["cells"][(x, gm["y0"] + h0, z)] == "air", c["id"]
        assert gm["cells"][(x, gm["y0"] + h0 + 1, z)].startswith("b:"), c["id"]


def test_each_natural_mouth_sits_in_a_slope_and_never_writes_a_cut_block(pack):
    # the incline's ground rises at least rise_min (measured on the heightmap) and no written block is cut, smooth, a stair or timber
    fns, _cb, _plan = pack
    nm = SPEC["geometry"]["natural_mouth"]
    for e in _natural_plan(pack):
        gm, c = e["geometry"], e["cave"]
        xz = C.M.frame(tuple(gm["anchor"]), gm["front"])
        hw = gm["layout"]["rows"][0]["hw"]
        rise = min(_raw_ground()(*xz(u, gm["layout"]["drop"])) for u in range(-hw, hw + 1)) - gm["y0"]
        assert rise >= nm["rise_min"], (c["id"], rise)
        used = {A.base(v) for v in A.replay(fns["build_%s" % c["id"]]).values()}
        assert not [b for b in used if any(w in b for w in A.BAD_NATURAL)], (c["id"], used)


def test_the_legacy_records_reproduce_the_cuttings_that_were_applied():
    # the restore takes down what the retired rules built: frozen numbers, so the demolition does not move when the record does
    for cid, cuts in LEGACY_CUTS.items():
        gm = C.legacy_geometry(SPEC, CAVES[cid], _raw_ground())
        assert gm["cutting_rows"] == cuts, cid


def test_the_restore_puts_terrain_back_and_a_second_run_changes_nothing(pack):
    # re-run safety: restore then build, twice over a world holding the retired cave, gives the same world, with nothing of the old
    # cutting left (every retired cell is rewritten by the restore or the build); the restore writes only the terrain's own blocks
    fns, _cb, _plan = pack
    g = _raw_ground()
    for c in NATURALS:
        cid = c["id"]
        old = C.legacy_geometry(SPEC, c, g)
        world = {cell: "OLD" for cell in old["cells"]}
        rest, build = A.replay(fns["restore_%s" % cid]), A.replay(fns["build_%s" % cid])
        once = {**world, **rest, **build}
        twice = {**once, **rest, **build}
        assert once == twice, cid
        assert "OLD" not in once.values(), cid
        tr = c["terrain"]
        assert {A.base(v) for v in rest.values()} <= {tr["deep"], tr["under"], tr["surface"], "minecraft:air"}, cid
        calls = [l for l in fns["build_%s" % cid] if l.startswith("function ")]
        assert calls == ["function cobblers:caves/restore_%s" % cid], (cid, calls)
        # the retired cutting's open air above the ground is air again wherever the new mouth does not stand
        for (x, y, z), r in old["cells"].items():
            if y > g(x, z) and (x, y, z) not in build:
                assert once[(x, y, z)] == "minecraft:air", (cid, x, y, z)


def test_the_reapply_step_holds_the_retired_mouth_too(ground):
    # the restore writes where the old cave stood: R9CK's forceload hold must cover both boxes
    steps = C.placement_steps(SPEC, _raw_ground())
    holds = {s[1] for s in steps if s[0] == "cmd" and s[1].startswith("forceload add")}
    for c in NATURALS:
        new = C.forceload_box(C.geometry(SPEC, c, _raw_ground()))
        old = C.forceload_box(C.legacy_geometry(SPEC, c, _raw_ground()))
        want = "forceload add %d %d %d %d" % (min(new[0], old[0]), min(new[1], old[1]), max(new[2], old[2]), max(new[3], old[3]))
        assert want in holds, (c["id"], want)


@pytest.mark.parametrize("name,edit,needle", [
    ("a stair in the rubble", lambda c: c["hillside"]["rubble"].append("minecraft:stone_stairs"), "no cut, smooth"),
    ("a brick in the scree", lambda c: c["hillside"]["scree"].append("minecraft:stone_bricks"), "no cut, smooth"),
    ("timber in the scree", lambda c: c["hillside"]["scree"].append("minecraft:spruce_planks"), "no cut, smooth"),
    ("no legacy", lambda c: c.pop("legacy"), "legacy.mouth is missing"),
    ("no terrain", lambda c: c.pop("terrain"), "terrain.surface is missing"),
    ("a stair in the palette", lambda c: c["palette"].update(stair="minecraft:stone_stairs"), "no mouth frame, lantern post, column or stair"),
    ("an incline too low to walk down", lambda c: c["passages"][0].update(height=2), "under 3 high"),
])
def test_the_loader_refuses_a_natural_mouth_that_is_built_not_found(name, edit, needle):
    probs = C.static_problems(_edit(SPEC, "cave_dusk_burrow", edit))
    assert any(needle in p for p in probs), (name, probs)


def test_a_mouth_the_ground_does_not_rise_into_is_refused_by_the_generator():
    # rise_min is the siting rule: an incline that enters flat ground is not an opening in a slope
    s = copy.deepcopy(SPEC)
    s["geometry"]["natural_mouth"]["rise_min"] = 9
    gm = C.geometry(s, next(c for c in s["caves"] if c["id"] == "cave_dusk_burrow"), _raw_ground())
    assert any("not in a slope" in p for p in gm["problems"]), gm["problems"]


def test_a_generator_that_opens_the_cutting_again_is_caught(monkeypatch, ground):
    # mutate the GENERATOR (the hillside mouth is not built, so the lid, mound and apron are gone and the air is open to the sky)
    probs = _mutated(monkeypatch, ground, lambda mp: mp.setattr(C, "hillside_mouth", lambda *a, **k: None))
    assert any("open to the sky" in p for p in probs), probs
    assert any("not written" in p or "differ from the rules" in p for p in probs), probs


def test_a_generator_that_picks_cut_stone_for_the_mouth_is_caught(monkeypatch, ground):
    probs = _mutated(monkeypatch, ground, lambda mp: mp.setattr(C, "pick", lambda lst, *k: "minecraft:stone_stairs"))
    assert any("the mouth writes minecraft:stone_stairs" in p for p in probs), probs


def test_a_generator_with_a_thin_lid_is_caught(monkeypatch, ground):
    # the cell two over the middle of the opening's top is left to the sky: the roof there is one block, not lid
    def fix(cave, gm):
        xz = C.M.frame(tuple(gm["anchor"]), gm["front"])
        x, z = xz(0, 0)
        gm["cells"].pop((x, gm["y0"] + gm["layout"]["rows"][0]["h"] + 2, z), None)
    probs = _mutated(monkeypatch, ground, lambda mp: _wrap_geometry(mp, _natural_only(fix)))
    assert any("solid blocks over them" in p or "open to the sky" in p for p in probs), probs


def test_a_generator_that_forgets_the_restore_is_caught(monkeypatch, ground):
    real = C.restore_lines
    probs = _mutated(monkeypatch, ground, lambda mp: mp.setattr(C, "restore_lines", lambda *a: real(*a)[:-6]))
    assert any("are not restored" in p or "not taken down" in p for p in probs), probs


def test_a_generator_whose_restore_writes_the_wrong_terrain_is_caught(monkeypatch, ground):
    real = C.restore_lines
    probs = _mutated(monkeypatch, ground, lambda mp: mp.setattr(
        C, "restore_lines", lambda *a: [l.replace("minecraft:stone", "minecraft:cobblestone") for l in real(*a)]))
    assert any("wrong block" in p for p in probs), probs


def test_a_build_that_does_not_call_its_restore_is_caught(monkeypatch, ground):
    real = C.build_lines
    probs = _mutated(monkeypatch, ground, lambda mp: mp.setattr(C, "build_lines", lambda *a: [l for l in real(*a) if not l.startswith("function ")]))
    assert any("does not call restore_" in p for p in probs), probs


def test_a_restore_that_reaches_outside_the_retired_mouth_is_caught(monkeypatch, ground):
    real = C.restore_lines
    probs = _mutated(monkeypatch, ground, lambda mp: mp.setattr(
        C, "restore_lines", lambda *a: real(*a) + ["fill 6700 80 1300 6700 80 1300 minecraft:stone"]))
    assert any("outside the retired mouth" in p for p in probs), probs
