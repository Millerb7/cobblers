"""No catching over the level cap (tools/levelcap_pack.py, data/level_cap.json -> build/datapacks/cobblers_levelcap):
the Cobblemon callback and its check function run together, in a MoLang interpreter (tests/nbt_sim.py) wired to a
command interpreter (tests/mcfunction_sim.py), with a thrower whose RCT cap the test sets.

Written by the test author, not by the session that built the pack (c55229a). Expectations are the owner's rule
(data/level_cap.json "decision": strictly over the cap breaks free, at the cap is caught; a cap or level that cannot be
read lets the catch through) and the message text in the data.

Not covered (the owner's in-game proof, docs/research/notes/level-cap-catch-block.md "Smallest proof"): that Cobblemon
1.8.0 fires poke_ball_capture_calculated with q.thrower, q.pokemon, is_player, uuid, add_tag/has_tag/remove_tag and
q.set_shakes as modelled; that `rctmod player get level_cap` returns the cap as its result; that a ball with 0 shakes
breaks free; anything about a Master Ball or a battle capture.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tests"))

import levelcap_pack as LP  # noqa: E402
import mcfunction_sim as M  # noqa: E402
import nbt_sim as NS  # noqa: E402

DOC = json.loads((ROOT / "data" / "level_cap.json").read_text(encoding="utf-8"))
FILES = LP.files(DOC)
CALLBACK_DIR = "data/cobblemon/callbacks/poke_ball_capture_calculated/"
TARGET, OVER = "cobblers.lc_target", "cobblers.overcap"


def callback_src():
    names = [p for p in FILES if p.startswith("data/cobblemon/callbacks/")]
    assert len(names) == 1
    return FILES[names[0]]


def functions():
    out = {}
    for rel, text in FILES.items():
        if rel.endswith(".mcfunction"):
            ns, _, path = rel[len("data/"):].partition("/function/")
            out["%s:%s" % (ns, path[:-len(".mcfunction")])] = text.splitlines()
    return out


class Callback(NS.Molang):
    """The capture callback, with the entity methods the pack calls and q.run_command run by the command interpreter
    as the server (at the world spawn), synchronously, as a MoLang command function returns before the next line."""

    def __init__(self, src, world):
        super().__init__(src)
        self.world = world
        self.shakes = None

    def ev(self, e):
        if e[0] == "call":
            name, args = e[1], [self.ev(a) for a in e[2]]
            if name in ("q.run_command", "query.run_command"):
                self.commands.append(args[0])
                self.world.command(args[0], self.world.server())
                return 1.0
            if name in ("q.set_shakes", "query.set_shakes"):
                self.shakes = int(self.num(args[0]))
                return 1.0
            obj, _, method = name.rpartition(".")
            if method in ("add_tag", "has_tag", "remove_tag"):
                ent = self.lookup(obj)["_entity"]
                if method == "add_tag":
                    ent.tags.add(args[0])
                    return 1.0
                if method == "remove_tag":
                    ent.tags.discard(args[0])
                    return 1.0
                return 1.0 if args[0] in ent.tags else 0.0
        return super().ev(e)


def throw(cap=20, level=21, player=True, stale_over=False, bystander_level=None):
    """One ball: a thrower with RCT cap `cap` (None: rctmod has no cap for them) at a Pokemon of `level` (None: no
    level to read). Returns (world, thrower, target, callback)."""
    w = M.World(functions(), spawn=(0.0, 64.0, 0.0))
    w.tags = {"load": ["cobblers:levelcap/load"], "tick": []}
    w.run_load()
    thrower = w.add(M.Entity("minecraft:player" if player else "cobblemon:pokemon", (100.0, 70.0, 100.0)))
    thrower.uuid = "0000-thrower"
    if stale_over:
        thrower.tags.add(OVER)
    if cap is not None:
        w.rct_cap[thrower.uid] = cap
    nbt = {"Pokemon": {"Level": level}} if level is not None else {"Pokemon": {}}
    target = w.add(M.Entity("cobblemon:pokemon", (104.0, 70.0, 100.0), nbt=nbt))
    if bystander_level is not None:                     # a wild one nearer the thrower than the target
        w.add(M.Entity("cobblemon:pokemon", (101.0, 70.0, 100.0), nbt={"Pokemon": {"Level": bystander_level}}))
    cb = Callback(callback_src(), w)
    cb.run(query={"thrower": {"is_player": 1.0 if player else 0.0, "uuid": thrower.uuid, "_entity": thrower},
                  "pokemon": {"_entity": target}})
    return w, thrower, target, cb


def blocked(cb):
    return cb.shakes == 0


# Without it the callback would sit where Cobblemon never reads it, or override another pack's callback by name.
def test_the_callback_is_a_cobblers_file_in_the_capture_calculated_folder():
    names = [p for p in FILES if p.startswith("data/cobblemon/callbacks/")]
    assert len(names) == 1 and names[0].startswith(CALLBACK_DIR)
    assert names[0][len(CALLBACK_DIR):].startswith("cobblers_") and names[0].endswith(".molang")


# Without it a catch at the cap would be refused (rctmod refuses a battle only strictly over), or one over it allowed.
@pytest.mark.parametrize("cap,level,refused", [(20, 19, False), (20, 20, False), (20, 21, True), (20, 100, True),
                                               (1, 2, True), (100, 100, False)])
def test_a_catch_breaks_free_only_strictly_over_the_throwers_cap(cap, level, refused):
    w, thrower, _t, cb = throw(cap, level)
    assert blocked(cb) is refused
    assert not w.errors, w.errors


# Without it a cap that has not loaded (0, RCT still starting), a player RCT has no cap for, or a level the check could
# not read would refuse every catch.
@pytest.mark.parametrize("cap,level", [(0, 50), (None, 50), (20, 0), (20, None)])
def test_a_cap_or_level_that_cannot_be_read_lets_the_catch_through(cap, level):
    _w, _p, _t, cb = throw(cap, level)
    assert not blocked(cb)


# Without it a Pokemon's own ball, or a dispenser's, would run a player's check, or be refused.
def test_the_callback_acts_only_for_a_player_thrower():
    w, thrower, target, cb = throw(20, 90, player=False)
    assert not blocked(cb) and cb.commands == [] and TARGET not in target.tags


# Without it the player would not be told why the ball broke free, or be told when it did not; and the words would
# break the fiction (the owner: in the player's terms, no gyms, no caps).
def test_the_message_is_the_datas_text_and_goes_only_to_a_refused_thrower():
    _w, thrower, _t, cb = throw(20, 21)
    assert [m["text"] for m in thrower.messages] == [DOC["message"]]
    assert thrower.messages[0].get("color") == DOC.get("message_color", "red")
    low = DOC["message"].lower()
    assert "gym" not in low and "cap" not in low
    _w, thrower, _t, _cb = throw(20, 20)
    assert thrower.messages == []


# Without it a stale answer would carry over: an old over-cap tag on the thrower refusing a later, allowed catch, or
# the target tag left on a Pokemon so a later throw reads the wrong one's level.
def test_no_tag_outlives_the_throw():
    w, thrower, target, cb = throw(20, 20, stale_over=True)
    assert not blocked(cb), "a stale over-cap tag refused a catch at the cap"
    w, thrower, target, cb = throw(20, 30)
    assert blocked(cb)
    assert OVER not in thrower.tags
    assert not [e for e in w.entities if TARGET in e.tags]


# Without it the check would read the level of whichever Pokemon stands nearest the thrower, not the one the ball hit.
def test_the_level_read_is_the_targets_not_a_nearer_pokemons():
    _w, _p, _t, cb = throw(20, 20, bystander_level=90)
    assert not blocked(cb)
    _w, _p, _t, cb = throw(20, 90, bystander_level=5)
    assert blocked(cb)


# Without it rctmod's command, written plainly, may be parsed at server start before the mod registers it (as
# spawnpokemonat was, EXP-046), and the whole check function would never load.
def test_the_rctmod_line_is_a_macro_and_the_callback_passes_its_argument():
    lines = FILES["data/cobblers/function/levelcap/check.mcfunction"].splitlines()
    rct = [l for l in lines if "rctmod" in l and not l.startswith("#")]
    assert rct and all(l.startswith("$") for l in rct)
    assert "levelcap/check {" in callback_src()
    w, _p, _t, _cb = throw(20, 21)
    assert not [e for e in w.errors if "macro" in e]


# Without it the scores the check stores into do not exist, and every store fails (every catch allowed).
def test_the_load_tag_creates_the_checks_objectives():
    assert json.loads(FILES["data/minecraft/tags/function/load.json"])["values"] == ["cobblers:levelcap/load"]
    w = M.World(functions())
    w.tags = {"load": ["cobblers:levelcap/load"], "tick": []}
    w.run_load()
    assert {LP.CAP, LP.LV} <= w.objectives


# Without it the pack goes to the global folder every world loads (the live one included), or reapply's prepare
# fails closed on a pack no step runs.
def test_reapply_installs_it_world_local_and_names_it_self_driving():
    import reapply
    assert "cobblers_levelcap" in reapply.SERVER_PACKS and "cobblers_levelcap" in reapply.WORLD_LOCAL
    assert reapply.EXCLUDED["cobblers_levelcap"].startswith("self-driving")
