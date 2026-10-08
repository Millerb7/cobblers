"""The independent audit of the repeatable Entei (tools/entei_boss.py, data/entei_boss.json), unit ENTEI 2026-10-10.

Written by the test author, not the builder (CLAUDE.md principle 16). The builder's own tests (tests/test_entei_boss.py)
read the generator's text; these RUN the generated pack on tests/pocket_sim.py, a dimension-aware interpreter written
from vanilla semantics, and drive it only through the hooks a player touches: eating the crafted sigil (the
consume_item advancement), clicking the arch (the interaction advancement), a ball (pokemon_captured), a faint
(battle_fainted), logging out and in, a restart, a crash, a blackout. No helper of tools/entei_boss.py computes an
expectation here: the generator is only RUN (and, in the mutation tests, broken) to produce the pack under test.
Expected positions come from data/entei_boss.json's declared origin and spacing, the room's shape from parsing the
generated fill/setblock commands, the bank from its own files, the level-cap comparison from the level-cap pack.

What this does NOT cover (a validity check is not runtime behaviour, .claude/rules/testing.md): whether a 1.21.1
server accepts the sigil's components, whether eating it fires consume_item before the stack shrinks (the order this
file assumes, from Player.eat), whether Cobblemon spawns Entei by command, how it ends a battle on a logout, whether a
capture in flight completes after its target is killed, and whether Fight or Flight makes Entei attack: those are
experiments/EXP-059-entei-boss X2-X4, NOT_EXECUTED. Chunk-load latency is not modelled: an entity is loaded while an
online player is within pocket_sim.LOAD_RANGE of it, else frozen.
"""
from __future__ import annotations

import copy
import json
import math
import random
import re
import sys
from collections import deque
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tests"))
import entei_boss as E  # noqa: E402  (RUN and mutated only; never asked for an expectation)
import pocket_sim as PS  # noqa: E402

DOC = json.loads((ROOT / "data" / "entei_boss.json").read_text(encoding="utf-8"))
POCKET = DOC["pocket"]["dimension"]
NETHER, OVER = "minecraft:the_nether", "minecraft:overworld"
GATE = DOC["gate_flag"]
CAUGHT = DOC["catch"]["advancement"]
LOCK = DOC["lockout"]["ticks"]
PERIOD = DOC["keeper"]["period_ticks"]
SLOTS = DOC["pocket"]["slots"]
OWN = DOC["objectives"]["own"]
PSLOT = DOC["objectives"]["slot"]
CLEARS = DOC["objectives"]["clears"]
SPECIES = DOC["species"]["id"]
FLOOR_Y = DOC["pocket"]["floor_y"]
HALF = DOC["room"]["half"]
EATEN_AT = (123.7, 70.0, -40.2)            # a Nether block the player stands on when they eat it
CHECKPOINT = (4300.5, 89.0, 4850.5)       # an overworld Center (the blackout's own test uses this one)


def centre(k):
    """Slot k's centre column, from the record's declared origin and spacing (origin_why), not from the generator."""
    p = DOC["pocket"]
    return p["origin"][0] + (k - 1) * p["spacing"], p["origin"][1]


def build(out, monkeypatch=None, functions=None, loot=None):
    """Run the generator into `out`; `functions` / `loot` wrap the generator's own emitters (a GENERATOR mutation)."""
    if functions is not None:
        real = E.functions
        monkeypatch.setattr(E, "functions", lambda doc, blackout=None: functions(real(doc, blackout)))
    if loot is not None:
        real_lt = E.loot_table
        monkeypatch.setattr(E, "loot_table", lambda doc: loot(real_lt(doc)))
    files = E.build(E.load())
    E.write(files, out)
    return out


@pytest.fixture(scope="module")
def pack(tmp_path_factory):
    return build(tmp_path_factory.mktemp("entei") / "pack")


# ------------------------------------------------------------------------------------------------ the scene

def sigil(pack):
    r = json.loads((pack / "data" / "cobblers" / "recipe" / "entei_boss" / "ember_sigil.json").read_text(encoding="utf-8"))
    return r["result"]["id"], r["result"]["components"]


def world(pack):
    w = PS.World(pack)
    w.boot()
    w.call("cobblers:entei_boss/place", w.server_ctx())   # reapply R16Q (test_the_rooms_are_rebuilt_by_reapply)
    return w


def champion(w, pack, name, sigils=1, dim=NETHER, pos=EATEN_AT, gate=True):
    p = w.player(name, dim, pos, advancements={GATE} if gate else ())
    item, comps = sigil(pack)
    if sigils:
        p.inventory.append([item, copy.deepcopy(comps), sigils])
    return p


def held(p, pack):
    """How many crafted sigils `p` holds: same item AND the same components (a lookalike does not count)."""
    item, comps = sigil(pack)
    return sum(s[2] for s in p.inventory if s[0] == item and PS.same_components(s[1], comps))


