#!/usr/bin/env python
"""The Mega field's contested borders, from data/mega_borders.json: scarred ground, broken rock and kills wherever two
dens' ranges overlap (the owner, 2026-10-04).

THE OWNER, 2026-10-04: "I want the southern Rift to feel like Megas are clashing over territory ... make the crowding
legible: overlapping ranges, scarred ground, broken rock where two territories meet, kills; a player should understand
what is happening there without being told."

The dens (data/gulch_mine.json farms[], laid out by tools/mega_field.py sites) stand 43 or more apart with ranges (leash
discs) of 36, so neighbours' ranges overlap: each overlap is a lens between two homes. Per lens, one function writes:

  the scar      along the lens's long axis (square to the line between the homes, through its middle), a band that
                thins to nothing at the lens's ends, ragged, with gaps: each column rewritten AT its ground surface with
                the scrape palette of the den whose side it lies on, or the shared scar palette (cracked deepslate,
                gravel, scorched blackstone)
  the rubble    at the lens's middle: toppled boulders of both kits' stone, some split through, and loose rubble
  the kill      where the ranges overlap deepest (kill.min_overlap): a carcass of bone along the border, a skull,
                loose bones and broken gear beside it

Never within keep.anchor_clear of an anchor nor keep.lair_clear of a column a lair writes (tools/mega_dens.py's plan),
never off tools/mega_field.py floor()'s dressing floor. Dark by design. Ground from tools/ground.py, never a world.
Every block is refused unless it is in blocks.ids and is not a spawn condition (data/spawn_blocks.json).

  python tools/mega_borders.py build [--source-root R] [--out DIR]   write the pack
  python tools/mega_borders.py plan  [--source-root R]               print the borders and coverage; writes nothing
  python tools/mega_borders.py probes [--source-root R]              print RCON block checks for the world

The re-application: placement_steps() is step R9MB (tools/reapply.py), after R9MD.
"""
from __future__ import annotations

import argparse
import json
import math
import random
import shutil
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import function_limits  # noqa: E402

DATA = ROOT / "data" / "mega_borders.json"
GULCH = ROOT / "data" / "gulch_mine.json"
DENS = ROOT / "data" / "mega_dens.json"
DEFAULT_OUT = ROOT / "build" / "datapacks" / "cobblers_mega_borders"
SCHEMA = "cobblers.mega-borders/1"
NS = "cobblers"
FN = "mega_borders"
PACK_FORMAT = 48  # Minecraft 1.21.1
# The ground rule (tools/ground_rule.py): nothing here reads a world; every Y comes from tools/ground.py.
WORLD_READS: set = set()


class BorderError(SystemExit):
    pass


def _base(state):
    return state.split("[")[0].split("{")[0]


def _pick(rng, weights):
    keys = sorted(weights)
    total = sum(weights[k] for k in keys)
    v = rng.random() * total
    for k in keys:
        v -= weights[k]
        if v < 0:
            return k
    return keys[-1]


def load(path=DATA):
    doc = json.loads(Path(path).read_text(encoding="utf-8"))
    if doc.get("schema") != SCHEMA:
        raise BorderError("%s: schema must be %s" % (path, SCHEMA))
    if doc.get("lighting") != "dark":
        raise BorderError("the borders are dark by design: lighting must be 'dark'")
    spawn = set(json.loads((ROOT / "data" / "spawn_blocks.json").read_text(encoding="utf-8"))["blocks"])
    bad = sorted(set(doc["blocks"]["ids"]) & spawn)
    if bad:
        raise BorderError("data/mega_borders.json blocks.ids holds spawn condition(s) %s (data/spawn_blocks.json)" % bad)
    return doc


def field_dens(gm):
    return [d for fa in gm["farms"] if fa["id"].startswith("field_") for d in fa["dens"]]


