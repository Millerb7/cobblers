#!/usr/bin/env python
"""Write docs/player/region-map.html: a self-contained encounter map for players.

Who it is for: a Nuzlocke player deciding where to spend the one catch a zone allows. It answers "what lives here, how
often, at what level, and when" for every campaign area, and "where does this Pokemon live" for every species, on a
shaded-relief picture of the region. One HTML file, no server, no network: the relief is an inline JPEG, the areas
inline SVG, the tables inline JSON.

What it reads (the live data, never a design document and never a world):
  - the pools tools/compile_spawns.py EMITS. By default this tool runs compile_spawns into a temporary directory, so the
    page is reproducible from data/ alone; --pack <dir> reads an existing compilation instead (e.g. build/datapacks/
    cobblers_spawns). Sub-region, marine, waterway and route-corridor files; habitat pools are all left out (below).
  - data/nuzlocke_zones.json for the catch-zone names and which compiled pool is a zone; data/regions.json for region
    names and outlines; data/towns.json and data/placements.json for settlement labels; data/routes.json for the route
    centrelines and display names; data/spawn_suppression.json for what keeps the pack's defaults.
  - server/config/mods/cobblemon/spawning/best-spawner-config.json worldBuckets for the bucket weights (read, never
    written).
  - the canonical heightmap through tools/terrain.py (root from terrain.env_source_root()), downsampled 4x.

The area unit is the Nuzlocke catch zone, which for land is exactly one compiled sub-region pool
(data/nuzlocke_zones.json derivation.tables_are_subregions; this tool checks every land zone has its file). Route
corridors are drawn as their own areas because their pool is a filtered copy of the zones they cross, so the rates
differ on the path; each says which catch zone it counts as.

Left out on purpose (discoveries, the page says so): heart entries (ids <area>_h<n>_), the Mega field den rows
(compile_spawns.mega_den_spawns, ids <area>_<den>_b<n>_), every habitat pool (bird nests, Victory Road's tiles, the
training grounds, the discovery sites), and everything other generators emit (legendaries, residents, shrines, caches,
portals, story). A compiled land pool with no ground at or above sea level on the heightmap is dropped and named in the
data notes.

Rates. Within one spawn position (land, water surface, underwater, sea floor), Cobblemon draws a bucket by its world
weight and then an entry by weight within the bucket. The page renormalises the bucket weights over the buckets present
at that position (an ASSUMPTION about Cobblemon 1.8.0, stated on the page), counts rain-only entries apart, and treats
altitude and nearby-block conditions as met. Day and night are computed separately.

  python tools/player_guide_map.py            # write docs/player/region-map.html
  python tools/player_guide_map.py --check    # exit 1 if the committed page differs from a fresh build
"""
from __future__ import annotations

import argparse
import base64
import contextlib
import hashlib
import html
import io
import json
import math
import re
import sys
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
import compile_spawns  # noqa: E402
import terrain  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUT = ROOT / "docs" / "player" / "region-map.html"
SPAWNER_CONFIG = ROOT / "server" / "config" / "mods" / "cobblemon" / "spawning" / "best-spawner-config.json"
ENCOUNTER_DOC = ROOT / "docs" / "mechanics" / "ENCOUNTER_DESIGN.md"
DOWNSAMPLE = 4
JPEG_QUALITY = 84
BUCKETS = ("common", "uncommon", "rare", "ultra-rare")
POSITIONS = {"grounded": "On land", "surface": "On the water's surface", "submerged": "Swimming underwater",
             "seafloor": "On the lake or sea floor"}
BOX_KEYS = ("minX", "maxX", "minZ", "maxZ")
KNOWN_CONDITIONS = set(BOX_KEYS) | {"canSeeSky", "timeRange", "isRaining", "minY", "maxY", "neededNearbyBlocks", "biomes"}
TIMES = ("day", "night")

# Settlements whose label would give a discovery away. Every other data/towns.json town is labelled, and a town that
# data/placements.json marks "retired" is dropped by the data itself.
HIDDEN_SETTLEMENTS = {
    "displaced_city": "hidden on purpose (docs/world-building/CRITICAL_PATH_WALK_1.md; a discovery waystone)",
    "frostpeak_shrine": "a shrine",
    "great_oak_pallet": "an elder tree: its nests are left to Professor Oak's hints",
    "sentinel_spruce_tarn": "an elder tree: its nests are left to Professor Oak's hints",
    "patriarch_wedge": "an elder tree: its nests are left to Professor Oak's hints",
    "cherry_elder_shrew": "an elder tree: its nests are left to Professor Oak's hints",
}

# Species ids whose display name is not their title-cased id.
SPECIAL_NAMES = {"mrmime": "Mr. Mime", "mimejr": "Mime Jr.", "mrrime": "Mr. Rime", "farfetchd": "Farfetch'd",
                 "sirfetchd": "Sirfetch'd", "nidoranf": "Nidoran F", "nidoranm": "Nidoran M", "porygonz": "Porygon-Z",
                 "hooh": "Ho-Oh", "jangmoo": "Jangmo-o", "hakamoo": "Hakamo-o", "kommoo": "Kommo-o",
                 "typenull": "Type: Null", "flabebe": "Flabebe", "hooh_": "Ho-Oh"}
FORMS = {"alolan": "Alolan", "galarian": "Galarian", "hisuian": "Hisuian", "paldean": "Paldean"}


def species_name(pokemon):
    parts = pokemon.split()
    base = SPECIAL_NAMES.get(parts[0], parts[0].replace("_", " ").title())
    forms = [FORMS.get(p, p.title()) for p in parts[1:]]
    return " ".join(forms + [base])


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


# ------------------------------------------------------------------ the compiled pools


def compile_pack():
    """Run tools/compile_spawns.py into a temporary directory and return {relative path: parsed json}."""
    with tempfile.TemporaryDirectory() as tmp:
        with contextlib.redirect_stdout(io.StringIO()):
            rc = compile_spawns.main(["--out", tmp])
        if rc:
            raise SystemExit("tools/compile_spawns.py failed (exit %s)" % rc)
        return read_pack(Path(tmp))


def read_pack(base):
    pools = {}
    root = Path(base) / "data" / "cobblers"
    if not root.is_dir():
        raise SystemExit("no compiled pack at %s (run python tools/compile_spawns.py)" % base)
    for f in sorted(root.rglob("*.json")):
        pools[f.relative_to(root).as_posix()] = json.loads(f.read_text(encoding="utf-8"))
    return pools


def condition_text(cond):
    out = []
    for k in sorted(cond):
        if k not in KNOWN_CONDITIONS:
            raise SystemExit("compiled condition key %r is not one this page knows how to describe; add it to "
                             "tools/player_guide_map.py rather than letting the page misreport it" % k)
    if cond.get("timeRange"):
        if cond["timeRange"] not in TIMES:
            raise SystemExit("timeRange %r is not day or night; the day/night rates would be wrong" % cond["timeRange"])
        out.append("%s only" % cond["timeRange"])
    if cond.get("isRaining") is True:
        out.append("rain only")
    elif cond.get("isRaining") is False:
        out.append("clear weather only")
    if "minY" in cond:
        out.append("at y%d and above" % cond["minY"])
    if "maxY" in cond:
        out.append("at y%d and below" % cond["maxY"])
    if cond.get("neededNearbyBlocks"):
        out.append("next to " + ", ".join(b.split(":")[-1].replace("_", " ") for b in cond["neededNearbyBlocks"]))
    if cond.get("biomes"):
        out.append("biome " + ", ".join(b.split(":")[-1].replace("_", " ") for b in cond["biomes"]))
    if cond.get("canSeeSky") is False:
        out.append("out of sight of the sky")
    return out


