# Macro {lo, hi, how}: a 7-day war ended (time, peace, gone or staff): logged with its kills for the
# Sunday post (tools/diplomacy.py report), and its own scores cleared. The caller ends dp.war.
$execute unless score #$(lo).$(hi) dp.until matches -2147483648.. run return 0
$scoreboard players operation #ka dp.tmp = #$(lo).$(hi) dp.score
$scoreboard players operation #kb dp.tmp = #$(hi).$(lo) dp.score
$function monkey:diplomacy/log {kind:"war_end",a:$(lo),b:$(hi)}
$data modify storage monkey:diplomacy log[-1].how set value "$(how)"
execute store result storage monkey:diplomacy log[-1].ka int 1 run scoreboard players get #ka dp.tmp
execute store result storage monkey:diplomacy log[-1].kb int 1 run scoreboard players get #kb dp.tmp
$scoreboard players reset #$(lo).$(hi) dp.until
$scoreboard players reset #$(lo).$(hi) dp.score
$scoreboard players reset #$(hi).$(lo) dp.score
$data remove storage monkey:diplomacy wars[{lo:$(lo),hi:$(hi)}]
