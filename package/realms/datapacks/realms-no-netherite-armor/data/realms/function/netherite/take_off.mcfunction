# Runs at a player wearing Netherite armor: each piece drops at their feet, as it was.
execute if items entity @s armor.head #realms:netherite_armor run function realms:netherite/drop_head
execute if items entity @s armor.chest #realms:netherite_armor run function realms:netherite/drop_chest
execute if items entity @s armor.legs #realms:netherite_armor run function realms:netherite/drop_legs
execute if items entity @s armor.feet #realms:netherite_armor run function realms:netherite/drop_feet
tellraw @s [{"text":"Netherite armor is off limits until the owners say otherwise (rule 24). ","color":"red"},{"text":"Netherite tools and weapons are fine.","color":"gray"}]
