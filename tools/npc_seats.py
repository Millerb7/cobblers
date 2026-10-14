#!/usr/bin/env python
"""The settlement NPCs' seats (data/npc_seats.json): checked offline, placed by tools/reapply.py R17N, probed in a world.

data/npc_seats.json is the STAND half of each dialogue NPC no other file seats: the residents of main_worldshift_reveal
and the speakers of ambient_stone_tips. The conversation, the name and the NPC class are data/dialogue.json's, compiled
by tools/compile_dialogue.py into cobblers_dialogue; this file only says where each one stands and which way it faces.

  python tools/npc_seats.py check          the offline checks (no world): every seat's class compiles, its y is its
                                           declared ground + 1, it is off every walked route line, and its ground
                                           kind is one the plan really records there
  python tools/npc_seats.py verify         the world probe over RCON (needs the server lock): one cobblemon:npc at
                                           each seat, standing on a solid block with air at its feet and head,
                                           facing its yaw, named as its class names it

An NPC whose stand follows a WORLD quest field (Lena, who moves once for everyone when the crushed house is checked) is a
"relocating_seats" record, not a seat: its stands are "markers", placed by reapply R18CH from the score the dialogue
writes (relocating_placements), and checked here like a seat (relocating_problems).

What it does NOT cover: route NPCs (data/scenes.json, R17), reward NPCs (data/rewards.json, R9F), ferrymen (R17F),
trader clerks (R14), trainers (tools/route_trainers.py), and whatever a template or a mod placed. A world sweep for
those is a different question from "are OUR seats right" (CLAUDE.md "Our list is not the world").
"""
from __future__ import annotations

import os

import argparse
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "npc_seats.json"
GROUND_KINDS = ("heightmap", "plaza", "lot_level", "template_floor")
MIN_ROUTE = 3.0          # an immovable NPC this close to a walked line stands in the road
YAW_SLACK = 10.0         # degrees: the probe's tolerance on a seat's facing


def load(path=DATA):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def placements(doc=None):
    """[(conversation id, (x, y, z), npc class, yaw)] for tools/reapply.py's npc action."""
    doc = doc or load()
    return [(s["conversation"], tuple(s["at"]), "cobblers:%s" % s["id"], s["yaw"]) for s in doc["seats"]]


def world_value(rc, holder, objective):
    """A world scoreboard value over RCON (0 when nobody has written it: no score, or no objective yet), the value a
    dialogue's world field holds (tools/compile_dialogue.py "world"). rc(cmd) -> reply text."""
    import re
    m = re.search(r"has (-?\d+) \[", rc("scoreboard players get %s %s" % (holder, objective)))
    return int(m.group(1)) if m else 0


def relocating_placements(doc=None):
    """[(conversation, (x, y, z), npc class, yaw, selector)] for tools/reapply.py's npc action: an NPC whose stand is
    decided by a WORLD field (data/npc_seats.json "relocating_seats", Lena in the crushed house). The stand is the
    marker of the field's first value; `selector` is {objective, holder, value, at, yaw} for each LATER value, and the
    action stands her there instead while the score holds that value. One later value is supported (check() says so)."""
    import compile_dialogue as CD
    doc = doc or load()
    mk = doc.get("markers") or {}
    out = []
    for s in doc.get("relocating_seats") or []:
        first, *later = list(s["states"].values())
        sel = [{"objective": CD.WORLD_OBJECTIVE, "holder": CD.world_holder(s["state_field"]), "value": i + 1,
                "at": tuple(mk[m]["at"]), "yaw": mk[m]["yaw"]} for i, m in enumerate(later)]
        out.append((s["conversation"], tuple(mk[first]["at"]), "cobblers:%s" % s["id"], mk[first]["yaw"], *sel[:1]))
    return out


