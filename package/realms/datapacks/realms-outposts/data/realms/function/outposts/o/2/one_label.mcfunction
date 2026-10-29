tag @e[type=minecraft:text_display,tag=op.l2,limit=1] add op.keep
kill @e[type=minecraft:text_display,tag=op.l2,tag=!op.keep]
tag @e[type=minecraft:text_display,tag=op.keep] remove op.keep
