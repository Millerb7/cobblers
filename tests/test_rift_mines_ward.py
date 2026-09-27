"""The Rift mine gate's ward (c9cb850): Mining Fatigue IV near the plug, grille and knock alcove.

Written by the test author, not by the session that wrote tools/rift_mines.py. gate_files() reads only the spec, so
these run without the out-of-repo heightmap (tests/test_rift_mines_review.py, which builds the whole pack, skips
without it).

Independent sources: data/rift_mines.json mine.gate (plug and knock boxes [x0, y0, z0, x1, y1, z1], the grille's x, y
and z ranges, ward_margin, and ward_why, which quotes the owner: "i can mine around the door", and states the aim: in
survival or adventure within ward_margin blocks of the plug, grille and alcove, Mining Fatigue IV, "so the gate cannot
be dug round or broken"); vanilla Minecraft 1.21.1: an effect's level is its amplifier + 1; a location trigger is
tested once a second (every 20 ticks); a location predicate tests the player's feet position against min <= v <= max;
a standing player's eyes are 1.62 above the feet and survival block reach (player.block_interaction_range) is 4.5.

Not covered, and it needs a running server: that the location advancement fires in the mine, that Mining Fatigue IV
makes the plug's blocks impractical to break with the best tools in the pack, and whether a player can outrun the
three-second effect.
"""
from __future__ import annotations

import copy
import itertools
import json
import math
import re
import sys
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import rift_mines as RM  # noqa: E402

SPEC = json.loads((ROOT / "data" / "rift_mines.json").read_text(encoding="utf-8"))
GATE = SPEC["mine"]["gate"]
ADV = "advancement/%s/gate_ward.json" % RM.FOLDER
EYE, REACH = 1.62, 4.5                    # vanilla 1.21.1: standing eye height, survival block interaction range


def gate(spec=None):
    return RM.gate_files(types.SimpleNamespace(spec=copy.deepcopy(spec or SPEC)), [{"min": [0, 0, 0], "max": [1, 1, 1]}])


def box_cells(b):
    return {(x, y, z) for x in range(b[0], b[3] + 1) for y in range(b[1], b[4] + 1) for z in range(b[2], b[5] + 1)}


def grille_cells(g):
    return {(g["x"], y, z) for y in range(g["y"][0], g["y"][1] + 1) for z in range(g["z"][0], g["z"][1] + 1)}


def protected(g=GATE):
    return box_cells(g["plug"]) | grille_cells(g["grille"]) | box_cells(g["knock"])


def ward_position(files):
    adv = files[ADV]
    (crit,) = adv["criteria"].values()
    assert crit["trigger"] == "minecraft:location", crit
    (cond,) = crit["conditions"]["player"]
    assert cond["condition"] == "minecraft:entity_properties" and cond["entity"] == "this", cond
    loc = cond["predicate"]["location"]
    assert loc["dimension"] == "minecraft:overworld", loc
    return loc["position"]


def inside(pos, p):
    return all(pos[a]["min"] <= v <= pos[a]["max"] for a, v in zip("xyz", p))


# Without it the ward misses part of the gate (a side of the plug, the grille or the alcove can be dug at full speed),
# or reaches further than ward_margin (fatigue where players mine legitimately). Every block of the plug, the grille
# and the alcove, and every block within ward_margin of them (the box they span, grown on every side), is in the ward;
# one block further out on any axis is not.
@pytest.mark.parametrize("margin", sorted({GATE["ward_margin"], 0, 4, 9}))
def test_the_ward_is_the_plug_grille_and_alcove_grown_by_exactly_ward_margin(margin):
    spec = copy.deepcopy(SPEC)
    spec["mine"]["gate"]["ward_margin"] = margin
    files, _fn = gate(spec)
    pos = ward_position(files)
    cells = protected()
    lo = [min(c[i] for c in cells) for i in range(3)]
    hi = [max(c[i] for c in cells) for i in range(3)]
    for i, a in enumerate("xyz"):
        # feet anywhere in the block cells lo - margin .. hi + margin
        assert (pos[a]["min"], pos[a]["max"]) == (lo[i] - margin, hi[i] + margin + 1), (a, pos[a], lo[i], hi[i])
    for c in cells:
        for d in itertools.product((-margin, 0, margin), repeat=3):
            assert inside(pos, (c[0] + d[0] + 0.5, c[1] + d[1], c[2] + d[2] + 0.5)), (c, d)
    for i in range(3):
        for edge in (lo[i] - margin - 1, hi[i] + margin + 1):          # the block one further out, its centre
            p = [(lo[j] + hi[j]) / 2 for j in range(3)]
            p[i] = edge + 0.5
            assert not inside(pos, p), ("xyz"[i], p)


