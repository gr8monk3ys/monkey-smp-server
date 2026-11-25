# Monkey SMP on Modrinth

Modrinth matters for two things now. Every plugin is pinned from it, and the server can have a Modrinth
**server listing** so players find it in Modrinth's server discovery. The relaunch has no client pack: players
join with a plain Java client or with Bedrock ([PLAYERS.md](PLAYERS.md)). So the old **Monkey SMP modpack** and
`tools/modrinth.py`, which uploaded each release's `.mrpack`, are gone.

## The old modpack project (the owner, once)

The modpack `monkeysmp` (`modrinth.com/modpack/monkeysmp`) holds the Fabric client pack, version 2.8.0, and was
submitted for review on 2026-10-28. It can't join the relaunch, so a player who finds it would install about
380 MB for nothing. On modrinth.com, withdraw it from review, or archive it if it was approved, and point its
description at the website's join steps. Don't delete it: the project URL is worth keeping in case the server
ever ships a pack again.

## The server listing

Worth making for the relaunch: it costs nothing, and discovery is where players browse for a server to join.
Make it by hand on modrinth.com; nothing in the repo keeps it current.

| Field | Value |
|---|---|
| Name | Monkey SMP |
| URL | `monkeysmp-server` (the unrelated "monkey smp" server owns `monkey-smp`) |
| Address | `monkeysmp.lscaturchio.xyz` (no port: its SRV record gives 25565, and Modrinth looks SRV records up) |
| Content | no modpack: a plain (vanilla) client joins. Give the Bedrock address, `play.monkeysmp.lscaturchio.xyz` port `19132`, in the description |
| Region | US West (the group plays evenings Pacific; US East only if the VPS is on the East Coast) |
| Language | English |
| Max players | 60 (`max-players` in `defaults/server.properties`) |
| Tags | whichever of Modrinth's fit the relaunch (economy, PvP, lifesteal, SMP, crossplay); not Whitelisted or Modded |

Discovery ranks servers by players online and by verified plays, and drops a server that can't be pinged for a
sustained time, so the server has to stay up and reachable at that address.

**Paid access.** Since July 2026 Modrinth's moderators don't list servers that "require players to pay for
access or donate to be able to join". That is why the Fabric server's listing was never made: it needed a pass.
The relaunch is public (`white-list=false`), so this should only matter if joining ever costs money again; ask
Modrinth support if the store's ranks or cosmetics raise the question. Server listings went through review in a
median of 4 days (checked 2026-10-25).

## Updating this page

When Modrinth answers, or the listing goes live, write the result and the date here, and remove what no longer
applies.
