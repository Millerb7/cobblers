"""The settlement NPCs' seats: data/npc_seats.json, tools/npc_seats.py placements(), and reapply.py step R17N.

Written by the test author, not by the session that seated the NPCs.

Independence. Every expectation here comes from data the seating did not use as its answer, or from a source the
seating claims to agree with and is checked against directly:

  - which NPC classes exist: tools/compile_dialogue.py build_all over data/dialogue.json (not npc_seats' own helper)
  - who else places NPCs: data/scenes.json (reapply.scene_npcs), data/rewards.json (reapply.npcs),
    data/ferries.json (ferries.npc_placements)
  - the roads: data/route_paths.json, distance to the walked SEGMENTS computed here (not npc_seats.MIN_ROUTE's
    point distance); 3 blocks is the brief's stated standoff, not a number tuned to the data
  - plaza and lot heights: data/placements.json plaza rect/y and levelled anchor rects, data/gym_buildings/*.json site
  - terrain: tools/ground.py (the canonical heightmap, rounded), only when COBBLERS_SOURCE_ROOT makes it readable
  - footprints: data/towns.json, or the settlement plan's own footprint where the plan declares one
  - what each quest actor was recorded at: data/quests.json main_worldshift_reveal actors
  - the template floor: the lab template's own NBT cells (kits/, local)

Every position, y and yaw under test is read through npc_seats.placements() (or R17N, which calls it), so a fault in
the GENERATOR is caught, not just a fault in the record. The test_mutated_generator_* tests prove that: each replaces
placements() with a broken version and asserts the property check reports it.

steps() needs build/datapacks index files and derived/ambient/plan.json; this file stubs reapply.indexed and
ambient.placement_steps (they feed R1/R2/... and R16C, not R17N) and needs the heightmap for the rest of steps().
Without COBBLERS_SOURCE_ROOT those tests SKIP; a skip is not a pass.

Not covered (needs a running server, or a tool this agent was refused): that spawnnpcat puts each NPC there and the
tp turns it (tools/npc_seats.py verify); that the floor under each seat is solid and the two blocks above are air in
a built world; that Oak's lab is seated at origin y117 (that is place_town.build's decision and was not re-run here);
that a trader, Pokemon or template entity does not later stand on a seat; and the reapply npc action's own RCON
sequence (it was not exercised with a fake RCON).
"""
import json
import math
import os
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import compile_dialogue as CD  # noqa: E402
import ferries  # noqa: E402
import npc_seats  # noqa: E402
import reapply  # noqa: E402


def _j(rel):
    return json.loads((ROOT / rel).read_text(encoding="utf-8"))


DOC = _j("data/npc_seats.json")
RECORD = {s["id"]: s for s in DOC["seats"]}
PLACEMENTS = _j("data/placements.json")
SETTLEMENTS = PLACEMENTS["settlements"]
TOWNS = {t["id"]: t for t in _j("data/towns.json")["towns"]}
ROUTES = _j("data/route_paths.json")["paths"]
QUESTS = {q["id"]: q for q in _j("data/quests.json")["quests"]}
STANDOFF = 3.0      # the brief: an immovable NPC closer than this to the walked line stands in the road


def _seats(gen=None):
    """{npc id: (conversation, (x, y, z), class, yaw-or-None)} from the generator under test."""
    out = {}
    for p in (gen or npc_seats.placements)():
        cls = p[2]
        assert cls.startswith("cobblers:"), cls
        out[cls.split(":", 1)[1]] = (p[0], tuple(p[1]), cls, p[3] if len(p) > 3 else None)
    return out


def _in(rect, x, z):
    return rect[0] <= x <= rect[2] and rect[1] <= z <= rect[3]


def _seg_dist(px, pz, a, b):
    ax, az = a
    bx, bz = b
    dx, dz = bx - ax, bz - az
    L = dx * dx + dz * dz
    t = 0.0 if L == 0 else max(0.0, min(1.0, ((px - ax) * dx + (pz - az) * dz) / L))
    return math.hypot(px - (ax + t * dx), pz - (az + t * dz))


def _route_dist(x, z):
    best = math.inf
    for pts in ROUTES.values():
        if len(pts) == 1:
            best = min(best, math.hypot(x - pts[0][0], z - pts[0][1]))
        for a, b in zip(pts, pts[1:]):
            best = min(best, _seg_dist(x, z, a, b))
    return best


