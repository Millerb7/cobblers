"""The dungeon's NPC fights: the CobbleDollars clawback, the Foreman's crews, the stands' classes and battle start
(tools/dungeon_fights.py, unit DG-CLAW, 2026-10-09).

Written by the builder because the brief asked for it; an independent test author should extend it. Three kinds of
check, none reading its expectation from the code under test:

  sweeps      over the BUILT pack, not a list of ours: every `q.npc.start_battle(` is preceded by a call that reaches
              claw/begin, every battle_victory callback's player-winner branch calls claw/settle and settle reaches
              `cobbledollars remove`, every NPC class file has its claw/bounds function, the tick and load tags name the
              clawback. A fixture stand is merged into the pack so the stand path is swept too.
  hand sums   the CobbleDollars bounds are recomputed here from the bytecode formula (B = S*S // 10; credit between
              (B + B//2) * 1.25 and 3B * 1.25, floored) for parties written out by hand from data/dungeons.json's rule.
  behaviour   the generated functions run in tests/test_dungeon.py's command model (imported, not copied), extended in
              tests/pocket_sim.py with `cobbledollars query|give|remove`. CobbleDollars' own payout is a credit the test
              makes at a moment it chooses, before the callback or after it, because the jar does not fix the order.

Mutations edit the GENERATOR's source in memory and leave every data file alone ("How to prove an audit is independent").

Not covered (needs a server, EXP-060 for the arena's identical timing): that `cobbledollars query` stores the balance
through `execute store result`; that CobbleDollars credits a win inside cobblers:pocket; which handler runs first; that
a datapack tick function runs before the callback's next-tick look (it is the first thing a tick runs).
"""
from __future__ import annotations

import json
import re
import sys
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tests"))

import dungeon as D  # noqa: E402
import dungeon_fights as DF  # noqa: E402
import pocket_sim as PS  # noqa: E402
import test_dungeon as TD  # noqa: E402

DOC = D.load()
NPCS = "data/cobblers/npcs/"
FUNCS = "data/cobblers/function/dungeons/"
MOLANG = "data/cobblemon/callbacks/battle_victory/"
BEGIN, SETTLE = "cobblers:dungeons/claw/begin", "cobblers:dungeons/claw/settle"

# ---- the Foreman's crews and the hand arithmetic -------------------------------------------------------------------
# Band 1 (base 20): the first stage's crew, ace Electabuzz at 18, the others at 17. Written out by hand.
B1_S1_LEVELS = [17, 17, 18]


