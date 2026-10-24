execute unless score @s rw.hours matches 10.. run return run tellraw @s {"text":"Emberfang is locked: 10 hours played.","color":"red"}
execute unless items entity @s weapon.mainhand #realms:wardrobe_blades run return run tellraw @s {"text":"Hold an ordinary sword in your main hand first.","color":"red"}
item modify entity @s weapon.mainhand realms:wardrobe/emberfang
playsound minecraft:item.armor.equip_chain player @s ~ ~ ~ 1 1.4
tellraw @s [{"text":"Emberfang on. ","color":"green"},{"text":"It changes the look only.","color":"gray"}]
