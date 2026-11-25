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

## DonutAuctionHouse stays on Modrinth

The economy's auction house, DonutAuctionHouse (Lorenzo's choice over zAuctionHouse, 25 Nov 2026), needs no
exception. Its Modrinth project (`donut-auction`) is unlisted, so Modrinth's search doesn't show it, but its files
are still served, and 2.0.1 is a release build for Paper 26.3, so it's pinned like any other plugin. Its GitHub
repository publishes no release files, and newer builds go to CurseForge only. If the Modrinth files go away, the
installer fails on the download rather than installing something else; the fallback is zAuctionHouse, which
`relaunch.py` keeps checking (`CANDIDATES`). A CurseForge pin would be a new decision.

Geyser itself stays on Modrinth, but GeyserMC publishes every build there as `beta`, so `entries.PRERELEASE_OK`
lets Geyser take beta builds. Every other plugin is pinned from `release` builds only.

## Considered Options

- Stay on Fabric and add Geyser: Geyser can't show Bedrock players content mods' blocks and mobs, and Java players still need the client pack.
- Fabric for Java, a separate Bedrock server: two worlds, against "one server anyone can join".
- Purpur or Folia instead of Paper: Purpur adds settings we don't need, and Folia breaks most of the plugin stack.
