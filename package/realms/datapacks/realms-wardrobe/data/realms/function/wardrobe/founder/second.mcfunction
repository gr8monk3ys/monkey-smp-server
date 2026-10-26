# Once a second, from the wardrobe's: while the window is open, count everyone online.
execute unless score #founder.open rw.day matches 1 run return 0
execute store result score #founder.now rw.day run time query gametime
execute if score #founder.now rw.day >= #founder.until rw.day run return run function realms:wardrobe/founder/close
scoreboard players add @a rw.launchtime 1
tellraw @a[scores={rw.launchtime=1}] [{"text":"Launch weekend: ","color":"gold"},{"text":"stay 10 minutes in all to keep Founder's Circlet, a helm skin.","color":"yellow"}]
scoreboard players set @a[scores={rw.launchtime=600..}] rw.launch 1
