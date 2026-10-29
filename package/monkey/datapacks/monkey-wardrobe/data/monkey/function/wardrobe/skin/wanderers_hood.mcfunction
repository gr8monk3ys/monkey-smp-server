execute unless score @s rw.months matches 12.. run return run tellraw @s {"text":"Wanderer's Hood is locked: 12 pass months.","color":"red"}
execute unless items entity @s armor.head #monkey:wardrobe_helms run return run tellraw @s {"text":"Wear an ordinary helmet first.","color":"red"}
item modify entity @s armor.head monkey:wardrobe/wanderers_hood
playsound minecraft:item.armor.equip_chain player @s ~ ~ ~ 1 1.4
tellraw @s [{"text":"Wanderer's Hood on. ","color":"green"},{"text":"It changes the look only.","color":"gray"}]
