"""A density heatmap of every authored point of interest, over the land and sea shape of the map.

Route and river polylines are NOT in the density. They are geometry: 1,365 vertices that would swamp the
2,760 real points. They are drawn as faint lines instead, because most of what a point of interest means
is how far it sits from the road.
"""
import json, glob, os, sys, collections, pathlib
import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = str(pathlib.Path(__file__).resolve().parent.parent)
sys.path.insert(0, ROOT + "/tools")
OUT = sys.argv[1] if len(sys.argv) > 1 else ROOT + "/derived/maps/poi_heatmap.png"
pathlib.Path(OUT).parent.mkdir(parents=True, exist_ok=True)
W = 8192                      # world blocks a side
MAP = 1600                    # map pixels a side -> 5.12 blocks per pixel
PAD_L, PAD_T, PAD_R, PAD_B = 70, 118, 330, 70
SIGMA_BLOCKS = 110.0          # the radius over which one point counts as nearby

CATEGORY = {
    "towns.json": "settlements", "sea_town.json": "settlements", "traders.json": "settlements",
    "placements.json": "buildings", "structures.json": "buildings",
    "trainers.json": "trainers", "route_trainers.json": "trainers", "vr_trainers.json": "trainers",
    "arena_trainers.json": "trainers", "gym_trainers.json": "trainers", "late_route_trainers.json": "trainers",
    "shrines.json": "shrines", "legendaries.json": "legendaries",
    "adopted_legendary_sites.json": "legendaries",
    "landmarks.json": "landmarks", "signposts.json": "landmarks", "elder_trees.json": "landmarks",
    "themed_saplings.json": "landmarks", "foliage.json": "landmarks",
    "habitat_blocks.json": "encounters", "spawn_blocks.json": "encounters", "spawns.json": "encounters",
    "gulch_mine.json": "encounters", "vr_caves.json": "encounters", "rift_mines.json": "encounters",
    "quests.json": "story", "scenes.json": "story", "dialogue.json": "story", "rewards.json": "story",
    "progression.json": "story", "route_events.json": "story", "town_dressing.json": "buildings",
    "gym_interiors.json": "buildings",
    "portals.json": "portals", "ferry_docks.json": "routes", "waystones.json": "routes", "ferries.json": "routes",
    "rift_zones.json": "rift", "rift_skin.json": "rift", "deep_city.json": "rift",
    "relic_underground.json": "rift", "rift_regions.json": "rift",
}
GEOMETRY_ONLY = {"routes.json", "rivers.json"}


def points(obj, out):
    if isinstance(obj, dict):
        x = z = None
        if isinstance(obj.get("x"), (int, float)) and isinstance(obj.get("z"), (int, float)):
            x, z = obj["x"], obj["z"]
        if x is None:
            for k in ("centre", "center", "position", "anchor", "site", "seat", "at", "placement"):
                c = obj.get(k)
                if isinstance(c, dict) and isinstance(c.get("x"), (int, float)) and isinstance(c.get("z"), (int, float)):
                    x, z = c["x"], c["z"]
                    break
                if isinstance(c, list) and len(c) in (2, 3) and all(isinstance(v, (int, float)) for v in c):
                    x, z = c[0], c[-1]
                    break
        if x is not None and 0 <= x < W and 0 <= z < W:
            out.append((float(x), float(z)))
        for v in obj.values():
            points(v, out)
    elif isinstance(obj, list):
        for v in obj:
            points(v, out)


cats = collections.defaultdict(list)
for f in sorted(glob.glob(ROOT + "/data/*.json")) + sorted(glob.glob(ROOT + "/data/*/*.json")):
    base = os.path.basename(f)
    if base in GEOMETRY_ONLY:
        continue
    cat = CATEGORY.get(base, "other")
    try:
        d = json.load(open(f, encoding="utf-8"))
    except Exception:
        continue
    p = []
    points(d, p)
    cats[cat].extend(p)
for c in cats:
    cats[c] = list(dict.fromkeys(cats[c]))
allpts = [p for v in cats.values() for p in v]
print("categories:", {c: len(v) for c, v in sorted(cats.items(), key=lambda kv: -len(kv[1]))})
print("total POIs:", len(allpts))

