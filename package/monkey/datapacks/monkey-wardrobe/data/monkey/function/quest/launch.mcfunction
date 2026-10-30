# Run by monkey:challenges/launch, before it sets #launched. At a world's first launch, everything test play
# did goes: who was signed up, every step, the skin. A launch run again later clears nothing.
execute if score #launched rw.day matches 1 run return 0
scoreboard players reset * rq.state
scoreboard players reset * rq.day
scoreboard players reset * rq.guide
scoreboard players reset * rq.home
scoreboard players reset * rq.faction
scoreboard players reset * rq.claim
scoreboard players reset * rq.outpost
# The skin only in Season I: a later season's world carries what players earned before.
execute if score #season rw.day matches 1 run scoreboard players reset * rw.quest
execute if score #season rw.day matches 1 run scoreboard players reset * rw.quest.seen
advancement revoke @a only monkey:quest/home
