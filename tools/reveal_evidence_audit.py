#!/usr/bin/env python
"""Independent audit of the mainline reveal's evidence displays: the BUILT pack, not the plan.

Reads the function files tools/reveal_evidence.py emitted (build/datapacks/cobblers_reveal_evidence) and checks
every block they write against sources the builder does not take its own expectation from. It never imports
tools/reveal_evidence.py: what is checked is the text a server would run.

  who tells it     data/quests.json main_worldshift_reveal dialogue_ids -> data/dialogue.json npc_id; the seat is
                   that NPC's record in data/npc_seats.json
  how far          data/reveal_evidence.json `about`: the prop TWO blocks to one side of the teller, on its line, the
                   sign against the prop. So the prop is 2 off the seat on one axis and 0 on the other, more to the
                   side than in front, the sign one block from the prop, no block on the seat's own column or the
                   3x3 round it, none more than 3 from the seat (2 + the sign's 1)
  the walked line  data/route_paths.json, exact point-to-segment distance computed here; a column the line passes
                   through (within half a column's diagonal, 0.71) FAILS; under 3.0 is REPORTED
  ground           the plaza's square (derived/plaza_centres/<town>.json) where the column is in it, else the gym
                   lot's level (data/gym_buildings/gym*.json site.lot_rect / lot_level) where it is in that lot,
                   else tools/ground.py's heightmap, rounded here from the raw heights array. The support block is
                   the y below the lowest block written; it must equal that ground
  what is there    derived/towns/<town>_plan.json street cells, lots, building anchors and lamps;
                   derived/plaza_centres/<town>.json pieces' columns; data/gym_buildings parts (fills and setblocks)
                   and footprint; every other seat's column. A display block on any of them FAILS: the write guard
                   would skip it at runtime and the display would silently not appear, or it stands in the road
  footprint        data/reveal_evidence.json: one prop column of len(prop) blocks stacked, one sign; a write anywhere
                   else, a block state the data does not name, or a removal of any other position FAILS
  guards           a placement only into #minecraft:replaceable over a non-replaceable block (or over the prop's own
                   lower block); a removal only of the exact id this display places there, while its sign stands
  sign text        the built sign's four messages equal the data's lines, and carry the content words the quest
                   record's own description names (QUEST_TERMS: each term is checked to occur in the quest record)
  spawn blocks     data/spawn_blocks.json: a display block a spawn condition names is a problem only if
                   data/spawn_block_policy.json's whitelist does not cover it; the owner's 2026-10-05 ALLOW decision
                   is recorded and not enforced, so this is REPORTED, never a failure

What it does NOT cover: the runtime result (the guards decide at run time; a flower or a slab already standing on a
display column makes the display silently not appear, and only a world probe shows that); whatever a template, the
town dressing or a later build places on these columns that is not in the derived plans named above; and whether the
sign is legible from where a player stands. It checks the pack as emitted; `reapply.py` prepare must run it after job
`reveal_evidence`.

  python tools/reveal_evidence_audit.py [--pack DIR] [--source-root DIR]     exit 1 on any FAIL
"""
from __future__ import annotations

import argparse
import json
import math
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))

DEFAULT_PACK = ROOT / "build" / "datapacks" / "cobblers_reveal_evidence"
FN_DIR = Path("data") / "cobblers" / "function" / "reveal_evidence"
QUEST_ID = "main_worldshift_reveal"
STATED_LATERAL = 2        # data/reveal_evidence.json about: "two blocks to one side of its teller"
ON_LINE = math.sqrt(2) / 2  # a line passing through a column passes within half its diagonal of the centre
ROUTE_REPORT = 3.0        # closer than this is reported (tools/npc_seats.py keeps seats 4+ off; not a failure here)
WORLD_READS: set = set()  # the ground rule: nothing here reads a world