small = np.zeros((MAP, MAP), np.float32)
shade = np.full((MAP, MAP), 0.5, np.float32)
land = np.zeros((MAP, MAP), bool)
try:
    import terrain as T
    h, world = T.load(ROOT + "/data/world.json", None)
    sea = T.sea_level(world)
    step = max(1, h.shape[0] // MAP)
    small = h[:MAP * step:step, :MAP * step:step].astype(np.float32)
    small = small[:MAP, :MAP]
    land = small > sea
    g = np.gradient(small)
    shade = np.clip(0.5 + (g[1] - g[0]) * 0.35, 0, 1)
    print("terrain backdrop %dx%d, sea %d, land %.1f%%" % (small.shape[1], small.shape[0], sea, 100 * land.mean()))
except Exception as e:
    print("no terrain backdrop (%s: %s)" % (type(e).__name__, e))

scale = MAP / float(W)
dens = np.zeros((MAP, MAP), np.float32)
for (x, z) in allpts:
    px, pz = int(x * scale), int(z * scale)
    if 0 <= px < MAP and 0 <= pz < MAP:
        dens[pz, px] += 1.0

sigma = SIGMA_BLOCKS * scale
rad = int(sigma * 3)
k = np.exp(-0.5 * (np.arange(-rad, rad + 1) / sigma) ** 2)
k /= k.sum()
for axis in (0, 1):
    dens = np.apply_along_axis(lambda m: np.convolve(m, k, mode="same"), axis, dens)
peak = float(dens.max())
print("density peak %.4f at pixel %s" % (peak, np.unravel_index(dens.argmax(), dens.shape)[::-1]))
norm = np.clip(dens / peak, 0, 1) ** 0.55

sea_rgb = np.array([14, 26, 48], np.float32)
land_rgb = np.array([46, 52, 46], np.float32)
base = np.where(land[..., None], land_rgb, sea_rgb) * (0.70 + 0.55 * shade[..., None])
img = np.clip(base, 0, 255)

stops = [(0.00, (14, 26, 48)), (0.12, (24, 70, 110)), (0.30, (26, 140, 140)),
         (0.50, (120, 190, 80)), (0.70, (240, 205, 60)), (0.86, (240, 130, 40)), (1.00, (235, 45, 45))]
ramp = np.zeros((256, 3), np.float32)
for i in range(256):
    t = i / 255.0
    for j in range(len(stops) - 1):
        a, b = stops[j], stops[j + 1]
        if a[0] <= t <= b[0]:
            f = (t - a[0]) / ((b[0] - a[0]) or 1)
            ramp[i] = np.array(a[1]) * (1 - f) + np.array(b[1]) * f
            break
heat = ramp[(norm * 255).astype(np.uint8)]
alpha = np.clip(norm * 1.7, 0, 0.92)[..., None]
img = img * (1 - alpha) + heat * alpha

canvas = Image.new("RGB", (PAD_L + MAP + PAD_R, PAD_T + MAP + PAD_B), (18, 18, 22))
canvas.paste(Image.fromarray(np.clip(img, 0, 255).astype(np.uint8)), (PAD_L, PAD_T))
d = ImageDraw.Draw(canvas)

drawn = {}
for fname, col in (("routes.json", (205, 205, 215)), ("rivers.json", (70, 120, 180))):
    try:
        doc = json.load(open(ROOT + "/data/" + fname, encoding="utf-8"))
    except Exception:
        continue
    lines = []

    def grab(o):
        if isinstance(o, dict):
            for kk, v in o.items():
                if kk in ("polyline", "graded_polyline", "course", "path", "points") \
                        and isinstance(v, list) and len(v) > 1:
                    pair = all(isinstance(q, (list, tuple)) and len(q) >= 2
                               and isinstance(q[0], (int, float)) and isinstance(q[1], (int, float)) for q in v)
                    dct = all(isinstance(q, dict) and "x" in q and "z" in q for q in v)
                    if pair or dct:
                        # a graded_polyline vertex is [x, z, water_y, bed_y]: x and z are the first two
                        lines.append([(q["x"], q["z"]) if isinstance(q, dict) else (q[0], q[1]) for q in v])
                        continue
                grab(v)
        elif isinstance(o, list):
            for v in o:
                grab(v)

    grab(doc)
    for ln in lines:
        pts = []
        for q in ln:
            try:
                pts.append((PAD_L + float(q[0]) * scale, PAD_T + float(q[1]) * scale))
            except (TypeError, ValueError):
                pass
        if len(pts) > 1:
            d.line(pts, fill=col, width=1)
    drawn[fname] = len(lines)
print("polylines drawn:", drawn)

try:
    F = ImageFont.truetype("arial.ttf", 17)
    FB = ImageFont.truetype("arialbd.ttf", 27)
    FS = ImageFont.truetype("arial.ttf", 14)
except Exception:
    F = FB = FS = ImageFont.load_default()

for i in range(9):
    p = PAD_L + i * MAP / 8.0
    d.line([(p, PAD_T), (p, PAD_T + MAP)], fill=(90, 90, 100), width=1)
    q = PAD_T + i * MAP / 8.0
    d.line([(PAD_L, q), (PAD_L + MAP, q)], fill=(90, 90, 100), width=1)
for i in range(8):
    d.text((PAD_L + (i + 0.5) * MAP / 8.0 - 5, PAD_T - 24), "12345678"[i], font=FS, fill=(150, 150, 160))
    d.text((PAD_L - 22, PAD_T + (i + 0.5) * MAP / 8.0 - 8), "ABCDEFGH"[i], font=FS, fill=(150, 150, 160))

# the named settlements, so a hot spot can be identified rather than only admired
try:
    towns = json.load(open(ROOT + "/data/towns.json", encoding="utf-8"))["towns"]
except Exception:
    towns = []
placed_labels = 0
for t in towns:
    c = t.get("centre") or {}
    if not isinstance(c.get("x"), (int, float)):
        continue
    name = t.get("display_name") or t.get("working_name") or t.get("id")
    px, pz = PAD_L + c["x"] * scale, PAD_T + c["z"] * scale
    d.ellipse([px - 2.5, pz - 2.5, px + 2.5, pz + 2.5], fill=(255, 255, 255), outline=(20, 20, 24))
    d.text((px + 6, pz - 7), str(name), font=FS, fill=(248, 248, 252),
           stroke_width=2, stroke_fill=(16, 16, 20))
    placed_labels += 1
print("settlements labelled:", placed_labels)

d.text((PAD_L, 24), "Cobblers - where the authored content is", font=FB, fill=(238, 238, 242))
d.text((PAD_L, 62), "%d points of interest in %d categories   |   8,192 blocks a side at %.2f blocks per pixel   |   cells are 1,024 blocks"
       % (len(allpts), len(cats), W / float(MAP)), font=FS, fill=(150, 150, 160))

lx = PAD_L + MAP + 26
ly = PAD_T + 6
d.text((lx, ly), "POINTS COUNTED", font=F, fill=(238, 238, 242))
ly += 30
for c, v in sorted(cats.items(), key=lambda kv: -len(kv[1])):
    d.text((lx, ly), "%-12s %4d" % (c, len(v)), font=FS, fill=(205, 205, 215))
    ly += 23
ly += 18
d.text((lx, ly), "DENSITY", font=F, fill=(238, 238, 242))
ly += 28
bar_h = 190
for i in range(bar_h):
    t = 1.0 - i / float(bar_h - 1)
    d.line([(lx, ly + i), (lx + 26, ly + i)], fill=tuple(int(v) for v in ramp[int(t * 255)]))
d.text((lx + 34, ly - 4), "most", font=FS, fill=(205, 205, 215))
d.text((lx + 34, ly + bar_h - 14), "none", font=FS, fill=(205, 205, 215))
ly += bar_h + 24
for s in ("Gaussian, sigma = %d blocks." % int(SIGMA_BLOCKS),
          "Relative, not absolute: the scale",
          "is normalised to the busiest",
          "place on the map.",
          "",
          "White lines are routes, blue are",
          "rivers. Neither is in the density:",
          "1,365 polyline vertices would",
          "swamp the real points.",
          "",
          "Grey is land, dark blue is sea,",
          "shaded by slope."):
    d.text((lx, ly), s, font=FS, fill=(140, 140, 150))
    ly += 19

# the busiest places, named, so the picture can be checked against something
flat = []
for (name, c) in [((t.get("display_name") or t.get("working_name") or t.get("id")),
                   (t.get("centre") or {})) for t in towns]:
    if isinstance(c.get("x"), (int, float)):
        px, pz = int(c["x"] * scale), int(c["z"] * scale)
        if 0 <= px < MAP and 0 <= pz < MAP:
            flat.append((float(dens[pz, px]), name, int(c["x"]), int(c["z"])))
flat.sort(reverse=True)
print("")
print("busiest named places (density at the centre, relative to peak %.4f):" % peak)
for v, name, x, z in flat[:10]:
    print("   %-22s (%5d, %5d)  %.0f%% of peak" % (name, x, z, 100 * v / peak))
print("")
print("quietest named places:")
for v, name, x, z in flat[-6:]:
    print("   %-22s (%5d, %5d)  %.0f%% of peak" % (name, x, z, 100 * v / peak))
empty = float((dens[land] < peak * 0.02).mean()) if land.any() else 0.0
print("")
print("land columns under 2%% of peak density: %.1f%%" % (100 * empty))

canvas.save(OUT)
print("wrote %s (%d x %d)" % (OUT, canvas.width, canvas.height))
