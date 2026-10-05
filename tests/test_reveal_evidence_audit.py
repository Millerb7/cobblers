"""tools/reveal_evidence_audit.py: the independent audit of the reveal evidence displays' BUILT pack.

Written by a session that did not build the displays. Three layers:

  synthetic   a hand-written function file and hand-made inputs (flat ground y64, one route line), with every
              expected number computable by hand; each defect the audit exists for is injected once and must be named
  real        tools/reveal_evidence.py's own output, built into a temporary directory, must audit clean
  mutation    the GENERATOR is mutated (its code, never data/): the offset, the overwrite guard, the ground it emits,
              the removal it targets. Each mutated build must FAIL the audit for every display it moves. A mutation
              of data would move the expectation with the output and prove nothing (CLAUDE.md "How to prove an
              audit is independent").

Not covered: what the guards decide at run time (a flower or slab already on a column makes a display silently not
appear); that needs a world probe after reapply step R17NE, not pytest.
"""
from __future__ import annotations

import inspect
import json
import math
import re
import sys
import textwrap
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import reveal_evidence_audit as A  # noqa: E402

# ---------------------------------------------------------------- the synthetic fixture

SIGN = ("minecraft:spruce_sign[rotation=0,waterlogged=false]"
        "{front_text:{messages:['\"BOUNDARY CORE\"','\"shale and soil\"','\"\"','\"\"']}}")
# A teller at (100, 65, 100) facing south (yaw 0) on flat ground y64. Its left is east, so the prop stands at
# (102, 100) and the sign one block in front of it, at (102, 101).
GOOD = "\n".join([
    "# hand-written fixture",
    "execute if block 102 65 101 minecraft:spruce_sign if block 102 66 100 minecraft:coarse_dirt run setblock 102 66 100 minecraft:air",
    "execute if block 102 65 101 minecraft:spruce_sign if block 102 65 100 minecraft:tuff run setblock 102 65 100 minecraft:air",
    "execute if block 102 65 101 minecraft:spruce_sign run setblock 102 65 101 minecraft:air",
    "execute if block 102 65 100 #minecraft:replaceable unless block 102 64 100 #minecraft:replaceable run setblock 102 65 100 minecraft:tuff",
    "execute if block 102 66 100 #minecraft:replaceable if block 102 65 100 minecraft:tuff run setblock 102 66 100 minecraft:coarse_dirt",
    "execute if block 102 65 101 #minecraft:replaceable unless block 102 64 101 #minecraft:replaceable run setblock 102 65 101 " + SIGN,
]) + "\n"


def synthetic_inputs(**over):
    inputs = {
        "doc": {"sign_wood": "spruce", "displays": [{
            "beat": "brock", "evidence": "brock_boundary_sample", "teller": "npc_t", "side": "left",
            "prop": ["minecraft:tuff", "minecraft:coarse_dirt"], "sign": ["BOUNDARY CORE", "shale and soil"]}]},
        "quest": {"physical_evidence": [{"id": "brock_boundary_sample", "site": "gym1_town"}]},
        "tellers": {"dlg_main_brock_fixture": "npc_t"},
        "seats": {"npc_t": {"at": [100, 65, 100], "yaw": 0, "settlement": "gym1_town",
                            "ground": {"kind": "heightmap", "y": 64}},
                  "npc_other": {"at": [120, 65, 120], "yaw": 0, "settlement": "gym1_town",
                                "ground": {"kind": "heightmap", "y": 64}}},
        "paths": {"r": [[100, 0], [100, 90]]},
        "towns": {"gym1_town": {"plaza_centres": None,
                                "plan": {"streets": {}, "lots": [], "anchors": [], "lamps": []}}},
        "gyms": [],
        "spawn_blocks": {"minecraft:coarse_dirt"},
        "whitelist": [],
        "ground": lambda x, z: 64,
    }
    inputs.update(over)
    return inputs


def write_pack(tmp_path, text, beat="brock"):
    f = tmp_path / A.FN_DIR / ("%s.mcfunction" % beat)
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(text, encoding="utf-8")
    return tmp_path


# Guards the fixture itself: if the clean case is not clean, every negative case below proves nothing.
def test_the_hand_written_display_audits_clean_with_hand_computed_numbers(tmp_path):
    r = A.audit(write_pack(tmp_path, GOOD), synthetic_inputs())
    assert r["problems"] == []
    (row,) = r["rows"]
    assert row["prop"] == (102, 65, 100) and row["sign"] == (102, 65, 101)
    # nearest point of the line (100, 0)-(100, 90) to the prop (102, 100) is its end (100, 90): hypot(2, 10)
    assert row["route"] == round(math.hypot(2, 10), 2) == 10.2
    assert row["ground"] == ["heightmap y64"]


