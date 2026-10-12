"""ENGINE-SCALE: the keeper's pass is split into scheduled calls, so its longest command chain is one slot's work.

maxCommandChainLength (65,536) is a quota per execution context: a scheduled function opens one, and every command it
reaches by `function` (and every fork of `execute as`) spends from it. The keeper used to reach every slot's member pass
in one chain: 54,739 commands by the independent audit's static count with three dungeons, 78,856 with four, and the
pocket holds sixteen (engine.slots). tools/dungeon.py now has the keeper count #up and schedule keeper/head, each live
slot's slot/s<g>/pass and keeper/end for the next tick, each its own chain.

What is measured here, on the generated text with the independent audit's own counter (count_commands: a `function`
call counts the callee's commands, `schedule function` does not):
  * every chain the pass opens (the keeper and each function it schedules) is under the limit with the real three and
    four dungeons and a synthetic sixteen (the four records duplicated under new ids);
  * a slot's pass reaches no other slot's functions and none of the shared fan-outs over every slot or dungeon (m/end,
    m/lines: it ends a run through its own slot/s<g>/end and m/lines_<short>), so its chain is its own slot's work;
    what still grows is m/margin's two lines a dungeon (the audit and its tests read it by name);
  * the audit's LIMIT check still bites: the generator mutated to call instead of schedule (dungeon.DISPATCH) re-joins
    the chain, and the audit names the keeper.

Written by the implementer (ENGINE-SCALE) as a measurement; the behaviour of the split pass is tests/test_dungeon*.py
on tests/pocket_sim.py and tools/dungeon_independent_audit.py's simulated runs.
"""
from __future__ import annotations

import copy
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import dungeon as D  # noqa: E402
import dungeon_independent_audit as A  # noqa: E402

FN = A.FN


def build(doc):
    """The pack, without data/dungeons.json's validation (problems(): tests/test_dungeon*.py run it; a synthetic doc
    duplicates rips and rows that it would rightly refuse, and it is most of a build's time). A duplicate's rooms roll
    as its original's do: the room kit seeds each room's dressing with the record's id (dungeon_rooms.rng), and a new
    id rolls new dressing, which the kit may refuse (the Ash Bell's bell_pit under another id: "pits the dressing
    made are still there")."""
    import dungeon_rooms as DR
    saved, saved_rng = D.problems, DR.rng

    def rng(d, room, salt=""):
        base = re.sub(r"_x\d+$", "", d["id"])
        return saved_rng(dict(d, id=base) if base != d["id"] else d, room, salt)
    D.problems = lambda *a, **k: []
    DR.rng = rng
    try:
        return D.build(doc)
    finally:
        D.problems, DR.rng = saved, saved_rng


def doc_of(n):
    """The real records cut to the first n (n <= 4), or the four repeated to n under new ids and shorts."""
    doc = D.load()
    real = doc["dungeons"]
    if n <= len(real):
        doc["dungeons"] = real[:n]
        return doc
    out = list(real)
    for i in range(len(real), n):
        d = copy.deepcopy(real[i % len(real)])
        d["id"] = "%s_x%d" % (d["id"], i)
        d["short"] = "%s%d" % (d["short"], i)
        d["name"] = "%s %d" % (d["name"], i)
        out.append(d)
    doc["dungeons"] = out
    return doc


def pass_chains(files):
    """{root: static count} for the keeper and every function it schedules: the chains one keeper pass opens."""
    pack = A.Pack(files)
    memo = {}
    roots = [FN + "keeper"] + [m.group(1) for ln in pack.lines(FN + "keeper")
                               for m in [re.search(r"\bschedule function (\S+) ", ln)] if m]
    return pack, {r: A.count_commands(pack, r, memo) for r in dict.fromkeys(roots)}


def reach(pack, start):
    seen, todo = set(), [start]
    while todo:
        f = todo.pop()
        if f in seen:
            continue
        seen.add(f)
        for ln in pack.lines(f):
            todo += re.findall(r"(?:^|\brun )function (\S+)", ln)
    return seen


@pytest.fixture(scope="module", params=[4, pytest.param(16, marks=pytest.mark.slow)])
def built(request):
    doc = doc_of(request.param)
    assert len(doc["dungeons"]) == request.param
    files = build(doc)
    pack, chains = pass_chains(files)
    return request.param, doc, pack, chains


def test_every_chain_of_the_keepers_pass_is_under_the_limit(built):
    n, doc, pack, chains = built
    slots = D.slots(doc)
    passes = {FN + "slot/s%d/pass" % s["g"] for s in slots}
    assert passes <= set(chains), "the keeper does not schedule every slot's pass"
    assert {FN + "keeper/head", FN + "keeper/end"} <= set(chains)
    worst = max(chains.items(), key=lambda kv: kv[1])
    print("%d dungeons, %d slots: the longest chain of a keeper pass is %s at %d commands (limit %d); the keeper "
          "itself %d" % (n, len(slots), worst[0].split(":", 1)[1], worst[1], A.CHAIN_LIMIT, chains[FN + "keeper"]))
    assert worst[1] < A.CHAIN_LIMIT, worst
    # the keeper calls nothing: every part of its pass is scheduled
    assert not [ln for ln in pack.lines(FN + "keeper") if re.search(r"(?:^|\brun )function ", ln)]


def test_a_slots_pass_reaches_no_other_slots_work(built):
    n, doc, pack, chains = built
    shorts = {d["short"] for d in doc["dungeons"]}
    for s in D.slots(doc):
        g, mine = s["g"], s["dungeon"]["short"]
        other = []
        for f in reach(pack, FN + "slot/s%d/pass" % g):
            m = re.match(re.escape(FN) + r"(?:slot/s(\d+)/\w+|room/[^/]+/[^/]+/s(\d+)/[\w/]+)$", f)
            if m and int(m.group(1) or m.group(2)) != g:
                other.append(f)
            # and no function that fans out over every slot or every dungeon (m/end, m/lines: keeper/head's and the
            # rips' callers, which do not know the slot)
            if f in (FN + "m/end", FN + "m/lines"):
                other.append(f)
            m = re.match(re.escape(FN) + r"m/lines_(\w+)$", f)
            if m and m.group(1) in shorts and m.group(1) != mine:
                other.append(f)
        assert not other, (g, sorted(other)[:6])


def test_a_generator_that_calls_its_pass_instead_of_scheduling_it_fails_the_audits_limit(monkeypatch):
    """Mutate the GENERATOR (dungeon.DISPATCH), not the record: the four real dungeons' pass re-joined in one chain
    is over 65,536 and the independent audit's static check names the keeper."""
    monkeypatch.setattr(D, "DISPATCH", "function %s")
    doc = doc_of(4)
    files = build(doc)
    pack, chains = pass_chains(files)
    assert chains[FN + "keeper"] >= A.CHAIN_LIMIT, chains[FN + "keeper"]
    F = A.Findings()
    A.static_audit(pack, doc, A.discover(pack, doc), F)
    named = [f for f in F if f["cat"] == "LIMIT" and f["room"] == "dungeons/keeper"]
    assert named, [A.fmt(f) for f in F][:5]