# Content words each sign must carry, read by hand from the quest record's description (data/quests.json
# main_worldshift_reveal physical_evidence). tests/test_reveal_evidence_audit.py checks every term occurs in that
# record, so the table cannot drift from the quest into words of its own.
QUEST_TERMS = {
    "brock_boundary_sample": ["shale", "soil"],
    "misty_refugee_ledger": ["ledger", "famil"],
    "surge_signal_record": ["signal", "record", "correct"],
    "erika_exchange_survey_ledger": ["survey", "ledger", "summit"],
    "koga_recovered_anchor": ["anchor", "drift", "plate", "ring", "hoopa"],
    "sabrina_convergence_table": ["water", "memory", "signal", "peak"],
    "blaine_occupied_destination_model": ["destination", "roads", "homes", "life", "warning"],
    "giovanni_dissenter_route_packet": ["route", "packet", "loyalist", "rift"],
}


def _json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


# ---------------------------------------------------------------- inputs

def heightmap(source_root=None):
    """(x, z) -> the heightmap's ground Y, rounded here from tools/ground.py's raw heights."""
    import numpy as np
    import ground as G
    g = G.Ground(source_root)
    h, ox, oz = g.heights, g.ox, g.oz

    def at(x, z):
        return int(np.round(float(h[int(z) - oz, int(x) - ox])))
    return at


def load_inputs(root=ROOT, source_root=None, ground=None):
    """Everything the audit reads, as plain data (a synthetic fixture passes the same shape)."""
    root = Path(root)
    data = root / "data"
    quest = next(q for q in _json(data / "quests.json")["quests"] if q["id"] == QUEST_ID)
    convs = {c["id"]: c for c in _json(data / "dialogue.json")["conversations"]}
    seats = {s["id"]: s for s in _json(data / "npc_seats.json")["seats"]}
    towns = {}
    for s in seats.values():
        t = s.get("settlement")
        if not t or t in towns:
            continue
        pc, pl = root / "derived" / "plaza_centres" / ("%s.json" % t), root / "derived" / "towns" / ("%s_plan.json" % t)
        towns[t] = {"plaza_centres": _json(pc) if pc.exists() else None, "plan": _json(pl) if pl.exists() else None}
    gyms = [_json(p) for p in sorted((data / "gym_buildings").glob("gym*.json"))]
    policy = _json(data / "spawn_block_policy.json")
    return {
        "doc": _json(data / "reveal_evidence.json"),
        "quest": quest,
        "tellers": {cid: convs[cid]["npc_id"] for cid in quest.get("dialogue_ids") or [] if cid in convs},
        "seats": seats,
        "paths": _json(data / "route_paths.json")["paths"],
        "towns": towns,
        "gyms": gyms,
        "spawn_blocks": set(_json(data / "spawn_blocks.json")["blocks"]),
        "whitelist": policy.get("whitelist") or [],
        "ground": ground if ground is not None else heightmap(source_root),
    }


# ---------------------------------------------------------------- the built function, parsed

CMD = re.compile(r"^execute (?P<conds>.*?) run setblock (?P<x>-?\d+) (?P<y>-?\d+) (?P<z>-?\d+) (?P<state>\S.*)$")
COND = re.compile(r"(if|unless) block (-?\d+) (-?\d+) (-?\d+) (\S+)")


def base(state):
    return state.split("[")[0].split("{")[0]


def parse_function(text):
    """[{pos, state, conds}] for every command; a line that is not a guarded setblock is kept as raw."""
    out = []
    for line in text.splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        m = CMD.match(s)
        if not m:
            out.append({"raw": s})
            continue
        conds = [(k, (int(x), int(y), int(z)), b) for k, x, y, z, b in COND.findall(m.group("conds"))]
        out.append({"pos": (int(m.group("x")), int(m.group("y")), int(m.group("z"))), "state": m.group("state"),
                    "conds": conds, "raw": s})
    return out


def sign_lines(state):
    m = re.search(r"messages:\[(.*)\]\}\}$", state)
    if not m:
        return None
    return [json.loads(t.replace("\\'", "'")) for t in re.findall(r"'((?:\\'|[^'])*)'", m.group(1))]


# ---------------------------------------------------------------- geometry

def seg_distance(p, a, b):
    """Distance from p to the segment a-b (written here, not taken from the builder)."""
    (px, pz), (ax, az), (bx, bz) = p, a, b
    vx, vz, wx, wz = bx - ax, bz - az, px - ax, pz - az
    vv = vx * vx + vz * vz
    if vv == 0:
        return math.hypot(wx, wz)
    t = (wx * vx + wz * vz) / vv
    t = 0.0 if t < 0 else 1.0 if t > 1 else t
    return math.hypot(px - (ax + t * vx), pz - (az + t * vz))


