scoreboard players set #phase fn 2
bossbar set monkey:finale color red
# Never below FINAL_SIZE, and a border already that small is left as it is.
execute in minecraft:overworld store result score #size fn run worldborder get
execute if score #size fn matches 257.. in minecraft:overworld run worldborder set 256 48000
tellraw @a ["",{"text":"The finale: ","color":"dark_red","bold":true},{"text":"the border is closing now","color":"red","bold":true},{"text":", down to 256 blocks across around the monument at ","color":"gold"},{"nbt":"at.x","storage":"monkey:finale","color":"yellow"},{"text":", ","color":"yellow"},{"nbt":"at.z","storage":"monkey:finale","color":"yellow"},{"text":" over 40 minutes. Anyone it passes is moved inside.","color":"gold"}]
