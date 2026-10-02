"""tools/ursaluna_cave_audit.py against tools/ursaluna_cave.py: the clean pack passes, and a broken GENERATOR fails.

Written by the session that wrote the generator and the audit (the brief asked one agent for both), so the
independent half of the proof is the mutation standard of CLAUDE.md, "How to prove an audit is independent": every
tamper case below changes the generator's CODE or OUTPUT and leaves data/ursaluna_cave.json alone. A record-side
mutation moves the expectation and the output together and proves nothing.

Needs the canonical heightmap (COBBLERS_SOURCE_ROOT); a skip names it. NOT covered, and it needs a running server
(experiments/EXP-049-ursaluna-wake): that the fills land, that the bear is twice normal size, that it sleeps, that the
wake fires and a battle can then start, that the callbacks fire for this bear, that a ball breaks free, and that
Teddiursa spawn round the activated block.

Since 2026-10-02 the den has no barrier and the bear wakes as a boss (the owner: "Wake it as a boss fight"); the old
"a missing curtain exposes the bear" proof is inverted into "a barrier put back is refused", and the wake has its own
generator mutations. The same day the owner set the boss rules ("returns after it is beaten, no badge to wake it,
catchable only late"): the return and the catch gate are RUN here, on tests/gulch_sim.py's command model (vanilla
1.21.1 semantics, written by the gulch's test author, not from tools/ursaluna_cave.py), extended below only with what
Cobblemon adds that this pack reads: `nbt=` selectors by partial NBT match, and a spawned Pokemon's species, level and
NoAI. The callbacks run on tests/nbt_sim.py's MoLang interpreter. Each behaviour also has a generator mutation that the
run catches, so a run that sees nothing cannot pass.
"""
import functools
import json
import os
import re
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tests"))

import ursaluna_cave as U  # noqa: E402
import ursaluna_cave_audit as A  # noqa: E402
import gulch_sim as GS  # noqa: E402
import nbt_sim as N  # noqa: E402

REC = json.loads((ROOT / "data" / "ursaluna_cave.json").read_text(encoding="utf-8"))
TAG = REC["ursaluna"]["tag"]
OBJ = "cobblers.ursaluna"
FREE = "cobblers.ursaluna_free"
LATE = ["cobblers:flag/%s" % f for f in REC["ursaluna"]["catch"]["gate_flags"]]
COOL = REC["ursaluna"]["returns"]["cooldown_ticks"]
CLEAR = REC["ursaluna"]["returns"]["clear_radius"]
PASS = REC["ursaluna"]["keeper"]["period_ticks"]


def _ground():
    import ground as G
    import terrain as T
    try:
        return G.Ground(os.environ.get("COBBLERS_SOURCE_ROOT"))
    except T.TerrainUnavailable as e:
        pytest.skip("the canonical heightmap is unusable: %s" % e)


@pytest.fixture(scope="module")
def ground():
    return _ground()


def run(ground, out):
    doc = U.load()
    for rel, text in U.files(doc, ground).items():
        f = out / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(text, encoding="utf-8", newline="\n")
    return A.audit(REC, ground, out, U.placement_steps(doc, ground))


def checks(rep):
    return sorted({e.split(":", 1)[0] for e in rep.errors})


def test_the_committed_cave_is_clean(ground, tmp_path):
    rep = run(ground, tmp_path)
    assert rep.errors == []


def test_a_thinner_shell_breaks_the_seal(ground, tmp_path, monkeypatch):
    real = U._dilate
    monkeypatch.setattr(U, "_dilate", lambda mask, m: real(mask, m - 1))
    assert "seal" in checks(run(ground, tmp_path))


def test_a_taller_hall_is_not_the_planned_void(ground, tmp_path, monkeypatch):
    real = U.Model.__init__

    def taller(self, doc, g):
        real(self, doc, g)
        self.void = self.void | np.roll(self.void, 1, axis=0)

    monkeypatch.setattr(U.Model, "__init__", taller)
    assert "void" in checks(run(ground, tmp_path))


