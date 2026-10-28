# The text over outpost 4: its name and who holds it.
data modify storage realms:outposts label.o4 set value {text:"",extra:[{text:"West outpost\n",color:"gold",bold:1b},{text:"held by ",color:"gray"},{text:"nobody",color:"white"}]}
execute unless score #o4 op.hold matches 1.. run return 0
execute store result storage realms:outposts tmp.h int 1 run scoreboard players get #o4 op.hold
function realms:outposts/o/4/label_holder with storage realms:outposts tmp
