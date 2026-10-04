"""Trainer refusals say why (commit 2ff594f): every rctmod dialog file we build carries every refusal context, and a
player whose party is over the level cap is told so near a trainer.

Written by the test author, not by the session that built them. Expectations:

  refusal keys   data/trainer_refusals.json `lines`, the set of contexts rctmod 0.19.0-beta's TrainerMob.replyTo can
                 ask for as that file records it (read from rctmod's source by the implementer; the jar is not in the
                 repository, so the key set itself is RELAYED, not re-measured here). A dialog file replaces rctmod's
                 default whole, so a key missing from it is a refusal said in silence.
  the notice     data/level_cap.json party_notice and its `decision`: rctmod refuses while a party member is STRICTLY
                 over the cap, so the notice fires strictly over it, never at it, never when the cap cannot be read.
                 The pack is RUN: tests/mcfunction_sim.py runs the functions over ticks, its `rctmod player get
                 level_cap` is the only rctmod command it accepts, and the party_compare runmolang is evaluated by
                 tests/nbt_sim.py's Molang with q.player.party.highest_level set by the test.

Not covered, and it needs a running server: that rctmod reads these contexts and says them (and which context each
refusal really asks for); that Cobblemon 1.8.0's runmolang binds q.player.party.highest_level as modelled; that the
tick sweep's cost is acceptable; the co-op hold-off notice (trainers/holdoff_notice), whose leader form selects on
advancements, which the simulator does not model.

Generator mutations run 2026-10-04 (tools edited, data untouched, then restored):
  route_trainers.with_refusals drops missing_required_trainer   19 failed: the every-file test here, and the 13 + 5
                                                                 dialog-key tests in test_route_trainers.py and
                                                                 test_mansion_guardians.py
  levelcap_pack party_notice `>` to `>=` (fires at the cap)      1 failed: the strictly-over test at cap 20, level 20
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

import levelcap_pack as LP  # noqa: E402
import mcfunction_sim as M  # noqa: E402
import nbt_sim as NS  # noqa: E402
import route_trainers as RT  # noqa: E402

REFUSALS = json.loads((ROOT / "data" / "trainer_refusals.json").read_text(encoding="utf-8"))["lines"]
DOC = json.loads((ROOT / "data" / "level_cap.json").read_text(encoding="utf-8"))
NOTICE = DOC["party_notice"]
DIALOGS = "data/rctmod/dialogs/trainers/single/"


@pytest.fixture(scope="module")
def built():
    return RT.files()


# ------------------------------------------------------------------------------------------------ dialog files

# Without it the over-cap refusal (and the League chain's "beat the one before") is silent for every trainer we seat.
def test_every_built_rctmod_dialog_file_holds_every_refusal_key(built):
    dialogs = {k: v for k, v in built.items() if k.startswith(DIALOGS)}
    assert dialogs
    assert {"over_level_cap", "missing_required_trainer"} <= set(REFUSALS)
    for path, d in dialogs.items():
        missing = set(REFUSALS) - set(d)
        assert not missing, "%s lacks %s" % (path, sorted(missing))
        for k in REFUSALS:
            assert isinstance(d[k], list) and d[k], (path, k)
            assert all(isinstance(x.get("text"), str) and x["text"].strip() for x in d[k]), (path, k)


# Without it a trainer we seat would speak rctmod's default (or nothing) instead of a file we checked, or a League
# override with authored lines would lose them.
def test_every_seated_trainer_and_every_authored_league_override_has_a_dialog_file(built):
    seated = {k[len("data/rctmod/mobs/trainers/single/"):-len(".json")]
              for k in built if k.startswith("data/rctmod/mobs/trainers/single/")}
    have = {k[len(DIALOGS):-len(".json")] for k in built if k.startswith(DIALOGS)}
    assert seated and seated <= have
    league = json.loads((ROOT / "data" / "league_trainers.json").read_text(encoding="utf-8"))
    authored = {e["upstream_trainer_id"] for e in league.get("trainers") or []
                if isinstance(e, dict) and e.get("dialogue_text") and e.get("upstream_trainer_id")}
    assert authored <= have


# Without it a refusal line in data/trainer_refusals.json would overwrite a trainer's own authored line.
def test_a_files_own_line_wins_over_a_refusal_line(tmp_path, monkeypatch):
    doc = json.loads((ROOT / "data" / "trainer_refusals.json").read_text(encoding="utf-8"))
    doc["lines"]["on_battle_start"] = "REFUSAL TEXT THAT MUST NOT WIN"
    p = tmp_path / "trainer_refusals.json"
    p.write_text(json.dumps(doc), encoding="utf-8")
    monkeypatch.setattr(RT, "REFUSALS", p)
    out = RT.with_refusals({"on_battle_start": [{"text": "own"}]})
    assert out["on_battle_start"] == [{"text": "own"}]
    assert out["over_level_cap"] == [{"text": doc["lines"]["over_level_cap"]}]


# ------------------------------------------------------------------------------------------------ the over-cap notice

FILES = LP.files(DOC)


def _functions():
    out = {}
    for rel, text in FILES.items():
        if rel.endswith(".mcfunction"):
            ns, _, path = rel[len("data/"):].partition("/function/")
            out["%s:%s" % (ns, path[:-len(".mcfunction")])] = text.splitlines()
    return out


class NoticeWorld(M.World):
    """mcfunction_sim plus Cobblemon's `runmolang "<molang>" <targets>`: q.player.uuid and q.player.party.highest_level
    are the target's, and q.run_command runs as the server."""

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self.highest = {}

    def c_runmolang(self, rest, ctx):
        m = re.fullmatch(r'"(.*)" (\S+)', rest)
        if not m:
            raise M.Unsupported("runmolang %r" % rest)
        targets = self.select(m.group(2), ctx)
        for t in targets:
            q = {"player": {"uuid": t.uuid, "party": {"highest_level": float(self.highest[t.uid])}}}
            for c in NS.Molang(m.group(1)).run(query=q):
                try:
                    self.command(c, self.server())
                except M.Failed:
                    pass
        return len(targets)


