execute unless score @s rw.founder matches 1.. run return run tellraw @s {"text":"Founder's Edge is locked: Played during the first season.","color":"red"}
execute unless items entity @s weapon.mainhand #monkey:wardrobe_blades run return run tellraw @s {"text":"Hold an ordinary sword in your main hand first.","color":"red"}
item modify entity @s weapon.mainhand monkey:wardrobe/founders_edge
playsound minecraft:item.armor.equip_chain player @s ~ ~ ~ 1 1.4
tellraw @s [{"text":"Founder's Edge on. ","color":"green"},{"text":"It changes the look only.","color":"gray"}]
