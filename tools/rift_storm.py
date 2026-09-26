#!/usr/bin/env python
"""The Rift's own storm, from data/rift_storm.json: thunder and lightning inside the Rift only.

Minecraft weather is one state for a whole dimension, so the Rift cannot have a real thunderstorm of its own. Its
biome already has no precipitation (it never rains inside the lip) and a dark sky; this pack adds the storm around each
player standing in the biome:

  storm/tick     once a period, for every player in the Rift: roll once
  storm/player   a strike, a rumble without a bolt, or nothing
  storm/strike   a marker thrown to a random surface point within max_range (spreadplayers), and a bolt there only if
                 the point is still in the Rift, on bare rock (the #cobblers:storm_ground tag), no player within
                 keep_clear_of_players and no Rift settlement within no_strike_margin; the marker is always removed

  python tools/rift_storm.py            # -> build/datapacks/cobblers_rift_storm (a world pack: it runs on its own)
"""
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "rift_storm.json"
OUT = ROOT / "build" / "datapacks" / "cobblers_rift_storm"
OBJ = "cobblers.storm"
TAG = "cobblers_storm"


def load(path=DATA):
    d = json.loads(Path(path).read_text(encoding="utf-8"))
    if d.get("schema") != "cobblers.rift-storm/1":
        raise SystemExit("%s: schema must be cobblers.rift-storm/1" % path)
    return d


def no_strike_boxes(d, placements):
    """(x0, z0, x1, z1) round each Rift settlement: its plan footprint, else 160 round its centre, plus the margin."""
    m = d["strike"]["no_strike_margin"]
    out = []
    for sid in d["strike"]["no_strike_settlements"]:
        s = placements["settlements"].get(sid)
        if s is None:
            raise SystemExit("data/rift_storm.json names %r, which data/placements.json has no settlement for" % sid)
        fp = ((s.get("plan") or {}).get("footprint") or {}).get("rect")
        if fp:
            x0, z0, x1, z1 = fp
        else:
            cx, cz = s["centre"][:2]
            x0, z0, x1, z1 = cx - 160, cz - 160, cx + 160, cz + 160
        out.append((x0 - m, z0 - m, x1 + m, z1 + m))
    return out


def files(d, placements):
    s = d["strike"]
    pc = d["per_check_percent"]
    biome = d["biome"]
    strike_hi = pc["strike"]
    rumble_hi = strike_hi + pc["rumble"]
    boxes = no_strike_boxes(d, placements)
    guard = ["execute as @e[type=minecraft:marker,tag=%s] if entity @s[x=%d,y=-64,z=%d,dx=%d,dy=640,dz=%d] run kill @s"
             % (TAG, x0, z0, x1 - x0, z1 - z0) for x0, z0, x1, z1 in boxes]
    fn = {
        "storm/load": ["scoreboard objectives add %s dummy" % OBJ,
                       "schedule function cobblers:storm/tick %dt replace" % d["period_ticks"]],
        "storm/tick": ["execute as @a[gamemode=!spectator] at @s if biome ~ ~ ~ %s run function cobblers:storm/player" % biome,
                       "schedule function cobblers:storm/tick %dt replace" % d["period_ticks"]],
        "storm/player": ["execute store result score @s %s run random value 1..100" % OBJ,
                         "execute if score @s %s matches 1..%d run function cobblers:storm/strike" % (OBJ, strike_hi),
                         "execute if score @s %s matches %d..%d run playsound %s weather @s ~ ~ ~ %s %s"
                         % (OBJ, strike_hi + 1, rumble_hi, d["rumble_sound"], d["rumble_volume"], 0.7)],
        "storm/strike": ["# runs as and at one player in the Rift",
                         "summon minecraft:marker ~ ~ ~ {Tags:[\"%s\"]}" % TAG,
                         "spreadplayers ~ ~ 1 %d false @e[type=minecraft:marker,tag=%s,limit=1,sort=nearest]" % (s["max_range"], TAG)]
                        + guard
                        + ["execute as @e[type=minecraft:marker,tag=%s] at @s unless biome ~ ~ ~ %s run kill @s" % (TAG, biome),
                           "execute as @e[type=minecraft:marker,tag=%s] at @s unless block ~ ~-1 ~ #cobblers:storm_ground run kill @s" % TAG,
                           "execute as @e[type=minecraft:marker,tag=%s] at @s if entity @a[distance=..%d] run kill @s"
                           % (TAG, s["keep_clear_of_players"]),
                           "execute at @e[type=minecraft:marker,tag=%s] run summon minecraft:lightning_bolt ~ ~ ~" % TAG,
                           "kill @e[type=minecraft:marker,tag=%s]" % TAG],
    }
    out = {"data/cobblers/function/%s.mcfunction" % k: "\n".join(v) + "\n" for k, v in fn.items()}
    # a mod block is optional in the tag: one missing id would fail the whole tag, and every check that names it
    out["data/cobblers/tags/block/storm_ground.json"] = json.dumps({"values": [
        b if b.startswith("minecraft:") else {"id": b, "required": False} for b in s["ground"]]}, indent=2) + "\n"
    out["data/minecraft/tags/function/load.json"] = json.dumps({"values": ["cobblers:storm/load"]}, indent=2) + "\n"
    out["pack.mcmeta"] = json.dumps({"pack": {"pack_format": 48, "description": "Cobblers: the Rift's own storm "
                                              "(tools/rift_storm.py)"}}, indent=2) + "\n"
    return out


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--out", default=str(OUT))
    a = p.parse_args(argv)
    d = load()
    placements = json.loads((ROOT / "data" / "placements.json").read_text(encoding="utf-8"))
    out = Path(a.out)
    if out.exists():
        shutil.rmtree(out)
    for rel, text in files(d, placements).items():
        f = out / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(text, encoding="utf-8", newline="\n")
    print("wrote %s: %d no-strike boxes" % (out, len(no_strike_boxes(d, placements))))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
