# Relaunch platform: Paper, Geyser and hosting

Season 1 of the relaunch runs Paper on Minecraft 26.3. Anyone can join from Java or Bedrock without client
mods. This page covers what changes from the Fabric server, how the server is tuned, what to host it on, and
how to cut over. The plugin list is in [plugin-stack.md](plugin-stack.md), and the decision is ADR-0010.

## Join addresses

| Client | Address | Port |
|---|---|---|
| Java | `monkeysmp.lscaturchio.xyz` | none (the SRV record gives 25565) |
| Bedrock | `play.monkeysmp.lscaturchio.xyz` | `19132` |

Bedrock doesn't read SRV records, so Bedrock players type the A-record host and the port. Geyser listens on
19132 by default. On Paper it finds Floodgate by itself and lets Bedrock players in with their Xbox accounts,
so no Geyser config ships. Floodgate gives Bedrock names a `.` prefix, so a Bedrock player and a Java player
can't end up with the same name.

## From Fabric to Paper

| Fabric server | Relaunch | Why |
|---|---|---|
| Fabric loader and about 175 mods | Paper and 26 plugins | Bedrock and vanilla clients can't run the content mods, and the brief is "no client mods" |
| Open Parties and Claims | GriefPrevention | claims on a plugin, and HuskClaims can't be pinned |
| LuckPerms (Fabric) | LuckPerms (Paper) | same groups: `defaults/plugins/LuckPerms/yaml-storage/groups` |
| BlueMap (Fabric) | BlueMap (Paper) | same maps, now in `defaults/plugins/BlueMap`; `map_border.py`, `border.py` and `outposts.py` follow the new folder |
| Chunky (Fabric) | Chunky (Paper) | same command |
| Lithium, Krypton, ServerCore, the anti-xray mod | Paper's own patches and settings, plus ChunkSpawnerLimiter | see Performance; Paper rather than Purpur, so every plugin runs on the platform it's built for |
| Simple Voice Chat | dropped | needs a client mod |
| Easy NPC | FancyNpcs | the Guide and the Town Crier keep their behaviour in `monkey-npcs`; staff create the NPC bodies with FancyNpcs |
| Wardrobe skins (`monkey-wardrobe`) | retired | their models came with the client pack; UltraCosmetics covers cosmetics, and the menu keeps challenges, goals and quests |
| Ledger, Tebex (Fabric), content and worldgen mods | dropped | Fabric only; Tebex comes back as the Paper plugin |
| The 13 patched mod and data packs (`package/monkey/patches`) | dropped | they patched Fabric mods and the Fabric data pack |
| Client pack (`client/`) and player installer (`player/`) | not needed | players join with a plain client |
| Our own data packs (`package/monkey/datapacks`) | kept | vanilla data packs run on Paper unchanged |

