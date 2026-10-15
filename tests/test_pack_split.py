"""tools/pack_split.py and the dungeon engine's split (tools/dungeon.py build_only).

Written by the same session that wrote the split (the brief asked for both): an independent review is still owed.
What a mistake costs: a function the keeper calls lands in the strippable pack, and the dungeon's door answers
"Unknown function" once the build half is stripped.
"""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import pack_split as PS  # noqa: E402


def pack(tmp_path, files):
    p = tmp_path / "cobblers_thing"
    p.mkdir()
    (p / "pack.mcmeta").write_text(json.dumps({"pack": {"pack_format": 48, "description": "x"}}), encoding="utf-8")
    for rel, body in files.items():
        f = p / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(body, encoding="utf-8")
    return p


FN = "data/cobblers/function/thing/%s.mcfunction"


def is_shell(fid):
    return fid.startswith("cobblers:thing/shells/") or fid == "cobblers:thing/place"


def test_split_moves_the_named_functions_under_the_same_ids(tmp_path):
    p = pack(tmp_path, {FN % "place": "function cobblers:thing/shells/s1\n", FN % "shells/s1": "fill 0 0 0 1 1 1 stone\n",
                        FN % "keeper": "# the shells are placed by cobblers:thing/place (a comment is no call)\nsay hi\n",
                        "data/cobblers/function/thing/index.txt": "place\nshells/s1\n",
                        "data/minecraft/tags/function/tick.json": '{"values": ["cobblers:thing/keeper"]}'})
    n, out = PS.split(p, is_shell, "the build half")
    assert n == 2 and out.name == "cobblers_thing_build"
    assert (out / (FN % "shells/s1")).is_file() and (out / (FN % "place")).is_file()      # same relative path = same id
    assert not (p / (FN % "shells/s1")).exists()
    assert (p / (FN % "keeper")).is_file() and (p / "data/cobblers/function/thing/index.txt").is_file()
    assert json.loads((out / "pack.mcmeta").read_text(encoding="utf-8"))["pack"]["pack_format"] == 48
    assert not (out / "data" / "minecraft").exists()                                    # tags stay with the runtime


def test_split_refuses_when_the_runtime_half_calls_a_moved_function(tmp_path):
    p = pack(tmp_path, {FN % "shells/s1": "fill 0 0 0 1 1 1 stone\n",
                        FN % "reset": "execute in cobblers:pocket run function cobblers:thing/shells/s1\n"})
    with pytest.raises(SystemExit) as e:
        PS.split(p, is_shell, "x")
    assert "reset" in str(e.value.code)
    assert (p / (FN % "shells/s1")).is_file(), "nothing moved"
    assert not (tmp_path / "cobblers_thing_build").exists()


def test_split_refuses_a_macro_or_string_built_name_under_a_moved_prefix(tmp_path):
    p = pack(tmp_path, {FN % "shells/s1": "fill 0 0 0 1 1 1 stone\n",
                        FN % "any": "$function cobblers:thing/shells/$(slot)\n"})
    with pytest.raises(SystemExit):
        PS.split(p, is_shell, "x")
    p2 = tmp_path / "b"
    p2.mkdir()
    p2 = pack(p2, {FN % "shells/s1": "fill\n",
                   "data/cobblemon/callbacks/x.molang": "q.run_command('function cobblers:thing/shells/' + v.s);"})
    with pytest.raises(SystemExit):
        PS.split(p2, is_shell, "x")


def test_a_longer_id_that_merely_starts_with_a_moved_one_is_not_a_call(tmp_path):
    p = pack(tmp_path, {FN % "shells/s1": "fill\n", FN % "shells/s1x": "say\n",
                        FN % "keep": "function cobblers:thing/shells/s1x_runtime\n"})
    n, _out = PS.split(p, lambda f: f == "cobblers:thing/shells/s1", "x")
    assert n == 1


# ------------------------------------------------------------------ the dungeon engine's split

def test_dungeon_build_only_takes_the_shell_and_rip_placement_and_nothing_a_run_calls():
    import dungeon as D
    steps = dict((sid, acts) for sid, _t, acts in D.reapply_steps())
    # R16DR runs the retire of the 13 trail rips (build: one-shot), the retire's entity sweep (a scheduled chain: runtime) and, since
    # 2026-10-14, the rip scheduler's init, which is in ANOTHER pack (cobblers_rips: runtime, tools/rip_scheduler.py)
    fns = [v for sid in ("R16DG", "R16DR") for k, v in steps[sid] if k == "fn" and v.startswith(D.F(""))]
    placement = [f for f in fns if "/entities" not in f]
    chains = [f for f in fns if "/entities" in f]
    assert placement and all(D.build_only(f) for f in placement), placement
    # the look-then-act chains stay with the runtime pack: their scheduled steps must not outlive a stripped pack
    assert chains and not any(D.build_only(f) for f in chains), chains
    assert D.SCHEDULER_INIT == "cobblers:rips/init" and not D.build_only(D.SCHEDULER_INIT)
    for runtime in ("load", "keeper", "slot/s1/reset", "slot/s1/reserve", "room/ash_bell/ash_bowl/s13/reset",
                    "rips/emit", "door/ab", "shells/entities", "shells/entities/look", "rips/entities_retired"):
        assert not D.build_only(D.F(runtime)), runtime
    for one_shot in ("place", "place/s1", "place/s27", "shells/build", "shells/s1", "shells/s1/clear",
                     "shells/s13/the_heart", "rips/retire", "rips/retire_ns"):
        assert D.build_only(D.F(one_shot)), one_shot


def test_dungeon_build_pack_is_installed_beside_its_runtime_pack():
    import reapply as R
    assert "cobblers_dungeons_build" in R.SERVER_PACKS and "cobblers_dungeons_build" in R.WORLD_LOCAL
