"""Activated Habitat Blocks in tools/habitat_blocks.py, and the habitat-pool timeRange passthrough in
tools/compile_spawns.py compile_habitat.

Written by the test author, not by the session that added the activated style (commit f6358c9).

Independent sources: docs/STATE.md's world fact "Never switch a placed Habitat Block's style with `data merge`"
(staging, 2026-09-26: an activated style merged onto a ticked block crashed the tick and kicked a player; the working
recipe is another block first, then one setblock with the whole NBT, PhaseOrder included; the activated keys Chance,
Trigger, CancelRange, SpawnRange, MaxSpawns, MaxSpawnsPerActivation); EXP-021 (overlapping natural ReplaceSpawns
ranges spawn nothing); and the Cobblemon 1.8.0 jar's own habitat_pools for the pool spawn keys.

What is asserted: static_problems accepts a well-formed activated block and names each malformed one; the overlap rule
applies only between natural ReplaceSpawns blocks and measures in three dimensions (the tool's current rule; see the
note on the overlap test); commands() places an activated block as exactly the mimic then one full-NBT setblock and
never `data merge`, for synthetic blocks, for every activated block of data/habitat_blocks.json, and in the function
file `habitat_blocks.py function` writes; compare() and world_problems() flag a mismatched MaxSpawns; rcon_problems
asks the cancels_regular_spawns state test once when false is expected and retries it when true is; compile_habitat
writes an entry's conditions.timeRange into the pool spawn only when present, under a key the jar's pools use.

Not covered, and it needs a running server: that the two setblocks build a ticking spawner in Cobblemon 1.8.0 (staging
evidence only, 2026-09-26), that an activated block survives a chunk reload or a restart, that a timeRange in a pool
spawn is honoured, and whether a natural block's reach is a sphere or a column (EXP-033).
"""
from __future__ import annotations

import copy
import json
import sys
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tests"))

import compile_spawns as CS  # noqa: E402
import habitat_blocks as HB  # noqa: E402
from test_habitat_blocks import world_with  # noqa: E402

SPAWNS = {"habitats": [{"id": "elder_x"}, {"id": "elder_y"}, {"id": "great_crater_bowls"}]}
MANIFEST = json.loads((ROOT / "data" / "habitat_blocks.json").read_text(encoding="utf-8"))


def act(bid="nest", x=1094, y=134, z=3496, pool="cobblers:elder_x", **over):
    b = {"id": bid, "pool": pool, "style": "activated", "replace_spawns": False, "position": {"x": x, "y": y, "z": z},
         "mimic": "minecraft:oak_log", "status": "placed",
         "activated": {"spawn_range": 16, "max_spawns": 7, "max_spawns_per_activation": 1, "chance": 1.0,
                       "trigger": "TICK", "cancel_range": -1}}
    b.update(over)
    return b


def nat(bid="field", x=1746, y=109, z=4815, r=16, pool="cobblers:great_crater_bowls", replace=True):
    return {"id": bid, "pool": pool, "style": "natural", "replace_spawns": replace, "range_of_influence": r,
            "position": {"x": x, "y": y, "z": z}, "status": "placed"}


def problems(*blocks):
    return HB.static_problems({"blocks": list(blocks)}, SPAWNS)


# ------------------------------------------------------------------------------------------------ static rules

# Without it the validator rejects the nests the manifest holds (158 blocks), or passes them only because a rule
# stopped running; a clean activated block, with no range_of_influence, must raise nothing.
def test_a_well_formed_activated_block_has_no_problems():
    assert problems(act()) == []
    assert problems(act(activated=dict(act()["activated"], trigger="REDSTONE", chance=0.25, cancel_range=8))) == []


def _without(key):
    b = act()
    del b[key]
    return b


def _with_act(**kv):
    b = act()
    b["activated"] = dict(b["activated"], **kv)
    return b


BAD = {
    "no mimic": (_without("mimic"), "mimic"),
    "mimic not namespaced": (act(mimic="oak_log"), "mimic"),
    "no activated settings": (_without("activated"), "activated settings"),
    "trigger unknown": (_with_act(trigger="ALWAYS"), "trigger"),
    "trigger lower case": (_with_act(trigger="tick"), "trigger"),
    "chance zero": (_with_act(chance=0), "chance"),
    "chance over one": (_with_act(chance=1.5), "chance"),
    "chance a string": (_with_act(chance="1.0"), "chance"),
    "max_spawns zero": (_with_act(max_spawns=0), "max_spawns"),
    "spawn_range missing": (_with_act(spawn_range=None), "spawn_range"),
    "cancel_range -2": (_with_act(cancel_range=-2), "cancel_range"),
    "replace_spawns true": (act(replace_spawns=True), "replace_spawns false"),
}


