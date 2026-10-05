# Running a Minecraft Java Roleplay Server in 2026: Research Report

*Researched 2026-10-04. Version and maintenance facts come from the Modrinth, PaperMC, Purpur, Fabric, NeoForge and SpigotMC APIs, queried live. Hosting prices and RAM rules of thumb come from vendor and blog pages and are less reliable; those are flagged.*

## Recommendation

For a small friend group (2 to 10 people):
- **Self-host** on this PC.
- Put the server files on **C:** (the SSD) and back them up to D:.
- Use **playit.gg** so friends can connect without router changes.
- **Whitelist only.**
- Stay on **26.1.2** to match the game you already play.

| | **Path A: Fabric server from your modpack** | **Path B: Paper server with RP plugins** |
|---|---|---|
| Best if | You want friends in *your* modded world; RP is light | RP mechanics come first (character cards, towns, NPCs, economy, dice) |
| Friends need | Your modpack (exported from Prism as .mrpack) | Plain Minecraft. Optional: Distant Horizons, Iris, Simple Voice Chat |
| RP tools | Thinner | Much richer and more mature |
| Keeps DH / Terralith / Tectonic / voice | Yes / yes / yes / yes | Yes (DH Support plugin) / yes (datapack) / yes (datapack) / yes |
| Loses | Bedrock crossplay | Better Combat, YUNG's structures and other content mods |

**Pick:**
- **Path B** if "roleplay server" is the real goal.
- **Path A** if the goal is "my modpack with friends, plus some RP flavour."

**Skip at first:**
- Bedrock crossplay.
- The paid plugins (ItemsAdder, Nexo, Citizens) until you know you need them.

## 1. Types of RP servers

| Type | What it needs |
|---|---|
| **Town / medieval / fantasy** | Character cards, local chat and emotes, land claims or towns (Towny, Lands, Open Parties and Claims), a light economy, NPCs, a lore wiki. Optional: dice, custom items, quests (BetonQuest, Typewriter) |
| **City / life RP** | Strong economy (Vault-compatible), jobs (Jobs Reborn), shops (ChestShop), plot rental, `/me` and `/do` commands (RP Plugin, RPUniverse), often custom models (ItemsAdder or Nexo, paid) |
| **Nation / war RP** | Towny or Towns & Nations, a web map (BlueMap or squaremap), PvP rules, Discord, active staff. Highest admin effort |
| **Theme park / Disney RP** | Build tools (WorldEdit/FAWE), NPCs (Citizens, FancyNpcs), custom models, audio, warps, little or no survival. IP risk if public or monetized |
| **Story / campaign (D&D-style)** | Dice, character cards, voice chat, NPCs, WorldEdit. Small and whitelisted. Probably the best fit for a friend group |

## 2. Platform choice

**Current versions:**
- **Paper:** 26.1.2 stable, 26.2 stable, 26.3 still beta. Needs Java 25.
- **Purpur:** has 26.1.2 to 26.3.
- **Fabric:** 26.1.2 to 26.3 stable.
- **NeoForge:** 26.3 still beta.

**Stay on 26.1.2 or 26.2 for now:** many RP plugins only list up to 26.2, and EssentialsX tops out at 26.1.2.

| | Plugin server (Paper/Purpur) | Modded (Fabric/NeoForge) | Hybrid (Arclight/Mohist) |
|---|---|---|---|
| RP plugins | Huge and mature | Smaller | Promises both, often breaks |
| Friends need | Plain Minecraft | The matching modpack | Same as modded |
| Content depth | Vanilla + resource packs | Unlimited | Unlimited in theory |
| Performance | Best | Fine with Lithium, C2ME, FerriteCore, ModernFix | Worst |
| Admin difficulty | Easiest | Medium | Hardest |
| Bedrock crossplay | Practical (Geyser) | Not practical | No |

Hybrids are not recommended.

### Reusing your 97-mod pack as a server (Path A)

| Mod | On the server? |
|---|---|
| Iris, Sodium | **No.** Client-only |
| Distant Horizons | **Yes, recommended.** The server builds far terrain and sends it to every player with DH. Players without DH can still join |
| Tectonic, Terralith | **Yes, required.** World generation runs on the server |
| YUNG's API | Yes, on both server and clients |
| YUNG's structure mods | Server-side only |
| Better Combat | Yes, on both. **Every friend must install it** |
| Simple Voice Chat | Yes. Needs **UDP port 24454** opened or tunnelled |
| Lithium, FerriteCore, ModernFix, C2ME | Yes. Good server performance mods |
| Xaero's maps | Client-only is fine |