def test_a_barrier_put_back_is_refused(ground, tmp_path, monkeypatch):
    real = U.carve_lines

    def walled(doc, M):
        # the old curtain, re-derived in the generator's own frame: a 2-thick band across the hall at s 63-64
        band = M.void & (M.S[None] >= 63 - U.EPS) & (M.S[None] < 65 - U.EPS)
        return real(doc, M) + [U._fill(r, "minecraft:barrier", " replace minecraft:air") for r in M.runs(band)]

    monkeypatch.setattr(U, "carve_lines", walled)
    assert "barrier" in checks(run(ground, tmp_path))


def test_a_wake_that_reaches_the_passage_is_refused(ground, tmp_path, monkeypatch):
    real = U.wake_selector
    r = REC["ursaluna"]["wake"]["radius"]
    monkeypatch.setattr(U, "wake_selector", lambda doc: real(doc).replace("distance=..%d," % r, "distance=..40,"))
    assert "wake" in checks(run(ground, tmp_path))


def _patch_output(monkeypatch, name, old, new):
    """The generator's output for one function, with `old` replaced: a mutation of the generator, not the record."""
    real = U.files

    def patched(doc, g):
        out = real(doc, g)
        k = name if name.startswith("data/") else "data/cobblers/function/ursaluna_cave/%s.mcfunction" % name
        assert old in out[k], (k, old)
        out[k] = out[k].replace(old, new)
        return out

    monkeypatch.setattr(U, "files", patched)


def test_a_wake_that_leaves_the_bear_unbattleable_is_refused(ground, tmp_path, monkeypatch):
    _patch_output(monkeypatch, "wake", "Unbattleable:0b,", "")
    assert "wake" in checks(run(ground, tmp_path))


def test_a_keeper_that_does_not_stand_down_is_refused(ground, tmp_path, monkeypatch):
    real = U.awake_if
    monkeypatch.setattr(U, "awake_if", lambda doc, v: real(doc, 2) if v == 1 else real(doc, v))
    assert "wake" in checks(run(ground, tmp_path))


def test_a_dress_that_keeps_the_bear_awake_is_refused(ground, tmp_path, monkeypatch):
    real = U.awake_set
    monkeypatch.setattr(U, "awake_set", lambda doc, v: real(doc, 1))
    assert "wake" in checks(run(ground, tmp_path))


@pytest.mark.parametrize("mutate", [
    lambda d: d["cave"]["blocks"].__setitem__("curtain", "minecraft:barrier"),
    lambda d: d["ursaluna"]["wake"]["awake_nbt"].__setitem__("Unbattleable", "1b"),
    lambda d: d["ursaluna"]["wake"]["awake_nbt"].__setitem__("PoseType", '"STAND"'),
    lambda d: d["ursaluna"]["wake"].__setitem__("radius", 48),
    lambda d: d["ursaluna"].__setitem__("encounter", "resident"),
    lambda d: d["ursaluna"]["returns"].__setitem__("cooldown_ticks", 6000),
    lambda d: d["ursaluna"]["returns"].__setitem__("clear_radius", 20),
    lambda d: d["ursaluna"]["returns"].__setitem__("absent_passes", 1),
    lambda d: d["ursaluna"]["catch"].__setitem__("gate_flags", []),
    lambda d: d["ursaluna"]["catch"].__setitem__("gate_flags", ["gym6_beaten"]),
], ids=["curtain", "unbattleable", "posetype", "radius-past-keeper", "resident", "farmable-cooldown",
        "returns-in-the-wake", "one-absent-pass", "no-catch-gate", "unknown-flag"])
def test_the_generator_refuses_a_record_that_is_not_the_boss(mutate, tmp_path):
    """The generator's own guard, not the audit's: a record that puts a wall back, wakes a bear that cannot fight,
    returns it as a farm or in a player's face, or lets anyone catch it."""
    import copy
    d = copy.deepcopy(U.load())
    mutate(d)
    p = tmp_path / "rec.json"
    p.write_text(json.dumps(d), encoding="utf-8")
    with pytest.raises(U.CaveError):
        U.load(p)


