"""tools/arena_runtime.py: Heaven's Arena's per-player opponents, built and walked offline.

Written by the session that built the tool (the brief asked for it); an independent audit is to follow. So the
expectations here are taken from the DATA wherever the data states them independently of the tool's arithmetic:
the designer's typical purses in data/arena_fights.json, set_pool.counts, the ranks' level bands, the champions'
authored teams. The venues are tests/fixtures/arena_dome.json: data/arena_dome.json is authored in parallel.

The walk-through tests run the generated functions in a small interpreter of exactly the command subset the pack
uses (scoreboard, execute incl. store result score|storage, tag, function and macros, storage, spawnnpcat, kill, tp,
runmolang as a hook, and the level-cap pack's `rctmod player get level_cap` and party compare, sweep U54). It models
one Minecraft rule set closely enough to follow scores and entities; it does NOT model Cobblemon: a battle is the
test calling the generated callback's commands, and start_battle's refusal is a switch.

Not covered, and it needs a running server: that spawnnpcat works from inside a macro function; that a cobblemon:npc
spawned by it is selectable in the same tick; that q.npc.in_battle / q.player.in_battle answer as named; that
`healpokemon @s`, `cobbledollars give` and the interaction-click advancement behave in game; two real accounts.
"""
import json
import math
import os
import re
import sys
import types
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import arena_runtime as AR  # noqa: E402
import levelcap_pack as LC  # noqa: E402  (only to EMIT the level-cap pack the challenge calls; never an expectation)

FIXTURE = ROOT / "tests" / "fixtures" / "arena_dome.json"
LEVEL_CAP = json.loads((ROOT / "data" / "level_cap.json").read_text(encoding="utf-8"))
LC_SRC = (ROOT / "tools" / "levelcap_pack.py").read_text(encoding="utf-8")
AR_SRC = (ROOT / "tools" / "arena_runtime.py").read_text(encoding="utf-8")
FIGHTS = json.loads((ROOT / "data" / "arena_fights.json").read_text(encoding="utf-8"))
TRAINERS = {t["id"]: t for t in json.loads((ROOT / "data" / "arena_trainers.json").read_text(encoding="utf-8"))["trainers"]}
DOME = json.loads(FIXTURE.read_text(encoding="utf-8"))
RANKS = {r["rank"]: r for r in FIGHTS["ranks"]}
FN = "data/cobblers/function/arena/%s.mcfunction"


@pytest.fixture(scope="module")
def pack():
    return AR.files(FIXTURE)


# ------------------------------------------------------------------ fail closed

def test_no_dome_no_pack(tmp_path):
    # Removing this lets prepare ship an arena whose posts stand nowhere
    with pytest.raises(SystemExit, match="arena_dome"):
        AR.files(tmp_path / "missing.json")


def test_a_rank_no_venue_offers_fails(tmp_path):
    # Removing this lets a ladder rung exist that no post can ever start (a player stuck at that rank for ever)
    d = json.loads(json.dumps(DOME))
    d["venues"] = [v for v in d["venues"] if 9 not in v["ranks"]]
    f = tmp_path / "dome.json"
    f.write_text(json.dumps(d), encoding="utf-8")
    with pytest.raises(SystemExit, match=r"rank\(s\) \[7, 8, 9\]"):
        AR.files(f)


# ------------------------------------------------------------------ the classes

def _classes(pack):
    return {k.split("/")[-1][:-5]: v for k, v in pack.items() if k.startswith("data/cobblers/npcs/")}


def test_every_rank_has_its_class_and_every_exam_its_champion(pack):
    cls = _classes(pack)
    singles = {"arena_rank_%d" % n for n, r in RANKS.items() if r["format"] != "streak"}
    st = RANKS[9]["streak"]
    streak = {"arena_streak_m%d" % m for m in range(st["members_start"], 7)}
    exams = set()
    for e in FIGHTS["rank_up_fights"]:
        exams |= {"arena_exam_%s" % t for t in e.get("legs", [e.get("trainer")])}
    assert set(cls) == singles | streak | exams, sorted(set(cls) ^ (singles | streak | exams))


def test_the_classes_are_per_challenger_opponents(pack):
    # the probe class's shape that passed in game, plus: nobody else can challenge it, it never despawns or moves
    for cid, c in _classes(pack).items():
        assert c["battleConfiguration"] == {"canChallenge": False}, cid
        assert c["canDespawn"] is False and c["isInvulnerable"] is True and c["isMovable"] is False, cid
        assert {"type": "apply_behaviours", "presets": ["cobblemon:battler", "cobblemon:looks_at_players"]} in c["ai"]


def test_a_pool_is_the_open_sets_and_rerolls(pack):
    # the designer's own counts (set_pool.counts) against the pools, so a min_rank slip shows
    counts = FIGHTS["set_pool"]["counts"]
    want = {1: counts["eligible_rank_1"], 2: counts["eligible_rank_2"], 3: counts["eligible_ranks_3_4"],
            4: counts["eligible_ranks_3_4"]}
    cls = _classes(pack)
    for n, r in RANKS.items():
        if r["format"] == "streak":
            continue
        p = cls["arena_rank_%d" % n]["party"]
        assert p["type"] == "pool" and p["isStatic"] is False
        assert p["minPokemon"] == p["maxPokemon"] == str(r["members"])
        assert len(p["pool"]) == want.get(n, counts["eligible_ranks_5_plus"]), n
        assert {e["levelVariation"] for e in p["pool"]} == {r["members"] - 1}


def test_no_member_is_ever_drawn_above_its_rank_s_top(pack):
    # the spawn level is in bout/start's storage line; plus levelVariation must land on the band's top exactly
    start = pack[FN % "bout/start"]
    cls = _classes(pack)
    for n, r in RANKS.items():
        if r["format"] == "streak":
            continue
        (lv,) = [int(m.group(1)) for l in start
                 for m in [re.search(r'kind matches 1 if score @s ar.cur matches %d run .*cls:"cobblers:arena_rank_%d",'
                                     r'level:(\d+)\}' % (n, n), l)] if m]
        var = cls["arena_rank_%d" % n]["party"]["pool"][0]["levelVariation"]
        assert lv + var == r["levels"]["top"] and lv >= r["levels"]["floor"], (n, lv, var)


def test_an_exam_is_the_champions_authored_team(pack):
    cls = _classes(pack)
    for tid, t in TRAINERS.items():
        mons = cls["arena_exam_%s" % tid]["party"]["pokemon"]
        assert len(mons) == len(t["team"])
        for s, m in zip(mons, t["team"]):
            assert s.split()[0] == m["species"] and "level=%d" % m["level"] in s.split()
            assert "moves=%s" % ",".join(m["moveset"]) in s.split()