def _levelled_rects(settlement):
    """[(where, rect, level)] for every rect the settlement's plan levels: anchors, house lots with a level."""
    plan = (SETTLEMENTS.get(settlement) or {}).get("plan") or {}
    out = []
    for key in ("anchors", "house_lots", "lots"):
        for a in plan.get(key) or []:
            if isinstance(a, dict) and a.get("rect") and a.get("level") is not None:
                out.append(("%s.%s" % (key, a.get("id")), a["rect"], a["level"]))
    return out


def _gym_sites():
    return {p.stem: _j("data/gym_buildings/%s" % p.name)["site"] for p in sorted((ROOT / "data" / "gym_buildings").glob("*.json"))}


# ------------------------------------------------------------------------------------------------- the checks
def coverage_problems(classes, refused_npcs, gen=None):
    seats = _seats(gen)
    sources = {}
    for name, rows in (("data/scenes.json", reapply.scene_npcs()), ("data/rewards.json", reapply.npcs()),
                       ("data/ferries.json", ferries.npc_placements(ferries.load()))):
        for r in rows:
            sources.setdefault(r[2].split(":", 1)[1], []).append(name)
    for nid in seats:
        sources.setdefault(nid, []).append("data/npc_seats.json")
    not_seated = {n["id"]: n.get("why") for n in DOC.get("not_seated") or []}
    probs = []
    for nid in sorted(classes):
        got = sources.get(nid, [])
        if len(got) != 1 and not (not got and nid in not_seated):
            probs.append("%s: placed by %s" % (nid, got or "nothing"))
        if got and nid in not_seated:
            probs.append("%s: placed by %s and also listed not_seated" % (nid, got))
    for nid, why in not_seated.items():
        if nid not in refused_npcs:
            probs.append("%s: not_seated, but compile_dialogue does not refuse its conversation" % nid)
        if not why:
            probs.append("%s: not_seated with no why" % nid)
    for nid in refused_npcs:
        if nid not in not_seated and nid not in sources:
            probs.append("%s: its conversation is refused and it is not listed not_seated" % nid)
    for nid in seats:
        if nid not in classes:
            probs.append("%s: seated, but compile_dialogue emits no class for it" % nid)
    return probs


def route_problems(gen=None):
    return ["%s: (%d, %d) is %.2f blocks from a walked route segment" % (nid, p[1][0], p[1][2], d)
            for nid, p in _seats(gen).items() for d in [_route_dist(p[1][0], p[1][2])] if d < STANDOFF]


def plaza_and_lot_problems(gen=None):
    probs = []
    sites = _gym_sites()
    for nid, (_, (x, y, z), _, _) in _seats(gen).items():
        rec = RECORD[nid]
        kind, st = rec["ground"]["kind"], rec.get("settlement")
        plan = (SETTLEMENTS.get(st) or {}).get("plan") or {}
        if kind == "plaza":
            pz = plan.get("plaza") or {}
            if not pz.get("rect") or not _in(pz["rect"], x, z):
                probs.append("%s: plaza seat (%d, %d) is not on %s's plaza %s" % (nid, x, z, st, pz.get("rect")))
            elif y != pz["y"] + 1:
                probs.append("%s: plaza seat at y%d, %s's plaza is paved at y%d" % (nid, y, st, pz["y"]))
        elif kind == "lot_level":
            hits = [(w, lv) for w, r, lv in _levelled_rects(st) if _in(r, x, z)]
            gym = [(g, s) for g, s in sites.items() if _in(s["lot_rect"], x, z)]
            if not hits and not gym:
                probs.append("%s: lot_level seat (%d, %d) is on no levelled rect of %s" % (nid, x, z, st))
            for w, lv in hits:
                if y != lv + 1:
                    probs.append("%s: on %s levelled to y%d, stands at y%d" % (nid, w, lv, y))
            for g, s in gym:
                if y != s["lot_level"] + 1:
                    probs.append("%s: on %s's lot (lot_level %d), stands at y%d" % (nid, g, s["lot_level"], y))
                if _in(s["footprint"], x, z):
                    probs.append("%s: inside %s's building footprint %s" % (nid, g, s["footprint"]))
    return probs


