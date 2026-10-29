# PvP kills count for the standings, except in the event arena (its fights are for the Cup).
execute as @a[scores={st.pk=1..},tag=!ev.arena] run scoreboard players operation @s st.kills += @s st.pk
scoreboard players set @a[scores={st.pk=1..}] st.pk 0
execute as @a[scores={standings=1..}] run function monkey:standings/use
