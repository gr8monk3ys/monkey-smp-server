# The stamp (#netherite_rule) says the rule holds; it goes stale once the pack is off.
execute store result score #netherite_rule realms.rules run time query gametime
execute as @a at @s if items entity @s armor.* #realms:netherite_armor run function realms:netherite/take_off
schedule function realms:netherite/second 20t replace
