# As the killer; the victim is tagged wt.target. Arena kills, faction mates and pact partners claim nothing.
execute if entity @s[tag=ev.arena] run return 0
execute if score @s st.faction = @a[tag=wt.target,limit=1] st.faction run return run title @s actionbar {"text":"No bounty: they're in your faction.","color":"red"}
execute if score @s st.faction matches 1.. if score @a[tag=wt.target,limit=1] st.faction matches 1.. if function monkey:wanted/pact run return run title @s actionbar {"text":"No bounty: your factions have a pact.","color":"red"}
scoreboard players add @s st.hunts 1
tellraw @a [{"text":"Bounty claimed: ","color":"gold"},{"selector":"@s","color":"white"},{"text":" took the bounty on ","color":"gray"},{"selector":"@a[tag=wt.target,limit=1]","color":"white"},{"text":" (","color":"gray"},{"score":{"name":"@a[tag=wt.target,limit=1]","objective":"st.wanted"},"color":"white"},{"text":" posted). The Bounty Hunter title is theirs.","color":"gray"}]
# The title, unless they show another (a supporter color or title is never taken away for it).
execute if entity @s[team=] run team join bounty_hunter @s
scoreboard players set @a[tag=wt.target,limit=1] st.wanted 0
scoreboard players add @a[tag=wt.target,limit=1] wt.gen 1
execute store result score #now wt run time query gametime
scoreboard players operation @a[tag=wt.target,limit=1] wt.free = #now wt
scoreboard players add @a[tag=wt.target,limit=1] wt.free 432000