def heightmap_problems(ground, gen=None):
    probs = []
    for nid, (_, (x, y, z), _, _) in _seats(gen).items():
        if RECORD[nid]["ground"]["kind"] != "heightmap":
            continue
        if y != ground(x, z) + 1:
            probs.append("%s: heightmap ground at (%d, %d) is y%d, the seat stands at y%d" % (nid, x, z, ground(x, z), y))
        # terrain is not the ground where any plan paves or levels: the plaza and every levelled rect, in ANY settlement
        for sid, s in SETTLEMENTS.items():
            pz = ((s.get("plan") or {}).get("plaza") or {})
            if pz.get("rect") and _in(pz["rect"], x, z):
                probs.append("%s: on %s's plaza, which is paved, not heightmap ground" % (nid, sid))
            for w, r, lv in _levelled_rects(sid):
                if _in(r, x, z):
                    probs.append("%s: on %s %s, levelled to y%d" % (nid, sid, w, lv))
    return probs


def yaw_problems(gen=None):
    """A seat whose `faces` names exactly one (x, z) must face it: Minecraft yaw = atan2(-dx, dz), within the half
    degree an integer yaw rounds away. Seats that face a compass word or a lane are not bound here."""
    probs = []
    for nid, (_, (x, _, z), _, yaw) in _seats(gen).items():
        if not isinstance(yaw, (int, float)) or not -180 <= yaw <= 180:
            probs.append("%s: yaw %r is not a Minecraft yaw" % (nid, yaw))
            continue
        pts = re.findall(r"\((-?\d+), (-?\d+)\)", RECORD[nid]["faces"])
        if len(pts) != 1:
            continue
        tx, tz = map(int, pts[0])
        want = math.degrees(math.atan2(-(tx - x), tz - z))
        off = abs((yaw - want + 180.0) % 360.0 - 180.0)
        if off > 0.5:
            probs.append("%s: yaw %s, but %r is at bearing %.1f (%.1f degrees off)" % (nid, yaw, RECORD[nid]["faces"], want, off))
    return probs


# ------------------------------------------------------------------------------------------------- fixtures
@pytest.fixture(scope="module")
def compiled():
    files, _done, refused = CD.build_all(ROOT / "data")
    classes = {Path(k).stem for k in files if re.fullmatch(r"data/cobblers/npcs/[^/]+\.json", k.replace("\\", "/"))}
    convs = {c["id"]: c for c in _j("data/dialogue.json")["conversations"]}
    refused_npcs = {convs[c]["npc_id"] for c in refused if convs.get(c, {}).get("npc_id")}
    return classes, refused_npcs


@pytest.fixture(scope="module")
def ground():
    if not os.environ.get("COBBLERS_SOURCE_ROOT"):
        pytest.skip("COBBLERS_SOURCE_ROOT unset: the canonical heightmap is not readable here")
    import ground as G
    try:
        return G.load()
    except Exception as e:  # terrain.TerrainUnavailable, a missing or mismatched file
        pytest.skip("heightmap unreadable: %s" % e)


def _steps(monkeypatch_ctx):
    import ambient
    monkeypatch_ctx.setattr(reapply, "indexed", lambda *a, **k: [])
    monkeypatch_ctx.setattr(ambient, "placement_steps", lambda *a, **k: [])
    return reapply.steps()


@pytest.fixture(scope="module")
def steps(ground):
    with pytest.MonkeyPatch.context() as mp:
        return _steps(mp)


# ------------------------------------------------------------------------------------------------- 1. coverage
def test_every_compiled_dialogue_npc_is_placed_by_exactly_one_source_or_listed_not_seated(compiled):
    # Removing this lets a compiled NPC class exist with nothing placing it (20 were placed nowhere before R17N).
    classes, refused_npcs = compiled
    assert classes, "compile_dialogue emitted no NPC classes: the fixture exercises nothing"
    assert coverage_problems(classes, refused_npcs) == []


def test_mutated_generator_dropping_a_seat_is_caught_by_coverage(compiled):
    # Removing this leaves the coverage check unproven against a placements() that silently loses a seat.
    classes, refused_npcs = compiled
    real = npc_seats.placements
    probs = coverage_problems(classes, refused_npcs, gen=lambda: real()[:-1])
    assert any(npc_seats.load()["seats"][-1]["id"] in p for p in probs), probs


# ------------------------------------------------------------------------------------------------- 2. roads
def test_no_seat_stands_within_three_blocks_of_a_walked_route_segment():
    # Removing this lets an immovable NPC be seated in the road (eight recorded actor columns were on it).
    assert route_problems() == []


