# As a player: the contest (and their faction's entry), then the hall.
execute if score #open mn matches 1 run tellraw @s ["",{"text":"Monument of the Month, ","color":"gold"},{"nbt":"contest.month","storage":"monkey:monuments","color":"gold"},{"text":": ","color":"gold"},{"nbt":"contest.theme","storage":"monkey:monuments","color":"white"},{"text":" (","color":"gray"},{"nbt":"contest.about","storage":"monkey:monuments","color":"gray"},{"text":"). Build it with your faction, then stand at it and ","color":"gray"},{"text":"/trigger monument","color":"aqua","click_event":{"action":"suggest_command","command":"/trigger monument"}},{"text":". Voting is on the Discord.","color":"gray"}]
execute unless score #open mn matches 1 run tellraw @s {"text":"No monument contest is taking entries right now.","color":"gray"}
execute if score #open mn matches 1 if score @s st.faction matches 1.. run function monkey:monuments/mine_of
function monkey:monuments/hall
