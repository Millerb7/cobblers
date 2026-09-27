"""Guardian recovery by the Pokemon's UUID, and the claim paths added with it (c9cb850, f08117e, 3e2906e).

Written by the test author, not by the session that wrote tools/blackout_pack.py. It runs the generated functions on
tests/nbt_sim.py's NbtSim (command storage as NBT, paths by NbtPathArgument's grammar) and the generated MoLang
callbacks on its MoLang-subset interpreter, feeding each callback's q.run_command text into the same simulator.

Independent sources:
  - Java's UUID.toString of a UUID stored as an int array (Minecraft's UUIDUtil: most significant bits = ints 0 and 1,
    least = ints 2 and 3), computed here with Python's uuid module; Cobblemon 1.8.0's MoLang `pokemon.id` is that text
    (the owner's bytecode check quoted in c9cb850: PokemonMoLangFunctions id = Pokemon.getUuid()).
  - Minecraft 1.21.1 scoreboard `%=` is floor-mod and `/=` floor-div (the simulator's arithmetic, checked below).
  - The owner's statements quoted in c9cb850: beating or catching a guardian resolves its claims; running away is not
    a blackout (a loss needs the whole party fainted); a wild Pokemon killing the player outside battle takes items
    like a battle loss; a rebuilt guardian spawns as its own species and level, not a Magikarp; the claim message
    names the items taken ("10 Ultra Ball"), not their category.
  - data/blackout.json claims lists (the claimable items) and vanilla's item translation key, item.<ns>.<path>.
  - 3e2906e's data and the owner's words it quotes: money percent, category quotas and (4a37312) slain_rule;
    money.held_by_wild_victor (a wild victor's claim holds the money its win took and pays it back; other losses lose
    it outright); "when i killed it with a sword it did respawn though, it should work both ways whether i kill it or
    my mon does".
  - Vanilla NBT path semantics as tests/nbt_sim.py models them, notably getOrCreate appending a list filter's pattern
    when nothing matches (the hit_mark finding rests on it) and `execute store` writing 0 when its command fails.

Not covered, and it needs a running server (EXP-042 and the owner's staging checks): that Cobblemon fires
battle_fainted and exposes c.pokemon.actor.is_wild, c.pokemon.pokemon.id and c.players there; that battle_victory's
player_losers carry player.party.pokemon[].current_hp after the battle; that a wild Pokemon's NBT has
Pokemon.PokemonOriginalTrainerType "NONE" and Pokemon.UUID as an int array, Species and Level under those names;
that `spawnpokemonat ~ ~ ~ cobblemon:<species> level=<n>` accepts a namespaced species; that entity_killed_player
fires before the tick's death charge and `on attacker` finds the killer; that each claimable item's translation key
really is item.<ns>.<path> (a plain BlockItem's is block.<ns>.<path>, unchecked here). From 3e2906e: that `on attacker`
finds a player or a player's Pokemon hurting a guardian and `on owner` finds a Cobblemon Pokemon's player; that a
guardian killed in one hit is ever noted (it is removed at the hit, before the next tick's recovery/watch); that
`cobbledollars give @s <n>` pays and accepts 0; the sword kill, the Pokemon kill and the held money in a real loss (the
commit says none has been run with a player).
"""
from __future__ import annotations

import copy
import json
import random
import re
import sys
import uuid
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tests"))

import nbt_sim as N  # noqa: E402
import test_blackout_pack as TB  # noqa: E402

NS = TB.NS
LEDGER = TB.LEDGER
PACK = TB.PACK
FNS = TB.FNS
CFG = TB.CFG
MOL = {"/".join(k.split("/")[3:5]): v for k, v in PACK.items() if k.endswith(".molang")}
VICTORY = MOL["battle_victory/cobblers_blackout.molang"]
FAINTED = MOL["battle_fainted/cobblers_recovery.molang"]
CAPTURED = MOL["pokemon_captured/cobblers_recovery.molang"]
NAMES = MOL["player_tick_pre/cobblers_names.molang"]
VICTOR_SEL = "@e[type=cobblemon:pokemon,tag=cobblers.victor,limit=1]"
M32 = 0xFFFFFFFF


def java_uuid_text(ints):
    """UUIDUtil.uuidFromIntArray then UUID.toString, independently of the pack."""
    a, b, c, d = (v & M32 for v in ints)
    return str(uuid.UUID(int=(a << 96) | (b << 64) | (c << 32) | d))


P1 = N.IntArray((123456789, -987654321, 42, -1))
P2 = N.IntArray((-5, 7, -2 ** 31, 2 ** 31 - 1))
P1_ID, P2_ID = java_uuid_text(P1), java_uuid_text(P2)
GUARD = (0x0A0B0C0D, -0x2F000001, 0x7FFF0000, -16)          # the guardian's Pokemon UUID ints
GUARD_ID = java_uuid_text(GUARD)
OTHER_ID = java_uuid_text((1, 2, 3, 4))


def strict_query(extra=None):
    """Answers for what only a server knows; anything else is a test that did not model a command."""
    table = {"time query gametime": 5000, "cobbledollars query @s": 1000}
    table.update(extra or {})

    def q(cmd):
        if cmd in table:
            return table[cmd]
        if cmd.startswith("clear @s ") or cmd.startswith("random value "):
            return 0
        raise AssertionError("unmodelled query: %s" % cmd)
    return q


def loaded(query=None, world=None, entity=None):
    s = N.NbtSim(query=query or strict_query(), world=world, entity=entity)
    for f in TB.load_functions():
        s.call(f)
    s.calls.clear()
    s.log.clear()
    return s


def ledger(s):
    return s.nbt[LEDGER]


def fn_calls(s, name):
    return [c for c in s.calls if c[0] == name]


# ------------------------------------------------------------------------------------------------ the models themselves

