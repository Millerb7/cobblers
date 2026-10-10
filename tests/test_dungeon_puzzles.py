"""The dungeon's puzzle and vault kinds (tools/dungeon_puzzles.py): geometry, walk check, and the runtime on the simulator.

  geometry   every variant builds in the three themes with no problem, the controls survive the theme's dressing and
             hang on something solid, every block exists in 1.21.1, nothing is a hazard, concrete, or the pick's.
  runtime    the generated functions driven on tests/pocket_sim.py (through test_dungeon.DW and a block-state model of
             this file's): the target is rolled on entry, a solved puzzle opens the gate once, a wrong attempt costs
             the clock and visibly resets, the slot reset puts it all back; a vault charges the clock once per chest
             and its reset re-places every chest from air with the entrant's band's loot table.
  mutation   the GENERATOR is changed (not the record) and a check or a runtime test must fail: order_perms,
             plate_cells, penalty_lines, the chest cost.

What the simulator does NOT know: block collision, whether a lever is usable in adventure mode, the real `LootTable`
behaviour of an opened chest, the real press timings. Those are the module docstring's UNPROVEN list.
"""
from __future__ import annotations

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
import dungeon_clock as DC  # noqa: E402
import dungeon_grid as G  # noqa: E402
import dungeon_puzzles as DP  # noqa: E402
import dungeon_rooms as R  # noqa: E402
import pocket_sim as PS  # noqa: E402
import test_dungeon as TD  # noqa: E402
import test_dungeon_rooms as TR  # noqa: E402

FIX = json.loads((ROOT / "tests" / "fixtures" / "dungeon_puzzle_rooms.json").read_text(encoding="utf-8"))["rooms"]
POCKET = TR.POCKET
THEMES = ("mine", "jungle", "flooded_ruin")


def pdoc(theme="mine", rooms=None):
    return TR.demo_doc(theme, rooms if rooms is not None else FIX)


@pytest.fixture(autouse=True)
def fresh_cache():
    R._BUILT.clear()
    yield
    R._BUILT.clear()


def built(doc, rid):
    d = doc["dungeons"][0]
    return next(b for b in R.slot_build(doc, d, D.slots(doc)[0]) if b.room["id"] == rid)


# ------------------------------------------------------------------------------------------------- geometry


@pytest.mark.parametrize("theme", THEMES)
def test_every_variant_builds_in_every_theme_with_no_problem_and_the_controls_survive_the_dressing(theme):
    doc = pdoc(theme)
    # the fixture as a finished rooms dungeon carries the clock derived from its own rooms (DUNGEON_ROOMS.md 7), as
    # every authored one does since DG-INTEGRATE; without it D.warnings rightly names the missing clock_s_by_band
    doc["dungeons"][0]["clock_s_by_band"] = DC.derive(doc, doc["dungeons"][0])
    assert R.problems(doc) == [] and D.warnings(doc) == [], (R.problems(doc), D.warnings(doc))
    for rid in ("lev", "seq", "plt", "vlt"):
        b = built(doc, rid)
        assert b.meta["expect"], rid
        for pos, want in b.meta["expect"]:
            assert G.base(b.grid.block_at(*pos)) == G.base(want), (theme, rid, pos, want)
        for pos, to in b.meta["attached"]:
            assert G.classify(b.grid.block_at(*to)) == G.SOLID, (theme, rid, pos)


@pytest.mark.parametrize("theme", THEMES)
def test_the_blocks_exist_in_1_21_1_and_none_is_banned_or_breakable_by_the_pick(theme):
    ids = TR.vanilla_ids()
    pick = set(TR.BASE["engine"]["rift_pick"]["can_break"])
    for name in (theme,):
        blocks = {v for k, v in DP.blocks_of(name).items() if isinstance(v, str)} | set(DP.blocks_of(name)["marks"])
        for b in blocks:
            assert not G.forbidden(b) and G.classify(b) != G.HAZARD, b
            assert b not in pick, b
            if ids is not None:
                assert b in ids, (name, b)


def test_a_button_is_wooden_so_a_press_outlasts_the_keepers_20_tick_period():
    """Stone buttons stay pressed 20 ticks and the keeper looks every 20: a press could fall between two looks."""
    period = TR.BASE["engine"]["keeper"]["period_ticks"]
    assert period == 20
    for t in THEMES:
        name = DP.blocks_of(t)["button"].split(":")[1]
        assert name.endswith("_button") and not name.startswith(("stone", "polished_blackstone")), name
        assert DP.blocks_of(t)["plate"] == "minecraft:stone_pressure_plate", "a plate that ignores thrown items"


