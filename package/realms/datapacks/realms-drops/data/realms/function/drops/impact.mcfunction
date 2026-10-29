# A Meteor coming down, at the drop's middle: its label, a flash and a bang. Nothing is broken or set alight.
execute positioned over motion_blocking_no_leaves run summon minecraft:text_display ~ ~1.8 ~ {Tags:["dr.label"],billboard:"center",text:{"text":"Meteor","color":"light_purple","bold":true}}
particle minecraft:explosion_emitter ~ ~1 ~ 0 0 0 0 1 force
particle minecraft:flame ~ ~1 ~ 1 1.5 1 0.05 80 force
particle minecraft:large_smoke ~ ~2 ~ 1 2 1 0.02 60 force
playsound minecraft:entity.generic.explode master @a ~ ~ ~ 6 0.6