# Without it every test below could pass on a model that ignores what it is given: the path parser must refuse a filter
# after a list index (the f08117e bug), `set` must create what Minecraft creates, a `set from` with no source must
# change nothing, a filter must compare tag types, macro text must drop a string's quotes, and scoreboard %= must
# floor-mod a negative score.
def test_the_nbt_simulator_follows_minecrafts_storage_rules():
    for bad in ('scan[0]{pid:"x"}', "a{b:1}{c:2}", "a..b", "a[x]"):
        with pytest.raises((N.PathError, N.SnbtError)):
            N.parse_path(bad)
    assert N.parse_path('pcur{pid:"x",state:"open"}') == [("keyf", "pcur", {"pid": "x", "state": "open"})]
    assert N.parse_path('item_keys."cobblemon:poke_ball"') == [("key", "item_keys"), ("key", "cobblemon:poke_ball")]
    s = N.NbtSim(fns={"t": ["data modify storage a:b x.y set value 3",
                            "data modify storage a:b l set value [{id:1,v:1b}]",
                            "data modify storage a:b l[{id:2}].v set value 5",
                            "data modify storage a:b z set from storage a:b nothing",
                            "execute if data storage a:b l[{v:1}] run data modify storage a:b hit set value 1",
                            "execute if data storage a:b l[{v:1b}] run data modify storage a:b hit2 set value 1",
                            "data remove storage a:b l[0]",
                            'data modify storage a:b m set value {s:"text",n:7,u:[I;1,-2]}',
                            "function cobblers:u with storage a:b m",
                            "scoreboard players set #a x -17", "scoreboard players set #16 x 16",
                            "scoreboard players operation #a x %= #16 x"],
                      "u": ["$data modify storage a:b out set value '$(s)|$(n)|$(u)'"]})
    s.call("t")
    st = s.nbt["a:b"]
    assert st["x"] == {"y": 3} and "z" not in st and "hit" not in st and st["hit2"] == 1, st
    assert st["l"] == [{"id": 2, "v": 5}], st["l"]                   # the unmatched filter appended its pattern
    assert s.failed == ["data modify storage a:b z set from storage a:b nothing"]
    assert st["out"] == "text|7|[I;1,-2]", st["out"]
    assert s.get("#a", "x") == 15


# Without it the callback tests could pass on an interpreter that skips branches or loops: it must run for_each over
# every element, take a `? {}` branch only when true, stop at `return`, concatenate strings, and refuse what it does
# not know (an unmodelled field, an unknown function, a stray character).
def test_the_molang_interpreter_runs_what_it_is_given_and_refuses_what_it_does_not_know():
    m = N.Molang("t.n = 0; for_each(t.x, c.xs, { t.x.v > 1 ? { t.n = t.n + 1; }; });"
                 "t.n == 2 ? { q.run_command('two ' + c.name); }; math.mod(q.gt, 100) != 0 ? { return 0; };"
                 "q.run_command('after');")
    assert m.run({"xs": [{"v": 1}, {"v": 2}, {"v": 3}], "name": "Ash"}, {"gt": 7}) == ["two Ash"]
    assert m.run({"xs": [{"v": 5}], "name": "Ash"}, {"gt": 200}) == ["after"]
    with pytest.raises(N.MolangError):
        N.Molang("q.run_command(c.missing);").run({}, {})
    with pytest.raises(N.MolangError):
        N.Molang("q.frobnicate(1);").run({}, {})
    with pytest.raises(N.MolangError):
        N.Molang("t.a = 1 # 2;")


# ------------------------------------------------------------------------------------------------ paths and the pid

def _storage_paths():
    """(where, path) for every NBT path after `storage <ns>` in every function, a macro's $(key) given a value."""
    out = []
    for name, lines in FNS.items():
        for l in lines:
            if l.startswith("#"):
                continue
            text = TB.MACRO_REF.sub("1", l[1:] if l.startswith("$") else l)
            for m in re.finditer(r"\bstorage ([a-z0-9_.-]+:[a-z0-9_/.-]+) (\S+)", text):
                out.append((name, m.group(2)))
            for m in re.finditer(r'"storage":"[^"]+","nbt":"([^"]+)"', text):
                out.append((name, m.group(1)))
    return out


# Without it a storage path Minecraft cannot parse ships: the whole function fails to load, or (on a macro line) the
# call fails when it runs. f08117e found one in game (pid_find filtered scan[0]{pid:...}, so no claim ever matched).
def test_every_storage_path_the_pack_uses_parses_as_an_nbt_path():
    paths = _storage_paths()
    assert len(paths) > 150, len(paths)
    bad = []
    for where, p in paths:
        try:
            N.parse_path(p)
        except (N.PathError, N.SnbtError) as e:
            bad.append((where, p, str(e)))
    assert not bad, bad[:5]
    assert ("recovery/pid_find", 'pcur{pid:"1",state:"open"}') in paths


EDGE_UUIDS = [(0, 0, 0, 0), (-1, -1, -1, -1), (1, 15, 16, 17), (-2 ** 31, 2 ** 31 - 1, -2 ** 31, 2 ** 31 - 1),
              (-16, -17, 0x0000FFFF, -0x10000), GUARD]


def _pid_of(ints, s=None):
    s = s or loaded()
    s.query = lambda cmd: ints[int(re.fullmatch(r"data get entity @s Pokemon\.UUID\[(\d)\]", cmd).group(1))]
    s.call("recovery/pid")
    return ledger(s)["pid"]["s"]


# Without it a claim records a pid that pokemon.id never equals (a digit order, a sign or a hyphen off), and no
# faint, win or catch ever resolves it: the owner's playtest bug of 2026-09-27 back again.
@pytest.mark.parametrize("ints", EDGE_UUIDS, ids=lambda v: ",".join(str(x) for x in v))
def test_the_pid_is_javas_uuid_text_for_edge_int_arrays(ints):
    assert _pid_of(ints) == java_uuid_text(ints)


# Without it only the hand-picked arrays above are right: random ones, negative and positive, must match too.
def test_the_pid_is_javas_uuid_text_for_random_int_arrays():
    rnd = random.Random(20260927)
    s = loaded()
    for _ in range(300):
        ints = tuple(rnd.randint(-2 ** 31, 2 ** 31 - 1) for _ in range(4))
        assert _pid_of(ints, s) == java_uuid_text(ints), ints


# ------------------------------------------------------------------------------------------------ a claim, committed

ITEMS = [{"id": "cobblemon:ultra_ball", "count": 10}, {"id": "cobblemon:potion", "count": 2},
         {"id": "cobblemon:thunder_stone", "count": 1}]


def _commit(items=ITEMS, pokemon_uuid=GUARD, s=None):
    snap = {"Species": "cobblemon:ursaring", "Level": 60, "UUID": N.IntArray(pokemon_uuid)}
    victor = "0-0-0-0-7"

    def entity(sel, path):
        if sel == victor and path == "Pokemon":
            return copy.deepcopy(snap)
        if sel == "@s" and path == "UUID":
            return P1
        raise AssertionError("unmodelled entity read %s %s" % (sel, path))

    def query(cmd):
        m = re.fullmatch(r"data get entity @s Pokemon\.UUID\[(\d)\]", cmd)
        if m:
            return pokemon_uuid[int(m.group(1))]
        if cmd.startswith("data get entity %s Pos[" % victor):
            return 100
        return strict_query()(cmd)

    s = s or loaded(query=query, entity=entity)
    s.command("data modify storage %s pending set value {items:%s,plan:[%s]}" % (
        LEDGER, N.to_snbt(items), ",".join('{slot:"container.%d",n:-%d}' % (i, it["count"]) for i, it in enumerate(items))))
    s.command('function %s:recovery/commit {victor:"%s",name:"Ash",id:"%s"}' % (NS, victor, P1_ID))
    return s


