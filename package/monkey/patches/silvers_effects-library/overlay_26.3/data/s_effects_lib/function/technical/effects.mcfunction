# Monkey SMP: a mob that never had one of these effects has none of the scores below, so no command in this
# function can match it; skip it with one command instead of 97. This ran for every loaded mob on every tick
# and went past Minecraft's 65,536-commands limit. Players always run it all: the last line re-arms their tick.
execute if entity @s[type=!minecraft:player] unless score @s s_effects_lib+batrachotoxin_duration matches -2147483648..2147483647 unless score @s s_effects_lib+bleed_duration matches -2147483648..2147483647 unless score @s s_effects_lib+electrify_duration matches -2147483648..2147483647 unless score @s s_effects_lib+eternal_flame_duration matches -2147483648..2147483647 unless score @s s_effects_lib+fatal_bleed_duration matches -2147483648..2147483647 unless score @s s_effects_lib+fatal_poison_duration matches -2147483648..2147483647 unless score @s s_effects_lib+frostbite_duration matches -2147483648..2147483647 unless score @s s_effects_lib+hypothermia_duration matches -2147483648..2147483647 unless score @s s_effects_lib+infection_duration matches -2147483648..2147483647 unless score @s s_effects_lib+invulnerability_duration matches -2147483648..2147483647 unless score @s s_effects_lib+lesser_stun_duration matches -2147483648..2147483647 unless score @s s_effects_lib+lethal_frostbite_duration matches -2147483648..2147483647 unless score @s s_effects_lib+nyctophobia_affected_duration matches -2147483648..2147483647 unless score @s s_effects_lib+nyctophobia_duration matches -2147483648..2147483647 unless score @s s_effects_lib+paralysis_duration matches -2147483648..2147483647 unless score @s s_effects_lib+rage_duration matches -2147483648..2147483647 unless score @s s_effects_lib+stun_duration matches -2147483648..2147483647 unless score @s s_effects_lib+undead_curse_duration matches -2147483648..2147483647 unless score @s s_effects_lib+vulnerability_duration matches -2147483648..2147483647 run return 0

# Effects:
## Bleed:
execute as @s[scores={s_effects_lib+bleed_duration=1..}] at @s anchored eyes positioned ^ ^ ^ positioned ~ ~-0.75 ~ run particle minecraft:item{"item":"minecraft:nether_bricks"} ~ ~ ~ 0.25 0.25 0.25 0.05 1 normal

execute as @s[type=minecraft:player,scores={s_effects_lib+damage_interval=9,s_effects_lib+bleed_duration=1..}] at @s run damage @s 3 s_effects_lib:bleed

