"""A player who logs out in Kyogre's cage and comes back is not left sealed in barrier (tools/kyogre_cave.py `tick` /
`rejoin_out`, data/kyogre_cave.json keeper.left_objective).

Kyogre's cage (`ky/close`) fills barrier over 242 cells a player can stand in once Kyogre is awake, and its guard sees only
ONLINE players, so a player who logged out on the dais came back inside the barrier (KYOGRE_CAVE.md: that must never happen;
tools/kyogre_rayquaza_audit.py `kyogre.cage_never_encloses_a_walkable_cell` is the static statement of the same fault).

These tests RUN the generated runtime functions on tests/mcfunction_sim.py's interpreter (extended below with only what the
Kyogre pack asks of it: `execute in`, the scores/gamemode/advancements selector filters, the box selector's hitbox, `scoreboard
players reset`, `gamemode`, `advancement`, `schedule`, and a `fill ... replace` that writes a block map). They run from the
generator's own plan, so they need the canonical heightmap and skip, with the reason, when it is unavailable.

What this does NOT cover: whether leave_game increments in a real server, how fast a rejoiner is caught (up to one keeper
pass, 40 ticks, in which they stand in barrier), or a player who was already offline in the box when the pack first loaded
(no score). Those are staging checks.
"""
from __future__ import annotations

import importlib.util
import json
import re
import sys
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tests"))

import kyogre_cave as K  # noqa: E402
import mcfunction_sim as S  # noqa: E402

BARRIER = "minecraft:barrier"
FN = K.F + "/"