def eat(w, p, pack):
    item, comps = sigil(pack)
    i = next(i for i, s in enumerate(p.inventory) if s[0] == item and PS.same_components(s[1], comps))
    w.eat(p, i)


def passes(w, n=1):
    w.tick(PERIOD * n)


def owner(w, k):
    return w.get("#s%d" % k, OWN) or 0


def pid(w, p):
    return w.get(p.name, DOC["objectives"]["id"])


def in_slot(p, k):
    cx, cz = centre(k)
    return p.dim == POCKET and abs(p.pos[0] - (cx + 0.5)) <= HALF + 1 and abs(p.pos[2] - (cz + 0.5)) <= HALF + 1


def slot_of(p):
    return next((k for k in range(1, SLOTS + 1) if in_slot(p, k)), None)


def bosses(w, k, alive_only=True):
    cx, cz = centre(k)
    return [e for e in w.ents if e.kind == "cobblemon:pokemon" and e.dim == POCKET
            and (e.alive or not alive_only) and e.nbt.get("Pokemon", {}).get("Species") == SPECIES
            and abs(e.pos[0] - cx) <= HALF + 1 and abs(e.pos[2] - cz) <= HALF + 1]


def boss(w, k):
    (b,) = [e for e in bosses(w, k) if w.loaded(e)]
    return b


def arch_click(w, p):
    """Walk to the arch's interaction and click it."""
    arch = min((e for e in w.ents if e.kind == "minecraft:interaction" and e.dim == p.dim),
               key=lambda e: math.dist(e.pos, p.pos))
    p.pos = [arch.pos[0], arch.pos[1], arch.pos[2] + 2.0]
    assert w.click(p), "no interaction within reach"


def blackout(p):
    """What the blackout does to a beaten player: blackout/checkpoint/tp, `execute in minecraft:overworld run tp`
    (test_a_beaten_player_is_sent_out_of_the_pocket_by_the_blackout pins that line)."""
    p.dim, p.pos = OVER, list(CHECKPOINT)


def back_where_eaten(p):
    return (p.dim == NETHER and p.pos[0] == math.floor(EATEN_AT[0]) + 0.5 and p.pos[2] == math.floor(EATEN_AT[2]) + 0.5
            and p.pos[1] == math.ceil(EATEN_AT[1]))


def enter(w, p, pack):
    eat(w, p, pack)
    k = slot_of(p)
    assert k, ("the sigil opened nothing", p, p.messages[-1:])
    return k


# ------------------------------------------------------------------------------------------------ traps: every way out

# Without it a player who wins could be left in a sealed bedrock box: the arch must take them back to the block they
# ate the sigil on and free the slot.
def test_a_winner_walks_out_by_the_arch_to_where_they_ate_the_sigil(pack):
    w = world(pack)
    p = champion(w, pack, "Ash")
    k = enter(w, p, pack)
    passes(w, 3)
    assert w.catch(p, boss(w, k))
    arch_click(w, p)
    assert back_where_eaten(p), p
    passes(w)
    assert owner(w, k) == 0 and not bosses(w, k)


# Without it a player beaten by Entei could stay in the pocket, or leave their slot held and its Entei standing.
def test_a_beaten_player_is_sent_out_of_the_pocket_by_the_blackout(pack):
    import test_blackout_pack as TB
    (line,) = TB.FNS["blackout/checkpoint/tp"]
    assert line.startswith("$execute in minecraft:overworld run tp @s"), line   # the blackout leaves ANY dimension
    w = world(pack)
    p = champion(w, pack, "Ash")
    k = enter(w, p, pack)
    passes(w, 3)
    first = boss(w, k)
    blackout(p)
    passes(w)
    assert owner(w, k) == 0
    # the next player into that slot meets only their own run's Entei: the beaten one is gone, loaded or not
    q = champion(w, pack, "Misty")
    assert enter(w, q, pack) == k
    passes(w, 3)
    assert [e for e in bosses(w, k)] == [boss(w, k)] and first.alive is False


# Without it running from the battle could end the run or strand the player: the Entei stays and the arch still works.
def test_a_flee_keeps_the_run_and_the_way_out(pack):
    w = world(pack)
    p = champion(w, pack, "Ash")
    k = enter(w, p, pack)
    passes(w, 3)
    b = boss(w, k)
    b.pos[0] += DOC["room"]["leash"] + 1.0   # it wanders past the leash after the battle; it is put back on its spot
    passes(w, 4)
    assert boss(w, k) is b and owner(w, k) == pid(w, p) and in_slot(p, k)
    assert abs(b.pos[0] - (centre(k)[0] + 0.5)) < 1e-9
    assert abs(b.pos[2] - (centre(k)[1] + DOC["room"]["spot_dz"] + 0.5)) < 1e-9
    arch_click(w, p)
    assert back_where_eaten(p)


