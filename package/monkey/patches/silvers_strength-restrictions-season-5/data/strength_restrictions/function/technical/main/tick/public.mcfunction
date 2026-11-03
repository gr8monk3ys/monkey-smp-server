advancement revoke @s only strength_restrictions:technical/tick

# Defaults:
execute unless score @s Strength_Restrictions+Mace_Cooldown matches -5.. run scoreboard players set @s Strength_Restrictions+Mace_Cooldown 0
execute unless score @s Strength_Restrictions+Mace_Cooldown_Max matches -5.. run scoreboard players set @s Strength_Restrictions+Mace_Cooldown_Max 0
execute unless score @s Strength_Restrictions+Lunge_Cooldown matches -5.. run scoreboard players set @s Strength_Restrictions+Lunge_Cooldown 0
execute unless score @s Strength_Restrictions+Lunge_Cooldown_Max matches -5.. run scoreboard players set @s Strength_Restrictions+Lunge_Cooldown_Max 0

# Durations Stuff
scoreboard players add @s Strength_Restrictions+Decreaser 1
scoreboard players set @s[scores={Strength_Restrictions+Decreaser=21..}] Strength_Restrictions+Decreaser 0

# Mace
execute as @s[scores={Strength_Restrictions+Decreaser=5,Strength_Restrictions+Mace_Cooldown=1..}] at @s run function strength_restrictions:technical/trigger/ftf/random/mace/reduce {duration:1}
function strength_restrictions:technical/trigger/ftf/random/mace/bossbar/get_id

execute if entity @s[scores={Strength_Restrictions+Mace_Cooldown=1..}] if items entity @s container.* minecraft:mace run function s_inv_lib:macro/item_modify/with_existing {"beginning_item":'minecraft:mace',"modifier_name":'strength_restrictions:mace/nerfed'}
execute if entity @s[scores={Strength_Restrictions+Mace_Cooldown=1..}] if items entity @s weapon.offhand minecraft:mace run function s_inv_lib:macro/item_modify/with_existing {"beginning_item":'minecraft:mace',"modifier_name":'strength_restrictions:mace/nerfed'}
execute if entity @s[scores={Strength_Restrictions+Mace_Cooldown=1..}] if items entity @s armor.* minecraft:mace run function s_inv_lib:macro/item_modify/with_existing {"beginning_item":'minecraft:mace',"modifier_name":'strength_restrictions:mace/nerfed'}
execute if entity @s[scores={Strength_Restrictions+Mace_Cooldown=..0}] if items entity @s container.* minecraft:poisonous_potato[minecraft:custom_data~{"Strength_Restrictions+Disabled_Mace":{}}] run function s_inv_lib:macro/item_modify/with_existing {"beginning_item":'minecraft:poisonous_potato[minecraft:custom_data~{"Strength_Restrictions+Disabled_Mace":{}}]',"modifier_name":'strength_restrictions:mace/default'}
execute if entity @s[scores={Strength_Restrictions+Mace_Cooldown=..0}] if items entity @s weapon.offhand minecraft:poisonous_potato[minecraft:custom_data~{"Strength_Restrictions+Disabled_Mace":{}}] run function s_inv_lib:macro/item_modify/with_existing {"beginning_item":'minecraft:poisonous_potato[minecraft:custom_data~{"Strength_Restrictions+Disabled_Mace":{}}]',"modifier_name":'strength_restrictions:mace/default'}
execute if entity @s[scores={Strength_Restrictions+Mace_Cooldown=..0}] if items entity @s armor.* minecraft:poisonous_potato[minecraft:custom_data~{"Strength_Restrictions+Disabled_Mace":{}}] run function s_inv_lib:macro/item_modify/with_existing {"beginning_item":'minecraft:poisonous_potato[minecraft:custom_data~{"Strength_Restrictions+Disabled_Mace":{}}]',"modifier_name":'strength_restrictions:mace/default'}

