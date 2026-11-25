---
status: accepted (supersedes ADR-0005)
---
# Paper and Geyser for the relaunch, with no client mods

From the relaunch (Season 1, February 2027) the server runs Paper on Minecraft 26.3, with Geyser and Floodgate
so Bedrock players can join, and a plugin stack instead of the Fabric mod list (docs/relaunch/plugin-stack.md).
The relaunch wants anyone to join from Java or Bedrock with a plain client. Fabric's content mods need a client
pack, and Bedrock can't run them at all. Paper also brings the plugins the new format needs: an economy on Vault,
lifesteal and combat tagging, land claims, and a cosmetics store. The price is the curated mod content (structures,
mobs, magic) and Simple Voice Chat. The installer and tools already understood Paper manifests (ADR-0005 kept
them), so the switch is the manifest, the first-run defaults and the removal of the Fabric files.

## Pins from GeyserMC

ADR-0002 pins every jar from Modrinth's CDN. Floodgate is an exception, as our own mods are under ADR-0009:
its Paper build is published only on GeyserMC's download API. A plugin listed in `entries.GEYSERMC_PINS`
(today only `floodgate`) may be pinned from exactly that build's URL,
`https://download.geysermc.org/v2/projects/<project>/versions/<version>/builds/<build>/downloads/spigot`, with
GeyserMC's sha256 checked against the download when it's pinned. `check_updates.py` follows its newest build.
Adding a project to that list is a change to this decision.

## DonutAuctionHouse from GitHub

The economy's auction house, DonutAuctionHouse, isn't on Modrinth either. Lorenzo chose it over zAuctionHouse on
25 Nov 2026, so it may be pinned from GitHub the way ADR-0009 pins our own mods: one named repository, exactly one
release asset's URL, and that file's sha512 recorded when it's pinned and checked on every install. Until its
repository and release are confirmed, it isn't in the manifest and `entries.GITHUB_PINS` lists only mods; adding
it there for plugins is the change this section allows, and no other.

Geyser itself stays on Modrinth, but GeyserMC publishes every build there as `beta`, so `entries.PRERELEASE_OK`
lets Geyser take beta builds. Every other plugin is pinned from `release` builds only.

## Considered Options

- Stay on Fabric and add Geyser: Geyser can't show Bedrock players content mods' blocks and mobs, and Java players still need the client pack.
- Fabric for Java, a separate Bedrock server: two worlds, against "one server anyone can join".
- Purpur or Folia instead of Paper: Purpur adds settings we don't need, and Folia breaks most of the plugin stack.
