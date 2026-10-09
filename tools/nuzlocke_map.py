#!/usr/bin/env python
"""An annotated Nuzlocke region map: one self-contained HTML page from the repo's data and the compiled spawn pack.

The owner, 2026-10-05: "can you make me an annotated region map for a nuzlocke, try to have 4-6 mon encounters per
gym, have towns labeled and the main path highlighted".

Every fact on the page is read, never invented:
  base map        the canonical heightmap (tools/ground.py), shaded at 1 px per --scale blocks; water is
                  tools/water_mask.py's rule (ground below data/world.json's sea level, or inside a landmark's
                  basin_polygons below its level_y); the 1024-block cell grid from data/cells.json
  towns           data/towns.json, at data/plaza_centres.json's square centre where a town has one (towns.json's
                  Pacifidlog centre is stale, REVIEW 58; its plaza square is the real site)
  gyms            data/gym_buildings/gym<N>.json leader.spawner; gym 2 (Misty, no building record) is
                  data/placements.json gym2_misty_gym + data/gym_interiors.json measured.misty_relative.trainer_spawner
  the League      data/towns.json "league" (the centre of data/placements.json league_building's footprint)
  main path       data/route_paths.json, in data/routes.json order
  level caps      rctmod's rule (docs/mechanics/LEAGUE_LEVEL_CAP.md section 1): max(initialLevelCap, next required
                  trainer's highest level + relativeLevelCap), with both values from modpack/config/rctmod-server.toml
                  and the aces from data/trainers.json
  encounters      the COMPILED spawn pack, build/datapacks/cobblers_spawns (python tools/compile_spawns.py)

AN ENCOUNTER AREA is a place, so that one place is one encounter. A route file's entries carry the sub-region their
box was assigned to (ids <box>[_p<k>]_<subregion>_<species>), so a route corridor's stretch through a sub-region and
that sub-region's own file (which excludes the corridor) are ONE area, named for the sub-region; whichever route
corridors cross it are listed. A species the corridor stretch never carries is tagged "off path". Waterway and marine
files are one area each. A heart (ids <area>_h<n>_<species>, ENCOUNTER_DESIGN.md section 10) is never a first-encounter
area; its alpha species are noted as "boss".

SELECTION, per segment (start -> gym 1, gym N -> gym N+1, gym 8 -> the League): the areas whose boxes the segment's
walked line passes through, in the order the line enters them, an area already taken by an earlier segment skipped
(one encounter per area). More than --max: keep the --max the line spends most blocks in. Fewer than --min: add the
nearest areas within --detour (300) blocks of the line, marked "detour" with their distance, never one that any
segment's line passes through; still short, the same from within --detour-max (600). Measured 2026-10-05: Route 2
(Brock -> Misty) runs only through Viltri Plateau, already Route 1's, and Lake Viltri Hollow, with no other area
within 300 blocks, so its detours come from 372-507 blocks. An area whose every entry is submerged, surface or seafloor
is marked "needs Surf/Dive".

WHAT THIS DOES NOT COVER. Spawns that are not in our compiled pack (Cobbleverse's own pools, Habitat Blocks in the
world, the Rift's own systems) are not on the page; nor are rates as the game rolls them -- the buckets are the
pack's. Valid output is not proof the encounters happen in game.

  python tools/compile_spawns.py          # first, if build/datapacks/cobblers_spawns is missing
  python tools/nuzlocke_map.py            # -> build/maps/nuzlocke.html
"""
from __future__ import annotations

import argparse
import base64
import html
import io
import json
import math
import re
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))

DEFAULT_PACK = ROOT / "build" / "datapacks" / "cobblers_spawns"
DEFAULT_OUT = ROOT / "build" / "maps" / "nuzlocke.html"
WORLD_SIZE = 8192
WATER_TYPES = {"submerged", "surface", "seafloor"}
BUCKETS = ("common", "uncommon", "rare", "ultra-rare")
ROUTE_ID = re.compile(r"^(?:r\d+|vr)_b\d{4}_(?:p\d+_)?")
HEART_ID = re.compile(r"_h\d{4}_")


# ------------------------------------------------------------------ data


def load_json(rel):
    return json.loads((ROOT / rel).read_text(encoding="utf-8"))


def pretty(slug):
    return " ".join(w.capitalize() for w in slug.replace("-", " ").split("_"))


def species_name(pokemon):
    return pretty(pokemon.split()[0])


def subregion_names():
    return {s["id"]: s.get("display_name") or pretty(s["id"]) for s in load_json("data/regions.json")["subregions"]}


def route_names():
    return {r["id"]: r["display_name"].split(" — ")[0] for r in load_json("data/routes.json")["routes"]}


def read_pack(pack_dir):
    """{(kind, stem): doc} for every spawn_pool_world file in the compiled pack."""
    pack_dir = Path(pack_dir)
    files = sorted(pack_dir.glob("data/*/spawn_pool_world/*/*.json"))
    if not files:
        raise SystemExit("no compiled spawn pack at %s: run python tools/compile_spawns.py first" % pack_dir)
    return {(f.parent.name, f.stem): json.loads(f.read_text(encoding="utf-8")) for f in files}


