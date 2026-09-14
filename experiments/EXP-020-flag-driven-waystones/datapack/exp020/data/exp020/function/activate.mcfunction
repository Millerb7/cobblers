waystones activate @a 3340 119 3330
waystones forget @a 3340 119 3330
waystones forget @a all
execute as @a if entity @s[advancements={exp020:flag/gym1=true}] run waystones activate @s 3340 119 3330
