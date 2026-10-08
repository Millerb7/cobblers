"""tools/key_ball.py: the Beast Ball is the only ball that catches a dungeon boss (data/key_ball.json).

Written with the generator (the builder's own tests); the independent audit is another agent's. The expectations
come from the owner's decisions as data/key_ball.json records them and from the jar, not from the generated text: the
callbacks are RUN by tests/nbt_sim.py's MoLang interpreter (extended here with `*`, `has_tag` and the two event
functions, as Cobblemon 1.8.0 names them: PokemonCatchRateEvent set_catch_rate, PokeBallCaptureCalculatedEvent
set_shakes / set_critical_capture), for every ball, tagged and untagged targets, player and non-player throwers.
The jar checks skip, NOT_EXECUTED, without the server snapshot.

What none of this covers: that Cobblemon fires the scripts as modelled, that ball_type compares as a string, that
set_shakes(0) breaks free and a battle continues, that the give lands -- experiments/EXP-064-beast-ball-key.
"""
from __future__ import annotations

import json
import re
import sys
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tests"))

import key_ball as KB  # noqa: E402
import nbt_sim as N  # noqa: E402

DOC = KB.load()
FILES = KB.build(DOC)
TAG, KEY, MULT = DOC["tag"], DOC["key_ball"], DOC["multiplier"]
RATE_CB = "data/cobblemon/callbacks/pokemon_catch_rate_calculated/cobblers_key_ball.molang"
CAPTURE_CB = "data/cobblemon/callbacks/poke_ball_capture_calculated/cobblers_key_ball.molang"
REFUSED = "data/cobblers/function/key_ball/refused.mcfunction"
JAR = Path("C:/Users/wnd/Documents/cobblers-local/server-snapshot-2026-10-05/mods/Cobblemon-fabric-1.8.0+1.21.1.jar")
BLACKOUT = json.loads((ROOT / "data" / "blackout.json").read_text(encoding="utf-8"))
# every ball the blackout knows, plus the four it never takes: the throws the tests make
BALLS = sorted(set(BLACKOUT["claims"]["balls"]) | {"cobblemon:master_ball", "cobblemon:cherish_ball",
                                                     "cobblemon:park_ball", "cobblemon:ancient_origin_ball", KEY})


class Mol(N.Molang):
    """nbt_sim's MoLang with multiplication, an entity's has_tag and the catch events' setters."""

    def add(self):
        return self.binary(self.mul, ("+", "-"))

    def mul(self):
        return self.binary(self.unary, ("*", "/"))

    def run(self, context=None, query=None):
        self.calls = []
        return super().run(context, query)

    def ev(self, e):
        if e[0] == "bin" and e[1] in ("*", "/"):
            a, b = self.num(self.ev(e[2])), self.num(self.ev(e[3]))
            return a * b if e[1] == "*" else a / b
        if e[0] == "call" and e[1].endswith(".has_tag"):
            ent = self.lookup(e[1][:-len(".has_tag")])
            return 1.0 if self.ev(e[2][0]) in ent["tags"] else 0.0
        if e[0] == "call" and e[1] in ("q.set_catch_rate", "q.set_shakes", "q.set_critical_capture"):
            self.calls.append((e[1][2:], [self.ev(a) for a in e[2]]))
            return 0.0
        return super().ev(e)


def player(name="p1"):
    return {"is_player": True, "uuid": "uuid-" + name, "tags": []}


def mob(tags):
    return {"tags": list(tags)}


def throw_rate(ball, tags, rate=3.0):
    """The catch rate after our pokemon_catch_rate_calculated script (None: it set nothing)."""
    m = Mol(FILES[RATE_CB])
    m.run(query={"thrower": player(), "poke_ball_entity": {"ball_type": ball}, "pokemon_entity": mob(tags),
                 "catch_rate": rate})
    sets = [args[0] for name, args in m.calls if name == "set_catch_rate"]
    assert len(sets) <= 1, m.calls
    return sets[0] if sets else None


def throw_capture(ball, tags, thrower=None, successful=True):
    m = Mol(FILES[CAPTURE_CB])
    cmds = m.run(query={"thrower": thrower or player(), "pokemon": mob(tags), "poke_ball": {"ball_type": ball},
                        "is_successful_capture": successful, "is_critical_capture": False})
    return m.calls, cmds


