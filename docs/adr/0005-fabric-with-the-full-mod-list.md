---
status: accepted (supersedes ADR-0001)
---
# Fabric 26.3 with the full mod list, instead of Paper with Towns & Nations

From 2.0 the server runs Fabric on Minecraft 26.3 so that the curated mod list (about 110 server-side mods: Moog's structures, Naturalist, Variants & Ventures, Easy Magic and the rest) actually runs, which Paper cannot do. The price is Towns & Nations: no Fabric mod offers wars or land capture, so factions are parties, allies and land claims from Open Parties and Claims, and 2.0 needs a fresh 26.3 world plus a 26.3 client pack. Paper releases stay available as 1.x, and the tools and installer still understand Paper manifests if this decision is ever reversed.

## Considered Options

- Keep Paper 1.x and add only what has datapack or plugin versions: wars stay, but roughly half the list (55 server mods) stays out.
- Run both as separate packages: twice the upkeep for a small group of players.