# Without it a claim is written without the guardian's pid (so nothing ever resolves it), or with another Pokemon's.
def test_a_committed_claim_records_its_guardians_pokemon_uuid_as_text():
    s = _commit()
    claims = ledger(s)["claims"]
    assert len(claims) == 1, claims
    c = claims[0]
    assert c["pid"] == GUARD_ID and c["state"] == "open" and c["owner_id"] == P1_ID, c
    assert [{k: i[k] for k in ("id", "count")} for i in c["items"]] == ITEMS
    assert "plan" not in c


# Without it the message names the category ("10 Poke Ball(s)") and not the stack taken (the owner, 2026-09-27: it
# sent them to count the wrong stack), or drops an item from the message.
def test_the_claim_message_names_each_item_taken_with_its_count():
    s = _commit()
    summary = [json.loads(x) for x in ledger(s)["summary"]]
    want = [[{"text": "%d " % i["count"]}, {"translate": "item.%s" % i["id"].replace(":", ".")}] for i in ITEMS]
    assert summary == want, summary
    told = [l for l in s.log if l.startswith("tellraw @s ") and '"nbt":"summary[]"' in l]
    assert len(told) == 1 and '"storage":"%s"' % LEDGER in told[0], s.log[-3:]


# Without it an item with no translation key (one added to a claim tag but not to item_keys) vanishes from the
# message; it must still be named, by its id.
def test_an_item_without_a_translation_key_is_named_by_its_id():
    s = _commit(items=[{"id": "cobblemon:not_a_real_item", "count": 3}])
    assert [json.loads(x) for x in ledger(s)["summary"]] == [[{"text": "3 "}, {"translate": "cobblemon:not_a_real_item"}]]


# Without it a claimable item is missing from item_keys (the message shows its raw id) or keyed wrongly; the keys are
# the claim lists of data/blackout.json and vanilla's item.<namespace>.<path>.
def test_item_keys_cover_every_claimable_item_with_its_item_translation_key():
    s = loaded()
    keys = ledger(s)["item_keys"]
    claimable = set(CFG["claims"]["balls"]) | set(CFG["claims"]["medicine"]) | set(CFG["claims"]["consumables"])
    assert set(keys) == claimable, sorted(set(keys) ^ claimable)
    wrong = {i: k for i, k in keys.items() if k != "item.%s.%s" % tuple(i.split(":", 1))}
    assert not wrong, wrong


# ------------------------------------------------------------------------------------------------ resolution by pid

def _claim(cid, g, pid, owner, owner_id, state="open", items=None, name="Ash"):
    return {"id": cid, "g": g, "pid": pid, "state": state, "owner": owner, "owner_id": owner_id, "owner_name": name,
            "seen": 0, "x": 10, "y": 64, "z": 10,
            "items": items or [{"id": "cobblemon:ultra_ball", "count": 3}],
            "snapshot": {"Species": "cobblemon:ursaring", "Level": 60}}


def _ledger_sim():
    s = loaded(entity=lambda sel, path: P1 if (sel, path) == ("@s", "UUID") else None)
    ledger(s)["claims"] = [
        _claim(4, 9, GUARD_ID, P1, P1_ID, state="resolved"),           # an older, settled claim with the same pid
        _claim(1, 1, GUARD_ID, P1, P1_ID, items=[{"id": "cobblemon:ultra_ball", "count": 3}]),
        _claim(2, 1, GUARD_ID, P2, P2_ID, items=[{"id": "cobblemon:potion", "count": 2}], name="Misty"),
        _claim(3, 2, OTHER_ID, P1, P1_ID, items=[{"id": "cobblemon:great_ball", "count": 5}]),
    ]
    return s


def _states(s):
    return {c["id"]: c["state"] for c in ledger(s)["claims"]}


def _drops(s):
    out = []
    for l in s.log:
        if l.startswith("summon item "):
            d = N.parse_snbt(l.split(" ", 5)[5])
            out.append((d["Item"]["id"], d["Item"]["count"], tuple(d["Owner"])))
    return out


# Without it beating or catching a guardian resolves nothing (the owner's playtest, 2026-09-27), resolves only one of
# the claims it guards, resolves another guardian's claims, or takes its guardian number from a settled claim that
# happens to share the pid. The claims of the guardian's number go to "deliver", the online owner's are dropped at
# their feet as theirs alone, and the other owner's wait for their login.
def test_resolve_pid_resolves_every_open_claim_of_that_guardian_and_no_other():
    s = _ledger_sim()
    s.command('function %s:recovery/resolve_pid {pid:"%s",resolver:"%s"}' % (NS, GUARD_ID, P2_ID))
    assert _states(s) == {4: "resolved", 1: "resolved", 2: "deliver", 3: "open"}, _states(s)
    assert _drops(s) == [("cobblemon:ultra_ball", 3, tuple(P1))], _drops(s)
    assert ledger(s)["claims"][2]["resolver"] == P2_ID


# Without it the guardian is released before its claims resolve (a failure part-way loses every claim it held,
# DEATH_AND_WIPE.md), or a guardian still standing for settled claims (a rebuilt one) keeps its tags and persistence.
def test_resolve_pid_releases_the_guardians_number_after_resolving():
    s = _ledger_sim()
    s.command('function %s:recovery/resolve_pid {pid:"%s",resolver:"%s"}' % (NS, GUARD_ID, P1_ID))
    names = [c[0] for c in s.calls]
    assert names.index("recovery/release") > max(i for i, n in enumerate(names) if n == "recovery/resolve_one")
    assert len(fn_calls(s, "recovery/release")) == 1 and ledger(s)["r"]["g"] == 1
    rel = [l for l in s.log if "cobblers.g1]" in l]
    for tag in ("cobblers.guardian", "cobblers.rebuilt", "cobblers.g1"):
        assert "tag @e[type=cobblemon:pokemon,tag=cobblers.g1] remove %s" % tag in rel, (tag, rel)
    assert "data merge entity @s {PersistenceRequired:0b}" in s.log
    assert not [l for l in s.log if "cobblers.g2" in l or "cobblers.g9" in l]
    # every line of the release acts on the entities carrying that guardian number, and only on them
    body = [l for l in FNS["recovery/release"] if not l.startswith("#")]
    assert len(body) == 5 and all("@e[type=cobblemon:pokemon,tag=cobblers.g$(g)]" in l for l in body), body
    assert "$scoreboard players reset @e[type=cobblemon:pokemon,tag=cobblers.g$(g)] bo.g" in body