def build_areas(pack, sub_names=None, rt_names=None):
    """{area id: area} from read_pack()'s documents. An area: kind, name, sub (its sub-region, if any), boxes
    (M x 4 int array of minX, maxX, minZ, maxZ), entries (non-heart spawn entries), hearts (heart entries)."""
    sub_names = sub_names or {}
    rt_names = rt_names or {}
    areas = {}

    def area(aid, **kw):
        if aid not in areas:
            areas[aid] = dict(id=aid, entries=[], hearts=[], boxset=set(), **kw)
        return areas[aid]

    for (kind, stem), doc in sorted(pack.items()):
        for s in doc.get("spawns", []):
            c = s.get("condition") or {}
            box = (c.get("minX"), c.get("maxX"), c.get("minZ"), c.get("maxZ"))
            if None in box:
                continue
            if kind == "routes":
                m = ROUTE_ID.match(s["id"])
                rest = s["id"][m.end():] if m else ""
                suffix = "_" + s["pokemon"]
                if not m or not rest.endswith(suffix):
                    raise SystemExit("%s: route entry id %r does not read as <box>_<subregion>_<species>" % (stem, s["id"]))
                sub = rest[:-len(suffix)]
                a = area("sub/" + sub, kind="land", sub=sub, name=sub_names.get(sub, pretty(sub)), routes=set())
                a["routes"].add(rt_names.get(stem, pretty(stem)))
                s = dict(s, corridor=True)
            elif kind == "subregions":
                a = area("sub/" + stem, kind="land", sub=stem, name=sub_names.get(stem, pretty(stem)), routes=set())
            else:
                a = area("%s/%s" % (kind, stem), kind=kind, sub=None, routes=set(),
                         name=pretty(stem) + {"marine": " (open sea)", "waterways": " (waterway)"}.get(kind, ""))
            if kind != "routes" and HEART_ID.search(s["id"][len(stem):] if s["id"].startswith(stem) else s["id"]):
                a["hearts"].append(s)
                continue
            a["entries"].append(s)
            a["boxset"].add(box)
    for a in areas.values():
        a["boxes"] = np.array(sorted(a.pop("boxset")), dtype=np.int64).reshape(-1, 4)
        a["routes"] = sorted(a["routes"])
    return {k: a for k, a in areas.items() if a["entries"]}


def summarise(area):
    """Levels, species by bucket, flags. A species seen in more than one bucket is listed in its most common one."""
    lo, hi = 999, 0
    best = {}
    per_sp = {}
    for e in area["entries"]:
        a, _, b = str(e["level"]).partition("-")
        lo, hi = min(lo, int(a)), max(hi, int(b or a))
        sp = species_name(e["pokemon"])
        r = BUCKETS.index(e["bucket"]) if e["bucket"] in BUCKETS else len(BUCKETS) - 1
        best[sp] = min(best.get(sp, r), r)
        f = per_sp.setdefault(sp, {"night": True, "rain": True, "water": True, "path": False})
        cond = e.get("condition") or {}
        f["night"] &= cond.get("timeRange") == "night"
        f["rain"] &= bool(cond.get("isRaining"))
        f["water"] &= e.get("spawnablePositionType") in WATER_TYPES
        f["path"] |= bool(e.get("corridor"))
    has_corridor = any(e.get("corridor") for e in area["entries"])
    groups = {b: [] for b in BUCKETS}
    for sp in sorted(best):
        tags = [t for t in ("night", "rain", "water") if per_sp[sp][t]]
        if has_corridor and not per_sp[sp]["path"]:
            tags.append("off path")
        groups[BUCKETS[best[sp]]].append((sp, tags))
    water_only = all(e.get("spawnablePositionType") in WATER_TYPES for e in area["entries"])
    bosses = sorted({species_name(h["pokemon"]) for h in area["hearts"] if "alpha=true" in h["pokemon"]})
    return {"levels": (lo, hi), "groups": groups, "water_only": water_only, "bosses": bosses}


# ------------------------------------------------------------------ selection


def inside_counts(points, boxes):
    """(count, first index) of path points inside any of the boxes. points N x 2 (x, z)."""
    if len(boxes) == 0 or len(points) == 0:
        return 0, -1
    x, z = points[:, 0:1], points[:, 1:2]
    hit = ((x >= boxes[:, 0]) & (x <= boxes[:, 1]) & (z >= boxes[:, 2]) & (z <= boxes[:, 3])).any(axis=1)
    idx = np.flatnonzero(hit)
    return int(idx.size), (int(idx[0]) if idx.size else -1)


def nearest(points, boxes):
    """(distance, path index, (x, z) on the boxes) of the closest approach between the path and the boxes."""
    x, z = points[:, 0:1].astype(float), points[:, 1:2].astype(float)
    cx = np.clip(x, boxes[:, 0], boxes[:, 1])
    cz = np.clip(z, boxes[:, 2], boxes[:, 3])
    d = np.hypot(x - cx, z - cz)
    i, j = np.unravel_index(int(np.argmin(d)), d.shape)
    return float(d[i, j]), int(i), (int(cx[i, j]), int(cz[i, j]))


def on_path(points, areas):
    """{area id: (blocks, first index)} for every area the walked line passes through."""
    points = np.asarray(points, dtype=np.int64).reshape(-1, 2)
    out = {}
    for aid, a in areas.items():
        n, first = inside_counts(points, a["boxes"])
        if n:
            out[aid] = (n, first)
    return out


