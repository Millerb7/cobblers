"""The mainline reveal's evidence displays (tools/reveal_evidence.py, data/reveal_evidence.json).

Written by the session that built them, so not an independent audit; expectations are derived here from sources the
builder does not compute them from where one exists:

  which evidence   data/quests.json main_worldshift_reveal physical_evidence: every record is either displayed or
                   named in data/reveal_evidence.json not_covered, never silently dropped
  beside whom      the conversation of the beat (dlg_main_<beat>_...) and its seat in data/npc_seats.json
  facing           the sign's rotation from the teller's yaw by Minecraft's own rule (rotation = yaw * 16 / 360,
                   0 = text toward the south), not from the builder's cardinal table
  ground           the canonical heightmap (tools/ground.py) or the plan's plaza y, never a world
  guarded writes   every block write in a function is conditional on what is there

Generator mutations run 2026-10-05 (tools/reveal_evidence.py edited, data untouched, then restored):
  LATERAL = 0 and the builder's own seat check removed       test_no_display_stands_on_an_npc fails x8
    (LATERAL = 0 alone: the builder refuses every display itself, 58 errors)
  the prop's `if block <it> #minecraft:replaceable` replaced  test_every_write_is_guarded fails x8 (the first form of
    by `unless block <it> minecraft:bedrock`                  that test passed it: it was tightened to the position)
  SIGN_ROTATION west/east swapped                             test_the_sign_faces_the_way_its_teller_faces fails x4
                                                              (the four east/west-facing tellers)
"""
from __future__ import annotations

import json
import math
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import reveal_evidence as RE  # noqa: E402

DATA = ROOT / "data"


def _json(name):
    return json.loads((DATA / name).read_text(encoding="utf-8"))


DOC = _json("reveal_evidence.json")
QUEST = next(q for q in _json("quests.json")["quests"] if q["id"] == "main_worldshift_reveal")
SEATS = {s["id"]: s for s in _json("npc_seats.json")["seats"]}
CONVS = {c["id"]: c for c in _json("dialogue.json")["conversations"]}
PLAZAS = {k: (v.get("plan") or {}).get("plaza") for k, v in _json("placements.json")["settlements"].items()}


@pytest.fixture(scope="module")
def ground():
    import ground as G
    return G.load()


@pytest.fixture(scope="module")
def plans(ground):
    return {p["beat"]: p for p in RE.plan(DOC, ground)}


@pytest.fixture(scope="module")
def pack(plans):
    return RE.files(list(plans.values()))


BEATS = [d["beat"] for d in DOC["displays"]]


def test_every_evidence_record_is_displayed_or_named_as_not_covered():
    shown = {d["evidence"] for d in DOC["displays"]}
    for e in QUEST["physical_evidence"]:
        assert e["id"] in shown or e["id"] in DOC["not_covered"], "%s is neither displayed nor not_covered" % e["id"]
    assert shown <= {e["id"] for e in QUEST["physical_evidence"]}, "a display names no evidence record"


@pytest.mark.parametrize("beat", BEATS)
def test_each_display_stands_beside_its_beats_teller(beat, plans):
    p = plans[beat]
    convs = [c for c in CONVS.values() if c["id"].startswith("dlg_main_%s_" % beat)]
    assert len(convs) == 1, convs
    assert convs[0]["npc_id"] == p["teller"]
    sx, sy, sz = SEATS[p["teller"]]["at"]
    for x, y, z in (p["prop_at"], p["sign_at"]):
        assert max(abs(x - sx), abs(z - sz)) <= 3 and abs(y - sy) <= 1, ((x, y, z), (sx, sy, sz))
    (px, _, pz), (gx, _, gz) = p["prop_at"], p["sign_at"]
    assert abs(px - gx) + abs(pz - gz) == 1, "the sign does not stand against its prop"


@pytest.mark.parametrize("beat", BEATS)
def test_no_display_stands_on_an_npc(beat, plans):
    p = plans[beat]
    seats = {(s["at"][0], s["at"][2]) for s in SEATS.values()}
    for x, _y, z in (p["prop_at"], p["sign_at"]):
        assert (x, z) not in seats


@pytest.mark.parametrize("beat", BEATS)
def test_no_display_stands_in_the_road(beat, plans):
    pts = [(x, z) for v in _json("route_paths.json")["paths"].values() for x, z in v]
    for x, _y, z in (plans[beat]["prop_at"], plans[beat]["sign_at"]):
        # densify each leg independently of the builder's segment distance
        best = min(math.hypot(x - px, z - pz) for px, pz in pts)
        for v in _json("route_paths.json")["paths"].values():
            for (ax, az), (bx, bz) in zip(v, v[1:]):
                n = max(1, int(math.hypot(bx - ax, bz - az) * 4))
                best = min(best, min(math.hypot(x - (ax + (bx - ax) * i / n), z - (az + (bz - az) * i / n))
                                     for i in range(n + 1)))
        assert best >= RE.MIN_ROUTE - 0.25, "(%d, %d) is %.2f from a walked route line" % (x, z, best)