# Without it an ordinary wild Pokemon's faint or capture (every one runs resolve_pid) changes the ledger or releases a
# guardian, and a second report for the same guardian (battle_fainted, then battle_victory) delivers twice.
def test_resolve_pid_with_no_open_claim_changes_nothing_and_a_second_report_delivers_nothing():
    s = _ledger_sim()
    before = copy.deepcopy(ledger(s)["claims"])
    r = s.call("recovery/resolve_pid", {"pid": OTHER_ID.replace("0", "f"), "resolver": P1_ID})
    assert r is N.FAIL and ledger(s)["claims"] == before
    assert not fn_calls(s, "recovery/release") and not fn_calls(s, "recovery/deliver")
    s.command('function %s:recovery/resolve_pid {pid:"%s",resolver:"%s"}' % (NS, GUARD_ID, P1_ID))
    first = _drops(s)
    after = copy.deepcopy(ledger(s)["claims"])
    s.log.clear()
    assert s.call("recovery/resolve_pid", {"pid": GUARD_ID, "resolver": P1_ID}) is N.FAIL
    assert _drops(s) == [] and ledger(s)["claims"] == after and first


# ------------------------------------------------------------------------------------------------ callbacks, run

def _party(*hps):
    return {"pokemon": [{"current_hp": float(h)} for h in hps]}


def _player(pid, name, *hps):
    return {"uuid": pid, "username": name, "party": _party(*hps)}


def _victory_ctx(winners, losers, player_losers, player_winners):
    return {"scriptable_winners": winners, "scriptable_losers": losers,
            "player_losers": [{"player": p} for p in player_losers],
            "player_winners": [{"player": p} for p in player_winners]}


WILD_W = {"is_pokemon": True, "is_npc": False, "uuid": "e0e0e0e0-0000-0000-0000-000000000001"}
NPC_W = {"is_pokemon": False, "is_npc": True, "uuid": "e0e0e0e0-0000-0000-0000-000000000002"}


def _loss_calls(cmds):
    """[(player uuid, function, inline args)] of every blackout command a callback issued."""
    out = []
    for c in cmds:
        m = re.fullmatch(r"execute as (\S+) run function %s:(blackout/battle_loss_[a-z]+) (\{.*\})" % NS, c)
        assert m, c
        out.append((m.group(1), m.group(2), TB.inline_args(m.group(3))))
    return out


# Without it running away counts as a blackout again (the owner lost $179 and a claim for fleeing, 2026-09-27), or a
# player whose whole party fainted is not blacked out; with two losers each is judged on their own party.
@pytest.mark.parametrize("hps,blackout", [((0, 0, 0), True), ((0,), True), ((0, 12, 0), False), ((35,), False),
                                          ((0, 0.5), False)])
def test_a_battle_loss_is_a_blackout_only_when_the_whole_party_has_fainted(hps, blackout):
    ctx = _victory_ctx([WILD_W], [], [_player(P1_ID, "Ash", *hps)], [])
    calls = _loss_calls(N.Molang(VICTORY).run(ctx, {}))
    want = [(P1_ID, "blackout/battle_loss_wild", {"victor": WILD_W["uuid"], "name": "Ash", "id": P1_ID})]
    assert calls == (want if blackout else []), calls
    ctx = _victory_ctx([NPC_W], [], [_player(P1_ID, "Ash", 0, 0), _player(P2_ID, "Misty", *hps)], [])
    calls = _loss_calls(N.Molang(VICTORY).run(ctx, {}))
    assert [(u, f) for u, f, _a in calls] == [(P1_ID, "blackout/battle_loss_npc")] + (
        [(P2_ID, "blackout/battle_loss_npc")] if blackout else []), calls


# Without it the command a wiped player's loss sends does not run the blackout in the pack (a name or argument
# mismatch between the MoLang string and the function), so the loss charges nothing.
def test_a_wiped_players_loss_command_runs_the_wild_blackout_in_the_pack():
    ctx = _victory_ctx([WILD_W], [], [_player(P1_ID, "Ash", 0)], [])
    cmds = N.Molang(VICTORY).run(ctx, {})
    s = loaded(world=lambda kind, toks: False)
    for c in cmds:
        s.command(c)
    assert [c[0] for c in s.calls][:2] == ["blackout/battle_loss_wild", "blackout/dedupe"], s.calls[:3]
    assert fn_calls(s, "blackout/charge_calc") and "tag @s add cobblers.bo_pending" in s.log
    assert not s.missing


# Without it beating a guardian in a battle whose loser list does carry it resolves nothing, resolves by the entity
# (gone by now), or credits the wrong player; each winning player is offered it (the first resolves, the rest find no
# open claim), and a losing trainer's Pokemon (not is_pokemon) resolves nothing.
def test_a_beaten_wild_pokemon_is_resolved_by_its_pokemon_uuid_for_each_winner():
    loser = {"is_pokemon": True, "uuid": "entity-uuid-not-the-pid", "pokemon": {"id": GUARD_ID}}
    ctx = _victory_ctx([], [loser, {"is_pokemon": False, "uuid": "npc"}], [],
                       [_player(P1_ID, "Ash"), _player(P2_ID, "Misty")])
    cmds = N.Molang(VICTORY).run(ctx, {})
    assert cmds == ['function %s:recovery/resolve_pid {pid:"%s",resolver:"%s"}' % (NS, GUARD_ID, p)
                    for p in (P1_ID, P2_ID)], cmds
    s = _ledger_sim()
    for c in cmds:
        s.command(c)
    assert _states(s) == {4: "resolved", 1: "resolved", 2: "deliver", 3: "open"}
    assert ledger(s)["claims"][2]["resolver"] == P1_ID, "the first winner resolves; the second finds nothing open"


# Without it a guardian beaten in battle resolves nothing (battle_fainted is where the entity is still present, and
# battle_victory may not list it), a player's own fainting Pokemon runs a resolution, or a multi-player battle
# resolves once per player.
@pytest.mark.parametrize("wild,players,want", [(True, [P1_ID, P2_ID], [P1_ID]), (True, [P2_ID], [P2_ID]),
                                               (False, [P1_ID], []), (True, [], [])])
def test_a_wild_pokemon_fainting_resolves_its_claims_once_for_the_first_player(wild, players, want):
    ctx = {"pokemon": {"actor": {"is_wild": wild}, "pokemon": {"id": GUARD_ID}},
           "players": [{"player": {"uuid": p}} for p in players]}
    cmds = N.Molang(FAINTED).run(ctx, {})
    assert cmds == ['function %s:recovery/resolve_pid {pid:"%s",resolver:"%s"}' % (NS, GUARD_ID, p) for p in want]
    s = _ledger_sim()
    for c in cmds:
        s.command(c)
    assert _states(s)[1] == ("resolved" if want else "open")


