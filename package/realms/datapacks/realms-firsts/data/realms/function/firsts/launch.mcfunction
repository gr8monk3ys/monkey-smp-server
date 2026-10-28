# Run by realms:rules/launch before challenges/launch sets #launched. At a world's first launch, a
# first claimed before it (by hand, in test play) is cleared; a launch run again later clears nothing.
execute if score #launched rw.day matches 1 run return 0
function realms:firsts/clear
# Whoever is online now without an item first's item can claim it from the start (no one-second gap).
function realms:firsts/clean
