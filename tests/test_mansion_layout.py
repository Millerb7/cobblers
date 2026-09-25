"""The Route 1 mansion without its grand stair, against the Gastly escort's scene and the Channelers' sight.

Written by the test author, not by the session that rebuilt the house, moved the markers or set the sight distances.

What is asserted, on the replayed house (data/placements.json route1_mansion_house, tools/build_audit.replay) and
the real scene and guardian data (data/scenes.json route1_gastly_family, data/mansion_guardians.json):

  one stair     every stair block between the ground floor and the upper floor surface (y114-120) inside the
                footprint is the servants' stair (x1642, z5036-5041); the upper floor is closed everywhere inside
                except the stair's well; and a walk over standable cells from the foyer reaches the upper floor with
                the servants' stair and never without it
  barrier       haunter_wait and gengar_trapped (every slot) are inside barrier_push's box; the reunion and family
                markers, ballroom_safe and bars_outside are outside it
  ballroom      ballroom_shut's box covers every standable cell of the ballroom and Carly's seat, leaves the hall's
                candles and bars_outside out, and pushes to bars_outside, which is standable; it is active exactly
                before the landing checkpoint while the quest is not completed
  no_build      the box lies inside the scene area, covers the footprint plus 4 blocks on every side from the floor up
                to the roof ridge (EAVE + 10), every block the house writes from its floor up (roof, chimneys, front
                steps) and every standable interior cell
  nobuild fns   the generated functions switch only survival -> adventure (on entering, tagged) and, for a tagged
                player outside, adventure -> survival; no other gamemode command is in the scene pack
  sight rule    each Channeler's sight_distance is less than the distance (feet cell to feet cell, 3D) from her seat
                to every standable cell inside the house that is outside her room, on either floor
  reach         each Channeler's sight still reaches her room's key cells: Paula the rear-door zone, Laurel each
                aisle end (the prop's floor cell or a standable cell next to it), Carly each ward mark

The rooms are the owner's brief as the coordinator stated it (2026-09-24), not read from the house commands:
foyer y115 x1625-1632 z5029-5042; dining y115 x1617-1623 z5029-5042; library y115 x1634-1642 z5029-5042; hall (its
bedrooms and the nook) y121 x1617-1642 z5032-5042; ballroom y121 x1622-1642 z5025-5030. "Standable" here is wider than
tests/test_route1_mansion.py's: a door counts as passable (a player stands in a doorway), and a solid block of any
kind (a shelf top, a chair) counts as floor, so the sight rule is checked against more cells, not fewer.

Not covered, and it needs a running server: rctmod's actual sight metric (entity positions, not cell centres, and
whether it needs line of sight at all); that a push box moves a player the way its selector volume suggests; that
adventure mode still lets a player click props, open doors and battle; that no player can climb from outside to an
upper window; and whether a battle on sight can be dodged by walking a room's edge (it can in this cell model: the
dialogue's guarded lines, not the sight, are what hold a room shut; tests/test_mansion_guardians.py walks that).
"""
import json
import math
import re
import sys
from collections import deque
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import build_audit as BA  # noqa: E402
import route1_mansion as RM  # noqa: E402
import scenes_pack as SP  # noqa: E402

PLACEMENTS = json.loads((ROOT / "data" / "placements.json").read_text(encoding="utf-8"))
SCENE = next(s for s in json.loads((ROOT / "data" / "scenes.json").read_text(encoding="utf-8"))["scenes"]
             if s["id"] == "route1_gastly_family")
GUARDS = {g["id"]: g for g in json.loads((ROOT / "data" / "mansion_guardians.json").read_text(encoding="utf-8"))["trainers"]}
EFFECTS = {e["id"]: e for e in SCENE["effects"]}
QID = "evt_route1_gastly_family"
CP_FIELD = "quest.%s.checkpoint" % QID
DONE_FIELD = "quest.%s.completed" % QID

AIR = {"minecraft:air", "minecraft:cave_air"}
THIN = ("_carpet", "minecraft:leaf_litter", "minecraft:candle", "_candle", "_trapdoor", "_door")
DEFAULT_SLOTS = [[0.0, 0.0], [0.9, 0.0], [0.0, 0.9], [-0.9, 0.0]]     # tools/scenes_pack.py SLOTS

# the servants' stair, as the owner's brief places it: the library's east wall, rising north into the SE bedroom
BACK_STAIR_X, BACK_STAIR_Z = 1642, range(5036, 5042)
WELL = {(1642, z) for z in range(5037, 5042)}
ROOMS = {                      # floor ("g" ground, "u" upper), x0, x1, z0, z1
    "foyer": ("g", 1625, 1632, 5029, 5042),
    "dining room": ("g", 1617, 1623, 5029, 5042),
    "library": ("g", 1634, 1642, 5029, 5042),
    "bedroom hall": ("u", 1617, 1642, 5032, 5042),
    "ballroom": ("u", 1622, 1642, 5025, 5030),
}


