"""R14L is safe to re-run (2026-10-12): a re-run leaves an existing legendary alone and adds only a missing one.

STATE.md recorded "R14L (a re-run would duplicate its summons)", so seven new chambers (Tornadus, Thundurus, Landorus,
Enamorus, Tapu Koko, Tapu Lele, Tapu Bulu) could not reach the staging world without risking a second Regirock.
The old step force-loaded a chamber, waited 3 seconds and ran `execute unless entity @e[tag=...] ... run
spawnpokemonat`. A force-loaded chunk accepts a summon at once but its SAVED entities arrive some ticks later (N155,
tools/chunk_look.py), so the guard saw nothing and the summon doubled the legendary. The new step runs a look-then-act
chain per chamber (tools/legendaries.py chain_parts), and skips the carve once a gate has opened.

The interpreter is tests/mcfunction_sim.py with test_markets_merchant_load.LateWorld (saved entities arrive `delay`
ticks after their chunk is force-loaded), extended here with `setblock` and with selector limits applied AFTER the
visibility filter. The steps are executed as tools/reapply.py executes them: "cmd" over RCON, "fn" as a function, "wait"
in seconds.

Mutations change the GENERATOR (tools/chunk_look.py chain, tools/legendaries.py), never the data:
  - a chain whose act does not ask whether a legendary stands doubles-and-replaces the existing one;
  - the old one-tick shape, written out here from the same record, doubles it (proving the world can show the fault).

NOT COVERED, and it needs a running server: that Cobblemon's `spawnpokemonat` macro line spawns in a chamber chunk
(EXP-046 proved the macro form elsewhere), that a real chunk's saved entities arrive within the chain's 300-tick limit,
and that a re-run on staging reads 15 of 15 with the checks R14L reads back.
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tests"))

import chunk_look as CL  # noqa: E402
import legendaries as L  # noqa: E402
import mcfunction_sim as S  # noqa: E402
from test_markets_merchant_load import LateWorld  # noqa: E402


@pytest.fixture(scope="module")
def ground():
    import ground as G
    import terrain as T
    try:
        return G.Ground(os.environ.get("COBBLERS_SOURCE_ROOT"))
    except T.TerrainUnavailable as e:
        pytest.skip("the canonical heightmap is unusable: %s" % e)


@pytest.fixture(scope="module")
def doc():
    return L.load()


class ChamberWorld(LateWorld):
    """LateWorld that also takes `setblock` and applies limit/sort after the visibility filter."""

    def select(self, sel, ctx, single=False):
        allents = self.entities
        self.entities = [e for e in allents if self.visible(e)]
        try:
            return S.World.select(self, sel, ctx, single)
        finally:
            self.entities = allents

    def c_setblock(self, rest, ctx):
        self._log((self.tick_no, "setblock", rest))
        return 1


def functions(doc, ground):
    out = {}
    for rel, text in L.files(doc, ground).items():
        m = re.match(r"data/([^/]+)/function/(.+)\.mcfunction$", rel)
        if m:
            out["%s:%s" % m.groups()] = text.splitlines()
    return out


def world(fns, delay):
    w = ChamberWorld(fns, delay)
    w.function("cobblers:legendary/load", w.server())
    return w


def spot(rec, doc, ground):
    lx, ly, lz = L.geometry(rec, doc, ground)["legendary"]
    return (lx + 0.5, float(ly), lz + 0.5)


def save_legendary(w, rec, doc, ground, tags=None):
    """A legendary saved in its chunk by an earlier run: tagged, dressed, invisible until the chunk has loaded."""
    tag = doc["tag_prefix"] + rec["id"]
    e = S.Entity("cobblemon:pokemon", spot(rec, doc, ground), nbt={"Pokemon": {"Species": rec["species"]}},
                 tags=tags if tags is not None else (tag,))
    w.save(e)
    return e


def run_steps(w, steps):
    """What tools/reapply.py does with an action list (the `check` actions read a score back; not run here)."""
    for kind, value in steps:
        if kind == "cmd":
            w.command(value, w.server(), from_macro=True)
        elif kind == "fn":
            w.function(value, w.server())
        elif kind == "wait":
            w.tick(int(value * 20))
        elif kind != "check":
            raise AssertionError("unknown action %r" % (kind,))


def standing(w, rec, doc):
    tag = doc["tag_prefix"] + rec["id"]
    return [e for e in w.entities if e.alive and e.type == "cobblemon:pokemon" and tag in e.tags]


def spawns(w):
    return [e for _t, k, e in w.log if k == "spawn"]


def sited(doc):
    return L.emitted(doc)


def steps_one(doc, ground, rid):
    """R14L's actions for one chamber: the same generator, over a doc holding only that record."""
    one = dict(doc, encounters=[r for r in doc["encounters"] if r["id"] == rid])
    return L.placement_steps(one, ground)