def test_every_superseded_marker_said_to_be_on_the_route_really_is():
    # Removing this lets a seat claim it moved off the road when the recorded column was never on it.
    moved = [(nid, r["supersedes_stand_marker"]) for nid, r in RECORD.items() if r.get("supersedes_stand_marker")]
    assert moved
    bad = [(nid, m["recorded_at"]) for nid, m in moved
           if "route" in m["why"] and _route_dist(m["recorded_at"][0], m["recorded_at"][2]) >= STANDOFF]
    assert bad == []


def test_mutated_generator_seating_at_the_recorded_markers_is_caught_on_the_road():
    # Removing this leaves the road check unproven: a placements() that used the quests' old columns must fail it.
    real = npc_seats.placements

    def at_recorded():
        out = []
        for p in real():
            m = RECORD[p[2].split(":", 1)[1]].get("supersedes_stand_marker")
            out.append((p[0], tuple(m["recorded_at"]) if m else p[1], p[2], p[3]))
        return out
    probs = route_problems(gen=at_recorded)
    on_route = [nid for nid, r in RECORD.items() if "route" in (r.get("supersedes_stand_marker") or {}).get("why", "")]
    assert on_route and all(any(n in p for p in probs) for n in on_route), probs


# ------------------------------------------------------------------------------------------------- 3. plazas and lots
def test_plaza_and_lot_seats_stand_one_above_the_plans_paved_or_levelled_surface():
    # Removing this lets a plaza or lot NPC stand a block in the paving or float above it.
    kinds = {r["ground"]["kind"] for r in RECORD.values()}
    assert {"plaza", "lot_level"} <= kinds, "no plaza or lot seats: the check exercises nothing"
    assert plaza_and_lot_problems() == []


def test_mutated_generator_raising_every_seat_one_block_is_caught_on_plazas_and_lots():
    # Removing this leaves the plaza/lot y check unproven against a placements() off by one.
    real = npc_seats.placements
    probs = plaza_and_lot_problems(gen=lambda: [(c, (x, y + 1, z), k, w) for c, (x, y, z), k, w in real()])
    n = sum(1 for r in RECORD.values() if r["ground"]["kind"] in ("plaza", "lot_level"))
    assert len({p.split(":")[0] for p in probs}) == n, probs


# ------------------------------------------------------------------------------------------------- 4. heightmap
def test_heightmap_seats_stand_one_above_the_rounded_canonical_heightmap(ground):
    # Removing this lets a terrain seat be buried or float, or take terrain where a plan paves or levels.
    assert any(r["ground"]["kind"] == "heightmap" for r in RECORD.values())
    assert heightmap_problems(ground) == []


def test_mutated_generator_lowering_every_seat_one_block_is_caught_on_the_heightmap(ground):
    # Removing this leaves the heightmap check unproven against a placements() that floors instead of rounds.
    real = npc_seats.placements
    probs = heightmap_problems(ground, gen=lambda: [(c, (x, y - 1, z), k, w) for c, (x, y, z), k, w in real()])
    n = sum(1 for r in RECORD.values() if r["ground"]["kind"] == "heightmap")
    assert len({p.split(":")[0] for p in probs}) == n, probs


def test_template_floor_seat_stands_on_the_templates_floor_cell_with_headroom():
    # Removing this lets a seat inside a template stand in a wall or a wall's column (the lab's own NBT decides).
    import nbt
    by_id = {p["id"]: p for p in PLACEMENTS["placements"]}
    tf = [(nid, s) for nid, s in _seats().items() if RECORD[nid]["ground"]["kind"] == "template_floor"]
    assert tf
    for nid, (_, (x, y, z), _, _) in tf:
        hosts = []
        for p in by_id.values():
            if p.get("settlement") != RECORD[nid].get("settlement") or p.get("rotation", "none") != "none" \
                    or p.get("anchor_mode") != "corner" or not p.get("file"):
                continue
            f = ROOT / p["file"]
            if not f.is_file():
                continue
            _, d = nbt.load(f)
            sx, _, sz = d["size"]
            px, pz = p["position"]["x"], p["position"]["z"]
            if px <= x < px + sx and pz <= z < pz + sz:
                hosts.append((p["id"], d, x - px, z - pz))
        if not hosts:
            pytest.skip("%s: no local template file covers (%d, %d) (kits/ not hydrated?)" % (nid, x, z))
        assert len(hosts) == 1, (nid, [h[0] for h in hosts])
        _, d, dx, dz = hosts[0]
        cells = {tuple(b["pos"]): d["palette"][b["state"]]["Name"] for b in d["blocks"]}
        air = ("minecraft:air", "minecraft:cave_air", None)
        assert cells.get((dx, 0, dz)) not in air, (nid, cells.get((dx, 0, dz)))
        assert cells.get((dx, 1, dz)) in air and cells.get((dx, 2, dz)) in air, (nid, cells.get((dx, 1, dz)), cells.get((dx, 2, dz)))


