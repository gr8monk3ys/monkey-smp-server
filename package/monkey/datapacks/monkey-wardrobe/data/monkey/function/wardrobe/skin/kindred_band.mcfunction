execute unless score @s rw.kin matches 1.. run return run tellraw @s {"text":"Kindred Band is locked: A friend joined with your referral code, or you joined with theirs.","color":"red"}
execute unless items entity @s armor.head #monkey:wardrobe_helms run return run tellraw @s {"text":"Wear an ordinary helmet first.","color":"red"}
item modify entity @s armor.head monkey:wardrobe/kindred_band
playsound minecraft:item.armor.equip_chain player @s ~ ~ ~ 1 1.4
tellraw @s [{"text":"Kindred Band on. ","color":"green"},{"text":"It changes the look only.","color":"gray"}]
