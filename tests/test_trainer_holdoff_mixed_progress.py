"""The trainer hold-off under a mixed-progress party (tools/route_trainers.py -> cobblers:trainers/cycle).

Written by the test author, not by the session that wrote the cycle, and independent of it: the pack is generated to a
temp directory and run as a datapack through the command interpreter (tests/mcfunction_sim.py), with Cobblemon's
per-player Molang supplied here (tests/nbt_sim.py's Molang) so `runmolang` really reads the player's saved data.

The property: a player who has beaten a placed trainer is never left open to a forced rematch by it, whatever the
rest of the party has done; and a player who has not beaten it can still be battled on sight. Cobblers plays
cooperatively with players at different progress, so "every nearby player has beaten me" is not the condition the
hold-off may depend on.

What a beaten player is, here, is not asserted from the cycle's own shape: the player is made beaten by running the
pack's own win function (cobblers:trainers/won/<id>, what rctmod's defeat_count advancement reward runs), so the
fixture's state is the state the game would hold.

How "can force-battle" is observed: rctmod decides on its own, in the server. Two things the datapack writes are
observable offline and are the whole of what it can say: the mob file's forceBattleOnSight / forceBattleMaxDistance,
and the trainer entity's Cooldown NBT, which rctmod's canBattleAgainst refuses to battle through (docs/STATE.md World
facts, the implementer's read of rctmod 0.19.0-beta). `_can_force_battle` below is therefore the tightest predicate
the simulator allows. If a fix holds the trainer off by some other means -- per-player state rctmod reads, a different
mob flag, an interaction gate -- the predicate has to grow a term for it; it deliberately does not pin `Cooldown:40`
or the `unless entity` clause, so any shape of fix that really stops the rematch passes.

Not covered, and it needs a running server: that rctmod honours Cooldown in canBattleAgainst and answers on_cooldown;
that forceBattleOnSight/forceBattleMaxDistance behave as modelled (the sight check passes through walls, so distance
is the whole of it here); that q.run_command and q.player.uuid work inside runmolang; that a forced battle is what a
player actually experiences when the cooldown lapses. Validity is not runtime behaviour (.claude/rules/testing.md).
"""
from __future__ import annotations

import json
import math
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tests"))

import mcfunction_sim as M  # noqa: E402
import nbt_sim as NS  # noqa: E402
import route_trainers as RT  # noqa: E402

_RECS, _SEATS, _FIELDS = RT.load()
SEATS = {s["id"]: s for s in _SEATS}
# the trainers that battle on sight: the ones a stale "engageable" really forces a rematch on
EYE_IDS = [s["id"] for s in _SEATS if s.get("eye_contact")]


# ------------------------------------------------------------------------------------------------ the runtime

class _PlayerMolang(NS.Molang):
    """Cobblemon's player Molang: q.player.data() is the player's saved compound, and a key never written reads 0."""

    def exec_block(self, stmts):
        for s in stmts:
            parts = s[1].split(".") if s[0] == "assign" else []
            if len(parts) == 3 and parts[0] in ("t", "temp") and isinstance(self.temp.get(parts[1]), dict):
                self.temp[parts[1]][parts[2]] = self.ev(s[2])       # t.d.<key> = 1, into the player's data
            else:
                super().exec_block([s])

    def lookup(self, name):
        try:
            return super().lookup(name)
        except NS.MolangError:
            parts = name.split(".")
            if len(parts) == 3 and parts[0] in ("t", "temp") and isinstance(self.temp.get(parts[1]), dict):
                return 0.0                                          # a field the player has never had reads 0
            raise

    def ev(self, e):
        if e[0] == "call" and e[1] in ("q.player.data", "query.player.data"):
            return self.query["player_data"]
        if e[0] == "call" and e[1] in ("q.player.save_data", "query.player.save_data"):
            return 0.0
        return super().ev(e)


class TrainerWorld(M.World):
    """mcfunction_sim plus `runmolang "<molang>" <targets>`, whose q.run_command runs as the server (a uuid selector).

    The simulator has no runmolang; the cycle is half Molang, so it is added here rather than in the shared sim.
    """

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self.player_data = {}                                       # entity uid -> the player's saved compound

    def c_runmolang(self, rest, ctx):
        m = re.fullmatch(r'"(.*)" (\S+)', rest)
        if not m:
            raise M.Unsupported("runmolang %r" % rest)
        targets = self.select(m.group(2), ctx)
        if not targets:
            raise M.Failed("runmolang: no target")
        for t in targets:
            data = self.player_data.setdefault(t.uid, {})
            cmds = _PlayerMolang(m.group(1)).run(query={"player": {"uuid": t.uuid}, "player_data": data})
            for c in cmds:
                try:
                    self.command(c, self.server())
                except M.Failed:
                    pass                                            # vanilla only logs a failed command
        return len(targets)


@pytest.fixture(scope="module")
def pack(tmp_path_factory):
    out = tmp_path_factory.mktemp("trainers") / "cobblers_trainers"
    RT.main(["--out", str(out)])
    return out


def _mob(pack, tid):
    p = pack / "data" / "rctmod" / "mobs" / "trainers" / "single" / ("%s.json" % tid)
    return json.loads(p.read_text(encoding="utf-8"))


