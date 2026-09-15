import subprocess, sys, json
from pathlib import Path
SRV = Path(__file__).with_name("srv.py")
colours = ["red", "blue", "green", "pink", "white", "yellow", "black"]
cmds = ["forceload add 3540 3170 3595 3225", "forceload add 3325 3315 3365 3355", "time set 1000",
        "gamerule doDaylightCycle false", "gamerule doMobSpawning false", "gamerule doPokemonSpawning false"]
trees = []
i = 0
for z in range(3178, 3218, 11):
    for x in range(3548, 3590, 11):
        c = colours[i % len(colours)]
        trees.append({"x": x, "y": 130, "z": z, "colour": c})
        cmds.append("place feature cobblemon:%s_apricorn_tree %d 130 %d" % (c, x, z))
        i += 1
# villager plot at the flat site near spawn (ground y118-119): three beds, bell, job sites
v = [
    "fill 3330 119 3325 3352 124 3345 minecraft:air",
    "fill 3330 118 3325 3352 118 3345 minecraft:stone_bricks",
    "setblock 3334 119 3328 minecraft:red_bed[facing=north,part=foot]", "setblock 3334 119 3327 minecraft:red_bed[facing=north,part=head]",
    "setblock 3336 119 3328 minecraft:red_bed[facing=north,part=foot]", "setblock 3336 119 3327 minecraft:red_bed[facing=north,part=head]",
    "setblock 3338 119 3328 minecraft:red_bed[facing=north,part=foot]", "setblock 3338 119 3327 minecraft:red_bed[facing=north,part=head]",
    "setblock 3340 119 3328 minecraft:red_bed[facing=north,part=foot]", "setblock 3340 119 3327 minecraft:red_bed[facing=north,part=head]",
    "setblock 3341 119 3335 minecraft:bell[attachment=floor]",
    "setblock 3346 119 3338 minecraft:lectern", "setblock 3346 119 3341 minecraft:composter", "setblock 3336 119 3341 minecraft:smithing_table",
    "summon minecraft:villager 3340 119 3336 {VillagerData:{profession:\"minecraft:none\",level:1,type:\"minecraft:plains\"},Inventory:[{id:\"minecraft:bread\",count:6}],Tags:[\"exp019\"]}",
    "summon minecraft:villager 3342 119 3336 {VillagerData:{profession:\"minecraft:none\",level:1,type:\"minecraft:plains\"},Inventory:[{id:\"minecraft:bread\",count:6}],Tags:[\"exp019\"]}",
    "summon minecraft:villager 3341 119 3338 {VillagerData:{profession:\"minecraft:none\",level:1,type:\"minecraft:plains\"},Inventory:[{id:\"minecraft:bread\",count:6}],Tags:[\"exp019\"]}",
]
cmds += v
json.dump(trees, open(Path(__file__).with_name("exp019_trees.json"), "w"), indent=1)
subprocess.run([sys.executable, str(SRV), "cmd"] + cmds, check=True)