def select_segment(points, areas, used=(), lo=4, hi=6, detour=300.0, detour_max=None, reserved=()):
    """The encounter areas for one walked line, in travel order. Returns [{id, at, index, blocks, detour, dist}].

    used: areas an earlier segment took (one encounter per place). reserved: areas some segment's line passes
    through, which a detour never takes (the segment that walks through it keeps it). Detours come from within
    `detour` blocks of the line, then, if still short of `lo`, from within `detour_max` (each shows its distance)."""
    points = np.asarray(points, dtype=np.int64).reshape(-1, 2)
    on = [{"id": aid, "index": first, "at": tuple(int(v) for v in points[first]), "blocks": n, "detour": False,
           "dist": 0} for aid, (n, first) in on_path(points, areas).items() if aid not in used]
    if len(on) > hi:
        on = sorted(on, key=lambda p: (-p["blocks"], p["index"]))[:hi]
    if len(on) < lo:
        taken = {p["id"] for p in on} | set(used) | set(reserved)
        near = []
        for aid, a in areas.items():
            if aid in taken:
                continue
            d, i, at = nearest(points, a["boxes"])
            near.append({"id": aid, "index": i, "at": at, "blocks": 0, "detour": True, "dist": int(round(d))})
        near.sort(key=lambda p: (p["dist"], p["id"]))
        for reach in (detour, detour_max):
            if reach is None:
                continue
            for p in near:
                if len(on) >= lo:
                    break
                if p["dist"] <= reach and p["id"] not in {q["id"] for q in on}:
                    on.append(p)
    return sorted(on, key=lambda p: (p["index"], p["detour"], p["id"]))


# ------------------------------------------------------------------ places and caps


def towns():
    plazas = load_json("data/plaza_centres.json")["towns"]
    out = []
    for t in load_json("data/towns.json")["towns"]:
        x, z = t["centre"]["x"], t["centre"]["z"]
        sq = (plazas.get(t["id"]) or {}).get("square") or {}
        if sq.get("rect"):
            x0, z0, x1, z1 = sq["rect"]
            x, z = (x0 + x1) // 2, (z0 + z1) // 2
        out.append({"id": t["id"], "name": t.get("display_name") or pretty(t["id"]), "tier": t.get("tier"),
                    "role": t.get("role"), "x": x, "z": z})
    return out


def gyms():
    leaders = {t["order"]: t for t in load_json("data/trainers.json")["trainers"] if t.get("class") == "gym_leader"}
    out = {}
    # a gym's arena, once it has one, is where its leader stands (tools/gym_arenas.py leader_seats)
    sys.path.insert(0, str(ROOT / "tools"))
    import gym_arenas
    moved = gym_arenas.leader_seats()
    for f in sorted((ROOT / "data" / "gym_buildings").glob("gym*.json")):
        n = int(re.sub(r"\D", "", f.stem))
        d = json.loads(f.read_text(encoding="utf-8"))
        sp = moved[d["leader"]["id"]]["seat"] if d["leader"]["id"] in moved else d["leader"]["spawner"]
        out[n] = {"n": n, "leader": d["leader"].get("name") or leaders[n]["display_name"], "x": sp[0], "z": sp[2],
                  "town": d.get("settlement")}
    if 2 not in out:
        p = next(p for p in load_json("data/placements.json")["placements"] if p["id"] == "gym2_misty_gym")
        if p.get("rotation", "none") != "none" or p.get("mirror", "none") != "none":
            raise SystemExit("gym2_misty_gym is rotated or mirrored: the template-relative spawner needs the transform")
        rel = load_json("data/gym_interiors.json")["measured"]["misty_relative"]["trainer_spawner"]
        out[2] = {"n": 2, "leader": leaders[2]["display_name"], "x": p["position"]["x"] + rel[0],
                  "z": p["position"]["z"] + rel[2], "town": p.get("settlement")}
    missing = set(range(1, 9)) - set(out)
    if missing:
        raise SystemExit("no gym position for gym(s) %s" % sorted(missing))
    return out


def rct_setting(name):
    text = (ROOT / "modpack" / "config" / "rctmod-server.toml").read_text(encoding="utf-8")
    m = re.search(r"^\s*%s\s*=\s*(-?\d+)" % name, text, re.M)
    if not m:
        raise SystemExit("modpack/config/rctmod-server.toml has no %s" % name)
    return int(m.group(1))


def level_caps():
    """{segment number 1..9: (cap, whose ace)}: segment k ends at gym k; segment 9 at the first Elite Four member."""
    init, rel = rct_setting("initialLevelCap"), rct_setting("relativeLevelCap")
    tr = load_json("data/trainers.json")["trainers"]
    nxt = {t["order"]: t for t in tr if t.get("class") == "gym_leader"}
    nxt[9] = next(t for t in tr if t.get("class") == "elite_four" and t.get("order") == 1)
    return {k: (max(init, max(m["level"] for m in t["team"]) + rel), t["display_name"]) for k, t in nxt.items()}


def segments():
    routes = sorted(load_json("data/routes.json")["routes"], key=lambda r: int(r["order"]))
    paths = load_json("data/route_paths.json")["paths"]
    names = {t["id"]: t.get("display_name") for t in load_json("data/towns.json")["towns"]}
    out = []
    for k, r in enumerate(routes, 1):
        if r["id"] not in paths:
            raise SystemExit("data/route_paths.json has no walked line for %s" % r["id"])
        out.append({"n": k, "route": r["id"], "title": r["display_name"], "walked": r["distance"]["computed_walked_blocks"],
                    "from": names.get(r["from_town"], r["from_town"]),
                    "to": names.get(r["to_town"], r["to_town"]), "points": np.array(paths[r["id"]], dtype=np.int64)})
    return out


