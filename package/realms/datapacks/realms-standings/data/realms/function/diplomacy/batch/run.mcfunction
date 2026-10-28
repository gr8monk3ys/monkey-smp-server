# Makes the changes in storage realms:diplomacy batch in order, each realms:diplomacy/<f> with its entry
# (tools/diplomacy.py batch_commands): many changes per RCON command.
execute unless data storage realms:diplomacy batch[0] run return 0
function realms:diplomacy/batch/one with storage realms:diplomacy batch[0]
data remove storage realms:diplomacy batch[0]
function realms:diplomacy/batch/run
