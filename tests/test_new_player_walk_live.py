"""The fresh player's walk, Pallet to the Champion, on the real game -- every run of the suite.

The owner, 2026-10-05: "Can a new player get a starter, reach gym 1, and beat it -- and onward to the Champion. That
answer should be known continuously, not discovered once." This runs tools/new_player_walk.py's every stage:

  - on the BUILT packs when a full build exists (build/datapacks holding every pack in W.REQUIRED_PACKS, or the
    directory COBBLERS_WALK_PACKS names), which is what prepare installs;
  - otherwise on what COMMITTED DATA builds (W.build_from_data into a temporary directory: never build/), where a pack
    that needs kits/ or the server is reported NOT_MODELLED by name.

and fails on any FAIL the tool's KNOWN list does not hold, or a KNOWN entry that now passes. It needs the canonical
heightmap and the Cobblemon jar; without either it SKIPS and says which. It is slow (about three minutes: every fight
of the campaign through tools/battle_sim.py).

NOT COVERED (validity is not behaviour): everything new_player_walk.py's docstring lists -- whether a player can
actually walk any of it, whether rctmod spawns, fires and moves the cap, whether Cobblemon applies the forms. A PASS
here says the built files and the coarse models allow the path; the in-game proof is an experiment.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import new_player_walk as W  # noqa: E402

ORDER = ["spawn_to_oak", "starter"] + [s for n in range(1, 9) for s in ("route_%d" % n, "gym_%d" % n)] + \
        ["victory_road", "league", "multiplayer"]


@pytest.fixture(scope="module")
def walked(tmp_path_factory):
    env = os.environ.get("COBBLERS_WALK_PACKS")
    built = Path(env) if env else ROOT / "build" / "datapacks"
    if all((built / p).is_dir() for p in W.REQUIRED_PACKS):
        packs, unbuilt, mode = built, {}, "built"
    else:
        packs = tmp_path_factory.mktemp("walk_packs")
        unbuilt, mode = W.build_from_data(packs), "data"
    inp = W.Inputs(packs=packs, unbuilt=unbuilt)
    try:
        inp.ground
    except (Exception, SystemExit) as e:
        pytest.skip("no canonical heightmap here (%s): the walk cannot run" % e)
    try:
        inp.jar()
    except Exception as e:
        pytest.skip("no Cobblemon 1.8 jar here (%s): the fights cannot run" % e)
    return mode, unbuilt, W.run(inp)


def test_the_walk_from_pallet_to_the_champion_has_no_new_fail(walked):
    # without this, a new blocker on the critical path is found by a player instead of by the suite
    mode, unbuilt, stages = walked
    failed, _known, fixed = W.triage(stages)
    lines = ["%s %s: %s" % (s.verdict, s.id, s.summary()) for s in stages if s.id in failed]
    lines += ["FIXED? %s %s: remove it from KNOWN" % k for k in fixed]
    assert not failed and not fixed, "(%s mode, unbuilt %s)\n%s" % (mode, sorted(unbuilt), "\n".join(lines))


def test_every_stage_from_pallet_to_the_champion_ran_in_order(walked):
    # without this, a stage dropped from run() would leave a shorter walk reading as a clean one
    _mode, _unbuilt, stages = walked
    assert [s.id for s in stages] == ORDER


def test_data_mode_leaves_only_the_town_pack_unbuilt(walked):
    # without this, a generator that broke in data mode would turn its checks NOT_MODELLED instead of failing
    mode, unbuilt, _stages = walked
    if mode == "built":
        pytest.skip("the built packs were walked: nothing was generated here")
    assert set(unbuilt) == {"cobblers_towns"}, unbuilt
