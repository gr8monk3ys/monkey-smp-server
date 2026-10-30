# Macro pair {a, b, lo, hi}, as a player of faction a who killed one of b in their 7-day war.
$scoreboard players add #$(a).$(b) dp.score 1
$title @s actionbar ["",{"text":"A war kill. ","color":"red"},{"text":"Your faction ","color":"gray"},{"score":{"name":"#$(a).$(b)","objective":"dp.score"},"color":"yellow"},{"text":", theirs ","color":"gray"},{"score":{"name":"#$(b).$(a)","objective":"dp.score"},"color":"yellow"}]