# Guards the owner's ALLOW decision: a spawn-condition block outside every whitelist is reported, never failed.
def test_a_spawn_condition_block_is_reported_not_failed(tmp_path):
    r = A.audit(write_pack(tmp_path, GOOD), synthetic_inputs())
    assert r["problems"] == []
    assert any("minecraft:coarse_dirt" in x and "spawn-condition" in x for x in r["reports"])


def _replace(old, new):
    def f(text):
        assert old in text
        return text.replace(old, new)
    return f


DEFECTS = [
    # (what is injected, how, inputs override, words the problem must contain)
    ("a route line through the prop", None, {"paths": {"r": [[90, 100], [110, 100]]}}, "ON walked line r (0.00)"),
    ("ground one lower than the display assumes", None, {"ground": lambda x, z: 63}, "heightmap ground there is y63"),
    ("a plan street under the sign", None,
     {"towns": {"gym1_town": {"plaza_centres": None, "plan": {
         "streets": {"lane": {"cells": [[101, 64, 95, 105]]}}, "lots": [], "anchors": [], "lamps": []}}}},
     "on street lane"),
    ("a plaza square at a different level", None,
     {"towns": {"gym1_town": {"plaza_centres": {"square": {"rect": [95, 95, 110, 110], "y": 70}, "pieces": []},
                              "plan": {"streets": {}, "lots": [], "anchors": [], "lamps": []}}}},
     "plaza_centres square ground there is y70"),
    ("another NPC seated on the prop's column", None,
     {"seats": {"npc_t": {"at": [100, 65, 100], "yaw": 0, "settlement": "gym1_town", "ground": {"kind": "heightmap", "y": 64}},
                "npc_other": {"at": [102, 65, 100], "yaw": 0, "settlement": "gym1_town", "ground": {"kind": "heightmap", "y": 64}}}},
     "seat npc_other"),
    ("a teller the quest does not name", None, {"tellers": {"dlg_main_brock_fixture": "npc_somebody"}},
     "spoken by ['npc_somebody']"),
    ("the sign's text changed", _replace('"shale and soil"', '"shale and sand"'), {}, "the built sign reads"),
    ("the prop moved into the teller's 3x3", _replace(" 102 ", " 101 "), {}, "the 3x3 round it"),
    ("the prop moved three further out", _replace(" 102 ", " 105 "), {}, "offset (+5, +0)"),
    ("the overwrite guard dropped", _replace("execute if block 102 65 100 #minecraft:replaceable unless",
                                             "execute unless"), {}, "without checking the block is replaceable"),
    ("the support check dropped", _replace(" unless block 102 64 101 #minecraft:replaceable", ""), {},
     "without checking what it stands on"),
    ("a removal outside the footprint", lambda t: t + "execute if block 104 65 100 minecraft:stone run setblock 104 65 100 minecraft:air\n",
     {}, "outside its own footprint"),
    ("a block the data does not declare", _replace("setblock 102 65 100 minecraft:tuff", "setblock 102 65 100 minecraft:stone"),
     {}, "the data declares minecraft:tuff"),
    ("an unguarded command", lambda t: t + "setblock 103 65 100 minecraft:stone\n", {}, "not a guarded setblock"),
]


# Guards each property the audit exists for: removing it lets that defect through unseen.
@pytest.mark.parametrize("name,edit,over,words", DEFECTS, ids=[d[0] for d in DEFECTS])
def test_each_injected_defect_is_named(tmp_path, name, edit, over, words):
    text = edit(GOOD) if edit else GOOD
    r = A.audit(write_pack(tmp_path, text), synthetic_inputs(**over))
    assert any(words in p for p in r["problems"]), (name, r["problems"])


# Guards against a missing build reading as a pass: no pack, no function, is a failure.
def test_a_missing_built_function_fails(tmp_path):
    (tmp_path / A.FN_DIR).mkdir(parents=True)
    r = A.audit(tmp_path, synthetic_inputs())
    assert any("no built function" in p for p in r["problems"])


# Guards QUEST_TERMS from becoming the audit's own invention: every term must occur in the quest record it cites.
def test_every_quest_term_is_in_the_quest_record():
    quest = next(q for q in json.loads((ROOT / "data" / "quests.json").read_text(encoding="utf-8"))["quests"]
                 if q["id"] == A.QUEST_ID)
    records = {e["id"]: json.dumps(e).lower() for e in quest["physical_evidence"]}
    displayed = {d["evidence"] for d in json.loads((ROOT / "data" / "reveal_evidence.json").read_text(encoding="utf-8"))["displays"]}
    assert displayed <= set(A.QUEST_TERMS)
    for ev, terms in A.QUEST_TERMS.items():
        for t in terms:
            assert t in records[ev], "%s: %r is not in the quest's record" % (ev, t)


