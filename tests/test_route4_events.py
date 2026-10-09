"""tools/route4_events.py: Route 4's middle event chain (the headwall camp, the steam hollow, the strayed load, the old
summit road, the thaw gate), its pack, and the records it writes into data/.

Written by the builder of the tool (the brief for this unit asked for tests with the build), NOT by a reviewer: an
independent audit by another agent is still owed. To keep the tests from being the generator agreeing with itself, the
pack is read back from the written .mcfunction files with this file's own parser, the road from data/route_paths.json,
the ground from tools/ground.py, the tunnel mouth from data/towns.json by the formula tools/cavern_plan.py is read for,
and the quest's shape from the quest JSON alone.

What is asserted
  - the tool exits clean: the records in data/ equal the design, nothing stands on the walked line, within 3.5 of the
    tunnel mouth, inside the gate's earthwork or on an undeclared spawn-condition block;
  - the pack: indexed, every function holds and releases its chunks, no concrete, only vanilla blocks;
  - the geometry, from the written commands: the trail is one 8-connected walkable strip from the walked line to the
    gate, the six milestones count down along it and each has its zone, people and markers stand in air on the ground;
  - the quest as a graph: every transition is invoked, every completion is reachable, nothing but flags, a scene sync
    and a once-only grant is written, each grant is guarded by its own claim, and no event reads another's flags to
    unlock itself (the finale's reward does not depend on the earlier events);
  - the economy: no reward item in the Bank's buy list, none a progression item, the sizes small, no cash;
  - the files: the records are spliced in without touching any other line, idempotently;
  - Routes 1-3: tools/route_events.py is imported, never assigned to.

Not covered (needs a running server): that a prop click opens its conversation, that a zone's transition fires, that the
HUD line shows, that the Gogoat actor stands where the state says, that the pool does not freeze and the moss does not
snow over (ASSUMED from the vanilla block-light rule), that the milestones read well at eye height, and that the grant
runs once for each of two players.
"""
import copy
import json
import math
import re
import shutil
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import route4_events as R  # noqa: E402
import ground as G  # noqa: E402

PACK = ROOT / "build" / "datapacks" / "cobblers_route4_events" / "data" / "cobblers" / "function" / "route4_events"
SPEC = json.loads((ROOT / "data" / "route4_events.json").read_text(encoding="utf-8"))
QID = SPEC["quest"]["id"]
SITES = ["headwall_camp", "steam_hollow", "strayed_load", "summit_road", "thaw_gate"]
SURFACE = {"minecraft:dirt_path", "minecraft:coarse_dirt", "minecraft:moss_block", "minecraft:gravel"}   # replace the ground itself
CMD_SET = re.compile(r"^setblock (-?\d+) (-?\d+) (-?\d+) (.+)$")
CMD_FILL = re.compile(r"^fill (-?\d+) (-?\d+) (-?\d+) (-?\d+) (-?\d+) (-?\d+) (\S+)$")