# Without it a player who logs out inside could hold a slot for ever, or log back in to a sealed room with no run.
def test_a_logout_frees_the_slot_and_the_relog_is_sent_back(pack):
    w = world(pack)
    p = champion(w, pack, "Ash")
    k = enter(w, p, pack)
    passes(w, 3)
    p.online = False
    passes(w)
    assert owner(w, k) == 0
    p.online = True
    passes(w)
    assert back_where_eaten(p) and w.get(p.name, PSLOT) == 0


# Without it a restart (or a crash that rolled the scores back to before the entry) leaves the player in the room.
@pytest.mark.parametrize("rollback", [False, True], ids=["restart", "crash_scores_rolled_back"])
def test_a_restart_or_crash_mid_run_never_keeps_the_player_in(pack, rollback):
    w = world(pack)
    p = champion(w, pack, "Ash")
    saved = dict(w.scores)
    k = enter(w, p, pack)
    passes(w, 3)
    p.online = False
    if rollback:
        w.scores = saved                 # the scoreboard as of the autosave before the sigil was eaten
    w.boot()                             # load runs again; schedules from before are gone
    passes(w)
    assert all(owner(w, i) == 0 for i in range(1, SLOTS + 1))
    p.online = True
    passes(w)
    assert p.dim in (NETHER, OVER) and not in_slot(p, k), p


def walkable(pack, k):
    """Every (x, y, z) block a player's feet can stand in, in slot k's room: from the arrival, through air, over a
    solid block, with air above -- read from the GENERATED fill/setblock commands of rooms/s<k>."""
    blocks = room_grid(pack, k)
    open_ = lambda c: blocks.get(c) == "minecraft:air"
    start = arrival(pack, k)
    seen, todo = {start}, deque([start])
    while todo:
        x, y, z = todo.popleft()
        for dx, dy, dz in ((1, 0, 0), (-1, 0, 0), (0, 0, 1), (0, 0, -1), (0, 1, 0), (0, -1, 0)):
            c = (x + dx, y + dy, z + dz)
            if c not in seen and open_(c) and open_((c[0], c[1] + 1, c[2])):
                seen.add(c)
                todo.append(c)
    return seen, blocks


def room_grid(pack, k):
    text = (pack / "data" / "cobblers" / "function" / "entei_boss" / "rooms" / ("s%d.mcfunction" % k)).read_text(encoding="utf-8")
    out = {}
    for line in text.splitlines():
        m = re.fullmatch(r"fill (-?\d+) (-?\d+) (-?\d+) (-?\d+) (-?\d+) (-?\d+) (\S+)", line)
        if m:
            a = [int(v) for v in m.groups()[:6]]
            for x in range(min(a[0], a[3]), max(a[0], a[3]) + 1):
                for y in range(min(a[1], a[4]), max(a[1], a[4]) + 1):
                    for z in range(min(a[2], a[5]), max(a[2], a[5]) + 1):
                        out[(x, y, z)] = m.group(7).split("[")[0]
            continue
        m = re.fullmatch(r"setblock (-?\d+) (-?\d+) (-?\d+) (\S+)", line)
        if m:
            out[tuple(int(v) for v in m.groups()[:3])] = m.group(4).split("[")[0]
    return out


def arrival(pack, k):
    text = (pack / "data" / "cobblers" / "function" / "entei_boss" / "slot" / ("s%d" % k) / "open.mcfunction").read_text(encoding="utf-8")
    m = re.search(r"execute in %s run tp @s (-?[\d.]+) (-?\d+) (-?[\d.]+)" % re.escape(POCKET), text)
    return (math.floor(float(m.group(1))), int(m.group(2)), math.floor(float(m.group(3))))


# Without it the keeper's sweep could send the owner out of their own room from a corner, a wall or a jump: every
# position a player can occupy in the room (each standable block, pressed against each wall, and at a jump's top)
# passes the sweep for the run that owns it.
def test_the_sweep_never_sends_the_owner_out_from_anywhere_they_can_stand(pack):
    for k in range(1, SLOTS + 1):
        cells, _ = walkable(pack, k)
        floor = [c for c in cells if c[1] == FLOOR_Y]
        assert len(floor) >= (2 * HALF + 1) ** 2 - 5, (k, len(floor))  # the whole floor, less the arch's five
        top = max(c[1] for c in cells)
        cells = [c for c in cells if c[1] in (FLOOR_Y, top)]
        w = world(pack)
        players = [champion(w, pack, "P%d" % i) for i in range(1, k + 1)]
        for q in players:
            enter(w, q, pack)
        p = players[-1]
        assert slot_of(p) == k
        for (x, y, z) in sorted(cells):
            for ox, oz in ((0.5, 0.5), (0.3, 0.3), (0.7, 0.7), (0.3, 0.7), (0.7, 0.3)):
                for oy in (0.0, 1.25):
                    p.dim, p.pos = POCKET, [x + ox, y + oy, z + oz]
                    w.call("cobblers:entei_boss/check", PS.Ctx(p, POCKET, p.pos))
                    assert p.dim == POCKET and owner(w, k) == pid(w, p), (k, x, y, z, ox, oy, oz)


