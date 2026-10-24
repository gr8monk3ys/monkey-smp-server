# Once a second. The End is closed until an admin runs realms:rules/open_end (rule 23).
execute unless score #end_open realms.rules matches 1 in minecraft:the_end as @a[distance=0..] run function realms:rules/leave_end
schedule function realms:rules/second 20t replace