def entry_row(s):
    cond = s["condition"]
    if s["bucket"] not in BUCKETS:
        raise SystemExit("bucket %r in %s is not one of %s" % (s["bucket"], s["id"], BUCKETS))
    if s["spawnablePositionType"] not in POSITIONS:
        raise SystemExit("position %r in %s is not one of %s" % (s["spawnablePositionType"], s["id"], sorted(POSITIONS)))
    lo, hi = (int(v) for v in s["level"].split("-"))
    rest = {k: v for k, v in cond.items() if k not in BOX_KEYS and k != "canSeeSky"}
    return {"pokemon": s["pokemon"], "bucket": s["bucket"], "pos": s["spawnablePositionType"], "lo": lo, "hi": hi,
            "weight": float(s["weight"]), "cond": rest, "box": tuple(cond[k] for k in BOX_KEYS)}


def rates(entries, bucket_weights):
    """{row key: {"day": chance, "night": chance, "inb_day": share in bucket, ...}} for one box's entries.

    Per position type. Rain-only entries are kept apart (chance None). Entries that share a key (one species in two
    crossed tables of a route box) add their weights."""
    merged = {}
    for e in entries:
        key = (e["pos"], e["pokemon"], e["bucket"], e["lo"], e["hi"], json.dumps(e["cond"], sort_keys=True))
        merged[key] = merged.get(key, 0.0) + e["weight"]
    out = {}
    for pos in POSITIONS:
        keys = [k for k in merged if k[0] == pos]
        for t in TIMES:
            active = [k for k in keys
                      if json.loads(k[5]).get("timeRange") in (None, t) and json.loads(k[5]).get("isRaining") is not True]
            present = sorted({k[2] for k in active})
            wsum = sum(bucket_weights[b] for b in present)
            for k in keys:
                out.setdefault(k, {})
                if k not in active:
                    out[k][t] = None
                    continue
                inb = sum(merged[q] for q in active if q[2] == k[2])
                out[k][t] = bucket_weights[k[2]] / wsum * merged[k] / inb
                out[k]["inb_" + t] = merged[k] / inb
    return out


def pool_area(spawns, keep):
    """(boxes, per-box entry lists) for the entries keep() accepts."""
    by_box = {}
    for s in spawns:
        if not keep(s):
            continue
        r = entry_row(s)
        by_box.setdefault(r["box"], []).append(r)
    return by_box


def summarise(by_box, bucket_weights):
    """Rows of an area: per row key the min and max chance over its boxes (one value where the boxes agree)."""
    acc = {}
    for box in sorted(by_box):
        for k, v in rates(by_box[box], bucket_weights).items():
            a = acc.setdefault(k, {t: [] for t in TIMES} | {"inb": []})
            for t in TIMES:
                a[t].append(v.get(t))
            if v.get("inb_day") is not None or v.get("inb_night") is not None:
                a["inb"].append(v.get("inb_day") if v.get("inb_day") is not None else v.get("inb_night"))
    rows = []
    for k in sorted(acc, key=lambda k: (list(POSITIONS).index(k[0]), BUCKETS.index(k[2]), k[1], k[3])):
        a = acc[k]
        cond = json.loads(k[5])
        row = {"pos": k[0], "sp": k[1], "name": species_name(k[1]), "bucket": k[2], "lv": [k[3], k[4]],
               "cond": condition_text(cond), "rain": cond.get("isRaining") is True}
        for t in TIMES:
            vals = [v for v in a[t] if v is not None]
            # a box where this row cannot appear at time t is a box with no chance of it then, so it counts as 0
            if len(vals) < len(a[t]) and vals:
                vals = vals + [0.0]
            row[t] = [round(min(vals), 6), round(max(vals), 6)] if vals else None
        row["inb"] = [round(min(a["inb"]), 6), round(max(a["inb"]), 6)] if a["inb"] else None
        rows.append(row)
    return rows


# ------------------------------------------------------------------ the picture


def relief(heights, sea):
    """A shaded-relief RGB image of the heightmap, 1 pixel per DOWNSAMPLE blocks, and the downsampled heights."""
    n = heights.shape[0] // DOWNSAMPLE
    h = heights[:n * DOWNSAMPLE, :n * DOWNSAMPLE].reshape(n, DOWNSAMPLE, n, DOWNSAMPLE).mean(axis=(1, 3))
    gz, gx = np.gradient(h.astype(np.float64) * 1.6 / DOWNSAMPLE)
    az, alt = math.radians(315.0), math.radians(40.0)
    slope = np.arctan(np.hypot(gx, gz))
    aspect = np.arctan2(-gx, gz)
    shade = np.sin(alt) * np.cos(slope) + np.cos(alt) * np.sin(slope) * np.cos(az - aspect)
    shade = np.clip(shade, 0.0, 1.0)
    stops = [(sea, (214, 205, 160)), (sea + 4, (128, 176, 98)), (sea + 50, (110, 158, 86)),
             (sea + 110, (168, 160, 104)), (sea + 170, (150, 128, 104)), (sea + 230, (140, 134, 128)),
             (sea + 290, (236, 238, 240))]
    levels = np.array([s[0] for s in stops], dtype=np.float64)
    land = np.zeros(h.shape + (3,))
    for c in range(3):
        land[..., c] = np.interp(h, levels, [s[1][c] for s in stops])
    land *= (0.45 + 0.75 * shade)[..., None]
    depth = np.clip((sea - h) / 40.0, 0.0, 1.0)[..., None]
    shallow, deep = np.array([126, 186, 222.0]), np.array([34, 78, 138.0])
    water = shallow * (1 - depth) + deep * depth
    img = np.where((np.round(h) < sea)[..., None], water, land)
    img = np.clip(np.round(img), 0, 255).astype(np.uint8)
    buf = io.BytesIO()
    Image.fromarray(img, "RGB").save(buf, "JPEG", quality=JPEG_QUALITY, optimize=True)
    return buf.getvalue(), h