# ------------------------------------------------------------------ base map


def relief_png(scale, max_colours=128):
    """The shaded-relief base map as PNG bytes, (WORLD_SIZE // scale) px square."""
    from PIL import Image, ImageDraw
    import ground
    import water_mask

    g = ground.Ground()
    h = g.heights
    if g.ox or g.oz or h.shape != (WORLD_SIZE, WORLD_SIZE):
        raise SystemExit("expected an %d-square heightmap at origin 0,0" % WORLD_SIZE)
    hr = np.round(h)
    wet = hr < water_mask.sea_level()
    for body in water_mask.bodies().values():
        if not body["basin"]:
            continue
        img = Image.new("1", (WORLD_SIZE, WORLD_SIZE), 0)
        dr = ImageDraw.Draw(img)
        for ring in body["basin"]:
            dr.polygon([tuple(p) for p in ring], fill=1)
        wet |= np.asarray(img, dtype=bool) & (hr < body["level_y"])
    n = WORLD_SIZE // scale
    cut = n * scale
    pool = lambda a: a[:cut, :cut].reshape(n, scale, n, scale).mean(axis=(1, 3))  # noqa: E731
    hs, ws = pool(h.astype(np.float32)), pool(wet.astype(np.float32)) > 0.5
    gz, gx = np.gradient(hs * 2.5, scale)
    az, alt = math.radians(315), math.radians(42)
    slope = np.arctan(np.hypot(gx, gz))
    aspect = np.arctan2(-gx, gz)
    shade = np.clip(np.sin(alt) * np.cos(slope) + np.cos(alt) * np.sin(slope) * np.cos(az - aspect), 0, 1)
    stops = [(62, (176, 196, 160)), (100, (196, 205, 162)), (140, (210, 206, 168)), (190, (198, 184, 156)),
             (240, (176, 168, 160)), (310, (236, 236, 232))]
    land = np.zeros(hs.shape + (3,), np.float32)
    for c in range(3):
        land[..., c] = np.interp(hs, [s[0] for s in stops], [s[1][c] for s in stops])
    land *= (0.62 + 0.5 * shade)[..., None]
    depth = np.clip((62 - hs) / 40.0, 0, 1)[..., None]
    water = np.array([168, 196, 210], np.float32) * (1 - depth) + np.array([128, 162, 186], np.float32) * depth
    rgb = np.where(ws[..., None], water, land)
    rgb = rgb * 0.82 + np.array([233, 238, 232], np.float32) * 0.18   # muted, so overlays read
    im = Image.fromarray(np.clip(rgb, 0, 255).astype(np.uint8), "RGB").quantize(colors=max_colours)
    buf = io.BytesIO()
    im.save(buf, "PNG", optimize=True)
    return buf.getvalue(), n


# ------------------------------------------------------------------ page

