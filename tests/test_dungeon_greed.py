"""GREED (unit GREED, 2026-10-10): every valuable a run takes weighs on the clock (tools/dungeon_greed.py,
data/dungeon_greed.json). The builder's own tests; the independent review is another agent's.

What each test holds is said where it is. The owner's rule is restated here, never read from the generator:
20 coal = 1 point, a diamond = 1 point, every 2 points +0.1x, x3 the most, per member, never falling.
Not covered: anything in a running Minecraft (that `minecraft.mined` rises in adventure mode under can_break is
EXP-073's open owner part; that the pokemon_captured callback reaches greed/catch is EXP-042's shape, not run for this).
"""
from __future__ import annotations

import copy
import re
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tests"))

import dungeon as D  # noqa: E402
import dungeon_fights as DF  # noqa: E402
import dungeon_greed as DGR  # noqa: E402
import dungeon_grid as G  # noqa: E402
import dungeon_rooms as R  # noqa: E402
import pocket_sim as PS  # noqa: E402
import test_dungeon as TD  # noqa: E402
import test_dungeon_rooms as TR  # noqa: E402
from test_dungeon_rooms import rooms_pack  # noqa: E402,F401  (the demo pack, built once a module)

DOC = D.load()
TABLE = DGR.load()
OWNER_RATE = lambda cp: min(30, 10 + (cp // 100) // 2)   # noqa: E731  the owner's words, in cp


# ------------------------------------------------------------------------------------------------- the table


def test_the_table_and_the_engine_pass_their_checks():
    assert DGR.problems(DOC) == []


def test_the_owners_anchors_and_the_rate():
    # 20 coal = 1 point and a diamond = 1 point (100 cp); 2 points = +0.1x; units_per_tick 10 makes 0.1x one unit
    it = TABLE["items"]
    assert 20 * it["minecraft:coal"]["cp"] == 100 and it["minecraft:diamond"]["cp"] == 100
    assert DOC["engine"]["clock"]["units_per_tick"] == 10
    for cp in (0, 199, 200, 399, 400, 1999, 2000, 3999, 4000, 10 ** 6):
        assert DGR.rate_of(TABLE, cp) == OWNER_RATE(cp), cp


def test_every_block_the_pick_can_break_anywhere_is_priced_and_its_cp_is_its_drops():
    # breaks if a dungeon's pick gains a block the table does not price (mined for free), or a row's cp drifts
    # from its own drops. The set is gathered here from the themes, not from DGR.breakable
    themes = R.load_themes()["themes"]
    want = set(DOC["engine"]["rift_pick"]["can_break"])
    for d in DOC["dungeons"]:
        t = themes[d["theme"]]
        want |= {e["block"] for e in t["seam"]["blocks"]}
        sb = (t.get("shapes") or {}).get("secret_block")
        if sb:
            want.add(sb)
    have = TABLE["blocks"]
    assert want <= set(have), sorted(want - set(have))
    for blk, row in have.items():
        cp = sum(n * (TABLE["items"].get(i, {}).get("cp") or next(g["cp"] for g in TABLE["groups"].values() if i in g["ids"]))
                 for i, n in row["drops"].items())
        assert row["cp"] == round(cp), blk


def test_the_coordinators_list_is_priced():
    # the owner's piles (coordinator, 2026-10-10): gold, redstone, lapis, emerald, diamond (ore and item), ancient
    # debris and netherite scrap, and every Mega Stone by its jar id
    for i in ("minecraft:raw_gold", "minecraft:gold_ingot", "minecraft:redstone", "minecraft:lapis_lazuli",
              "minecraft:emerald", "minecraft:diamond", "minecraft:ancient_debris", "minecraft:netherite_scrap",
              "mega_showdown:mega_stone", "mega_showdown:tyranitarite", "mega_showdown:dragoninite"):
        assert DGR.item_cp(TABLE, i), i
    for b in ("gold", "redstone", "lapis", "emerald", "diamond"):
        assert DGR.block_cp(TABLE, "minecraft:%s_ore" % b) and DGR.block_cp(TABLE, "minecraft:deepslate_%s_ore" % b), b
    assert DGR.block_cp(TABLE, "minecraft:ancient_debris") == TABLE["items"]["minecraft:ancient_debris"]["cp"]


def test_a_prize_is_high_below_a_legendary_and_keyed_on_the_beast_ball_band():
    lf = DOC["engine"]["prize"]["legendary_from_band"]
    rare = [DGR.catch_cp(TABLE, "habitat", b, DOC) for b in range(1, lf)]
    leg = [DGR.catch_cp(TABLE, "habitat", b, DOC) for b in range(lf, 7)]
    assert set(rare) == {TABLE["catches"]["habitat"]["rare_cp"]} and set(leg) == {TABLE["catches"]["habitat"]["legendary_cp"]}
    assert max(DGR.catch_cp(TABLE, "nest", b) for b in range(1, 7)) < rare[0] < leg[0]
    assert DGR.rate_of(TABLE, leg[0]) < 30, "a prize alone never reaches the cap"


# ------------------------------------------------------------------------------------------------- catch flags


def test_every_dungeon_pokemon_is_catchable_and_a_legendary_only_from_the_beast_ball_band():
    # the owner (2026-10-10): nests, mini-bosses and living rooms catchable; a legendary is the prize, from gym 6 on
    lf = DOC["engine"]["prize"]["legendary_from_band"]
    a = {"boss": [0, 96, 0, 0], "legendary": [0, 96, 0, 0], "spawns": [[0, 96, 0, 0]]}
    nest = {"kind": "nest", "params": {"species": ["larvitar"], "count_by_band": {str(b): 1 for b in range(1, 7)},
                                       "level_spread": [5, 5]}}
    mini = {"kind": "miniboss", "params": {"species_by_band": {str(b): "onix" for b in range(1, 7)}}}
    hab = {"kind": "habitat", "params": {"species": "regidrago", "level_by_band": {str(b): 20 for b in range(1, 7)}}}
    for room, unc_at in ((nest, set()), (mini, set()), (hab, set(range(1, lf)))):
        got = {b for b, lst in DF.wild_spawns(DOC, room, a).items() if "uncatchable" in lst[0][2].split()}
        assert got == unc_at, (room["kind"], got)
    fo = copy.deepcopy(hab)
    fo["params"]["fight_only"] = True
    assert all("uncatchable" in lst[0][2].split() for lst in DF.wild_spawns(DOC, fo, a).values())


# ------------------------------------------------------------------------------------------------- the generated pack


def _gen(doc=DOC):
    fns = DGR.functions(doc)
    return fns, DGR.objective_lines(doc), DGR.load_lines(doc)


def coverage_problems(doc, fns, objs, loads):
    """Independent of counted(): every valued pick-breakable block has a mined objective of the right criterion, a #v
    constant of its table cp, and greed/mined converts that objective with that constant."""
    bad = []
    crit = {m.group(2): m.group(1) for o in objs for m in [re.match(r"scoreboard objectives add (\S+) minecraft\.mined:(\S+)$", o)] if m}
    const = {m.group(1): int(m.group(2)) for l in loads for m in [re.match(r"scoreboard players set #(v\d+) dg\.t (\d+)$", l)] if m}
    mined = "\n".join(fns["greed/mined"])
    for blk, row in TABLE["blocks"].items():
        if not row["cp"] or blk not in DGR.breakable(doc):
            continue
        obj = crit.get(blk.replace(":", "."))
        if obj is None:
            bad.append("%s: no mined objective" % blk)
            continue
        i = obj.split("dg.m", 1)[1]
        if const.get("v" + i) != row["cp"]:
            bad.append("%s: #v%s is %r, the table says %d" % (blk, i, const.get("v" + i), row["cp"]))
        if "matches 1.. run function cobblers:dungeons/greed/m%s" % i not in mined:
            bad.append("%s: greed/mined never converts %s" % (blk, obj))
        body = fns.get("greed/m%s" % i, [])
        if "scoreboard players operation #m dg.t *= #v%s dg.t" % i not in body:
            bad.append("%s: greed/m%s does not multiply by its own value" % (blk, i))
    return bad


def test_every_valued_block_is_watched_by_a_mined_objective():
    fns, objs, loads = _gen()
    assert coverage_problems(DOC, fns, objs, loads) == []


def test_mutating_the_generator_to_skip_a_block_is_caught(monkeypatch):
    real = DGR.counted
    monkeypatch.setattr(DGR, "counted", lambda doc, table=None: [x for x in real(doc, table) if x[1] != "minecraft:coal_ore"])
    fns, objs, loads = _gen()
    bad = coverage_problems(DOC, fns, objs, loads)
    assert any(b.startswith("minecraft:coal_ore") for b in bad), bad


def test_the_points_only_rise_and_nothing_reads_the_old_count():
    # loot dropped, stashed or released can never refund time: no generated line lowers dg.gp except the two zeroes
    # (the rip's go and the threshold) and the hand-run test hook; and the old seam count dg.greed and greed/take are gone
    files = D.build(DOC)
    lowers = []
    for rel, body in files.items():
        if not rel.endswith(".mcfunction"):
            continue
        for l in body.split("\n"):
            assert "dg.greed" not in l and "greed/take" not in l, (rel, l)
            if re.search(r"dg\.gp\b", l) and re.search(r"players (set|remove|reset)|operation @s dg\.gp (-|\*|/|%|<)?=", l) \
                    and "+=" not in l:
                lowers.append((rel.split("/function/")[1], l))
    allowed = {"dungeons/greed/zero.mcfunction", "dungeons/greed/test_set.mcfunction"}
    odd = [(r, l) for r, l in lowers if r not in allowed and not re.match(r"dungeons/go/", r)
           and l != "scoreboard players set @s dg.gp 0"]
    assert not odd, odd[:5]
    assert files[DGR.CALLBACK_PATH].count("function cobblers:dungeons/greed/catch") == 1


# ------------------------------------------------------------------------------------------------- in the simulator


def mined_obj(doc, block):
    return "dg.m%d" % {b: i for i, b, _v in DGR.counted(doc)}[block]


def test_a_block_mined_anywhere_in_the_run_counts_at_its_value(rooms_pack):
    # the owner (staging, 2026-10-10): coal ore mined in a wall "should" count. The stat is per block mined, wherever
    doc, w = TR.rooms_world(rooms_pack)
    p, s = TR.enter_run(doc, w)
    r = TR.room_of(doc, "rest")                                     # a safe room: no seam anywhere near
    p.pos = [r["ix0"] + 4.5, r["floor_in"], r["z_in"] + 0.5]
    w.passes(1)
    w.set(p.name, mined_obj(doc, "minecraft:deepslate_coal_ore"), 3)
    w.set(p.name, mined_obj(doc, "minecraft:deepslate_diamond_ore"), 2)
    w.passes(1)
    assert w.get(p.name, "dg.gp") == 3 * 5 + 2 * 100
    assert w.get(p.name, "dg.rate") == OWNER_RATE(215) == 11
    w.passes(3)
    assert w.get(p.name, "dg.gp") == 215, "a count is converted once"


def test_mining_before_the_threshold_or_loot_carried_in_never_counts(rooms_pack):
    doc, w = TR.rooms_world(rooms_pack)
    p = w.player("Brock", "minecraft:overworld", (1352.5, 130, 4120.5))
    p.inventory.append(TD.soot())
    p.inventory.append(("minecraft:diamond", 64))                    # brought in: no event ever weighs it
    w.call("cobblers:dungeons/door/ns", PS.Ctx(p, p.dim, p.pos))
    w.passes(4)
    w.set(p.name, mined_obj(doc, "minecraft:deepslate_coal_ore"), 40)   # mined before the threshold (or before the run)
    s = D.slots(doc)[w.get(p.name, "dg.slot") - 1]
    pt = D.points(doc, s)
    p.pos = [pt["threshold_x"] + 1.5, 96.0, s["cz"] + 0.5]
    w.passes(3)
    assert w.get(p.name, "dg.st") == 3
    assert w.get(p.name, "dg.gp") == 0 and w.get(p.name, "dg.rate") == 10
    p.inventory.clear()                                                 # dropped ...
    w.passes(1)
    p.inventory.append(("minecraft:diamond", 64))                       # ... and picked up again
    w.passes(1)
    assert w.get(p.name, "dg.gp") == 0


def test_the_rate_never_falls(rooms_pack):
    doc, w = TR.rooms_world(rooms_pack)
    p, s = TR.enter_run(doc, w)
    w.set(p.name, mined_obj(doc, "minecraft:deepslate_diamond_ore"), 8)
    w.passes(1)
    assert w.get(p.name, "dg.rate") == 14
    ctx = PS.Ctx(p, p.dim, p.pos)
    w.call("cobblers:dungeons/greed/test_set", ctx, {"p": 0})           # even a forced zero of the points
    assert w.get(p.name, "dg.rate") == 14


def catch_at(w, doc, p, rid):
    r = TR.room_of(doc, rid)
    p.pos = [(r["ix0"] + r["ix1"]) / 2.0, float(r["floor_in"]), (r["iz0"] + r["iz1"]) / 2.0]
    w.run_callback("pokemon_captured", query={"pokemon": {"species": {"identifier": "larvitar"}, "id": "pk-larvitar", "is_shiny": 0}, "player": {"uuid": p.uid}})


def test_a_catch_weighs_by_the_room_it_was_made_in_and_only_in_a_live_run(rooms_pack):
    doc, w = TR.rooms_world(rooms_pack)
    p, s = TR.enter_run(doc, w)
    band = w.get(p.name, "dg.band")
    gp = 0
    for rid, kind in (("rest", "ambient"), ("nest", "nest"), ("mini", "miniboss"), ("hab", "habitat")):
        catch_at(w, doc, p, rid)
        gp += DGR.catch_cp(TABLE, kind, band, doc)
        assert w.get(p.name, "dg.gp") == gp, (rid, kind)
    p.party.clear()                                                     # released: nothing refunds
    w.passes(1)
    assert w.get(p.name, "dg.gp") == gp
    q = w.player("Misty", "minecraft:overworld", (0.5, 70, 0.5))
    w.run_callback("pokemon_captured", query={"pokemon": {"species": {"identifier": "psyduck"}, "id": "pk-psyduck", "is_shiny": 0}, "player": {"uuid": q.uid}})
    assert not w.get(q.name, "dg.gp"), "a catch outside a run weighs nothing"


# ------------------------------------------------------------------------------------------------- no hole to the void


def breakable_on_the_shell(doc, d, slot):
    """[(room id, cell)] for every block the dungeon's pick can break that sits on its room box's outer layer, where
    breaking it opens the void or another room. The box is the room's whole hull (walls, floor, ceiling courses)."""
    pick = set(doc["engine"]["rift_pick"]["can_break"]) | set(R.pick_blocks(d))
    out = []
    for b in R.slot_build(doc, d, slot):
        g = b.grid
        ids = [i for i, name in enumerate(g.pal) if G.base(name) in pick]
        if not ids:
            continue
        for c in np.argwhere(np.isin(g.a, ids)):
            if any(v == 0 or v == n - 1 for v, n in zip(c, g.shape)):
                out.append((b.room["id"], tuple(int(v) + o for v, o in zip(c, g.box[:3]))))
    return out


@pytest.mark.parametrize("di", range(len(DOC["dungeons"])))
def test_no_block_the_pick_can_break_is_on_a_room_hull(di):
    # the coordinator (2026-10-10): a wall ore must never open a hole to the void. Every slot, every variant built
    d = DOC["dungeons"][di]
    for s in [x for x in D.slots(DOC) if x["dungeon"] is d]:
        assert breakable_on_the_shell(DOC, d, s) == [], (d["id"], s["g"])


def test_the_hull_check_names_an_ore_set_into_a_wall(monkeypatch):
    # the check above bites: a coal ore written into the outer wall course of a real built room is named
    d = DOC["dungeons"][0]
    s = next(x for x in D.slots(DOC) if x["dungeon"] is d)
    b = copy.deepcopy(next(x for x in R.slot_build(DOC, d, s) if x.room["kind"] == "safe_room"))
    b.grid.a[0, 2, 2] = b.grid.pid("minecraft:deepslate_coal_ore")
    monkeypatch.setattr(R, "slot_build", lambda doc, d_, slot: [b])
    assert [c for _r, c in breakable_on_the_shell(DOC, d, s)] == [(b.grid.box[0], b.grid.box[1] + 2, b.grid.box[2] + 2)]
