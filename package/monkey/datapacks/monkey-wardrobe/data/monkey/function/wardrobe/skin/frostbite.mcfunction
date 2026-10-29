execute unless score @s rw.days matches 15.. run return run tellraw @s {"text":"Frostbite is locked: 15 days played.","color":"red"}
execute unless items entity @s weapon.mainhand #monkey:wardrobe_blades run return run tellraw @s {"text":"Hold an ordinary sword in your main hand first.","color":"red"}
item modify entity @s weapon.mainhand monkey:wardrobe/frostbite
playsound minecraft:item.armor.equip_chain player @s ~ ~ ~ 1 1.4
tellraw @s [{"text":"Frostbite on. ","color":"green"},{"text":"It changes the look only.","color":"gray"}]
