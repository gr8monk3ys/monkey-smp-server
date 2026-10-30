schedule function monkey:camera/second 20t replace
execute if score #open cm matches 1 run function monkey:camera/close
execute if score #open cm matches 2.. run scoreboard players remove #open cm 1
scoreboard players enable @a[scores={cm.ok=1}] camera
scoreboard players remove @a[scores={cm.wait=1..}] cm.wait 1
scoreboard players set @a[scores={cm.ok=1,cm.hurt=1..}] cm.wait 15
scoreboard players reset @a[scores={cm.hurt=1..}] cm.hurt
execute as @a[scores={camera=1..}] run function monkey:camera/use
execute as @a[scores={cm.in=1}] run function monkey:camera/check