def relocating_problems(doc=None, ground=None, classes=None, progression=None):
    """Problems with the markers and the relocating seats: a marker is a place an NPC stands, so it is held to a seat's
    rules (ground + 1, off the road, facing what it says); a relocating seat must name a compiled class, a world field
    of progression.json whose allowed values are its states in order, and markers that exist."""
    import math
    import re
    import numpy as np
    doc = doc or load()
    classes = compiled_classes() if classes is None else classes
    progression = progression or json.loads((ROOT / "data" / "progression.json").read_text(encoding="utf-8"))
    fields = {f["id"]: f for f in progression["quest_fields"]}
    mk = doc.get("markers") or {}
    probs = []
    pts = _route_points()
    for mid, m in mk.items():
        x, y, z = m["at"]
        if y != m["ground"]["y"] + 1:
            probs.append("%s: stands at y%d, but its ground is y%d (a marker is ground + 1)" % (mid, y, m["ground"]["y"]))
        if ground is not None and ground(x, z) != m["ground"]["y"]:
            probs.append("%s: heightmap ground at (%d, %d) is y%d, the marker says y%d" % (mid, x, z, ground(x, z), m["ground"]["y"]))
        if not isinstance(m.get("yaw"), (int, float)) or not -180 <= m["yaw"] <= 180:
            probs.append("%s: yaw %r is not a Minecraft yaw in -180..180" % (mid, m.get("yaw")))
        elif len(re.findall(r"\((-?\d+), (-?\d+)\)", m.get("faces", ""))) == 1:
            tx, tz = map(int, re.findall(r"\((-?\d+), (-?\d+)\)", m["faces"])[0])
            want = math.degrees(math.atan2(-(tx - x), tz - z))
            if abs((m["yaw"] - want + 180.0) % 360.0 - 180.0) > 0.5:
                probs.append("%s: yaw %s, but %r is at bearing %.1f" % (mid, m["yaw"], m["faces"], want))
        d = float(np.min(np.hypot(pts[:, 0] - x, pts[:, 1] - z)))
        if d < MIN_ROUTE:
            probs.append("%s: %.1f blocks from a walked route line" % (mid, d))
    seated = {s["id"] for s in doc["seats"]}
    for s in doc.get("relocating_seats") or []:
        sid = s["id"]
        if sid in seated:
            probs.append("%s: in both seats and relocating_seats (R17N would seat a second one)" % sid)
        if sid not in classes:
            probs.append("%s: no compiled NPC class" % sid)
        f = fields.get(s["state_field"])
        if not f or f.get("scope") != "world":
            probs.append("%s: state_field %s is not a world field of data/progression.json" % (sid, s["state_field"]))
        elif list(s["states"]) != f.get("allowed_values"):
            probs.append("%s: states %s are not the field's allowed_values %s in order" % (sid, list(s["states"]), f.get("allowed_values")))
        if len(s["states"]) != 2:
            probs.append("%s: %d states; R18CH's npc action takes exactly two (a first stand and one later)" % (sid, len(s["states"])))
        for st, mid in s["states"].items():
            if mid not in mk:
                probs.append("%s: state %s names marker %s, which is not in markers" % (sid, st, mid))
    return probs


def compiled_classes():
    """{npc id: display name} for every NPC class tools/compile_dialogue.py --all emits (its refusals are absent)."""
    import compile_dialogue as CD
    import tempfile
    import contextlib
    import io
    with tempfile.TemporaryDirectory() as tmp:
        with contextlib.redirect_stdout(io.StringIO()):
            CD.main(["--all", "--out", tmp])
        return {f.stem: (json.loads(f.read_text(encoding="utf-8")).get("names") or [None])[0]
                for f in (Path(tmp) / "data" / "cobblers" / "npcs").glob("*.json")}


def _route_points():
    import numpy as np
    paths = json.loads((ROOT / "data" / "route_paths.json").read_text(encoding="utf-8"))["paths"]
    return np.array([(x, z) for v in paths.values() for x, z in v], dtype=float)


def check(doc=None, ground=None, classes=None):
    """Problems, as strings; empty when every seat passes the offline checks."""
    import numpy as np
    doc = doc or load()
    probs = []
    classes = compiled_classes() if classes is None else classes
    pl = json.loads((ROOT / "data" / "placements.json").read_text(encoding="utf-8"))
    pts = _route_points()
    seen = set()
    for s in doc["seats"]:
        sid, (x, y, z), g = s["id"], s["at"], s["ground"]
        if sid in seen:
            probs.append("%s: seated twice" % sid)
        seen.add(sid)
        if sid not in classes:
            probs.append("%s: no compiled NPC class (tools/compile_dialogue.py --all does not emit it)" % sid)
        if g["kind"] not in GROUND_KINDS:
            probs.append("%s: unknown ground kind %r" % (sid, g["kind"]))
        if y != g["y"] + 1:
            probs.append("%s: stands at y%d, but its ground is y%d (a seat is ground + 1)" % (sid, y, g["y"]))
        if not isinstance(s.get("yaw"), (int, float)) or not -180 <= s["yaw"] <= 180:
            probs.append("%s: yaw %r is not a Minecraft yaw in -180..180" % (sid, s.get("yaw")))
        d = float(np.min(np.hypot(pts[:, 0] - x, pts[:, 1] - z)))
        if d < MIN_ROUTE:
            probs.append("%s: %.1f blocks from a walked route line; an immovable NPC there blocks the road" % (sid, d))
        st = pl["settlements"].get(s.get("settlement") or "", {})
        plan = st.get("plan") or {}
        if g["kind"] == "plaza":
            pz = plan.get("plaza") or {}
            r = pz.get("rect")
            if not r or not (r[0] <= x <= r[2] and r[1] <= z <= r[3]):
                probs.append("%s: ground kind plaza, but (%d, %d) is not on %s's plaza" % (sid, x, z, s.get("settlement")))
            elif pz.get("y") != g["y"]:
                probs.append("%s: plaza ground y%d, the plan's plaza is y%s" % (sid, g["y"], pz.get("y")))
        if g["kind"] == "heightmap" and ground is not None:
            # a heightmap seat on a plaza takes the plaza's paved y, not the terrain under it
            pz = plan.get("plaza") or {}
            r = pz.get("rect")
            if r and r[0] <= x <= r[2] and r[1] <= z <= r[3]:
                probs.append("%s: on %s's plaza (paved y%s) but takes its ground from the heightmap"
                             % (sid, s.get("settlement"), pz.get("y")))
            if ground(x, z) != g["y"]:
                probs.append("%s: heightmap ground at (%d, %d) is y%d, the seat says y%d" % (sid, x, z, ground(x, z), g["y"]))
    for n in doc.get("not_seated") or []:
        if n["id"] in seen:
            probs.append("%s: both seated and not_seated" % n["id"])
        if not n.get("why"):
            probs.append("%s: not seated, and no why" % n["id"])
    probs += relocating_problems(doc, ground, classes)
    return probs


