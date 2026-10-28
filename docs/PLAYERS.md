# Joining Monkey SMP

## What you need

- **Minecraft Java Edition** (the one from minecraft.net; not Bedrock / Windows 10 Edition), on Windows,
  macOS or Linux.
- **The Monkey SMP pack.** The server adds blocks, mobs and items, so plain Minecraft can't join. The easiest
  way to get it is the Modrinth App (A below), on every computer.
- Your Minecraft username on the server's **guest list** (whitelist). Tell the host your exact name.
- The server address from the host. Monkey SMP's own server is `monkeysmp.lscaturchio.xyz`.

## Install (pick one)

### A. The Modrinth App (recommended, Windows, macOS and Linux)

1. Install the [Modrinth App](https://modrinth.com/app) (free) and sign in with the Microsoft account you
   play Minecraft with. You don't buy Minecraft again.
2. Open the [Monkey SMP modpack](https://modrinth.com/modpack/monkeysmp) and press **Install** (or search
   for "Monkey SMP" in the app's Discover). It downloads about 560 MB: the mods, resource packs and shaders.
3. Give the game enough memory: the instance's settings > **Java and memory**, 6 GB (8 GB if the computer has more
   than 16 GB of RAM).
   Too little memory makes the game stutter or crash.
4. Press **Play**. The first start takes a few minutes. In the game: **Multiplayer > Add Server**, type the
   address, **Done**, **Join Server**.

Can't find the pack on Modrinth? It is waiting for Modrinth's review. Until it's up, get
`TheRealms-Client-<version>.mrpack` from the host and import it instead: in the app, **+ > Import**, choose
the file. If your host runs an older release than the newest one, install the matching version from the
pack's **Versions** tab, or import that release's `.mrpack`.

### B. Windows: the normal Minecraft Launcher

If you'd rather keep the normal launcher, get **`TheRealms-Player-<version>.zip`** from the host.

1. Start the Minecraft Launcher once, sign in, then **close it**.
2. Unzip `TheRealms-Player-<version>.zip` and double-click **`Install for Minecraft Launcher.bat`**.
   If Windows says *"Windows protected your PC"*, click **More info > Run anyway**.
   It downloads about 560 MB (mods, resource packs, shaders) from their official websites and checks
   every file, and sets the game's memory from your computer's RAM. When it's done, press a key to close
   the window.
3. Open the launcher, click the version box next to the green **Play** button, choose **Monkey SMP**,
   press **Play**. The first start takes a few minutes.
4. **Multiplayer > Add Server**, type the address from the host, **Done**, **Join Server**.

Your normal Minecraft isn't touched: Monkey SMP keeps its own mods, settings and worlds in a separate
folder (`%APPDATA%\.the-realms`). To remove it, double-click **`Uninstall Monkey SMP.bat`**.

### C. Prism Launcher

[Prism Launcher](https://prismlauncher.org) (free, Windows, macOS, Linux): **Add Instance > Modrinth**, search
for "Monkey SMP", **OK**; or **Add Instance > Import** and choose the `.mrpack` from the host. Set the memory
in the instance's **Settings > Java**, as in step 3 of A, then add the server as in step 4.

### Updating

Always play the version that matches the server: 2.x is Minecraft 26.3; 1.x packs were 26.1.2 and won't join a
2.x server. When the host says the pack changed:

- **Modrinth App:** the Monkey SMP instance offers the update; take it before you play.
- **Minecraft Launcher (B):** unzip the new player zip and double-click the installer again. It updates the same
  "Monkey SMP" installation and keeps your settings, worlds and screenshots.
- **Prism:** a pack installed from Modrinth updates on the instance's **Edit > Modpack** page; an imported
  `.mrpack` is updated by importing the new one.

**Performance:** shaders are heavy. If it stutters, press **O** in game (Iris shader menu) to pick a lighter
profile or turn shaders off, and lower **Video Settings > Render Distance**. On a slow computer, leave out the
heavy extras: see [Low-end PC](#low-end-pc).

**Voice chat:** press **V** to open Simple Voice Chat settings. Proximity voice works out of the box.

## Low-end PC

Most of the pack is there to look and sound good, not because the server needs it. Those files are
**optional**: the shaders, the resource packs and about 135 of the mods. Leave them out and you still join and
play. The rest are **required**: the mods that add blocks, mobs and items, and the libraries they need. Without
one of them the server turns you away ("This server requires ... installed on your client").

How to leave files out:

- **Prism Launcher (C):** when you install or import the pack, Prism lists the optional files with tick boxes,
  all ticked. Untick what you don't want. Required files have no tick box. Later, switch mods off in the
  instance's **Edit > Mods**.
- **Modrinth App (A):** install the pack as usual, then switch mods off in the instance's **Content** tab. The
  app doesn't mark which ones are optional, so only switch off the ones below.
- **Minecraft Launcher (B):** the installer always installs everything. On a slow computer, use A or C.

After an update, check the list again: an update can switch them back on.

What to leave out:

1. **Distant Horizons.** It draws land far beyond your render distance (up to 256 chunks out, as the pack is
   set up), which takes memory, processor time and disk space. The first one to try.
2. **Shaders:** Iris and the shader packs. Shaders are off until you turn them on with **O**, so this mostly
   saves download and disk space.
3. **Resource packs:** Patrix 32x (73 MB, not switched on by default) and Enhanced Audio (19 MB) are the big
   ones. Fresh Animations needs Entity Model Features and Entity Texture Features to move.
4. **Animations and effects:** Entity Model Features, Entity Texture Features, 3D Skin Layers, Particle
   Effects, Falling Leaves, Wakes, Explosive Enhancement, Interactive Foliage, Cosy Critters, Windy and the
   like.
5. **Extras:** Essential (cosmetics, friends and screenshots) and the cape mods. Leave out Simple Voice Chat
   only if you don't want proximity voice: without it you can't hear or talk to anyone.
6. **Maps:** Xaero's Minimap and Xaero's World Map. Without them, claim land by standing in the chunk and typing
   `/oclaims claim`.

Keep the **speed mods** on: Sodium, Lithium, FerriteCore, ImmediatelyFast and Better Block Entities make the
game faster and lighter, not slower.

Some optional mods need another optional one. If you keep the first, keep the second too, or the game won't
start:

| Keep | Needs |
| --- | --- |
| Iris, Better Block Entities | Sodium |
| Entity Model Features | Entity Texture Features |
| Status Effect Bars | Cloth Config |
| Controlling | Searchables |
| Inventory Essentials | Balm |
| Better Stats | TCDCommons |
| Bind Commands | Mod Menu |
| Light Overlay | OverlayLib |
| MAS Effects | ukulib |
| Interactive Foliage | Sway |
| OneConfig | Compose Multiplatform |
| Wakes Reforged | BaguetteLib |

Give the game the memory from step 3 of A either way. The full list of optional mods, sorted by what they
do, is `OPTIONAL_MODS` in [`tools/client_env.py`](../tools/client_env.py).

## Playing

- **New here?** Right-click the **Guide** at spawn for the short rules, how to find a faction, and this week's
  challenges. The **Town Crier**, also at spawn, has this week's Saturday event.
- **Parties, allies and land claims** come from *Open Parties and Claims*:
  - Claim land on the map: open Xaero's World Map (**M**) or the minimap, then right-click chunks to claim them.
    Or stand in a chunk and type `/oclaims claim`.
    Claimed land can't be broken into or griefed by outsiders.
  - Parties: `/oparties create`, then `/oparties member invite <player>`; the invited player types
    `/oparties join <party owner>`. Ally another party with `/oparties ally add <party owner>`. Allies and party
    members share claims.
  - Type `/oclaims`, `/oparties` or `/opac` and press **Tab** to see every command; the claims screen shows how
    many chunks you can still claim.
- **War and pacts:** `/trigger diplomacy` shows how your faction stands with the others. Your party's owner can
  declare war (kills between the two count double in the weekly standings until Sunday's close) or offer a pact
  (no war between you until one side breaks it). Claims and the rules stay the same.
- **Trading** is by hand, items for items: there is no money, shop or auction house on the server. Meet up,
  agree on the deal, then swap. Lying about what you're trading is a scam and breaks the rules: see
  [Trading](RULES.md#trading).
- **PvP is on** outside the spawn area. Spawn itself can't be built in.
- **Dying** drops your things where you died, as in plain Minecraft (there are no corpses since 2.8.0).
- **Carry On:** sneak and right-click with both hands empty to pick up a passive animal, a beehive with its bees
  or a block like an enchanting table; right-click to put it down. Anything that stores items (chests, barrels,
  shulker boxes, furnaces, hoppers and the like), spawners, banners, beds, doors, players and the NPCs at spawn
  can't be carried, and nothing in someone else's claim can.
- **Loot chests refill:** a structure's loot chest that you empty fills again a week later. Once it has been
  opened, only staff can break it.
- **Bedrock** breaks with a netherite pickaxe, slowly. No holes into the void, no breaking the End's exit
  portal or gateways, and nothing on top of the Nether roof: rules 44 to 46 in [the rules](RULES.md#bedrock).
- **New in 2.8.0** as well: a new End (Endercon, with Qrafty's End Villages), Dungeons and Taverns and Crazy
  Chambers structures, Friends & Foes mobs, mobs of random sizes, emotes (Emotecraft), chained minecarts
  (Ultimate Minecarts), and more recipes (Better Craftables, craftable tridents, tipped arrows from any potion).
  If two recipes clash, Polymorph+ lets you pick the result. Dungeons and Taverns' own enchantments are event
  rewards only (B18), so you won't find them in chests.
- There are no wars or land capture in 2.x (that was Towns & Nations on the 1.x Paper server).
