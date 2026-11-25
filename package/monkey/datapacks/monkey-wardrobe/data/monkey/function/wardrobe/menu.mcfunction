# The menu (/trigger wardrobe, /trigger challenges): the counts, this week's challenges, the server goal,
# and the first-week quest's line for a player taking it.
tellraw @s ["",{"text":"\nYour progress","color":"gold","bold":true},{"text":"  challenges new every Monday, 12 AM Pacific","color":"gray"}]
tellraw @s [{"text":"","color":"gray"},{"score":{"name":"@s","objective":"rw.days"},"color":"white"}," days played, ",{"score":{"name":"@s","objective":"rw.hours"},"color":"white"}," hours played, ",{"score":{"name":"@s","objective":"rw.events"},"color":"white"}," events, ",{"score":{"name":"@s","objective":"rw.challenges"},"color":"white"}," challenges done in all seasons"]
function monkey:challenges/lines
function monkey:goal/line
function monkey:quest/status
