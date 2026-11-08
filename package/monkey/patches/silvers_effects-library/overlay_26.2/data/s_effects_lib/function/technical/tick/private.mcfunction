# Monkey SMP patch (docs/MAINTAINING.md, "Patches this pack carries"): upstream ran 2 world-wide @e scans for the
# stun interactions and 18 for the eternal flame block displays every tick, one per lifetime step. Each is now one
# pass that runs this function again as that entity: the lines just below are upstream's lines for one entity,
# in upstream's order.
# Interaction Lifetime (run as one stun interaction)
execute if entity @s[type=minecraft:interaction,tag=s_effects_lib+Stun_Interaction] run scoreboard players add @s s_effects_lib+stun_interaction_lifetime 1
execute if entity @s[type=minecraft:interaction,tag=s_effects_lib+Stun_Interaction,scores={s_effects_lib+stun_interaction_lifetime=15..}] run kill @s

# Eternal Flame Lifetime (run as one eternal flame block display)
execute if entity @s[type=minecraft:block_display,tag=s_effects_lib+Eternal_Flame-Block_Display] run scoreboard players add @s s_effects_lib+eternal_flame_lifetime 1
execute if entity @s[type=minecraft:block_display,tag=s_effects_lib+Eternal_Flame-Block_Display,scores={s_effects_lib+eternal_flame_lifetime=1}] run data merge entity @s {block_state:{Properties:{age:"0",east:"false",north:"false",south:"false",up:"false",west:"false"}}}
execute if entity @s[type=minecraft:block_display,tag=s_effects_lib+Eternal_Flame-Block_Display,scores={s_effects_lib+eternal_flame_lifetime=2}] run data merge entity @s {block_state:{Properties:{age:"1",east:"false",north:"false",south:"false",up:"false",west:"false"}}}
execute if entity @s[type=minecraft:block_display,tag=s_effects_lib+Eternal_Flame-Block_Display,scores={s_effects_lib+eternal_flame_lifetime=3}] run data merge entity @s {block_state:{Properties:{age:"2",east:"false",north:"false",south:"false",up:"false",west:"false"}}}
execute if entity @s[type=minecraft:block_display,tag=s_effects_lib+Eternal_Flame-Block_Display,scores={s_effects_lib+eternal_flame_lifetime=4}] run data merge entity @s {block_state:{Properties:{age:"3",east:"false",north:"false",south:"false",up:"false",west:"false"}}}
execute if entity @s[type=minecraft:block_display,tag=s_effects_lib+Eternal_Flame-Block_Display,scores={s_effects_lib+eternal_flame_lifetime=5}] run data merge entity @s {block_state:{Properties:{age:"4",east:"false",north:"false",south:"false",up:"false",west:"false"}}}
execute if entity @s[type=minecraft:block_display,tag=s_effects_lib+Eternal_Flame-Block_Display,scores={s_effects_lib+eternal_flame_lifetime=6}] run data merge entity @s {block_state:{Properties:{age:"5",east:"false",north:"false",south:"false",up:"false",west:"false"}}}
execute if entity @s[type=minecraft:block_display,tag=s_effects_lib+Eternal_Flame-Block_Display,scores={s_effects_lib+eternal_flame_lifetime=7}] run data merge entity @s {block_state:{Properties:{age:"6",east:"false",north:"false",south:"false",up:"false",west:"false"}}}
execute if entity @s[type=minecraft:block_display,tag=s_effects_lib+Eternal_Flame-Block_Display,scores={s_effects_lib+eternal_flame_lifetime=8}] run data merge entity @s {block_state:{Properties:{age:"7",east:"false",north:"false",south:"false",up:"false",west:"false"}}}
execute if entity @s[type=minecraft:block_display,tag=s_effects_lib+Eternal_Flame-Block_Display,scores={s_effects_lib+eternal_flame_lifetime=9}] run data merge entity @s {block_state:{Properties:{age:"8",east:"false",north:"false",south:"false",up:"false",west:"false"}}}
execute if entity @s[type=minecraft:block_display,tag=s_effects_lib+Eternal_Flame-Block_Display,scores={s_effects_lib+eternal_flame_lifetime=10}] run data merge entity @s {block_state:{Properties:{age:"9",east:"false",north:"false",south:"false",up:"false",west:"false"}}}
execute if entity @s[type=minecraft:block_display,tag=s_effects_lib+Eternal_Flame-Block_Display,scores={s_effects_lib+eternal_flame_lifetime=11}] run data merge entity @s {block_state:{Properties:{age:"10",east:"false",north:"false",south:"false",up:"false",west:"false"}}}
execute if entity @s[type=minecraft:block_display,tag=s_effects_lib+Eternal_Flame-Block_Display,scores={s_effects_lib+eternal_flame_lifetime=12}] run data merge entity @s {block_state:{Properties:{age:"11",east:"false",north:"false",south:"false",up:"false",west:"false"}}}
execute if entity @s[type=minecraft:block_display,tag=s_effects_lib+Eternal_Flame-Block_Display,scores={s_effects_lib+eternal_flame_lifetime=13}] run data merge entity @s {block_state:{Properties:{age:"12",east:"false",north:"false",south:"false",up:"false",west:"false"}}}
execute if entity @s[type=minecraft:block_display,tag=s_effects_lib+Eternal_Flame-Block_Display,scores={s_effects_lib+eternal_flame_lifetime=14}] run data merge entity @s {block_state:{Properties:{age:"13",east:"false",north:"false",south:"false",up:"false",west:"false"}}}
execute if entity @s[type=minecraft:block_display,tag=s_effects_lib+Eternal_Flame-Block_Display,scores={s_effects_lib+eternal_flame_lifetime=15}] run data merge entity @s {block_state:{Properties:{age:"14",east:"false",north:"false",south:"false",up:"false",west:"false"}}}
execute if entity @s[type=minecraft:block_display,tag=s_effects_lib+Eternal_Flame-Block_Display,scores={s_effects_lib+eternal_flame_lifetime=16}] run data merge entity @s {block_state:{Properties:{age:"15",east:"false",north:"false",south:"false",up:"false",west:"false"}}}
execute if entity @s[type=minecraft:block_display,tag=s_effects_lib+Eternal_Flame-Block_Display,scores={s_effects_lib+eternal_flame_lifetime=20..}] run kill @s
execute if entity @s run return 0

