execute unless data storage realms:outposts cands[0] run return run function realms:outposts/done
data modify storage realms:outposts cand set from storage realms:outposts cands[0]
data remove storage realms:outposts cands[0]
function realms:outposts/pick with storage realms:outposts cand
