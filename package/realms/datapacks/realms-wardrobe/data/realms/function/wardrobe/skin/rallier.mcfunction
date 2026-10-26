execute unless score @s rw.events matches 3.. run return run tellraw @s {"text":"Rallier is locked: 3 events attended.","color":"red"}
execute unless items entity @s weapon.mainhand #realms:wardrobe_blades run return run tellraw @s {"text":"Hold an ordinary sword in your main hand first.","color":"red"}
item modify entity @s weapon.mainhand realms:wardrobe/rallier
playsound minecraft:item.armor.equip_chain player @s ~ ~ ~ 1 1.4
tellraw @s [{"text":"Rallier on. ","color":"green"},{"text":"It changes the look only.","color":"gray"}]
