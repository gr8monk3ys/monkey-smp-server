# Macro {f}: the player's faction's entry, if it has one.
$execute unless data storage monkey:monuments entries.f$(f) run return run tellraw @s {"text":"Your faction hasn't entered yet.","color":"gray"}
$function monkey:monuments/mine_at with storage monkey:monuments entries.f$(f)
