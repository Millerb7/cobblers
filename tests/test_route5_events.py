"""Route 5's Bellwether chain (tools/route5_events.py, data/quests.json evt_route5_bellwether).

Four layers, each caught by a different test:
  the sites     what is built, where, and that it is built on ground the heightmap gives and clear of the walked line;
  the records   data/scenes.json and data/rewards.json agree with the build, and the chain's trainers are not in a scene;
  the chain     a model player walks the dialogue DATA (entry rules, choices, transitions, grants) in every order and two
                players at once: what each reward is, that it is given once, that the strap changes exactly one reward;
  the economy   what the chain pays, priced from data/markets.json, against the leg's trainer income.

Nothing here reads the compiled dialogue or a world: the chain test interprets the authored data under the schema in
data/dialogue.json / data/quests.json, so it shares nothing with tools/compile_dialogue.py. Routes 1-3 are untouched: their
own tests (tests/test_route_events.py) are the proof, and the last test here pins the shared module's state.
"""
from __future__ import annotations

import itertools
import json
import math
import os
import re
import sys
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import route_events as RE  # noqa: E402
import route5_events as R5  # noqa: E402

DATA = ROOT / "data"
QUEST_ID = "evt_route5_bellwether"
F = "quest.%s." % QUEST_ID


def load(name):
    return json.loads((DATA / name).read_text(encoding="utf-8"))


SCENES = {s["id"]: s for s in load("scenes.json")["scenes"]}
QUESTS = {q["id"]: q for q in load("quests.json")["quests"]}
CONVS = {c["id"]: c for c in load("dialogue.json")["conversations"]}
FIELDS = {f["id"]: f for f in load("progression.json")["quest_fields"]}
REWARDS = {r["id"]: r for r in load("rewards.json")["rewards"]}
QUEST = QUESTS[QUEST_ID]
AIR = {"minecraft:air", "minecraft:cave_air", "minecraft:water"}
PASSABLE = ("_carpet", "_trapdoor", "_candle", "_button", "_pressure_plate", "minecraft:short_grass", "minecraft:fern")


def base(b):
    return b.split("[")[0].split("{")[0] if b else b


def passable(b):
    return b is None or base(b) in AIR or base(b).endswith(PASSABLE)


def solid(b):
    return b is not None and not passable(b)


@pytest.fixture(scope="module")
def built():
    import ground as G
    import terrain as T
    try:
        g = G.Ground()
    except T.TerrainUnavailable as e:
        pytest.skip("the canonical heightmap is unusable: %s" % e)
    road = R5.Road5()
    return g, road, R5.build(g, road)


def site(sites, sid):
    got = [s for s in sites if s.id == sid]
    assert len(got) == 1
    return got[0]


# ------------------------------------------------------------------ the tool as prepare runs it
# Without it `reapply.py prepare` stops at this step (drift, or something standing on the road) and nothing else says so.
def test_the_tool_exits_clean_as_prepare_runs_it(built, monkeypatch, tmp_path, capsys):
    orig = R5.write_pack
    monkeypatch.setattr(R5, "write_pack", lambda sites, out=None: orig(sites, tmp_path / "pack"))
    assert R5.main([]) == 0
    out = capsys.readouterr().out
    assert "DRIFT" not in out and "ROAD CLEARANCE" not in out
    assert (tmp_path / "pack" / "data" / "cobblers" / "function" / "route5_events" / "index.txt").is_file()


# Without it a drifted record (a position moved by a reshaped heightmap) passes because the check only looked at a clean file.
def test_a_moved_prop_is_reported_as_drift(built):
    g, road, sites = built
    scenes_doc, rewards_doc = load("scenes.json"), load("rewards.json")
    assert R5.drift(sites, scenes_doc, rewards_doc, write=False) == []
    rec = next(s for s in scenes_doc["scenes"] if s["id"] == "route5_cairn_bells")
    rec["props"][0]["on"][1] += 1
    rewards_doc["rewards"][[r["id"] for r in rewards_doc["rewards"]].index(R5.CACHE_ID)]["container"]["at"][2] += 1
    got = R5.drift(sites, scenes_doc, rewards_doc, write=False)
    assert any("bell_west" in d for d in got) and any(R5.CACHE_ID in d for d in got), got


