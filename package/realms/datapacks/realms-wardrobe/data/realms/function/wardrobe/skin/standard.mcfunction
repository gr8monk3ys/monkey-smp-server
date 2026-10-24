execute unless score @s rw.tier matches 2.. run return run tellraw @s {"text":"Standard is locked: Supporters at Banner or above.","color":"red"}
execute unless items entity @s weapon.mainhand #realms:wardrobe_blades run return run tellraw @s {"text":"Hold an ordinary sword in your main hand first.","color":"red"}
item modify entity @s weapon.mainhand realms:wardrobe/standard
playsound minecraft:item.armor.equip_chain player @s ~ ~ ~ 1 1.4
tellraw @s [{"text":"Standard on. ","color":"green"},{"text":"It changes the look only.","color":"gray"}]