# ------------------------------------------------------------------------------------------------- 5. R17N
def test_r17n_places_exactly_the_records_seats_in_order_each_with_its_yaw(steps):
    # Removing this lets R17N drift from data/npc_seats.json, or lose the yaw the npc action turns each NPC to.
    acts = [v for k, v in [s for s in steps if s[0] == "R17N"][0][2]]
    want = [(s["conversation"], tuple(s["at"]), "cobblers:%s" % s["id"], s["yaw"]) for s in DOC["seats"]]
    assert [(a[0], tuple(a[1]), a[2], a[3] if len(a) > 3 else None) for a in acts] == want
    assert all(k == "npc" for k, _ in [s for s in steps if s[0] == "R17N"][0][2])


def test_r17n_runs_after_every_step_that_builds_a_seated_settlement(steps):
    # Removing this lets an NPC be spawned before (and then buried or erased by) the town, gym or plaza under it.
    ids = [s[0] for s in steps]
    assert "R17N" in ids
    tokens = set()
    for r in RECORD.values():
        st = r.get("settlement")
        if st:
            tokens.add(st)
            m = re.fullmatch(r"(gym\d+)_town", st)
            if m:
                tokens.add(m.group(1) + "_")   # gym_buildings/gym1, structures/place_gym1_..., gym_demolish/gym1
                tokens.add(m.group(1))
    after = {"R14"}   # town traders: entities placed after, and their dedupe kills only their own tag
    builders = {"R7", "R8", "R8B", "R16G", "R17F"}
    for sid, title, acts in steps:
        fns = [v for k, v in acts if k == "fn"]
        names = [f.split(":", 1)[-1] for f in fns]
        if sid not in after and (
                any(re.search(r"(^|[/_])%s($|[/_])" % re.escape(t.rstrip("_")), f) for t in tokens for f in names)
                or any(t.rstrip("_").replace("_", " ") in title.lower() for t in tokens if "_" in t.rstrip("_"))):
            builders.add(sid)
    late = sorted(b for b in builders if b in ids and ids.index(b) > ids.index("R17N"))
    assert late == [], "steps that build a seated place run after R17N: %s" % late
    assert ids.index("R17N") < ids.index("V")


def test_mutated_generator_dropping_yaw_is_caught_in_r17n(ground):
    # Removing this leaves the R17N yaw check unproven against a placements() that returns 3-tuples.
    real = npc_seats.placements
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(npc_seats, "placements", lambda doc=None: [p[:3] for p in real(doc)])
        st = _steps(mp)
    acts = [v for _, v in [s for s in st if s[0] == "R17N"][0][2]]
    assert acts and all(len(a) == 3 for a in acts)
    with pytest.raises(AssertionError):
        test_r17n_places_exactly_the_records_seats_in_order_each_with_its_yaw(st)


# ------------------------------------------------------------------------------------------------- facing
XFAIL_YAW = set()  # npc_main_league_steward fixed 2026-10-02: yaw -114, toward its named (3656, 2486)


@pytest.mark.parametrize("nid", sorted(RECORD))
def test_a_seat_faces_the_one_point_its_record_names(nid, request):
    # Removing this lets a seat's yaw disagree with what it says it looks at (the probe allows only 10 degrees).
    if nid in XFAIL_YAW:
        request.applymarker(pytest.mark.xfail(strict=True, reason=(
            "data/npc_seats.json npc_main_league_steward: yaw -90 (due east), but faces names (3656, 2486), at "
            "bearing -114.0 from (3647, 2490): 24 degrees apart, beyond the probe's 10")))
    assert [p for p in yaw_problems() if p.startswith(nid + ":")] == []


def test_mutated_generator_reversing_yaw_is_caught_on_facing():
    # Removing this leaves the facing check unproven against a placements() that turns every NPC around.
    real = npc_seats.placements
    flip = lambda: [(c, a, k, ((w + 360) % 360) - 180) for c, a, k, w in real()]  # noqa: E731
    probs = yaw_problems(gen=flip)
    named = [n for n, r in RECORD.items() if len(re.findall(r"\((-?\d+), (-?\d+)\)", r["faces"])) == 1]
    assert named and all(any(p.startswith(n + ":") for p in probs) for n in named), probs


