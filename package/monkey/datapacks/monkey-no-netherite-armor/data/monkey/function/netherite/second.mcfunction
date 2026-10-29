# The stamp (#netherite_rule) says the rule holds; it goes stale once the pack is off.
execute store result score #netherite_rule monkey.rules run time query gametime
execute as @a at @s if items entity @s armor.* #monkey:netherite_armor run function monkey:netherite/take_off
schedule function monkey:netherite/second 20t replace
