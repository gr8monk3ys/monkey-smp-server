# From monkey:rules/second, before rule 26's expiry check, only while someone has a bubble.
execute store result score #keep ck run time query gametime
scoreboard players add #keep ck 40
execute as @a[scores={ck.bubble=1..}] run function monkey:catchup/hold
