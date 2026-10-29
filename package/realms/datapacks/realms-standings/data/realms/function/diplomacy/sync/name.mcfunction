$data modify storage realms:factions names.f$(n) set value {text:""}
$data modify storage realms:factions names.f$(n).text set from storage realms:diplomacy batch[0].v
