"""tools/pack_roles.py: which installed packs a strip may take out of the heap, and that it fails closed.

Written by the same session that wrote the classifier (the brief asked for both; CLAUDE.md prefers a different agent):
an independent review of these cases is still owed.

Fixtures are tiny synthetic packs under tmp_path. Each test names the property it protects; the cost of getting one
wrong is a runtime function stripped out of a live server: a keeper, a callback or a door that answers "Unknown
function" in the middle of play.
"""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import pack_roles as PR  # noqa: E402


def write_pack(base: Path, name: str, files: dict):
    p = base / name
    (p).mkdir(parents=True)
    (p / "pack.mcmeta").write_text('{"pack": {"pack_format": 48, "description": "%s"}}' % name, encoding="utf-8")
    for rel, body in files.items():
        f = p / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(body, (dict, list)):
            body = json.dumps(body)
        f.write_text(body, encoding="utf-8")
    return (name, p)


def fn(ns, path):
    return "data/%s/function/%s.mcfunction" % (ns, path)


def tick(*ids):
    return {"data/minecraft/tags/function/tick.json": {"values": list(ids)}}


def roles(tmp_path, packs, steps=None):
    return PR.classify([write_pack(tmp_path, n, f) for n, f in packs], steps, config_dirs=())


def role(rep, name):
    return rep["packs"][name]["role"]


# ------------------------------------------------------------------ reachability across packs

CROSS = [
    ("p_keeper", dict(tick("keeper:tick"), **{fn("keeper", "tick"): "execute as @a run function placer:spot\n"})),
    ("p_placer", {fn("placer", "spot"): "setblock 1 2 3 stone\n", fn("placer", "shell"): "fill 0 0 0 9 9 9 stone\n"}),
    ("p_oneshot", {fn("oneshot", "shell"): "fill 0 0 0 9 9 9 stone\n" * 50}),
]


def test_a_pack_reached_only_through_another_packs_tick_is_runtime(tmp_path):
    # without it: the placer pack holds no tag of its own, looks one-shot, and a strip removes a function a keeper in
    # another pack calls every tick
    rep = roles(tmp_path, CROSS)
    assert_cross(rep)
    assert rep["packs"]["p_oneshot"]["lines"] == 50


def assert_cross(rep):
    assert role(rep, "p_keeper") == "runtime"
    assert role(rep, "p_placer") == "runtime"
    assert role(rep, "p_oneshot") == "build"


def test_mutation_ignoring_cross_pack_calls_is_caught(tmp_path, monkeypatch):
    # the mutation the brief asked for, applied to the CLASSIFIER (not the fixture): drop every edge into another
    # pack. The cross-pack property above must then fail -- proving that test bites
    real_load = PR.load

    def no_cross(packs):
        g = real_load(packs)
        for f, refs in list(g.edges.items()):
            src = g.functions.get(f)
            if src is not None:
                g.edges[f] = {r for r in refs if g.functions.get(r, src) == src}
        return g
    monkeypatch.setattr(PR, "load", no_cross)
    rep = roles(tmp_path, CROSS)
    with pytest.raises(AssertionError):
        assert_cross(rep)


def test_a_macro_function_call_reaches_every_function_its_pattern_matches(tmp_path):
    # without it: `$function door:room/$(id)` names no literal id, and every room it opens looks unreachable
    rep = roles(tmp_path, [
        ("p_tick", dict(tick("t:tick"), **{fn("t", "tick"): "function t:open {id:\"a\"}\n",
                                            fn("t", "open"): "$function door:room/$(id)\n"})),
        ("p_door", {fn("door", "room/a"): "say a\n", fn("door", "room/b"): "say b\n"}),
        ("p_other", {fn("other", "room/a"): "say not matched\n"}),
    ])
    assert role(rep, "p_door") == "runtime"
    assert rep["packs"]["p_door"]["reachable_functions"] == 2
    assert role(rep, "p_other") == "build"


def test_a_function_tag_reaches_its_values_in_another_pack(tmp_path):
    rep = roles(tmp_path, [
        ("p_tick", dict(tick("t:tick"), **{fn("t", "tick"): "function #grp:all\n"})),
        ("p_grp", {"data/grp/tags/function/all.json": {"values": ["member:go"]}}),
        ("p_member", {fn("member", "go"): "say go\n"}),
    ])
    assert role(rep, "p_member") == "runtime"


def test_an_unparseable_call_in_a_runtime_function_makes_everything_runtime(tmp_path):
    # fail closed: `function $(f)` could be any function at all, so no pack is provably build-only
    rep = roles(tmp_path, [
        ("p_tick", dict(tick("t:tick"), **{fn("t", "tick"): "function t:dispatch {f:\"x:y\"}\n",
                                            fn("t", "dispatch"): "$function $(f)\n"})),
        ("p_oneshot", {fn("oneshot", "shell"): "fill 0 0 0 1 1 1 stone\n"}),
    ])
    assert rep["everything_reachable"] is True
    assert role(rep, "p_oneshot") == "runtime"
    assert rep["unresolved"]


def test_a_macro_command_that_is_itself_a_macro_value_fails_closed(tmp_path):
    rep = roles(tmp_path, [
        ("p_tick", dict(tick("t:tick"), **{fn("t", "tick"): "function t:run {cmd:\"say\"}\n",
                                            fn("t", "run"): "$execute as @a run $(cmd)\n"})),
        ("p_oneshot", {fn("oneshot", "shell"): "fill 0 0 0 1 1 1 stone\n"}),
    ])
    assert role(rep, "p_oneshot") == "runtime"


