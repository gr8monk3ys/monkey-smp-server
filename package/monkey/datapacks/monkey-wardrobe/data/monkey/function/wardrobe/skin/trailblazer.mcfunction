execute unless score @s rw.challenges matches 3.. run return run tellraw @s {"text":"Trailblazer is locked: 3 weekly challenges.","color":"red"}
execute unless items entity @s weapon.mainhand #monkey:wardrobe_blades run return run tellraw @s {"text":"Hold an ordinary sword in your main hand first.","color":"red"}
item modify entity @s weapon.mainhand monkey:wardrobe/trailblazer
playsound minecraft:item.armor.equip_chain player @s ~ ~ ~ 1 1.4
tellraw @s [{"text":"Trailblazer on. ","color":"green"},{"text":"It changes the look only.","color":"gray"}]
