# Macro {now, open, close, label} from the timer (tools/sieges.py commands): the minute, the seconds until
# the window open now or next opens (0: open now) and closes, and its hours in words.
$scoreboard players set #now sg $(now)
scoreboard players set #sec sg 0
$scoreboard players set #opens sg $(open)
$scoreboard players set #closes sg $(close)
$data modify storage monkey:sieges label set value "$(label)"
scoreboard players set #synced sg 1
execute if score #on sg matches 1 run function monkey:sieges/check