def land_share(boxes, small, sea):
    cells = dry = 0
    n = small.shape[0]
    for x0, x1, z0, z1 in boxes:
        a, b = max(0, x0 // DOWNSAMPLE), min(n, x1 // DOWNSAMPLE + 1)
        c, d = max(0, z0 // DOWNSAMPLE), min(n, z1 // DOWNSAMPLE + 1)
        if a >= b or c >= d:
            continue
        sub = small[c:d, a:b]
        cells += sub.size
        dry += int((np.round(sub) >= sea).sum())
    return dry / cells if cells else 0.0


def box_path(boxes):
    return "".join("M%d %dh%dv%dh-%dz" % (x0, z0, x1 - x0 + 1, z1 - z0 + 1, x1 - x0 + 1) for x0, x1, z0, z1 in sorted(boxes))


def label_point(boxes):
    tot = sum((b[1] - b[0] + 1) * (b[3] - b[2] + 1) for b in boxes)
    cx = sum((b[0] + b[1] + 1) / 2 * (b[1] - b[0] + 1) * (b[3] - b[2] + 1) for b in boxes) / tot
    cz = sum((b[2] + b[3] + 1) / 2 * (b[1] - b[0] + 1) * (b[3] - b[2] + 1) for b in boxes) / tot
    if not any(b[0] <= cx <= b[1] + 1 and b[2] <= cz <= b[3] + 1 for b in boxes):
        b = min(boxes, key=lambda b: ((b[0] + b[1]) / 2 - cx) ** 2 + ((b[2] + b[3]) / 2 - cz) ** 2)
        cx, cz = (b[0] + b[1] + 1) / 2, (b[2] + b[3] + 1) / 2
    return round(cx), round(cz)


def hue(i):
    return round((i * 137.508 + 20) % 360)


# ------------------------------------------------------------------ the model


def clean_name(s):
    return (s or "").replace("�", "-")


def build_model(pools, heights_small, sea, bucket_weights):
    nz = load_json(ROOT / "data" / "nuzlocke_zones.json")
    regions = load_json(ROOT / "data" / "regions.json")
    routes = load_json(ROOT / "data" / "routes.json")
    zones = {z["zone"]: z for z in nz["zones"]}
    reg_name = {r["id"]: r["display_name"] for r in regions["regions"]}
    reg_name.update({m["id"]: m["display_name"] for m in regions["marine_regions"]})
    sub_ids = sorted(s["id"] for s in regions["subregions"])
    region_order = sorted(reg_name)
    excluded = {"hearts": 0, "heart_areas": set(), "mega_den_rows": 0, "mega_den_areas": set(), "dropped": [],
                "habitat_pools": sorted(k.split("/")[-1][:-5] for k in pools if k.startswith("habitat_pools/"))}
    areas, notes = [], []

    def zone_area(stem, kind, spawns, region):
        z = zones.get(stem)
        base_re = re.compile(re.escape(stem) + r"_(?:s\d+_)?b\d+_")
        heart_re = re.compile(re.escape(stem) + r"_h\d{4}_")

        def keep(s):
            if heart_re.match(s["id"]):
                excluded["hearts"] += 1
                excluded["heart_areas"].add(stem)
                return False
            if base_re.match(s["id"]):
                return True
            excluded["mega_den_rows"] += 1
            excluded["mega_den_areas"].add(stem)
            return False

        by_box = pool_area(spawns, keep)
        boxes = sorted(by_box)
        rows = summarise(by_box, bucket_weights)
        share = land_share(boxes, heights_small, sea)
        return {"id": stem, "kind": kind, "name": z["name"] if z else stem.replace("_", " ").title(),
                "region": region, "zones": [stem] if z else [], "boxes": boxes, "rows": rows,
                "land_share": round(share, 3), "is_zone": z is not None}

    for key in sorted(k for k in pools if k.startswith("spawn_pool_world/subregions/")):
        stem = key.split("/")[-1][:-5]
        parent = next(s["parent"] for s in regions["subregions"] if s["id"] == stem)
        a = zone_area(stem, "land", pools[key]["spawns"], parent)
        land_rows = [r for r in a["rows"] if r["pos"] == "grounded"]
        if a["land_share"] == 0 and len(land_rows) == len(a["rows"]):
            excluded["dropped"].append((stem, "compiled with %d land Pokemon, but none of its %d boxes has ground at "
                                        "or above sea level (y%d) on the heightmap (4-block downsample), so nothing in "
                                        "it can spawn; left off the map. data/nuzlocke_zones.json lists it under "
                                        "not_zones too." % (len(a["rows"]), len(a["boxes"]), sea)))
            continue
        areas.append(a)
    for key in sorted(k for k in pools if k.startswith("spawn_pool_world/marine/")):
        stem = key.split("/")[-1][:-5]
        z = zones.get(stem) or {}
        areas.append(zone_area(stem, "sea", pools[key]["spawns"], z.get("region") or "windward_deep"))
    for key in sorted(k for k in pools if k.startswith("spawn_pool_world/waterways/")):
        stem = key.split("/")[-1][:-5]
        areas.append(zone_area(stem, "waterway", pools[key]["spawns"], "waterways"))
    reg_name["waterways"] = "Waterways"
    reg_name["routes"] = "Route paths"

    route_meta = {r["id"]: r for r in routes["routes"]}
    for key in sorted(k for k in pools if k.startswith("spawn_pool_world/routes/")):
        rid = key.split("/")[-1][:-5]
        boxes_subs, by_box_all, box_order = {}, {}, {}
        for s in pools[key]["spawns"]:
            m = re.match(r"^([a-z0-9]+_b\d+)_(?:p\d+_)?(.*)$", s["id"])
            if not m:
                raise SystemExit("route entry id %r does not parse" % s["id"])
            sub = max((x for x in sub_ids if m.group(2).startswith(x + "_")), key=len, default=None)
            if sub is None:
                raise SystemExit("route entry %r names no data/regions.json sub-region" % s["id"])
            r = entry_row(s)
            box_order[r["box"]] = min(box_order.get(r["box"], 1 << 30), int(m.group(1).rsplit("_b", 1)[1]))
            boxes_subs.setdefault(r["box"], set()).add(sub)
            by_box_all.setdefault(r["box"], []).append(r)
        groups = {}
        for box, subs in boxes_subs.items():
            groups.setdefault(tuple(sorted(subs)), {})[box] = by_box_all[box]
        rname = clean_name(route_meta.get(rid, {}).get("display_name") or rid)
        short = re.split(r"\s[—–-]\s", rname)[0].strip()
        # along the route: the corridor's own box numbering runs from its start
        for n, subs in enumerate(sorted(groups, key=lambda g: (min(box_order[b] for b in groups[g]), g))):
            by_box = groups[subs]
            zn = [zones[s]["name"] if s in zones else s for s in subs]
            areas.append({"id": "%s__%d" % (rid, n), "kind": "route", "name": "%s path, %s" % (short, " / ".join(zn)),
                          "route": short, "short": " / ".join(zn), "region": "routes", "zones": [s for s in subs if s in zones],
                          "boxes": sorted(by_box), "rows": summarise(by_box, bucket_weights),
                          "land_share": round(land_share(sorted(by_box), heights_small, sea), 3), "is_zone": False})
    # land zones without a compiled pool would be a gap in the page
    missing = sorted(z for z, v in zones.items() if v["kind"] == "land" and z not in {a["id"] for a in areas})
    if missing:
        raise SystemExit("land catch zones with no compiled sub-region pool: %s" % missing)
    return {"areas": areas, "reg_name": reg_name, "region_order": region_order, "excluded": excluded, "zones": zones,
            "nz": nz, "regions": regions, "routes": routes, "notes": notes}


def data_notes(model, bucket_weights):
    """Where the data and the documents (or two data files) disagree. Every number here is computed now."""
    notes = []
    doc = ENCOUNTER_DOC.read_text(encoding="utf-8") if ENCOUNTER_DOC.is_file() else ""
    m = re.search(r"common ([\d.]+), uncommon ([\d.]+), rare ([\d.]+),\s*ultra-rare ([\d.]+)", doc)
    if m:
        docw = dict(zip(BUCKETS, (float(v) for v in m.groups())))
        if any(abs(docw[b] - bucket_weights[b]) > 1e-9 for b in BUCKETS):
            notes.append("Bucket weights: docs/mechanics/ENCOUNTER_DESIGN.md gives common %s, uncommon %s, rare %s, "
                         "ultra-rare %s (Cobbleverse's 1.7 config). The server's recorded config "
                         "(server/config/mods/cobblemon/spawning/best-spawner-config.json worldBuckets) says %s. "
                         "This page uses the server's." % (*(m.groups()),
                         ", ".join("%s %s" % (b, fmt_num(bucket_weights[b])) for b in BUCKETS)))
    bad = [r["id"] for r in model["routes"]["routes"] if "�" in (r.get("display_name") or "")]
    if bad:
        notes.append("Route names: %d of %d data/routes.json display names carry a broken character (U+FFFD where a "
                     "dash was meant); shown here with a hyphen." % (len(bad), len(model["routes"]["routes"])))
    stale = [s["id"] for s in model["regions"]["subregions"]
             if (s.get("encounters") or {}).get("status") == "empty"
             and any(a["id"] == s["id"] and a["rows"] for a in model["areas"])]
    if stale:
        notes.append("data/regions.json still marks %d sub-regions' encounters as \"empty, not populated\" (e.g. %s); "
                     "their compiled pools are populated, and the compiled pools are what the game reads."
                     % (len(stale), ", ".join(sorted(stale)[:3])))
    for a in model["areas"]:
        z = model["zones"].get(a["id"])
        if not z or a["kind"] == "route":
            continue
        n = len({r["sp"] for r in a["rows"]})
        lv = [min(r["lv"][0] for r in a["rows"]), max(r["lv"][1] for r in a["rows"])] if a["rows"] else None
        if z.get("species") is not None and z["species"] != n:
            notes.append("%s: data/nuzlocke_zones.json counts %d species, the compiled pool has %d (hearts excluded)."
                         % (a["name"], z["species"], n))
        if z.get("levels") and lv and list(z["levels"]) != lv:
            notes.append("%s: data/nuzlocke_zones.json gives levels %s, the compiled pool (its rarer spot excluded) %s."
                         % (a["name"], "-".join(map(str, z["levels"])), "-".join(map(str, lv))))
    for stem, why in model["excluded"]["dropped"]:
        notes.append("%s: %s" % (stem, why))
    return notes


def fmt_num(v):
    return ("%g" % v)


# ------------------------------------------------------------------ the page


CSS = r"""
:root{--bg:#f6f4ee;--fg:#1d2126;--muted:#5b6470;--card:#ffffff;--line:#d5d0c4;--accent:#b4441a;--chip:#efe9dc;
--common:#3b7a3b;--uncommon:#2f5f9e;--rare:#8a3fa0;--ultra-rare:#b4441a;--btext:#fff;color-scheme:light}
:root[data-theme=dark]{--bg:#14171b;--fg:#e7e9ec;--muted:#9aa3ad;--card:#1d2127;--line:#353b44;--accent:#f08a5d;
--chip:#2a3038;--common:#7cc47c;--uncommon:#7aa9ee;--rare:#d08ae4;--ultra-rare:#f08a5d;--btext:#111;color-scheme:dark}
@media (prefers-color-scheme:dark){:root:not([data-theme=light]){--bg:#14171b;--fg:#e7e9ec;--muted:#9aa3ad;
--card:#1d2127;--line:#353b44;--accent:#f08a5d;--chip:#2a3038;--common:#7cc47c;--uncommon:#7aa9ee;--rare:#d08ae4;
--ultra-rare:#f08a5d;--btext:#111;color-scheme:dark}}
*{box-sizing:border-box}html,body{margin:0;background:var(--bg);color:var(--fg);
font:15px/1.45 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}
header{display:flex;flex-wrap:wrap;gap:.5rem 1rem;align-items:center;padding:.6rem 1rem;border-bottom:1px solid var(--line)}
header h1{font-size:1.15rem;margin:0;flex:1 1 16rem}
#q{font:inherit;padding:.4rem .6rem;border:1px solid var(--line);border-radius:6px;background:var(--card);color:var(--fg);
width:min(22rem,100%)}
button{font:inherit;padding:.35rem .7rem;border:1px solid var(--line);border-radius:6px;background:var(--card);
color:var(--fg);cursor:pointer}button:hover{border-color:var(--accent)}
main{display:grid;grid-template-columns:minmax(0,1.35fr) minmax(20rem,1fr);gap:0;height:calc(100vh - 3.4rem);min-height:30rem}
#mapwrap{position:relative;overflow:hidden;border-right:1px solid var(--line);background:#224e8a;touch-action:none}
#map{width:100%;height:100%;display:block;cursor:grab;user-select:none}
#map.drag{cursor:grabbing}
.tools{position:absolute;top:.5rem;left:.5rem;display:flex;flex-direction:column;gap:.3rem}
.tools button{width:2.2rem;height:2.2rem;padding:0;font-size:1.1rem;opacity:.92}
.layers{position:absolute;top:.5rem;right:.5rem;background:var(--card);border:1px solid var(--line);border-radius:6px;
padding:.3rem .5rem;font-size:.82rem;opacity:.94}
.layers label{display:block;white-space:nowrap}
#coord{position:absolute;bottom:.4rem;left:.5rem;background:var(--card);border:1px solid var(--line);border-radius:4px;
padding:.1rem .4rem;font-size:.78rem;opacity:.9;font-variant-numeric:tabular-nums}
#panel{overflow:auto;padding:.8rem 1rem 2rem}
#panel h2{margin:.1rem 0 .2rem;font-size:1.2rem}#panel h3{margin:1rem 0 .3rem;font-size:.95rem;color:var(--muted);
text-transform:uppercase;letter-spacing:.04em}
.meta{color:var(--muted);font-size:.88rem;margin:.1rem 0}
table{border-collapse:collapse;width:100%;font-size:.86rem}
th,td{text-align:left;padding:.25rem .35rem;border-bottom:1px solid var(--line);vertical-align:top}
th{font-weight:600;color:var(--muted);font-size:.78rem}td.n{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}
.b{display:inline-block;padding:0 .35rem;border-radius:4px;font-size:.76rem;font-weight:600;color:var(--btext);
white-space:nowrap}
.b.common{background:var(--common)}.b.uncommon{background:var(--uncommon)}.b.rare{background:var(--rare)}
.b.ultra-rare{background:var(--ultra-rare)}
.cond{color:var(--muted);font-size:.8rem}
a,.link{color:var(--accent);cursor:pointer;text-decoration:underline;text-underline-offset:2px}
.reglist{columns:2 13rem;column-gap:1.2rem;padding:0;margin:.3rem 0;list-style:none}
.reglist li{break-inside:avoid;margin:0 0 .6rem}.reglist b{display:block;font-size:.88rem}
.reglist span{display:inline-block;margin:.05rem .4rem .05rem 0;font-size:.86rem}
.sw{display:inline-block;width:.8rem;height:.8rem;border-radius:2px;vertical-align:-.05rem;margin-right:.3rem;
border:1px solid rgba(0,0,0,.25)}
.area{fill-opacity:.30;stroke:none;cursor:pointer}.area:hover{fill-opacity:.55}
#map.has-sel .area{fill-opacity:.12}#map.has-sel .area.sel{fill-opacity:.7}
#map.has-hit .area{fill-opacity:.08}#map.has-hit .area.hit{fill-opacity:.65}
#map.has-hit .area.sel,#map.has-sel .area.sel{fill-opacity:.75}
.outline{fill:none;stroke:#fff;stroke-opacity:.55;vector-effect:non-scaling-stroke;stroke-width:1;pointer-events:none}
.cl{fill:none;stroke:#fff3c4;stroke-width:2;stroke-dasharray:6 5;vector-effect:non-scaling-stroke;pointer-events:none;
stroke-opacity:.9}
.lbl{font-family:system-ui,sans-serif;paint-order:stroke;stroke:#000;stroke-opacity:.7;fill:#fff;pointer-events:none;
text-anchor:middle;dominant-baseline:middle}
.lbl.town{font-weight:700;fill:#fffbe8}.lbl.area-l{font-style:italic;fill:#e9f2ff}
.dot{fill:#fffbe8;stroke:#000;stroke-opacity:.7;vector-effect:non-scaling-stroke;pointer-events:none}
section.doc{max-width:62rem;margin:0 auto;padding:.6rem 1rem}section.doc h2{font-size:1.05rem;margin:1.2rem 0 .3rem}
section.doc li{margin:.15rem 0}.small{font-size:.85rem;color:var(--muted)}
.spec-row{cursor:pointer}.spec-row:hover td{background:var(--chip)}
.legend-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(14rem,1fr));gap:.2rem 1rem;font-size:.88rem}
@media (max-width:820px){main{grid-template-columns:minmax(0,1fr);height:auto}#mapwrap{height:62vh;border-right:0;
border-bottom:1px solid var(--line)}#panel{max-height:none;overflow-x:auto;padding:.6rem .6rem 1.5rem}.reglist{columns:1}
header h1{flex-basis:100%}#q{flex:1 1 auto;width:auto;min-width:0}th,td{padding:.2rem .25rem}table{font-size:.8rem}
.layers{font-size:.75rem;padding:.2rem .35rem}}
"""

JS = r"""
(function(){
const D=JSON.parse(document.getElementById('data').textContent);
const svg=document.getElementById('map'),panel=document.getElementById('panel');
const W=D.view;let vb=W.slice();const MINW=256;
const byId={};D.areas.forEach(a=>byId[a.id]=a);
const pct=v=>{if(v===null)return'-';const p=v*100;if(p===0)return'0%';if(p>=10)return p.toFixed(0)+'%';
 if(p>=1)return p.toFixed(1)+'%';return p.toPrecision(2)+'%'};
const rng=r=>r===null?'-':(Math.abs(r[0]-r[1])<5e-5?pct(r[0]):pct(r[0])+'-'+pct(r[1]));
const lv=r=>r[0]===r[1]?String(r[0]):r[0]+'-'+r[1];
const esc=s=>String(s).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
function setVB(){svg.setAttribute('viewBox',vb.join(' '));const r=svg.getBoundingClientRect();
 const upp=Math.max(vb[2]/(r.width||800),vb[3]/(r.height||800));
 svg.querySelectorAll('.lbl').forEach(t=>{const px=+t.dataset.s;t.setAttribute('font-size',(px*upp).toFixed(1));
 t.setAttribute('stroke-width',(px*upp/5).toFixed(1));if(t.dataset.dy)t.setAttribute('dy',(-px*upp*0.9).toFixed(1))});
 svg.querySelectorAll('.dot').forEach(c=>c.setAttribute('r',(3.5*upp).toFixed(1)));
 const al=document.getElementById('L-alabels');const show=document.getElementById('t-alabels').checked&&upp<8;
 al.style.display=show?'':'none';}
window.addEventListener('resize',()=>setVB());
function toWorld(cx,cy){const p=svg.createSVGPoint();p.x=cx;p.y=cy;return p.matrixTransform(svg.getScreenCTM().inverse())}
function zoomAt(f,wx,wy){let nw=Math.min(Math.max(vb[2]*f,MINW),W[2]*1.2);const r=nw/vb[2];
 vb=[wx-(wx-vb[0])*r,wy-(wy-vb[1])*r,nw,vb[3]*r];setVB()}
svg.addEventListener('wheel',e=>{e.preventDefault();const p=toWorld(e.clientX,e.clientY);
 zoomAt(e.deltaY>0?1.2:1/1.2,p.x,p.y)},{passive:false});
const ptrs=new Map();let moved=0,start=null,pinch=null;
svg.addEventListener('pointerdown',e=>{svg.setPointerCapture(e.pointerId);ptrs.set(e.pointerId,{x:e.clientX,y:e.clientY});
 moved=0;start={x:e.clientX,y:e.clientY,t:e.target};if(ptrs.size===2){const[a,b]=[...ptrs.values()];
 pinch={d:Math.hypot(a.x-b.x,a.y-b.y)}}svg.classList.add('drag')});
svg.addEventListener('pointermove',e=>{const p=toWorld(e.clientX,e.clientY);
 document.getElementById('coord').textContent='x '+Math.round(p.x)+'  z '+Math.round(p.y);
 if(!ptrs.has(e.pointerId))return;const prev=ptrs.get(e.pointerId);ptrs.set(e.pointerId,{x:e.clientX,y:e.clientY});
 if(ptrs.size===2&&pinch){const[a,b]=[...ptrs.values()];const d=Math.hypot(a.x-b.x,a.y-b.y);
  const m=toWorld((a.x+b.x)/2,(a.y+b.y)/2);zoomAt(pinch.d/d,m.x,m.y);pinch.d=d;moved=99;return}
 const r=svg.getBoundingClientRect();const s=Math.max(vb[2]/r.width,vb[3]/r.height);
 vb[0]-=(e.clientX-prev.x)*s;vb[1]-=(e.clientY-prev.y)*s;moved+=Math.abs(e.clientX-prev.x)+Math.abs(e.clientY-prev.y);setVB()});
function up(e){ptrs.delete(e.pointerId);if(ptrs.size<2)pinch=null;if(!ptrs.size)svg.classList.remove('drag');
 if(e.type==='pointerup'&&moved<6&&start){const el=document.elementFromPoint(e.clientX,e.clientY);
 const g=el&&el.closest&&el.closest('[data-area]');if(g)selectArea(g.dataset.area,false);}}
svg.addEventListener('pointerup',up);svg.addEventListener('pointercancel',up);
document.getElementById('zin').onclick=()=>zoomAt(1/1.5,vb[0]+vb[2]/2,vb[1]+vb[3]/2);
document.getElementById('zout').onclick=()=>zoomAt(1.5,vb[0]+vb[2]/2,vb[1]+vb[3]/2);
document.getElementById('zreset').onclick=()=>{vb=W.slice();setVB()};
function fitTo(b){const pad=Math.max(b[2],b[3])*0.35+120;const w=Math.max(b[2]+2*pad,MINW*2),h=Math.max(b[3]+2*pad,MINW*2);
 const r=svg.getBoundingClientRect();const asp=r.width/r.height||1;let nw=Math.max(w,h*asp),nh=nw/asp;
 vb=[b[0]+b[2]/2-nw/2,b[1]+b[3]/2-nh/2,nw,nh];setVB()}
['routes','outlines','towns','alabels','centre'].forEach(k=>{const c=document.getElementById('t-'+k);
 c.onchange=()=>{document.getElementById('L-'+k).style.display=c.checked?'':'none';setVB()}});
function clearMarks(){svg.classList.remove('has-sel','has-hit');svg.querySelectorAll('.sel,.hit').forEach(n=>n.classList.remove('sel','hit'))}
function table(rows,showPos){let h='';const groups={};rows.forEach(r=>(groups[r.pos]=groups[r.pos]||[]).push(r));
 D.positions.forEach(([p,label])=>{const g=groups[p];if(!g)return;h+='<h3>'+esc(label)+'</h3><table><thead><tr><th>Pokemon</th>'+
 '<th>Bucket</th><th>Levels</th><th class="n" title="Chance per spawn at this kind of spot, by day">Day</th>'+
 '<th class="n" title="Chance per spawn at this kind of spot, at night">Night</th></tr></thead><tbody>';
 g.forEach(r=>{const c=r.cond.length?'<div class="cond">'+esc(r.cond.join('; '))+'</div>':'';
  const dn=r.rain?'<td class="n" colspan="2">in rain</td>':'<td class="n">'+rng(r.day)+'</td><td class="n">'+rng(r.night)+'</td>';
  h+='<tr><td><span class="link" data-sp="'+esc(r.sp)+'">'+esc(r.name)+'</span>'+c+'</td><td><span class="b '+r.bucket+'" title="'+
  (r.inb?esc(rng(r.inb)+' of this spot\'s '+r.bucket+' draws'):'')+'">'+r.bucket+'</span></td><td>'+lv(r.lv)+'</td>'+dn+'</tr>'});
 h+='</tbody></table>'});return h}
function selectArea(id,fit){const a=byId[id];if(!a)return;clearMarks();
 history.replaceState(null,'','#area='+encodeURIComponent(id));svg.classList.add('has-sel');
 svg.querySelectorAll('[data-area="'+id+'"]').forEach(n=>n.classList.add('sel'));if(fit)fitTo(a.bbox);
 const zs=a.zones.map(z=>D.zoneNames[z]||z);
 let h='<p class="meta"><span class="link" id="back">All areas</span></p><h2>'+esc(a.name)+'</h2>';
 h+='<p class="meta">'+esc(D.regName[a.region]||a.region)+' &middot; '+esc(D.kinds[a.kind])+' &middot; around x '+a.label[0]+', z '+
  a.label[1]+' &middot; levels '+lv(a.lv)+' &middot; '+a.nsp+' species</p>';
 if(a.kind==='route')h+='<p class="meta">The path itself has its own table, a cut-down copy of the area'+(zs.length>1?'s':'')+
  ' it crosses. For a Nuzlocke this counts as <b>'+esc(zs.join(' or '))+'</b>'+(zs.length>1?' (it runs along a border)':'')+'.</p>';
 else if(a.is_zone)h+='<p class="meta">Nuzlocke catch zone: <b>'+esc(a.name)+'</b>. The first Pokemon you meet here is your catch for it.</p>';
 if(a.land<1&&a.kind==='land')h+='<p class="meta">'+Math.round(a.land*100)+'% of it is dry ground on the heightmap; the rest is water.</p>';
 h+=table(a.rows);panel.innerHTML=h;panel.scrollTop=0;
 document.getElementById('back').onclick=home;bindSp()}
function bindSp(){panel.querySelectorAll('[data-sp]').forEach(n=>n.onclick=()=>selectSpecies(n.dataset.sp))}
function selectSpecies(sp){const hits=D.areas.filter(a=>a.rows.some(r=>r.sp===sp));clearMarks();
 if(sp)history.replaceState(null,'','#pokemon='+encodeURIComponent(sp));
 if(!hits.length){panel.innerHTML='<p class="meta"><span class="link" id="back">All areas</span></p><p>No campaign area lists that Pokemon.</p>';
  document.getElementById('back').onclick=home;return}
 svg.classList.add('has-hit');hits.forEach(a=>svg.querySelectorAll('[data-area="'+a.id+'"]').forEach(n=>n.classList.add('hit')));
 const name=hits[0].rows.find(r=>r.sp===sp).name;
 let h='<p class="meta"><span class="link" id="back">All areas</span></p><h2>'+esc(name)+'</h2><p class="meta">Found in '+
  hits.length+' area'+(hits.length>1?'s':'')+', highlighted on the map. Pick one to see the rest of its table.</p>';
 h+='<table><thead><tr><th>Where</th><th>Bucket</th><th>Levels</th><th class="n">Day</th><th class="n">Night</th></tr></thead><tbody>';
 const rows=[];hits.forEach(a=>a.rows.filter(r=>r.sp===sp).forEach(r=>rows.push([a,r])));
 rows.sort((x,y)=>(Math.max(...(y[1].day||[0]),...(y[1].night||[0])))-(Math.max(...(x[1].day||[0]),...(x[1].night||[0]))));
 rows.forEach(([a,r])=>{const c=[D.posShort[r.pos]].concat(r.cond).join('; ');
  const dn=r.rain?'<td class="n" colspan="2">in rain</td>':'<td class="n">'+rng(r.day)+'</td><td class="n">'+rng(r.night)+'</td>';
  h+='<tr class="spec-row" data-go="'+a.id+'"><td><span class="link">'+esc(a.name)+'</span><div class="cond">'+
  esc((D.regName[a.region]||'')+' - '+c)+'</div></td><td><span class="b '+r.bucket+'">'+r.bucket+'</span></td><td>'+lv(r.lv)+'</td>'+dn+'</tr>'});
 h+='</tbody></table>';panel.innerHTML=h;panel.scrollTop=0;document.getElementById('back').onclick=home;
 panel.querySelectorAll('[data-go]').forEach(n=>n.onclick=()=>selectArea(n.dataset.go,true))}
function home(){clearMarks();let h=document.getElementById('intro').innerHTML;h+='<ul class="reglist">';
 const item=(rid,title,as)=>'<li><b><span class="sw" style="background:'+D.regColor[rid]+'"></span>'+esc(title)+'</b>'+
  as.map(a=>'<span class="link" data-go="'+a.id+'">'+esc(a.short||a.name)+'</span>').join(' ')+'</li>';
 D.regionOrder.forEach(rid=>{const as=D.areas.filter(a=>a.region===rid);if(!as.length)return;
  if(rid!=='routes'){h+=item(rid,D.regName[rid]||rid,as);return}
  const by={};as.forEach(a=>(by[a.route]=by[a.route]||[]).push(a));
  Object.keys(by).forEach(r=>{h+=item(rid,r+' (path)',by[r])})});
 h+='</ul>';panel.innerHTML=h;panel.querySelectorAll('[data-go]').forEach(n=>n.onclick=()=>selectArea(n.dataset.go,true));
 history.replaceState(null,'',location.pathname+location.search)}
const q=document.getElementById('q');
q.addEventListener('change',()=>{const v=q.value.trim().toLowerCase();if(!v)return home();
 const m=D.species.find(s=>s[1].toLowerCase()===v)||D.species.find(s=>s[1].toLowerCase().startsWith(v))||
 D.species.find(s=>s[1].toLowerCase().includes(v));if(m)selectSpecies(m[0]);else selectSpecies('')});
q.addEventListener('keydown',e=>{if(e.key==='Enter')q.dispatchEvent(new Event('change'))});
document.getElementById('theme').onclick=()=>{const r=document.documentElement;
 const dark=r.dataset.theme?r.dataset.theme==='dark':matchMedia('(prefers-color-scheme: dark)').matches;
 r.dataset.theme=dark?'light':'dark'};
setVB();
const hm=/^#(area|pokemon)=(.+)$/.exec(location.hash);
if(hm&&hm[1]==='area'&&byId[decodeURIComponent(hm[2])])selectArea(decodeURIComponent(hm[2]),true);
else if(hm&&hm[1]==='pokemon')selectSpecies(decodeURIComponent(hm[2]));else home();
})();
"""


def build_page(pack_pools, source_note):
    heights, world = terrain.load()
    sea = int(terrain.sea_level(world))
    jpeg, small = relief(heights, sea)
    del heights
    cfg = load_json(SPAWNER_CONFIG)
    bucket_weights = {b: float(cfg["worldBuckets"][b]) for b in BUCKETS}
    model = build_model(pack_pools, small, sea, bucket_weights)
    areas = model["areas"]
    reg_name = model["reg_name"]
    regions_used = sorted({a["region"] for a in areas},
                          key=lambda r: (r in ("waterways", "routes"), r == "routes",
                                         re.sub(r"^The ", "", reg_name.get(r, r))))
    reg_color = {}
    for i, r in enumerate(sorted(r for r in regions_used if r not in ("routes", "waterways", "windward_deep"))):
        reg_color[r] = "hsl(%d 72%% 52%%)" % hue(i)
    reg_color["routes"] = "repeating-linear-gradient(45deg,#fff 0 3px,#222 3px 6px)"
    reg_color["waterways"] = "#00d0e0"
    reg_color["windward_deep"] = "#2d8cff"

    allb = [b for a in areas for b in a["boxes"]]
    minx = min([0] + [b[0] for b in allb]) - 64
    minz = min([0] + [b[2] for b in allb]) - 64
    maxx = max([8192] + [b[1] + 1 for b in allb]) + 64
    maxz = max([8192] + [b[3] + 1 for b in allb]) + 64
    view = [minx, minz, maxx - minx, maxz - minz]

    out_areas = []
    for a in areas:
        bx = a["boxes"]
        bbox = [min(b[0] for b in bx), min(b[2] for b in bx)]
        bbox += [max(b[1] + 1 for b in bx) - bbox[0], max(b[3] + 1 for b in bx) - bbox[1]]
        lvs = [r["lv"] for r in a["rows"]]
        out_areas.append({"id": a["id"], "name": a["name"], "kind": a["kind"], "region": a["region"],
                          "zones": a["zones"], "is_zone": a["is_zone"], "rows": a["rows"],
                          "label": list(label_point(bx)), "bbox": bbox, "land": a["land_share"],
                          "lv": [min(v[0] for v in lvs), max(v[1] for v in lvs)] if lvs else [0, 0],
                          "nsp": len({r["sp"] for r in a["rows"]}),
                          **({"route": a["route"], "short": a["short"]} if a["kind"] == "route" else {})})
    species = sorted({(r["sp"], r["name"]) for a in areas for r in a["rows"]}, key=lambda s: s[1])
    entries = sum(len(a["rows"]) for a in areas)

    # SVG layers
    order = {"sea": 0, "waterway": 1, "land": 2, "route": 3}
    area_svg = "".join('<path class="area" data-area="%s" fill="%s" d="%s"><title>%s</title></path>'
                       % (a["id"], reg_color[a["region"]], box_path(a["boxes"]), html.escape(a["name"]))
                       for a in sorted(areas, key=lambda a: (order[a["kind"]], a["id"])) if a["kind"] != "route")
    route_svg = "".join('<path class="area" data-area="%s" fill="%s" d="%s"><title>%s</title></path>'
                        % (a["id"], "url(#rp)", box_path(a["boxes"]), html.escape(a["name"]))
                        for a in areas if a["kind"] == "route")
    shown = {a["id"] for a in areas}
    outlines = "".join('<path class="outline" d="%s"/>' % "".join(
        "M" + "L".join("%d %d" % (p[0], p[1]) for p in poly) + "Z" for poly in s["polygons"])
        for s in sorted(model["regions"]["subregions"], key=lambda s: s["id"]) if s["id"] in shown)
    centre = "".join('<polyline class="cl" points="%s"/>' % " ".join(
        "%d,%d" % (p["x"], p["z"]) for p in r["corridor"]["polyline"]) for r in model["routes"]["routes"])
    towns = load_json(ROOT / "data" / "towns.json")
    placements = load_json(ROOT / "data" / "placements.json")
    hidden_towns = dict(HIDDEN_SETTLEMENTS)
    for tid, s in placements["settlements"].items():
        if s.get("retired"):
            hidden_towns.setdefault(tid, "retired (data/placements.json)")
    town_svg, labelled = "", []
    for t in sorted(towns["towns"], key=lambda t: t["id"]):
        if t["id"] in hidden_towns:
            continue
        x, z = t["centre"]["x"], t["centre"]["z"]
        name = t.get("display_name") or t["working_name"]
        size = 13 if t["role"] in ("hometown", "gym_town", "league", "major_town") else 11
        town_svg += '<circle class="dot" cx="%d" cy="%d" r="28"/>' % (x, z)
        town_svg += '<text class="lbl town" x="%d" y="%d" data-s="%d" data-dy="1">%s</text>' % (
            x, z, size, html.escape(name))
        labelled.append(name)
    alabels = "".join('<text class="lbl area-l" x="%d" y="%d" data-s="11">%s</text>'
                      % (*label_point(a["boxes"]), html.escape(a["name"])) for a in areas if a["kind"] != "route")
    img = base64.b64encode(jpeg).decode("ascii")
    svg = ('<svg id="map" xmlns="http://www.w3.org/2000/svg" viewBox="%d %d %d %d" preserveAspectRatio="xMidYMid meet" '
           'role="img" aria-label="Shaded relief map of the region with its encounter areas">'
           '<defs><pattern id="rp" width="24" height="24" patternUnits="userSpaceOnUse" '
           'patternTransform="rotate(45)"><rect width="12" height="24" fill="#fff"/>'
           '<rect x="12" width="12" height="24" fill="#222"/></pattern></defs>'
           '<image href="data:image/jpeg;base64,%s" x="0" y="0" width="8192" height="8192" preserveAspectRatio="none"/>'
           '<g id="L-areas">%s</g><g id="L-outlines">%s</g><g id="L-routes">%s</g><g id="L-centre">%s</g>'
           '<g id="L-alabels">%s</g><g id="L-towns">%s</g></svg>'
           % (*view, img, area_svg, outlines, route_svg, centre, alabels, town_svg))

    notes = data_notes(model, bucket_weights)
    ex = model["excluded"]
    supp = load_json(ROOT / "data" / "spawn_suppression.json")
    retain = [r.replace("_", " ") for r in supp.get("retain_defaults") or []]
    pools_out = ex["habitat_pools"]

    def count(prefix):
        return sum(1 for p in pools_out if p.startswith(prefix))

    vr = count("vrc_")
    nests = count("elder_") + count("sapling_") + count("route_1_sapling")
    tg = count("training_ground_")
    other_pools = len(pools_out) - vr - nests - tg
    data = {"view": view, "areas": out_areas, "regName": reg_name, "regColor": reg_color,
            "regionOrder": regions_used, "zoneNames": {k: v["name"] for k, v in model["zones"].items()},
            "positions": [[k, v] for k, v in POSITIONS.items()],
            "posShort": {"grounded": "land", "surface": "water surface", "submerged": "underwater",
                         "seafloor": "lake/sea floor"},
            "kinds": {"land": "land area", "sea": "open sea", "waterway": "creek", "route": "route path"},
            "species": [list(s) for s in species]}
    n_land = sum(1 for a in areas if a["kind"] == "land")
    n_sea = sum(1 for a in areas if a["kind"] == "sea")
    n_way = sum(1 for a in areas if a["kind"] == "waterway")
    n_route = sum(1 for a in areas if a["kind"] == "route")
    bw = ", ".join("%s %s" % (b, fmt_num(bucket_weights[b])) for b in BUCKETS)
    e = html.escape
    intro = ('<div id="intro" hidden><h2>Where to catch what</h2><p class="meta">Tap or click an area on the map, '
             'pick one below, or search for a Pokemon. %d land areas, %d sea bands, %d creek and %d route-path '
             'sections; %d species.</p></div>' % (n_land, n_sea, n_way, n_route, len(species)))
    datalist = "".join('<option value="%s">' % e(s[1]) for s in species)
    legend = (
        '<section class="doc" id="legend"><h2>Reading the map</h2><div class="legend-grid">'
        + "".join('<div><span class="sw" style="background:%s"></span>%s</div>' % (reg_color[r], e(reg_name.get(r, r)))
                  for r in regions_used)
        + '</div><ul>'
        '<li><b>Coloured areas</b> are the campaign\'s encounter areas, one per Nuzlocke catch zone. Thin white lines '
        'are their drawn borders; the colour shows exactly where the table applies. <b>Striped</b> bands are route '
        'paths, which carry their own table; the dashed line is the route\'s centre.</li>'
        '<li><b>Blue</b> on the relief is water: ground below sea level (y%d). Dots are towns.</li>'
        '<li><b>Buckets.</b> Every spawn first rolls a bucket, then a Pokemon inside it. The server\'s weights are %s '
        '(per 100 rolls). <b>Day</b> and <b>Night</b> are the chance that one spawn at that kind of spot (land, water '
        'surface, underwater, floor) is that Pokemon. Hover a bucket badge for the share inside the bucket. A range '
        '(e.g. 3.1%%-4.0%%) means the chance differs across the area.</li>'
        '<li>Those chances are an <b>estimate</b>: they assume the bucket roll only counts buckets the spot has '
        '(not confirmed for Cobblemon 1.8), treat height and nearby-water conditions as met, and leave rain-only '
        'Pokemon out of the sum (they show "in rain"). Land and surface spawns need open sky: nothing on these tables '
        'spawns under a roof or in a cave.</li>'
        '<li>No campaign spawn is limited by biome: the area is the condition. Conditions that do apply are written '
        'under the Pokemon\'s name.</li></ul></section>' % (sea, bw))
    excluded_html = (
        '<section class="doc" id="not-covered"><h2>What this map does not show</h2><ul>'
        '<li><b>It is not everything.</b> Outside the campaign\'s areas the modpack\'s own default spawns still run '
        '(by design: %s). Inside them the defaults are meant to be switched off. Fishing is not covered.</li>'
        '<li><b>Discoveries are left for you to find:</b> legendary and mythical Pokemon, resident Pokemon, the '
        'Mega dens and their families, shrines, caches, portals, and story encounters.</li>'
        '<li><b>Rarer spots inside areas</b> (%d areas have one, with stronger alpha Pokemon) are not marked.</li>'
        '<li><b>Nests in old trees and saplings</b> carry their own birds (%d nest tables). Professor Oak knows more.</li>'
        '<li><b>Victory Road\'s caves</b> (%d cave tables) are part of the final climb and not listed; its outdoor path is.</li>'
        '<li><b>Other special places</b> with their own tables (%d, plus %d training grounds not yet built) are not shown.</li>'
        '<li>Held items on wild Pokemon are not listed.</li>'
        '<li>This page is generated from the campaign\'s data. The server may run an older or newer copy; what you '
        'meet in game wins.</li></ul></section>'
        % (e("; ".join(retain)), len(ex["heart_areas"] & {a["id"] for a in areas}), nests, vr, other_pools, tg))
    notes_html = ('<section class="doc" id="data-notes"><h2>Data notes</h2><p class="small">Where the data and a '
                  'design document (or two data files) disagree. The compiled data is what the game reads, so the '
                  'page follows it.</p><ul>' + "".join("<li>%s</li>" % e(n) for n in notes) + "</ul></section>")
    footer = ('<section class="doc small"><p>Generated by <code>python tools/player_guide_map.py</code> from %s; '
              'heightmap %s. %d areas, %d species, %d table rows. Not verified in game.</p></section>'
              % (e(source_note), e((world.get("heightmap") or {}).get("sha256", "")[:12]), len(areas), len(species),
                 entries))
    page = ('<!doctype html>\n<html lang="en"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            '<title>Cobblers: where to catch what</title><style>%s</style></head><body>'
            '<header><h1>Cobblers: where to catch what</h1>'
            '<input id="q" list="species" placeholder="Search a Pokemon" aria-label="Search a Pokemon">'
            '<datalist id="species">%s</datalist><button id="theme" type="button">Light / dark</button></header>'
            '<main><section id="mapwrap">%s<div class="tools"><button id="zin" type="button" aria-label="Zoom in">+'
            '</button><button id="zout" type="button" aria-label="Zoom out">&minus;</button><button id="zreset" '
            'type="button" aria-label="Whole map">&#8634;</button></div><div class="layers">'
            '<label><input type="checkbox" id="t-routes" checked> Route paths</label>'
            '<label><input type="checkbox" id="t-centre" checked> Route lines</label>'
            '<label><input type="checkbox" id="t-outlines" checked> Borders</label>'
            '<label><input type="checkbox" id="t-alabels" checked> Area names</label>'
            '<label><input type="checkbox" id="t-towns" checked> Towns</label></div>'
            '<div id="coord">x - z -</div></section><aside id="panel"></aside></main>%s%s%s%s%s'
            '<script id="data" type="application/json">%s</script><script>%s</script></body></html>\n'
            % (CSS, datalist, svg, intro, legend, excluded_html, notes_html, footer,
               json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False).replace("</", "<\\/"), JS))
    stats = {"areas": len(areas), "land": n_land, "sea": n_sea, "waterway": n_way, "route": n_route,
             "species": len(species), "rows": entries, "notes": notes, "labelled_towns": labelled,
             "hidden_towns": sorted(hidden_towns), "jpeg_bytes": len(jpeg), "excluded": {
                 "hearts": ex["hearts"], "heart_areas": len(ex["heart_areas"]), "mega_den_rows": ex["mega_den_rows"],
                 "habitat_pools": len(pools_out), "dropped": [d[0] for d in ex["dropped"]]}}
    return page, stats


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--out", default=str(DEFAULT_OUT))
    p.add_argument("--pack", default=None,
                   help="read this compiled pack (e.g. build/datapacks/cobblers_spawns) instead of compiling afresh")
    p.add_argument("--check", action="store_true", help="exit 1 if --out differs from a fresh build; write nothing")
    a = p.parse_args(argv)
    if a.pack:
        pools = read_pack(Path(a.pack))
        manifest = Path(a.pack) / "manifest.json"
        if not manifest.is_file():
            raise SystemExit("%s has no manifest.json, so its inputs cannot be checked; drop --pack" % a.pack)
        if manifest.is_file():
            ins = load_json(manifest).get("inputs") or {}
            stale = [k for k, v in ins.items() if (ROOT / k).is_file() and sha(ROOT / k) != v]
            if stale:
                raise SystemExit("%s was compiled from older %s; rerun python tools/compile_spawns.py or drop --pack"
                                 % (a.pack, ", ".join(stale)))
    else:
        pools = compile_pack()
    # the same words either way: a --pack run on a fresh compilation must produce the same page
    src = "tools/compile_spawns.py output (data/spawns.json %s, data/routes.json %s)" % (
        sha(ROOT / "data" / "spawns.json")[:12], sha(ROOT / "data" / "routes.json")[:12])
    page, stats = build_page(pools, src)
    out = Path(a.out)
    if a.check:
        same = out.is_file() and out.read_bytes() == page.encode("utf-8")
        print("%s: %s" % (out, "up to date" if same else "DIFFERS from a fresh build; rerun without --check"))
        return 0 if same else 1
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(page.encode("utf-8"))
    print("wrote %s (%s bytes; relief %s bytes): %d areas (%d land, %d sea, %d creek, %d route sections), %d species, "
          "%d rows; left out %d heart rows in %d areas, %d Mega den rows, %d habitat pools; dropped %s; %d data notes"
          % (out, format(out.stat().st_size, ","), format(stats["jpeg_bytes"], ","), stats["areas"], stats["land"],
             stats["sea"], stats["waterway"], stats["route"], stats["species"], stats["rows"],
             stats["excluded"]["hearts"], stats["excluded"]["heart_areas"], stats["excluded"]["mega_den_rows"],
             stats["excluded"]["habitat_pools"], stats["excluded"]["dropped"] or "none", len(stats["notes"])))
    for n in stats["notes"]:
        print("  note:", n[:160])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
