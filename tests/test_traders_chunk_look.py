"""The town traders (tools/traders.py, reapply step R14) as tools/chunk_look.py's look-then-act chain, N155.

A force-loaded chunk accepts a summon at once but its SAVED entities arrive later (staging 2026-10-08, the stall
merchants). The traders' old function summoned 40 ticks after the forceload and de-duplicated at 140, so an old trader
whose chunk was slower than that survived beside the new one. A plaza spans chunks, and one chunk's entities prove
nothing about another's, so the chain looks for EVERY standing trader before it acts (`all_shown`, R17M's per-seat look).

The world is tests/test_markets_merchant_load.py's LateWorld with a delay per chunk, plus the three selector arguments
and the block test the traders' functions use that tests/mcfunction_sim.py does not model (dx/dy/dz, name, and
`execute if block`, read here as "no jigsaw there"). The templates are fakes: the installed pack is not needed.

Written by the implementer of the fix (minecraft-systems-dev); an independent test-author review is still owed
(CLAUDE.md principle 16).
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tests"))

import chunk_look as CL  # noqa: E402
import chunk_look_audit as CA  # noqa: E402
import mcfunction_sim as S  # noqa: E402
import traders as TR  # noqa: E402
from test_markets_merchant_load import LateWorld  # noqa: E402

KIND = "cobbledollars:cobble_merchant"
TOWN = "t1"
ENTRY = "cobblers:towns/vendors_%s" % TOWN
HOLDER = TR.holder_of(TOWN)
SPOTS = [(5, 100, 5), (40, 100, 5)]          # two traders, two chunks (x 0-15 and 32-47)


def _rec(i, x, y, z, stock="regional"):
    return {"id": "%s_vendor_%02d" % (TOWN, i), "settlement": TOWN, "template": "bca:shop/s%d" % i, "source": {},
            "position": {"x": x, "y": y, "z": z}, "status": "planned", "stock": stock}


def _recs():
    return [_rec(i, *p) for i, p in enumerate(SPOTS, 1)]


def _fake(_template):
    return KIND, {"NoAI": True}                 # no name: the stray selector is type + spot


def _fns(recs=None):
    out = TR.town_functions(TOWN, recs or _recs(), _fake)
    return {"cobblers:towns/" + k: v for k, v in out.items()}


def _old_shape(recs=None):
    """The pre-fix functions, as tools/traders.py emitted them before this change: summon at 40, de-duplicate at 140."""
    recs = recs or _recs()
    box = "%d %d %d %d" % TR.plaza_box(recs)
    place, done = [], []
    for r in recs:
        x, y, z = (r["position"][k] for k in "xyz")
        tag = TR.tag_of(r["id"])
        place.append(TR.summon_line(KIND, x, y, z, {"NoAI": True, "Tags": [TR.TAG_ALL, tag, TR.TAG_NEW]}))
        done += ["execute if entity @e[tag=%s,tag=%s] run kill @e[tag=%s,tag=!%s]" % (tag, TR.TAG_NEW, tag, TR.TAG_NEW),
                 "tag @e[tag=%s,tag=%s] remove %s" % (tag, TR.TAG_NEW, TR.TAG_NEW)]
    return {ENTRY: ["forceload add " + box, "schedule function %s_place 40t replace" % ENTRY],
            ENTRY + "_place": place + ["schedule function %s_done 100t replace" % ENTRY],
            ENTRY + "_done": done + ["forceload remove " + box]}


class PlazaWorld(LateWorld):
    """LateWorld with a delay per chunk (default `delay`), dx/dy/dz and name selectors, and no blocks to test."""

    def __init__(self, functions, delay, per_chunk=None):
        super().__init__(functions, delay)
        self.per_chunk = per_chunk or {}

    def visible(self, e):
        if not getattr(e, "saved", False):
            return True
        c = (int(e.pos[0]) // 16, int(e.pos[2]) // 16)
        at = self.forced_at.get(c)
        return at is not None and self.tick_no - at >= self.per_chunk.get(c, self.delay)

    def select(self, sel, ctx, single=False):
        m = re.match(r"@e\[(.*)\]$", sel)
        if not m:
            return super().select(sel, ctx, single)
        args = [a for a in m.group(1).split(",") if a]
        box = {a.split("=")[0]: float(a.split("=")[1]) for a in args if a.split("=")[0] in ("dx", "dy", "dz")}
        names = [a.split("=", 1)[1].strip('"') for a in args if a.startswith("name=")]
        keep = [a for a in args if a.split("=")[0] not in ("dx", "dy", "dz", "name")]
        if box:
            origin = {a.split("=")[0]: float(a.split("=")[1]) for a in keep if a.split("=")[0] in ("x", "y", "z")}
            keep = [a for a in keep if a.split("=")[0] not in ("x", "y", "z")]
        got = super().select("@e[%s]" % ",".join(keep), ctx, single)
        if box:
            got = [e for e in got if all(origin[k] <= e.pos[i] < origin[k] + box["d" + k] + 1
                                         for i, k in enumerate("xyz"))]
        if names:
            got = [e for e in got if e.nbt.get("CustomName") in (json.dumps({"text": names[0]}), json.dumps(names[0]))]
        return got

    def c_execute(self, rest, ctx):
        if rest.startswith("if block "):
            return 0                            # no jigsaw left on any spot
        return super().c_execute(rest, ctx)


def _world(fns, delay, per_chunk=None, seeded=True, recs=None):
    w = PlazaWorld(fns, delay, per_chunk)
    if seeded:
        for r in recs or _recs():
            x, y, z = (r["position"][k] for k in "xyz")
            w.save(S.Entity(KIND, (x + 0.5, y, z + 0.5), tags=(TR.TAG_ALL, TR.tag_of(r["id"]))))
    return w


def _standing(w):
    return sorted(t for e in w.living(KIND, TR.TAG_ALL) for t in e.tags if t.startswith(TR.TAG_ALL + "_" + TOWN))


# --------------------------------------------------------------------------------------------- the simulated world
@pytest.mark.parametrize("delay", [150, 200])
def test_the_old_fixed_wait_doubles_a_trader_whose_chunk_is_slower_than_140_ticks(delay):
    # Without it the fix has nothing to fix: what a re-run did to every trader whose saved copy came late.
    w = _world(_old_shape(), delay)
    w.run(ENTRY, CL.STEP_TICKS)
    assert len(_standing(w)) == 2 * len(SPOTS)


@pytest.mark.parametrize("delay", [0, 1, 20, 60, 150, 200, 299])
def test_the_chain_leaves_one_trader_per_spot_however_late_the_plaza_arrives(delay):
    # Without it a re-run doubles the traders again.
    w = _world(_fns(), delay)
    w.run(ENTRY, CL.STEP_TICKS + 5)
    assert _standing(w) == sorted(TR.tag_of(r["id"]) for r in _recs())
    assert not any(TR.TAG_NEW in e.tags for e in w.living(KIND, TR.TAG_ALL))
    assert w.scores[("#" + HOLDER, CL.OBJ)] == TR.town_want(_recs()) == len(SPOTS)
    assert not w.forced, "the chain left the plaza force-loaded"


def test_one_chunk_in_early_does_not_start_the_act_while_another_is_still_out():
    # Without it (a look that acts on ANY trader seen) the second trader's chunk, 180 ticks slower, is still out at the
    # act and at the de-duplication 100 ticks later, and its old trader survives beside the new one.
    w = _world(_fns(), 20, per_chunk={(2, 0): 200})
    w.run(ENTRY, CL.STEP_TICKS + 5)
    assert len(_standing(w)) == len(SPOTS)
    acted = [t for t, _e in w.logged("summon")]
    assert min(acted) >= 200


def test_a_look_on_any_trader_is_the_mutation_that_doubles_the_slow_chunk(monkeypatch):
    # The generator mutated: all_shown dropped. The same world as above doubles the slow chunk's trader.
    orig = CL.chain
    monkeypatch.setattr(CL, "chain", lambda *a, **k: orig(*a, **dict(k, all_shown=False)))
    w = _world(_fns(), 20, per_chunk={(2, 0): 200})
    w.run(ENTRY, CL.STEP_TICKS + 5)
    assert len(_standing(w)) == len(SPOTS) + 1


def test_a_first_run_with_nothing_to_see_acts_blind_inside_the_step_wait():
    # Without it a fresh export (no traders saved) would never get its traders.
    w = _world(_fns(), 20, seeded=False)
    w.run(ENTRY, CL.STEP_TICKS + 5)
    acted = [t for t, _e in w.logged("summon")]
    assert acted and min(acted) == CL.BLIND_TICKS
    assert len(_standing(w)) == len(SPOTS) and CL.STEP_SECONDS * 20 >= CL.STEP_TICKS


def test_a_withdrawn_trader_is_killed_and_not_counted():
    recs = _recs() + [_rec(3, 8, 100, 20, stock="withdrawn")]
    w = _world(_fns(recs), 60, recs=recs)
    w.run(ENTRY, CL.STEP_TICKS + 5)
    assert _standing(w) == sorted(TR.tag_of(r["id"]) for r in recs[:2])
    assert w.scores[("#" + HOLDER, CL.OBJ)] == TR.town_want(recs) == 2


def test_the_count_reads_minus_one_until_the_chain_ends():
    # Without it reapply could read an earlier run's count and pass a chain that never finished.
    w = _world(_fns(), 20)
    w.run(ENTRY, 50)
    assert w.scores[("#" + HOLDER, CL.OBJ)] == -1


def _act_at_once(monkeypatch):
    """The generator mutated: the entry runs the act in the tick it force-loads (the look dropped)."""
    orig = CL.chain

    def at_once(base, *a, **k):
        fns = orig(base, *a, **k)
        fns[base] = fns[base] + ["function %s_act" % base]
        return fns
    monkeypatch.setattr(CL, "chain", at_once)


def test_dropping_the_look_in_the_generator_doubles_again(monkeypatch):
    _act_at_once(monkeypatch)
    w = _world(_fns(), 150)
    w.run(ENTRY, CL.STEP_TICKS + 5)
    assert len(_standing(w)) == 2 * len(SPOTS)


# --------------------------------------------------------------------------------------------- the chain's audit
def _write(tmp_path, fns):
    for rel, lines in CL.files(fns).items():
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return tmp_path


def _manifest():
    return json.loads((ROOT / "data" / "traders.json").read_text(encoding="utf-8"))


def _towns():
    by = {}
    for r in _manifest()["traders"]:
        by.setdefault(r["settlement"], []).append(r)
    return by


def test_every_towns_chain_passes_the_independent_audit(tmp_path):
    # Every settlement of data/traders.json, with fake templates (the shapes come from the data, not the shop).
    policy = _manifest().get("stock_policy")
    for town, recs in sorted(_towns().items()):
        fns = {"cobblers:towns/" + k: v for k, v in TR.town_functions(town, recs, _fake, policy).items()}
        pack = _write(tmp_path / town, fns)
        assert CA.problems(pack, "cobblers:towns/vendors_%s" % town, TR.TAG_ALL, town) == [], town


def test_the_audit_names_the_dropped_look(tmp_path, monkeypatch):
    _act_at_once(monkeypatch)
    pack = _write(tmp_path, _fns())
    got = CA.problems(pack, ENTRY, TR.TAG_ALL)
    assert any("summons in the tick it force-loads" in p for p in got), got


def test_the_audit_names_the_old_shape(tmp_path):
    pack = _write(tmp_path, _old_shape())
    got = CA.problems(pack, ENTRY, TR.TAG_ALL)
    assert any("calls the act ungated" in p or "summons before it kills" in p for p in got), got


def test_the_audit_names_a_all_shown_look_one_of_whose_selectors_is_not_a_trader(tmp_path):
    # The audit's reading of a several-entity look line: every selector must carry the site's tag.
    fns = _fns()
    look = ENTRY + "_look"
    fns[look] = [l.replace("if entity @e[tag=%s," % TR.TAG_ALL, "if entity @e[", 1) if " if entity " in l and
                 l.count("if entity") > 1 else l for l in fns[look]]
    got = CA.problems(_write(tmp_path, fns), ENTRY, TR.TAG_ALL)
    assert any("sets the act's flag without a look" in p for p in got), got


# --------------------------------------------------------------------------------------------- the reapply step
def test_r14_starts_every_town_then_waits_the_whole_chain_then_reads_each_count():
    towns = _towns()
    st = TR.steps()
    assert [s for s in st if s[0] == "cmd"] == [], "a step-level forceload would release a plaza under its chain"
    assert [s[1] for s in st if s[0] == "fn"] == ["cobblers:towns/vendors_%s" % t for t in sorted(towns)]
    waits = [i for i, s in enumerate(st) if s[0] == "wait"]
    assert len(waits) == 1 and st[waits[0]][1] * 20 >= CL.STEP_TICKS
    fns_at = [i for i, s in enumerate(st) if s[0] == "fn"]
    checks = [(i, s[1]) for i, s in enumerate(st) if s[0] == "check"]
    assert max(fns_at) < waits[0] < min(i for i, _c in checks)
    want = {c[1]: c[2] for _i, c in checks if c[0] == "chunk_look"}
    assert want == {"vendors_%s" % t: sum(1 for r in rs if r.get("stock") != "withdrawn") for t, rs in towns.items()}


def test_no_two_plazas_share_a_chunk():
    # The chains run at once; a chunk two plazas share would be released by the first chain to end, under the other.
    seen = {}
    for town, recs in sorted(_towns().items()):
        x0, z0, x1, z1 = TR.plaza_box(recs)
        for c in {(cx, cz) for cx in range(x0 // 16, x1 // 16 + 1) for cz in range(z0 // 16, z1 // 16 + 1)}:
            assert c not in seen, "chunk %s held by %s and %s" % (c, seen[c], town)
            seen[c] = town


def test_reapply_runs_r14_from_the_traders_tool():
    text = (ROOT / "tools" / "reapply.py").read_text(encoding="utf-8")
    assert 'out.append(("R14", "town traders", traders.steps()))' in text
