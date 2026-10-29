# The ceasefire is over: normal rules again, and the banned items go.
scoreboard players set #anarchy ev.state 0
bossbar remove monkey:anarchy
clear @a minecraft:totem_of_undying
clear @a minecraft:end_crystal
clear @a minecraft:enchanted_golden_apple
tellraw @a {"text":"The ceasefire is over and the normal rules are back. Totems, end crystals and enchanted golden apples were cleared; any found later fall under the bans.","color":"green"}
