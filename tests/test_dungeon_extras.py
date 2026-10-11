"""The three extra room kinds (tools/dungeon_extras.py, unit RT-A): bank_vault, wishing_well, bait_room.

Three layers, each independent of the generator it checks where it can be:
  * the record and the build: the fixture (tests/fixtures/dungeon_extras_rooms.json) builds with no problem and no warning
    in all three themes, the kit's walk check, pits and light coverage included; the tables are checked against GREED's
    table and the jars; an existing dungeon's pack is untouched;
  * the functions, run on the pocket simulator (PW from tests/test_dungeon_puzzles.py plus this file's small additions:
    sign text by `data modify block`, item entities by `Item.id` and `Item.count`, `give` of a plain id). `random value`
    is PW's (a queue of forced rolls, else seeded); nothing was added to tests/pocket_sim.py;
  * generator mutations a test catches: the expectation moves with nothing the mutated code owns.
Expected pays are computed here from data/dungeon_extras.json and data/dungeon_greed.json with this file's own arithmetic,
never from the generated functions. What none of this proves is the game: see the module docstring.
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
import dungeon_clock as DC  # noqa: E402
import dungeon_extras as DX  # noqa: E402
import dungeon_greed as DG  # noqa: E402
import dungeon_grid as G  # noqa: E402
import dungeon_puzzles as DP  # noqa: E402
import dungeon_rooms as R  # noqa: E402
import pocket_sim as PS  # noqa: E402
import test_dungeon as TD  # noqa: E402
import test_dungeon_rooms as TR  # noqa: E402
from test_dungeon_puzzles import PW  # noqa: E402

FIX = json.loads((ROOT / "tests" / "fixtures" / "dungeon_extras_rooms.json").read_text(encoding="utf-8"))["rooms"]
POCKET = TR.POCKET
U1 = TR.BASE["engine"]["clock"]["units_per_tick"] * 20
THEMES = ("mine", "jungle", "flooded_ruin")
XDATA = json.loads((ROOT / "data" / "dungeon_extras.json").read_text(encoding="utf-8"))
GREED = json.loads((ROOT / "data" / "dungeon_greed.json").read_text(encoding="utf-8"))
THEMEDOC = json.loads((ROOT / "data" / "dungeon_themes.json").read_text(encoding="utf-8"))["themes"]


def xdoc(theme="mine", rooms=None):
    doc = TR.demo_doc(theme, rooms if rooms is not None else FIX)
    doc["dungeons"][0]["clock_s_by_band"] = DC.derive(doc, doc["dungeons"][0])
    return doc


@pytest.fixture(autouse=True)
def fresh_cache():
    R._BUILT.clear()
    DX._BUDGET.clear()
    yield
    R._BUILT.clear()
    DX._BUDGET.clear()


def built(doc, rid):
    d = doc["dungeons"][0]
    return next(b for b in R.slot_build(doc, d, D.slots(doc)[0]) if b.room["id"] == rid)


def room_of(doc, rid):
    return next(r for r in R.plan(doc, doc["dungeons"][0], D.slots(doc)[0]) if r["id"] == rid)


# ------------------------------------------------------------------------------------------------- the build


@pytest.mark.parametrize("theme", THEMES)
def test_the_fixture_builds_clean_in_every_theme_walk_check_pits_and_lights_included(theme):
    doc = xdoc(theme)
    assert R.problems(doc) == [] and D.warnings(doc) == [], (R.problems(doc), D.warnings(doc))
    # the checks really looked at the rooms: all three kinds are in the plan and built
    assert {r["kind"] for r in R.plan(doc, doc["dungeons"][0], D.slots(doc)[0])} >= set(DX.OWN_KINDS)


@pytest.mark.parametrize("theme", THEMES)
def test_every_block_the_kinds_place_exists_in_1_21_1_and_is_neither_banned_nor_breakable_by_the_pick(theme):
    ids = TR.vanilla_ids()
    pick = set(TR.BASE["engine"]["rift_pick"]["can_break"])
    doc = xdoc(theme)
    seen = set()
    for rid in ("bank", "well", "bait", "d1", "d2"):
        b = built(doc, rid)
        for op in b.ops:
            blk = op[2] if op[0] == "fill" else op[2]
            seen.add(G.base(blk))
    for blk in seen:
        assert not G.forbidden(blk) and G.classify(blk) != G.HAZARD, blk
        assert blk not in pick, blk
        if ids is not None and blk.startswith("minecraft:") and "sign" not in blk:
            assert blk in ids, (theme, blk)
    for sign in {THEMEDOC[theme]["crossroads"]["sign"]}:
        assert sign in G.PASSABLE, "a wall sign has no collision: the walk check must see through the keypad's signs"


def test_the_tables_are_clean_and_every_id_is_in_a_jar():
    doc = xdoc("mine")
    assert DX.table_problems(doc, force=True) == []
    for bait in XDATA["bait_room"]["baits"]:
        assert DX.item_known(bait["id"]) in (True, None), bait["id"]
    # the shares: weights sum to 100, a chance of nothing and a chance of more, the expected share under the cap
    for b, rows in XDATA["wishing_well"]["shares_by_band"].items():
        assert sum(w for w, _ in rows) == 100 and any(s == 0 for _, s in rows) and any(s > 100 for _, s in rows), b
        assert sum(w * s for w, s in rows) / 10000.0 <= XDATA["wishing_well"]["ev_cap"], b


def test_the_default_bank_loot_fits_the_vault_budget_of_the_real_dungeons():
    real = D.load()
    budget = DG.vault_budget(real)
    n = XDATA["bank_vault"]["defaults"]["chests"]
    loot = XDATA["bank_vault"]["default_loot_by_band"]
    for band in range(1, 7):
        key = max(k for k in map(int, loot) if k <= band)
        cp = DG.chest_cp(DG.load(), loot[str(key)])
        assert cp <= budget[band] // n, (band, cp, budget[band] // n)


def test_a_dungeon_with_none_of_the_kinds_is_untouched():
    real = D.load()
    assert DX.functions(real) == {} and DX.pack_files(real) == {}
    for s in D.slots(real):
        assert DX.start_lines(real, s) == [], s["g"]
    fns = {"load": ["a"], "slot/s1/start": ["b"]}
    before = copy.deepcopy(fns)
    DX.patch_functions(real, fns)
    assert fns == before


def assert_gate_shut_in_shell(doc, theme):
    b = built(doc, "bank")
    gate = THEMEDOC[theme]["door"]["gate"]
    r = room_of(doc, "bank")
    cx = (r["ix0"] + r["ix1"]) // 2
    pz = r["iz1"] - 7
    fy = r["floor_in"]
    want = ("fill", (cx - 1, fy, pz, cx + 1, fy + 3, pz), gate)
    assert want in b.gate_ops, "the shell writes the vault's gate last, closed"
    assert G.base(b.grid.block_at(cx, fy, pz)) == "minecraft:air", "the walk check's grid has it open, so the chamber is reached"
    # the chests stand behind it: a south-wall chest and a stand cell inside the chamber
    for c in b.meta["chest_cells"]:
        assert c[2] == r["iz1"] and c[1] == fy


@pytest.mark.parametrize("theme", THEMES)
def test_the_gate_is_shut_in_the_shell_and_open_in_the_walk_checks_grid(theme):
    assert_gate_shut_in_shell(xdoc(theme), theme)


@pytest.mark.parametrize("theme", THEMES)
def test_each_digit_sign_stands_over_its_button(theme):
    doc = xdoc(theme)
    b = built(doc, "bank")
    for k, (x, y, z) in b.meta["buttons"].items():
        assert G.base(b.grid.block_at(x, y, z)).endswith("_button")
        sign = b.grid.block_at(x, y + 1, z)
        assert "wall_sign" in sign and ("'\"%s\"'" % k) in sign, (k, sign)


@pytest.mark.parametrize("theme", THEMES)
def test_each_clue_room_holds_its_sign_on_a_wall_off_the_trail_and_the_slots_agree(theme):
    doc = xdoc(theme)
    d = doc["dungeons"][0]
    for rid, digits in (("d1", [0, 2]), ("d2", [1, 3])):
        b = built(doc, rid)
        sg = b.meta["clue_signs"]
        assert len(sg) == 1 and sg[0]["digits"] == digits and sg[0]["vault"] == "bank", sg
        x, y, z = sg[0]["pos"]
        assert "wall_sign" in b.grid.block_at(x, y, z)
        r = room_of(doc, rid)
        assert y == r["floor_in"] + 2 and r["ix0"] <= x <= r["ix1"] and r["iz0"] <= z <= r["iz1"]
    other = copy.deepcopy(doc)
    other["engine"]["slots"]["per_dungeon"] = 4
    R._BUILT.clear()
    s1, s3 = D.slots(other)[0], D.slots(other)[2]
    a = [b for b in R.slot_build(other, other["dungeons"][0], s1) if b.room["id"] == "d1"][0].meta["clue_signs"][0]["pos"]
    c = [b for b in R.slot_build(other, other["dungeons"][0], s3) if b.room["id"] == "d1"][0].meta["clue_signs"][0]["pos"]
    assert [a[0], a[1]] == [c[0], c[1]] and a[2] - s1["z0"] == c[2] - s3["z0"], "one dungeon, four slots: the same sign place"


def _well(rooms):
    return next(r for r in rooms if r["id"] == "well")


def _bank(rooms):
    return next(q for r in rooms if r["kind"] == "side" for q in r["rooms"] if q["kind"] == "bank_vault")


def _bait(rooms):
    return next(r for r in rooms if r["kind"] == "bait_room")


def _problems_of(mutate):
    """The problems of the fixture after `mutate`, or the build's refusal text (a kind that cannot be built raises)."""
    rooms = copy.deepcopy(FIX)
    mutate(rooms)
    try:
        return R.problems(xdoc("mine", rooms))
    except R.RoomError as e:
        return [str(e)]


