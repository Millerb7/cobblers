#!/usr/bin/env python
"""Re-place donor structures that live only in an installed pack, from data/placements.json.

Brock's gym is Cobbleverse's own `cobbleverse:brock` template. Its licence forbids redistribution, so the .nbt is
never committed; but the pack that carries it is installed on the server, so the structure can be placed by resource
id and then have the campaign's block substitutions applied. That makes the placement reproducible from committed
data alone: the record here, plus data/spawn_block_policy.json.

A record is handled by this tool when it has `pack_template` (a resource id the server can already place):

  {"id": ..., "pack_template": "cobbleverse:brock", "position": {"x":…, "y":…, "z":…},
   "rotation": "180", "mirror": "none", "size": [27,17,24], "substitutions": "data/spawn_block_policy.json"}

  python tools/place_donor.py function [--out build/datapacks/cobblers_donor]
  python tools/place_donor.py verify --world <stopped world copy>

`function` writes one mcfunction per record: forceload, `place template`, then a `fill … replace` per substitution
(EXP-024 measured these counts as identical to the ones data/spawn_block_policy.json recorded for the hand-placed
gym). `verify` reads the saved chunks and reports the substituted block counts and the block entities in the box,
so a re-application can be checked without a player.
"""
from __future__ import annotations

import argparse
import os
import json
import sys
from collections import Counter
from pathlib import Path

import function_limits

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
DEFAULT_OUT = ROOT / "build" / "datapacks" / "cobblers_donor"
NS = "cobblers"


# The ground rule (tools/ground_rule.py): the functions here that read a world, each only to check, never to
# decide a position: `verify` reads a stopped world to check a donor stands; placement never does.
WORLD_READS = {'main', 'read_world'}


def records(placements_doc):
    return [p for p in placements_doc.get("placements") or [] if isinstance(p, dict) and p.get("pack_template")]


ROTATIONS = ("none", "clockwise_90", "180", "counterclockwise_90")
MIRRORS = ("none", "left_right", "front_back")


def transform(x, z, rot, mirror="none"):
    """StructureTemplate.transform with the pivot at the origin, as `/place template` uses it: mirror (LEFT_RIGHT
    negates z, FRONT_BACK negates x), then rotate about the placement position."""
    if rot not in ROTATIONS:
        raise SystemExit("unknown rotation %r" % rot)
    if mirror not in MIRRORS:
        raise SystemExit("unknown mirror %r" % mirror)
    if mirror == "left_right":
        z = -z
    elif mirror == "front_back":
        x = -x
    return {"none": (x, z), "clockwise_90": (-z, x), "180": (-x, -z), "counterclockwise_90": (z, -x)}[rot]


def turned_rect(x, z, size, rot, mirror="none"):
    """(x0, z0, x1, z1), the inclusive columns a template of `size` covers when `/place template` puts it at (x, z)
    with this rotation and mirror: turned ABOUT (x, z), so (x, z) is a min corner only when nothing turns."""
    sx, _sy, sz = size
    cells = [transform(tx, tz, rot, mirror) for tx in (0, sx - 1) for tz in (0, sz - 1)]
    return (x + min(c[0] for c in cells), z + min(c[1] for c in cells),
            x + max(c[0] for c in cells), z + max(c[1] for c in cells))


def footprint(rec, size):
    """(x0, z0, x1, z1), the inclusive columns a data/placements.json building occupies, as its placer seats it.

    The two placers anchor differently, and a footprint computed the other way lands on the wrong side of the origin:
      - a `pack_template` record (this tool) is `/place template` at its position, turned about that position;
      - a `file` record (tools/place_town.py) has its position at the building's minimum corner: place_town offsets
        the template's origin so the turned footprint starts there.
    `size` is the template's [x, y, z] as stored, before any turn."""
    import place_town
    x, z = int(rec["position"]["x"]), int(rec["position"]["z"])
    rot = rec.get("rotation") or "none"
    mirror = rec.get("mirror") or "none"
    if rec.get("pack_template"):
        return turned_rect(x, z, size, rot, mirror)
    if rec.get("file"):
        if mirror != "none":
            raise SystemExit("%s: place_town places no mirror, so a mirrored file record has no known footprint" % rec.get("id"))
        _mx, _mz, w, d = place_town.footprint(size, rot)
        return (x, z, x + w - 1, z + d - 1)
    raise SystemExit("%s: neither a pack_template nor a file, so no placer seats it and its footprint is unknown"
                     % rec.get("id"))


