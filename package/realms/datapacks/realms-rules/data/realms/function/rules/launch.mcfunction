# Rule 23. An admin runs this once, at launch: PvP and the Nether close for 60 minutes.
gamerule pvp false
gamerule allow_entering_nether_using_portals false
scoreboard players set #end_open realms.rules 0
schedule function realms:rules/launch_over 3600s replace
tellraw @a [{"text":"[Monkey SMP] ","color":"gold"},{"text":"Welcome to Season I! PvP, the Nether and the End are closed for the first 60 minutes.","color":"yellow"}]
