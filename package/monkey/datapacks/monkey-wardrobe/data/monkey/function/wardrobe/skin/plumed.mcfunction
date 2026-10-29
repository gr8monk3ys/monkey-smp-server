execute unless score @s rw.events matches 10.. run return run tellraw @s {"text":"Plumed Helm is locked: 10 events attended.","color":"red"}
execute unless items entity @s armor.head #monkey:wardrobe_helms run return run tellraw @s {"text":"Wear an ordinary helmet first.","color":"red"}
item modify entity @s armor.head monkey:wardrobe/plumed
playsound minecraft:item.armor.equip_chain player @s ~ ~ ~ 1 1.4
tellraw @s [{"text":"Plumed Helm on. ","color":"green"},{"text":"It changes the look only.","color":"gray"}]
