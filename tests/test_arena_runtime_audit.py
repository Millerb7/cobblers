"""tools/arena_runtime_audit.py: Heaven's Arena's runtime pack, audited independently of its builder.

The audit derives every expectation from data/arena_fights.json, data/arena_trainers.json, data/arena_dome.json,
data/progression.json, data/league_trainers.json and data/blackout.json, and EXECUTES the emitted functions in its own
command model. tools/arena_runtime.py is used here only to EMIT the pack under test, never for an expectation.

PROOF OF INDEPENDENCE: the generator is mutated, the data is not. Each MUTANTS entry below edits tools/arena_runtime.py's
source in memory (data/ untouched), emits a pack from the mutant and runs the audit on it. Observed 2026-10-03, every
mutant fails the audit with the named problem:
  min_rank      pool filter `min_rank <= n` -> `<= n + 1`: rank 1's pool gains froslass, krookodile, rhyperior
  purse_k       purse coefficient k -> k + 1: rank 1 pays 2350 against the data's 2200 (54 problems)
  intermission  rank 8's heal moved from before leg 4 to before leg 5: "rank 8 leg 3: 0 heals, the format says 1"
  exh_bonus     the clear bonus no longer withheld from an exhibition: rank 3 played down pays [550, 2000]
  owner         the opponent's owner marker set to 1 for everyone: the second player's battle never starts
  legs          gauntlet `legs - 1` -> `legs - 2`: rank 3's run ends (and pays its clear bonus) after one leg
  tag_early     the blackout exemption tag dropped at the loss itself: the loss reaches cobblers:blackout/dedupe
  prize_once    the first-clear guard reads the wrong tag: every rank's prize is given again on a second rank-up
  streak_every  the streak levels up every 2 wins, not 3: "streak bout 2 ... ace 78" and the purse off by 100
  exam_level    each exam member one level over the authored team: the exam classes' teams differ from the data
  relative      spawnnpcat at relative coordinates: refused by the static check and by the model
  named_holder  a player's name as a score holder: refused by the no-identity check
A mutation test that only edited data would move the expectation and the output together and prove nothing.

NOT COVERED (validity is not runtime behaviour; see the audit's own docstring): Cobblemon accepting each properties
string, the battle_victory event's real collections, levelVariation's bound (relayed from the research note), two
players, a forfeit and a flee in a real server. Those are an experiment, not pytest.
"""
import json
import sys
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import arena_runtime_audit as A  # noqa: E402

SRC = (ROOT / "tools" / "arena_runtime.py").read_text(encoding="utf-8")


def emit(out, source=SRC):
    """The pack as tools/arena_runtime.py (or a mutant of it) writes it."""
    mod = types.ModuleType("arena_runtime_under_test")
    mod.__file__ = str(ROOT / "tools" / "arena_runtime.py")
    exec(compile(source, "arena_runtime_under_test", "exec"), mod.__dict__)
    mod.main(["--out", str(out)])
    return out


@pytest.fixture(scope="module")
def pack(tmp_path_factory):
    return emit(tmp_path_factory.mktemp("arena") / "cobblers_arena")


@pytest.fixture(scope="module")
def report(pack):
    return A.audit(pack), dict(A.STATS)


def unknown(problems):
    return [p for p in problems if not p.startswith("KNOWN")]


# Protects: the emitted pack matches the data in every audited property. Removing it lets any drift ship.
def test_the_emitted_pack_meets_the_data_but_for_known_defects(report):
    problems, _stats = report
    assert unknown(problems) == []


# Protects: the flows really ran the ladder; a model that silently ran nothing would pass everything above.
def test_the_flows_ran_every_bout_the_data_implies(report):
    _p, stats = report
    E = A.Expect()
    pool = sum(E.need(n) * E.legs(n) for n in E.ranks if not E.is_streak(n))
    exams = sum(len(E.exam_legs(n)) for n in E.exams)
    ms = [m["streak"] for m in E.ranks[E.streak()[0]]["milestones"]]
    streak = (max(ms) + 1) + (min(ms) + 1)
    assert stats["wins"] >= pool + exams + streak
    assert stats["losses"] >= 3                      # the gauntlet loss and two streak losses
    assert stats["clicks"] >= len(E.venues) * len(E.ranks) * 8


# Protects: a KNOWN defect is pruned when the builder fixes it, so the list never hides a new one under an old name.
def test_known_defects_still_reproduce(report):
    problems, _s = report
    for key in A.KNOWN:
        assert any(p.startswith("KNOWN %s" % key) for p in problems), "KNOWN %s no longer reproduces: remove it" % key