# Without it the key does nothing, or something else gets the x5: exactly a Beast Ball at a tagged target has its
# rate multiplied, by the owner's x5; every other ball, and the Beast Ball at an untagged Pokemon (x1, as the jar's
# LabelModifier gives a non-Ultra-Beast), keeps the jar's rate untouched.
@pytest.mark.parametrize("ball", BALLS)
@pytest.mark.parametrize("tagged", [True, False])
def test_only_the_key_ball_at_a_tagged_boss_has_its_rate_raised(ball, tagged):
    got = throw_rate(ball, [TAG, "cobblers.eb"] if tagged else ["cobblers.eb"], rate=3.0)
    if tagged and ball == "cobblemon:beast_ball":
        assert got == pytest.approx(3.0 * 5) and MULT == 5
    else:
        assert got is None, (ball, tagged, got)


# Without it a Master Ball (or any ball) still catches a dungeon boss, or a refused ball is lost, or the key is
# refused: at a tagged boss every ball but the Beast Ball breaks free (set_shakes(0)) and its thrower gets exactly that
# ball back through key_ball/refused; the Beast Ball is left to its roll; an untagged Pokemon is never touched.
@pytest.mark.parametrize("ball", BALLS)
@pytest.mark.parametrize("tagged", [True, False])
def test_every_other_ball_breaks_free_at_a_tagged_boss_and_is_handed_back(ball, tagged):
    calls, cmds = throw_capture(ball, [TAG] if tagged else [], successful=True)
    refused = tagged and ball != "cobblemon:beast_ball"
    if refused:
        assert calls == [("set_shakes", [0.0])], (ball, calls)
        assert cmds == ['execute as uuid-p1 at @s run function cobblers:key_ball/refused {ball:"%s"}' % ball], cmds
    else:
        assert calls == [] and cmds == [], (ball, tagged, calls, cmds)


# Without it a ball thrown by a dispenser or a non-player would hand an item to nobody, or the script would read a
# player field off a non-player: the refusal still holds, and no command runs.
def test_a_non_player_throw_is_refused_and_given_nothing():
    calls, cmds = throw_capture("cobblemon:master_ball", [TAG], thrower={"is_player": False, "tags": []})
    assert calls == [("set_shakes", [0.0])] and cmds == []


# Without it the scripts could force a catch, which would make the order of the poke_ball_capture_calculated scripts
# matter (the level cap, the Hoopa cradle and Ursaluna refuse in the same folder; research note section 3): neither
# of ours ever calls set_critical_capture or sets a shake count other than 0, for any throw.
def test_our_scripts_only_ever_refuse():
    for ball in BALLS:
        for tags in ([TAG], []):
            for ok in (True, False):
                calls, _ = throw_capture(ball, tags, successful=ok)
                assert all(c == ("set_shakes", [0.0]) for c in calls), calls
    assert "set_critical_capture" not in FILES[CAPTURE_CB] + FILES[RATE_CB]


# Without it the order-free premise breaks silently elsewhere: every other generated poke_ball_capture_calculated
# script in the repo (the level cap, the Hoopa cradle, Ursaluna) also only refuses, so whichever order Cobblemon runs
# the folder in, a refusal from any of them wins and none can undo another's.
def test_every_other_capture_callback_in_the_repo_only_refuses():
    import hoopa_cradle
    import levelcap_pack
    import ursaluna_cave
    texts = {"levelcap": levelcap_pack.files(json.loads(levelcap_pack.DATA.read_text(encoding="utf-8"))),
             "hoopa": hoopa_cradle.callbacks(hoopa_cradle.load()),
             "ursaluna": ursaluna_cave.callback_files(ursaluna_cave.load())}
    seen = 0
    for who, files in texts.items():
        for rel, text in files.items():
            if "/poke_ball_capture_calculated/" not in rel:
                continue
            seen += 1
            assert "set_critical_capture" not in text, (who, rel)
            assert re.findall(r"set_shakes\(([^)]*)\)", text) == ["0"], (who, rel)
    assert seen == 3


def _run_refused(ball, gamemode="survival"):
    """Expand the macro as Minecraft does and return the commands that would run, with `execute unless entity
    @s[gamemode=X]` resolved for a player in `gamemode`."""
    out = []
    for line in FILES[REFUSED].split("\n"):
        if not line or line.startswith("#"):
            continue
        if line.startswith("$"):
            line = line[1:].replace("$(ball)", ball)
        assert "$(" not in line, line
        m = re.match(r"execute unless entity @s\[gamemode=(\w+)\] run (.*)", line)
        if m:
            if m.group(1) != gamemode:
                out.append(m.group(2))
            continue
        out.append(line)
    return out


