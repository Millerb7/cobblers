#!/usr/bin/env python
"""Ore that goes into the rock: veins grown from the exposed ore, and hidden clusters behind the walls (the owner, 2026-10-23:
"is there a way to make the blocks around the edges like ore more than 1 deep, feels lack luster and sloppy, ores are only on
the band" / "i think with the some ore should be hidden").

One helper for tools/cave_systems.py and tools/mine_networks.py, so both read the same rules. It is a pure function of its
inputs: no world, no heightmap, no files. The caller says what is open air, what rock may become ore, which ores exist and how
to pick one; this module only decides WHICH ROCK CELLS, deterministically (every choice is a hash of the seed and a position).

  veins    every exposed ore cell (a base ore with an open cell beside it) seeds a vein with chance `seed_rate`: 3 to 10 blocks
           of the SAME ore in all (the seed counted), a seeded random walk that goes 1 to 4 blocks INTO the rock (inward = away
           from the open cells beside the seed), with a few cells sideways. `break_rate` of the veins break the surface in 2 or 3
           cells in all (the seed and one or two more); every other cell of every vein is rock with no open cell beside it.
  hidden   a rock cell beside the open air seeds a cluster with chance `hidden_rate` x the caller's richness for that wall (richer
           deeper and farther from a town, so the ore mix and its trend by depth are the base ore's own): 2 to 6 blocks of one
           ore, centred 2 to 6 blocks inward of the wall, every cell with NO open cell beside it. Nothing about it shows from a
           passage until a player digs.

THE SAFETY RULES, each enforced twice: here, by `rock_ok`/`air`, and in the generated commands, by the filter every write carries
(`... replace #minecraft:base_stone_overworld`: stone, deepslate, tuff, andesite, diorite, granite; never air, water, lava, a
structure block, a fitting or another ore). Both generators write the layer in its OWN function per tile (not the carve, not
the shell), so a re-run repeats it safely: a cell that is already ore no longer matches the filter. The tools' audits re-check the
filter, the cover, the reach and the water from the BUILT functions (tools/cave_systems_audit.py, tools/mine_networks_audit.py).

What this does NOT know (CLAUDE.md "Our list is not the world"): a natural cave, a mod structure or a spawner in the rock that
is in no data file. The filter keeps it whole; a hidden cell beside one is not hidden from it.
"""
from __future__ import annotations

DIRS6 = ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1))
ORE_FILTER = "#minecraft:base_stone_overworld"     # what an ore write may replace: the rock, nothing else
REACH2 = 49                                          # every layer cell is within sqrt(49) = 7 of the wall cell it grows from


def h32(*vals):
    """The house mix (tools/cave_systems.py hash01, tools/mines.py h32) over integers: 32 bits per call."""
    a = 0x811C9DC5
    for v in vals:
        a = ((a ^ (int(v) & 0xFFFFFFFF)) * 0x01000193) & 0xFFFFFFFF
        a ^= a >> 15
        a = (a * 0x2C1B3C6D) & 0xFFFFFFFF
        a ^= a >> 12
    return a


def unit(*vals):
    return h32(*vals) / 4294967296.0


def add(c, d, k=1):
    return (c[0] + d[0] * k, c[1] + d[1] * k, c[2] + d[2] * k)


def inward_of(air, c):
    """(axis, sign) pointing from the open cells beside `c` into the rock, or None when no neighbour is open."""
    v = [0, 0, 0]
    for d in DIRS6:
        if air(add(c, d)):
            v[0] -= d[0]
            v[1] -= d[1]
            v[2] -= d[2]
    m = max(abs(q) for q in v)
    if m == 0:
        return None
    tied = [i for i in range(3) if abs(v[i]) == m]
    i = tied[h32(c[0], c[1], c[2], 7) % len(tied)]
    return i, (1 if v[i] > 0 else -1)


def unit_vec(axis, sign):
    d = [0, 0, 0]
    d[axis] = sign
    return tuple(d)


def exposed(air, c):
    return any(air(add(c, d)) for d in DIRS6)