MUTANTS = {
    "min_rank": ('open_sets = [s for s in sets if s["min_rank"] <= n]',
                 'open_sets = [s for s in sets if s["min_rank"] <= n + 1]',
                 "set_pool entries with min_rank <= 1"),
    "purse_k": ("return (k * sum(levels) + step // 2 - 1) // step * step",
                "return ((k + 1) * sum(levels) + step // 2 - 1) // step * step",
                "rank 1 leg 0: paid [2350]"),
    "intermission": ('% (n, e["heal_before_leg"]))', '% (n, e["heal_before_leg"] + 1))',
                     "rank 8 leg 3: 0 heals"),
    "exh_bonus": ('"execute if score @s ar.cur matches %d if score @s ar.exh matches 0 run function %s {amount:%d}"',
                  '"execute if score @s ar.cur matches %d run function %s {amount:%d}"',
                  "exhibition rank 3"),
    "owner": ('"scoreboard players operation @s ar.id = #me ar.id"]', '"scoreboard players set @s ar.id 1"]',
              "two players"),
    "legs": ('"@s ar.next 1" % (n, e["legs"] - 1))', '"@s ar.next 1" % (n, e["legs"] - 2))',
             "rank 3 leg 0: paid [2300, 2000]"),
    "tag_early": ('"scoreboard players set @s ar.idle 0",\n        "scoreboard players set @s ar.end %d" % END_TICKS]',
                  '"scoreboard players set @s ar.idle 0", "tag @s remove %s" % bout_tag,\n'
                  '        "scoreboard players set @s ar.end %d" % END_TICKS]',
                  "an arena loss reached the blackout"),
    "prize_once": ('"execute if score @s ar.rank matches %d unless entity @s[tag=cobblers.%s]',
                   '"execute if score @s ar.rank matches %d unless entity @s[tag=cobblers.x%s]',
                   "a second rank-up gave the first-clear prize again"),
    "streak_every": ('"scoreboard players set #k ar.t %d" % st["level_step_every_wins"]',
                     '"scoreboard players set #k ar.t %d" % (st["level_step_every_wins"] - 1)',
                     "streak bout 2"),
    "exam_level": ('[properties(m, m["level"]) for m in t["team"]]', '[properties(m, m["level"] + 1) for m in t["team"]]',
                   "authored team"),
    "relative": ('"$spawnnpcat %s %s %s $(cls) $(level)" % (fmt(ox), fmt(oy), fmt(oz))',
                 '"$spawnnpcat ~ ~ ~%s $(cls) $(level)" % fmt(0)',
                 "not ABSOLUTE coordinates"),
    "named_holder": ('"scoreboard players operation @s ar.id = #next ar.id"]',
                     '"scoreboard players operation Steve ar.id = #next ar.id"]',
                     "a named score holder 'Steve'"),
}


# Protects: the audit's independence from the builder. Each mutant changes the GENERATOR with data/ untouched; an
# audit that shared the builder's derivation would pass it. Removing this leaves independence asserted, not shown.
@pytest.mark.parametrize("name", sorted(MUTANTS))
def test_a_mutated_generator_fails_the_audit(name, tmp_path):
    old, new, expect = MUTANTS[name]
    assert SRC.count(old) == 1, "mutant %s no longer matches tools/arena_runtime.py: re-aim it" % name
    out = emit(tmp_path / "pack", SRC.replace(old, new))
    bad = unknown(A.audit(out, route=False))
    assert bad, "the audit passed a generator mutated by %s" % name
    assert any(expect in p for p in bad), bad[:5]


