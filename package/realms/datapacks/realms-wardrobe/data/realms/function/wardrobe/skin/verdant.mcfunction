execute unless score @s rw.invites matches 1.. run return run tellraw @s {"text":"Verdant is locked: 1 friend invited.","color":"red"}
execute unless items entity @s weapon.mainhand #realms:wardrobe_blades run return run tellraw @s {"text":"Hold an ordinary sword in your main hand first.","color":"red"}
item modify entity @s weapon.mainhand realms:wardrobe/verdant
playsound minecraft:item.armor.equip_chain player @s ~ ~ ~ 1 1.4
tellraw @s [{"text":"Verdant on. ","color":"green"},{"text":"It changes the look only.","color":"gray"}]