# Without it catching a guardian keeps its claims open (the owner's playtest, 2026-09-27: the entity is gone when
# pokemon_captured runs), or the catch is credited to someone else.
def test_catching_a_guardian_resolves_its_claims_by_its_pokemon_uuid():
    cmds = N.Molang(CAPTURED).run({}, {"pokemon": {"id": GUARD_ID}, "player": {"uuid": P2_ID}})
    assert cmds == ['function %s:recovery/resolve_pid {pid:"%s",resolver:"%s"}' % (NS, GUARD_ID, P2_ID)]
    s = _ledger_sim()
    s.command(cmds[0])
    assert _states(s) == {4: "resolved", 1: "resolved", 2: "deliver", 3: "open"}
    assert all(c["resolver"] == P2_ID for c in ledger(s)["claims"] if c["id"] in (1, 2))


# ------------------------------------------------------------------------------------------------ killed outside battle

def _remember(s, ints, name, gt=100):
    pid = java_uuid_text(ints)
    cmds = N.Molang(NAMES).run({}, {"player": {"uuid": pid, "username": name, "world": {"game_time": float(gt)}}})
    s.entity = lambda sel, path: ints if (sel, path) == ("@s", "UUID") else None
    for c in cmds:
        s.command(c)
    return cmds


# Without it a player's name and UUID text are never kept (every out-of-battle death stays environmental), are kept
# on every tick (the callback's command every tick), or pile up a record per login or per rename.
def test_the_name_record_is_kept_once_per_player_and_replaced_not_duplicated():
    s = loaded(world=lambda kind, toks: False)
    assert _remember(s, P1, "Ash", gt=101) == []
    assert _remember(s, P1, "Ash") == ["execute as %s unless entity @s[tag=cobblers.named] run function "
                                       '%s:recovery/remember {name:"Ash",id:"%s"}' % (P1_ID, NS, P1_ID)]
    _remember(s, P2, "Misty")
    _remember(s, P1, "Ash2")
    names = ledger(s)["names"]                     # in the claim ledger since 3e2906e (it settles claims too)
    assert sorted((tuple(r["UUID"]), r["name"], r["id"]) for r in names) == sorted(
        [(tuple(P1), "Ash2", P1_ID), (tuple(P2), "Misty", P2_ID)]), names
    assert s.log.count("tag @s add cobblers.named") == 3
    assert "tag @s remove cobblers.named" in FNS["blackout/login"], "a login must let the record refresh"


# Without it the kill advancement never fires (wrong trigger), fires for any killer (a zombie's kill would take items),
# or rewards a function that does not exist.
def test_the_killed_by_pokemon_advancement_fires_for_a_pokemon_killer_only():
    adv = json.loads(PACK["data/%s/advancement/blackout/killed_by_pokemon.json" % NS])
    (crit,) = adv["criteria"].values()
    assert crit["trigger"] == "minecraft:entity_killed_player"
    assert crit["conditions"]["entity"] == [{"condition": "minecraft:entity_properties", "entity": "this",
                                             "predicate": {"type": "cobblemon:pokemon"}}]
    assert adv["rewards"] == {"function": "%s:blackout/killed" % NS}
    assert "blackout/killed" in FNS


def _killed(attacker, wild=True, remembered=((P1, "Ash"), (P2, "Misty")), me=P1, then_death=False):
    """Run blackout/killed as `me`; attacker: whether `on attacker` finds anyone. (sim, calls of battle_loss_wild)."""
    state = {}

    def world(kind, toks):
        if kind == "on":
            assert toks == ["attacker"], toks
            return attacker
        if kind == "entity" and toks[0].startswith("@s[type=cobblemon:pokemon,nbt="):
            assert toks[0] == '@s[type=cobblemon:pokemon,nbt={Pokemon:{PokemonOriginalTrainerType:"NONE"}}]', toks
            return wild
        if kind == "entity" and toks[0] in ("@e[type=cobblemon:pokemon,tag=cobblers.victor]", VICTOR_SEL):
            return state.get("victor", False)
        if kind == "entity" and toks[0] == "@s[tag=cobblers.named]":
            return False                                  # the name callback, before the kill
        raise AssertionError("unmodelled test %s %s" % (kind, toks))

    s = loaded(world=world)
    for ints, name in remembered:
        _remember(s, ints, name)
    s.entity = lambda sel, path: me if (sel, path) == ("@s", "UUID") else None
    s.log.clear()
    s.calls.clear()
    orig = s.command

    def command(cmd):
        if cmd == "tag @s add cobblers.victor":
            state["victor"] = True
        elif cmd == "tag @e[type=cobblemon:pokemon,tag=cobblers.victor] remove cobblers.victor":
            state["victor"] = False
        return orig(cmd)
    s.command = command
    s.call("blackout/killed")
    if then_death:
        s.call("blackout/death")
    return s, fn_calls(s, "blackout/battle_loss_wild")


# Without it a wild Pokemon killing the player outside battle takes nothing (the owner, 2026-09-27: "the same loss of
# items should happen"), names the wrong player (another remembered one), or loses the victor on the way to the claim.
def test_a_wild_pokemon_killing_the_player_runs_the_wild_battle_loss_as_that_player():
    s, loss = _killed(attacker=True)
    assert s.log[0] == "advancement revoke @s only %s:blackout/killed_by_pokemon" % NS
    assert len(loss) == 1, loss
    make = fn_calls(s, "recovery/make")
    assert make and TB.inline_args(make[0][1]) == {"victor": VICTOR_SEL, "name": "Ash", "id": P1_ID}, make
    s, _ = _killed(attacker=True, me=P2)
    assert TB.inline_args(fn_calls(s, "recovery/make")[0][1])["name"] == "Misty"
    assert s.log[-1] == "tag @e[type=cobblemon:pokemon,tag=cobblers.victor] remove cobblers.victor"


# Without it an owned Pokemon's kill (a player's own, or another player's) takes the victim's items, a death with no
# attacker is charged as a battle loss, or a player with no name record yet runs a claim that cannot name them.
@pytest.mark.parametrize("attacker,wild,remembered", [(True, False, ((P1, "Ash"),)), (False, True, ((P1, "Ash"),)),
                                                      (True, True, ((P2, "Misty"),))],
                         ids=["owned killer", "no attacker", "no name record"])
def test_no_claim_is_made_for_an_owned_killer_no_attacker_or_an_unknown_name(attacker, wild, remembered):
    s, loss = _killed(attacker=attacker, wild=wild, remembered=remembered)
    assert loss == [] and not fn_calls(s, "recovery/make") and not fn_calls(s, "blackout/charge"), s.calls


# Without it the death that follows the kill is charged a second time (one incident, one charge; the dedupe the battle
# path already uses), assuming, as the tool does, that the advancement runs before the tick sees the death.
def test_a_kill_and_the_death_it_causes_are_charged_once():
    s, loss = _killed(attacker=True, then_death=True)
    assert len(loss) == 1
    assert len(fn_calls(s, "blackout/charge_calc")) == 1, [c[0] for c in s.calls]
    s, loss = _killed(attacker=False, then_death=True)
    assert loss == [] and len(fn_calls(s, "blackout/charge_calc")) == 1