def route_nearest(x, z, paths):
    best, which = float("inf"), None
    for name, pts in paths.items():
        legs = list(zip(pts, pts[1:])) or [(pts[0], pts[0])]
        for a, b in legs:
            d = seg_distance((x, z), a, b)
            if d < best:
                best, which = d, name
    return best, which


def yaw_vector(yaw):
    """Minecraft yaw: 0 faces +z (south), 90 faces -x (west)."""
    r = math.radians(yaw)
    return -math.sin(r), math.cos(r)


def in_rect(x, z, r, pad=0):
    x0, z0, x1, z1 = r
    return min(x0, x1) - pad <= x <= max(x0, x1) + pad and min(z0, z1) - pad <= z <= max(z0, z1) + pad


# ---------------------------------------------------------------- what the plans say is on a column

def town_ground(x, z, settlement, inputs):
    """(ground y, source) for a column by the plans, else the heightmap."""
    town = inputs["towns"].get(settlement) or {}
    pc = town.get("plaza_centres")
    if pc and in_rect(x, z, pc["square"]["rect"]):
        return pc["square"]["y"], "plaza_centres square"
    for gb in inputs["gyms"]:
        site = gb.get("site") or {}
        if gb.get("settlement") == settlement and site.get("lot_rect") and in_rect(x, z, site["lot_rect"]):
            return site["lot_level"], "%s lot_level" % gb.get("id")
    return inputs["ground"](x, z), "heightmap"


def occupants(x, y, z, settlement, inputs, own_seat):
    """What a plan or another system puts on this column (or this exact block, for gym parts)."""
    hits = []
    town = inputs["towns"].get(settlement) or {}
    plan, pc = town.get("plan"), town.get("plaza_centres")
    if plan:
        for sid, st in (plan.get("streets") or {}).items():
            for cz, _cy, cx0, cx1 in st.get("cells") or []:
                if cz == z and cx0 <= x <= cx1:
                    hits.append("street %s" % sid)
                    break
        for lot in plan.get("lots") or []:
            if in_rect(x, z, lot["rect"]):
                hits.append("lot %s" % lot.get("id"))
        gym_ids = {gb.get("settlement") for gb in inputs["gyms"]}
        for an in plan.get("anchors") or []:
            # a gym's anchor rect is its whole lot (forecourt included): its building is checked by footprint below
            if an.get("rect") and not (an.get("role") == "gym" and settlement in gym_ids) and in_rect(x, z, an["rect"]):
                hits.append("anchor %s" % an.get("id"))
        for lamp in plan.get("lamps") or []:
            if (lamp["at"][0], lamp["at"][2]) == (x, z):
                hits.append("lamp on %s" % lamp.get("street"))
    if pc:
        for piece in pc.get("pieces") or []:
            if [x, z] in [list(c) for c in piece.get("columns") or []]:
                hits.append("plaza piece %s" % piece.get("id"))
            elif any((b[0], b[2]) == (x, z) for b in piece.get("blocks") or []):
                hits.append("plaza piece %s" % piece.get("id"))
    for gb in inputs["gyms"]:
        if gb.get("settlement") != settlement:
            continue
        fp = gb.get("footprint")
        if fp and in_rect(x, z, fp):
            hits.append("%s building footprint" % gb.get("id"))
        for part in gb.get("parts") or []:
            if part.get("op") == "fill" and part.get("box"):
                bx0, by0, bz0, bx1, by1, bz1 = part["box"]
                if min(bx0, bx1) <= x <= max(bx0, bx1) and min(by0, by1) <= y <= max(by0, by1) \
                        and min(bz0, bz1) <= z <= max(bz0, bz1) and part.get("block") != "minecraft:air":
                    hits.append("%s part %s (%s)" % (gb.get("id"), part.get("block"), part.get("why", "")[:40]))
            elif part.get("pos") and tuple(part["pos"]) == (x, y, z) and part.get("block") != "minecraft:air":
                hits.append("%s part %s (%s)" % (gb.get("id"), part.get("block"), part.get("why", "")[:40]))
    for sid, s in inputs["seats"].items():
        if sid != own_seat and (s["at"][0], s["at"][2]) == (x, z):
            hits.append("seat %s" % sid)
    return hits


