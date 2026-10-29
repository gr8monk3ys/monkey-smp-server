execute unless score @s rw.tier matches 3.. run return run tellraw @s {"text":"Regalia is locked: Supporters at Crown or above.","color":"red"}
execute unless items entity @s weapon.mainhand #monkey:wardrobe_blades run return run tellraw @s {"text":"Hold an ordinary sword in your main hand first.","color":"red"}
item modify entity @s weapon.mainhand monkey:wardrobe/regalia
playsound minecraft:item.armor.equip_chain player @s ~ ~ ~ 1 1.4
tellraw @s [{"text":"Regalia on. ","color":"green"},{"text":"It changes the look only.","color":"gray"}]
