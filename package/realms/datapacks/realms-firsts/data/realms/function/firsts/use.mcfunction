# Runs as a player who used /trigger firsts: every milestone and who holds it.
scoreboard players set @s firsts 0
scoreboard players enable @s firsts
# How many this player holds, into their own rf score (only the # holders are the pack's state).
scoreboard players set @s rf 0
execute if score @s rf.diamond matches 1.. run scoreboard players add @s rf 1
execute if score @s rf.nether matches 1.. run scoreboard players add @s rf 1
execute if score @s rf.fortress matches 1.. run scoreboard players add @s rf 1
execute if score @s rf.bastion matches 1.. run scoreboard players add @s rf 1
execute if score @s rf.debris matches 1.. run scoreboard players add @s rf 1
execute if score @s rf.vault matches 1.. run scoreboard players add @s rf 1
execute if score @s rf.mace matches 1.. run scoreboard players add @s rf 1
execute if score @s rf.raid matches 1.. run scoreboard players add @s rf 1
execute if score @s rf.wither matches 1.. run scoreboard players add @s rf 1
execute if score @s rf.beacon matches 1.. run scoreboard players add @s rf 1
execute if score @s rf.end matches 1.. run scoreboard players add @s rf 1
execute if score @s rf.dragon matches 1.. run scoreboard players add @s rf 1
execute if score @s rf.elytra matches 1.. run scoreboard players add @s rf 1
execute if score @s rf.netherite matches 1.. run scoreboard players add @s rf 1
tellraw @s ["",{"text":"\nServer Firsts","color":"gold","bold":true},{"text":"  the first on the server to each, for the season","color":"gray"}]
function realms:firsts/show/diamond
function realms:firsts/show/nether
function realms:firsts/show/fortress
function realms:firsts/show/bastion
function realms:firsts/show/debris
function realms:firsts/show/vault
function realms:firsts/show/mace
function realms:firsts/show/raid
function realms:firsts/show/wither
function realms:firsts/show/beacon
function realms:firsts/show/end
function realms:firsts/show/dragon
function realms:firsts/show/elytra
function realms:firsts/show/netherite
tellraw @s ["",{"text":"You hold ","color":"gray"},{"score":{"name":"@s","objective":"rf"},"color":"white"},{"text":". The most firsts at the season's end earns a title.","color":"gray"}]
