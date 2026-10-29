# Macro {h}: a minute held counts while a survival player of another faction is online (someone who
# could take it back). A faction that is gone holds nothing.
$execute unless data storage monkey:factions names.f$(h) run return run function monkey:outposts/o/1/gone
$execute store result score #mine op if entity @a[gamemode=survival,scores={st.faction=$(h)}]
execute store result score #all op if entity @a[gamemode=survival,scores={st.faction=1..}]
execute unless score #all op > #mine op run return 0
$scoreboard players add #f$(h) op.min 1