# ------------------------------------------------------------------------------------------------ rebuild

# Without it a rebuilt guardian shows as a Magikarp over its real data (the owner, 2026-09-27: the client keeps the
# model it was spawned with), or as another claim's species or level.
def test_a_rebuilt_guardian_is_spawned_as_its_own_species_and_level():
    s = loaded(world=lambda kind, toks: False)
    ledger(s)["claims"] = [
        dict(_claim(1, 1, GUARD_ID, P1, P1_ID), snapshot={"Species": "cobblemon:ursaring", "Level": 60}),
        dict(_claim(2, 2, OTHER_ID, P1, P1_ID), x=-40, y=70, z=900,
             snapshot={"Species": "cobblemon:gyarados", "Level": 41})]
    s.command("function %s:recovery/rebuild {g:2,x:-40,y:70,z:900,id:2}" % NS)
    spawns = [l for l in s.log if "spawnpokemonat" in l]
    assert spawns == ["spawnpokemonat ~ ~ ~ cobblemon:gyarados level=41"], s.log
    names = [c[0] for c in s.calls]
    assert names.index("recovery/rebuild_spawn") < names.index("recovery/rebuild_as")
    assert TB.inline_args(fn_calls(s, "recovery/rebuild_as")[0][1]) == {"g": "2", "id": "2"}
    assert not [(n, l) for n, lines in FNS.items() for l in lines if "magikarp" in l.lower() and not l.startswith("#")]


# ------------------------------------------------------------------------------------------------ money held (3e2906e)

WILD_UUID = WILD_W["uuid"]
MONEY = CFG["money"]