def test_variant_blocks_is_refused_and_so_is_an_unknown_one_and_a_bad_size():
    for params in ({"variant": "blocks"}, {"variant": "wheel"}, {"variant": "levers", "size": 9},
                   {"variant": "sequence", "length": 2}):
        rooms = [dict(r, params=params) if r["id"] == "lev" else r for r in FIX]
        assert R.problems(pdoc("mine", rooms)), params
    rooms = [dict(r, length=16) if r["id"] == "lev" else r for r in FIX]
    assert any("console" in p for p in R.problems(pdoc("mine", rooms))), "too short a room for its console"


def test_the_plates_keep_clear_of_the_line_between_the_doors_and_five_apart():
    doc = pdoc("mine")
    b = built(doc, "plt")
    r = b.room
    cells = [tuple(a[:3]) for a in b.anchors["controls"]]
    assert len(cells) == 4
    for i, (x, y, z) in enumerate(cells):
        assert abs(z - r["z_in"]) >= 4, "a player walking door to door never steps on a plate"
        for (x2, _y2, z2) in cells[i + 1:]:
            assert (x - x2) ** 2 + (z - z2) ** 2 >= 25


def test_the_four_slots_are_one_puzzle_dungeon():
    doc = pdoc("jungle")
    d = doc["dungeons"][0]
    doc["engine"]["slots"]["per_dungeon"] = 4
    ss = D.slots(doc)
    a = R.slot_build(doc, d, ss[0])
    b = R.slot_build(doc, d, ss[1])
    for x, y in zip(a, b):
        assert x.meta.get("variants") == y.meta.get("variants")
        rel = lambda bb, sl: [[c[0], c[1], c[2] - sl["z0"]] for c in bb.anchors.get("controls", [])]  # noqa: E731
        assert rel(x, ss[0]) == rel(y, ss[1])


def test_the_shell_and_the_functions_are_inside_the_limits():
    import function_limits as FL
    for t in THEMES:
        files = D.build(pdoc(t))
        for rel, body in files.items():
            if "/room/night_shift/" in rel and rel.endswith(".mcfunction"):
                assert FL.check_lines(body.splitlines(), rel) == [], rel


# ------------------------------------------------------------------------------------------------- loot tables


def test_a_vault_with_item_stacks_gets_a_loot_table_per_band_and_a_string_is_used_as_it_is():
    doc = pdoc("mine")
    files = D.build(doc)
    key = "data/cobblers/loot_table/dungeons/vault/night_shift/vlt/b1.json"
    assert key in files and not any(k.endswith("/b4.json") for k in files if "/vault/" in k), "band 4 names a vanilla table"
    t = json.loads(files[key])
    assert t["type"] == "minecraft:chest" and len(t["pools"]) == 2
    first = t["pools"][0]["entries"][0]
    assert first["name"] == "minecraft:iron_ingot" and first["functions"][0]["count"] == {"type": "minecraft:uniform", "min": 4, "max": 8}
    second = t["pools"][1]
    assert second["conditions"] == [{"condition": "minecraft:random_chance", "chance": 0.5}]
    assert second["entries"][0]["functions"][0]["count"] == 2
    reset = files["data/cobblers/function/dungeons/room/night_shift/vlt/s1/reset.mcfunction"]
    assert 'LootTable:"cobblers:dungeons/vault/night_shift/vlt/b1"' in reset
    assert 'LootTable:"minecraft:chests/simple_dungeon"' in reset
    for band in (2, 3):
        assert re.search(r"matches %d run setblock .*b1" % band, reset), "bands 2 and 3 take band 1's table"
    for band in (4, 5, 6):
        assert re.search(r"matches %d run setblock .*simple_dungeon" % band, reset)


def test_loot_params_are_checked():
    for loot in ({"1": 5}, {"x": "minecraft:chests/simple_dungeon"}, {"2": "minecraft:chests/simple_dungeon"},
                 {"1": [{"item": "diamond"}]}, {"1": [{"item": "minecraft:diamond", "count": 99}]}, {"1": []}):
        rooms = [dict(r, params=dict(r["params"], loot_by_band=loot)) if r["id"] == "vlt" else r for r in FIX]
        assert R.problems(pdoc("mine", rooms)), loot