# Protects: the command model's arithmetic, macros, return and selectors, on a hand-computed fixture; an interpreter
# that got floor division, macro substitution or `return run` wrong would mis-judge every flow above.
def test_the_command_model_runs_a_hand_computed_pack(tmp_path):
    root = tmp_path / "p"
    (root / "data/minecraft/tags/function").mkdir(parents=True)
    (root / "data/t/function").mkdir(parents=True)
    (root / "pack.mcmeta").write_text('{"pack":{"pack_format":48,"description":"fixture"}}')
    (root / "data/minecraft/tags/function/load.json").write_text('{"values":["t:load"]}')
    (root / "data/minecraft/tags/function/tick.json").write_text('{"values":[]}')
    (root / "data/cobblemon/callbacks/battle_victory").mkdir(parents=True)
    (root / "data/cobblemon/callbacks/battle_victory/x.molang").write_text(
        "for_each(t.l, c.scriptable_losers, {\n  t.l.is_npc ? {\n    for_each(t.w, c.player_winners, {\n"
        "      q.run_command('scoreboard players set #o v 1');\n    });\n  };\n});\n"
        "for_each(t.v, c.scriptable_winners, {\n  t.v.is_npc ? {\n    for_each(t.p, c.player_losers, {\n"
        "      q.run_command('scoreboard players set #o v 2');\n    });\n  };\n});\n")
    fns = {
        "load": ["scoreboard objectives add v dummy", "scoreboard players set #a v -7", "scoreboard players set #b v 2",
                 "scoreboard players operation #a v /= #b v",          # floor(-7 / 2) = -4
                 "scoreboard players set #c v -7", "scoreboard players operation #c v %= #b v",   # floorMod = 1
                 "function t:pay {amount:150}",
                 "data modify storage t:s a set value {amount:25}", "function t:pay with storage t:s a",
                 "function t:early", "execute as @a[scores={v=5}] run scoreboard players add #hit v 1"],
        "pay": ["$scoreboard players add #sum v $(amount)"],               # 150 + 25 = 175
        "early": ["scoreboard players set #r v 1", "execute if score #r v matches 1 run return run scoreboard "
                  "players set #r v 2", "scoreboard players set #r v 99"],   # returns at 2, never 99
    }
    for k, v in fns.items():
        (root / ("data/t/function/%s.mcfunction" % k)).write_text("\n".join(v) + "\n")
    W = A.World(A.Pack(root))
    assert W.score("#a", "v") == -4
    assert W.score("#c", "v") == 1
    assert W.score("#sum", "v") == 175
    assert W.score("#r", "v") == 2
    assert W.score("#hit", "v") is None                     # no player has v=5: the execute ran for no one
    p = W.player((0, 0, 0))
    W.set_score(p, "v", 5)
    W.command("execute as @a[scores={v=5},distance=..1] run scoreboard players add #hit v 1", None, (0.5, 0, 0))
    W.command("execute as @a[scores={v=5},distance=..1] run scoreboard players add #hit v 1", None, (3, 0, 0))
    assert W.score("#hit", "v") == 1                        # in range once, out of range once


# Protects: the purse's half-rounding is read from the data (rank 8: 13 x 225 = 2925 typed 2900), not assumed.
def test_nearest_rounds_an_exact_half_down_as_the_data_does():
    assert A.nearest(2925, 50) == 2900
    assert A.nearest(2926, 50) == 2950
    assert A.nearest(2184, 50) == 2200
    assert A.nearest(2145, 50) == 2150
    assert A.nearest(2100, 50) == 2100


# Protects: the data's own purse figures agree with its own formula; a slip there is named as the data's.
def test_the_data_agrees_with_its_own_purse_formula():
    problems = []
    A.check_data(A.Expect(), problems)
    assert problems == []


# Protects: only the bout tag exempts, only in the NPC-loss path. A tag check copied into the wild-loss path would
# let a player dodge the blackout with an arena tag; this proves the check sees it.
def test_the_blackout_check_bites_on_a_second_exemption():
    E = A.Expect()
    files = dict(A.blackout_files())
    ok = []
    A.check_blackout(E, files, ok)
    assert ok == []
    wild = "data/cobblers/function/blackout/battle_loss_wild.mcfunction"
    files[wild] = "execute if entity @s[tag=%s] run return 0\n" % E.bout_tag + files[wild]
    bad = []
    A.check_blackout(E, files, bad)
    assert any("NPC-loss path only" in p for p in bad)


# Protects: the seven retired spire champions stay retired in route_trainers (no seat, record or gate) and the other
# 56 stay seated. Removing it lets a champion reappear in the hub, or the hub's trainers vanish with them.
def test_route_trainers_seats_everyone_but_the_retired_champions():
    problems = []
    A.check_route_trainers(A.Expect(), problems)
    assert problems == []


# Protects: prepare runs the audit right after the pack it audits, so a failing pack stops prepare before install.
def test_prepare_runs_the_audit_right_after_arena_runtime():
    import reapply
    names = [n for n, _f in reapply.prepare_jobs(types.SimpleNamespace(source_root="", server_dir=""))]
    assert names.index("arena_runtime_audit") == names.index("arena_runtime") + 1


# Protects: the audit's verdict leaves the pack it read unchanged (an audit is a reader).
def test_the_audit_does_not_write_the_pack(pack):
    before = {p: p.read_bytes() for p in Path(pack).rglob("*") if p.is_file()}
    A.audit(pack, route=False)
    after = {p: p.read_bytes() for p in Path(pack).rglob("*") if p.is_file()}
    assert before == after
    assert json.loads((Path(pack) / "pack.mcmeta").read_text())["pack"]["pack_format"] == 48
