#!/usr/bin/env python
"""How big each gym leader's Pokemon are in the world, measured from the installed jars and datapacks.

The owner, 2026-10-08: "Big enough for the largest Pokemon on that leader's team, MEASURED." Cobblemon battles
happen in the world: both sides are sent out as entities into the room the battle starts in, so a room smaller
than the team's largest member puts it into the walls in the fight that matters most.

  python tools/pokemon_sizes.py [--snapshot <server snapshot dir>] [--write] [--markdown]

WHAT AN ENTITY'S SIZE IS (read from the 1.8.0 jar, not assumed; javap -c on the classes named):

  com.cobblemon.mod.common.entity.pokemon.PokemonEntity.getDimensions (obf. method_18377):
      scale = form.baseScale * pokemon.getEffectiveScale()      (or a MocKEffect's own scale, the Transform/
                                                                 Illusion mock, which no leader uses)
      dims  = exposedForm.hitbox.scale(scale), then .scale(LivingEntity.getScale())   (the vanilla generic.scale
                                                                 attribute, 1.0 unless something sets it)
  com.cobblemon.mod.common.pokemon.Pokemon.getEffectiveScale:
      level <= 1 or under babyPokemonLevelDuration -> a ramp from babyPokemonSizeMultiplier up to 1 (config:
      duration 9, multiplier 0.9); isAlpha -> the alpha multiplier; otherwise scaleModifier, default 1.0.
      Every leader's Pokemon is level 18 or more and none is alpha or carries a scale, so the factor is 1.0.

  So the hitbox a leader's Pokemon has in battle is hitbox.width * baseScale by hitbox.height * baseScale, for
  the form it is in. No leader's team names an aspect, a form, a mega stone, a Z-crystal or a Dynamax item
  (data/trainers.json, checked by this tool), so every member is in its base form.

  Dynamax (Mega Showdown): config/mega_showdown/config.json dynamax true, dynamaxScaleFactor 4.0,
  dynamaxAnywhere false, powerSpotRange 32: a Pokemon may Dynamax only within 32 blocks of a power spot. An
  arena more than 32 blocks from every power spot never sees one; this tool reports the factor and does not
  size for it.

THE RENDERED MODEL is not the hitbox. A wall clips the MODEL, and Onix's model is a long body over a 2 by 4
hitbox. So this tool also measures each member's bedrock model (assets/cobblemon/bedrock/pokemon/models,
through the species' resolver), in its bind pose, times the same scale. That figure is approximate: an animation
moves the bones, and the bind pose is only where they start. It is reported beside the hitbox, not instead of it.

WHERE THE DATA COMES FROM, every candidate, in load priority low to high: the Cobblemon jar, the other mod jars
that ship species or species_additions (zamega, Mega Showdown), then the COBBLEVERSE datapack. A world datapack
overrides a mod's file at the same path; between two mod jars the order is the loader's and not pinned, so the
DESIGN figure is the largest over every candidate, never one picked by an assumed order. Each figure carries the
archive and path it came from.

Writes data/gym_arena_sizes.json (--write), the table tools/gym_arenas.py sizes an arena against; nothing is
read from a world.
"""
from __future__ import annotations

import argparse
import glob
import json
import math
import os
import re
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "gym_arena_sizes.json"
TRAINERS = ROOT / "data" / "trainers.json"
GYM_TRAINERS = ROOT / "data" / "gym_trainers.json"

# the jars and packs that can carry species data (the snapshot was scanned for data/*/species*/ on 2026-10-08:
# only these four do)
ARCHIVES = (
    ("mods", "Cobblemon-fabric-*.jar"),
    ("mods", "zamega-fabric-*.jar"),
    ("mods", "mega_showdown-fabric-*.jar"),
    ("datapacks", "COBBLEVERSE-DP-v*.zip"),
)
CONFIG_MAIN = ("config", "cobblemon", "main.json")
CONFIG_MEGA = ("config", "mega_showdown", "config.json")
FORM_KEYS = ("aspects", "form", "forms", "mega", "dynamax", "gmax", "teraType", "scale", "gimmicks")


class SizeError(SystemExit):
    pass


def snapshot_dir(arg=None):
    """The server snapshot the jars come from: --snapshot, else COBBLERS_SERVER_SNAPSHOT, else the newest
    C:/Users/wnd/Documents/cobblers-local/server-snapshot-*."""
    cands = [arg, os.environ.get("COBBLERS_SERVER_SNAPSHOT")] + sorted(
        glob.glob("C:/Users/wnd/Documents/cobblers-local/server-snapshot-*"), reverse=True)
    for c in cands:
        if c and Path(c, "mods").is_dir():
            return Path(c)
    raise SizeError("no server snapshot with a mods/ folder: pass --snapshot (fail closed; nothing is guessed)")