def test_the_teddiursa_block_is_activated_and_audited(ground, tmp_path, monkeypatch):
    blk = next(b for b in json.loads((ROOT / "data" / "habitat_blocks.json").read_text(encoding="utf-8"))["blocks"]
               if b["id"] == REC["teddiursa"]["block"])
    assert blk["style"] == "activated" and blk["replace_spawns"] is False
    assert blk["activated"]["max_spawns"] == REC["teddiursa"]["group"]
    import habitat_blocks as HB
    cmds = HB.commands(blk)
    assert cmds[0].startswith("setblock 1514 158 1424 %s" % blk["mimic"])
    assert "SpawningStyle:\"cobblemon:activated\"" in cmds[1] and "MaxSpawns:%d" % REC["teddiursa"]["group"] in cmds[1]


def test_a_bare_distance_guard_is_refused(ground, tmp_path, monkeypatch):
    real = U.summon_command
    monkeypatch.setattr(U, "summon_command", lambda doc, g, M=None: real(doc, g, M).replace(
        "unless entity @e[tag=%s] " % TAG, "").replace("," + U._species_sel(doc), ""))
    assert "summon" in checks(run(ground, tmp_path))


def test_a_floor_over_air_is_caught(ground, tmp_path, monkeypatch):
    real = U.Model.__init__

    def everywhere(self, doc, g):
        real(self, doc, g)
        self.hall_cols = self.void.any(axis=0) & ~self.den_cols

    monkeypatch.setattr(U.Model, "__init__", everywhere)
    assert "floor" in checks(run(ground, tmp_path))


# ------------------------------------------------------------------ the boss rules: generator mutations the audit sees

SEL = U._species_sel(REC)


@pytest.mark.parametrize("name,old,new,check", [
    # a restart that resets the clock brings a beaten bear back at once
    ("load", "execute unless score #gone %s matches -2147483648.. run scoreboard players set #gone %s -1" % (OBJ, OBJ),
     "scoreboard players set #gone %s -1" % OBJ, "return"),
    # no cooldown: a farm
    ("track", "execute if score #d %s < #cool %s run return 0\n" % (OBJ, OBJ), "", "return"),
    # it returns in a player's face
    ("track", "if entity @a[distance=..%d] run return 0" % CLEAR, "if entity @a[distance=..8] run return 0", "return"),
    # one absent pass: a bear not yet loaded counts as gone
    ("track", "matches ..1 run return 0", "matches ..0 run return 0", "return"),
    # a callback that moves a started clock
    ("gone", "execute unless score #gone %s matches -1 run return 0\n" % OBJ, "", "return"),
    # R14C's failure: a guard on distance alone
    ("respawn", "tag=!%s,distance=..4,%s" % (TAG, SEL), "distance=..4", "return"),
    # a plain spawn line: parsed at start, it spawns nothing until a /reload
    ("spawn_at", "$spawnpokemonat $(x) $(y) $(z) ", "spawnpokemonat 1 2 3 ", "return"),
    # the catch gate on the wrong badge
    ("catch_check", "gym6_cleared", "gym1_cleared", "catch"),
    # a sleeping bear a ball can take
    ("catch_check", "execute unless score #awake %s matches 1 run tag @s add %s\n" % (OBJ, FREE), "", "catch"),
    # every wild Pokemon's faint counted, tame or not
    (U.CALLBACKS % "battle_fainted", "c.pokemon.actor.is_wild ? {", "1 ? {", "callbacks"),
    # the shakes never cut
    (U.CALLBACKS % "poke_ball_capture_calculated", "q.set_shakes(0);", "q.set_critical_capture(0);", "callbacks"),
], ids=["load-resets-clock", "no-cooldown", "returns-in-a-face", "one-absent-pass", "callback-moves-clock",
        "distance-guard", "plain-spawn", "wrong-badge", "sleeping-catchable", "tame-faints", "shakes-uncut"])
def test_a_generator_that_breaks_a_boss_rule_is_refused(ground, tmp_path, monkeypatch, name, old, new, check):
    _patch_output(monkeypatch, name, old, new)
    assert check in checks(run(ground, tmp_path))


def test_a_generator_that_raises_the_fight_past_the_band_is_refused(ground, tmp_path, monkeypatch):
    """The fight's level is checked against the sub-region's band from data/spawns.json, not against the record."""
    real = U.files

    def stronger(doc, g):
        import copy
        d = copy.deepcopy(doc)
        d["ursaluna"]["level"] = 41
        return real(d, g)

    monkeypatch.setattr(U, "files", stronger)
    rep = run(ground, tmp_path)
    assert {"catch", "return"} <= set(checks(rep))