def _world(cap, level, dist=5.0):
    w = NoticeWorld(_functions(), spawn=(0.0, 64.0, 0.0))
    w.tags = {k: json.loads(FILES["data/minecraft/tags/function/%s.json" % k])["values"] for k in ("load", "tick")}
    w.run_load()
    w.add(M.Entity("rctmod:trainer", (100.0, 70.0, 100.0)))
    p = w.add_player((100.0 + dist, 70.0, 100.0))
    p.uuid = "0000-player"
    if cap is not None:
        w.rct_cap[p.uid] = cap
    w.highest[p.uid] = level
    return w, p


def _told(p):
    return [m for m in p.messages if NOTICE["text"] in json.dumps(m)]


# Without it a player at the cap (whom rctmod battles) would be told they cannot battle, or one over it never told.
@pytest.mark.parametrize("cap,level,told", [(20, 19, False), (20, 20, False), (20, 21, True), (20, 100, True),
                                            (0, 50, False), (None, 50, False)])
def test_the_notice_fires_only_strictly_over_the_cap_rctmod_reports(cap, level, told):
    w, p = _world(cap, level)
    w.tick(int(NOTICE["period_ticks"]))
    assert bool(_told(p)) == told, (cap, level, p.messages, w.errors)
    if told:
        # the cap the message shows is the score the rctmod command stored, read on this sweep
        (msg,) = _told(p)
        assert {"name": "@s", "objective": LP.CAP} in [c.get("score") for c in msg if isinstance(c, dict)]
        assert w.scores[("e%d" % p.uid, LP.CAP)] == cap


# Without it the notice reads some other number than rctmod's cap: the same command the catch block's check uses.
def test_the_notice_reads_the_cap_with_the_same_rctmod_command_as_the_catch_check():
    def rct(fn):
        return {l.split(" run ", 1)[1] for l in FILES["data/cobblers/function/levelcap/%s.mcfunction" % fn].splitlines()
                if "rctmod " in l and not l.startswith("#")}
    assert rct("party_check") == rct("check") == {"rctmod player get level_cap @s$(x)"}


# Without it the notice speaks from across the map, or not at the radius the data names.
def test_the_notice_needs_a_trainer_within_the_datas_radius():
    r = float(NOTICE["radius"])
    w, p = _world(20, 30, dist=r)
    w.tick(int(NOTICE["period_ticks"]))
    assert _told(p)
    w, p = _world(20, 30, dist=r + 1.0)
    w.tick(int(NOTICE["period_ticks"]))
    assert not _told(p)


# Without it the notice repeats every two seconds while the player stands there, or never again on a later approach.
def test_the_notice_is_said_once_per_approach():
    period = int(NOTICE["period_ticks"])
    w, p = _world(20, 30)
    w.tick(period * 3)
    assert len(_told(p)) == 1
    p.pos[0] += 40.0
    w.tick(period)
    p.pos[0] -= 40.0
    w.tick(period * 2)
    assert len(_told(p)) == 2
    assert not w.errors, w.errors
