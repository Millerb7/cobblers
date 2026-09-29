#!/usr/bin/env python
"""The Celebi asleep in Route 1's world-tree sapling, and its wake, from data/sapling_celebi.json.

EXP-023 candidate A: a Pokemon entity with the flags that experiment proved (not battleable, immobile, asleep,
unlabelled, never despawning). The one thing it could not give is damage immunity: Cobblemon ignores Invulnerable and
a sword killed it. So the branch is walled in barrier blocks, invisible and solid: a melee hit, an arrow or a thrown
ball stops at the barrier, and the Celebi is still seen through it.

Cobblemon's spawn command does nothing when a plainly parsed function runs it (measured on staging 2026-09-25:
`spawnpokemonat` from the console spawned the Celebi, the same line in a function spawned nothing, and vanilla
`summon` refuses cobblemon:pokemon). So the Celebi is summoned over RCON by the re-application (placement_steps,
tools/reapply.py R14C), and the pack does what functions can:

  celebi/shell      the barrier blocks round the branch (they replace air only), unless it is already awake
  celebi/dress_new  the flags, the tag, the branch and the heading, on the Celebi just summoned
  celebi/keeper     every period_ticks, while a player is within player_radius: celebi/near
  celebi/near       WHILE IT SLEEPS: keep it, and watch for the wake. Awake, this loop does nothing at all.
  celebi/keep       remove a second Celebi (a load race) and put it back on its branch if anything moved it
  celebi/wake_check the wake trigger: a player past the gate, within wake.radius, holding wake.item
  celebi/wake       hand off to cobblers:legendary/celebi_wake/open (which owns the gate), then advise on the cap

THE TWO FAULTS THIS FILE CLOSES (docs/mechanics/CELEBI_WAKE.md, docs/NIGHT_REVIEW.md 2026-09-29)

  The keeper.  celebi/keep teleports the Celebi back onto its branch every period_ticks. That is right while it
    sleeps and wrong the moment it wakes: a woken Celebi is meant to be fought and caught, and a keeper that snaps
    it home every two seconds pins it through its own encounter. The keeper now stands down on an awake score, which
    celebi/dress sets back to 0 whenever a fresh dormant Celebi is installed, so the flag cannot outlive the entity.
    (It never re-merged the dormant NBT, which is what NIGHT_REVIEW recorded; the fault is the teleport.)

  The level and `uncatchable`.  data/level_cap.json refuses a catch strictly above the thrower's RCT cap, a Master
    Ball included, so the old level 70 was uncatchable at any gate this campaign has. The level is data; see
    data/sapling_celebi.json level_why. `uncatchable` is off the spawn for a harder reason: it is stored in the
    Pokemon's own data and nothing verified clears it on a spawned entity, so it would survive the wake.

  python tools/sapling_celebi.py                 # -> build/datapacks/cobblers_celebi (a world pack: it runs on its own)
"""
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "sapling_celebi.json"
OUT = ROOT / "build" / "datapacks" / "cobblers_celebi"
TAG = "cobblers_celebi"
OBJ = "cobblers.celebi"
# the awake flag: a fake-player score on this pack's own objective. tools/legendaries.py sets it when the wake opens
# and reads these two helpers rather than spelling the holder out again.
AWAKE = "#awake"
WAKE_FN = "cobblers:legendary/celebi_wake/open"


def awake_set(value):
    return "scoreboard players set %s %s %d" % (AWAKE, OBJ, int(value))


def awake_if(value):
    return "score %s %s matches %d" % (AWAKE, OBJ, int(value))


def load(path=DATA):
    d = json.loads(Path(path).read_text(encoding="utf-8"))
    if d.get("schema") != "cobblers.sapling-celebi/1":
        raise SystemExit("%s: schema must be cobblers.sapling-celebi/1" % path)
    if "uncatchable" in d.get("spawn_properties", []):
        raise SystemExit("%s: `uncatchable` cannot be cleared on a spawned Pokemon, so the wake could never make "
                         "this Celebi catchable (data/sapling_celebi.json spawn_properties_why)" % path)
    return d