def _base(b):
    return b.split("[")[0] if b else b


def _passable(b):
    return b is not None and (b in AIR or _base(b).endswith(THIN))


def _solid(b):
    return b is not None and not _passable(b)


@pytest.fixture(scope="module")
def house():
    recs = [p for p in PLACEMENTS["placements"] if p["id"] == "route1_mansion_house"]
    assert len(recs) == 1, "data/placements.json must hold the house exactly once"
    cmds = recs[0]["commands"]
    assert len(cmds) > 1000, "the recorded house is (nearly) empty: nothing to check against"
    cols = {(x, z) for x in range(RM.X0 - 2, RM.X1 + 3) for z in range(RM.Z0 - 2, RM.Z1 + 3)}
    rep = BA.replay(cmds, cols)
    return rep


def _at(rep, x, y, z):
    return rep.get((x, z), {}).get(y)


@pytest.fixture(scope="module")
def stand(house):
    ys = sorted({y for col in house.values() for y in col})
    out = set()
    for (x, z) in house:
        for y in range(ys[0] + 1, ys[-1]):
            if _passable(_at(house, x, y, z)) and _passable(_at(house, x, y + 1, z)) and _solid(_at(house, x, y - 1, z)):
                out.add((x, y, z))
    assert len(out) > 500, "the replay yields almost no standable cells: nothing to check against"
    return out


def _floor(y):
    return "g" if RM.F < y <= RM.U else ("u" if RM.U < y < RM.EAVE else "-")


def _in_room(c, room):
    f, x0, x1, z0, z1 = ROOMS[room]
    return _floor(c[1]) == f and x0 <= c[0] <= x1 and z0 <= c[2] <= z1


def _interior(c):
    return RM.X0 < c[0] < RM.X1 and RM.Z0 < c[2] < RM.Z1 and RM.F < c[1] < RM.EAVE


def _in_box(c, b):
    return all(min(b["from"][i], b["to"][i]) <= c[i] <= max(b["from"][i], b["to"][i]) for i in range(3))


def _slots(name):
    m = SCENE["markers"][name]
    for ox, oz in m.get("slots") or SCENE.get("slots") or DEFAULT_SLOTS:
        yield (math.floor(m["at"][0] + 0.5 + ox), m["at"][1], math.floor(m["at"][2] + 0.5 + oz))


def _walk(cells, start):
    """Every standable cell reachable from start: a step to a side neighbour, up one block or down up to three
    (a generous player: more reach than the game gives, so 'never reached' is the stronger claim)."""
    seen, todo = {start}, deque([start])
    while todo:
        x, y, z = todo.popleft()
        for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            for dy in (1, 0, -1, -2, -3):
                n = (x + dx, y + dy, z + dz)
                if n in cells and n not in seen:
                    seen.add(n)
                    todo.append(n)
    return seen


# ------------------------------------------------------------------------------------------------ one stair

# Without it a grand stair (or any stair) comes back in the foyer and the house is no longer walked room by room.
def test_the_only_stair_between_the_floors_is_the_servants_stair(house):
    stairs = sorted((x, y, z) for (x, z), col in house.items() for y, b in col.items()
                    if b and _base(b).endswith("_stairs") and RM.F <= y <= RM.U
                    and RM.X0 <= x <= RM.X1 and RM.Z0 <= z <= RM.Z1)
    assert stairs, "no stair at all: the upper floor is unreachable"
    stray = [s for s in stairs if not (s[0] == BACK_STAIR_X and s[2] in BACK_STAIR_Z)]
    assert not stray, "stairs outside the servants' stair: %s" % stray


# Without it a hole in the upper floor (the old stairwell, a missing plank over the nook) is a second way up.
def test_the_upper_floor_is_closed_except_the_servants_stairs_well(house):
    open_ = sorted((x, z) for x in range(RM.X0 + 1, RM.X1) for z in range(RM.Z0 + 1, RM.Z1)
                   if not _solid(_at(house, x, RM.U, z)))
    assert set(open_) == WELL, "openings in the upper floor: %s" % open_


# Without it the upper floor is unreachable (the stair was cut off) or reachable some other way (a climb over
# furniture, a gap the floor check misses).
def test_the_floors_connect_only_through_the_servants_stair(stand):
    foyer = (1628, RM.F + 1, 5038)
    assert foyer in stand
    upper = lambda cells: [c for c in cells if _floor(c[1]) == "u"]
    assert upper(_walk(stand, foyer)), "the upper floor cannot be reached from the foyer"
    without = {c for c in stand if not (c[0] == BACK_STAIR_X and 5035 <= c[2] <= 5042 and RM.F < c[1] <= RM.U + 1)}
    assert not upper(_walk(without, foyer)), "the upper floor is reachable without the servants' stair"