REFUSALS = [
    (lambda r: _well(r).update(width=11), "wishing well needs a room"),
    (lambda r: _bank(r)["params"].update(clue_rooms=["d1", "nowhere"]), "not a room of this dungeon"),
    (lambda r: _bank(r)["params"].update(clue_rooms=[]), "clue_rooms is a list of distinct room ids"),
    (lambda r: _bank(r)["params"].update(clue_rooms=["entry", "d2"]), "cannot be this vault, the entry"),
    (lambda r: _bank(r)["params"].update(digits=5, clue_rooms=["d1"]), "more than 3 to a sign"),
    (lambda r: _bank(r)["params"].update(digits=2), "params.digits must be an integer 3..5"),
    (lambda r: _bank(r).update(width=17), "a bank vault needs a room"),
    (lambda r: _bank(r).update(gate="cleared"), "gate must be open"),
    (lambda r: _bait(r)["params"].update(lure_room="arena"), "is not a living room"),
    (lambda r: _bait(r)["params"].update(lure_room="bait"), "is not a living room"),
    (lambda r: _bait(r)["params"].update(lure_room="ghost"), "lure_room 'ghost' is not a room"),
    (lambda r: _bank(r)["params"].update(loot_by_band={"1": [{"item": "minecraft:diamond", "count": 8}]}), "over the vault budget"),
    (lambda r: _bank(r)["params"].update(loot_by_band={"1": [{"item": "minecraft:bedrock", "count": 1}]}), "not priced"),
]


@pytest.mark.parametrize("mutate,want", REFUSALS)
def test_the_kinds_refuse_what_cannot_work(mutate, want):
    assert any(want in p for p in _problems_of(mutate)), (want, _problems_of(mutate))


def test_a_vault_is_optional_by_route_only_a_side_entry_or_an_optional_fork_route_counts():
    on = DX._on_optional_route
    assert on({"route": "wing"}) and on({"route": "f1/loop", "optional": True})
    assert not on({"route": "main"}) and not on({"route": "f1/fast"}) and not on({"route": "f1/fast", "optional": False})


def test_mutating_the_route_rule_lets_a_vault_onto_the_required_path_and_the_check_says_so(monkeypatch):
    monkeypatch.setattr(DX, "_on_optional_route", lambda room: False)
    assert any("never on the required path" in p for p in R.problems(xdoc("mine")))