**Rule of thumb:** each mod's Modrinth page has a "Server: Required / Optional / Unsupported" label.
- Required and optional mods go on the server.
- Friends get the full pack.
- Remove anything marked "Unsupported" from the server.

### Bedrock crossplay (Geyser + Floodgate)
- **On Paper:** feasible. Bedrock players connect on UDP 19132.
- **With your Fabric pack:** effectively impossible, because Bedrock clients can't run the client-side mods.
- **RP drawbacks:** no clickable chat links or tab-complete, and signs behave differently.
- **Verdict:** skip unless a friend can only play on console or phone.

## 3. RP plugin stack (checked 2026-10-04)

✅ = maintained with 26.x builds; ⚠️ = stale or lagging.

### Paper / Purpur

| Function | Plugin | Cost | Status |
|---|---|---|---|
| Character cards + local chat | **Character Cards** | Free | ✅ 26.2. Small project; name/age/race/lore cards, local chat with spy, EssentialsX nickname sync |
| `/me` `/do` `/roll` `/try` `/whisper` `/yell` | **RP Plugin** | Free | ⚠️ up to 1.21.11 |
| City RP framework | **RPUniverse** | Free | ⚠️ up to 1.21.5 |
| Local chat | **Better Local Chat** (50-block radius, `!` for global) | Free | ✅ 26.3 |
| Basics, economy, kits, warps, nicknames | **EssentialsX** | Free | ✅ 26.1.2 (no 26.2/26.3 build yet) |
| Economy API bridge | **VaultUnlocked** (original Vault is stale, 2020) | Free | ✅ 26.3 |
| Towns / nations | **Towny** | Free | ✅ 26.2 |
| Towns / nations (RP-focused) | **Towns & Nations** | Free | ✅ 26.3 |
| Land claims | **GriefPrevention** | Free | ✅ 26.3 |
| Land claims | **Lands** | €19.99 | ✅ 26.3 |
| Town claims | **HuskTowns** | £9.99 (free if self-built) | ⚠️ no 26.x release |
| Permissions | **LuckPerms** | Free | ✅ 26.3 |
| Jobs | **Jobs Reborn** | Free | ✅ 26.2 |
| Player shops | **ChestShop** | Free | ✅ 26.2 |
| NPCs | **Citizens** | $19.99 (free dev builds historically) | ✅ 26.2 |
| NPCs | **FancyNpcs** | Free | ✅ 26.3 |
| Quests / dialogue | **BetonQuest**, **Typewriter** | Free | ✅ |
| Custom items / models | **ItemsAdder**, **Oraxen**, **Nexo** | €19.99 each | ✅ |
| Custom items / models | **CraftEngine Community Edition** | Free | ✅ 26.2 |
| Voice | **Simple Voice Chat** (UDP 24454) | Free | ✅ 26.3 |
| Voice | **Plasmo Voice** | Free | ✅ 26.3 |
| Rollback / anti-grief | **CoreProtect** | Free | ✅ |
| Discord link | **DiscordSRV** | Free | ✅ 26.3 |
| World editing | **WorldEdit**, **FastAsyncWorldEdit** | Free | ✅ 26.3 |
| Web map | **BlueMap** (3D), **squaremap** (2D) | Free | ✅ 26.3 |
| Web map | **Dynmap** | Free | ⚠️ |
| Distant Horizons on Paper | **Distant Horizons Support** | Free | ✅ up to 26.2 |
| Pre-generation / profiling / tab list | **Chunky**, **spark**, **TAB** | Free | ✅ |

"RPEngine" could not be verified as an existing current plugin.

### Fabric equivalents (Path A, all free)
- **Chat and names:** Styled Chat, Better Local Chat, Styled Nicknames.
- **Claims and logging:** Open Parties and Claims, Ledger (rollback).
- **Permissions:** LuckPerms.
- **Emotes:** Emote (server-side).
- **Economy:** EconomyCraft.
- **Custom server-side content:** Polymer.
- **Maps, editing, pre-gen, voice:** BlueMap, squaremap, WorldEdit, Chunky, Simple Voice Chat.
- **Gaps:** no character-card mod for 26.x, weak NPCs (Taterzens is stale), nothing as complete as Towny.

## 4. Hosting

### Self-host on this PC (recommended for friends)