def template_size(rec, templates):
    """A placement's template size [x, y, z]: read from the template's NBT when `templates` (a
    tools/town_character.Templates) can find it, else the record's own `size`; (None, why) when neither. Both read
    and disagreeing is refused: the record's `size` would then be keeping a wrong area clear."""
    doc, where = templates.get(rec) if templates is not None else (None, "no template reader")
    read = [int(v) for v in doc["size"]] if doc is not None else None
    stored = [int(v) for v in rec["size"]] if rec.get("size") else None
    if read and stored and read != stored:
        raise SystemExit("%s: data/placements.json says size %s, but the template %s is %s"
                         % (rec.get("id"), stored, where, read))
    return (read or stored), (None if (read or stored) else where)


def box(rec):
    """Inclusive world box the template occupies, for the given rotation and mirror about its placement position."""
    x, y, z = (rec["position"][k] for k in "xyz")
    sy = rec["size"][1]
    x0, z0, x1, z1 = turned_rect(x, z, rec["size"], rec.get("rotation", "none"), rec.get("mirror", "none"))
    return (x0, y, z0), (x1, y + sy - 1, z1)


SETTLE = 20        # ticks between force-loading the box and placing, and between placing and checking
NATURAL = {"minecraft:" + b for b in ("dirt", "grass_block", "coarse_dirt", "podzol", "rooted_dirt", "mud", "stone",
                                      "andesite", "diorite", "granite", "deepslate", "tuff", "sand", "red_sand", "gravel",
                                      "clay", "water", "lava", "short_grass", "tall_grass", "moss_block")}


def sentinel(rec, template_doc, subs):
    """(x, y, z, block) in the world: a solid block of the template's lowest layer, near its middle, named as it will
    stand after the substitutions. The check step places the template again if this block is not there."""
    import place_town
    pal = template_doc["palette"]
    sx, _, sz = template_doc["size"]
    swap = {s["from"]: s["to"] for s in subs}
    cands = [(b["pos"], pal[b["state"]]["Name"]) for b in template_doc["blocks"]
             if pal[b["state"]]["Name"] not in ("minecraft:air", "minecraft:structure_void", "minecraft:cave_air", "minecraft:jigsaw")
             and not pal[b["state"]]["Name"].endswith(("_door", "_carpet", "_slab", "_stairs"))
             # a block the ground may already hold would pass the check with nothing placed
             and pal[b["state"]]["Name"] not in NATURAL]
    low = min(p[1] for p, _ in cands)
    (tx, ty, tz), name = min(((p, n) for p, n in cands if p[1] == low),
                             key=lambda q: (q[0][0] - sx / 2) ** 2 + (q[0][2] - sz / 2) ** 2)
    rx, rz = place_town.rotate(tx, tz, rec.get("rotation", "none"))
    return rec["position"]["x"] + rx, rec["position"]["y"] + ty, rec["position"]["z"] + rz, swap.get(name, name)


def own_substitutions(rec):
    """A record's own substitutions, when it lists them. Brock's and Misty's records carry the string
    "data/spawn_block_policy.json" there, a pointer to the policy rather than a list of their own."""
    subs = rec.get("substitutions")
    return list(subs) if isinstance(subs, list) else []


def load_template(server_dir, template_id):
    """A template from the installed packs, or from the server jar for a vanilla one (minecraft:...)."""
    import glob
    import zipfile
    import nbt
    import traders
    if template_id.startswith("minecraft:"):
        name = "data/minecraft/structure/%s.nbt" % template_id.split(":", 1)[1]
        for j in glob.glob(os.path.join(server_dir, "versions", "*", "*.jar")) + glob.glob(os.path.join(server_dir, "*.jar")):
            try:
                z = zipfile.ZipFile(j)
            except (zipfile.BadZipFile, OSError):  # not a readable jar
                continue
            if name in z.namelist():
                return nbt.loads(z.read(name))
        raise SystemExit("vanilla template not found in the server jar: %s" % template_id)
    return nbt.loads(traders.find_template(server_dir, template_id))


