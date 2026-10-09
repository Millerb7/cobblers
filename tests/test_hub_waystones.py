"""tools/hub_waystones.py: one waystone each at the main places that are not gym towns (data/hub_waystones.json; the
owner, 2026-10-09).

Builder's tests (written with the generator); the independent audit is another agent's. Ground comes from the
canonical heightmap (tools/ground.py), never a world. The clearance check imports each place's own builder plan, so a
change to a builder that moves a column is seen here; what these tests cannot see is the world: nothing was placed,
and the waystone block's states (`half`, `facing`) are the ones tools/place_town.py already writes for the towns.

What none of this covers: that the server runs the function and the mod registers the stone, that a right-click on it
activates it, and what the ground looks like there (the heightmap is not the world's top block where a tree or a
build stands).
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

import ground as G  # noqa: E402
import hub_waystones as HW  # noqa: E402

DOC = HW.load()
GRD = G.load()
HUBS = {h["id"]: h for h in DOC["hubs"]}
EXPECT = {"shrew_station": (544, 2808, "west"), "coldwater_station": (6052, 1846, "east"),
          "northeast_landing": (6605, 2311, "north")}


def data(name):
    return json.loads((ROOT / "data" / name).read_text(encoding="utf-8"))


# ------------------------------------------------------------------------------------------------ the chosen hubs
def test_the_registry_chooses_the_three_and_their_positions_are_in_their_own_files():
    # Without it a hub is dropped or moved in its place's file and the registry still lists it.
    assert set(HUBS) == set(EXPECT)
    for hid, (x, z, face) in EXPECT.items():
        s = HW.stone(HUBS[hid], GRD)
        assert (s["x"], s["z"], s["facing"]) == (x, z, face), hid
    assert data("research_station.json")["waystone"]["at"] == [544, 2808]
    assert data("coldwater_station.json")["waystone"]["at"] == [6052, 1846]
    dock = next(d for d in data("ferry_docks.json")["docks"] if d["id"] == "northeast_landing")
    assert dock["waystone"]["at"] == [6605, 2311]


def test_the_checks_pass_on_the_committed_data():
    assert HW.problems(DOC, GRD) == []


def test_the_lower_half_is_one_above_the_heightmap_ground_and_dry():
    sea = data("world.json")["vertical"]["sea_level"]
    for hid in EXPECT:
        s = HW.stone(HUBS[hid], GRD)
        ground = int(GRD(s["x"], s["z"]))
        assert s["y"] == ground + 1
        assert ground >= sea + 1, "%s stands at the waterline" % hid


def test_the_function_sets_a_town_waystones_two_blocks_after_sweeping_an_older_one():
    # The same commands tools/place_town.py writes for a town (setblock lower then upper, same facing), after a fill
    # that removes a stone already standing so a rebuild never stacks a second.
    for s in HW.plan(DOC, GRD):
        body = [l for l in s["lines"] if not l.startswith("#")]
        assert len(body) == 3
        assert re.fullmatch(r"fill (-?\d+) (-?\d+) (-?\d+) (-?\d+) (-?\d+) (-?\d+) minecraft:air replace waystones:waystone", body[0])
        x0, y0, z0, x1, y1, z1 = map(int, body[0].split()[1:7])
        assert x0 <= s["x"] <= x1 and z0 <= s["z"] <= z1 and y0 <= s["y"] and s["y"] + 1 <= y1
        assert (x1 - x0 + 1) * (y1 - y0 + 1) * (z1 - z0 + 1) <= 32768
        assert body[1] == "setblock %d %d %d waystones:waystone[half=lower,facing=%s]" % (s["x"], s["y"], s["z"], s["facing"])
        assert body[2] == "setblock %d %d %d waystones:waystone[half=upper,facing=%s]" % (s["x"], s["y"] + 1, s["z"], s["facing"])


def test_the_function_force_loads_nothing_itself_so_the_step_must():
    import reapply  # noqa: F401  (the step is read below from the source)
    for s in HW.plan(DOC, GRD):
        assert not any(l.startswith("forceload") for l in s["lines"])
        assert any("chunks-loaded-by" in l for l in s["lines"])
    steps = HW.placement_steps(DOC, GRD)
    kinds = [k for k, _ in steps]
    # per hub: forceload add, wait, the function, forceload remove, in that order
    assert kinds == ["cmd", "wait", "fn", "cmd"] * 3
    for i in range(0, len(steps), 4):
        add, rm = steps[i][1], steps[i + 3][1]
        assert add.startswith("forceload add ") and rm == add.replace("add", "remove", 1)
        x0, z0, x1, z1 = map(int, add.split()[2:])
        fn = steps[i + 2][1]
        s = next(q for q in HW.plan(DOC, GRD) if fn.endswith("/" + q["id"]))
        assert x0 <= s["x"] - 2 and s["x"] + 2 <= x1 and z0 <= s["z"] - 2 and s["z"] + 2 <= z1


# ---------------------------------------------------------------------------------------- the clearance, and that it bites
def test_a_stone_on_a_column_a_builder_writes_is_refused():
    # Mutating the position (a record-side change) shows the check bites on each builder's own plan; the builders'
    # own plans are the authority for what they write, so this is as independent as the check can be.
    cases = {"shrew_station": (558, 2822), "coldwater_station": (6058, 1846), "northeast_landing": (6605, 2306)}
    for hid, at in cases.items():
        bad = copy.deepcopy(DOC)
        hub = next(h for h in bad["hubs"] if h["id"] == hid)
        real = HW.record

        def fake(h, hid=hid, at=at, real=real):
            r = dict(real(h))
            if h["id"] == hid:
                r["at"] = list(at)
            return r
        HW.record = fake
        try:
            probs = HW.problems(bad, GRD)
        finally:
            HW.record = real
        assert any(hid in p for p in probs), (hid, probs)


def test_a_wet_or_steep_site_is_refused():
    real = HW.record
    try:
        HW.record = lambda h: dict(real(h), at=[500, 2808]) if h["id"] == "shrew_station" else real(h)   # the jetty's water
        assert any("shrew_station" in p for p in HW.problems(DOC, GRD))
    finally:
        HW.record = real


def test_two_hubs_on_one_column_are_refused():
    bad = copy.deepcopy(DOC)
    bad["hubs"][1] = dict(bad["hubs"][1], source=bad["hubs"][0]["source"], path=bad["hubs"][0]["path"],
                          builder=bad["hubs"][0]["builder"], id="twin")
    assert any("share the column" in p for p in HW.problems(bad, GRD))


def test_a_hub_both_chosen_and_rejected_is_refused():
    bad = copy.deepcopy(DOC)
    bad["rejected"].append({"id": "shrew_station", "reason": "x"})
    assert any("both chosen and rejected" in p for p in HW.problems(bad, GRD))


# ------------------------------------------------------------------- our list is not the world: a sweep, not a list
def test_every_built_ferry_dock_and_every_station_is_a_hub_or_gives_a_reason():
    """A new built dock or station would otherwise be silently left without a decision. Each is accounted for here:
    chosen, rejected with a reason, or inside a place that already holds a waystone (its settlement)."""
    chosen = set(HUBS)
    rejected = {r["id"] for r in DOC["rejected"]}
    ferries = data("ferries.json")
    covered_by_a_waystoned_place = {
        # dock -> the waystone it is within a town of (distance, blocks, x/z, measured in the registry's rejected why)
        "sunset_south_pier": "sunset_west", "sunset_quay": "sunset_west", "tilpey_sabrina_dock": "gym6_town",
        "coldwater_station_jetty": "coldwater_station",
    }
    for d in ferries["docks"]:
        if d["status"] not in ("built",):
            continue
        assert d["id"] in chosen | rejected | set(covered_by_a_waystoned_place) | {"pacifidlog_square"}, \
            "built dock %s has no decision in data/hub_waystones.json" % d["id"]
    for sid in ("research_station.json", "coldwater_station.json"):
        assert any(h["source"] == sid for h in DOC["hubs"]), sid
    towns = {t["id"]: t for t in data("towns.json")["towns"]}
    placed = data("placements.json")["settlements"]
    for tid, t in towns.items():
        s = placed.get(tid) or {}
        has = bool(s.get("waystone") or (s.get("plan") or {}).get("waystone"))
        if has or t.get("tier") in ("outpost", "landmark_tree"):
            continue
        assert tid in rejected, "town %s has no waystone and no reason in data/hub_waystones.json" % tid


def test_no_hub_is_in_the_badge_ledger_or_the_blackout_checkpoints():
    # Hubs are earned by a visit: none is a flag's waystone (tools/progression_pack.py would forget or activate it)
    prog = data("progression.json")
    towns_in_ledger = {f["waystone"]["town"] for f in prog["flags"] if f.get("waystone")}
    assert not towns_in_ledger & set(HUBS)
    assert prog["waystone_gate"]["enforced"] is False


def test_the_old_no_waystone_answer_is_kept_and_marked_superseded():
    s = data("research_station.json")["site"]["waystone"]
    assert "SUPERSEDED 2026-10-09" in s and "no waystone" in s


# ----------------------------------------------------------------------------------------- probes and registration
def test_the_presence_probes_are_the_generators_two_halves_of_each_stone():
    probes = data("world_probes.json")["places"]["hub_waystones"]
    assert probes == HW.probes(DOC, GRD)
    assert len(probes) == 6
    assert all(p["expect"] is True and p["block"][3].startswith("waystones:waystone[half=") for p in probes)


def test_the_pack_is_built_and_run_by_a_step_after_the_builders_it_stands_on():
    import reapply
    assert "cobblers_hub_waystones" in reapply.SERVER_PACKS
    assert "cobblers_hub_waystones" not in reapply.EXCLUDED, "a step runs its functions; nothing excuses the pack"
    src = (ROOT / "tools" / "reapply.py").read_text(encoding="utf-8")
    order = [src.index('("%s"' % s) for s in ("R9RS", "R16H", "R18CW", "R18W", "R14")]
    assert order == sorted(order)
    files = HW.files(DOC, GRD)
    assert {p.rsplit("/", 1)[1][:-len(".mcfunction")] for p in files if p.endswith(".mcfunction")} == set(EXPECT)