**Hardware:**
- **RAM:** 64 GB is plenty.
- **CPU:** the i7-8700K is the limit. Rough estimates (not benchmarks): about 10 to 15 players on Paper, about 5 to 10 on the heavy Fabric pack while you also play.
- **Pre-generate the world** with Chunky before people join.
- **Storage:** server on C:, backups to D:. A pregenerated world is about 5 to 20 GB, and Distant Horizons data grows over time.
- **Uptime:** the server only runs while the PC is on. Agree on "RP nights" or disable sleep while hosting.

**Getting friends connected:**
1. **playit.gg (easiest).** The free tier covers Java, Bedrock and Simple Voice Chat; premium is $3/month. Your home IP stays hidden. You create the account yourself.
2. **Port forwarding.** TCP 25565, plus UDP 24454 for voice. Exposes your IP, needs router access, and some ISPs (CGNAT) block it.
3. **e4mc mod.** Fine for a quick test of a LAN world; not a real server.

**Security:**
- Keep `online-mode=true` (Mojang requires genuine accounts).
- Use a whitelist.
- Keep software updated.
- Download plugins only from Modrinth, Hangar, SpigotMC or official sites.
- Don't give OP to people you don't fully trust; use LuckPerms roles.
- Open only the ports you need.

### Paid hosts
⚠️ Mostly from comparison blogs. Only PebbleHost's price was confirmed on its own site.

| Host | ~Price per GB of RAM per month | Notes |
|---|---|---|
| PebbleHost | $1 budget (confirmed); ~$2.25 premium | |
| BisectHosting | ~$2.60 | Big modpack library |
| Shockbyte | ~$2.80 | |
| Sparked Host | ~$2.59 | |
| Apex | ~$3 to $5 | Watch the renewal price |
| exaroton | Pay per hour; starts when someone joins | Good for scheduled RP nights |

**Rough monthly cost:** about $6 to $20 for a 6 to 8 GB Paper server, about $10 to $35 for a 10 to 12 GB modded server.

### Free hosts
- **Minehut:** 1 GB RAM, 10 players, sleeps when empty. Too small for mods.
- **Aternos:** about 2 to 4 GB, curated mod list, queues. ⚠️ Details unverified. OK for a tiny Paper RP server; poor for your modpack.

## 5. RAM / CPU sizing (estimates)

| Players | Paper RP (25 to 40 plugins) | Fabric RP (your pack + DH on the server) |
|---|---|---|
| 5 | 4 to 6 GB, easy to self-host | 8 to 10 GB, OK if you pregenerate |
| 15 | 6 to 8 GB, OK | 10 to 14 GB, marginal on the 8700K |
| 40 | 10 to 12 GB on a fast host CPU | 16 GB+ on premium hardware; not a self-host target |

**Tuning:**
- Set equal `-Xms` and `-Xmx`.
- Cap view distance at 8 to 10; Distant Horizons covers the far view.
- Use spark to find lag.

## 6. Simplest starting setup (Path B, Paper 26.1.2, 2 to 10 friends)

