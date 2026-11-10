## Armor
scoreboard players set @s[nbt={HurtTime:9s}] Strength_SMP+Damaged_Counter_Duration 60
scoreboard players remove @s[scores={Strength_SMP+Damaged_Counter_Duration=1..}] Strength_SMP+Damaged_Counter_Duration 1
scoreboard players set @s[scores={Strength_SMP+Damaged_Counter_Duration=0}] Strength_SMP+Damaged_Counter 0
execute unless score @s Strength_SMP+Selected_Weapon_ID matches 9 run tag @s[tag=Strength_SMP+Armor_Passive_Activated] remove Strength_SMP+Armor_Passive_Activated
tag @s[tag=Strength_SMP+Armor_Passive_Activated,scores={Strength_SMP+Damaged_Counter=0}] remove Strength_SMP+Armor_Passive_Activated
execute unless score @s Strength_SMP+Selected_Weapon_ID matches 9 run tag @s[tag=Strength_SMP+Armor_Ultimate_Activated] remove Strength_SMP+Armor_Ultimate_Activated
tag @s[tag=Strength_SMP+Armor_Ultimate_Activated,scores={Strength_SMP+Damaged_Counter=0}] remove Strength_SMP+Armor_Ultimate_Activated

execute as @s[scores={Strength_SMP+Strength_Level=5..,Strength_SMP+Armor-Ultimate_Cooldown=..0},tag=!Strength_SMP+Armor_Ultimate_Activated] at @s if score @s Strength_SMP+Damaged_Counter >= $Config Strength_SMP+Config-Ultimate_Damage_Counter_Sufficient_Armor run function strength_smp:technical/trigger/ftf/activate/armor/ultimate
execute as @s[scores={Activate_Weapon_Ultimate=1..,Strength_SMP+Armor-Ultimate_Lifetime=1..}] at @s if predicate strength_smp:armor_check run function strength_smp:technical/trigger/ftf/activate/armor/activate
execute as @s[scores={Strength_SMP+Armor-Ultimate_Lifetime=1}] at @s run function strength_smp:technical/trigger/ftf/lost_weapon_ultimate/armor
scoreboard players remove @s[scores={Strength_SMP+Armor-Ultimate_Lifetime=2..}] Strength_SMP+Armor-Ultimate_Lifetime 1

attribute @s[scores={Strength_SMP+Armor-Ultimate_Duration=1..}] minecraft:knockback_resistance modifier add strength_smp:armor_ultimate-knockback_resistance 5 add_value
attribute @s[scores={Strength_SMP+Armor-Ultimate_Duration=1..}] minecraft:explosion_knockback_resistance modifier add strength_smp:armor_ultimate-explosion_knockback_resistance 5 add_value
# Monkey SMP: the ultimate's own modifier names (it shared the shield's); tick/public takes them off for every player.
execute as @s[scores={Strength_SMP+Armor-Ultimate_Cooldown=0}] at @s run function strength_smp:technical/trigger/ftf/off_cooldown/armor

# Monkey SMP: no diamond -> netherite swap (it never swapped back). armor_check takes diamond or netherite.
# Monkey SMP: the passive instead. Each worn diamond piece gets what netherite has over it (+1 armor toughness,
# +0.1 knockback resistance) as a player modifier, so no item changes. Adding one already there fails quietly, as
# upstream's strength buffs do. tick/public takes it all off when the power changes or the player dies.
tag @s add strength_smp.armor_passive
execute if items entity @s armor.head minecraft:diamond_helmet run attribute @s minecraft:armor_toughness modifier add strength_smp:armor_passive-head-armor_toughness 1 add_value
execute if items entity @s armor.head minecraft:diamond_helmet run attribute @s minecraft:knockback_resistance modifier add strength_smp:armor_passive-head-knockback_resistance 0.1 add_value
execute unless items entity @s armor.head minecraft:diamond_helmet run attribute @s minecraft:armor_toughness modifier remove strength_smp:armor_passive-head-armor_toughness
execute unless items entity @s armor.head minecraft:diamond_helmet run attribute @s minecraft:knockback_resistance modifier remove strength_smp:armor_passive-head-knockback_resistance
execute if items entity @s armor.chest minecraft:diamond_chestplate run attribute @s minecraft:armor_toughness modifier add strength_smp:armor_passive-chest-armor_toughness 1 add_value
execute if items entity @s armor.chest minecraft:diamond_chestplate run attribute @s minecraft:knockback_resistance modifier add strength_smp:armor_passive-chest-knockback_resistance 0.1 add_value
execute unless items entity @s armor.chest minecraft:diamond_chestplate run attribute @s minecraft:armor_toughness modifier remove strength_smp:armor_passive-chest-armor_toughness
execute unless items entity @s armor.chest minecraft:diamond_chestplate run attribute @s minecraft:knockback_resistance modifier remove strength_smp:armor_passive-chest-knockback_resistance
execute if items entity @s armor.legs minecraft:diamond_leggings run attribute @s minecraft:armor_toughness modifier add strength_smp:armor_passive-legs-armor_toughness 1 add_value
execute if items entity @s armor.legs minecraft:diamond_leggings run attribute @s minecraft:knockback_resistance modifier add strength_smp:armor_passive-legs-knockback_resistance 0.1 add_value
execute unless items entity @s armor.legs minecraft:diamond_leggings run attribute @s minecraft:armor_toughness modifier remove strength_smp:armor_passive-legs-armor_toughness
execute unless items entity @s armor.legs minecraft:diamond_leggings run attribute @s minecraft:knockback_resistance modifier remove strength_smp:armor_passive-legs-knockback_resistance
execute if items entity @s armor.feet minecraft:diamond_boots run attribute @s minecraft:armor_toughness modifier add strength_smp:armor_passive-feet-armor_toughness 1 add_value
execute if items entity @s armor.feet minecraft:diamond_boots run attribute @s minecraft:knockback_resistance modifier add strength_smp:armor_passive-feet-knockback_resistance 0.1 add_value
execute unless items entity @s armor.feet minecraft:diamond_boots run attribute @s minecraft:armor_toughness modifier remove strength_smp:armor_passive-feet-armor_toughness
execute unless items entity @s armor.feet minecraft:diamond_boots run attribute @s minecraft:knockback_resistance modifier remove strength_smp:armor_passive-feet-knockback_resistance





scoreboard players enable @s Activate_Weapon_Ultimate
scoreboard players set @s[scores={Activate_Weapon_Ultimate=1..}] Activate_Weapon_Ultimate 0
advancement revoke @s only strength_smp:technical/powers/armor