def archives(snap):
    out = []
    for sub, pat in ARCHIVES:
        hits = sorted(glob.glob(str(snap / sub / pat)))
        if not hits:
            raise SizeError("%s/%s: not found in %s" % (sub, pat, snap))
        out.append(Path(hits[-1]))
    return out


# --------------------------------------------------------------------------------------------- the leaders
def gimmick_items(arcs):
    """Every item Mega Showdown adds (its assets/mega_showdown/models/item/*.json): mega stones, Z-crystals, the
    Dynamax band, form items. A leader's Pokemon holding one may change form or size; none does (2026-10-08)."""
    ms = [a for a in arcs if a.name.startswith("mega_showdown")]
    z = zipfile.ZipFile(ms[0])
    return {n.rsplit("/", 1)[1][:-5] for n in z.namelist()
            if n.startswith("assets/mega_showdown/models/item/") and n.endswith(".json")}


def leader_teams(gimmicks=frozenset()):
    """{leader record id: {"upstream": id, "members": {species: [tier, ...]}}} over EVERY tier: the record's
    team, each modes.<tier>.team, and the rct payload's team (which is what rctmod is given)."""
    recs = {r["id"]: r for r in json.loads(TRAINERS.read_text(encoding="utf-8"))["trainers"]}
    gyms = json.loads(GYM_TRAINERS.read_text(encoding="utf-8"))["trainers"]
    out = {}
    for g in gyms:
        r = recs.get(g["id"])
        if r is None:
            raise SizeError("data/gym_trainers.json names %s, which data/trainers.json does not have" % g["id"])
        teams = [("team", r.get("team") or [])]
        for tier, m in sorted((r.get("modes") or {}).items()):
            teams.append((tier, m.get("team") or []))
            rct = m.get("rct") or {}
            if rct.get("team"):
                teams.append((tier + ".rct", rct["team"]))
        teams.append(("rct", (r.get("rct") or {}).get("team") or []))
        members = {}
        for tier, team in teams:
            for m in team:
                odd = sorted(k for k in m if k in FORM_KEYS)
                item = (m.get("heldItem") or "").split(":")[-1]
                if odd or item in gimmicks:
                    raise SizeError("%s %s %s carries %s / item %r: a form or gimmick this tool does not size "
                                    "(teach it the form before trusting the table)" % (g["id"], tier, m["species"],
                                                                                        odd, item))
                members.setdefault(m["species"], set()).add(tier)
        out[g["id"]] = {"upstream": g["upstream_trainer_id"], "order": g["order"],
                        "name": r.get("display_name"),
                        "members": {s: sorted(t) for s, t in sorted(members.items())}}
    return out


# ------------------------------------------------------------------------------------------- species data
def species_index(arcs):
    """{species: [candidate, ...]} where a candidate is {archive, path, hitbox, baseScale, kind}."""
    out = {}
    for arc in arcs:
        z = zipfile.ZipFile(arc)
        for n in z.namelist():
            m = re.match(r"data/cobblemon/(species|species_additions)/(?:.+/)?([a-z0-9_\-]+)\.json$", n)
            if not m:
                continue
            try:
                d = json.loads(z.read(n).decode("utf-8-sig"))
            except ValueError:
                continue
            if m.group(1) == "species":
                name = m.group(2)
            else:
                t = d.get("target") or ""
                name = t.split(":")[-1] if t else None
                if not name:
                    continue
            if "hitbox" not in d and "baseScale" not in d:
                continue
            out.setdefault(name, []).append({"archive": arc.name, "path": n, "kind": m.group(1),
                                             "hitbox": d.get("hitbox"), "baseScale": d.get("baseScale")})
    return out