def loot_commands(rec, template_doc):
    """`data remove` for every container the template fills from a loot table, when the record asks for it: a
    pillager outpost's chest is crossbows and the like, which is not what a lookout keeps."""
    if not rec.get("clear_loot"):
        return []
    import place_town
    out = []
    for b in template_doc["blocks"]:
        if (b.get("nbt") or {}).get("LootTable"):
            tx, ty, tz = b["pos"]
            rx, rz = place_town.rotate(tx, tz, rec.get("rotation", "none"))
            out.append("data remove block %d %d %d LootTable" % (rec["position"]["x"] + rx, rec["position"]["y"] + ty,
                                                                   rec["position"]["z"] + rz))
    return out


def jigsaw_commands(rec, template_doc):
    """A `setblock` of its own final state for every jigsaw the template holds, when the record asks for it.

    `place template` leaves jigsaw blocks standing; worldgen would have resolved each into its final state. A bca
    building's jigsaws are its floor, its berry soil and its decoration points (final state planks, dirt, stone or
    nothing), so removing them all to air, as the watchtower's one jigsaw was, would hole the floor. This is what
    tools/place_town.py does for a house, and what tools/town_audit.py already expects to find."""
    if rec.get("jigsaws") != "final_state":
        return []
    import place_town
    own = {s["from"]: s["to"] for s in own_substitutions(rec)}
    own.update({b: "minecraft:air" for b in rec.get("remove_blocks") or []})
    out = []
    pal = template_doc["palette"]
    for b in template_doc["blocks"]:
        if pal[b["state"]]["Name"] != "minecraft:jigsaw":
            continue
        final = (b.get("nbt") or {}).get("final_state") or "minecraft:air"
        if final.split("[")[0] == "minecraft:structure_void":
            final = "minecraft:air"
        final = own.get(final.split("[")[0], final)
        tx, ty, tz = b["pos"]
        rx, rz = place_town.rotate(tx, tz, rec.get("rotation", "none"))
        out.append("setblock %d %d %d %s" % (rec["position"]["x"] + rx, rec["position"]["y"] + ty, rec["position"]["z"] + rz, final))
    return out


def load_box(rec, margin=16):
    """(x0, z0, x1, z1) to force-load before /place template: the rotated footprint the template is written into AND
    the unrotated extent (origin to origin + size). Vanilla's /place template refuses with "That position is not
    loaded" unless the unrotated extent is loaded, even though it writes the rotated one: the League turned
    clockwise_90 on the Rift's floor placed nothing in a whole staging run (2026-09-21), and the other rotated donors
    had worked only because their unrotated extents happened to be loaded by the town around them."""
    lo, hi = box(rec)
    x, z = rec["position"]["x"], rec["position"]["z"]
    sx, _, sz = rec.get("size") or [hi[0] - lo[0] + 1, 0, hi[2] - lo[2] + 1]
    return (min(lo[0], x) - margin, min(lo[2], z) - margin, max(hi[0], x + sx - 1) + margin, max(hi[2], z + sz - 1) + margin)


def functions(rec, subs, check=None, extra=None):
    """{function name: lines}. Force-load, wait SETTLE ticks, place and substitute, wait SETTLE ticks, and if the
    check block is missing place again, then release the box.

    Two of twenty pack-donor placements failed in full rebuilds of the disposable world on 2026-09-21 (Koga's gym
    in one run, Blaine's in the next) and none of ten failed when run on their own; the cause was not found. The
    wait and the check make the placement not depend on it, and tools/town_audit.py checks the result."""
    name = "place_%s" % rec["id"]
    fl = "%d %d %d %d" % load_box(rec)
    body = commands(rec, subs)
    body = [l for l in body if not l.startswith("forceload")] + list(extra or [])
    held = "# chunks-loaded-by: cobblers:structures/%s" % name
    out = {name: [body[0], "forceload add %s" % fl, "schedule function %s:structures/%s_go %dt replace" % (NS, name, SETTLE)],
           name + "_go": [held] + body[1:] + ["schedule function %s:structures/%s_check %dt replace" % (NS, name, SETTLE)]}
    chk = [held]
    if check:
        cx, cy, cz, blk = check
        chk.append("execute unless block %d %d %d %s run function %s:structures/%s_again" % (cx, cy, cz, blk, NS, name))
        out[name + "_again"] = [held, "# the check block was missing: place it again"] + body[1:]
    out[name + "_check"] = chk + ["forceload remove %s" % fl]
    return out