# Without it a refused $27,000 Master Ball is gone, or a refund mints a ball: a survival thrower gets exactly one of
# the very ball refused; a creative thrower (whose throw took nothing) gets none; both see the owner's line.
@pytest.mark.parametrize("ball", ["cobblemon:master_ball", "cobblemon:ultra_ball", "cobblemon:poke_ball"])
def test_the_refund_is_one_of_the_same_ball_and_never_in_creative(ball):
    surv = _run_refused(ball)
    gives = [c for c in surv if c.startswith("give ")]
    assert gives == ["give @s %s 1" % ball], surv
    assert not [c for c in _run_refused(ball, "creative") if c.startswith("give ")]
    for cmds in (surv, _run_refused(ball, "creative")):
        tells = [json.loads(c[len("tellraw @s "):]) for c in cmds if c.startswith("tellraw @s ")]
        assert [t["text"] for t in tells] == [DOC["message"]]


# Without it the message gives the key away, or loses the owner's shape: it says the ball is wrong and that a Master
# Ball will not do either, and names no ball, no town and no shop.
def test_the_refusal_names_nothing():
    msg = DOC["message"]
    assert "it is not this." in msg and msg.endswith("Even a Master Ball will not close on it.")
    for word in ("beast", "ultra", "cinderlee", "crater", "volcano", "buy", "shop", "sold", "counter"):
        assert word not in msg.lower(), word
    bad = dict(DOC, message="It needs a Beast Ball. Even a Master Ball will not close on it.")
    assert any("hints at the key" in p for p in KB.problems(bad))


def _never(cond):
    """Fabric API 0.116.14 resource conditions, test-side: fabric:true and fabric:not (DefaultResourceConditionTypes)."""
    if cond["condition"] == "fabric:true":
        return True
    if cond["condition"] == "fabric:not":
        return not _never(cond["value"])
    raise AssertionError("condition not modelled: %r" % cond)


def _closed_paths():
    return {rel for rel, text in FILES.items() if "fabric:load_conditions" in text}


# Without it the recipe stays live (it makes 8 Beast Balls from 4 gold and 4 echo shards) or the override parses as a
# broken recipe: every closed file is only load conditions, and they never pass, so Fabric skips the file at load.
def test_the_closed_files_hold_only_a_condition_that_never_passes():
    assert _closed_paths() == {"data/cobblemon/recipe/beast_ball.json",
                               "data/cobblemon/advancement/recipes/balls/beast_ball.json"}
    for rel in _closed_paths():
        body = json.loads(FILES[rel])
        assert list(body) == ["fabric:load_conditions"], rel
        assert body["fabric:load_conditions"] and not all(_never(c) for c in body["fabric:load_conditions"]), rel


# Without it another recipe (a second jar, a nested jar) still crafts the key, or the override misses the jar's path:
# read from the snapshot jar, every recipe whose result is the key ball, and every advancement that rewards one, is
# closed at its own path.
@pytest.mark.skipif(not JAR.is_file(), reason="NOT_EXECUTED: no server snapshot jar at %s" % JAR)
def test_every_jar_recipe_for_the_key_ball_is_closed_at_its_own_path():
    want = set()
    with zipfile.ZipFile(JAR) as z:
        for n in z.namelist():
            if not (n.startswith("data/") and n.endswith(".json")):
                continue
            if re.fullmatch(r"data/[^/]+/recipe/.+\.json", n):
                r = json.loads(z.read(n).decode("utf-8-sig"))
                res = r.get("result")
                rid = res if isinstance(res, str) else (res.get("id") or res.get("item")) if isinstance(res, dict) \
                    else None
                if rid == KEY:
                    want.add(n)
                    ns, path = n[len("data/"):-len(".json")].split("/recipe/", 1)
                    rec = "%s:%s" % (ns, path)
                    for m in z.namelist():
                        if "/advancement/" in m and m.endswith(".json"):
                            adv = json.loads(z.read(m).decode("utf-8-sig"))
                            if rec in ((adv.get("rewards") or {}).get("recipes") or []):
                                want.add(m)
    assert want and want == _closed_paths(), (sorted(want), sorted(_closed_paths()))


# Without it a Beast Ball is lost on a wild blackout, which the owner exempted exactly as the Master Ball is: no claim
# category of data/blackout.json, and so no generated claim tag, holds it.
def test_the_blackout_never_takes_a_beast_ball():
    for cat in ("balls", "medicine", "consumables"):
        assert KEY not in BLACKOUT["claims"][cat], cat
        assert "cobblemon:master_ball" not in BLACKOUT["claims"][cat], cat
    bad = json.loads(json.dumps(BLACKOUT))
    bad["claims"]["balls"].append(KEY)
    assert any("never lost" in p for p in KB.problems(DOC, blackout=bad))