def resolve(species, cands):
    """The base form's hitbox and scale per candidate, and the design figure: the largest over every candidate.
    An addition that sets only one of the two fields inherits the other from the base species file."""
    base = [c for c in cands if c["kind"] == "species" and c["hitbox"]]
    if not base:
        # a species file without the fields takes the constructor's defaults (com.cobblemon.mod.common.pokemon.
        # Species.<init>: baseScale = 1.0F; hitbox = EntityDimensions method_18385(1.0F, 1.0F)); pawmot is one
        base = [{"archive": "Cobblemon jar", "path": "Species.<init> defaults (no hitbox in the species file)",
                 "kind": "species", "hitbox": {"width": 1.0, "height": 1.0}, "baseScale": 1.0}]
        cands = base + list(cands)
    rows = []
    for c in cands:
        hb = c["hitbox"] or base[0]["hitbox"]
        sc = c["baseScale"] if c["baseScale"] is not None else (base[0]["baseScale"] if base[0]["baseScale"]
                                                                  is not None else 1.0)
        rows.append({"archive": c["archive"], "path": c["path"], "width": float(hb["width"]),
                     "height": float(hb["height"]), "baseScale": float(sc),
                     "world_width": round(float(hb["width"]) * float(sc), 3),
                     "world_height": round(float(hb["height"]) * float(sc), 3)})
    return rows


# ---------------------------------------------------------------------------------------- the bedrock model
def _rot(r):
    """Bedrock euler degrees -> 3x3, applied X then Y then Z (Blockbench's bedrock order)."""
    ax, ay, az = (math.radians(v) for v in r)
    cx, sx, cy, sy, cz, sz = math.cos(ax), math.sin(ax), math.cos(ay), math.sin(ay), math.cos(az), math.sin(az)
    rx = [[1, 0, 0], [0, cx, -sx], [0, sx, cx]]
    ry = [[cy, 0, sy], [0, 1, 0], [-sy, 0, cy]]
    rz = [[cz, -sz, 0], [sz, cz, 0], [0, 0, 1]]
    return _mm(rz, _mm(ry, rx))


def _mm(a, b):
    return [[sum(a[i][k] * b[k][j] for k in range(3)) for j in range(3)] for i in range(3)]


def _apply(t, p):
    (m, o) = t
    return [sum(m[i][k] * p[k] for k in range(3)) + o[i] for i in range(3)]


def _compose(outer, inner):
    (m1, o1), (m2, o2) = outer, inner
    return (_mm(m1, m2), _apply(outer, o2))


def _about(pivot, rot):
    """translate(pivot) . R . translate(-pivot)"""
    m = _rot(rot)
    o = [pivot[i] - sum(m[i][k] * pivot[k] for k in range(3)) for i in range(3)]
    return (m, o)


IDENT = ([[1, 0, 0], [0, 1, 0], [0, 0, 1]], [0, 0, 0])


def model_extent(z, model_id):
    """(x, y_min, y_max, z) in blocks at scale 1 of a geo model's cubes in its bind pose, or None."""
    ns, path = model_id.split(":", 1) if ":" in model_id else ("cobblemon", model_id)
    want = "/" + path + ".json"
    hits = [n for n in z.namelist() if n.startswith("assets/%s/bedrock/pokemon/models/" % ns) and n.endswith(want)]
    if not hits:
        return None
    g = json.loads(z.read(hits[0]).decode("utf-8-sig"))
    geo = (g.get("minecraft:geometry") or [None])[0]
    if not geo:
        return None
    bones = {b["name"]: b for b in geo.get("bones", [])}
    memo = {}

    def bone_t(name):
        if name in memo:
            return memo[name]
        b = bones[name]
        t = _about(b.get("pivot", [0, 0, 0]), b.get("rotation", [0, 0, 0]))
        if b.get("parent") in bones:
            t = _compose(bone_t(b["parent"]), t)
        memo[name] = t
        return t

    pts = []
    for name, b in bones.items():
        for c in b.get("cubes", []) or []:
            o, s = c["origin"], c["size"]
            inf = c.get("inflate", 0)
            t = bone_t(name)
            if c.get("rotation"):
                t = _compose(t, _about(c.get("pivot", [0, 0, 0]), c["rotation"]))
            for dx in (0, 1):
                for dy in (0, 1):
                    for dz in (0, 1):
                        p = [o[0] - inf + dx * (s[0] + 2 * inf), o[1] - inf + dy * (s[1] + 2 * inf),
                             o[2] - inf + dz * (s[2] + 2 * inf)]
                        pts.append(_apply(t, p))
    if not pts:
        return None
    xs, ys, zs = zip(*pts)
    reach = max(math.hypot(p[0], p[2]) for p in pts)
    return (round((max(xs) - min(xs)) / 16, 2), round(min(ys) / 16, 2), round(max(ys) / 16, 2),
            round((max(zs) - min(zs)) / 16, 2), hits[0], round(reach / 16, 2),
            [round(v / 16, 2) for v in (min(xs), max(xs), min(zs), max(zs))])