def command_rewrites(rec):
    """`data merge block` for each command block the record rewrites after the paste.

    The Necrozma towers ship a summit chain that spawns a level-80 Necrozma for whoever steps on the plate, then
    fills itself in: one spawn, for the whole server. Placed as shipped, a player below the cap would burn it on a
    Pokemon nobody can catch, so the records gate each link on our own Champion flag. `at` is template-relative and
    turned with the template; the command is authored in data/placements.json, never read from the template."""
    import place_town
    if rec.get("mirror", "none") != "none" and rec.get("set_commands"):
        raise SystemExit("%s: set_commands under a mirror is not supported" % rec["id"])
    out = []
    for c in rec.get("set_commands") or []:
        tx, ty, tz = c["at"]
        rx, rz = place_town.rotate(tx, tz, rec.get("rotation", "none"))
        out.append("data merge block %d %d %d {Command:%s}" % (rec["position"]["x"] + rx, rec["position"]["y"] + ty,
                                                              rec["position"]["z"] + rz,
                                                              json.dumps(c["command"], ensure_ascii=False)))
    return out


def data_removals(rec):
    """`data remove block` for each block-entity path the record strips after the paste.

    The Crown Spire's barrel ships the one lumymon:calyrex_crown in the game; left in, it hands a level-70 Calyrex to
    whoever finds the barrel first, under any cap, past the archivist's champion_cleared gate
    (data/research_station.json). `at` is template-relative and turned with the template, exactly as set_commands;
    `path` is an NBT path authored in data/placements.json, never read from the template."""
    import place_town
    if rec.get("mirror", "none") != "none" and rec.get("data_remove"):
        raise SystemExit("%s: data_remove under a mirror is not supported" % rec["id"])
    out = []
    for c in rec.get("data_remove") or []:
        tx, ty, tz = c["at"]
        rx, rz = place_town.rotate(tx, tz, rec.get("rotation", "none"))
        out.append("data remove block %d %d %d %s" % (rec["position"]["x"] + rx, rec["position"]["y"] + ty,
                                                       rec["position"]["z"] + rz, c["path"]))
    return out


