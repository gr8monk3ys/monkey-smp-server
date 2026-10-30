# Macro {state}: the act's record ends this way.
$data modify storage monkey:boss at.state set value "$(state)"
function monkey:boss/record_at with storage monkey:boss at
