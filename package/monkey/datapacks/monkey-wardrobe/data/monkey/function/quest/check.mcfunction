# Runs as a player taking part, once a second: each open step whose score is reached is done.
execute unless score @s rq.guide matches 1.. if score @s rq.guide matches 1.. run function monkey:quest/step/guide
execute unless score @s rq.home matches 1.. if score @s rq.home matches 1.. run function monkey:quest/step/home
execute unless score @s rq.faction matches 1.. if score @s st.faction matches 1.. run function monkey:quest/step/faction
execute unless score @s rq.claim matches 1.. if score @s st.claimed matches 1.. run function monkey:quest/step/claim
execute unless score @s rq.outpost matches 1.. if score @s op.visit matches 1.. run function monkey:quest/step/outpost
execute unless score @s rq.day = #today rw.day run function monkey:quest/remind