def model_of(z, species):
    """The base variation's model id from the species' resolver(s) in the Cobblemon jar."""
    for n in z.namelist():
        if "/bedrock/pokemon/resolvers/" not in n or not n.endswith(".json"):
            continue
        if not re.search(r"/\d+_%s/" % re.escape(species), n):
            continue
        d = json.loads(z.read(n).decode("utf-8-sig"))
        if d.get("species", "").split(":")[-1] != species:
            continue
        for v in d.get("variations", []):
            if not v.get("aspects") and v.get("model"):
                return v["model"]
    return None


# ------------------------------------------------------------------------------------------------- the table
def measure(snap):
    arcs = archives(snap)
    idx = species_index(arcs)
    cob = zipfile.ZipFile(arcs[0])
    main = json.loads((snap.joinpath(*CONFIG_MAIN)).read_text(encoding="utf-8"))
    mega = json.loads((snap.joinpath(*CONFIG_MEGA)).read_text(encoding="utf-8"))
    leaders = leader_teams(gimmick_items(arcs))
    out = {}
    for lid, L in leaders.items():
        rows = []
        for sp, tiers in L["members"].items():
            cands = resolve(sp, idx.get(sp, []))
            w = max(cands, key=lambda c: c["world_width"])
            h = max(cands, key=lambda c: c["world_height"])
            mid = model_of(cob, sp)
            ext = model_extent(cob, mid) if mid else None
            scale_for_model = max(c["baseScale"] for c in cands)
            row = {"species": sp, "tiers": tiers, "candidates": cands,
                   "design_width": w["world_width"], "width_from": "%s %s" % (w["archive"], w["path"]),
                   "design_height": h["world_height"], "height_from": "%s %s" % (h["archive"], h["path"])}
            if ext:
                row["model"] = {"id": mid, "path": ext[4], "x": round(ext[0] * scale_for_model, 2),
                                "y_top": round(ext[2] * scale_for_model, 2),
                                "y_bottom": round(ext[1] * scale_for_model, 2),
                                "z": round(ext[3] * scale_for_model, 2),
                                "reach": round(ext[5] * scale_for_model, 2),
                                "x_min_max_z_min_max": [round(v * scale_for_model, 2) for v in ext[6]],
                                "note": "bind pose, cubes only, times the largest baseScale; approximate. reach = "
                                        "the farthest any cube corner lies from the entity's origin, "
                                        "horizontally: the radius it sweeps turning on the spot"}
            # the radius the arena keeps clear round this Pokemon's marker: its model's reach where a model is in
            # the server's archives, never less than the hitbox's half-diagonal (a turned square)
            # rounded UP to the hundredth: a clearance rounded down is a clearance shaved
            row["clear_radius"] = math.ceil(100 * max(row["model"]["reach"] if row.get("model") else 0.0,
                                                      w["world_width"] / math.sqrt(2)) - 1e-9) / 100.0
            row["clear_radius_from"] = ("model reach" if row.get("model") and row["model"]["reach"] >=
                                        w["world_width"] / math.sqrt(2) else "hitbox half-diagonal"
                                        + ("" if row.get("model") else " (no model in any server archive: a "
                                                                       "client resource pack draws it)"))
            row["clear_height"] = round(max(h["world_height"], row["model"]["y_top"] if row.get("model") else 0.0), 2)
            rows.append(row)
        bw = max(rows, key=lambda r: (r["design_width"], r["species"]))
        bh = max(rows, key=lambda r: (r["design_height"], r["species"]))
        mods = [r for r in rows if r.get("model")]
        bm = max(mods, key=lambda r: max(r["model"]["x"], r["model"]["z"])) if mods else None
        bmh = max(mods, key=lambda r: r["model"]["y_top"]) if mods else None
        cr = max(rows, key=lambda r: (r["clear_radius"], r["species"]))
        ch = max(rows, key=lambda r: (r["clear_height"], r["species"]))
        out[lid] = {"upstream": L["upstream"], "order": L["order"], "name": L["name"], "members": rows,
                    "design": {"clear_radius": cr["clear_radius"], "clear_radius_species": cr["species"],
                               "clear_radius_from": cr["clear_radius_from"],
                               "clear_height": ch["clear_height"], "clear_height_species": ch["species"]},
                    "largest_by_width": {"species": bw["species"], "width": bw["design_width"],
                                         "from": bw["width_from"]},
                    "largest_by_height": {"species": bh["species"], "height": bh["design_height"],
                                          "from": bh["height_from"]},
                    "largest_model_horizontal": ({"species": bm["species"],
                                                  "extent": max(bm["model"]["x"], bm["model"]["z"]),
                                                  "from": bm["model"]["path"]} if bm else None),
                    "largest_model_height": ({"species": bmh["species"], "y_top": bmh["model"]["y_top"],
                                              "from": bmh["model"]["path"]} if bmh else None)}
    return {
        "schema": "gym_arena_sizes/1",
        "generated_by": "tools/pokemon_sizes.py --write (from the jars; do not hand-edit)",
        "snapshot": snap.name,
        "archives": [a.name for a in arcs],
        "scale_rule": ("PokemonEntity.getDimensions (method_18377): hitbox.scale(form.baseScale * "
                       "Pokemon.getEffectiveScale()).scale(LivingEntity.getScale()); getEffectiveScale is 1.0 at "
                       "level >= babyPokemonLevelDuration for a non-alpha Pokemon with scaleModifier 1.0"),
        "config": {"babyPokemonLevelDuration": main.get("babyPokemonLevelDuration"),
                   "babyPokemonSizeMultiplier": main.get("babyPokemonSizeMultiplier"),
                   "dynamax": mega.get("dynamax"), "dynamaxAnywhere": mega.get("dynamaxAnywhere"),
                   "dynamaxScaleFactor": mega.get("dynamaxScaleFactor"),
                   "powerSpotRange": mega.get("powerSpotRange")},
        "leaders": out,
    }