# ------------------------------------------------------------------------------------------------ barrier and ballroom

# Without it Haunter or Gengar stands where the player can walk up to them before the barrier drops, or the reunion
# happens behind the barrier's push (the family is out of reach at the end).
def test_haunter_and_gengar_wait_behind_the_barrier_and_the_reunion_is_outside_it():
    push = EFFECTS["barrier_push"]
    for name in ("haunter_wait", "gengar_trapped"):
        assert all(_in_box(c, push) for c in _slots(name)), name
    for name in [n for n in SCENE["markers"] if n.startswith(("reunion_", "family_"))] + ["ballroom_safe", "bars_outside"]:
        assert not any(_in_box(c, push) for c in _slots(name)), name


# Without it part of the ballroom stays open before the candles are done (Carly or a ward mark is reachable early), or
# the push lands the player back inside the box it pushes out of.
def test_ballroom_shut_covers_every_standable_ballroom_cell_and_pushes_to_a_standable_cell_outside(stand):
    shut = EFFECTS["ballroom_shut"]
    cells = [c for c in stand if _in_room(c, "ballroom")]
    assert len(cells) > 20
    assert not [c for c in cells if not _in_box(c, shut)]
    assert _in_box(tuple(GUARDS["mansion_guardian_5"]["seat"]), shut)
    assert shut["kind"] == "push" and shut["to_marker"] == "bars_outside"
    for c in _slots("bars_outside"):
        assert c in stand and not _in_box(c, shut), c
    # the hall's candles, the library checkpoint's puzzle, stay reachable while the ballroom is shut
    for p in SCENE["props"]:
        if p["id"].startswith("candle_"):
            assert not _in_box([math.floor(v) for v in p["at"]], shut), p["id"]


def _eval(c, st):
    k = c["kind"]
    if k == "not":
        return not _eval(c["condition"], st)
    if k == "any":
        return any(_eval(x, st) for x in c["conditions"])
    if k == "all":
        return all(_eval(x, st) for x in c["conditions"])
    if k == "progression_equals":
        return st[c["field"]] == c["value"]
    if k == "progression_in":
        return st[c["field"]] in c["values"]
    raise AssertionError("condition kind %s" % k)


# Without it the ballroom opens before the candles are done, or stays shut once the player has reached the landing
# (the wards, Carly and the ending are locked away).
@pytest.mark.parametrize("cp", ["foyer", "stairs", "service", "library", "landing", "family"])
@pytest.mark.parametrize("done", [False, True])
def test_ballroom_shut_is_active_exactly_before_the_landing_checkpoint(cp, done):
    active = _eval(EFFECTS["ballroom_shut"]["when"], {CP_FIELD: cp, DONE_FIELD: done})
    assert active == (not done and cp in ("foyer", "stairs", "service", "library"))


# ------------------------------------------------------------------------------------------------ no building

NO_BUILD_MARGIN = 4


# Without it a survival player can break or place blocks in a room of the house (a wall, a shelf, the puzzle's
# props), or stands outside and breaks the walls, the roof or a chimney from there (the owner, 2026-09-24: the house
# and a margin round it). A box that leaves the scene area is refused by the scene runtime.
def test_no_build_covers_the_house_with_a_margin_up_past_the_ridge(house, stand):
    boxes = SCENE["no_build"]
    assert boxes
    inside = lambda c: any(_in_box(c, b) for b in boxes)
    area = SCENE["area"]
    for b in boxes:
        assert _in_box(b["from"], area) and _in_box(b["to"], area)
    m, ridge = NO_BUILD_MARGIN, RM.EAVE + 10
    corners = [(x, y, z) for x in (RM.X0 - m, RM.X1 + m) for z in (RM.Z0 - m, RM.Z1 + m) for y in (RM.F, ridge)]
    assert all(inside(c) for c in corners), [c for c in corners if not inside(c)]
    # every block the house writes from its floor up (walls, roof, chimneys, the front steps) and every cell a player
    # can stand in inside it
    built = [(x, y, z) for (x, z), col in house.items() for y, b in col.items() if y >= RM.F and b not in AIR]
    assert built and not [c for c in built if not inside(c)]
    assert not [c for c in stand if _interior(c) and not inside(c)]


@pytest.fixture(scope="module")
def scene_pack():
    files, _scenes = SP.build()
    return files


