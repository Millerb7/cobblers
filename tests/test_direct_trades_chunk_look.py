"""The barterers (tools/direct_trades.py, reapply step R18DT) as tools/chunk_look.py's look-then-act chain, N155.

The old step force-loaded the booth, waited 3 s, summoned and de-duplicated 100 ticks later (160 ticks after the
forceload), so a villager whose saved chunk came later than that survived beside the new one. Now each barterer's
function is a chain: block checks, kill and summon only once its saved copy is seen (or blind after 300 ticks).

The world is tests/test_traders_chunk_look.py's PlazaWorld (LateWorld with a delay per chunk), told here what the
booth's blocks are: every shell cell the booth's own stone (no breach) unless a test says otherwise. Built on a flat
heightmap, so no canonical source is needed.

Written by the implementer of the fix (minecraft-systems-dev); an independent test-author review is still owed
(CLAUDE.md principle 16).
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tests"))

np = pytest.importorskip("numpy")
import chunk_look as CL  # noqa: E402
import chunk_look_audit as CA  # noqa: E402
import direct_trades as D  # noqa: E402
import mcfunction_sim as S  # noqa: E402
from test_direct_trades import FlatGround  # noqa: E402
from test_traders_chunk_look import PlazaWorld  # noqa: E402

DOC = D.load()
NS, FO = DOC["namespace"], DOC["folder"]
WHO = {"place": "barterer", "counter": "counter_barterer"}


def _entry(name):
    return "%s:%s/%s" % (NS, FO, name)


def _tag(name):
    return DOC[WHO[name]]["tag"]


def _files(doc=DOC):
    out, res = D.files(doc, FlatGround())
    fns = {}
    for rel, text in out.items():
        if rel.endswith(".mcfunction"):
            fns["%s:%s" % (NS, rel.split("/function/", 1)[1][:-len(".mcfunction")])] = text.splitlines()
    return fns, res


def _old_shape(name):
    """The pre-fix shape for one barterer, as R18DT ran it: the step force-loaded, waited 3 s (60 ticks), ran a
    function that summoned and scheduled the de-duplication 100 ticks on; the step released 7 s later."""
    fns, res = _files()
    tag = _tag(name)
    summon = next(l for l in fns[_entry(name) + "_act"] if l.startswith("summon "))
    x0, z0, x1, z1 = D.booth_box(res["booth"]) if name == "place" else D.counter_box(DOC)
    box = "%d %d %d %d" % (x0, z0, x1, z1)
    return {_entry(name): ["forceload add " + box, "schedule function %s_go 60t replace" % _entry(name)],
            _entry(name) + "_go": [summon, "schedule function %s_done 100t replace" % _entry(name)],
            _entry(name) + "_done": ["execute if entity @e[type=%s,tag=%s,tag=%s_new] run kill @e[type=%s,tag=%s,tag=!%s_new]"
                                     % (D.KIND, tag, tag, D.KIND, tag, tag),
                                     "tag @e[type=%s,tag=%s,tag=%s_new] remove %s_new" % (D.KIND, tag, tag, tag),
                                     "schedule function %s_release 140t replace" % _entry(name)],
            _entry(name) + "_release": ["forceload remove " + box]}


class BoothWorld(PlazaWorld):
    """Blocks are what the booth and the Mart are: no breach anywhere unless `breach` names a cell."""

    def __init__(self, functions, delay, breach=None):
        super().__init__(functions, delay)
        self.breach = breach

    def c_execute(self, rest, ctx):
        if rest.startswith(("if block ", "unless block ")):
            t = rest.split()
            hit = self.breach is not None and tuple(int(v) for v in t[2:5]) == self.breach and t[0] == "if"
            if not hit:
                return 0
            return self.command(rest.split(" run ", 1)[1], ctx)     # the breached cell: its check passes
        return super().c_execute(rest, ctx)

    def c_setblock(self, rest, ctx):
        self._log((self.tick_no, "setblock", rest))
        return 1

    def c_return(self, rest, ctx):
        if rest.strip() == "fail":
            raise S.Return(0)
        return super().c_return(rest, ctx)


def _world(fns, name, delay, seeded=True, breach=None):
    w = BoothWorld(fns, delay, breach)
    if seeded:
        x, y, z = (_files()[1]["booth"] if name == "place" else _files()[1]["counter"])["villager"]
        w.save(S.Entity(D.KIND, (x + 0.5, y, z + 0.5), tags=(_tag(name),)))
    return w


def _standing(w, name):
    return len(w.living(D.KIND, _tag(name)))


# --------------------------------------------------------------------------------------------- the simulated world
@pytest.mark.parametrize("name", ["place", "counter"])
@pytest.mark.parametrize("delay", [170, 250])
def test_the_old_step_doubles_a_barterer_whose_chunk_is_slower_than_160_ticks(name, delay):
    # Without it the fix has nothing to fix.
    w = _world(_old_shape(name), name, delay)
    w.run(_entry(name), 320)
    assert _standing(w, name) == 2


@pytest.mark.parametrize("name", ["place", "counter"])
@pytest.mark.parametrize("delay", [0, 20, 60, 170, 250, 299])
def test_the_chain_leaves_one_barterer_however_late_its_chunk_arrives(name, delay):
    fns, _ = _files()
    w = _world(fns, name, delay)
    w.run(_entry(name), CL.STEP_TICKS + 5)
    assert _standing(w, name) == 1
    assert not any(_tag(name) + "_new" in e.tags for e in w.living(D.KIND, _tag(name)))
    assert w.scores[("#" + D.holder(name), CL.OBJ)] == 1
    assert not w.forced, "the chain left its box force-loaded"


@pytest.mark.parametrize("name", ["place", "counter"])
def test_a_first_run_acts_blind_inside_the_step_wait(name):
    fns, _ = _files()
    w = _world(fns, name, 20, seeded=False)
    w.run(_entry(name), CL.STEP_TICKS + 5)
    acted = [t for t, _e in w.logged("summon")]
    assert acted == [CL.BLIND_TICKS] and _standing(w, name) == 1


def test_a_breach_keeps_the_standing_barterer_carves_nothing_and_still_releases():
    # Without it a breach ended the act before its de-duplication was scheduled: the box stayed force-loaded for ever
    # and the count read -1. The breach comes after the look, so the standing villager is seen, kept, and counted.
    fns, res = _files()
    (x0, y0, z0), _hi = res["booth"]["shell"]
    w = _world(fns, "place", 20, breach=(x0, y0, z0))
    w.run(_entry("place"), CL.STEP_TICKS + 5)
    assert not w.logged("summon") and not w.logged("fill")
    assert _standing(w, "place") == 1 and w.scores[("#" + D.holder("place"), CL.OBJ)] == 1
    assert w.scores[("#breach", D.OBJECTIVE)] == 1
    assert not w.forced


def _act_at_once(monkeypatch):
    """The generator mutated: the entry runs the act in the tick it force-loads (the look dropped)."""
    orig = CL.chain

    def at_once(base, *a, **k):
        fns = orig(base, *a, **k)
        fns[base] = fns[base] + ["function %s_act" % base]
        return fns
    monkeypatch.setattr(CL, "chain", at_once)


@pytest.mark.parametrize("name", ["place", "counter"])
def test_dropping_the_look_in_the_generator_doubles_again(name, monkeypatch):
    _act_at_once(monkeypatch)
    fns, _ = _files()
    w = _world(fns, name, 150)
    w.run(_entry(name), CL.STEP_TICKS + 5)
    assert _standing(w, name) == 2


# --------------------------------------------------------------------------------------------- the chain's audit
def _write(tmp_path, doc=DOC):
    out, _ = D.files(doc, FlatGround())
    D.write(out, tmp_path / "pack")
    return tmp_path / "pack"


@pytest.mark.parametrize("name", ["place", "counter"])
def test_both_chains_pass_the_independent_audit(name, tmp_path):
    assert CA.problems(_write(tmp_path), _entry(name), _tag(name), name) == []


@pytest.mark.parametrize("name", ["place", "counter"])
def test_the_audit_names_the_dropped_look(name, tmp_path, monkeypatch):
    _act_at_once(monkeypatch)
    got = CA.problems(_write(tmp_path), _entry(name), _tag(name), name)
    assert any("summons in the tick it force-loads" in p for p in got), got


@pytest.mark.parametrize("name", ["place", "counter"])
def test_the_audit_names_the_old_shape(name, tmp_path):
    pack = tmp_path / "old"
    for ref, lines in _old_shape(name).items():
        p = CA.pack_path(pack, ref)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    got = CA.problems(pack, _entry(name), _tag(name), name)
    assert any("ungated" in p for p in got), got