STYLE = """
@import url('https://fonts.googleapis.com/css2?family=Alegreya+Sans:ital,wght@0,400;0,500;0,700;1,400&family=Zilla+Slab:wght@500;700&display=swap');
:root{
  --paper:#e7ece4; --card:#f5f7f1; --ink:#1b2830; --ink-soft:#4d5d66; --rule:#c3cdc4;
  --path:#d1203a; --path-case:#fffdf6; --marker:#1e3b5c; --marker-ink:#ffffff; --detour:#0e766c;
  --water:#2c6c9a; --gold:#e2ad22; --gold-ink:#2a2006; --halo:rgba(247,249,243,.93); --grid:rgba(27,40,48,.28);
  --town:#1b2830; --tag-bg:#dfe6dc; --night:#3b4a8a; --frame:#cfd8cd; --focus:#fff1a8;
  --display:'Zilla Slab', Rockwell, 'Roboto Slab', Georgia, serif;
  --body:'Alegreya Sans', 'Gill Sans', 'Trebuchet MS', system-ui, sans-serif;
}
@media (prefers-color-scheme: dark){ :root:not([data-theme="light"]){
  --paper:#12181c; --card:#1b2328; --ink:#e3eae2; --ink-soft:#a6b4ad; --rule:#2e3b42;
  --path:#ff4a5f; --path-case:#12181c; --marker:#e9eef5; --marker-ink:#14202b; --detour:#52c7b8;
  --water:#7fbfe6; --gold:#f0c046; --gold-ink:#241b02; --halo:rgba(18,24,28,.9); --grid:rgba(227,234,226,.25);
  --town:#eef3ec; --tag-bg:#26313a; --night:#a9b6ff; --frame:#26313a; --focus:#4a4210; color-scheme:dark;
}}
:root[data-theme="dark"]{
  --paper:#12181c; --card:#1b2328; --ink:#e3eae2; --ink-soft:#a6b4ad; --rule:#2e3b42;
  --path:#ff4a5f; --path-case:#12181c; --marker:#e9eef5; --marker-ink:#14202b; --detour:#52c7b8;
  --water:#7fbfe6; --gold:#f0c046; --gold-ink:#241b02; --halo:rgba(18,24,28,.9); --grid:rgba(227,234,226,.25);
  --town:#eef3ec; --tag-bg:#26313a; --night:#a9b6ff; --frame:#26313a; --focus:#4a4210; color-scheme:dark;
}
*{box-sizing:border-box}
body{margin:0;background:var(--paper);color:var(--ink);font-family:var(--body);font-size:16px;line-height:1.45}
.nz{max-width:1280px;margin:0 auto;padding:20px 16px 48px}
.nz h1{font-family:var(--display);font-weight:700;font-size:clamp(1.7rem,4.5vw,2.6rem);margin:0 0 4px;letter-spacing:.01em}
.nz h2{font-family:var(--display);font-weight:700;font-size:1.25rem;margin:0}
.nz .sub{color:var(--ink-soft);margin:0 0 16px}
.top{display:grid;grid-template-columns:minmax(0,1fr);gap:16px}
@media (min-width:1000px){.top{grid-template-columns:minmax(0,1fr) 300px}}
.panel{background:var(--card);border:1px solid var(--rule);border-radius:10px;padding:14px 16px}
.panel h2{margin-bottom:8px}
.rules ol{margin:0;padding-left:1.2em}.rules li{margin:4px 0}
.legend ul{list-style:none;margin:0;padding:0;display:grid;gap:6px}
.legend li{display:flex;align-items:center;gap:8px}
.legend svg{flex:none}
.mapwrap{border:1px solid var(--rule);border-radius:10px;background:var(--frame);overflow:hidden}
.mapbar{display:flex;justify-content:space-between;align-items:center;gap:8px;padding:6px 10px;font-size:.9rem;color:var(--ink-soft)}
.mapbar button{font:inherit;color:var(--ink);background:var(--card);border:1px solid var(--rule);border-radius:6px;padding:4px 10px;cursor:pointer}
.mapscroll{overflow:auto;-webkit-overflow-scrolling:touch}
.map{display:block;width:100%;height:auto;min-width:760px}
.mapwrap.fit .map{min-width:0}
@media (min-width:800px){.mapbar button{display:none}}
.map text{font-family:var(--display);paint-order:stroke;stroke:var(--halo);stroke-linejoin:round}
.map .town{fill:var(--town);font-size:118px;font-weight:700;stroke-width:30px}
.map .town.minor{font-size:92px;font-weight:500}
.map .gymlbl{fill:var(--ink);font-size:92px;font-weight:500;stroke-width:26px}
.map .cell{fill:var(--grid);font-size:150px;font-weight:700;stroke:none}
.map .gridline{stroke:var(--grid);stroke-width:6;fill:none;stroke-dasharray:40 30}
.map .pathcase{stroke:var(--path-case);stroke-width:46;fill:none;stroke-linejoin:round;stroke-linecap:round;opacity:.9}
.map .path{stroke:var(--path);stroke-width:24;fill:none;stroke-linejoin:round;stroke-linecap:round}
.map .dot{fill:var(--town);stroke:var(--halo);stroke-width:16}
.map .gym{fill:var(--gold);stroke:var(--gold-ink);stroke-width:12}
.map .gymn{fill:var(--gold-ink);font-size:92px;font-weight:700;stroke:none;text-anchor:middle;dominant-baseline:central}
.map .mk circle{fill:var(--marker);stroke:var(--halo);stroke-width:14}
.map .mk .lead{stroke:var(--marker);stroke-width:10}
.map .mk circle.pin{stroke-width:6}
.map .mk text{fill:var(--marker-ink);font-size:88px;font-weight:700;stroke:none;text-anchor:middle;dominant-baseline:central;font-family:var(--body)}
.map .mk.detour circle{fill:var(--detour)}
.map .mk.surf circle{fill:var(--water)}
.map .mk:hover circle:not(.pin),.map .mk:focus circle:not(.pin){r:100}
.map .start{fill:var(--path);stroke:var(--path-case);stroke-width:14}
.map .league{fill:var(--gold);stroke:var(--gold-ink);stroke-width:14}
.segs{display:grid;gap:16px;margin-top:20px;grid-template-columns:minmax(0,1fr)}
@media (min-width:760px){.segs{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media (min-width:1180px){.segs{grid-template-columns:repeat(3,minmax(0,1fr))}}
.seg header{display:flex;justify-content:space-between;align-items:baseline;gap:8px;border-bottom:2px solid var(--path);padding-bottom:6px;margin-bottom:8px;flex-wrap:wrap}
.seg .cap{font-family:var(--display);font-weight:700;background:var(--gold);color:var(--gold-ink);border-radius:999px;padding:1px 10px;white-space:nowrap}
.seg .route{color:var(--ink-soft);font-size:.92rem;margin:0 0 8px}
.area{list-style:none;margin:0;padding:0}
.area>li{border-top:1px dashed var(--rule);padding:8px 0;scroll-margin-top:12px}
.area>li:first-child{border-top:0}
.area>li:target{background:var(--focus);border-radius:6px;padding:8px}
.ah{display:flex;gap:8px;align-items:baseline;flex-wrap:wrap}
.num{flex:none;display:inline-grid;place-items:center;min-width:1.7em;height:1.7em;border-radius:999px;background:var(--marker);color:var(--marker-ink);font-weight:700;font-size:.9rem}
.num.detour{background:var(--detour)}.num.surf{background:var(--water)}
.aname{font-weight:700}
.lv{color:var(--ink-soft);font-size:.92rem}
.tag{font-size:.78rem;background:var(--tag-bg);border-radius:4px;padding:0 6px;white-space:nowrap}
.tag.surf{color:var(--water)}.tag.detour{color:var(--detour)}
.sp{margin:4px 0 0;font-size:.95rem;display:grid;grid-template-columns:auto minmax(0,1fr);gap:1px 10px}
.sp dt{color:var(--ink-soft);font-size:.8rem;text-transform:uppercase;letter-spacing:.05em;padding-top:2px}
.sp dd{margin:0;overflow-wrap:anywhere}
.sp i{color:var(--night);font-style:normal;font-size:.8rem}
.off{color:var(--ink-soft)}
.boss{margin:4px 0 0;font-size:.9rem}
.via{margin:2px 0 0;color:var(--ink-soft);font-size:.85rem;font-style:italic}
.src{margin-top:24px;color:var(--ink-soft);font-size:.85rem}
.src code{font-size:.8rem;overflow-wrap:anywhere}
"""

