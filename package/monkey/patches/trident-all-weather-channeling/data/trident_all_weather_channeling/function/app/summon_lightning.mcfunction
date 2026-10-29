# Monkey SMP patch (docs/MAINTAINING.md, "Patches this pack carries"). Scheduled by app/trident_hit_entity, so
# it runs from the server: in the Overworld, at the world spawn. Lightning isn't damage a player causes, so
# neither PvP grace nor the spawn claim stops it (rule 26). So no strike within 64 blocks of spawn (at any
# height), or within 6 blocks of a player in grace; elsewhere the marked tridents are struck as upstream did.
tag @e[type=minecraft:trident,tag=tawc.hit] add tawc.done
execute positioned ~-64 -64 ~-64 as @e[type=minecraft:trident,tag=tawc.hit,dx=128,dy=384,dz=128] run tag @s remove tawc.hit
execute as @e[type=minecraft:trident,tag=tawc.hit] at @s as @a[distance=..6] \
  if items entity @s armor.body *[custom_data~{monkey_grace:{}}] \
    run tag @e[type=minecraft:trident,tag=tawc.hit,distance=..0.01,limit=1] remove tawc.hit
execute as @e[type=minecraft:trident,tag=tawc.hit] at @s run summon minecraft:lightning_bolt ~ ~ ~
execute as @e[type=minecraft:trident,tag=tawc.hit] at @s run playsound minecraft:item.trident.thunder ambient @a[distance=..50] ~ ~ ~ 1 1 1
tag @e[type=minecraft:trident,tag=tawc.hit] remove tawc.hit