def _yaw_diff(a, b):
    return abs((a - b + 180.0) % 360.0 - 180.0)


def verify(rc, doc=None, classes=None):
    """The world probe over an RCON callable rc(cmd) -> str. Returns [(id, verdict, detail)]; verdict ok or FAIL."""
    import time
    doc = doc or load()
    classes = compiled_classes() if classes is None else classes
    out = []
    # a relocating NPC is probed at the stand its world field selects now (the same read R18CH seats her by)
    stands = list(doc["seats"])
    for p, rs in zip(relocating_placements(doc), doc.get("relocating_seats") or []):
        at, yaw = p[1], p[3]
        if len(p) > 4 and world_value(rc, p[4]["holder"], p[4]["objective"]) == p[4]["value"]:
            at, yaw = p[4]["at"], p[4]["yaw"]
        stands.append({"id": rs["id"], "at": list(at), "yaw": yaw})
    for s in stands:
        sid, (x, y, z) = s["id"], s["at"]
        rc("forceload add %d %d" % (x, z))
        for _ in range(30):
            if "passed" in rc("execute if loaded %d %d %d" % (x, y, z)):
                break
            time.sleep(1)
        time.sleep(2)
        near = "@e[type=cobblemon:npc,x=%d.5,y=%d,z=%d.5,distance=..1.5]" % (x, y, z)
        bad = []
        rc("execute store result storage cobblers:npc_seats n int 1 if entity %s" % near)
        got = rc("data get storage cobblers:npc_seats n").rsplit(":", 1)[-1].strip()
        if got != "1":
            bad.append("%s NPCs within 1.5 blocks, not 1" % got)
        if "passed" not in rc("execute unless block %d %d %d #minecraft:replaceable" % (x, y - 1, z)):
            bad.append("no solid block under its feet at y%d" % (y - 1))
        for dy in (0, 1):
            if "passed" in rc("execute unless block %d %d %d #minecraft:replaceable" % (x, y + dy, z)):
                bad.append("a solid block at its %s (y%d)" % ("feet" if dy == 0 else "head", y + dy))
        r = rc("data get entity %s Rotation[0]" % near.replace("]", ",limit=1]"))
        try:
            yaw = float(r.rsplit(":", 1)[-1].strip().rstrip("f"))
            if _yaw_diff(yaw, s["yaw"]) > YAW_SLACK:
                bad.append("faces %.0f, authored %d" % (yaw, s["yaw"]))
        except ValueError:
            bad.append("no rotation read: %r" % r[:80])
        r = rc("data get entity %s Pos" % near.replace("]", ",limit=1]"))
        rc("forceload remove %d %d" % (x, z))
        out.append((sid, "FAIL" if bad else "ok", "; ".join(bad) or ("at %s" % r.rsplit(":", 1)[-1].strip()[:60])))
    return out


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("action", choices=("check", "verify"))
    p.add_argument("--server-dir", default=os.environ.get("COBBLERS_SERVER_ROOT"),
                   help="the server directory; defaults to $COBBLERS_SERVER_ROOT (never a hard-coded runtime path)")
    a = p.parse_args(argv)
    sys.path.insert(0, str(ROOT / "tools"))
    if a.action == "check":
        import ground as G
        try:
            g = G.load()
        except (SystemExit, OSError, FileNotFoundError) as e:
            print("heightmap unreadable (%s): the heightmap checks are skipped" % e)
            g = None
        probs = check(ground=g)
        doc = load()
        print("%d seats, %d relocating (%d markers), %d not seated: %s"
              % (len(doc["seats"]), len(doc.get("relocating_seats") or []), len(doc.get("markers") or {}),
                 len(doc.get("not_seated") or []), "clean" if not probs else "%d problem(s)" % len(probs)))
        for m in probs:
            print("  PROBLEM " + m)
        return 1 if probs else 0
    import reapply
    rc = reapply.Rcon(a.server_dir)
    res = verify(rc)
    for sid, verdict, detail in res:
        print("%-4s %-40s %s" % (verdict, sid, detail))
    fails = [r for r in res if r[1] != "ok"]
    print("%d of %d seats verified in the world" % (len(res) - len(fails), len(res)))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    raise SystemExit(main())
