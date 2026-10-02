#!/usr/bin/env python
"""Every trainer in the WORLD, checked over RCON: our seats, and the gym leaders' spawners our seats never list.

  python tools/trainer_world_audit.py [--server-dir DIR] [--out FILE]

Needs the server lock (tools/runtime_guard.py, through reapply.Rcon). Reads the world to CHECK, never to decide.

Two halves, because a list of what WE seat is not a list of what is in the world (CLAUDE.md "Our list is not the
world"):

  seats      tools/route_trainers.py placements(): the route, late-route, mansion, arena and Victory Road trainers.
             For each: exactly ONE rctmod:trainer with that TrainerId within 1.5 blocks of the seat, and none
             other with that id within 24 (a doubled seat); a solid block under its feet, nothing solid at its
             feet or head; its body yaw within 10 degrees of the authored yaw; movement speed 0 (pinned) and
             Invulnerable.
  spawners   each gym leader's rctmod:trainer_spawner block, where data/gym_buildings/<gym>.json (leader.spawner)
             or, for a gym with no authored building, data/gym_interiors.json (expect_spawner_at) puts it, naming
             the leader's upstream id in its TrainerIds.

NOT covered: the Elite Four and the Champion's spawners (inside the kanto_league template; data/ records their
template, not their world blocks, so their positions would be this tool's own guess), Cobbleverse's naturally
spawning RCT trainers, and the trainer's team (that is the installed datapack: tools/install_check.py compares the
installed cobblers_trainers with the build).
"""
from __future__ import annotations

import os

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
YAW_SLACK = 10.0


def _yaw_diff(a, b):
    return abs((a - b + 180.0) % 360.0 - 180.0)


def _num(reply):
    """The number a reply ends with. Most replies put it after a colon ("... entity data: 315.0f"), but `attribute
    ... get` does not ("Attribute Speed for entity Trail Novice is 0.0"), and reading only after the colon turned
    every pinned trainer into "not pinned" on this audit's first run against a world (2026-10-02)."""
    words = reply.split()
    for tail in (reply.rsplit(":", 1)[-1], words[-1] if words else ""):
        try:
            return float(tail.strip().rstrip("fdb"))
        except ValueError:
            continue
    return None


def _hold(rc, x, y, z):
    rc("forceload add %d %d" % (x, z))
    for _ in range(30):
        if "passed" in rc("execute if loaded %d %d %d" % (x, y, z)):
            break
        time.sleep(1)
    time.sleep(2)              # a chunk's entities load after its blocks


def _count(rc, sel):
    rc("execute store result storage cobblers:audit n int 1 if entity %s" % sel)
    return _num(rc("data get storage cobblers:audit n"))


def seats(rc):
    import route_trainers
    out = []
    for tid, (x, y, z), yaw in route_trainers.placements():
        _hold(rc, x, y, z)
        bad = []
        here = '@e[type=rctmod:trainer,x=%d.5,y=%d,z=%d.5,distance=..1.5,nbt={TrainerId:"%s"}]' % (x, y, z, tid)
        wide = '@e[type=rctmod:trainer,x=%d,y=%d,z=%d,distance=..24,nbt={TrainerId:"%s"}]' % (x, y, z, tid)
        n, w = _count(rc, here), _count(rc, wide)
        if n != 1:
            bad.append("%s at the seat, not 1" % (n if n is not None else "?"))
        if w is not None and w > 1:
            bad.append("%d with this id within 24 (doubled)" % w)
        if "passed" not in rc("execute unless block %d %d %d #minecraft:replaceable" % (x, y - 1, z)):
            bad.append("nothing solid under its feet (y%d)" % (y - 1))
        for dy, part in ((0, "feet"), (1, "head")):
            if "passed" in rc("execute unless block %d %d %d #minecraft:replaceable" % (x, y + dy, z)):
                bad.append("solid block at its %s (y%d)" % (part, y + dy))
        one = here.replace("]", ",limit=1]")
        if n:
            got = _num(rc("data get entity %s Rotation[0]" % one))
            if got is None or _yaw_diff(got, yaw) > YAW_SLACK:
                bad.append("faces %s, authored %d" % (got, yaw))
            if "1b" not in rc("data get entity %s Invulnerable" % one):
                bad.append("not Invulnerable")
            sp = rc("attribute %s minecraft:generic.movement_speed base get" % one)
            if _num(sp) not in (0.0,):
                bad.append("movement speed %r, not 0 (not pinned)" % sp[-40:])
        rc("forceload remove %d %d" % (x, z))
        out.append(("seat", tid, (x, y, z), "; ".join(bad)))
    return out


