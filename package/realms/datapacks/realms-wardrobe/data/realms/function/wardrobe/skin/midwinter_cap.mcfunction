execute unless score @s rw.midwinter matches 1.. run return run tellraw @s {"text":"Midwinter Cap is locked: From the Midwinter event (late December).","color":"red"}
execute unless items entity @s armor.head #realms:wardrobe_helms run return run tellraw @s {"text":"Wear an ordinary helmet first.","color":"red"}
item modify entity @s armor.head realms:wardrobe/midwinter_cap
playsound minecraft:item.armor.equip_chain player @s ~ ~ ~ 1 1.4
tellraw @s [{"text":"Midwinter Cap on. ","color":"green"},{"text":"It changes the look only.","color":"gray"}]
