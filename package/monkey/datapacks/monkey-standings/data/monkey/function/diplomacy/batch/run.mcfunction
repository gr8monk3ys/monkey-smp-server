# Makes the changes in storage monkey:diplomacy batch in order, each monkey:diplomacy/<f> with its entry
# (tools/diplomacy.py batch_commands): many changes per RCON command.
execute unless data storage monkey:diplomacy batch[0] run return 0
function monkey:diplomacy/batch/one with storage monkey:diplomacy batch[0]
data remove storage monkey:diplomacy batch[0]
function monkey:diplomacy/batch/run