# ------------------------------------------------------------------ the boss rules, run

class Den(GS.World):
    """tests/gulch_sim.py's world, plus what Cobblemon adds that the den's pack reads: an `nbt=` selector filter
    (NbtUtils.compareNbt, partial, applied before limit and sort as vanilla's EntitySelector does), and a spawned
    Pokemon's Pokemon.Species and Pokemon.Level, with NoAI 1b on the entity when `no_ai` is given (the jar's
    NoAIProperty sets the entity's NoAI and nothing on the Pokemon). Messages and sounds are logged."""

    def command(self, cmd):
        t = cmd.split(" ")
        if t[0] in ("tellraw", "playsound"):
            self.log.append(cmd)
            return None
        r = super().command(cmd)
        if t[0] == "spawnpokemonat":
            e = self.entities[-1]
            props = t[5:]
            e["nbt"]["Pokemon"]["Species"] = "cobblemon:%s" % t[4]
            e["nbt"]["Pokemon"]["Level"] = int(next(p for p in props if p.startswith("level="))[len("level="):])
            if "no_ai" in props:
                e["nbt"]["NoAI"] = N.Byte(1)
        return r

    def select(self, sel, origin=None):
        m = re.fullmatch(r"(@[aes])\[(.*)\]", sel)
        if not m or "nbt=" not in m.group(2):
            return super().select(sel, origin)
        f = GS.split_filters(m.group(2))
        pats = [N.parse_snbt(v) for k, v in f if k == "nbt"]
        rest = ",".join("=".join(kv) for kv in f if kv[0] not in ("nbt", "limit", "sort"))
        out = [e for e in super().select("%s[%s]" % (m.group(1), rest), origin)
               if all(N.matches(p, e.get("nbt", {})) for p in pats)]
        o = origin or self.pos
        sort = [v for k, v in f if k == "sort"]
        if sort:
            out.sort(key=lambda e: GS.math.dist(e["pos"], o), reverse=sort[0] == "furthest")
        lim = [int(v) for k, v in f if k == "limit"]
        return out[:lim[0]] if lim else out


@functools.lru_cache(maxsize=None)
def _generated():
    g = _ground()
    return U.files(U.load(), g), A.Plan(REC, g).bear()


def den_fns(patch=None):
    """The generated pack's functions by name; `patch` (name, old, new) mutates the generator's output."""
    files, _bear = _generated()
    fns = {rel[len("data/cobblers/function/"):-len(".mcfunction")]: text.splitlines()
           for rel, text in files.items() if rel.endswith(".mcfunction")}
    if patch:
        name, old, new = patch
        name = "ursaluna_cave/" + name
        text = "\n".join(fns[name])
        assert old in text, (name, old)
        fns[name] = text.replace(old, new).splitlines()
    return fns


def molang(event):
    return _generated()[0][U.CALLBACKS % event]


def spot():
    """The bear's spot, from the audit's own plan (its frame, not the generator's): (block, centre)."""
    bx, by, bz = _generated()[1]
    return (bx, by, bz), (bx + 0.5, float(by), bz + 0.5)


def den(fns=None, gt=5_000_000):
    w = Den(fns or den_fns())
    w.gt = gt
    w.call("ursaluna_cave/load")
    return w


def install(w):
    """What R18U does over RCON: a summon at the spot, then dress_new (the console is no function: it spawns)."""
    (bx, by, bz), _c = spot()
    w.command("spawnpokemonat %d %d %d %s level=%d scale_modifier=%s %s" % (
        bx, by, bz, REC["ursaluna"]["species"], REC["ursaluna"]["level"], REC["ursaluna"]["scale_modifier"],
        " ".join(REC["ursaluna"]["spawn_properties"])))
    w.call("ursaluna_cave/dress_new")
    return bears(w)[0]


def bears(w):
    return [e for e in w.entities if TAG in e["tags"]]


def score(w, h):
    return w.score.get((h, OBJ))


def passes(w, n):
    out = []
    for _ in range(n):
        w.gt += PASS
        w.call("ursaluna_cave/keeper")
        out.append(len(bears(w)))
    return out


