#!/usr/bin/env python
"""The scene runtime: what a quest needs in the world besides its dialogue, generated from data/scenes.json as the
datapack build/datapacks/cobblers_scenes.

A scene belongs to one quest and holds, inside an area:

  props      clickable things (a cup, a sign, a door): a vanilla interaction entity each, placed once and shared.
             A click opens that prop's conversation for the player who clicked, so every player gets their own
             state from the same prop.
  actors     Pokemon that belong to one player: each player in the area has their own copy, standing at the marker
             their own quest state names (the first `place` rule whose condition holds). An actor is a Cobblemon
             Pokemon spawned uncatchable and without AI, then marked Unbattleable and Invulnerable, with an
             interaction entity on it; a click opens the actor's conversation, but only for its owner (anyone else
             is told it is not theirs). This is the checkpoint mechanism: an actor's position is a function of the
             owner's saved fields, so leaving, dying, disconnecting or a restart cannot lose it. The actor goes when
             its owner leaves the area and comes back where their state says.
  zones      boxes that run quest transitions for a player standing in them (the transition's own conditions decide).
  effects    things one player sees or feels: particles sent only to them (`force <player>`), a push back out of a box,
             a sequence of lights, a sound. Each runs while its condition holds for that player.
  functions  named command lists a dialogue can run as the player (effect scene_function in data/quests.json).
  no_build   boxes (a building's interior) where a survival player is put in adventure mode, and back on leaving.
  npcs       Cobblemon NPCs (people) that open a conversation; shared and static. NPC classes load only at server
             start, so they are placed over RCON after a restart (tools/reapply.py), not by a function.

How it runs, every 20 ticks (cobblers:scenes/cycle):
  1. every actor not refreshed since the last cycle vanishes: its owner left the area, logged off, or no longer
     qualifies (tag cobblers_fresh);
  2. every player inside a scene's area runs its beat: `runmolang` reads their quest fields (q.player.data(), the
     store the dialogue compiler writes, EXP-022) and calls the actor and effect functions their state selects,
     which move or spawn that player's actors and mark them fresh; then the zones.
Ownership is the scoreboard `cobblers_pid`: a number per player, copied onto each of their actors. It is identity,
not quest state: every mutable quest field stays in the Cobblemon player data.

Runtime facts this rests on (staging cobblers-dryrun9, 2026-09-24, Cobblemon 1.8.0): `spawnpokemonat <pos> gastly
uncatchable no_ai` gives NoAI:1b, and `data merge` then holds Unbattleable:1b, Invulnerable:1b and tags on it;
`runmolang`, `opendialogue`, `spawnpokemonat` and `rctmod trainer summon_persistent` load and run inside a function;
q.run_command from runmolang runs. Not yet seen: a player clicking, two players at once (EXP-034).

  python tools/scenes_pack.py [--out DIR]             write the pack
  python tools/scenes_pack.py --check                 the static checks only
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import compile_dialogue as CD  # noqa: E402

DATA = ROOT / "data"
DEFAULT_OUT = ROOT / "build" / "datapacks" / "cobblers_scenes"
NS = "cobblers"
PID, CLOCK, PERIOD = "cobblers_pid", "cobblers_scene", 20
SLOTS = [(0.0, 0.0), (0.9, 0.0), (0.0, 0.9), (-0.9, 0.0)]   # side by side when players stand at one checkpoint together
ID = re.compile(r"[a-z0-9_]+")
SPECIES = re.compile(r"[a-z0-9_]+")
PARTICLE = re.compile(r"[a-z0-9_]+:[a-z0-9_]+")


class SceneError(SystemExit):
    pass


def load(data_dir=DATA):
    return json.loads((data_dir / "scenes.json").read_text(encoding="utf-8"))


def box(b):
    """(x, y, z, dx, dy, dz) for a selector volume from {"from": [...], "to": [...]}."""
    a, c = b["from"], b["to"]
    lo = [min(a[i], c[i]) for i in range(3)]
    hi = [max(a[i], c[i]) for i in range(3)]
    return lo + [hi[i] - lo[i] for i in range(3)]


def sel(b):
    x, y, z, dx, dy, dz = box(b)
    return "x=%d,y=%d,z=%d,dx=%d,dy=%d,dz=%d" % (x, y, z, dx, dy, dz)


def inside(p, b):
    x, y, z, dx, dy, dz = box(b)
    return x <= p[0] <= x + dx + 1 and y <= p[1] <= y + dy + 1 and z <= p[2] <= z + dz + 1


def num(v):
    s = ("%.2f" % v).rstrip("0").rstrip(".")
    return "0" if s in ("-0", "") else s


def mol_str(s):
    """A Molang string literal inside a runmolang "..." argument: no double quotes, no single quotes."""
    if '"' in s or "'" in s or "\\" in s:
        raise SceneError("text %r cannot sit inside a runmolang argument" % s)
    return s


class Scene:
    def __init__(self, doc, quests, fields, conversations):
        self.doc = doc
        self.id = doc["id"]
        if not ID.fullmatch(self.id):
            raise SceneError("scene id %r" % self.id)
        self.quest = quests.get(doc["quest_id"])
        if self.quest is None:
            raise SceneError("scene %s: unknown quest %s" % (self.id, doc["quest_id"]))
        CD.check_fields(self.quest, fields)
        fake = {"nodes": [], "cursor": {"progression_field": None, "initial_node": None}, "entry_rules": []}
        self.c = CD.Compiler(fake, self.quest, fields)
        self.convs = conversations
        self.markers = doc.get("markers") or {}
        self.area = doc["area"]
        self.fn = "%s:scenes/%s" % (NS, self.id)

    # ------------------------------------------------------------------ helpers
    def cond(self, c):
        probes = {}
        out = self.c.cond(c, probes)
        if probes:
            raise SceneError("scene %s: held-item conditions cannot run in a beat (commands under runmolang are queued, "
                             "so the probe would be read before it runs)" % self.id)
        return out

    def run_as(self, fn):
        return "q.run_command('execute as ' + q.player.uuid + ' at @s run function %s');" % fn

    def conv(self, cid, opened_by):
        conv = self.convs.get(cid)
        if conv is None:
            raise SceneError("scene %s: no conversation %s" % (self.id, cid))
        if conv["quest_id"] != self.quest["id"]:
            raise SceneError("scene %s: conversation %s runs quest %s, not %s" % (self.id, cid, conv["quest_id"], self.quest["id"]))
        if opened_by != "npc" and conv.get("npc_id"):
            raise SceneError("scene %s: %s is opened by a %s, so it must have npc_id null" % (self.id, cid, opened_by))
        if opened_by == "npc" and not conv.get("npc_id"):
            raise SceneError("scene %s: %s is an NPC's conversation and has no npc_id" % (self.id, cid))
        return cid

    def marker(self, name):
        """(x, y, z, yaw, slots) for a marker: [x, y, z], [x, y, z, yaw] or {"at": [x, y, z], "yaw": .., "slots": ..}.
        Slots are the offsets from the block centre at which the owners' copies stand side by side (pid mod count)."""
        m = self.markers.get(name)
        slots = self.doc.get("slots") or SLOTS
        if isinstance(m, dict):
            at, yaw, slots = m.get("at"), m.get("yaw", 0), m.get("slots") or slots
        elif isinstance(m, list) and len(m) in (3, 4):
            at, yaw = m[:3], (m[3] if len(m) > 3 else 0)
        else:
            at = None
        if not (isinstance(at, list) and len(at) == 3):
            raise SceneError("scene %s: marker %r needs [x, y, z]" % (self.id, name))
        if not inside(at, self.area):
            raise SceneError("scene %s: marker %s %s is outside the area" % (self.id, name, at))
        if not (isinstance(slots, list) and slots and all(isinstance(s, list) and len(s) == 2 for s in slots)):
            raise SceneError("scene %s: marker %s slots" % (self.id, name))
        return at[0], at[1], at[2], yaw, [tuple(s) for s in slots]

    # ------------------------------------------------------------------ generation
    def files(self):
        out = {}
        beat = ["# %s: one player's beat (as and at the player), run each cycle while they are in the area" % self.id,
                "execute unless score @s %s matches 1.. run function %s:scenes/pid" % (PID, NS)]
        mol = ["t.d = q.player.data();"]
        for a in self.doc.get("actors") or []:
            mol.append(self.actor(a, out))
        for e in self.doc.get("effects") or []:
            mol.append(self.effect(e, out))
        beat.append('runmolang "%s" @s' % " ".join(m for m in mol if m))
        for z in self.doc.get("zones") or []:
            beat += self.zone(z)
        if self.doc.get("actors") or self.doc.get("effects") or self.doc.get("zones"):
            out["beat"] = beat                 # the cycle calls a beat only for these (build()); none is written unused
        for p in self.doc.get("props") or []:
            self.prop(p, out)
        place = ["# %s: its props, once (a re-run replaces them); the chunks must be loaded" % self.id]
        for p in self.doc.get("props") or []:
            x, y, z = p["at"]
            w, h = p.get("size", [1.0, 1.0])
            place.append("kill @e[type=minecraft:interaction,tag=cobblers_prop_%s_%s]" % (self.id, p["id"]))
            place.append('summon minecraft:interaction %s %s %s {width:%sf,height:%sf,response:1b,Tags:["cobblers_prop","cobblers_prop_%s_%s"]}'
                         % (num(x), num(y), num(z), num(w), num(h), self.id, p["id"]))
        props = self.doc.get("props") or []
        if props:
            from place_town import forceload_commands
            box = (int(min(q["at"][0] for q in props)), int(min(q["at"][2] for q in props)),
                   int(max(q["at"][0] for q in props)), int(max(q["at"][2] for q in props)))
            place = place[:1] + forceload_commands(box, "add") + place[1:] + forceload_commands(box, "remove")
        out["place"] = place
        for name, cmds in (self.doc.get("functions") or {}).items():
            if not ID.fullmatch(name):
                raise SceneError("scene %s: function name %r" % (self.id, name))
            if not isinstance(cmds, list) or not all(isinstance(c, str) and c and not c.startswith("/") for c in cmds):
                raise SceneError("scene %s: function %s must be a list of commands without a leading /" % (self.id, name))
            # spawnpokemonat does nothing inside a function (see the actors' spawn): it runs through q.run_command
            run = [('runmolang "q.run_command(\'%s\');" @s' % mol_str(c)) if c.startswith("spawnpokemonat ") else c for c in cmds]
            out["fn/%s" % name] = ["# %s: %s (run as and at the player, by a dialogue's scene_function)" % (self.id, name)] + run
        for n in self.doc.get("npcs") or []:
            self.conv(n["conversation"], "npc")
            if not inside(n["at"], self.area):
                raise SceneError("scene %s: npc %s at %s is outside the area" % (self.id, n["conversation"], n["at"]))
        return out

    def actor(self, a, out):
        aid = a["id"]
        if not ID.fullmatch(aid) or not SPECIES.fullmatch(a["species"]):
            raise SceneError("scene %s: actor id %r / species %r" % (self.id, aid, a["species"]))
        self.conv(a["conversation"], "actor")
        tag = "cobblers_actor_%s_%s" % (self.id, aid)
        click = "cobblers_click_%s_%s" % (self.id, aid)
        markers = []
        for r in a["place"]:
            if r["marker"] not in markers:
                markers.append(r["marker"])
        at_tags = ["cobblers_at_%s_%s_%d" % (aid, m, k) for m in markers for k in range(len(self.marker(m)[4]))]
        props = "level=%d uncatchable no_ai" % int(a["level"])
        name = a.get("name")
        merge = "Unbattleable:1b,Invulnerable:1b,PersistenceRequired:1b,DeathLootTable:\"minecraft:empty\""
        if name:
            if not re.fullmatch(r"[A-Za-z' .-]+", name):
                raise SceneError("scene %s: actor name %r" % (self.id, name))
            merge += ",CustomName:'\"%s\"',CustomNameVisible:1b" % name
        for m in markers:
            x, y, z, yaw, slots = self.marker(m)
            at = ["# %s: %s stands at marker %s (as the owner)" % (self.id, aid, m),
                  "scoreboard players operation #owner %s = @s %s" % (PID, PID),
                  "scoreboard players operation #slot %s = @s %s" % (PID, PID),
                  "scoreboard players set #n %s %d" % (CLOCK, len(slots)),
                  "scoreboard players operation #slot %s %%= #n %s" % (PID, CLOCK)]
            at += ["execute if score #slot %s matches %d run function %s/%s/at/%s_%d" % (PID, k, self.fn, aid, m, k) for k in range(len(slots))]
            out["%s/at/%s" % (aid, m)] = at
            for k, (ox, oz) in enumerate(slots):
                px, pz = x + 0.5 + ox, z + 0.5 + oz
                here = "cobblers_at_%s_%s_%d" % (aid, m, k)
                pos = "%s %s %s" % (num(px), num(y), num(pz))
                out["%s/at/%s_%d" % (aid, m, k)] = [
                    "execute as @e[tag=%s] if score @s %s = #owner %s run tag @s add cobblers_mine" % (tag, PID, PID),
                    # one of each, whatever loaded: an actor saved with its chunk before the cycle removed it (a
                    # restart, a fast teleport out and back) loads after its owner's new one was spawned
                    "tag @e[type=cobblemon:pokemon,tag=cobblers_mine,limit=1,sort=arbitrary] add cobblers_keep",
                    "tag @e[type=minecraft:interaction,tag=cobblers_mine,limit=1,sort=arbitrary] add cobblers_keep",
                    "execute as @e[tag=cobblers_mine,tag=!cobblers_keep] at @s run function %s:scenes/vanish" % NS,
                    "tag @e[tag=cobblers_keep] remove cobblers_keep",
                    "execute as @e[tag=cobblers_mine,tag=!%s] at @s run function %s/%s/move/%s_%d" % (here, self.fn, aid, m, k),
                    "execute unless entity @e[type=cobblemon:pokemon,tag=cobblers_mine] run function %s/%s/spawn/%s_%d" % (self.fn, aid, m, k),
                    "execute unless entity @e[type=minecraft:interaction,tag=cobblers_mine] run function %s/%s/hitbox/%s_%d" % (self.fn, aid, m, k),
                    "tag @e[tag=cobblers_mine] add cobblers_fresh",
                    "tag @e[tag=cobblers_mine] remove cobblers_mine"]
                out["%s/move/%s_%d" % (aid, m, k)] = (
                    ["particle minecraft:large_smoke ~ ~0.5 ~ 0.25 0.35 0.25 0.01 10 force"]
                    + ["tag @s remove %s" % t for t in at_tags]
                    + ["tag @s add %s" % here, "tp @s %s %s 0" % (pos, num(yaw)),
                       "particle minecraft:large_smoke %s 0.25 0.35 0.25 0.01 10 force" % pos])
                # spawnpokemonat does nothing inside a function (staging, 2026-09-24: typed, or under execute, it spawns;
                # from a function, never), so it runs through q.run_command, which executes as the console does. The
                # adoption is queued after it, as the owner, re-reading their id: other players' beats may have
                # changed #owner before the queue runs
                out["%s/spawn/%s_%d" % (aid, m, k)] = [
                    'runmolang "q.run_command(\'spawnpokemonat %d %d %d %s %s\'); '
                    'q.run_command(\'execute as \' + q.player.uuid + \' at @s run function %s/%s/claim/%s_%d\');" @s'
                    % (x, y, z, a["species"], props, self.fn, aid, m, k)]
                out["%s/claim/%s_%d" % (aid, m, k)] = [
                    "scoreboard players operation #owner %s = @s %s" % (PID, PID),
                    # only the Pokemon just spawned: without AI and of this species, so a sent-out party Pokemon or a
                    # wild one near the marker is never taken over
                    "execute positioned %d %d %d as @e[type=cobblemon:pokemon,distance=..1.5,tag=!cobblers_actor,"
                    "nbt={NoAI:1b,Pokemon:{Species:\"cobblemon:%s\"}},sort=nearest,limit=1] "
                    "run function %s/%s/adopt/%s_%d" % (x, y, z, a["species"], self.fn, aid, m, k)]
                out["%s/adopt/%s_%d" % (aid, m, k)] = [
                    "data merge entity @s {%s}" % merge,
                    "tag @s add cobblers_actor", "tag @s add %s" % tag, "tag @s add cobblers_fresh", "tag @s add %s" % here,
                    "scoreboard players operation @s %s = #owner %s" % (PID, PID),
                    "tp @s %s %s 0" % (pos, num(yaw))]
                w, h = a.get("hitbox", [1.1, 1.3])
                out["%s/hitbox/%s_%d" % (aid, m, k)] = [
                    'summon minecraft:interaction %s {width:%sf,height:%sf,response:1b,Tags:["cobblers_actor","%s","%s","cobblers_mine","%s"]}'
                    % (pos, num(w), num(h), tag, click, here),
                    "execute positioned %s as @e[type=minecraft:interaction,tag=cobblers_mine,distance=..0.01] "
                    "run scoreboard players operation @s %s = #owner %s" % (pos, PID, PID)]
        other = a.get("not_yours", "That one is following someone else.")
        out["%s/clicked" % aid] = [
            "advancement revoke @s only %s:scenes/click/%s_%s" % (NS, self.id, aid),
            "execute unless score @s %s matches 1.. run function %s:scenes/pid" % (PID, NS),
            "scoreboard players operation #owner %s = @s %s" % (PID, PID),
            "tag @s add cobblers_clicker",
            # the box this player clicked (several owners' copies can stand in one place, and the client always hits
            # the same one), then: is one of this player's own boxes within 1.5 of it? The conversation opened is
            # always the clicker's own, so a click on a stacked copy is theirs to use
            "execute as @e[type=minecraft:interaction,tag=%s,distance=..8] at @s on target if entity @s[tag=cobblers_clicker] "
            "run tag @e[type=minecraft:interaction,tag=%s,distance=..0.05] add cobblers_hit" % (click, click),
            "execute as @e[type=minecraft:interaction,tag=%s,distance=..8] if score @s %s = #owner %s at @s "
            "if entity @e[type=minecraft:interaction,tag=cobblers_hit,distance=..1.5] run tag @a[tag=cobblers_clicker] add cobblers_own_click"
            % (click, PID, PID),
            "tag @e[tag=cobblers_hit] remove cobblers_hit",
            "execute as @e[type=minecraft:interaction,tag=%s,distance=..8] run data remove entity @s interaction" % click,
            "execute if entity @s[tag=cobblers_own_click] run opendialogue %s:%s @s" % (NS, a["conversation"]),
            'execute unless entity @s[tag=cobblers_own_click] run tellraw @s {"text":%s,"color":"gray","italic":true}' % json.dumps(other),
            "tag @s remove cobblers_clicker", "tag @s remove cobblers_own_click"]
        out["advancement:click/%s_%s" % (self.id, aid)] = self.click_advancement(click, "%s/%s/clicked" % (self.fn, aid))
        # the Molang that chooses the marker: the first rule that holds wins; none means no actor for this player
        parts = ["t.done = 0;"]
        for r in a["place"]:
            cond = self.cond(r["when"]) if r.get("when") else "1"
            parts.append("(t.done == 0 && %s) ? { %s t.done = 1; };" % (cond, self.run_as("%s/%s/at/%s" % (self.fn, aid, r["marker"]))))
        return " ".join(parts)

    def click_advancement(self, tag, fn):
        return {"criteria": {"click": {"trigger": "minecraft:player_interacted_with_entity", "conditions": {
                    "entity": [{"condition": "minecraft:entity_properties", "entity": "this",
                                "predicate": {"type": "minecraft:interaction", "nbt": "{Tags:[\"%s\"]}" % tag}}]}}},
                "rewards": {"function": fn}}

    def prop(self, p, out):
        pid = p["id"]
        if not ID.fullmatch(pid):
            raise SceneError("scene %s: prop id %r" % (self.id, pid))
        self.conv(p["conversation"], "prop")
        tag = "cobblers_prop_%s_%s" % (self.id, pid)
        out["prop/%s" % pid] = [
            "advancement revoke @s only %s:scenes/prop/%s_%s" % (NS, self.id, pid),
            "execute as @e[type=minecraft:interaction,tag=%s,distance=..8] run data remove entity @s interaction" % tag,
            "opendialogue %s:%s @s" % (NS, p["conversation"])]
        out["advancement:prop/%s_%s" % (self.id, pid)] = self.click_advancement(tag, "%s/prop/%s" % (self.fn, pid))

    def zone(self, z):
        zid = z["id"]
        if not ID.fullmatch(zid):
            raise SceneError("scene %s: zone id %r" % (self.id, zid))
        if not (inside(z["from"], self.area) and inside(z["to"], self.area)):
            raise SceneError("scene %s: zone %s leaves the area" % (self.id, zid))
        out = []
        for tid in z["transitions"]:
            if tid not in self.c.transitions:
                raise SceneError("scene %s: zone %s names unknown transition %s" % (self.id, zid, tid))
            t = self.c.transitions[tid]
            def items(c):
                if isinstance(c, dict):
                    return c.get("kind") in ("held_item", "inventory_contains") or any(items(v) for v in c.values())
                return isinstance(c, list) and any(items(v) for v in c)
            if items(t["conditions"]):
                raise SceneError("scene %s: zone %s: transition %s checks an item, which a beat cannot" % (self.id, zid, tid))
            if any(e["kind"] in ("consume_held_item", "give_item", "grant_reward_once") for e in t["effects"]):
                raise SceneError("scene %s: zone %s: transition %s moves items; only a dialogue may" % (self.id, zid, tid))
            mol = "t.d = q.player.data(); " + self.c.transition(tid)
            out.append('execute if entity @s[%s] run runmolang "%s" @s' % (sel(z), mol))
        return out

    def effect(self, e, out):
        eid = e["id"]
        if not ID.fullmatch(eid):
            raise SceneError("scene %s: effect id %r" % (self.id, eid))
        kind = e["kind"]
        cmds = ["# %s: effect %s (%s), for this player only" % (self.id, eid, kind)]
        if kind == "particles":
            for p in e["particles"]:
                cmds.append(self.particle(p))
        elif kind == "sequence":
            steps = e["steps"]
            cmds.append("scoreboard players operation #phase %s = #beat %s" % (CLOCK, CLOCK))
            cmds.append("scoreboard players set #len %s %d" % (CLOCK, len(steps)))
            cmds.append("scoreboard players operation #phase %s %%= #len %s" % (CLOCK, CLOCK))
            for k, step in enumerate(steps):
                for p in step:
                    cmds.append("execute if score #phase %s matches %d run %s" % (CLOCK, k, self.particle(p)))
        elif kind == "push":
            dest = self.marker(e["to_marker"])
            yaw = dest[3]
            cmds.append("execute if entity @s[%s] run tellraw @s {\"text\":%s,\"color\":\"gray\",\"italic\":true}"
                        % (sel(e), json.dumps(e.get("message", ""))))
            cmds.append("execute if entity @s[%s] run tp @s %s %s %s %s 0" % (sel(e), num(dest[0] + 0.5), num(dest[1]), num(dest[2] + 0.5), num(yaw)))
        else:
            raise SceneError("scene %s: effect kind %s" % (self.id, kind))
        out["fx/%s" % eid] = cmds
        cond = self.cond(e["when"]) if e.get("when") else "1"
        return "(%s) ? { %s };" % (cond, self.run_as("%s/fx/%s" % (self.fn, eid)))

    def no_build(self, files, fn):
        """Adventure mode inside the scene's no_build boxes: a survival player who steps in cannot break or place,
        and goes back to survival on stepping out. Only survival is switched, and only a player this switched is
        switched back, so creative and spectator are never touched. A player who dies or logs off inside keeps the
        tag and is switched back on the first cycle they are outside. The cycle lines for the scene."""
        boxes = self.doc.get("no_build") or []
        if not boxes:
            return []
        for b in boxes:
            if not (inside(b["from"], self.area) and inside(b["to"], self.area)):
                raise SceneError("scene %s: a no_build box leaves the area" % self.id)
        tag = "cobblers_nobuild_%s" % self.id
        files[fn("%s/nobuild/enter" % self.id)] = [
            "# %s: a survival player inside the house: adventure mode, remembered by a tag" % self.id,
            "gamemode adventure @s", "tag @s add %s" % tag]
        files[fn("%s/nobuild/leave" % self.id)] = [
            "# %s: a player this switched, now outside: back to survival (unless something else changed the mode)" % self.id,
            "execute if entity @s[gamemode=adventure] run gamemode survival @s", "tag @s remove %s" % tag]
        lines = ["# %s: no building or breaking inside" % self.id]
        for b in boxes:
            lines.append("execute as @a[gamemode=survival,%s] run function %s:scenes/%s/nobuild/enter" % (sel(b), NS, self.id))
        outside = " ".join("unless entity @s[%s]" % sel(b) for b in boxes)
        lines.append("execute as @a[tag=%s] %s run function %s:scenes/%s/nobuild/leave" % (tag, outside, NS, self.id))
        return lines

    def particle(self, p):
        if not PARTICLE.fullmatch(p["particle"]):
            raise SceneError("scene %s: particle %r" % (self.id, p["particle"]))
        x, y, z = p["at"]
        dx, dy, dz = p.get("delta", [0, 0, 0])
        return "particle %s %s %s %s %s %s %s %s %d force @s" % (
            p["particle"], num(x), num(y), num(z), num(dx), num(dy), num(dz), num(p.get("speed", 0)), int(p.get("count", 1)))