def test_a_vault_with_no_loot_named_holds_the_placeholder_and_still_builds():
    rooms = [dict(r, params={"chests": 4}) if r["id"] == "vlt" else r for r in FIX]
    doc = pdoc("mine", rooms)
    assert R.problems(doc) == []
    files = D.build(doc)
    assert any(k.endswith("/vlt/b5.json") for k in files)


# ------------------------------------------------------------------------------------------------- the simulator


class PW(TD.DW):
    """DW plus a block-state model (`if block`, `if data block ... LootTable`, setblock and fill that change it, and the
    vanilla rule that a setblock onto an identical state fails and loads no NBT) and `random value`."""

    BLK = re.compile(r"\b(if|unless) block (-?\d+) (-?\d+) (-?\d+) (\S+)")
    DAT = re.compile(r"\b(if|unless) data block (-?\d+) (-?\d+) (-?\d+) LootTable")

    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.blocks = {}
        self.loot = {}
        self.rolls = []
        self.rng = random.Random(11)
        self.specs = {}

    @staticmethod
    def split(spec):
        spec = spec.split("{", 1)[0]
        m = re.fullmatch(r"([a-z0-9_:]+)(?:\[(.*)\])?", spec)
        props = dict(p.split("=") for p in m.group(2).split(",")) if m and m.group(2) else {}
        return m.group(1), props

    def block_matches(self, pos, spec):
        hid, hp = self.split(self.blocks.get(pos, "minecraft:air"))
        wid, wp = self.split(spec)
        return hid == wid and all(hp.get(k) == v for k, v in wp.items())

    def tag(self, key, truth):
        name = self.specs.setdefault(key, "__b%d" % len(self.specs))
        for p in self.players():
            (p.tags.add if truth else p.tags.discard)(name)
        return name

    def run(self, cmd, ctx, from_macro=False):
        def blk(m):
            pos = (int(m.group(2)), int(m.group(3)), int(m.group(4)))
            return "%s entity @s[tag=%s]" % (m.group(1), self.tag((pos, m.group(5)), self.block_matches(pos, m.group(5))))

        def dat(m):
            pos = (int(m.group(2)), int(m.group(3)), int(m.group(4)))
            return "%s entity @s[tag=%s]" % (m.group(1), self.tag((pos, "LootTable"), pos in self.loot))
        cmd = self.DAT.sub(dat, self.BLK.sub(blk, cmd))
        return super().run(cmd, ctx, from_macro)

    def set_block(self, pos, spec):
        if self.blocks.get(pos, "minecraft:air") == spec.split("{", 1)[0]:
            raise PS.Failed("Could not set the block")           # an identical state: vanilla fails, loads nothing
        self.blocks[pos] = spec.split("{", 1)[0]
        m = re.search(r'LootTable:"([^"]+)"', spec)
        if m:
            self.loot[pos] = m.group(1)
        else:
            self.loot.pop(pos, None)

    def run_tokens(self, t, ctx, from_macro=False, raw=None):
        if t[0] == "setblock":
            self.set_block((int(t[1]), int(t[2]), int(t[3])), t[4])
        elif t[0] == "fill":
            x0, y0, z0, x1, y1, z1 = (int(v) for v in t[1:7])
            for x in range(min(x0, x1), max(x0, x1) + 1):
                for y in range(min(y0, y1), max(y0, y1) + 1):
                    for z in range(min(z0, z1), max(z0, z1) + 1):
                        self.blocks[(x, y, z)] = t[7]
        elif t[0] == "random" and t[1] == "value":
            lo, hi = (int(v) for v in t[2].split(".."))
            v = self.rolls.pop(0) if self.rolls else self.rng.randint(lo, hi)
            assert lo <= v <= hi
            return v
        return super().run_tokens(t, ctx, from_macro, raw)


def world(theme="mine", rooms=None, tmp_path_factory=None, cache={}):
    doc = pdoc(theme, rooms)
    key = (theme, json.dumps(rooms, sort_keys=True))
    if key not in cache:
        out = Path(tmp_path_factory.mktemp("cobblers_puzzles"))
        D.write(D.build(doc), out)
        cache[key] = out
    w = PW(cache[key], dict(TD.FAKES))
    w.objectives |= {"cobblers.lc_cap", "tailend", "stale"}
    w.boot()
    return doc, w


@pytest.fixture
def mk(tmp_path_factory):
    return lambda theme="mine", rooms=None: world(theme, rooms, tmp_path_factory)


def start(doc, w):
    p, s = TR.enter_run(doc, w)
    return p, s