PROP_KEYS = {"level", "moves", "ability", "held_item", "nature"}


def test_every_properties_string_uses_only_known_keys(pack):
    # keys read from the 1.8.0 jar's PokemonProperties parser; held_item proven in game (EXP-041)
    for cid, c in _classes(pack).items():
        p = c["party"]
        strings = p["pokemon"] if p["type"] == "simple" else [e["pokemon"] for e in p["pool"]]
        for s in strings:
            sp, *kv = s.split()
            assert re.fullmatch(r"[a-z0-9]+", sp), s
            keys = [x.split("=", 1)[0] for x in kv]
            assert set(keys) <= PROP_KEYS and len(keys) == len(set(keys)), s
            assert all(x.split("=", 1)[1].startswith("cobblemon:") for x in kv if x.startswith("held_item=")), s
            assert not any("mega_showdown" in x for x in kv), s


def _jar():
    env = os.environ.get("COBBLERS_COBBLEMON_JAR")
    cands = [Path(env)] if env else []
    cands += list((ROOT / "experiments" / "EXP-000-cobblemon-1.8-compat" / "runtime" / "server" / "mods").glob(
        "Cobblemon-fabric-1.8.0*.jar"))
    return next((c for c in cands if c.is_file()), None)


def test_no_legendary_or_mythical_species_is_drawn_or_examined(pack):
    # decisions_pending Q6 default: none in the arena's own teams. Read from the jar's species labels
    jar = _jar()
    if jar is None:
        pytest.skip("no Cobblemon 1.8.0 jar (set COBBLERS_COBBLEMON_JAR); the labels live in its species files")
    z = zipfile.ZipFile(jar)
    labels = {}
    for n in z.namelist():
        if n.startswith("data/cobblemon/species/") and n.endswith(".json"):
            d = json.loads(z.read(n))
            labels[n.rsplit("/", 1)[-1][:-5]] = set(d.get("labels", []))
    species = {s["member"]["species"] for s in FIGHTS["set_pool"]["sets"]}
    species |= {m["species"] for t in TRAINERS.values() for m in t["team"]}
    missing = sorted(s for s in species if s not in labels)
    assert not missing, missing
    bad = sorted(s for s in species if labels[s] & {"legendary", "mythical", "ultra_beast", "paradox"})
    assert not bad, bad
    items = {held for held in [s["member"].get("heldItem") for s in FIGHTS["set_pool"]["sets"]]
             + [m.get("heldItem") for t in TRAINERS.values() for m in t["team"]] if held}
    names = set(z.namelist())
    assert not [i for i in items if "assets/cobblemon/models/item/%s.json" % i not in names]
    for p in FIGHTS["prizes"]["items"]:
        for c in p["contents"]:
            ns, i = c["item"].split(":")
            if ns == "cobblemon":
                assert "assets/cobblemon/models/item/%s.json" % i in names, c["item"]


# ------------------------------------------------------------------ money, against the designer's own figures

def _amounts(lines, pat):
    return [int(m.group(1)) for l in lines for m in [re.search(pat + r".*\{amount:(\d+)\}", l)] if m]


def test_the_purses_are_the_designers_typical_figures(pack):
    pu = pack[FN % "purse"]
    for n, r in RANKS.items():
        if r["format"] == "streak":
            continue
        (full,) = _amounts(pu, r"kind matches 1 if score @s ar.cur matches %d if score @s ar.exh matches 0 " % n)
        assert full == r["purse"].get("typical", r["purse"].get("typical_per_leg")), (n, full)
        (exh,) = _amounts(pu, r"kind matches 1 if score @s ar.cur matches %d if score @s ar.exh matches 1 " % n)
        assert exh % 50 == 0 and abs(exh - full / 4) <= 25, (n, exh)
    for e in FIGHTS["rank_up_fights"]:
        got = _amounts(pu, r"kind matches 2 if score @s ar.cur matches %d " % e["rank"])
        assert sum(got) == e["purse_typical"], (e["rank"], got)


# ------------------------------------------------------------------ the blackout exemption

def test_an_arena_loss_is_not_a_blackout():
    # read from the generator's source: blackout_pack.build() needs inputs this test does not own
    cfg = json.loads((ROOT / "data" / "blackout.json").read_text(encoding="utf-8"))
    tag = cfg["arena_exempt"]["player_tag"]
    src = (ROOT / "tools" / "blackout_pack.py").read_text(encoding="utf-8")
    i = src.index('fn("blackout/battle_loss_npc"')
    body = src[i:src.index('fn("blackout/battle_loss_other"')]
    assert body.index('arena["player_tag"]') < body.index("blackout/dedupe")
    assert tag == "cobblers.arena_bout"


def test_the_bout_tag_is_the_one_the_blackout_reads(pack):
    tag = json.loads((ROOT / "data" / "blackout.json").read_text(encoding="utf-8"))["arena_exempt"]["player_tag"]
    assert "tag @s add %s" % tag in pack[FN % "bout/start"]
    assert "tag @s remove %s" % tag in pack[FN % "end_run"]


# ------------------------------------------------------------------ reapply wiring

def test_reapply_builds_installs_and_places_it():
    import reapply
    assert "cobblers_arena" in reapply.SERVER_PACKS and "cobblers_arena" in reapply.WORLD_LOCAL
    src = (ROOT / "tools" / "reapply.py").read_text(encoding="utf-8")
    assert src.index('add("route_trainers"') < src.index('add("arena_runtime", "arena_runtime.py")')
    r17, r17a = src.index('out.append(("R17", '), src.index('out.append(("R17A", ')
    assert r17 < r17a < src.index('out.append(("R17F", ')
    for f in ("cobblers:arena/load", "cobblers:arena/retire_spire", "cobblers:arena/posts/place"):
        assert '("fn", "%s")' % f in src[r17a:src.index('out.append(("R17F", ')]


def test_the_retired_spire_champions_are_removed_where_they_stood(pack):
    lines = [l for l in pack[FN % "retire_spire"] if l.startswith("kill")]
    assert len(lines) == len(TRAINERS)
    for tid, t in TRAINERS.items():
        x, y, z = t["superseded_seat"]["seat"]
        assert ('kill @e[type=rctmod:trainer,x=%d.5,y=%d,z=%d.5,distance=..24,nbt={TrainerId:"%s"}]'
                % (x, y, z, tid)) in lines