# Without it a malformed activated block reaches the function file: a setblock with no mimic or a trigger Cobblemon
# reads with valueOf fails half-loaded on the server (docs/STATE.md), and ReplaceSpawns on an activated block would
# make it cancel the forest's spawns it was never meant to touch.
@pytest.mark.parametrize("case", sorted(BAD))
def test_a_malformed_activated_block_is_named(case):
    b, word = BAD[case]
    got = problems(b)
    assert any(bid == "nest" and word in m for bid, m in got), (case, got)


# Without it a natural block loses the one field its placement needs; the per-style split must not relax it.
def test_a_natural_block_still_needs_its_range():
    b = nat()
    del b["range_of_influence"]
    assert any("range_of_influence" in m for _, m in problems(b))


# Without it a style Cobblemon does not have is accepted and placed as a natural block.
def test_an_unknown_style_is_refused():
    assert any("style" in m for _, m in problems(act(style="flock")))


# ------------------------------------------------------------------------------------------------ overlap

# Without it the three nest blocks stacked in one trunk (0 apart horizontally, 23 apart vertically) are reported as
# overlapping and the manifest cannot hold them; activated blocks do not cancel one another, nor a natural block.
def test_activated_blocks_are_never_reported_as_overlapping():
    stacked = [act("a", y=134), act("b", y=157), act("c", y=180, pool="cobblers:elder_y")]
    assert problems(*stacked) == [], problems(*stacked)
    mixed = [act("a", x=1746, y=109, z=4815), nat("n")]
    assert not any("overlap" in m for _, m in problems(*mixed)), problems(*mixed)
    # an activated block written with replace_spawns true is refused as malformed, not treated as a ReplaceSpawns range
    wrong = [act("a", x=1746, y=109, z=4815, replace_spawns=True), nat("n")]
    assert not any("overlap" in m for _, m in problems(*wrong))


# Without it two natural ReplaceSpawns blocks whose ranges meet spawn nothing in the overlap (EXP-021) and nobody
# notices. The tool now measures the distance in three dimensions (commit f6358c9); these cases pin that: a vertical
# overlap is reported, a pair far enough apart in y is not although they share (x, z). EXP-033 (the reach's vertical
# shape) is still open, so the 3D measure is the tool's rule, not a verified fact; data/habitat_blocks.json's natural
# blocks also clear the stricter horizontal measure (test below).
def test_natural_replace_spawns_overlap_is_reported_in_three_dimensions():
    assert any("overlaps b" in m for _, m in problems(nat("a"), nat("b", y=109 + 30)))              # 30 < 16 + 16
    assert not any("overlap" in m for _, m in problems(nat("a"), nat("b", y=109 + 33)))             # 33 > 32
    assert any("overlaps b" in m for _, m in problems(nat("a"), nat("b", x=1746 + 20, y=109 + 20)))  # 28.3 < 32
    assert not any("overlap" in m for _, m in problems(nat("a"), nat("b", x=1746 + 20, y=109 + 30)))  # 36.1 > 32
    # a natural block without ReplaceSpawns cancels nothing and overlaps freely
    assert not any("overlap" in m for _, m in problems(nat("a"), nat("b", y=110, replace=False)))


# Without it the manifest's natural ReplaceSpawns blocks could come to rely on the 3D relaxation: while EXP-033 is
# open they are held to the horizontal measure the manifest was built to (EXP-021's measured edge).
def test_the_manifests_natural_replace_spawns_blocks_clear_the_horizontal_measure():
    import math
    rs = [b for b in MANIFEST["blocks"] if b.get("style") == "natural" and b.get("replace_spawns")]
    assert len(rs) >= 50, len(rs)
    bad = []
    for i, a in enumerate(rs):
        for c in rs[i + 1:]:
            d = math.hypot(a["position"]["x"] - c["position"]["x"], a["position"]["z"] - c["position"]["z"])
            if d < a["range_of_influence"] + c["range_of_influence"]:
                bad.append((a["id"], c["id"], round(d, 1)))
    assert not bad, bad[:10]


# Without it two records set the same cell and the second silently replaces the first in the world.
def test_no_two_manifest_blocks_share_a_position():
    seen = {}
    for b in MANIFEST["blocks"]:
        seen.setdefault(tuple(b["position"][k] for k in "xyz"), []).append(b["id"])
    dup = {p: ids for p, ids in seen.items() if len(ids) > 1}
    assert not dup, dup


# ------------------------------------------------------------------------------------------------ commands