MAP_TOGGLE = """<script>
(function(){var w=document.getElementById('mapwrap'),b=document.getElementById('fitbtn');if(!w||!b)return;
b.addEventListener('click',function(){var f=w.classList.toggle('fit');b.textContent=f?'Zoom in':'Fit to screen';});})();
</script>"""


def esc(s):
    return html.escape(str(s), quote=True)


def thin(points, step=6):
    pts = points[::step].tolist()
    if pts[-1] != points[-1].tolist():
        pts.append(points[-1].tolist())
    return " ".join("%d,%d" % (x, z) for x, z in pts)


def species_html(groups):
    rows = []
    for b in BUCKETS:
        if not groups[b]:
            continue
        items = []
        for sp, tags in groups[b]:
            t = "".join(" <i>%s</i>" % esc(x) for x in tags if x != "off path")
            items.append(('<span class="off">%s†</span>' if "off path" in tags else "%s") % esc(sp) + t)
        rows.append("<dt>%s</dt><dd>%s</dd>" % (esc(b.replace("-", " ")), ", ".join(items)))
    return "<dl class=\"sp\">%s</dl>" % "".join(rows)


def render(png, segs, picks, areas, summaries, caps, town_list, gym_list, league):
    uri = "data:image/png;base64," + base64.b64encode(png).decode("ascii")
    svg = ['<svg class="map" viewBox="0 0 %d %d" role="img" aria-label="Region map with the main path, towns, gyms and '
           'numbered encounter areas" xmlns="http://www.w3.org/2000/svg">' % (WORLD_SIZE, WORLD_SIZE),
           '<image href="%s" x="0" y="0" width="%d" height="%d" preserveAspectRatio="none"/>' % (uri, WORLD_SIZE, WORLD_SIZE)]
    cells = load_json("data/cells.json")["cells"]
    rows = sorted({(c["row"], c["id"][0], c["bounds"]["min_z"]) for c in cells})
    cols = sorted({(c["column"], c["id"][1:], c["bounds"]["min_x"]) for c in cells})
    for _, _, z in rows[1:]:
        svg.append('<line class="gridline" x1="0" y1="%d" x2="%d" y2="%d"/>' % (z, WORLD_SIZE, z))
    for _, _, x in cols[1:]:
        svg.append('<line class="gridline" x1="%d" y1="0" x2="%d" y2="%d"/>' % (x, x, WORLD_SIZE))
    for _, lab, z in rows:
        svg.append('<text class="cell" x="40" y="%d">%s</text>' % (z + 170, esc(lab)))
    for _, lab, x in cols:
        svg.append('<text class="cell" x="%d" y="150">%s</text>' % (x + 470, esc(lab)))
    for s in segs:
        pts = thin(s["points"])
        svg.append('<polyline class="pathcase" points="%s"/>' % pts)
    for s in segs:
        svg.append('<polyline class="path" points="%s"><title>%s</title></polyline>' % (thin(s["points"]), esc(s["title"])))
    gyms_by_town = {g["town"]: g for g in gym_list.values()}
    for t in town_list:
        if t["tier"] not in ("critical", "major", "rest_stop") or t["id"] == "league":
            continue
        x, z = t["x"], t["z"]
        if t["id"] == "hometown":
            svg.append('<polygon class="start" points="%s"><title>Start: %s</title></polygon>' % (star(x, z, 120), esc(t["name"])))
        else:
            svg.append('<circle class="dot" cx="%d" cy="%d" r="%d"/>' % (x, z, 52 if t["tier"] != "rest_stop" else 38))
        minor = "" if t["tier"] in ("critical", "major") else " minor"
        label = t["name"] + (" (start)" if t["id"] == "hometown" else "")
        svg.append('<text class="town%s" x="%d" y="%d">%s</text>' % (minor, x + 90, z - 70, esc(label)))
        g = gyms_by_town.get(t["id"])
        if g:
            svg.append('<text class="gymlbl" x="%d" y="%d">Gym %d · %s</text>' % (x + 90, z + 40, g["n"], esc(g["leader"])))
    for g in gym_list.values():
        svg.append('<g><title>Gym %d: %s</title><polygon class="gym" points="%s"/><text class="gymn" x="%d" y="%d">%d</text></g>'
                   % (g["n"], esc(g["leader"]), hexagon(g["x"], g["z"], 80), g["x"], g["z"], g["n"]))
    svg.append('<g><title>The League</title><polygon class="league" points="%s"/></g>' % star(league["x"], league["z"], 150))
    svg.append('<text class="town" x="%d" y="%d">%s</text>' % (league["x"] + 170, league["z"] + 40, esc(league["name"])))
    num = 0
    side = []
    true_at = [p["at"] for s in segs for p in picks[s["n"]]]
    shown_at = spread(true_at)
    for s in segs:
        cap, whose = caps[s["n"]]
        items = []
        for p in picks[s["n"]]:
            num += 1
            a, sm = areas[p["id"]], summaries[p["id"]]
            cls = "surf" if sm["water_only"] else ("detour" if p["detour"] else "")
            (tx, tz), (x, z) = p["at"], shown_at[num - 1]
            lead = ""
            if (tx, tz) != (x, z):
                lead = ('<line class="lead" x1="%d" y1="%d" x2="%d" y2="%d"/><circle class="pin" cx="%d" cy="%d" r="22"/>'
                        % (tx, tz, x, z, tx, tz))
            svg.append('<a href="#enc-%d" class="mk %s"><title>%d. %s (Lv %d-%d)</title>%s<circle cx="%d" cy="%d" r="78"/>'
                       '<text x="%d" y="%d">%d</text></a>' % (num, cls, num, esc(a["name"]), sm["levels"][0], sm["levels"][1],
                                                               lead, x, z, x, z, num))
            tags = []
            if p["detour"]:
                tags.append('<span class="tag detour">detour, %d blocks off the path</span>' % p["dist"])
            if sm["water_only"]:
                tags.append('<span class="tag surf">needs Surf/Dive</span>')
            boss = ('<p class="boss"><b>Boss:</b> %s (alpha, in the area\'s heart; not a first encounter)</p>'
                    % esc(", ".join(sm["bosses"]))) if sm["bosses"] else ""
            via = ('<p class="via">Crossed by %s</p>' % esc(", ".join(a["routes"]))) if a.get("routes") else ""
            items.append('<li id="enc-%d"><div class="ah"><span class="num %s">%d</span><span class="aname">%s</span>'
                         '<span class="lv">Lv %d-%d</span>%s</div>%s%s%s</li>'
                         % (num, cls, num, esc(a["name"]), sm["levels"][0], sm["levels"][1], "".join(tags), via,
                            species_html(sm["groups"]), boss))
        dest = ("Gym %d · %s" % (s["n"], gym_list[s["n"]]["leader"])) if s["n"] in gym_list else "The League"
        side.append('<section class="panel seg"><header><h2>%d. %s → %s</h2><span class="cap">Cap %d</span></header>'
                    '<p class="route">%s · %s blocks walked · ends at %s · cap is %s\'s ace</p><ol class="area">%s</ol></section>'
                    % (s["n"], esc(s["from"]), esc(s["to"]), cap, esc(s["title"]), "{:,}".format(s["walked"]),
                       esc(dest), esc(whose), "".join(items)))
    svg.append("</svg>")
    legend = """<section class="panel legend"><h2>Legend</h2><ul>
<li><svg width="34" height="12" viewBox="0 0 34 12"><line x1="2" y1="6" x2="32" y2="6" stroke="var(--path-case)" stroke-width="8" stroke-linecap="round"/><line x1="2" y1="6" x2="32" y2="6" stroke="var(--path)" stroke-width="4" stroke-linecap="round"/></svg>Main path, Pallet to the League</li>
<li><svg width="34" height="22" viewBox="0 0 34 22"><circle cx="17" cy="11" r="10" fill="var(--marker)"/><text x="17" y="15" text-anchor="middle" font-size="12" font-weight="700" fill="var(--marker-ink)">1</text></svg>Encounter area, where the path enters it</li>
<li><svg width="34" height="22" viewBox="0 0 34 22"><circle cx="17" cy="11" r="10" fill="var(--detour)"/></svg>Detour: off the path (distance in its card)</li>
<li><svg width="34" height="22" viewBox="0 0 34 22"><circle cx="17" cy="11" r="10" fill="var(--water)"/></svg>Water only: needs Surf/Dive</li>
<li><svg width="34" height="22" viewBox="0 0 34 22"><polygon points="%s" fill="var(--gold)" stroke="var(--gold-ink)" stroke-width="1.5"/></svg>Gym and badge number</li>
<li><svg width="34" height="22" viewBox="0 0 34 22"><polygon points="%s" fill="var(--path)"/></svg>Start (Pallet Town)</li>
<li><svg width="34" height="22" viewBox="0 0 34 22"><polygon points="%s" fill="var(--gold)" stroke="var(--gold-ink)" stroke-width="1.5"/></svg>The League</li>
<li><svg width="34" height="22" viewBox="0 0 34 22"><circle cx="17" cy="11" r="5" fill="var(--town)"/></svg>Town or rest stop</li>
<li><span class="tag" style="font-family:var(--display);font-weight:700">C4</span>1024-block cell: rows A-H north to south, columns 1-8 west to east</li>
</ul></section>""" % (hexagon(17, 11, 10), star(17, 11, 10), star(17, 11, 10))
    rules = """<section class="panel rules"><h2>Nuzlocke rules</h2><ol>
<li>Only the <b>first</b> Pokémon you meet in each numbered area may be caught. Miss it or knock it out and that area is spent.</li>
<li>Nickname every catch.</li>
<li>A Pokémon that faints is dead: release it or box it for good.</li>
<li>Stay at or under the segment's level cap until its gym is beaten.</li>
<li>Bosses in an area's heart are not first encounters.</li>
</ol></section>"""
    parts = ["<title>Region Nuzlocke Map</title>", "<style>%s</style>" % STYLE, '<main class="nz">',
             "<h1>Region Nuzlocke Map</h1>",
             '<p class="sub">The main path from Pallet Town through eight gyms to the League, with %d encounter areas '
             'numbered in the order you reach them. Tap a number on the map to jump to its list.</p>' % num,
             '<div class="top"><div class="mapwrap" id="mapwrap"><div class="mapbar"><span>North is up. One square is '
             '1024 blocks.</span><button type="button" id="fitbtn">Fit to screen</button></div><div class="mapscroll">',
             "".join(svg), "</div></div><div>", rules, legend, "</div></div>",
             '<div class="segs">', "".join(side), "</div>",
             '<p class="src">Species, levels and rarities are read from the compiled spawn pack (cobblers_spawns); '
             'level caps from the server\'s Radical Cobblemon Trainers settings and each next leader\'s strongest '
             'Pokémon. <i>night</i>, <i>rain</i> and <i>water</i> mark a species that appears only then or there; '
             'a † species lives in the area but not along the path itself, so step off the trail for it. '
             'Not every spawn in the world is listed: the base pack\'s own spawns and special habitats are not.</p>',
             "</main>", MAP_TOGGLE]
    return "\n".join(parts)


