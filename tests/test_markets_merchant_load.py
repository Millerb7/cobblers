"""N155 (docs/OVERNIGHT_REVIEW_2026-10-06.md): R17M doubled stall merchants on staging, 2026-10-08, twice in one day.

A force-loaded chunk accepts a summon at once, but its SAVED entities arrive some ticks later (the main session saw a
tagged query return nothing for about 5 s after `forceload add`). The 2026-10-08 shape force-loaded, waited a fixed 40
ticks, killed by seat and summoned: where the old merchant had not arrived yet, the kill missed it and the stall was
doubled. tools/markets.py now staffs a seat only once its chunk shows its entities are in (the merchant or the old
dialogue keeper seen on the seat), or blind after MERCHANT_POLLS looks.

The interpreter is tests/mcfunction_sim.py, extended here with the two things this needs and nothing else:
  late entities  an entity saved in a chunk that was not loaded is invisible to every selector until `delay` ticks
                 after the chunk is force-loaded; an entity summoned into a loaded chunk is visible at once; on
                 `forceload remove` everything in the released chunks is saved again (vanilla unloads and saves them)
  schedule       `schedule function <name> <n>t [replace]` runs the function n ticks later; `replace` drops a pending
                 run of the same function (vanilla ScheduleCommand)

Written by the implementer of the fix (minecraft-systems-dev), at the orchestrator's request; an independent
test-author review of it is still owed (CLAUDE.md principle 16).
"""
from __future__ import annotations

import math
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tests"))

import markets as M  # noqa: E402
import mcfunction_sim as S  # noqa: E402

TOWN = "gym1_town"          # Stoneford: six merchants, the town that doubled on staging