def into(doc, w, p, rid, dx=4):
    r = next(x for x in R.plan(doc, doc["dungeons"][0], D.slots(doc)[0]) if x["id"] == rid)
    p.pos = [r["ix0"] + dx + 0.5, r["floor_in"], r["z_in"] + 0.5]
    w.passes(1)
    return r


def hold(s, r):
    return "#s%dr%d" % (s["g"], r["i"])


def reset_slot(w, p, s):
    w.call("cobblers:dungeons/slot/s%d/reset" % s["g"], PS.Ctx(p, POCKET, p.pos))


def door_shut(w, r):
    x0, y0, z0, x1, y1, z1 = r["door_out"]
    return w.blocks.get((x0, y0, z0)) not in (None, "minecraft:air")


def door_open(w, r):
    x0, y0, z0, x1, y1, z1 = r["door_out"]
    return all(w.blocks.get((x, y, z)) == "minecraft:air" for x in range(x0, x1 + 1) for y in range(y0, y1 + 1) for z in range(z0, z1 + 1))


def grid_row(b, y, z):
    """x -> block of the grid's row (y, z) across the room (the shell's blocks, independent of the generator's records)."""
    r = b.room
    return {x: b.grid.block_at(x, y, z) for x in range(r["ix0"], r["ix1"] + 1)}


# ------------------------------------------------------------------------------------------------- levers


def lamp_pattern(w, b):
    r = b.room
    fy, iz0 = r["floor_in"], r["iz0"]
    xs = [a[0] for a in b.anchors["controls"]]
    on = DP.blocks_of(r["theme"])["lamp_on"]
    return [w.blocks.get((x, fy + 2, iz0)) == on for x in xs]


def levers_wrong_attempt(doc, w, p, s):
    r = into(doc, w, p, "lev")
    b = built(doc, "lev")
    fy = r["floor_in"]
    levs = [(a[0], a[1], a[2]) for a in b.anchors["controls"]]
    seal = tuple(b.anchors["seal"][0][:3])
    pat = lamp_pattern(w, b)
    assert any(pat), "a target with every lamp dark would be solved before it began"
    for k, pos in enumerate(levs):                      # every lever the OPPOSITE of its lamp
        w.blocks[pos] = DP.lever(not pat[k])
    w.blocks[seal] = DP.button(DP.blocks_of("mine"), True)
    clock = w.get(p.name, "dg.clock")
    w.passes(1)
    pen = (doc["engine"]["clock"]["fall_penalty_s"] if "penalty_s" not in r["params"] else r["params"]["penalty_s"]) * 80
    assert w.get(p.name, "dg.clock") == clock - 80 - pen, "one pass of the clock and the wrong seal's penalty"
    assert all(w.blocks[pos] == DP.lever(False) for pos in levs), "the levers flip back, where the player can see"
    assert w.get(hold(s, r), "dg.rs") == 1 and door_shut(w, r)


def test_levers_a_wrong_seal_charges_the_clock_and_flips_every_lever_back(mk):
    doc, w = mk()
    p, s = start(doc, w)
    levers_wrong_attempt(doc, w, p, s)


def test_levers_the_right_pattern_opens_the_gate_once_for_every_target_the_room_can_roll(mk):
    doc, w = mk()
    p, s = start(doc, w)
    b = built(doc, "lev")
    k = len(b.meta["variants"])
    assert k == 8
    seen = set()
    for j in range(k):
        reset_slot(w, p, s)
        assert w.get(hold(s, b.room), "dg.rs") == 0
        w.rolls = [j]
        r = into(doc, w, p, "lev")
        assert w.get(hold(s, r), "dg.rs") == 1 and door_shut(w, r)
        pat = lamp_pattern(w, b)
        assert pat == b.meta["variants"][j], "the roll %d put variant %d on the lamps" % (j, j)
        seen.add(tuple(pat))
        for pos, on in zip([tuple(a[:3]) for a in b.anchors["controls"]], pat):
            w.blocks[pos] = DP.lever(on)
        w.blocks[tuple(b.anchors["seal"][0][:3])] = DP.button(DP.blocks_of("mine"), True)
        clock = w.get(p.name, "dg.clock")
        w.passes(1)
        assert w.get(hold(s, r), "dg.rs") == 2 and door_open(w, r), j
        assert w.get(p.name, "dg.clock") == clock - 80, "a right seal costs nothing"
    assert len(seen) == k, "eight distinct targets"


