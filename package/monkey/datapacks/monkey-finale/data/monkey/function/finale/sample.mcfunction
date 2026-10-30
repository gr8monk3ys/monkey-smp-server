# Macro at {x0, z0, d}: each faction member at the monument (survival, not in the arena) scores a point.
$execute in minecraft:overworld as @a[x=$(x0),y=-64,z=$(z0),dx=$(d),dy=384,dz=$(d),gamemode=survival,tag=!ev.arena,scores={st.faction=1..}] run function monkey:finale/count
