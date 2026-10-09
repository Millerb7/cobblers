"""The dungeon engine core (tools/dungeon.py, data/dungeons.json): the BUILDER's own tests.

Two kinds. Static checks read the generated pack's text. Simulated runs drive the generated functions on
tests/pocket_sim.py (written by the test author for the Entei audit, from vanilla semantics), extended here only with
the commands this pack uses that the Entei pack did not (bossbar, title, gamemode, clear, give, runmolang, spawnnpcat,
tag remove, `scores=` selectors, `if items`, a condition with no `run`). Battles are not modelled: a test says who is
in battle and drives the victory callback. The independent audit is another agent's; these prove the builder's intent,
not independence.
"""
from __future__ import annotations

import copy
import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tests"))

import dungeon as D  # noqa: E402
import pocket_sim as PS  # noqa: E402

DOC = D.load()
BLACKOUT = json.loads((ROOT / "data" / "blackout.json").read_text(encoding="utf-8"))
EX = BLACKOUT["dungeon_exempt"]
RUN_TAG = EX["player_tag"]
TAIL_END, BACKSTOP = EX["tail_end_function"], EX["backstop_function"]
EXEMPT = BLACKOUT["claims"]["exempt_tag"]
FILES = D.build(DOC)
FNS = {p[len("data/cobblers/function/dungeons/"):-len(".mcfunction")]: t.splitlines()
       for p, t in FILES.items() if p.endswith(".mcfunction")}
POCKET = DOC["engine"]["pocket"]["dimension"]
OW = "minecraft:overworld"


def body(name):
    return [l for l in FNS[name] if l.strip() and not l.startswith("#")]


# ------------------------------------------------------------------------------------------------- static


def test_the_record_has_no_problems_and_the_pack_builds():
    assert D.problems(DOC) == []
    assert any(p.endswith("dungeons/keeper.mcfunction") for p in FILES)


def test_every_npc_spawn_is_a_macro_line_and_every_spawner_binds_with_the_exempt_tag():
    spawn_lines = [(n, l) for n, ls in FNS.items() for l in ls if "spawnnpcat" in l and not l.startswith("#")]
    assert spawn_lines and all(l.startswith("$") for _n, l in spawn_lines), spawn_lines
    callers = [n for n in FNS if any("dungeons/npc_at" in l for l in body(n))]
    assert callers
    for n in callers:
        binds = [l for l in body(n) if re.search(r"run function cobblers:dungeons/slot/s\d+/bind_boss$", l)]
        assert binds, n
        bind = re.search(r"(slot/s\d+/bind)_boss$", binds[0]).group(1)
        assert "tag @s add %s" % EXEMPT in body(bind)
    # the keeper's backstop binds any untagged NPC in a slot a pass later
    for s in D.slots(DOC):
        assert any("tag=!dg.npc" in l and "slot/s%d/bind" % s["g"] in l for l in body("slot/s%d/tend" % s["g"]))


def test_the_run_tag_is_added_where_the_slot_is_reserved_before_the_arrival_and_cancels_a_tail():
    for d in DOC["dungeons"]:
        go = body("door/go_%s" % d["short"])
        add = go.index("tag @s add %s" % RUN_TAG)
        reserve = [i for i, l in enumerate(go) if "/reserve" in l]
        assert reserve and max(reserve) < add
        assert go[add + 1] == "scoreboard players set @s dg.tail 0"
    # the arrival never touches the tag; it only teleports later
    for s in D.slots(DOC):
        assert not any(RUN_TAG in l for l in body("slot/s%d/arrive" % s["g"]))


def test_no_engine_function_removes_the_run_tag():
    bad = [(n, l) for n, ls in FNS.items() for l in ls if re.search(r"\btag \S+ remove %s\b" % re.escape(RUN_TAG), l)]
    assert bad == []


def test_the_tail_end_and_the_backstop_run_only_outside_the_pocket():
    tail = body("m/tail")
    i = tail.index("execute at @s run function %s" % TAIL_END)
    assert "execute if entity @s[tag=dg.pk] run return 0" in tail[:i]
    stale = [l for l in body("keeper") if BACKSTOP in l]
    assert len(stale) == 1 and "tag=!dg.pk" in stale[0] and "tag=%s" % RUN_TAG in stale[0]
    callers = {n for n in FNS for l in body(n) if TAIL_END in l or BACKSTOP in l}
    assert callers == {"m/tail", "keeper"}


