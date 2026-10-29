# Macro {seq}: after the close's war_over and offer_over (tools/diplomacy.py week_end): says so if a war
# ended, and trims the log up to seq, the closed week's last declaration (posted to Discord).
execute if score #ended dp.state matches 1.. run tellraw @a [{"text":"The week is over, and so are its wars. ","color":"gold"},{"text":"Pacts stand. A leader can declare war again with /trigger diplomacy.","color":"gray"}]
scoreboard players set #ended dp.state 0
$scoreboard players set #trim dp.tmp $(seq)
function realms:diplomacy/trim