def _can_force_battle(trainer, player, mob):
    """Everything the generated pack says, offline, about this trainer forcing a battle on this player."""
    if not mob.get("forceBattleOnSight"):
        return False
    if math.dist(trainer.pos, player.pos) > float(mob.get("forceBattleMaxDistance", 0.0)):
        return False
    return float(trainer.nbt.get("Cooldown", 0)) <= 0                # rctmod will not battle through a Cooldown


def _world(pack, tid):
    x, y, z = SEATS[tid]["seat"]
    w = TrainerWorld.from_pack(pack, spawn=(x + 0.5, y, z + 0.5))
    w.run_load()
    trainer = w.add(M.Entity("rctmod:trainer", (x + 0.5, y, z + 0.5), nbt={"TrainerId": tid, "InBattle": 0, "Cooldown": 0}))
    return w, trainer


def _player(w, tid, name, offset, beaten):
    """A player one block from the seat; `beaten` runs the pack's own win function for them, as the advancement does."""
    x, y, z = SEATS[tid]["seat"]
    p = w.add_player((x + 0.5 + offset, y, z + 0.5), name=name)
    p.uuid = "uuid-%s" % name
    w.player_data[p.uid] = {}
    if beaten:
        w.function("cobblers:trainers/won/%s" % tid, M.Ctx(p, tuple(p.pos)))
    return p


# Without it two players at different progress silence nothing: the trainer stays live and force-battles the player
# who already beat it every time the party walks past together. This is the cooperative case Cobblers is played in.
# STRICT XFAIL, and the marker is the record of the fault (.claude/rules/testing.md: a failure that stands
# today is marked through, never deleted or loosened, and the fix removes the entry). The fault is real and
# reproduced below; the fix the owner chose (2026-09-29) is per-player trainers through the scene runtime,
# which is gated on EXP-034 and a second Minecraft account. Strict, so that the day the fix lands this test
# passes, the strict marker fails, and whoever fixed it must come back and delete these two lines.
@pytest.mark.xfail(strict=True, reason="mixed-progress hold-off: a shared trainer entity cannot hold off per "
                                       "player; fix is per-player trainers via scenes_pack, gated on EXP-034")
@pytest.mark.parametrize("tid", EYE_IDS)
def test_a_beaten_player_is_not_force_battled_while_an_unbeaten_party_member_stands_with_them(pack, tid):
    w, trainer = _world(pack, tid)
    mob = _mob(pack, tid)
    won = _player(w, tid, "won", +1.0, beaten=True)
    fresh = _player(w, tid, "fresh", -1.0, beaten=False)
    assert _can_force_battle(trainer, won, mob), "fixture: the trainer must start able to battle, or nothing is proven"
    assert _can_force_battle(trainer, fresh, mob)
    w.tick(10)
    assert not _can_force_battle(trainer, won, mob), (
        "%s can still force a rematch on the player who beat it, because %s stands next to them "
        "(trainer NBT %s)" % (tid, fresh.name, trainer.nbt))


# Without it the one case the cycle was written for breaks: a lone player who won is battled again on every pass
# (rctmod forgets the win on a restart, so nothing else stops it).
@pytest.mark.parametrize("tid", EYE_IDS)
def test_a_beaten_player_alone_is_not_force_battled(pack, tid):
    w, trainer = _world(pack, tid)
    mob = _mob(pack, tid)
    won = _player(w, tid, "won", +1.0, beaten=True)
    w.tick(10)
    assert not _can_force_battle(trainer, won, mob), trainer.nbt


# Without it a party that has all beaten the trainer is still force-battled by it.
@pytest.mark.parametrize("tid", EYE_IDS)
def test_a_party_that_has_all_beaten_the_trainer_is_not_force_battled(pack, tid):
    w, trainer = _world(pack, tid)
    mob = _mob(pack, tid)
    a = _player(w, tid, "a", +1.0, beaten=True)
    b = _player(w, tid, "b", -1.0, beaten=True)
    w.tick(10)
    assert not _can_force_battle(trainer, a, mob), trainer.nbt
    assert not _can_force_battle(trainer, b, mob), trainer.nbt


# Without it the hold-off could be fixed by cooling the trainer down always: the eye-contact lesson and every mansion
# room's guard fight would then never happen, because nobody could be battled at all.
@pytest.mark.parametrize("tid", EYE_IDS)
def test_an_unbeaten_player_alone_can_still_be_force_battled(pack, tid):
    w, trainer = _world(pack, tid)
    mob = _mob(pack, tid)
    fresh = _player(w, tid, "fresh", +1.0, beaten=False)
    w.tick(10)
    assert _can_force_battle(trainer, fresh, mob), (
        "%s no longer battles a player who has not beaten it (trainer NBT %s)" % (tid, trainer.nbt))


# Without it the trainer could be held off permanently by an empty room -- a player who arrives later, having beaten
# nobody, walks past a guard that never fights.
@pytest.mark.parametrize("tid", EYE_IDS)
def test_a_newcomer_arriving_at_an_empty_seat_can_still_be_force_battled(pack, tid):
    w, trainer = _world(pack, tid)
    mob = _mob(pack, tid)
    w.tick(30)                                                      # three cycles with nobody near
    fresh = _player(w, tid, "fresh", +1.0, beaten=False)
    w.tick(10)
    assert _can_force_battle(trainer, fresh, mob), trainer.nbt
