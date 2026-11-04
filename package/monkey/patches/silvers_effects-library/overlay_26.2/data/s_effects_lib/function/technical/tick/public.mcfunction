scoreboard players enable @s show_custom_effect_duration
execute unless score @s show_custom_effect_duration matches -2147483648..2147483647 run scoreboard players set @s show_custom_effect_duration 0

# Hide Duration
execute if score @s s_effects_lib+bleed_duration matches ..1 run function s_effects_lib:technical/bossbar/get_id {"effect_type":"bleed"}
execute if score @s s_effects_lib+fatal_bleed_duration matches ..1 run function s_effects_lib:technical/bossbar/get_id {"effect_type":"fatal_bleed"}
execute if score @s s_effects_lib+frostbite_duration matches ..1 run function s_effects_lib:technical/bossbar/get_id {"effect_type":"frostbite"}
execute if score @s s_effects_lib+lethal_frostbite_duration matches ..1 run function s_effects_lib:technical/bossbar/get_id {"effect_type":"lethal_frostbite"}
execute if score @s s_effects_lib+electrify_duration matches ..1 run function s_effects_lib:technical/bossbar/get_id {"effect_type":"electrify"}
execute if score @s s_effects_lib+stun_duration matches ..1 run function s_effects_lib:technical/bossbar/get_id {"effect_type":"stun"}
execute if score @s s_effects_lib+lesser_stun_duration matches ..1 run function s_effects_lib:technical/bossbar/get_id {"effect_type":"lesser_stun"}
execute if score @s s_effects_lib+paralysis_duration matches ..1 run function s_effects_lib:technical/bossbar/get_id {"effect_type":"paralysis"}
execute if score @s s_effects_lib+eternal_flame_duration matches ..1 run function s_effects_lib:technical/bossbar/get_id {"effect_type":"eternal_flame"}
execute if score @s s_effects_lib+rage_duration matches ..1 run function s_effects_lib:technical/bossbar/get_id {"effect_type":"rage"}
execute if score @s s_effects_lib+invulnerability_duration matches ..1 run function s_effects_lib:technical/bossbar/get_id {"effect_type":"invulnerability"}
execute if score @s s_effects_lib+vulnerability_duration matches ..1 run function s_effects_lib:technical/bossbar/get_id {"effect_type":"vulnerability"}
execute if score @s s_effects_lib+infection_duration matches ..1 run function s_effects_lib:technical/bossbar/get_id {"effect_type":"infection"}
execute if score @s s_effects_lib+batrachotoxin_duration matches ..1 run function s_effects_lib:technical/bossbar/get_id {"effect_type":"batrachotoxin"}
execute if score @s s_effects_lib+fatal_poison_duration matches ..1 run function s_effects_lib:technical/bossbar/get_id {"effect_type":"fatal_poison"}
execute if score @s s_effects_lib+nyctophobia_duration matches ..1 run function s_effects_lib:technical/bossbar/get_id {"effect_type":"nyctophobia"}
execute if score @s s_effects_lib+undead_curse_duration matches ..1 run function s_effects_lib:technical/bossbar/get_id {"effect_type":"undead_curse"}
execute if score @s s_effects_lib+hypothermia_duration matches ..1 run function s_effects_lib:technical/bossbar/get_id {"effect_type":"hypothermia"}

# Decreaser:
scoreboard players add @s s_effects_lib+decreaser 1
scoreboard players set @s[scores={s_effects_lib+decreaser=31..}] s_effects_lib+decreaser 0

