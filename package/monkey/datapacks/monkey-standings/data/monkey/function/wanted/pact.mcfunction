# 1 when @s's faction and the tagged player's (wt.target) have a pact (tools/diplomacy.py), else 0.
scoreboard players operation #a dp.tmp = @s st.faction
scoreboard players operation #b dp.tmp = @a[tag=wt.target,limit=1] st.faction
function monkey:diplomacy/pair
return run function monkey:wanted/pact_of with storage monkey:diplomacy pair
