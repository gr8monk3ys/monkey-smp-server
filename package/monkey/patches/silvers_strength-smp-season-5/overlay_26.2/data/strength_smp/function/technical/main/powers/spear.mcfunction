## Spear
scoreboard players set @s[scores={Strength_SMP+Poke_Counter=1..},nbt={HurtTime:9s}] Strength_SMP+Poke_Counter 0
scoreboard players remove @s[scores={Strength_SMP+Poke_Counter_Duration=1..}] Strength_SMP+Poke_Counter_Duration 1
scoreboard players set @s[scores={Strength_SMP+Poke_Counter_Duration=0}] Strength_SMP+Poke_Counter 0
execute unless score @s[tag=Strength_SMP+Spear_Passive_Activated] Strength_SMP+Selected_Weapon_ID matches 7 run tag @s remove Strength_SMP+Spear_Passive_Activated
tag @s[tag=Strength_SMP+Spear_Passive_Activated,scores={Strength_SMP+Poke_Counter=0}] remove Strength_SMP+Spear_Passive_Activated
execute unless score @s[tag=Strength_SMP+Spear_Ultimate_Activated] Strength_SMP+Selected_Weapon_ID matches 7 run tag @s remove Strength_SMP+Spear_Ultimate_Activated
tag @s[tag=Strength_SMP+Spear_Ultimate_Activated,scores={Strength_SMP+Poke_Counter=0}] remove Strength_SMP+Spear_Ultimate_Activated

execute as @s[scores={Strength_SMP+Strength_Level=5..,Strength_SMP+Poke_Counter=15..,Strength_SMP+Spear-Ultimate_Cooldown=..0},tag=!Strength_SMP+Spear_Ultimate_Activated] at @s run function strength_smp:technical/trigger/ftf/activate/spear/ultimate
execute as @s[scores={Activate_Weapon_Ultimate=1..,Strength_SMP+Spear-Ultimate_Lifetime=1..}] at @s if items entity @s weapon.* #minecraft:spears run function strength_smp:technical/trigger/ftf/activate/spear/activate
execute as @s[scores={Strength_SMP+Spear-Ultimate_Lifetime=1}] at @s run function strength_smp:technical/trigger/ftf/lost_weapon_ultimate/spear
scoreboard players remove @s[scores={Strength_SMP+Spear-Ultimate_Lifetime=2..}] Strength_SMP+Spear-Ultimate_Lifetime 1

execute as @s[scores={Strength_SMP+Spear-Ultimate_Cooldown=0}] at @s run function strength_smp:technical/trigger/ftf/off_cooldown/spear

execute if items entity @s container.* minecraft:wooden_spear run function s_inv_lib:macro/item_modify/with_existing {"beginning_item":'minecraft:wooden_spear',"modifier_name":'strength_smp:sword/wooden'}
execute if items entity @s weapon.offhand minecraft:wooden_spear run function s_inv_lib:macro/item_modify/with_existing {"beginning_item":'minecraft:wooden_spear',"modifier_name":'strength_smp:sword/wooden'}
execute if items entity @s armor.* minecraft:wooden_spear run function s_inv_lib:macro/item_modify/with_existing {"beginning_item":'minecraft:wooden_spear',"modifier_name":'strength_smp:sword/wooden'}
execute if items entity @s container.* minecraft:stone_spear run function s_inv_lib:macro/item_modify/with_existing {"beginning_item":'minecraft:stone_spear',"modifier_name":'strength_smp:sword/stone'}
execute if items entity @s weapon.offhand minecraft:stone_spear run function s_inv_lib:macro/item_modify/with_existing {"beginning_item":'minecraft:stone_spear',"modifier_name":'strength_smp:sword/stone'}
execute if items entity @s armor.* minecraft:stone_spear run function s_inv_lib:macro/item_modify/with_existing {"beginning_item":'minecraft:stone_spear',"modifier_name":'strength_smp:sword/stone'}
execute if items entity @s container.* minecraft:copper_spear run function s_inv_lib:macro/item_modify/with_existing {"beginning_item":'minecraft:copper_spear',"modifier_name":'strength_smp:sword/copper'}
execute if items entity @s weapon.offhand minecraft:copper_spear run function s_inv_lib:macro/item_modify/with_existing {"beginning_item":'minecraft:copper_spear',"modifier_name":'strength_smp:sword/copper'}
execute if items entity @s armor.* minecraft:copper_spear run function s_inv_lib:macro/item_modify/with_existing {"beginning_item":'minecraft:copper_spear',"modifier_name":'strength_smp:sword/copper'}
execute if items entity @s container.* minecraft:iron_spear run function s_inv_lib:macro/item_modify/with_existing {"beginning_item":'minecraft:iron_spear',"modifier_name":'strength_smp:sword/iron'}
execute if items entity @s weapon.offhand minecraft:iron_spear run function s_inv_lib:macro/item_modify/with_existing {"beginning_item":'minecraft:iron_spear',"modifier_name":'strength_smp:sword/iron'}
execute if items entity @s armor.* minecraft:iron_spear run function s_inv_lib:macro/item_modify/with_existing {"beginning_item":'minecraft:iron_spear',"modifier_name":'strength_smp:sword/iron'}
execute if items entity @s container.* minecraft:golden_spear run function s_inv_lib:macro/item_modify/with_existing {"beginning_item":'minecraft:golden_spear',"modifier_name":'strength_smp:sword/golden'}
execute if items entity @s weapon.offhand minecraft:golden_spear run function s_inv_lib:macro/item_modify/with_existing {"beginning_item":'minecraft:golden_spear',"modifier_name":'strength_smp:sword/golden'}
execute if items entity @s armor.* minecraft:golden_spear run function s_inv_lib:macro/item_modify/with_existing {"beginning_item":'minecraft:golden_spear',"modifier_name":'strength_smp:sword/golden'}
execute if items entity @s container.* minecraft:diamond_spear run function s_inv_lib:macro/item_modify/with_existing {"beginning_item":'minecraft:diamond_spear',"modifier_name":'strength_smp:sword/diamond'}
execute if items entity @s weapon.offhand minecraft:diamond_spear run function s_inv_lib:macro/item_modify/with_existing {"beginning_item":'minecraft:diamond_spear',"modifier_name":'strength_smp:sword/diamond'}
execute if items entity @s armor.* minecraft:diamond_spear run function s_inv_lib:macro/item_modify/with_existing {"beginning_item":'minecraft:diamond_spear',"modifier_name":'strength_smp:sword/diamond'}
execute if items entity @s container.* minecraft:netherite_spear run function s_inv_lib:macro/item_modify/with_existing {"beginning_item":'minecraft:netherite_spear',"modifier_name":'strength_smp:sword/netherite'}
execute if items entity @s weapon.offhand minecraft:netherite_spear run function s_inv_lib:macro/item_modify/with_existing {"beginning_item":'minecraft:netherite_spear',"modifier_name":'strength_smp:sword/netherite'}
execute if items entity @s armor.* minecraft:netherite_spear run function s_inv_lib:macro/item_modify/with_existing {"beginning_item":'minecraft:netherite_spear',"modifier_name":'strength_smp:sword/netherite'}




scoreboard players enable @s Activate_Weapon_Ultimate
scoreboard players set @s[scores={Activate_Weapon_Ultimate=1..}] Activate_Weapon_Ultimate 0
advancement revoke @s only strength_smp:technical/powers/spear
