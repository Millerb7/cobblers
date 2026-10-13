"""The dungeon draw (tools/dungeon.py 'THE DRAW', docs/mechanics/DUNGEON_DRAW.md 2.2-2.4): the BUILDER's own tests, run on
tests/pocket_sim.py. The INDEPENDENT audit of the draw is another agent's; these prove the builder's intent, not independence.

What each test holds is said where it is. Not covered: anything in a running Minecraft (that `random value 0..2^30-1` and
`scoreboard players operation ... %=` behave in a function as the simulator models them, that a rip's click reaches
the door function through the advancement reward on a server: EXP-034's proven shape, not re-run), and the co-op party draw
(deferred: DUNGEON_DRAW.md section 5).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tests"))

import dungeon as D  # noqa: E402
import pocket_sim as PS  # noqa: E402
import test_dungeon as TD  # noqa: E402
from test_dungeon import pack  # noqa: E402,F401  (the generated pack, written once a module)

DOC = TD.DOC
DS = DOC["dungeons"]
RIPS = DOC["rips"]
OW = "minecraft:overworld"
FLAG = "cobblers:flag/%s"
UNGATED_BAND1 = [d["id"] for d in DS if d["first_band"] <= 1 and not d["gate_flag"]]


def draw_world(pack, cap=20):
    fakes = dict(TD.FAKES)
    fakes["cobblers:levelcap/battle_check"] = ["$scoreboard players set @s cobblers.lc_cap %d$(x)" % cap]
    w = TD.DW(pack, fakes)
    w.objectives |= {"cobblers.lc_cap", "tailend", "stale"}
    w.boot()
    # A slot's reset writes its whole shell (hundreds of thousands of lines in the simulator, minutes a click); the draw
    # tests click dozens of times and are about WHICH dungeon opens, not what the slot's blocks hold. The resets are
    # tested where they are (tests/test_dungeon_rooms.py and the audit's runs).
    for s in D.slots(DOC):
        w.functions["cobblers:dungeons/slot/s%d/reset" % s["g"]] = ["# the slot's block reset, not under test here"]
    return w


def sigil(band, n=1):
    x = D.sigils(DOC)[band - 1]
    return [x["item"], {"cobblers_dg_sigil": band}, n]


def rip_fn(rip_id):
    return "cobblers:dungeons/" + D.rip_door(next(x for x in RIPS if x["id"] == rip_id))


def at_rip(w, rip_id="rip_trail_ns", name="Ash", band=1, flags=(), tags=()):
    r = next(x for x in RIPS if x["id"] == rip_id)
    p = w.player(name, OW, (r["outside"][0], r["outside"][1], r["outside"][2]), advancements=[FLAG % f for f in flags])
    p.tags.update(tags)
    p.inventory.append(sigil(band, 20))
    return p


def click(w, p, rip_id="rip_trail_ns"):
    w.call(rip_fn(rip_id), PS.Ctx(p, p.dim, p.pos))


def drawn(w, p):
    n = w.get(p.name, "dg.dun")
    return DS[n - 1]["id"] if n else None


def abandon(w, p):
    """A back-out as far as the draw sees it: the run is over, the slot free, the sigil's refund the player's. The stamp
    the draw left (dg.dr_<short>) stays: a backed-out run counts as drawn."""
    slot = w.get(p.name, "dg.slot")
    if slot:
        w.set("#s%d" % slot, "dg.own", 0)
    w.set(p.name, "dg.st", 0)
    w.set(p.name, "dg.slot", 0)
    p.tags.discard(TD.RUN_TAG)
    w.passes(1)                                   # the uptime moves, so the next draw's ages differ


def draws(w, p, n, rip_id="rip_trail_ns"):
    out = []
    for _ in range(n):
        click(w, p, rip_id)
        assert w.get(p.name, "dg.st") == 1, "the click was refused: %s" % w.get(p.name, "dg.st")
        out.append(drawn(w, p))
        abandon(w, p)
    return out


# ------------------------------------------------------------------------------------------------- static


def test_every_rip_has_its_own_click_door_and_advancement_and_the_draw_is_one_chain():
    files = TD.FILES
    for r in RIPS:
        adv = json.loads(files["data/cobblers/advancement/dungeons/rip_%s.json" % D.rip_name(r)])
        assert adv["rewards"]["function"] == rip_fn(r["id"])
        assert any(l.endswith("function cobblers:dungeons/draw") for l in TD.body(D.rip_door(r)))
    adv_files = {k for k in files if k.startswith("data/cobblers/advancement/dungeons/rip_")}
    assert len(adv_files) == len(RIPS), "one click advancement a rip and no dungeon's left over"
    # one chain per click: the draw never schedules, never forks a new function context but through `function`
    draw = TD.body("draw") + TD.body("draw/open")
    assert not any("schedule" in l or " with " in l for l in draw)
    # and nothing in the keeper reads or writes the draw's state
    keeper = [l for n in TD.FNS if n.startswith("keeper") for l in TD.body(n)]
    assert not any("dg.dr_" in l or "#dun" in l or "draw" in l for l in keeper)


def test_the_draw_refuses_nothing_itself_and_the_sigil_is_taken_only_by_the_dungeons_door():
    # the draw reads and writes only scratch scores (#c #f #l #a #tier #best #n #r #k #dun, dg.t) and calls the doors: no
    # clear, no give, no tag, no teleport, no dg.dr_ stamp (the go stamps, so a refusal never counts as a draw)
    for l in TD.body("draw"):
        assert not l.startswith(("clear ", "give ", "tag ", "tp ")) and " run clear " not in l and " run give " not in l
        assert "operation @s dg.dr_" not in l and "set @s dg.dr_" not in l, l        # reads the stamps, never writes one


# ------------------------------------------------------------------------------------------------- rotation


def test_a_band_one_player_sees_every_open_dungeon_before_a_repeat(pack):
    w = draw_world(pack)
    p = at_rip(w, band=1)
    got = draws(w, p, 2 * len(UNGATED_BAND1))
    n = len(UNGATED_BAND1)
    assert set(got[:n]) == set(UNGATED_BAND1) and len(got[:n]) == len(set(got[:n])), got
    assert set(got[n:]) == set(UNGATED_BAND1) and len(set(got[n:])) == n, got
    assert all(got[i] != got[i + 1] for i in range(len(got) - 1)), "the same dungeon twice in a row"


def test_a_backed_out_dungeon_counts_as_drawn_and_the_next_click_does_not_repeat_it(pack):
    w = draw_world(pack)
    p = at_rip(w)
    click(w, p)
    first = drawn(w, p)
    assert w.get(p.name, "dg.dr_%s" % next(d["short"] for d in DS if d["id"] == first)) is not None
    abandon(w, p)
    click(w, p)
    assert drawn(w, p) != first


def test_the_tie_for_the_oldest_is_broken_by_the_random_number(pack):
    # five never-drawn dungeons tie: the roll v takes the (v mod 5)+1'th of them in the file's order
    for v, want in ((0, 0), (1, 1), (4, 4), (7, 2), (1073741823, 3)):
        w = draw_world(pack)
        p = at_rip(w)
        w.random_values.append(v)
        click(w, p)
        assert drawn(w, p) == UNGATED_BAND1[want], (v, drawn(w, p))
        assert w.random_log[-1][:2] == (0, 1073741823)


def test_a_later_tie_is_among_the_oldest_only(pack):
    w = draw_world(pack)
    p = at_rip(w)
    first = draws(w, p, 3)
    w.random_values.append(0)
    click(w, p)
    assert drawn(w, p) not in first, "with undrawn dungeons left a drawn one is never the oldest"


# ------------------------------------------------------------------------------------------------- progression


def test_the_band_comes_from_the_cap_and_a_dungeon_is_never_drawn_below_its_first_band(pack):
    # every flag held, every band: whatever is drawn has first_band <= the player's band (DUNGEON_DRAW.md 2.2)
    flags = sorted({d["gate_flag"].split("/", 1)[1] for d in DS if d["gate_flag"]})
    for cap, band in ((20, 1), (45, 3), (55, 4), (62, 5), (100, 6)):
        w = draw_world(pack, cap)
        p = at_rip(w, band=band, flags=flags)
        got = set(draws(w, p, 40))
        allowed = {d["id"] for d in DS if d["first_band"] <= band}
        assert got <= allowed, (band, got - allowed)
        assert w.get(p.name, "dg.band") == band
        if band == 6:
            assert got == allowed, "band 6 draws all of them: %s" % (allowed - got)


def test_a_gate_not_held_keeps_a_dungeon_out_and_holding_it_lets_it_in(pack):
    w = draw_world(pack, 62)
    p = at_rip(w, band=5)
    no_flags = set(draws(w, p, 40))
    assert no_flags == {d["id"] for d in DS if d["first_band"] <= 5 and not d["gate_flag"]}, no_flags
    w = draw_world(pack, 62)
    p = at_rip(w, band=5, flags=["gym8_cleared"])
    with_8 = set(draws(w, p, 60))
    assert with_8 == {d["id"] for d in DS if d["first_band"] <= 5 and d["gate_flag"] in (None, FLAG % "gym8_cleared")}, with_8
    assert "field_of_swords" not in with_8, "gym 6's gate is not gym 8's"
    assert "dragonspiral" not in with_8 and "crucible" not in with_8, "first band 6"


def test_the_champions_flag_does_not_open_a_band_six_dungeon_to_a_band_five_player(pack):
    w = draw_world(pack, 62)
    p = at_rip(w, band=5, flags=["gym6_cleared", "gym8_cleared", "champion_cleared"])
    got = set(draws(w, p, 60))
    assert got.isdisjoint({"dragonspiral", "crucible"}), got


# ------------------------------------------------------------------------------------------------- lockout, slots, refusals


def test_a_locked_out_dungeon_is_skipped_and_a_full_one_falls_through(pack):
    w = draw_world(pack)
    p = at_rip(w)
    w.set("#up", "dg.up", 5000)
    w.set(p.name, "dg.lk_ns", 4000)                      # entered 1000 ticks ago: locked for the hour
    for s in D.slots(DOC):
        if s["dungeon"]["id"] == "jungle":
            w.set("#s%d" % s["g"], "dg.own", 77)           # every slot of the jungle held
    got = set(draws(w, p, 12))
    assert got == set(UNGATED_BAND1) - {"night_shift", "jungle"}, got


def test_with_every_open_dungeon_locked_the_draw_names_one_and_its_door_refuses_for_the_right_reason(pack):
    w = draw_world(pack)
    p = at_rip(w)
    w.set("#up", "dg.up", 5000)
    for d in DS:
        w.set(p.name, "dg.lk_%s" % d["short"], 4900)
    click(w, p)
    assert w.get(p.name, "dg.st") in (None, 0) and not w.get(p.name, "dg.rip"), "refused: no run, no rip recorded"
    assert any(i[0] == sigil(1)[0] for i in p.inventory) and sum(i[2] for i in p.inventory if i[0] == sigil(1)[0]) == 20, \
        "a refusal never touches a sigil"
    assert not any(w.get(p.name, "dg.dr_%s" % d["short"]) is not None for d in DS), "a refused click is not a draw"


def test_with_every_slot_of_every_open_dungeon_held_the_door_says_busy_and_nothing_is_taken(pack):
    w = draw_world(pack)
    p = at_rip(w)
    for s in D.slots(DOC):
        w.set("#s%d" % s["g"], "dg.own", 77)
    click(w, p)
    assert w.get(p.name, "dg.st") in (None, 0)
    assert sum(i[2] for i in p.inventory if i[0] == sigil(1)[0]) == 20


def test_no_sigil_is_a_refusal_that_does_not_stamp_or_record_the_rip(pack):
    w = draw_world(pack)
    p = at_rip(w)
    p.inventory.clear()
    click(w, p, "rip_the_rift")
    assert w.get(p.name, "dg.st") in (None, 0) and not w.get(p.name, "dg.rip")
    assert not any(w.get(p.name, "dg.dr_%s" % d["short"]) is not None for d in DS)


def test_a_player_already_in_a_run_is_refused_and_the_run_is_untouched(pack):
    w = draw_world(pack)
    p = at_rip(w)
    click(w, p, "rip_trail_ns")
    run, slot, dun, rip = (w.get(p.name, o) for o in ("dg.run", "dg.slot", "dg.dun", "dg.rip"))
    click(w, p, "rip_the_rift")
    assert (w.get(p.name, "dg.run"), w.get(p.name, "dg.slot"), w.get(p.name, "dg.dun"), w.get(p.name, "dg.rip")) == (run, slot, dun, rip)
    assert sum(i[2] for i in p.inventory if i[0] == sigil(1)[0]) == 19, "one sigil, once"


def test_the_way_out_is_the_rip_the_run_was_entered_by(pack):
    # the same dungeon can now open from any rip, so the exit point is the rip's, not the dungeon's
    for rip_id in ("rip_trail_ns", "rip_the_rift", "rip_pine_isles", "rip_eastern_dunes"):
        w = draw_world(pack)
        p = at_rip(w, rip_id)
        click(w, p, rip_id)
        w.passes(4)
        assert p.dim == TD.POCKET and w.get(p.name, "dg.st") == 2
        w.call("cobblers:dungeons/back", PS.Ctx(p, p.dim, p.pos))
        r = next(x for x in RIPS if x["id"] == rip_id)
        assert p.dim == OW and [round(v, 1) for v in p.pos] == [round(float(v), 1) for v in r["outside"][:3]], (rip_id, p.pos)
        assert sum(i[2] for i in p.inventory if i[0] == sigil(1)[0]) == 20, "the back rip refunds the sigil"


# ------------------------------------------------------------------------------------------------- the staging playtest


def test_a_playtester_gets_the_dungeon_they_name_whatever_the_draw_or_gate_says(pack):
    ab = next(i for i, d in enumerate(DS, 1) if d["id"] == "ash_bell")
    w = draw_world(pack)
    p = at_rip(w, band=5, tags=[D.PLAYTEST_TAG])
    w.set(p.name, "dg.ptband", 5)
    w.set(p.name, "dg.ptdun", ab)
    click(w, p)
    assert drawn(w, p) == "ash_bell" and w.get(p.name, "dg.st") == 1, "the named dungeon, the gate bypassed"
    w = draw_world(pack)
    q = at_rip(w, band=5)
    w.set(q.name, "dg.ptdun", ab)                 # no tag: the score is ignored
    click(w, q)
    assert drawn(w, q) != "ash_bell"