def near(w):
    _b, (cx, cy, cz) = spot()
    return w.player((cx + 10, cy, cz + 10), flags=())


def away(w, p):
    _b, (cx, cy, cz) = spot()
    p["pos"] = (cx + CLEAR + 40, cy, cz)


def beaten(w, bear):
    """A battle won against it: Cobblemon's battle_fainted callback for a wild Pokemon, then the entity goes."""
    pid = GS.uuid_text(bear["nbt"]["Pokemon"]["UUID"])
    for c in N.Molang(molang("battle_fainted")).run({"pokemon": {"actor": {"is_wild": 1.0}, "pokemon": {"id": pid}}}, {}):
        w.command(c)
    w.entities.remove(bear)


def caught(w, bear):
    pid = GS.uuid_text(bear["nbt"]["Pokemon"]["UUID"])
    w.entities.remove(bear)                     # gone before pokemon_captured runs (tools/blackout_pack.py)
    for c in N.Molang(molang("pokemon_captured")).run({}, {"pokemon": {"id": pid}}):
        w.command(c)


def wake(w, p):
    _b, (cx, cy, cz) = spot()
    p["pos"] = (cx + 3, cy, cz + 3)
    passes(w, 1)
    assert score(w, "#awake") == 1


def asleep_at_home(w, bear):
    _b, c = spot()
    n = bear["nbt"]
    assert TAG in bear["tags"] and bear["pos"] == c, (bear["tags"], bear["pos"], c)
    assert n["Unbattleable"] == N.Byte(1) and n["NoAI"] == N.Byte(1) and n["PoseType"] == "SLEEP", n
    assert n["Pokemon"]["Level"] == REC["ursaluna"]["level"] and n["Pokemon"]["Species"] == "cobblemon:ursaluna"
    assert score(w, "#awake") == 0 and score(w, "#gone") == -1
    assert w.sget("cobblers:ursaluna", "bear.pid") == [GS.uuid_text(n["Pokemon"]["UUID"])]


def _until_due(w, t_gone):
    """Passes until one before the clock is due; the counts of bears seen."""
    seen = []
    while w.gt + PASS - t_gone < COOL:
        seen += passes(w, 1)
    return seen


@pytest.mark.parametrize("how,why", [("beaten", 1), ("caught", 2)])
def test_a_beaten_or_caught_bear_returns_asleep_at_home_after_the_cooldown_and_not_before(how, why):
    w = den()
    bear = install(w)
    asleep_at_home(w, bear)
    p = near(w)
    wake(w, p)
    (beaten if how == "beaten" else caught)(w, bear)
    t_gone = w.gt
    assert (score(w, "#gone"), score(w, "#why")) == (t_gone, why)
    away(w, p)
    assert not any(_until_due(w, t_gone)), "it came back before its cooldown"
    seen = passes(w, 2)
    assert seen[-1] == 1, seen
    (new,) = bears(w)
    assert new is not bear
    asleep_at_home(w, new)