def test_every_way_out_starts_a_tail_of_at_least_the_credit_window():
    end = body("m/end")
    starts = [int(l.split()[-1]) for l in end if l.startswith("scoreboard players set @s dg.tail ")]
    # counted down period_ticks a pass from the next pass, so at least tail_ticks elapse
    assert starts and starts[0] - DOC["engine"]["keeper"]["period_ticks"] >= EX["tail_ticks"]
    for way in ("back", "far", "m/died", "m/left", "m/void"):
        assert "function cobblers:dungeons/m/end" in body(way), way


def test_survival_is_restored_and_the_pick_taken_by_its_component_on_every_way_out():
    pick = D.pick_match(DOC)
    assert "custom_data~{cobblers_dg_pick:1b}" in pick
    for n in ("m/end", "m/restore") + tuple("check_%s" % d["short"] for d in DOC["dungeons"]):
        b = body(n)
        assert any("gamemode survival @s" in l for l in b), n
        assert "clear @s %s" % pick in b, n


def test_the_timer_kill_is_kill_and_waits_for_the_clawback():
    t = body("m/timeout")
    assert t[-1] == "kill @s"
    assert "execute if score @s dg.claw matches 1.. run return 0" in t
    assert not any("outside_border" in l for ls in FNS.values() for l in ls)


def test_lockout_binds_and_counts_on_uptime_never_gametime():
    assert DOC["engine"]["lockout_ticks"] >= max(b["clock_s"] for b in DOC["engine"]["bands"]) * 20
    assert not any("time query gametime" in l for ls in FNS.values() for l in ls)


def test_sigils_are_matched_given_and_crafted_in_one_byte_form():
    for x in D.sigils(DOC):
        r = json.loads(FILES["data/cobblers/recipe/dg_sigil_b%d.json" % x["band"]])
        assert r["result"]["components"]["minecraft:custom_data"] == {"cobblers_dg_sigil": x["band"]}
        assert sum(1 for _ in r["ingredients"]) == sum(n for _i, n in x["recipe"])
        assert "{cobblers_dg_sigil:%db}" % x["band"] in D.sigil_match(x, DOC)
        assert "custom_data={cobblers_dg_sigil:%db}" % x["band"] in D.sigil_components_snbt(x, DOC)
    assert len(D.sigils(DOC)) == 6


def test_the_open_owner_decisions_are_data_switches_and_staging_values():
    sg = DOC["engine"]["sigils"]
    assert sg["free_first_entry"]["owner_decision"] == "Q20 OPEN" and sg["free_first_entry"]["dungeons"] == []
    assert sg["recipe_gate"]["owner_decision"] == "Q23 OPEN" and sg["recipe_gate"]["mode"] == "band"
    assert "STAGING VALUE" in sg["free_first_entry"]["staging_value"] and "STAGING VALUE" in sg["recipe_gate"]["staging_value"]
    assert not any("/free/" in p for p in FILES)
    assert any("recipe take" in l for l in body("recipes/one"))
    doc = copy.deepcopy(DOC)
    doc["engine"]["sigils"]["free_first_entry"]["dungeons"] = ["night_shift"]
    doc["engine"]["sigils"]["recipe_gate"]["mode"] = "all"
    files = D.build(doc)
    assert "data/cobblers/advancement/dungeons/free/ns.json" in files
    one = files["data/cobblers/function/dungeons/recipes/one.mcfunction"]
    assert "recipe take" not in one and one.count("recipe give") == 6


def test_slots_stay_out_of_every_other_pocket_user_and_the_record_refuses_an_overlap():
    for s in D.slots(DOC):
        assert s["z0"] >= 1024
    doc = copy.deepcopy(DOC)
    doc["engine"]["slots"]["rows_from_z"] = -700
    assert any("probe pack" in p or "rescue" in p for p in D.problems(doc))
    doc = copy.deepcopy(DOC)
    doc["engine"]["lockout_ticks"] = 1000
    assert any("lockout" in p for p in D.problems(doc))


def test_the_reapply_steps_count_the_entities_they_summon():
    steps = D.reapply_steps(DOC)
    assert [s[0] for s in steps] == ["R16DG", "R16DR"]
    assert [v for k, v in steps[0][2] if k == "fn"][0] == "cobblers:dungeons/place"
    assert [v for k, v in steps[1][2] if k == "fn"][0] == "cobblers:dungeons/rips/place"
    check = [v for k, v in steps[0][2] if k == "check"][0]
    assert check[2] == 3 * len(D.slots(DOC))
    check = [v for k, v in steps[1][2] if k == "check"][0]
    assert check[2] == len(DOC["dungeons"])