def _chunk(x, z):
    return (math.floor(x) // 16, math.floor(z) // 16)


class LateWorld(S.World):
    def __init__(self, functions, delay):
        super().__init__(functions, loaded=lambda x, z: False)
        self.delay = delay
        self.forced_at = {}
        self.pending = []           # [due tick, function]

    # entities saved in a chunk arrive `delay` ticks after it is force-loaded
    def save(self, e):
        e.saved = True
        return self.add(e)

    def visible(self, e):
        if not getattr(e, "saved", False):
            return True
        at = self.forced_at.get(_chunk(e.pos[0], e.pos[2]))
        return at is not None and self.tick_no - at >= self.delay

    def select(self, sel, ctx, single=False):
        if "limit=" in sel or "sort=" in sel:
            raise S.Unsupported("LateWorld filters after the selector: no limit or sort")
        return [e for e in super().select(sel, ctx, single) if self.visible(e)]

    def c_forceload(self, rest, ctx):
        before = set(self.forced)
        n = super().c_forceload(rest, ctx)
        for c in self.forced - before:
            self.forced_at[c] = self.tick_no
        for c in before - self.forced:
            self.forced_at.pop(c, None)
            for e in self.entities:
                if e.alive and _chunk(e.pos[0], e.pos[2]) == c:
                    e.saved = True
        return n

    def c_schedule(self, rest, ctx):
        m = re.match(r"function (\S+) (\d+)t(?: (replace|append))?$", rest.strip())
        if not m:
            raise S.Unsupported("schedule %s" % rest)
        name, n, mode = m.group(1), int(m.group(2)), m.group(3) or "replace"
        if mode == "replace":
            self.pending = [p for p in self.pending if p[1] != name]
        self.pending.append([self.tick_no + n, name])
        return 1

    def tick(self, n=1):
        for _ in range(n):
            self.tick_no += 1
            due = [p for p in self.pending if p[0] <= self.tick_no]
            self.pending = [p for p in self.pending if p[0] > self.tick_no]
            for _due, name in due:
                self.function(name, self.server())

    def run(self, name, ticks):
        self.function(name, self.server())
        self.tick(ticks)


def _functions(files):
    out = {}
    for k, v in files.items():
        m = re.match(r"data/([^/]+)/function/(.+)\.mcfunction$", k)
        if m:
            out["%s:%s" % m.groups()] = list(v)
    return out


def _new_pack():
    doc = M.load()
    return doc, _functions(M.build(doc, {})[0])


def _old_pack(doc):
    """The 2026-10-08 shape, written out from the same merchants: force-load, 40 ticks, kill by seat and summon,
    100 ticks, kill older copies where a new one stands, release."""
    import traders as TR
    cfg = M.merchant_cfg(doc)
    new, radius = cfg["tag"] + "_new", float(cfg["remove_radius"])
    ms = [m for m in M.stall_merchants(doc, {}) if m["town"] == TOWN]
    box = "%d %d %d %d" % M.merchant_box(ms)
    ref = lambda n: "cobblers:old/%s" % n
    place = ["kill @e[type=cobblemon:npc,x=%d.5,y=%d,z=%d.5,distance=..%s]" % (m["at"] + (radius,)) for m in ms]
    place += [TR.summon_line(cfg["kind"], *m["at"], m["data"]) for m in ms]
    place.append("schedule function %s 100t replace" % ref("done"))
    done = []
    for m in ms:
        done += ["execute if entity @e[tag=%s,tag=%s] run kill @e[tag=%s,tag=!%s]" % (m["tag"], new, m["tag"], new),
                 "tag @e[tag=%s,tag=%s] remove %s" % (m["tag"], new, new)]
    done.append("forceload remove %s" % box)
    return {ref("start"): ["forceload add %s" % box, "schedule function %s 40t replace" % ref("place")],
            ref("place"): place, ref("done"): done}


def _merchants(doc):
    return [m for m in M.stall_merchants(doc, {}) if m["town"] == TOWN]


def _seed(w, doc, steve=False):
    """A world after an earlier run: each seat's merchant saved in its unloaded chunk (or, steve=True, the Cobblemon
    dialogue keeper the merchants replaced, one block behind the seat)."""
    cfg = M.merchant_cfg(doc)
    for m in _merchants(doc):
        x, y, z = m["at"]
        if steve:
            w.save(S.Entity("cobblemon:npc", (x + 0.5, y, z + 1.5)))
        else:
            w.save(S.Entity(cfg["kind"], (x + 0.5, y, z + 0.5), tags=(cfg["tag"], m["tag"])))


def _count(w, doc):
    """{stall: merchants alive with its tag}, read from the whole world (loaded or not)."""
    cfg = M.merchant_cfg(doc)
    return {m["stall"]: len(w.living(cfg["kind"], m["tag"])) for m in _merchants(doc)}


def _start(name):
    return "cobblers:stalls/merchants/%s" % name


# ------------------------------------------------------------------------------------------------ the defect
@pytest.mark.parametrize("delay", [141, 200])
def test_the_old_shape_doubles_a_stall_whose_merchant_arrives_after_its_dedupe(delay):
    """The old shape's _done de-duplication (tick 140) catches a merchant that arrives by then; staging still doubled
    6-7 stalls, so there its chunks' entities took longer. Past 140 ticks the old shape doubles every stall."""
    doc, _ = _new_pack()
    w = LateWorld(_old_pack(doc), delay=delay)
    _seed(w, doc)
    w.run("cobblers:old/start", 400)
    assert set(_count(w, doc).values()) == {2}, _count(w, doc)


def test_the_old_shape_survives_a_merchant_that_arrives_before_its_dedupe():
    doc, _ = _new_pack()
    w = LateWorld(_old_pack(doc), delay=100)
    _seed(w, doc)
    w.run("cobblers:old/start", 400)
    assert set(_count(w, doc).values()) == {1}, _count(w, doc)


def test_the_limit_a_chunk_slower_than_the_blind_staffing_and_the_dedupe_still_doubles():
    """Stated, not hidden: a seat is staffed blind after 300 ticks and de-duplicated 100 later; a merchant that
    arrives after both (here 401 ticks) is still a second copy, as with the old shape after 140. R17M's verify then
    names it ("2 merchants tagged ..."), and a re-run, with the chunk now quick, clears it."""
    doc, fns = _new_pack()
    w = LateWorld(fns, delay=M.MERCHANT_STEP_TICKS + 1)
    _seed(w, doc)
    w.run(_start(TOWN), M.MERCHANT_STEP_TICKS + 2)
    assert set(_count(w, doc).values()) == {2}
    w.delay = 0
    w.run(_start(TOWN), M.MERCHANT_STEP_TICKS + 1)
    assert set(_count(w, doc).values()) == {1}


@pytest.mark.parametrize("delay", [0, 1, 39, 41, 100, 141, 200, 299, 300, 350, 399])
def test_one_run_seats_exactly_one_merchant_per_stall_however_late_the_chunk_s_entities_arrive(delay):
    doc, fns = _new_pack()
    w = LateWorld(fns, delay=delay)
    _seed(w, doc)
    w.run(_start(TOWN), M.MERCHANT_STEP_TICKS + 1)
    assert set(_count(w, doc).values()) == {1}, (delay, _count(w, doc))
    cfg = M.merchant_cfg(doc)
    for m in _merchants(doc):
        (e,) = w.living(cfg["kind"], m["tag"])
        assert e.pos == [m["at"][0] + 0.5, float(m["at"][1]), m["at"][2] + 0.5]
        assert e.nbt.get("CobbleMerchantShop") == m["data"]["CobbleMerchantShop"]
        assert cfg["tag"] + "_new" not in e.tags
    assert w.forced == set() and w.pending == []          # released, nothing left scheduled


def test_a_re_run_and_a_third_run_still_leave_one_each():
    doc, fns = _new_pack()
    w = LateWorld(fns, delay=100)
    _seed(w, doc)
    for _ in range(3):
        w.run(_start(TOWN), M.MERCHANT_STEP_TICKS + 1)
        assert set(_count(w, doc).values()) == {1}, _count(w, doc)


def test_a_seat_still_staffed_by_a_dialogue_keeper_loses_it_and_gets_one_merchant():
    doc, fns = _new_pack()
    w = LateWorld(fns, delay=100)
    _seed(w, doc, steve=True)
    w.run(_start(TOWN), M.MERCHANT_STEP_TICKS + 1)
    assert set(_count(w, doc).values()) == {1}
    assert w.living("cobblemon:npc") == []


def test_an_empty_seat_is_staffed_blind_inside_the_step_s_wait():
    doc, fns = _new_pack()
    w = LateWorld(fns, delay=100)                  # nothing saved anywhere: the first run at a new stall
    w.function(_start(TOWN), w.server())
    summoned = None
    for t in range(1, M.MERCHANT_STEP_TICKS + 2):
        w.tick()
        if summoned is None and w.logged("summon"):
            summoned = t
    assert set(_count(w, doc).values()) == {1}
    # the blind staffing waits out every look, and the whole run ends before R17M's verify starts
    assert summoned == M.MERCHANT_LOAD_WAIT + (M.MERCHANT_POLLS - 1) * M.MERCHANT_POLL_EVERY
    assert w.forced == set() and w.pending == []
    assert M.MERCHANT_STEP_TICKS <= M.MERCHANT_STEP_SECONDS * 20


def test_a_seen_seat_is_staffed_as_soon_as_its_merchant_arrives():
    doc, fns = _new_pack()
    w = LateWorld(fns, delay=100)
    _seed(w, doc)
    w.function(_start(TOWN), w.server())
    w.tick(99)
    assert not w.logged("summon")                  # nothing summoned before the old merchants are in
    w.tick(21)
    assert len(w.logged("summon")) == len(_merchants(doc))


# ------------------------------------------------------------------------------------------------ generator mutations
def test_reverting_the_fix_in_the_generator_doubles_again(monkeypatch):
    """The generator mutated, the data untouched: one look, so every seat is staffed blind at 40 ticks, the old
    shape's timing. The same world that the fixed generator leaves at one merchant a stall is doubled again."""
    doc = M.load()
    monkeypatch.setattr(M, "MERCHANT_POLLS", 1)
    w = LateWorld(_functions(M.build(doc, {})[0]), delay=200)
    _seed(w, doc)
    w.run(_start(TOWN), M.MERCHANT_STEP_TICKS + 1)
    assert set(_count(w, doc).values()) == {2}, _count(w, doc)


def test_a_look_that_proves_nothing_is_caught_by_the_audit(monkeypatch):
    """The seat marked shown on a selector that does not prove its chunk is loaded (any merchant anywhere), and the
    blind staffing dropped: merchant_problems names every seller both ways."""
    doc = M.load()
    every = {"%s %s" % (kind, s["id"]) for s, kind in M.merchant_records(doc)}
    named = lambda files, needle: {p.split(" merchant:")[0] for p in M.output_problems(doc, files) if needle in p}
    monkeypatch.setattr(M, "seat_shown", lambda cfg, m: ["@e[type=%s]" % cfg["kind"]])
    files = M.build(doc, {})[0]
    monkeypatch.undo()
    assert named(files, "does not look for the merchant or the dialogue keeper on its seat") == every
    real = M.merchant_functions
    monkeypatch.setattr(M, "merchant_functions", lambda d, p: {
        k: [x for x in v if "matches ..0 run scoreboard players set #seat_" not in x] for k, v in real(d, p).items()})
    assert named(M.build(doc, {})[0], "never staffs the seat blind") == every