def _check_activated_commands(b):
    x, y, z = (b["position"][k] for k in "xyz")
    cmds = HB.commands(b)
    assert len(cmds) == 2, cmds
    assert cmds[0] == "setblock %d %d %d %s replace" % (x, y, z, b["mimic"]), cmds[0]
    head = "setblock %d %d %d cobblemon:habitat_block[cancels_regular_spawns=false,activated_style=true]{" % (x, y, z)
    assert cmds[1].startswith(head) and cmds[1].endswith("} replace"), cmds[1]
    for part in ('PhaseOrder:"SIMPLE"', 'SpawningStyle:"cobblemon:activated"', 'MimicId:"%s"' % b["mimic"],
                 'PoolId:"%s"' % b["pool"], "MaxSpawns:%d," % b["activated"]["max_spawns"],
                 "SpawnRange:%d," % b["activated"]["spawn_range"], 'Trigger:"%s"' % b["activated"]["trigger"]):
        assert part in cmds[1], (part, cmds[1])
    assert not any("data merge" in c for c in cmds), cmds


# Without it an activated block is placed with setblock + data merge, which on a block that has ticked leaves the
# spawner unbuilt and crashes every tick (staging, 2026-09-26), or without PhaseOrder, which fails half-loaded.
def test_an_activated_block_is_the_mimic_then_one_full_nbt_setblock():
    _check_activated_commands(act())
    _check_activated_commands(act(mimic="minecraft:dark_oak_log", activated=dict(act()["activated"], max_spawns=10)))


# Without it one of the placed nests in the manifest is written with a merge or without its PhaseOrder.
def test_every_activated_manifest_block_places_without_a_merge():
    acts = [b for b in MANIFEST["blocks"] if b.get("style") == "activated"]
    assert len(acts) >= 150, len(acts)
    for b in acts:
        _check_activated_commands(b)


# Without it the function file (what a post-export re-apply runs) differs from commands(): a merge line for an
# activated block, or its setblocks out of order.
def test_the_function_file_places_an_activated_block_without_a_merge(tmp_path):
    (tmp_path / "m.json").write_text(json.dumps({"blocks": [act(), nat()]}), encoding="utf-8")
    (tmp_path / "s.json").write_text(json.dumps(SPAWNS), encoding="utf-8")
    out = tmp_path / "pack"
    assert HB.main(["--manifest", str(tmp_path / "m.json"), "--spawns", str(tmp_path / "s.json"), "function",
                    "--out", str(out)]) == 0
    lines = (out / "data" / "cobblers" / "function" / "habitats" / "place.mcfunction").read_text(encoding="utf-8").splitlines()
    i = lines.index("# nest (cobblers:elder_x)")
    j = lines.index("# field (cobblers:great_crater_bowls)")
    nest = [l for l in lines[i + 1:j] if not l.startswith("forceload")]
    assert nest == HB.commands(act())
    assert not any("data merge" in l for l in lines[i:j])
    assert any(l.startswith("data merge block 1746 109 4815") for l in lines[j:])   # the natural block keeps its pair


# ------------------------------------------------------------------------------------------------ verify

# The block entity as Cobblemon 1.8.0 saves an activated block (keys from docs/STATE.md), written by hand here.
FOUND = {"id": HB.BLOCK, "SpawningStyle": "cobblemon:activated", "PoolId": "cobblers:elder_x",
         "MimicId": "minecraft:oak_log", "SpawnRange": 16, "MaxSpawns": 7, "MaxSpawnsPerActivation": 1,
         "CancelRange": -1, "Trigger": "TICK", "cancels_regular_spawns": "false"}


# Without it a nest the world holds with a different capacity (a hand edit, an older placement at max 4) passes the
# verify, and the tree holds fewer birds than the manifest says.
def test_compare_flags_a_mismatched_max_spawns():
    assert HB.compare(act(), dict(FOUND)) == []
    msgs = HB.compare(act(), dict(FOUND, MaxSpawns=4))
    assert len(msgs) == 1 and "MaxSpawns" in msgs[0], msgs
    assert any("SpawningStyle" in m for m in HB.compare(act(), dict(FOUND, SpawningStyle="cobblemon:natural")))


# Without it the stopped-world verify reads an activated block entity wrongly (a missing key, a byte read as a string)
# and either passes a wrong block or fails a right one.
def test_world_verify_reads_an_activated_block(tmp_path):
    entity = dict({k: v for k, v in FOUND.items() if k != "cancels_regular_spawns"}, x=1094, y=134, z=3496)
    ok = world_with(tmp_path / "ok", entity, cancels="false", x=1094, y=134, z=3496)
    assert HB.world_problems({"blocks": [act()]}, ok) == []
    bad = world_with(tmp_path / "bad", dict(entity, MaxSpawns=4), cancels="false", x=1094, y=134, z=3496)
    msgs = [m for _, m in HB.world_problems({"blocks": [act()]}, bad)]
    assert any("MaxSpawns" in m for m in msgs), msgs