def test_a_player_who_stays_in_the_den_never_sees_it_return():
    w = den()
    bear = install(w)
    p = near(w)
    wake(w, p)
    beaten(w, bear)
    assert not any(passes(w, COOL // PASS + 50)), "it returned with a player within %d" % CLEAR
    away(w, p)
    assert passes(w, 2)[-1] == 1


def test_a_bear_killed_outside_a_battle_returns_too_after_two_loaded_passes():
    w = den()
    bear = install(w)
    w.entities.remove(bear)                     # a sword: no callback
    passes(w, 1)
    assert score(w, "#gone") == -1, "one absent pass counted (entities load a moment after their chunk)"
    passes(w, 1)
    assert score(w, "#why") == 3 and score(w, "#gone") == w.gt
    t_gone = w.gt
    assert not any(_until_due(w, t_gone))
    assert passes(w, 2)[-1] == 1


def test_a_bear_that_is_only_unloaded_or_late_to_load_never_starts_the_clock():
    w = den()
    bear = install(w)
    w.entities.remove(bear)
    w.loaded = lambda x, y, z: False            # the den's chunk unloaded: the bear goes with it
    passes(w, 500)
    w.loaded = lambda x, y, z: True
    passes(w, 1)                                # loaded, the entity not yet in (the load race)
    w.entities.append(bear)
    passes(w, 3)
    assert score(w, "#gone") == -1 and bears(w) == [bear]
    # alternating: absent on one loaded pass, unloaded on the next, never two loaded in a row
    for _ in range(50):
        w.entities.remove(bear)
        passes(w, 1)
        w.loaded = lambda x, y, z: False
        passes(w, 1)
        w.loaded = lambda x, y, z: True
        w.entities.append(bear)
    assert score(w, "#gone") == -1


def test_a_bear_moved_off_its_spot_is_not_gone_and_is_put_back():
    w = den()
    bear = install(w)
    _b, (cx, cy, cz) = spot()
    bear["pos"] = (cx + 30, cy, cz)
    near(w)
    passes(w, 1)
    assert score(w, "#gone") == -1 and bear["pos"] == (cx, cy, cz)


def test_another_wild_pokemon_fainting_or_caught_changes_nothing():
    w = den()
    bear = install(w)
    other = w.pokemon((0.5, 64, 0.5), species="teddiursa")
    beaten(w, other)
    caught(w, w.pokemon((0.5, 64, 0.5), species="teddiursa"))
    assert score(w, "#gone") == -1 and bears(w) == [bear]


def test_a_restart_or_a_walk_in_and_out_never_brings_it_back_early():
    """Contract C14's shape: no repeatable player action moves the return clock."""
    w = den()
    bear = install(w)
    p = near(w)
    wake(w, p)
    beaten(w, bear)
    t_gone = w.gt
    _b, c = spot()
    i = 0
    while w.gt + 2 * PASS - t_gone < COOL:
        w.call("ursaluna_cave/load")
        p["pos"] = c if i % 2 else (c[0] + CLEAR + 40, c[1], c[2])
        assert not any(passes(w, 1)), "back early at %d of %d" % (w.gt - t_gone, COOL)
        i += 1
    assert score(w, "#gone") == t_gone


def test_a_fight_fled_lays_the_bear_down_again_once_left_alone():
    w = den()
    bear = install(w)
    p = near(w)
    wake(w, p)
    assert bear["nbt"]["Unbattleable"] == N.Byte(0)
    passes(w, 3)
    assert score(w, "#awake") == 1, "laid down with a player in the den"
    away(w, p)
    passes(w, 1)
    asleep_at_home(w, bear)


def test_the_stored_uuid_is_the_text_molang_gives_for_negative_and_positive_words():
    """recovery/pid's method, here as ursaluna_cave/pid, against Python's own UUID formatting (gulch_sim.uuid_text)."""
    w = den()
    seen = set()
    for _ in range(12):
        bear = install(w)
        seen |= {v < 0 for v in bear["nbt"]["Pokemon"]["UUID"]}
        assert w.sget("cobblers:ursaluna", "bear.pid") == [GS.uuid_text(bear["nbt"]["Pokemon"]["UUID"])]
        w.entities.remove(bear)
    assert seen == {True, False}


# ---- the catch gate: the capture callback with the entity methods it calls, and its command run synchronously

class Ball(N.Molang):
    def __init__(self, world):
        super().__init__(molang("poke_ball_capture_calculated"))
        self.world, self.shakes = world, None

    def ev(self, e):
        if e[0] == "call":
            name, args = e[1], [self.ev(a) for a in e[2]]
            if name == "q.run_command":
                self.commands.append(args[0])
                self.world.command(args[0])
                return 1.0
            if name == "q.set_shakes":
                self.shakes = int(self.num(args[0]))
                return 1.0
            obj, _, method = name.rpartition(".")
            if method in ("has_tag", "remove_tag"):
                ent = self.lookup(obj)["_entity"]
                if method == "remove_tag":
                    ent["tags"].discard(args[0])
                    return 1.0
                return 1.0 if args[0] in ent["tags"] else 0.0
        return super().ev(e)


def throw(w, thrower, target):
    b = Ball(w)
    b.run({}, {"thrower": {"is_player": 1.0, "uuid": GS.uuid_text(thrower["nbt"]["UUID"]), "_entity": thrower},
               "pokemon": {"_entity": target}})
    return b


@pytest.mark.parametrize("late,awake,holds", [(False, True, False), (True, True, True), (False, False, False),
                                              (True, False, False)])
def test_only_a_late_thrower_holds_the_awake_bear_and_nobody_the_sleeping_one(late, awake, holds):
    w = den()
    bear = install(w)
    p = w.player(spot()[1], flags=LATE if late else ())
    if awake:
        wake(w, p)
    b = throw(w, p, bear)
    assert (b.shakes != 0) is holds, (b.shakes, b.commands)
    assert FREE not in p["tags"]
    assert score(w, "#awake") == 1, "a ball at the sleeping bear did not wake it"
    assert bear["nbt"]["Unbattleable"] == N.Byte(0)
    said = [l for l in w.log if l.startswith("tellraw @s ") and REC["ursaluna"]["catch"]["message"] in l]
    assert bool(said) is (not late)


def test_a_stale_answer_on_a_late_thrower_does_not_refuse_them():
    w = den()
    bear = install(w)
    p = w.player(spot()[1], flags=LATE, tags=(FREE,))
    wake(w, p)
    assert throw(w, p, bear).shakes is None


def test_a_ball_at_any_other_pokemon_is_left_alone():
    w = den()
    install(w)
    p = w.player(spot()[1])
    b = throw(w, p, w.pokemon((0.5, 64, 0.5), species="teddiursa"))
    assert b.shakes is None and b.commands == []


# ---- each run above sees the fault it exists for: the same runs on a generator broken in that one place fail

@pytest.mark.parametrize("patch,test", [
    (("track", "execute if score #d %s < #cool %s run return 0" % (OBJ, OBJ), ""),
     lambda: test_a_beaten_or_caught_bear_returns_asleep_at_home_after_the_cooldown_and_not_before("beaten", 1)),
    (("track", "if entity @a[distance=..%d] run return 0" % CLEAR, "if entity @a[distance=..1] run return 0"),
     test_a_player_who_stays_in_the_den_never_sees_it_return),
    (("track", "matches ..1 run return 0", "matches ..0 run return 0"),
     test_a_bear_that_is_only_unloaded_or_late_to_load_never_starts_the_clock),
    (("load", "execute unless score #gone %s matches -2147483648.. run " % OBJ, ""),
     test_a_restart_or_a_walk_in_and_out_never_brings_it_back_early),
    (("catch_check", "gym6_cleared", "gym1_cleared"),
     lambda: test_only_a_late_thrower_holds_the_awake_bear_and_nobody_the_sleeping_one(True, True, True)),
    (("pid", "#u1 ", "#u2 "), test_the_stored_uuid_is_the_text_molang_gives_for_negative_and_positive_words),
], ids=["no-cooldown", "returns-in-a-face", "one-absent-pass", "load-resets", "wrong-badge", "pid-word-swapped"])
def test_each_run_fails_on_a_generator_broken_where_it_looks(monkeypatch, patch, test):
    real = den_fns
    monkeypatch.setattr(sys.modules[__name__], "den_fns", lambda patch_=None, _p=patch: real(_p))
    with pytest.raises(AssertionError) as e:
        test()
    # failed by its own check, not because the model met something it does not know
    assert not any(k in str(e.value) for k in ("does not know", "simulator", "unmodelled", "macro ")), str(e.value)


# ---- contract C14 (tests/test_gate_clocks.py): the return clock with the actions a player can repeat

def den_restart(fns=None):
    w = den(fns)
    bear = install(w)
    beaten(w, bear)
    t_gone = w.gt
    while w.gt + 2 * PASS - t_gone < COOL:
        w.call("ursaluna_cave/load")
        assert not any(passes(w, 1)), "a restart brought the bear back at %d of %d" % (w.gt - t_gone, COOL)


def den_reapproach(fns=None):
    w = den(fns)
    bear = install(w)
    p = near(w)
    beaten(w, bear)
    t_gone = w.gt
    _b, c = spot()
    i = 0
    while w.gt + 2 * PASS - t_gone < COOL:
        p["pos"] = c if i % 2 else (c[0] + CLEAR + 40, c[1], c[2])
        assert not any(passes(w, 1)), "walking in and out brought the bear back at %d of %d" % (w.gt - t_gone, COOL)
        i += 1
