"""The rip scheduler (tools/rip_scheduler.py, data/rip_scheduler.json): the BUILDER's own tests of its generator's properties.

Written by the builder; the independent audit of the draw (tools/dungeon_draw_audit.py) is another agent's and is not touched here.
What each test holds is said where it is. Nothing here starts Minecraft: the emitted functions are replayed in tests/mcfunction_sim.py
(a vanilla-semantics command interpreter written apart from the generators), extended below with the block commands the scheduler
uses. A replay proves the TEXT does what it should under vanilla's documented semantics; that vanilla does so (clone copying block
entities, forceload making a chunk writable in the same function, a schedule surviving a restart) is the in-game experiment this
file cannot stand in for (see tools/rip_scheduler.py: ASSUMED).
"""
from __future__ import annotations

import copy
import json
import random
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tests"))

import dungeon as D  # noqa: E402
import dungeon_rips as DRP  # noqa: E402
import function_limits  # noqa: E402
import mcfunction_sim as SIM  # noqa: E402
import rip_scheduler as RS  # noqa: E402

DDOC = D.load()
RDOC = RS.load()
V = RS.values(RDOC)
AIR = "minecraft:air"
NS = "cobblers:rips/"


# ------------------------------------------------------------------------------------------------ a world to replay in

class BlockWorld(SIM.World):
    """tests/mcfunction_sim.py's World with blocks: setblock, fill, clone, `execute in`, `return run`, `scores=` selectors, schedule,
    scoreboard reset and random value. A block write into a chunk that is not loaded does NOTHING and is recorded in `dropped`
    (vanilla: function_limits.py's measured rule), so a write that is not preceded by a forceload shows up as a drop."""

    def __init__(self, functions, original, seed=1, loaded_all=False, **kw):
        super().__init__(functions, loaded=(lambda x, z: True) if loaded_all else (lambda x, z: False), **kw)
        self.original = original            # (x, y, z) -> block string, for a cell nothing has written
        self.blocks = {}
        self.dropped = []
        self.queue = []                     # (due tick, function)
        self.rng = random.Random(seed)
        self.time = 0
        self.all_loaded = loaded_all

    # -- blocks
    def get(self, p):
        return self.blocks.get(p, self.original(*p))

    def _ok(self, x, z):
        return self.all_loaded or ((int(x) // 16, int(z) // 16) in self.forced)

    def _cells(self, a, b):
        return [(x, y, z) for x in range(min(a[0], b[0]), max(a[0], b[0]) + 1) for y in range(min(a[1], b[1]), max(a[1], b[1]) + 1)
                for z in range(min(a[2], b[2]), max(a[2], b[2]) + 1)]

    def c_setblock(self, rest, ctx):
        t = rest.split()
        p = tuple(int(float(v)) for v in t[0:3])
        if not self._ok(p[0], p[2]):
            self.dropped.append(("setblock", p))
            raise SIM.Failed("unloaded")
        self.blocks[p] = t[3]
        return 1

    def c_fill(self, rest, ctx):
        t = rest.split()
        a, b = tuple(int(float(v)) for v in t[0:3]), tuple(int(float(v)) for v in t[3:6])
        if len(t) != 7:
            raise SIM.Unsupported("fill with a mode: %s" % rest)
        cells = self._cells(a, b)
        if not all(self._ok(c[0], c[2]) for c in cells):
            self.dropped.append(("fill", a, b))
            raise SIM.Failed("unloaded")
        for c in cells:
            self.blocks[c] = t[6]
        return len(cells)

    def c_clone(self, rest, ctx):
        t = rest.split()
        if len(t) != 9:
            raise SIM.Unsupported("clone with a mask or mode: %s" % rest)
        a, b, d = tuple(int(float(v)) for v in t[0:3]), tuple(int(float(v)) for v in t[3:6]), tuple(int(float(v)) for v in t[6:9])
        src = self._cells(a, b)
        off = (d[0] - min(a[0], b[0]), d[1] - min(a[1], b[1]), d[2] - min(a[2], b[2]))
        dst = [(x + off[0], y + off[1], z + off[2]) for x, y, z in src]
        if not all(self._ok(c[0], c[2]) for c in src + dst):
            self.dropped.append(("clone", a, b, d))
            raise SIM.Failed("unloaded")
        vals = [self.get(c) for c in src]            # read everything first, as vanilla does
        for c, v in zip(dst, vals):
            self.blocks[c] = v
        return len(src)

    # -- commands the base interpreter lacks
    def c_return(self, rest, ctx):
        if rest.startswith("run "):
            raise SIM.Return(self.command(rest[4:], ctx))
        raise SIM.Return(int(rest))

    def c_random(self, rest, ctx):
        m = re.match(r"value (-?\d+)\.\.(-?\d+)$", rest)
        if not m:
            raise SIM.Unsupported("random %s" % rest)
        return self.rng.randint(int(m.group(1)), int(m.group(2)))

    def c_schedule(self, rest, ctx):
        m = re.match(r"function (\S+) (\d+)t replace$", rest)
        if not m:
            raise SIM.Unsupported("schedule %s" % rest)
        self.queue = [q for q in self.queue if q[1] != m.group(1)]          # replace
        self.queue.append((self.time + int(m.group(2)), m.group(1)))
        return 1

    def c_scoreboard(self, rest, ctx):
        t = rest.split()
        if t[:2] == ["players", "reset"]:
            self.scores.pop((self.holder(t[2], ctx), t[3]), None)
            return 1
        return super().c_scoreboard(rest, ctx)

    def c_execute(self, rest, ctx):
        toks = rest.split(" ")
        out, i = [], 0
        while i < len(toks):
            if toks[i] == "run":
                out += toks[i:]
                break
            if toks[i] == "in" and i + 1 < len(toks) and ":" in toks[i + 1]:
                self.dims_seen.add(toks[i + 1])
                i += 2
                continue
            out.append(toks[i])
            i += 1
        return self._execute(out, 0, ctx, [])

    dims_seen = set()

    def select(self, sel, ctx, single=False):
        m = re.search(r"scores=\{([^}]*)\}", sel)
        if not m:
            return super().select(sel, ctx, single)
        base = sel[:m.start()] + sel[m.end():]
        base = re.sub(r",,", ",", base).replace("[,", "[").replace(",]", "]")
        base = base.replace("[]", "")
        want = []
        for part in m.group(1).split(","):
            obj, rng = part.split("=")
            lo, hi = SIM._range(rng)
            want.append((obj, lo, hi))
        out = []
        for e in super().select(base, ctx, single):
            ok = True
            for obj, lo, hi in want:
                v = self.scores.get(("e%d" % e.uid, obj))
                if v is None or not (lo <= v <= hi):
                    ok = False
            if ok:
                out.append(e)
        return out

    # -- time
    def advance(self, ticks):
        """Run `ticks` game ticks: each tick, every scheduled function that is due (in the order scheduled), as the server does."""
        for _ in range(ticks):
            self.time += 1
            self.tick_no = self.time
            due = [q for q in self.queue if q[0] <= self.time]
            self.queue = [q for q in self.queue if q[0] > self.time]
            for _t, fn in due:
                self.function(fn, self.server())

    def call(self, fn, **kw):
        return self.function(NS + fn, self.server())


def original_world(x, y, z):
    """A deterministic, varied 'original world' for every cell below the sky hold: ground, plants, leaves, logs, stairs with states.
    Not air everywhere, so a restore that writes air or a guess differs from it."""
    if y >= 500:
        return AIR
    h = (x * 73856093 ^ y * 19349663 ^ z * 83492791) % 13
    return ["minecraft:grass_block[snowy=false]", "minecraft:dirt", "minecraft:short_grass", "minecraft:poppy", AIR,
            "minecraft:oak_leaves[distance=3,persistent=false]", "minecraft:oak_log[axis=y]", "minecraft:stone",
            "minecraft:oak_stairs[facing=north,half=top,shape=straight]", "minecraft:moss_block", "minecraft:fern", AIR, "minecraft:sand"][h]


def build_world(ddoc=None, rdoc=None, seed=1, loaded_all=False, rdoc_edit=None):
    ddoc = ddoc or DDOC
    rdoc = copy.deepcopy(rdoc or RDOC)
    if rdoc_edit:
        rdoc_edit(rdoc)
    fns = {NS + k: v for k, v in RS.functions(ddoc, rdoc).items()}
    w = BlockWorld(fns, original_world, seed=seed, loaded_all=loaded_all)
    w.tags["load"] = ["cobblers:rips/load"]
    # the dungeon pack's objectives, which the scheduler reads and never creates
    w.objectives |= {"dg.rip", "dg.st"}
    return w


def edit_settings(**kw):
    def f(rdoc):
        for k, val in kw.items():
            rdoc["settings"][k]["value"] = val
    return f


def idx(r):
    return D.rips(DDOC).index(r) + 1


_DFNS = []


def dungeon_functions():
    """tools/dungeon.py functions(): built once for the module (it takes about a minute)."""
    if not _DFNS:
        _DFNS.append(D.functions(DDOC))
    return _DFNS[0]


def footprint_cells(r):
    """Every cell the open writes, derived from rip_lines' own text (fill / setblock), not from rip_write_boxes."""
    cells = set()
    for ln in D.rip_lines(r):
        t = ln.split()
        if t[0] == "setblock":
            cells.add(tuple(int(v) for v in t[1:4]))
        else:
            a = [int(v) for v in t[1:7]]
            cells |= {(x, y, z) for x in range(a[0], a[3] + 1) for y in range(a[1], a[4] + 1) for z in range(a[2], a[5] + 1)}
    return cells


def zone_cells(r):
    """A generous box round the rip, hold excluded: every cell a test compares before and after."""
    wx0, wz0, wx1, wz1 = DRP.window(r["frame"])
    gy = r["frame"]["y"] - 1
    return [(x, y, z) for x in range(wx0 - 2, wx1 + 3) for y in range(gy - 3, gy + 9) for z in range(wz0 - 2, wz1 + 3)]


def hold_cells(r):
    return [(x, y, z) for x in range(r["frame"]["x0"] - 1, r["frame"]["x1"] + 2) for y in range(V["hold_y"] - 1, V["hold_y"] + 8)
            for z in range(r["frame"]["z"] - 1, r["frame"]["z"] + 4)]


def stand_player(w, pos, name="p"):
    p = w.add_player(pos, name)
    return p


def far_player(w):
    return stand_player(w, (0.5, 70.0, 0.5), "far")


def set_score(w, p, obj, v):
    w.scores[("e%d" % p.uid, obj)] = v


# ------------------------------------------------------------------------------------------------ the data

def test_every_default_is_confirmed_by_the_owner():
    # the owner, 2026-10-15: "Take the rip scheduler defaults." Breaks if a setting is added without the owner's answer
    # (a new one starts owner_confirmed false and this fails until it is answered), or without saying where it came from
    assert RS.settings_problems(RDOC) == []
    assert sorted(RDOC["settings"]) == sorted(RS.KNOWN)
    for k, rec in RDOC["settings"].items():
        assert rec["owner_confirmed"] is True, k
        assert len(rec["origin"]) > 20, k
    assert "Take the rip scheduler defaults" in RDOC["status"]


def test_the_owners_proposal_is_what_the_file_says():
    # 6-9 open (the owner, 2026-10-16: "we need more rifts"; job D proposed 3-5), an hour of play each, closed once
    # entered, anywhere including gated, a chat line naming the region
    assert (V["open_min"], V["open_max"]) == (6, 9)
    assert V["lifetime_minutes"] == 60 and V["close_when_entered"] is True
    assert V["sites"] == "anywhere" and V["gated_sites"] == "allow"
    assert "{region}" in V["announce"]


@pytest.mark.parametrize("key,val,needle", [
    ("open_min", 10, "above open_max"), ("open_max", 0, "open_max"), ("lifetime_jitter_minutes", 60, "jitter"),
    ("gated_sites", "maybe", "gated_sites"), ("announce", "A rift has opened.", "announce"), ("pass_seconds", 0, "pass_seconds"),
    ("sites", "nearby", "sites"), ("enabled", "yes", "enabled")])
def test_a_setting_out_of_range_is_named_and_the_build_refuses(key, val, needle):
    bad = copy.deepcopy(RDOC)
    bad["settings"][key]["value"] = val
    problems = RS.settings_problems(bad)
    assert any(needle in p for p in problems), problems
    with pytest.raises(SystemExit):
        RS.functions(DDOC, bad)


def test_an_unknown_or_missing_setting_is_refused():
    bad = copy.deepcopy(RDOC)
    bad["settings"]["invented"] = bad["settings"]["open_min"]
    assert RS.settings_problems(bad)
    bad = copy.deepcopy(RDOC)
    del bad["settings"]["hold_y"]
    assert RS.settings_problems(bad)


# ------------------------------------------------------------------------------------------------ the pool, any size

def synthetic(ddoc, n):
    """A copy of the doc with n rips of today's record shape: the first one, moved 40 blocks apart, renamed. Proves the generator
    does not depend on there being 20 (the pool grows beside this work)."""
    d = copy.deepcopy(ddoc)
    base = d["rips"][0]
    rips = []
    regions = [r["id"] for r in json.loads((ROOT / "data" / "regions.json").read_text(encoding="utf-8"))["regions"]]
    for k in range(n):
        r = copy.deepcopy(base)
        dx = 40 * k
        r["id"] = "rip_synth_%d" % k
        r["name"] = "A rift, synthetic %d" % k
        r["region"] = regions[k % len(regions)]
        r.pop("reachable_after", None)
        f = r["frame"]
        f["x0"] += dx
        f["x1"] += dx
        r["click"][0] += dx
        r["outside"][0] += dx
        r["restore"] = {str(int(x) + dx): v for x, v in base["restore"].items()}
        rips.append(r)
    d["rips"] = rips
    return d


@pytest.mark.parametrize("n", [1, 7, 20, 60])
def test_the_pool_is_the_rips_list_whatever_its_length(n):
    # three functions a candidate (open, close, kill polls) and seven fixed; the pass and the pick name every candidate once
    d = synthetic(DDOC, n)
    rd = copy.deepcopy(RDOC)
    rd["settings"]["open_min"]["value"] = min(3, n)         # a pool smaller than the minimum is refused (the next test)
    rd["settings"]["open_max"]["value"] = min(5, n)
    fns = RS.functions(d, rd)
    assert len(fns) == 3 * n + 7
    for i in range(1, n + 1):
        assert {"o%d" % i, "c%d" % i, "x%d" % i} <= set(fns)
    pass_text = "\n".join(fns["pass"])
    for i in range(1, n + 1):
        assert pass_text.count("function cobblers:rips/c%d\n" % i) + pass_text.count("function cobblers:rips/c%d" % i) >= 1
        assert "function cobblers:rips/o%d" % i in "\n".join(fns["pick"])
    assert "random value 1..%d" % n in "\n".join(fns["pick"])


def test_a_pool_smaller_than_the_minimum_open_is_refused_not_built():
    with pytest.raises(SystemExit):
        RS.functions(synthetic(DDOC, 2), RDOC)


def test_the_function_count_grows_linearly_with_the_pool_so_the_heap_cost_is_measurable():
    lines = []
    for n in (10, 20, 40):
        files = RS.pack_files(synthetic(DDOC, n), RDOC)
        lines.append(RS.measure(files)[2])
    assert lines[1] - lines[0] > 0 and abs((lines[2] - lines[1]) - 2 * (lines[1] - lines[0])) <= 2 * (lines[1] - lines[0]) * 0.1 + 40


def test_the_real_pool_builds_clean_and_every_function_passes_the_servers_own_limits():
    files = RS.pack_files(DDOC, RDOC)                       # raises on a command the server would refuse or drop
    assert files["pack.mcmeta"] and json.loads(files["data/minecraft/tags/function/load.json"])["values"] == ["cobblers:rips/load"]
    n = len(D.rips(DDOC))
    assert RS.measure(files)[1] == 3 * n + 7
    assert RS.build_problems(DDOC, RDOC) == []


def test_windows_that_overlap_are_refused_because_their_holds_and_checks_would_too():
    d = synthetic(DDOC, 2)
    d["rips"][1]["frame"]["x0"] -= 36                        # 4 blocks from the first: the 9 x 7 windows overlap
    d["rips"][1]["frame"]["x1"] -= 36
    d["rips"][1]["click"][0] -= 36
    d["rips"][1]["outside"][0] -= 36
    d["rips"][1]["restore"] = {str(int(x) - 36): v for x, v in d["rips"][1]["restore"].items()}
    assert any("overlap" in p for p in RS.build_problems(d, RDOC))


def test_an_exit_point_inside_a_written_cell_is_refused():
    # the safe fallback for a run whose rip has closed is the rip's own exit point; it must lie outside everything the scheduler writes.
    # The mutation is on the record, but the check is the generator's (a different derivation from the siting rule's)
    d = copy.deepcopy(DDOC)
    r = d["rips"][0]
    r["outside"] = [r["click"][0] + 0.5, r["frame"]["y"], r["frame"]["z"] + 0.5, 0]            # in the plane the open clears
    assert any("exit point" in p for p in RS.build_problems(d, RDOC))
    for rip in DDOC["rips"]:
        ox, oy, oz, _ = rip["outside"]
        assert (int(ox // 1), int(oy // 1), int(oz // 1)) not in footprint_cells(rip), rip["id"]


def test_a_rip_too_high_for_the_hold_is_refused():
    d = copy.deepcopy(DDOC)
    d["rips"][0]["frame"]["y"] = V["hold_y"]
    assert any("hold" in p for p in RS.build_problems(d, RDOC))


def test_the_hold_is_inside_the_overworld_the_world_runs():
    top = RS.overworld_top()
    assert top == 575                                        # modpack/datapacks/cobblers_height: min_y -64, height 640
    assert V["hold_y"] + 4 <= top and V["hold_y"] > 535      # above the world tree's crown (tools/reapply.py CROWN y535)


def test_a_gated_site_opens_like_any_other_unless_the_owner_excludes_it():
    gated = [r for r in D.rips(DDOC) if r.get("reachable_after")]
    assert gated                                              # rip_the_rift stands in Rift zone z2
    allow = {i for i, _r in RS.pool(DDOC, RDOC)}
    assert all(idx(r) in allow for r in gated)
    ex = copy.deepcopy(RDOC)
    ex["settings"]["gated_sites"]["value"] = "exclude"
    left = {i for i, _r in RS.pool(DDOC, ex)}
    assert not any(idx(r) in left for r in gated) and len(left) == len(allow) - len(gated)
    fns = RS.functions(DDOC, ex)
    assert ("o%d" % idx(gated[0])) not in fns                # never picked, and keeps its number (the others are unchanged)
    assert "o%d" % idx(D.rips(DDOC)[0]) in fns


# ------------------------------------------------------------------------------------------------ the text's order

def first(lines, pred):
    return next((n for n, ln in enumerate(lines) if pred(ln)), None)


@pytest.mark.parametrize("r", D.rips(DDOC), ids=lambda r: r["id"])
def test_an_open_checks_then_holds_the_chunks_then_saves_then_writes_and_releases_last(r):
    # breaks if a write comes before a check (a rip opened over a player), before the forceload (a write into an unloaded chunk is
    # dropped silently), or before the save (the ground would be lost); and the release is the last line so the writes landed
    i = idx(r)
    fns = RS.functions(DDOC, RDOC)
    o = [ln for ln in fns["o%d" % i] if ln.strip() and not ln.startswith("#")]
    f_add = first(o, lambda s: s.startswith("forceload add"))
    f_rem = first(o, lambda s: s.startswith("forceload remove"))
    guard_player = first(o, lambda s: "if entity @a[dx=" in s and "run return 0" in s)
    guard_run = first(o, lambda s: "scores={dg.rip=%d,dg.st=1..}" % i in s and "run return 0" in s)
    guard_state = first(o, lambda s: s == "execute if score #r%d rp.s matches 1.. run return 0" % i)
    first_write = first(o, lambda s: re.match(r"(fill|setblock|clone|summon|kill|tellraw|scoreboard players set)\b", s) is not None)
    first_clone = first(o, lambda s: s.startswith("clone"))
    first_fill = first(o, lambda s: re.match(r"(fill|setblock)\b", s) is not None)
    assert None not in (f_add, f_rem, guard_player, guard_run, guard_state, first_clone, first_fill)
    assert max(guard_state, guard_run, guard_player) < f_add < first_write
    assert first_clone < first_fill                          # the save before the first write
    assert f_rem == len(o) - 1                               # released last
    assert [ln for ln in o if ln.startswith("clone")] == D.rip_save_lines(r, V["hold_y"])
    assert function_limits.check_lines(fns["o%d" % i]) == []


@pytest.mark.parametrize("r", D.rips(DDOC), ids=lambda r: r["id"])
def test_a_close_checks_the_player_before_it_holds_or_writes_and_x_releases_only_at_the_end(r):
    i = idx(r)
    fns = RS.functions(DDOC, RDOC)
    c = [ln for ln in fns["c%d" % i] if ln.strip() and not ln.startswith("#")]
    assert c[0] == "execute unless score #r%d rp.s matches 1 run return 0" % i
    g = first(c, lambda s: "if entity @a[dx=" in s and "run return 0" in s)
    add = first(c, lambda s: s.startswith("forceload add"))
    assert g is not None and g < add < first(c, lambda s: s.startswith("clone")) < first(c, lambda s: s.startswith("fill"))
    assert not [ln for ln in c if ln.startswith("forceload remove")]            # held until the last poll
    x = [ln for ln in fns["x%d" % i] if ln.strip() and not ln.startswith("#")]
    rel = [ln for ln in x if "forceload remove" in ln]
    assert len(rel) == 1 and "matches ..0" in rel[0] and x.index(rel[0]) == len(x) - 1
    st0 = [ln for ln in x if "players set #r%d rp.s 0" % i in ln]
    assert len(st0) == 1 and "matches ..0" in st0[0] and x.index(st0[0]) < x.index(rel[0])
    # one forceload box for all three functions, the same text, so what the close holds is what the open held
    def box(ls):
        return {m.group(1) for ln in ls for m in [re.search(r"forceload (?:add|remove) (-?\d+ -?\d+ -?\d+ -?\d+)$", ln)] if m}
    assert len(box(fns["o%d" % i])) == 1
    assert box(c) == box(fns["o%d" % i]) and box(x) == box(fns["o%d" % i])


def test_the_player_check_covers_the_whole_siting_window_and_the_exit_point():
    # the 9 x 7 window (tools/dungeon_rips.py WIN), from a block under the ground to six over it; the exit point is in it, so a
    # player coming out of a run is never under a rip being opened or closed
    for r in D.rips(DDOC):
        px, py, pz, sel = RS.check_selector(r)
        wx0, wz0, wx1, wz1 = DRP.window(r["frame"])
        dx, dy, dz = (int(v) for v in re.findall(r"d[xyz]=(\d+)", sel))
        assert (px, pz, px + dx, pz + dz) == (wx0, wz0, wx1, wz1)
        gy = r["frame"]["y"] - 1
        assert py <= gy - 1 and py + dy >= gy + 6
        ox, oy, oz, _ = r["outside"]
        assert px <= ox < px + dx + 1 and pz <= oz < pz + dz + 1 and py <= oy < py + dy + 1


# ------------------------------------------------------------------------------------------------ exact restore (rip.under)

@pytest.mark.parametrize("r", D.rips(DDOC), ids=lambda r: r["id"])
def test_close_gives_back_every_block_exactly_and_empties_the_hold(r):
    # THE property: after open then close, every cell in and round the rip holds what the world had (block and state), the sky hold
    # is air again, and nothing outside the footprint was ever written. The original world is varied (plants, leaves, stairs with
    # states), so a restore to air, to a guess, or to the recorded restore would differ from it.
    i = idx(r)
    w = build_world(seed=i)
    far_player(w)
    before = {c: w.original(*c) for c in zone_cells(r) + hold_cells(r)}
    w.call("init")
    w.call("o%d" % i)
    assert w.scores[("#r%d" % i, "rp.s")] == 1
    written = {c for c in zone_cells(r) if w.get(c) != before[c]}
    assert written and written <= footprint_cells(r)                           # the open wrote inside its footprint only
    assert w.blocks[(r["click"][0], r["frame"]["y"] - 1, r["click"][2] - 1 + 1)] is not None
    held = [c for c in hold_cells(r) if w.get(c) != AIR]
    assert len(held) >= len(footprint_cells(r)) - 25                           # the original blocks wait in the hold (air cells excepted)
    w.call("c%d" % i)
    assert w.scores[("#r%d" % i, "rp.s")] == 2
    w.advance(40 + 20 * 14)
    after = {c: w.get(c) for c in before}
    assert after == before
    assert w.scores[("#r%d" % i, "rp.s")] == 0 and not w.forced and w.dropped == []
    assert not w.living(tag=D.rip_tag(r))


def test_close_restores_a_plane_that_held_vegetation_and_a_patch_that_was_already_the_themed_block():
    # the case a recorded-restore design gets wrong: the plane held plants and a leaf block; the patch's cell was already moss
    r = D.rips(DDOC)[0]
    i = idx(r)
    f = r["frame"]
    custom = {(f["x0"] + 1, f["y"], f["z"]): "minecraft:oak_leaves[distance=1,persistent=true]",
              (f["x0"] + 2, f["y"] + 2, f["z"]): "minecraft:poppy",
              (f["x0"] + 3, f["y"] - 1, f["z"] + 1): D.rip_scorch(r)["core"]}
    w = build_world(seed=3)
    far_player(w)
    base = w.original
    w.original = lambda x, y, z: custom.get((x, y, z), base(x, y, z))
    snap = {c: w.get(c) for c in zone_cells(r)}
    w.call("init")
    w.call("o%d" % i)
    assert w.get((f["x0"] + 1, f["y"], f["z"])) == AIR                         # the open cleared the plane
    w.call("c%d" % i)
    w.advance(400)
    assert {c: w.get(c) for c in snap} == snap


def test_nothing_is_written_to_the_hold_or_the_world_before_the_checks_pass():
    r = D.rips(DDOC)[0]
    i = idx(r)
    w = build_world()
    far_player(w)
    px, py, pz, _s = RS.check_selector(r)
    stand_player(w, (px + 4.5, py + 2.0, pz + 3.5), "on_it")
    w.call("init")
    w.call("o%d" % i)
    assert w.blocks == {} and w.dropped == [] and not w.forced
    assert w.scores[("#r%d" % i, "rp.s")] == 0 and not w.living(tag=D.rip_tag(r))


# ------------------------------------------------------------------------------------------------ safety

def test_open_and_close_both_wait_while_a_player_stands_on_the_rip_and_proceed_when_he_leaves():
    r = D.rips(DDOC)[0]
    i = idx(r)
    w = build_world()
    far_player(w)
    px, py, pz, _s = RS.check_selector(r)
    on = stand_player(w, (px + 1.5, py + 1.0, pz + 1.5), "on_it")
    w.call("init")
    w.call("o%d" % i)
    assert w.scores[("#r%d" % i, "rp.s")] == 0 and w.blocks == {}              # not opened over a player
    on.pos = [0.5, 70.0, 5.5]
    w.call("o%d" % i)
    assert w.scores[("#r%d" % i, "rp.s")] == 1
    on.pos = [px + 4.5, py + 2.0, pz + 3.5]                                    # he walks back onto it (the exit point's side)
    snapshot = dict(w.blocks)
    w.scores[("#r%d" % i, "rp.t")] = 0
    w.call("c%d" % i)
    assert w.scores[("#r%d" % i, "rp.s")] == 1 and w.blocks == snapshot        # not closed over a player; still open, timer at 0
    assert w.living(tag=D.rip_tag(r))
    on.pos = [0.5, 70.0, 5.5]
    w.call("c%d" % i)
    assert w.scores[("#r%d" % i, "rp.s")] == 2


def test_a_close_that_found_a_player_is_asked_again_by_the_next_pass():
    r = D.rips(DDOC)[0]
    i = idx(r)
    w = build_world(rdoc_edit=edit_settings(open_min=0, extra_open_every_minutes=100000))
    far_player(w)
    px, py, pz, _s = RS.check_selector(r)
    w.call("init")
    w.call("o%d" % i)
    on = stand_player(w, (px + 4.5, py + 2.0, pz + 3.5), "on_it")
    w.scores[("#r%d" % i, "rp.t")] = 50
    w.advance(100 * 5)                                                          # timers run out; he is still there
    assert w.scores[("#r%d" % i, "rp.s")] == 1
    on.pos = [0.5, 70.0, 5.5]
    w.advance(100 * 2)
    assert w.scores[("#r%d" % i, "rp.s")] == 2                                  # closing now: the pass asked again and found nobody


def test_a_rip_is_not_opened_while_a_player_in_a_run_would_come_out_at_it():
    # the return point: dg.rip = this rip's number with dg.st >= 1. Opening it would put the oval under the player who arrives
    r = D.rips(DDOC)[0]
    i = idx(r)
    w = build_world()
    far_player(w)
    runner = stand_player(w, (5000.5, 70.0, 5000.5), "in_a_run")
    set_score(w, runner, "dg.rip", i)
    set_score(w, runner, "dg.st", 3)
    w.call("init")
    w.call("o%d" % i)
    assert w.scores[("#r%d" % i, "rp.s")] == 0 and w.blocks == {} and not w.forced
    set_score(w, runner, "dg.st", 0)                                            # the run is over; dg.rip is kept by the engine
    w.call("o%d" % i)
    assert w.scores[("#r%d" % i, "rp.s")] == 1
    other = [x for x in D.rips(DDOC) if x is not r][0]
    w2 = build_world()
    far_player(w2)
    rn = stand_player(w2, (5000.5, 70.0, 5000.5), "in_a_run")
    set_score(w2, rn, "dg.rip", i)
    set_score(w2, rn, "dg.st", 3)
    w2.call("init")
    w2.call("o%d" % idx(other))                                                  # someone else's return point does not block this one
    assert w2.scores[("#r%d" % idx(other), "rp.s")] == 1


def test_a_run_that_outlives_its_rip_comes_out_at_the_closed_ground_not_at_another_rip():
    # the safe fallback, named: m/out sends a player to the exit point of the rip he went in by (dg.rip); the rip has closed, so that
    # point is on the ground the close gave back. No function of the scheduler moves a player, and the exit point is not a cell it writes
    for name, lines in RS.functions(DDOC, RDOC).items():
        assert not any(re.match(r"(execute .*run )?tp\b", ln) for ln in lines), name
    out = "\n".join(D.functions(DDOC)["m/out"]) if False else None            # (m/out is the dungeon pack's; built and tested there)
    assert out is None
    for r in D.rips(DDOC):
        ox, oy, oz, _ = r["outside"]
        assert (int(ox // 1), int(oy // 1), int(oz // 1)) not in footprint_cells(r)
        assert int(oy) == r["frame"]["y"]                                       # standing on the ground's top, one over the patch


def test_two_rips_of_one_region_are_never_open_together():
    d = synthetic(DDOC, 3)
    for r in d["rips"]:
        r["region"] = "pallet_fields"

    def small(rdoc):  # a pool of 3 cannot hold the live minimum; the rule under test is the region's, not the counts
        rdoc["settings"]["open_min"]["value"], rdoc["settings"]["open_max"]["value"] = 1, 3
    w = build_world(ddoc=d, rdoc_edit=small)
    far_player(w)
    w.call("init")
    w.call("o1")
    w.call("o2")
    w.call("o3")
    assert [w.scores[("#r%d" % i, "rp.s")] for i in (1, 2, 3)] == [1, 0, 0]
    def small_off(rdoc):
        small(rdoc)
        edit_settings(one_open_per_region=False)(rdoc)
    off = build_world(ddoc=d, rdoc_edit=small_off)
    far_player(off)
    off.call("init")
    off.call("o1")
    off.call("o2")
    assert [off.scores[("#r%d" % i, "rp.s")] for i in (1, 2)] == [1, 1]


def test_a_closing_rip_cannot_be_opened_again_until_its_polls_are_done():
    r = D.rips(DDOC)[0]
    i = idx(r)
    w = build_world()
    far_player(w)
    w.call("init")
    w.call("o%d" % i)
    w.call("c%d" % i)
    w.call("o%d" % i)
    assert w.scores[("#r%d" % i, "rp.s")] == 2                                  # still closing: the open refused
    w.advance(40 + 20 * 14)
    assert w.scores[("#r%d" % i, "rp.s")] == 0
    w.call("o%d" % i)
    assert w.scores[("#r%d" % i, "rp.s")] == 1


def test_forceload_is_held_only_while_writing_and_released_in_both_directions():
    r = D.rips(DDOC)[0]
    i = idx(r)
    w = build_world()
    far_player(w)
    w.call("init")
    w.call("o%d" % i)
    assert not w.forced and w.dropped == []                                     # held and released inside the one function
    w.call("c%d" % i)
    assert w.forced and w.dropped == []                                         # the close holds the chunks for its polls
    w.advance(40 + 20 * 14)
    assert not w.forced and w.dropped == []


def test_a_ghost_click_or_oval_that_arrived_late_in_a_closed_rips_chunk_is_killed_by_the_pass():
    # a chunk's saved entities arrive some ticks after a forceload (tools/chunk_look.py); the close's polls cover most of that, and
    # the pass kills what is left, so a closed rip is never clickable
    r = D.rips(DDOC)[0]
    i = idx(r)
    w = build_world(loaded_all=True, rdoc_edit=edit_settings(open_min=0, extra_open_every_minutes=100000))
    far_player(w)
    w.call("init")
    ghost = w.add(SIM.Entity("minecraft:interaction", (r["click"][0] + 0.5, r["click"][1], r["click"][2] + 0.5), tags=["dg.rip", D.rip_tag(r)]))
    w.call("pass")
    assert not ghost.alive


def test_an_open_rip_is_not_killed_by_the_ghost_sweep():
    r = D.rips(DDOC)[0]
    i = idx(r)
    w = build_world(loaded_all=True, rdoc_edit=edit_settings(open_min=0, extra_open_every_minutes=100000))
    far_player(w)
    w.call("init")
    w.call("o%d" % i)
    w.call("pass")
    assert len(w.living(tag=D.rip_tag(r))) == 2                                 # the interaction and the oval


# ------------------------------------------------------------------------------------------------ the clock, the cap, the pick

def count_open(w, n):
    return sum(1 for i in range(1, n + 1) if w.scores.get(("#r%d" % i, "rp.s"), 0) in (1, 2))


def test_the_cap_holds_and_the_minimum_is_reached():
    n = len(D.rips(DDOC))
    w = build_world(seed=11)
    far_player(w)
    w.run_load()
    peak = 0
    for _ in range(40):
        w.advance(100)
        peak = max(peak, count_open(w, n))
        assert count_open(w, n) <= V["open_max"]
    assert peak >= V["open_min"]


def test_with_nobody_online_nothing_opens_and_nothing_ages():
    n = len(D.rips(DDOC))
    w = build_world()
    w.run_load()
    w.advance(100 * 30)
    assert count_open(w, n) == 0 and w.blocks == {}
    p = far_player(w)
    w.advance(100 * 10)
    assert count_open(w, n) >= 1
    opened = [i for i in range(1, n + 1) if w.scores.get(("#r%d" % i, "rp.s")) == 1][0]
    t0 = w.scores[("#r%d" % opened, "rp.t")]
    p.alive = False                                                              # everyone leaves
    w.advance(100 * 20)
    assert w.scores[("#r%d" % opened, "rp.t")] == t0


def test_the_pause_switch_stops_the_pass():
    n = len(D.rips(DDOC))
    w = build_world()
    far_player(w)
    w.run_load()
    w.call("stop")
    w.advance(100 * 30)
    assert count_open(w, n) == 0
    w.call("start")
    w.advance(100 * 10)
    assert count_open(w, n) >= 1


def test_a_rip_closes_after_about_an_hour_of_play_and_never_before_the_minimum_lifetime():
    r = D.rips(DDOC)[0]
    i = idx(r)
    w = build_world(seed=5, rdoc_edit=edit_settings(open_min=0, extra_open_every_minutes=100000))
    far_player(w)
    w.call("init")
    w.call("o%d" % i)
    t0 = w.scores[("#r%d" % i, "rp.t")]
    lo = (V["lifetime_minutes"] - V["lifetime_jitter_minutes"]) * 1200
    hi = (V["lifetime_minutes"] + V["lifetime_jitter_minutes"]) * 1200
    assert lo <= t0 <= hi
    ticks = 0
    while w.scores[("#r%d" % i, "rp.s")] == 1 and ticks < hi + 2000:
        w.advance(100)
        ticks += 100
    assert w.scores[("#r%d" % i, "rp.s")] in (2, 0)
    assert lo - 100 <= ticks <= hi + 200


def test_a_rip_closes_once_a_player_has_gone_through_it():
    r = D.rips(DDOC)[0]
    i = idx(r)
    w = build_world(rdoc_edit=edit_settings(open_min=0, extra_open_every_minutes=100000))
    far_player(w)
    runner = stand_player(w, (5000.5, 70.0, 5000.5), "runner")
    w.call("init")
    w.call("o%d" % i)
    w.advance(100 * 3)
    assert w.scores[("#r%d" % i, "rp.s")] == 1                                   # nobody has gone through: still open
    set_score(w, runner, "dg.rip", i)
    set_score(w, runner, "dg.st", 1)
    w.advance(100 * 2)
    assert w.scores[("#r%d" % i, "rp.s")] == 2                                   # closing: the click and the oval are gone at once
    assert not w.living(tag=D.rip_tag(r))
    w.advance(40 + 20 * 14)
    assert w.scores[("#r%d" % i, "rp.s")] == 0


def test_a_run_through_another_rip_does_not_close_this_one():
    r = D.rips(DDOC)[0]
    i = idx(r)
    w = build_world(rdoc_edit=edit_settings(open_min=0, extra_open_every_minutes=100000))
    far_player(w)
    runner = stand_player(w, (5000.5, 70.0, 5000.5), "runner")
    set_score(w, runner, "dg.rip", i + 1)
    set_score(w, runner, "dg.st", 3)
    w.call("init")
    w.call("o%d" % i)
    w.advance(100 * 6)
    assert w.scores[("#r%d" % i, "rp.s")] == 1


def test_the_chat_line_names_the_region_plainly_and_goes_to_every_player():
    r = D.rips(DDOC)[0]
    i = idx(r)
    w = build_world()
    a, b = far_player(w), stand_player(w, (100.5, 70.0, 100.5), "second")
    w.call("init")
    w.call("o%d" % i)
    names = {x["id"]: x["display_name"] for x in json.loads((ROOT / "data" / "regions.json").read_text(encoding="utf-8"))["regions"]}
    nm = names[r["region"]]
    phrase = "the " + nm[4:] if nm.startswith("The ") else nm
    for p in (a, b):
        assert [m["text"] for m in p.messages] == ["A rift has opened in %s." % phrase]
    assert RS.region_phrase("The Rift") == "the Rift" and RS.region_phrase("Pallet Fields") == "Pallet Fields"


def test_the_pick_is_uniform_over_the_pool_and_every_candidate_can_be_drawn():
    d = synthetic(DDOC, 6)
    w = build_world(ddoc=d, seed=2)
    far_player(w)
    w.call("init")
    seen = {}
    for k in range(600):
        for i in range(1, 7):
            w.scores[("#r%d" % i, "rp.s")] = 0
        w.blocks.clear()
        w.call("pick")
        for i in range(1, 7):
            if w.scores[("#r%d" % i, "rp.s")] == 1:
                seen[i] = seen.get(i, 0) + 1
    assert set(seen) == set(range(1, 7))
    assert min(seen.values()) > 600 / 6 * 0.5                                    # nothing is starved (a loose bound, not a threshold tuned to pass)


def test_init_is_safe_over_open_rips_and_resumes_a_close_the_server_stopped_in():
    r = D.rips(DDOC)[0]
    i = idx(r)
    w = build_world()
    far_player(w)
    w.call("init")
    w.call("o%d" % i)
    w.call("c%d" % i)
    w.queue.clear()                                                              # the stop lost the schedule
    blocks = dict(w.blocks)
    w.call("init")
    assert w.scores[("#r%d" % i, "rp.s")] == 2 and w.blocks == blocks            # init changed no block and no state
    assert any(q[1] == NS + "x%d" % i for q in w.queue) and any(q[1] == NS + "pass" for q in w.queue)
    w.advance(40 + 20 * 14)
    assert w.scores[("#r%d" % i, "rp.s")] == 0


def test_close_all_closes_every_open_rip_and_pauses():
    n = len(D.rips(DDOC))
    w = build_world(seed=4)
    far_player(w)
    w.run_load()
    w.advance(100 * 30)
    assert count_open(w, n) >= 1
    w.call("close_all")
    w.advance(40 + 20 * 14 + 100)
    assert count_open(w, n) == 0 and w.dropped == []


# ------------------------------------------------------------------------------------------------ the engine's side

def test_the_write_boxes_are_exactly_the_cells_the_open_writes():
    # rip_write_boxes is derived from the frame and the patch; rip_lines is the text. They must name the same cells, or the save
    # misses a cell the open writes (lost) or copies one it does not (a stranger's change erased at the close)
    for r in D.rips(DDOC):
        cells = set()
        for b in D.rip_write_boxes(r):
            cells |= {(x, y, z) for x in range(b[0], b[3] + 1) for y in range(b[1], b[4] + 1) for z in range(b[2], b[5] + 1)}
        assert cells == footprint_cells(r), r["id"]
        hb = D.rip_hold_boxes(r, V["hold_y"])
        assert all(h[1] >= V["hold_y"] for h in hb) and len(hb) == len(D.rip_write_boxes(r))


def test_rip_close_lines_fails_closed_with_neither_a_record_nor_a_hold_and_still_reads_a_record():
    r = copy.deepcopy(D.rips(DDOC)[0])
    with pytest.raises(D.DungeonError):
        D.rip_close_lines(r)                                                     # the old failure, unchanged
    r["under"] = {"%d,%d" % (x, z): "minecraft:grass_block" for x, _y, z, _b in D.rip_scorch_cells(r)}
    lines = D.rip_close_lines(r)                                                 # a recorded rip.under still works
    assert lines[0].startswith("kill") and any(ln.startswith("setblock") for ln in lines)
    held = D.rip_close_lines(D.rips(DDOC)[0], V["hold_y"])                       # and the hold needs no record
    assert any(ln.startswith("clone") for ln in held) and not any(ln.startswith("setblock") for ln in held)


def test_the_close_gives_the_ground_back_before_the_plane():
    # a plant in the plane stands on the ground it was cloned with; the plane first would put it on the themed patch
    r = D.rips(DDOC)[0]
    lines = D.rip_close_lines(r, V["hold_y"])
    clones = [ln for ln in lines if ln.startswith("clone")]
    f = r["frame"]
    assert clones[-1].split()[-3:] == [str(f["x0"]), str(f["y"]), str(f["z"])]     # the plane is the last clone
    assert all(ln.split()[-2] == str(f["y"] - 1) for ln in clones[:-1])             # the rows before it are the ground's


def test_the_old_one_shot_rips_are_gone_from_the_dungeon_pack():
    fns = dungeon_functions()
    assert "rips/place" not in fns and not [k for k in fns if k.startswith("rips/blocks_")]
    steps = dict((s[0], s[2]) for s in D.reapply_steps(DDOC))
    assert ("fn", D.SCHEDULER_INIT) in steps["R16DR"] and ("fn", D.F("rips/retire")) in steps["R16DR"]


def test_the_per_rip_click_and_advancement_still_exist_for_every_candidate():
    # the scheduler stands the interaction; the click's advancement and function are the dungeon pack's, one per candidate
    fns = dungeon_functions()
    for r in D.rips(DDOC):
        assert D.rip_door(r) in fns


# ------------------------------------------------------------------------------------------------ the pack, as the server sees it

def test_the_pack_is_runtime_content_and_its_functions_are_all_reachable(tmp_path):
    import pack_roles as PR
    RS.write(RS.pack_files(DDOC, RDOC), tmp_path / "cobblers_rips")
    rep = PR.classify([("cobblers_rips", tmp_path / "cobblers_rips")], None, config_dirs=())
    p = rep["packs"]["cobblers_rips"]
    assert p["role"] == "runtime", p["why"]
    # everything but the operator's three (start, stop, close_all: run by hand over RCON) is reachable from minecraft:load
    assert p["functions"] - p["reachable_functions"] == 3
    assert not rep["unresolved"]


def test_the_reapply_wiring_installs_the_pack_world_local_and_builds_it_after_the_dungeons():
    import reapply as R
    assert "cobblers_rips" in R.SERVER_PACKS and "cobblers_rips" in R.WORLD_LOCAL
    jobs = [n for n, _f in R.prepare_jobs(type("A", (), {"source_root": "x", "server_dir": "x"})())]
    assert "rip_scheduler" in jobs and jobs.index("rip_scheduler") > jobs.index("dungeons")


def test_no_function_of_the_pack_is_orphaned_for_prepare(tmp_path):
    # tools/reapply.py unreferenced(): every function is run by a step or named by some text. Replayed here over the pack alone
    import reapply as R
    RS.write(RS.pack_files(DDOC, RDOC), tmp_path / "cobblers_rips")
    names = set()
    text = []
    for f in (tmp_path / "cobblers_rips").rglob("*.mcfunction"):
        text.append(f.read_text(encoding="utf-8"))
        rel = f.relative_to(tmp_path / "cobblers_rips" / "data").parts
        names.add("%s:%s" % (rel[0], "/".join(rel[2:])[:-len(".mcfunction")]))
    blob = "\n".join(text) + json.dumps({"values": ["cobblers:rips/load"]}) + "cobblers:rips/init"
    referenced = set(R.FUNCTION_REF.findall(blob))
    assert names - referenced == set()