def spread(points, gap=180.0, rounds=60):
    """Marker positions nudged apart so no two discs overlap; a moved marker keeps a leader line to its true point."""
    pos = [list(map(float, p)) for p in points]
    for _ in range(rounds):
        moved = False
        for i in range(len(pos)):
            for j in range(i + 1, len(pos)):
                dx, dz = pos[j][0] - pos[i][0], pos[j][1] - pos[i][1]
                d = math.hypot(dx, dz)
                if d >= gap:
                    continue
                if d < 1e-6:
                    dx, dz, d = 1.0, 0.0, 1.0
                push = (gap - d) / 2.0
                pos[i][0] -= dx / d * push
                pos[i][1] -= dz / d * push
                pos[j][0] += dx / d * push
                pos[j][1] += dz / d * push
                moved = True
        if not moved:
            break
    return [(int(round(x)), int(round(z))) for x, z in pos]


def star(x, z, r):
    pts = []
    for i in range(10):
        a = -math.pi / 2 + i * math.pi / 5
        rr = r if i % 2 == 0 else r * 0.45
        pts.append("%.1f,%.1f" % (x + rr * math.cos(a), z + rr * math.sin(a)))
    return " ".join(pts)


def hexagon(x, z, r):
    return " ".join("%.1f,%.1f" % (x + r * math.cos(math.pi / 6 + i * math.pi / 3), z + r * math.sin(math.pi / 6 + i * math.pi / 3))
                    for i in range(6))