# Without it a player could hold two slots at once (two Entei, two drops per lockout), or a slot could stay held by
# someone who is not in it. A seeded walk of eats, clicks, logouts, logins, blackouts and passes by three players.
def test_no_player_ever_holds_two_slots_and_no_absent_owner_survives_a_pass(pack):
    rng = random.Random(20261010)
    w = world(pack)
    ps = [champion(w, pack, n, sigils=40) for n in ("Ash", "Misty", "Brock")]
    start = sum(held(p, pack) for p in ps)
    entries = 0
    for step in range(600):
        p = rng.choice(ps)
        act = rng.choice(["eat", "eat", "click", "logout", "login", "blackout", "pass", "pass", "nether", "wait"])
        if act == "eat" and p.online and not p.dead and held(p, pack):
            before = slot_of(p)
            eat(w, p, pack)
            if slot_of(p) and not before:
                entries += 1
        elif act == "click" and p.online and slot_of(p):
            arch_click(w, p)
        elif act == "logout":
            p.online = False
        elif act == "login":
            p.online = True
        elif act == "blackout" and p.online and slot_of(p):
            blackout(p)
        elif act == "nether" and p.online and not slot_of(p):
            p.dim, p.pos = NETHER, list(EATEN_AT)
        elif act == "wait":
            w.gametime += LOCK
        passes(w) if act == "pass" else w.tick(1)
        owned = [owner(w, k) for k in range(1, SLOTS + 1)]
        held_ids = [o for o in owned if o]
        assert len(held_ids) == len(set(held_ids)), (step, owned)
        if act == "pass":
            for k, o in enumerate(owned, 1):
                if o:
                    (q,) = [q for q in ps if pid(w, q) == o]
                    assert q.online and in_slot(q, k), (step, k, q)
            for q in ps:
                if q.online and q.dim == POCKET:
                    assert slot_of(q) and owner(w, slot_of(q)) == pid(w, q), (step, q)
    assert sum(held(p, pack) for p in ps) + entries == start, "a sigil was lost or made"
    assert entries >= 5, entries


# Without it four players who log out inside would leave every slot busy for good, refusing everyone after them.
def test_logouts_inside_never_fill_the_slots_for_good(pack):
    w = world(pack)
    ps = [champion(w, pack, "P%d" % i) for i in range(SLOTS)]
    for p in ps:
        enter(w, p, pack)
    late = champion(w, pack, "Late")
    eat(w, late, pack)
    assert late.dim == NETHER and held(late, pack) == 1      # busy: refused, sigil back
    for p in ps:
        p.online = False
    passes(w)
    assert all(owner(w, k) == 0 for k in range(1, SLOTS + 1))
    assert enter(w, late, pack) == 1


# ------------------------------------------------------------------------------------------------ traps: the sigil

def refusals(pack):
    """(name, world, player) for every way a sigil can be eaten and open nothing."""
    out = []
    w = world(pack)
    out.append(("overworld", w, champion(w, pack, "Ow", dim=OVER, pos=(4000.5, 70.0, 4000.5))))
    w = world(pack)
    out.append(("before_the_champion", w, champion(w, pack, "Early", gate=False)))
    w = world(pack)
    p = champion(w, pack, "Twice", sigils=2)
    enter(w, p, pack)
    arch_click(w, p)
    w.gametime += LOCK - 1
    out.append(("lockout", w, p))
    w = world(pack)
    p = champion(w, pack, "Inside", sigils=2)
    enter(w, p, pack)
    out.append(("during_a_run", w, p))
    w = world(pack)
    for i in range(SLOTS):
        enter(w, champion(w, pack, "B%d" % i), pack)
    out.append(("every_slot_busy", w, champion(w, pack, "Fifth")))
    return out


def check_refusals(pack):
    for name, w, p in refusals(pack):
        n, dim, pos = held(p, pack), p.dim, list(p.pos)
        mine = [k for k in range(1, SLOTS + 1) if owner(w, k) == (pid(w, p) or -1)]
        eat(w, p, pack)
        assert held(p, pack) == n, (name, "the refused sigil did not come back", p.inventory)
        assert p.dim == dim and p.pos == pos, (name, p)
        assert [k for k in range(1, SLOTS + 1) if owner(w, k) == pid(w, p)] == mine, name
        assert p.messages, (name, "refused without a reason")


# Without it a sigil eaten at the wrong time (wrong dimension, before the Champion, in the lockout, during a run, all
# slots busy) is destroyed: two netherite ingots gone for nothing. The returned item must be the crafted one, with
# every component, so it still opens a slot later.
def test_every_refusal_gives_the_crafted_sigil_back_with_a_reason(pack):
    check_refusals(pack)
    # and the one it gives back still works
    w = world(pack)
    p = champion(w, pack, "Ow", dim=OVER, pos=(4000.5, 70.0, 4000.5))
    eat(w, p, pack)
    p.dim, p.pos = NETHER, list(EATEN_AT)
    assert enter(w, p, pack)


