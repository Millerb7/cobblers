"""An independent audit of commit 9569c34: tools/entei_boss.py's fixes for review N142's three defects, and the
re-theme of data/entei_boss.json as "The Tower After the Fire".

Written by a test author who wrote neither the generator nor tests/test_entei_boss_audit.py. The generated pack is RUN
on tests/pocket_sim.py (the N142 auditor's interpreter, written from vanilla semantics and not from the generator; the
facts these tests lean on are vanilla: an offline player is in no selector and keeps their scores, an entity in an
unloaded chunk cannot be selected or killed, `scoreboard players operation` creates a missing score at 0, and
`if score` on a missing score is false). Every expectation comes from data/entei_boss.json's declared rules (catch.rule,
lockout.ticks, lockout.never_entered, lockout.clock_reset) and its declared origin and spacing; no helper of
tools/entei_boss.py is asked for one. The generator is only run, and in the mutation tests its SOURCE is edited (the
data is never touched) to show each check bites.

What this does NOT cover (validity is not runtime behaviour, .claude/rules/testing.md):
- whether a capture can complete before the keeper's next pass kills its target. Fix 1, and the two strict xfails
  below, rest on the builder's premise that "a ball can land first" (data/entei_boss.json does_not_cover). If that
  premise is false in game, relog_caught is dead code AND the two xfails are unreachable; EXP-059 must settle it;
- chunk loading as the server does it: pocket_sim loads an entity while an online player in its dimension is within
  128 blocks (x and z); a real server uses view-distance (server/config/server.properties.example: 10 chunks), so a
  player in a neighbouring slot 128 blocks away may keep a logged-out player's room loaded, and no Entei is left;
- `/time set` and `/time add` are not simulated: they change the day time, never the game time (vanilla TimeCommand),
  so the property is checked as "every clock the pack reads is gametime";
- the Mart templates' own stock (data/traders.json stock "regional" lives in the BCA templates, not in data/).
"""
from __future__ import annotations

import copy
import json
import re
import sys
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tests"))
import pocket_sim as PS  # noqa: E402

GEN = ROOT / "tools" / "entei_boss.py"
DOC = json.loads((ROOT / "data" / "entei_boss.json").read_text(encoding="utf-8"))
POCKET = DOC["pocket"]["dimension"]
NETHER, OVER = "minecraft:the_nether", "minecraft:overworld"
GATE = DOC["gate_flag"]
CAUGHT = DOC["catch"]["advancement"]
LOCK = DOC["lockout"]["ticks"]
PERIOD = DOC["keeper"]["period_ticks"]
DELAY = DOC["keeper"]["arrive_delay_ticks"]
SPECIES = DOC["species"]["id"]
HALF = DOC["room"]["half"]
O = DOC["objectives"]
NETHER_AT = (-201.3, 64.0, 77.6)


# ------------------------------------------------------------------------------------------------ the generator, run

def generate(out, edits=()):
    """Run tools/entei_boss.py into `out`, with `edits` (old, new) applied to its SOURCE first: a generator mutation.
    Each `old` must occur exactly once, so a mutation that no longer matches the code fails loudly instead of
    silently testing the unmutated generator."""
    src = GEN.read_text(encoding="utf-8")
    for old, new in edits:
        assert src.count(old) == 1, "mutation target is not in the generator exactly once: %r" % old
        src = src.replace(old, new)
    mod = types.ModuleType("entei_boss_under_audit")
    mod.__file__ = str(GEN)
    exec(compile(src, str(GEN), "exec"), mod.__dict__)
    mod.write(mod.build(mod.load()), out)
    return out


@pytest.fixture(scope="module")
def pack(tmp_path_factory):
    return generate(tmp_path_factory.mktemp("entei_fixes") / "pack")


# ------------------------------------------------------------------------------------------------ the scene

class Broken(AssertionError):
    """A property this file protects does not hold. The mutation tests require THIS, not any assertion."""


