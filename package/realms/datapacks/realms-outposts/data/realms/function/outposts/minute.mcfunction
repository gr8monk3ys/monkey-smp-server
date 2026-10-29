scoreboard players set #sec op 0
# A gone faction's minutes are reset by the hourly timer (tools/outposts.py gone_minutes).
execute if score #o1 op.hold matches 1.. run function realms:outposts/o/1/minute
execute if score #o2 op.hold matches 1.. run function realms:outposts/o/2/minute
execute if score #o3 op.hold matches 1.. run function realms:outposts/o/3/minute
execute if score #o4 op.hold matches 1.. run function realms:outposts/o/4/minute