# Without it an entry could be free (the stack never shrinks) or cost two: a run costs exactly one sigil.
def test_a_successful_entry_costs_exactly_one_sigil(pack):
    w = world(pack)
    p = champion(w, pack, "Ash", sigils=3)
    enter(w, p, pack)
    assert held(p, pack) == 2


# Without it the lockout could be shorter than its record (a free second run) or never end.
def test_the_lockout_ends_at_its_ticks_and_not_before(pack):
    w = world(pack)
    p = champion(w, pack, "Ash", sigils=3)
    t0 = w.gametime
    enter(w, p, pack)
    arch_click(w, p)
    w.gametime = t0 + LOCK - 1
    eat(w, p, pack)
    assert p.dim == NETHER and held(p, pack) == 2
    w.gametime = t0 + LOCK
    assert enter(w, p, pack) and held(p, pack) == 1


# Without it a re-export (tools/carry_players.py carries data/scoreboard.dat, not level.dat's Time, so the game clock
# restarts near 0) locks out every player who ever entered until the new clock passes their old entry time: days of
# uptime. Found by this audit: tools/entei_boss.py:433-436 treats a NEGATIVE now - eb.last as inside the lockout.
@pytest.mark.xfail(strict=True, reason="DEFECT tools/entei_boss.py:435-436: `#d matches ..lock-1` also matches a "
                   "negative delta, so a game clock that restarts lower (a re-export) locks a past entrant out")
def test_a_game_clock_that_restarts_lower_never_locks_a_past_entrant_out(pack):
    w = world(pack)
    w.gametime = 5_000_000
    p = champion(w, pack, "Ash", sigils=2)
    enter(w, p, pack)
    arch_click(w, p)
    w.gametime = 200                     # the re-exported world, its scores carried
    w.boot()
    assert enter(w, p, pack)


# Without it a player who has NEVER entered is refused on a world younger than one lockout: `operation -= @s eb.last`
# creates the missing score at 0 (getOrCreatePlayerScore), so the `matches -2147483648..` guard no longer tells
# "never entered" apart. A fresh export is such a world for its first 24,000 ticks.
@pytest.mark.xfail(strict=True, reason="DEFECT tools/entei_boss.py:433-436: the subtraction creates eb.last=0 before "
                   "the guard reads it, so a never-entrant on a clock under the lockout is refused")
def test_a_player_who_never_entered_is_never_locked_out(pack):
    w = world(pack)
    w.gametime = 300
    p = champion(w, pack, "Fresh")
    assert enter(w, p, pack)


# ------------------------------------------------------------------------------------------------ the catch rule

# Without it the first clear could be uncatchable, or every clear after a catch catchable (a legendary per lockout).
def test_the_first_run_is_catchable_and_every_run_after_a_catch_is_not(pack):
    w = world(pack)
    p = champion(w, pack, "Ash", sigils=3)
    k = enter(w, p, pack)
    passes(w, 3)
    assert w.catch(p, boss(w, k)) and CAUGHT in p.advancements and w.get(p.name, CLEARS) == 1
    arch_click(w, p)
    for _ in range(2):
        w.gametime += LOCK
        k = enter(w, p, pack)
        passes(w, 3)
        b = boss(w, k)
        assert not w.catch(p, b), "a second Entei was catchable"
        arch_click(w, p)
    assert p.party == [SPECIES]


# Without it another player could stand in someone's slot long enough to catch their Entei, or a catch by anyone but
# the owner could set a flag: an intruder is sent out on the next pass, and their catch grants nobody anything.
def check_intruder(pack):
    w = world(pack)
    a = champion(w, pack, "Owner")
    k = enter(w, a, pack)
    passes(w, 3)
    b = champion(w, pack, "Intruder", sigils=0)
    b.dim, b.pos = POCKET, [a.pos[0] + 1.0, a.pos[1], a.pos[2]]
    passes(w)
    assert not in_slot(b, k), ("the intruder is still in the owner's room", b)
    assert in_slot(a, k) and owner(w, k) == pid(w, a)
    b.dim, b.pos = POCKET, [a.pos[0] + 1.0, a.pos[1], a.pos[2]]
    assert w.catch(b, boss(w, k))
    assert CAUGHT not in b.advancements and CAUGHT not in a.advancements


def test_an_intruder_is_sent_out_and_their_catch_grants_nobody_the_flag(pack):
    check_intruder(pack)


# Without it a player catches TWO Entei: a catchable one left standing when its run ended (its owner logged out, so
# the keeper's kill could not reach its unloaded chunk) is still there when they log back in, and a catch then is
# outside an owned slot, so the flag is never granted and their next run is catchable again.
@pytest.mark.xfail(strict=True, reason="DEFECT: slot/s<k>/free's kill cannot reach an unloaded Entei "
                   "(tools/entei_boss.py:516) and the stale-run kill runs only for an OWNED slot (:504); caught "
                   "grants only in an owned slot in mode 1 (:565, :582), so a relog catch leaves the flag unset")
