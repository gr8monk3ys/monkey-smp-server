execute unless score @s rw.quest matches 1.. run return run tellraw @s {"text":"Pathfinder is locked: Finished the first-week quest (/trigger quest).","color":"red"}
execute unless items entity @s weapon.mainhand #monkey:wardrobe_blades run return run tellraw @s {"text":"Hold an ordinary sword in your main hand first.","color":"red"}
item modify entity @s weapon.mainhand monkey:wardrobe/pathfinder
playsound minecraft:item.armor.equip_chain player @s ~ ~ ~ 1 1.4
tellraw @s [{"text":"Pathfinder on. ","color":"green"},{"text":"It changes the look only.","color":"gray"}]