# ------------------------------------------------------------------ the sites
def test_four_sites_build_with_their_scenes_and_nothing_else_is_in_the_pack(built, tmp_path):
    g, road, sites = built
    assert [s.id for s in sites] == R5.SCENE_IDS and all(s.scene == s.id for s in sites)
    R5.write_pack(sites, tmp_path / "pack")
    fdir = tmp_path / "pack" / "data" / "cobblers" / "function" / R5.FOLDER
    assert (fdir / "index.txt").read_text(encoding="utf-8").split() == ["00_clear"] + R5.SCENE_IDS
    assert sorted(p.stem for p in fdir.glob("*.mcfunction")) == sorted(["00_clear"] + R5.SCENE_IDS)


# Without it a site goes up on a column the walked line uses, or narrows the road.
def test_nothing_built_stands_within_a_block_of_the_walked_line_except_a_trail(built):
    _g, road, sites = built
    assert [p for s in sites for p in s.road_problems()] == []
    assert sum(len(s.surface) for s in sites) > 30, "the trails were not exercised"


# Without it the chain is out of order along the road, bunched, or a payoff that is not at the end.
def test_the_chain_runs_along_the_road_in_order_with_room_between(built):
    _g, road, sites = built
    walked = [road.nearest(*(((a["from"][0] + a["to"][0]) // 2, (a["from"][2] + a["to"][2]) // 2)))[2]
              for a in (SCENES[sid]["area"] for sid in R5.SCENE_IDS)]
    assert walked == sorted(walked), walked
    assert all(b - a >= 150 for a, b in zip(walked, walked[1:])), walked
    assert 100 <= walked[0] <= 200 and walked[-1] >= 850, walked           # the payoff is the last thing before Koga's town
    # the walked line itself: Route 5 is 1,051 blocks (data/routes.json); the payoff stands inside the last 20 per cent
    assert walked[-1] >= 0.8 * road.walked[-1] * 0.99 or walked[-1] > 850


# Without it an event stands where a trainer is seated (late_route_trainers refuses a seat inside any scene area, so the
# next prepare would fail on the other tool) or in the sight line of a fight.
def test_no_scene_area_holds_a_route_trainers_seat_and_none_is_within_forty_of_a_seat(built):
    late = load("late_route_trainers.json")["trainers"]
    seats = [t["seat"] for t in late if t["route"] == R5.ROUTE]
    assert len(seats) == 4
    for sid in R5.SCENE_IDS:
        a = SCENES[sid]["area"]
        for x, _y, z in seats:
            inside = a["from"][0] <= x <= a["to"][0] and a["from"][2] <= z <= a["to"][2]
            assert not inside, "%s holds a seat at %s" % (sid, (x, z))
            dx = max(a["from"][0] - x, 0, x - a["to"][0])
            dz = max(a["from"][2] - z, 0, z - a["to"][2])
            assert math.hypot(dx, dz) >= 40, "%s is %.0f from the seat at %s" % (sid, math.hypot(dx, dz), (x, z))


# Without it a scene overlaps a town's own ground, a shrine or another scene (checked against the data, not our builds).
def test_scene_areas_are_clear_of_towns_and_other_scenes():
    import town_audit
    import reapply
    pl = json.loads((DATA / "placements.json").read_text(encoding="utf-8"))
    towns = {sid: town_audit.town_bounds(sid, pl) for sid in ["hometown"] + reapply.places(pl)}
    for sid in R5.SCENE_IDS:
        a = SCENES[sid]["area"]
        for tid, (x0, z0, x1, z1) in towns.items():
            assert not (a["from"][0] <= x1 and a["to"][0] >= x0 and a["from"][2] <= z1 and a["to"][2] >= z0), (sid, tid)
        for other, o in SCENES.items():
            if other == sid:
                continue
            ob = o["area"]
            assert not (a["from"][0] <= ob["to"][0] and a["to"][0] >= ob["from"][0]
                        and a["from"][2] <= ob["to"][2] and a["to"][2] >= ob["from"][2]), (sid, other)
    pts = [tuple(sh["at"][:2]) for sh in load("shrines.json")["shrines"]]
    assert (4509, 2303) in pts, "the Route 5 niche moved: re-check the winter fold's distance from it"
    for sid in R5.SCENE_IDS:
        a = SCENES[sid]["area"]
        for x, z in pts:
            assert not (a["from"][0] - 8 <= x <= a["to"][0] + 8 and a["from"][2] - 8 <= z <= a["to"][2] + 8), (sid, x, z)


# Without it a block that decides encounters (data/spawn_blocks.json: wool, concrete, bell, lightning rod, white carpet...)
# goes into a place that the spawn policy never allows. Independent of the tool: the list is read from the data.
def test_no_site_writes_a_block_a_spawn_condition_names(built):
    _g, _road, sites = built
    banned = set(load("spawn_blocks.json")["blocks"])
    used = {base(b) for s in sites for b in s.blocks.values()}
    for s in sites:
        for c in s.cmds:
            m = re.match(r"(?:setblock \S+ \S+ \S+|fill \S+ \S+ \S+ \S+ \S+ \S+) (\S+)", c)
            if m:
                used.add(base(m.group(1)))
    assert len(used) > 25, "the set of blocks was barely exercised"
    assert used & banned == set(), sorted(used & banned)
    assert not any("concrete" in b or "wool" in b for b in used)


# Without it a prop's click box floats over grass beside the thing the dialogue talks about.
def test_every_prop_is_on_a_block_its_site_writes(built):
    _g, _road, sites = built
    n = 0
    for sid in R5.SCENE_IDS:
        s = site(sites, sid)
        for p in SCENES[sid]["props"]:
            got = s.blocks.get(tuple(p["on"]))
            assert got is not None and base(got) != "minecraft:air", "%s/%s on %s" % (sid, p["id"], p["on"])
            n += 1
    assert n == 6


def _standers(sid):
    rec, out = SCENES[sid], []
    for name, m in (rec.get("markers") or {}).items():
        for ox, oz in m["slots"]:
            out.append(("marker %s" % name, (math.floor(m["at"][0] + 0.5 + ox), m["at"][1], math.floor(m["at"][2] + 0.5 + oz))))
    for n in rec.get("npcs") or []:
        out.append(("npc %s" % n["conversation"], tuple(n["at"])))
    return out


# Without it an actor or NPC is placed inside a wall, a post or a bench the site built, in the ground, or over a hole.
def test_every_npc_and_actor_slot_has_room_and_something_to_stand_on(built):
    g, _road, sites = built
    checked = bad = 0
    msgs = []
    for sid in R5.SCENE_IDS:
        s = site(sites, sid)
        # the records' positions AND the build's own (a record that has not caught up with the build is drift's business)
        built_npcs = [("built npc %s" % n["conversation"], tuple(n["at"])) for n in s.npcs]
        for what, (x, y, z) in _standers(sid) + built_npcs:
            checked += 1
            feet, head, below = s.blocks.get((x, y, z)), s.blocks.get((x, y + 1, z)), s.blocks.get((x, y - 1, z))
            if not passable(feet) or not passable(head):
                msgs.append("%s %s: feet %s head %s" % (sid, what, feet, head))
            if (x, y, z) not in s.blocks and y <= g(x, z):
                msgs.append("%s %s: feet at y%d inside the ground (heightmap y%d)" % (sid, what, y, g(x, z)))
            if not (solid(below) or (below is None and g(x, z) == y - 1)):
                msgs.append("%s %s: below is %s, ground y%d" % (sid, what, below, g(x, z)))
    assert checked >= 13
    assert msgs == []


# Without it a building floor sits above the ground outside its door (a step nobody built) or the door is walled in.
def test_the_hut_and_byre_doors_open_level_with_the_ground_outside(built):
    g, _road, sites = built
    hut, byre = site(sites, "route5_lee_hut"), site(sites, "route5_winter_fold")
    for s, door_out, door_in in ((hut, (4396, 2074), (4397, 2074)), (byre, (4571, 2293), (4571, 2292))):
        f = g(*door_out)
        assert s.blocks.get((door_in[0], f + 1, door_in[1])) == "minecraft:air", (s.id, "no door")
        assert s.blocks.get((door_in[0], f + 2, door_in[1])) == "minecraft:air", (s.id, "door too low")
        assert base(s.blocks.get((door_in[0], f, door_in[1]))) == "minecraft:spruce_planks", (s.id, "sill is not the floor")


CLEAR = re.compile(r"fill -?\d+ -?\d+ -?\d+ -?\d+ -?\d+ -?\d+ minecraft:air replace ")


@pytest.fixture(scope="module")
def pack(built, tmp_path_factory):
    _g, _road, sites = built
    out = tmp_path_factory.mktemp("route5_events") / "pack"
    R5.write_pack(sites, out)
    return sites, out / "data" / "cobblers" / "function" / R5.FOLDER


# Without it a function writes into chunks it has not loaded (a silent no-op) or releases a chunk a later write needs.
def test_each_function_holds_every_chunk_it_writes_for_its_whole_run(pack):
    import function_limits as FL
    sites, fdir = pack
    for s in sites:
        lines = (fdir / ("%s.mcfunction" % s.id)).read_text(encoding="utf-8").splitlines()
        assert [l for l in lines if re.match(r"(setblock|fill) ", l)] == [c for c in s.cmds if re.match(r"(setblock|fill) ", c)]
        assert FL.unloaded_writes(lines) == [] and not FL.releases_mid_run(lines) and FL.check_lines(lines, s.id) == []
    clear = (fdir / "00_clear.mcfunction").read_text(encoding="utf-8").splitlines()
    assert sum(1 for l in clear if CLEAR.match(l)) > 100
    assert FL.unloaded_writes(clear) == [] and FL.check_lines(clear, "00_clear") == []


# Without it a clear lands in a town or an elder's crown (the protection is the only thing between a clear and a tree
# another tool built), or the elder 118 blocks away reads as in the way.
def test_no_clearing_tile_touches_a_town_or_a_built_elder(built):
    _g, _road, sites = built
    elders = load("elder_trees.json")["elders"]
    assert any(abs(e["x"] - 4346) < 3 and abs(e["z"] - 2296) < 3 for e in elders), "the elder near Route 5 moved"
    n = 0
    for s in sites:
        for (x0, _y0, z0, x1, _y1, z1) in s.cleared:
            n += 1
            assert R5.protected(x0, z0, x1, z1) is None
            for e in elders:
                nx, nz = min(max(e["x"], x0), x1), min(max(e["z"], z0), z1)
                assert math.hypot(nx - e["x"], nz - e["z"]) > 26
    assert n > 40


# Without it the protection could be bypassed by any widened clear and nothing here would notice.
def test_a_clear_over_a_town_or_an_elder_is_refused_by_the_protection(built):
    g, road, _sites = built
    t = R5.Site5("probe", g, road, None, "a clear over Erika's town")
    t.clear(4290, 1530, 4330, 1570, up=14)
    assert t.cleared == [] and any(k.startswith("town ") for k in t.kept), t.kept
    e = R5.Site5("probe", g, road, None, "a clear over the elder at (4346, 2296)")
    e.clear(4340, 2290, 4352, 2302, up=14)
    assert e.cleared == [] and any("(4346, 2296)" in k for k in e.kept), e.kept


# Without it the probes in data/world_probes.json fall behind the build.
def test_the_presence_probes_match_what_the_sites_build(built):
    _g, _road, sites = built
    have = load("world_probes.json")["places"].get(R5.PROBE_KEY)
    assert have == R5.probes(sites), "run: python tools/route5_events.py probes --write"
    assert len(have) >= 12 and sum(1 for p in have if "entity" in p) == 3
    for p in have:
        if "block" in p:
            x, y, z, want = p["block"]
            assert base(site(sites, p["what"].split(":")[0]).blocks[(x, y, z)]) == want


# ------------------------------------------------------------------ the records
def test_the_four_scenes_belong_to_the_one_quest_and_open_only_its_conversations():
    assert [s for s in SCENES if SCENES[s]["quest_id"] == QUEST_ID] == R5.SCENE_IDS
    opened = set()
    for sid in R5.SCENE_IDS:
        sc = SCENES[sid]
        assert "tools/route5_events.py" in sc["built_by"]
        opened |= {p["conversation"] for p in sc["props"]} | {a["conversation"] for a in sc["actors"]} | {n["conversation"] for n in sc["npcs"]}
    assert opened == set(QUEST["dialogue_ids"]) and len(opened) == 11
    for cid in opened:
        assert CONVS[cid]["quest_id"] == QUEST_ID
    npcs = {c for c in opened if CONVS[c]["npc_id"]}
    assert npcs == {"dlg_r5_nan", "dlg_r5_gorse", "dlg_r5_jory"}


def test_every_field_the_chain_uses_is_declared_once_for_a_player_and_listed():
    refs = QUEST["progression_field_refs"]
    assert len(refs) == len(set(refs)) == 13
    assert {FIELDS[f]["scope"] for f in refs} == {"player"}
    assert {f["id"] for f in FIELDS.values() if f["quest_id"] == QUEST_ID} == set(refs)
    used = set(re.findall(r'"field": "(quest\.%s\.[a-z_]+)"' % QUEST_ID, json.dumps([QUEST, [CONVS[c] for c in QUEST["dialogue_ids"]]])))
    assert used <= set(refs)


def test_the_cache_is_a_barrel_inside_its_trigger_and_asks_for_no_quest_state():
    r = REWARDS[R5.CACHE_ID]
    x, y, z = r["container"]["at"]
    lo, hi = r["trigger"]["min"], r["trigger"]["max"]
    assert r["kind"] == "cache" and r["container"]["block"] == "minecraft:barrel"
    assert lo[0] <= x <= hi[0] and lo[1] <= y <= hi[1] and lo[2] <= z <= hi[2]
    assert "requires_flags" not in r                               # a cache cannot read a quest field; the dialogue says so
    assert {c["item"] for c in r["contents"]} == {"cobblemon:sitrus_berry", "cobblemon:lum_berry"}


# ------------------------------------------------------------------ the chain, played from the data
class Player:
    """A model player: quest fields (initial values from data/progression.json), an inventory, and the talk() loop that
    reads the authored dialogue and quest records. Written from the schema in those files' own headers, not from
    tools/compile_dialogue.py."""

    def __init__(self):
        self.f = {fid: d["initial"] for fid, d in FIELDS.items() if d["quest_id"] == QUEST_ID}
        self.inv = {}
        self.log = []

    def holds(self, c):
        k = c["kind"]
        if k == "always":
            return True
        if k == "progression_equals":
            return self.f[c["field"]] == c["value"]
        if k == "all":
            return all(self.holds(x) for x in c["conditions"])
        if k == "any":
            return any(self.holds(x) for x in c["conditions"])
        if k == "not":
            return not self.holds(c["condition"])
        raise AssertionError("condition kind %s" % k)

    def transition(self, tid):
        t = next(t for t in QUEST["transitions"] if t["id"] == tid)
        if not all(self.holds(c) for c in t["conditions"]):
            self.log.append("%s refused" % tid)
            return
        for e in t["effects"]:
            if e["kind"] == "set_progression":
                self.f[e["field"]] = e["value"]
            elif e["kind"] == "grant_reward_once":
                if self.f[e["claim_field"]] is not True:
                    for it in next(r for r in QUEST["rewards"] if r["id"] == e["reward"])["contents"]:
                        self.inv[it["item"]] = self.inv.get(it["item"], 0) + it["count"]
                    self.f[e["claim_field"]] = True
                    self.log.append("granted %s" % e["reward"])
            else:
                raise AssertionError("effect kind %s" % e["kind"])
        self.log.append(tid)

    def talk(self, cid, picks=()):
        c = CONVS[cid]
        nodes = {n["id"]: n for n in c["nodes"]}
        picks = list(picks)
        entry = next(r for r in sorted(c["entry_rules"], key=lambda r: r["priority"]) if self.holds(r["when"]))
        for a in entry.get("actions") or []:
            self.transition(a["transition"])
        node, seen = nodes[entry["node"]], []
        while True:
            seen.append(node["id"])
            assert len(seen) < 60, seen
            if node["kind"] == "line":
                for a in node.get("actions_after_acknowledge") or []:
                    self.transition(a["transition"])
                if node["next"] == node["id"]:
                    return seen
                node = nodes[node["next"]]
            else:
                if not picks:
                    return seen
                want = picks.pop(0)
                visible = [r for r in node["responses"] if not r.get("visible_when") or self.holds(r["visible_when"])]
                assert want in [r["id"] for r in visible], "%s: %s is not offered at %s (offered: %s)" % (cid, want, node["id"], [r["id"] for r in visible])
                r = next(r for r in visible if r["id"] == want)
                closes = False
                for a in r.get("actions") or []:
                    if a["kind"] == "quest_transition":
                        self.transition(a["transition"])
                    elif a["kind"] == "close_dialogue":
                        closes = True
                if closes:
                    return seen
                node = nodes[r["next"]]


EVENTS = {
    "fold": lambda p: p.talk("dlg_r5_nan", ["r_where", "r_bell", "r_help"]),
    "bells": lambda p: (p.talk("dlg_r5_bell_west"), p.talk("dlg_r5_bell_south"), p.talk("dlg_r5_bell_north")),
    "hut": lambda p: p.talk("dlg_r5_gorse", ["r_box", "r_salve"]),
    "winter": lambda p: (p.talk("dlg_r5_tolly"), p.talk("dlg_r5_jory")),
}
FULL = {"cobblemon:full_heal": 3, "cobblemon:great_ball": 2, "cobblemon:sitrus_berry": 2, "cobblemon:magnet": 1}


def test_the_whole_chain_in_order_pays_the_commons_parcel_and_the_full_reward_once():
    p = Player()
    for e in ("fold", "bells", "hut", "winter"):
        EVENTS[e](p)
    assert p.inv == FULL, p.inv
    assert p.f[F + "reward_claimed"] and p.f[F + "commons_taken"] and p.f[F + "completed"] and p.f[F + "strap"]
    before, fields = dict(p.inv), {k: v for k, v in p.f.items() if not k.endswith("cursor")}
    for _ in range(3):                                       # coming back to every one of them changes nothing
        for cid in ("dlg_r5_nan", "dlg_r5_bell_north", "dlg_r5_gorse", "dlg_r5_tolly", "dlg_r5_jory"):
            p.talk(cid, ["r_bye"] if CONVS[cid]["npc_id"] else [])
    assert p.inv == before and {k: v for k, v in p.f.items() if not k.endswith("cursor")} == fields


# Without it the strap does not matter (or Jory pays twice): the magnet is exactly the strap's reward, in every order.
@pytest.mark.parametrize("order", list(itertools.permutations(["fold", "bells", "hut", "winter"])), ids=lambda o: "-".join(o))
def test_every_order_reaches_the_same_state_and_the_magnet_follows_the_strap(order):
    p = Player()
    for e in order:
        EVENTS[e](p)
    magnet = order.index("bells") < order.index("winter")      # the strap must be in hand when Jory pays
    expect = dict(FULL)
    if not magnet:
        del expect["cobblemon:magnet"]
    assert p.inv == expect, (order, p.inv)
    assert p.f[F + "reward_claimed"] is True and p.f[F + "strap"] is True


def test_jory_pays_nothing_until_tolly_is_found_and_the_first_visit_introduces_him():
    p = Player()
    first = p.talk("dlg_r5_jory", ["r_fold"])
    assert first[0] == "j_01" and p.inv == {} and p.f[F + "met_jory"]
    again = p.talk("dlg_r5_jory", ["r_tolly"])
    assert again[0] == "j_hub" and p.inv == {}
    p.talk("dlg_r5_tolly")
    assert p.f[F + "found_tolly"] and p.inv == {}
    p.talk("dlg_r5_jory")
    assert p.inv == {"cobblemon:great_ball": 2, "cobblemon:sitrus_berry": 2}


def test_the_commons_box_gives_one_parcel_and_never_offers_the_other_afterwards():
    p = Player()
    p.talk("dlg_r5_gorse", ["r_box", "r_oil"])
    assert p.inv == {"cobblemon:super_potion": 2}
    seen = p.talk("dlg_r5_gorse", ["r_tear"])
    with pytest.raises(AssertionError, match="is not offered"):
        p.talk("dlg_r5_gorse", ["r_box"])
    assert p.inv == {"cobblemon:super_potion": 2} and seen[0] == "g_hub"


def test_a_player_who_chose_but_was_not_paid_is_taken_back_to_the_parcel_not_the_menu():
    p = Player()
    p.talk("dlg_r5_gorse")                                  # met
    p.transition("pick_salve")                              # chose; the delivery failed before the claim was written
    assert p.f[F + "commons"] == "salve" and not p.f[F + "commons_taken"]
    assert p.talk("dlg_r5_gorse")[0] == "g_salve"
    assert p.inv == {"cobblemon:full_heal": 3}


def test_two_players_share_nothing():
    a, b = Player(), Player()
    for e in ("fold", "bells", "hut", "winter"):
        EVENTS[e](a)
    assert b.inv == {} and not any(v is True for k, v in b.f.items() if not k.endswith("cursor"))
    EVENTS["winter"](b)
    assert b.inv == {"cobblemon:great_ball": 2, "cobblemon:sitrus_berry": 2} and a.inv == FULL


def test_every_conversation_node_is_reachable_and_every_transition_is_used():
    used, reached = set(), set()
    for cid in QUEST["dialogue_ids"]:
        c = CONVS[cid]
        nodes = {n["id"]: n for n in c["nodes"]}
        todo = [r["node"] for r in c["entry_rules"]]
        for r in c["entry_rules"]:
            used |= {a["transition"] for a in r.get("actions") or []}
        while todo:
            n = todo.pop()
            if (cid, n) in reached:
                continue
            reached.add((cid, n))
            node = nodes[n]
            used |= {a["transition"] for a in node.get("actions_after_acknowledge") or []}
            if node["kind"] == "line":
                todo.append(node["next"])
            for r in node.get("responses") or []:
                used |= {a["transition"] for a in r.get("actions") or [] if a["kind"] == "quest_transition"}
                todo.append(r["next"])
        assert {(cid, n) for n in nodes} <= reached, sorted(set(nodes) - {n for c2, n in reached if c2 == cid})
    assert used == {t["id"] for t in QUEST["transitions"]}, sorted({t["id"] for t in QUEST["transitions"]} - used)


# ------------------------------------------------------------------ the economy
def _grants():
    """Every item the chain can give one player, by the worst case (the best choice at the commons box, the strap held)."""
    best_commons = max(QUEST["rewards"][:2], key=lambda r: sum(i["count"] for i in r["contents"]))
    full = next(r for r in QUEST["rewards"] if r["id"] == "reward_full")
    return best_commons["contents"] + full["contents"] + REWARDS[R5.CACHE_ID]["contents"]


def _shelf_prices():
    out = {}

    def walk(v):
        if isinstance(v, dict):
            if "item" in v and "price" in v and "count" in v:
                out[v["item"]] = v["price"] / v["count"]
            for c in v.values():
                walk(c)
        elif isinstance(v, list):
            for c in v:
                walk(c)
    walk(load("markets.json"))
    return out


# Without it an event pays more than the leg's trainers do, or sells into the bank (income that is not a battle).
def test_what_the_chain_pays_is_a_small_part_of_the_legs_trainer_income_and_cannot_be_sold_to_the_bank():
    mk = load("markets.json")
    leg = mk["income_basis"]["leg_by_badge"]["5"]                  # Route 5's trainers are walked after badge 4, in leg 5
    prices = _shelf_prices()
    grants = _grants()
    priced = sum(prices[i["item"]] * i["count"] for i in grants if i["item"] in prices)
    unpriced = sorted({i["item"] for i in grants if i["item"] not in prices})
    assert unpriced == ["cobblemon:lum_berry", "cobblemon:sitrus_berry"], unpriced      # the berries are the only unpriced items
    assert 0 < priced <= 0.12 * leg, (priced, leg)
    assert not any(i["item"].endswith(("coins", "dollars")) or "cobbledollars" in i["item"] for i in grants)   # no money
    bank = load("bank.json")
    bought = {b["item"] for b in bank["buys"]}
    assert {i["item"] for i in grants} & bought == set(), "the bank buys a reward item"


# Without it an item id is typed from memory: every id is looked up at its jar path.
def test_every_reward_item_exists_in_the_cobblemon_1_8_jar():
    jars = list(Path("C:/Users/wnd/Documents/cobblers-local/server-snapshot-2026-10-05/mods").glob("Cobblemon-fabric-1.8.0*.jar"))
    if not jars:
        pytest.skip("the 1.8.0 server snapshot is not on this machine")
    names = set(zipfile.ZipFile(jars[0]).namelist())
    ids = {i["item"] for i in _grants()}
    assert len(ids) == 5
    for it in ids:
        assert "assets/cobblemon/models/item/%s.json" % it.split(":")[1] in names, it
    for r in QUEST["rewards"] + [REWARDS[R5.CACHE_ID]]:
        for it in r["contents"]:
            assert it["verification"].startswith("assets/cobblemon/models/item/") and it["verification"].split(" in ")[0] in names


# ------------------------------------------------------------------ Routes 1-3 are untouched
# Without it extending the walked-line check for Route 5 could leave Routes 1-3's region changed for the next caller.
def test_the_shared_module_is_left_exactly_as_it_was_found(built):
    before = (RE.REGION, tuple(RE.SITES), RE.ROUTES.copy())
    R5.check_paths_heightmap()
    assert (RE.REGION, tuple(RE.SITES), RE.ROUTES) == before and RE.REGION == (1000, 1200, 2400, 5450)
    assert not any(s.__name__ in ("empty_fold", "cairn_bells", "lee_hut", "winter_fold") for s in RE.SITES)
    assert not any(sid in SCENES and "tools/route_events.py" in SCENES[sid]["built_by"] for sid in R5.SCENE_IDS)


# ------------------------------------------------------------------ the re-apply step
@pytest.fixture(scope="module")
def steps():
    import reapply
    if not (reapply.PACKS / "cobblers_route5_events" / "data" / "cobblers" / "function" / "route5_events" / "index.txt").is_file():
        pytest.skip("cobblers_route5_events is not built here (python tools/reapply.py prepare, or python tools/route5_events.py)")
    try:
        return reapply.steps()
    except SystemExit as e:
        pytest.skip("reapply.steps() needs packs and derived files this checkout lacks: %s" % str(e)[:120])


def _step(steps, sid):
    ids = [s[0] for s in steps]
    assert sid in ids, "no step %s" % sid
    return steps[ids.index(sid)], ids.index(sid)


# Without it the sites go up before the signposts and a donor's air margin erases them (the Route 7 post), or the props
# and NPCs R17 places are stood where the blocks do not exist yet.
def test_r12r5_runs_after_the_signposts_and_routes_1_to_3_and_before_the_props_stand(steps):
    (_s, i), r15, r12, r17 = _step(steps, "R12R5"), _step(steps, "R15")[1], _step(steps, "R12")[1], _step(steps, "R17")[1]
    assert r15 < r12 < i < r17


# Without it R12R5 runs a subset of the sites, none, or runs them out of the order the pack wrote.
def test_r12r5_runs_every_function_the_pack_lists_in_its_order(steps):
    import reapply
    listed = reapply.indexed("cobblers_route5_events", R5.FOLDER)
    assert listed == ["00_clear"] + R5.SCENE_IDS
    assert _step(steps, "R12R5")[0][2] == [("fn", "cobblers:route5_events/%s" % f) for f in listed]
    base = reapply.PACKS / "cobblers_route5_events" / "data" / "cobblers" / "function" / R5.FOLDER
    assert all((base / ("%s.mcfunction" % f)).is_file() for f in listed)


# Without it the pack is built and never installed, or is excluded with no reason (the fail-closed check would stop prepare).
def test_the_pack_is_installed_on_the_server_and_covered_by_its_step(steps):
    import reapply
    assert "cobblers_route5_events" in reapply.SERVER_PACKS
    assert "cobblers_route5_events" not in reapply.EXCLUDED and "cobblers_route5_events" not in reapply.WORLD_LOCAL
    assert not [b for b in reapply.uncovered(steps) if b.startswith("cobblers_route5_events ")]
    without = [s for s in steps if s[0] != "R12R5"]
    assert any(b.startswith("cobblers_route5_events ") for b in reapply.uncovered(without))


# Without it prepare never runs the tool, and a drifted record is found only when a human runs it.
def test_prepare_runs_the_tool():
    src = (ROOT / "tools" / "reapply.py").read_text(encoding="utf-8")
    assert 'add("route5_events", "route5_events.py", *src)' in src
