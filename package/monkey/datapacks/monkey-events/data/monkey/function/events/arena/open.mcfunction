execute unless data storage monkey:events arena.lx run return run tellraw @s {"text":"Set the entrance first: /function monkey:events/arena/set_lobby","color":"red"}
execute unless data storage monkey:events arena.px run return run tellraw @s {"text":"Set the waiting room first: /function monkey:events/arena/set_pit","color":"red"}
scoreboard players set #arena ev.state 1
scoreboard players enable @a arena
tellraw @a [{"text":"Arena Glory is open. ","color":"gold"},{"text":"Come to the arena entrance with an empty inventory and ","color":"gray"},{"text":"[join]","color":"green","click_event":{"action":"run_command","command":"/trigger arena set 1"},"hover_event":{"action":"show_text","value":"Your Strength is set to +3 inside; your gear stays safe because you bring none."}},{"text":". Your real Strength comes back when you leave.","color":"gray"}]