# ================================================================== the interpreter

class Ent:
    n = 0

    def __init__(self, kind, pos, **kw):
        Ent.n += 1
        self.uuid = "00000000-0000-0000-0000-%012d" % Ent.n
        self.kind, self.pos, self.tags, self.adv = kind, list(pos), set(), set()
        self.__dict__.update(kw)


class Sim:
    """The level-cap pack (tools/levelcap_pack.py, emitted for data/level_cap.json, or `levelcap` when given) is loaded
    beside the arena's, because every challenge calls its battle_check (sweep U54). Each player has an RCT cap
    (`rctmod player get level_cap` answers it; None: the command fails, as when RCT is still loading, and a failed
    command stores 0 through `execute store result`) and a party whose highest level `q.player.party.highest_level`
    answers. The default player sits AT the cap (50/50), so every older flow also walks the strictly-over boundary."""

    def __init__(self, pack, levelcap=None):
        self.fns = {k[len("data/cobblers/function/"):-len(".mcfunction")]: v for k, v in pack.items()
                    if k.startswith("data/cobblers/function/")}
        for k, v in (LC.files(LEVEL_CAP) if levelcap is None else levelcap).items():
            if k.startswith("data/cobblers/function/"):
                assert k[len("data/cobblers/function/"):-len(".mcfunction")] not in self.fns, k
                self.fns[k[len("data/cobblers/function/"):-len(".mcfunction")]] = (
                    v.splitlines() if isinstance(v, str) else v)
        self.callback = pack["data/cobblemon/callbacks/battle_victory/cobblers_arena.molang"]
        self.scores, self.storage, self.ents = {}, {}, []
        self.money, self.heals, self.gives, self.started, self.said = {}, {}, {}, [], []
        self.refuse = False
        self.in_battle = set()
        self.call("arena/load", None)

    # -- entities
    def player(self, pos=(3580, 20, 3200), adv=(), cap=50, top=50):
        p = Ent("player", pos, cap=cap, top=top)
        p.adv |= set(adv)
        self.ents.append(p)
        return p

    def npcs(self):
        return [e for e in self.ents if e.kind == "npc"]

    def holder(self, h, ctx):
        if h == "@s":
            return ctx["s"].uuid
        if h.startswith("@"):
            (e,) = self.select(h, ctx)
            return e.uuid
        return h

    def get(self, h, obj):
        return self.scores.get((h, obj))

    def select(self, sel, ctx):
        if re.fullmatch(r"[0-9a-f-]{36}", sel):
            return [e for e in self.ents if e.uuid == sel]
        m = re.fullmatch(r"@([saep])(?:\[(.*)\])?", sel)
        assert m, sel
        kind, args = m.group(1), m.group(2) or ""
        if kind == "s":
            cands = [ctx["s"]] if ctx["s"] is not None else []
        elif kind in "ap":
            cands = [e for e in self.ents if e.kind == "player"]
        else:
            cands = list(self.ents)
        parts = re.findall(r"(\w+)=(\{[^}]*\}|[^,]+)", args)
        limit, out = None, []
        for e in cands:
            ok = True
            for k, v in parts:
                if k == "type":
                    ok &= (v == "cobblemon:npc" and e.kind == "npc") or (v == "minecraft:interaction" and e.kind == "post") \
                          or (v == "rctmod:trainer" and e.kind == "rct") or (v == "minecraft:text_display" and e.kind == "label")
                elif k == "tag":
                    ok &= (v[1:] not in e.tags) if v.startswith("!") else (v in e.tags)
                elif k == "distance":
                    ok &= math.dist(e.pos, ctx["pos"]) <= float(v.lstrip("."))
                elif k == "scores":
                    for kk, vv in re.findall(r"([\w.]+)=([\d.]+)", v):
                        sc = self.get(e.uuid, kk)
                        ok &= sc is not None and self.inrange(sc, vv)
                elif k == "advancements":
                    for a in re.findall(r"([\w:/]+)=true", v):
                        ok &= a in e.adv
                elif k == "limit":
                    limit = int(v)
                elif k in ("sort", "x", "y", "z", "nbt", "gamemode"):
                    pass
            if ok:
                out.append(e)
        if kind == "p":
            out = out[:1]
        return out[:limit] if limit else out

    @staticmethod
    def inrange(v, r):
        if ".." not in r:
            return v == int(r)
        lo, hi = r.split("..")
        return (lo == "" or v >= int(lo)) and (hi == "" or v <= int(hi))

    # -- running
    def call(self, name, s, macro=None):
        ctx = {"s": s, "pos": list(s.pos) if s else [0, 0, 0]}
        for line in self.fns[name]:
            if not line or line.startswith("#"):
                continue
            if line.startswith("$"):
                line = re.sub(r"\$\((\w+)\)", lambda m: str(macro[m.group(1)]), line[1:])
            r = self.run(line, dict(ctx))
            if r == "RETURN":
                return

    def run(self, line, ctx):
        toks = line.split(" ")
        if toks[0] == "execute":
            return self.execute(toks[1:], ctx)
        if toks[0] == "return":
            if toks[1] == "run":
                self.run(" ".join(toks[2:]), ctx)
            return "RETURN"
        return self.command(line, ctx)

    def execute(self, t, ctx):
        i = 0
        while i < len(t):
            w = t[i]
            if w == "run":
                return self.run(" ".join(t[i + 1:]), ctx)
            if w == "as":
                ents = self.select(t[i + 1], ctx)
                r = None
                for e in ents:
                    r2 = self.execute(t[i + 2:], dict(ctx, s=e))
                    r = r2 if r2 == "RETURN" else r
                return r
            if w == "at":
                ctx["pos"] = list(ctx["s"].pos)
                i += 2
                continue
            if w == "positioned":
                ctx["pos"] = [float(x) for x in t[i + 1:i + 4]]
                i += 4
                continue
            if w in ("if", "unless"):
                what = t[i + 1]
                if what == "score":
                    a = self.get(self.holder(t[i + 2], ctx), t[i + 3])
                    if t[i + 4] == "matches":
                        res = a is not None and self.inrange(a, t[i + 5])
                        n = 6
                    else:
                        b = self.get(self.holder(t[i + 5], ctx), t[i + 6])
                        op = t[i + 4]
                        res = a is not None and b is not None and {"=": a == b, "<": a < b, ">": a > b,
                                                                   "<=": a <= b, ">=": a >= b}[op]
                        n = 7
                elif what == "entity":
                    res = bool(self.select(t[i + 2], ctx))
                    n = 3
                elif what == "data":
                    res = self.dget(t[i + 3], t[i + 4]) is not None
                    n = 5
                else:
                    raise AssertionError(line)
                if res != (w == "if"):
                    return None
                i += n
                continue
            if w == "store":
                # execute store result storage S path int 1 | store result score H O, then `run <a query>`; a query
                # that fails stores 0 (vanilla 1.20.3+: the failure callback stores 0 through `store result`)
                j = t.index("run", i)
                v = self.query(" ".join(t[j + 1:]), ctx)
                if t[i + 1:i + 3] == ["result", "storage"]:
                    self.dset(t[i + 3], t[i + 4], v)
                elif t[i + 1:i + 3] == ["result", "score"]:
                    self.scores[(self.holder(t[i + 3], ctx), t[i + 4])] = v
                else:
                    raise AssertionError("execute %s" % " ".join(t))
                return None
            raise AssertionError("execute %s" % " ".join(t))

    def query(self, cmd, ctx):
        """What a command returns as its result (for `execute store result`); 0 when it fails."""
        t = cmd.split(" ")
        if t[:3] == ["scoreboard", "players", "get"]:
            v = self.get(self.holder(t[3], ctx), t[4])
            return 0 if v is None else v
        if t[:4] == ["rctmod", "player", "get", "level_cap"] and len(t) == 5:
            (e,) = self.select(t[4], ctx)
            return 0 if getattr(e, "cap", None) is None else e.cap
        raise AssertionError("unmodelled query: %s" % cmd)

    def party_molang(self, mol, s):
        """`runmolang "<mol>" @s` where mol compares q.player.party.highest_level with a rendered number and runs one
        branch's q.run_command lines as the server (MoLang's ternary, a number compare, string concatenation)."""
        m = re.fullmatch(r"\(q\.player\.party\.highest_level (>=|>|<=|<|==) (-?\d+)\) \? \{ (.*) \} : \{ (.*) \};", mol)
        assert m, "unmodelled molang: %s" % mol
        op, n = m.group(1), int(m.group(2))
        yes = {">": s.top > n, ">=": s.top >= n, "<": s.top < n, "<=": s.top <= n, "==": s.top == n}[op]
        for expr in re.findall(r"q\.run_command\((.*?)\);", m.group(3) if yes else m.group(4)):
            cmd = "".join(json.loads('"%s"' % p[1:-1]) if p.startswith("'") else {"q.player.uuid": s.uuid}[p]
                          for p in [x.strip() for x in re.split(r"\s\+\s", expr)])
            self.run(cmd, {"s": None, "pos": [0, 0, 0]})

    def dget(self, st, path):
        d = self.storage.get(st, {})
        for p in path.split("."):
            if not isinstance(d, dict) or p not in d:
                return None
            d = d[p]
        return d

    def dset(self, st, path, v):
        d = self.storage.setdefault(st, {})
        ps = path.split(".")
        for p in ps[:-1]:
            d = d.setdefault(p, {})
        d[ps[-1]] = v

    @staticmethod
    def snbt(s):
        s = s.strip()
        if s.startswith('"'):
            return json.loads(s)
        return {k: (json.loads(v) if v.startswith('"') else int(v))
                for k, v in re.findall(r'(\w+):("[^"]*"|-?\d+)', s)}

    def command(self, line, ctx):
        s = ctx["s"]
        t = line.split(" ")
        c = t[0]
        if c == "scoreboard":
            if t[1] == "objectives":
                return
            h = self.holder(t[3], ctx) if t[2] != "operation" else None
            if t[2] == "set":
                self.scores[(h, t[4])] = int(t[5])
            elif t[2] == "add":
                self.scores[(h, t[4])] = (self.get(h, t[4]) or 0) + int(t[5])
            elif t[2] == "remove":
                self.scores[(h, t[4])] = (self.get(h, t[4]) or 0) - int(t[5])
            elif t[2] == "reset":
                self.scores.pop((h, t[4]), None)
            elif t[2] == "operation":
                a, ao, op, b, bo = self.holder(t[3], ctx), t[4], t[5], self.holder(t[6], ctx), t[7]
                x, y = self.get(a, ao) or 0, self.get(b, bo) or 0
                self.scores[(a, ao)] = {"=": y, "+=": x + y, "-=": x - y, "*=": x * y, "/=": x // y if y else x,
                                        "%=": x % y if y else x, "<": min(x, y), ">": max(x, y)}[op]
            return
        if c == "function":
            name = t[1].split(":", 1)[1]
            if len(t) > 2 and t[2] == "with":
                assert t[3] == "storage", line
                # no path: the whole compound (FunctionCommand)
                return self.call(name, s, self.dget(t[4], t[5]) if len(t) > 5 else dict(self.storage.get(t[4], {})))
            if len(t) > 2:
                return self.call(name, s, self.snbt(" ".join(t[2:])))
            return self.call(name, s)
        if c == "tag":
            for e in self.select(t[1], ctx):
                (e.tags.add if t[2] == "add" else e.tags.discard)(t[3])
            return
        if c == "kill":
            for e in self.select(t[1], ctx):
                self.ents.remove(e)
                for k in [k for k in self.scores if k[0] == e.uuid]:
                    del self.scores[k]
            return
        if c == "spawnnpcat":
            self.ents.append(Ent("npc", [float(x) for x in t[1:4]], cls=t[4], level=int(t[5])))
            return
        if c == "tp":
            if t[2] != "~":
                s.pos = [float(x) for x in t[2:5]]
            return
        if c == "healpokemon":
            self.heals[s.uuid] = self.heals.get(s.uuid, 0) + 1
            return
        if c == "cobbledollars":
            self.money[s.uuid] = self.money.get(s.uuid, 0) + int(t[3])
            return
        if c == "give":
            self.gives.setdefault(s.uuid, []).append((t[2], int(t[3])))
            return
        if c == "data":
            if t[1] == "remove" and t[2] == "storage":
                self.storage.get(t[3], {}).pop(t[4], None)
            elif t[1] == "modify":
                self.dset(t[3], t[4], self.snbt(" ".join(t[7:])))
            return
        if c == "runmolang":
            m = re.fullmatch(r'runmolang "(.*)" @s', line)
            if m and "q.player.party." in m.group(1):
                return self.party_molang(m.group(1), s)
            (npc,) = self.select(t[-1], ctx)
            mol = line[len("runmolang "):].rsplit(" ", 2)[0]
            if "start_battle" in mol:
                self.started.append((s.uuid, npc.cls, npc.level))
                if self.refuse:
                    self.call("arena/refused", s)
                else:
                    self.in_battle |= {s.uuid, npc.uuid}
            elif "in_battle" in mol:
                if npc.uuid not in self.in_battle and s.uuid not in self.in_battle:
                    self.call("arena/idle", s)
            return
        if c == "summon":
            kind = {"minecraft:interaction": "post", "minecraft:text_display": "label"}[t[1]]
            e = Ent(kind, [float(x) for x in t[2:5]])
            e.tags |= set(re.findall(r'"(cobblers_arena_post[\w]*)"', line))
            self.ents.append(e)
            return
        if c in ("tellraw", "title"):
            self.said.append((s.uuid if s else None, line))
            return
        if c in ("advancement",):
            return
        raise AssertionError("unmodelled: %s" % line)

    # -- the game around the pack
    def tick(self, n=1):
        for _ in range(n):
            self.call("arena/tick", None)

    def result(self, player, won):
        """A battle between `player` and their opponent ends: the callback's own commands, evaluated."""
        (npc,) = [e for e in self.npcs() if self.get(e.uuid, "ar.id") == self.get(player.uuid, "ar.id")
                  and "cobblers_arena_done" not in e.tags]
        self.in_battle -= {player.uuid, npc.uuid}
        block = self.callback.split("for_each(t.v")[0 if won else 1]
        env = {"t.l.uuid": npc.uuid, "t.w.player.uuid": player.uuid, "t.v.uuid": npc.uuid, "t.p.player.uuid": player.uuid}
        for expr in re.findall(r"q\.run_command\((.*)\);", block):
            cmd = "".join(json.loads('"%s"' % p[1:-1]) if p.startswith("'") else env[p]
                          for p in [x.strip() for x in re.split(r"\s\+\s", expr)])
            self.run(cmd, {"s": None, "pos": [0, 0, 0]})

    def click(self, player, venue):
        self.call("arena/post/%s" % venue, player)

    def sc(self, p, obj):
        return self.get(p.uuid, obj)

    def mine(self, p):
        return [e for e in self.npcs() if self.get(e.uuid, "ar.id") == self.sc(p, "ar.id")]