def test_levers_the_seal_is_consumed_so_one_press_is_one_attempt(mk):
    doc, w = mk()
    p, s = start(doc, w)
    r = into(doc, w, p, "lev")
    b = built(doc, "lev")
    seal = tuple(b.anchors["seal"][0][:3])
    w.blocks[seal] = DP.button(DP.blocks_of("mine"), True)
    clock = w.get(p.name, "dg.clock")
    w.passes(1)
    after_one = w.get(p.name, "dg.clock")
    w.passes(2)
    assert after_one == clock - 80 - 12 * 80
    assert w.get(p.name, "dg.clock") == after_one - 160, "no second penalty from the same press"


def test_levers_nothing_happens_before_entry_or_after_the_solve(mk):
    doc, w = mk()
    p, s = start(doc, w)
    b = built(doc, "lev")
    r = b.room
    seal = tuple(b.anchors["seal"][0][:3])
    w.blocks[seal] = DP.button(DP.blocks_of("mine"), True)
    clock = w.get(p.name, "dg.clock")
    w.passes(1)
    assert w.get(p.name, "dg.clock") == clock - 80, "a member outside the room is not judged"
    reset_slot(w, p, s)
    into(doc, w, p, "lev")
    w.call("cobblers:dungeons/room/night_shift/lev/s1/clear", PS.Ctx(p, p.dim, p.pos))
    assert w.get(hold(s, r), "dg.rs") == 2
    clock = w.get(p.name, "dg.clock")
    w.blocks[seal] = DP.button(DP.blocks_of("mine"), True)
    w.passes(1)
    assert w.get(p.name, "dg.clock") == clock - 80, "a cleared room charges nothing"


def test_levers_the_slot_reset_puts_the_console_back_and_the_next_entry_rolls_again(mk):
    doc, w = mk()
    p, s = start(doc, w)
    b = built(doc, "lev")
    r = into(doc, w, p, "lev")
    levs = [tuple(a[:3]) for a in b.anchors["controls"]]
    for pos in levs:
        w.blocks[pos] = DP.lever(True)
    reset_slot(w, p, s)
    assert all(w.blocks[pos] == DP.lever(False) for pos in levs) and w.get(hold(s, r), "dg.rs") == 0
    assert lamp_pattern(w, b) == b.meta["variants"][0]
    w.rolls = [5]
    into(doc, w, p, "lev")
    assert lamp_pattern(w, b) == b.meta["variants"][5]


# ------------------------------------------------------------------------------------------------- sequence


def sequence_order(w, b):
    """The buttons to press, in order: read from the world's coloured row, matched to the markers over the buttons."""
    r = b.room
    fy, iz0 = r["floor_in"], r["iz0"]
    ctl = [tuple(a[:3]) for a in b.anchors["controls"]]
    marks = {x: b.grid.block_at(x, fy + 2, iz0) for (x, _y, _z) in ctl}
    row = [w.blocks.get((x, fy + 4, iz0)) for (x, _y, _z) in ctl]
    return [next(i for i, (x, _y, _z) in enumerate(ctl) if marks[x] == colour) for colour in row], ctl


def press(w, pos, B):
    w.blocks[pos] = DP.button(B, True)


def test_sequence_pressing_in_the_shown_order_one_a_pass_lights_the_progress_and_clears(mk):
    doc, w = mk()
    p, s = start(doc, w)
    b = built(doc, "seq")
    B = DP.blocks_of("mine")
    w.rolls = [2]
    r = into(doc, w, p, "seq")
    order, ctl = sequence_order(w, b)
    assert sorted(order) == list(range(4)) and order != [0, 1, 2, 3]
    assert order == b.meta["variants"][2]
    prog_y = r["floor_in"] + 3
    xs = [c[0] for c in ctl]
    for step, i in enumerate(order):
        assert w.get(hold(s, r), "dg.rs") == 1 and door_shut(w, r)
        press(w, ctl[i], B)
        w.passes(1)
        assert w.blocks[ctl[i]] == DP.button(B, False), "the press is consumed"
        lit = [w.blocks.get((x, prog_y, r["iz0"])) == B["lamp_on"] for x in xs]
        assert lit == [k <= step for k in range(4)], (step, lit)
    assert w.get(hold(s, r), "dg.rs") == 2 and door_open(w, r)


def test_sequence_four_presses_in_one_keeper_pass_still_count_in_the_shown_order(mk):
    doc, w = mk()
    p, s = start(doc, w)
    b = built(doc, "seq")
    B = DP.blocks_of("mine")
    w.rolls = [0]
    r = into(doc, w, p, "seq")
    order, ctl = sequence_order(w, b)
    clock = w.get(p.name, "dg.clock")
    for i in order:
        press(w, ctl[i], B)
    w.passes(1)
    assert w.get(hold(s, r), "dg.rs") == 2 and w.get(p.name, "dg.clock") == clock - 80, "no penalty for a quick hand"


