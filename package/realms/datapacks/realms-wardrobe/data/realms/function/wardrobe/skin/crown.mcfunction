execute unless score @s rw.tier matches 3.. run return run tellraw @s {"text":"Crown is locked: Supporters at Crown or above.","color":"red"}
execute unless items entity @s armor.head #realms:wardrobe_helms run return run tellraw @s {"text":"Wear an ordinary helmet first.","color":"red"}
item modify entity @s armor.head realms:wardrobe/crown
playsound minecraft:item.armor.equip_chain player @s ~ ~ ~ 1 1.4
tellraw @s [{"text":"Crown on. ","color":"green"},{"text":"It changes the look only.","color":"gray"}]
