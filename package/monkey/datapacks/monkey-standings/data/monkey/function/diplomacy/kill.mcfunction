# Macro {b}, as the killer: a war enemy's kill counts twice (st.kills has the first), outside the arena,
# as st.kills does, and only after the launch.
execute unless score #launched rw.day matches 1 run return 0
execute if entity @s[tag=ev.arena] run return 0
execute unless score @s st.faction matches 1.. run return 0
scoreboard players operation #a dp.tmp = @s st.faction
$scoreboard players set #b dp.tmp $(b)
function monkey:diplomacy/pair
function monkey:diplomacy/war_kill with storage monkey:diplomacy pair
