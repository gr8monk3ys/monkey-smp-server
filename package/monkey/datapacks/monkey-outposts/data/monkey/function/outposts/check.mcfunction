execute unless score #busy op matches 1 run return 0
execute if function monkey:outposts/stopped run return run function monkey:outposts/abort
function monkey:outposts/check_at with storage monkey:outposts cand
