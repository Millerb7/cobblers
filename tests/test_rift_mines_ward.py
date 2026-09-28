"""The seam's one crystal behind the company grille, and its per-player ward (data/rift_mines.json mine.tease).

Rewritten by the test author for the cut-back spur (72f8ddb): the company gate and its ward are retired with the gated
galleries (retired_gated_section); the ward now belongs to the tease (decision 2, SOUTHERN_RIFT_MEGA.md section 8: "one
mega_stone_crystal in the seam's face at the prospect drift's end, visible and out of reach: behind the company's
grille, inside the Mining Fatigue ward ... The ward is an effect given to players, so it can be per player: it lifts for
a player holding gym6_cleared"). tease_files() reads only the spec, so these run without the heightmap.

Independent sources: data/rift_mines.json mine.tease (the grille's cells, the face box, ward_margin and ward_why: "the
grille, the pocket and the face box grown by 7"; "Mining Fatigue IV only for players lacking the flag") and its
`geometry` words for the tube and the pocket (rasterised here, not by the tool); the flag (gym6_cleared); vanilla
Minecraft 1.21.1: an effect's level is its amplifier + 1, a location trigger is tested once a second, a position range
tests the feet, a standing player's eyes are 1.62 above the feet and survival block reach is 4.5.

Not covered, and it needs a running server: that the location advancement fires at the seam, that Mining Fatigue IV
makes the grille and meteorid impractical to break, that the flag test lifts it for one player and not another, and
that a player cannot see the crystal as a reason to tunnel in from further away (the ward is the only guard: there is
no zone check here, by the data's design).
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
TEASE = SPEC["mine"]["tease"]
FLAG = "cobblers:flag/gym6_cleared"
ADV = "advancement/%s/tease_ward.json" % RM.FOLDER
EYE, REACH = 1.62, 4.5


def tease(spec=None):
    return RM.tease_files(types.SimpleNamespace(spec=copy.deepcopy(spec or SPEC)))


def half_up(v):
    return int(math.floor(v + 0.5))


def tube(path, r, height):
    """geometry.tube, in this file's own words: n = ceil(4 * horizontal length) + 1 points per segment, each stamping
    the (2r+1)^2 columns round (floor(x+.5), floor(z+.5)) from feet floor(y+.5) up `height` blocks."""
    out = set()
    for a, b in zip(path, path[1:]):
        L = math.hypot(b[0] - a[0], b[2] - a[2])
        n = int(math.ceil(4 * L)) + 1 if L > 0 else 1
        for s in range(n):
            f = s / (n - 1) if n > 1 else 0.0
            px, py, pz = (half_up(a[q] + (b[q] - a[q]) * f) for q in range(3))
            out |= {(x, y, z) for x in range(px - r, px + r + 1) for z in range(pz - r, pz + r + 1) for y in range(py, py + height)}
    return out


def pocket(at, r):
    """geometry.pocket: columns with dx2+dz2 <= (r+0.5)^2; feet to feet+r+1 where dx2+dz2 <= (r-0.5)^2, else feet+r."""
    cx, feet, cz = at
    out = set()
    for dx in range(-r - 1, r + 2):
        for dz in range(-r - 1, r + 2):
            q = dx * dx + dz * dz
            if q <= (r + 0.5) ** 2:
                out |= {(cx + dx, y, cz + dz) for y in range(feet, feet + (r + 1 if q <= (r - 0.5) ** 2 else r) + 1)}
    return out


DRIFT = next(f for f in SPEC["mine"]["features"] if f["id"] == TEASE["drift"])
G = TEASE["grille"]
GRILLE = {(x, y, G["z"]) for x in range(G["x"][0], G["x"][1] + 1) for y in range(G["y"][0], G["y"][1] + 1)}
FB = TEASE["face"]["box"]
FACE = {(x, y, z) for x in range(FB[0], FB[3] + 1) for y in range(FB[1], FB[4] + 1) for z in range(FB[2], FB[5] + 1)}
POCKET = pocket(DRIFT["pocket"]["at"], DRIFT["pocket"]["r"])


def ward_position(files):
    (crit,) = files[ADV]["criteria"].values()
    assert crit["trigger"] == "minecraft:location", crit
    (cond,) = crit["conditions"]["player"]
    assert cond["condition"] == "minecraft:entity_properties" and cond["entity"] == "this", cond
    loc = cond["predicate"]["location"]
    assert loc["dimension"] == "minecraft:overworld", loc
    return loc["position"]


def inside(pos, p):
    return all(pos[a]["min"] <= v <= pos[a]["max"] for a, v in zip("xyz", p))


# Without it the crystal is not behind the grille: drift C (by the data's geometry) reaches the face's front from the
# drift's mouth without passing through a grille cell, so the grille is decoration and the crystal is in the open.
# With the grille's cells removed from the drift, the face's front is cut off from the mouth; with them, it is not.
def test_the_crystal_is_behind_the_grille():
    open_ = tube(DRIFT["path"], DRIFT["r"], DRIFT["height"]) | POCKET
    assert GRILLE <= open_, "the grille does not stand in the drift"
    assert not FACE & open_, "the face box is carved"
    step = {"south": (0, 0, 1), "north": (0, 0, -1), "east": (1, 0, 0), "west": (-1, 0, 0)}[TEASE["face"]["front"]]
    front = {(x + step[0], y + step[1], z + step[2]) for x, y, z in FACE} & open_
    assert front, "the face's front meets nothing open"
    mouth = tuple(DRIFT["path"][0])

    def reach(cells):
        seen, stack = {mouth}, [mouth]
        while stack:
            x, y, z = stack.pop()
            for d in ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1)):
                q = (x + d[0], y + d[1], z + d[2])
                if q in cells and q not in seen:
                    seen.add(q)
                    stack.append(q)
        return seen
    assert not reach(open_ - GRILLE) & front, "the face is reached from the drift's mouth without passing the grille"
    assert reach(open_) & front, "the drift does not lead to the face at all"


# Without it the ward misses part of what it guards (the grille, the pocket behind it or the face can be dug at full
# speed) or reaches further than ward_margin: every block of the three is inside, grown by exactly ward_margin on each
# side, and one block further out on any axis is not.
@pytest.mark.parametrize("margin", sorted({TEASE["ward_margin"], 0, 4, 9}))
def test_the_ward_is_the_grille_pocket_and_face_grown_by_exactly_ward_margin(margin):
    spec = copy.deepcopy(SPEC)
    spec["mine"]["tease"]["ward_margin"] = margin
    pos = ward_position(tease(spec)[0])
    cells = GRILLE | POCKET | FACE
    lo = [min(c[i] for c in cells) for i in range(3)]
    hi = [max(c[i] for c in cells) for i in range(3)]
    for i, a in enumerate("xyz"):
        assert (pos[a]["min"], pos[a]["max"]) == (lo[i] - margin, hi[i] + margin + 1), (a, pos[a], lo[i], hi[i])
    for i in range(3):
        for edge in (lo[i] - margin - 1, hi[i] + margin + 1):
            p = [(lo[j] + hi[j]) / 2 for j in range(3)]
            p[i] = edge + 0.5
            assert not inside(pos, p), ("xyz"[i], p)


def _gets_fatigue(fn, has_flag, mode):
    """Evaluate tease/ward's effect line's selector for one player."""
    body = [l for l in fn["tease/ward"] if not l.startswith("#")]
    assert body[0] == "advancement revoke @s only %s:%s/tease_ward" % (RM.NS, RM.FOLDER), body
    assert len(body) == 2, body
    m = re.fullmatch(r"execute if entity @s\[([^\]]*)\] run effect give @s minecraft:mining_fatigue (\d+) (\d+) true",
                     body[1])
    assert m, body[1]
    sel = m.group(1)
    ok = True
    for f in re.findall(r"gamemode=(!?\w+)", sel):
        ok &= (mode != f[1:]) if f.startswith("!") else (mode == f)
    for adv, val in re.findall(r"advancements=\{([a-z0-9_:/]+)=(true|false)\}", sel):
        assert adv == FLAG, adv
        ok &= has_flag == (val == "true")
    assert set(re.sub(r"advancements=\{[^}]*\}", "", sel).replace("gamemode=!creative", "").replace(
        "gamemode=!spectator", "").replace(",", "")) == set(), sel
    return ok, int(m.group(2)), int(m.group(3))


# Without it the ward stays on a player who holds the flag (the crystal is never theirs: decision 2, "it lifts for a
# player holding gym6_cleared"), lifts for one who does not, fatigues builders in creative and spectators, gives the
# wrong effect or level, or lapses between the location trigger's one-second checks.
@pytest.mark.parametrize("has_flag", [False, True], ids=["without the flag", "with the flag"])
@pytest.mark.parametrize("mode", ["survival", "adventure", "creative", "spectator"])
def test_the_ward_fatigues_only_survival_and_adventure_players_lacking_gym6(has_flag, mode):
    files, fn = tease()
    assert files[ADV]["rewards"] == {"function": "%s:%s/tease/ward" % (RM.NS, RM.FOLDER)}
    got, seconds, amp = _gets_fatigue(fn, has_flag, mode)
    assert got == (not has_flag and mode in ("survival", "adventure")), (has_flag, mode)
    assert amp + 1 == 4 and seconds * 20 > 20


# Without it a player just outside the ward, feet out, eyes 1.62 higher, reaches the grille or the crystal's face at
# full speed (the reach finding that set the old gate's margin to 7, c9cb850 -> 4a37312, applies to this ward too).
def test_no_player_outside_the_ward_can_reach_the_grille_or_the_face():
    pos = ward_position(tease()[0])
    parts = {"grille": sorted(GRILLE), "face": sorted(FACE)}

    def dist(eye, b):
        return math.sqrt(sum(max(b[i] - eye[i], 0.0, eye[i] - (b[i] + 1)) ** 2 for i in range(3)))

    eps = 1e-3
    lattice = {a: [pos[a]["min"] + k for k in range(int(pos[a]["max"] - pos[a]["min"]) + 1)] for a in "xyz"}
    points = set()
    for a in "xyz":
        for out in (pos[a]["min"] - eps, pos[a]["max"] + eps):
            points |= set(itertools.product(*[lattice[b] if b != a else [out] for b in "xyz"]))
    reached = {}
    for p in sorted(points):
        eye = (p[0], p[1] + EYE, p[2])
        for what, blocks in parts.items():
            d = min(dist(eye, b) for b in blocks)
            if d <= REACH:
                reached.setdefault(what, []).append((round(d, 2), p))
    assert not reached, {k: (len(v), sorted(v)[:2]) for k, v in reached.items()}