# ------------------------------------------------------------------------------------------------ the properties


def test_a_first_run_summons_each_legendary_once_at_its_level(doc, ground):
    # Without it the chain could be rewritten into one that never summons, and every re-run test below would pass.
    w = world(functions(doc, ground), delay=0)
    run_steps(w, L.placement_steps(doc, ground))
    for rec in sited(doc):
        got = standing(w, rec, doc)
        assert len(got) == 1, "%s: %d standing after a first run" % (rec["id"], len(got))
        assert got[0].nbt["Pokemon"]["Species"] == rec["species"] and got[0].nbt["Pokemon"]["Level"] == int(rec["level"])
    assert len(spawns(w)) == len(sited(doc))
    assert not w.forced, "the steps left chunks force-loaded"
    assert not w.errors, w.errors


@pytest.mark.parametrize("delay", [0, 3, 15, 35, 80])
def test_a_rerun_leaves_every_existing_legendary_alone_however_late_it_arrives(doc, ground, delay):
    # N155: the saved legendary arrives `delay` ticks after the force-load. If the guard looked once and early, the
    # summon doubled it. Without this test the guard could regress to the 3-second shape and nothing would say so.
    w = world(functions(doc, ground), delay=delay)
    saved = {rec["id"]: save_legendary(w, rec, doc, ground) for rec in sited(doc)}
    run_steps(w, L.placement_steps(doc, ground))
    for rec in sited(doc):
        got = standing(w, rec, doc)
        assert got == [saved[rec["id"]]], "%s: %s stands after a re-run (delay %d)" % (rec["id"], got, delay)
    assert not spawns(w), "a re-run summoned over a legendary that stood: %s" % spawns(w)
    assert not [1 for _t, k, e in w.log if k == "kill"], "a re-run killed something"
    assert not w.errors, w.errors


def test_a_rerun_adds_only_the_missing_legendary(doc, ground):
    # The point of the change: seven new chambers reach a world whose older chambers already hold their legendaries.
    recs = sited(doc)
    missing = recs[-1]
    w = world(functions(doc, ground), delay=25)
    saved = {r["id"]: save_legendary(w, r, doc, ground) for r in recs if r is not missing}
    run_steps(w, L.placement_steps(doc, ground))
    assert [e.nbt["Pokemon"]["Species"] for e in spawns(w)] == [missing["species"]]
    assert len(standing(w, missing, doc)) == 1
    for r in recs:
        if r is not missing:
            assert standing(w, r, doc) == [saved[r["id"]]]


def test_an_undressed_legendary_already_at_the_spot_is_dressed_not_doubled(doc, ground):
    # An interrupted earlier run left a summoned but untagged Pokemon at the spot: dress_new takes it.
    rec = next(r for r in sited(doc) if r["kind"] == "sealed_chamber")
    w = world(functions(doc, ground), delay=0)
    e = save_legendary(w, rec, doc, ground, tags=())
    run_steps(w, steps_one(doc, ground, rec["id"]))
    assert not spawns(w) and standing(w, rec, doc) == [e], "an undressed one at the spot was doubled or ignored"


def test_a_rerun_does_not_reseal_a_chamber_a_player_has_opened(doc, ground):
    # carve fills the envelope solid first, which puts the plug back; the gate's score stays 1, so `open` never runs
    # again and the legendary would be sealed for ever. Without carve_once the opened chamber loses its door.
    rec = next(r for r in sited(doc) if r["kind"] == "sealed_chamber")
    w = world(functions(doc, ground), delay=0)
    obj = doc["objective"]
    w.set_score("#" + rec["id"], obj, 1, w.server())
    steps = steps_one(doc, ground, rec["id"])
    run_steps(w, steps)
    assert not [1 for _t, k, d in w.log if k == "fill" and d], "an opened chamber was re-carved"
    # and a shut one is carved
    w2 = world(functions(doc, ground), delay=0)
    run_steps(w2, steps)
    assert [1 for _t, k, d in w2.log if k == "fill"], "a shut chamber was not carved"