def kits(gm, md):
    """{species: the hand-authored lair kit record it is dressed with} (mega_field.dressing.kit_of)."""
    by = {r["species"]: r for r in md["superseded_dens"]}
    return {sp: by[k] for sp, k in gm["mega_field"]["dressing"]["kit_of"].items()}


def borders(gm):
    """[(a, b, distance, overlap)] for every two field dens whose leash discs overlap, nearest pairs first."""
    ds = field_dens(gm)
    out = []
    for i, a in enumerate(ds):
        for b in ds[i + 1:]:
            s = math.hypot(a["anchor"][0] - b["anchor"][0], a["anchor"][2] - b["anchor"][2])
            if s < a["leash"] + b["leash"]:
                out.append((a, b, s, a["leash"] + b["leash"] - s))
    return sorted(out, key=lambda t: (t[2], t[0]["id"], t[1]["id"]))


class Context:
    """What every border shares: the ground, the dressing floor, the lairs' columns, the anchors."""

    def __init__(self, doc, gm, md, g, source_root=None):
        import mega_field as MF
        import mega_dens as MD
        self.doc, self.gm, self.g = doc, gm, g
        (self.x0, self.z0, self.x1, self.z1), M, self.H = MF.floor(gm, source_root)
        self.dress = M["field"] & M["dry"] & (M["crit"] >= 128) & ~M["in_grid"] & (M["gulch"] > 32) & (M["other"] >= 0)
        self.walk = M["field"] & M["dry"] & M["walk"]
        mdoc, mdens = MD.load()
        lair = set()
        for d in MD.plan(mdoc, mdens, g):
            lair |= {(x, z) for (x, _y, z) in d.w}
        r = doc["keep"]["lair_clear"]
        self.lair = {(x + i, z + j) for x, z in lair for i in range(-r, r + 1) for j in range(-r, r + 1)}
        self.anchors = [(d["anchor"][0], d["anchor"][2]) for d in field_dens(gm)]
        self.kit = kits(gm, md)
        self.taken = set()

    def ground(self, x, z):
        return int(self.H[z - self.z0, x - self.x0]) if self.x0 <= x <= self.x1 and self.z0 <= z <= self.z1 \
            else int(round(self.g(x, z)))

    def writable(self, x, z):
        if not (self.x0 <= x <= self.x1 and self.z0 <= z <= self.z1):
            return False
        if not self.dress[z - self.z0, x - self.x0] or (x, z) in self.lair:
            return False
        ac = self.doc["keep"]["anchor_clear"]
        return all((x - ax) ** 2 + (z - az) ** 2 > ac * ac for ax, az in self.anchors)

    def flat(self, x, z):
        if not (self.x0 + 1 <= x <= self.x1 - 1 and self.z0 + 1 <= z <= self.z1 - 1):
            return False
        y = self.ground(x, z)
        f = self.doc["keep"]["flat"]
        return all(abs(self.ground(x + i, z + j) - y) <= f for i, j in ((1, 0), (-1, 0), (0, 1), (0, -1)))


