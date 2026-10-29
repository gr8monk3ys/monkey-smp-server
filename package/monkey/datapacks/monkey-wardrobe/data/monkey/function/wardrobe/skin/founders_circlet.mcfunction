execute unless score @s rw.launch matches 1.. run return run tellraw @s {"text":"Founder's Circlet is locked: Played on Season I's launch weekend.","color":"red"}
execute unless items entity @s armor.head #monkey:wardrobe_helms run return run tellraw @s {"text":"Wear an ordinary helmet first.","color":"red"}
item modify entity @s armor.head monkey:wardrobe/founders_circlet
playsound minecraft:item.armor.equip_chain player @s ~ ~ ~ 1 1.4
tellraw @s [{"text":"Founder's Circlet on. ","color":"green"},{"text":"It changes the look only.","color":"gray"}]
