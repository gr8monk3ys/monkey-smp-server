# Ends raid early, without what its end does.
scoreboard players set #raid ev.state 0
scoreboard players set #raid ev.timer 0
bossbar remove realms:raid
tellraw @a {"text":"Staff ended the Faction Raid early.","color":"gray"}
