# The launch hour is up: PvP and only the Nether open (rule 23).
gamerule pvp true
gamerule allow_entering_nether_using_portals true
scoreboard players set #launching realms.rules 0
tellraw @a [{"text":"[Monkey SMP] ","color":"gold"},{"text":"The first hour is up: PvP and the Nether are open. The End stays closed for now.","color":"red"}]