# Without it the key is not sold where the owner put it, or at another price: one line, at Cinderlee, $5,000 for one.
def test_cinderlee_sells_one_beast_ball_for_5000_and_the_ball_floor_holds():
    import bank
    markets = json.loads((ROOT / "data" / "markets.json").read_text(encoding="utf-8"))
    lines = [(c["id"], it) for c in markets["counters"] + list(markets.get("stalls") or []) for it in c["stock"]
             if it["item"] == KEY]
    assert [(cid, it["count"], it["price"]) for cid, it in lines] == [("cinderlee", 1, 5000)]
    floors, _missing = bank.exchange_floors(json.loads((ROOT / "data" / "bank.json").read_text(encoding="utf-8")),
                                            markets)
    master = [it["price"] / it["count"] for c in markets["counters"] for it in c["stock"]
              if it["item"] == "cobblemon:master_ball"]
    assert master and floors["ball"][0] < min(master), (floors["ball"], master)


# Without it a dungeon boss spawns untagged and any ball catches it: the Entei bind adds the shared tag, beside its
# own tags, in every slot; and a boss tool that stops adding it fails the check (the GENERATOR mutated, not the data).
def test_the_entei_bind_adds_the_shared_tag_and_a_dropped_tag_is_caught(monkeypatch):
    import entei_boss
    files = entei_boss.build(entei_boss.load())
    binds = {r: t for r, t in files.items() if r.endswith("/bind.mcfunction")}
    assert len(binds) == entei_boss.load()["pocket"]["slots"]
    for rel, text in binds.items():
        lines = text.split("\n")
        assert "tag @s add %s" % TAG in lines and "tag @s add cobblers.eb" in lines, rel
    assert KB.boss_problems(DOC) == []
    real = entei_boss.functions

    def untagged(*a, **kw):
        out = real(*a, **kw)
        return {k: [l for l in v if l != "tag @s add %s" % TAG] for k, v in out.items()}
    monkeypatch.setattr(entei_boss, "functions", untagged)
    bad = KB.boss_problems(DOC)
    assert len(bad) == len(binds) and all("does not run" in p for p in bad), bad


# Without it the key ball breaks the claim that waits (data/entei_boss.json catch.rule): the catch-mode Entei still
# binds in the same function that spawns it (so it is tagged before any ball can land), a fainted catch-mode run still
# says it will be waiting, and the catch is still granted by species in pokemon_captured, which a refused ball never
# reaches.
def test_the_waiting_claim_is_untouched():
    import entei_boss
    doc = entei_boss.load()
    files = entei_boss.build(doc)
    appear = files["data/cobblers/function/entei_boss/slot/s1/appear.mcfunction"].split("\n")
    spawn = [i for i, l in enumerate(appear) if "spawn_at" in l]
    bind = [i for i, l in enumerate(appear) if l.endswith("slot/s1/bind")]
    assert spawn and bind and max(spawn) < bind[0], appear
    assert "It will be waiting when you return." in doc["message"]["faint_catch"]
    settle = files["data/cobblers/function/entei_boss/slot/s1/settle.mcfunction"]
    assert "It will be waiting when you return." in settle
    cap = files["data/cobblemon/callbacks/pokemon_captured/cobblers_entei_boss.molang"]
    assert "q.pokemon.species.identifier" in cap and TAG not in cap


# Without it the pack loads globally (the live world would refuse its players' Master Balls) or prepare never builds
# it: tools/reapply.py lists it as a world-local, self-driving server pack with a prepare job.
def test_reapply_registers_the_pack_world_local_and_self_driving():
    import reapply
    assert "cobblers_key_ball" in reapply.SERVER_PACKS
    assert "cobblers_key_ball" in reapply.WORLD_LOCAL
    assert reapply.EXCLUDED["cobblers_key_ball"].startswith("self-driving")
    assert re.search(r'add\("key_ball", "key_ball\.py"\)', (ROOT / "tools" / "reapply.py").read_text(encoding="utf-8"))


# Without it a malformed record reaches the server: a multiplier that does not raise the rate, a refund of more than
# one, or a key ball whose own recipe stays open are each refused by the check.
def test_the_record_check_refuses_a_bad_record():
    assert KB.problems(DOC) == []
    assert KB.problems(dict(DOC, multiplier=1))
    assert KB.problems(dict(DOC, refund=dict(DOC["refund"], ball_count=2)))
    assert KB.problems(dict(DOC, recipe_off=dict(DOC["recipe_off"], recipes=[])))
    assert KB.problems(dict(DOC, tag="has space"))
