"""Walks a simulated player through the BUILT cobblers_titles pack and counts the titles it shows.

The pack is read as text, the way the server reads it, and run by a small interpreter of exactly the command forms it
emits (an unknown form fails the test, so the interpreter cannot quietly skip a line). The server-side rules it models
are vanilla 1.21.1's: the `minecraft:location` trigger is tested every 20 player ticks for advancements the player does
not hold; an advancement's reward function runs as the player when it is granted; `#minecraft:tick` functions run every
tick, `#minecraft:load` once; `return` ends only the function it is in; an unset score fails every `if score` test.

What this proves: the pack's own logic (enter/leave pairs, the settlement guard, the cooldown gate, the re-arm on
joining and on leaving) titles a place once on arrival, comes back to the right title after a detour, and does not
spam on a border. What it cannot prove: that the server parses the files (a boot's log does) or that the client draws
the title (somebody has to walk in).
"""
import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import location_titles as LT  # noqa: E402

NS = "cobblers"


class Player:
    def __init__(self, pack):
        self.pack = pack
        self.fn = {}
        for p in (pack / "data" / NS / "function").rglob("*.mcfunction"):
            rel = p.relative_to(pack / "data" / NS / "function").as_posix()[:-len(".mcfunction")]
            self.fn["%s:%s" % (NS, rel)] = [l for l in p.read_text(encoding="utf-8").splitlines()
                                            if l.strip() and not l.startswith("#")]
        self.adv = {}
        for p in (pack / "data" / NS / "advancement").rglob("*.json"):
            rel = p.relative_to(pack / "data" / NS / "advancement").as_posix()[:-5]
            self.adv["%s:%s" % (NS, rel)] = json.loads(p.read_text(encoding="utf-8"))
        self.pred = {}
        for p in (pack / "data" / NS / "predicate").rglob("*.json"):
            rel = p.relative_to(pack / "data" / NS / "predicate").as_posix()[:-5]
            self.pred["%s:%s" % (NS, rel)] = json.loads(p.read_text(encoding="utf-8"))
        tags = pack / "data" / "minecraft" / "tags" / "function"
        self.tick_fns = json.loads((tags / "tick.json").read_text(encoding="utf-8"))["values"]
        self.held = set()
        self.scores = {}
        self.objectives = set()
        self.titles = []          # (time, title text)
        self.time = 0
        self.ptick = 0            # the player's own tick count, reset on join
        self.pos = (0, 100, 0)
        self.sky = True
        self.online = False
        for f in json.loads((tags / "load.json").read_text(encoding="utf-8"))["values"]:
            self.run(f)

    # ------------------------------------------------------------------ conditions
    def cond(self, c):
        k = c["condition"]
        if k == "minecraft:any_of":
            return any(self.cond(t) for t in c["terms"])
        if k == "minecraft:all_of":
            return all(self.cond(t) for t in c["terms"])
        if k == "minecraft:inverted":
            return not self.cond(c["term"])
        if k == "minecraft:entity_properties":
            assert c["entity"] == "this"
            loc = c["predicate"]["location"]
            assert set(loc) <= {"dimension", "position", "can_see_sky"}, loc
            if "dimension" in loc and loc["dimension"] != "minecraft:overworld":
                return False
            if "can_see_sky" in loc and loc["can_see_sky"] != self.sky:
                return False
            for axis, v in loc.get("position", {}).items():
                q = self.pos["xyz".index(axis)]
                if not (v["min"] <= q <= v["max"]):
                    return False
            return True
        raise AssertionError("condition the interpreter does not know: %s" % k)

    # ------------------------------------------------------------------ commands
    def score(self, obj):
        return self.scores.get(obj)

    def run(self, name):
        for line in self.fn[name]:
            if self.line(line) == "return":
                return

    def line(self, l):
        m = re.fullmatch(r"execute as @a(?:\[scores=\{(\S+)=(\S+)\}\])? (.+)", l)
        if m:                                   # one player online: @a is this player, filtered by its scores
            if m.group(1) and not self.score_test(["@s", m.group(1), "matches", m.group(2)]):
                return None
            rest = m.group(3)
            return self.line(rest[4:] if rest.startswith("run ") else "execute " + rest)
        m = re.fullmatch(r"execute store result score @s (\S+) run time query gametime", l)
        if m:
            self.scores[m.group(1)] = self.time
            return None
        m = re.fullmatch(r"execute (if|unless) (.+?) run (.+)", l)
        if m:
            conds, rest = self.split_conds(m.group(1) + " " + m.group(2))
            if not all(conds):
                return None
            return self.line(m.group(3))
        if l.startswith("return run "):
            self.line(l[len("return run "):])
            return "return"
        m = re.fullmatch(r"advancement revoke @s only (\S+)", l)
        if m:
            assert m.group(1) in self.adv, m.group(1)
            self.held.discard(m.group(1))
            return None
        m = re.fullmatch(r"function (\S+)", l)
        if m:
            self.run(m.group(1))
            return None
        m = re.fullmatch(r"scoreboard players set @s (\S+) (-?\d+)", l)
        if m:
            assert m.group(1) in self.objectives, m.group(1)
            self.scores[m.group(1)] = int(m.group(2))
            return None
        m = re.fullmatch(r"scoreboard players add @s (\S+) (-?\d+)", l)
        if m:
            self.scores[m.group(1)] = (self.score(m.group(1)) or 0) + int(m.group(2))
            return None
        m = re.fullmatch(r"scoreboard players operation @s (\S+) (=|-=) @s (\S+)", l)
        if m:
            src = self.score(m.group(3)) or 0
            self.scores[m.group(1)] = src if m.group(2) == "=" else (self.score(m.group(1)) or 0) - src
            return None
        m = re.fullmatch(r"scoreboard objectives add (\S+) (\S+)", l)
        if m:
            self.objectives.add(m.group(1))
            return None
        m = re.fullmatch(r"title @s (times \d+ \d+ \d+|subtitle .+|title (.+))", l)
        if m:
            if m.group(2):
                self.titles.append((self.time, json.loads(m.group(2))["text"]))
            return None
        raise AssertionError("command form the interpreter does not know: %r" % l)

    def split_conds(self, s):
        out, toks, i = [], s.split(" "), 0
        while i < len(toks):
            mode, kind = toks[i], toks[i + 1]
            neg = mode == "unless"
            assert mode in ("if", "unless"), s
            if kind == "predicate":
                out.append(self.cond(self.pred[toks[i + 2]]) != neg)
                i += 3
            elif kind == "entity":
                m = re.fullmatch(r"@s\[advancements=\{(\S+)=true\}\]", toks[i + 2])
                assert m, toks[i + 2]
                out.append((m.group(1) in self.held) != neg)
                i += 3
            elif kind == "score":
                n = 4 if toks[i + 4] == "matches" else 5
                out.append(self.score_test(toks[i + 2:i + 2 + n]) != neg)
                i += 2 + n
            else:
                raise AssertionError("execute condition the interpreter does not know: %s" % s)
        return out, None

    def score_test(self, t):
        # "@s <obj> matches <range>" or "@s <obj> = @s <obj>"
        assert t[0] == "@s"
        a = self.score(t[1])
        if t[2] == "matches":
            if a is None:
                return False
            lo, _, hi = t[3].partition("..")
            if ".." not in t[3]:
                return a == int(lo)
            return (lo == "" or a >= int(lo)) and (hi == "" or a <= int(hi))
        assert t[2] == "=" and t[3] == "@s"
        b = self.score(t[4])
        return a is not None and b is not None and a == b

    # ------------------------------------------------------------------ the server loop
    def join(self):
        self.online = True
        self.ptick = 0

    def leave(self):
        self.online = False
        self.scores["cob_t_left"] = (self.score("cob_t_left") or 0) + 1

    def tick(self):
        self.time += 1
        for f in self.tick_fns:
            if self.online:
                self.run(f)
        if not self.online:
            return
        self.ptick += 1
        if self.ptick % 20 == 0:
            matching = [a for a, d in self.adv.items() if a not in self.held
                        and all(self.cond(c) for c in d["criteria"]["here"]["conditions"]["player"])]
            for a in sorted(matching):
                if a in self.held:
                    continue
                self.held.add(a)
                self.run(self.adv[a]["rewards"]["function"])

    def stay(self, seconds, pos=None, sky=True):
        if pos is not None:
            self.pos, self.sky = pos, sky
        for _ in range(int(seconds * 20)):
            self.tick()




