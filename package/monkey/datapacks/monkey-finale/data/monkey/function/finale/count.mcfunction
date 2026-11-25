execute unless score @s st.team matches 1.. run function monkey:finale/solo
execute store result storage monkey:finale n.n int 1 run scoreboard players get @s st.team
function monkey:finale/add with storage monkey:finale n