class KyogreWorld(S.World):
    """mcfunction_sim.World plus the few things the Kyogre pack's keeper uses that the base model lacks."""

    def __init__(self, functions, **kw):
        super().__init__(functions, **kw)
        self.cells = {}
        self.big_fills = []
        self.schedules = []

    # -- players: logging out takes the player out of every selector and counts the leave_game statistic
    def player(self, pos, mode="survival", flags=(), tags=(), name="p"):
        e = self.add_player(pos, name)
        e.mode, e.flags = mode, set(flags)
        e.tags |= set(tags)
        return e

    def logout(self, e):
        e.alive = False
        key = ("e%d" % e.uid, "kc.left")
        self.scores[key] = self.scores.get(key, 0) + 1          # minecraft.custom:minecraft.leave_game

    def login(self, e):
        e.alive = True

    # -- blocks
    def block_at(self, x, y, z):
        return self.cells.get(tuple(int(v // 1) for v in (x, y, z)), "minecraft:air")

    def c_fill(self, rest, ctx):
        t = rest.split()
        a, b = self.coords(t[0:3], ctx), self.coords(t[3:6], ctx)
        lo = [int(min(a[i], b[i]) // 1) for i in range(3)]
        hi = [int(max(a[i], b[i]) // 1) for i in range(3)]
        vol = (hi[0] - lo[0] + 1) * (hi[1] - lo[1] + 1) * (hi[2] - lo[2] + 1)
        self._log((self.tick_no, "fill", (a, b, t[6:])))
        if vol > 5000:
            self.big_fills.append(rest)                          # not modelled; a test that cares asserts there are none
            return 1
        block, flt = t[6], (t[8] if len(t) > 8 and t[7] == "replace" else None)
        n = 0
        for x in range(lo[0], hi[0] + 1):
            for y in range(lo[1], hi[1] + 1):
                for z in range(lo[2], hi[2] + 1):
                    if flt is None or self.cells.get((x, y, z), "minecraft:air") == flt:
                        self.cells[(x, y, z)] = block
                        n += 1
        return n

    # -- commands
    def c_gamemode(self, rest, ctx):
        mode, sel = rest.split()
        ents = self.select(sel, ctx)
        for e in ents:
            e.mode = mode
        return len(ents)

    def c_advancement(self, rest, ctx):
        t = rest.split()
        ents = self.select(t[1], ctx)
        for e in ents:
            (e.flags.add if t[0] == "grant" else e.flags.discard)(t[-1])
        return len(ents)

    def c_schedule(self, rest, ctx):
        self.schedules.append(rest)
        return 1

    def c_scoreboard(self, rest, ctx):
        t = rest.split()
        if t[:2] == ["players", "reset"]:
            for e in self.select(t[2], ctx):
                self.scores.pop(("e%d" % e.uid, t[3]), None)
            return 1
        return super().c_scoreboard(rest, ctx)

    def c_return(self, rest, ctx):
        if rest.startswith("run "):                              # `return run <command>`: that command's result, then stop
            try:
                r = self.command(rest[4:], ctx)
            except S.Failed:
                r = 0
            raise S.Return(int(r or 0))
        return super().c_return(rest, ctx)

    def c_execute(self, rest, ctx):
        toks, out, i = rest.split(" "), [], 0
        while i < len(toks):                                     # `in <dimension>`: one dimension is modelled
            if toks[i] == "run":
                out += toks[i:]
                break
            if toks[i] == "in":
                i += 2
                continue
            out.append(toks[i])
            i += 1
        return self._execute(out, 0, ctx, [])

    # -- selectors: scores, gamemode, advancements and the box (x/y/z + dx/dy/dz meets the entity's hitbox)
    def select(self, sel, ctx, single=False):
        m = re.match(r"@([aepsr])(?:\[(.*)\])?$", sel)
        if not m or not m.group(2):
            return super().select(sel, ctx, single)
        args = S._args(m.group(2))
        extra = [(k, v) for k, v in args if k in ("scores", "gamemode", "advancements")]
        box = {k: float(v) for k, v in args if k in ("x", "y", "z", "dx", "dy", "dz")}
        has_box = any(k in box for k in ("dx", "dy", "dz"))
        keep = [(k, v) for k, v in args if k not in ("scores", "gamemode", "advancements")
                and not (has_box and k in ("x", "y", "z", "dx", "dy", "dz"))]
        body = ",".join("%s=%s" % kv for kv in keep)
        pool = super().select("@%s%s" % (m.group(1), "[%s]" % body if body else ""), ctx, single)
        out = []
        for e in pool:
            ok = True
            for k, v in extra:
                if k == "gamemode":
                    neg = v.startswith("!")
                    ok &= (getattr(e, "mode", "survival") == v.lstrip("!")) != neg
                elif k == "scores":
                    for obj, rng in re.findall(r"([\w.]+)=([-\d.]+)", v.strip("{}")):
                        got = self.scores.get(("e%d" % e.uid, obj))
                        lo, hi = S._range(rng)
                        ok &= got is not None and lo <= got <= hi
                else:
                    for adv, val in re.findall(r"([a-z0-9_:/.]+)=(true|false)", v):
                        ok &= (adv in getattr(e, "flags", set())) == (val == "true")
            if has_box:
                ox, oy, oz = (box.get(a, c) for a, c in zip("xyz", ctx.pos))
                dx, dy, dz = (box.get(a, 0.0) for a in ("dx", "dy", "dz"))
                px, py, pz = e.pos
                h, ht = 0.3, 1.8
                ok &= (px - h < ox + dx + 1 and px + h > ox and py < oy + dy + 1 and py + ht > oy
                       and pz - h < oz + dz + 1 and pz + h > oz)
            if ok:
                out.append(e)
        return out


# ------------------------------------------------------------------------------------------------ the pack, as generated

@pytest.fixture(scope="module")
def doc():
    return K.load()


@pytest.fixture(scope="module")
def plan(doc):
    try:
        import ground as G
        return K.plan(doc, G.Ground())
    except (FileNotFoundError, OSError) as e:                    # no canonical heightmap in this checkout
        pytest.skip("the heightmap is unavailable: %s" % e)


def _functions(doc, plan, module=K):
    fns, _adv, _other = module.runtime_files(doc, plan["M"], plan["arch"], len(plan["reef"]))
    return {FN + k: v for k, v in fns.items()}


@pytest.fixture(scope="module")
def fns(doc, plan):
    return _functions(doc, plan)


def _mutated_module(drop):
    """tools/kyogre_cave.py with every source line containing `drop` removed, loaded as a separate module (the mutation is
    in the generator's code; the authored data is untouched)."""
    path = ROOT / "tools" / "kyogre_cave.py"
    lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    kept = [ln for ln in lines if drop not in ln]
    assert len(kept) < len(lines), "the mutation matched nothing: %r" % drop
    mod = types.ModuleType("kyogre_cave_mutant")
    mod.__file__ = str(path)
    exec(compile("".join(kept), str(path), "exec"), mod.__dict__)
    return mod


# ------------------------------------------------------------------------------------------------ the scenario

class Scene:
    def __init__(self, doc, plan, fns):
        self.doc, self.arch = doc, plan["arch"]
        ky, g = doc["kyogre"], doc["gate"]
        self.cage = ky["cage"]
        self.dais = (self.cage[0] + 3.5, self.cage[1], self.cage[2] + 3.5)             # a cell in the cage box
        sx, sy, sz = ky["spot"]
        self.lip = (doc["rooms"]["basin"]["causeway"][0] - 1 + 0.5, sy, sz + 0.5)       # the Basin's west lip, outside the cage
        self.ante = doc["rooms"]["antechamber"]["arrive"]
        self.dive = json.loads((ROOT / "data" / "portals.json").read_text(encoding="utf-8"))["gates"]["dive"]["tag"]
        self.adv = ["cobblers:flag/%s" % g["flags"][0], g["advancement"]]
        w = self.w = KyogreWorld(fns)
        w.function(FN + "load", w.server())
        for h, v in (("built", 1), ("awake", 1), ("cage", 0)):
            w.scores[("#%s" % h, doc["keeper"]["objective"])] = v
        self.kyogre = S.Entity("cobblemon:pokemon", (sx + 0.5, sy, sz + 0.5), tags=[ky["tag"], "cobblers.guardian_exempt"])
        w.add(self.kyogre)

    def qualified(self, pos, adventure=True):
        p = self.w.player(pos, mode="adventure" if adventure else "survival", flags=self.adv,
                          tags=[self.dive] + (["cobblers.kc.adv"] if adventure else []))
        return p

    def pass_(self, n=1):
        for _ in range(n):
            self.w.tick_no += 40
            self.w.function(FN + "tick", self.w.server())

    def score(self, h):
        return self.w.scores.get(("#" + h, self.doc["keeper"]["objective"]))

    def way_out(self):
        s = self.arch["stand"]
        return (s[0] + 0.5, float(s[1]), s[2] + 0.5)


def scenario_logout_on_the_dais(doc, plan, fns):
    """P is on the dais with Kyogre awake and logs out; B waits in the antechamber until Kyogre sleeps, then walks to the
    lip, and the cage closes (P is offline, so the guard sees nobody); P logs in. Returns the observations."""
    sc = Scene(doc, plan, fns)
    w = sc.w
    p = sc.qualified(sc.dais)
    b = sc.qualified((sc.ante[0] + 0.5, sc.ante[1], sc.ante[2] + 0.5))
    w.logout(p)
    sc.pass_(4)                                   # B alone in the cave, out of the Basin: Kyogre goes back to sleep
    asleep = sc.score("awake") == 0
    b.pos = list(sc.lip)
    sc.pass_(2)                                   # B on the lip, nobody beside the cage: it closes
    cell = tuple(int(v // 1) for v in p.pos)
    closed = sc.score("cage") == 1 and w.block_at(*p.pos) == BARRIER
    w.login(p)
    on_login = tuple(p.pos)
    sc.pass_(1)                                   # the next keeper pass
    return {"sc": sc, "p": p, "asleep": asleep, "closed": closed, "cell": cell, "on_login": on_login,
            "cell_block": w.block_at(*cell)}


def test_a_player_who_logged_out_on_the_dais_is_put_at_the_way_out_not_left_in_barrier(doc, plan, fns):
    # Without the rejoin eject the player returns to the dais inside the barrier the cage closed over their offline body
    # (KYOGRE_CAVE.md: nobody is ever shut in); the cave's own arches are across the whole Basin.
    o = scenario_logout_on_the_dais(doc, plan, fns)
    sc, p = o["sc"], o["p"]
    assert o["asleep"] and o["closed"], "the setup must reach the defect: the cage closed over the offline player's cell"
    assert o["cell_block"] == BARRIER, "the cell they logged out in is still barrier"
    assert tuple(p.pos) == sc.way_out(), "the rejoiner must end at the arch's stand, not at %s" % (p.pos,)
    assert sc.w.block_at(*p.pos) != BARRIER
    assert p.mode == "survival" and "cobblers.kc.adv" not in p.tags, "the cave's adventure mode goes with them"
    assert ("e%d" % p.uid, "kc.left") not in sc.w.scores, "the logout count is cleared once seen"
    assert any(m.get("text") == doc["messages"]["rejoined"] for m in p.messages)


def test_a_rejoiner_in_the_cage_box_is_sent_out_before_the_keeper_runs_for_them(doc, plan, fns):
    # The eject must be the tick's first act: the guard, the gate sweep and the rescue all read where a player stands.
    lines = [l for l in fns[FN + "tick"] if l.strip() and not l.startswith("#")]
    assert "rejoin_out" in lines[1] and lines[0].startswith("schedule function"), lines[:3]
    assert all("rejoin_out" not in l for l in lines[2:])


@pytest.mark.parametrize("cage_open", [True, False])
def test_a_rejoiner_in_the_box_is_sent_out_whether_or_not_the_cage_is_closed(doc, plan, fns, cage_open):
    sc = Scene(doc, plan, fns)
    p = sc.qualified(sc.dais)
    sc.w.logout(p)
    sc.w.login(p)
    if not cage_open:
        sc.w.scores[("#cage", doc["keeper"]["objective"])] = 1
        sc.w.scores[("#awake", doc["keeper"]["objective"])] = 0
    sc.pass_(1)
    assert tuple(p.pos) == sc.way_out()


def test_a_rejoiner_outside_the_cage_box_stays_where_they_are_and_their_count_is_cleared(doc, plan, fns):
    sc = Scene(doc, plan, fns)
    p = sc.qualified(sc.lip)
    sc.w.logout(p)
    sc.w.login(p)
    sc.pass_(1)
    assert tuple(p.pos) == sc.lip, "only a player the cage can seal is moved"
    assert ("e%d" % p.uid, "kc.left") not in sc.w.scores


CORNERS = [(dx, dy, dz) for dx in (0.5, 10.5) for dy in (0, 3) for dz in (0.5, 10.5)]


@pytest.mark.parametrize("dx,dy,dz", CORNERS)
def test_the_cage_never_closes_over_a_player_standing_in_any_corner_of_its_box(doc, plan, fns, dx, dy, dz):
    # The online guard (`unless entity @a[cage box + 1]`) must cover every cell the fill writes; the corners are the
    # cells nearest its edge. Kyogre asleep, cage open, only the standing player in the Basin.
    sc = Scene(doc, plan, fns)
    c = sc.cage
    assert (c[3] - c[0], c[4] - c[1], c[5] - c[2]) == (10, 3, 10), "the corner list assumes the 11 by 4 by 11 cage"
    sc.w.scores[("#awake", doc["keeper"]["objective"])] = 0
    p = sc.qualified((c[0] + dx, c[1] + dy, c[2] + dz))
    sc.pass_(4)
    assert sc.score("cage") == 0 and sc.w.cells == {}, "the cage closed over a player at %s" % (p.pos,)
    assert tuple(p.pos) == (c[0] + dx, c[1] + dy, c[2] + dz)


def test_with_nobody_in_the_box_the_cage_does_close(doc, plan, fns):
    # The control for the test above: the same scene with the player on the lip closes the cage, so "never closes" is
    # the guard's doing and not a scene that cannot close.
    sc = Scene(doc, plan, fns)
    sc.w.scores[("#awake", doc["keeper"]["objective"])] = 0
    sc.qualified(sc.lip)
    sc.pass_(4)
    assert sc.score("cage") == 1
    c = sc.cage
    assert sc.w.block_at(c[0], c[1], c[2]) == BARRIER and sc.w.block_at(c[3], c[4], c[5]) == BARRIER


# ------------------------------------------------------------------------------------------------ the mutation

def test_a_generator_that_drops_the_eject_leaves_the_rejoiner_in_barrier(doc, plan):
    # Mutation of the GENERATOR (the tick's rejoin line removed from tools/kyogre_cave.py; data untouched): the scenario
    # must now end with the player still on the dais, in the barrier. Proves the tests above bite on the eject.
    mut = _mutated_module('run function %s/rejoin_out" % (dim, LO, box_sel(cage), F)')
    o = scenario_logout_on_the_dais(doc, plan, _functions(doc, plan, mut))
    p = o["p"]
    assert o["closed"]
    assert tuple(p.pos) != o["sc"].way_out()
    assert o["sc"].w.block_at(*p.pos) == BARRIER, "the mutant leaves the player sealed in"
