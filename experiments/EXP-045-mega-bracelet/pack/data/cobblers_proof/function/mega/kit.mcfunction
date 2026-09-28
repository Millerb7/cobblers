# EXP-045 (staging only): as the player. The bracelet, two Mega Stones and their Pokemon, at the Hometown Center.
# Items from Mega Showdown 1.0.2 (mega_showdown-fabric-1.0.2+1.8+1.21.1-release.jar: item ids, the accessories
# mega_slot tag that holds the bracelet).
gamemode survival @s
tp @s 1440 120 5248 -120 0
give @s mega_showdown:mega_bracelet
give @s mega_showdown:lucarionite
give @s mega_showdown:charizardite_x
pokegive lucario level=50
pokegive charizard level=50
tellraw @s {"text": "EXP-045 kit: put the Mega Bracelet in its accessory slot, give Lucario the Lucarionite (sneak and use it on Lucario once it is out), then /function cobblers_proof:mega/opponent and battle.", "color": "gold"}
