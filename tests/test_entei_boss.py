"""tools/entei_boss.py and data/entei_boss.json: the repeatable Entei, each player their own copy in cobblers:pocket.

Written by the builder of the pack (unit ENTEI, 2026-10-08), at the coordinator's request, so these are the builder's
own checks and NOT an independent audit; the audit owed is listed in experiments/EXP-059-entei-boss/README.md.

Where an expectation comes from, never the record under test:
  the pocket     data/portals.json pocket (dimension, floor, bands, rescue margin)
  the border     docs/STATE.md:74, playable x/z -1024..9215 (stated here as a constant)
  the cap        docs/mechanics/LEAGUE_LEVEL_CAP.md: 100 after the Champion; the catch block refuses only above it
  the bank       modpack/config/cobbledollars/bank.json and data/bank.json buys, read here
  the exemption  data/blackout.json claims.exempt_tag, read here

Mutations change the GENERATOR (monkeypatched functions) or an in-memory copy of the record; no file is written.
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
import entei_boss as E  # noqa: E402

DOC = E.load()
PORTALS = json.loads((ROOT / "data" / "portals.json").read_text(encoding="utf-8"))
BLACKOUT = json.loads((ROOT / "data" / "blackout.json").read_text(encoding="utf-8"))
BORDER = (-1024, 9215)            # docs/STATE.md:74
CAP_AFTER_CHAMPION = 100          # docs/mechanics/LEAGUE_LEVEL_CAP.md
FUNCTION_REF = re.compile(r"function (cobblers:[a-z0-9_./]+)")


@pytest.fixture(scope="module")
def files():
    return E.build(DOC)


def fn(files, name):
    return files["data/cobblers/function/entei_boss/%s.mcfunction" % name].splitlines()


def test_the_committed_record_has_no_problems():
    assert E.problems(DOC) == []


def test_the_rooms_are_in_the_portals_pocket_and_out_of_their_rescue_box():
    p = PORTALS["pocket"]
    assert DOC["pocket"]["dimension"] == p["dimension"]
    rz0 = min(p["bands"].values()) - p["rescue_margin"]
    for k in range(1, DOC["pocket"]["slots"] + 1):
        g = E.slot_geometry(DOC, k)
        x, y, z, dx, dy, dz = g["box"]
        assert z + dz < rz0, "slot %d meets the portals' rescue box" % k
        assert BORDER[0] < x and x + dx < BORDER[1] and BORDER[0] < z and z + dz < BORDER[1]
        assert z + dz < 0 or x + dx < 0, "slot %d shares coordinates with the overworld map" % k


def test_the_band_box_and_slot_boxes_do_not_overlap_and_the_band_holds_them():
    bx, by, bz, bdx, bdy, bdz = E.band_box(DOC)
    boxes = [E.slot_geometry(DOC, k)["box"] for k in range(1, DOC["pocket"]["slots"] + 1)]
    for a in boxes:
        assert bx <= a[0] and a[0] + a[3] <= bx + bdx and bz <= a[2] and a[2] + a[5] <= bz + bdz
    for i, a in enumerate(boxes):
        for b in boxes[i + 1:]:
            assert a[0] + a[3] < b[0] or b[0] + b[3] < a[0] or a[2] + a[5] < b[2] or b[2] + b[5] < a[2]


def test_the_room_is_sealed_and_the_spot_and_arrival_stand_on_floor():
    k = 1
    blocks = {}
    for x, y, z, b in E.room_blocks(DOC, k):
        blocks[(x, y, z)] = b
    g = E.slot_geometry(DOC, k)
    cx, cz = g["centre"]
    half, height, fy = DOC["room"]["half"], DOC["room"]["height"], DOC["pocket"]["floor_y"]
    # the outermost course is all bedrock, on every face
    for (x, y, z), b in blocks.items():
        if abs(x - cx) == half + 2 or abs(z - cz) == half + 2 or y in (fy - 2, fy + height + 1):
            assert b == "minecraft:bedrock", (x, y, z, b)
    for name in ("spot", "arrive", "click"):
        x, y, z = g[name]
        assert blocks[(x, y, z)] == "minecraft:air" and blocks[(x, y + 1, z)] == "minecraft:air", name
        assert blocks[(x, y - 1, z)] not in ("minecraft:air", "minecraft:magma_block"), name
    assert "minecraft:magma_block" not in blocks.values()


def test_the_level_sits_at_the_cap_of_everyone_the_gate_lets_in():
    assert DOC["gate_flag"] == "cobblers:flag/champion_cleared"
    assert int(DOC["level"]) <= CAP_AFTER_CHAMPION
    for phase in ("catch", "farm"):
        assert "level=%d" % DOC["level"] in DOC["props"][phase].split()
        assert not any(t.startswith("alpha") for t in DOC["props"][phase].split())
    assert "uncatchable" not in DOC["props"]["catch"].split()
    assert "uncatchable" in DOC["props"]["farm"].split()


def test_a_record_that_makes_the_first_clear_uncatchable_is_refused():
    bad = copy.deepcopy(DOC)
    bad["props"]["catch"] += " uncatchable"
    assert any("first clear" in p for p in E.problems(bad))


def test_a_record_with_an_alpha_boss_is_refused():
    bad = copy.deepcopy(DOC)
    bad["props"]["farm"] += " alpha=true"
    assert any("alpha" in p for p in E.problems(bad))


def _bank():
    ids = set()
    out = ROOT / "modpack" / "config" / "cobbledollars" / "bank.json"
    for e in json.loads(out.read_text(encoding="utf-8"))["bank"]:
        ids.add(e["item"])
    for e in json.loads((ROOT / "data" / "bank.json").read_text(encoding="utf-8"))["buys"]:
        ids.add(e["item"])
    return ids


def test_no_drop_is_money_bankable_or_a_plate(files):
    table = json.loads(files["data/cobblers/loot_table/entei_boss/drops.json"])
    names = [e["name"] for pool in table["pools"] for e in pool["entries"]]
    assert names, "an empty drop table"
    bank = _bank()
    for n in names:
        assert n not in bank, n
        assert "plate" not in n, n
        assert not n.startswith("cobbledollars:"), n
    for line in sum((files[f].splitlines() for f in files if f.endswith(".mcfunction")), []):
        assert not line.lstrip().startswith("cobbledollars"), line


def _bank_file_items():
    """The ids the CobbleDollars bank file buys, read here from the committed file (not through entei_boss.py)."""
    path = ROOT / "modpack" / "config" / "cobbledollars" / "bank.json"
    return {e["item"] for e in json.loads(path.read_text(encoding="utf-8"))["bank"]}


# Without it a drop the bank buys would launder the repeatable boss into money. The drop is chosen from the bank file
# as it stands (the first bought id the boss does not already drop), so the bank's list moving cannot leave the test
# mutating with an item the bank no longer buys (pp_up left in baba770 and made this test vacuous-red).
def test_a_bankable_drop_is_refused():
    drops = {e["item"] for e in DOC["drops"]["entries"]}
    bankable = sorted(_bank_file_items() - drops)
    assert bankable, "the bank file buys nothing the boss does not already drop"
    bad = copy.deepcopy(DOC)
    bad["drops"]["entries"].append({"item": bankable[0], "count": 1, "weight": 1})
    assert any(bankable[0] in p and "bank" in p for p in E.problems(bad)), bankable[0]


# Without it the bank check could be a stale constant list: an item the bank file no longer buys (pp_up, removed in
# baba770) is not refused as bankable.
def test_an_item_the_bank_stopped_buying_is_not_called_bankable():
    assert "cobblemon:pp_up" not in _bank_file_items()
    ok = copy.deepcopy(DOC)
    ok["drops"]["entries"].append({"item": "cobblemon:pp_up", "count": 1, "weight": 1})
    assert not [p for p in E.problems(ok) if "cobblemon:pp_up" in p and "bank" in p]


def test_the_refund_gives_back_exactly_what_the_recipe_makes(files):
    rec = json.loads(files["data/cobblers/recipe/entei_boss/ember_sigil.json"])
    adv = json.loads(files["data/cobblers/advancement/entei_boss/sigil.json"])
    res = rec["result"]
    want = adv["criteria"]["eat"]["conditions"]["item"]
    assert want["items"] == res["id"]
    assert want["components"]["minecraft:custom_data"] == res["components"]["minecraft:custom_data"]
    give = [l for l in fn(files, "refund") if l.startswith("give @s ")]
    assert len(give) == 1
    assert give[0].startswith("give @s %s[" % res["id"])
    assert 'minecraft:custom_data={cobblers_entei:"sigil"}' in give[0]
    assert "can_always_eat:true" in give[0]
    # materials only: no authored counter SELLS an ingredient (a priced stock line); an exchange_for price names the
    # item without selling it
    sold = set()

    def walk(v):
        if isinstance(v, dict):
            if "item" in v and "price" in v:
                sold.add(v["item"])
            for x in v.values():
                walk(x)
        elif isinstance(v, list):
            for x in v:
                walk(x)
    for name in ("markets.json", "traders.json"):
        walk(json.loads((ROOT / "data" / name).read_text(encoding="utf-8")))
    assert sold, "the walk found no stock line at all: the shape it reads has changed"
    for ing in rec["ingredients"]:
        assert ing["item"] not in sold, ing


def test_the_entry_price_is_the_economy_designs_two_netherite_ingots():
    # docs/mechanics/ECONOMY_OVERHAUL.md section 8 / U9 (integration branch 213b1d8), relayed by the coordinator
    ings = DOC["key"]["recipe"]["ingredients"]
    assert ings == [{"item": "minecraft:netherite_ingot", "count": 2}]


def test_enter_refunds_every_refusal_before_anything_changes(files):
    lines = [l for l in fn(files, "enter") if not l.startswith("#")]
    refund_at = next(i for i, l in enumerate(lines) if "function cobblers:entei_boss/refund" in l)
    assert "unless score #why eb.t matches 0" in lines[refund_at]
    for l in lines[:refund_at]:
        # before the refund nothing about the run is written: only scratch scores and the player's own number
        assert "eb.last" not in l or "-=" in l or "matches" in l, l
        assert " tp " not in l and "eb.slot = " not in l
    for code in range(1, 6):
        assert any("set #why eb.t %d" % code in l for l in lines[:refund_at]), code


def test_the_nether_test_is_a_positional_player_selector_never_a_bare_self():
    lines = fn(files=E.build(DOC), name="enter")
    nether = [l for l in lines if "#nether eb.t 1" in l]
    assert len(nether) == 1
    assert nether[0].startswith("execute in minecraft:the_nether positioned as @s as @a[distance=..")


def test_the_entei_carries_the_blackouts_exempt_tag(files):
    tag = BLACKOUT["claims"]["exempt_tag"]
    for k in range(1, DOC["pocket"]["slots"] + 1):
        assert "tag @s add %s" % tag in fn(files, "slot/s%d/bind" % k)


def test_a_generator_that_drops_the_exemption_is_caught(monkeypatch):
    real = E.functions

    def broken(doc, blackout=None):
        out = real(doc, blackout)
        for k in list(out):
            out[k] = [l for l in out[k] if l != "tag @s add %s" % BLACKOUT["claims"]["exempt_tag"]]
        return out
    monkeypatch.setattr(E, "functions", broken)
    built = E.build(DOC)
    with pytest.raises(AssertionError):
        test_the_entei_carries_the_blackouts_exempt_tag(built)


def test_the_spawn_lands_on_each_slots_spot_in_the_pocket(files):
    for k in range(1, DOC["pocket"]["slots"] + 1):
        x, y, z = E.slot_geometry(DOC, k)["spot"]
        lines = [l for l in fn(files, "slot/s%d/appear" % k) if "spawn_at" in l]
        assert len(lines) == 2
        for l in lines:
            assert " in %s run function" % DOC["pocket"]["dimension"] in l
            assert 'x:"%.1f",y:%d,z:"%.1f"' % (x + 0.5, y, z + 0.5) in l


def test_a_generator_that_moves_the_spawn_is_caught(monkeypatch):
    real = E.slot_geometry

    def moved(doc, k):
        g = dict(real(doc, k))
        if "spot" in g:
            g["spot"] = (g["spot"][0] + 40, g["spot"][1], g["spot"][2])
        return g
    built_with = {}
    monkeypatch.setattr(E, "slot_geometry", moved)
    built_with.update(E.build(DOC))
    monkeypatch.setattr(E, "slot_geometry", real)
    with pytest.raises(AssertionError):
        test_the_spawn_lands_on_each_slots_spot_in_the_pocket(built_with)


def test_a_slot_with_its_owner_gone_is_freed_before_anything_else(files):
    for k in range(1, DOC["pocket"]["slots"] + 1):
        body = [l for l in fn(files, "slot/s%d/tend" % k) if not l.startswith("#")]
        free_at = next(i for i, l in enumerate(body) if "slot/s%d/free" % k in l)
        assert "#here eb.t matches 0" in body[free_at] and "return run" in body[free_at]
        assert not any("spawn" in l or "appear" in l or "effect give" in l for l in body[:free_at])
        free = fn(files, "slot/s%d/free" % k)
        assert any(l.startswith("kill @e[type=cobblemon:pokemon,tag=cobblers.eb.s%d]" % k) for l in free)
        assert "scoreboard players set #s%d eb.own 0" % k in free


def test_the_way_out_is_never_gated(files):
    leave = [l for l in fn(files, "leave") if not l.startswith("#")]
    assert leave[-1] == "function cobblers:entei_boss/eject"
    eject = [l for l in fn(files, "eject") if not l.startswith("#")]
    assert eject[0] == "scoreboard players set @s eb.slot 0"
    assert any("in minecraft:overworld run tp @s" in l for l in eject), "no fallback for a player with no return point"
    assert fn(files, "go") == ["$execute in minecraft:the_nether run tp @s $(x) $(y) $(z)"]


def test_a_drop_is_rolled_once_per_run_and_only_in_farm_mode(files):
    for k in range(1, DOC["pocket"]["slots"] + 1):
        body = [l for l in fn(files, "slot/s%d/settle" % k) if not l.startswith("#")]
        loot = next(i for i, l in enumerate(body) if l.startswith("loot give @s loot cobblers:entei_boss/drops"))
        assert body[0] == "execute unless score #s%d eb.mode matches 1..2 run return 0" % k
        assert body[1] == "execute unless score #s%d eb.roll matches 0 run return 0" % k
        assert body[2] == "scoreboard players set #s%d eb.roll 1" % k
        assert "eb.mode matches 1 run return run" in body[3]
        assert loot > 3


def test_the_catch_grants_only_in_catch_mode_for_the_slots_owner(files):
    for k in range(1, DOC["pocket"]["slots"] + 1):
        body = [l for l in fn(files, "slot/s%d/caught" % k) if not l.startswith("#")]
        assert body[0] == "execute unless score #s%d eb.mode matches 1 run return 0" % k
        assert body[-1] == "advancement grant @s only %s" % DOC["catch"]["advancement"]
    for name in ("fainted", "caught"):
        calls = [l for l in fn(files, name) if "run function" in l]
        assert len(calls) == DOC["pocket"]["slots"]
        for l in calls:
            assert l.startswith("execute in %s as @a[x=" % DOC["pocket"]["dimension"])


def test_every_function_named_exists_and_the_callbacks_name_ours(files):
    have = {"cobblers:" + f.split("/function/", 1)[1][:-len(".mcfunction")]
            for f in files if f.endswith(".mcfunction")}
    text = "\n".join(files.values())
    for ref in set(FUNCTION_REF.findall(text)):
        if ref.startswith("cobblers:entei_boss/"):
            assert ref in have, ref
    for event in ("battle_fainted", "pokemon_captured"):
        body = files["data/cobblemon/callbacks/%s/cobblers_entei_boss.molang" % event]
        assert "'%s'" % DOC["species"]["id"] in body
        # a comment is a single-quoted MoLang string: an apostrophe inside it would end it early
        for line in body.splitlines():
            if line.startswith("'"):
                assert line.count("'") == 2, line


def test_the_pack_writes_one_load_tag_the_advancements_and_the_rooms(tmp_path, files):
    E.write(files, tmp_path / "p")
    tag = json.loads((tmp_path / "p" / "data/minecraft/tags/function/load.json").read_text(encoding="utf-8"))
    assert tag == {"values": ["cobblers:entei_boss/load"]}
    for rel in ("data/cobblers/advancement/entei_boss/caught.json", "data/cobblers/advancement/entei_boss/exit.json",
                "data/cobblers/advancement/entei_boss/sigil.json"):
        assert (tmp_path / "p" / rel).is_file(), rel
    for k in range(1, DOC["pocket"]["slots"] + 1):
        room = fn(files, "rooms/s%d" % k)
        assert room[0].startswith("forceload add") or any(l.startswith("forceload add") for l in room[:5])
        assert any(l.startswith("summon minecraft:interaction") and "cobblers_eb_exit_s%d" % k in l for l in room)
    assert fn(files, "place")[-1] == "execute in %s run function cobblers:entei_boss/rooms/build" % DOC["pocket"]["dimension"]