GYM8 = "cobblers:flag/gym8_cleared"
LANCE = "cobbleverse:trainer/kanto/defeat_elite_lance"
CHAMP = "cobblers:flag/champion_cleared"
VENUE = {v["id"]: v for v in DOME["venues"]}


def _bout(sim, p, won=True):
    sim.tick(AR.GO_TICKS)
    sim.result(p, won)
    sim.tick(AR.END_TICKS)


def test_a_first_bout_spawns_in_front_starts_without_a_click_and_pays(pack):
    sim = Sim(pack)
    p = sim.player(adv=[GYM8])
    sim.click(p, "floor_ring")
    (n,) = sim.mine(p)
    v = VENUE["floor_ring"]
    assert n.pos == [float(x) for x in v["opponent_spot"][:3]] and n.cls == "cobblers:arena_rank_1"
    assert "cobblers_arena" in n.tags and "cobblers.arena_bout" in p.tags
    assert p.pos[0] == v["challenger_mark"][0] + 0.5 and sim.heals[p.uuid] == 1
    assert not sim.started
    sim.tick(AR.GO_TICKS)
    assert sim.started == [(p.uuid, "cobblers:arena_rank_1", RANKS[1]["levels"]["top"] - 2)]
    sim.result(p, True)
    assert sim.money[p.uuid] == RANKS[1]["purse"]["typical"] and sim.sc(p, "ar.wins") == 1
    assert sim.mine(p), "cleared only after the delay"
    sim.tick(AR.END_TICKS)
    assert not sim.mine(p) and sim.sc(p, "ar.live") == 0 and "cobblers.arena_bout" not in p.tags


