# A first claimed without its holder's name (the read failed): read it again where the holder stands
# once they are online, and keep #unnamed set while any is still missing.
scoreboard players set #unnamed rf 0
execute if data storage monkey:firsts held.diamond{name:""} as @a[scores={rf.diamond=1..},limit=1] at @s run function monkey:firsts/rename/diamond
execute if data storage monkey:firsts held.nether{name:""} as @a[scores={rf.nether=1..},limit=1] at @s run function monkey:firsts/rename/nether
execute if data storage monkey:firsts held.fortress{name:""} as @a[scores={rf.fortress=1..},limit=1] at @s run function monkey:firsts/rename/fortress
execute if data storage monkey:firsts held.bastion{name:""} as @a[scores={rf.bastion=1..},limit=1] at @s run function monkey:firsts/rename/bastion
execute if data storage monkey:firsts held.debris{name:""} as @a[scores={rf.debris=1..},limit=1] at @s run function monkey:firsts/rename/debris
execute if data storage monkey:firsts held.vault{name:""} as @a[scores={rf.vault=1..},limit=1] at @s run function monkey:firsts/rename/vault
execute if data storage monkey:firsts held.mace{name:""} as @a[scores={rf.mace=1..},limit=1] at @s run function monkey:firsts/rename/mace
execute if data storage monkey:firsts held.raid{name:""} as @a[scores={rf.raid=1..},limit=1] at @s run function monkey:firsts/rename/raid
execute if data storage monkey:firsts held.wither{name:""} as @a[scores={rf.wither=1..},limit=1] at @s run function monkey:firsts/rename/wither
execute if data storage monkey:firsts held.beacon{name:""} as @a[scores={rf.beacon=1..},limit=1] at @s run function monkey:firsts/rename/beacon
execute if data storage monkey:firsts held.end{name:""} as @a[scores={rf.end=1..},limit=1] at @s run function monkey:firsts/rename/end
execute if data storage monkey:firsts held.dragon{name:""} as @a[scores={rf.dragon=1..},limit=1] at @s run function monkey:firsts/rename/dragon
execute if data storage monkey:firsts held.elytra{name:""} as @a[scores={rf.elytra=1..},limit=1] at @s run function monkey:firsts/rename/elytra
execute if data storage monkey:firsts held.netherite{name:""} as @a[scores={rf.netherite=1..},limit=1] at @s run function monkey:firsts/rename/netherite
execute if data storage monkey:firsts held.diamond{name:""} run scoreboard players set #unnamed rf 1
execute if data storage monkey:firsts held.nether{name:""} run scoreboard players set #unnamed rf 1
execute if data storage monkey:firsts held.fortress{name:""} run scoreboard players set #unnamed rf 1
execute if data storage monkey:firsts held.bastion{name:""} run scoreboard players set #unnamed rf 1
execute if data storage monkey:firsts held.debris{name:""} run scoreboard players set #unnamed rf 1
execute if data storage monkey:firsts held.vault{name:""} run scoreboard players set #unnamed rf 1
execute if data storage monkey:firsts held.mace{name:""} run scoreboard players set #unnamed rf 1
execute if data storage monkey:firsts held.raid{name:""} run scoreboard players set #unnamed rf 1
execute if data storage monkey:firsts held.wither{name:""} run scoreboard players set #unnamed rf 1
execute if data storage monkey:firsts held.beacon{name:""} run scoreboard players set #unnamed rf 1
execute if data storage monkey:firsts held.end{name:""} run scoreboard players set #unnamed rf 1
execute if data storage monkey:firsts held.dragon{name:""} run scoreboard players set #unnamed rf 1
execute if data storage monkey:firsts held.elytra{name:""} run scoreboard players set #unnamed rf 1
execute if data storage monkey:firsts held.netherite{name:""} run scoreboard players set #unnamed rf 1
