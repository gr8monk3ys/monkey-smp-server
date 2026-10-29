# Once a second. The End is closed until an admin runs monkey:rules/open_end (rule 23).
execute unless score #end_open monkey.rules matches 1 in minecraft:the_end as @a[distance=0..] run function monkey:rules/leave_end
# The welcome, a few seconds after a first join so the loading screen doesn't swallow it.
execute as @a[scores={monkey.welcome=1}] run function monkey:rules/welcome
scoreboard players remove @a[scores={monkey.welcome=2..}] monkey.welcome 1
execute as @a[tag=!monkey.joined] run function monkey:rules/first_join
# Rule 26.
execute store result score #now monkey.rules run time query gametime
execute as @a[scores={end_grace=1..}] run function monkey:rules/grace_end
execute as @a if score @s monkey.grace <= #now monkey.rules run function monkey:rules/grace_end
# The item goes with the grace (the launch and an admin's grace_end take both), it's off in the arena,
# and it comes back after a death. A copy anywhere else (looted from a corpse) is taken away; clear takes
# the body slot's too, so it only runs on someone who has one.
execute as @a if items entity @s container.* *[custom_data~{monkey_grace:{}}] run clear @s *[custom_data~{monkey_grace:{}}]
execute as @a if items entity @s weapon.offhand *[custom_data~{monkey_grace:{}}] run clear @s *[custom_data~{monkey_grace:{}}]
execute as @a if items entity @s player.cursor *[custom_data~{monkey_grace:{}}] run clear @s *[custom_data~{monkey_grace:{}}]
execute as @a if items entity @s player.crafting.* *[custom_data~{monkey_grace:{}}] run clear @s *[custom_data~{monkey_grace:{}}]
execute as @a if items entity @s armor.body *[custom_data~{monkey_grace:{}}] unless score @s monkey.grace > #now monkey.rules run item replace entity @s armor.body with minecraft:air
execute as @a[tag=ev.arena] if items entity @s armor.body *[custom_data~{monkey_grace:{}}] run item replace entity @s armor.body with minecraft:air
execute as @a[tag=!ev.arena] if score @s monkey.grace > #now monkey.rules unless items entity @s armor.body * run item replace entity @s armor.body with minecraft:paper[custom_data={monkey_grace:{}},enchantments={"monkey:pvp_grace":1},equippable={slot:"body",swappable:false,dispensable:false,allowed_entities:"minecraft:player"},item_name="PvP grace"]
execute as @e[type=minecraft:mannequin,tag=player_corpses.corpse] if items entity @s armor.body *[custom_data~{monkey_grace:{}}] run item replace entity @s armor.body with minecraft:air
schedule function monkey:rules/second 20t replace
