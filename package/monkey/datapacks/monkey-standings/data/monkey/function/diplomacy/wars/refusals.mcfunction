# Macro pair {a, b, lo, hi}: 1 (and says why) when faction a can't start a 7-day war on b now.
$execute if score #$(lo).$(hi) dp.pact matches 1 run return run function monkey:diplomacy/wars/no {why:"You have a pact with them. Break it first (everyone is told)."}
$execute if score #$(lo).$(hi) dp.war matches 1.. run return run function monkey:diplomacy/wars/no {why:"You're at war with them already."}
execute unless score #now sg matches 1.. run return run function monkey:diplomacy/wars/no {why:"The server's clock isn't set yet (it comes every 5 minutes): try again shortly."}
$scoreboard players operation #left dp.tmp = #f$(a) dp.next
scoreboard players operation #left dp.tmp -= #now sg
$execute unless score #f$(a) dp.next matches -2147483648.. run scoreboard players set #left dp.tmp 0
execute if score #left dp.tmp matches ..0 run return 0
scoreboard players add #left dp.tmp 59
scoreboard players operation #left dp.tmp /= #60 dp.tmp
tellraw @s ["",{"text":"Your faction can declare one war every 48 hours: the next in ","color":"red"},{"score":{"name":"#left","objective":"dp.tmp"},"color":"red"},{"text":" h.","color":"red"}]
return 1
