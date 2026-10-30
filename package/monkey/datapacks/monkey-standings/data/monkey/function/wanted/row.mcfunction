# As a rival online: their line in the asker's menu.
scoreboard players add #rows wt 1
execute store result storage monkey:wanted row.id int 1 run scoreboard players get @s wt.id
function monkey:wanted/row_show with storage monkey:wanted row