# Without it the ward stops working after its first second (a location advancement is granted once unless its reward
# revokes it), gives the wrong effect or level, lapses between checks, or fatigues builders in creative and spectators.
def test_the_ward_gives_mining_fatigue_iv_to_survival_and_adventure_players_only():
    files, fn = gate()
    assert files[ADV]["rewards"] == {"function": "%s:%s/gate/ward" % (RM.NS, RM.FOLDER)}
    body = [l for l in fn["gate/ward"] if not l.startswith("#")]
    assert body[0] == "advancement revoke @s only %s:%s/gate_ward" % (RM.NS, RM.FOLDER), body
    assert len(body) == 2, body
    m = re.fullmatch(r"execute if entity @s\[([^\]]*)\] run effect give @s minecraft:mining_fatigue (\d+) (\d+) (true|false)",
                     body[1])
    assert m, body[1]
    filters = [f.split("=", 1) for f in m.group(1).split(",")]
    assert {k for k, _v in filters} == {"gamemode"}, filters

    def gets(mode):
        return all((mode != v[1:]) if v.startswith("!") else (mode == v) for _k, v in filters)
    assert {g for g in ("survival", "adventure", "creative", "spectator") if gets(g)} == {"survival", "adventure"}
    seconds, amplifier = int(m.group(2)), int(m.group(3))
    assert amplifier + 1 == 4, "Mining Fatigue IV is amplifier 3"
    assert seconds * 20 > 20, "the effect must outlast the location trigger's one-second period"


# Without it a player tunnelling under or beside the ward, their feet just outside it, can still reach and break the
# plug or the grille (ward_why: "so the gate cannot be dug round or broken"). The margin is measured at the feet, but a
# standing player's eyes are 1.62 higher and reach 4.5 blocks: found by this suite at c9cb850 with ward_margin 4 (from
# under the ward the plug's bottom was 2.4 blocks from the eyes, the grille 3.4; from beside it the plug's outer layer
# 4.0); fixed in 4a37312 (ward_margin 7).
def test_no_player_outside_the_ward_can_reach_the_plug_or_the_grille():
    files, _fn = gate()
    pos = ward_position(files)
    parts = {"grille": sorted(grille_cells(GATE["grille"])), "plug": sorted(box_cells(GATE["plug"]))}

    def dist(eye, b):
        return math.sqrt(sum(max(b[i] - eye[i], 0.0, eye[i] - (b[i] + 1)) ** 2 for i in range(3)))

    # feet positions just outside each face of the ward, on a one-block lattice across the face
    eps = 1e-3
    lattice = {a: [pos[a]["min"] + k for k in range(int(pos[a]["max"] - pos[a]["min"]) + 1)] for a in "xyz"}
    points = set()
    for a in "xyz":
        for out in (pos[a]["min"] - eps, pos[a]["max"] + eps):
            points |= set(itertools.product(*[lattice[b] if b != a else [out] for b in "xyz"]))
    reached = {}
    for p in sorted(points):
        assert not inside(pos, p)
        eye = (p[0], p[1] + EYE, p[2])
        for what, blocks in parts.items():
            d, near = min((dist(eye, b), b) for b in blocks)
            if d <= REACH:
                reached.setdefault(what, []).append((round(d, 2), tuple(round(v, 2) for v in p), near))
    assert not reached, {k: (len(v), sorted(v)[:2]) for k, v in reached.items()}
