execute unless score @s rw.champion matches 1.. run return run tellraw @s {"text":"Champion's Helm is locked: The season champion's faction.","color":"red"}
execute unless items entity @s armor.head #monkey:wardrobe_helms run return run tellraw @s {"text":"Wear an ordinary helmet first.","color":"red"}
item modify entity @s armor.head monkey:wardrobe/champions_helm
playsound minecraft:item.armor.equip_chain player @s ~ ~ ~ 1 1.4
tellraw @s [{"text":"Champion's Helm on. ","color":"green"},{"text":"It changes the look only.","color":"gray"}]
