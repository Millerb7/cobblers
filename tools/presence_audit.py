#!/usr/bin/env python
"""Is it STANDING? Over RCON, for the things that were reported built and that the owner has not seen.

  python tools/presence_audit.py [--server-dir DIR] [--only arena,gulch,dens,relic,extra] [--out FILE]

Needs the server lock (tools/runtime_guard.py, through reapply.Rcon). Reads the world to CHECK, never to decide.

Written 2026-10-02 because four things were reported built or decided and the owner believed none of them was in the
world: the gulch's Mega mine and its seven open-air dens, Hoopa's relic site moved underground, Heaven's Arena, and the
Deep in general. Each answer is one of: never built, built and never applied, applied to a world since deleted, or
present. A repository cannot tell those apart; only the world can, so this asks the world.

What each check expects comes from the authored record or the build's own plan, never from the world:

  arena   data/deep_city.json `arena` (tiers, crown, radius) and the computed centre and stands in
          derived/deep_city/plan.json (the centre is computed by tools/deep_city.py and recorded nowhere else). Per tier:
          a floor under the stand, air at the stand's feet and head, the drum's wall at the radius. The crown floor and
          the beacon. One rctmod:trainer at each stand (the seven champions, R17).
  gulch   data/gulch_mine.json: the square paved at its surface_y, the adit's posts and open mouth, air in the Tally
          Hall and the Cutting Floor, the grille's iron bars, the three Cutters, the two hall Megas, and six of the
          cove's 69 buildings (their wall block somewhere up the rect's corner column).
  dens    data/gulch_mine.json `farms[].dens` and the mine's two hall slots: each den's chunk is held, its keeper
          driven three times from the console (the tick drives it only while a PLAYER is inside the den's approach
          box, 128 square and anchor-24 to anchor+32, so a player flying over higher never sees a den spawn), then
          its Megas counted: a mine slot's one by its own tag; a farm den's PACK (pack_size, 3 since 2026-10-05) by
          the den's tag (expected the pack size) and by each member's tag <den>_m<k> (expected 1 each). A wrong count
          is reported WITH the short members' clock scores (gm.gone, gm.resp, #now gm.t) and any player within
          `megas.spawn_clear`, which blocks a spawn by design.
          This WRITES: it spawns any Mega that is due. Staging only.
  relic   the superseded surface (the ring on its plinth, the cordon's gate: tools/relic_surface_superseded.py
          old_record, the old build's own record, since the capped derived/deep_city/plan.json carries neither) and
          the underground hall (data/relic_underground.json). Before R9RU: surface present, hall solid. After: the
          reverse.
  extra   data/world_probes.json: per-place probes the builders of 2026-10-02 named (block or entity), so the new
          southern places are checked by the same runner.

NOT covered: the Deep's 196 buildings block by block (`tools/deep_city.py verify --world`, which reads the saved
world), the Rift's gatehouses (re-run R9Z: its fixes landed after the 2026-10-01 apply), trainers' seats
(`tools/trainer_world_audit.py`), and whether a Pokemon RENDERS (a client fact: someone has to look).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))


def _passed(reply):
    return "passed" in (reply or "")


def _hold(rc, x, y, z, settle=2):
    rc("forceload add %d %d" % (x, z))
    for _ in range(30):
        if _passed(rc("execute if loaded %d %d %d" % (x, y, z))):
            break
        time.sleep(1)
    time.sleep(settle)                     # a chunk's entities load after its blocks


def _free(rc, x, z):
    rc("forceload remove %d %d" % (x, z))


def _count(rc, sel):
    r = rc("execute if entity %s" % sel)
    if "count:" in (r or ""):
        return int(r.rsplit(":", 1)[1].strip())
    return 0


def _block(rc, x, y, z, want):
    """want: a block id, '!air' (anything but air) or 'air'."""
    if want == "!air":
        return not _passed(rc("execute if block %d %d %d minecraft:air" % (x, y, z)))
    return _passed(rc("execute if block %d %d %d %s" % (x, y, z, want)))


def _plan():
    p = ROOT / "derived" / "deep_city" / "plan.json"
    if not p.exists():
        raise SystemExit("presence_audit: %s is missing; run tools/deep_city.py (or prepare) first" % p)
    return json.loads(p.read_text(encoding="utf-8"))


def arena(rc):
    rec = json.loads((ROOT / "data" / "deep_city.json").read_text(encoding="utf-8"))["arena"]
    a = _plan()["arena"]
    cx, cz = a["centre"]
    out = []
    if [t["y"] for t in a["tiers"]] != rec["tiers"]:
        out.append(("arena", "plan", (cx, cz), "the plan's tiers %s are not the record's %s"
                    % ([t["y"] for t in a["tiers"]], rec["tiers"])))
    _hold(rc, cx, 64, cz)
    retired = {r["tier"] for r in json.loads((ROOT / "data" / "arena_trainers.json").read_text(encoding="utf-8"))["trainers"]
               if r.get("seated") is False}
    for t in a["tiers"]:
        sx, sy, sz = t["stand"]
        # the drum's radius at this tier's walls: the halls layout steps in at its setbacks (data/deep_city.json taper)
        r = rec["radius"]
        for ty, tr in sorted(rec.get("taper") or []):
            if t["y"] + 4 > ty:
                r = tr
        checks = [((sx, sy - 1, sz), "!air", "floor under the stand"),
                  ((sx, sy, sz), "minecraft:air", "air at the stand's feet"),
                  ((sx, sy + 1, sz), "minecraft:air", "air at the stand's head")]
        wall = [(cx + r, t["y"] + 4, cz), (cx - r, t["y"] + 4, cz), (cx, t["y"] + 4, cz + r), (cx, t["y"] + 4, cz - r)]
        bad = [why for (p, want, why) in checks if not _block(rc, *p, want)]
        if not any(_block(rc, *p, "!air") for p in wall):
            bad.append("no drum wall at radius %d" % r)
        n = _count(rc, "@e[type=rctmod:trainer,x=%d,y=%d,z=%d,distance=..2]" % (sx, sy, sz))
        # the hub's champions were retired 2026-10-03 (the owner: "remove the trainer battles, have the middle just be
        # hubs"; data/arena_trainers.json seated false): a retired tier's stand must now be EMPTY
        want = 0 if t["tier"] in retired else 1
        if n != want:
            bad.append("%d trainers at the stand, expected %d" % (n, want))
        out.append(("arena", "tier %d (y%d)" % (t["tier"], t["y"]), (sx, sy, sz), "; ".join(bad)))
    crown = rec["crown"]
    # the crown's own deck, at the crown's y (it read y crown-1 until 2026-10-03: the ring layout's tier-7 air, which
    # is why one of its four points was always "open")
    ring = [(cx + 8, crown, cz), (cx - 8, crown, cz), (cx, crown, cz + 8), (cx, crown, cz - 8)]
    out.append(("arena", "crown floor y%d" % crown, (cx, crown, cz),
                "" if all(_block(rc, *p, "!air") for p in ring) else "a crown floor point is air"))
    bx, by, bz = a["beacon"]
    out.append(("arena", "beacon", (bx, by, bz), "" if _block(rc, bx, by, bz, "minecraft:beacon") else "no beacon"))
    _free(rc, cx, cz)
    return out


def gulch(rc):
    d = json.loads((ROOT / "data" / "gulch_mine.json").read_text(encoding="utf-8"))
    out = []
    sq = d["town"]["square"]
    x0, z0 = sq["rect"][0] + 4, sq["rect"][1] + 4
    _hold(rc, x0, sq["surface_y"], z0)
    ok = _block(rc, x0, sq["surface_y"], z0, "!air") and _block(rc, x0, sq["surface_y"] + 2, z0, "minecraft:air")
    out.append(("gulch", "the Cutters' square paved", (x0, sq["surface_y"], z0), "" if ok else "not paved, or not clear"))
    po = d["mine"]["portal"]
    (px, pz), y0 = po["posts"][0], po["y"][0]
    mx = (po["posts"][0][0] + po["posts"][1][0]) // 2
    _hold(rc, mx, y0, pz)
    ok = _block(rc, px, y0 + 1, pz, "!air") and _block(rc, mx, y0 + 1, pz, "minecraft:air")
    out.append(("gulch", "the adit's mouth", (mx, y0 + 1, pz), "" if ok else "post missing or mouth not open"))
    for h in d["mine"]["halls"]:
        hx, hz = h["centre"]
        _hold(rc, hx, h["feet"], hz)
        ok = _block(rc, hx, h["feet"] + 1, hz, "minecraft:air") and _block(rc, hx, h["feet"] - 1, hz, "!air")
        out.append(("gulch", h["id"], (hx, h["feet"] + 1, hz), "" if ok else "not carved (no air over a floor)"))
        _free(rc, hx, hz)
    g = d["gate"]["grille"]
    gx, gz, gy = g["x"], g["z"][0] + 1, g["y"][0] + 1
    _hold(rc, gx, gy, gz)
    out.append(("gulch", "the grille", (gx, gy, gz), "" if _block(rc, gx, gy, gz, "minecraft:iron_bars") else "no bars"))
    _free(rc, gx, gz)
    b = d["cutters"]["benches"][0]["at"]
    _hold(rc, *b)
    n = _count(rc, "@e[type=minecraft:villager,tag=%s,x=%d,y=%d,z=%d,distance=..40]" % (d["cutters"]["tag"], *b))
    want = len(d["cutters"]["benches"])
    out.append(("gulch", "the Cutters", tuple(b), "" if n == want else "%d cutters, expected %d" % (n, want)))
    bs = d["cove"]["buildings"]
    for bld in bs[:: max(1, len(bs) // 6)][:6]:
        if "walls" not in bld:
            continue
        x, z = bld["rect"][0], bld["rect"][1]
        _hold(rc, x, 90, z, settle=0)
        hit = any(_block(rc, x, y, z, bld["walls"]) for y in range(84, 104))
        out.append(("gulch", "cove " + bld["id"], (x, None, z), "" if hit else "no %s in the corner column" % bld["walls"]))
        _free(rc, x, z)
    _free(rc, x0, z0)
    _free(rc, mx, pz)
    _free(rc, b[0], b[2])
    return out


def dens(rc, wait):
    d = json.loads((ROOT / "data" / "gulch_mine.json").read_text(encoding="utf-8"))
    tag = d["megas"]["tag"]
    # A mine slot holds one Mega, kept under the slot's own id. A farm den holds a PACK (the owner, 2026-10-05:
    # mega_field.layout.pack_size, or the den's own pack_size; tools/gulch_mine.py pack_homes, commit cd64bea): member
    # k is <den>_m<k>, with its own tag, keeper and clock (#<den>_m<k> gm.gone); every member also carries the den's
    # tag. So a den is expected to hold its pack size under the den's tag and exactly one under each member's tag, and
    # its clocks are the members' -- a den-level #<den> gm.gone is never written for a pack and reads "Can't get value".
    # (Before this, the probe expected 1 under the den's tag and read #<den> gm.gone: N50/U57's "2-3 Megas, clock
    # unset" was a pack read by a single-Mega probe.)
    pack_default = ((d.get("mega_field") or {}).get("layout") or {}).get("pack_size", 1)
    rows = [(s["id"], s["anchor"][0], None, s["anchor"][1], "mine", [s["id"]]) for s in d["megas"]["slots"]]
    for f in d.get("farms", []):
        for den in f["dens"]:
            x, y, z = den["anchor"]
            n = den.get("pack_size", pack_default)
            mids = ["%s_m%d" % (den["id"], k + 1) for k in range(n)] if n > 1 else [den["id"]]
            rows.append((den["id"], x, y, z, f["id"], mids))
    out = []
    for did, x, y, z, where, mids in rows:
        y = 64 if y is None else y
        _hold(rc, x, y, z, settle=wait)
        # The tick runs a den's keeper (drive_<farm>) only while a PLAYER stands in its approach box (128 square,
        # anchor-24 to anchor+32), so a held chunk with nobody in it never spawns its Mega. Drive it as the tick
        # would: the keeper waits for two absent passes before it counts the Mega gone, then spawns it.
        for _ in range(3):
            rc("execute store result score #now gm.t run time query gametime")
            rc("function cobblers:gulch_mine/drive_%s" % where)
            time.sleep(1)
        time.sleep(wait)
        n = _count(rc, "@e[type=cobblemon:pokemon,tag=%s.%s]" % (tag, did))
        per = {m: (n if m == did else _count(rc, "@e[type=cobblemon:pokemon,tag=%s.%s]" % (tag, m))) for m in mids}
        why = ""
        if n != len(mids) or any(c != 1 for c in per.values()):
            sc = {m: {k: rc("scoreboard players get #%s %s" % (m, k)) for k in ("gm.gone", "gm.resp")}
                  for m, c in per.items() if c != 1}
            sc["now"] = rc("scoreboard players get #now gm.t")
            near = _count(rc, "@a[x=%d,y=%d,z=%d,distance=..%d]" % (x, y, z, d["megas"]["spawn_clear"]))
            why = "%d Megas under the den's tag (expected %d); per member %s (expected 1 each); player within " \
                  "spawn_clear: %d; clock %s" % (n, len(mids), per, near, sc)
        out.append(("dens", "%s (%s)" % (did, where), (x, y, z), why))
        _free(rc, x, z)
    return out


def relic(rc, source_root=None):
    # Where the old ring and cordon stood comes from the SUPERSEDED generator's own record
    # (tools/relic_surface_superseded.py old_record, the old build kept verbatim), never from derived/deep_city/plan.json:
    # since data/deep_city.json relic_area.capped (2026-10-02) the current build writes no ring or cordon and its plan
    # records neither, which crashed this probe with KeyError 'ring'. The hall is data/relic_underground.json's.
    import relic_surface_superseded as S
    from terrain import env_source_root
    sr = source_root or env_source_root()
    if not sr:
        raise SystemExit("presence_audit relic: needs --source-root or COBBLERS_SOURCE_ROOT (the old ring's height "
                         "comes from the heightmap, as the old build took it)")
    r = S.old_record(sr)
    u = json.loads((ROOT / "data" / "relic_underground.json").read_text(encoding="utf-8"))
    out = []
    cx, ry, cz = r["ring"]["centre"]
    rad = r["ring"]["radius"]
    _hold(rc, cx, ry, cz)
    pts = [(cx + rad, ry, cz), (cx - rad, ry, cz), (cx, ry + rad, cz), (cx, ry, cz + rad), (cx, ry, cz - rad)]
    ring = sum(_block(rc, *p, "!air") for p in pts)
    gx, gz = r["cordon"]["gate"][0]
    cordon = any(_block(rc, gx, y, gz, b) for y in range(80, 100)
                 for b in ("minecraft:tinted_glass", "minecraft:iron_bars"))
    out.append(("relic", "superseded surface ring (%d of %d points solid)" % (ring, len(pts)), (cx, ry, cz),
                "the surface ring still stands" if ring else ""))
    out.append(("relic", "superseded cordon at its gate", (gx, None, gz), "the cordon still stands" if cordon else ""))
    hall = u["geometry"]["hall"]
    hc, hf = hall["centre"], hall["floor_y"]
    _hold(rc, hc[0], hf, hc[1])
    ok = _block(rc, hc[0], hf + 2, hc[1], "minecraft:air") and _block(rc, hc[0], hf - 1, hc[1], "!air")
    out.append(("relic", "the underground hall", (hc[0], hf + 2, hc[1]), "" if ok else "not carved"))
    _free(rc, hc[0], hc[1])
    _free(rc, cx, cz)
    return out


def extra(rc):
    p = ROOT / "data" / "world_probes.json"
    if not p.exists():
        return []
    out = []
    for place, probes in json.loads(p.read_text(encoding="utf-8"))["places"].items():
        for pr in probes:
            if "block" in pr:
                x, y, z, want = pr["block"]
                _hold(rc, x, y, z, settle=0)
                ok = _block(rc, x, y, z, want) == pr.get("expect", True)
                out.append((place, pr["what"], (x, y, z), "" if ok else "expected %s%s"
                            % ("" if pr.get("expect", True) else "NOT ", want)))
            else:
                x, y, z = pr["hold"]
                _hold(rc, x, y, z)
                n = _count(rc, pr["entity"])
                out.append((place, pr["what"], (x, y, z), "" if n == pr["count"] else "%d, expected %d" % (n, pr["count"])))
            _free(rc, x, z)
    return out


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--server-dir", default=os.environ.get("COBBLERS_SERVER_ROOT"),
                   help="the server directory; defaults to $COBBLERS_SERVER_ROOT (never a hard-coded runtime path)")
    p.add_argument("--only", default="arena,gulch,dens,relic,extra")
    p.add_argument("--den-wait", type=int, default=6, help="seconds to let a den's keeper run after its chunk loads")
    p.add_argument("--source-root", default=None, help="the heightmap root for the relic probe; defaults to "
                                                       "COBBLERS_SOURCE_ROOT (tools/terrain.py env_source_root)")
    p.add_argument("--out", help="write every row here; the console gets the verdict and the failures only")
    a = p.parse_args(argv)
    import reapply
    rc = reapply.Rcon(a.server_dir)
    want = a.only.split(",")
    rows = []
    for name, fn in (("arena", arena), ("gulch", gulch), ("dens", lambda r: dens(r, a.den_wait)),
                     ("relic", lambda r: relic(r, a.source_root)), ("extra", extra)):
        if name in want:
            rows += fn(rc)
    fails = [r for r in rows if r[3]]
    if a.out:
        Path(a.out).write_text("\n".join("%s\t%s\t%s\t%s" % (k, i, at, why or "ok") for k, i, at, why in rows) + "\n",
                               encoding="utf-8")
    print("%d of %d present in the world; %d not" % (len(rows) - len(fails), len(rows), len(fails)))
    for k, i, at, why in fails:
        print("  NOT %s %s at %s: %s" % (k, i, at, why))
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main())
