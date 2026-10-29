# An event started (or the season was locked) while an omen was on: the event takes over. A Meteor's
# drop carries on: drops.py's own rules apply to it.
execute unless score #state om matches 2 run tellraw @a {"text":"An event is starting, so the omen is over.","color":"gray"}
function monkey:omens/end