def sequence_wrong(doc, w, p, s):
    b = built(doc, "seq")
    B = DP.blocks_of("mine")
    r = into(doc, w, p, "seq")
    order, ctl = sequence_order(w, b)
    press(w, ctl[order[0]], B)
    w.passes(1)
    wrong = next(i for i in range(4) if i != order[1])
    clock = w.get(p.name, "dg.clock")
    press(w, ctl[wrong], B)
    w.passes(1)
    pen = doc["engine"]["clock"]["fall_penalty_s"] * 80
    assert w.get(p.name, "dg.clock") == clock - 80 - pen
    assert w.get(hold(s, r) + "g", "dg.rs") == 0, "the sequence starts over"
    assert all(w.blocks[c] == DP.button(B, False) for c in ctl)
    prog_y = r["floor_in"] + 3
    assert not any(w.blocks.get((c[0], prog_y, r["iz0"])) == B["lamp_on"] for c in ctl), "the progress lamps go dark"
    assert w.get(hold(s, r), "dg.rs") == 1 and door_shut(w, r)
    return order, ctl, r


def test_sequence_a_wrong_button_charges_the_clock_and_starts_it_over(mk):
    doc, w = mk()
    p, s = start(doc, w)
    order, ctl, r = sequence_wrong(doc, w, p, s)
    B = DP.blocks_of("mine")
    for i in order:                                      # and it can still be solved from the top
        press(w, ctl[i], B)
        w.passes(1)
    assert w.get(hold(s, r), "dg.rs") == 2


def test_sequence_the_first_button_pressed_out_of_order_is_wrong_not_ignored(mk):
    doc, w = mk()
    p, s = start(doc, w)
    b = built(doc, "seq")
    B = DP.blocks_of("mine")
    r = into(doc, w, p, "seq")
    order, ctl = sequence_order(w, b)
    clock = w.get(p.name, "dg.clock")
    press(w, ctl[order[1]], B)
    w.passes(1)
    assert w.get(p.name, "dg.clock") == clock - 80 - doc["engine"]["clock"]["fall_penalty_s"] * 80


# ------------------------------------------------------------------------------------------------- plates


def plate_order(w, b):
    r = b.room
    fy, iz0 = r["floor_in"], r["iz0"]
    cells = [tuple(a[:3]) for a in b.anchors["controls"]]
    tile = {i: b.grid.block_at(c[0], fy - 1, c[2]) for i, c in enumerate(cells)}
    row = [w.blocks.get((x, fy + 2, iz0)) for x in range(r["ix0"], r["ix1"] + 1)]
    row = [v for v in row if v in tile.values()]
    return [next(i for i, t in tile.items() if t == colour) for colour in row], cells


def step_on(w, pos, B):
    w.blocks[pos] = B["plate"] + "[powered=true]"


def test_plates_stepping_in_the_shown_order_lights_each_tile_removes_the_plate_and_clears(mk):
    doc, w = mk()
    p, s = start(doc, w)
    b = built(doc, "plt")
    B = DP.blocks_of("mine")
    w.rolls = [3]
    r = into(doc, w, p, "plt")
    order, cells = plate_order(w, b)
    assert sorted(order) == list(range(4)) and order != [0, 1, 2, 3] and order == b.meta["variants"][3]
    fy = r["floor_in"]
    for n, i in enumerate(order):
        step_on(w, cells[i], B)
        w.passes(1)
        assert w.blocks[cells[i]] == "minecraft:air", "a stepped plate is removed, so standing on it cannot count twice"
        assert w.blocks[(cells[i][0], fy - 1, cells[i][2])] == B["lamp_on"]
    assert w.get(hold(s, r), "dg.rs") == 2 and door_open(w, r)