# ------------------------------------------------------------------------------------------------- the simulator


class XW(PW):
    """PW plus what these kinds use: `Item.id` and `Item.count` of item entities, `give` of a plain id, sign text rewritten by
    `data modify block ... front_text.messages[n] set value`, and an entity's `Item.count` set by `execute store result entity`."""

    DATENT = re.compile(r'\b(if|unless) data entity @s \{Item:\{id:"([^"]+)"\}\}')

    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.signs = {}

    @staticmethod
    def slug(i):
        return re.sub(r"[^a-z0-9]", "_", i)

    def run(self, cmd, ctx, from_macro=False):
        for e in self.ents:
            if e.kind == "minecraft:item":
                e.tags = {t for t in e.tags if not t.startswith("__it_")} | {"__it_" + self.slug(e.nbt["Item"]["id"])}
        cmd = self.DATENT.sub(lambda m: "%s entity @s[tag=__it_%s]" % (m.group(1), self.slug(m.group(2))), cmd)
        return super().run(cmd, ctx, from_macro)

    def execute(self, t, ctx, from_macro):
        if t[:3] == ["store", "result", "entity"]:
            v = self.run_tokens(t[t.index("run") + 1:], ctx, from_macro)
            self.one(t[3], ctx).nbt["Item"]["count"] = int(v)
            return v
        return super().execute(t, ctx, from_macro)

    def run_tokens(self, t, ctx, from_macro=False, raw=None):
        if t[:3] == ["data", "get", "entity"] and t[4] == "Item.count":
            return int(self.one(t[3], ctx).nbt["Item"]["count"])
        if t[:3] == ["data", "modify", "block"]:
            pos = (int(t[3]), int(t[4]), int(t[5]))
            m = re.fullmatch(r"front_text\.messages\[(\d)\]", t[6])
            assert m and t[7:9] == ["set", "value"], t
            self.signs.setdefault(pos, ["", "", "", ""])[int(m.group(1))] = json.loads(json.loads(t[9][1:-1].replace("\\'", "'")) and t[9][1:-1])
            return 1
        if t[0] == "give" and "[" not in t[2]:
            for e in self.select(t[1], ctx):
                e.inventory.append([t[2], {}, int(t[3]) if len(t) > 3 else 1])
            return 1
        return super().run_tokens(t, ctx, from_macro, raw)


def world(theme="mine", rooms=None, tmp_path_factory=None, cache={}):
    doc = xdoc(theme, rooms)
    key = (theme, json.dumps(rooms, sort_keys=True))
    if key not in cache:
        out = Path(tmp_path_factory.mktemp("cobblers_extras"))
        D.write(D.build(doc), out)
        cache[key] = out
    w = XW(cache[key], dict(TD.FAKES))
    w.objectives |= {"cobblers.lc_cap", "tailend", "stale"}
    w.boot()
    return doc, w


@pytest.fixture
def mk(tmp_path_factory):
    return lambda theme="mine", rooms=None: world(theme, rooms, tmp_path_factory)


def start(doc, w, rolls=()):
    w.rolls = list(rolls)
    p, s = TR.enter_run(doc, w)
    w.rolls = []
    return p, s


def into(doc, w, p, rid, dx=4):
    r = room_of(doc, rid)
    p.pos = [r["ix0"] + dx + 0.5, r["floor_in"], r["z_in"] + 0.5]
    w.passes(1)
    return r


def hold(s, r, tag=""):
    return "#s%dr%d%s" % (s["g"], r["i"], tag)


def reset_slot(w, p, s):
    w.call("cobblers:dungeons/slot/s%d/reset" % s["g"], PS.Ctx(p, POCKET, p.pos))


def second_run(doc, w, p):
    """The same player ends a run by the far rip and starts another (the lockout cleared: it is the engine's, not under test)."""
    w.call("cobblers:dungeons/far", PS.Ctx(p, p.dim, p.pos))
    w.passes(8)
    w.scores.pop((p.name, "dg.lk_ns"), None)
    p.inventory.append(TD.soot())
    p.dim, p.pos = "minecraft:overworld", [1352.5, 130.0, 4120.5]
    w.call("cobblers:dungeons/door/ns", PS.Ctx(p, p.dim, p.pos))
    w.passes(4)
    assert p.dim == POCKET and w.get(p.name, "dg.st") == 2
    s = D.slots(doc)[w.get(p.name, "dg.slot") - 1]
    p.pos = [D.points(doc, s)["threshold_x"] + 1.5, 96.0, s["cz"] + 0.5]
    w.passes(1)
    assert w.get(p.name, "dg.st") == 3
    return s


def drop(w, r, item, n=1, where=None):
    """An item entity resting in the room's pool (well) or on its altar (bait): at the place the room is built round."""
    cx, cz = (r["ix0"] + r["ix1"]) // 2, (r["iz0"] + r["iz1"]) // 2
    y = r["floor_in"] + (0.2 if where == "well" else 1.1)
    e = PS.Ent("minecraft:item", POCKET, (cx + 0.5, y, cz + 0.5), nbt={"Item": {"id": item, "count": n}})
    w.ents.append(e)
    return e


def in_pool(r, e):
    cx, cz = (r["ix0"] + r["ix1"]) // 2, (r["iz0"] + r["iz1"]) // 2
    return e.alive and abs(e.pos[0] - (cx + 0.5)) <= 1.5 and abs(e.pos[2] - (cz + 0.5)) <= 1.5 and e.pos[1] < r["floor_in"] + 1.5


# ------------------------------------------------------------------------------------------------- the bank vault


def digits_of(s, w, r, n=4):
    return [w.get(hold(s, r, "_d%d" % j), "dg.rs") for j in range(n)]


def press(w, b, k):
    w.blocks[tuple(b.meta["buttons"][str(k)])] = "%s[face=wall,facing=south,powered=true]" % DP.blocks_of("mine")["button"]
    w.passes(1)


def enter_code(w, b, code):
    for k in code:
        press(w, b, k)


