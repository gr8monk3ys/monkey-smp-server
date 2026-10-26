execute unless score @s rw.challenges matches 18.. run return run tellraw @s {"text":"Pinnacle is locked: 18 weekly challenges.","color":"red"}
execute unless items entity @s weapon.mainhand #realms:wardrobe_blades run return run tellraw @s {"text":"Hold an ordinary sword in your main hand first.","color":"red"}
item modify entity @s weapon.mainhand realms:wardrobe/pinnacle
playsound minecraft:item.armor.equip_chain player @s ~ ~ ~ 1 1.4
tellraw @s [{"text":"Pinnacle on. ","color":"green"},{"text":"It changes the look only.","color":"gray"}]
