# Staff: ends the omen now. A Meteor's drop goes on: /function realms:drops/stop ends that.
execute unless score #state om matches 1.. run return run tellraw @s {"text":"No omen is on.","color":"red"}
execute unless score #state om matches 2 run tellraw @a {"text":"Staff called the omen off.","color":"gray"}
function realms:omens/end
tellraw @s {"text":"Omen stopped.","color":"green"}