def _ceil_pct(n, pct):
    return -(-n * pct // 100)


def _wild_loss(slots, balance, claims=None):
    """P1 loses a battle to the wild WILD_UUID (GUARD's Pokemon UUID), holding {slot index: (id, count)}.
    Returns the simulator after blackout/battle_loss_wild."""
    tags = {c: set(CFG["claims"][c]) for c in ("balls", "medicine", "consumables")}

    def category(item):
        return next(c for c, ids in tags.items() if item in ids)

    def query(cmd):
        m = re.fullmatch(r"clear @s #%s:claim/(\w+) 0" % NS, cmd)
        if m:
            return sum(n for i, n in slots.values() if category(i) == m.group(1))
        m = re.fullmatch(r"data get entity @s Inventory\[\{Slot:(-?\d+)b\}\]\.count", cmd)
        if m:
            return slots[int(m.group(1))][1]
        m = re.fullmatch(r"data get entity @s Pokemon\.UUID\[(\d)\]", cmd)
        if m:
            return GUARD[int(m.group(1))]
        if cmd.startswith("data get entity %s Pos[" % WILD_UUID):
            return 100
        return strict_query({"cobbledollars query @s": balance})(cmd)

    def world(kind, toks):
        if kind == "entity" and toks == [WILD_UUID]:
            return True
        if kind == "items":
            slot = toks[2]
            n = -106 if slot == "weapon.offhand" else int(slot.split(".")[1])
            return n in slots and "#%s:claim/%s" % (NS, category(slots[n][0])) == toks[3]
        raise AssertionError("unmodelled test %s %s" % (kind, toks))

    def entity(sel, path):
        if (sel, path) == ("@s", "UUID"):
            return P1
        if sel == WILD_UUID and path == "Pokemon":
            return {"Species": "cobblemon:ursaring", "Level": 60, "UUID": N.IntArray(GUARD)}
        m = re.fullmatch(r"Inventory\[\{Slot:(-?\d+)b\}\]", path)
        if sel == "@s" and m:
            i, n = slots[int(m.group(1))]
            return {"Slot": N.Byte(int(m.group(1))), "id": i, "count": n}
        raise AssertionError("unmodelled entity read %s %s" % (sel, path))

    s = loaded(query=query, world=world, entity=entity)
    if claims:
        ledger(s)["claims"] = copy.deepcopy(claims)
    s.command('execute as %s run function %s:blackout/battle_loss_wild {victor:"%s",name:"Ash",id:"%s"}'
              % (P1_ID, NS, WILD_UUID, P1_ID))
    return s


def _gives(s):
    return [l for l in s.log if l.startswith("cobbledollars give ")]


# Without it the money a wild victor's win takes is lost outright (the owner, 2026-09-27: "i should want to go back and
# kill that thing"; data money.held_by_wild_victor), is held at a different amount from the charge, or is paid back
# twice (a second delivery, at the next login) or to the wrong player. The charge is ceil(balance * percent / 100).
def test_a_wild_victors_claim_holds_the_money_its_win_took_and_pays_it_back_once():
    assert MONEY["held_by_wild_victor"] is True
    s = _wild_loss({0: ("cobblemon:ultra_ball", 20)}, balance=1000)
    (claim,) = ledger(s)["claims"]
    charge = _ceil_pct(1000, MONEY["percent"])
    assert claim["money"] == charge and s.get("@s", "bo.lost") == charge, (claim.get("money"), charge)
    cat = CFG["claims"]["categories"]["balls"]
    took = min(_ceil_pct(20, cat["percent"]), cat["max"])
    assert [(i["id"], i["count"]) for i in claim["items"]] == [("cobblemon:ultra_ball", took)]
    assert claim["pid"] == GUARD_ID
    s.log.clear()
    s.call("recovery/resolve_pid", {"pid": GUARD_ID, "resolver": P2_ID})
    assert _gives(s) == ["cobbledollars give @s %d" % charge], s.log
    assert _drops(s) == [("cobblemon:ultra_ball", took, tuple(P1))]
    s.log.clear()
    s.call("recovery/deliver")                              # the next login
    assert _gives(s) == [] and _drops(s) == []


# Without it a claim that holds no money pays some on delivery, or an environmental death, a trainer loss or any other
# loss holds money in a claim (data money.held_by_wild_victor_why: they "lose it outright"), or the data's switch off
# still holds it.
def test_only_a_wild_battle_loss_holds_money_and_a_claim_without_money_pays_none():
    s = _ledger_sim()
    s.call("recovery/resolve_pid", {"pid": GUARD_ID, "resolver": P1_ID})
    assert _drops(s) and _gives(s) == []
    callers = sorted({w for w, _ns, f, _r in TB._references() if f == "recovery/hold_money"})
    assert callers == ["blackout/battle_loss_wild"], callers
    cfg = copy.deepcopy(CFG)
    cfg["money"]["held_by_wild_victor"] = False
    off = TB.build(cfg)
    fns = TB.functions(off)
    assert not [w for w, _ns, f, _r in TB._references(off) if f == "recovery/hold_money"]
    assert not [l for l in fns["blackout/arrive"] if CFG["messages"]["claim_money"] in l]


# Without it the loss's charge lands in another player's claim: when recovery/make set bo.clm 2 before it knew a claim
# would be written, a loss with nothing claimable ran hold_money, which wrote claims[-1], the last claim in the ledger,
# someone else's (found by this suite at 3e2906e; fixed in 4a37312).
def test_a_wild_loss_with_nothing_claimable_holds_no_money_in_another_players_claim():
    other = _claim(1, 1, OTHER_ID, P2, P2_ID, name="Misty")
    s = _wild_loss({}, balance=1000, claims=[other])
    assert ledger(s)["claims"] == [other], ledger(s)["claims"]


# Without it the held money goes by position ("the last claim") rather than to the claim this loss wrote (4a37312: "the
# money goes to that claim by its own id"), or lands in a claim that is no longer open.
def test_held_money_goes_to_the_claim_this_loss_wrote_by_its_id_and_only_if_open():
    s = loaded()
    ours, later = _claim(7, 3, GUARD_ID, P1, P1_ID), _claim(8, 4, OTHER_ID, P2, P2_ID, name="Misty")
    ledger(s)["claims"] = copy.deepcopy([ours, later])
    ledger(s)["pending"] = {"id": 7}
    s.set("@s", "bo.lost", 150)
    s.call("recovery/hold_money")
    assert [c.get("money") for c in ledger(s)["claims"]] == [150, None]
    s = loaded()
    ledger(s)["claims"] = copy.deepcopy([dict(ours, state="deliver"), later])
    ledger(s)["pending"] = {"id": 7}
    s.set("@s", "bo.lost", 150)
    s.call("recovery/hold_money")
    assert [c.get("money") for c in ledger(s)["claims"]] == [None, None]


# Without it a player who lost with nothing claimable is told the victor "has your money too" though no claim holds it:
# the money is gone, and the message sends them after it (found by this suite at 3e2906e; fixed in 4a37312).
def test_the_arrival_does_not_say_the_victor_holds_money_when_no_claim_was_made():
    s = _wild_loss({}, balance=1000)
    assert ledger(s)["claims"] == []
    s.log.clear()
    s.world = lambda kind, toks: False
    s.call("blackout/arrive")
    told = [l for l in s.log if l.startswith("tellraw @s")]
    assert told, s.log
    assert not [l for l in told if CFG["messages"]["claim_money"] in l], told


# ------------------------------------------------------------------------------------------------ guardian slain (3e2906e)

class Hurt:
    """The guardian's last attacker for recovery/watch: None, "player", "owned" (a player's Pokemon) or "wild".
    Each execute starts with the guardian as executor; `on attacker` and `on owner` move it as Minecraft does."""

    def __init__(self, sim, attacker, slayer=P2):
        self.attacker, self.ctx, self.tagged = attacker, "guardian", False
        orig_execute, orig_command = sim.execute, sim.command

        def execute(t):
            self.ctx = "guardian"
            return orig_execute(t)

        def command(cmd):
            if cmd == "tag @s add cobblers.slayer":
                assert self.ctx == "player", self.ctx
                self.tagged = True
            elif cmd == "tag @a remove cobblers.slayer":
                self.tagged = False
            return orig_command(cmd)
        sim.execute, sim.command = execute, command
        sim.world = self.world
        sim.entity = lambda sel, path: slayer if (sel, path) == ("@s", "UUID") else None

    def world(self, kind, toks):
        if kind == "on" and toks == ["attacker"]:
            if self.ctx != "guardian" or self.attacker is None:
                return False
            self.ctx = {"player": "player", "owned": "pokemon_owned", "wild": "pokemon_wild"}[self.attacker]
            return True
        if kind == "on" and toks == ["owner"]:
            if self.ctx != "pokemon_owned":
                return False
            self.ctx = "player"
            return True
        if kind == "entity" and toks == ["@s[type=player]"]:
            return self.ctx == "player"
        if kind == "entity" and toks == ["@s[type=cobblemon:pokemon]"]:
            return self.ctx.startswith("pokemon")
        if kind == "entity" and toks == ["@a[tag=cobblers.slayer]"]:
            return self.tagged
        raise AssertionError("unmodelled test %s %s" % (kind, toks))


def _watch_sim(attacker, t=5000, remembered=((P1, "Ash"), (P2, "Misty"))):
    s = loaded(query=strict_query({"time query gametime": t}), world=lambda kind, toks: False)
    for ints, name in remembered:
        _remember(s, ints, name)
    ledger(s)["claims"] = [
        _claim(1, 1, GUARD_ID, P1, P1_ID), _claim(2, 1, GUARD_ID, P1, P1_ID),
        _claim(5, 1, GUARD_ID, P1, P1_ID, state="deliver"), _claim(3, 2, OTHER_ID, P1, P1_ID)]
    Hurt(s, attacker)
    s.log.clear()
    s.set("@s", "bo.g", 1)                             # the guardian's number, as recovery/watch reads it
    return s


# Without it a guardian hurt by a player, or by a player's Pokemon, keeps no note of who (so a kill outside battle is
# rebuilt: the owner, 2026-09-27, "when i killed it with a sword it did respawn"), the note goes on another guardian's
# claims or a settled one, or a wild attacker, no attacker, or a player with no name record is noted.
@pytest.mark.parametrize("attacker,noted", [("player", True), ("owned", True), ("wild", False), (None, False)])
def test_watch_notes_the_player_hurting_a_guardian_on_its_open_claims_only(attacker, noted):
    s = _watch_sim(attacker)
    before = copy.deepcopy(ledger(s)["claims"])
    s.call("recovery/watch")
    hits = {c["id"]: c.get("hit") for c in ledger(s)["claims"]}
    want = {"who": P2_ID, "t": 5000} if noted else None
    assert hits == {1: want, 2: want, 5: None, 3: None}, hits
    if not noted:
        assert ledger(s)["claims"] == before
    s = _watch_sim("player", remembered=((P1, "Ash"),))
    s.call("recovery/watch")
    assert not [c for c in ledger(s)["claims"] if "hit" in c]
    assert "execute as @e[type=cobblemon:pokemon,tag=cobblers.guardian] run function %s:recovery/watch" % NS \
        in FNS["blackout/tick"], "every tick, every guardian"


# Without it a guardian still tagged after its claims settled (a rebuilt copy that was in an unloaded chunk when
# release ran, then came back) writes a new, malformed "open" claim when a player hits it: a filtered
# `claims[{g:..,state:"open"}].hit set` appends its filter as a new element when nothing matches (vanilla getOrCreate),
# and maintenance then calls recovery/check on a claim with no id or site (found by this suite at 3e2906e; fixed in
# 4a37312).
def test_hurting_a_guardian_with_no_open_claim_adds_nothing_to_the_ledger():
    s = _watch_sim("player")
    for c in ledger(s)["claims"]:
        if c["g"] == 1:
            c["state"] = "resolved"
    before = copy.deepcopy(ledger(s)["claims"])
    s.call("recovery/watch")
    assert ledger(s)["claims"] == before, ledger(s)["claims"][len(before):]


# The rule, data/blackout.json claims.slain_rule (4a37312): a guardian found gone from its loaded site counts as killed
# by the last player (or player's Pokemon) who hurt it if that blow was noted after maintenance last saw it alive
# (claim alive_t); vanilla forgets an attacker 100 ticks after the last blow, so an old fight never counts.
SLAIN_RULE = CFG["claims"]["slain_rule"]
ALIVE = 19000


def _vanish_sim(hit_t, alive_t=ALIVE, now=20000):
    s = loaded(query=strict_query({"time query gametime": now}),
               entity=lambda sel, path: P1 if (sel, path) == ("@s", "UUID") else None,
               world=lambda kind, toks: False)
    c1, c2 = _claim(1, 1, GUARD_ID, P1, P1_ID), _claim(2, 1, GUARD_ID, P2, P2_ID, name="Misty")
    for c in (c1, c2):
        if hit_t is not None:
            c["hit"] = {"who": P2_ID, "t": hit_t}
        if alive_t is not None:
            c["alive_t"] = alive_t
    ledger(s)["claims"] = [c1, c2]
    return s


def _settled(s):
    return {c["id"]: c["state"] for c in ledger(s)["claims"]} == {1: "resolved", 2: "deliver"} \
        and all(c["resolver"] == P2_ID for c in ledger(s)["claims"])


def _spawns(s):
    return [l for l in s.log if "spawnpokemonat" in l]


# Without it a guardian killed by a player outside battle is rebuilt (the owner's complaint), or one gone for another
# reason after an old fight (lava, a fall, another wild Pokemon) is settled for whoever once hurt it. A note after the
# last alive sighting settles every open claim of that guardian for the player who hurt it last; a note before it, or
# none, rebuilds. A note at the sighting's own tick counts: blackout/tick runs the watch before maintenance, so a
# killing blow landing after the sighting leaves its last note at that tick. A claim maintenance has never seen alive
# (killed before the first pass) has nothing to be older than.
@pytest.mark.parametrize("hit_t,alive_t,settle", [(ALIVE + 1, ALIVE, True), (ALIVE, ALIVE, True),
                                                  (ALIVE - 1, ALIVE, False), (None, ALIVE, False),
                                                  (ALIVE - 5000, None, True), (None, None, False)],
                         ids=["after", "same tick", "before", "no note", "never seen alive", "neither"])
def test_a_vanished_guardian_is_settled_for_a_blow_noted_since_it_was_last_seen_alive(hit_t, alive_t, settle):
    assert "after maintenance last saw the guardian alive" in SLAIN_RULE and "alive_t" in SLAIN_RULE
    tick = FNS["blackout/tick"]
    assert TB._index(tick, lambda l: "recovery/watch" in l, "watch") < TB._index(tick, lambda l: "recovery/maintain" in l,
                                                                                  "maintain")
    s = _vanish_sim(hit_t, alive_t)
    s.command("function %s:recovery/vanished {g:1,x:10,y:64,z:10,id:1}" % NS)
    if settle:
        assert _settled(s) and _spawns(s) == [], (ledger(s)["claims"], s.log)
    else:
        assert {c["id"]: c["state"] for c in ledger(s)["claims"]} == {1: "open", 2: "open"}
        assert _spawns(s) == ["spawnpokemonat ~ ~ ~ cobblemon:ursaring level=60"], s.log


def _maintain(s, passes):
    """recovery/maintain at each (gametime, site loaded, guardian present)."""
    for gt, is_loaded, present in passes:
        def world(kind, toks, L=is_loaded, P=present):
            if kind == "loaded":
                return L
            if kind == "entity" and toks[0].startswith("@e[type=cobblemon:pokemon,tag=cobblers.g"):
                return P
            if kind == "entity" and toks[0].startswith("@s[distance=.."):
                return True                              # within the leash
            raise AssertionError("unmodelled test %s %s" % (kind, toks))
        s.query = strict_query({"time query gametime": gt})
        s.world = world
        s.call("recovery/maintain")


M = CFG["claims"]["maintenance_ticks"]


# Without it maintenance never records when it last saw a guardian alive, so every note ever made counts (an old fight
# settles a guardian that later died of something else), or the record is written for another claim.
def test_maintenance_records_when_it_last_saw_each_guardian_alive():
    s = _vanish_sim(None, alive_t=None)
    ledger(s)["claims"].append(_claim(3, 2, OTHER_ID, P1, P1_ID))
    _maintain(s, [(7000, True, True)])
    assert {c["id"]: c.get("alive_t") for c in ledger(s)["claims"]} == {1: 7000, 2: 7000, 3: 7000}
    assert all(c["seen"] == 0 for c in ledger(s)["claims"])


# Without it a guardian hurt and left, then dead of something else, is settled for the old attacker; or a guardian
# killed after maintenance last saw it is rebuilt. Both through maintenance itself: seen alive, then two loaded passes
# without it.
@pytest.mark.parametrize("hit_t,settle", [(7000 - 100, False), (7000 + M // 2, True)], ids=["old fight", "killed"])
def test_maintenance_settles_a_kill_after_the_last_sighting_and_rebuilds_after_an_old_fight(hit_t, settle):
    s = _vanish_sim(None, alive_t=None)
    _maintain(s, [(7000, True, True)])
    for c in ledger(s)["claims"]:
        c["hit"] = {"who": P2_ID, "t": hit_t}
    _maintain(s, [(7000 + M, True, False), (7000 + 2 * M, True, False)])
    if settle:
        assert _settled(s) and _spawns(s) == []
    else:
        assert _spawns(s) and {c["state"] for c in ledger(s)["claims"]} == {"open"}


# Without it a guardian killed with a sword comes back if its killer leaves: settlement waits for maintenance to find
# the site loaded twice without it, however long that takes (the owner, 2026-09-27: "it should work both ways whether
# i kill it or my mon does"). Found by this suite at 3e2906e, when the note had to be under 400 ticks old; fixed in
# 4a37312.
def test_a_guardian_killed_by_a_player_who_then_leaves_is_settled_not_rebuilt():
    s = _vanish_sim(None, alive_t=None)
    _maintain(s, [(9900, True, True)])                                    # seen alive before the fight
    for c in ledger(s)["claims"]:
        c["hit"] = {"who": P2_ID, "t": 10000}
    unloaded = [(10000 + M // 2 + k * M, False, False) for k in range(20)]
    back = [(13000 + M // 2, True, False), (13000 + M // 2 + M, True, False)]
    _maintain(s, unloaded + back)
    assert not _spawns(s), "rebuilt though a player killed it"
    assert _settled(s)
