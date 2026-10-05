---
status: superseded by ADR-0005
---
# Paper with Towns & Nations, not a Fabric server

The server runs Paper so it can use the Towns & Nations plugin (towns, nations, alliances, land claims and wars), which is the core of the factions play. No Fabric mod offers wars or land capture, and the hybrid servers that load Fabric mods and Paper plugins together were unstable or unavailable for this Minecraft version. The cost is roughly 48 Fabric content mods (new mobs, blocks and items) that can't run on the server; world generation and structures were kept by using their datapack versions, and visual mods live in the client pack, where they still work.

## Considered Options

- A Fabric server with every mod plus Open Parties and Claims: claims and allies, but no wars.
- A hybrid server (Cardboard/Banner): stopped at an older Minecraft version and not reliable enough for a server people depend on.
