execute unless score @s rw.hallowtide matches 1.. run return run tellraw @s {"text":"Gravelight is locked: From the Hallowtide event (late October).","color":"red"}
execute unless items entity @s weapon.mainhand #realms:wardrobe_blades run return run tellraw @s {"text":"Hold an ordinary sword in your main hand first.","color":"red"}
item modify entity @s weapon.mainhand realms:wardrobe/gravelight
playsound minecraft:item.armor.equip_chain player @s ~ ~ ~ 1 1.4
tellraw @s [{"text":"Gravelight on. ","color":"green"},{"text":"It changes the look only.","color":"gray"}]