def test_three_wins_open_the_exam_and_beating_it_ranks_up_with_its_prize_once(pack):
    sim = Sim(pack)
    p = sim.player(adv=[GYM8])
    for _ in range(RANKS[1]["advance"]["wins_at_rank"]):
        sim.click(p, "floor_ring")
        _bout(sim, p)
    sim.click(p, "floor_ring")
    assert sim.mine(p)[0].cls == "cobblers:arena_exam_arena_tier_1_champion"
    _bout(sim, p)
    assert sim.sc(p, "ar.rank") == 2 and sim.sc(p, "ar.wins") == 0
    assert sim.gives[p.uuid] == [("cobblemon:choice_band", 1)]
    sim.click(p, "floor_ring")
    assert sim.mine(p)[0].cls == "cobblers:arena_rank_2"


def test_a_loss_keeps_the_rank_holds_the_blackout_tag_until_cleared_and_costs_nothing(pack):
    sim = Sim(pack)
    p = sim.player(adv=[GYM8])
    sim.click(p, "floor_ring")
    sim.tick(AR.GO_TICKS)
    sim.result(p, False)
    # the blackout callback runs in the same event: the tag must still be on the player
    assert "cobblers.arena_bout" in p.tags and sim.money.get(p.uuid, 0) == 0
    sim.tick(AR.END_TICKS)
    assert sim.sc(p, "ar.rank") == 1 and not sim.mine(p) and "cobblers.arena_bout" not in p.tags


def test_a_gauntlet_chains_legs_without_a_heal_and_a_clear_counts_once(pack):
    sim = Sim(pack)
    p = sim.player(adv=[GYM8])
    sim.scores[(p.uuid, "ar.id")] = 7
    sim.scores[(p.uuid, "ar.rank")] = 3
    sim.click(p, "floor_ring")
    legs = RANKS[3]["legs"]
    for leg in range(legs):
        assert len(sim.mine(p)) == 1 and sim.mine(p)[0].cls == "cobblers:arena_rank_3", leg
        _bout(sim, p)
    assert sim.heals[p.uuid] == 1, "healed at the run's start only"
    assert sim.sc(p, "ar.wins") == 1 and not sim.mine(p) and sim.sc(p, "ar.live") == 0
    assert sim.money[p.uuid] == legs * RANKS[3]["purse"]["typical_per_leg"] + RANKS[3]["purse"]["clear_bonus"]


def test_a_gauntlet_loss_ends_the_run_and_legs_already_won_keep_their_purse(pack):
    sim = Sim(pack)
    p = sim.player(adv=[GYM8])
    sim.scores[(p.uuid, "ar.id")] = 3
    sim.scores[(p.uuid, "ar.rank")] = 3
    sim.click(p, "floor_ring")
    _bout(sim, p, True)
    _bout(sim, p, False)
    assert sim.sc(p, "ar.wins") in (None, 0) and sim.money[p.uuid] == RANKS[3]["purse"]["typical_per_leg"]
    assert not sim.mine(p) and sim.sc(p, "ar.live") == 0