execute as @s[type=!minecraft:player,type=!#silvers_tags:ignored_entities,scores={s_effects_lib+bleed_duration=1..}] at @s run damage @s 3 s_effects_lib:bleed



## Fatal Bleed:
execute as @s[scores={s_effects_lib+fatal_bleed_duration=1..}] at @s anchored eyes positioned ^ ^ ^ positioned ~ ~-0.75 ~ run particle minecraft:item{"item":"minecraft:nether_wart_block"} ~ ~ ~ 0.25 0.25 0.25 0.05 1 normal

execute as @s[type=minecraft:player,scores={s_effects_lib+damage_interval=3,s_effects_lib+fatal_bleed_duration=1..}] at @s run damage @s 3 s_effects_lib:fatal_bleed
execute as @s[type=minecraft:player,scores={s_effects_lib+damage_interval=8,s_effects_lib+fatal_bleed_duration=1..}] at @s run damage @s 3 s_effects_lib:fatal_bleed

execute as @s[type=!minecraft:player,type=!#silvers_tags:ignored_entities,scores={s_effects_lib+fatal_bleed_duration=1..}] at @s run damage @s 3 s_effects_lib:fatal_bleed



## Frostbite:
execute as @s[scores={s_effects_lib+frostbite_duration=1..}] at @s anchored eyes positioned ^ ^ ^ positioned ~ ~-0.75 ~ run particle minecraft:item{"item":"minecraft:packed_ice"} ~ ~ ~ 0.25 0.35 0.25 0 1 normal

execute as @s[type=minecraft:player,scores={s_effects_lib+damage_interval=7,s_effects_lib+frostbite_duration=1..}] at @s unless biome ~ ~ ~ #s_effects_lib:frostbite_dangerous_biomes run damage @s 3 s_effects_lib:frostbite
execute as @s[type=minecraft:player,scores={s_effects_lib+damage_interval=7,s_effects_lib+frostbite_duration=1..}] at @s if biome ~ ~ ~ #s_effects_lib:frostbite_dangerous_biomes run damage @s 5 s_effects_lib:frostbite

execute as @s[type=!minecraft:player,type=!#silvers_tags:ignored_entities,scores={s_effects_lib+frostbite_duration=1..}] at @s unless biome ~ ~ ~ #s_effects_lib:frostbite_dangerous_biomes run damage @s 3 s_effects_lib:frostbite
execute as @s[type=!minecraft:player,type=!#silvers_tags:ignored_entities,scores={s_effects_lib+frostbite_duration=1..}] at @s if biome ~ ~ ~ #s_effects_lib:frostbite_dangerous_biomes run damage @s 5 s_effects_lib:frostbite



## Lethal Frostbite:
execute as @s[scores={s_effects_lib+lethal_frostbite_duration=1..}] at @s anchored eyes positioned ^ ^ ^ positioned ~ ~-0.75 ~ run particle minecraft:item{"item":"minecraft:blue_ice"} ~ ~ ~ 0.25 0.35 0.25 0 1 normal
execute as @s[scores={s_effects_lib+lethal_frostbite_duration=1..}] at @s anchored eyes positioned ^ ^ ^ positioned ~ ~-0.8 ~ run particle minecraft:snowflake ~ ~ ~ 0 0.2 0 0.05 1 normal

execute as @s[type=minecraft:player,scores={s_effects_lib+damage_interval=4,s_effects_lib+lethal_frostbite_duration=1..}] at @s unless biome ~ ~ ~ #s_effects_lib:frostbite_dangerous_biomes run damage @s 3 s_effects_lib:lethal_frostbite
execute as @s[type=minecraft:player,scores={s_effects_lib+damage_interval=8,s_effects_lib+lethal_frostbite_duration=1..}] at @s unless biome ~ ~ ~ #s_effects_lib:frostbite_dangerous_biomes run damage @s 3 s_effects_lib:lethal_frostbite
execute as @s[type=minecraft:player,scores={s_effects_lib+damage_interval=4,s_effects_lib+lethal_frostbite_duration=1..}] at @s if biome ~ ~ ~ #s_effects_lib:frostbite_dangerous_biomes run damage @s 5 s_effects_lib:lethal_frostbite
execute as @s[type=minecraft:player,scores={s_effects_lib+damage_interval=8,s_effects_lib+lethal_frostbite_duration=1..}] at @s if biome ~ ~ ~ #s_effects_lib:frostbite_dangerous_biomes run damage @s 5 s_effects_lib:lethal_frostbite

execute as @s[type=!minecraft:player,type=!#silvers_tags:ignored_entities,scores={s_effects_lib+lethal_frostbite_duration=1..}] at @s unless biome ~ ~ ~ #s_effects_lib:frostbite_dangerous_biomes run damage @s 3 s_effects_lib:lethal_frostbite
execute as @s[type=!minecraft:player,type=!#silvers_tags:ignored_entities,scores={s_effects_lib+lethal_frostbite_duration=1..}] at @s if biome ~ ~ ~ #s_effects_lib:frostbite_dangerous_biomes run damage @s 3 s_effects_lib:lethal_frostbite



## Electrify:
execute as @s[scores={s_effects_lib+electrify_duration=1..}] at @s anchored eyes positioned ^ ^ ^ positioned ~ ~-0.75 ~ run particle minecraft:electric_spark ~ ~ ~ 0.25 0.35 0.25 0 5 normal

execute as @s[type=minecraft:player,scores={s_effects_lib+damage_interval=6,s_effects_lib+electrify_duration=1..}] at @s unless predicate s_effects_lib:electrify_check run damage @s 3 s_effects_lib:electrify
execute as @s[type=minecraft:player,scores={s_effects_lib+damage_interval=6,s_effects_lib+electrify_duration=1..}] at @s if predicate s_effects_lib:electrify_check run damage @s 5 s_effects_lib:electrify

execute as @s[type=!minecraft:player,type=!#silvers_tags:ignored_entities,scores={s_effects_lib+electrify_duration=1..}] at @s unless predicate s_effects_lib:electrify_check run damage @s 3 s_effects_lib:electrify
execute as @s[type=!minecraft:player,type=!#silvers_tags:ignored_entities,scores={s_effects_lib+electrify_duration=1..}] at @s if predicate s_effects_lib:electrify_check run damage @s 5 s_effects_lib:electrify



## Stun:
execute as @s[scores={s_effects_lib+stun_duration=1..}] at @s anchored eyes positioned ^ ^ ^ positioned ~ ~0.15 ~ run particle minecraft:crit ~ ~ ~ 0.15 0 0.15 0 15 normal

execute as @s[type=minecraft:player,scores={s_effects_lib+stun_duration=1..}] at @s anchored eyes positioned ^ ^ ^ positioned ~ ~-0.1 ~ unless entity @e[type=minecraft:marker,tag=s_effects_lib+Stun_Marker,distance=..2] run function s_effects_lib:technical/random/stun/summon
execute as @s[type=minecraft:player,scores={s_effects_lib+stun_duration=1..}] at @s anchored eyes positioned ^ ^ ^ positioned ~ ~-0.6 ~ run summon minecraft:interaction ~ ~ ~ {width:0.5,height:0.85,response:1b,Tags:["s_effects_lib+Stun_Interaction"]}
execute as @s[type=minecraft:player,scores={s_effects_lib+stun_duration=1..}] at @s run tp @s @e[type=minecraft:marker,tag=s_effects_lib+Stun_Marker,sort=nearest,limit=1]
execute as @s[type=minecraft:player,scores={s_effects_lib+decreaser=3,s_effects_lib+stun_duration=0}] at @s run function s_effects_lib:technical/random/stun/kill


execute as @s[scores={s_effects_lib+stun_duration=1..}] at @s run attribute @s minecraft:block_interaction_range modifier add s_effects_lib:stun-block_interaction_range -999 add_value
execute as @s[scores={s_effects_lib+stun_duration=1..}] at @s run attribute @s minecraft:attack_damage modifier add s_effects_lib:stun-attack_damage -999 add_value
execute as @s[scores={s_effects_lib+stun_duration=1..},type=!minecraft:player] at @s run attribute @s minecraft:movement_speed modifier add s_effects_lib:stun-movement_speed -999 add_value
execute as @s[scores={s_effects_lib+stun_duration=1..},type=!minecraft:player] at @s run attribute @s minecraft:jump_strength modifier add s_effects_lib:stun-jump_strength -999 add_value
execute as @s[scores={s_effects_lib+stun_duration=..0}] at @s run attribute @s minecraft:block_interaction_range modifier remove s_effects_lib:stun-block_interaction_range
execute as @s[scores={s_effects_lib+stun_duration=..0}] at @s run attribute @s minecraft:attack_damage modifier remove s_effects_lib:stun-attack_damage
execute as @s[scores={s_effects_lib+stun_duration=..0}] at @s run attribute @s minecraft:movement_speed modifier remove s_effects_lib:stun-movement_speed
execute as @s[scores={s_effects_lib+stun_duration=..0}] at @s run attribute @s minecraft:jump_strength modifier remove s_effects_lib:stun-jump_strength



## Lesser Stun:
execute as @s[scores={s_effects_lib+lesser_stun_duration=1..}] at @s anchored eyes positioned ^ ^ ^ positioned ~ ~0.15 ~ run particle minecraft:crit ~ ~ ~ 0.15 0 0.15 0 15 normal

execute as @s[scores={s_effects_lib+lesser_stun_duration=1..}] at @s run attribute @s minecraft:movement_speed modifier add s_effects_lib:stun-movement_speed -999 add_value
execute as @s[scores={s_effects_lib+lesser_stun_duration=..0}] at @s run attribute @s minecraft:movement_speed modifier remove s_effects_lib:stun-movement_speed



## Paralysis:
execute as @s[scores={s_effects_lib+paralysis_duration=1..}] at @s anchored eyes positioned ^ ^ ^ positioned ~ ~-0.75 ~ run particle minecraft:effect{color:16776877} ~ ~ ~ 0.25 0.5 0.25 0 1 normal

execute as @s[scores={s_effects_lib+paralysis_duration=1..}] at @s run attribute @s minecraft:jump_strength modifier add s_effects_lib:stun-jump_strength -999 add_value
execute as @s[scores={s_effects_lib+paralysis_duration=..0}] at @s run attribute @s minecraft:jump_strength modifier remove s_effects_lib:stun-jump_strength



## Eternal Flame:
execute as @s[scores={s_effects_lib+eternal_flame_duration=1..}] at @s anchored eyes positioned ^ ^ ^ positioned ~ ~-0.75 ~ run particle minecraft:flame ~ ~ ~ 0.25 0.35 0.25 0 1 normal

execute as @s[scores={s_effects_lib+eternal_flame_duration=1..}] at @s anchored feet positioned ^ ^ ^ positioned ~ ~0.5 ~ run summon minecraft:block_display ~ ~ ~ {block_state:{id:"minecraft:fire",properties:{age:"0",east:"false",north:"false",south:"false",up:"false",west:"false"}},brightness:{block:15,sky:15},transformation:{left_rotation:[0.0f,0.0f,0.0f,1.0f],right_rotation:[0.0f,0.0f,0.0f,1.0f],scale:[1.0f,1.0f,1.0f],translation:[-0.5f,-0.5f,-0.5f]},view_range:2.0f,Tags:["s_effects_lib+Eternal_Flame-Block_Display"]}
execute as @s[scores={s_effects_lib+damage_interval=10,s_effects_lib+eternal_flame_duration=1..}] at @s unless biome ~ ~ ~ #s_effects_lib:eternal_flame_dangerous_biomes run damage @s 3 s_effects_lib:eternal_flame
execute as @s[scores={s_effects_lib+damage_interval=10,s_effects_lib+eternal_flame_duration=1..}] at @s if biome ~ ~ ~ #s_effects_lib:eternal_flame_dangerous_biomes run damage @s 5 s_effects_lib:eternal_flame

execute as @s[type=minecraft:player,scores={s_effects_lib+eternal_flame_duration=1..,s_effects_lib+Fire=..0}] at @s run function s_effects_lib:technical/random/eternal_flame/set_on_fire
execute as @s[type=!minecraft:player,scores={s_effects_lib+eternal_flame_duration=1..}] at @s run data modify entity @s Fire set value 20



## Rage:
execute as @s[scores={s_effects_lib+rage_duration=1..}] at @s anchored eyes positioned ^ ^ ^ positioned ~ ~-0.75 ~ run particle minecraft:instant_effect{color:8463910} ~ ~ ~ 0.25 0.35 0.25 0 1 normal
execute as @s[scores={s_effects_lib+rage_duration=1..}] at @s anchored eyes positioned ^ ^ ^ positioned ~ ~-0.75 ~ run particle minecraft:effect{color:8463910} ~ ~ ~ 0.2 0.35 0.2 0 1 normal

execute as @s[type=minecraft:player,scores={s_effects_lib+rage_duration=1..},nbt={HurtTime:9s}] at @s if predicate s_effects_lib:rage_chance run function s_effects_lib:technical/random/rage/increase
execute as @s[scores={s_effects_lib+rage_duration=..0}] at @s run scoreboard players set @s s_effects_lib+rage_stage 0
execute as @s[scores={s_effects_lib+rage_duration=1..,s_effects_lib+rage_stage=1..}] at @s run attribute @s minecraft:attack_damage modifier add s_effects_lib:rage-attack_damage-stage_1 0.05 add_multiplied_total
execute as @s[scores={s_effects_lib+rage_duration=1..,s_effects_lib+rage_stage=1..}] at @s run attribute @s minecraft:attack_damage modifier add s_effects_lib:rage-attack_damage-stage_2 0.05 add_multiplied_total
execute as @s[scores={s_effects_lib+rage_duration=1..,s_effects_lib+rage_stage=1..}] at @s run attribute @s minecraft:attack_damage modifier add s_effects_lib:rage-attack_damage-stage_3 0.05 add_multiplied_total
execute as @s[scores={s_effects_lib+rage_duration=1..,s_effects_lib+rage_stage=1..}] at @s run attribute @s minecraft:attack_damage modifier add s_effects_lib:rage-attack_damage-stage_4 0.05 add_multiplied_total
execute as @s[scores={s_effects_lib+rage_duration=1..,s_effects_lib+rage_stage=1..}] at @s run attribute @s minecraft:attack_damage modifier add s_effects_lib:rage-attack_damage-stage_5 0.05 add_multiplied_total
execute as @s[scores={s_effects_lib+rage_duration=..0}] at @s run attribute @s minecraft:attack_damage modifier remove s_effects_lib:rage-attack_damage-stage_1
execute as @s[scores={s_effects_lib+rage_duration=..0}] at @s run attribute @s minecraft:attack_damage modifier remove s_effects_lib:rage-attack_damage-stage_2
execute as @s[scores={s_effects_lib+rage_duration=..0}] at @s run attribute @s minecraft:attack_damage modifier remove s_effects_lib:rage-attack_damage-stage_3
execute as @s[scores={s_effects_lib+rage_duration=..0}] at @s run attribute @s minecraft:attack_damage modifier remove s_effects_lib:rage-attack_damage-stage_4
execute as @s[scores={s_effects_lib+rage_duration=..0}] at @s run attribute @s minecraft:attack_damage modifier remove s_effects_lib:rage-attack_damage-stage_5




## Invulnerability:
execute as @s[scores={s_effects_lib+invulnerability_duration=1..}] at @s anchored eyes positioned ^ ^ ^ positioned ~ ~-0.75 ~ run particle minecraft:effect{color:4673362} ~ ~ ~ 0.25 0.5 0.25 0 1 normal

execute as @s[scores={s_effects_lib+invulnerability_duration=1..},nbt={HurtTime:9s}] at @s run function s_effects_lib:technical/random/invulnerability/give_effect





## Vulnerability:
execute as @s[scores={s_effects_lib+vulnerability_duration=1..}] at @s anchored eyes positioned ^ ^ ^ positioned ~ ~-0.75 ~ run particle minecraft:effect{color:10329495} ~ ~ ~ 0.25 0.5 0.25 0 1 normal

execute as @s[scores={s_effects_lib+vulnerability_duration=1..},nbt={HurtTime:9s}] at @s if predicate s_effects_lib:vulnerability_check run effect clear @s minecraft:resistance





## Infection:
execute as @s[scores={s_effects_lib+infection_duration=1..}] at @s anchored eyes positioned ^ ^ ^ positioned ~ ~-0.75 ~ run particle minecraft:instant_effect{color:6051928} ~ ~ ~ 0.25 0.35 0.25 0 1 normal

execute as @s[type=minecraft:player,scores={s_effects_lib+infection_duration=1..},nbt={HurtTime:9s}] at @s if predicate s_effects_lib:infection_chance if biome ~ ~ ~ #s_effects_lib:hot_biomes run function s_effects_lib:technical/random/infestation/spawn/husks
execute as @s[type=minecraft:player,scores={s_effects_lib+infection_duration=1..},nbt={HurtTime:9s}] at @s if predicate s_effects_lib:infection_chance if biome ~ ~ ~ #s_effects_lib:water_biomes run function s_effects_lib:technical/random/infestation/spawn/drowned
execute as @s[type=minecraft:player,scores={s_effects_lib+infection_duration=1..},nbt={HurtTime:9s}] at @s if predicate s_effects_lib:infection_chance if dimension minecraft:the_nether run function s_effects_lib:technical/random/infestation/spawn/zombified_piglin
execute as @s[type=minecraft:player,scores={s_effects_lib+infection_duration=1..},nbt={HurtTime:9s}] at @s if predicate s_effects_lib:infection_chance unless biome ~ ~ ~ #s_effects_lib:hot_biomes unless biome ~ ~ ~ #s_effects_lib:water_biomes unless dimension minecraft:the_nether run function s_effects_lib:technical/random/infestation/spawn/zombie



## Batrachotoxin:
execute as @s[scores={s_effects_lib+batrachotoxin_duration=1..}] at @s anchored eyes positioned ^ ^ ^ positioned ~ ~-0.75 ~ run particle minecraft:effect{color:2142513} ~ ~ ~ 0.25 0.5 0.25 0 1 normal

execute as @s[scores={s_effects_lib+damage_interval=5,s_effects_lib+health=3..5,s_effects_lib+batrachotoxin_duration=1..}] at @s run damage @s 1 s_effects_lib:batrachotoxin
execute as @s[scores={s_effects_lib+damage_interval=5,s_effects_lib+health=6..17,s_effects_lib+batrachotoxin_duration=1..}] at @s run damage @s 2 s_effects_lib:batrachotoxin
execute as @s[scores={s_effects_lib+damage_interval=5,s_effects_lib+health=18..,s_effects_lib+batrachotoxin_duration=1..}] at @s run damage @s 5 s_effects_lib:batrachotoxin



## Fatal Poison:
execute as @s[scores={s_effects_lib+fatal_poison_duration=1..}] at @s anchored eyes positioned ^ ^ ^ positioned ~ ~-0.75 ~ run particle minecraft:effect{color:5149489} ~ ~ ~ 0.25 0.5 0.25 0 1 normal

execute as @s[scores={s_effects_lib+damage_interval=10,s_effects_lib+fatal_poison_duration=1..}] at @s run damage @s 3 s_effects_lib:fatal_poison



## Nyctophobia:
execute as @s[scores={s_effects_lib+nyctophobia_duration=1..}] at @s anchored eyes positioned ^ ^ ^ positioned ~ ~-0.75 ~ run particle minecraft:effect{color:5726303} ~ ~ ~ 0.25 0.5 0.25 0 1 normal

execute as @s[scores={s_effects_lib+nyctophobia_duration=1..}] at @s if predicate s_effects_lib:nyctophobia_check run effect give @s minecraft:darkness infinite 53 true
execute as @s[scores={s_effects_lib+nyctophobia_duration=1..}] at @s unless predicate s_effects_lib:nyctophobia_check if predicate s_effects_lib:has_nyctophobia_darkness run effect clear @s minecraft:darkness
execute as @s[scores={s_effects_lib+nyctophobia_duration=0}] at @s if predicate s_effects_lib:has_nyctophobia_darkness run effect clear @s minecraft:darkness

execute as @s[scores={s_effects_lib+nyctophobia_duration=1..}] at @s if predicate s_effects_lib:nyctophobia_check run scoreboard players add @s s_effects_lib+nyctophobia_affected_duration 1
execute as @s[scores={s_effects_lib+nyctophobia_duration=1..}] at @s unless predicate s_effects_lib:nyctophobia_check if predicate s_effects_lib:has_nyctophobia_darkness run scoreboard players set @s s_effects_lib+nyctophobia_affected_duration 0
execute as @s[scores={s_effects_lib+nyctophobia_duration=..0}] at @s if predicate s_effects_lib:has_nyctophobia_darkness run scoreboard players set @s s_effects_lib+nyctophobia_affected_duration 0

execute as @s[scores={s_effects_lib+nyctophobia_duration=1..,s_effects_lib+nyctophobia_affected_duration=50..}] at @s run effect give @s minecraft:blindness 5 0 false
execute as @s[scores={s_effects_lib+nyctophobia_duration=1..,s_effects_lib+damage_interval=9,s_effects_lib+nyctophobia_affected_duration=50..}] at @s run damage @s 3 s_effects_lib:nyctophobia


## Undead Curse:
execute as @s[scores={s_effects_lib+undead_curse_duration=1..}] at @s anchored eyes positioned ^ ^ ^ positioned ~ ~-0.75 ~ run particle minecraft:effect{color:2910253} ~ ~ ~ 0.25 0.5 0.25 0 1 normal

execute as @s[type=minecraft:player,scores={s_effects_lib+undead_curse_duration=1..,s_effects_lib+Fire=..0}] at @s if predicate s_effects_lib:undead_curse_check run function s_effects_lib:technical/random/eternal_flame/set_on_fire
execute as @s[type=!minecraft:player,scores={s_effects_lib+undead_curse_duration=1..}] at @s run data modify entity @s Fire set value 20



## Hypothermia:
execute as @s[scores={s_effects_lib+hypothermia_duration=1..}] at @s anchored eyes positioned ^ ^ ^ positioned ~ ~-0.75 ~ run particle minecraft:item{"item":"minecraft:blue_ice"} ~ ~ ~ 0.25 0.35 0.25 0 1 normal

execute as @s[type=minecraft:player,scores={s_effects_lib+damage_interval=7,s_effects_lib+hypothermia_duration=1..}] at @s if predicate s_effects_lib:hypothermia_check unless biome ~ ~ ~ #s_effects_lib:frostbite_dangerous_biomes run damage @s 3 s_effects_lib:hypothermia
execute as @s[type=minecraft:player,scores={s_effects_lib+damage_interval=7,s_effects_lib+hypothermia_duration=1..}] at @s if predicate s_effects_lib:hypothermia_check if biome ~ ~ ~ #s_effects_lib:frostbite_dangerous_biomes run damage @s 5 s_effects_lib:hypothermia

execute as @s[type=!minecraft:player,type=!#silvers_tags:ignored_entities,scores={s_effects_lib+hypothermia_duration=1..}] at @s if predicate s_effects_lib:hypothermia_check unless biome ~ ~ ~ #s_effects_lib:frostbite_dangerous_biomes run damage @s 3 s_effects_lib:hypothermia
execute as @s[type=!minecraft:player,type=!#silvers_tags:ignored_entities,scores={s_effects_lib+hypothermia_duration=1..}] at @s if predicate s_effects_lib:hypothermia_check if biome ~ ~ ~ #s_effects_lib:frostbite_dangerous_biomes run damage @s 5 s_effects_lib:hypothermia








# Ticking
advancement revoke @s only s_effects_lib:technical/effects