@pytest.fixture(scope="module")
def pack(tmp_path_factory):
    out = tmp_path_factory.mktemp("titles_play") / "pack"
    LT.build(out)
    return out


def settlement(sid):
    return next(s for s in LT.settlements(LT.regions()) if s["id"] == sid)


def zone_point(zone_id, avoid=()):
    """A column deep inside the zone's own in_ boxes and in no other zone's or settlement's box."""
    zs = {z["zone"]: z for z in LT.zones()}
    others = [b for k, z in zs.items() if k != zone_id for b in z["boxes"]]
    others += [(s["box"][0] - 24, s["box"][1] - 24, s["box"][2] + 24, s["box"][3] + 24, None, None)
               for s in LT.settlements(LT.regions())]
    for x0, z0, x1, z1, _, _ in sorted(zs[zone_id]["boxes"], key=lambda b: -(b[2] - b[0]) * (b[3] - b[1])):
        x, z = (x0 + x1) // 2, (z0 + z1) // 2
        if not any(b[0] - 24 <= x <= b[2] + 24 and b[1] - 24 <= z <= b[3] + 24 for b in others):
            return (x, 100, z)
    raise AssertionError("no clear column in %s" % zone_id)


def titles_after(p, t0):
    return [t for when, t in p.titles if when > t0]