def test_the_relay_exam_is_odell_then_nessa_with_no_heal_between(pack):
    sim = Sim(pack)
    p = sim.player(adv=[GYM8])
    sim.scores[(p.uuid, "ar.rank")] = 3
    sim.scores[(p.uuid, "ar.wins")] = RANKS[3]["advance"]["clears_at_rank"]
    sim.click(p, "floor_ring")
    seen = []
    for _ in range(2):
        seen.append(sim.mine(p)[0].cls)
        _bout(sim, p)
    assert seen == ["cobblers:arena_exam_arena_tier_1_champion", "cobblers:arena_exam_arena_tier_2_champion"]
    assert sim.heals[p.uuid] == 1 and sim.sc(p, "ar.rank") == 4


def test_playing_down_two_ranks_is_an_exhibition_and_counts_nothing(pack):
    sim = Sim(pack)
    p = sim.player(adv=[GYM8, LANCE, CHAMP])
    sim.scores[(p.uuid, "ar.rank")] = 7
    sim.click(p, "door_ring")                 # offers 3-6: the highest the player holds is 6
    assert sim.mine(p)[0].cls == "cobblers:arena_rank_6"
    sim.call("arena/lose_run", p)
    p.pos = [3580.0, 20.0, 3200.0]
    sim.click(p, "floor_ring")                # 1-3: rank 3, four below
    assert sim.sc(p, "ar.exh") == 1
    _bout(sim, p)
    assert sim.money[p.uuid] == pytest.approx(RANKS[3]["purse"]["typical_per_leg"] / 4, abs=25)
    assert sim.sc(p, "ar.wins") in (None, 0) and sim.sc(p, "ar.rank") == 7


def test_the_champion_door_waits_for_lance(pack):
    sim = Sim(pack)
    p = sim.player(pos=(3620, 20, 3200), adv=[GYM8])
    sim.scores[(p.uuid, "ar.rank")] = 4
    sim.click(p, "door_ring")
    assert sim.mine(p)[0].cls == "cobblers:arena_rank_3", "rank 4 is closed without Lance: play down to 3"
    q = sim.player(pos=(3660, 20, 3200), adv=[GYM8])
    sim.click(q, "crown_ring")
    assert not sim.mine(q) and sim.sc(q, "ar.live") in (None, 0)


def test_a_postgame_newcomer_goes_straight_to_the_exam(pack):
    sim = Sim(pack)
    p = sim.player(adv=[GYM8, LANCE, CHAMP])
    sim.click(p, "floor_ring")
    assert sim.mine(p)[0].cls == "cobblers:arena_exam_arena_tier_1_champion"


def test_two_players_each_get_their_own_opponent_and_result(pack):
    sim = Sim(pack)
    p = sim.player(pos=(3580, 20, 3200), adv=[GYM8])
    q = sim.player(pos=(3620, 20, 3200), adv=[GYM8])
    sim.scores[(q.uuid, "ar.rank")] = 3          # the fixture's door ring opens at rank 3
    sim.click(p, "floor_ring")
    sim.click(q, "door_ring")
    assert len(sim.mine(p)) == len(sim.mine(q)) == 1 and sim.mine(p)[0] is not sim.mine(q)[0]
    sim.tick(AR.GO_TICKS)
    sim.result(p, True)
    sim.result(q, False)
    sim.tick(AR.END_TICKS)
    assert sim.sc(p, "ar.wins") == 1 and sim.sc(q, "ar.wins") in (None, 0)
    assert sim.money.get(q.uuid, 0) == 0 and sim.money[p.uuid] > 0


def test_a_busy_venue_refuses_a_second_player(pack):
    sim = Sim(pack)
    p = sim.player(adv=[GYM8])
    q = sim.player(adv=[GYM8])
    sim.click(p, "floor_ring")
    sim.click(q, "floor_ring")
    assert len(sim.npcs()) == 1 and not sim.mine(q)


def test_a_second_click_while_live_spawns_nothing(pack):
    sim = Sim(pack)
    p = sim.player(adv=[GYM8])
    sim.click(p, "floor_ring")
    sim.click(p, "floor_ring")
    assert len(sim.mine(p)) == 1


def test_a_refused_start_clears_the_opponent_and_the_run(pack):
    sim = Sim(pack)
    sim.refuse = True
    p = sim.player(adv=[GYM8])
    sim.click(p, "floor_ring")
    sim.tick(AR.GO_TICKS)
    assert not sim.mine(p) and sim.sc(p, "ar.live") == 0 and "cobblers.arena_bout" not in p.tags


def test_an_abandoned_bout_is_found_by_the_sweep(pack):
    sim = Sim(pack)
    p = sim.player(adv=[GYM8])
    sim.click(p, "floor_ring")
    sim.tick(AR.GO_TICKS)
    sim.in_battle.clear()                         # a flee: the battle ends with no result
    sim.tick(AR.SWEEP_TICKS * (AR.IDLE_SWEEPS + 1))
    assert not sim.mine(p) and sim.sc(p, "ar.live") == 0


def test_a_bout_in_battle_is_never_swept(pack):
    sim = Sim(pack)
    p = sim.player(adv=[GYM8])
    sim.click(p, "floor_ring")
    sim.tick(AR.GO_TICKS + AR.SWEEP_TICKS * 5)
    assert sim.mine(p) and sim.sc(p, "ar.live") == 1


def test_an_owner_who_walks_off_leaves_an_orphan_the_sweep_kills(pack):
    sim = Sim(pack)
    p = sim.player(adv=[GYM8])
    sim.click(p, "floor_ring")
    sim.tick(AR.GO_TICKS)
    p.pos = [0.0, 70.0, 0.0]
    sim.tick(AR.SWEEP_TICKS)
    assert not sim.mine(p)
    p.pos = [3580.0, 20.0, 3200.0]
    sim.click(p, "floor_ring")                    # the stale run is repaired, a new bout starts
    assert len(sim.mine(p)) == 1


def test_leaving_the_server_mid_run_loses_the_run_on_return(pack):
    sim = Sim(pack)
    p = sim.player(adv=[GYM8])
    sim.click(p, "floor_ring")
    sim.scores[(p.uuid, "ar.left")] = 1
    sim.tick()
    assert not sim.mine(p) and sim.sc(p, "ar.live") == 0 and sim.get(p.uuid, "ar.left") is None