def check_levels(doc):
    """Every member's level is past the baby ramp, so the effective scale is 1.0 (the table assumes it)."""
    dur = doc["config"]["babyPokemonLevelDuration"]
    recs = {r["id"]: r for r in json.loads(TRAINERS.read_text(encoding="utf-8"))["trainers"]}
    low = []
    for lid in doc["leaders"]:
        r = recs[lid]
        for tier, team in [("team", r.get("team") or [])] + [(t, m.get("team") or [])
                                                                for t, m in (r.get("modes") or {}).items()]:
            low += ["%s %s %s L%d" % (lid, tier, m["species"], m["level"]) for m in team if m["level"] < dur]
    if low:
        raise SizeError("members under babyPokemonLevelDuration %s are scaled down: %s" % (dur, low))


def markdown(doc):
    lines = ["| Gym | Leader | Widest hitbox (w x scale) | Tallest hitbox (h x scale) | Largest model, bind pose "
             "(extent / top) | Clear radius (sweep) | Clear height | Members over all tiers |",
             "|---|---|---|---|---|---|---|---|"]
    for lid, L in sorted(doc["leaders"].items(), key=lambda kv: kv[1]["order"]):
        mw, mh, d = L["largest_model_horizontal"], L["largest_model_height"], L["design"]
        lines.append("| %d | %s | %s %.2f | %s %.2f | %s %.1f / %s %.1f | %s %.2f | %s %.2f | %s |" % (
            L["order"], L["name"], L["largest_by_width"]["species"], L["largest_by_width"]["width"],
            L["largest_by_height"]["species"], L["largest_by_height"]["height"],
            mw["species"] if mw else "-", mw["extent"] if mw else 0, mh["species"] if mh else "-",
            mh["y_top"] if mh else 0, d["clear_radius_species"], d["clear_radius"], d["clear_height_species"],
            d["clear_height"], ", ".join(m["species"] for m in L["members"])))
    return "\n".join(lines)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--snapshot", default=None)
    p.add_argument("--write", action="store_true", help="write data/gym_arena_sizes.json")
    p.add_argument("--markdown", action="store_true", help="print the table as markdown")
    a = p.parse_args(argv)
    doc = measure(snapshot_dir(a.snapshot))
    check_levels(doc)
    if a.write:
        OUT.write_text(json.dumps(doc, indent=1) + "\n", encoding="utf-8")
        print("wrote", OUT.relative_to(ROOT))
    if a.markdown:
        print(markdown(doc))
    else:
        for lid, L in sorted(doc["leaders"].items(), key=lambda kv: kv[1]["order"]):
            print("%-16s widest %-11s %.2f  tallest %-11s %.2f" % (
                lid, L["largest_by_width"]["species"], L["largest_by_width"]["width"],
                L["largest_by_height"]["species"], L["largest_by_height"]["height"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
