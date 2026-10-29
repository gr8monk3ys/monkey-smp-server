# The text over outpost 2: its name and who holds it.
data modify storage monkey:outposts label.o2 set value {text:"",extra:[{text:"East outpost\n",color:"gold",bold:1b},{text:"held by ",color:"gray"},{text:"nobody",color:"white"}]}
execute unless score #o2 op.hold matches 1.. run return 0
execute store result storage monkey:outposts tmp.h int 1 run scoreboard players get #o2 op.hold
function monkey:outposts/o/2/label_holder with storage monkey:outposts tmp
