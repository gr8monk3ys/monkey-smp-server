# Macro {x:0.5,y:72,z:3.5,yaw:180}: puts the Guide there, facing yaw (0 south, 90 west, 180 north,
# 270 east). From the server console or RCON, with someone standing near the spot so it is loaded.
# Its UUID is fixed, so running this again replaces the Guide with the preset's current version
# (removing it first: an import onto the same UUID would keep an owner or edits the preset doesn't set).
easy_npc delete d20849a4-bcc2-5970-bca9-f3aae3bdbd04
$easy_npc preset import data realms:easy_npc/preset/humanoid/guide.npc.snbt $(x) $(y) $(z) d20849a4-bcc2-5970-bca9-f3aae3bdbd04
$rotate d20849a4-bcc2-5970-bca9-f3aae3bdbd04 $(yaw) 0
tag d20849a4-bcc2-5970-bca9-f3aae3bdbd04 add global.ignore