def read(path):
    return json.loads((ROOT / "data" / path).read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def run():
    """The tool as prepare runs it: exit code, and the pack it wrote."""
    return R.main([])


@pytest.fixture(scope="module")
def blocks(run):
    """{site: {(x, y, z): block id}}, parsed from the written functions with this file's own reader; fills that have a
    `replace` filter are conditional clears and are not writes."""
    out = {}
    for s in SITES:
        d = {}
        for line in (PACK / ("%s.mcfunction" % s)).read_text(encoding="utf-8").splitlines():
            m = CMD_SET.match(line)
            if m:
                d[(int(m[1]), int(m[2]), int(m[3]))] = (m[4], re.split(r"[\[{]", m[4])[0])
                continue
            m = CMD_FILL.match(line)
            if m:
                x0, y0, z0, x1, y1, z1 = [int(v) for v in m.groups()[:6]]
                for x in range(min(x0, x1), max(x0, x1) + 1):
                    for y in range(min(y0, y1), max(y0, y1) + 1):
                        for z in range(min(z0, z1), max(z0, z1) + 1):
                            d[(x, y, z)] = (m[7], re.split(r"[\[{]", m[7])[0])
        out[s] = d
    return out


@pytest.fixture(scope="module")
def ground(run):
    return G.Ground(None)


@pytest.fixture(scope="module")
def road():
    doc = read("route_paths.json")["paths"]["route_04_surge_to_erika"]
    return [tuple(p) for p in doc]


def scenes():
    return {s["id"]: s for s in read("scenes.json")["scenes"] if s["id"].startswith("route4_")}


# ---------------------------------------------------------------- the tool and its pack
def test_the_tool_exits_clean_as_prepare_runs_it(run):
    """No drift between the design and data/, and no problem the tool's own checks find."""
    assert run == 0


def test_the_pack_is_indexed_and_every_function_holds_and_releases_its_chunks(run):
    idx = (PACK / "index.txt").read_text(encoding="utf-8").split()
    assert idx == ["00_clear"] + SITES
    for name in idx:
        text = (PACK / ("%s.mcfunction" % name)).read_text(encoding="utf-8")
        assert text.strip(), name
    for s in SITES:
        lines = (PACK / ("%s.mcfunction" % s)).read_text(encoding="utf-8").splitlines()
        adds = [i for i, l in enumerate(lines) if l.startswith("forceload add")]
        rems = [i for i, l in enumerate(lines) if l.startswith("forceload remove")]
        writes = [i for i, l in enumerate(lines) if l.startswith(("setblock", "fill"))]
        assert adds and rems and max(adds) < min(writes) and min(rems) > max(writes), s


def test_nothing_is_concrete_everything_is_vanilla_and_spawn_conditions_are_declared(blocks):
    cond = set(read("spawn_blocks.json")["blocks"])
    for s, d in blocks.items():
        for (full, base) in d.values():
            assert base.startswith("minecraft:"), (s, base)
            assert "concrete" not in base, (s, base)
            if base in cond:
                assert base in R.SPAWN_OK, "%s writes the spawn-condition block %s undeclared" % (s, base)
    # the declared ones are real spawn conditions, so the declaration is not decoration
    assert set(R.SPAWN_OK) <= cond
    # and each has a policy entry whose scope names this tool (contract C4 wants a place, not a hope)
    policy = read("spawn_block_policy.json")["whitelist"]
    for b in R.SPAWN_OK:
        assert any(b in w["blocks"] and "route4_events" in (w.get("scope") or "") for w in policy), b


def test_nothing_stands_on_the_walked_line_but_the_ground_itself(blocks, road):
    cells = set(road)
    near = lambda x, z: any((x + dx, z + dz) in cells for dx in (-1, 0, 1) for dz in (-1, 0, 1))
    bad = [(s, p, b[1]) for s, d in blocks.items() for p, b in d.items()
           if b[1] != "minecraft:air" and b[1] not in SURFACE and near(p[0], p[2])]
    assert bad == []


def test_nothing_is_written_within_3_5_of_the_tunnel_mouth_or_inside_the_gate_earthwork(blocks, ground):
    fp = next(t for t in read("towns.json")["towns"] if t["id"] == "displaced_city")["footprint"]
    mouth = (fp["max_x"], (fp["min_z"] + fp["max_z"]) // 2 - 10)
    assert mouth == tuple(SPEC["sites"]["thaw_gate"]["mouth"]) == (3035, 1700)
    src = (ROOT / "tools" / "cavern_plan.py").read_text(encoding="utf-8")
    assert 'mouth = (fp["max_x"], (fp["min_z"] + fp["max_z"]) // 2 - 10)' in src, "the cavern pack's mouth formula changed: re-derive the mouth"
    gate = [a for a in read("placements.json")["settlements"]["displaced_city"]["plan"]["anchors"] if a["id"] == "displaced_gate"]
    x0, z0, x1, z1 = gate[0]["rect"]
    for s, d in blocks.items():
        for (x, y, z), (_, b) in d.items():
            if b == "minecraft:air":
                continue
            assert math.hypot(x - mouth[0], z - mouth[1]) >= 3.5, (s, (x, y, z))
            if s != "summit_road":
                assert not (x0 <= x <= x1 and z0 <= z <= z1 and y >= ground(x, z) - 2), (s, (x, y, z))


def test_sites_keep_clear_of_trainers_the_merian_hut_and_each_other(blocks):
    trainers = [t["seat"] for t in read("late_route_trainers.json")["trainers"] if t["id"].startswith("route_04")]
    hut = next(p for p in read("placements.json")["placements"] if p["id"] == "merian_hut_pokecenter")["position"]
    for s, d in blocks.items():
        for (x, y, z), (_, b) in d.items():
            if b == "minecraft:air":
                continue
            assert math.hypot(x - hut["x"], z - hut["z"]) > 150, (s, (x, y, z))
            for t in trainers:
                assert math.hypot(x - t[0], z - t[2]) > 30, (s, (x, y, z), t)


# ---------------------------------------------------------------- the trail and the milestones
def sign_text(full):
    m = re.search(r"messages:\[(.*?)\]", full)
    return [json.loads(q.replace("\\'", "'")) for q in re.findall(r"'((?:[^'\\]|\\.)*)'", m[1]) if q]


def milestones(blocks):
    out = {}
    for p, (full, base) in blocks["summit_road"].items():
        if base.endswith("_sign"):
            lines = sign_text(full)
            if lines[0] == "SUMMIT" or lines[0].startswith("OLD SUMMIT"):
                n = int(next(l for l in lines if l.isdigit()))
                out[n] = p
    return out


def test_the_trail_is_one_walkable_strip_from_the_road_to_the_gate(blocks, ground, road):
    trail = {(x, z) for (x, y, z), (_, b) in blocks["summit_road"].items() if b == "minecraft:dirt_path"}
    assert len(trail) > 300
    start = [c for c in trail if any(math.hypot(c[0] - r[0], c[1] - r[1]) <= 1.5 for r in road)]
    assert start, "the trail never touches the walked line"
    seen, frontier = set(start[:1]), list(start[:1])
    while frontier:
        x, z = frontier.pop()
        for dx in (-1, 0, 1):
            for dz in (-1, 0, 1):
                n = (x + dx, z + dz)
                if n in trail and n not in seen:
                    assert abs(ground(*n) - ground(x, z)) <= 1, "a step of more than one block at %s" % (n,)
                    seen.add(n)
                    frontier.append(n)
    assert seen == trail, "%d trail cells are cut off from the road" % len(trail - seen)
    gx, gz = SPEC["sites"]["thaw_gate"]["gate"]
    assert min(math.hypot(x - gx, z - gz) for x, z in trail) <= 4


def test_six_milestones_count_down_along_the_trail_and_each_has_its_zone(blocks):
    m = milestones(blocks)
    assert sorted(m) == [0, 1, 2, 3, 4, 5]
    gx, gz = SPEC["sites"]["thaw_gate"]["gate"]
    dist = [math.hypot(m[n][0] - gx, m[n][2] - gz) for n in (5, 4, 3, 2, 1, 0)]
    assert all(a > b + 20 for a, b in zip(dist, dist[1:])), "the stones are not in order along the trail: %s" % dist
    zones = {z["id"]: z for z in scenes()["route4_summit_road"]["zones"]}
    for n, (x, y, z) in m.items():
        box = zones["z%d" % n]
        assert all(box["from"][i] <= (x, y, z)[i] <= box["to"][i] for i in range(3)), "zone z%d does not hold its stone" % n
        assert zones["z%d" % n]["transitions"] == ["pass_%d" % n]
    # a stone and its sign: a pillar of two blocks under the sign
    for n, (x, y, z) in m.items():
        assert blocks["summit_road"][(x, y - 1, z)][1] == "minecraft:stone_bricks"
        assert blocks["summit_road"][(x, y - 2, z)][1] == "minecraft:mossy_stone_bricks"
        assert "is_waxed:1b" in blocks["summit_road"][(x, y, z)][0]


def test_people_markers_and_props_stand_in_air_on_the_ground(blocks, ground):
    written = {p: b[1] for d in blocks.values() for p, b in d.items() if b[1] != "minecraft:air"}
    for sid, sc in scenes().items():
        stands = [tuple(n["at"]) for n in sc["npcs"]] + [tuple(m["at"]) for m in sc["markers"].values()]
        for (x, y, z) in stands:
            assert y == ground(x, z) + 1, (sid, (x, y, z))
            assert (x, y, z) not in written and (x, y + 1, z) not in written, (sid, (x, y, z))
        for p in sc["props"]:
            x, y, z = p["on"]
            assert (x, y, z) in written or ground(x, z) in (y, y - 1), (sid, p["id"], "sits on nothing")
            assert abs(p["at"][0] - (x + 0.5)) < 1e-6 and abs(p["at"][2] - (z + 0.5)) < 1e-6
        a = sc["area"]
        for (x, y, z) in stands:
            assert a["from"][0] <= x <= a["to"][0] and a["from"][2] <= z <= a["to"][2] and a["from"][1] <= y <= a["to"][1]


def test_the_find_is_a_barrel_in_its_trigger_box_on_solid_ground_far_from_the_road(blocks, ground, road):
    r = next(x for x in read("rewards.json")["rewards"] if x["id"] == "r4_strayed_load")
    cx, cy, cz = r["container"]["at"]
    assert blocks["strayed_load"][(cx, cy, cz)][1] == "minecraft:barrel"
    assert ground(cx, cz) == cy - 1
    lo, hi = r["trigger"]["min"], r["trigger"]["max"]
    assert all(lo[i] <= (cx, cy, cz)[i] <= hi[i] for i in range(3))
    assert min(math.hypot(cx - x, cz - z) for x, z in road) > 80, "a find 'off the path' that is beside it"
    assert blocks["strayed_load"][(cx - 3, ground(cx - 3, cz - 3) + 8, cz - 3)][1] == "minecraft:red_banner"


# ---------------------------------------------------------------- the quest as a graph
def quest():
    return next(q for q in read("quests.json")["quests"] if q["id"] == QID)


def cond_fields(c):
    if isinstance(c, dict):
        out = set()
        if "field" in c:
            out.add(c["field"].split(".")[-1])
        for v in c.values():
            out |= cond_fields(v)
        return out
    if isinstance(c, list):
        return set().union(*[cond_fields(v) for v in c]) if c else set()
    return set()


GROUP = {
    "camp": {"camp_started", "clue_scar", "clue_lead", "camp_answered", "camp_reward_claimed", "camp_done", "hallam_cursor"},
    "hollow": {"seen_tracks", "seen_pool", "hollow_done"},
    "road": {"passed_5", "passed_0", "last_stone", "road_done"},
    "gate": {"gate_reward_claimed", "gate_done", "invited", "oriel_cursor"},
}
OWNER = {"camp_start": "camp", "clue_scar": "camp", "clue_lead": "camp", "camp_answer": "camp", "camp_grant": "camp", "camp_complete": "camp",
         "see_tracks": "hollow", "see_pool": "hollow", "follow": "hollow", "finish_road": "road", "gate_grant": "gate", "gate_complete": "gate"}
OWNER.update({"pass_%d" % n: "road" for n in range(6)})


def test_every_transition_is_invoked_and_every_completion_is_reachable():
    q = quest()
    ids = {t["id"] for t in q["transitions"]}
    used = set()
    for c in read("dialogue.json")["conversations"]:
        if c["quest_id"] != QID:
            continue
        for r in c["entry_rules"]:
            used |= {a["transition"] for a in r.get("actions", []) if a["kind"] == "quest_transition"}
        for n in c["nodes"]:
            used |= {a["transition"] for a in n.get("actions_after_acknowledge", []) if a["kind"] == "quest_transition"}
            for r in n.get("responses", []):
                used |= {a["transition"] for a in r.get("actions", []) if a["kind"] == "quest_transition"}
    for z in scenes()["route4_summit_road"]["zones"]:
        used |= set(z["transitions"])
    assert used == ids, "uninvoked: %s, invoked but undefined: %s" % (ids - used, used - ids)
    # fixpoint over the quest alone: apply any transition whose conditions hold, until nothing changes
    state = {f["field"]: f["initial"] for f in read("progression.json")["quest_fields"] if f["quest_id"] == QID}

    def holds(c):
        k = c["kind"]
        if k == "progression_equals":
            return state[c["field"].split(".")[-1]] == c["value"]
        if k == "not":
            return not holds(c["condition"])
        if k == "all":
            return all(holds(x) for x in c["conditions"])
        raise AssertionError(k)

    for _ in range(40):
        before = dict(state)
        for t in q["transitions"]:
            if all(holds(c) for c in t["conditions"]):
                for e in t["effects"]:
                    if e["kind"] == "set_progression":
                        state[e["field"].split(".")[-1]] = e["value"]
                    elif e["kind"] == "grant_reward_once":
                        state[e["claim_field"].split(".")[-1]] = True
        if state == before:
            break
    for done in ("camp_done", "hollow_done", "road_done", "gate_done", "invited"):
        assert state[done] is True, "%s is unreachable" % done


def test_the_quest_writes_only_flags_a_scene_sync_and_a_once_only_grant():
    for t in quest()["transitions"]:
        for e in t["effects"]:
            assert e["kind"] in ("set_progression", "sync_scene", "grant_reward_once"), (t["id"], e["kind"])
            if e["kind"] == "grant_reward_once":
                claim = e["claim_field"]
                assert any(c.get("field") == claim and c.get("value") is False for c in t["conditions"]), "%s: a grant not guarded by its claim" % t["id"]
                assert any(x["kind"] == "set_progression" for x in t["effects"]) or claim.endswith("_claimed")
                assert "{player_uuid}" in e["idempotency_key"] and e["target"] == "triggering_player"
    claims = [e["claim_field"] for t in quest()["transitions"] for e in t["effects"] if e["kind"] == "grant_reward_once"]
    assert len(claims) == len(set(claims)) == 2


def test_no_event_reads_another_events_flags_so_walking_in_any_order_unlocks_the_same_things():
    for t in quest()["transitions"]:
        fields = cond_fields(t["conditions"])
        own = GROUP[OWNER[t["id"]]] | {"prop_cursor"}
        assert fields <= own, "%s reads %s outside its own event" % (t["id"], fields - own)
    gate = next(t for t in quest()["transitions"] if t["id"] == "gate_grant")
    assert [(c["field"].split(".")[-1], c["value"]) for c in gate["conditions"]] == [("gate_reward_claimed", False)], \
        "the finale's reward must not depend on the earlier events"
    # the only place the earlier events are read is the finale's greeting
    for c in read("dialogue.json")["conversations"]:
        if c["quest_id"] != QID or c["id"] == "dlg_route4_thaw_gate":
            continue
        own = {"dlg_route4_headwall_camp": GROUP["camp"], "dlg_route4_scar": GROUP["camp"], "dlg_route4_lead": GROUP["camp"],
               "dlg_route4_hollow_tracks": GROUP["hollow"], "dlg_route4_hollow_pool": GROUP["hollow"], "dlg_route4_hollow_petal": GROUP["hollow"],
               "dlg_route4_stone_zero": GROUP["road"], "dlg_route4_biscuit": GROUP["gate"], "dlg_route4_drift": GROUP["gate"]}[c["id"]] | {"prop_cursor"}
        for r in c["entry_rules"]:
            assert cond_fields(r["when"]) <= own, (c["id"], cond_fields(r["when"]) - own)


def reachable(conv, start_nodes):
    nodes = {n["id"]: n for n in conv["nodes"]}
    seen, todo = set(), list(start_nodes)
    while todo:
        i = todo.pop()
        if i in seen or i == "$cursor":
            continue
        assert i in nodes, "%s: node %s does not exist" % (conv["id"], i)
        seen.add(i)
        n = nodes[i]
        if n.get("next"):
            todo.append(n["next"])
        todo += [r["next"] for r in n.get("responses", []) if r.get("next")]
    return seen


def test_the_two_people_can_be_talked_all_the_way_to_their_rewards():
    convs = {c["id"]: c for c in read("dialogue.json")["conversations"] if c["quest_id"] == QID}
    for cid, grant in (("dlg_route4_headwall_camp", "camp_grant"), ("dlg_route4_thaw_gate", "gate_grant")):
        c = convs[cid]
        seen = reachable(c, [r["node"] for r in c["entry_rules"]])
        assert seen == {n["id"] for n in c["nodes"]}, "%s: unreachable nodes %s" % (cid, {n["id"] for n in c["nodes"]} - seen)
        fires = [n["id"] for n in c["nodes"] if any(a.get("transition") == grant for a in n.get("actions_after_acknowledge", []))]
        # from the first state a player can be in with the means to finish (the riddle asked / the first meeting)
        assert fires and fires[0] in reachable(c, ["m_ask" if "camp" in cid else "g1"])
    # the packer's riddle has a right answer and two wrong ones that come back to the question
    ask = next(n for n in convs["dlg_route4_headwall_camp"]["nodes"] if n["id"] == "m_ask")
    assert len(ask["responses"]) == 3 and sum(1 for r in ask["responses"] if r.get("actions")) == 1


def test_every_conversation_compiles():
    import compile_dialogue as CD
    quests = {q["id"]: q for q in read("quests.json")["quests"]}
    fields = {f["id"]: f for f in read("progression.json")["quest_fields"]}
    n = 0
    for c in read("dialogue.json")["conversations"]:
        if c["quest_id"] == QID:
            CD.compile_conversation(c, quests, fields)
            n += 1
    assert n == 10


def test_the_scenes_pass_the_scene_runtimes_own_static_checks():
    import scenes_pack as SP
    doc = SP.load()
    files, scene_objs = SP.build()[:2]
    assert {"route4_headwall_camp", "route4_steam_hollow", "route4_summit_road", "route4_thaw_gate"} <= {s.id for s in scene_objs}
    assert any(k.endswith("route4_summit_road/beat") or "route4_summit_road" in k for k in files)


# ---------------------------------------------------------------- the economy
FORBIDDEN = ("rare_candy", "exp_candy", "_candy", "lucky_egg", "technical_machine", "tm_", "_stone", "ability_capsule", "ability_patch", "bottle_cap", "master_ball")


def test_rewards_are_small_items_no_cash_nothing_the_bank_buys_and_no_progression_item():
    bank = {b["item"] for b in read("bank.json")["buys"]}
    recs = [r for r in read("rewards.json")["rewards"] if r["id"].startswith("r4_")]
    assert len(recs) == 3
    total = {}
    for r in recs:
        for c in r["contents"]:
            assert c["item"] not in bank, c["item"]
            assert not any(f in c["item"] for f in FORBIDDEN), c["item"]
            assert c["count"] <= 5
            total[c["item"]] = total.get(c["item"], 0) + c["count"]
    assert sum(total.values()) <= 20, total
    assert "cobblemon:never_melt_ice" in total and total["cobblemon:never_melt_ice"] == 1
    # no cash anywhere in the quest: its effect kinds were checked above; the records say no money either
    assert not any("dollar" in json.dumps(r).lower() or "money" in json.dumps(r["contents"]).lower() for r in recs)
    import rewards_pack
    assert rewards_pack.problems({"rewards": recs}) == []
    # the quest's rewards and the records agree
    qr = {x["id"]: x["contents"] for x in quest()["rewards"]}
    got = {r["id"]: r["contents"] for r in recs if r["kind"] == "npc_grant"}
    assert sorted(map(json.dumps, qr.values())) == sorted(map(json.dumps, got.values()))
    # the held item is one the wild pools already carry
    assert "cobblemon:never_melt_ice" in (ROOT / "data" / "spawns.json").read_text(encoding="utf-8")


def test_the_gogoat_is_inside_the_bands_cap_and_never_catchable():
    r4 = next(r for r in read("routes.json")["routes"] if r["id"] == "route_04_surge_to_erika")
    actors = [a for sc in scenes().values() for a in sc["actors"]]
    assert [a["species"] for a in actors] == ["gogoat"]
    assert actors[0]["level"] <= r4["party_level_band"]["maximum"]


# ---------------------------------------------------------------- the files
@pytest.mark.parametrize("key", list(R.TARGETS))
def test_records_splice_in_idempotently_without_touching_any_other_line(key, tmp_path, run):
    fname, arr, anchor, owned = R.TARGETS[key]
    sites = R.build(G.Ground(None), R.Road4(), SPEC)
    recs = R.build_records(SPEC, sites)[key]
    src = ROOT / "data" / fname
    work = tmp_path / fname
    shutil.copyfile(src, work)
    assert R.splice(work, arr, anchor, owned, recs, True) is True      # the repository already holds exactly these
    once = work.read_text(encoding="utf-8")
    assert once == src.read_text(encoding="utf-8")
    # remove our block by hand and splice it back: the text must come back byte for byte
    doc = json.loads(once)
    others = [o for o in doc[arr] if not owned(o)]
    assert len(others) == len(doc[arr]) - len(recs) and len(recs) > 0
    assert R.splice(work, arr, anchor, owned, recs[:-1] + [copy.deepcopy(recs[-1])], True) is True
    assert R.splice(work, arr, anchor, owned, recs, True) is True
    assert work.read_text(encoding="utf-8") == once
    # a changed record is reported and fixed in place, still touching nothing else
    changed = copy.deepcopy(recs)
    changed[0]["source"] = "elsewhere"
    assert R.splice(work, arr, anchor, owned, changed, True) is False
    assert R.splice(work, arr, anchor, owned, recs, True) is False
    assert work.read_text(encoding="utf-8") == once


def test_world_probes_name_blocks_the_pack_writes_and_props_the_scenes_place(blocks):
    probes = read("world_probes.json")["places"]["route4_events"]
    assert len(probes) >= 20
    props = {(sid, p["id"]) for sid, sc in scenes().items() for p in sc["props"]}
    seen_props = set()
    for pr in probes:
        if "block" in pr:
            x, y, z, want = pr["block"]
            site = pr["what"].split(":")[0]
            assert blocks[site][(x, y, z)][1] == R.base(want), pr["what"]
        else:
            m = re.search(r"cobblers_prop_(\w+?)_(\w+)\]", pr["entity"])
            seen_props.add(next((sid, pid) for sid, pid in props if pr["entity"].endswith("cobblers_prop_%s_%s]" % (sid, pid))))
            assert pr["count"] == 1
    assert seen_props == props


# ---------------------------------------------------------------- the checkers bite, and Routes 1-3 are left alone
def test_the_road_check_and_the_spawn_check_fire_on_a_bad_build(run):
    g = G.Ground(None)
    road = R.Road4()
    spec = copy.deepcopy(SPEC)
    sites = R.build(g, road, spec)
    assert R.problems(sites, g, road, spec) == []
    px, pz = road.paths[R.ROUTE][500]
    sites[0].on_ground(px, pz, "minecraft:cobblestone")
    sites[0].set(px + 40, g(px + 40, pz) + 1, pz, "minecraft:flowering_azalea")
    probs = R.problems(sites, g, road, spec)
    assert any("within 1 of the walked line" in p for p in probs)
    assert any("flowering_azalea" in p for p in probs)


def test_the_tunnel_mouth_check_fires():
    g = G.Ground(None)
    road = R.Road4()
    sites = R.build(g, road, SPEC)
    mx, mz = SPEC["sites"]["thaw_gate"]["mouth"]
    sites[4].set(mx + 1, g(mx, mz) + 1, mz, "minecraft:cobblestone")
    assert any("tunnel mouth" in p for p in R.problems(sites, g, road, SPEC))


def test_routes_1_to_3_are_imported_never_assigned_to():
    import route_events as RE
    assert sorted(RE.ROUTES) == [1, 2, 3] and len(RE.SITES) == 11
    src = (ROOT / "tools" / "route4_events.py").read_text(encoding="utf-8")
    assert not re.findall(r"\bRE\.[A-Za-z_]+\s*=[^=]", src), "route4_events.py assigns to something in route_events"
    assert "monkeypatch" not in src and "setattr(RE" not in src
    # and the 'protected' it uses is its own, so route_events.protected keeps reading derived/ for Routes 1-3
    assert R.protected is not RE.protected


# ---------------------------------------------------------------- the re-apply wiring
def test_the_pack_is_installed_prepared_and_run_by_a_step_after_the_route_1_to_3_sites(run):
    """steps() needs every other pack built, which a worktree has not got, so this reads the registration itself:
    the pack is a SERVER_PACKS member (not EXCLUDED), the prepare job runs after route_events and before the scene
    runtime, and R12R4 sits between R12 and R17 and runs exactly the functions the pack indexes."""
    import reapply
    assert "cobblers_route4_events" in reapply.SERVER_PACKS and "cobblers_route4_events" not in reapply.EXCLUDED
    src = (ROOT / "tools" / "reapply.py").read_text(encoding="utf-8")
    a = src.index('add("route_events", "route_events.py", *src)')
    b = src.index('add("route4_events", "route4_events.py", *src)')
    c = src.index('add("scenes_pack", "scenes_pack.py")')
    assert a < b < c
    r12 = src.index('out.append(("R12", "Routes 1-3 event sites')
    r12r4 = src.index('out.append(("R12R4"')
    r17 = src.index('out.append(("R17", "scene props')
    assert r12 < r12r4 < r17
    assert reapply.indexed("cobblers_route4_events", "route4_events") == ["00_clear"] + SITES
    # the scenes' props and NPCs reach R17 through data/scenes.json, which reapply reads, not through a list of ours
    names = {p[0] for p in reapply.scene_props()}
    assert {"route4_headwall_camp", "route4_steam_hollow", "route4_summit_road", "route4_thaw_gate"} <= names
    npcs = {n[0] for n in reapply.scene_npcs()}
    assert {"dlg_route4_headwall_camp", "dlg_route4_thaw_gate"} <= npcs
