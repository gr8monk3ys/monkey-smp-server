# Enchant Stuff
execute as @s at @s run function strength_smp:technical/main/enchant/add

execute as @s at @s if items entity @s player.cursor #strength_smp:strength_smp_weapons run item modify entity @s player.cursor strength_smp:remove_enchants
execute as @s at @s if entity @e[type=minecraft:marker,tag=Strength_SMP+Enchanting_Block,distance=..5] run function strength_smp:technical/main/enchant/clear

execute unless score @s Strength_SMP+Selected_Weapon_ID matches 3 if items entity @s container.* minecraft:crossbow run function s_inv_lib:macro/item_modify/with_existing {"beginning_item":'minecraft:crossbow',"modifier_name":'strength_smp:remove_enchants/crossbow'}
execute unless score @s Strength_SMP+Selected_Weapon_ID matches 3 if items entity @s weapon.offhand minecraft:crossbow run function s_inv_lib:macro/item_modify/with_existing {"beginning_item":'minecraft:crossbow',"modifier_name":'strength_smp:remove_enchants/crossbow'}
execute unless score @s Strength_SMP+Selected_Weapon_ID matches 3 if items entity @s armor.* minecraft:crossbow run function s_inv_lib:macro/item_modify/with_existing {"beginning_item":'minecraft:crossbow',"modifier_name":'strength_smp:remove_enchants/crossbow'}
execute unless score @s Strength_SMP+Selected_Weapon_ID matches 4 if items entity @s container.* minecraft:bow run function s_inv_lib:macro/item_modify/with_existing {"beginning_item":'minecraft:bow',"modifier_name":'strength_smp:remove_enchants/bow'}
execute unless score @s Strength_SMP+Selected_Weapon_ID matches 4 if items entity @s weapon.offhand minecraft:bow run function s_inv_lib:macro/item_modify/with_existing {"beginning_item":'minecraft:bow',"modifier_name":'strength_smp:remove_enchants/bow'}
execute unless score @s Strength_SMP+Selected_Weapon_ID matches 4 if items entity @s armor.* minecraft:bow run function s_inv_lib:macro/item_modify/with_existing {"beginning_item":'minecraft:bow',"modifier_name":'strength_smp:remove_enchants/bow'}

advancement revoke @s only strength_smp:technical/enchant/tick