def gate_cell(r):
    return ((r["ix0"] + r["ix1"]) // 2, r["floor_in"], r["iz1"] - 7)


def bank_world(mk, rolls=(3, 1, 4, 1), band=1):
    """A run at `band`, the slot reset again so its chests are placed for that band (the reset reads dg.band)."""
    doc, w = mk("mine", None)
    p, s = start(doc, w, rolls)
    w.set(p.name, "dg.band", band)
    reset_slot(w, p, s)
    return doc, w, p, s


def threshold_world(mk, rolls=(3, 1, 4, 1)):
    doc, w = mk("mine", None)
    p, s = start(doc, w, rolls)
    return doc, w, p, s


def assert_code_rolled(mk):
    doc, w, p, s = threshold_world(mk, (3, 1, 4, 1))
    r = room_of(doc, "bank")
    assert digits_of(s, w, r) == [3, 1, 4, 1] and w.get(hold(s, r, "_c"), "dg.rs") == 3141
    doc, w, p, s = threshold_world(mk, (0, 0, 7, 2))
    assert w.get(hold(s, room_of(doc, "bank"), "_c"), "dg.rs") == 72, "a leading zero is just a smaller number: 0072"


def test_the_threshold_rolls_the_code_from_random_value_and_builds_it_digit_by_digit(mk):
    assert_code_rolled(mk)


def test_the_signs_show_the_digits_only_in_the_clue_rooms_and_only_once_they_are_entered(mk):
    doc, w, p, s = threshold_world(mk, (3, 1, 4, 1))
    sg1 = tuple(built(doc, "d1").meta["clue_signs"][0]["pos"])
    sg2 = tuple(built(doc, "d2").meta["clue_signs"][0]["pos"])
    assert sg1 not in w.signs or all("?" in x or x == "" for x in w.signs[sg1]), "nothing is on the wall before the member comes"
    into(doc, w, p, "d1")
    assert w.signs[sg1][1:3] == ["NO.1: 3", "NO.3: 4"], w.signs.get(sg1)
    assert sg2 not in w.signs or "3" not in "".join(w.signs[sg2]), "the other sign is not written yet"
    into(doc, w, p, "d2")
    assert w.signs[sg2][1:3] == ["NO.2: 1", "NO.4: 1"], w.signs.get(sg2)


def test_a_second_run_rolls_another_code_and_the_reset_blanks_the_signs(mk):
    doc, w, p, s = threshold_world(mk, (3, 1, 4, 1))
    r = room_of(doc, "bank")
    sg1 = tuple(built(doc, "d1").meta["clue_signs"][0]["pos"])
    into(doc, w, p, "d1")
    assert w.signs[sg1][1] == "NO.1: 3"
    w.rolls = [9, 8, 7, 6]
    s2 = second_run(doc, w, p)
    assert digits_of(s2, w, r) == [9, 8, 7, 6] and w.get(hold(s2, r, "_c"), "dg.rs") == 9876, "the code is not the last run's"
    assert w.signs[sg1][1] == "NO.1: ?", "the slot's reset put the wall back to '?': a stale digit never shows"


def test_the_right_code_opens_the_gate_and_costs_the_clock_nothing_extra(mk):
    doc, w, p, s = threshold_world(mk, (3, 1, 4, 1))
    b = built(doc, "bank")
    r = into(doc, w, p, "bank")
    gx, gy, gz = gate_cell(r)
    gate = THEMEDOC["mine"]["door"]["gate"]
    assert w.blocks[(gx, gy, gz)] == gate, "shut by the slot's reset"
    clock = w.get(p.name, "dg.clock")
    rate = w.get(p.name, "dg.rate")
    enter_code(w, b, [3, 1, 4, 1])
    assert w.blocks[(gx, gy, gz)] == "minecraft:air" and w.blocks[(gx + 1, gy + 3, gz)] == "minecraft:air"
    assert w.get(hold(s, r), "dg.rs") == 2
    assert w.get(p.name, "dg.clock") == clock - 4 * 20 * rate, "four passes of ordinary clock, no penalty"
    assert [w.blocks[tuple(l)] for l in b.meta["lamps"]] == [DP.blocks_of("mine")["lamp_on"]] * 4


def test_a_wrong_code_charges_the_penalty_blanks_the_lamps_and_starts_over(mk):
    doc, w, p, s = threshold_world(mk, (3, 1, 4, 1))
    b = built(doc, "bank")
    r = into(doc, w, p, "bank")
    clock = w.get(p.name, "dg.clock")
    rate = w.get(p.name, "dg.rate")
    enter_code(w, b, [3, 1, 4, 2])
    assert w.get(p.name, "dg.clock") == clock - 4 * 20 * rate - 20 * U1, "20 s for a wrong code, on top of the passes"
    assert w.get(hold(s, r, "_w"), "dg.rs") == 1 and w.get(hold(s, r, "_e"), "dg.rs") == 0 and w.get(hold(s, r, "_v"), "dg.rs") == 0
    assert [w.blocks[tuple(l)] for l in b.meta["lamps"]] == [DP.blocks_of("mine")["lamp_off"]] * 4
    assert w.blocks[gate_cell(r)] == THEMEDOC["mine"]["door"]["gate"]
    clock = w.get(p.name, "dg.clock")
    enter_code(w, b, [3, 1, 4, 1])
    assert w.blocks[gate_cell(r)] == "minecraft:air", "and the right code still opens it afterwards"
    assert w.get(p.name, "dg.clock") == clock - 4 * 20 * rate


def test_five_wrong_codes_jam_the_lock_for_the_run_and_the_room_is_optional_so_nothing_is_trapped(mk):
    doc, w, p, s = threshold_world(mk, (3, 1, 4, 1))
    b = built(doc, "bank")
    r = into(doc, w, p, "bank")
    for _ in range(5):
        enter_code(w, b, [0, 0, 0, 0])
    assert w.get(hold(s, r, "_j"), "dg.rs") == 1
    enter_code(w, b, [3, 1, 4, 1])
    assert w.blocks[gate_cell(r)] == THEMEDOC["mine"]["door"]["gate"] and w.get(hold(s, r), "dg.rs") == 1
    assert r["gate"] == "open" and r["door_out"] is None, "a dead end off a wing; the main way never passes through it"


def test_digits_pressed_in_one_keeper_pass_are_read_in_ascending_order_a_known_limit(mk):
    # the keypad is read once per keeper pass (1 s): two buttons down at one look cannot be ordered
    doc, w, p, s = threshold_world(mk, (3, 1, 4, 1))
    b = built(doc, "bank")
    r = into(doc, w, p, "bank")
    for k in (4, 1):
        w.blocks[tuple(b.meta["buttons"][str(k)])] = "%s[face=wall,facing=south,powered=true]" % DP.blocks_of("mine")["button"]
    w.passes(1)
    assert w.get(hold(s, r, "_v"), "dg.rs") == 14 and w.get(hold(s, r, "_e"), "dg.rs") == 2


def test_each_chest_weighs_its_loot_once_charges_the_clock_once_and_the_reset_rearms_the_lot(mk):
    doc, w, p, s = threshold_world(mk, (3, 1, 4, 1))
    b = built(doc, "bank")
    r = into(doc, w, p, "bank")
    cells = [tuple(c) for c in b.meta["chest_cells"]]
    assert [w.loot.get(c) for c in cells] == ["cobblers:dungeons/bank/night_shift/bank/b1"] * 4
    want = round(2.5 * GREED["items"]["minecraft:iron_ingot"]["cp"])        # the fixture's band-1 chest: 2-3 iron ingots
    gp0 = w.get(p.name, "dg.gp") or 0
    clock = w.get(p.name, "dg.clock")
    rate = w.get(p.name, "dg.rate")
    del w.loot[cells[1]]
    w.passes(1)
    assert w.get(p.name, "dg.gp") - gp0 == want
    assert w.get(p.name, "dg.clock") < clock - 20 * rate - 20 * U1 + 1 and w.get(p.name, "dg.clock") >= clock - 20 * rate - 20 * U1 - 1, \
        "20 s for the chest on top of the pass"
    w.passes(3)
    assert w.get(p.name, "dg.gp") - gp0 == want, "an open chest is weighed once"
    reset_slot(w, p, s)
    assert all(c in w.loot for c in cells) and w.blocks[gate_cell(r)] == THEMEDOC["mine"]["door"]["gate"]
    assert w.get(hold(s, r, "_c"), "dg.rs") == 0 and w.get(hold(s, r), "dg.rs") == 0, "the run's code is gone with the run"


def test_the_chests_of_a_band_come_from_that_bands_table_and_the_loot_tables_are_in_the_pack(mk):
    files = D.build(xdoc("mine"))
    names = {k for k in files if "/loot_table/dungeons/bank/" in k}
    assert names == {"data/cobblers/loot_table/dungeons/bank/night_shift/bank/b%d.json" % k for k in (1, 3, 5)}
    t = json.loads(files["data/cobblers/loot_table/dungeons/bank/night_shift/bank/b3.json"])
    assert t["pools"][0]["entries"][0]["name"] == "minecraft:gold_ingot"
    for band, want in ((1, "b1"), (2, "b1"), (3, "b3"), (4, "b3"), (5, "b5"), (6, "b5")):
        doc, w, p, s = bank_world(mk, band=band)
        c = [tuple(x) for x in built(doc, "bank").meta["chest_cells"]][0]
        assert w.loot[c].endswith("/" + want), (band, w.loot[c])


# ------------------------------------------------------------------------------------------------- the wishing well


def expected_pay(v, roll, band):
    """(item, count, credit) from data/dungeon_extras.json and data/dungeon_greed.json, by this file's own arithmetic."""
    w = XDATA["wishing_well"]
    lo = 1
    share = 0
    for weight, sh in w["shares_by_band"][str(band)]:
        if lo <= roll < lo + weight:
            share = sh
        lo += weight
    amount = v * share // 100
    ladder = [(it, GREED["items"][it]["cp"]) for it, _n in w["ladders_by_band"][str(band)]]
    pick = [x for x in ladder if x[1] <= amount]
    if not pick:
        return None, 0, 0
    item, cp = pick[-1]
    q = min(64, amount // cp)
    return item, q, max(0, q * cp - v)


def well_world(mk, band=1, theme="mine"):
    doc, w = mk(theme, None)
    p, s = start(doc, w)
    w.set(p.name, "dg.band", band)
    r = into(doc, w, p, "well")
    return doc, w, p, s, r


def inv(p, item):
    return sum(i[2] for i in p.inventory if i[0] == item)


def assert_pay(mk, roll):
    doc, w, p, s, r = well_world(mk)
    item, q, credit = expected_pay(100, roll, 1)         # one diamond: 100 cp (GREED, the owner's anchor)
    gp0 = w.get(p.name, "dg.gp") or 0
    e = drop(w, r, "minecraft:diamond", 1, "well")
    w.rolls = [roll]
    w.passes(1)
    assert not e.alive, "the well takes the gift"
    assert (inv(p, item) if item else 0) == q
    assert w.get(p.name, "dg.gp") - gp0 == credit
    assert w.get(hold(s, r, "_t"), "dg.rs") == 1


@pytest.mark.parametrize("roll", [10, 40, 50, 64, 70, 85, 95, 100])
def test_the_pay_is_the_rolled_share_rounded_down_into_the_dearest_item_it_reaches_and_only_a_gain_is_charged(mk, roll):
    assert_pay(mk, roll)


def test_a_stack_is_worth_the_sum_and_the_pay_is_capped(mk):
    doc, w, p, s, r = well_world(mk)
    gp0 = w.get(p.name, "dg.gp") or 0
    drop(w, r, "minecraft:iron_ingot", 10, "well")            # 90 cp
    w.rolls = [85]                                             # 200%: 180 cp
    w.passes(1)
    item, q, credit = expected_pay(90, 85, 1)
    assert inv(p, item) == q and w.get(p.name, "dg.gp") - gp0 == credit and q * 22 == 176 and credit == 86
    cap = XDATA["wishing_well"]["limits"]["max_count"]
    doc, w, p, s, r = well_world(mk)
    drop(w, r, "minecraft:diamond", 64, "well")                # 6,400 cp, 500%: 32,000 cp of gold ingots, capped at 64
    w.rolls = [100]
    w.passes(1)
    assert inv(p, "minecraft:gold_ingot") == cap


def test_nothing_is_a_real_outcome_and_a_loss_is_never_refunded(mk):
    doc, w, p, s, r = well_world(mk)
    w.set(p.name, "dg.gp", 500)
    drop(w, r, "minecraft:diamond", 1, "well")
    w.rolls = [5]
    w.passes(1)
    assert not [i for i in p.inventory if i[0] in ("minecraft:coal", "minecraft:iron_ingot", "minecraft:gold_ingot")]
    assert w.get(p.name, "dg.gp") == 500, "GREED's points only rise: the gift is gone, the points stay"


@pytest.mark.parametrize("item,n,why", [
    ("minecraft:dirt", 64, "unpriced: not in GREED's table at all"),
    ("cobblemon:rare_candy", 64, "a placeholder price (source 'unpriced', 1 cp): 64 of them reach min_cp"),
    ("cobblemon:exp_candy_xl", 64, "the same"),
    ("minecraft:coal", 2, "under min_cp (10 cp of 20)"),
])
def test_a_worthless_gift_is_refused_and_thrown_back_without_using_a_throw(mk, item, n, why):
    assert_refused(mk, item, n, why)


def assert_refused(mk, item, n, why=""):
    doc, w, p, s, r = well_world(mk)
    gp0 = w.get(p.name, "dg.gp") or 0
    e = drop(w, r, item, n, "well")
    w.rolls = [99]
    w.passes(1)
    assert e.alive and not in_pool(r, e), why
    assert w.get(hold(s, r, "_t"), "dg.rs") == 0 and w.get(p.name, "dg.gp") == gp0
    assert not [i for i in p.inventory if i[0] in ("minecraft:coal", "minecraft:iron_ingot", "minecraft:gold_ingot")]
    w.passes(3)
    assert e.alive and not in_pool(r, e), "and it stays out: no message every second, no throw spent"


def test_a_mega_stone_is_priced_and_taken_like_any_other_valued_item(mk):
    stone = GREED["groups"]["mega_stones"]["ids"][0]
    doc, w, p, s, r = well_world(mk, band=5)
    e = drop(w, r, stone, 1, "well")
    w.rolls = [64]                                      # 100%: 625 cp back
    w.passes(1)
    assert not e.alive
    item, q, credit = expected_pay(GREED["groups"]["mega_stones"]["cp"], 64, 5)
    assert inv(p, item) == q and q > 0


def test_at_most_throws_a_run_then_the_well_is_dry_and_gives_the_gift_back(mk):
    doc, w, p, s, r = well_world(mk)
    for _ in range(2):
        drop(w, r, "minecraft:diamond", 1, "well")
        w.rolls = [64]
        w.passes(1)
    assert w.get(hold(s, r, "_t"), "dg.rs") == 2
    third = drop(w, r, "minecraft:diamond", 1, "well")
    n = inv(p, "minecraft:gold_ingot")
    w.rolls = [64]
    w.passes(2)
    assert third.alive and not in_pool(r, third) and inv(p, "minecraft:gold_ingot") == n, "a third throw is not taken"
    assert w.get(hold(s, r, "_t"), "dg.rs") == 2


def test_two_gifts_in_one_pass_are_taken_one_a_pass_not_both_for_one_roll(mk):
    doc, w, p, s, r = well_world(mk)
    a = drop(w, r, "minecraft:diamond", 1, "well")
    b = drop(w, r, "minecraft:diamond", 1, "well")
    w.rolls = [64, 64]
    w.passes(1)
    assert [a.alive, b.alive].count(False) == 1 and w.get(hold(s, r, "_t"), "dg.rs") == 1
    w.passes(1)
    assert not a.alive and not b.alive and w.get(hold(s, r, "_t"), "dg.rs") == 2


def test_the_slot_reset_gives_the_next_run_its_throws_back(mk):
    doc, w, p, s, r = well_world(mk)
    for _ in range(2):
        drop(w, r, "minecraft:diamond", 1, "well")
        w.rolls = [64]
        w.passes(1)
    reset_slot(w, p, s)
    assert w.get(hold(s, r, "_t"), "dg.rs") == 0
    into(doc, w, p, "well")
    drop(w, r, "minecraft:diamond", 1, "well")
    w.rolls = [64]
    w.passes(1)
    assert w.get(hold(s, r, "_t"), "dg.rs") == 1


@pytest.mark.parametrize("band", [1, 2, 3, 4, 5, 6])
def test_no_roll_and_no_item_beats_the_bank_the_pay_never_exceeds_the_share_of_the_value(mk, band):
    # the property that makes the gamble safe: whatever the roll, the pay is at most share x value, and every band's
    # expected share is under the cap. Exhaustive over the 100 rolls and a spread of gifts, by this file's arithmetic
    cap = XDATA["wishing_well"]["ev_cap"]
    total = {}
    for v in (20, 45, 100, 450, 2100, 6400):
        paid = 0
        for roll in range(1, 101):
            item, q, credit = expected_pay(v, roll, band)
            got = q * GREED["items"][item]["cp"] if item else 0
            share = next(sh for lo, hi, sh in _bands(band) if lo <= roll <= hi)
            assert got <= v * share // 100, (band, v, roll)
            paid += got
        total[v] = paid / 100.0 / v
        assert total[v] <= cap, (band, v, total[v])


def _bands(band):
    lo, out = 1, []
    for w, sh in XDATA["wishing_well"]["shares_by_band"][str(band)]:
        out.append((lo, lo + w - 1, sh))
        lo += w
    return out


# ------------------------------------------------------------------------------------------------- the bait room


def bait_world(mk, band=1, rolls=()):
    doc, w = mk("mine", None)
    p, s = start(doc, w, rolls)
    w.set(p.name, "dg.band", band)
    r = into(doc, w, p, "bait")
    return doc, w, p, s, r


def test_a_bait_left_on_the_altar_is_taken_and_stored_on_the_player(mk):
    doc, w, p, s, r = bait_world(mk)
    e = drop(w, r, "cobblemon:oran_berry", 1, "bait")
    w.passes(1)
    assert not e.alive and w.get(p.name, "dg.bait") == 1
    e2 = drop(w, r, "cobblemon:razz_berry", 1, "bait")
    w.passes(2)
    assert e2.alive and not (abs(e2.pos[2] - ((r["iz0"] + r["iz1"]) // 2 + 0.5)) < 1.5), "one bait at a time: the second is returned"
    assert w.get(p.name, "dg.bait") == 1


def test_a_stack_gives_one_and_the_rest_comes_back(mk):
    doc, w, p, s, r = bait_world(mk)
    e = drop(w, r, "cobblemon:sitrus_berry", 5, "bait")
    w.passes(1)
    assert e.alive and e.nbt["Item"]["count"] == 4 and w.get(p.name, "dg.bait") == 4
    w.passes(2)
    assert e.alive and e.nbt["Item"]["count"] == 4 and w.get(p.name, "dg.bait") == 4, "the rest is not eaten: it is sent back out"
    assert abs(e.pos[2] - ((r["iz0"] + r["iz1"]) // 2 + 0.5)) > 1.5


def test_a_gift_that_is_no_bait_is_thrown_back_and_stores_nothing(mk):
    doc, w, p, s, r = bait_world(mk)
    e = drop(w, r, "minecraft:diamond", 1, "bait")
    w.passes(2)
    assert e.alive and (w.get(p.name, "dg.bait") or 0) == 0
    assert abs(e.pos[2] - ((r["iz0"] + r["iz1"]) // 2 + 0.5)) > 1.5


def lure_species(w):
    return [(e.nbt["Pokemon"]["Species"], e.nbt["Pokemon"]["Level"], e) for e in w.spawned if e.alive and "dg.lure" in e.tags]


def assert_lure_once_and_consumed(mk):
    doc, w, p, s, r = bait_world(mk, band=1)
    drop(w, r, "cobblemon:oran_berry", 1, "bait")
    w.passes(1)
    assert w.get(p.name, "dg.bait") == 1
    into(doc, w, p, "d3")
    assert lure_species(w) == [], "this run's bait is for the NEXT run: nothing comes now"
    s2 = second_run(doc, w, p)
    assert (w.get(p.name, "dg.bait") or 0) == 0, "consumed at the threshold of the next run"
    lr = room_of(doc, "d3")
    assert w.get(hold(s2, room_of(doc, "bait"), "_z"), "dg.rs") == 1
    into(doc, w, p, "d3")
    got = lure_species(w)
    lower = TR.BASE["engine"]["bands"][0]["caps"][0]
    assert [(sp, lv) for sp, lv, _e in got] == [("cobblemon:marill", lower)], got
    e = got[0][2]
    assert all(t in e.tags for t in (TR.BASE["engine"]["sweep"]["keep_tag"], "dg.s%d" % s2["g"], "dg.lure"))
    assert "uncatchable" not in e.props and "no_ai" not in e.props, "catchable, and free to wander"
    lx, lz = e.pos[0], e.pos[2]
    assert lr["ix0"] <= lx <= lr["ix1"] + 1 and lr["iz0"] <= lz <= lr["iz1"] + 1, "in the lure room"
    s3 = second_run(doc, w, p)
    into(doc, w, p, "d3")
    assert not [x for x in lure_species(w) if x[2] is e], "the earlier run's lure was discarded with its slot"
    assert w.get(hold(s3, room_of(doc, "bait"), "_z"), "dg.rs") == 0, "a third run has no lure: the bait is gone"


def test_the_next_run_spawns_the_lured_pokemon_in_the_living_room_once_and_consumes_the_bait(mk):
    assert_lure_once_and_consumed(mk)


@pytest.mark.parametrize("band,bait,species", [(3, 1, "azumarill"), (5, 4, "blissey"), (6, 6, "scizor")])
def test_the_lure_depends_on_the_bait_and_the_band(mk, band, bait, species):
    doc, w, p, s, r = bait_world(mk, band=band)
    w.set(p.name, "dg.bait", bait)
    s2 = second_run(doc, w, p)
    w.set(p.name, "dg.band", band)
    into(doc, w, p, "d3")
    assert [sp for sp, _lv, _e in lure_species(w)] == ["cobblemon:" + species]
    lv = lure_species(w)[0][1]
    assert lv == TR.BASE["engine"]["bands"][band - 1]["caps"][0]


def test_the_bait_survives_a_logout_and_a_death_it_is_the_players_score(mk):
    doc, w, p, s, r = bait_world(mk)
    drop(w, r, "cobblemon:pecha_berry", 1, "bait")
    w.passes(1)
    assert w.get(p.name, "dg.bait") == 2
    p.online = False
    w.passes(3)
    p.online = True
    w.call("cobblers:dungeons/far", PS.Ctx(p, p.dim, p.pos))
    w.passes(8)
    assert w.get(p.name, "dg.bait") == 2, "no run end, logout or sweep resets it"


def test_the_reset_clears_the_runs_lure_so_a_run_without_bait_gets_none(mk):
    doc, w, p, s, r = bait_world(mk)
    w.set(hold(s, room_of(doc, "bait"), "_z"), "dg.rs", 3)
    reset_slot(w, p, s)
    assert w.get(hold(s, room_of(doc, "bait"), "_z"), "dg.rs") == 0


# ------------------------------------------------------------------------------------------------- generator mutations


def rebuild(doc):
    R._BUILT.clear()
    return R.problems(doc)


def test_mutating_the_clue_placement_to_no_wall_is_refused(monkeypatch):
    monkeypatch.setattr(DX, "_wall_cells", lambda ctx, salt: [])
    assert any("no wall in clue room" in p for p in rebuild(xdoc("mine"))), "a vault whose code cannot be read must not build"


def test_mutating_the_gate_to_stay_open_in_the_shell_fails_the_shell_test(monkeypatch):
    real = R.gate_closing_ops
    monkeypatch.setattr(R, "gate_closing_ops", lambda room, theme: [op for op in real(room, theme)
                                                                    if not (room["kind"] == "bank_vault" and op[2] == theme["door"]["gate"])])
    R._BUILT.clear()
    with pytest.raises(AssertionError):
        assert_gate_shut_in_shell(xdoc("mine"), "mine")


def test_mutating_the_chamber_to_be_walled_in_even_with_the_gate_open_fails_the_walk_check(monkeypatch):
    real = DX.build_bank

    def sealed(doc, d, slot, room, theme):
        res = real(doc, d, slot, room, theme)
        g = DX.bank_geom(room, int(room["params"].get("chests", 4)))
        res = dict(res)
        res["blocks"] = list(res["blocks"]) + [R.fill(g["gate"], "minecraft:stone_bricks")]
        return res
    monkeypatch.setitem(R.KINDS, "bank_vault", sealed)
    assert any("unreachable" in p or "not reached" in p or "reach" in p for p in rebuild(xdoc("mine"))), rebuild(xdoc("mine"))


def test_mutating_the_penalty_to_nothing_fails_the_wrong_code_test(monkeypatch, tmp_path_factory):
    monkeypatch.setattr(DP, "U", lambda doc: 0)
    R._BUILT.clear()
    doc, w = world("mine", None, tmp_path_factory, cache={})
    p, s = start(doc, w, (3, 1, 4, 1))
    b = built(doc, "bank")
    r = into(doc, w, p, "bank")
    clock = w.get(p.name, "dg.clock")
    rate = w.get(p.name, "dg.rate")
    enter_code(w, b, [3, 1, 4, 2])
    with pytest.raises(AssertionError):
        assert w.get(p.name, "dg.clock") == clock - 4 * 20 * rate - 20 * U1


def test_mutating_the_roll_to_a_constant_code_fails_the_rolled_code_test(monkeypatch, tmp_path_factory):
    real = DX.start_lines
    monkeypatch.setattr(DX, "start_lines", lambda doc, slot: [ln.replace("random value 0..9", "random value 7..7") for ln in real(doc, slot)])
    R._BUILT.clear()
    with pytest.raises(AssertionError):
        assert_code_rolled(lambda theme="mine", rooms=None: world(theme, rooms, tmp_path_factory, cache={}))


def test_mutating_the_priced_list_to_include_placeholders_fails_the_refusal_test(monkeypatch, tmp_path_factory):
    real = DX.priced_ids
    monkeypatch.setattr(DX, "priced_ids", lambda table: real(table) + [(i, int(row["cp"])) for i, row in table["items"].items()
                                                                       if row.get("source") == "unpriced"])
    R._BUILT.clear()
    with pytest.raises(AssertionError):
        assert_refused(lambda theme="mine", rooms=None: world(theme, rooms, tmp_path_factory, cache={}), "cobblemon:rare_candy", 64)


def test_mutating_a_share_table_over_the_cap_is_refused_by_the_table_check(monkeypatch):
    mutated = copy.deepcopy(XDATA)
    mutated["wishing_well"]["shares_by_band"]["3"] = [[10, 0], [20, 100], [30, 200], [30, 300], [10, 500]]
    monkeypatch.setattr(DX, "load", lambda path=DX.DATA: mutated)
    bad = DX.table_problems(xdoc("mine"), force=True)
    assert any("expected share" in p and "band 3" in p for p in bad), bad


def test_mutating_the_ladder_to_an_unpriced_first_item_is_refused(monkeypatch):
    mutated = copy.deepcopy(XDATA)
    mutated["wishing_well"]["ladders_by_band"]["2"][0] = ["cobblemon:rare_candy", "rare candies"]
    monkeypatch.setattr(DX, "load", lambda path=DX.DATA: mutated)
    assert any("no GREED price" in p for p in DX.table_problems(xdoc("mine"), force=True))


def test_mutating_a_bait_to_a_legendary_is_refused(monkeypatch):
    mutated = copy.deepcopy(XDATA)
    mutated["bait_room"]["baits"][0]["species_by_band"]["6"] = "mewtwo"
    monkeypatch.setattr(DX, "load", lambda path=DX.DATA: mutated)
    labels = DX.species_labels()
    if labels is None:
        pytest.skip("no Cobblemon jar on this machine")
    assert any("legendary" in p for p in DX.table_problems(xdoc("mine"), force=True))


def test_mutating_the_start_to_keep_the_bait_fails_the_consumed_once_test(monkeypatch, tmp_path_factory):
    real = DX.start_lines
    monkeypatch.setattr(DX, "start_lines", lambda doc, slot: [ln for ln in real(doc, slot) if "set @s dg.bait 0" not in ln])
    R._BUILT.clear()
    with pytest.raises(AssertionError):
        assert_lure_once_and_consumed(lambda theme="mine", rooms=None: world(theme, rooms, tmp_path_factory, cache={}))


def _functions_without(monkeypatch, drop_line=None, swap=None):
    real = DX.functions

    def fn(doc):
        out = real(doc)
        for name, lines in out.items():
            if name.startswith("well/b"):
                lines = [ln for ln in lines if ln != drop_line]
                if swap:
                    lines = [ln.replace(*swap) for ln in lines]
                out[name] = lines
        return out
    monkeypatch.setattr(DX, "functions", fn)


def test_mutating_the_net_to_the_full_pay_fails_the_pay_test(monkeypatch, tmp_path_factory):
    # charging the whole reward, not the gain over the gift: the diamond thrown at 100% would be charged 88 cp, not 0
    _functions_without(monkeypatch, drop_line="scoreboard players operation #gv dg.t -= #iv dg.t")
    R._BUILT.clear()
    with pytest.raises(AssertionError):
        assert_pay(lambda theme="mine", rooms=None: world(theme, rooms, tmp_path_factory, cache={}), 70)


def test_mutating_the_pay_to_double_fails_the_pay_test(monkeypatch, tmp_path_factory):
    _functions_without(monkeypatch, swap=("/= #100 dg.t", "/= #50 dg.t"))
    R._BUILT.clear()
    with pytest.raises(AssertionError):
        assert_pay(lambda theme="mine", rooms=None: world(theme, rooms, tmp_path_factory, cache={}), 85)