def need(cond, prop, detail=""):
    if not cond:
        raise Broken("%s: %s" % (prop, detail))


def centre(k):
    p = DOC["pocket"]
    return p["origin"][0] + (k - 1) * p["spacing"], p["origin"][1]


def key_stack(pack):
    ns, path = DOC["key"]["recipe"]["id"].split(":", 1)
    r = json.loads((pack / "data" / ns / "recipe" / (path + ".json")).read_text(encoding="utf-8"))
    return [r["result"]["id"], copy.deepcopy(r["result"]["components"]), 1]


def world(pack, gametime=1_000_000):
    w = PS.World(pack)
    w.gametime = gametime
    w.boot()
    w.call("cobblers:entei_boss/place", w.server_ctx())
    return w


def player(w, pack, name, keys=4, caught=False):
    p = w.player(name, NETHER, NETHER_AT, advancements={GATE} | ({CAUGHT} if caught else set()))
    stack = key_stack(pack)
    stack[2] = keys
    p.inventory.append(stack)
    return p


def keys_held(p, pack):
    item, comps, _ = key_stack(pack)
    return sum(s[2] for s in p.inventory if s[0] == item and PS.same_components(s[1], comps))


def slot_of(p):
    for k in range(1, DOC["pocket"]["slots"] + 1):
        cx, cz = centre(k)
        if p.dim == POCKET and abs(p.pos[0] - (cx + 0.5)) <= HALF + 1 and abs(p.pos[2] - (cz + 0.5)) <= HALF + 1:
            return k
    return None


def eat(w, p, pack):
    """Eat one key wherever `p` stands. Returns the slot it opened, or None."""
    item, comps, _ = key_stack(pack)
    i = next(i for i, s in enumerate(p.inventory) if s[0] == item and PS.same_components(s[1], comps))
    w.eat(p, i)
    return slot_of(p)


def to_nether(p):
    p.dim, p.pos = NETHER, list(NETHER_AT)


def walk_out(w, p):
    """Leave by the arch (its interaction is the nearest one in the room)."""
    arch = min((e for e in w.ents if e.kind == "minecraft:interaction" and e.dim == p.dim),
               key=lambda e: (e.pos[0] - p.pos[0]) ** 2 + (e.pos[2] - p.pos[2]) ** 2)
    p.pos = [arch.pos[0], arch.pos[1], arch.pos[2] + 2.0]
    assert w.click(p)
    to_nether(p)


def passes(w, n=1):
    w.tick(PERIOD * n)