def test_any_catch_of_a_boss_entei_makes_the_next_run_uncatchable(pack):
    w = world(pack)
    p = champion(w, pack, "Ash", sigils=2)
    k = enter(w, p, pack)
    passes(w, 3)
    p.online = False
    passes(w)
    p.online = True
    stale = [e for e in bosses(w, k) if w.loaded(e)]
    assert stale, "nothing left standing: the premise is gone, so this would prove nothing"
    assert w.catch(p, stale[0])
    passes(w)
    p.dim, p.pos = NETHER, list(EATEN_AT)
    w.gametime += LOCK
    k = enter(w, p, pack)
    passes(w, 3)
    assert not w.catch(p, boss(w, k)), "a second Entei: %s" % p.party


# Without it the level-100 boss is refused by the level-cap catch block for every player the gate lets in. The cap
# after the Champion is 100 (RCT's maxLevel when no next trainer remains: docs/mechanics/LEAGUE_LEVEL_CAP.md:20,
# relayed from rctmod source, not measured here); the catch block's own generated comparison is run on the simulator.
def test_the_boss_level_is_catchable_under_the_post_champion_cap(pack):
    import levelcap_pack as LP
    w = world(pack)
    p = champion(w, pack, "Ash")
    k = enter(w, p, pack)
    passes(w, 3)
    level = boss(w, k).nbt["Pokemon"]["Level"]
    files = LP.files(json.loads((ROOT / "data" / "level_cap.json").read_text(encoding="utf-8")))
    (check,) = [t for path, t in files.items() if path.endswith("levelcap/check.mcfunction")]
    (line,) = [l for l in check.splitlines() if "cobblers.overcap" in l and l.startswith("execute") and " if score " in l
               and "run tag @s add" in l]
    for obj in ("cobblers.lc_cap", "cobblers.lc_lv"):
        w.objectives.add(obj)

    def refused(cap, lv):
        p.tags.discard("cobblers.overcap")
        w.set(p.name, "cobblers.lc_cap", cap)
        w.set(p.name, "cobblers.lc_lv", lv)
        w.run(line, PS.Ctx(p, p.dim, p.pos))
        return "cobblers.overcap" in p.tags
    assert not refused(100, level), "the boss is over the post-Champion cap"
    assert refused(100, 101) and refused(60, level), "the comparison does not bite: this check proves nothing"


# ------------------------------------------------------------------------------------------------ the economy

def bank_ids():
    ids = set()
    for path in (ROOT / "base-pack" / "cobbleverse" / "config" / "cobbledollars" / "bank.json",
                 ROOT / "modpack" / "config" / "cobbledollars" / "bank.json"):
        if path.is_file():
            ids |= {e["item"] for e in json.loads(path.read_text(encoding="utf-8")).get("bank", []) if e.get("item")}
    ids |= {e["item"] for e in json.loads((ROOT / "data" / "bank.json").read_text(encoding="utf-8")).get("buys", [])
            if isinstance(e, dict) and e.get("item")}
    return ids


def check_drops_unbankable(pack):
    for table in (pack / "data").rglob("loot_table/**/*.json"):
        for pool in json.loads(table.read_text(encoding="utf-8"))["pools"]:
            for e in pool["entries"]:
                assert e["name"] not in bank_ids(), ("a boss drop sells to the bank", table.name, e["name"])
                assert not e["name"].startswith("cobbledollars:"), e["name"]


# Without it a boss that can be fought once per lockout for ever mints money through the bank: no generated drop is on
# the base bank's, our generated bank's or data/bank.json's buy list.
def test_no_generated_drop_sells_to_any_bank(pack):
    assert bank_ids(), "no bank list read: this would prove nothing"
    check_drops_unbankable(pack)


# Without it a farm run could pay twice (a second faint event, a relayed callback) or a catch-mode faint could pay.
def test_one_drop_per_farm_run_and_none_for_a_catch_run_or_outside_the_slot(pack):
    w = world(pack)
    p = champion(w, pack, "Ash", sigils=3)
    k = enter(w, p, pack)
    passes(w, 3)
    b = boss(w, k)
    n = len(p.inventory)
    w.faint(p, b)                                   # catch mode: fainted, nothing paid
    assert len(p.inventory) == n and w.get(p.name, CLEARS) in (None, 0)
    arch_click(w, p)
    p.advancements.add(CAUGHT)                      # as if caught on an earlier run
    w.gametime += LOCK
    k = enter(w, p, pack)
    passes(w, 3)
    b = boss(w, k)
    n = len(p.inventory)
    w.faint(p, b)
    w.faint(p, b)                                   # the same event twice
    drops = p.inventory[n:]
    assert len(drops) == 1 and w.get(p.name, CLEARS) == 1, drops
    names = {e["name"] for pool in json.loads((pack / "data" / "cobblers" / "loot_table" / "entei_boss" / "drops.json")
                                               .read_text(encoding="utf-8"))["pools"] for e in pool["entries"]}
    assert drops[0][0] in names
    arch_click(w, p)
    n = len(p.inventory)
    w.faint(p, b)                                   # out of the slot: an Entei fainted elsewhere pays nothing
    assert len(p.inventory) == n


