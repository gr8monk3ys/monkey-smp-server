# /trigger monument: enters (or moves) the faction's entry while a contest is open; otherwise, and with
# set 2, what is on and the hall.
scoreboard players operation #use mn = @s monument
scoreboard players set @s monument 0
execute if score #use mn matches 1 if score #open mn matches 1 run return run function monkey:monuments/submit
function monkey:monuments/info