def test_leaving_the_venue_between_legs_ends_the_run(pack):
    sim = Sim(pack)
    p = sim.player(adv=[GYM8])
    sim.scores[(p.uuid, "ar.rank")] = 3
    sim.click(p, "floor_ring")
    sim.tick(AR.GO_TICKS)
    sim.result(p, True)
    p.pos[0] += 40
    sim.tick(AR.END_TICKS)
    assert not sim.mine(p) and sim.sc(p, "ar.live") == 0


def _streak(n, st):
    """The streak's (level, members) after n wins, straight from the rank's own words in the data."""
    lv = min(st["level_start"] + st["level_step"] * (n // st["level_step_every_wins"]), st["level_max"])
    full = next(k for k in range(1000) if st["level_start"] + st["level_step"] * (k // st["level_step_every_wins"])
                >= st["level_max"])
    mem = min(st["members_start"] + max(0, n - full) // 6, 6)
    return lv, mem


@pytest.mark.parametrize("wins", [0, 1, 3, 32, 33, 38, 39, 51, 80])
def test_the_streak_climbs_by_the_rules_in_the_data(pack, wins):
    sim = Sim(pack)
    p = sim.player(pos=(3660, 20, 3200), adv=[GYM8, LANCE, CHAMP])
    sim.scores[(p.uuid, "ar.rank")] = 9
    sim.click(p, "crown_ring")
    for _ in range(wins):
        _bout(sim, p)
    lv, mem = _streak(wins, RANKS[9]["streak"])
    (n,) = sim.mine(p)
    assert n.cls == "cobblers:arena_streak_m%d" % mem and n.level + (mem - 1) == lv, (wins, n.cls, n.level)
    assert sim.sc(p, "ar.streak") == wins and (sim.sc(p, "ar.best") or 0) == wins


def test_a_streak_pays_its_bonus_and_milestone_and_a_loss_resets_it(pack):
    sim = Sim(pack)
    p = sim.player(pos=(3660, 20, 3200), adv=[GYM8, LANCE, CHAMP])
    sim.scores[(p.uuid, "ar.rank")] = 9
    sim.click(p, "crown_ring")
    for _ in range(10):
        _bout(sim, p)
    want = 0
    for k in range(10):
        lv, m = _streak(k, RANKS[9]["streak"])
        # to the nearest 50, an exact half down: the designer's own rank 8 figure (13 x 225 = 2925 typed as 2900)
        want += (13 * (m * lv - m * (m - 1) // 2) + 24) // 50 * 50
    want += 2 * RANKS[9]["purse"]["every_5th_win_bonus"]
    assert sim.money[p.uuid] == want
    assert ("obc:bottle_cap_gold", 1) in sim.gives[p.uuid]
    _bout(sim, p, False)
    assert sim.sc(p, "ar.streak") == 0 and sim.sc(p, "ar.best") == 10 and not sim.mine(p)


# ================================================================== the level cap (sweep U54, review N57)
#
# An arena opponent is a cobblemon:npc, which rctmod's own over-cap refusal (TrainerMob.canBattleAgainst) never
# reaches, so the challenge runs the level-cap pack's battle_check first. The rule is rctmod's own: a party whose
# HIGHEST level is strictly over the player's RCT cap is refused, at the cap is matched. Written by the test author
# (not the builder of 85be563); the cap and the party are set by the test, the pack's text is executed. The mutants
# change a GENERATOR's source (tools/levelcap_pack.py or tools/arena_runtime.py) with data/ untouched.
#
# Not covered (needs a server): that `rctmod player get level_cap @s` returns the cap as its result; that
# q.player.party.highest_level answers inside runmolang; that a tag set by a nested q.run_command is visible to the
# next line of the same function.

def _module(src, name, file):
    mod = types.ModuleType(name)
    mod.__file__ = str(file)
    exec(compile(src, name, "exec"), mod.__dict__)
    return mod


def _mutant(src, old, new, name, file):
    assert src.count(old) == 1, "mutant no longer matches %s: re-aim it (%r)" % (file.name, old[:70])
    return _module(src.replace(old, new), name, file)


def lc_mutant(old, new):
    """The level-cap pack's files as a mutated tools/levelcap_pack.py emits them for data/level_cap.json."""
    return _mutant(LC_SRC, old, new, "levelcap_pack_mutant", ROOT / "tools" / "levelcap_pack.py").files(LEVEL_CAP)


def ar_mutant(old, new):
    """The arena pack as a mutated tools/arena_runtime.py emits it for the fixture dome."""
    return _mutant(AR_SRC, old, new, "arena_runtime_mutant", ROOT / "tools" / "arena_runtime.py").files(FIXTURE)


def challenge(pack, levelcap=None, cap=50, top=50, tags=()):
    """One rank-1 player clicks the floor ring; returns (sim, player, matched) -- matched: an opponent of theirs
    stands and, after the start delay, their battle started."""
    sim = Sim(pack, levelcap)
    p = sim.player(adv=[GYM8], cap=cap, top=top)
    p.tags |= set(tags)
    sim.click(p, "floor_ring")
    spawned = bool(sim.mine(p))
    sim.tick(AR.GO_TICKS)
    return sim, p, spawned and any(u == p.uuid for u, _c, _l in sim.started)


def told_cap(sim, p):
    """The tellraw lines to p that show a score: (objective, the score the message would display)."""
    out = []
    for who, line in sim.said:
        if who == p.uuid:
            for obj in re.findall(r'"objective":"([^"]+)"', line):
                out.append((obj, sim.get(p.uuid, obj)))
    return out


# Protects: an over-cap party is refused BEFORE anything is spawned, healed or started, and is told its cap (the
# message's score is the player's RCT cap, 30 here). If removed, a level-100 Pokemon fights a rank-1 opponent again
# (the owner, in game, 2026-10-06) and nothing in the suite says so.
def test_an_over_cap_party_is_refused_before_anything_spawns_and_is_told_its_cap(pack):
    sim, p, matched = challenge(pack, cap=30, top=31)
    assert not matched and not sim.npcs() and not sim.started
    assert sim.heals.get(p.uuid, 0) == 0 and sim.sc(p, "ar.live") in (None, 0) and "cobblers.arena_bout" not in p.tags
    assert any(v == 30 for _o, v in told_cap(sim, p)), told_cap(sim, p)


# Protects: the boundary is rctmod's -- strictly over is refused, AT the cap (and under it) is matched. If removed, an
# off-by-one would refuse every player who has levelled exactly to the cap, which is most of them before each gym.
@pytest.mark.parametrize("top", [29, 30])
def test_a_party_at_or_under_the_cap_is_matched(pack, top):
    _sim, _p, matched = challenge(pack, cap=30, top=top)
    assert matched


# Protects: NO TRAP. A refused player who puts the over-cap Pokemon away is matched on the very next click. If
# removed, a check that latched its refusal (a tag it never re-evaluates) could lock a player out of the arena.
def test_a_refused_player_is_matched_once_the_party_is_back_under_the_cap(pack):
    sim = Sim(pack)
    p = sim.player(adv=[GYM8], cap=30, top=45)
    sim.click(p, "floor_ring")
    assert not sim.mine(p)
    p.top = 30
    sim.click(p, "floor_ring")
    sim.tick(AR.GO_TICKS)
    assert sim.mine(p) and [u for u, _c, _l in sim.started] == [p.uuid]


def _refusal_tags(pack):
    sim, p, _m = challenge(pack, cap=30, top=31)
    tags = set(p.tags)
    assert tags, "the refusal left no tag: the stale-tag test below has nothing to exercise"
    return tags


# Protects: NO TRAP from a stale answer. Whatever tag a refusal leaves on a player (read from the run above, not from
# the builder's constant) never refuses that player later when the party is under the cap -- whether the cap reads or
# not. If removed, a tag left by an old refusal (or by the over-cap notice, which shares it) could refuse a player
# whose party is fine, and nothing would clear it.
@pytest.mark.parametrize("cap", [30, None])
def test_a_stale_refusal_tag_never_refuses_an_under_cap_player(pack, cap):
    _sim, p, matched = challenge(pack, cap=cap, top=20, tags=_refusal_tags(pack))
    assert matched, (cap, p.tags)


# Protects: the chosen direction when the cap cannot be read (rctmod still loading, the command failing): the
# challenge goes ahead, as a catch does. A check that failed CLOSED would refuse every player at every venue -- and
# the HQ's Brann and Elara, who gate the finale -- for as long as the read fails. If removed, a change to fail-closed
# (a trap for everyone) would pass unseen.
def test_a_cap_that_cannot_be_read_lets_the_challenge_through(pack):
    _sim, _p, matched = challenge(pack, cap=None, top=100)
    assert matched


# Protects: nothing changes for an under-cap player: matched, healed once, started, no message about the cap and no
# tag but the bout's own. If removed, the check could start talking to (or tagging) every challenger.
def test_an_under_cap_challenge_is_unchanged_by_the_check(pack):
    sim, p, matched = challenge(pack, cap=60, top=40)
    assert matched and sim.heals[p.uuid] == 1 and p.tags == {"cobblers.arena_bout"}
    assert not any("level cap" in line for who, line in sim.said if who == p.uuid)


# FINDING (test-author, U54): only the CHALLENGE is checked. A gauntlet's later legs (and every streak bout after the
# first) start from arena/after -> bout/start with no battle_check, so a party that goes over the cap between legs
# (experience from the leg just won, if the cap does not stop it; or a party swap within the venue range) fights on.
# Strict xfail: when the builder re-checks each leg, this XPASSes and fails -- then drop the marker.
@pytest.mark.xfail(strict=True, reason="U54 finding: a gauntlet's later legs are not re-checked against the cap")
def test_an_over_cap_party_is_refused_at_every_gauntlet_leg(pack):
    sim = Sim(pack)
    p = sim.player(adv=[GYM8], cap=30, top=30)
    sim.scores[(p.uuid, "ar.rank")] = 3
    sim.click(p, "floor_ring")
    assert RANKS[3]["legs"] > 1 and sim.mine(p)
    sim.tick(AR.GO_TICKS)
    sim.result(p, True)
    p.top = 31                                  # over the cap before the next leg
    sim.tick(AR.END_TICKS + AR.GO_TICKS)
    assert not sim.mine(p) and len(sim.started) == 1


# ---- mutants: the GENERATOR changes, data/ does not, and a property above must fail

# Protects: INDEPENDENCE of the boundary test. tools/levelcap_pack.py comparing `>=` (at-or-over) must refuse a party
# AT the cap; if this passes, the boundary test is not reading the emitted comparison.
def test_mutation_at_or_over_refuses_a_party_at_the_cap(pack):
    lc = lc_mutant("highest_level > $(cap)", "highest_level >= $(cap)")
    assert challenge(pack, cap=30, top=30)[2] and not challenge(pack, lc, cap=30, top=30)[2]


# Protects: INDEPENDENCE of the no-trap test. battle_check without its clear-first line keeps an old refusal when the
# cap does not read: the stale-tag property must fail under it.
def test_mutation_no_clear_first_traps_a_stale_tag(pack):
    tags = _refusal_tags(pack)
    lc = lc_mutant('"tag @s remove %s" % PARTY_OVER,\n            "scoreboard players set @s %s 0" % CAP,',
                   '"scoreboard players set @s %s 0" % CAP,')
    assert challenge(pack, cap=None, top=20, tags=tags)[2]
    assert not challenge(pack, lc, cap=None, top=20, tags=tags)[2]


# Protects: INDEPENDENCE of the fail-open test. battle_check tagging the player when the cap does not read (fail
# closed) must refuse the unreadable-cap challenge.
def test_mutation_fail_closed_refuses_when_the_cap_cannot_be_read(pack):
    old = ('"$execute store result score @s %s run rctmod player get level_cap @s$(x)" % CAP,\n'
           '            "execute unless score @s %s matches 1.. run return 0" % CAP,')
    new = ('"$execute store result score @s %s run rctmod player get level_cap @s$(x)" % CAP,\n'
           '            "execute unless score @s %s matches 1.. run tag @s add %s" % (CAP, PARTY_OVER),\n'
           '            "execute unless score @s %s matches 1.. run return 0" % CAP,')
    assert not challenge(pack, lc_mutant(old, new), cap=None, top=20)[2]


# Protects: INDEPENDENCE of the refusal test. tools/arena_runtime.py reading a tag the check never sets must let the
# over-cap party through, so the refusal test is reading the arena's own guard line.
def test_mutation_arena_ignores_the_check(pack):
    mut = ar_mutant('"execute if entity @s[tag=%s] run return run tellraw', '"execute if entity @s[tag=%s_x] run return run tellraw')
    assert not challenge(pack, cap=30, top=31)[2] and challenge(mut, cap=30, top=31)[2]