def gym_support(x, y, z, settlement, inputs):
    """True when a gym part lays a solid block at (x, y, z): positive evidence of a lot's support."""
    for gb in inputs["gyms"]:
        if gb.get("settlement") != settlement:
            continue
        for part in gb.get("parts") or []:
            if part.get("op") == "fill" and part.get("box") and part.get("block") != "minecraft:air":
                bx0, by0, bz0, bx1, by1, bz1 = part["box"]
                if min(bx0, bx1) <= x <= max(bx0, bx1) and min(by0, by1) <= y <= max(by0, by1) \
                        and min(bz0, bz1) <= z <= max(bz0, bz1):
                    return True
    return False


# ---------------------------------------------------------------- the audit

def _state_pattern(spec):
    return re.compile("^" + re.escape(spec).replace(re.escape("$facing"), "(north|south|east|west)") + "$")


def whitelisted(block, entries):
    """A whitelist entry covers this pack only if it names it (scopes are prose naming one place each)."""
    for e in entries:
        if block in (e.get("blocks") or []) and "reveal_evidence" in (e.get("scope") or ""):
            return True
    return False


def audit(pack_dir, inputs):
    """{"problems": [...], "reports": [...], "rows": [...]}; a problem is a failure, a report is not."""
    pack_dir = Path(pack_dir)
    problems, reports, rows = [], [], []
    doc, quest = inputs["doc"], inputs["quest"]
    evidence = {e["id"]: e for e in quest.get("physical_evidence") or []}
    fdir = pack_dir / FN_DIR
    built = {p.stem for p in fdir.glob("*.mcfunction")} if fdir.exists() else set()
    want = {d["beat"] for d in doc["displays"]}
    if not fdir.exists():
        problems.append("no built pack at %s (run tools/reveal_evidence.py build)" % fdir)
    for extra in sorted(built - want):
        problems.append("%s: a built function no display in data/reveal_evidence.json declares" % extra)

    for d in doc["displays"]:
        beat, ev = d["beat"], d["evidence"]
        tag = "%s (%s)" % (beat, ev)
        f = fdir / ("%s.mcfunction" % beat)
        if not f.exists():
            problems.append("%s: no built function %s" % (tag, f.name))
            continue
        cmds = parse_function(f.read_text(encoding="utf-8"))

        # --- who tells it
        if ev not in evidence:
            problems.append("%s: evidence id is not in data/quests.json %s physical_evidence" % (tag, QUEST_ID))
        tellers = {n for cid, n in inputs["tellers"].items() if cid.startswith("dlg_main_%s_" % beat)}
        if tellers != {d["teller"]}:
            problems.append("%s: teller %s, but the quest's dialogue for beat %s is spoken by %s"
                            % (tag, d["teller"], beat, sorted(tellers) or "nobody"))
        seat = inputs["seats"].get(d["teller"])
        if seat is None:
            problems.append("%s: teller %s has no seat in data/npc_seats.json" % (tag, d["teller"]))
            continue
        sx, sy, sz = seat["at"]
        settlement = seat.get("settlement")
        site = (evidence.get(ev) or {}).get("site") or ""
        named = re.findall(r"\b(gym\d_town|hometown|league)\b", site)
        if named and settlement not in named:
            problems.append("%s: the quest puts it at %r; its teller sits in %s" % (tag, site, settlement))
        elif not named and site:
            reports.append("%s: the quest's site is %r; the display stands beside %s in %s on %s ground"
                           % (tag, site, d["teller"], settlement, seat["ground"]["kind"]))

        # --- footprint: what the data declares this display writes
        unknown = [c["raw"] for c in cmds if "pos" not in c]
        for u in unknown:
            problems.append("%s: a command that is not a guarded setblock: %s" % (tag, u[:90]))
        places = [c for c in cmds if "pos" in c and base(c["state"]) != "minecraft:air"]
        removes = [c for c in cmds if "pos" in c and base(c["state"]) == "minecraft:air"]
        signs = [c for c in places if base(c["state"]).endswith("_sign")]
        props = sorted((c for c in places if c not in signs), key=lambda c: c["pos"][1])
        wood = doc.get("sign_wood", "spruce")
        if len(signs) != 1 or base(signs[0]["state"]) != "minecraft:%s_sign" % wood:
            problems.append("%s: %d sign placements (want one minecraft:%s_sign)" % (tag, len(signs), wood))
            continue
        sign = signs[0]
        if len(props) != len(d["prop"]):
            problems.append("%s: %d prop blocks written, the data declares %d" % (tag, len(props), len(d["prop"])))
            continue
        for c, spec in zip(props, d["prop"]):
            if not _state_pattern(spec).match(c["state"]):
                problems.append("%s: writes %s at %s; the data declares %s" % (tag, c["state"], c["pos"], spec))
        px, py, pz = props[0]["pos"]
        for i, c in enumerate(props):
            if c["pos"] != (px, py + i, pz):
                problems.append("%s: prop block %d at %s is not stacked on %s" % (tag, i, c["pos"], (px, py, pz)))
        declared = {c["pos"] for c in props} | {sign["pos"]}
        for c in removes:
            if c["pos"] not in declared:
                problems.append("%s: removes a block at %s, outside its own footprint %s"
                                % (tag, c["pos"], sorted(declared)))
        if len(places) != len(declared):
            problems.append("%s: writes the same position twice" % tag)

        # --- guards
        placed_at = {c["pos"]: base(c["state"]) for c in places}
        for c in places:
            x, y, z = c["pos"]
            here = any(k == "if" and p == (x, y, z) and b == "#minecraft:replaceable" for k, p, b in c["conds"])
            below = any((k == "unless" and p == (x, y - 1, z) and b == "#minecraft:replaceable")
                        or (k == "if" and p == (x, y - 1, z) and placed_at.get(p) == b) for k, p, b in c["conds"])
            if not here:
                problems.append("%s: places %s at %s without checking the block is replaceable"
                                % (tag, base(c["state"]), c["pos"]))
            if not below:
                problems.append("%s: places %s at %s without checking what it stands on"
                                % (tag, base(c["state"]), c["pos"]))
        for c in removes:
            own = any(k == "if" and p == c["pos"] and b == placed_at.get(c["pos"]) for k, p, b in c["conds"])
            if not own:
                problems.append("%s: removes %s without matching its own block there" % (tag, c["pos"]))

        # --- how far from the teller
        ox, oz = px - sx, pz - sz
        fx, fz = yaw_vector(seat["yaw"])
        if sorted((abs(ox), abs(oz))) != [0, STATED_LATERAL]:
            problems.append("%s: prop at (%d, %d) is offset (%+d, %+d) from %s's seat (%d, %d); the data states %d "
                            "to one side" % (tag, px, pz, ox, oz, d["teller"], sx, sz, STATED_LATERAL))
        else:
            ahead, aside = ox * fx + oz * fz, ox * fz - oz * fx
            if abs(ahead) > abs(aside) + 1e-9:
                problems.append("%s: prop at (%d, %d) stands %s %s (yaw %s), not to its side"
                                % (tag, px, pz, "in front of" if ahead > 0 else "behind", d["teller"], seat["yaw"]))
            elif abs(ahead) > 1e-9:
                reports.append("%s: %s faces diagonally (yaw %s); the prop stands 45 degrees %s its side"
                               % (tag, d["teller"], seat["yaw"], "ahead of" if ahead > 0 else "behind"))
            side = "right" if aside < 0 else "left"
            if d.get("side") and side != d["side"]:
                reports.append("%s: stands on the teller's %s; the data asks for %s" % (tag, side, d["side"]))
        gx, gy, gz = sign["pos"]
        if abs(gx - px) + abs(gz - pz) != 1:
            problems.append("%s: sign (%d, %d) does not stand against its prop (%d, %d)" % (tag, gx, gz, px, pz))
        elif abs(ahead_sign := (gx - px) * fx + (gz - pz) * fz) < 0.5:
            reports.append("%s: sign (%d, %d) stands beside the prop on the teller's line, not in front of it as "
                           "the data's about says" % (tag, gx, gz))
        elif ahead_sign < 0:
            problems.append("%s: sign (%d, %d) stands behind its prop, away from the side %s faces"
                            % (tag, gx, gz, d["teller"]))
        for (x, y, z) in declared:
            cheb = max(abs(x - sx), abs(z - sz))
            if cheb <= 1:
                problems.append("%s: block (%d, %d, %d) is on %s's seat or the 3x3 round it" % (tag, x, y, z, d["teller"]))
            if cheb > STATED_LATERAL + 1:
                problems.append("%s: block (%d, %d, %d) is %d from the seat, beyond the stated %d + 1"
                                % (tag, x, y, z, cheb, STATED_LATERAL))

        # --- the walked line, ground, what is there
        cols = {(px, pz): py, (gx, gz): gy}
        route_min, ground_src = [], set()
        for (x, z), y in cols.items():
            dist, name = route_nearest(x, z, inputs["paths"])
            route_min.append(dist)
            if dist <= ON_LINE:
                problems.append("%s: column (%d, %d) is ON walked line %s (%.2f)" % (tag, x, z, name, dist))
            elif dist < ROUTE_REPORT:
                reports.append("%s: column (%d, %d) is %.2f from walked line %s" % (tag, x, z, dist, name))
            want_y, src = town_ground(x, z, settlement, inputs)
            ground_src.add("%s y%d" % (src, want_y))
            if y - 1 != want_y:
                problems.append("%s: column (%d, %d) stands on y%d; %s ground there is y%d"
                                % (tag, x, z, y - 1, src, want_y))
            if src.endswith("lot_level") and not gym_support(x, want_y, z, settlement, inputs):
                problems.append("%s: column (%d, %d) on %s has no gym part laying its y%d" % (tag, x, z, src, want_y))
            if (inputs["towns"].get(settlement) or {}).get("plan") is None and settlement:
                problems.append("%s: no derived/towns/%s_plan.json to check the column against" % (tag, settlement))
            for yy in sorted({c[1] for c in declared if (c[0], c[2]) == (x, z)}):
                for hit in occupants(x, yy, z, settlement, inputs, d["teller"]):
                    problems.append("%s: block (%d, %d, %d) is on %s" % (tag, x, yy, z, hit))

        # --- sign text
        got = sign_lines(sign["state"])
        if got != (list(d["sign"]) + ["", "", "", ""])[:4]:
            problems.append("%s: the built sign reads %s; the data says %s" % (tag, got, d["sign"]))
        text = " ".join(got or []).lower()
        for term in QUEST_TERMS.get(ev, []):
            if term not in text:
                problems.append("%s: the sign never says %r, which the quest's description of %s carries"
                                % (tag, term, ev))
        if ev not in QUEST_TERMS:
            problems.append("%s: no quest terms recorded for this evidence (add them to QUEST_TERMS)" % tag)

        # --- spawn-condition blocks: reported, never failed (the owner's ALLOW, 2026-10-05)
        for c in places:
            b = base(c["state"])
            if b in inputs["spawn_blocks"] and not whitelisted(b, inputs["whitelist"]):
                reports.append("%s: %s at %s is a spawn-condition block no whitelist entry covers here "
                               "(owner ALLOW 2026-10-05: reported, not failed)" % (tag, b, c["pos"]))
        rows.append({"beat": beat, "prop": (px, py, pz), "sign": (gx, gy, gz), "seat": (sx, sy, sz),
                     "route": round(min(route_min), 2), "ground": sorted(ground_src)})
    return {"problems": problems, "reports": reports, "rows": rows}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--pack", default=str(DEFAULT_PACK))
    ap.add_argument("--source-root", default=None)
    a = ap.parse_args(argv)
    r = audit(a.pack, load_inputs(source_root=a.source_root))
    for row in r["rows"]:
        print("%-9s prop %s sign %s seat %s route %.2f ground %s" % (
            row["beat"], row["prop"], row["sign"], row["seat"], row["route"], ", ".join(row["ground"])))
    for line in r["reports"]:
        print("REPORT " + line)
    for line in r["problems"]:
        print("PROBLEM " + line)
    print("reveal_evidence_audit: %s -- %d displays, %d problems, %d reports"
          % ("FAIL" if r["problems"] else "PASS", len(r["rows"]), len(r["problems"]), len(r["reports"])))
    return 1 if r["problems"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