def spawners():
    """[(gym, leader id, (x, y, z), source)] from the gym building, else the interior record."""
    gi = json.loads((ROOT / "data" / "gym_interiors.json").read_text(encoding="utf-8"))
    built = {}
    for f in sorted((ROOT / "data" / "gym_buildings").glob("*.json")):
        d = json.loads(f.read_text(encoding="utf-8"))
        built[d["id"]] = (d["leader"]["id"], tuple(d["leader"]["spawner"]), "data/gym_buildings/%s" % f.name)
    out = []
    for gid in ["gym%d" % i for i in range(1, 9)]:
        if gid in built:
            lid, at, src = built[gid]
        else:
            ts = _interior_spawner(gi, gid)
            if not ts:
                out.append((gid, None, None, "no spawner position in data"))
                continue
            lid, at, src = ts["id"], tuple(ts["expect_spawner_at"]), "data/gym_interiors.json"
        out.append((gid, lid, at, src))
    return out


def _interior_spawner(doc, gid):
    def walk(o):
        if isinstance(o, dict):
            # a gym's record is keyed by its id, or carries it as `id`
            mine = o.get(gid) if isinstance(o.get(gid), dict) else (o if o.get("id") == gid else None)
            # the record's `leader` names the upstream id and where the template's spawner is expected
            if mine and isinstance(mine.get("leader"), dict) and mine["leader"].get("expect_spawner_at"):
                return mine["leader"]
            for v in o.values():
                r = walk(v)
                if r:
                    return r
        elif isinstance(o, list):
            for v in o:
                r = walk(v)
                if r:
                    return r
        return None
    return walk(doc)


def spawner_check(rc):
    out = []
    for gid, lid, at, src in spawners():
        if at is None:
            out.append(("spawner", gid, None, src))
            continue
        x, y, z = at
        _hold(rc, x, y, z)
        bad = []
        if "passed" not in rc("execute if block %d %d %d rctmod:trainer_spawner" % (x, y, z)):
            bad.append("no rctmod:trainer_spawner at %s (%s)" % (at, src))
        else:
            r = rc("data get block %d %d %d" % (x, y, z))
            if lid not in r:
                bad.append("spawner does not name %s: %s" % (lid, r[-120:]))
        rc("forceload remove %d %d" % (x, z))
        out.append(("spawner", "%s %s" % (gid, lid), at, "; ".join(bad)))
    return out


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--server-dir", default=os.environ.get("COBBLERS_SERVER_ROOT"),
                   help="the server directory; defaults to $COBBLERS_SERVER_ROOT (never a hard-coded runtime path)")
    p.add_argument("--out", help="write every row here; the console gets the verdict and the failures only")
    a = p.parse_args(argv)
    import reapply
    rc = reapply.Rcon(a.server_dir)
    rows = seats(rc) + spawner_check(rc)
    fails = [r for r in rows if r[3]]
    if a.out:
        Path(a.out).write_text("\n".join("%s\t%s\t%s\t%s" % (k, i, at, why or "ok") for k, i, at, why in rows) + "\n",
                               encoding="utf-8")
    print("%d of %d checked in the world; %d failed" % (len(rows) - len(fails), len(rows), len(fails)))
    for k, i, at, why in fails:
        print("  FAIL %s %s at %s: %s" % (k, i, at, why))
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main())