def test_plates_a_wrong_plate_charges_the_clock_sends_the_member_back_and_restores_the_field(mk):
    doc, w = mk()
    p, s = start(doc, w)
    b = built(doc, "plt")
    B = DP.blocks_of("mine")
    r = into(doc, w, p, "plt")
    order, cells = plate_order(w, b)
    fy = r["floor_in"]
    step_on(w, cells[order[0]], B)
    w.passes(1)
    wrong = next(i for i in range(4) if i != order[1] and i != order[0])
    p.pos = [cells[wrong][0] + 0.5, fy, cells[wrong][2] + 0.5]
    step_on(w, cells[wrong], B)
    clock = w.get(p.name, "dg.clock")
    w.passes(1)
    assert w.get(p.name, "dg.clock") == clock - 80 - 10 * 80
    assert [int(v) for v in p.pos[:3]] == [r["ix0"] + 2, fy, r["z_in"]], "sent back to the door"
    for i, c in enumerate(cells):
        assert w.blocks[c] == B["plate"] + "[powered=false]" or w.blocks[c] == B["plate"], "every plate is back"
        assert w.blocks[(c[0], fy - 1, c[2])] == b.grid.block_at(c[0], fy - 1, c[2]), "every tile its own colour again"
    assert w.get(hold(s, r) + "g", "dg.rs") == 0 and w.get(hold(s, r), "dg.rs") == 1 and door_shut(w, r)


def test_plates_a_later_plate_stepped_on_too_early_is_wrong(mk):
    doc, w = mk()
    p, s = start(doc, w)
    b = built(doc, "plt")
    B = DP.blocks_of("mine")
    r = into(doc, w, p, "plt")
    order, cells = plate_order(w, b)
    clock = w.get(p.name, "dg.clock")
    step_on(w, cells[order[2]], B)
    w.passes(1)
    assert w.get(p.name, "dg.clock") == clock - 80 - 10 * 80


def test_plates_the_slot_reset_restores_the_field(mk):
    doc, w = mk()
    p, s = start(doc, w)
    b = built(doc, "plt")
    B = DP.blocks_of("mine")
    r = into(doc, w, p, "plt")
    order, cells = plate_order(w, b)
    step_on(w, cells[order[0]], B)
    w.passes(1)
    assert w.blocks[cells[order[0]]] == "minecraft:air"
    reset_slot(w, p, s)
    assert w.blocks[cells[order[0]]].startswith(B["plate"]) and w.get(hold(s, r) + "g", "dg.rs") == 0


# ------------------------------------------------------------------------------------------------- vault


def chest_cells(b):
    return [tuple(c) for c in b.meta["chest_cells"]]


def vault_world(mk, band=1, rooms=None):
    doc, w = mk("mine", rooms)
    p, s = start(doc, w)
    w.set(p.name, "dg.band", band)
    reset_slot(w, p, s)
    return doc, w, p, s


def test_vault_the_reset_places_every_chest_from_air_with_the_entrants_bands_table(mk):
    for band, want in ((1, "cobblers:dungeons/vault/night_shift/vlt/b1"), (3, "cobblers:dungeons/vault/night_shift/vlt/b1"),
                       (4, "minecraft:chests/simple_dungeon"), (6, "minecraft:chests/simple_dungeon")):
        doc, w, p, s = vault_world(mk, band)
        b = built(doc, "vlt")
        assert [w.loot.get(c) for c in chest_cells(b)] == [want] * 4, band
        reset_slot(w, p, s)         # and again: a chest onto the same chest state would fail and keep the old table
        assert [w.loot.get(c) for c in chest_cells(b)] == [want] * 4, band
        w.set(p.name, "dg.band", 6 if band < 4 else 1)
        reset_slot(w, p, s)
        assert w.loot[chest_cells(b)[0]] != want, "a new entrant's band replaces the table"


def test_vault_each_chest_opened_costs_the_clock_once_and_a_chest_is_never_charged_twice(mk):
    doc, w, p, s = vault_world(mk, 1)
    b = built(doc, "vlt")
    r = into(doc, w, p, "vlt")
    cells = chest_cells(b)
    clock = w.get(p.name, "dg.clock")
    w.passes(2)
    assert w.get(p.name, "dg.clock") == clock - 160, "unopened chests cost nothing"
    del w.loot[cells[2]]                        # chest 2 is opened: its LootTable is gone
    clock = w.get(p.name, "dg.clock")
    w.passes(1)
    assert w.get(p.name, "dg.clock") == clock - 80 - 25 * 80
    w.passes(2)
    assert w.get(p.name, "dg.clock") == clock - 80 - 25 * 80 - 160, "the same chest is not charged again"
    del w.loot[cells[0]], w.loot[cells[1]]
    clock = w.get(p.name, "dg.clock")
    w.passes(1)
    assert w.get(p.name, "dg.clock") == clock - 80 - 2 * 25 * 80, "two chests opened between two looks are two charges"
    assert w.get(hold(s, r), "dg.rs") == 1
    del w.loot[cells[3]]
    w.passes(1)
    assert w.get(hold(s, r), "dg.rs") == 2, "the vault is done when every chest is"
    assert w.get(p.name, "dg.greed") in (None, 0), "no ladder unless the record asks"