# ------------------------------------------------------------------------------------------------ mutations


def test_dropping_the_look_in_the_generator_replaces_the_existing_legendary(doc, ground, monkeypatch):
    # Mutates the GENERATOR (chunk_look.chain), not the data: the entry runs the act in the tick it force-loads, with
    # no look (the shape test_chunk_look.py mutates). The saved legendary has not arrived, both guards see nothing, a
    # second is summoned, and the chain's de-duplication later kills the saved one: the count still reads 1, so only
    # the no-spawn and identity checks above can see it. This proves they bite.
    orig = CL.chain

    def at_once(base, *a, **k):
        fns = orig(base, *a, **k)
        fns[base] = fns[base] + ["function %s_act" % base]
        return fns

    monkeypatch.setattr(CL, "chain", at_once)
    rec = next(r for r in sited(doc) if r["kind"] == "sealed_chamber")
    w = world(functions(doc, ground), delay=100)
    saved = save_legendary(w, rec, doc, ground)
    run_steps(w, steps_one(doc, ground, rec["id"]))
    assert spawns(w), "the mutation did not change behaviour: the test would not notice a regression"
    assert standing(w, rec, doc) != [saved]


def test_the_old_one_tick_shape_doubles_a_late_legendary(doc, ground):
    # R14L as it was before 2026-10-12, written out from the same record: force-load, wait 3 s, summon unless a
    # tagged one is seen. A legendary that arrives later than 3 s is not seen, and the summon doubles it. This shows
    # the simulated world CAN show the fault, so the passes above mean something.
    rec = next(r for r in sited(doc) if r["kind"] == "sealed_chamber")
    ns, rid, tag = doc["namespace"], rec["id"], doc["tag_prefix"] + rec["id"]
    g = L.geometry(rec, doc, ground)
    x0, _y0, z0, x1, _y1, z1 = g["bbox"]
    lx, ly, lz = g["legendary"]
    at = "%.1f %d %.1f" % (lx + 0.5, ly, lz + 0.5)
    old = [("cmd", "forceload add %d %d %d %d" % (x0, z0, x1, z1)), ("wait", 3),
           ("fn", "%s:legendary/%s/carve" % (ns, rid)),
           ("cmd", "execute unless entity @e[tag=%s] positioned %s unless entity @e[type=cobblemon:pokemon,distance=..3] "
                   "run spawnpokemonat %s %s level=%d no_ai" % (tag, at, at, rec["species"], int(rec["level"]))),
           ("wait", 1), ("fn", "%s:legendary/%s/dress_new" % (ns, rid)),
           ("cmd", "forceload remove %d %d %d %d" % (x0, z0, x1, z1))]
    w = world(functions(doc, ground), delay=100)
    save_legendary(w, rec, doc, ground)
    run_steps(w, old)
    # a console `spawnpokemonat` is inert in the simulator when it runs inside `execute`; the log still records that
    # the guard let the summon through while the saved legendary stood a few ticks from arriving
    assert len(w.logged("inert_spawn")) == 1, "the old shape's guard did not let a summon through a late legendary"
    w2 = world(functions(doc, ground), delay=100)
    save_legendary(w2, rec, doc, ground)
    run_steps(w2, steps_one(doc, ground, rec["id"]))
    assert not w2.logged("inert_spawn") and not spawns(w2), "the new shape summoned over the same late legendary"


# ------------------------------------------------------------------------------------------------ the step shape


def test_each_step_releases_its_own_hold_before_the_chain_and_reads_the_count_back(doc, ground):
    # tools/chunk_look.py: a forceload is per chunk, not counted, so a release after the chain's entry would drop the
    # chunk under the chain. And without the read-back a chain that never finished would pass.
    steps = L.placement_steps(doc, ground)
    n = 0
    for i, (kind, value) in enumerate(steps):
        if kind == "fn" and value.endswith("/place"):
            n += 1
            assert steps[i - 1][0] == "cmd" and steps[i - 1][1].startswith("forceload remove "), steps[i - 3:i + 1]
            assert steps[i + 1] == ("wait", CL.STEP_SECONDS)
            assert steps[i + 2][0] == "check" and steps[i + 2][1][0] == "chunk_look" and steps[i + 2][1][2] == 1
    assert n == len(sited(doc))
