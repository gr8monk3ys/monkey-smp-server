# A player killed a roused mob (advancement realms:omens/blood_kill): the bonus drop, at their feet.
advancement revoke @s only realms:omens/blood_kill
execute unless score #state om matches 1 run return 0
execute unless score #phase om matches 1 run return 0
execute if score @s om.loot matches 20.. run return 0
scoreboard players add @s om.loot 1
loot spawn ~ ~ ~ loot realms:omens/blood_moon