# Run Effects
execute as @e[type=!player,type=!#silvers_tags:ignored_entities] at @s run function s_effects_lib:technical/effects

# Decreaser:
scoreboard players add $Value s_effects_lib+decreaser 1
execute if score $Value s_effects_lib+decreaser matches 21.. run scoreboard players set $Value s_effects_lib+decreaser 0

execute if score $Value s_effects_lib+decreaser matches 5 run execute as @e[type=!player,type=!#silvers_tags:ignored_entities,scores={s_effects_lib+bleed_duration=0..}] at @s run scoreboard players remove @s s_effects_lib+bleed_duration 1
execute if score $Value s_effects_lib+decreaser matches 5 run execute as @e[type=!player,type=!#silvers_tags:ignored_entities,scores={s_effects_lib+fatal_bleed_duration=0..}] at @s run scoreboard players remove @s s_effects_lib+fatal_bleed_duration 1
execute if score $Value s_effects_lib+decreaser matches 5 run execute as @e[type=!player,type=!#silvers_tags:ignored_entities,scores={s_effects_lib+frostbite_duration=0..}] at @s run scoreboard players remove @s s_effects_lib+frostbite_duration 1
execute if score $Value s_effects_lib+decreaser matches 5 run execute as @e[type=!player,type=!#silvers_tags:ignored_entities,scores={s_effects_lib+lethal_frostbite_duration=0..}] at @s run scoreboard players remove @s s_effects_lib+lethal_frostbite_duration 1
execute if score $Value s_effects_lib+decreaser matches 5 run execute as @e[type=!player,type=!#silvers_tags:ignored_entities,scores={s_effects_lib+electrify_duration=0..}] at @s run scoreboard players remove @s s_effects_lib+electrify_duration 1
execute if score $Value s_effects_lib+decreaser matches 5 run execute as @e[type=!player,type=!#silvers_tags:ignored_entities,scores={s_effects_lib+stun_duration=0..}] at @s run scoreboard players remove @s s_effects_lib+stun_duration 1
execute if score $Value s_effects_lib+decreaser matches 5 run execute as @e[type=!player,type=!#silvers_tags:ignored_entities,scores={s_effects_lib+lesser_stun_duration=0..}] at @s run scoreboard players remove @s s_effects_lib+lesser_stun_duration 1
execute if score $Value s_effects_lib+decreaser matches 5 run execute as @e[type=!player,type=!#silvers_tags:ignored_entities,scores={s_effects_lib+paralysis_duration=0..}] at @s run scoreboard players remove @s s_effects_lib+paralysis_duration 1
execute if score $Value s_effects_lib+decreaser matches 5 run execute as @e[type=!player,type=!#silvers_tags:ignored_entities,scores={s_effects_lib+eternal_flame_duration=0..}] at @s run scoreboard players remove @s s_effects_lib+eternal_flame_duration 1
execute if score $Value s_effects_lib+decreaser matches 5 run execute as @e[type=!player,type=!#silvers_tags:ignored_entities,scores={s_effects_lib+rage_duration=0..}] at @s run scoreboard players remove @s s_effects_lib+rage_duration 1
execute if score $Value s_effects_lib+decreaser matches 5 run execute as @e[type=!player,type=!#silvers_tags:ignored_entities,scores={s_effects_lib+invulnerability_duration=0..}] at @s run scoreboard players remove @s s_effects_lib+invulnerability_duration 1
execute if score $Value s_effects_lib+decreaser matches 5 run execute as @e[type=!player,type=!#silvers_tags:ignored_entities,scores={s_effects_lib+vulnerability_duration=0..}] at @s run scoreboard players remove @s s_effects_lib+vulnerability_duration 1
execute if score $Value s_effects_lib+decreaser matches 5 run execute as @e[type=!player,type=!#silvers_tags:ignored_entities,scores={s_effects_lib+infection_duration=0..}] at @s run scoreboard players remove @s s_effects_lib+infection_duration 1
execute if score $Value s_effects_lib+decreaser matches 5 run execute as @e[type=!player,type=!#silvers_tags:ignored_entities,scores={s_effects_lib+batrachotoxin_duration=0..}] at @s run scoreboard players remove @s s_effects_lib+batrachotoxin_duration 1
execute if score $Value s_effects_lib+decreaser matches 5 run execute as @e[type=!player,type=!#silvers_tags:ignored_entities,scores={s_effects_lib+fatal_poison_duration=0..}] at @s run scoreboard players remove @s s_effects_lib+fatal_poison_duration 1
execute if score $Value s_effects_lib+decreaser matches 5 run execute as @e[type=!player,type=!#silvers_tags:ignored_entities,scores={s_effects_lib+nyctophobia_duration=0..}] at @s run scoreboard players remove @s s_effects_lib+nyctophobia_duration 1
execute if score $Value s_effects_lib+decreaser matches 5 run execute as @e[type=!player,type=!#silvers_tags:ignored_entities,scores={s_effects_lib+undead_curse_duration=0..}] at @s run scoreboard players remove @s s_effects_lib+undead_curse_duration 1
execute if score $Value s_effects_lib+decreaser matches 5 run execute as @e[type=!player,type=!#silvers_tags:ignored_entities,scores={s_effects_lib+hypothermia_duration=0..}] at @s run scoreboard players remove @s s_effects_lib+hypothermia_duration 1

# Add ID
execute as @r at @s unless score @s s_effects_lib+id matches 0.. run function s_effects_lib:technical/add_id

# Interaction Lifetime
execute as @e[type=minecraft:interaction,tag=s_effects_lib+Stun_Interaction] run function s_effects_lib:technical/tick/private

# Revoke
advancement revoke @a only s_effects_lib:technical/tick

# Eternal Flame Lifetime
execute as @e[type=minecraft:block_display,tag=s_effects_lib+Eternal_Flame-Block_Display] run function s_effects_lib:technical/tick/private
