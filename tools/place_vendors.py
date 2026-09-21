#!/usr/bin/env python
"""Put the traders on a town's plaza, as entities rather than as structures.

The shopkeeper donors are 1 by 2 by 1 templates holding one villager and one jigsaw block. Placing
them with /place template leaves the jigsaw standing on the pavement and, on the disposable world,
produced no villager at all. Reading the entity out of the template and summoning it directly gives
the trader with its own trade list, puts nothing else on the square, and can be re-run without
stacking anything: each summon is preceded by killing the trader already at that spot.

  python tools/place_vendors.py --out build/datapacks/cobblers_vendors
  then: /reload and /function cobblers:towns/vendors_<settlement>

Ownership: generated output under build/ (gitignored). The choice of who stands where is authored in
data/placements.json as kind "vendor"; this tool only translates.
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import re
import zipfile
from pathlib import Path

import function_limits
import nbt

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUT = ROOT / "build" / "datapacks" / "cobblers_vendors"
PAT = re.compile(r"data/([^/]+)/structure(?:s)?/(.+)\.nbt$")


def find_template(server_dir, template_id):
    """The raw nbt of a template the server can place, from a mod jar or a datapack."""
    ns, rel = template_id.split(":", 1)
    want = "data/%s/structure/%s.nbt" % (ns, rel)
    alt = "data/%s/structures/%s.nbt" % (ns, rel)
    sources = sorted(glob.glob(os.path.join(server_dir, "mods", "*.jar"))) + \
        sorted(glob.glob(os.path.join(server_dir, "datapacks", "*.zip")))
    for path in sources:
        try:
            z = zipfile.ZipFile(path)
        except Exception:
            continue
        for name in (want, alt):
            if name in z.namelist():
                return z.read(name)
    raise SystemExit("template not found in the installed packs: %s" % template_id)


def to_snbt(value):
    """NBT value -> the SNBT a command takes."""
    if isinstance(value, tuple) and len(value) == 2 and isinstance(value[0], int):
        tag, v = value
        return to_snbt(v)
    if isinstance(value, dict):
        return "{%s}" % ",".join('%s:%s' % (k, to_snbt(v)) for k, v in value.items())
    if isinstance(value, list):
        return "[%s]" % ",".join(to_snbt(v) for v in value)
    if isinstance(value, bool):
        return "1b" if value else "0b"
    if isinstance(value, float):
        return "%sf" % value
    if isinstance(value, int):
        return str(value)
    # SNBT has no unicode escape, and json.dumps writes one for any non-ASCII character: a
    # trader whose shop category is spelled with an accent stopped the whole function loading.
    text = str(value).replace(chr(92), chr(92) * 2).replace('"', chr(92) + '"')
    return '"%s"' % text


def surface_reader(surface_world):
    """(x, z) -> the Y of the top solid block in the built world.

    The world, not the heightmap: the plaza is paved at its graded level, which is a block above the
    terrain the heightmap records. A trader placed off the heightmap stands inside the pavement.
    """
    import numpy as np
    import world_heights as WH
    cache = {}

    def read(x, z):
        key = (x >> 6, z >> 6)
        if key not in cache:
            bx, bz = (x >> 6) << 6, (z >> 6) << 6
            g, _, _ = WH.extract(surface_world, (bx, bz, bx + 63, bz + 63))
            cache[key] = (bx, bz, g)
        bx, bz, g = cache[key]
        v = g[z - bz, x - bx]
        return int(v) if v > WH.NONE else None

    return read


def vendor_commands(rec, server_dir, surface=None):
    raw = find_template(server_dir, rec["pack_template"])
    _, root = nbt.loads(raw)
    entities = root.get("entities") or []
    if not entities:
        raise SystemExit("%s holds no entity to summon" % rec["pack_template"])
    ent = entities[0]
    data = dict(ent.get("nbt") or {})
    kind = data.pop("id", "minecraft:villager")
    # Keep what the trader is, drop what the engine owns. A copied UUID collides with the entity
    # already in the world on a re-run, Pos and Motion fight the summon's own coordinates, and the
    # whole brain and attribute block made the command 1,625 characters, over what RCON will carry.
    for engine_owned in ("UUID", "Pos", "Motion", "Rotation", "Brain", "attributes", "Attributes",
                         "HurtByTimestamp", "HurtTime", "DeathTime", "FallDistance", "FallFlying",
                         "PortalCooldown", "OnGround", "Air", "AbsorptionAmount", "fabric:attachments",
                         "cardinal_components", "Bukkit.updateLevel", "WorldUUIDLeast", "WorldUUIDMost"):
        data.pop(engine_owned, None)
    # stand them on the ground the heightmap records, not on the plaza's authored level: the paving
    # sits on the ground and the authored y is the level it was cut to, which is a block out here
    gy = rec["position"]["y"]
    if surface is not None:
        found = surface(rec["position"]["x"], rec["position"]["z"])
        if found is not None:
            gy = found + 1
    x, y, z = rec["position"]["x"] + 0.5, gy, rec["position"]["z"] + 0.5
    tag = "cobblers_vendor_%s" % rec["id"]
    data["Tags"] = [tag, "cobblers_vendor"]
    data["PersistenceRequired"] = True
    return [
        "# %s: %s" % (rec["id"], rec["pack_template"]),
        "forceload add %d %d" % (rec["position"]["x"], rec["position"]["z"]),
        "kill @e[tag=%s]" % tag,
        # the earlier attempt placed these as structures, which left the template's jigsaw standing.
        # setblock's third word is a mode, not a block to replace: that is fill's syntax, and getting
        # it wrong stops the whole function loading.
        "execute if block %d %d %d minecraft:jigsaw run setblock %d %d %d minecraft:air"
        % (rec["position"]["x"], rec["position"]["y"], rec["position"]["z"],
           rec["position"]["x"], rec["position"]["y"], rec["position"]["z"]),
        "execute if block %d %d %d minecraft:jigsaw run setblock %d %d %d minecraft:air"
        % (rec["position"]["x"], rec["position"]["y"] + 1, rec["position"]["z"],
           rec["position"]["x"], rec["position"]["y"] + 1, rec["position"]["z"]),
        "summon %s %.1f %d %.1f %s" % (str(kind).split("'")[-1] if "'" in str(kind) else kind, x, y, z, to_snbt(data)),
        "forceload remove %d %d" % (rec["position"]["x"], rec["position"]["z"]),
    ]


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--placements", default=str(ROOT / "data" / "placements.json"))
    p.add_argument("--server-dir", default=os.environ.get("COBBLERS_SERVER_ROOT"),
                   help="the server whose packs hold the shopkeeper templates; "
                        "defaults to $COBBLERS_SERVER_ROOT")
    p.add_argument("--surface-world", help="a STOPPED world copy, so traders stand on the paving that is there")
    p.add_argument("--out", default=str(DEFAULT_OUT))
    a = p.parse_args(argv)
    doc = json.loads(Path(a.placements).read_text(encoding="utf-8"))
    if not a.server_dir:
        raise SystemExit("no server directory: pass --server-dir, or set COBBLERS_SERVER_ROOT")
    surface = surface_reader(a.surface_world) if a.surface_world else None
    by_town = {}
    for rec in doc["placements"]:
        if rec.get("kind") == "vendor":
            by_town.setdefault(rec["settlement"], []).append(rec)
    out = Path(a.out)
    (out / "data" / "cobblers" / "function" / "towns").mkdir(parents=True, exist_ok=True)
    (out / "pack.mcmeta").write_text(json.dumps(
        {"pack": {"pack_format": 48, "description": "Cobblers town traders (generated)"}}, indent=2) + "\n",
        encoding="utf-8", newline="\n")
    for town, recs in sorted(by_town.items()):
        xs = [r["position"]["x"] for r in recs]
        zs = [r["position"]["z"] for r in recs]
        loader = ["# Generated by tools/place_vendors.py from data/placements.json",
                  "forceload add %d %d %d %d" % (min(xs) - 8, min(zs) - 8, max(xs) + 8, max(zs) + 8),
                  "schedule function cobblers:towns/vendors_%s_place 2t replace" % town]
        placer = ["# Generated by tools/place_vendors.py; called by cobblers:towns/vendors_%s" % town]
        for rec in sorted(recs, key=lambda q: q["id"]):
            placer += vendor_commands(rec, a.server_dir, surface)
        # The unload waits. Dropping the forceload in the same function as the summon unloads the
        # chunk before the entity is saved and the trader is gone again: that is why a summon that
        # worked by hand produced nothing from the function.
        placer.append("schedule function cobblers:towns/vendors_%s_done 100t replace" % town)
        done = ["# Generated by tools/place_vendors.py; releases the ground the traders were summoned on",
                "forceload remove %d %d %d %d" % (min(xs) - 8, min(zs) - 8, max(xs) + 8, max(zs) + 8)]
        for name, out_lines in (("vendors_%s" % town, loader), ("vendors_%s_place" % town, placer),
                                ("vendors_%s_done" % town, done)):
            refused = function_limits.check_lines(out_lines, name)
            if refused:
                raise SystemExit("%s: %d command(s) the server would refuse" % (name, len(refused)))
            f = out / "data" / "cobblers" / "function" / "towns" / ("%s.mcfunction" % name)
            f.write_text("\n".join(out_lines) + "\n", encoding="utf-8", newline="\n")
        print("wrote vendors_%s and its placer: %d traders" % (town, len(recs)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