## Decrease Duration:
execute as @s[scores={s_effects_lib+decreaser=2,s_effects_lib+bleed_duration=0..}] at @s run function s_effects_lib:cmd/give_effect/reduce {"effect_type":"bleed","duration":1}
execute as @s[scores={s_effects_lib+decreaser=2,s_effects_lib+fatal_bleed_duration=0..}] at @s run function s_effects_lib:cmd/give_effect/reduce {"effect_type":"fatal_bleed","duration":1}
execute as @s[scores={s_effects_lib+decreaser=2,s_effects_lib+frostbite_duration=0..}] at @s run function s_effects_lib:cmd/give_effect/reduce {"effect_type":"frostbite","duration":1}
execute as @s[scores={s_effects_lib+decreaser=2,s_effects_lib+lethal_frostbite_duration=0..}] at @s run function s_effects_lib:cmd/give_effect/reduce {"effect_type":"lethal_frostbite","duration":1}
execute as @s[scores={s_effects_lib+decreaser=2,s_effects_lib+electrify_duration=0..}] at @s run function s_effects_lib:cmd/give_effect/reduce {"effect_type":"electrify","duration":1}
execute as @s[scores={s_effects_lib+decreaser=2,s_effects_lib+stun_duration=0..}] at @s run function s_effects_lib:cmd/give_effect/reduce {"effect_type":"stun","duration":1}
execute as @s[scores={s_effects_lib+decreaser=2,s_effects_lib+lesser_stun_duration=0..}] at @s run function s_effects_lib:cmd/give_effect/reduce {"effect_type":"lesser_stun","duration":1}
execute as @s[scores={s_effects_lib+decreaser=2,s_effects_lib+paralysis_duration=0..}] at @s run function s_effects_lib:cmd/give_effect/reduce {"effect_type":"paralysis","duration":1}
execute as @s[scores={s_effects_lib+decreaser=2,s_effects_lib+eternal_flame_duration=0..}] at @s run function s_effects_lib:cmd/give_effect/reduce {"effect_type":"eternal_flame","duration":1}
execute as @s[scores={s_effects_lib+decreaser=2,s_effects_lib+rage_duration=0..}] at @s run function s_effects_lib:cmd/give_effect/reduce {"effect_type":"rage","duration":1}
execute as @s[scores={s_effects_lib+decreaser=2,s_effects_lib+invulnerability_duration=0..}] at @s run function s_effects_lib:cmd/give_effect/reduce {"effect_type":"invulnerability","duration":1}
execute as @s[scores={s_effects_lib+decreaser=2,s_effects_lib+vulnerability_duration=0..}] at @s run function s_effects_lib:cmd/give_effect/reduce {"effect_type":"vulnerability","duration":1}
execute as @s[scores={s_effects_lib+decreaser=2,s_effects_lib+infection_duration=0..}] at @s run function s_effects_lib:cmd/give_effect/reduce {"effect_type":"infection","duration":1}
execute as @s[scores={s_effects_lib+decreaser=2,s_effects_lib+batrachotoxin_duration=0..}] at @s run function s_effects_lib:cmd/give_effect/reduce {"effect_type":"batrachotoxin","duration":1}
execute as @s[scores={s_effects_lib+decreaser=2,s_effects_lib+fatal_poison_duration=0..}] at @s run function s_effects_lib:cmd/give_effect/reduce {"effect_type":"fatal_poison","duration":1}
execute as @s[scores={s_effects_lib+decreaser=2,s_effects_lib+nyctophobia_duration=-1..}] at @s run function s_effects_lib:cmd/give_effect/reduce {"effect_type":"nyctophobia","duration":1}
execute as @s[scores={s_effects_lib+decreaser=2,s_effects_lib+undead_curse_duration=0..}] at @s run function s_effects_lib:cmd/give_effect/reduce {"effect_type":"undead_curse","duration":1}
execute as @s[scores={s_effects_lib+decreaser=2,s_effects_lib+hypothermia_duration=0..}] at @s run function s_effects_lib:cmd/give_effect/reduce {"effect_type":"hypothermia","duration":1}

# Decreaser:
scoreboard players add @s s_effects_lib+damage_interval 1
scoreboard players set @s[scores={s_effects_lib+damage_interval=11..}] s_effects_lib+damage_interval 0

# Death Reset:
execute as @s[scores={s_effects_lib+deathCount=1..}] at @s run function s_effects_lib:cmd/clear_effects

# show_custom_effect_duration
scoreboard players set @s[scores={show_custom_effect_duration=2..}] show_custom_effect_duration 0
scoreboard players set @s[scores={show_custom_effect_duration=..-1}] show_custom_effect_duration 0

# Fire Get
execute if score @s s_effects_lib+eternal_flame_duration matches 1.. store result score @s s_effects_lib+Fire run data get entity @s Fire
execute if score @s s_effects_lib+undead_curse_duration matches 1.. store result score @s s_effects_lib+Fire run data get entity @s Fire



# Ticking
advancement revoke @s only s_effects_lib:technical/tick