def test_vault_the_reset_rearms_every_chest(mk):
    doc, w, p, s = vault_world(mk, 1)
    b = built(doc, "vlt")
    r = into(doc, w, p, "vlt")
    cells = chest_cells(b)
    del w.loot[cells[1]]
    w.passes(1)
    reset_slot(w, p, s)
    assert all(c in w.loot for c in cells) and w.get(hold(s, r), "dg.rs") == 0
    into(doc, w, p, "vlt")
    clock = w.get(p.name, "dg.clock")
    del w.loot[cells[1]]
    w.passes(1)
    assert w.get(p.name, "dg.clock") == clock - 80 - 25 * 80, "the re-armed chest charges again in the next run"


def test_vault_with_the_ladder_on_each_chest_also_counts_as_a_greed_block(mk):
    rooms = [dict(r, params=dict(r["params"], ladder=True)) if r["id"] == "vlt" else r for r in FIX]
    doc, w, p, s = vault_world(mk, 1, rooms)
    b = built(doc, "vlt")
    into(doc, w, p, "vlt")
    cells = chest_cells(b)
    del w.loot[cells[0]]
    w.passes(1)
    assert w.get(p.name, "dg.greed") == 1


# ------------------------------------------------------------------------------------------------- mutations of the generator


def test_mutating_order_perms_to_the_identity_is_refused_by_the_checks(monkeypatch):
    monkeypatch.setattr(DP, "order_perms", lambda d, room, n, salt: [list(range(n))])
    problems = R.problems(pdoc("mine"))
    assert any("not a solvable target" in p for p in problems), problems


def test_mutating_lever_patterns_to_all_dark_is_refused_by_the_checks(monkeypatch):
    monkeypatch.setattr(DP, "lever_patterns", lambda d, room, n: [[False] * n])
    assert any("not a solvable target" in p for p in R.problems(pdoc("mine")))


def test_mutating_plate_cells_onto_the_door_line_is_refused_by_the_checks(monkeypatch):
    def on_the_line(c, n):
        r = c.room
        return [(r["ix0"] + 8 + 7 * i, r["z_in"]) for i in range(n)]
    monkeypatch.setattr(DP, "plate_cells", on_the_line)
    assert any("door" in p and "plate" in p for p in R.problems(pdoc("mine"))), R.problems(pdoc("mine"))


def test_mutating_the_panel_off_its_wall_leaves_a_lever_with_nothing_to_hang_on(monkeypatch):
    real = DP.panel_xs
    monkeypatch.setattr(DP, "panel_xs", lambda room, n: (real(room, n)[0], [x for x in real(room, n)[1]]))
    orig = DP.build_levers

    def floating(c):
        res = orig(c)
        res["blocks"] = [op for op in res["blocks"] if not (op[0] == "fill" and op[2] == c.B["console"])]
        return res
    monkeypatch.setitem(DP.BUILDERS, "levers", floating)
    assert any("not solid" in p or "overwrote" in p for p in R.problems(pdoc("mine"))), R.problems(pdoc("mine"))


def test_mutating_the_penalty_to_nothing_fails_the_wrong_attempt_test(monkeypatch, tmp_path_factory):
    monkeypatch.setattr(DP, "penalty_lines", lambda c, msg: [])
    R._BUILT.clear()
    doc, w = world("mine", None, tmp_path_factory, cache={})
    p, s = start(doc, w)
    with pytest.raises(AssertionError):
        levers_wrong_attempt(doc, w, p, s)


def test_mutating_the_chest_cost_to_free_fails_the_vault_cost_test(monkeypatch, tmp_path_factory):
    real = DP.U
    monkeypatch.setattr(DP, "U", lambda doc: 0)
    R._BUILT.clear()
    doc, w = world("mine", None, tmp_path_factory, cache={})
    p, s = start(doc, w)
    w.set(p.name, "dg.band", 1)
    reset_slot(w, p, s)
    b = built(doc, "vlt")
    into(doc, w, p, "vlt")
    clock = w.get(p.name, "dg.clock")
    del w.loot[chest_cells(b)[0]]
    w.passes(1)
    assert w.get(p.name, "dg.clock") != clock - 80 - 25 * 80, "a free chest is not what the record says"
    assert real(doc) == 80