# Without it the entry is not a sink: the sigil's recipe consumes items the bank values, and nothing the pack runs
# pays money. The cost is read from the generated recipe and priced by the bank's own list.
def test_the_entry_destroys_bank_value_and_no_function_pays_money(pack):
    import economy_audit as EA
    files = {p.relative_to(pack).as_posix(): p.read_text(encoding="utf-8") for p in pack.rglob("*") if p.is_file()}
    prices = EA.bank_effective(json.loads((ROOT / "modpack" / "config" / "cobbledollars" / "bank.json")
                                          .read_text(encoding="utf-8"))["bank"])
    fails, reps = EA.entei_checks(prices, {}, files)
    assert not fails, fails
    (rep,) = [r for r in reps if r.startswith("ENTEI entry:")]
    value = int(re.search(r"\$(\d+) of Bank value", rep).group(1))
    assert value > 0, rep


# ------------------------------------------------------------------------------------------------ world writes

# Without it a room could leak: a player walking, or digging through anything but bedrock, could leave the slot box
# the keeper sweeps (and the sweep would then send them out mid-fight, or never find them). Read from the generated
# fill/setblock commands: through non-bedrock blocks, the arrival reaches no cell the room function does not write.
def test_every_room_is_closed_by_a_bedrock_shell(pack):
    for k in range(1, SLOTS + 1):
        cells, blocks = walkable(pack, k)
        start = arrival(pack, k)
        seen, todo = {start}, deque([start])
        while todo:
            x, y, z = todo.popleft()
            for d in ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1)):
                c = (x + d[0], y + d[1], z + d[2])
                if c in seen:
                    continue
                assert c in blocks, (k, "a dig from the arrival reaches unwritten space at", c)
                if blocks[c] != "minecraft:bedrock":
                    seen.add(c)
                    todo.append(c)
        cx, cz = centre(k)
        assert all(abs(x - cx) <= HALF + 1 and abs(z - cz) <= HALF + 1 for x, _y, z in seen), k
        spot = (cx, FLOOR_Y, cz + DOC["room"]["spot_dz"])
        assert spot in cells and blocks[(spot[0], FLOOR_Y - 1, spot[2])] != "minecraft:air", k


# Without it a room is built in the wrong dimension (the overworld map, over a town) or past the world border: every
# block the rebuild writes is in the pocket, inside the border, and inside the pocket's height.
def test_the_rebuild_writes_only_into_the_pocket_inside_the_border(pack):
    w = PS.World(pack)
    w.boot()
    w.call("cobblers:entei_boss/place", w.server_ctx())
    assert w.block_writes
    gen = json.loads((ROOT / "data" / "portals.json").read_text(encoding="utf-8"))["pocket"]["generator"]
    lo, hi = DOC["pocket"]["border"]
    for dim, cmd in w.block_writes:
        assert dim == POCKET, cmd
        nums = [int(v) for v in re.findall(r"-?\d+", cmd.split(" minecraft:")[0])]
        xs, ys, zs = nums[0::3], nums[1::3], nums[2::3]
        assert all(lo < v < hi for v in xs + zs), cmd
        assert all(gen["min_y"] <= v < gen["min_y"] + gen["height"] for v in ys), cmd
    assert not any(w.forced.values()), "the rebuild left chunks force-loaded"
    arches = [e for e in w.ents if e.kind == "minecraft:interaction"]
    w.call("cobblers:entei_boss/place", w.server_ctx())        # a second rebuild must not stack a second arch
    assert len([e for e in w.ents if e.kind == "minecraft:interaction" and e.alive]) == len(arches) == SLOTS


