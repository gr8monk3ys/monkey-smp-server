# As the poster; #v wt is the target's wt.id. Each refusal says why and posts nothing.
execute unless score @s st.faction matches 1.. run return run tellraw @s {"text":"Join a faction first: bounties are between factions. The server picks a new one up within the hour.","color":"red"}
execute store result score #now wt run time query gametime
# Only for someone who has posted: an operation that reads an unset score sets it to 0.
scoreboard players set #since wt -1
execute if score @s wt.last matches -2147483648.. run scoreboard players operation #since wt = #now wt
execute if score @s wt.last matches -2147483648.. run scoreboard players operation #since wt -= @s wt.last
execute if score #since wt matches 0..863999 run return run tellraw @s {"text":"You posted a bounty in the last 12 hours: one every 12 hours.","color":"red"}
execute as @a if score @s wt.id = #v wt run tag @s add wt.target
execute unless entity @a[tag=wt.target] run return run tellraw @s {"text":"They aren't online any more.","color":"red"}
execute if entity @s[tag=wt.target] run return run tellraw @s {"text":"Not on yourself.","color":"red"}
execute unless entity @a[tag=wt.target,scores={st.faction=1..}] run return run tellraw @s {"text":"They're in no faction the server knows: bounties are between factions.","color":"red"}
execute if score @s st.faction = @a[tag=wt.target,limit=1] st.faction run return run tellraw @s {"text":"They're in your faction.","color":"red"}
execute if function monkey:wanted/pact run return run tellraw @s {"text":"Your factions have a pact.","color":"red"}
execute if score @a[tag=wt.target,limit=1] wt.free > #now wt run return run tellraw @s {"text":"A bounty on them was claimed in the last 6 hours: give them a break.","color":"red"}
execute if score @s wt.mark = #v wt if score @s wt.mgen = @a[tag=wt.target,limit=1] wt.gen run return run tellraw @s {"text":"Your bounty on them is still up.","color":"red"}
scoreboard players add @a[tag=wt.target,limit=1] st.wanted 1
scoreboard players operation @s wt.mark = #v wt
scoreboard players operation @s wt.mgen = @a[tag=wt.target,limit=1] wt.gen
scoreboard players operation @s wt.last = #now wt
tellraw @a [{"text":"Wanted: ","color":"red"},{"selector":"@s","color":"white"},{"text":" put a bounty on ","color":"gray"},{"selector":"@a[tag=wt.target,limit=1]","color":"white"},{"text":" (","color":"gray"},{"score":{"name":"@a[tag=wt.target,limit=1]","objective":"st.wanted"},"color":"white"},{"text":" on them now). Kill them in a fair fight outside the arena to claim it: ","color":"gray"},{"text":"/trigger wanted","color":"aqua","click_event":{"action":"run_command","command":"/trigger wanted"}}]