# Guards independence by construction: the audit must never take its expectation from the builder's code.
def test_the_audit_does_not_import_the_builder():
    src = (ROOT / "tools" / "reveal_evidence_audit.py").read_text(encoding="utf-8")
    assert not re.search(r"^\s*(import reveal_evidence\b|from reveal_evidence\b)", src, re.M)


# ---------------------------------------------------------------- the real build, and the generator mutated

def _have_real_inputs():
    if not (ROOT / "derived" / "plaza_centres").is_dir() or not (ROOT / "derived" / "towns").is_dir():
        return "derived/plaza_centres and derived/towns are absent (a fresh worktree): copy them in"
    try:
        A.heightmap()
    except (OSError, SystemExit) as e:  # the canonical heightmap is outside the repo; any other error is a fault
        return "canonical heightmap unavailable: %s" % e
    return None


SKIP = _have_real_inputs()
needs_real = pytest.mark.skipif(SKIP is not None, reason=SKIP or "")


@pytest.fixture(scope="module")
def real_inputs():
    return A.load_inputs()


@pytest.fixture(scope="module")
def builder_ground():
    import ground as G
    return G.load()


@pytest.fixture
def RE(monkeypatch):
    import reveal_evidence as RE
    return RE


def build(RE, ground, out):
    RE.write(RE.files(RE.plan(g=ground)), out)
    return out


def mutate(monkeypatch, RE, fn, old, new):
    """Replace one fragment of a generator function's source and install the mutant (data untouched)."""
    src = textwrap.dedent(inspect.getsource(getattr(RE, fn)))
    assert src.count(old) >= 1, "%s no longer contains %r: re-aim the mutation" % (fn, old)
    ns = {}
    exec(compile(src.replace(old, new), RE.__file__, "exec"), RE.__dict__, ns)
    monkeypatch.setattr(RE, fn, ns[fn])


BEATS = [d["beat"] for d in json.loads((ROOT / "data" / "reveal_evidence.json").read_text(encoding="utf-8"))["displays"]]


def _failing_beats(r, words):
    words = (words,) if isinstance(words, str) else words
    return {p.split(" ", 1)[0] for p in r["problems"] if any(w in p for w in words)}


# Guards the real pack: the builder's own output must pass the independent audit.
@needs_real
def test_the_real_build_audits_clean(tmp_path, RE, builder_ground, real_inputs):
    r = A.audit(build(RE, builder_ground, tmp_path / "pack"), real_inputs)
    assert r["problems"] == []
    assert len(r["rows"]) == len(BEATS) == 8


MUTATIONS = [
    # (the generator change, function, old fragment, new fragment or attribute value, words, beats that must fail)
    ("prop offset 2 -> 5 (LATERAL)", "LATERAL", None, 5, "offset", "all"),
    ("overwrite guard skipped (writes over anything but bedrock)", "lines_for",
     '"execute if block %d %d %d #minecraft:replaceable unless block',
     '"execute unless block %d %d %d minecraft:bedrock unless block',
     "without checking the block is replaceable", "all"),
    ("ground emitted one block high", "plan", "cols[name] = (x, gy + 1, z, src)", "cols[name] = (x, gy + 2, z, src)",
     "ground there is", "all"),
    # brock's and sabrina's signs stand WEST of their props, so one block east is the prop itself: inside the
    # footprint, and named instead as a removal that does not match its own block there
    ("sign removal aimed one block east", "lines_for", "sign_id, sx, sy, sz))", "sign_id, sx + 1, sy, sz))",
     ("outside its own footprint", "without matching its own block there"), "all"),
    # only erika's columns differ: at sabrina's and blaine's display columns the rounded heightmap equals the plaza
    # y (94, 107), so this mutant emits the same y there and there is nothing to catch
    ("plaza columns given heightmap ground", "column_ground",
     '    if kind == "plaza":\n        py = site.plaza(x, z)', '    if kind == "plaza":\n        py = None',
     "ground there is", ["erika"]),
]


# Guards independence: each mutation of the GENERATOR (data untouched) must turn the audit red for every display it
# moves. If one passes, the audit shares the builder's derivation for that property and proves nothing about it.
@needs_real
@pytest.mark.parametrize("name,fn,old,new,words,beats", MUTATIONS, ids=[m[0] for m in MUTATIONS])
def test_a_mutated_generator_fails_the_audit(tmp_path, monkeypatch, RE, builder_ground, real_inputs,
                                             name, fn, old, new, words, beats):
    if old is None:
        monkeypatch.setattr(RE, fn, new)
    else:
        mutate(monkeypatch, RE, fn, old, new)
    r = A.audit(build(RE, builder_ground, tmp_path / "pack"), real_inputs)
    want = set(BEATS) if beats == "all" else set(beats)
    assert want <= _failing_beats(r, words), (name, sorted(_failing_beats(r, words)), r["problems"][:4])
