"""Rare world spawns (the owner, 2026-10-12: a wild legendary is repeatable and very rare).

data/encounter_design.json `rare_spawns` -> tools/build_encounters.py -> data/spawns.json -> tools/compile_spawns.py.
Buzzwole and Pheromosa ride the Long Isle's jungle end (tier 8) as ultra-rare entries at a fractional weight, at the
level of the tier's cap, never alpha, with the AllTheMons model gate declared.

Independent sources: the level cap comes from tools/legendaries_audit.py rct_caps (the RCT config and our trainers, the
way rctmod computes it), not from the design's own rules.tiers; the species labels and the doll list come from the jar
and modpack/manifest/client-pack-atm-subset.json.

Mutations change the GENERATOR (tools/build_encounters.py), never the data.

NOT COVERED, and it needs a running server: that Cobblemon draws these at the rate computed here (RS-0, nobody has
measured spawns per player-hour), that Buzzwole/Pheromosa render for a player with the AllTheMons subset, and that the
inherited DP spawns are really gone from a live server.
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import build_encounters as BE  # noqa: E402
import compile_spawns as CS  # noqa: E402
import legendaries_audit as LA  # noqa: E402

DESIGN = json.loads((ROOT / "data" / "encounter_design.json").read_text(encoding="utf-8"))
DOLLS = set(json.loads((ROOT / "modpack" / "manifest" / "client-pack-atm-subset.json").read_text(encoding="utf-8"))["species"])
RARE = {r["species"]: r for r in DESIGN["rare_spawns"]}


@pytest.fixture(scope="module")
def dex():
    import battle_sim
    try:
        return BE.Dex(battle_sim.find_jar())
    except battle_sim.SimError as exc:
        pytest.skip("no Cobblemon 1.8 jar: labels and evolutions come from it (%s)" % exc)


@pytest.fixture(scope="module")
def pack(tmp_path_factory):
    out = tmp_path_factory.mktemp("rare_spawn_pack")
    CS.main(["--out", str(out)])
    return out / "data" / "cobblers"


def test_the_design_names_buzzwole_and_pheromosa_on_the_long_isle_south():
    # Without it the whole feature could be deleted and every test below that loops over RARE would pass vacuously.
    assert sorted(RARE) == ["buzzwole", "pheromosa"]
    assert {r["table"] for r in RARE.values()} == {"long_isle_south"}


def test_the_committed_spawns_are_what_the_design_expands_to():
    assert BE.main(["--check"]) == 0, "data/spawns.json differs from data/encounter_design.json: run tools/build_encounters.py"


def test_a_generator_that_drops_the_rare_spawns_is_noticed(monkeypatch):
    # Mutates the generator: with it the committed spawns no longer match, so the check above is not vacuous.
    monkeypatch.setattr(BE, "build_rare_spawns", lambda dex, rules, design, dolls: ({}, []))
    assert BE.main(["--check"]) == 1


def test_each_rare_spawn_is_a_legendary_at_the_cap_after_gym_7_and_very_rare(dex):
    caps = LA.rct_caps()
    for sp, r in RARE.items():
        labels = set(dex.record(sp)[0].get("labels") or [])
        assert labels & {"legendary", "mythical", "ultra_beast"}, "%s: %s" % (sp, sorted(labels))
        assert r["level"] == caps["gym7_cleared"], "%s: level %s is not the cap after gym 7 (%s)" % (sp, r["level"], caps["gym7_cleared"])
        assert 0 < r["weight"] <= 0.1
        assert r["model_gate"] == "atm_subset" and sp in DOLLS, "%s: the gate and the doll list disagree" % sp


def test_the_compiled_pool_has_each_one_as_a_plain_ultra_rare_overworld_spawn(pack):
    # Without it a rare spawn could compile as an alpha (uncatchable below the Champion), in the wrong bucket, at the
    # wrong level, or bound to every dimension (the dungeon pockets and the Nether).
    d = json.loads((pack / "spawn_pool_world" / "subregions" / "long_isle_south.json").read_text(encoding="utf-8"))
    for sp, r in RARE.items():
        rows = [s for s in d["spawns"] if s["pokemon"].split()[0] == sp]
        assert rows, "%s is not in the compiled long_isle_south pool" % sp
        for s in rows:
            assert s["pokemon"] == sp, "%s compiled as %r (an alpha or modified spawn)" % (sp, s["pokemon"])
            assert s["bucket"] == "ultra-rare" and s["level"] == "%d-%d" % (r["level"], r["level"]) and s["weight"] == r["weight"]
            assert s["condition"]["dimensions"] == ["minecraft:overworld"], s["condition"]
    # per box: the legendaries' share of the ultra-rare bucket stays under one tenth of the table's own family
    by_box = {}
    for s in d["spawns"]:
        if s["bucket"] == "ultra-rare":
            box = s["id"].split("_b")[1].split("_")[0]
            by_box.setdefault(box, {"leg": 0.0, "all": 0.0})
            by_box[box]["all"] += s["weight"]
            if s["pokemon"] in RARE:
                by_box[box]["leg"] += s["weight"]
    assert by_box and all(0 < v["leg"] / v["all"] < 0.11 for v in by_box.values()), by_box


# ------------------------------------------------------------------------------------------------ fail closed


def problems(dex, mutate):
    design = copy.deepcopy(DESIGN)
    mutate(design)
    return BE.build_rare_spawns(dex, design["rules"], design, DOLLS)[1]


def test_the_committed_rare_spawns_have_no_problems(dex):
    assert problems(dex, lambda d: None) == []


@pytest.mark.parametrize("name,mutate,needle", [
    ("an unknown table", lambda d: d["rare_spawns"][0].update(table="nowhere"), "not a design table"),
    ("a species that is not a legendary", lambda d: d["rare_spawns"][0].update(species="pikachu", model_gate=None), "not a legendary"),
    ("a level above the tier cap", lambda d: d["rare_spawns"][0].update(level=60), "not table"),
    ("a level below the tier cap", lambda d: d["rare_spawns"][0].update(level=54), "not table"),
    ("a weight over the ceiling", lambda d: d["rare_spawns"][0].update(weight=0.5), "max_weight"),
    ("a zero weight", lambda d: d["rare_spawns"][0].update(weight=0), "max_weight"),
    ("a doll with no model gate", lambda d: d["rare_spawns"][0].update(model_gate=None), "substitute doll"),
    ("a gate on a species the doll list does not name", lambda d: d["rare_spawns"][0].update(species="mewtwo"), "NOT named"),
    ("the same species twice", lambda d: d["rare_spawns"].append(dict(d["rare_spawns"][0], id="again")), "twice"),
])
def test_a_bad_rare_spawn_fails_closed(dex, name, mutate, needle):
    got = problems(dex, mutate)
    assert any(needle in p for p in got), "%s: %s" % (name, got)