def _at(d):
    return "%s %s %s" % tuple(d["position"])


def shell_box(d):
    """(x0, y0, z0, x1, y1, z1): the barrier box, the Celebi's block and the one above it left open inside it."""
    x, y, z = (int(v // 1) for v in d["position"])
    return x - 1, y - 1, z - 1, x + 1, y + 2, z + 1


def placement_steps(d):
    """The re-application's actions: load the branch, wall it, summon the Celebi over RCON if none stands there
    (tagged or not, so a run never stacks a second), dress it, release the chunk."""
    x, _y, z = (int(v // 1) for v in d["position"])
    at = _at(d)
    return [("cmd", "forceload add %d %d" % (x, z)), ("wait", 3),
            ("fn", "cobblers:celebi/shell"),
            ("cmd", "execute unless entity @e[tag=%s] positioned %s unless entity @e[type=cobblemon:pokemon,distance=..3] "
                    "run spawnpokemonat %s %s level=%d %s" % (TAG, at, at, d["species"], d["level"], " ".join(d["spawn_properties"]))),
            ("wait", 1),
            ("fn", "cobblers:celebi/dress_new"),
            ("cmd", "forceload remove %d %d" % (x, z))]


def wake_selector(d):
    """The players who wake it: past the gate, within wake.radius, holding wake.item in the main hand.

    `SelectedItem` is the player's main-hand stack in vanilla player data; the advancement predicate is the same
    per-player flag every legendary gate uses (tools/progression_pack.py writes cobblers:flag/<id>).
    """
    w = d["wake"]
    adv = ",".join("cobblers:flag/%s=true" % f for f in w["gate_flags"])
    return ("@a[distance=..%d,advancements={%s},nbt={SelectedItem:{id:\"%s\"}},limit=1,sort=nearest]"
            % (int(w["radius"]), adv, w["item"]))


def files(d):
    at = _at(d)
    yaw = d["yaw"]
    k = d["keeper"]
    w = d["wake"]
    nbt = ",".join("%s:%s" % (key, v) for key, v in d["nbt"].items())
    x, y, z = (int(v // 1) for v in d["position"])
    x0, y0, z0, x1, y1, z1 = shell_box(d)
    cap_msg = json.dumps({"text": "Your level cap is below %d: a %s that strong breaks free from every ball, a "
                                  "Master Ball included. Come back when the League has raised it."
                                  % (d["level"], d["species"].capitalize()), "color": "red"}, ensure_ascii=False)
    out = {
        "celebi/load": ["scoreboard objectives add %s dummy" % OBJ,
                        "# NOT reset here: a restart must not put a woken Celebi back to sleep. celebi/dress owns it.",
                        "schedule function cobblers:celebi/keeper %dt replace" % k["period_ticks"]],
        "celebi/shell": ["# Generated by tools/sapling_celebi.py: barriers round the branch; the Celebi's own column stays open",
                         "# chunks-loaded-by: tools/reapply.py R14C (forceload add over RCON before this runs)",
                         "# a re-application on a world where the wake already happened must not wall the woken",
                         "# Celebi back in - but if it is gone (caught, killed), the dormant one R14C summons next",
                         "# needs its shell, so the entity has to be there too",
                         "execute if %s if entity @e[tag=%s] run return 0" % (awake_if(1), TAG),
                         "fill %d %d %d %d %d %d minecraft:barrier replace minecraft:air" % (x0, y0, z0, x1, y1, z1),
                         "fill %d %d %d %d %d %d minecraft:air replace minecraft:barrier" % (x, y, z, x, y + 1, z)],
        "celebi/dress_new": ["execute positioned %s as @e[type=cobblemon:pokemon,tag=!%s,distance=..2,limit=1,sort=nearest] "
                             "run function cobblers:celebi/dress" % (at, TAG)],
        "celebi/dress": ["data merge entity @s {%s}" % nbt,
                         "tag @s add %s" % TAG,
                         "tp @s %s %s 0" % (at, yaw),
                         "# this Celebi is dormant by construction, so the awake flag describes it again",
                         awake_set(0)],
        "celebi/keeper": ["execute positioned %s if entity @a[distance=..%d] run function cobblers:celebi/near"
                          % (at, k["player_radius"]),
                          "schedule function cobblers:celebi/keeper %dt replace" % k["period_ticks"]],
        "celebi/near": ["# WHILE IT SLEEPS ONLY. A woken Celebi is an ordinary wild Pokemon: keeping it would teleport",
                        "# it off the battle the wake exists to give, every %d ticks." % k["period_ticks"],
                        "execute if %s run return 0" % awake_if(1),
                        "function cobblers:celebi/keep",
                        "function cobblers:celebi/wake_check"],
        "celebi/keep": ["execute store result score #n %s if entity @e[tag=%s]" % (OBJ, TAG),
                        "execute if score #n %s matches 2.. run kill @e[tag=%s,limit=1,sort=random]" % (OBJ, TAG),
                        "execute as @e[tag=%s] positioned %s unless entity @s[distance=..%s] run tp @s %s %s 0"
                        % (TAG, at, k["home_tolerance"], at, yaw)],
        "celebi/wake_check": ["# The wake (docs/mechanics/CELEBI_WAKE.md): a STATE CHECK, never an advancement trigger.",
                              "# An advancement fires once per player for ever and cannot test another advancement, so a",
                              "# player who tried the item before the gate opened would have burned it; and the barrier",
                              "# shell seals every face of the branch, so the block cannot be used on at all.",
                              "execute positioned %s as %s run function cobblers:celebi/wake" % (at, wake_selector(d))],
        "celebi/wake": ["# run as the waking player. The badge gate lives in %s, which is the authority." % WAKE_FN,
                        "# chunks-loaded-by: the waking player, who stands within %d blocks of the shell it opens"
                        % int(w["radius"]),
                        "function %s" % WAKE_FN,
                        "# open refused (the gate): say nothing at all, and let them try again later",
                        "execute if %s run return 0" % awake_if(0),
                        "function cobblers:celebi/cap_advice {x:\"\"}"],
        "celebi/cap_advice": ["# $(x) is empty: this line is a macro only so rctmod's command is parsed when it runs.",
                              "# A mod's command written plainly in a function may be parsed at server start before it",
                              "# is usable (.claude/rules/datapacks.md, EXP-046).",
                              "scoreboard players set @s %s 0" % OBJ,
                              "$execute store result score @s %s run rctmod player get level_cap @s$(x)" % OBJ,
                              "# a cap that did not read (0) says nothing: data/level_cap.json lets that catch through",
                              "execute if score @s %s matches 1..%d run tellraw @s %s" % (OBJ, d["level"] - 1, cap_msg)],
    }
    return {"data/cobblers/function/%s.mcfunction" % n: "\n".join(v) + "\n" for n, v in out.items()} | {
        "data/minecraft/tags/function/load.json": json.dumps({"values": ["cobblers:celebi/load"]}, indent=2) + "\n",
        "pack.mcmeta": json.dumps({"pack": {"pack_format": 48, "description": "Cobblers: the sleeping Celebi in the Route 1 "
                                            "sapling and its wake (tools/sapling_celebi.py)"}}, indent=2) + "\n"}


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--out", default=str(OUT))
    a = p.parse_args(argv)
    d = load()
    out = Path(a.out)
    if out.exists():
        shutil.rmtree(out)
    for rel, text in files(d).items():
        f = out / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(text, encoding="utf-8", newline="\n")
    print("wrote %s: a %s level %d at %s, walled in %s, kept every %d ticks while it sleeps, woken by %s within %d"
          % (out, d["species"], d["level"], d["position"], shell_box(d), d["keeper"]["period_ticks"],
             d["wake"]["item"], d["wake"]["radius"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