def test_reapply_installs_the_pack_world_local_prepares_it_and_runs_its_steps_after_r16q():
    src = (ROOT / "tools" / "reapply.py").read_text(encoding="utf-8")
    import reapply as R
    assert "cobblers_dungeons" in R.SERVER_PACKS and "cobblers_dungeons" in R.WORLD_LOCAL
    assert 'add("dungeons", "dungeon.py")' in src
    assert src.index('out.append(("R16Q"') < src.index("out.extend(DG.reapply_steps())") < src.index('out.append(("R15"')


def test_shell_writes_stay_inside_the_fill_and_forceload_limits():
    import function_limits as FL
    for s in D.slots(DOC):
        lines = FNS["shells/s%d" % s["g"]]
        assert FL.check_lines(lines) == []
        assert any(l.startswith("forceload add") for l in lines)
        assert D.shell_blocks(DOC, s) > 0


# ------------------------------------------------------------------------------------------------- the simulator


class DW(PS.World):
    """pocket_sim's World with the commands this pack uses. Items: [id, {'custom_data': {...}}, n]."""

    ITEM = re.compile(r"([a-z0-9_:]+)\[minecraft:custom_data~?=?\{([a-z_]+):(\d+)b\}")

    def __init__(self, pack_dir, extra=None):
        super().__init__(pack_dir, extra)
        self.in_battle = set()
        self.queue = []
        self.titles, self.bars, self.started = [], {}, []
        self.items = {}
        self.caps = {}

    # items
    def _key(self, pred):
        m = self.ITEM.match(pred)
        return (m.group(1), m.group(2), int(m.group(3)))

    def has(self, e, key):
        return any(it[0] == key[0] and it[1].get(key[1]) == key[2] for it in e.inventory)

    def run(self, cmd, ctx, from_macro=False):
        # `if|unless items entity @s container.* PRED` becomes a tag test, the tag kept in step with the inventory
        def sub(m):
            key = self._key(m.group(2))
            tag = "__has_%s_%s_%d" % (key[0].split(":")[1], key[1], key[2])
            self.items[tag] = key
            return "%s entity @s[tag=%s]" % (m.group(1), tag)
        cmd = re.sub(r"\b(if|unless) items entity @s container\.\* (\S+)", sub, cmd)
        cmd = re.sub(r"\b(if|unless) items entity @s armor\.chest minecraft:elytra", r"\1 entity @s[tag=__elytra]", cmd)
        for p in self.players():
            for tag, key in self.items.items():
                (p.tags.add if self.has(p, key) else p.tags.discard)(tag)
        return super().run(cmd, ctx, from_macro)

    def select(self, sel, ctx):
        if not sel.startswith("@") and not re.fullmatch(r"[0-9a-f-]{36}", sel):
            return [p for p in self.players() if p.name == sel and p.online]
        m = re.search(r",?scores=\{([^}]*)\}", sel)
        if not m:
            return super().select(sel, ctx)
        rest = sel.replace(m.group(0), "").replace("[,", "[").replace("[]", "")
        out = []
        for e in super().select(rest, ctx):
            ok = True
            for part in m.group(1).split(","):
                obj, _, rng = part.partition("=")
                lo, hi = PS._range(rng)
                v = self.get(e.holder, obj)
                ok = ok and v is not None and lo <= v <= hi
            if ok:
                out.append(e)
        return out

    def execute(self, t, ctx, from_macro):
        if "run" not in t:
            for i in range(len(t) - 1, -1, -1):
                if t[i] in ("if", "unless"):
                    t = t[:i] + ["run", "__cond"] + t[i:]
                    break
        if t[:3] == ["store", "result", "bossbar"]:
            self.bars.setdefault(t[3], {})[t[4]] = self.run_tokens(t[6:], ctx, from_macro)
            return 1
        return super().execute(t, ctx, from_macro)

    def run_tokens(self, t, ctx, from_macro=False, raw=None):
        h = t[0]
        if h == "__cond":
            want = t[1] == "if"
            n = len(self.select(t[3], ctx)) if t[2] == "entity" else None
            if n is None:
                raise PS.Unsupported(" ".join(t))
            if want:
                if not n:
                    raise PS.Failed("none")
                return n
            if n:
                raise PS.Failed("some")
            return 1
        if h == "tag" and t[2] == "remove":
            for e in self.select(t[1], ctx):
                e.tags.discard(t[3])
            return 1
        if h in ("title", "playsound", "particle", "ride", "recipe"):
            if h == "title":
                self.titles.append((ctx.ent.name if ctx.ent else None, " ".join(t[2:])))
            return 1
        if h == "bossbar":
            bar = self.bars.setdefault(t[2], {})
            if t[1] == "add":
                bar["exists"] = True
            elif t[1] == "remove":
                bar.clear()
                bar["removed"] = True
            elif t[1] == "set":
                bar[t[3]] = [e.name for e in self.select(t[4], ctx)] if t[3] == "players" and len(t) > 4 else (
                    [] if t[3] == "players" else " ".join(t[4:]))
            return 1
        if h == "gamemode":
            for e in self.select(t[2], ctx):
                e.gamemode = t[1]
            return 1
        if h == "give":
            m = self.ITEM.match(t[2].replace("custom_data={", "custom_data~{"))
            for e in self.select(t[1], ctx):
                e.inventory.append([m.group(1), {m.group(2): int(m.group(3))}, int(t[3]) if len(t) > 3 else 1])
            return 1
        if h == "clear":
            key = self._key(t[2])
            n = int(t[3]) if len(t) > 3 else 10 ** 6
            took = 0
            for e in self.select(t[1], ctx):
                for it in list(e.inventory):
                    if took < n and it[0] == key[0] and it[1].get(key[1]) == key[2]:
                        k = min(it[2], n - took)
                        it[2] -= k
                        took += k
                        if it[2] == 0:
                            e.inventory.remove(it)
            if not took:
                raise PS.Failed("clear: nothing")
            return took
        if h == "runmolang":
            expr = t[1].strip('"')
            ent = ctx.ent
            if "q.entity.discard" in expr:
                ent.alive = False
                return 1
            if "start_battle" in expr:
                self.started.append((ent.name, t[3]))
                return 1
            if expr.startswith("(q.player.in_battle == 0)") and ent.name not in self.in_battle:
                m = re.search(r"q\.run_command\('execute as ' \+ q\.player\.uuid \+ ' (.*?)'\);", expr)
                self.queue.append((ent.uid, m.group(1)))
            return 1
        if h == "rctmod" and t[1:4] == ["player", "get", "level_cap"]:
            e = self.one(t[4], ctx)
            if e.name not in self.caps:
                raise PS.Failed("no cap")
            return self.caps[e.name]
        if h == "spawnnpcat":
            if not from_macro:
                self.log.append("inert_spawn " + " ".join(t))
                return 0
            pos = [float(v) for v in t[1:4]]
            e = PS.Ent("cobblemon:npc", ctx.dim, pos, nbt={"NPCClass": t[4], "level": int(t[5])})
            self.ents.append(e)
            self.spawned.append(e)
            return 1
        return super().run_tokens(t, ctx, from_macro, raw)

    def drain(self):
        """runmolang's nested commands are queued (EXP-022): run them after the calling function."""
        q, self.queue = self.queue, []
        for uid, rest in q:
            try:
                self.run("execute as %s %s" % (uid, rest), self.server_ctx())
            except PS.Failed:
                pass

    def passes(self, n=1):
        for _ in range(n):
            self.tick(DOC["engine"]["keeper"]["period_ticks"])
            self.drain()


