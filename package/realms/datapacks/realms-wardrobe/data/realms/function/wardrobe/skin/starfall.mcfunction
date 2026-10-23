execute unless score @s rw.days matches 30.. run return run tellraw @s {"text":"Starfall is locked: 30 days played.","color":"red"}
execute unless items entity @s weapon.mainhand #realms:wardrobe_blades run return run tellraw @s {"text":"Hold an ordinary sword in your main hand first.","color":"red"}
item modify entity @s weapon.mainhand realms:wardrobe/starfall
playsound minecraft:item.armor.equip_chain player @s ~ ~ ~ 1 1.4
tellraw @s [{"text":"Starfall on. ","color":"green"},{"text":"It changes the look only.","color":"gray"}]
