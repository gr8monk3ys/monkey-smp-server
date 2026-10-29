advancement revoke @a only trident_all_weather_channeling:trident_hit_entity

# Monkey SMP patch (docs/MAINTAINING.md, "Patches this pack carries"). Runs as the player whose Channeling
# trident hit. Upstream struck every Channeling trident that had ever hit something; this marks only this
# player's own trident, still in flight and not handled before (its owner is checked, so another player's
# trident nearby is never picked). The strike waits a tick, in app/summon_lightning, so it runs from the server
# at the world spawn and can leave spawn out.
tag @s add tawc.attacker
execute as @e[type=minecraft:trident,distance=..128,tag=!tawc.done,nbt={DealtDamage:1b,inGround:0b,item:{components:{"minecraft:enchantments":{"minecraft:channeling":1}}}}] \
  at @s on owner if entity @s[tag=tawc.attacker] \
    run tag @e[type=minecraft:trident,tag=!tawc.done,distance=..0.01,limit=1] add tawc.hit
tag @s remove tawc.attacker
schedule function trident_all_weather_channeling:app/summon_lightning 1t replace
