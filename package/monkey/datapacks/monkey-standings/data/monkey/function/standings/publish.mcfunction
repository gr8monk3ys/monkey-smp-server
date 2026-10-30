# Builds the board from the two tables tools/standings.py writes (week: this week so far; last: last
# week's final standings), then every board display picks it up within a second.
data modify storage monkey:standings board set value {text:"",extra:[{text:"Faction standings\n",color:"gold",bold:1b}]}
data modify storage monkey:standings board.extra append from storage monkey:standings week
# The wanted board's Most Wanted (tools/wanted.py): empty while it is off.
data modify storage monkey:standings board.extra append from storage monkey:standings wanted
data modify storage monkey:standings board.extra append value {text:"\n"}
data modify storage monkey:standings board.extra append from storage monkey:standings last
data modify storage monkey:standings board.extra append value {text:"\nScored as Cup 40, land 20, Strength 20, kills this week 20 (a war enemy's count twice), each as a share of the leader; +5 a bounty; +1 an hour holding an outpost (at most 20).\n/trigger standings shows this in chat.",color:"dark_gray"}
scoreboard players add #board st.ver 1
