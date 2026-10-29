execute unless score @s rw.days matches 7.. run return run tellraw @s {"text":"Laurel is locked: 7 days played.","color":"red"}
execute unless items entity @s armor.head #monkey:wardrobe_helms run return run tellraw @s {"text":"Wear an ordinary helmet first.","color":"red"}
item modify entity @s armor.head monkey:wardrobe/laurel
playsound minecraft:item.armor.equip_chain player @s ~ ~ ~ 1 1.4
tellraw @s [{"text":"Laurel on. ","color":"green"},{"text":"It changes the look only.","color":"gray"}]