class Border:
    """One lens's writes, {(x, y, z): state}, between den a and den b."""

    def __init__(self, ctx, a, b, s, overlap, index):
        self.ctx, self.doc = ctx, ctx.doc
        self.a, self.b, self.s, self.overlap = a, b, s, overlap
        self.name = "%s__%s" % (a["species"], b["species"])
        ax, _ay, az = a["anchor"]
        bx, _by, bz = b["anchor"]
        self.mx, self.mz = (ax + bx) / 2.0, (az + bz) / 2.0
        self.ux, self.uz = (bx - ax) / s, (bz - az) / s            # from a's home toward b's
        self.vx, self.vz = -self.uz, self.ux                       # along the border
        # half the lens's length: where the two circles cross (unequal leashes: from a's side)
        la, lb = a["leash"], b["leash"]
        da = (s * s + la * la - lb * lb) / (2 * s)
        self.cx, self.cz = ax + self.ux * da, az + self.uz * da   # the lens's centre line crosses the homes' line here
        self.h = math.sqrt(max(0.0, la * la - da * da))
        self.allowed = set(self.doc["blocks"]["ids"])
        self.rng = random.Random(self.doc["seed"] * 1009 + index)
        self.w, self.top, self.used = {}, {}, set()

    # --- primitives
    def free(self, x, z):
        """On the dressing floor, off every lair and anchor, and not a column an earlier border wrote (where three
        ranges meet, two lenses cross: the nearer pair's border, built first, keeps the ground)."""
        return (x, z) not in self.ctx.taken and self.ctx.writable(x, z)

    def put(self, x, y, z, state):
        if _base(state) not in self.allowed:
            raise BorderError("%s: %s is not in data/mega_borders.json blocks.ids" % (self.name, _base(state)))
        g = self.ctx.ground(x, z)
        if y > g + self.doc["max_rise"] or y < g:
            raise BorderError("%s: (%d, %d, %d) is outside ground y%d .. +%d" % (self.name, x, y, z, g, self.doc["max_rise"]))
        if not self.free(x, z):
            raise BorderError("%s: (%d, %d) is not on the dressing floor, or is a lair's or an anchor's" % (self.name, x, z))
        self.w[(x, y, z)] = state

    def gtop(self, x, z):
        return self.top.get((x, z), self.ctx.ground(x, z))

    def stack(self, x, z, state):
        y = self.gtop(x, z) + 1
        self.put(x, y, z, state)
        self.top[(x, z)] = y

    def can_stand(self, x, z):
        return (x, z) not in self.used and self.free(x, z) and self.ctx.flat(x, z) \
            and self.gtop(x, z) == self.ctx.ground(x, z)

    def side(self, x, z):
        """Signed distance across the border: negative on a's side."""
        return (x + 0.5 - self.cx) * self.ux + (z + 0.5 - self.cz) * self.uz

    def along(self, x, z):
        return (x + 0.5 - self.cx) * self.vx + (z + 0.5 - self.cz) * self.vz

    def at(self, t, w=0.0):
        return (int(math.floor(self.cx + t * self.vx + w * self.ux)), int(math.floor(self.cz + t * self.vz + w * self.uz)))

    # --- the parts
    def scar(self):
        B = self.doc["border"]
        hw0, rag = B["half_width"], B["ragged"]
        p1, p2 = self.rng.uniform(0, 6.28), self.rng.uniform(0, 6.28)
        n = int(math.ceil(max(self.h, hw0 + rag))) + 2
        ka, kb = self.ctx.kit[self.a["species"]]["scrape"], self.ctx.kit[self.b["species"]]["scrape"]
        icx, icz = int(round(self.cx)), int(round(self.cz))
        for x in range(icx - n, icx + n + 1):
            for z in range(icz - n, icz + n + 1):
                t, w = self.along(x, z), self.side(x, z)
                if abs(t) > self.h:
                    continue
                k = t / self.h if self.h else 1.0
                hw = hw0 * math.sqrt(max(0.0, 1 - k * k)) + rag * (0.5 * math.sin(0.35 * t + p1) + 0.5 * math.sin(0.9 * t + p2))
                if abs(w) > hw or self.rng.random() > B["cover"] or not self.free(x, z):
                    continue
                if self.rng.random() < B["own_side"]:
                    st = _pick(self.rng, ka if w < 0 else kb)
                else:
                    st = _pick(self.rng, self.doc["scar"])
                self.put(x, self.ctx.ground(x, z), z, st)    # the scar is the ground itself: things may lie on it
        self.scarred = {(x, z) for (x, _y, z) in self.w}

    def rubble(self):
        R = self.doc["rubble"]
        stones = sorted(set(self.ctx.kit[self.a["species"]]["boulder"]) | set(self.ctx.kit[self.b["species"]]["boulder"]))
        placed = []
        for i in range(self.rng.randint(*R["boulders"])):
            for _try in range(16):
                t = self.rng.uniform(-self.h / 3.0, self.h / 3.0)
                cx, cz = self.at(t, self.rng.uniform(-2.0, 2.0))
                br = self.rng.uniform(*R["boulder_radius"])
                cells = [(x, z) for x in range(cx - 2, cx + 3) for z in range(cz - 2, cz + 3)
                         if math.hypot(x - cx, z - cz) <= br]
                if cells and all(self.free(x, z) and self.ctx.flat(x, z) and self.gtop(x, z) == self.ctx.ground(x, z)
                                 for x, z in cells) and all(math.hypot(cx - px, cz - pz) > 4 for px, pz in placed):
                    break
            else:
                continue
            placed.append((cx, cz))
            split = (i % R["split_every"]) == 0
            ang = self.rng.uniform(0, math.pi)
            hb = self.rng.randint(*R["boulder_height"])
            for x, z in cells:
                if split and abs((x - cx) * math.cos(ang) + (z - cz) * math.sin(ang)) < 0.5:
                    continue                                   # split through: the crack between its halves
                hh = max(1, int(round(hb * (1 - (math.hypot(x - cx, z - cz) / (br + 0.8)) ** 2))))
                for _ in range(hh):
                    self.stack(x, z, self.rng.choice(stones))
                self.used.add((x, z))
        self.boulders = placed
        for _ in range(self.rng.randint(*R["loose"])):
            for _try in range(12):
                t = self.rng.uniform(-R["spread"], R["spread"])
                x, z = self.at(t, self.rng.uniform(-R["spread"] / 2.0, R["spread"] / 2.0))
                if self.can_stand(x, z):
                    self.stack(x, z, self.rng.choice(R["loose_blocks"]))
                    self.used.add((x, z))
                    break

    def kill(self):
        K = self.doc["kill"]
        self.carcass = None
        if self.overlap < K["min_overlap"]:
            return
        # a third of the way along, on the side of the border away from the rubble's mean
        mean = sum(self.along(x, z) for x, z in self.boulders) / len(self.boulders) if self.boulders else 0.0
        sgn = -1 if mean > 0 else 1
        axis = "x" if abs(self.vx) >= abs(self.vz) else "z"
        step = (1, 0) if axis == "x" else (0, 1)
        sidev = (0, 1) if axis == "x" else (1, 0)
        n = K["spine"]
        for frac in (1 / 3.0, 0.42, 0.25, 0.5, 0.18):
            px, pz = self.at(sgn * frac * self.h, self.rng.uniform(-1.0, 1.0))
            spine = [(px + i * step[0], pz + i * step[1]) for i in range(-(n // 2), n - n // 2)]
            ribs = [(px + i * step[0] + s * sidev[0], pz + i * step[1] + s * sidev[1])
                    for i in range(-(K["ribs"] // 2), K["ribs"] - K["ribs"] // 2) for s in (-1, 1)]
            head = (spine[-1][0] + step[0], spine[-1][1] + step[1])
            if all(self.can_stand(x, z) for x, z in spine + ribs + [head]):
                break
        else:
            return
        for x, z in spine:
            self.stack(x, z, "minecraft:bone_block[axis=%s]" % axis)
            self.used.add((x, z))
        for x, z in ribs:
            self.stack(x, z, "minecraft:bone_block[axis=y]")
            self.used.add((x, z))
        self.stack(head[0], head[1], "minecraft:skeleton_skull[rotation=%d]" % self.rng.randint(0, 15))
        self.used.add(head)
        self.carcass = (px, pz)
        for _ in range(self.rng.randint(*K["bones"])):
            for _try in range(12):
                x, z = px + self.rng.randint(-4, 4), pz + self.rng.randint(-4, 4)
                if self.can_stand(x, z):
                    self.stack(x, z, "minecraft:bone_block[axis=%s]" % self.rng.choice("xz"))
                    self.used.add((x, z))
                    break
        for _ in range(self.rng.randint(*K["gear_count"])):
            for _try in range(12):
                x, z = px + self.rng.randint(-3, 3), pz + self.rng.randint(-3, 3)
                if self.can_stand(x, z):
                    gear = self.rng.choice(K["gear"])
                    self.stack(x, z, gear + ("[axis=%s]" % self.rng.choice("xz") if gear.endswith("chain") else ""))
                    self.used.add((x, z))
                    break

    def build(self):
        self.scar()
        self.rubble()
        self.kill()
        return self

    def columns(self):
        return {(x, z) for (x, _y, z) in self.w}

    def box(self):
        xs = [k[0] for k in self.w]
        zs = [k[2] for k in self.w]
        return min(xs), min(zs), max(xs), max(zs)


def plan(doc=None, gm=None, md=None, g=None, source_root=None):
    import ground as G
    doc = doc or load()
    gm = gm or json.loads(GULCH.read_text(encoding="utf-8"))
    md = md or json.loads(DENS.read_text(encoding="utf-8"))
    g = g or G.load(source_root)
    ctx = Context(doc, gm, md, g, source_root)
    out = []
    for i, (a, b, s, ov) in enumerate(borders(gm)):
        out.append(Border(ctx, a, b, s, ov, i).build())
        ctx.taken |= out[-1].columns()
    seen = {}
    for bd in out:
        for c in bd.columns():
            if c in seen:
                raise BorderError("%s and %s both write column %s" % (seen[c], bd.name, c))
            seen[c] = bd.name
    cov = coverage(ctx, gm, seen)
    if cov["fraction"] > doc["coverage_cap"]:
        raise BorderError("the borders rewrite %.1f%% of the ranges' floor, over coverage_cap %.1f%%"
                          % (100 * cov["fraction"], 100 * doc["coverage_cap"]))
    return out, cov


def coverage(ctx, gm, cols):
    gx, gz = np.meshgrid(np.arange(ctx.x0, ctx.x1 + 1), np.arange(ctx.z0, ctx.z1 + 1))
    inr = np.zeros(ctx.walk.shape, dtype=bool)
    for d in field_dens(gm):
        inr |= np.hypot(gx - d["anchor"][0], gz - d["anchor"][2]) <= d["leash"]
    floor = int((ctx.walk & inr).sum())
    return {"range floor": floor, "written columns": len(cols), "fraction": len(cols) / float(floor or 1)}


# ---------------------------------------------------------------------------------------------------------- the pack
def _runs(blocks):
    """setblock and fill lines, one fill per run of one state along x, bottom up (a block is written after what it
    rests on)."""
    out = []
    keys = sorted(blocks, key=lambda k: (k[1], k[2], k[0]))
    i = 0
    while i < len(keys):
        x, y, z = keys[i]
        st = blocks[keys[i]]
        j = i
        while j + 1 < len(keys) and keys[j + 1] == (keys[j][0] + 1, y, z) and blocks[keys[j + 1]] == st:
            j += 1
        out.append("setblock %d %d %d %s" % (x, y, z, st) if j == i else
                   "fill %d %d %d %d %d %d %s" % (x, y, z, keys[j][0], y, z, st))
        i = j + 1
    return out


def build_lines(bd):
    out = ["# Generated by tools/mega_borders.py from data/mega_borders.json. Re-run to rebuild; do not edit.",
           "# The border between the %s den (%s) and the %s den (%s): homes %.0f apart, ranges overlapping %.0f blocks."
           % (bd.a["species"], bd.a["id"], bd.b["species"], bd.b["id"], bd.s, bd.overlap),
           "# Scarred ground along it, broken rock at its middle%s. Dark by design: no light source."
           % (", a kill a third of the way along" if bd.carcass else "")]
    return out + _runs(bd.w)


def files(bds):
    out = {"pack.mcmeta": json.dumps({"pack": {"pack_format": PACK_FORMAT, "description":
                                               "Cobblers: the Mega field's contested borders (tools/mega_borders.py)"}},
                                     indent=2) + "\n"}
    for bd in bds:
        lines = function_limits.ensure_loaded(build_lines(bd))
        bad = function_limits.check_lines(lines, bd.name)
        if bad:
            raise BorderError("%s: %d command(s) the server would refuse: %s" % (bd.name, len(bad), bad[:3]))
        out["data/%s/function/%s/%s.mcfunction" % (NS, FN, bd.name)] = "\n".join(lines) + "\n"
    return out


def placement_steps(bds=None):
    """For tools/reapply.py, step R9MB (after R9MD, before R9E): per border, hold its box, build, release."""
    if bds is None:
        bds, _cov = plan()
    steps = []
    for bd in bds:
        x0, z0, x1, z1 = bd.box()
        hold = "%d %d %d %d" % (x0, z0, x1, z1)
        steps += [("cmd", "forceload add " + hold), ("wait", 3), ("fn", "%s:%s/%s" % (NS, FN, bd.name)),
                  ("cmd", "forceload remove " + hold)]
    return steps


def write(out_files, out):
    out = Path(out)
    if out.exists():
        shutil.rmtree(out)
    for rel, text in out_files.items():
        f = out / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(text, encoding="utf-8", newline="\n")


def report(bds, cov):
    lines = []
    for bd in bds:
        kinds = {}
        for st in bd.w.values():
            kinds[_base(st)] = kinds.get(_base(st), 0) + 1
        lines.append("%-22s homes %3.0f apart, overlap %4.1f, lens %3.0f long: %4d blocks, %3d columns scarred, %d boulders"
                     "%s" % (bd.name, bd.s, bd.overlap, 2 * bd.h, len(bd.w), len(bd.scarred), len(bd.boulders),
                             ", a kill at (%d, %d)" % bd.carcass if bd.carcass else ""))
    lines.append("borders %d, kills %d, written columns %d of the ranges' %d walkable floor (%.1f%%, cap %.1f%%)"
                 % (len(bds), sum(1 for b in bds if b.carcass), cov["written columns"], cov["range floor"],
                    100 * cov["fraction"], 100 * load()["coverage_cap"]))
    return lines


def probes(bds):
    out = []
    for bd in bds:
        out.append("### %s" % bd.name)
        sc = sorted(bd.scarred)
        if sc:
            x, z = sc[len(sc) // 2]
            k = (x, bd.ctx.ground(x, z), z)
            out.append("- `execute if block %d %d %d %s` -> `Test passed` (the scar)" % (k[0], k[1], k[2], _base(bd.w[k])))
        sk = sorted(k for k, s in bd.w.items() if _base(s) == "minecraft:skeleton_skull")
        if sk:
            out.append("- `execute if block %d %d %d minecraft:skeleton_skull` -> `Test passed` (the kill's skull)" % sk[0])
        out.append("")
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("cmd", choices=("build", "plan", "probes"))
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    ap.add_argument("--source-root")
    ap.add_argument("--server-dir", help="accepted for tools/reapply.py prepare's sake; not read")
    a = ap.parse_args(argv)
    bds, cov = plan(source_root=a.source_root)
    if a.cmd == "plan":
        print("\n".join(report(bds, cov)))
        print("steps (R9MB): %d" % len(placement_steps(bds)))
        return 0
    if a.cmd == "probes":
        print("\n".join(probes(bds)))
        return 0
    out_files = files(bds)
    write(out_files, a.out)
    n = sum(1 for rel, t in out_files.items() if rel.endswith(".mcfunction") for l in t.splitlines()
            if l and not l.startswith("#"))
    print("mega_borders: %d files -> %s (%d commands)" % (len(out_files), a.out, n))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
