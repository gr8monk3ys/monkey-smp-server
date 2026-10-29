execute unless data storage monkey:outposts cands[0] run return run function monkey:outposts/done
data modify storage monkey:outposts cand set from storage monkey:outposts cands[0]
data remove storage monkey:outposts cands[0]
function monkey:outposts/pick with storage monkey:outposts cand
