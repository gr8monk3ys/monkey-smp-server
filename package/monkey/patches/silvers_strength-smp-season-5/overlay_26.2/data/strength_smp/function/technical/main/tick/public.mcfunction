# Tags
execute unless score @s Strength_SMP+Strength_Level matches -2147483648..2147483647 run scoreboard players set @s Strength_SMP+Strength_Level 3

execute unless score @s Strength_SMP+1-Score_Tags matches 10.. run scoreboard players add @s Strength_SMP+1-Score_Tags 1
execute unless score $Admin Strength_SMP+1-Score_Tags matches 11.. run scoreboard players add $Admin Strength_SMP+1-Score_Tags 1

execute as @s[scores={Strength_SMP+1-Score_Tags=2..4}] at @s run function strength_smp:technical/trigger/ftf/restart
execute as @s[scores={Strength_SMP+1-Score_Tags=3}] run function strength_smp:technical/trigger/ftf/change_weapon/random/run
execute as @s[scores={Strength_SMP+1-Score_Tags=3}] run function strength_smp:technical/trigger/ftf/death_resets

# Dev Stuff
execute if score $Admin Strength_SMP+1-Score_Tags matches 10 run tellraw @a[tag=Strength_SMP+Dev_Tag] ""
execute if score $Admin Strength_SMP+1-Score_Tags matches 10 run tellraw @a[tag=Strength_SMP+Dev_Tag] [{"text":"! ","color":"dark_purple","bold":true},{"text":"someone has triggered a data reset!","color":"gray","bold":false}]

# Strength Amount
scoreboard players enable @s Strength
execute as @s[scores={Strength=1..}] run function strength_smp:technical/trigger/ftf/status
scoreboard players set @s[scores={Strength=1..}] Strength 0

# Strength Main
scoreboard players enable @s Withdraw_Strength
execute as @s[scores={Withdraw_Strength=4..,Strength_SMP+Strength_Level=5..}] run function strength_smp:technical/trigger/ftf/withdraw_strength {amount:4}
execute as @s[scores={Withdraw_Strength=3..,Strength_SMP+Strength_Level=4..}] run function strength_smp:technical/trigger/ftf/withdraw_strength {amount:3}
execute as @s[scores={Withdraw_Strength=2..,Strength_SMP+Strength_Level=3..}] run function strength_smp:technical/trigger/ftf/withdraw_strength {amount:2}
execute as @s[scores={Withdraw_Strength=1..,Strength_SMP+Strength_Level=2..}] run function strength_smp:technical/trigger/ftf/withdraw_strength {amount:1}
scoreboard players set @s[scores={Withdraw_Strength=1..}] Withdraw_Strength 0

# Passive
attribute @s[scores={Strength_SMP+Strength_Level=2..}] minecraft:attack_damage modifier add strength_smp:buff-level_1 1 add_value
attribute @s[scores={Strength_SMP+Strength_Level=3..}] minecraft:attack_damage modifier add strength_smp:buff-level_2 1 add_value
attribute @s[scores={Strength_SMP+Strength_Level=4..}] minecraft:attack_damage modifier add strength_smp:buff-level_3 1 add_value
attribute @s[scores={Strength_SMP+Strength_Level=5..}] minecraft:attack_damage modifier add strength_smp:buff-level_4 1 add_value
attribute @s[scores={Strength_SMP+Strength_Level=..1}] minecraft:attack_damage modifier remove strength_smp:buff-level_1
attribute @s[scores={Strength_SMP+Strength_Level=..1}] minecraft:attack_damage modifier remove strength_smp:buff-level_2
attribute @s[scores={Strength_SMP+Strength_Level=..1}] minecraft:attack_damage modifier remove strength_smp:buff-level_3
attribute @s[scores={Strength_SMP+Strength_Level=..1}] minecraft:attack_damage modifier remove strength_smp:buff-level_4
attribute @s[scores={Strength_SMP+Strength_Level=..1}] minecraft:attack_damage modifier remove strength_smp:buff-level_5

