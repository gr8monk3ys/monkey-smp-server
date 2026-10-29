execute unless score @s rw.challenges matches 9.. run return run tellraw @s {"text":"Vanguard Helm is locked: 9 weekly challenges.","color":"red"}
execute unless items entity @s armor.head #monkey:wardrobe_helms run return run tellraw @s {"text":"Wear an ordinary helmet first.","color":"red"}
item modify entity @s armor.head monkey:wardrobe/vanguard
playsound minecraft:item.armor.equip_chain player @s ~ ~ ~ 1 1.4
tellraw @s [{"text":"Vanguard Helm on. ","color":"green"},{"text":"It changes the look only.","color":"gray"}]
