# Macro {b}: the menu's line for faction b.
scoreboard players operation #a dp.tmp = @s st.faction
$scoreboard players set #b dp.tmp $(b)
function realms:diplomacy/pair
scoreboard players add #rows dp.tmp 1
function realms:diplomacy/row_show with storage realms:diplomacy pair
