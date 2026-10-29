execute unless score #busy op matches 1 run return 0
execute if function realms:outposts/stopped run return run function realms:outposts/abort
function realms:outposts/check_at with storage realms:outposts cand