def hand_bounds(levels):
    """(most, least) CobbleDollars credit: B = S*S // 10; most 3B * 1.25, least (B + B//2) * 1.25, both floored."""
    b = max(1, sum(levels) ** 2 // 10)
    return 3 * b * 5 // 4, (b + b // 2) * 5 // 4


def test_the_hand_bounds_of_the_first_stage():
    assert hand_bounds(B1_S1_LEVELS) == (1012, 506)             # S = 52, B = 270


# ---- the built pack, with a fixture stand merged in ----------------------------------------------------------------
ROOM = {"id": "t_room", "params": {"trainers": [{"name": "Test Hand", "team_by_band": {
    "1": ["rattata", "pidgey"], "2": ["raticate", "pidgeotto", "geodude"], "3": ["raticate", "pidgeotto", "geodude"],
    "4": ["raticate", "pidgeotto", "geodude", "onix"], "5": ["raticate", "pidgeotto", "geodude", "onix", "machoke"],
    "6": ["raticate", "pidgeotto", "geodude", "onix", "machoke", "golem"]}}]}}
SID = 7
CLEAR = "cobblers:dungeons/test/clear"
D0 = DOC["dungeons"][0]
S1 = D.slots(DOC)[0]
PT = D.points(DOC, S1)
SPOT = (PT["box"][0] + 10, 96, S1["cz"])


def with_stand(files):
    files = dict(files)
    for rel, text in DF.stand_files(DOC, D0, ROOM).items():
        files[rel] = text
    fns = DF.stand_functions(DOC, D0, ROOM, 1, S1["g"], SPOT, SID)
    fns.update(DF.stand_dispatch([(SID, CLEAR)]))
    fns["test/clear"] = ["tag @s add t_cleared"]
    for name, lines in fns.items():
        files[FUNCS + name + ".mcfunction"] = "\n".join(lines) + "\n"
    return files


@pytest.fixture(scope="module")
def built():
    return D.build(DOC)


@pytest.fixture(scope="module")
def built_with_stand(built):
    return with_stand(built)


def fn_table(files):
    out = {}
    for rel, text in files.items():
        if rel.startswith(FUNCS) and rel.endswith(".mcfunction"):
            out["cobblers:dungeons/" + rel[len(FUNCS):-len(".mcfunction")]] = [
                l for l in text.splitlines() if l.strip() and not l.startswith("#")]
    return out


def calls(lines):
    return re.findall(r"\bfunction (cobblers:[a-z0-9_/.-]+)", " ".join(lines))


def reaches(fns, start, pred, seen=None):
    """Does `start` (a function id) or anything it calls contain a line satisfying pred?"""
    seen = seen if seen is not None else set()
    if start in seen or start not in fns:
        return False
    seen.add(start)
    return any(pred(l) for l in fns[start]) or any(reaches(fns, c, pred, seen) for c in calls(fns[start]))


# ---- the sweeps ----------------------------------------------------------------------------------------------------


def sweep(files):
    """Every problem with the clawback's coverage of the pack `files` (a built datapack). Empty means covered."""
    bad = []
    fns = fn_table(files)
    battle_starts = 0
    for name, lines in fns.items():
        for i, l in enumerate(lines):
            if "q.npc.start_battle(" not in l:
                continue
            battle_starts += 1
            before = lines[:i]
            ok = any(c == BEGIN or reaches(fns, c, lambda x: x == "function %s" % BEGIN)
                     for ln in before for c in calls([ln]))
            if not ok:
                bad.append("%s starts a battle with no claw/begin before it" % name)
    if not battle_starts:
        bad.append("the sweep found no start_battle at all")
    victories = [(rel, t) for rel, t in files.items() if rel.startswith(MOLANG)]
    if not victories:
        bad.append("no battle_victory callback")
    for rel, text in victories:
        m = re.search(r"for_each\(t\.w, c\.player_winners.*?\}\); \};", text.replace("\n", " "))
        branch = m.group(0) if m else ""
        if "function %s" % SETTLE not in branch:
            bad.append("%s: the player-winner branch does not call claw/settle" % rel)
    if not reaches(fns, SETTLE, lambda l: l.startswith("$cobbledollars remove")):
        bad.append("claw/settle never reaches `cobbledollars remove`")
    if not reaches(fns, SETTLE, lambda l: "set @s dg.claw 1" in l):
        bad.append("claw/settle never defers a win (dg.claw 1)")
    for rel in files:
        if rel.startswith(NPCS) and rel.endswith(".json"):
            stem = rel[len(NPCS):-len(".json")]
            if "cobblers:dungeons/claw/bounds/%s" % stem not in fns:
                bad.append("class %s has no claw/bounds function" % stem)
    if "cobblers:dungeons/claw/tick" not in json.loads(files["data/minecraft/tags/function/tick.json"])["values"]:
        bad.append("claw/tick is not in tick.json")
    if "cobblers:dungeons/claw/init" not in json.loads(files["data/minecraft/tags/function/load.json"])["values"]:
        bad.append("claw/init is not in load.json")
    return bad


def test_the_built_pack_is_covered(built):
    assert sweep(built) == []


def test_the_pack_with_a_stand_is_covered_and_the_sweep_sees_the_stand(built_with_stand):
    assert sweep(built_with_stand) == []
    fns = fn_table(built_with_stand)
    starts = [n for n, ls in fns.items() if any("q.npc.start_battle(" in l for l in ls)]
    assert any("/stand/" in n for n in starts) and any("/slot/" in n for n in starts), starts


def test_every_function_the_pack_calls_exists(built_with_stand):
    fns = fn_table(built_with_stand)
    # the pack's own functions only: levelcap and the blackout's two are other packs' (tests/test_dungeon.py FAKES)
    missing = {c for ls in fns.values() for c in calls(ls) if c.startswith("cobblers:dungeons/") and c not in fns}
    assert not missing, sorted(missing)[:5]


# ---- mutations of the GENERATORS -----------------------------------------------------------------------------------


def mutated(module, old, new):
    path = ROOT / "tools" / ("%s.py" % module)
    src = path.read_text(encoding="utf-8")
    assert src.count(old) == 1, "the mutation's anchor is not unique in tools/%s.py: %r" % (module, old)
    mod = types.ModuleType("%s_mutant" % module)
    mod.__file__ = str(path)
    exec(compile(src.replace(old, new), str(path), "exec"), mod.__dict__)
    return mod


def test_mutation_the_victory_path_without_the_clawback_is_found(monkeypatch):
    mutant = mutated("dungeon_fights", '% (npc, F("claw/settle")),', '% (npc, F("claw/drop")),')
    monkeypatch.setitem(sys.modules, "dungeon_fights", mutant)
    files = D.build(DOC)
    bad = sweep(files)
    assert any("claw/settle" in b for b in bad), bad


def test_mutation_dropping_the_settle_call_leaves_the_payout_with_the_player(tmp_path, monkeypatch):
    # the same scenario as test_a_boss_win_pays_nothing_net_*, run against a build whose victory path lost its
    # claw/settle call: the player keeps the 800 (the data file is untouched; only the generator changed)
    mutant = mutated("dungeon_fights", '% (npc, F("claw/settle")),', '% (npc, F("claw/drop")),')
    monkeypatch.setitem(sys.modules, "dungeon_fights", mutant)
    D.write(D.build(DOC), tmp_path)
    w, p, npc = boss_fight(tmp_path)
    w.tick(1)
    w.money[p.holder] += 800
    win(w, p, npc)
    assert w.money[p.holder] == 1800


def test_mutation_a_battle_start_without_the_baseline_is_found(monkeypatch):
    mutant = mutated("dungeon", '''            "function %s" % F("claw/boss_begin_%s" % d["short"]),\n''', "")
    files = mutant.build(mutant.load())
    bad = sweep(files)
    assert any("starts a battle with no claw/begin" in b for b in bad), bad


def test_mutation_a_stand_that_forgets_the_baseline_is_found(monkeypatch):
    mutant = mutated("dungeon_fights", '        "function %s" % F("claw/begin"),\n        "execute in %s run runmolang',
                     '        "execute in %s run runmolang')
    monkeypatch.setitem(sys.modules, "dungeon_fights", mutant)
    files = D.build(DOC)
    fns = mutant.stand_functions(DOC, D0, ROOM, 1, S1["g"], SPOT, SID)
    for name, lines in fns.items():
        files[FUNCS + name + ".mcfunction"] = "\n".join(lines) + "\n"
    bad = sweep(files)
    assert any("/stand/" in b and "no claw/begin" in b for b in bad), bad


def test_mutation_a_clawback_that_takes_nothing_is_found(monkeypatch):
    mutant = mutated("dungeon_fights", '"$cobbledollars remove @s $(amount)"', '"$cobbledollars give @s 0"')
    monkeypatch.setitem(sys.modules, "dungeon_fights", mutant)
    files = D.build(DOC)
    assert any("cobbledollars remove" in b for b in sweep(files))


# ---- the boss classes match boss.teams -----------------------------------------------------------------------------


def test_the_boss_classes_are_boss_teams_by_hand(built):
    bo = D0["boss"]
    seen = 0
    for band in DOC["engine"]["bands"]:
        base = min(band["caps"])
        for k, off in enumerate(bo["stage_level_offsets"], 1):
            crew = bo["teams"][str(band["band"])][k - 1]
            want = ["%s level=%d" % (sp, base + off + (0 if i == len(crew) - 1 else bo["member_level_offset"]))
                    for i, sp in enumerate(crew)]
            cls = json.loads(built["%sdg_ns_boss_b%d_s%d.json" % (NPCS, band["band"], k)])
            assert cls["party"]["pokemon"] == want, (band["band"], k)
            assert cls["party"]["pokemon"][-1].endswith("level=%d" % (base + off))        # the ace last, at the stage
            assert len(crew) <= 6
            seen += 1
    assert seen == 18


def test_a_boss_crew_is_never_above_the_bands_lower_cap(built):
    for rel, text in built.items():
        m = re.fullmatch(NPCS + r"dg_ns_boss_b(\d)_s\d\.json", rel)
        if m:
            band = DOC["engine"]["bands"][int(m.group(1)) - 1]
            for p in json.loads(text)["party"]["pokemon"]:
                assert int(p.split("level=")[1]) <= min(band["caps"]), (rel, p)


def test_every_class_has_the_boss_class_shape(built_with_stand):
    boss = json.loads(built_with_stand[NPCS + "dg_ns_boss_b1_s1.json"])
    stand = json.loads(built_with_stand[NPCS + "dg_ns_st_t_room_t1_b1.json"])
    assert set(stand) == set(boss) and stand["ai"] == boss["ai"] and stand["resourceIdentifier"] == boss["resourceIdentifier"]
    assert stand["battleConfiguration"] == boss["battleConfiguration"] and stand["isInvulnerable"] is True


def test_every_bound_is_the_hand_bound_of_its_party(built_with_stand):
    n = 0
    for rel, text in built_with_stand.items():
        m = re.fullmatch(NPCS + r"(dg_.+)\.json", rel)
        if not m:
            continue
        levels = [int(p.split("level=")[1]) for p in json.loads(text)["party"]["pokemon"]]
        body = built_with_stand["%sclaw/bounds/%s.mcfunction" % (FUNCS, m.group(1))]
        hi = int(re.search(r"dg\.cmax (\d+)", body).group(1))
        lo = int(re.search(r"dg\.cmin (\d+)", body).group(1))
        want_hi, want_lo = hand_bounds(levels)
        assert hi == want_hi, rel                        # the most is exact
        assert 0 < lo <= want_lo and lo >= want_lo * 0.99, (rel, lo, want_lo)   # the least is never above the true least
        n += 1
    # each dungeon's boss: 6 bands x 3 stages; 6 bands for every trainer of every stand and gauntlet room the data
    # carries (DG-INTEGRATE: the three full-length dungeons seat 15); the test stand's 6
    trainers = sum(len(r["params"]["trainers"]) for d in DOC["dungeons"] for r in d.get("rooms") or []
                   if r["kind"] in ("stand", "gauntlet"))
    assert trainers > 0
    assert n == 18 * len(DOC["dungeons"]) + 6 * trainers + 6


# ---- the stands' classes -------------------------------------------------------------------------------------------


def test_stand_levels_follow_the_designs_members_and_levels():
    members = {1: 2, 2: 3, 3: 3, 4: 4, 5: 5, 6: 6}                           # DUNGEONS.md 5.3, by hand
    classes = DF.stand_classes(DOC, D0, ROOM)
    assert len(classes) == 6
    for b in DOC["engine"]["bands"]:
        cls = classes["dg_ns_st_t_room_t1_b%d" % b["band"]][0]
        lv = [int(p.split("level=")[1]) for p in cls["party"]["pokemon"]]
        assert len(lv) == members[b["band"]] and lv == sorted(lv)
        if b["band"] == 6:
            assert lv[0] == 95 and lv[-1] == 99 and all(95 <= x <= 99 for x in lv)
        else:
            lo = min(b["caps"])
            assert lv[0] == lo - 2 and lv[-1] == lo - 1 and all(lo - 2 <= x <= lo - 1 for x in lv), (b["band"], lv)


def test_a_stand_with_the_wrong_member_count_or_a_bad_id_is_refused():
    bad = json.loads(json.dumps(ROOM))
    bad["params"]["trainers"][0]["team_by_band"]["3"] = ["geodude"]
    with pytest.raises(DF.FightError, match="band 3"):
        DF.stand_classes(DOC, D0, bad)
    with pytest.raises(DF.FightError, match="room id"):
        DF.stand_classes(DOC, D0, {"id": "Bad Room", "params": ROOM["params"]})
    with pytest.raises(DF.FightError, match="neither"):
        DF.stand_classes(DOC, D0, {"id": "x", "params": {}})
    with pytest.raises(DF.FightError, match="pool"):
        DF.stand_classes(DOC, D0, {"id": "x", "params": {"pool": "nope"}})


def test_a_pool_id_resolves_through_the_engine_record():
    doc = json.loads(json.dumps(DOC))
    doc["engine"]["stands"]["pools"]["p1"] = ROOM["params"]["trainers"]
    assert list(DF.stand_classes(doc, D0, {"id": "pooled", "params": {"pool": "p1"}})) == [
        "dg_ns_st_pooled_t1_b%d" % b for b in range(1, 7)]


def test_two_stands_with_one_id_are_refused():
    with pytest.raises(DF.FightError, match="twice"):
        DF.stand_dispatch([(3, "cobblers:a"), (3, "cobblers:b")])


# ---- behaviour: the money -----------------------------------------------------------------------------------------


@pytest.fixture(scope="module")
def pack_dir(tmp_path_factory, built_with_stand):
    out = tmp_path_factory.mktemp("dg_fights")
    D.write(built_with_stand, out)
    return out


def boss_fight(pack_dir):
    """A world with the player at the boss, stage 1 spawned and its battle started. Returns (w, p, npc)."""
    w = TD.world(pack_dir)
    p = w.player("Lance", TD.OW, (1352.5, 130, 4120.5))
    p.inventory.append(TD.soot())
    TD.click_rip(w, p)
    s = TD.arrive_and_cross(w, p)
    pt = D.points(DOC, s)
    # the arena's own floor and middle (pass 2 seats the arena below floor_y and off the slot's centre line)
    p.pos = [pt["spot"][0] - 4.5, float(pt["spot"][1]), pt["spot"][2] + 0.5]
    w.money[p.holder] = 1000
    w.passes(1)
    npc = next(e for e in w.ents if e.kind == "cobblemon:npc" and e.alive)
    w.passes(1)
    assert w.started and w.started[-1][0] == "Lance"
    assert w.get(p.name, "dg.band") == 1
    return w, p, npc


def win(w, p, npc):
    w.run_callback("battle_victory", context={
        "scriptable_losers": [{"is_npc": 1, "uuid": npc.uid}], "player_winners": [{"player": {"username": p.name}}],
        "scriptable_winners": [], "player_losers": []})


@pytest.mark.parametrize("order", ["cobbledollars_first", "callback_first"])
@pytest.mark.parametrize("credit", [506, 800, 1012])
def test_a_boss_win_pays_nothing_net_in_either_handler_order(pack_dir, order, credit):
    w, p, npc = boss_fight(pack_dir)
    w.tick(1)                                          # the tick function re-reads the baseline
    if order == "cobbledollars_first":
        w.money[p.holder] += credit                    # CobbleDollars' battleVictory, then the callback
        win(w, p, npc)
    else:
        win(w, p, npc)                                 # the callback, then CobbleDollars' handler
        assert w.get(p.name, "dg.claw") == 1 and w.money[p.holder] == 1000
        w.money[p.holder] += credit
        w.tick(1)                                      # the start of the next tick
    assert w.money[p.holder] == 1000, order
    assert not w.get(p.name, "dg.claw") and w.get(p.name, "dg.bal") is None


def test_money_moved_in_battle_is_not_taken(pack_dir):
    w, p, npc = boss_fight(pack_dir)
    w.tick(1)
    w.money[p.holder] -= 150                           # spent between ticks, mid-battle
    w.tick(1)                                          # the next tick's baseline includes it
    w.money[p.holder] += 800
    win(w, p, npc)
    assert w.money[p.holder] == 850                    # 1000 - 150: the payout alone went back


def test_the_take_is_bounded_by_the_most_the_class_can_pay(pack_dir):
    w, p, npc = boss_fight(pack_dir)
    w.tick(1)
    w.money[p.holder] += 1012 + 5000                   # the payout at its maximum and a gift in the same window
    win(w, p, npc)
    assert w.money[p.holder] == 1000 + 5000            # exactly the 1,012 hand maximum went back, no more


def test_a_player_who_cannot_pay_it_back_loses_no_more_than_they_hold(pack_dir):
    w, p, npc = boss_fight(pack_dir)
    w.tick(1)
    w.money[p.holder] += 800
    w.money[p.holder] = 100                            # spent almost everything inside the same tick window
    win(w, p, npc)
    assert w.money[p.holder] >= 0


def test_a_baseline_outside_a_run_is_dropped_and_a_pending_look_is_resolved(pack_dir):
    w, p, npc = boss_fight(pack_dir)
    q = w.player("Ash", TD.OW, (0.5, 70, 0.5))
    w.set(q.name, "dg.bal", 777)
    w.tick(1)
    assert w.get(q.name, "dg.bal") is None             # not in a run (dg.st unset): no baseline is kept
    assert w.get(p.name, "dg.bal") is not None         # in the run: re-read every tick


def test_the_second_look_waits_for_the_tick_not_the_callback(pack_dir):
    w, p, npc = boss_fight(pack_dir)
    w.tick(1)
    win(w, p, npc)                                     # nothing paid yet: deferred
    assert w.get(p.name, "dg.claw") == 1
    w.tick(1)                                          # CobbleDollars never paid: nothing to take, and nothing pending
    assert w.get(p.name, "dg.claw") == 0 and w.money[p.holder] == 1000


# ---- behaviour: a stand ----------------------------------------------------------------------------------------


def stand_world(pack_dir):
    w = TD.world(pack_dir)
    p = w.player("Lance", TD.OW, (1352.5, 130, 4120.5))
    p.inventory.append(TD.soot())
    TD.click_rip(w, p)
    TD.arrive_and_cross(w, p)
    p.pos = [SPOT[0] - 3.5, 96.0, SPOT[2] + 0.5]
    w.money[p.holder] = 500
    return w, p


START = "cobblers:dungeons/stand/%s/start" % DF.stand_key(D0, ROOM, 1, S1["g"])


def test_a_stand_spawns_its_class_binds_it_and_starts_the_battle_later(pack_dir):
    w, p = stand_world(pack_dir)
    w.call(START, PS.Ctx(p, p.dim, p.pos))
    (npc,) = [e for e in w.ents if e.kind == "cobblemon:npc" and e.alive]
    assert npc.nbt["NPCClass"] == "cobblers:dg_ns_st_t_room_t1_b1" and npc.nbt["level"] == 19
    key = DF.stand_key(D0, ROOM, 1, S1["g"])
    assert {"dg.stand", "dg.npc", "dg.stk." + key, TD.EXEMPT} <= npc.tags
    assert w.get(npc.holder, "dg.sid") == SID
    assert not w.started and ("dg.sgo." + key) in p.tags
    w.tick(DOC["engine"]["stands"]["go_ticks"] - 1)
    assert not w.started
    w.tick(1)
    assert w.started and w.started[-1][0] == "Lance" and ("dg.sgo." + key) not in p.tags
    assert w.get(p.name, "dg.claw") == 0 and w.get(p.name, "dg.bal") == 500
    assert (w.get(p.name, "dg.cmax"), w.get(p.name, "dg.cmin")) == (510, 255)       # levels 18, 19: S = 37, B = 136, by hand


@pytest.mark.parametrize("order", ["cobbledollars_first", "callback_first"])
def test_a_stand_win_pays_nothing_net_and_runs_the_rooms_clear(pack_dir, order):
    w, p = stand_world(pack_dir)
    w.call(START, PS.Ctx(p, p.dim, p.pos))
    w.tick(DOC["engine"]["stands"]["go_ticks"])
    (npc,) = [e for e in w.ents if e.kind == "cobblemon:npc" and e.alive]
    w.tick(1)
    if order == "cobbledollars_first":
        w.money[p.holder] += 400
        win(w, p, npc)
    else:
        win(w, p, npc)
        w.money[p.holder] += 400
        w.tick(1)
    assert w.money[p.holder] == 500
    assert "t_cleared" in p.tags and w.get(p.name, "dg.sid") is None, "the dispatch reached the room's clear"


def test_a_boss_win_does_not_run_a_stands_clear(pack_dir):
    w, p, npc = boss_fight(pack_dir)
    w.tick(1)
    win(w, p, npc)
    assert "t_cleared" not in p.tags and w.get(p.name, "dg.sid") is None


def test_a_refused_stand_battle_retries_then_says_so(pack_dir):
    w, p = stand_world(pack_dir)
    key = DF.stand_key(D0, ROOM, 1, S1["g"])
    refused = "cobblers:dungeons/stand/%s/refused" % key
    w.set(p.name, "dg.sgo", 2)
    w.call(refused, PS.Ctx(p, p.dim, p.pos))
    assert ("dg.sgo." + key) in p.tags and "cobblers:dungeons/stand/%s/go" % key in w.scheduled
    p.tags.discard("dg.sgo." + key)
    w.scheduled.clear()
    w.call(refused, PS.Ctx(p, p.dim, p.pos))             # the last try
    assert ("dg.sgo." + key) not in p.tags and not w.scheduled