# Monkey SMP: the armor passive (powers/armor) comes off when the power is no longer Armor and at death, before
# death_resets zeroes the death count; powers/armor puts it back.
execute if entity @s[tag=strength_smp.armor_passive] unless score @s Strength_SMP+Selected_Weapon_ID matches 9 run tag @s add strength_smp.armor_passive.off
tag @s[tag=strength_smp.armor_passive,scores={Strength_SMP+Death=1..}] add strength_smp.armor_passive.off
attribute @s[tag=strength_smp.armor_passive.off] minecraft:armor_toughness modifier remove strength_smp:armor_passive-head-armor_toughness
attribute @s[tag=strength_smp.armor_passive.off] minecraft:knockback_resistance modifier remove strength_smp:armor_passive-head-knockback_resistance
attribute @s[tag=strength_smp.armor_passive.off] minecraft:armor_toughness modifier remove strength_smp:armor_passive-chest-armor_toughness
attribute @s[tag=strength_smp.armor_passive.off] minecraft:knockback_resistance modifier remove strength_smp:armor_passive-chest-knockback_resistance
attribute @s[tag=strength_smp.armor_passive.off] minecraft:armor_toughness modifier remove strength_smp:armor_passive-legs-armor_toughness
attribute @s[tag=strength_smp.armor_passive.off] minecraft:knockback_resistance modifier remove strength_smp:armor_passive-legs-knockback_resistance
attribute @s[tag=strength_smp.armor_passive.off] minecraft:armor_toughness modifier remove strength_smp:armor_passive-feet-armor_toughness
attribute @s[tag=strength_smp.armor_passive.off] minecraft:knockback_resistance modifier remove strength_smp:armor_passive-feet-knockback_resistance
tag @s[tag=strength_smp.armor_passive.off] remove strength_smp.armor_passive
tag @s[tag=strength_smp.armor_passive.off] remove strength_smp.armor_passive.off

# Death
execute as @s[scores={Strength_SMP+Death=1..}] at @s run function strength_smp:technical/trigger/ftf/death_resets

# Random
scoreboard players set @s[scores={Strength_SMP+Strength_Level=..-1}] Strength_SMP+Strength_Level 0
execute as @s[scores={Strength_SMP+Strength_Level=6..}] at @s run function strength_smp:cmd/give/strength {amount:1}
scoreboard players remove @s[scores={Strength_SMP+Strength_Level=6..}] Strength_SMP+Strength_Level 1
scoreboard players remove @s[scores={Strength_SMP+Temp=1..}] Strength_SMP+Temp 1

# Decreaser
scoreboard players add @s Strength_SMP+Decreaser 1
scoreboard players set @s[scores={Strength_SMP+Decreaser=21..}] Strength_SMP+Decreaser 0

