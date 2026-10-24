# Ends anarchy early, without what its end does.
scoreboard players set #anarchy ev.state 0
scoreboard players set #anarchy ev.timer 0
bossbar remove realms:anarchy
tellraw @a {"text":"Staff ended the Anarchy early.","color":"gray"}