def build(data_dir=DATA):
    """{relative path in the pack: content} and the scene objects."""
    doc = load(data_dir)
    dialogue, quests, fields = CD.load(data_dir)
    convs = {c["id"]: c for c in dialogue["conversations"]}
    files = {"pack.mcmeta": {"pack": {"pack_format": 48, "description": "Cobblers scene runtime (generated by tools/scenes_pack.py)"}},
             "data/minecraft/tags/function/load.json": {"values": ["%s:scenes/load" % NS]},
             "data/minecraft/tags/function/tick.json": {"values": ["%s:scenes/tick" % NS]}}
    fn = lambda rel: "data/%s/function/scenes/%s.mcfunction" % (NS, rel)
    files[fn("load")] = ["scoreboard objectives add %s dummy" % PID, "scoreboard objectives add %s dummy" % CLOCK,
                         # a beat's q.run_command calls are top-level commands run as the player, so without these every
                         # one echoes "Running function ..." to operators' chat and the server log, once a second per
                         # player (the owner's first flight, 2026-09-24). Errors still show
                         "gamerule sendCommandFeedback false", "gamerule logAdminCommands false"]
    files[fn("tick")] = ["scoreboard players add #clock %s 1" % CLOCK,
                         "execute if score #clock %s matches %d.. run function %s:scenes/cycle" % (CLOCK, PERIOD, NS)]
    files[fn("pid")] = ["# a player's scene id: identity for owning actors, never quest state",
                        "scoreboard players add #next %s 1" % PID, "scoreboard players operation @s %s = #next %s" % (PID, PID)]
    files[fn("vanish")] = ["particle minecraft:large_smoke ~ ~0.5 ~ 0.25 0.35 0.25 0.01 10 force", "tp @s ~ -300 ~", "kill @s"]
    cycle = ["scoreboard players set #clock %s 0" % CLOCK, "scoreboard players add #beat %s 1" % CLOCK,
             "# an actor nobody refreshed since the last cycle: its owner left, logged off, or no longer qualifies",
             "execute as @e[tag=cobblers_actor,tag=!cobblers_fresh] at @s run function %s:scenes/vanish" % NS,
             "tag @e[tag=cobblers_actor,tag=cobblers_fresh] remove cobblers_fresh"]
    scenes, seen = [], set()
    for sdoc in doc["scenes"]:
        s = Scene(sdoc, quests, fields, convs)
        if s.id in seen:
            raise SceneError("duplicate scene %s" % s.id)
        seen.add(s.id)
        scenes.append(s)
        for rel, content in s.files().items():
            if rel.startswith("advancement:"):
                files["data/%s/advancement/scenes/%s.json" % (NS, rel.split(":", 1)[1])] = content
            else:
                files[fn("%s/%s" % (s.id, rel))] = content
        if s.doc.get("actors") or s.doc.get("effects") or s.doc.get("zones"):
            cycle.append("execute as @a[%s] at @s run function %s:scenes/%s/beat" % (sel(s.area), NS, s.id))
        cycle += s.no_build(files, fn)
    files[fn("cycle")] = cycle
    return files, scenes


def write(files, out):
    out = Path(out)
    if out.exists():
        shutil.rmtree(out)
    for rel, content in files.items():
        f = out / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, list):
            text = "\n".join(content) + "\n"
        else:
            text = json.dumps(content, indent=2, ensure_ascii=False) + "\n"
        f.write_text(text, encoding="utf-8", newline="\n")


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--data", default=str(DATA))
    p.add_argument("--out", default=str(DEFAULT_OUT))
    p.add_argument("--check", action="store_true", help="build in memory and report; write nothing")
    a = p.parse_args(argv)
    files, scenes = build(Path(a.data))
    for s in scenes:
        print("%-28s actors %d  props %d  zones %d  effects %d  npcs %d  functions %d" % (
            s.id, len(s.doc.get("actors") or []), len(s.doc.get("props") or []), len(s.doc.get("zones") or []),
            len(s.doc.get("effects") or []), len(s.doc.get("npcs") or []), len(s.doc.get("functions") or {})))
    if a.check:
        return 0
    write(files, a.out)
    print("wrote %d files to %s" % (len(files), a.out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