Three of our data packs still call Fabric content and need a change from the rules workstream before launch.
`monkey-npcs` placed Easy NPC characters (now FancyNpcs, below), `monkey-events` syncs the Strength SMP arena, and
`monkey-nights` mentions Open Parties and Claims in its grace-period text. The other 15 only use vanilla commands.
All 18 are generated for Minecraft 26.2 (`tools/datapacks.py`: `MINECRAFT`, `DATA_FORMAT`, and the rules
pack's treasure list). On 26.3 those need bumping and re-checking, and
`tests/test_datapacks.py` fails until they are. On 26.2 they stay as they are.

Removing the Fabric files (patches, Fabric mod configs, Fabric-only tests and tools, and the voice chat port) is a
separate follow-up PR, and removing the client pack and the player installer is the PR after that. This PR
switches the manifest, so `validate.py` reports the unused patches and the client pack until both land. The three
merge together.

## Performance

Launch night maxed the 2-thread VPS at 12 players on the modded server. Paper without the content mods is far
lighter, but a public server needs headroom for 40 to 60 players. These are the first-run settings, each in
`package/monkey/defaults`:

- **server.properties:** view distance 8, simulation distance 5 (fewer chunks tick per player), sync chunk writes off, and the watchdog back at 60 seconds now that no mod world generation can stall a tick.
- **paper-world-defaults.yml:**
  - Alternate Current redstone.
  - Faster explosions.
  - Grass spread every 4 ticks, mob spawners every 2.
  - Lighter villager point-of-interest checks.
  - Armor stands don't tick.
  - At most 2 entity collisions.
  - Treasure maps don't search for new structures.
  - Per-chunk caps on arrows, pearls, snowballs and XP orbs, which stops lag machines.
  - Cobblestone, dirt and similar junk items despawn after 15 seconds.
- **Anti-xray, engine mode 2.** Ores are money on an economy server. Mode 2 hides real ores among fake ones up to Y 64. It costs a little CPU and bandwidth, and Paper recommends it against current x-ray clients.
- **spigot.yml:** shorter entity activation ranges (animals 16, monsters 24), wider item and XP merging.
- **Villagers** (ServerCore's job on the Fabric server):
  - `spigot.yml` stops villagers outside the 16-block activation range from ticking at all (`tick-inactive-villagers: false`). A trading hall or farm next to a player works as normal; an abandoned one costs nothing.
  - `paper-world-defaults.yml` runs villagers' job-site and bed searches less often. Villagers notice a new workstation a few seconds later; trading and breeding are unchanged.
  - **ChunkSpawnerLimiter** caps animals and villagers per chunk, so a breeding farm can't grow without end. It ships with its own defaults; set the caps after the load test. VillagerOptimizer and AntiVillagerLag have no 26.3 release.
- **bukkit.yml:** per-player spawn caps a little under vanilla (monsters 50, animals 10), monster spawn attempts every 2 ticks.
- **paper-global.yml:** chunk sending limits sized for a pre-generated world, and at most 3 joins per tick so a rush at launch doesn't stall the server.
- **Pre-generate before launch.** Run `chunky radius <border>` on the new world after the boot test, so players never wait for chunk generation.

Paper fills in every setting left out of these files. After the first boot, check that the files still hold
these values (the test checklist in the PR covers it).

Profile with spark (`/spark profiler --timeout 300`) during the load test and in the first week, and change
one setting at a time.

## Hosting

The game thread runs on one core, so single-core speed matters most. Chunk loading, Geyser and BlueMap use
the other cores. The current Reizor VPS has the right CPU (Ryzen 9 9950X, Dallas) but only 2 threads, which is
why launch night maxed out.

Recommendation:

1. **4 or more dedicated threads** on a high-clock Ryzen (9950X or 9800X3D), **16 GB** of RAM, NVMe storage, US Central. The simplest step is the same provider with more threads, keeping Dallas, the backups and the deploy setup.
2. **Heap of 8 GB** (`MEMORY_GB=8` in the host's `.env`). The installer picks 5 GB on a 16 GB machine because it was sized for the modded pack. Paper with these plugins needs less per player, but 60 players and BlueMap renders fit better in 8.
3. **Load-test before launch** with `tools/loadtest.py` at 60 to 100 fake players on the new host. Then read the spark profile, and keep MSPT under about 40 at the target player count.

If the load test passes at 60 players on 4 threads, there's no need for more. A dedicated game host (an OVH
Game server, for example) is the next step if it doesn't. Prices change, so check them when deciding.

## Cutover

Season I runs on the Fabric server until it ends on 23 Jan 2027. Nothing here merges or deploys before then,
and the live server isn't touched until cutover.

1. After 23 Jan: merge this PR and the Fabric removal PR together, then tag a release.
2. Back up the Season I world and keep it (the archive copy, not the live server).
   - Off-server backups keep running for the new world: `monkey-backup.timer` already sends the whole server folder (world, nether, end and every plugin's data, such as balances, claims, hearts, ranks and auction listings) to the R2 bucket every hour, without jars or BlueMap tiles (docs/LIVE.md, "Backups off the machine").
   - Before the beta, run the restore drill (`monkey-restore-drill.service`) on the new server and time it. Then check by hand that the restored copy still has a test player's balance, claim, hearts, rank and an auction listing, because the drill only checks the world and that the server boots. Run it again before the season finale.
3. On the host (Lorenzo):
   - Open 19132 UDP and TCP in the VPS firewall.
   - Set `BEDROCK_PORT` if it isn't 19132, and set `MEMORY_GB`.
   - Resize or move the VPS if that was decided.
4. Deploy the release with a new world (new seed, `{{SEED}}` in server.properties), boot it, and run the test checklist.
5. Pre-generate with Chunky and run the load test.
6. Open the doors on 6 Feb.

## Decisions

Lorenzo took every recommendation on 25 Nov 2026:

- **Minecraft 26.3.** Re-run the pins in mid-January (`relaunch-pins.yml`), and drop to 26.2 only if EssentialsX, EssentialsX Spawn, LPC, CoreProtect, Tebex and UltraCosmetics still have no 26.3 release. On 26.2 (pin run of 25 Nov, Paper build 135) everything but EssentialsX and EssentialsX Spawn has one, and our data packs already target it.
- **EssentialsX fallback:** OpenEco, if EssentialsX has no release by 15 Jan. It has a release for both 26.3 and 26.2 (1.6.1).
- **Auction house:** DonutAuctionHouse 2.0.1, pinned from its unlisted Modrinth project like any other plugin (ADR-0010).
- **Whitelist off.** The relaunch is public, so `white-list=false`. Staff moderate with GrimAC, GriefPrevention and bans instead.
- **New world seed** for Season 1.
- **Off-server backups and a restore drill before the beta** (cutover step 2).

Still Lorenzo's to do, because each changes or costs money on his host:

- **Hosting:** a 4-thread VPS instead of today's 2-thread plan, and whether to move providers.
- **Firewall:** open 19132 UDP and TCP on the VPS.