FAKES = {
    # the levelcap pack's check (tools/levelcap_pack.py battle_check): the cap the test gives, no party over it
    "cobblers:levelcap/battle_check": ["$scoreboard players set @s cobblers.lc_cap 20$(x)"],
    # the blackout's two E1 functions (built in tools/blackout_pack.py): record, and remove the tag as they do
    TAIL_END: ["tag @s remove %s" % RUN_TAG, "scoreboard players add @s tailend 1"],
    BACKSTOP: ["tag @s remove %s" % RUN_TAG, "scoreboard players add @s stale 1"],
}


@pytest.fixture(scope="module")
def pack(tmp_path_factory):
    out = tmp_path_factory.mktemp("cobblers_dungeons")
    D.write(FILES, out)
    return out


def world(pack):
    w = DW(pack, {k: v for k, v in FAKES.items()})
    w.objectives |= {"cobblers.lc_cap", "tailend", "stale"}
    w.boot()
    return w


def soot(n=1):
    x = D.sigils(DOC)[0]
    return [x["item"], {"cobblers_dg_sigil": 1}, n]


def click_rip(w, p):
    w.call("cobblers:dungeons/door/ns", PS.Ctx(p, p.dim, p.pos))


def arrive_and_cross(w, p):
    w.passes(4)                                    # the arrival delay
    assert p.dim == POCKET and w.get(p.name, "dg.st") == 2, (p, w.get(p.name, "dg.st"))
    s = D.slots(DOC)[w.get(p.name, "dg.slot") - 1]
    p.pos = [D.points(DOC, s)["threshold_x"] + 1.5, 96.0, s["cz"] + 0.5]
    w.passes(1)
    assert w.get(p.name, "dg.st") == 3
    return s


