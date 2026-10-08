#!/usr/bin/env python
"""Independent audit of Oak's lab scene and Challenge mode (docs/mechanics/OAK_AND_CHALLENGE.md section 6).

WHY THIS EXISTS. tools/challenge_mode.py, its wiring in tools/route_trainers.py, the oak_lab scene and Oak's League
rules were built by one agent, which also asserted its own invariants (challenge_rct's ace check, check_chain,
check_series_guard). Every one of those reads data/challenge_mode.json or data/trainers.json -- the builder's own
data -- so a clean build proves the builder agrees with itself. This audit takes the GENERATED OUTPUT (the in-memory
files the generators emit, exactly what prepare would write) and compares it with sources the builder did not
derive it from:

  upstream     COBBLEVERSE-RCT-DP-v20.zip in the local server snapshot: which trainers form rctmod's `kanto`
               series, their mob files and their requiredDefeats chain, Kanto's series file. COBBLEVERSE-DP-v31.zip:
               the defeat advancements (matched by their own criteria, not by name) and the misty / kanto_league
               structure templates, re-transformed here with vanilla's rotation rule
  rctmod       docs/research/RCT_PER_PLAYER_MODE.md (read from the v0.19.0-beta source): the level-cap formula
               (LevelUtils), isOfSeries, every `player set series` wipes progress, uniqueness by identity
  the config   modpack/config/cobblemon/starters.json and modpack/config/rctmod-server.toml
  the contract data/trainers.json generation_contract.gym_ace_levels and each League record's ace_level
  Codex        docs/story/CHALLENGE_GYM_DESIGN.md "Oak's world-wide choice" (the lines as written), with only the
               three per-player substitutions OAK_AND_CHALLENGE.md section 2 declares
  the world    the gym buildings' emitted command text replayed here over their pad (data/placements.json lot
               level), the lab template (kits/), the misty and kanto_league templates; vanilla's redstone rule
  rctmod       the route-seat swap lines run through a small interpreter of the selectors they use, over every
  selectors    seat and every mix of nearby players, in and out of battle

Checks (FAIL fails the run; REPORT is a finding that needs an owner or another tool, not this audit):

  C   config      allowStarterOnJoin false; the chooser's eight species are the eight standing in the lab
  S   starter     world spawn inside the hint area; Oak's seat standable and reachable on foot from outside the lab
                  template (wooden doors pass, iron doors do not); the greet zone covers Oak's seat and opens his
                  conversation only for stage not_started, once; nothing teleports a player out of the spawn-to-Oak
                  corridor; the lab actors and hint show only while the starter tag (from the compiled
                  starter_chosen callback) is absent; the lab starter conversation grants nothing
  M   series      `rctmod player set series` appears exactly once in all compiled output, names the series the
                  trainers pack defines, sits inside a Molang branch whose condition reads the lock field at its
                  initial value and the negated gym1_cleared probe, and sets the lock in that same branch; no
                  transition anywhere re-opens the lock; the transition is reachable only through the starter-gated
                  edge of Oak's conversation and referenced nowhere else; over every sequence of talks the command
                  runs at most once and never after gym1_cleared
  T   text        Oak's rules pages equal Codex's lines with exactly the declared substitutions; no easy/hard
  B   bosses      the Challenge ids are exactly rctmod's kanto series (read from the zip) suffixed; the series file
                  sets no cap; each mob mirrors upstream's mob with the chain re-pointed; rctmod's level for every
                  Challenge id equals the Normal one and the contract ace, and the cap curve after k defeats is the
                  same in both series; each identity is its own; loot empty; wrong_series line present; each badge
                  flag lists both ids; each win grants the DP-v31 advancement whose criteria name the Normal id
  P   spawners    exactly one Normal and one Challenge spawner per boss across every generated pack and template;
                  the Challenge one set into a solid floor block with two air over it, not on or over a container,
                  door or redstone-sensitive block, its redstone block touching nothing redstone-sensitive, on the
                  same floor and in a straight open line from the Normal leader; the self-placing cycle line checks
                  exactly that cell. A boss in data/challenge_mode.json single_leader.rollout is judged instead by P1
                  (Audit.check_single_leader): one spawner and no second; the swap run through a 3-D command model
                  (CommandWorld) over mixed crowds in and out of battle; the retire function writing only the retired
                  cell and the one under it, back to the gym's own replayed build, removing the old Challenge trainer
                  whether or not the cycle ran first, never in a battle, never the one leader; nothing else still
                  anchored at the retired cell; reapply step R17L running it; for a boss whose one spawner moves
                  (single_leader.move), the move judged against the build and run after the retire, leaving no
                  trainer the swap cannot reach
  R   routes      every seated trainer with a Challenge team has a copy whose mob is the Normal mob but for series,
                  whose team is the record's Challenge team; both ids in the seat's defeat advancement; the swap
                  never summons or kills (one exception, matched exactly: a one-leader boss's retire function may
                  kill its old Challenge-id trainer at the retired cell, out of battle; P1 judges it), never acts in battle, ends on the Challenge id exactly when the nearest
                  player within the seat's reach carries the mode tag, and on the Normal id otherwise
  K   keyed       REPORT: other systems that key on a Normal boss id and never mention the Challenge id

  python tools/challenge_mode_audit.py [--snapshot DIR] [--only C,S,M,T,B,P,R,K]
Exit 0 when clean, 1 with problems, 2 when an upstream input is missing (nothing is passed without its source).

NOT COVERED. Validity, not behaviour. Whether rctmod really refuses the other mode (E2), really reproduces the cap
(E3), lets two identities coexist (E5), wipes on a second call (E6), and whether a TrainerId merge swaps the team at
all (E7) are RCT_PER_PLAYER_MODE.md section 7 and need a running Minecraft. The swap model is of the SELECTORS, not
of rctmod. tools/reapply.py R17 checks a seat by its Normal id only (reapply.py, kind "trainer"): run while a
Challenge player stands within reach, it summons a second trainer; that is reported, not modelled. The donor's
post-placement substitutions inside misty/kanto_league are replayed for P1's restore only (data/spawn_block_policy.json
substitutions, the record's own, its remove_blocks; 2026-10-08); P's floor checks and the healer sweep are not.
P1 models vanilla's commands, not rctmod: no spawner spawns or despawns, a TrainerId merge notifies no spawner, and
whether InBattle is saved as a 0b/1b byte is ASSUMED (reported as P1:inbattle_assumed, never passed as fact). The
one-leader proof in a running game is docs/mechanics/ONE_LEADER_SWAP.md.
Oak's own entry and offer pages are tools/oak_starter_audit.py's (P1/P3/P6); this audit does not re-derive them.
"""
from __future__ import annotations

import argparse
import functools
import importlib
import itertools
import json
import os
import re
import sys
import zipfile
from collections import Counter
from pathlib import Path

STARTER_COUNT = 8   # the owner, 2026-10-08: eight starters, and the set is closed

ROOT = Path(__file__).resolve().parent.parent
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))
DATA = ROOT / "data"
SNAPSHOT = Path(os.environ.get("COBBLERS_SNAPSHOT_DATAPACKS")
                or "C:/Users/wnd/Documents/cobblers-local/server-snapshot-2026-10-05/datapacks")
RCT_ZIP = "COBBLEVERSE-RCT-DP-v20.zip"
DP_ZIP = "COBBLEVERSE-DP-v31.zip"
SERIES_CMD = "rctmod player set series"
SPAWNER = "rctmod:trainer_spawner"
CHECKS = "CSMTBPRK"

# the per-player rewrites OAK_AND_CHALLENGE.md section 2 declares; anything else changed in Codex's lines is a fault
DECLARED_REWRITES = [
    ("This record belongs to the whole campaign. Once I enter it, everyone uses it and it cannot be changed.",
     "This record is yours alone. Once I enter it, it cannot be changed."),
    ("for this world", "for your journey"),
    ("this campaign", "your journey"),
]
BANNED = re.compile(r"\b(easy|easier|easiest|hard|harder|hardest|difficult|difficulty|tougher|toughest)\b", re.I)