def commands(rec, subs):
    x, y, z = (rec["position"][k] for k in "xyz")
    lo, hi = box(rec)
    out = ["# %s: %s at (%d, %d, %d) rotation %s" % (rec["id"], rec["pack_template"], x, y, z, rec.get("rotation", "none")),
           "forceload add %d %d %d %d" % load_box(rec),
           "place template %s %d %d %d %s %s 1.0 0" % (rec["pack_template"], x, y, z, rec.get("rotation", "none"), rec.get("mirror", "none"))]
    out += command_rewrites(rec)
    out += data_removals(rec)
    # /fill refuses more than 32,768 blocks, and it refuses the whole command rather than part of it.
    # Brock's gym is 11,016 and fitted; Misty's is 46,080 and every substitution silently did nothing
    # until this was split (found 2026-09-20 by place_donor.py verify, 958 blocks left unsubstituted).
    area = (hi[0] - lo[0] + 1) * (hi[2] - lo[2] + 1)
    layers = max(1, min(hi[1] - lo[1] + 1, 32768 // max(area, 1)))
    # the record's own changes after the policy's: blocks this one building must not carry (the League's red sand,
    # wool and lily pads, 2026-09-21), and blocks it must lose (the watchtower's ominous banners)
    own = own_substitutions(rec) + [{"from": b, "to": "minecraft:air"} for b in rec.get("remove_blocks") or []]
    for s in list(subs) + own:
        for y0 in range(lo[1], hi[1] + 1, layers):
            y1 = min(y0 + layers - 1, hi[1])
            out.append("fill %d %d %d %d %d %d %s replace %s"
                       % (lo[0], y0, lo[2], hi[0], y1, hi[2], s["to"], s["from"]))
    # A building that straddles a bank needs something under it, or the template's own ground shows as
    # a mound: Misty's gym stands with its back to the water and its floor at the promenade, so the
    # lake side is carried on a quay rather than on dirt.
    plinth = rec.get("plinth")
    if plinth:
        top = y - 1
        base = int(plinth.get("from_y", top - 8))
        material = plinth.get("material", "minecraft:stone_bricks")
        area = (hi[0] - lo[0] + 1) * (hi[2] - lo[2] + 1)
        layers = max(1, min(top - base + 1, 32768 // max(area, 1)))
        for y0 in range(base, top + 1, layers):
            y1 = min(y0 + layers - 1, top)
            for gone in ("minecraft:water", "minecraft:air"):
                out.append("fill %d %d %d %d %d %d %s replace %s"
                           % (lo[0], y0, lo[2], hi[0], y1, hi[2], material, gone))
    out.append("forceload remove %d %d %d %d" % load_box(rec))
    return out


def read_world(world, lo, hi):
    """(block name counts, block entity id counts) inside the inclusive box of a stopped world."""
    import structure_nbt as SN
    import nbt
    b = SN.capture(world, lo, hi)
    names = Counter(v[0] for v in b.blocks.values())
    bes = Counter()
    for rx in range(lo[0] >> 9, (hi[0] >> 9) + 1):
        for rz in range(lo[2] >> 9, (hi[2] >> 9) + 1):
            p = Path(world) / "region" / ("r.%d.%d.mca" % (rx, rz))
            if not p.is_file():
                continue
            for _, _, ch in nbt.region_chunks(p):
                for be in ch.get("block_entities") or []:
                    if lo[0] <= be.get("x", -1) <= hi[0] and lo[1] <= be.get("y", -1) <= hi[1] and lo[2] <= be.get("z", -1) <= hi[2]:
                        bes[be.get("id")] += 1
    return names, bes


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--placements", default=str(ROOT / "data" / "placements.json"))
    p.add_argument("--policy", default=str(ROOT / "data" / "spawn_block_policy.json"))
    sub = p.add_subparsers(dest="cmd", required=True)
    f = sub.add_parser("function")
    f.add_argument("--out", default=str(DEFAULT_OUT))
    f.add_argument("--server-dir", default=os.environ.get("COBBLERS_SERVER_ROOT"),
                   help="the server whose packs hold the templates, to choose each placement's check block; "
                        "without it the function places without checking")
    v = sub.add_parser("verify")
    v.add_argument("--world", required=True, help="a stopped world copy; the live world is refused")
    a = p.parse_args(argv)
    placements = json.loads(Path(a.placements).read_text(encoding="utf-8"))
    subs = json.loads(Path(a.policy).read_text(encoding="utf-8"))["substitutions"]
    recs = records(placements)
    if not recs:
        print("no pack_template placements")
        return 0
    if a.cmd == "function":
        out = Path(a.out)
        for rec in recs:
            check, extra = None, []
            if a.server_dir:
                _, tdoc = load_template(a.server_dir, rec["pack_template"])
                own = {s["from"]: s["to"] for s in own_substitutions(rec)}
                check = sentinel(rec, tdoc, list(subs) + [{"from": k, "to": v} for k, v in own.items()])
                extra = loot_commands(rec, tdoc) + jigsaw_commands(rec, tdoc)
            elif rec.get("clear_loot") or rec.get("jigsaws"):
                raise SystemExit("%s clears loot or resolves jigsaws, which needs --server-dir to read its template" % rec["id"])
            for name, lines_out in functions(rec, subs, check, extra).items():
                fn = out / "data" / NS / "function" / "structures" / ("%s.mcfunction" % name)
                fn.parent.mkdir(parents=True, exist_ok=True)
                refused = function_limits.check_lines(lines_out, str(fn))
                if refused:
                    for _n, _cmd, _why in refused:
                        print("REFUSED line %d: %s" % (_n, _why))
                        print("   %s" % _cmd)
                    raise SystemExit("%s: %d command(s) the server would refuse; not written" % (fn, len(refused)))
                fn.write_text("\n".join(lines_out) + "\n", encoding="utf-8", newline="\n")
            print("wrote place_%s%s" % (rec["id"], " (checked at %s)" % (check,) if check else " (no check block)"))
        (out / "pack.mcmeta").write_text(json.dumps({"pack": {"pack_format": 48, "description": "Cobblers donor structure placements (generated)"}}) + "\n", encoding="utf-8")
        return 0
    import runtime_guard
    runtime_guard.check(a.world, "read")
    bad = 0
    for rec in recs:
        lo, hi = box(rec)
        names, bes = read_world(a.world, lo, hi)
        print("== %s %s..%s" % (rec["id"], lo, hi))
        print("   non-air blocks", sum(names.values()), "block entities", sum(bes.values()), dict(bes))
        for s in subs:
            got, left = names.get(s["to"], 0), names.get(s["from"], 0)
            expected = (rec.get("expect_substituted") or {}).get(s["to"])
            state = "ok" if (expected is None or got == expected) and left == 0 else "MISMATCH"
            if state != "ok":
                bad += 1
            if got or left or expected:
                print("   %-46s %5d (expected %s), unsubstituted left %d  %s" % (s["to"], got, expected, left, state))
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
