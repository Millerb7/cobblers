"""A small interpreter for the keeper function tools/scenes_pack.py emits (data/scenes.json "keepers"), over the world of
tests/molang_dialogue_sim.py.

Like that file it runs exactly the command shapes the generator writes and raises on any other, so a generator change that
emits a command this file does not know fails loudly instead of being skipped. It is not Minecraft: it cannot say that
Minecraft accepts a selector, that `@s[x=,y=,z=,distance=]` measures from those coordinates, or that a teleported NPC
keeps its dialogue screen open. It says what the commands DECIDE, for players standing where a test puts them.

Players stand where `world.pos[name]` says (a player with no entry is offline or elsewhere: no selector finds them).
NPCs are molang_dialogue_sim.Npc, standing at `.pos` with `.tags`.
"""
import re

ARG = re.compile(r"(\w+)=(\{[^}]*\}|[^,]*)")


def parse(args):
    return [(k, v) for k, v in ARG.findall(args)]


def in_range(val, rng):
    if val is None:
        return False
    lo, _, hi = rng.partition("..")
    if ".." not in rng:
        return val == int(lo)
    return (not lo or val >= int(lo)) and (not hi or val <= int(hi))


class Keeper:
    def __init__(self, world, lines):
        self.w = world
        if not hasattr(world, "pos"):
            world.pos = {}
        self.lines = [ln for ln in lines if ln.strip() and not ln.startswith("#")]
        self.log = []

    # ------------------------------------------------------------------ selectors
    def match(self, who, args, is_player):
        pos = self.w.pos.get(who.name) if is_player else who.pos
        if pos is None:
            return False
        a = dict(parse(args))
        if "type" in a and (is_player or a["type"] != "cobblemon:npc"):
            return False
        tags = who.tags
        if "tag" in a:
            t = a["tag"]
            if (t[1:] in tags) if t.startswith("!") else (t not in tags):
                return False
        if "scores" in a:
            for k, rng in re.findall(r"(\w+)=([^,}]+)", a["scores"]):
                if not in_range(who.scores.get(k) if is_player else None, rng):
                    return False
        origin = None
        if all(k in a for k in "xyz"):
            origin = (float(a["x"]), float(a["y"]), float(a["z"]))
        if all(k in a for k in ("dx", "dy", "dz")):
            lo = origin
            hi = (lo[0] + int(a["dx"]) + 1, lo[1] + int(a["dy"]) + 1, lo[2] + int(a["dz"]) + 1)
            if not all(lo[i] <= pos[i] <= hi[i] for i in range(3)):
                return False
        elif "distance" in a:
            d = sum((pos[i] - origin[i]) ** 2 for i in range(3)) ** .5
            if d > float(a["distance"].lstrip(".")):
                return False
        return True

    def entities(self, args):
        found = [n for n in self.w.npcs if self.match(n, args, False)]
        return found[:1] if "limit=1" in args else found

    def players(self, args):
        return [p for p in self.w.players.values() if self.match(p, args, True)]

    # ------------------------------------------------------------------ commands
    def cycle(self):
        for ln in self.lines:
            self.run(ln)

    def run(self, line):
        if not line.startswith("execute "):
            return self.cmd(line, None)
        self.execute(line[len("execute "):], None)

    def execute(self, rest, me):
        rest = rest.strip()
        if rest.startswith("run "):
            return self.cmd(rest[4:], me)
        m = re.match(r"(if|unless) score (\S+) (\S+) matches (\S+) (.*)", rest)
        if m:
            held = in_range(self.w.scores.get((m.group(2), m.group(3))), m.group(4))
            if held == (m.group(1) == "if"):
                self.execute(m.group(5), me)
            return
        m = re.match(r"as @e\[(.*?)\] (.*)", rest)
        if m:
            for e in self.entities(m.group(1)):
                self.execute(m.group(2), e)
            return
        m = re.match(r"unless entity @s\[(.*?)\] (.*)", rest)
        if m:
            if not self.match(me, m.group(1), False):
                self.execute(m.group(2), me)
            return
        m = re.fullmatch(r"store success score (\S+) (\S+) if entity @a\[(.*?)\]", rest)
        if m:
            self.w.scores[(m.group(1), m.group(2))] = 1 if self.players(m.group(3)) else 0
            return
        raise RuntimeError("keeper_sim does not know this execute clause: %r" % rest)

    def cmd(self, text, me):
        self.log.append(text)
        m = re.fullmatch(r"tag @s add (\S+)", text)
        if m and me is not None:
            me.tags.add(m.group(1))
            return
        m = re.fullmatch(r"tp @s (\S+) (\S+) (\S+) (-?\d+) 0", text)
        if m and me is not None:
            me.pos = (float(m.group(1)), float(m.group(2)), float(m.group(3)))
            return
        m = re.fullmatch(r"scoreboard players set (\S+) (\S+) (-?\d+)", text)
        if m:
            self.w.scores[(m.group(1), m.group(2))] = int(m.group(3))
            return
        m = re.fullmatch(r"scoreboard players remove @a\[(.*?)\] (\S+) (\d+)", text)
        if m:
            for p in self.players(m.group(1)):
                p.scores[m.group(2)] = p.scores.get(m.group(2), 0) - int(m.group(3))
            return
        raise RuntimeError("keeper_sim does not know this command: %r" % text)