def wait_for_entei(w):
    passes(w, DELAY // PERIOD + 2)


def entei_in(w, k, loaded_only=True):
    cx, cz = centre(k)
    return [e for e in w.ents if e.kind == "cobblemon:pokemon" and e.alive and e.dim == POCKET
            and e.nbt.get("Pokemon", {}).get("Species") == SPECIES
            and abs(e.pos[0] - cx) <= HALF + 1 and abs(e.pos[2] - cz) <= HALF + 1
            and (w.loaded(e) or not loaded_only)]


def bosses_held(p):
    return p.party.count(SPECIES)


def logout(p):
    p.online = False


def login(p):
    p.online = True


def a_run_left_standing(w, pack, p):
    """`p` enters, their Entei appears, they log out alone, and the keeper frees their slot while the room is
    unloaded. Returns the slot. Fails if the premise (an Entei left standing) is not reached."""
    k = eat(w, p, pack)
    assert k, ("the key opened nothing", p.messages[-1:])
    wait_for_entei(w)
    assert entei_in(w, k), "no Entei appeared"
    logout(p)
    passes(w)
    assert w.get("#s%d" % k, O["own"]) == 0, "the slot was not freed"
    assert entei_in(w, k, loaded_only=False) and not entei_in(w, k), "premise: the Entei must be left standing, unloaded"
    return k


# ------------------------------------------------------------------------------------------------ fix 1: the relog catch

def check_relog_catch_sets_the_flag(pack):
    w = world(pack)
    other = player(w, pack, "Bystander", keys=0)              # online throughout, in another dimension
    other.dim, other.pos = OVER, [10.5, 70.0, 10.5]
    a = player(w, pack, "Ash")
    k = a_run_left_standing(w, pack, a)
    login(a)
    (stale,) = entei_in(w, k)
    assert w.catch(a, stale)
    need(CAUGHT in a.advancements, "relog catch", "a catch of one's own left-standing Entei did not grant the flag")
    passes(w)
    to_nether(a)
    w.gametime += LOCK
    k2 = eat(w, a, pack)
    wait_for_entei(w)
    (b,) = entei_in(w, k2)
    need(not w.catch(a, b) and bosses_held(a) == 1, "relog catch", "a second Entei after a relog catch")


# Without it a player catches their run's Entei after a relog and the flag stays unset, so every later run is catchable
# again: one legendary per lockout (review N142 defect 1). Reverting relog_caught's dispatch breaks it.
def test_a_relog_catch_of_ones_own_left_standing_entei_makes_every_later_run_uncatchable(pack):
    check_relog_catch_sets_the_flag(pack)


def check_free_slot_holds_no_entei(pack):
    w = world(pack)
    a = player(w, pack, "Ash")
    k = a_run_left_standing(w, pack, a)
    login(a)
    passes(w)
    need(slot_of(a) is None, "free slot", "the relogger was not sent out")
    need(not entei_in(w, k, loaded_only=False), "free slot",
         "an Entei is still standing in free slot %d after the pass that loaded it" % k)


# Without it a left-standing Entei survives its owner's return and waits, frozen, for whoever is next given the slot.
# Reverting the keeper's free-slot kill breaks it.
def test_a_free_slot_holds_no_entei_after_the_first_pass_that_loads_it(pack):
    check_free_slot_holds_no_entei(pack)


# Without it a catch by one relogger of ANOTHER relogger's left-standing Entei would leave the catcher flagless.
# Two players, two runs of one slot, both logged out, both back: the catch counts for whoever threw the ball.
def test_a_relogger_catching_someone_elses_left_standing_entei_is_flagged(pack):
    w = world(pack)
    a = player(w, pack, "Ash")
    c = player(w, pack, "Cyd")
    k = a_run_left_standing(w, pack, a)
    assert eat(w, c, pack) == k, "the second run did not reuse the freed slot (the test's premise)"
    passes(w)
    assert not [e for e in entei_in(w, k) if w.get(e.uid, O["run"]) != w.get("#s%d" % k, O["run"])], \
        "the first run's Entei survived the second run's first pass"
    wait_for_entei(w)
    logout(c)
    passes(w)
    login(a)
    login(c)
    (stale,) = entei_in(w, k)
    assert w.catch(a, stale)
    assert CAUGHT in a.advancements and bosses_held(a) == 1
    passes(w)
    assert slot_of(a) is None and slot_of(c) is None


# DEFECT (this audit): the slot's NEW owner catches the left-standing Entei of the run before theirs and is not
# flagged, so their own run then spawns a catchable Entei: two legendaries. slot/s<k>/caught returns at `eb.mode` 0
# (tools/entei_boss.py:595: the new run's Entei has not appeared yet), and relog_caught needs the catcher NOT to own
# the slot (:628). Same window as the builder's own fix (one keeper pass, :532 kills it), same premise.
@pytest.mark.xfail(strict=True, raises=Broken, reason="DEFECT tools/entei_boss.py:595 + :628: a new owner's catch of the previous "
                   "run's left-standing Entei grants no flag, so their own catchable Entei is a second")
def test_a_new_owner_cannot_catch_two_entei_through_a_reassigned_slot(pack):
    w = world(pack)
    a = player(w, pack, "Ash")
    b = player(w, pack, "Brock")
    k = a_run_left_standing(w, pack, a)
    assert eat(w, b, pack) == k                    # B is given the slot A's Entei still stands in
    (stale,) = entei_in(w, k)
    assert w.catch(b, stale)
    wait_for_entei(w)
    for e in entei_in(w, k):
        w.catch(b, e)
    need(bosses_held(b) <= 1, "one Entei per player", "B holds %d" % bosses_held(b))


# DEFECT (this audit): a player who already holds the flag, logging back into their old slot after it was given to
# someone else, can catch the new owner's CATCHABLE Entei: a second legendary for them, and the owner's run is spent
# with no Entei and no flag. relog_caught (tools/entei_boss.py:601-610) grants a flag they already hold; nothing
# refuses the ball. data/entei_boss.json catch.why_no_ball_check rests on "nobody else can stand at the Entei to
# throw", which the relog premise (does_not_cover) contradicts for one keeper pass.
@pytest.mark.xfail(strict=True, raises=Broken, reason="DEFECT tools/entei_boss.py:601-610 / data/entei_boss.json catch."
                   "why_no_ball_check: a flagged relogger can catch the new owner's catchable Entei")
def test_a_flagged_relogger_cannot_catch_the_new_owners_entei(pack):
    w = world(pack)
    a = player(w, pack, "Ash")
    k = eat(w, a, pack)
    wait_for_entei(w)
    (first,) = entei_in(w, k)
    assert w.catch(a, first) and CAUGHT in a.advancements
    walk_out(w, a)
    passes(w)
    w.gametime += LOCK
    assert eat(w, a, pack) == k
    wait_for_entei(w)
    logout(a)
    passes(w)
    b = player(w, pack, "Brock")
    assert eat(w, b, pack) == k
    wait_for_entei(w)
    login(a)
    for e in entei_in(w, k):
        w.catch(a, e)
    need(bosses_held(a) <= 1, "one Entei per player", "A holds %d" % bosses_held(a))


# ------------------------------------------------------------------------------------------------ fix 2: the clock

def entered_then_clock_drops(pack, entered_at, now):
    w = world(pack, gametime=entered_at)
    a = player(w, pack, "Ash")
    assert eat(w, a, pack)
    walk_out(w, a)
    passes(w)
    w.gametime = now                                # a re-export: the scores carried, the clock not
    w.boot()
    return w, a


def check_clock_drop_never_locks(pack, drop):
    t0 = 5_000_000
    w, a = entered_then_clock_drops(pack, t0, t0 + PERIOD - drop)
    need(eat(w, a, pack), "clock reset", "a clock %d ticks behind the entry locked the player out" % (drop - PERIOD))


# Without it a clock that restarts lower (a re-export) locks every past entrant out until it catches up: days of
# uptime (review N142 defect 2). Every size of drop, from one tick to the whole clock. Reverting `0..` breaks it.
@pytest.mark.parametrize("drop", [PERIOD + 1, PERIOD + 2, PERIOD + LOCK - 1, PERIOD + LOCK, PERIOD + LOCK + 1,
                                  PERIOD + 4_999_999, PERIOD + 5_000_000])
def test_a_game_clock_that_went_back_by_any_amount_never_locks_a_past_entrant_out(pack, drop):
    check_clock_drop_never_locks(pack, drop)


# Without it the fix could have opened the lockout instead of fixing it: an entrant is refused (key returned) for
# exactly LOCK ticks from entry, counting the entry tick itself, and admitted from then on.
@pytest.mark.parametrize("dt,admitted", [(0, False), (1, False), (LOCK - 1, False), (LOCK, True), (LOCK + 1, True),
                                         (40 * LOCK, True)])
def test_the_lockout_lasts_exactly_its_ticks_from_entry(pack, dt, admitted):
    w = world(pack)
    a = player(w, pack, "Ash", keys=2)
    t0 = w.gametime
    assert eat(w, a, pack)
    walk_out(w, a)
    w.gametime = t0 + dt
    got = eat(w, a, pack)
    assert bool(got) == admitted, (dt, a.messages[-1:])
    assert keys_held(a, pack) == (0 if admitted else 1)


# Without it a reset would end the lockout for good: after the clock goes back, the next entry stamps the new clock
# and the lockout runs again from there.
def test_after_a_clock_reset_the_lockout_runs_again_from_the_new_entry(pack):
    w, a = entered_then_clock_drops(pack, 5_000_000, 200)
    assert eat(w, a, pack)
    walk_out(w, a)
    w.gametime = 200 + LOCK - 1
    assert not eat(w, a, pack)
    w.gametime = 200 + LOCK
    assert eat(w, a, pack)


def check_run_across_reset_gets_its_entei(pack):
    w = world(pack, gametime=5_000_000)
    a = player(w, pack, "Ash")
    k = eat(w, a, pack)
    passes(w)                                       # inside the arrival delay: no Entei yet
    assert not entei_in(w, k)
    w.gametime = 300                                # the server comes back on a lower clock, the owner still in it
    w.boot()
    wait_for_entei(w)
    need(len(entei_in(w, k)) == 1, "arrival across a reset", "no Entei %d ticks after a clock reset" % (DELAY + 2 * PERIOD))


# Without it a run in progress when the clock goes back gets no Entei until the clock passes its old entry time: the
# key is spent for nothing. Reverting the eb.at restart breaks it.
def test_a_run_in_progress_across_a_clock_reset_still_gets_its_entei(pack):
    check_run_across_reset_gets_its_entei(pack)


# Without it `/time set` (or `/time add`) could move or end a lockout: every clock the pack reads is the game time,
# which those commands never change, and the pack never sets the time itself.
def test_time_set_cannot_move_the_lockout(pack):
    lines = [l for f in (pack / "data").rglob("*.mcfunction") for l in f.read_text(encoding="utf-8").splitlines()
             if not l.lstrip().startswith("#")]
    queries = [l for l in lines if re.search(r"\btime\s+query\b", l)]
    assert queries and all(re.search(r"\btime query gametime\b", l) for l in queries), queries
    assert not [l for l in lines if re.search(r"\btime\s+(set|add)\b", l)]


# ------------------------------------------------------------------------------------------------ fix 3: never entered

def check_never_entrant_admitted(pack, now):
    w = world(pack, gametime=now)
    p = player(w, pack, "Fresh")
    need(eat(w, p, pack), "never entered", "a never-entrant refused at gametime %d: %s" % (now, p.messages[-1:]))


# Without it a player who has never entered is refused on a world younger than one lockout (review N142 defect 3): a
# fresh export's first 24,000 ticks. From its first tick on. Reverting the conditional subtraction breaks it.
@pytest.mark.parametrize("now", [0, 1, PERIOD, LOCK - 1])
def test_a_never_entrant_is_admitted_from_a_fresh_worlds_first_tick(pack, now):
    check_never_entrant_admitted(pack, now)


def check_never_entered_vs_locked_out(pack):
    w = world(pack, gametime=0)
    locked = player(w, pack, "Locked")
    need(eat(w, locked, pack), "never entered", "a never-entrant refused on the first tick")
    walk_out(w, locked)
    passes(w)
    w.gametime = 300
    fresh = player(w, pack, "Fresh")
    assert not eat(w, locked, pack) and keys_held(locked, pack) == 3, "the entrant at tick 0 was not locked out"
    assert locked.messages[-1:] and DOC["message"]["refund_lockout"] in json.dumps(locked.messages[-1], ensure_ascii=False)
    need(eat(w, fresh, pack), "never entered", "the never-entrant was refused beside a locked-out player")


# Without it the pack cannot tell "never entered" from "entered at tick 0" on a young world: one must be admitted
# and the other told the lockout, side by side.
def test_a_never_entrant_and_a_locked_out_player_are_told_apart(pack):
    check_never_entered_vs_locked_out(pack)


def check_refusal_starts_no_lockout(pack):
    w = world(pack, gametime=300)
    p = player(w, pack, "Fresh")
    p.dim, p.pos = OVER, [10.5, 70.0, 10.5]
    assert not eat(w, p, pack) and keys_held(p, pack) == 4          # refused: not in the Nether
    need(w.get(p.name, O["last"]) is None, "refusal starts no lockout", "a refusal wrote eb.last")
    to_nether(p)
    need(eat(w, p, pack), "refusal starts no lockout", "refused after an earlier refusal")


# Without it a never-entrant who eats the key in the wrong place first (any refusal) starts a lockout they never ran.
def test_a_refusal_for_another_reason_starts_no_lockout(pack):
    check_refusal_starts_no_lockout(pack)


# ------------------------------------------------------------------------------------------------ the mutations

RELOG_DISPATCH = ('        if target == "caught":\n', '        if False:\n')
FREE_SLOT_KILL = ('"execute if score #s%d %s matches 0 run kill @e[type=cobblemon:pokemon,tag=%s.s%d]"',
                  '"# mutant: no free-slot kill %d %s %s %d"')
LOCK_NONNEG = ('matches 0..%d run scoreboard players set #why %s 4', 'matches ..%d run scoreboard players set #why %s 4')
AT_RESTART = ('"execute if score #d %s matches ..-1 run scoreboard players operation %s %s = #now %s"',
              '"# mutant: no eb.at restart %s %s %s %s"')
SUB_GUARDED = [('"execute if score @s %s matches -2147483648.. run scoreboard players operation #d %s = #now %s" % (LAST, W, W)',
                '"scoreboard players operation #d %s = #now %s" % (W, W)'),
               ('"execute if score @s %s matches -2147483648.. run scoreboard players operation #d %s -= @s %s" % (LAST, W, LAST)',
                '"scoreboard players operation #d %s -= @s %s" % (W, LAST)')]

MUTATIONS = {
    "fix1_relog_caught_dispatch_removed": ([RELOG_DISPATCH], check_relog_catch_sets_the_flag),
    "fix1_free_slot_kill_removed": ([FREE_SLOT_KILL], check_free_slot_holds_no_entei),
    "fix2_negative_delta_inside_lockout": ([LOCK_NONNEG], lambda p: check_clock_drop_never_locks(p, PERIOD + 4_999_999)),
    "fix2_arrival_stamp_not_restarted": ([AT_RESTART], check_run_across_reset_gets_its_entei),
    "fix3_subtraction_unguarded": (SUB_GUARDED, lambda p: check_never_entrant_admitted(p, 300)),
    "fix3_subtraction_unguarded_side_by_side": (SUB_GUARDED, check_never_entered_vs_locked_out),
    "fix3_subtraction_unguarded_after_refusal": (SUB_GUARDED, check_refusal_starts_no_lockout),
}


# Without it the checks above could pass against a generator that never had the fixes: each reverts one fix in
# tools/entei_boss.py's SOURCE (data/entei_boss.json untouched) and requires the matching property to break.
@pytest.mark.parametrize("name", sorted(MUTATIONS))
def test_reverting_each_fix_in_the_generator_breaks_its_property(name, tmp_path):
    edits, check = MUTATIONS[name]
    mutant = generate(tmp_path / "mutant", edits)
    with pytest.raises(Broken):
        check(mutant)


# ------------------------------------------------------------------------------------------------ the re-theme

FIRE_WORDS = re.compile(r"\b(ember\w*|heat\w*|flame\w*|blaz\w*|burn\w*|magma\w*|lava|inferno|scorch\w*|smoulder\w*|"
                        r"sigil\w*|fire\w*)\b", re.I)


def visible_texts(pack):
    """Every string a player can read: tellraw bodies in the generated functions, the key's name and lore."""
    out = []
    for f in (pack / "data").rglob("*.mcfunction"):
        for l in f.read_text(encoding="utf-8").splitlines():
            m = re.match(r"(?:.* run )?tellraw @s (.+)$", l)
            if m:
                body = json.loads(m.group(1))
                for part in body if isinstance(body, list) else [body]:
                    if isinstance(part, dict) and "text" in part:
                        out.append(part["text"])
                    elif isinstance(part, str):
                        out.append(part)
    _, comps, _ = key_stack(pack)
    out.append(json.loads(comps["minecraft:item_name"])["text"])
    out += [json.loads(l)["text"] for l in comps.get("minecraft:lore", [])]
    return [t for t in out if t]


# Without it the re-theme could leave the first build's fire voice in front of a player (NETHER_ENCOUNTERS.md 3.1:
# "the grief of the place, not its heat"). "fire" is allowed only as the section's own phrase, "after the fire".
def test_no_player_visible_text_speaks_of_fire(pack):
    texts = visible_texts(pack)
    assert len(texts) >= len(DOC["message"]), texts
    bad = [t for t in texts if FIRE_WORDS.search(re.sub(r"(?i)\bafter the fire\b", "", t))]
    assert not bad, bad


# Without it a drop could carry a fire name back in (Fire Gem, Heat Rock, Flame Orb, Magmarizer were the first table).
def test_no_drop_is_fire_named(pack):
    lt = json.loads((pack / "data" / "cobblers" / "loot_table" / "entei_boss" / "drops.json").read_text(encoding="utf-8"))
    ids = [e["name"] for pool in lt["pools"] for e in pool["entries"]]
    assert ids and not [i for i in ids if re.search(r"fire|flame|heat|magma|ember|blaze|lava|burn", i)], ids


VANILLA_FLAMMABLE = re.compile(r"(planks|_log\b|_wood\b|_stem\b|hyphae|leaves|wool|carpet|bookshelf|hay_block|"
                               r"scaffolding|tnt|vine|dried_kelp|coal_block|target|lectern|_fence|bamboo|beehive|"
                               r"bee_nest|campfire|azalea)")


def room_writes(pack):
    """[(lo, hi, block)] for every setblock and fill in slot 1's room function, in order (a later write wins)."""
    text = (pack / "data" / "cobblers" / "function" / "entei_boss" / "rooms" / "s1.mcfunction").read_text(encoding="utf-8")
    out = []
    for l in text.splitlines():
        m = re.search(r"\bsetblock (-?\d+) (-?\d+) (-?\d+) (\S+)", l)
        if m:
            c = tuple(int(m.group(i)) for i in (1, 2, 3))
            out.append((c, c, m.group(4)))
            continue
        m = re.search(r"\bfill (-?\d+) (-?\d+) (-?\d+) (-?\d+) (-?\d+) (-?\d+) (\S+)", l)
        if m:
            a = [int(m.group(i)) for i in range(1, 7)]
            out.append((tuple(min(a[i], a[i + 3]) for i in range(3)), tuple(max(a[i], a[i + 3]) for i in range(3)),
                        m.group(7)))
    assert out, "the room function writes no blocks"
    return out


def block_at(writes, cell):
    got = None
    for lo, hi, b in writes:
        if all(lo[i] <= cell[i] <= hi[i] for i in range(3)):
            got = b
    return got


# Without it the decor could be a thing that burns, or a block that falls into a hole: every decor entry is a
# non-flammable vanilla block set into the floor course (y = floor_y - 1), which the room's function really writes.
def test_the_decor_cannot_burn_and_is_set_into_the_floor_course(pack):
    cx, cz = centre(1)
    sx, sz = cx, cz + DOC["room"]["spot_dz"]
    fy = DOC["pocket"]["floor_y"] - 1
    writes = room_writes(pack)
    decor = DOC["room"]["decor"]
    assert decor
    for d in decor:
        assert not VANILLA_FLAMMABLE.search(d["block"]), d
        cell = (sx + d["dx"], fy, sz + d["dz"])
        assert block_at(writes, cell) == d["block"], (d, block_at(writes, cell))
        assert block_at(writes, (cell[0], cell[1] - 1, cell[2])) == "minecraft:bedrock", ("not on bedrock", d)
        assert block_at(writes, (cell[0], cell[1] + 1, cell[2])) == "minecraft:air", ("not open above", d)


def bank_buys():
    b = json.loads((ROOT / "modpack" / "config" / "cobbledollars" / "bank.json").read_text(encoding="utf-8"))["bank"]
    d = json.loads((ROOT / "data" / "bank.json").read_text(encoding="utf-8"))["buys"]
    return {e["item"] for e in b} | {e["item"] for e in d}


def stock_items(node, out, path=""):
    """Every `item` in a `stock` list anywhere in a document (superseded stock is not stock)."""
    if isinstance(node, dict):
        for k, v in node.items():
            if k == "stock" and isinstance(v, list):
                for e in v:
                    if isinstance(e, dict) and "item" in e:
                        out.append((e["item"], path))
            stock_items(v, out, path + "/" + str(node.get("id", k)))
    elif isinstance(node, list):
        for v in node:
            stock_items(v, out, path)
    return out


def drop_ids():
    return [e["item"] for e in DOC["drops"]["entries"]]


# Without it a farm-mode run is a money printer: no drop and no room block is on the CobbleDollars bank's buy list
# (the generated bank and data/bank.json buys, read here, not through the generator's bank check).
def test_no_drop_or_room_block_is_bankable(pack):
    buys = bank_buys()
    assert len(buys) > 40
    assert not set(drop_ids()) & buys
    blocks = {re.sub(r"\[.*$", "", b) for _, _, b in room_writes(pack)}
    assert not blocks & buys, blocks & buys


# Without it the key could be bought with money (no cash path to a run): nothing the key is made of, nor the key's
# item, is in any counter's or stall's stock.
def test_no_key_ingredient_or_the_key_item_is_sold(pack):
    stock = {i for i, _ in stock_items(json.loads((ROOT / "data" / "markets.json").read_text(encoding="utf-8")), [])}
    stock |= {i for i, _ in stock_items(json.loads((ROOT / "data" / "traders.json").read_text(encoding="utf-8")), [])}
    assert len(stock) > 50
    want = {DOC["key"]["item"]} | {g["item"] for g in DOC["key"]["recipe"]["ingredients"]}
    assert not want & stock, want & stock


# FINDING (this audit, against the brief's property "drops absent from every counter's stock"): cobblemon:charcoal_stick
# is a farm drop AND a $1,000 counter line (data/markets.json:299, Rim Ironmonger). Not an arbitrage (no counter buys
# it back), but a repeatable post-Champion source of a stocked power line. data/entei_boss.json drops.why_these says it
# knowingly ("a single shop line"); if the owner accepts that, delete this test with that decision cited.
@pytest.mark.xfail(strict=True, raises=AssertionError, reason="FINDING data/entei_boss.json drops + data/markets.json:299: charcoal_stick is "
                   "both a repeatable boss drop and counter stock")
def test_no_drop_is_counter_stock():
    stock = stock_items(json.loads((ROOT / "data" / "markets.json").read_text(encoding="utf-8")), [])
    hit = [(i, where) for i, where in stock if i in set(drop_ids())]
    assert not hit, hit


# FINDING (this audit): cobblemon:life_orb is an arena prize given once per player (data/arena_fights.json prizes.items),
# and the owner's decision arena_trophies_not_sold (data/markets.json decisions, 2026-10-09) is "A prize you can buy is
# not a prize". A 1-in-6 drop every farm-mode run is a repeatable source of the same trophy. Owner to rule.
@pytest.mark.xfail(strict=True, raises=AssertionError, reason="FINDING data/entei_boss.json drops: life_orb is a once-per-player arena prize "
                   "(arena_trophies_not_sold) and a repeatable boss drop")
def test_no_drop_is_a_once_per_player_arena_prize():
    arena = json.loads((ROOT / "data" / "arena_fights.json").read_text(encoding="utf-8"))
    prizes = {c["item"] for p in arena["prizes"]["items"] for c in p["contents"]}
    assert prizes
    assert not set(drop_ids()) & prizes, set(drop_ids()) & prizes