# Without it a creative or spectator player (an operator building) is switched to adventure, a player is left in
# adventure after leaving, or a player someone else put in adventure is switched to survival.
def test_nobuild_switches_only_survival_to_adventure_and_back_for_tagged_players(scene_pack):
    sid = SCENE["id"]
    tag = "cobblers_nobuild_%s" % sid
    base = "data/cobblers/function/scenes/%s/nobuild/" % sid
    body = lambda f: [l for l in scene_pack[base + f] if l.strip() and not l.startswith("#")]
    assert body("enter.mcfunction") == ["gamemode adventure @s", "tag @s add %s" % tag]
    assert body("leave.mcfunction") == ["execute if entity @s[gamemode=adventure] run gamemode survival @s",
                                        "tag @s remove %s" % tag]
    cycle = scene_pack["data/cobblers/function/scenes/cycle.mcfunction"]
    enters = [l for l in cycle if l.endswith("scenes/%s/nobuild/enter" % sid)]
    leaves = [l for l in cycle if l.endswith("scenes/%s/nobuild/leave" % sid)]
    assert len(enters) == len(SCENE["no_build"]) and len(leaves) == 1
    for l in enters:
        assert l.startswith("execute as @a[gamemode=survival,") and "tag=" not in l, l
    for b in SCENE["no_build"]:
        assert "unless entity @s[%s]" % SP.sel(b) in leaves[0]
        assert any("@a[gamemode=survival,%s]" % SP.sel(b) in l for l in enters)
    assert leaves[0].startswith("execute as @a[tag=%s] " % tag)
    # nothing else in the scene pack changes a game mode
    cmd = re.compile(r"(^|\s)gamemode (survival|creative|adventure|spectator)\b")
    other = [(k, l) for k, v in scene_pack.items() if isinstance(v, list) and not k.startswith(base)
             for l in v if not l.startswith("#") and cmd.search(l)]
    assert not other, other


# ------------------------------------------------------------------------------------------------ the Channelers' sight

# Without it a Channeler's battle on sight reaches through a wall into another room or the other floor (the owner saw
# Paula start a fight from the foyer), so a player is dragged into the wrong room's fight.
@pytest.mark.parametrize("gid", sorted(GUARDS))
def test_each_channelers_sight_stops_short_of_every_cell_outside_her_room(stand, gid):
    g = GUARDS[gid]
    assert g["room"] in ROOMS, "%s's room %r is not one of the brief's rooms" % (gid, g["room"])
    seat = tuple(g["seat"])
    assert _in_room(seat, g["room"]) and seat in stand, "%s's seat is not a standable cell of her room" % gid
    outside = [c for c in stand if _interior(c) and not _in_room(c, g["room"])]
    assert outside
    d, c = min((math.dist(seat, c), c) for c in outside)
    assert g["sight_distance"] < d, "%s sees %.2f, and %s outside the %s is %.2f away" % (
        gid, g["sight_distance"], c, g["room"], d)


def _key_cells(stand, floor_cell):
    """A prop's floor cell when a player can stand there, else the standable cells beside it (same height)."""
    if floor_cell in stand:
        return [floor_cell]
    x, y, z = floor_cell
    return [c for c in stand if c[1] == y and max(abs(c[0] - x), abs(c[2] - z)) == 1]


def _prop_cell(pid):
    p = next(p for p in SCENE["props"] if p["id"] == pid)
    return tuple(math.floor(v) for v in p["at"])


REACH = [("mansion_guardian_2", "zone", "dining_rear_door"),
         ("mansion_guardian_3", "prop", "aisle_west"), ("mansion_guardian_3", "prop", "aisle_middle"),
         ("mansion_guardian_3", "prop", "aisle_east"),
         ("mansion_guardian_5", "prop", "ward_a"), ("mansion_guardian_5", "prop", "ward_b"),
         ("mansion_guardian_5", "prop", "ward_c")]


# Without it a Channeler's sight is cut so short that she cannot see the place her room's task is done (the rear
# door, an aisle end, a ward mark), and battle on sight never happens there. At exactly the sight distance counts.
@pytest.mark.parametrize("gid,kind,what", REACH, ids=["%s-%s" % (g, w) for g, _k, w in REACH])
def test_each_channelers_sight_reaches_her_rooms_key_cells(stand, gid, kind, what):
    g = GUARDS[gid]
    seat = tuple(g["seat"])
    if kind == "zone":
        z = next(z for z in SCENE["zones"] if z["id"] == what)
        cells = [c for c in stand if _in_box(c, z)]
    else:
        cells = _key_cells(stand, _prop_cell(what))
    assert cells, "no standable cell at %s" % what
    d, c = min((math.dist(seat, c), c) for c in cells)
    assert d <= g["sight_distance"], "%s sees %.2f; the nearest cell at %s, %s, is %.2f away" % (
        gid, g["sight_distance"], what, c, d)