def test_a_function_named_inside_a_command_block_placed_by_a_build_function_is_a_root(tmp_path):
    # the build function itself runs once, but the command block it places runs in the world forever after
    rep = roles(tmp_path, [
        ("p_build", {fn("b", "place"): 'setblock 1 2 3 command_block{Command:"function cb:fire"}\n'}),
        ("p_cb", {fn("cb", "fire"): "say fire\n"}),
    ])
    assert role(rep, "p_cb") == "runtime"
    assert role(rep, "p_build") == "build"


def test_a_click_event_in_a_text_component_is_a_root(tmp_path):
    rep = roles(tmp_path, [
        ("p_build", {fn("b", "sign"): 'tellraw @a {"text":"x","clickEvent":{"action":"run_command","value":"/function cl:go"}}\n'}),
        ("p_cl", {fn("cl", "go"): "say go\n"}),
    ])
    assert role(rep, "p_cl") == "runtime"


def test_runtime_data_names_roots_and_is_runtime_itself(tmp_path):
    rep = roles(tmp_path, [
        ("p_adv", {"data/a/advancement/x.json": {"criteria": {"c": {"trigger": "minecraft:tick"}},
                                                 "rewards": {"function": "rew:give"}}}),
        ("p_rew", {fn("rew", "give"): "give @s stone\n"}),
        ("p_cb", {"data/cobblemon/callbacks/battle_victory/x.molang":
                  "q.run_command('function cbk:won/' + t.id);"}),
        ("p_cbk", {fn("cbk", "won/a"): "say a\n", fn("cbk", "other"): "say b\n"}),
    ])
    assert role(rep, "p_adv") == "runtime"            # an advancement is runtime data
    assert role(rep, "p_rew") == "runtime"            # its reward function is a root
    assert role(rep, "p_cbk") == "runtime"            # a string-built name reaches everything under its prefix
    assert rep["packs"]["p_cbk"]["reachable_functions"] == 1


def test_a_kind_the_tool_does_not_know_is_runtime(tmp_path):
    rep = roles(tmp_path, [("p_new", {"data/n/some_new_registry/x.json": {"a": 1}, fn("n", "f"): "say\n"})])
    assert role(rep, "p_new") == "runtime"


def test_a_block_tag_is_runtime_only_when_a_runtime_function_names_it(tmp_path):
    rep = roles(tmp_path, [
        ("p_tick", dict(tick("t:tick"), **{fn("t", "tick"): "execute if block 1 2 3 #used:void run say\n"})),
        ("p_used", {"data/used/tags/block/void.json": {"values": ["minecraft:air"]},
                    fn("used", "fill"): "fill 0 0 0 1 1 1 stone replace #used:void\n"}),
        ("p_unused", {"data/unused/tags/block/void.json": {"values": ["minecraft:air"]},
                      fn("unused", "fill"): "fill 0 0 0 1 1 1 stone replace #unused:void\n"}),
    ])
    assert role(rep, "p_used") == "runtime"
    assert role(rep, "p_unused") == "build"


def test_a_file_two_packs_ship_at_one_path_keeps_both_loaded_unless_it_is_a_merging_tag(tmp_path):
    # last-wins files depend on pack order, and a pack put back after a strip is enabled in a different place
    rep = roles(tmp_path, [
        ("p_a", {fn("same", "f"): "say a\n", "data/same/tags/block/t.json": {"values": ["minecraft:air"]},
                 "data/same/function/index.txt": "f\n"}),
        ("p_b", {fn("same", "f"): "say b\n"}),
        ("p_c", {fn("other", "g"): "say c\n", "data/same/tags/block/t.json": {"values": ["minecraft:stone"]},
                 "data/same/function/index.txt": "g\n"}),
    ])
    assert role(rep, "p_a") == "runtime" and role(rep, "p_b") == "runtime"
    assert role(rep, "p_c") == "build"                 # a merging tag and an index.txt are not overrides


def test_the_steps_closure_names_every_pack_a_step_reaches(tmp_path):
    rep = roles(tmp_path, [
        ("p_steps", {fn("s", "go"): "function deep:shell\n"}),
        ("p_deep", {fn("deep", "shell"): "fill 0 0 0 1 1 1 stone\n"}),
        ("p_alone", {fn("alone", "x"): "say\n"}),
    ], steps={"R1": ["s:go"], "R2": ["alone:x"]})
    assert rep["steps"]["R1"] == ["p_deep", "p_steps"]
    assert rep["packs"]["p_deep"]["apply_steps"] == ["R1"]
    assert role(rep, "p_deep") == "build"              # an apply-time root is NOT a runtime root


def test_scan_line_separates_calls_from_embedded_names():
    calls, emb, unres = PR.scan_line('execute as @a[tag=x] if function a:check run function b:go {n:"c:d"}')
    assert calls == ["a:check", "b:go"] and emb == ["c:d"] and not unres
    calls, _e, _u = PR.scan_line("schedule function a:later 5t replace")
    assert calls == ["a:later"]
    calls, _e, _u = PR.scan_line("function tick")
    assert calls == ["minecraft:tick"]
    _c, _e, unres = PR.scan_line("function")
    assert unres