# ------------------------------------------------------------------------------------------------- 6. footprints
XFAIL_FOOTPRINT = set()  # npc_stone_tip_viltri_light_keeper fixed 2026-10-02: moved to x555


@pytest.mark.parametrize("nid", sorted(n for n, r in RECORD.items() if r.get("settlement")))
def test_a_seat_lies_inside_its_own_settlements_footprint(nid, request):
    # Removing this lets an NPC be filed under one settlement and stand outside it.
    # The plan's own footprint wins where it declares one: placements.json says of displaced_city that
    # towns.json's footprint "is the surface entrance, where only the gate stands".
    if nid in XFAIL_FOOTPRINT:
        request.applymarker(pytest.mark.xfail(strict=True, reason=(
            "npc_stone_tip_viltri_light_keeper at (556, 4514) is outside data/towns.json viltri_light footprint "
            "x544-555: the plaza rect [554, 4512, 559, 4524] it stands on runs four blocks past the footprint, and "
            "the seat took a column on the overhang")))
    st = RECORD[nid]["settlement"]
    _, (x, _, z), _, _ = _seats()[nid]
    pf = ((SETTLEMENTS.get(st) or {}).get("plan") or {}).get("footprint")
    if pf and pf.get("rect"):
        assert _in(pf["rect"], x, z), (nid, st, "plan.footprint", pf["rect"], (x, z))
    else:
        f = TOWNS[st]["footprint"]
        assert _in((f["min_x"], f["min_z"], f["max_x"], f["max_z"]), x, z), (nid, st, "towns.json", f, (x, z))


# ------------------------------------------------------------------------------------------------- 7. the steward
def test_the_league_steward_is_not_seated_on_the_stale_quest_coordinate_and_the_record_is_kept():
    # Removing this lets the steward be seated on the retired cradle coordinate, or the stale record be erased.
    actor = [a for a in QUESTS["main_worldshift_reveal"]["actors"] if a["npc_id"] == "npc_main_league_steward"]
    assert len(actor) == 1 and actor[0]["recorded_position_xz"] == [3297, 2603]
    _, (x, _, z), _, _ = _seats()["npc_main_league_steward"]
    assert (x, z) != (3297, 2603)
    assert _in(SETTLEMENTS["league"]["plan"]["footprint"]["rect"], x, z)


def test_a_quest_actors_recorded_stand_marker_is_kept_or_named_as_superseded():
    # Removing this lets a seat quietly move an actor away from the quest's verified-pending marker without saying so.
    probs = []
    seats = _seats()
    for a in QUESTS["main_worldshift_reveal"]["actors"]:
        m = a.get("stand_marker")
        if not m or a["npc_id"] not in seats:
            continue
        at = list(seats[a["npc_id"]][1])
        sup = (RECORD[a["npc_id"]].get("supersedes_stand_marker") or {}).get("recorded_at")
        if at != m["at"] and sup != m["at"]:
            probs.append("%s: seat %s, marker %s, superseded %s" % (a["npc_id"], at, m["at"], sup))
    assert probs == []


# ------------------------------------------------------------------------------------------------- spacing
def _cube_dist(p, q):
    """Distance from block corner p (reapply's selector centre x=%d,y=%d,z=%d) to the unit cell an entity at q fills."""
    return math.sqrt(sum(max(qi - pi, 0, pi - (qi + 1)) ** 2 for pi, qi in zip(p, q)))


def test_no_two_npcs_reapply_places_are_within_its_already_there_radius():
    # Removing this lets R17N's "an NPC is already there" probe (distance ..2) mistake another NPC for this one,
    # skip the spawn, and turn the wrong NPC to the seat's yaw.
    allp = ([("scene", n[2], n[1]) for n in reapply.scene_npcs()] + [("reward", n[2], n[1]) for n in reapply.npcs()]
            + [("ferry", n[2], n[1]) for n in ferries.npc_placements(ferries.load())]
            + [("seat", n[2], n[1]) for n in npc_seats.placements()])
    bad = [(a[1], b[1]) for i, a in enumerate(allp) for b in allp[i + 1:]
           if "seat" in (a[0], b[0]) and min(_cube_dist(a[2], b[2]), _cube_dist(b[2], a[2])) <= 2.0]
    assert bad == []