@pytest.mark.parametrize("beat", BEATS)
def test_each_column_stands_on_its_planned_ground(beat, plans, ground):
    p = plans[beat]
    seat = SEATS[p["teller"]]
    plaza = PLAZAS.get(seat.get("settlement")) or {}
    for (x, y, z), src in ((p["prop_at"], p["prop_ground"]), (p["sign_at"], p["sign_ground"])):
        r = plaza.get("rect")
        on_plaza = bool(r) and r[0] <= x <= r[2] and r[1] <= z <= r[3]
        if seat["ground"]["kind"] == "lot_level":
            assert y - 1 == seat["ground"]["y"]
        elif on_plaza:
            assert src == "plaza" and y - 1 == plaza["y"]
        else:
            assert src == "heightmap" and y - 1 == ground(x, z)
            assert abs(ground(x, z) - seat["ground"]["y"]) <= 1


@pytest.mark.parametrize("beat", BEATS)
def test_the_sign_faces_the_way_its_teller_faces(beat, plans):
    p = plans[beat]
    rot = int(re.search(r"rotation=(\d+)", p["sign"]).group(1))
    want = round(SEATS[p["teller"]]["yaw"] * 16 / 360) % 16
    diff = min((rot - want) % 16, (want - rot) % 16)
    assert diff <= 2, "sign rotation %d, teller yaw %s wants %d" % (rot, SEATS[p["teller"]]["yaw"], want)


@pytest.mark.parametrize("beat", BEATS)
def test_the_sign_says_what_the_data_says(beat, plans):
    d = next(d for d in DOC["displays"] if d["beat"] == beat)
    msgs = re.search(r"messages:\[(.*)\]\}\}$", plans[beat]["sign"]).group(1)
    got = [json.loads(m.replace("\\'", "'")) for m in re.findall(r"'((?:\\'|[^'])*)'", msgs)]
    assert got == (d["sign"] + ["", "", "", ""])[:4]
    assert all(len(l) <= 16 for l in d["sign"])


@pytest.mark.parametrize("beat", BEATS)
def test_every_write_is_guarded(beat, pack):
    text = pack["data/cobblers/function/reveal_evidence/%s.mcfunction" % beat]
    cmds = [l for l in text.splitlines() if l.strip() and not l.startswith("#")]
    assert cmds
    for c in cmds:
        assert not c.startswith(("fill", "setblock", "clone")), "an unguarded write: %s" % c
        assert c.startswith("execute ") and " run setblock " in c, c
        head, block = c.split(" run setblock ", 1)
        x, y, z = (int(v) for v in block.split()[:3])
        if block.split()[3] == "minecraft:air":
            # a removal: only where this display's own block is, by exact id at the same position
            assert re.search(r"if block %d %d %d minecraft:[a-z_]+( |$)" % (x, y, z), head), c
        else:
            # a placement: only into a replaceable block, and only over solid ground or the prop's own lower block
            assert "if block %d %d %d #minecraft:replaceable" % (x, y, z) in head, c
            assert ("unless block %d %d %d #minecraft:replaceable" % (x, y - 1, z) in head
                    or re.search(r"if block %d %d %d minecraft:[a-z_]+( |$)" % (x, y - 1, z), head)), c


def test_the_steps_hold_each_displays_chunk_around_its_function(plans):
    steps = RE.placement_steps(plans=list(plans.values()))
    fns = [s[1] for s in steps if s[0] == "fn"]
    assert fns == ["cobblers:reveal_evidence/%s" % b for b in BEATS]
    for i, s in enumerate(steps):
        if s[0] != "fn":
            continue
        beat = s[1].rsplit("/", 1)[1]
        add, rem = steps[i - 2][1].split(), steps[i + 1][1].split()
        assert add[:2] == ["forceload", "add"] and rem[:2] == ["forceload", "remove"] and add[2:] == rem[2:]
        x0, z0, x1, z1 = map(int, add[2:])
        for x, _y, z in (plans[beat]["prop_at"], plans[beat]["sign_at"]):
            assert x0 <= x <= x1 and z0 <= z <= z1


def test_the_pack_is_one_function_per_display_and_its_meta(pack):
    assert set(pack) == {"pack.mcmeta"} | {"data/cobblers/function/reveal_evidence/%s.mcfunction" % b for b in BEATS}