# Mace no Enchant
execute unless score @s Strength_SMP+Mace-Ultimate_Duration matches 1.. if items entity @s container.* minecraft:mace run function s_inv_lib:macro/item_modify/with_existing {"beginning_item":'minecraft:mace',"modifier_name":'strength_restrictions:mace_no_enchant'}
execute unless score @s Strength_SMP+Mace-Ultimate_Duration matches 1.. if items entity @s weapon.offhand minecraft:mace run function s_inv_lib:macro/item_modify/with_existing {"beginning_item":'minecraft:mace',"modifier_name":'strength_restrictions:mace_no_enchant'}
execute unless score @s Strength_SMP+Mace-Ultimate_Duration matches 1.. if items entity @s armor.* minecraft:mace run function s_inv_lib:macro/item_modify/with_existing {"beginning_item":'minecraft:mace',"modifier_name":'strength_restrictions:mace_no_enchant'}

# Lunge
execute as @s[scores={Strength_Restrictions+Decreaser=5,Strength_Restrictions+Lunge_Cooldown=1..}] at @s run function strength_restrictions:technical/trigger/ftf/random/lunge/reduce {duration:1}
function strength_restrictions:technical/trigger/ftf/random/lunge/bossbar/get_id

# Contraband
execute store result score @s Strength_Restrictions+Speed_II_Amount run clear @s #strength_restrictions:potions[minecraft:potion_contents={"potion":"minecraft:strong_swiftness"}] 0
execute store result score @s Strength_Restrictions+Strength_Amount run clear @s #strength_restrictions:potions[minecraft:potion_contents={"potion":"minecraft:strength"}] 0
execute store result score @s Strength_Restrictions+Strength_Long_Amount run clear @s #strength_restrictions:potions[minecraft:potion_contents={"potion":"minecraft:long_strength"}] 0
execute store result score @s Strength_Restrictions+Strength_Strong_Amount run clear @s #strength_restrictions:potions[minecraft:potion_contents={"potion":"minecraft:strong_strength"}] 0
execute store result score @s Strength_Restrictions+Totems_Amount run clear @s minecraft:totem_of_undying 0

execute if score @s Strength_Restrictions+Speed_II_Amount matches 1.. run function strength_restrictions:technical/trigger/ftf/random/clear/potions/speed_2
execute if score @s Strength_Restrictions+Strength_Amount matches 1.. run function strength_restrictions:technical/trigger/ftf/random/clear/potions/strength
execute if score @s Strength_Restrictions+Strength_Long_Amount matches 1.. run function strength_restrictions:technical/trigger/ftf/random/clear/potions/long_strength
execute if score @s Strength_Restrictions+Strength_Strong_Amount matches 1.. run function strength_restrictions:technical/trigger/ftf/random/clear/potions/strong_strength
execute if score @s Strength_Restrictions+Totems_Amount matches 1.. run function strength_restrictions:technical/trigger/ftf/random/clear/totem

execute if predicate strength_restrictions:has_speed run function strength_restrictions:technical/trigger/ftf/random/clear/effects/speed
execute if predicate strength_restrictions:has_strength run function strength_restrictions:technical/trigger/ftf/random/clear/effects/strength

# No Fire Enchants:
execute if items entity @s container.* #minecraft:enchantable/durability[minecraft:enchantments~[{enchantments:["minecraft:fire_aspect","minecraft:flame"]}]] run function s_inv_lib:macro/item_modify/with_existing {"beginning_item":'#minecraft:enchantable/durability[minecraft:enchantments~[{enchantments:["minecraft:fire_aspect","minecraft:flame"]}]]',"modifier_name":'strength_restrictions:remove_fire_enchants'}
execute if items entity @s weapon.offhand #minecraft:enchantable/durability[minecraft:enchantments~[{enchantments:["minecraft:fire_aspect","minecraft:flame"]}]] run function s_inv_lib:macro/item_modify/with_existing {"beginning_item":'#minecraft:enchantable/durability[minecraft:enchantments~[{enchantments:["minecraft:fire_aspect","minecraft:flame"]}]]',"modifier_name":'strength_restrictions:remove_fire_enchants'}
execute if items entity @s armor.* #minecraft:enchantable/durability[minecraft:enchantments~[{enchantments:["minecraft:fire_aspect","minecraft:flame"]}]] run function s_inv_lib:macro/item_modify/with_existing {"beginning_item":'#minecraft:enchantable/durability[minecraft:enchantments~[{enchantments:["minecraft:fire_aspect","minecraft:flame"]}]]',"modifier_name":'strength_restrictions:remove_fire_enchants'}
