# Macro {name}: no more camera (out within a second if in it now, or at their next login).
$scoreboard players reset $(name) cm.ok
$scoreboard players reset $(name) camera
$tellraw @s {"text":"$(name) is no longer approved for the camera.","color":"yellow"}