def test_a_clean_run_out_by_the_far_rip(pack):
    w = world(pack)
    p = w.player("Ash", OW, (1352.5, 130, 4120.5))
    p.inventory.append(soot())
    click_rip(w, p)
    assert RUN_TAG in p.tags and w.get(p.name, "dg.st") == 1
    assert not p.inventory, "the sigil is taken at the rip"
    s = arrive_and_cross(w, p)
    assert p.gamemode == "adventure" and any(i[0] == "minecraft:iron_pickaxe" for i in p.inventory)
    full = DOC["engine"]["bands"][0]["clock_s"] * 80
    w.passes(3)
    assert w.get(p.name, "dg.clock") == full - 3 * 80, "three passes at x1 since the pass that crossed"
    assert w.get(p.name, "dg.lk_ns") is not None
    w.call("cobblers:dungeons/far", PS.Ctx(p, p.dim, p.pos))
    assert p.dim == OW and p.gamemode == "survival" and not any(i[0] == "minecraft:iron_pickaxe" for i in p.inventory)
    assert w.get(p.name, "dg.st") == 0 and w.get("#s%d" % s["g"], "dg.own") == 0
    assert RUN_TAG in p.tags, "the engine never removes the run tag"
    w.passes(5)
    assert RUN_TAG in p.tags, "the tail lasts at least tail_ticks"
    w.passes(2)
    assert RUN_TAG not in p.tags and w.get(p.name, "tailend") == 1 and not w.get(p.name, "stale")


def test_the_back_rip_before_the_threshold_returns_the_sigil_and_stamps_no_lockout(pack):
    w = world(pack)
    p = w.player("Brock", OW, (1352.5, 130, 4120.5))
    p.inventory.append(soot())
    click_rip(w, p)
    w.passes(4)
    assert w.get(p.name, "dg.st") == 2
    w.call("cobblers:dungeons/back", PS.Ctx(p, p.dim, p.pos))
    assert p.dim == OW and [i[0] for i in p.inventory] == ["minecraft:miner_pottery_sherd"]
    assert w.get(p.name, "dg.lk_ns") is None
    click_rip(w, p)
    assert w.get(p.name, "dg.st") == 1, "no lockout before the threshold"


def test_refusals_take_nothing(pack):
    w = world(pack)
    p = w.player("Misty", OW, (1352.5, 130, 4120.5))
    click_rip(w, p)
    assert w.get("#why", "dg.t") == 8 and RUN_TAG not in p.tags and w.get(p.name, "dg.st") in (None, 0)
    p.tags.add("__elytra")
    p.inventory.append(soot())
    click_rip(w, p)
    assert w.get("#why", "dg.t") == 4 and p.inventory == [soot()]


def test_timeout_kills_once_out_of_battle_and_the_death_ends_the_run_with_a_tail(pack):
    w = world(pack)
    p = w.player("Gary", OW, (1352.5, 130, 4120.5))
    p.inventory.append(soot())
    click_rip(w, p)
    s = arrive_and_cross(w, p)
    w.in_battle.add(p.name)
    w.set(p.name, "dg.clock", 100)
    w.passes(3)
    assert w.get(p.name, "dg.st") == 4 and not p.dead, "sudden death holds while in battle"
    w.set(p.name, "dg.claw", 1)
    w.in_battle.discard(p.name)
    w.passes(2)
    assert not p.dead, "the clawback runs to completion before the kill (E1 rule 6)"
    w.set(p.name, "dg.claw", 0)
    w.passes(1)
    assert p.dead and w.get(p.name, "dg.cause") == 1
    # the respawn: the blackout returns them to the overworld; deathCount moved
    p.dead, p.dim, p.pos = False, OW, [100.5, 70.0, 100.5]
    w.set(p.name, "dg.dc", 1)
    w.passes(1)
    assert w.get(p.name, "dg.st") == 0 and p.gamemode == "survival" and RUN_TAG in p.tags
    assert w.get("#s%d" % s["g"], "dg.own") == 0
    assert any("The rift closed" in t for _n, t in w.titles)
    w.passes(7)
    assert RUN_TAG not in p.tags and w.get(p.name, "tailend") == 1


