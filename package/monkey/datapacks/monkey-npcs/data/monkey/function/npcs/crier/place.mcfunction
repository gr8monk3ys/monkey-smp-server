# Macro {x:0.5,y:72,z:3.5,yaw:180}: puts the Town Crier there, facing yaw (0 south, 90 west, 180 north,
# 270 east). From the server console or RCON, with someone standing near the spot so it is loaded.
# Its UUID is fixed, so running this again replaces the Town Crier with the preset's current version
# (removing it first: an import onto the same UUID would keep an owner or edits the preset doesn't set).
easy_npc delete 91d80ba8-ad23-547d-9658-def753c77a93
$easy_npc preset import data monkey:easy_npc/preset/humanoid/crier.npc.snbt $(x) $(y) $(z) 91d80ba8-ad23-547d-9658-def753c77a93
$rotate 91d80ba8-ad23-547d-9658-def753c77a93 $(yaw) 0
tag 91d80ba8-ad23-547d-9658-def753c77a93 add global.ignore