def test_spawn_in_pallet_titles_the_town_after_the_loading_screen_then_the_meadows_outside(pack):
    p = Player(pack)
    town = settlement("hometown")
    x0, z0, x1, z1 = town["box"]
    p.join()
    p.stay(4, ((x0 + x1) // 2, 100, (z0 + z1) // 2))
    assert p.titles == [], "a title in the first seconds lands under the loading screen"
    p.stay(4)
    assert [t for _, t in p.titles] == [town["name"]]
    t = p.time
    p.stay(3, zone_point("pallet_meadows"))
    assert titles_after(p, t) == ["Pallet Meadows"]
    t = p.time
    p.stay(60)
    assert titles_after(p, t) == [], "standing still must not re-title"


def test_a_border_walked_back_and_forth_titles_rarely_and_ends_right(pack):
    p = Player(pack)
    a, b = zone_point("pallet_meadows"), zone_point("route1_maze_forest")
    p.join()
    p.stay(8, a)
    t = p.time
    for _ in range(15):                    # two minutes of A, B, A, B every four seconds
        p.stay(4, b)
        p.stay(4, a)
    shown = titles_after(p, t)
    assert len(shown) <= 2 * (120 // 30) + 2, shown
    p.stay(35, a)
    assert p.titles[-1][1] == "Pallet Meadows", "after the cooldown the screen must name where the player is"


def test_a_detour_into_the_creek_comes_back_to_the_zone_around_it(pack):
    p = Player(pack)
    zs = {z["zone"]: z for z in LT.zones()}
    land = [(k, z) for k, z in zs.items() if z["kind"] == "land"]
    # the first creek box whose centre a land zone holds (some lie on a seam no sub-region covers: NUZLOCKE_ZONES.md)
    cx, cz, around = next(((c[0] + c[2]) // 2, (c[1] + c[3]) // 2, k) for c in zs["mt_clay_outflow"]["boxes"]
                          for k, z in land
                          if any(b[0] <= (c[0] + c[2]) // 2 <= b[2] and b[1] <= (c[1] + c[3]) // 2 <= b[3] for b in z["boxes"]))
    # a column of the surrounding zone 60 blocks from the creek box, clear of it
    side = next((cx + dx, 100, cz + dz) for r in (40, 60, 80, 120) for dx, dz in ((r, 0), (-r, 0), (0, r), (0, -r),
                                                                                 (r, r), (-r, r), (r, -r), (-r, -r))
                if any(b[0] <= cx + dx <= b[2] and b[1] <= cz + dz <= b[3] for b in zs[around]["boxes"])
                and not any(b[0] - 9 <= cx + dx <= b[2] + 9 and b[1] - 9 <= cz + dz <= b[3] + 9
                            for b in zs["mt_clay_outflow"]["boxes"]))
    p.join()
    p.stay(8, side)
    assert p.titles[-1][1] == zs[around]["name"]
    p.stay(3, (cx, 100, cz))
    assert p.titles[-1][1] == zs["mt_clay_outflow"]["name"]
    p.stay(35, side)
    assert p.titles[-1][1] == zs[around]["name"], "back out of the creek, the screen must name the zone again"


def test_logging_back_in_where_you_left_titles_the_place_again(pack):
    p = Player(pack)
    a = zone_point("viltri_plateau")
    p.join()
    p.stay(8, a)
    assert [t for _, t in p.titles] == ["Viltri Plateau"]
    p.leave()
    p.stay(60)
    p.join()
    p.stay(8)
    assert [t for _, t in p.titles] == ["Viltri Plateau", "Viltri Plateau"]


def test_a_cave_zone_titles_underground_and_not_under_the_sky(pack):
    p = Player(pack)
    blocks = json.loads((ROOT / "data" / "habitat_blocks.json").read_text(encoding="utf-8"))["blocks"]
    b = next(b for b in blocks if b["pool"] == "cobblers:vrc_bloom" and b.get("status") == "placed")
    pos = (b["position"]["x"], b["position"]["y"], b["position"]["z"])
    p.join()
    p.stay(8, pos, sky=True)
    assert "The Bloom" not in [t for _, t in p.titles]
    p.stay(3, pos, sky=False)
    assert p.titles[-1][1] == "The Bloom"