def read_json(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def text_of(v):
    if isinstance(v, str):
        return v
    if isinstance(v, list) and all(isinstance(x, str) for x in v):
        return "\n".join(v)
    return json.dumps(v)


def lines_of(v):
    return v if isinstance(v, list) else text_of(v).splitlines()


def strings(v):
    """Every string leaf of a generated file (a line list, a JSON document, or text)."""
    if isinstance(v, str):
        yield v
    elif isinstance(v, dict):
        for x in v.values():
            yield from strings(x)
    elif isinstance(v, list):
        for x in v:
            yield from strings(x)


# ------------------------------------------------------------------------------------------------ block classes
AIRLIKE = {"minecraft:air", "minecraft:cave_air", "minecraft:void_air", "minecraft:light"}
NO_COLLISION_PARTS = ("torch", "flower", "sapling", "short_grass", "tall_grass", "fern", "button", "lever",
                      "pressure_plate", "_sign", "banner", "rail", "redstone_wire", "vine", "ladder", "tripwire",
                      "dead_bush", "carpet", "lily_pad", "snow", "moss_carpet", "cobweb")
FLUIDS = {"minecraft:water", "minecraft:lava", "minecraft:bubble_column"}
CONTAINER_PARTS = ("chest", "barrel", "shulker", "hopper", "dispenser", "dropper", "furnace", "smoker", "brewing",
                   "crafter", "decorated_pot", "lectern", "bookshelf", "sack", "healing_machine")
# what reacts to a redstone block beside it (vanilla components) -- and another spawner, which would be powered too
REDSTONE_SENSITIVE_PARTS = ("door", "trapdoor", "fence_gate", "piston", "redstone_lamp", "dispenser", "dropper",
                            "note_block", "tnt", "powered_rail", "activator_rail", "hopper", "redstone_wire",
                            "repeater", "comparator", "bell", "command_block", "copper_bulb", "crafter", "observer",
                            "trainer_spawner")
INTERACTIVE_PARTS = ("button", "lever", "pressure_plate", "tripwire", "target", "door", "gate", "sign")


def bname(state):
    return (state or "").split("[", 1)[0].split("{", 1)[0]


def is_air(state):
    return bname(state) in AIRLIKE


def passable(state):
    """No collision for a player's feet or head. Unknown (None) is not passable."""
    if state is None:
        return False
    n = bname(state)
    if n in AIRLIKE:
        return True
    if "door" in n and "trapdoor" not in n and "iron" not in n:
        return True
    return any(p in n for p in NO_COLLISION_PARTS)


def solid_floor(state):
    if state is None:
        return False
    n = bname(state)
    return not passable(state) and n not in FLUIDS and "door" not in n


def has_part(state, parts):
    n = bname(state)
    return any(p in n for p in parts)


# ------------------------------------------------------------------------------------------------ upstream
class Upstream:
    """What the installed Cobbleverse packs say, read from the snapshot zips."""

    def __init__(self, snapshot=SNAPSHOT):
        self.snapshot = Path(snapshot)
        self.rct = self.snapshot / RCT_ZIP
        self.dp = self.snapshot / DP_ZIP
        missing = [p for p in (self.rct, self.dp) if not p.exists()]
        if missing:
            raise FileNotFoundError("upstream input missing: %s" % ", ".join(str(p) for p in missing))

    @functools.cached_property
    def mobs(self):
        out = {}
        with zipfile.ZipFile(self.rct) as z:
            for n in z.namelist():
                if "/mobs/trainers/" in n and n.endswith(".json"):
                    out[n.rsplit("/", 1)[1][:-5]] = json.loads(z.read(n).decode("utf-8-sig"))
        return out

    @functools.cached_property
    def series_files(self):
        out = {}
        with zipfile.ZipFile(self.rct) as z:
            for n in z.namelist():
                if "/series/" in n and n.endswith(".json"):
                    out[n.rsplit("/", 1)[1][:-5]] = json.loads(z.read(n).decode("utf-8-sig"))
        return out

    def series_members(self, sid):
        return {k for k, m in self.mobs.items() if sid in (m.get("series") or [])}

    @functools.cached_property
    def defeat_advancements(self):
        """{trainer id: advancement id} for every DP-v31 advancement whose criterion is rctmod:defeat_count."""
        out = {}
        with zipfile.ZipFile(self.dp) as z:
            for n in z.namelist():
                m = re.fullmatch(r"data/([^/]+)/advancement/(.+)\.json", n)
                if not m:
                    continue
                try:
                    d = json.loads(z.read(n).decode("utf-8-sig"))
                except ValueError:
                    continue
                for c in (d.get("criteria") or {}).values():
                    if c.get("trigger") == "rctmod:defeat_count":
                        for t in (c.get("conditions") or {}).get("trainer_ids") or []:
                            out.setdefault(t, set()).add("%s:%s" % (m.group(1), m.group(2)))
        return out

    @functools.lru_cache(maxsize=4)
    def template(self, name):
        """(size, {cell: state}) of data/cobbleverse/structure/<name>.nbt, spawner NBT kept on the state."""
        import nbt
        with zipfile.ZipFile(self.dp) as z:
            _n, t = nbt.loads(z.read("data/cobbleverse/structure/%s.nbt" % name))
        return template_cells(t)


def template_cells(t):
    pal = []
    for p in t["palette"]:
        props = p.get("Properties") or {}
        pal.append(p["Name"] + ("[%s]" % ",".join("%s=%s" % kv for kv in sorted(props.items())) if props else ""))
    cells = {}
    for b in t["blocks"]:
        st = pal[b["state"]]
        if bname(st) == SPAWNER:
            ids = list((b.get("nbt") or {}).get("TrainerIds") or [])
            st = st + "{TrainerIds:%s}" % json.dumps(ids)
        cells[tuple(b["pos"])] = st
    return list(t["size"]), cells


def rotate(cell, origin, rotation):
    """Vanilla StructureTemplate placement about pivot (0,0,0), mirror none: CLOCKWISE_90 (x, z) -> (-z, x),
    CLOCKWISE_180 -> (-x, -z), COUNTERCLOCKWISE_90 -> (z, -x)."""
    x, y, z = cell
    ox, oy, oz = origin
    r = {"none": (x, z), "clockwise_90": (-z, x), "clockwise_180": (-x, -z), "counterclockwise_90": (z, -x)}
    if rotation not in r:
        raise ValueError("rotation %r" % rotation)
    dx, dz = r[rotation]
    return (ox + dx, oy + y, oz + dz)


def spawner_ids(state):
    m = re.search(r"TrainerIds:\s*(\[[^\]]*\])", state or "")
    if not m:
        return []
    return re.findall(r'"([^"]+)"', m.group(1))


# ------------------------------------------------------------------------------------------------ gym replay
FILL = re.compile(r"^fill (-?\d+) (-?\d+) (-?\d+) (-?\d+) (-?\d+) (-?\d+) (\S+)(?: (replace|outline|hollow|keep|destroy))?(?: (\S+))?$")
SET = re.compile(r"^setblock (-?\d+) (-?\d+) (-?\d+) (\S+)$")


class Replay:
    """The emitted fill/setblock text of one building over a pad: rock to `level`, sky above. Written here, not taken
    from the generator's own voxel model."""

    def __init__(self, lines, level):
        self.level = level
        self.cells = {}
        for raw in lines:
            line = raw.strip()
            m = FILL.match(line)
            if m:
                x0, y0, z0, x1, y1, z1 = (int(v) for v in m.groups()[:6])
                state, mode, filt = m.group(7), m.group(8), m.group(9)
                for x in range(min(x0, x1), max(x0, x1) + 1):
                    for y in range(min(y0, y1), max(y0, y1) + 1):
                        for z in range(min(z0, z1), max(z0, z1) + 1):
                            edge = x in (x0, x1) or y in (y0, y1) or z in (z0, z1)
                            if mode in ("outline", "hollow") and not edge:
                                if mode == "hollow":
                                    self.cells[(x, y, z)] = "minecraft:air"
                                continue
                            if mode == "keep" and not is_air(self.at((x, y, z))):
                                continue
                            if mode == "replace" and filt and bname(self.at((x, y, z))) != bname(filt):
                                continue
                            self.cells[(x, y, z)] = state
                continue
            m = SET.match(line)
            if m:
                self.cells[tuple(int(v) for v in m.groups()[:3])] = m.group(4)

    def at(self, c):
        st = self.cells.get(tuple(c))
        if st is not None:
            return st
        return "minecraft:stone" if c[1] <= self.level else "minecraft:air"

    def spawners(self):
        return [(c, spawner_ids(s)) for c, s in self.cells.items() if bname(s) == SPAWNER]


class TemplateWorld:
    """A placed template. A cell the template does not list is structure void: the world keeps what was there, and
    on a levelled lot that is rock to the lot's level and air above it (the prep cuts and fills the lot; plan data,
    not a world read). Without a level, a void cell stays unknown (None) and every check on it fails."""

    def __init__(self, size, cells, origin, rotation, level=None):
        self.cells = {rotate(c, origin, rotation): s for c, s in cells.items()}
        self.level = level

    def at(self, c):
        st = self.cells.get(tuple(c))
        if st is None and self.level is not None:
            return "minecraft:stone" if c[1] <= self.level else "minecraft:air"
        return st

    def spawners(self):
        return [(c, spawner_ids(s)) for c, s in self.cells.items() if bname(s) == SPAWNER]


# ------------------------------------------------------------------------------------------------ rctmod's cap
def trainer_level(tid, top, mobs, series_rel, config_rel, memo=None):
    """LevelUtils.trainerLevel (RCT_PER_PLAYER_MODE.md section 3): max(clamp(top + relativeLevelCap), max over
    requiredDefeats of their level); the trainer's own relativeLevelCap beats the series' and the config's."""
    memo = {} if memo is None else memo
    if tid in memo:
        return memo[tid]
    mob = mobs[tid]
    rel = mob.get("relativeLevelCap")
    if rel is None:
        rel = series_rel if series_rel is not None else config_rel
    own = min(100, max(0, top[tid] + rel))
    reqs = [r for g in (mob.get("requiredDefeats") or []) for r in g]
    memo[tid] = max([own] + [trainer_level(r, top, mobs, series_rel, config_rel, memo) for r in reqs])
    return memo[tid]


def chain_order(mobs):
    """The members of one linear requiredDefeats chain, root first; None when it is not one chain."""
    req = {t: [r for g in (m.get("requiredDefeats") or []) for r in g] for t, m in mobs.items()}
    roots = [t for t, r in req.items() if not r]
    if len(roots) != 1:
        return None
    order, cur = [roots[0]], roots[0]
    while True:
        nxt = [t for t, r in req.items() if r == [cur]]
        if not nxt:
            break
        if len(nxt) != 1:
            return None
        cur = nxt[0]
        order.append(cur)
    return order if len(order) == len(mobs) else None


def cap_curve(order, levels, initial):
    """The cap after k defeats along the chain, k = 0..n: max(initialLevelCap, level of the next), 100 at the end."""
    return [max(initial, levels[order[k]]) if k < len(order) else 100 for k in range(len(order) + 1)]


def toml_value(path, key):
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        m = re.match(r"\s*%s\s*=\s*\"?([^\"#]+)\"?" % re.escape(key), line)
        if m:
            v = m.group(1).strip()
            return int(v) if re.fullmatch(r"-?\d+", v) else v
    return None


# ------------------------------------------------------------------------------------------------ selector model
def split_args(body):
    out, depth, cur, q = [], 0, "", False
    for ch in body:
        if ch == '"':
            q = not q
        if not q and ch in "{[":
            depth += 1
        if not q and ch in "}]":
            depth -= 1
        if ch == "," and depth == 0 and not q:
            out.append(cur)
            cur = ""
            continue
        cur += ch
    if cur:
        out.append(cur)
    return [a.strip() for a in out]


def take_selector(tokens_text):
    """(selector, rest) from the start of `tokens_text`."""
    m = re.match(r"@[aeprs]", tokens_text)
    if not m:
        raise ValueError("no selector at %r" % tokens_text[:40])
    i = 2
    if i < len(tokens_text) and tokens_text[i] == "[":
        depth, q = 0, False
        while i < len(tokens_text):
            ch = tokens_text[i]
            if ch == '"':
                q = not q
            if not q and ch in "[{":
                depth += 1
            if not q and ch in "]}":
                depth -= 1
                if depth == 0:
                    i += 1
                    break
            i += 1
    return tokens_text[:i], tokens_text[i:].lstrip()


def parse_selector(sel):
    kind = sel[1]
    args = {}
    if "[" in sel:
        for a in split_args(sel[sel.index("[") + 1:-1]):
            k, _, v = a.partition("=")
            args.setdefault(k, []).append(v)
    return kind, args


class SeatModel:
    """One seat: trainers stand ON the seat; players at a distance from it. Enough of vanilla's selectors to run the
    swap lines (as / at @s / if|unless entity / data merge entity ... {TrainerId})."""

    def __init__(self, seat, trainers, players):
        self.seat = tuple(seat)
        self.trainers = [dict(t) for t in trainers]     # {"id", "battle"}
        self.players = [dict(p) for p in players]        # {"d", "tags"}

    @staticmethod
    def _dist(base, ent):
        """Trainers stand on the seat (distance 0 from it); a player stands `d` from it. `base` is the seat, a
        player, or FAR (a selector anchored somewhere else)."""
        if base == "seat":
            return 0.0 if "id" in ent else ent["d"]
        if base == "far":
            return 1e9
        if ent is base:
            return 0.0
        return base["d"] if "id" in ent else abs(ent["d"] - base["d"])

    @staticmethod
    def _nbt_ok(t, nbt):
        m = re.search(r'TrainerId:"([^"]+)"', nbt)
        if m and t["id"] != m.group(1):
            return False
        if "InBattle:0b" in nbt and t["battle"]:
            return False
        return True

    def select(self, sel, executor, base):
        kind, a = parse_selector(sel)
        if kind == "s":
            pool = [executor] if executor is not None else []
        elif kind == "e":
            types = a.get("type", [])
            pool = list(self.trainers) if types == ["rctmod:trainer"] else (
                list(self.trainers) + list(self.players) if not types else [])
        else:
            pool = list(self.players)
        if "x" in a:
            here = (float(a["x"][0]), float(a["y"][0]), float(a["z"][0]))
            seat = (self.seat[0] + 0.5, self.seat[1], self.seat[2] + 0.5)
            base = "seat" if max(abs(here[i] - seat[i]) for i in range(3)) <= 0.51 else "far"
        out = []
        for e in pool:
            ok = True
            for d in a.get("distance", []):
                if not d.startswith(".."):
                    raise ValueError("distance %r" % d)
                if self._dist(base, e) > float(d[2:]) + 1e-9:
                    ok = False
            for t in a.get("tag", []):
                tags = e.get("tags", set())
                if (t.startswith("!") and t[1:] in tags) or (not t.startswith("!") and t not in tags):
                    ok = False
            for n in a.get("nbt", []):
                if "id" not in e or not self._nbt_ok(e, n):
                    ok = False
            if a.get("type") == ["rctmod:trainer"] and "id" not in e:
                ok = False
            if ok:
                out.append(e)
        if kind == "p":
            out = sorted(out, key=lambda e: self._dist(base, e))[:1]
        if "limit" in a:
            out = out[:int(a["limit"][0])]
        return out

    def run(self, line):
        """Run one `execute ... run data merge entity <sel> {TrainerId:"X"}` line; anything else is refused."""
        m = re.fullmatch(r'execute (.*) run data merge entity (@\S+?(?:\[.*\])?) \{TrainerId:"([^"]+)"\}', line)
        if not m:
            raise ValueError("not a TrainerId merge: %s" % line[:80])
        chain, target, new = m.group(1), m.group(2), m.group(3)
        ctxs = [(None, "seat")]
        rest = chain
        while rest:
            if rest.startswith("as "):
                sel, rest = take_selector(rest[3:])
                ctxs = [(e, b) for (_x, b) in ctxs for e in self.select(sel, _x, b)]
            elif rest.startswith("at @s"):
                rest = rest[5:].lstrip()
                ctxs = [(x, ("seat" if x is not None and "id" in x else x)) for (x, _b) in ctxs]
            elif rest.startswith("if entity ") or rest.startswith("unless entity "):
                neg = rest.startswith("unless")
                sel, rest = take_selector(rest[len("unless entity " if neg else "if entity "):])
                ctxs = [(x, b) for (x, b) in ctxs if bool(self.select(sel, x, b)) != neg]
            else:
                raise ValueError("unsupported execute part %r" % rest[:40])
        for x, b in ctxs:
            for t in self.select(target, x, b):
                if "id" in t:
                    t["id"] = new


class CommandWorld:
    """A small 3-D world for a one-leader gym (data/challenge_mode.json single_leader.rollout): blocks by cell,
    trainers and players at real positions. Written here from vanilla's command rules, not from tools/challenge_mode.py:

      execute   if loaded | if/unless block X Y Z state | if/unless entity <sel> | positioned X Y Z | as <sel> | at @s
      run       data merge block X Y Z {TrainerIds:[..]} | data merge entity <sel> {TrainerId:".."} | setblock | kill
                | tag <sel> add|remove <name> (also as a bare line, run by the server with no position)

    Selectors: @a @p @e @s with x/y/z (the origin), distance=..r, type, tag (and tag=!name), nbt (TrainerId,
    InBattle), sort=nearest|furthest|arbitrary, limit; @p sorts nearest, @e and @a arbitrary (list order), and limit
    applies after the sort. Distances are measured from the selector's own x/y/z if given, else from the position
    the execute chain has reached at that point. A block predicate `name{TrainerIds:[..]}` matches when every listed id is in the block's list (vanilla's
    NBT list predicate). A `data merge entity` whose target can match more than one entity is REFUSED, as vanilla
    refuses it when the function loads. `inbattle=False` models an rctmod that never saves InBattle as a byte: no
    InBattle predicate matches then. rctmod itself is not modelled (a spawner never spawns, a merge notifies nothing)."""

    def __init__(self, blocks, trainers, players, inbattle=True):
        self.blocks = dict(blocks)                     # {(x, y, z): state}
        self.trainers = [dict(t) for t in trainers]    # {"id", "battle", "pos": (x, y, z)}
        self.players = [dict(p) for p in players]      # {"pos": (x, y, z), "tags": set}
        self.inbattle = inbattle

    @staticmethod
    def _d(a, b):
        return sum((a[i] - b[i]) ** 2 for i in range(3)) ** 0.5

    def _nbt(self, t, nbt):
        body = nbt.strip()[1:-1]
        for part in split_args(body):
            k, _, v = part.partition(":")
            if k == "TrainerId":
                if t["id"] != v.strip('"'):
                    return False
            elif k == "InBattle":
                if not self.inbattle or v not in ("0b", "1b") or t["battle"] != (v == "1b"):
                    return False
            else:
                raise ValueError("nbt key %r is not modelled" % k)
        return True

    def select(self, sel, executor, pos):
        kind, a = parse_selector(sel)
        if kind == "s":
            pool = [executor] if executor is not None else []
        elif kind == "e":
            if a.get("type") != ["rctmod:trainer"]:
                raise ValueError("@e without type=rctmod:trainer is not modelled: %s" % sel)
            pool = list(self.trainers)
        else:
            pool = list(self.players)
        origin = pos
        if "x" in a:
            origin = (float(a["x"][0]), float(a["y"][0]), float(a["z"][0]))
        out = []
        for e in pool:
            ok = True
            for d in a.get("distance", []):
                if not d.startswith(".."):
                    raise ValueError("distance %r" % d)
                if origin is None:
                    raise ValueError("a distance with no position: %s" % sel)
                if self._d(origin, e["pos"]) > float(d[2:]) + 1e-9:
                    ok = False
            for t in a.get("tag", []):
                tags = e.get("tags", set())
                if (t.startswith("!") and t[1:] in tags) or (not t.startswith("!") and t not in tags):
                    ok = False
            for n in a.get("nbt", []):
                if "id" not in e or not self._nbt(e, n):
                    ok = False
            if a.get("type") == ["rctmod:trainer"] and "id" not in e:
                ok = False
            if set(a) - {"x", "y", "z", "distance", "tag", "nbt", "type", "limit", "sort"}:
                raise ValueError("selector argument not modelled: %s" % sel)
            if ok:
                out.append(e)
        # vanilla: @p sorts nearest and takes one; @e/@a sort `arbitrary` unless told; limit applies after the sort
        sort = (a.get("sort") or ["nearest" if kind == "p" else "arbitrary"])[0]
        if sort not in ("nearest", "furthest", "arbitrary"):
            raise ValueError("sort=%s is not modelled" % sort)
        if sort != "arbitrary":
            if origin is None:
                raise ValueError("a sort with no position: %s" % sel)
            out = sorted(out, key=lambda e: self._d(origin, e["pos"]), reverse=(sort == "furthest"))
        if kind == "p":
            out = out[:1]
        if "limit" in a:
            out = out[:int(a["limit"][0])]
        return out

    @staticmethod
    def _single(sel):
        kind, a = parse_selector(sel)
        return kind in "sp" or a.get("limit") == ["1"]

    def block_ok(self, cell, pred):
        state = self.blocks.get(cell, "minecraft:air")
        name = pred.split("{", 1)[0]
        if bname(state) != name:
            return False
        if "{" in pred:
            have = spawner_ids(state)
            return all(i in have for i in spawner_ids(pred))
        return True

    def run(self, line):
        line = line.strip()
        if not line or line.startswith("#"):
            return
        if line.startswith("tag "):
            return self._do(line, None, None)
        if not line.startswith("execute "):
            raise ValueError("not modelled: %s" % line[:80])
        chain, sep, cmd = line[len("execute "):].partition(" run ")
        if not sep:
            raise ValueError("no run: %s" % line[:80])
        ctxs, rest = [(None, None)], chain.strip()
        while rest:
            m = re.match(r"if loaded -?\d+ -?\d+ -?\d+\s*", rest)
            if m:
                rest = rest[m.end():]
                continue
            m = re.match(r"(if|unless) block (-?\d+) (-?\d+) (-?\d+) (\S+)\s*", rest)
            if m:
                cell = tuple(int(v) for v in m.groups()[1:4])
                if self.block_ok(cell, m.group(5)) == (m.group(1) == "unless"):
                    return
                rest = rest[m.end():]
                continue
            m = re.match(r"positioned (-?[\d.]+) (-?[\d.]+) (-?[\d.]+)\s*", rest)
            if m:
                p = tuple(float(v) for v in m.groups())
                ctxs = [(x, p) for x, _p in ctxs]
                rest = rest[m.end():]
                continue
            if rest.startswith("as "):
                sel, rest = take_selector(rest[3:])
                ctxs = [(e, p) for (x, p) in ctxs for e in self.select(sel, x, p)]
                continue
            if rest.startswith("at @s"):
                rest = rest[5:].lstrip()
                ctxs = [(x, x["pos"] if x is not None else p) for (x, p) in ctxs]
                continue
            if rest.startswith("if entity ") or rest.startswith("unless entity "):
                neg = rest.startswith("unless")
                sel, rest = take_selector(rest[len("unless entity " if neg else "if entity "):])
                ctxs = [(x, p) for (x, p) in ctxs if bool(self.select(sel, x, p)) != neg]
                continue
            raise ValueError("execute part not modelled: %r" % rest[:50])
        for x, p in ctxs:
            self._do(cmd, x, p)

    def _do(self, cmd, x, p):
        """One command run as `x` at `p` (both None for a bare line of the function: the server, no position)."""
        m = re.fullmatch(r"tag (@\S+?(?:\[.*\])?) (add|remove) ([A-Za-z0-9_.+-]+)", cmd)
        if m:
            for t in self.select(m.group(1), x, p):
                tags = t.setdefault("tags", set())
                (tags.add if m.group(2) == "add" else tags.discard)(m.group(3))
            return
        m = re.fullmatch(r'data merge block (-?\d+) (-?\d+) (-?\d+) \{TrainerIds:(\[[^\]]*\])\}', cmd)
        if m:
            cell = tuple(int(v) for v in m.groups()[:3])
            state = self.blocks.get(cell, "minecraft:air")
            if bname(state) == SPAWNER:
                self.blocks[cell] = "%s{TrainerIds:%s}" % (SPAWNER, m.group(4))
            return
        m = re.fullmatch(r'data merge entity (@\S+?(?:\[.*\])?) \{TrainerId:"([^"]+)"\}', cmd)
        if m:
            if not self._single(m.group(1)):
                raise ValueError("data merge entity needs one target; vanilla refuses %s" % m.group(1))
            for t in self.select(m.group(1), x, p):
                t["id"] = m.group(2)
            return
        m = re.fullmatch(r"setblock (-?\d+) (-?\d+) (-?\d+) (\S+)", cmd)
        if m:
            self.blocks[tuple(int(v) for v in m.groups()[:3])] = m.group(4)
            return
        m = re.fullmatch(r"kill (@\S+?(?:\[.*\])?)", cmd)
        if m:
            gone = self.select(m.group(1), x, p)
            self.trainers = [t for t in self.trainers if not any(t is g for g in gone)]
            return
        raise ValueError("run not modelled: %s" % cmd[:80])


# ------------------------------------------------------------------------------------------------ the artifacts
class Artifacts:
    """The generated output under audit, produced by the generators as they are now (tests swap in mutated ones
    through sys.modules)."""

    def __init__(self, data=DATA):
        self.data = Path(data)

    def mod(self, name):
        return sys.modules.get(name) or importlib.import_module(name)

    @functools.cached_property
    def trainers(self):
        return self.mod("route_trainers").files()

    @functools.cached_property
    def dialogue(self):
        files, _done, refused = self.mod("compile_dialogue").build_all(self.data)
        return files

    @functools.cached_property
    def scenes(self):
        files, _s = self.mod("scenes_pack").build(self.data)
        return files

    @functools.cached_property
    def gyms(self):
        """{gym id: (leader id, [command lines], pad level)} from tools/gym_buildings.py's emitted text."""
        GB = self.mod("gym_buildings")
        out = {}
        for _p, doc in GB.records():
            e, _rect, _lvl = GB.build_one(doc)
            out[doc["id"]] = ((doc.get("leader") or {}).get("id"), list(e.ops), doc["settlement"])
        return out

    @functools.cached_property
    def seats(self):
        recs, seats, _f = self.mod("route_trainers").load()
        return recs, seats


# ------------------------------------------------------------------------------------------------ the audit
class Audit:
    def __init__(self, art, up, root=ROOT):
        self.art, self.up, self.root = art, up, Path(root)
        self.data = self.root / "data"
        self.problems, self.reports, self.notes = [], [], []
        self.ran = 0

    def fail(self, code, msg):
        self.problems.append((code, msg))

    def report(self, code, msg):
        self.reports.append((code, msg))

    def note(self, msg):
        self.notes.append(msg)

    def doc(self, name):
        return read_json(self.data / name)

    # ---- shared readings
    @functools.cached_property
    def cm(self):
        return self.doc("challenge_mode.json")

    @functools.cached_property
    def suffix(self):
        return self.cm["id_suffix"]

    @functools.cached_property
    def series_id(self):
        """The series the trainers pack actually defines (one file under data/rctmod/series/)."""
        got = [k for k in self.art.trainers if re.fullmatch(r"data/rctmod/series/[a-z0-9_]+\.json", k)]
        return got[0].rsplit("/", 1)[1][:-5] if len(got) == 1 else None

    @functools.cached_property
    def kanto(self):
        return sorted(self.up.series_members("kanto"))

    @functools.cached_property
    def starter_tag(self):
        """The tag the compiled starter_chosen callback adds (Cobblemon's callback, not the scene's notion of it)."""
        for k, v in self.art.dialogue.items():
            if "/callbacks/starter_chosen/" in k:
                m = re.search(r"tag \S+ add ([a-z0-9_.]+)|add ([a-z0-9_.]+)", text_of(v))
                if m:
                    return m.group(1) or m.group(2)
        return None

    def conv(self, cid):
        return next(c for c in self.doc("dialogue.json")["conversations"] if c["id"] == cid)

    def transitions(self):
        for q in self.doc("quests.json")["quests"]:
            for t in q.get("transitions") or []:
                yield q["id"], t

    def field_decl(self, fid):
        return next((f for f in self.doc("progression.json")["quest_fields"] if f.get("id") == fid), None)

    # ================================================================================================ C
    def check_config(self):
        cfg = read_json(self.root / "modpack" / "config" / "cobblemon" / "starters.json")
        if cfg.get("allowStarterOnJoin") is not False:
            self.fail("C:allow_on_join", "starters.json allowStarterOnJoin is %r, not false"
                      % cfg.get("allowStarterOnJoin"))
        species = [p.split()[0] for c in cfg.get("starters") or [] for p in c.get("pokemon") or []]
        # the owner, 2026-10-08: "Eight, and STOP THERE. The set is full and more dilutes the choice."
        if len(species) != STARTER_COUNT or len(set(species)) != STARTER_COUNT:
            self.fail("C:eight", "the chooser offers %d entries (%s), not %d distinct"
                      % (len(species), species, STARTER_COUNT))
        scene = next((s for s in self.doc("scenes.json")["scenes"] if s["id"] == "oak_lab"), None)
        if scene is None:
            self.fail("C:lab_scene", "data/scenes.json has no oak_lab scene")
            return
        actors = sorted(a["species"] for a in scene.get("actors") or [])
        if actors != sorted(species):
            self.fail("C:lab_species", "the lab shows %s; the chooser offers %s" % (actors, sorted(species)))
        self.ran += 3

    # ================================================================================================ S
    def check_starter(self):
        scene = next(s for s in self.doc("scenes.json")["scenes"] if s["id"] == "oak_lab")
        tag = self.starter_tag
        if not tag:
            self.fail("S:callback", "no compiled starter_chosen callback adds a tag: nothing marks a pick")
            return
        spawn = (self.doc("world.json").get("export") or {}).get("spawn")
        a0, a1 = scene["area"]["from"], scene["area"]["to"]
        if not spawn or not (min(a0[0], a1[0]) <= spawn[0] <= max(a0[0], a1[0])
                             and min(a0[2], a1[2]) <= spawn[1] <= max(a0[2], a1[2])):
            self.fail("S:hint_at_spawn", "world spawn %s is outside the oak_lab area %s..%s: the hint is not seen "
                      "from spawn" % (spawn, a0, a1))
        seat = next(s for s in self.doc("npc_seats.json")["seats"] if s.get("conversation") == "dlg_main_pallet_oak")
        oak = tuple(seat["at"])
        lab = next(p for p in self.doc("placements.json")["placements"] if p["id"] == "hometown_oaks_lab")
        if lab.get("rotation", "none") != "none" or lab.get("mirror", "none") != "none":
            self.fail("S:lab_rotation", "the lab is rotated (%s): this audit's walk does not model that" % lab["rotation"])
            return
        import nbt
        _n, t = nbt.loads((self.root / lab["file"]).read_bytes())
        size, cells = template_cells(t)
        ox, oz = lab["position"]["x"], lab["position"]["z"]
        oy = oak[1] - 1          # Oak stands on the template's floor layer: checked by `stand` below
        at = lambda c: cells.get((c[0] - ox, c[1] - oy, c[2] - oz), "minecraft:air"
                                 if not (0 <= c[0] - ox < size[0] and 0 <= c[2] - oz < size[2]) else None)
        stand = lambda c: solid_floor(at((c[0], c[1] - 1, c[2]))) and passable(at(c)) and passable(at((c[0], c[1] + 1, c[2])))
        if not stand(oak):
            self.fail("S:oak_stands", "Oak's seat %s is not standable in the lab template (floor %s, feet %s)"
                      % (oak, at((oak[0], oak[1] - 1, oak[2])), at(oak)))
        # walk in from every cell just outside the template's footprint on the floor layer
        y = oak[1]
        starts = [(x, y, z) for x in range(ox - 1, ox + size[0] + 1) for z in range(oz - 1, oz + size[2] + 1)
                  if not (ox <= x < ox + size[0] and oz <= z < oz + size[2])]
        seen, todo = set(starts), list(starts)
        while todo:
            c = todo.pop()
            for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                for dy in (0, 1, -1):
                    n = (c[0] + dx, c[1] + dy, c[2] + dz)
                    if n in seen or not (ox - 1 <= n[0] <= ox + size[0] and oz - 1 <= n[2] <= oz + size[2]):
                        continue
                    inside = ox <= n[0] < ox + size[0] and oz <= n[2] < oz + size[2]
                    if not inside and n[1] != y:
                        continue          # outside the template the town ground is taken as the floor level
                    if inside and not (oy <= n[1] < oy + size[1] and stand(n)):
                        continue
                    if dy == 1 and not passable(at((c[0], c[1] + 2, c[2]))):
                        continue
                    seen.add(n)
                    todo.append(n)
        if oak not in seen:
            self.fail("S:oak_reachable", "Oak's seat %s cannot be reached on foot from outside the lab template "
                      "(wooden doors pass, iron do not)" % (oak,))
        # the greet zone, from the compiled beat
        beat = lines_of(self.art.scenes.get("data/cobblers/function/scenes/oak_lab/beat.mcfunction") or [])
        greet = [l for l in beat if "opendialogue cobblers:dlg_main_pallet_oak" in l]
        if len(greet) != 1:
            self.fail("S:greet", "the oak_lab beat opens Oak's conversation from %d lines, not 1" % len(greet))
        else:
            g = greet[0]
            m = re.search(r"@s\[x=(-?\d+),y=(-?\d+),z=(-?\d+),dx=(\d+),dy=(\d+),dz=(\d+)\]", g)
            stage_key = "cobblers__quest__main_worldshift_reveal__stage"
            greet_key = "cobblers__quest__main_worldshift_reveal__oak_greeted"
            cond = g[g.index("runmolang"):g.index("? {")] if "? {" in g else ""
            if not m:
                self.fail("S:greet_box", "the greet line has no box selector: %s" % g[:100])
            else:
                x, yy, z, dx, dy, dz = (int(v) for v in m.groups())
                if not (x <= oak[0] <= x + dx and yy <= oak[1] <= yy + dy and z <= oak[2] <= z + dz):
                    self.fail("S:greet_box", "the greet zone %s does not hold Oak's seat %s" % (m.group(0), oak))
            if "%s == 'not_started'" % stage_key not in cond or "%s != 1" % greet_key not in cond:
                self.fail("S:greet_once", "the greet opens Oak without requiring stage not_started and not yet "
                          "greeted: %s" % cond[:200])
            body = g[g.index("? {"):] if "? {" in g else ""
            if "%s = 1" % greet_key not in body or "save_data" not in body:
                self.fail("S:greet_once", "the greet branch does not record that it ran (oak_greeted = 1, saved)")
        # nothing teleports a player out of the spawn-to-Oak corridor
        xs = (min(spawn[0], ox) - 2, max(spawn[0], ox + size[0]) + 2) if spawn else (ox, ox + size[0])
        zs = (min(spawn[1], oz) - 2, max(spawn[1], oz + size[2]) + 2) if spawn else (oz, oz + size[2])
        for pack, files in (("scenes", self.art.scenes), ("trainers", self.art.trainers), ("dialogue", self.art.dialogue)):
            for k, v in files.items():
                if not k.endswith(".mcfunction"):
                    continue
                for line in lines_of(v):
                    if " tp @" not in line and not line.startswith("tp @"):
                        continue
                    for m in re.finditer(r"@[as]\[x=(-?\d+),y=(-?\d+),z=(-?\d+),dx=(\d+),dy=(\d+),dz=(\d+)", line):
                        x, yy, z, dx, dy, dz = (int(v) for v in m.groups())
                        if x <= xs[1] and x + dx >= xs[0] and z <= zs[1] and z + dz >= zs[0] and yy <= 135 and yy + dy >= 105:
                            self.fail("S:corridor_tp", "%s %s teleports players in the spawn-to-Oak corridor: %s"
                                      % (pack, k, line[:140]))
        # actors and hint only before the pick
        neg = "!(q.player.has_tag('%s'))" % tag
        mol = " ".join(l for l in beat if l.startswith("runmolang"))

        def branch_condition(i):
            """The condition of the Molang branch that holds position i: the text from the statement start to `? {`."""
            br = mol.rfind("? {", 0, i)
            return mol[mol.rfind(";", 0, br) + 1:br] if br >= 0 else ""
        for a in scene.get("actors") or []:
            for p in a.get("place") or []:
                i = mol.find("oak_lab/%s/at/%s'" % (a["id"], p["marker"]))
                if i < 0 or neg not in branch_condition(i):
                    self.fail("S:actor_after_pick", "actor %s at %s is not placed under %s" % (a["id"], p["marker"], neg))
        i = mol.find("fx/oak_is_waiting")
        if i < 0 or neg not in branch_condition(i):
            self.fail("S:hint_after_pick", "the lab hint is not conditioned on %s" % neg)
        whens = [json.dumps(p.get("when")) for a in scene.get("actors") or [] for p in a.get("place") or []]
        if not any("stage" in w for w in whens):
            self.report("S:legacy_tagless", "the lab actors and hint key on the %s tag alone. A player who picked a "
                        "starter before the starter_chosen callback was installed (any pick before the 2026-10-05 "
                        "build) has no tag and is past not_started: they see five starters and 'Professor Oak is "
                        "waiting' in Pallet for good. A stage condition (not_started) would exclude them" % tag)
        # the lab starter conversation grants nothing
        lab_dlg = text_of(self.art.dialogue.get("data/cobblers/dialogues/dlg_main_pallet_lab_starter.json") or "")
        for bad in ("give ", "openstarterscreen", "spawnpokemon", "pokegive", "givepokemon"):
            if bad in lab_dlg:
                self.fail("S:lab_dialogue_gives", "dlg_main_pallet_lab_starter runs %r" % bad.strip())
        self.ran += 9

    # ================================================================================================ M
    def check_series_command(self):
        lock = self.cm["mode"]["lock_field"]
        decl = self.field_decl(lock)
        if not decl:
            self.fail("M:lock_declared", "%s is not a declared quest field" % lock)
            return
        initial = decl.get("initial")
        sites = []
        for pack, files in (("dialogue", self.art.dialogue), ("scenes", self.art.scenes), ("trainers", self.art.trainers)):
            for k, v in files.items():
                for s in strings(v):
                    for m in re.finditer(re.escape(SERIES_CMD), s):
                        sites.append((pack, k, s, m.start()))
        if len(sites) != 1:
            self.fail("M:once", "`%s` appears %d times in the compiled output (%s), not once"
                      % (SERIES_CMD, len(sites), sorted({s[1] for s in sites})))
        if not sites:
            return
        _pack, path, action, i = sites[0]
        named = re.match(re.escape(SERIES_CMD) + r" ([a-z0-9_]+)", action[i:]).group(1)
        if named != self.series_id:
            self.fail("M:series_name", "the command sets series %s; the trainers pack defines %s" % (named, self.series_id))
        # the molang action that holds it: inside a branch whose condition holds the lock and the gym1 probe
        depth, opens = 0, []
        for j, ch in enumerate(action[:i]):
            if ch == "{":
                opens.append(j)
            elif ch == "}":
                opens.pop() if opens else None
        if not opens:
            self.fail("M:guarded", "the series command runs outside any Molang branch: %s" % action[:200])
            return
        br = opens[-1]
        cond = action[action.rfind(";", 0, br) + 1:br]
        key = "cobblers__" + lock.replace(".", "__")
        if "%s == %s" % (key, "'%s'" % initial) not in cond:
            self.fail("M:guarded", "the branch running the series command does not require %s == %r: %s"
                      % (lock, initial, cond.strip()[:200]))
        probe = re.findall(r"advancements=\{cobblers:flag/gym1_cleared=true\}\] run tag @s add ([a-z0-9_]+)", action[:br])
        if not probe or "!(q.player.has_tag('%s'))" % probe[-1] not in cond:
            self.fail("M:gym1", "the branch running the series command does not refuse a gym1_cleared player: %s"
                      % cond.strip()[:200])
        close = action.find("}", i)
        body = action[br:close]
        if not re.search(r"%s = '(?!%s')[a-z_]+'" % (re.escape(key), re.escape(str(initial))), body):
            self.fail("M:locks_itself", "the branch running the series command does not move %s off %r" % (lock, initial))
        if "save_data" not in action[i:]:
            self.fail("M:locks_itself", "the lock written beside the series command is never saved")
        # nothing re-opens the lock, and only one-shot transitions write it
        writers = []
        for qid, t in self.transitions():
            for e in t.get("effects") or []:
                if e.get("kind") == "set_progression" and e.get("field") == lock:
                    writers.append(t["id"])
                    if e.get("value") == initial:
                        self.fail("M:reopened", "%s/%s sets %s back to %r" % (qid, t["id"], lock, initial))
                    if not any(c.get("kind") == "progression_equals" and c.get("field") == lock
                               and c.get("value") == initial for c in t.get("conditions") or []):
                        self.fail("M:reopened", "%s writes %s without requiring it %r" % (t["id"], lock, initial))
        compiled = sum(len(re.findall(r"%s = " % re.escape(key), s))
                       for files in (self.art.dialogue, self.art.scenes) for v in files.values() for s in strings(v))
        if compiled != len(writers):
            self.fail("M:other_writers", "the compiled dialogue and scenes write %s %d times; data/quests.json has %d "
                      "writers" % (lock, compiled, len(writers)))
        series_t = [(qid, t) for qid, t in self.transitions()
                    if any(e.get("kind") == "rctmod_series" for e in t.get("effects") or [])]
        if len(series_t) != 1:
            self.fail("M:once", "%d transitions run rctmod_series, not 1" % len(series_t))
            return
        tid = series_t[0][1]["id"]
        # every writer of the lock referenced only from Oak's conversation (a scene zone or another dialogue could
        # otherwise run it before the starter: test_oak_starter.py's gate looks at Oak's conversation alone)
        for w in sorted(set(writers) | {tid}):
            refs = []
            for p in sorted(self.data.rglob("*.json")):
                if p.name != "quests.json" and re.search(r"\b%s\b" % re.escape(w), p.read_text(encoding="utf-8", errors="replace")):
                    refs.append(p.relative_to(self.root).as_posix())
            if refs != ["data/dialogue.json"]:
                self.fail("M:referenced_elsewhere", "%s is referenced from %s, not only data/dialogue.json" % (w, refs))
        conv = self.conv("dlg_main_pallet_oak")
        nodes = {n["id"]: n for n in conv["nodes"]}
        holders = [n["id"] for n in conv["nodes"] for r in n.get("responses") or [] for a in r.get("actions") or []
                   if a.get("transition") == tid] + [n["id"] for n in conv["nodes"]
                                                    for a in n.get("actions_after_acknowledge") or []
                                                    if a.get("transition") == tid]
        other_convs = [c["id"] for c in self.doc("dialogue.json")["conversations"]
                       if c["id"] != conv["id"] and tid in json.dumps(c)]
        if other_convs:
            self.fail("M:referenced_elsewhere", "%s is also used by %s" % (tid, other_convs))
        reach = self.ungated(conv)
        if not holders or set(holders) & reach:
            self.fail("M:before_starter", "%s is run from %s, reachable without the starter-gated edge"
                      % (tid, sorted(set(holders) & reach) or "nowhere"))
        # every sequence of talks: at most one run, none after gym1_cleared
        self.simulate_lock(lock, initial, tid)
        self.ran += 10

    def ungated(self, conv):
        """Nodes reachable from the cursor's initial node without the open_starter_screen response's edge. The cursor
        persists after each node, so a reached node is also an entry; a transition that writes the cursor from a
        reached node adds its value."""
        nodes = {n["id"]: n for n in conv["nodes"]}
        cursor = conv["cursor"]["progression_field"]
        writes = {}
        for _q, t in self.transitions():
            for e in t.get("effects") or []:
                if e.get("kind") == "set_progression" and e.get("field") == cursor:
                    writes.setdefault(t["id"], []).append(e["value"])
        seen, todo = set(), [conv["cursor"]["initial_node"]]
        while todo:
            n = todo.pop()
            if n in seen or n not in nodes:
                continue
            seen.add(n)
            node = nodes[n]
            outs = []
            if node.get("next"):
                outs.append(node["next"])
            for a in node.get("actions_after_acknowledge") or []:
                outs += writes.get(a.get("transition"), [])
            for r in node.get("responses") or []:
                acts = r.get("actions") or []
                if any(a.get("kind") == "open_starter_screen" for a in acts):
                    continue
                if r.get("next"):
                    outs.append(r["next"])
                for a in acts:
                    if a.get("kind") == "set_cursor":
                        outs.append(a["node"])
                    outs += writes.get(a.get("transition"), [])
            todo += outs
        return seen

    def eval_cond(self, c, state):
        k = c.get("kind")
        if k == "progression_equals":
            return state.get(c["field"]) == c["value"]
        if k == "not":
            return not self.eval_cond(c["condition"], state)
        if k == "flag":
            return c["flag"] in state["flags"]
        raise ValueError(k)

    def simulate_lock(self, lock, initial, tid):
        ts = {t["id"]: t for _q, t in self.transitions()
              if any(e.get("field") == lock or e.get("kind") == "rctmod_series" for e in t.get("effects") or [])}
        events = sorted(ts) + ["beat_brock"]
        worst = None
        for n in range(1, 5):
            for seq in itertools.product(events, repeat=n):
                st = {lock: initial, "flags": set()}
                runs, after = 0, 0
                for ev in seq:
                    if ev == "beat_brock":
                        st["flags"].add("gym1_cleared")
                        continue
                    t = ts[ev]
                    try:
                        ok = all(self.eval_cond(c, st) for c in t.get("conditions") or [])
                    except ValueError:
                        ok = True          # an unknown condition is assumed to pass: the worst case
                    if not ok:
                        continue
                    for e in t.get("effects") or []:
                        if e.get("kind") == "set_progression":
                            st[e["field"]] = e["value"]
                        if e.get("kind") == "rctmod_series":
                            runs += 1
                            after += "gym1_cleared" in st["flags"]
                if runs > 1 or after:
                    worst = (seq, runs, after)
                    break
            if worst:
                break
        if worst:
            self.fail("M:sequence", "the talk sequence %s runs the series command %d time(s), %d after gym1_cleared"
                      % (list(worst[0]), worst[1], worst[2]))

    # ================================================================================================ T
    def check_text(self):
        md = (self.root / "docs" / "story" / "CHALLENGE_GYM_DESIGN.md").read_text(encoding="utf-8")
        sec = md.split("## Oak's world-wide choice", 1)[1].split("\n## ", 1)[0]
        quotes = [l[2:].strip() for l in sec.splitlines() if l.startswith("> ")]
        pairs = re.findall(r"- `([^`]+)` → `([^`]+)`", sec)

        def rewrite(s):
            for a, b in DECLARED_REWRITES:
                s = s.replace(a, b)
            return s
        conv = self.conv("dlg_main_pallet_oak")
        nodes = {n["id"]: n for n in conv["nodes"]}
        got = [nodes.get("oak_mode_%03d" % i, {}).get("text") for i in range(1, 6)]
        want = [rewrite(q) for q in quotes[:5]]
        for i, (g, w) in enumerate(zip(got, want), 1):
            if g != w:
                self.fail("T:codex", "oak_mode_%03d is %r; Codex's line with the declared rewrites is %r" % (i, g, w))
        confirms = {"Use Standard rules.": "oak_mode_confirm_standard", "Use Full-Team rules.": "oak_mode_confirm_full"}
        for opt, line in pairs:
            nid = confirms.get(opt)
            if nid and nodes.get(nid, {}).get("text") != rewrite(line):
                self.fail("T:codex", "%s is %r; Codex's line with the declared rewrites is %r"
                          % (nid, nodes.get(nid, {}).get("text"), rewrite(line)))
        texts = [n.get("text") or "" for n in conv["nodes"] if n["id"].startswith("oak_mode")]
        texts += [r.get("text") or "" for n in conv["nodes"] if n["id"].startswith("oak_mode") for r in n.get("responses") or []]
        sf = self.art.trainers.get("data/rctmod/series/%s.json" % self.series_id) or {}
        texts += [text_of(sf.get("title")), text_of(sf.get("description"))]
        for t in texts:
            m = BANNED.search(t)
            if m:
                self.fail("T:easy_hard", "%r says %r" % (t[:80], m.group(0)))
        self.ran += 2

    # ================================================================================================ B
    def mapping(self):
        """{upstream id: data/trainers.json record id} from the gym and League rosters."""
        out = {}
        for f in ("gym_trainers.json", "league_trainers.json"):
            for e in self.doc(f)["trainers"]:
                if e.get("upstream_trainer_id"):
                    out[e["upstream_trainer_id"]] = e["id"]
        return out

    def check_bosses(self):
        T, sfx, sid = self.art.trainers, self.suffix, self.series_id
        kanto = self.kanto
        if len(kanto) != 13:
            self.note("rctmod's kanto series has %d members in %s" % (len(kanto), RCT_ZIP))
        # series file
        if sid is None:
            self.fail("B:series_file", "the trainers pack defines %d series files, not 1"
                      % sum(1 for k in T if k.startswith("data/rctmod/series/")))
            return
        sf = T["data/rctmod/series/%s.json" % sid]
        caps = sorted(set(sf) & {"initialLevelCap", "relativeLevelCap", "requiredSeries"})
        if caps:
            self.fail("B:series_caps", "series %s sets %s: the Challenge cap would not follow Kanto's" % (sid, caps))
        if sf.get("difficulty") != self.up.series_files["kanto"].get("difficulty"):
            self.fail("B:series_rank", "series %s difficulty %r differs from Kanto's %r: the card ranks the modes"
                      % (sid, sf.get("difficulty"), self.up.series_files["kanto"].get("difficulty")))
        # the ids: exactly kanto, suffixed
        made = sorted(k.split("/")[-1][:-5] for k in T if k.startswith("data/rctmod/mobs/trainers/single/")
                      and sid in (T[k].get("series") or []))
        bosses = sorted(m for m in made if m[:-len(sfx)] in kanto)
        want = sorted(u + sfx for u in kanto)
        if bosses != want:
            self.fail("B:ids", "Challenge boss mobs %s; rctmod's kanto series suffixed is %s"
                      % (sorted(set(bosses) ^ set(want)), "13 ids"))
        mapping, recs = self.mapping(), {r["id"]: r for r in self.doc("trainers.json")["trainers"]}
        contract = self.doc("trainers.json")["generation_contract"]["gym_ace_levels"]
        order = chain_order({u: self.up.mobs[u] for u in kanto})
        if order is None:
            self.fail("B:chain", "rctmod's kanto series is not one linear chain in %s: the cap comparison below "
                      "assumes one" % RCT_ZIP)
            return
        cmobs, ctop, ntop = {}, {}, {}
        normal_identity = {}
        for k, u in enumerate(order):
            cid = u + sfx
            mob = T.get("data/rctmod/mobs/trainers/single/%s.json" % cid)
            team = T.get("data/rctmod/trainers/%s.json" % cid)
            nteam = T.get("data/rctmod/trainers/%s.json" % u)
            if not mob or not team or not nteam:
                self.fail("B:files", "%s: mob %s, team %s, Normal override %s" % (cid, bool(mob), bool(team), bool(nteam)))
                continue
            upm = self.up.mobs[u]
            want_req = [[r + sfx for r in g] for g in (upm.get("requiredDefeats") or [])]
            if (mob.get("requiredDefeats") or []) != want_req:
                self.fail("B:chain", "%s requiredDefeats %s; upstream %s's is %s, suffixed %s"
                          % (cid, mob.get("requiredDefeats"), u, upm.get("requiredDefeats"), want_req))
            if mob.get("series") != [sid]:
                self.fail("B:series", "%s series %s, not [%s]" % (cid, mob.get("series"), sid))
            if mob.get("optional"):
                self.fail("B:optional", "%s is optional: it would not enter the cap" % cid)
            extra = {k2: (mob.get(k2), upm.get(k2)) for k2 in set(mob) | set(upm)
                     if k2 not in ("series", "requiredDefeats", "relativeLevelCap") and mob.get(k2) != upm.get(k2)}
            if extra:
                self.fail("B:mob_mirror", "%s differs from upstream %s in %s" % (cid, u, sorted(extra)))
            cmobs[cid] = mob
            ctop[cid] = max(m["level"] for m in team["team"])
            ntop[u] = max(m["level"] for m in nteam["team"])
            # identity: rctmod falls back to the name when a team file has none
            nid = nteam.get("identity") or text_of((nteam.get("name") or {}).get("literal", nteam.get("name")))
            cident = team.get("identity")
            normal_identity[u] = nid
            if not cident or cident == nid:
                self.fail("B:identity", "%s identity %r is not its own (Normal %s is %r): rctmod's uniqueness rule "
                          "refuses one of them within uniqueTrainerRadius" % (cid, cident, u, nid))
            loot = T.get("data/rctmod/loot_table/trainers/single/%s.json" % cid)
            if loot is None or any((p.get("entries") or p.get("rolls")) for p in (loot.get("pools") or [])):
                self.fail("B:loot", "%s loot table is %s, not empty" % (cid, json.dumps(loot)[:80]))
            dlg = T.get("data/rctmod/dialogs/trainers/single/%s.json" % cid) or {}
            for need in ("wrong_series", "on_battle_start"):
                if not dlg.get(need):
                    self.fail("B:dialog", "%s has no %s line" % (cid, need))
            # the contract
            rec = recs.get(mapping.get(u))
            want_ace = contract[k] if k < len(contract) else (rec or {}).get("ace_level")
            if ntop[u] != want_ace:
                self.fail("B:normal_ace", "Normal %s tops out at %s, the contract ace is %s" % (u, ntop[u], want_ace))
        idents = [t.get("identity") for k2, t in T.items() if k2.startswith("data/rctmod/trainers/")
                  and k2.endswith(sfx + ".json") and k2.split("/")[-1][:-len(sfx) - 5] in kanto]
        dup = [i for i, n in Counter(idents).items() if n > 1]
        if dup:
            self.fail("B:identity", "Challenge identities shared: %s" % dup)
        # rctmod's levels and the cap curve, both series
        toml = self.root / "modpack" / "config" / "rctmod-server.toml"
        initial = toml_value(toml, "initialLevelCap")
        cfg_rel = toml_value(toml, "relativeLevelCap") or 0
        k_rel = self.up.series_files["kanto"].get("relativeLevelCap")
        c_rel = sf.get("relativeLevelCap")
        try:
            nlev = {u: trainer_level(u, ntop, {u2: self.up.mobs[u2] for u2 in order}, k_rel, cfg_rel) for u in order}
            clev = {u + sfx: trainer_level(u + sfx, ctop, cmobs, c_rel, cfg_rel) for u in order}
        except KeyError as e:
            self.fail("B:cap", "cannot compute rctmod's level: %s is missing from the chain" % e)
            return
        for u in order:
            if clev[u + sfx] != nlev[u]:
                self.fail("B:cap", "rctmod's level for %s is %d; for %s it is %d: the Challenge cap breaks the curve"
                          % (u + sfx, clev[u + sfx], u, nlev[u]))
        k_init = self.up.series_files["kanto"].get("initialLevelCap")
        ncurve = cap_curve(order, nlev, initial if k_init is None else k_init)
        ccurve = cap_curve([u + sfx for u in order], clev,
                           initial if sf.get("initialLevelCap") is None else sf["initialLevelCap"])
        if ncurve != ccurve:
            self.fail("B:cap_curve", "cap after k defeats: Normal %s, Challenge %s" % (ncurve, ccurve))
        # flags
        flags = self.doc("progression.json")["flags"]
        listed = {}
        for f in flags:
            for lst in ((f.get("set_by") or {}).get("trainer_ids") or {}).values():
                for t in lst:
                    listed.setdefault(t, set()).add(f["id"])
                for t in lst:
                    if t.endswith(sfx) and t[:-len(sfx)] not in lst:
                        self.fail("B:flags", "%s lists %s without its Normal id" % (f["id"], t))
        for u in order:
            if u in listed and listed[u] != listed.get(u + sfx):
                self.fail("B:flags", "%s sets %s; %s sets %s" % (u, sorted(listed[u]), u + sfx,
                                                                   sorted(listed.get(u + sfx, []))))
        gyms_and_champ = [u for u in order if u in listed]
        if len(gyms_and_champ) != 9:
            self.fail("B:flags", "%d of the kanto series set a progression flag, not 9 (eight badges and the "
                      "Champion): %s" % (len(gyms_and_champ), gyms_and_champ))
        # doors: a Challenge win grants upstream's own advancement for the Normal id
        for u in order:
            cid = u + sfx
            adv = T.get("data/cobblers/advancement/trainer/%s.json" % cid) or {}
            crit = [c for c in (adv.get("criteria") or {}).values() if c.get("trigger") == "rctmod:defeat_count"]
            if not crit or crit[0]["conditions"].get("trainer_ids") != [cid]:
                self.fail("B:win", "%s has no defeat_count advancement on its own id" % cid)
                continue
            fn = (adv.get("rewards") or {}).get("function", "")
            body = text_of(T.get("data/%s/function/%s.mcfunction" % tuple(fn.split(":", 1))) or "")
            granted = set(re.findall(r"advancement grant @s only (\S+)", body))
            want = self.up.defeat_advancements.get(u, set())
            if granted != want:
                self.fail("B:doors", "a %s win grants %s; DP-v31's advancements on %s are %s"
                          % (cid, sorted(granted), u, sorted(want)))
        # a later series that needs Kanto completed
        need_kanto = [s for s, f in self.up.series_files.items()
                      if any("kanto" in g for g in (f.get("requiredSeries") or []))]
        if need_kanto:
            self.report("B:later_series", "%s's rctmod series %s require Kanto COMPLETED (requiredSeries); a "
                        "Challenge player completes %s instead. data/progression.json lists them as prestige "
                        "candidates: a Challenge player would be locked out by rctmod unless %s is accepted there"
                        % (RCT_ZIP, need_kanto, sid, sid))
        self.ran += 14

    # ================================================================================================ P
    def check_spawners(self):
        T, sfx = self.art.trainers, self.suffix
        order = chain_order({u: self.up.mobs[u] for u in self.kanto}) or self.kanto
        normal, worlds = {}, {}
        for gid, (leader, lines, settlement) in self.art.gyms.items():
            level = None
            plan = (self.doc("placements.json").get("settlements") or {}).get(settlement) or {}
            for a in (plan.get("plan") or {}).get("anchors") or []:
                if a.get("role") == "gym":
                    level = a.get("level")
            w = Replay(lines, level if level is not None else -999)
            for c, ids in w.spawners():
                for i in ids:
                    normal.setdefault(i, []).append(c)
                    worlds[c] = w
        places = {p["id"]: p for p in self.doc("placements.json")["placements"]}
        for pid, tname in (("gym2_misty_gym", "misty"), ("league_building", "kanto_league")):
            p = places[pid]
            pos = p["position"]
            if p.get("mirror", "none") != "none":
                self.fail("P:template", "%s is mirrored: not modelled" % pid)
                continue
            size, cells = self.up.template(tname)
            level = None
            plan = (self.doc("placements.json").get("settlements") or {}).get(p.get("settlement")) or {}
            for a in (plan.get("plan") or {}).get("anchors") or []:
                if a.get("id") == p.get("lot", pid) or (p.get("kind") == "gym" and a.get("role") == "gym"):
                    level = a.get("level")
            w = TemplateWorld(size, cells, (pos["x"], pos["y"], pos["z"]), p.get("rotation", "none"), level)
            # what the donor placement then fills over the template (tools/place_donor.py `commands`: the policy's
            # substitutions, then the record's own, then remove_blocks to air), read here from the data itself, so the
            # retire's restore is judged against the block the world held when the second spawner replaced it
            # (2026-10-08: Bruno's orange concrete is Moar Concrete as built)
            own = p.get("substitutions") if isinstance(p.get("substitutions"), list) else []
            w.donor_subs = (list(self.doc("spawn_block_policy.json").get("substitutions") or []) + list(own)
                            + [{"from": b, "to": "minecraft:air"} for b in p.get("remove_blocks") or []])
            self.note("P: %s placed from the %s template at %s %s, structure void resolved against lot level %s"
                      % (pid, tname, (pos["x"], pos["y"], pos["z"]), p.get("rotation", "none"), level))
            for c, ids in w.spawners():
                for i in ids:
                    normal.setdefault(i, []).append(c)
                    worlds[c] = w
        # a check on the transform itself: Misty's spawner where gym_interiors measured it
        for g in self.doc("gym_interiors.json")["gyms"]:
            lead = g.get("leader") or {}
            if lead.get("id") == "kanto_misty" and lead.get("expect_spawner_at"):
                if normal.get("kanto_misty") != [tuple(lead["expect_spawner_at"])]:
                    self.fail("P:transform", "the misty template puts kanto_misty at %s; gym_interiors measured %s"
                              % (normal.get("kanto_misty"), lead["expect_spawner_at"]))
        challenge = {}
        for k, v in T.items():
            if not k.endswith(".mcfunction"):
                continue
            for line in lines_of(v):
                m = re.match(r"setblock (-?\d+) (-?\d+) (-?\d+) rctmod:trainer_spawner(\{.*\})", line.strip())
                if m:
                    for i in spawner_ids(m.group(4)):
                        challenge.setdefault(i, []).append((tuple(int(x) for x in m.groups()[:3]), k))
                        if not i.endswith(sfx):
                            normal.setdefault(i, []).append(tuple(int(x) for x in m.groups()[:3]))
        cycle = lines_of(T.get("data/cobblers/function/trainers/challenge/cycle.mcfunction") or [])
        tick = text_of(T.get("data/cobblers/function/trainers/tick.mcfunction") or "")
        if "function cobblers:trainers/challenge/cycle" not in tick:
            self.fail("P:cycle_runs", "the trainers tick never runs cobblers:trainers/challenge/cycle")
        single = self.rollout
        for u in order:
            cid = u + sfx
            ns, cs = normal.get(u, []), challenge.get(cid, [])
            if u in single:
                self.check_single_leader(u, cid, ns, cs, worlds, cycle)
                continue
            if len(ns) != 1 or len(cs) != 1:
                self.fail("P:count", "%s: %d Normal spawner(s), %s: %d Challenge spawner(s)" % (u, len(ns), cid, len(cs)))
                if not ns or not cs:
                    continue
            n, (c, path) = ns[0], cs[0]
            both = [i for i, cl in challenge.items() if i != cid and any(x[0] == c for x in cl)]
            if both:
                self.fail("P:count", "the spawner at %s also carries %s" % (c, both))
            fn = lines_of(T[path])
            if "setblock %d %d %d minecraft:redstone_block" % (c[0], c[1] - 1, c[2]) not in [l.strip() for l in fn]:
                self.fail("P:powered", "%s's spawner at %s is not powered from below by its place function" % (cid, c))
            w = worlds.get(n)
            floor, below = w.at(c), w.at((c[0], c[1] - 1, c[2]))
            above = [w.at((c[0], c[1] + 1, c[2])), w.at((c[0], c[1] + 2, c[2]))]
            if not solid_floor(floor) or has_part(floor, CONTAINER_PARTS + REDSTONE_SENSITIVE_PARTS + INTERACTIVE_PARTS):
                self.fail("P:floor", "%s at %s replaces %s, not a plain floor block" % (cid, c, floor))
            # exactly minecraft:air: that is what the self-placing line tests (`if block ... minecraft:air`), so a
            # light block, seagrass or water there means the spawner is never set at all
            if not all(bname(a) == "minecraft:air" for a in above):
                self.fail("P:headroom", "%s at %s has %s over it, not two minecraft:air: the self-placing line never "
                          "fires and this leader never spawns" % (cid, c, above))
            if below is None or has_part(below, CONTAINER_PARTS + REDSTONE_SENSITIVE_PARTS + INTERACTIVE_PARTS) \
                    or bname(below) in FLUIDS:
                self.fail("P:below", "%s's redstone block at y%d replaces %s" % (cid, c[1] - 1, below))
            elif is_air(below):
                self.report("P:hanging", "%s's redstone block at %s replaces air: it hangs under the floor, visible "
                            "from below" % (cid, (c[0], c[1] - 1, c[2])))
            for d in ((1, 0, 0), (-1, 0, 0), (0, 0, 1), (0, 0, -1), (0, -1, 0)):
                nb = (c[0] + d[0], c[1] - 1 + d[1], c[2] + d[2])
                st = w.at(nb)
                if st is not None and has_part(st, REDSTONE_SENSITIVE_PARTS):
                    self.fail("P:powers", "%s's redstone block at %s powers %s at %s"
                              % (cid, (c[0], c[1] - 1, c[2]), st, nb))
            # the same floor, a straight open line from the Normal leader
            if n[1] != c[1] or (n[0] != c[0] and n[2] != c[2]):
                self.fail("P:room", "%s at %s is not on the same floor in a straight line from %s at %s"
                          % (cid, c, u, n))
            else:
                ax = 0 if n[0] != c[0] else 2
                lo, hi = sorted((n[ax], c[ax]))
                for v in range(lo + 1, hi):
                    cell = list(c)
                    cell[ax] = v
                    f, h1, h2 = w.at(tuple(cell)), w.at((cell[0], cell[1] + 1, cell[2])), w.at((cell[0], cell[1] + 2, cell[2]))
                    if not solid_floor(f) or not passable(h1) or not passable(h2):
                        self.fail("P:room", "between %s and %s the cell %s is %s / %s / %s: not one open floor"
                                  % (u, cid, tuple(cell), f, h1, h2))
                        break
            # the self-placing line names this cell and checks its headroom
            want = ["if loaded %d %d %d" % c, "unless block %d %d %d %s" % (c[0], c[1], c[2], SPAWNER),
                    "if block %d %d %d minecraft:air" % (c[0], c[1] + 1, c[2]),
                    "if block %d %d %d minecraft:air" % (c[0], c[1] + 2, c[2]),
                    "run function cobblers:trainers/challenge/place_%s" % cid]
            lines = [l for l in cycle if l.endswith("place_%s" % cid)]
            if len(lines) != 1 or not all(x in lines[0] for x in want):
                self.fail("P:cycle", "%s's self-placing line does not check %s exactly: %s"
                          % (cid, c, lines[0][:200] if lines else "missing"))
        self.ran += 9

    # ---- P1: a boss that stands as ONE leader (the owner, 2026-10-07; data/challenge_mode.json single_leader)
    @functools.cached_property
    def rollout(self):
        """The bosses data/challenge_mode.json names in single_leader.rollout (a list, or "all"). Read from the data,
        not from tools/challenge_mode.py rollout()."""
        r = (self.cm.get("single_leader") or {}).get("rollout") or []
        return set(self.cm["bosses"]) if r == "all" else set(r)

    @staticmethod
    def retire_path(cid):
        return "data/cobblers/function/trainers/challenge/retire_%s.mcfunction" % cid

    def check_single_leader(self, u, cid, ns, cs, worlds, cycle):
        """The one-leader rule for boss `u`, judged from the generated text run through CommandWorld:

          P1:count    exactly one spawner carries the Normal id; none carries the Challenge id; no place function
                      or place line for a second spawner
          P1:swap     the cycle's lines for this boss, run over every mix of nearby players from either id, in and
                      out of battle, toward and away from the retired cell: in a battle nothing changes (block or
                      trainer); otherwise the spawner AND the trainer end on the Challenge id exactly when the nearest
                      player within rctmod's forceBattleMaxDistance (modpack/config/rctmod-server.toml: the farthest
                      a battle starts on sight) carries the mode tag, and on the Normal id when nobody is within it
                      plus 16. Between those two distances either answer is allowed: that is the generator's reach
          P1:swap_at  every `data merge block` naming either id targets the one spawner
          P1:retire*  the retire function writes only the retired cell (data/challenge_mode.json bosses.<u>.spawner.at,
                      where the earlier build set the second spawner) and the cell under it, back to what the gym's
                      own replayed build has there (tools/gym_buildings.py's emitted text, or the template); a world
                      without the second spawner, or with something else in that cell, is left alone; the old
                      Challenge trainer standing on the retired cell is gone afterwards, whether or not the cycle ran
                      first (R17L forceloads and waits before the retire); a trainer in a battle is never killed; and
                      the one leader is never killed while a player stands where a battle with it can start
          P1:stale    nothing else in the generated packs still anchors at the retired cell
          P1:wired    tools/reapply.py has step R17L and it runs this retire function (and a moved boss's move
                      function after it)
          P1:retire_renames  with a Challenge player where a battle with the leader can start, R17L leaves the
                      leader's id and its spawner as they were (a battle could start on the wrong team before the
                      next cycle)
          P1:move*    a boss with single_leader.move (data/challenge_mode.json; the swap then follows move.to):
                      move.from is the build's one spawner; the new cell is a floor of the build with two passable
                      cells over it and its redstone block touches nothing redstone-sensitive (P1:move_to); the move
                      writes only the new cell (the Normal spawner), the one under it (what the build has under its own
                      spawner) and the old cell (what the build has on all four sides: P1:move_restore) (P1:move_at);
                      the record's to_replaces/from_restore match the build (P1:move_record); after R17L with nobody
                      near the spawner stands moved (P1:move), never moved under a battle (P1:move_battle), a re-run
                      changes nothing (P1:move_rerun); and every trainer of either id left standing is one the swap
                      still drives (P1:move_orphan: rctmod spawns no second trainer of an identity while one stands),
                      after a first run, a held run then a re-run, and on a world without the second spawner
          REPORT P1:inbattle_assumed   what the swap does if rctmod does not save InBattle as a 0b/1b byte (ASSUMED,
                      docs/research/notes/rct-arena-capabilities.md:59 documents the tag, not its form)

        NOT modelled: rctmod. A spawner never spawns or despawns here, a TrainerId merge notifies no spawner, and a
        spawner whose TrainerIds no longer match its trainer does nothing; those are experiment E7 and the staging
        proof (docs/mechanics/ONE_LEADER_SWAP.md)."""
        T = self.art.trainers
        tag = self.cm["mode"]["tag"]
        if len(ns) != 1 or cs:
            self.fail("P1:count", "%s stands as one leader: %d spawner(s) carry %s and %d carry %s, want 1 and 0"
                      % (cid, len(ns), u, len(cs), cid))
            if len(ns) != 1:
                return
        place = "data/cobblers/function/trainers/challenge/place_%s.mcfunction" % cid
        if place in T or any(l.strip().endswith("place_%s" % cid) for l in cycle):
            self.fail("P1:count", "%s stands as one leader but its second spawner is still placed (%s)" % (cid, place))
        n = ns[0]
        # A boss whose ONE spawner moves (data/challenge_mode.json bosses.<u>.single_leader.move, the owner's
        # 2026-10-09 decision for Lance): the build has it at n0 (move.from must be that cell, read from the replayed
        # build, not from the generator), and after R17L it stands at move.to, which the swap must then follow.
        mv = ((self.cm["bosses"][u].get("single_leader") or {}).get("move")) or None
        n0 = n
        if mv:
            if tuple(mv.get("from") or ()) != n0 or not mv.get("to"):
                self.fail("P1:move", "%s: single_leader.move.from %s is not the build's one spawner %s (or no move.to)"
                          % (u, mv.get("from"), n0))
                return
            n = tuple(mv["to"])
        n0d = (n0[0], n0[1] - 1, n0[2])
        nd = (n[0], n[1] - 1, n[2])
        c = tuple(self.cm["bosses"][u]["spawner"]["at"])
        cd = (c[0], c[1] - 1, c[2])
        fb = toml_value(self.root / "modpack" / "config" / "rctmod-server.toml", "forceBattleMaxDistance")
        try:
            fb = float(fb)
        except (TypeError, ValueError):
            self.fail("P1:swap", "modpack/config/rctmod-server.toml has no forceBattleMaxDistance (%r)" % (fb,))
            return
        sp = lambda i: '%s{TrainerIds:["%s"]}' % (SPAWNER, i)
        stand = lambda cell: (cell[0] + 0.5, cell[1] + 1.0, cell[2] + 0.5)
        dx, dz = n[0] - c[0], n[2] - c[2]
        ln = (dx * dx + dz * dz) ** 0.5 or 1.0
        away = (dx / ln, 0.0, dz / ln) if (dx or dz) else (1.0, 0.0, 0.0)
        at = lambda d, sgn=1: tuple(stand(n)[i] + sgn * away[i] * d for i in range(3))
        ids_re = r'\{TrainerId:"(%s|%s)"\}$' % (re.escape(u), re.escape(cid))
        mine = [l.strip() for l in cycle if l.strip().startswith("execute")
                and ("run data merge block %d %d %d " % n in l or re.search(r"run data merge entity .*" + ids_re, l.strip()))]
        for k, v in T.items():
            if k.endswith(".mcfunction"):
                for line in lines_of(v):
                    m = re.search(r"data merge block (-?\d+) (-?\d+) (-?\d+) \{TrainerIds:(\[[^\]]*\])\}", line)
                    if m and set(spawner_ids("TrainerIds:" + m.group(4))) & {u, cid} \
                            and tuple(int(x) for x in m.groups()[:3]) != n:
                        self.fail("P1:swap_at", "%s merges a spawner at %s, not %s's one spawner %s"
                                  % (k, m.groups()[:3], u, n))
        if not mine:
            self.fail("P1:swap", "%s stands as one leader but the cycle has no swap lines for its spawner %s" % (u, n))
            return

        def run(cw, lines, times=1):
            for _ in range(times):
                for line in lines:
                    cw.run(line)
            return cw

        inside, far = fb - 0.5, fb + 16
        crowds = [[], [(inside, True)], [(inside, False)], [(1.0, True), (inside, False)], [(1.0, False), (inside, True)],
                  [(far, True)], [(far, False), (far, True)], [(inside, True), (far, False)]]
        try:
            bad = None
            for sgn, start, battle, crowd in itertools.product((1, -1), (u, cid), (False, True), crowds):
                players = [{"pos": at(d, sgn), "tags": {tag} if t else set()} for d, t in crowd]
                cw = run(CommandWorld({n: sp(start), nd: "minecraft:redstone_block"},
                                      [{"id": start, "battle": battle, "pos": stand(n)}], players), mine)
                near = sorted((d, t) for d, t in crowd if d <= fb)
                want = start if battle else (cid if near and near[0][1] else u)
                got = (spawner_ids(cw.blocks.get(n)), [t["id"] for t in cw.trainers])
                if got != ([want], [want]):
                    bad = "from %s, in battle %s, players %s (%s the retired cell): spawner %s, trainer %s, expected %s" % (
                        start, battle, crowd, "away from" if sgn > 0 else "toward", got[0], got[1], want)
                    break
            if bad:
                self.fail("P1:swap", "%s: %s" % (u, bad))
            # the battle guard rests on InBattle's form, which is ASSUMED: say what happens without it
            blind = []
            for battle in (False, True):
                cw = run(CommandWorld({n: sp(u), nd: "minecraft:redstone_block"},
                                      [{"id": u, "battle": battle, "pos": stand(n)}],
                                      [{"pos": at(inside), "tags": {tag}}], inbattle=False), mine)
                blind.append((spawner_ids(cw.blocks.get(n)), [t["id"] for t in cw.trainers]))
            if blind != [([cid], [cid]), ([u], [u])]:
                self.report("P1:inbattle_assumed", "%s: if rctmod does not save InBattle as a 0b/1b byte, a Challenge "
                            "player within %g leaves the spawner on %s and the trainer on %s out of battle, and the "
                            "spawner on %s during a battle. A trainer left on %s refuses that player (wrong_series) for "
                            "as long as it lasts: Challenge mode cannot pass %s. Proof: ONE_LEADER_SWAP.md a-steps"
                            % (u, inside, blind[0][0], blind[0][1], blind[1][0], u, u))
        except ValueError as e:
            self.fail("P1:model", "%s's swap lines are not ones this audit can run: %s" % (u, e))
            return

        # the retire
        rp = self.retire_path(cid)
        rn = "%s (%s)" % (cid, rp)
        if rp not in T:
            self.fail("P1:retire", "%s stands as one leader but nothing retires its second spawner at %s (%s)" % (cid, c, rp))
            return
        rl = [l.strip() for l in lines_of(T[rp]) if l.strip() and not l.strip().startswith("#")]
        w = worlds.get(n0)

        def built(cell):
            """The gym's own replayed build at `cell`, after place_donor's fills (a template placement), in order."""
            st = w.at(cell) if w is not None else None
            for s in getattr(w, "donor_subs", ()):
                st = s["to"] if st is not None and bname(st) == s["from"] else st
            return st
        floor, under = built(c), built(cd)
        if floor is None or under is None:
            self.fail("P1:retire", "%s: no replayed build holds %s and %s, so the restore cannot be judged" % (cid, c, cd))
            return
        for line in rl:
            m = re.search(r"run (setblock|fill) (-?\d+) (-?\d+) (-?\d+) (\S+)", line)
            if not m:
                continue
            cell = tuple(int(x) for x in m.groups()[1:4])
            if m.group(1) == "fill" or cell not in (c, cd):
                self.fail("P1:retire_at", "%s writes %s at %s, not only the retired cell %s and the one under it"
                          % (rn, m.group(1), cell, c))
            elif m.group(5) != (floor if cell == c else under):
                self.fail("P1:restore", "%s sets %s at %s; the gym's own build has %s there"
                          % (rn, m.group(5), cell, floor if cell == c else under))
        # The move (a moved boss only): R17L runs the retire, then cobblers:trainers/challenge/move_<u>. Every block it
        # may write is judged against the build, never against the record or the generator: the new cell must be a
        # floor of the build with two passable cells over it, the block under it what the build has under its own one
        # spawner (the template's spawners each sit on a redstone block), and the old cell what the build has on all
        # four sides of it.
        ml, mpath, restore0, under0, to_floor, to_under = [], None, None, None, None, None
        if mv:
            mpath = "data/cobblers/function/trainers/challenge/move_%s.mcfunction" % u
            if mpath not in T:
                self.fail("P1:move", "%s's spawner moves to %s (single_leader.move) but nothing moves it (%s)" % (u, n, mpath))
                return
            ml = [l.strip() for l in lines_of(T[mpath]) if l.strip() and not l.strip().startswith("#")]
            sides = [built((n0[0] + a, n0[1], n0[2] + b)) for a, b in ((1, 0), (-1, 0), (0, 1), (0, -1))]
            restore0 = sides[0] if sides[0] is not None and len(set(sides)) == 1 else None
            under0, to_floor, to_under = built(n0d), built(n), built(nd)
            if restore0 is None:
                self.fail("P1:move", "%s: the build's four sides of the old cell %s disagree (%s): the restore cannot be "
                          "judged" % (u, n0, sides))
                return
            over = [built((n[0], n[1] + i, n[2])) for i in (1, 2)]
            if (not solid_floor(to_floor) or bname(to_floor) == SPAWNER or has_part(to_floor, CONTAINER_PARTS)
                    or not all(passable(s) for s in over)):
                self.fail("P1:move_to", "%s: the new cell %s holds %s with %s over it in the build: not a floor a "
                          "trainer stands on" % (u, n, to_floor, over))
            for a, b, h in ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, -1)):
                nb = (nd[0] + a, nd[1] + h, nd[2] + b)
                if has_part(built(nb), REDSTONE_SENSITIVE_PARTS) or bname(built(nb)) == SPAWNER:
                    self.fail("P1:move_to", "%s: the redstone block under %s would touch %s at %s" % (u, n, built(nb), nb))
            want_at = {n: sp(u), nd: under0, n0: restore0}
            for line in ml:
                mm = re.search(r"run (setblock|fill) (-?\d+) (-?\d+) (-?\d+) (\S+)", line)
                if not mm:
                    continue
                cell = tuple(int(x) for x in mm.groups()[1:4])
                if mm.group(1) == "fill" or cell not in want_at:
                    self.fail("P1:move_at", "%s writes %s at %s, not only the new cell %s, the one under it and the "
                              "old cell %s" % (mpath, mm.group(1), cell, n, n0))
                elif mm.group(5) != want_at[cell]:
                    self.fail("P1:move_restore" if cell == n0 else "P1:move_at", "%s sets %s at %s; want %s (the "
                              "build's %s)" % (mpath, mm.group(5), cell, want_at[cell],
                                               "four sides of the old cell" if cell == n0 else
                                               "block under its own spawner" if cell == nd else "spawner, moved"))
            # the record tells the truth about what the move replaces (a data check, from the build)
            rep = mv.get("to_replaces") or {}
            if (bname(rep.get("floor")), bname(rep.get("under"))) != (bname(to_floor), bname(to_under)) \
                    or mv.get("from_restore") != restore0:
                self.fail("P1:move_record", "%s: single_leader.move records to_replaces %s and from_restore %s; the "
                          "build has %s over %s at %s and %s around %s" % (u, rep, mv.get("from_restore"), to_floor,
                                                                           to_under, n, restore0, n0))
        r17 = rl + ml   # R17L: the retire, then the move (tools/challenge_mode.py retire_functions(), checked below)
        seat_now = {n0: sp(u), n0d: under0 or "minecraft:redstone_block"}
        if mv:
            seat_now.update({n: to_floor, nd: to_under})
        old_world = dict(seat_now)
        old_world.update({c: sp(cid), cd: "minecraft:redstone_block"})

        def moved_wrong(cw):
            """None when the one spawner stands moved: move.to the Normal spawner over the build's under-spawner
            block, the old cell the build's floor (else a description)."""
            got = (cw.blocks.get(n), cw.blocks.get(nd), cw.blocks.get(n0))
            if spawner_ids(got[0]) != [u] or bname(got[0]) != SPAWNER or got[1:] != (under0, restore0):
                return "%s holds %s over %s and the old cell %s holds %s; want %s over %s and %s" % (
                    n, got[0], got[1], n0, got[2], sp(u), under0, restore0)
            return None

        def ungoverned(cw):
            """After R17L, every standing trainer of either id must be one the swap still drives (rctmod spawns no
            second trainer of an identity while one stands, uniqueTrainerRadius 151, so one the swap cannot reach is
            THE leader for good): a Challenge player near the one spawner must turn it to the Challenge id and, gone,
            back. Returns the trainers it does not drive."""
            out = []
            for players, want in (([{"pos": at(inside), "tags": {tag}}], cid), ([], u)):
                cw2 = CommandWorld(cw.blocks, [dict(t, battle=False) for t in cw.trainers if t["id"] in (u, cid)],
                                   players)
                run(cw2, mine, 3)
                out += ["%s at %s stays %s (want %s)" % (t.get("who", "a trainer"), t["pos"], t["id"], want)
                        for t in cw2.trainers if t["id"] != want]
            return out
        try:
            # R17L forceloads and waits 3 s before the retire; the trainers clock runs the cycle every 10 ticks, so
            # the cycle has run anywhere from 0 to 6 times first
            for k in range(0, 7):
                for leader_battle in (False, True):
                    cw = CommandWorld(old_world, [{"id": u, "battle": leader_battle, "pos": stand(n0), "who": "leader"},
                                                  {"id": cid, "battle": False, "pos": stand(c), "who": "old"}], [])
                    run(cw, mine, k)
                    run(cw, r17)
                    left = [(t["who"], t["id"]) for t in cw.trainers]
                    if (cw.blocks.get(c), cw.blocks.get(cd)) != (floor, under):
                        self.fail("P1:retire", "%s after the cycle ran %d time(s): %s holds %s over %s, want %s over %s"
                                  % (cid, k, c, cw.blocks.get(c), cw.blocks.get(cd), floor, under))
                        break
                    # a moved boss's idle leader may go with the retire (the moved spawner then spawns him at the new
                    # cell); a leader in a battle never goes, and the old Challenge trainer always does
                    want_left = [[("leader", u)]] if (leader_battle or not mv) else [[("leader", u)], []]
                    if left not in want_left:
                        self.fail("P1:retire", "%s with nobody near, the leader %s, after the cycle ran %d time(s) "
                                  "first (R17L forceloads and waits before the retire): trainers left %s, want only "
                                  "the leader on %s" % (cid, "in a battle" if leader_battle else "idle", k, left, u))
                        break
                    if not mv:
                        continue
                    if leader_battle:
                        # never moved under a battle; and once the battle is over the next re-apply's R17L moves it
                        if (cw.blocks.get(n0), cw.blocks.get(n)) != (sp(u), to_floor):
                            self.fail("P1:move_battle", "%s's spawner moves while %s is in a battle by it: %s now holds "
                                      "%s, %s holds %s" % (u, u, n0, cw.blocks.get(n0), n, cw.blocks.get(n)))
                            break
                        for t in cw.trainers:
                            t["battle"] = False
                        run(cw, r17)
                    bad = moved_wrong(cw)
                    if bad:
                        self.fail("P1:move", "%s after R17L with nobody near (the leader %s, cycle %d time(s) first): %s"
                                  % (u, "in a battle, then a re-run" if leader_battle else "idle", k, bad))
                        break
                    bad = ungoverned(cw)
                    if bad:
                        self.fail("P1:move_orphan", "%s after R17L (the leader %s first, cycle %d time(s)): %s -- the "
                                  "spawner moved to %s and left a trainer the swap cannot reach"
                                  % (u, "in a battle, then a re-run" if leader_battle else "idle", k, "; ".join(bad), n))
                        break
                    # a re-run of the completed R17L (every re-apply runs it) changes nothing, the new leader included
                    cw.trainers.append({"id": u, "battle": False, "pos": stand(n), "who": "new leader"})
                    snap = (dict(cw.blocks), [(t["who"], t["id"]) for t in cw.trainers])
                    run(cw, r17)
                    if (dict(cw.blocks), [(t["who"], t["id"]) for t in cw.trainers]) != snap:
                        self.fail("P1:move_rerun", "%s: R17L run again after the move changes the world: %s -> %s"
                                  % (u, snap[1], [(t["who"], t["id"]) for t in cw.trainers]))
                        break
                else:
                    continue
                break
            # the one leader already gone (despawned): at most one trainer may be left, and none on the Challenge id
            for k in range(0, 7):
                cw = CommandWorld(old_world, [{"id": cid, "battle": False, "pos": stand(c), "who": "old"}], [])
                run(cw, mine, k)
                run(cw, r17)
                ids = [t["id"] for t in cw.trainers]
                if len(ids) > 1 or cid in ids:
                    self.fail("P1:retire", "%s with only the old trainer standing, after the cycle ran %d time(s): "
                              "trainers left %s" % (cid, k, ids))
                    break
                if mv and (moved_wrong(cw) or ungoverned(cw)):
                    self.fail("P1:move_orphan" if not moved_wrong(cw) else "P1:move",
                              "%s with only the old trainer standing: %s" % (u, moved_wrong(cw) or ungoverned(cw)))
                    break
            # a world without the second spawner (a fresh export; or something else in that cell): the retire changes
            # nothing; a moved boss's spawner still moves, and the trainer its old spawner already spawned must not be
            # left where the swap cannot reach it
            for state, below in ((floor, under), ("minecraft:chest", "minecraft:stone")):
                fresh = dict(seat_now)
                fresh.update({c: state, cd: below})
                cw = run(CommandWorld(fresh, [{"id": u, "battle": False, "pos": stand(n0), "who": "leader"}], []), r17)
                if (cw.blocks.get(c), cw.blocks.get(cd)) != (state, below) or len(cw.trainers) > 1 \
                        or (not mv and len(cw.trainers) != 1):
                    self.fail("P1:retire_at", "%s changes a world whose %s holds %s over %s: now %s over %s, %d trainer(s)"
                              % (rn, c, state, below, cw.blocks.get(c), cw.blocks.get(cd), len(cw.trainers)))
                elif mv and moved_wrong(cw):
                    self.fail("P1:move", "%s in a world without the second spawner: %s" % (u, moved_wrong(cw)))
                elif mv and ungoverned(cw):
                    self.fail("P1:move_orphan", "%s in a world without the second spawner (%s over %s at %s), its "
                              "leader standing by the old cell: %s -- the spawner moved to %s and left a trainer the "
                              "swap cannot reach" % (u, state, below, c, "; ".join(ungoverned(cw)), n))
            # the one leader is never killed, renamed or re-spawnered while a Challenge player stands where a battle
            # with it can start: on a re-run (the second spawner already gone) and on the first run (it still stands),
            # cycle 0..6 times first (P1:rerun_kills for a re-run, every re-apply runs R17L; P1:retire_kills for the
            # first run; P1:retire_renames for a leader left standing with its id or its spawner changed under the
            # player). Measured from where the leader stands before R17L (the old cell for a moved boss).
            ax, az = n0[0] - c[0], n0[2] - c[2]
            al = (ax * ax + az * az) ** 0.5
            away0 = (ax / al, 0.0, az / al) if al else away
            at0 = lambda d, sgn: tuple(stand(n0)[i] + sgn * away0[i] * d for i in range(3))
            for first in (False, True):
                for sgn, k in itertools.product((1, -1), range(0, 7)):
                    blocks = dict(old_world) if first else dict(seat_now)
                    if not first:
                        blocks.update({c: floor, cd: under})
                    trainers = [{"id": u, "battle": False, "pos": stand(n0), "who": "leader"}]
                    if first:
                        trainers.append({"id": cid, "battle": False, "pos": stand(c), "who": "old"})
                    cw = CommandWorld(blocks, trainers, [{"pos": at0(inside, sgn), "tags": {tag}}])
                    run(cw, mine, k)
                    snap = ([t["id"] for t in cw.trainers if t["who"] == "leader"], cw.blocks.get(n0), cw.blocks.get(n))
                    run(cw, r17)
                    if not any(t["who"] == "leader" for t in cw.trainers):
                        self.fail("P1:retire_kills" if first else "P1:rerun_kills",
                                  "%s, %s, after the cycle ran %d time(s), kills the one leader while a Challenge "
                                  "player stands %g from %s's spawner %s the retired cell (within %g, where a battle "
                                  "starts on sight): the guard is anchored at %s, %.1f from the spawner the swap "
                                  "follows" % (rn, "on its first run" if first else "run again", k, inside, u,
                                               "away from" if sgn > 0 else "toward", fb, c, ln))
                        break
                    now = ([t["id"] for t in cw.trainers if t["who"] == "leader"], cw.blocks.get(n0), cw.blocks.get(n))
                    if now != snap:
                        self.fail("P1:retire_renames",
                                  "%s, %s, after the cycle ran %d time(s), changes the one leader (id, spawner %s, %s) "
                                  "from %s to %s while a Challenge player stands %g from it %s the retired cell "
                                  "(within %g, where a battle starts on sight): a battle can start before the next "
                                  "cycle puts it back" % (rn, "on its first run" if first else "run again", k, n0, n,
                                                          snap, now, inside, "away from" if sgn > 0 else "toward", fb))
                        break
            cw = run(CommandWorld(old_world, [{"id": u, "battle": False, "pos": stand(n0)},
                                              {"id": cid, "battle": True, "pos": stand(c)}], []), r17)
            if not any(t["id"] == cid and t["battle"] for t in cw.trainers):
                self.fail("P1:retire_battle", "%s kills a trainer that is in a battle" % rn)
        except ValueError as e:
            self.fail("P1:model", "%s is not a function this audit can run: %s" % (rn, e))
        # nothing else still anchors at the retired cell
        anchors = ("x=%d.5,y=%d,z=%d.5" % c, "%d %d %d" % c)
        for k, v in T.items():
            if k.endswith(".mcfunction") and k != rp:
                for line in lines_of(v):
                    if not line.strip().startswith("#") and any(a in line for a in anchors):
                        self.fail("P1:stale", "%s still names the retired cell %s: %s" % (k, c, line.strip()[:140]))
                        break
        # a moved boss: nothing but its move function still names the old cell (the cycle follows move.to)
        if mv:
            anchors0 = ("x=%d.5,y=%d,z=%d.5" % n0, "%d %d %d" % n0)
            for k, v in T.items():
                if k.endswith(".mcfunction") and k != mpath:
                    for line in lines_of(v):
                        if not line.strip().startswith("#") and any(a in line for a in anchors0):
                            self.fail("P1:stale", "%s still names %s's old cell %s: %s" % (k, u, n0, line.strip()[:140]))
                            break
        # the re-apply step that runs it
        ra = self.root / "tools" / "reapply.py"
        src = ra.read_text(encoding="utf-8", errors="replace") if ra.exists() else ""
        fid = "cobblers:trainers/challenge/retire_%s" % cid
        try:
            fns = list(self.art.mod("challenge_mode").retire_functions())
        except Exception as e:  # noqa: BLE001 - a generator that cannot list its own retire functions is the finding
            fns = []
            self.note("P1: challenge_mode.retire_functions() raised %s" % e)
        listed = fid in fns
        if '"R17L"' not in src or "retire_functions()" not in src or not listed:
            self.fail("P1:wired", "tools/reapply.py step R17L does not run %s" % fid)
        if mv:
            # R17L runs the move AFTER the retire: the retire's kills are what clear the old cell's trainer (above)
            mfid = "cobblers:trainers/challenge/move_%s" % u
            if mfid not in fns or not listed or fns.index(mfid) < fns.index(fid):
                self.fail("P1:wired", "tools/reapply.py step R17L does not run %s after %s (%s)" % (mfid, fid, fns))

    # ================================================================================================ R
    def check_routes(self):
        T, sfx, sid = self.art.trainers, self.suffix, self.series_id
        recs, seats = self.art.seats
        challenge_cycle = lines_of(T.get("data/cobblers/function/trainers/challenge/cycle.mcfunction") or [])
        normal_cycle = lines_of(T.get("data/cobblers/function/trainers/cycle.mcfunction") or [])
        # ONE exception: a one-leader boss's retire function may kill, in exactly these two shapes, only while the
        # second spawner still stands at the retired cell, only with no player near that cell, never in a battle:
        # the Challenge-id trainers there, and the Normal-id trainers there that do not carry the keep tag. Whether
        # those kills are SAFE is P1's (check_single_leader runs them); here they are only excused.
        exempt = {}
        for u in self.rollout:
            cid = u + sfx
            c = tuple((self.cm["bosses"].get(u) or {}).get("spawner", {}).get("at") or ())
            if len(c) == 3:
                head = (r'execute if block %d %d %d %s\{TrainerIds:\["%s"\]\} positioned %d\.5 %d %d\.5 unless entity '
                        r'@a\[distance=\.\.[0-9.]+\] run kill @e\[type=rctmod:trainer,distance=\.\.[0-9.]+,'
                        % (c[0], c[1], c[2], re.escape(SPAWNER), re.escape(cid), c[0], c[1], c[2]))
                exempt[self.retire_path(cid)] = [
                    re.compile(head + r'nbt=\{TrainerId:"%s",InBattle:0b\}\]' % re.escape(cid)),
                    re.compile(head + r'nbt=\{TrainerId:"%s",InBattle:0b\},tag=!cobblers_keep_leader\]' % re.escape(u))]
        for k, v in T.items():
            if k.endswith(".mcfunction"):
                for line in lines_of(v):
                    if any(rx.fullmatch(line.strip()) for rx in exempt.get(k, ())):
                        continue
                    if re.search(r"rctmod trainer summon|summon rctmod:trainer|kill @e\[type=rctmod:trainer", line):
                        self.fail("R:summon", "%s summons or kills a trainer: %s" % (k, line[:120]))
        tag = self.cm["mode"]["tag"]
        oak_tags = re.findall(r"run tag @s add ([a-z0-9_]+)", text_of(self.art.dialogue.get(
            "data/cobblers/dialogues/dlg_main_pallet_oak.json") or ""))
        if tag not in oak_tags:
            self.fail("R:tag", "the swap reads tag %s; Oak's compiled choice adds %s" % (tag, oak_tags))
        checked = 0
        for s in seats:
            tid = s["id"]
            r = recs.get(tid)
            m = ((r or {}).get("modes") or {}).get("challenge") or {}
            if not (m.get("rct") or {}).get("team"):
                if "data/rctmod/mobs/trainers/single/%s%s.json" % (tid, sfx) in T:
                    self.fail("R:copy", "%s has a Challenge copy but its record has no Challenge team" % tid)
                continue
            cid = tid + sfx
            nm = T.get("data/rctmod/mobs/trainers/single/%s.json" % tid)
            cm = T.get("data/rctmod/mobs/trainers/single/%s.json" % cid)
            if not nm or not cm:
                self.fail("R:copy", "%s: Normal mob %s, Challenge mob %s" % (tid, bool(nm), bool(cm)))
                continue
            diff = sorted(k for k in set(nm) | set(cm) if k != "series" and nm.get(k) != cm.get(k))
            if diff or cm.get("series") != [sid] or nm.get("series"):
                self.fail("R:mob", "%s's copy differs from the Normal mob in %s (series %s / %s)"
                          % (cid, diff, nm.get("series"), cm.get("series")))
            if not cm.get("optional") or cm.get("requiredDefeats"):
                self.fail("R:cap", "%s is not optional with no requiredDefeats: it would enter the cap" % cid)
            team = T.get("data/rctmod/trainers/%s.json" % cid) or {}
            want = [(p["species"], p["level"]) for p in m["rct"]["team"]]
            if [(p.get("species"), p.get("level")) for p in team.get("team") or []] != want:
                self.fail("R:team", "%s's team is not the record's Challenge team" % cid)
            if T.get("data/rctmod/dialogs/trainers/single/%s.json" % cid) != T.get("data/rctmod/dialogs/trainers/single/%s.json" % tid):
                self.fail("R:lines", "%s does not speak %s's lines" % (cid, tid))
            adv = T.get("data/cobblers/advancement/trainer/%s.json" % tid) or {}
            ids = [c["conditions"].get("trainer_ids") for c in (adv.get("criteria") or {}).values()]
            if ids != [[tid, cid]]:
                self.fail("R:advancement", "%s's defeat advancement lists %s, not both ids" % (tid, ids))
            # the reach the Normal cycle gives this seat
            seat = tuple(s["seat"])
            reach = None
            for line in normal_cycle:
                mm = re.match(r"execute positioned %d\.5 %d %d\.5 as @a\[distance=\.\.([0-9.]+)\] run runmolang"
                              % seat, line)
                if mm and ("cobblers_beat_%s'" % tid) in line:
                    reach = float(mm.group(1))
            swaps = [l for l in challenge_cycle if l.endswith('{TrainerId:"%s"}' % cid) or l.endswith('{TrainerId:"%s"}' % tid)]
            homes = [l for l in challenge_cycle if 'TrainerId:"%s",InBattle:0b}] positioned' % cid in l]
            if not homes:
                self.fail("R:home", "%s's Challenge id has no home line: a swapped trainer wanders" % tid)
            if reach is None or not swaps:
                self.fail("R:swap", "%s: reach %s, %d swap lines" % (tid, reach, len(swaps)))
                continue
            for problem in self.swap_cases(seat, swaps, tid, cid, tag, reach):
                self.fail("R:swap", "%s: %s" % (tid, problem))
                break
            checked += 1
        self.note("R: the swap was run for %d seats" % checked)
        # our list is not the world: the re-apply step that seats these trainers looks for the Normal id only
        ra = (self.root / "tools" / "reapply.py")
        if ra.exists():
            src = ra.read_text(encoding="utf-8", errors="replace")
            if "summon_persistent" in src and not re.search(r"%s\b|challenge_mode" % re.escape(self.suffix), src):
                self.report("R:r17", "tools/reapply.py seats a route trainer with `rctmod trainer summon_persistent` "
                            "unless an entity with the NORMAL TrainerId stands within 24. While a Challenge player is "
                            "within a seat's reach the entity carries the Challenge id, so a re-apply then summons a "
                            "second trainer; when the player leaves, the swap turns both back to Normal and the seat "
                            "stays doubled. The check should accept either id (OAK_AND_CHALLENGE.md section 6 item 10 "
                            "names this gap; nothing enforces 'nobody near the routes')")
        self.ran += 8

    @staticmethod
    def swap_cases(seat, lines, tid, cid, tag, reach):
        """Every mix of nearby players, in and out of battle, from either id; the rule is the one the mode means."""
        inside, outside = max(reach - 1, 0.5), reach + 0.5
        crowds = [[], [(inside, False)], [(inside, True)], [(1.0, True), (inside, False)], [(1.0, False), (inside, True)],
                  [(outside, True)], [(outside, False), (outside, True)], [(inside, True), (outside, False)]]
        out = []
        for start, battle, crowd in itertools.product((tid, cid), (False, True), crowds):
            players = [{"d": d, "tags": {tag} if t else set()} for d, t in crowd]
            sm = SeatModel(seat, [{"id": start, "battle": battle}], players)
            for line in lines:
                sm.run(line)
            near = sorted((p for p in players if p["d"] <= reach), key=lambda p: p["d"])
            want = start if battle else (cid if near and tag in near[0]["tags"] else tid)
            got = [t["id"] for t in sm.trainers]
            if got != [want]:
                out.append("from %s, in battle %s, players %s: ends %s, expected %s" % (start, battle, crowd, got, want))
        return out

    # ================================================================================================ K
    def check_keyed(self):
        ids = self.kanto
        pat = re.compile(r"\b(%s)\b" % "|".join(map(re.escape, ids)))
        skip = {"challenge_mode.py", "challenge_mode_audit.py", "route_trainers.py"}
        hits = []
        for p in sorted((self.root / "tools").glob("*.py")) + sorted(self.data.glob("*.json")):
            if p.name in skip:
                continue
            s = p.read_text(encoding="utf-8", errors="replace")
            if pat.search(s) and not re.search(r"%s\b|challenge_mode" % re.escape(self.suffix), s):
                hits.append(p.relative_to(self.root).as_posix())
        if hits:
            self.report("K:keyed", "%d file(s) key on a Normal Kanto boss id and never mention the Challenge id "
                        "(OAK_AND_CHALLENGE.md section 6 item 9): %s" % (len(hits), ", ".join(hits)))
        for p in sorted(self.data.glob("*.json")):
            for m in re.finditer(r"rct_defeated:(\w+)", p.read_text(encoding="utf-8", errors="replace")):
                if m.group(1) in ids:
                    self.report("K:rct_defeated", "%s gates on rct_defeated:%s, which a Challenge player never has "
                                "(their win is on %s%s)" % (p.relative_to(self.root).as_posix(), m.group(1),
                                                            m.group(1), self.suffix))
        self.ran += 1

    def run(self, only=CHECKS):
        steps = {"C": self.check_config, "S": self.check_starter, "M": self.check_series_command,
                 "T": self.check_text, "B": self.check_bosses, "P": self.check_spawners, "R": self.check_routes,
                 "K": self.check_keyed}
        for k in CHECKS:
            if k in only:
                steps[k]()
        return self


def codes(audit):
    return {c for c, _m in audit.problems}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--snapshot", default=str(SNAPSHOT), help="the server snapshot's datapacks folder (upstream zips)")
    ap.add_argument("--only", default=CHECKS, help="check groups, e.g. B,P")
    a = ap.parse_args(argv)
    try:
        up = Upstream(a.snapshot)
    except FileNotFoundError as e:
        print("challenge_mode_audit: CANNOT AUDIT -- %s" % e)
        return 2
    audit = Audit(Artifacts(), up).run(a.only.replace(",", ""))
    for c, m in audit.problems:
        print("FAIL    %s %s" % (c, m))
    for c, m in audit.reports:
        print("REPORT  %s %s" % (c, m))
    for n in audit.notes:
        print("NOTE    %s" % n)
    part = "" if set(CHECKS) <= set(a.only.replace(",", "")) else " (PARTIAL: only %s)" % a.only
    if audit.problems:
        print("challenge_mode_audit: FAIL -- %d problem(s), %d report(s)%s" % (len(audit.problems), len(audit.reports), part))
        return 1
    print("challenge_mode_audit: ok -- %d checks, 0 problems, %d report(s)%s" % (audit.ran, len(audit.reports), part))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