1. **Write the concept:** one paragraph of setting, plus 5 to 10 rules.
2. **Install Java 25.**
3. **Create a folder on C:,** e.g. `C:\MCServer\rp\`, and download Paper 26.1.2 from papermc.io.
4. **First run:** `java -Xms6G -Xmx6G -jar paper.jar --nogui`. Accept `eula.txt`, then stop the server.
5. **Edit `server.properties`:** `white-list=true`, `online-mode=true`, `view-distance=8`, `simulation-distance=6`.
6. **Terrain:** put the Tectonic and Terralith datapacks into `world/datapacks` *before* the world generates.
7. **Add plugins:**
   - LuckPerms, EssentialsX, VaultUnlocked
   - Character Cards
   - GriefPrevention or Towny
   - CoreProtect, WorldEdit/FAWE
   - Simple Voice Chat
   - BlueMap or squaremap
   - Chunky, FancyNpcs
   - Optional: DH Support, DiscordSRV, RP Plugin
8. **Pre-generate:** `/chunky radius 3000`, then `/chunky start`.
9. **Permissions:** create LuckPerms groups `default`, `builder`, `moderator`, `admin` (`/lp editor`).
10. **Connect friends:** install playit.gg and create tunnels for Minecraft Java (TCP) and voice (UDP 24454).
11. **Whitelist friends:** `whitelist add <name>`.
12. **Friends' game:** plain 26.1.2. Simple Voice Chat to hear voice; Sodium, Iris and DH optional.
13. **Backups:** copy the server folder to `D:\Backups\MCServer\<date>` on a schedule. Keep about 7 daily and 4 weekly copies.
14. **Discord:** channels for rules, lore, character applications, announcements, out-of-character chat and support.

**Path A differences:**
- Use the Fabric server installer.
- Copy the server-side mods from Prism and remove the client-only ones (Iris, Sodium, …).
- Add LuckPerms, Open Parties and Claims, Ledger, Styled Chat/Nicknames, Better Local Chat, Emote, BlueMap and Chunky.
- Share the pack with friends as an .mrpack.
- Expect 8 to 10 GB of RAM.

## 7. Community, admin and legal

**Community:**
- **Whitelist vs public:** whitelist for friends. Public RP servers attract griefers and need staff.
- **Rules:** no metagaming or powergaming, in-character vs out-of-character separation, consent for dark RP, what a character "death" means, build standards, local chat for in-character talk.
- **Lore doc:** world summary, factions, map, timeline, races/classes, and a character-sheet template.
- **Staff:** you as owner, 1 to 2 moderators, and optionally a lore keeper/GM and builders, each with their own permission group.

**Mojang's rules (minecraft.net usage guidelines):**

Allowed:
- Charging the same price to everyone for access.
- Donations with no personal perks; server-wide rewards for donation goals are fine.
- Cosmetics, except capes.
- Gameplay perks, only if they don't hurt others' experience or give an advantage.
- In-game currency with no real-world value.

Required:
- Genuine paid accounts only.
- Content suitable for all ages.
- Prices disclosed before joining.

**In practice:** don't sell anything. If you need to cover hosting, ask for donations with no individual perks.

**Disney / theme-park RP:**
- A private, non-monetized fan build is low-risk in practice.
- Risk rises if you monetize, use Disney names, logos or music, or advertise publicly.
- Safer: "inspired by" original parks and names, no copyrighted audio, no sales.
- Not legal advice.

## 8. Time and cost

| Item | Path B (Paper, self-host) | Path A (Fabric, self-host) | Paid host |
|---|---|---|---|
| Initial setup | 4 to 8 h | 6 to 12 h | 1 to 2 h less |
| World prep | 2 to 6 h of computer time, plus building | Same, plus DH generation | Same |
| Lore, rules, NPCs | 5 to 20 h | Same | Same |
| Ongoing | 1 to 2 h/week | 2 to 3 h/week | ~1 h/week |
| Money | $0 + electricity (~2.5 to 3.5 kWh/day if left on 24/7) | Same | $6 to 35/month |
| Optional paid plugins | All avoidable with free alternatives | n/a | Same |

## Could not verify
- Most hosting prices (pages blocked or JavaScript-rendered).
- Aternos limits.
- "RPEngine".
- Citizens' free builds.
- A HuskTowns 26.x build.
- RP Plugin and DH Support load-tested on 26.1.2.
- Disney enforcement history.
- 8700K player capacity (estimate only).
- Hybrid servers.

## Key sources
- PaperMC: https://fill.papermc.io/v3/projects/paper and https://docs.papermc.io/paper/getting-started
- Fabric: https://meta.fabricmc.net/v2/versions/game
- Minecraft 26.3: https://minecraft.wiki/w/Java_Edition_26.3
- Mojang usage guidelines: https://www.minecraft.net/en-us/usage-guidelines
- Simple Voice Chat server setup: https://modrepo.de/minecraft/voicechat/wiki/server_setup_self_hosted
- Geyser limitations: https://geysermc.org/wiki/geyser/current-limitations/
- playit.gg: https://playit.gg/ and https://playit.gg/pricing
- Minehut: https://minehut.com/
- Nexo: https://nexomc.com/
- HuskTowns: https://github.com/WiIIiam278/HuskTowns
- PebbleHost: https://pebblehost.com/minecraft
- Sparked Host RAM guide: https://help.sparkedhost.com/en/article/how-much-ram-do-you-need-for-a-minecraft-server-10s60h6/
- DH Support plugin: https://modrinth.com/plugin/distant-horizons-support
- Modrinth project API: https://api.modrinth.com/v2/project/<slug>
- SpigotMC data: https://api.spiget.org/v2/resources/<id>
- Hangar: https://hangar.papermc.io/api/v1/projects
- Price estimates (treat with caution): https://wisehosting.com/blog/cheapest-minecraft-server-hosting-providers and https://teramont.net/blog/best-minecraft-server-hosting-2026