# Without it the Entei sweep and the portals' rescue fight over the same players: the boss's band (every player in it
# who is not in their own slot is sent out) must not hold a portal room, and the rescue's box (everyone in it below the
# floors is sent home) must not hold a slot. Both boxes are read from the two GENERATED packs.
def test_the_boss_band_and_the_portals_rescue_never_overlap(pack):
    import portals as P
    try:
        import ground as G
        import terrain
        doc = P.load()
        S = P.sites(doc, G.Ground(terrain.env_source_root()))
    except Exception as e:  # the portals' sites need the canonical heightmap
        pytest.skip("NOT_EXECUTED: the portals pack needs the heightmap (%s)" % e)
    files = P.files(doc, S)
    tick = files["data/cobblers/function/portals/tick.mcfunction"]
    (rescue,) = re.findall(r"execute in %s as @a\[x=(-?\d+),y=(-?\d+),z=(-?\d+),dx=(\d+),dy=(\d+),dz=(\d+)\]"
                           % re.escape(POCKET), tick)
    rx, ry, rz, rdx, rdy, rdz = (int(v) for v in rescue)
    keeper = (pack / "data" / "cobblers" / "function" / "entei_boss" / "keeper.mcfunction").read_text(encoding="utf-8")
    (band,) = re.findall(r"execute in %s as @a\[x=(-?\d+),y=(-?\d+),z=(-?\d+),dx=(\d+),dy=(\d+),dz=(\d+)"
                         % re.escape(POCKET), keeper)
    bx, by, bz, bdx, bdy, bdz = (int(v) for v in band)
    for k in range(1, SLOTS + 1):
        for (x, y, z) in room_grid(pack, k):
            assert not (rx <= x <= rx + rdx and rz <= z <= rz + rdz), ("a slot in the portals' rescue box", k, x, z)
    room_tps = re.findall(r"execute in %s run tp @s (-?[\d.]+) (-?[\d.]+) (-?[\d.]+)" % re.escape(POCKET),
                          "\n".join(t for p, t in files.items() if p.endswith(".mcfunction")))
    assert room_tps, "no portal arrival read: this would prove nothing"
    for x, _y, z in room_tps:
        assert not (bx <= float(x) <= bx + bdx + 1 and bz <= float(z) <= bz + bdz + 1), ("a portal room in the band", x, z)


# Without it a re-export (which replaces the pocket's blocks, EXP-047) leaves the slots as void: reapply's R16Q must
# rebuild them, after the portals' R16P (whose pack defines the dimension), and the pack must be world-local.
def test_the_rooms_are_rebuilt_by_reapply_after_the_portals(pack):
    import reapply as R
    assert "cobblers_entei_boss" in R.WORLD_LOCAL
    src = (ROOT / "tools" / "reapply.py").read_text(encoding="utf-8")
    p = src.index('out.append(("R16P"')
    q = src.index('out.append(("R16Q"')
    assert p < q and '("fn", "cobblers:entei_boss/place")' in src[q:q + 300]
    assert (pack / "data" / "cobblers" / "function" / "entei_boss" / "place.mcfunction").is_file()


# ------------------------------------------------------------------------------------------------ mutations
# Each breaks the GENERATOR (its emitters, wrapped), never data/entei_boss.json, and shows the check above goes red.

def test_mutation_a_refusal_that_keeps_the_sigil_is_caught(tmp_path, monkeypatch):
    def drop_give(fns):
        fns["refund"] = [l for l in fns["refund"] if not l.startswith("give ")]
        return fns
    bad = build(tmp_path / "m", monkeypatch, functions=drop_give)
    with pytest.raises(AssertionError, match="did not come back"):
        check_refusals(bad)


def test_mutation_a_sweep_without_the_owner_check_is_caught(tmp_path, monkeypatch):
    def no_owner(fns):
        fns["check"] = [re.sub(r" if score @s eb\.id = #s\d+ eb\.own", "", re.sub(r"if score @s eb\.slot matches \d+ ", "", l))
                        for l in fns["check"]]
        return fns
    bad = build(tmp_path / "m", monkeypatch, functions=no_owner)
    with pytest.raises(AssertionError, match="intruder is still"):
        check_intruder(bad)


def test_mutation_a_bind_without_the_blackout_exemption_is_caught_by_c12(tmp_path, monkeypatch):
    import test_system_contracts as SC
    exempt = json.loads((ROOT / "data" / "blackout.json").read_text(encoding="utf-8"))["claims"]["exempt_tag"]

    def no_exempt(fns):
        for name in [n for n in fns if n.endswith("/bind")]:
            fns[name] = [l for l in fns[name] if l != "tag @s add %s" % exempt]
        return fns
    bad = build(tmp_path / "m", monkeypatch, functions=no_exempt)
    files = {p.relative_to(bad).as_posix(): p.read_text(encoding="utf-8") for p in bad.rglob("*") if p.is_file()}
    with pytest.raises(AssertionError, match="makes a claim"):
        SC.entei_c12(files)


def test_mutation_a_bankable_drop_is_caught(tmp_path, monkeypatch):
    def add_scrap(table):
        table["pools"][0]["entries"].append({"type": "minecraft:item", "name": "minecraft:netherite_scrap", "weight": 1})
        return table
    bad = build(tmp_path / "m", monkeypatch, loot=add_scrap)
    with pytest.raises(AssertionError, match="sells to the bank"):
        check_drops_unbankable(bad)
    import economy_audit as EA
    files = {p.relative_to(bad).as_posix(): p.read_text(encoding="utf-8") for p in bad.rglob("*") if p.is_file()}
    prices = EA.bank_effective(json.loads((ROOT / "modpack" / "config" / "cobbledollars" / "bank.json")
                                          .read_text(encoding="utf-8"))["bank"])
    fails, _r = EA.entei_checks(prices, {}, files)
    assert any("minecraft:netherite_scrap" in f for f in fails), fails