# ------------------------------------------------------------------ main


def plan(pack_dir, lo=4, hi=6, detour=300.0, detour_max=600.0):
    """(segments, picks by segment, areas, summaries): everything but the base map."""
    areas = build_areas(read_pack(pack_dir), subregion_names(), route_names())
    segs = segments()
    reserved = set()
    for s in segs:
        reserved |= set(on_path(s["points"], areas))
    picks, used = {}, set()
    for s in segs:
        picks[s["n"]] = select_segment(s["points"], areas, used, lo, hi, detour, detour_max, reserved)
        used |= {p["id"] for p in picks[s["n"]]}
    summaries = {aid: summarise(areas[aid]) for aid in used}
    return segs, picks, areas, summaries


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--pack", default=str(DEFAULT_PACK), help="the compiled spawn pack (python tools/compile_spawns.py)")
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    ap.add_argument("--scale", type=int, default=5, help="blocks per base-map pixel (5 -> 1638 px)")
    ap.add_argument("--colours", type=int, default=160, help="base-map palette size")
    ap.add_argument("--min", dest="lo", type=int, default=4)
    ap.add_argument("--max", dest="hi", type=int, default=6)
    ap.add_argument("--detour", type=float, default=300.0, help="how far off the line a detour area may be, in blocks")
    ap.add_argument("--detour-max", type=float, default=600.0,
                    help="the farther reach used only when a segment is still short of --min (0: none)")
    a = ap.parse_args(argv)
    segs, picks, areas, summaries = plan(a.pack, a.lo, a.hi, a.detour, a.detour_max or None)
    t = towns()
    league = next(x for x in t if x["id"] == "league")
    png, px = relief_png(a.scale, a.colours)
    page = render(png, segs, picks, areas, summaries, level_caps(), t, gyms(), league)
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(page, encoding="utf-8")
    for s in segs:
        ps = picks[s["n"]]
        print("segment %d %-28s %d areas (%d on path, %d detour)" % (s["n"], s["route"], len(ps),
                                                                    sum(not p["detour"] for p in ps), sum(p["detour"] for p in ps)))
    print("wrote %s: %d bytes, base map %d px (%d bytes PNG)" % (out, out.stat().st_size, px, len(png)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
