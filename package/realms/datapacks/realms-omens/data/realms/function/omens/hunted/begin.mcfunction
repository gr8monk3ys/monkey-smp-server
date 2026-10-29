# Returns 1 when it starts: the first of the names sent who is online in survival, outside the arena,
# with a streak of 3 or more now.
execute unless data storage realms:omens hunt[0] run return 0
data modify storage realms:omens target set from storage realms:omens hunt[0]
data remove storage realms:omens hunt[0]
execute store result score #r om run function realms:omens/hunted/mark with storage realms:omens target
execute if score #r om matches 1 run return 1
return run function realms:omens/hunted/begin