def test_a_logout_keeps_the_clock_running_and_a_dead_run_kills_on_return(pack):
    w = world(pack)
    p = w.player("Erika", OW, (1352.5, 130, 4120.5))
    p.inventory.append(soot())
    click_rip(w, p)
    s = arrive_and_cross(w, p)
    before = w.get(p.name, "dg.clock")
    p.online = False
    w.passes(10)
    p.online = True
    w.passes(1)
    assert w.get(p.name, "dg.clock") == before - 11 * 80, "the absence is charged at the rate, as if present"
    assert w.get(p.name, "dg.st") == 3
    # a long absence: the slot's deadline passes while they are away and the slot is freed without them
    w.set(p.name, "dg.clock", 400)
    w.passes(1)
    p.online = False
    w.passes(4)
    assert w.get("#s%d" % s["g"], "dg.own") >= 1, "not before the deadline"
    w.passes(2)
    assert w.get("#s%d" % s["g"], "dg.own") == 0, "the slot freed at the absent member's deadline"
    p.online = True
    w.passes(1)
    assert p.dead and w.get(p.name, "dg.cause") == 4, "back to a dead run: killed into the blackout"


def test_a_player_who_is_not_a_member_is_put_out_of_the_slots(pack):
    w = world(pack)
    s = D.slots(DOC)[0]
    pt = D.points(DOC, s)
    q = w.player("Stray", POCKET, (pt["arrive"][0], 96, pt["arrive"][2]))
    w.passes(1)
    x, y, z, _yaw = DOC["dungeons"][0]["rip"]["outside"]
    assert q.dim == OW and q.pos == [x, y, z]


def test_the_greed_ladder_on_a_marker(pack):
    w = world(pack)
    m = PS.Ent("minecraft:marker", OW, (0.5, 70, 0.5), tags=("t",))
    w.ents.append(m)
    want = {}
    for r in D.ladder(DOC):
        want[r["taken"]] = r["rate"]
    rate = DOC["engine"]["clock"]["ladder"][0]["rate"]
    for n in range(0, 26):
        rate = want.get(n, rate)
        w.call("cobblers:dungeons/greed/test_set", PS.Ctx(m, OW, m.pos), {"n": n})
        assert w.get(m.uid, "dg.rate") == rate, n


def test_the_staged_boss_spawns_by_macro_chains_on_victory_and_opens_the_gate(pack):
    w = world(pack)
    p = w.player("Lance", OW, (1352.5, 130, 4120.5))
    p.inventory.append(soot())
    click_rip(w, p)
    s = arrive_and_cross(w, p)
    pt = D.points(DOC, s)
    p.pos = [pt["spot"][0] - 4.5, 96.0, s["cz"] + 0.5]
    for stage in (1, 2, 3):
        w.passes(1)
        npcs = [e for e in w.ents if e.kind == "cobblemon:npc" and e.alive]
        assert len(npcs) == 1 and {"dg.boss", "dg.npc", EXEMPT} <= npcs[0].tags, (stage, npcs)
        assert npcs[0].nbt["NPCClass"] == "cobblers:dg_ns_boss_b1_s%d" % stage
        w.passes(1)
        assert w.started and w.started[-1][0] == "Lance"
        # the victory callback, as Cobblemon runs it with the NPC as the loser
        w.run_callback("battle_victory", context={
            "scriptable_losers": [{"is_npc": 1, "uuid": npcs[0].uid}], "player_winners": [{"player": {"username": "Lance"}}],
            "scriptable_winners": [], "player_losers": []})
        assert "dg.next" in p.tags
        w.passes(1)
        assert not npcs[0].alive and w.get(p.name, "dg.stage") == stage + 1
        if stage < 3:
            w.passes(3)                            # the gap
    assert w.get("#s%d" % s["g"], "dg.bdone") == 1 and w.get(p.name, "dg.bossd") == 1
    assert any(d == POCKET and "minecraft:air" in c and c.startswith("fill %d" % pt["gate"][0]) for d, c in w.block_writes)