class Layer:
    """cfg: the `layer` block of the data. seed: an int. air(c): the cell is open (carved). rock_ok(c): the cell is rock that may
    become ore (not open, not a fitting or an existing ore or a reserved cell, under enough cover, inside the system's envelope).
    ore_ok(t, c): the type may stand at c. block_for(t, c): the block name. type_of(block): the type record of a base ore block."""

    def __init__(self, cfg, seed, air, rock_ok, ore_ok, block_for, type_of):
        self.cfg, self.seed = cfg, int(seed)
        self.air, self.rock_ok, self.ore_ok, self.block_for, self.type_of = air, rock_ok, ore_ok, block_for, type_of
        self.taken = {}                 # cell -> (block, type id, "vein" | "hidden")

    # -- veins from the exposed ore ------------------------------------------------------------------------------------
    def vein(self, e, t):
        cfg, s = self.cfg, self.seed
        ax = inward_of(self.air, e)
        if ax is None:
            i = h32(s, 20, *e) % 4
            ax = (0, 1) if i == 0 else (0, -1) if i == 1 else (2, 1) if i == 2 else (2, -1)
        inw = unit_vec(*ax)
        lat = [unit_vec(i, sg) for i in range(3) if i != ax[0] for sg in (1, -1)]
        lo, hi = cfg["size"]
        size = lo + h32(s, 21, *e) % (hi - lo + 1)                       # blocks of ore in all, the seed counted
        dlo, dhi = cfg["depth"]
        depth_max = dlo + h32(s, 22, *e) % (dhi - dlo + 1)
        breaker = unit(s, 23, *e) < cfg["break_rate"]
        blo, bhi = cfg["break_cells"]
        extra = (blo + h32(s, 24, *e) % (bhi - blo + 1)) - 1 if breaker else 0   # more exposed cells than the seed
        cells = []
        frontier = [e]
        seen = {e}
        used = 0
        for j in range(size * 10):
            if len(cells) >= size - 1:
                break
            k = len(frontier) - 1 if unit(s, 25, *e, j) < 0.6 else h32(s, 26, *e, j) % len(frontier)
            b = frontier[k]
            r = h32(s, 27, *e, j)
            step = inw if (r % 2 == 0 or j == 0) else lat[(r >> 1) % len(lat)]
            n = add(b, step)
            if n in seen:
                continue
            seen.add(n)
            rel = (n[0] - e[0], n[1] - e[1], n[2] - e[2])
            if rel[ax[0]] * ax[1] > depth_max or rel[0] ** 2 + rel[1] ** 2 + rel[2] ** 2 > REACH2:
                continue
            if n in self.taken or not self.rock_ok(n) or not self.ore_ok(t, n):
                continue
            if exposed(self.air, n):
                if used >= extra:
                    continue
                used += 1
            cells.append(n)
            frontier.append(n)
        if len(cells) < 2:
            return []                                                       # not a vein: under 3 blocks with the seed
        return cells

    def grow_veins(self, seeds):
        """seeds: [(cell, block)] the exposed base ore. Returns the number of veins grown."""
        cfg, s = self.cfg, self.seed
        n_v = 0
        for e, blk in sorted(seeds, key=lambda q: (h32(self.seed, 30, *q[0]), q[0])):
            if unit(s, 31, *e) >= cfg["seed_rate"]:
                continue
            t = self.type_of(blk)
            if t is None:
                continue
            if unit(s, 32, *e) >= t.get("layer_scale", 1.0):       # the rare ores (gold, diamond) get fewer veins: the bank pays for them
                continue
            cells = self.vein(e, t)
            if not cells:
                continue
            n_v += 1
            for c in cells:
                self.taken[c] = (self.block_for(t, c), t["id"], "vein")
        return n_v

    # -- hidden clusters behind the walls ------------------------------------------------------------------------------
    def grow_hidden(self, walls, pick):
        """walls: [(cell, richness)] rock cells with open air beside them (already thinned by the caller or not).
        pick(cluster centre, richness, wall cell) -> a type record or None. Returns the number of clusters."""
        cfg, s = self.cfg, self.seed
        dlo, dhi = cfg["hidden_depth"]
        slo, shi = cfg["hidden_size"]
        n_c = 0
        for w, rich in walls:
            if unit(s, 40, *w) >= cfg["hidden_rate"] * rich:
                continue
            ax = inward_of(self.air, w)
            if ax is None:
                continue
            d = dlo + h32(s, 41, *w) % (dhi - dlo + 1)
            c0 = add(w, unit_vec(*ax), d)
            oth = [i for i in range(3) if i != ax[0]]
            c0 = list(c0)
            c0[oth[0]] += h32(s, 42, *w) % 3 - 1
            c0[oth[1]] += h32(s, 43, *w) % 3 - 1
            c0 = tuple(c0)
            if not self.hidden_ok(c0, w, None):
                continue
            t = pick(c0, rich, w)
            if t is None or not self.ore_ok(t, c0) or unit(s, 47, *w) >= t.get("layer_scale", 1.0):
                continue
            size = slo + h32(s, 44, *w) % (shi - slo + 1)
            cells = [c0]
            seen = {c0}
            for j in range(size * 8):
                if len(cells) >= size:
                    break
                b = cells[h32(s, 45, *w, j) % len(cells)]
                n = add(b, DIRS6[h32(s, 46, *w, j) % 6])
                if n in seen:
                    continue
                seen.add(n)
                if self.hidden_ok(n, w, t):
                    cells.append(n)
            if len(cells) < slo:
                continue
            n_c += 1
            for c in cells:
                self.taken[c] = (self.block_for(t, c), t["id"], "hidden")
        return n_c

    def hidden_ok(self, c, w, t):
        rel = (c[0] - w[0], c[1] - w[1], c[2] - w[2])
        if rel[0] ** 2 + rel[1] ** 2 + rel[2] ** 2 > REACH2:
            return False
        if c in self.taken or not self.rock_ok(c) or exposed(self.air, c):
            return False
        return t is None or self.ore_ok(t, c)

    def result(self):
        """[(x, y, z, block, type id, kind)] sorted by position."""
        return sorted((c[0], c[1], c[2], v[0], v[1], v[2]) for c, v in self.taken.items())


def summarise(base, layer):
    """{type id: {"exposed": n, "hidden": n}} before (the base ore) and after (base + the layer), from the open-cell predicate
    the caller supplies in each record: base = [(cell, type id, is_exposed)], layer = [(cell, type id, is_exposed)]."""
    out = {"before": {}, "added": {}, "after": {}}
    for tag, rows in (("before", base), ("added", layer)):
        for _c, tid, ex in rows:
            d = out[tag].setdefault(tid, {"exposed": 0, "hidden": 0})
            d["exposed" if ex else "hidden"] += 1
    for tid in set(out["before"]) | set(out["added"]):
        a = out["before"].get(tid, {"exposed": 0, "hidden": 0})
        b = out["added"].get(tid, {"exposed": 0, "hidden": 0})
        out["after"][tid] = {"exposed": a["exposed"] + b["exposed"], "hidden": a["hidden"] + b["hidden"]}
    return out