scoreboard players remove @s[scores={Strength_SMP+Decreaser=3,Strength_SMP+Sword-Passive_Duration=1..}] Strength_SMP+Sword-Passive_Duration 1
scoreboard players remove @s[scores={Strength_SMP+Decreaser=3,Strength_SMP+Sword-Ultimate_Duration=1..}] Strength_SMP+Sword-Ultimate_Duration 1
scoreboard players remove @s[scores={Strength_SMP+Decreaser=3,Strength_SMP+Shield-Ultimate_Duration=1..}] Strength_SMP+Shield-Ultimate_Duration 1
scoreboard players remove @s[scores={Strength_SMP+Decreaser=3,Strength_SMP+Axe-Passive_Duration=1..}] Strength_SMP+Axe-Passive_Duration 1
scoreboard players remove @s[scores={Strength_SMP+Decreaser=3,Strength_SMP+Axe-Ultimate_Duration=1..}] Strength_SMP+Axe-Ultimate_Duration 1
scoreboard players remove @s[scores={Strength_SMP+Decreaser=3,Strength_SMP+Trident-Ultimate_Duration=1..}] Strength_SMP+Trident-Ultimate_Duration 1
scoreboard players remove @s[scores={Strength_SMP+Decreaser=3,Strength_SMP+Axe-Ultimate_Duration=..0,Strength_SMP+Axe-Ultimate_Cooldown=1..}] Strength_SMP+Axe-Ultimate_Cooldown 1
scoreboard players remove @s[scores={Strength_SMP+Decreaser=3,Strength_SMP+Shield-Ultimate_Duration=..0,Strength_SMP+Shield-Ultimate_Cooldown=1..}] Strength_SMP+Shield-Ultimate_Cooldown 1
scoreboard players remove @s[scores={Strength_SMP+Decreaser=3,Strength_SMP+Sword-Ultimate_Duration=..0,Strength_SMP+Sword-Ultimate_Cooldown=1..}] Strength_SMP+Sword-Ultimate_Cooldown 1
scoreboard players remove @s[scores={Strength_SMP+Decreaser=3,Strength_SMP+Trident-Ultimate_Duration=..0,Strength_SMP+Trident-Ultimate_Cooldown=1..}] Strength_SMP+Trident-Ultimate_Cooldown 1
scoreboard players remove @s[scores={Strength_SMP+Decreaser=3,Strength_SMP+Crossbow-Ultimate_Duration=1..}] Strength_SMP+Crossbow-Ultimate_Duration 1
scoreboard players remove @s[scores={Strength_SMP+Decreaser=3,Strength_SMP+Crossbow-Ultimate_Duration=0,Strength_SMP+Crossbow-Ultimate_Cooldown=1..}] Strength_SMP+Crossbow-Ultimate_Cooldown 1
scoreboard players remove @s[scores={Strength_SMP+Decreaser=3,Strength_SMP+Bow-Ultimate_Duration=0,Strength_SMP+Bow-Ultimate_Cooldown=1..}] Strength_SMP+Bow-Ultimate_Cooldown 1
scoreboard players remove @s[scores={Strength_SMP+Decreaser=3,Strength_SMP+Spear-Ultimate_Cooldown=1..}] Strength_SMP+Spear-Ultimate_Cooldown 1
scoreboard players remove @s[scores={Strength_SMP+Decreaser=3,Strength_SMP+Mace-Ultimate_Duration=1..}] Strength_SMP+Mace-Ultimate_Duration 1
scoreboard players remove @s[scores={Strength_SMP+Decreaser=3,Strength_SMP+Mace-Ultimate_Duration=..0,Strength_SMP+Mace-Ultimate_Cooldown=1..}] Strength_SMP+Mace-Ultimate_Cooldown 1
# Monkey SMP: upstream never counted the armor ultimate down, so it lasted until death and came back only after one.
scoreboard players remove @s[scores={Strength_SMP+Decreaser=3,Strength_SMP+Armor-Ultimate_Duration=1..}] Strength_SMP+Armor-Ultimate_Duration 1
scoreboard players remove @s[scores={Strength_SMP+Decreaser=3,Strength_SMP+Armor-Ultimate_Duration=..0,Strength_SMP+Armor-Ultimate_Cooldown=1..}] Strength_SMP+Armor-Ultimate_Cooldown 1
# Monkey SMP: the armor ultimate's knockback immunity comes off once it ends, for every player (a reroll used to keep it).
execute if score @s Strength_SMP+Decreaser matches 3 unless score @s Strength_SMP+Armor-Ultimate_Duration matches 1.. run attribute @s minecraft:knockback_resistance modifier remove strength_smp:armor_ultimate-knockback_resistance
execute if score @s Strength_SMP+Decreaser matches 3 unless score @s Strength_SMP+Armor-Ultimate_Duration matches 1.. run attribute @s minecraft:explosion_knockback_resistance modifier remove strength_smp:armor_ultimate-explosion_knockback_resistance
# Monkey SMP: the names it used before, still on players it never let go of. Only the armor ultimate added the explosion one;
# the shield ultimate shares the other, so that one waits for both to be over.
execute if score @s Strength_SMP+Decreaser matches 3 unless score @s Strength_SMP+Armor-Ultimate_Duration matches 1.. run attribute @s minecraft:explosion_knockback_resistance modifier remove strength_smp:shield_ultimate-explosion_knockback_resistance
execute if score @s Strength_SMP+Decreaser matches 3 unless score @s Strength_SMP+Armor-Ultimate_Duration matches 1.. unless score @s Strength_SMP+Shield-Ultimate_Duration matches 1.. run attribute @s minecraft:knockback_resistance modifier remove strength_smp:shield_ultimate-knockback_resistance


# Contraband
#execute if score @s Strength_SMP+Selected_Weapon_ID matches 2 run function strength_smp:technical/trigger/ftf/change_weapon/random/run
#execute if score @s Strength_SMP+Selected_Weapon_ID matches 4 run function strength_smp:technical/trigger/ftf/change_weapon/random/run
# execute if score @s Strength_SMP+Selected_Weapon_ID matches 7 run function strength_smp:technical/trigger/ftf/change_weapon/random/run

#execute if score @s Strength_SMP+Selected_Weapon_ID matches 2 run tellraw @a[tag=Strength_SMP+Dev_Tag] [{"text":"! ","color":"dark_purple","bold":true},{"selector":"@s","color":"yellow","bold":false},{"text":" had a contraband id, it has been changed.","color":"gray","bold":false}]
#execute if score @s Strength_SMP+Selected_Weapon_ID matches 4 run tellraw @a[tag=Strength_SMP+Dev_Tag] [{"text":"! ","color":"dark_purple","bold":true},{"selector":"@s","color":"yellow","bold":false},{"text":" had a contraband id, it has been changed.","color":"gray","bold":false}]
# execute if score @s Strength_SMP+Selected_Weapon_ID matches 7 run tellraw @a[tag=Strength_SMP+Dev_Tag] [{"text":"! ","color":"dark_purple","bold":true},{"selector":"@s","color":"yellow","bold":false},{"text":" had a contraband id, it has been changed.","color":"gray","bold":false}]

# Recipe
recipe give @s strength_smp:reroll_weapon
recipe give @s strength_smp:strength




# Ticking
advancement revoke @s only strength_smp:technical/tick