class FakeRcon:
    """A server that answers `data get block` with a fixed entity and every state test with `answer`."""

    def __init__(self, entity_text, answer):
        self.entity_text, self.answer, self.sent = entity_text, answer, []

    def run(self, cmds, pw, timeout=None):
        self.sent.extend(cmds)
        c = cmds[0]
        if c.startswith("data get block"):
            return ["1094, 134, 3496 has the following block data: " + self.entity_text]
        if c.startswith("execute if block"):
            return [self.answer]
        return [""]


# Without it the RCON verify either waits and retries on every activated block (whose state is false by design) or
# gives up after one read on a natural ReplaceSpawns block whose state reads false straight after a forceload
# (staging, 2026-09-26: a different handful of 237 each run).
def test_rcon_state_test_is_retried_only_when_true_is_expected(monkeypatch):
    import runtime_guard
    import time
    monkeypatch.setattr(time, "sleep", lambda s: None)
    act_text = ('{MimicId: "minecraft:oak_log", SpawningStyle: "cobblemon:activated", PoolId: "cobblers:elder_x", '
                'Trigger: "TICK", SpawnRange: 16, MaxSpawns: 7, MaxSpawnsPerActivation: 1, CancelRange: -1, '
                'id: "cobblemon:habitat_block"}')
    fake = FakeRcon(act_text, "Test failed")
    monkeypatch.setattr(runtime_guard, "rcon", lambda d: (fake, "pw"))
    assert HB.rcon_problems({"blocks": [act()]}, "server") == []
    assert sum(c.startswith("execute if block") for c in fake.sent) == 1, fake.sent

    nat_text = ('{SpawningStyle: "cobblemon:natural", PoolId: "cobblers:great_crater_bowls", RangeOfInfluence: 16, '
                'ReplaceSpawns: 1b, id: "cobblemon:habitat_block"}')
    fake = FakeRcon(nat_text, "Test failed")
    monkeypatch.setattr(runtime_guard, "rcon", lambda d: (fake, "pw"))
    got = HB.rcon_problems({"blocks": [nat()]}, "server")
    assert sum(c.startswith("execute if block") for c in fake.sent) == 4, fake.sent
    assert any("cancels_regular_spawns" in m for _, m in got), got
    fake = FakeRcon(nat_text, "Test passed")
    monkeypatch.setattr(runtime_guard, "rcon", lambda d: (fake, "pw"))
    assert HB.rcon_problems({"blocks": [nat()]}, "server") == []
    assert sum(c.startswith("execute if block") for c in fake.sent) == 1, fake.sent


# ------------------------------------------------------------------------------------------------ compile_habitat

HABITAT = {"id": "elder_x", "entries": [{"pokemon": "hoothoot", "species": "Hoothoot"}]}


def _entry(**kv):
    e = {"species": "hoothoot", "bucket": "common", "weight": 24.0, "level": "18-21", "ambient": True,
         "spawnable_position": "grounded", "conditions": {}}
    e.update(kv)
    return e


# Without it a night bird authored with a timeRange spawns in a tree at noon (the condition is dropped between the
# authored entry and the pool file), or the passthrough writes a key the pool format does not have.
def test_a_time_range_reaches_the_pool_spawn_and_is_absent_otherwise():
    doc, _ = CS.compile_habitat(HABITAT, [_entry(conditions={"timeRange": "night"})])
    assert doc["spawns"][0]["timeRange"] == "night"
    for e in (_entry(), _entry(conditions=None), _entry(conditions={"canSeeSky": True})):
        e = copy.deepcopy(e)
        if e["conditions"] is None:
            del e["conditions"]
        doc, _ = CS.compile_habitat(HABITAT, [e])
        assert "timeRange" not in doc["spawns"][0], doc["spawns"][0]
    # two entries, one timed: only that one carries it
    doc, _ = CS.compile_habitat(HABITAT, [_entry(conditions={"timeRange": "night"}), _entry(species="noctowl")])
    assert ["timeRange" in s for s in doc["spawns"]] == [True, False]


# Without it the pool spawn keys drift from Cobblemon's format (principle 7): every key compile_habitat writes,
# timeRange included, must appear on some spawn in the jar's own habitat_pools.
def test_compiled_pool_spawn_keys_are_keys_the_jars_habitat_pools_use():
    import battle_sim
    jar = next((c for c in battle_sim.JAR_CANDIDATES if c.is_file()), None)
    if jar is None:
        pytest.skip("no Cobblemon-fabric-1.8.0 jar outside the live server (EXP-000 runtime copy)")
    z = zipfile.ZipFile(jar)
    keys = set()
    for n in z.namelist():
        if n.startswith("data/cobblemon/habitat_pools/") and n.endswith(".json"):
            for s in json.loads(z.read(n)).get("spawns") or []:
                keys |= set(s)
    assert "species" in keys, sorted(keys)
    doc, _ = CS.compile_habitat(HABITAT, [_entry(conditions={"timeRange": "night"})])
    written = set(doc["spawns"][0])
    assert written <= keys, sorted(written - keys)
