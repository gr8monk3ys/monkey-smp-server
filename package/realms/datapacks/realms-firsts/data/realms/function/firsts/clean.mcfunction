# Each item first counts for a player only once they have been seen without its item since the launch,
# so one carried over from test play doesn't claim it. Run at the launch and every second after it.
execute as @a[tag=!rf.clean.diamond] unless items entity @s container.* minecraft:diamond unless items entity @s armor.* minecraft:diamond unless items entity @s weapon.offhand minecraft:diamond run tag @s add rf.clean.diamond
execute as @a[tag=!rf.clean.debris] unless items entity @s container.* minecraft:ancient_debris unless items entity @s armor.* minecraft:ancient_debris unless items entity @s weapon.offhand minecraft:ancient_debris run tag @s add rf.clean.debris
execute as @a[tag=!rf.clean.mace] unless items entity @s container.* minecraft:mace unless items entity @s armor.* minecraft:mace unless items entity @s weapon.offhand minecraft:mace run tag @s add rf.clean.mace
execute as @a[tag=!rf.clean.elytra] unless items entity @s container.* minecraft:elytra unless items entity @s armor.* minecraft:elytra unless items entity @s weapon.offhand minecraft:elytra run tag @s add rf.clean.elytra
