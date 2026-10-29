execute unless score @s rw.tier matches 1.. run return run tellraw @s {"text":"Lantern is locked: Supporters at Ember or above.","color":"red"}
execute unless items entity @s weapon.mainhand #monkey:wardrobe_blades run return run tellraw @s {"text":"Hold an ordinary sword in your main hand first.","color":"red"}
item modify entity @s weapon.mainhand monkey:wardrobe/lantern
playsound minecraft:item.armor.equip_chain player @s ~ ~ ~ 1 1.4
tellraw @s [{"text":"Lantern on. ","color":"green"},{"text":"It changes the look only.","color":"gray"}]
