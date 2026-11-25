# Relaunch plugin stack (Season 1, Paper 26.3)

Every jar the relaunch server runs. `tools/relaunch.py` pins the whole list in one run (keep its `STACK` in step
with this table), and `tools/check_updates.py` keeps the pins current afterwards. Status is from the pin run on
25 Nov 2026 against Paper 26.3 build 262; re-run it before the boot test and again in mid-January.

Config paths are under the server folder. The installer copies `package/monkey/defaults/<path>` once, on first
install, so a config shipped there is the starting point and the live file is the admins' afterwards.

| Plugin | Modrinth slug | What it does | Config owner | 26.3 status |
|---|---|---|---|---|
| Geyser | `geyser` | Bedrock players join the Java server | platform | 2.12.1-b1308 (beta channel, see below) |
| Floodgate | GeyserMC download API | Bedrock players join with their Xbox account, no Java account | platform | 2.2.5 build 141 |
| LuckPerms | `luckperms` | groups and permissions | ranks (groups), platform (storage) | 5.5.71 |
| EssentialsX | `essentialsx` | homes, warps, /tpa, kits, and the Vault economy | economy | **no 26.3 release yet** |
| EssentialsX Spawn | `essentialsx-spawn` | spawn point and first-join spawn | rules | **no 26.3 release yet** |
| LPC | `lpc-chat` | chat format from LuckPerms prefixes and PlaceholderAPI (shows DeluxeTags) | store | **26.2 only** (4.4.0) |
| VaultUnlocked | `vaultunlocked` | the Vault API that economy, shop and store plugins talk to | platform | 2.20.3 |
| GrimAC | `grimac` | anti-cheat, Bedrock-aware through Floodgate | platform | 2.3.74 |
| Chunky | `chunky` | pre-generates the world inside the border before launch | platform | 1.5.66 |
| WorldEdit | `worldedit` | build tools for staff; WorldGuard needs it | platform | 7.4.6 |
| WorldGuard | `worldguard` | spawn and safe-zone regions (no PvP there) | rules | 7.0.21 |
| GriefPrevention | `griefprevention` | player land claims with a golden shovel | rules | 16.18.8 |
| PlaceholderAPI | `placeholderapi` | placeholders for chat, tab, scoreboards and the store | platform | 2.12.3 |
| ViaVersion | `viaversion` | Java clients newer than the server can join | platform | 5.12.3 |
| ViaBackwards | `viabackwards` | Java clients older than the server can join | platform | 5.12.3 |
| BlueMap | `bluemap` | web map, fitted to the world border, no player markers | platform | 5.29 |
| LifeStealZ | `lifestealz` | hearts: lose one on death to a player, gain one on a kill | rules | 2.21.1 |
| PvPManager | `pvpmanager` | combat tag, newbie protection, blocks /home and /tpa in combat | rules | 4.0.30 |
| EconomyShopGUI | `economyshopgui` | the server shop | economy | 7.3.4 |
| Tebex | `tebex` | store checkout; its secret is set on the server with `tebex secret`, never in the repo | store | **26.2 only** (2.4.6) |
| UltraCosmetics | `ultracosmetics` | cosmetics (gadgets, pets, particles) | store | **26.3 only as a dev build** (3.17-DEV-b1) |
| DeluxeTags | `deluxetags` | `/tags` picker for chat tags | store | 1.10.0 |

Not pinned yet, because nothing on Modrinth fits:

- **Auction house.** DonutAuctionHouse isn't on Modrinth. Lorenzo decides between allowing it as a hash-pinned GitHub download (a change to the installer's source rule) and zAuctionHouse (`zauctionhouse`), which is on Modrinth.
- **Fallback economy provider** if EssentialsX has no release by 15 Jan: OpenEco (`openeco`), the economy workstream's pick.

`tools/relaunch.py` checks OpenEco and zAuctionHouse for the same Minecraft version on every run (`CANDIDATES`) and lists them under "Candidates" in its report, without pinning them.

## Why these, and not others

- **Pinned from Modrinth only, or not at all.** The installer downloads every jar and checks its hash (ADR-0002), and `tools/entries.py` only lets a jar come from Modrinth's CDN. A plugin that is only on SpigotMC or a vendor site can't be installed that way. That ruled out HuskClaims (GriefPrevention instead) and the original auction house and fallback economy picks. Floodgate is the one exception: its Paper jar is published only on GeyserMC's own download API (ADR-0010).
- **Geyser and the beta channel.** Every other plugin is pinned from Modrinth's `release` channel only. GeyserMC publishes every Geyser build as `beta`, including the ones it recommends, so `entries.PRERELEASE_OK` lets Geyser take beta builds.
- **Chat.** EssentialsX Chat doesn't read PlaceholderAPI, so DeluxeTags' `%deluxetags_tag%` wouldn't show. LPC formats chat from LuckPerms prefixes and suffixes and reads PlaceholderAPI, with no injector plugin.
- **Dropped from the Fabric server:** Simple Voice Chat (needs a client mod), Open Parties and Claims (GriefPrevention), Easy NPC, Ledger, ServerCore, Lithium and Krypton (Paper's own patches cover them), the Fabric Tebex build, and the Fabric-only content mods. `docs/relaunch/platform.md` has the whole map.
