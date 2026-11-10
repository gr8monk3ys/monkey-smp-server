# Joining Monkey SMP

## What you need

- **Minecraft Java Edition** (the one from minecraft.net; not Bedrock / Windows 10 Edition), on Windows,
  macOS or Linux.
- **The Monkey SMP pack.** The server adds blocks, mobs and items, so plain Minecraft can't join. The easiest
  way to get it is a launcher that installs packs, the Modrinth App or Prism Launcher (A below), on every
  computer.
- Your Minecraft username on the server's **guest list** (whitelist). Tell the host your exact name.
- The server address from the host. Monkey SMP's own server is `monkeysmp.lscaturchio.xyz`.

## Install (pick one)

**The game can look frozen while it starts.** With the whole pack, getting to the title screen takes about 3
minutes on a fast computer, every time. Near the end, Windows may show **Not Responding** on and off for up
to a minute. That's normal: don't close the window, and choose **Wait** if Windows asks.

### A. The Modrinth App or Prism Launcher (recommended; Windows, macOS and Linux)

Both are free launchers that install the whole pack from one file, with no installer to run. You sign in with
the Microsoft account you play Minecraft with; you don't buy Minecraft again.

1. Get the pack: **Get the modpack** on [the website](https://monkeysmp.lscaturchio.xyz/#join), or
   `MonkeySMP-Client-<version>.mrpack` from the host. To make sure the file is the one we published, see
   [Check a download](#check-a-download).
2. Install it. The launcher downloads about 380 MB: the mods and resource packs.
   - **[Modrinth App](https://modrinth.com/app):** open the file (double-click it). Or in the app, press **+**
     (*Create new instance*) and choose **Upload a modpack**. The app asks you to confirm, because the pack
     isn't published on Modrinth yet: choose **Install anyway**.
   - **[Prism Launcher](https://prismlauncher.org):** **Add Instance > Import**, then choose the file.
3. Give the game enough memory: 6 GB (8 GB if the computer has more than 16 GB of RAM). In the Modrinth App
   that is the instance's settings > **Java and memory**; in Prism, the instance's **Settings > Java**.
   Too little memory makes the game stutter or crash.
4. Press **Play**. The first start takes a few minutes. In the game: **Multiplayer > Add Server**, type the
   address, **Done**, **Join Server**.

The pack is also waiting for Modrinth's review. Once it is up as the
[Monkey SMP modpack](https://modrinth.com/modpack/monkeysmp), you can search for "Monkey SMP" in the Modrinth
App (Discover) or in Prism (**Add Instance > Modrinth**) and install it from there instead of from a file. If
your host runs an older release than the newest one, install the matching version from the pack's **Versions**
tab, or import that release's `.mrpack`.

### B. Windows: the normal Minecraft Launcher

If you'd rather keep the normal launcher, get **`MonkeySMP-Player-<version>.zip`**: **Get the installer** on
[the website](https://monkeysmp.lscaturchio.xyz/#join), or from the host.

1. Start the Minecraft Launcher once, sign in, then **close it**.
2. Unzip `MonkeySMP-Player-<version>.zip` and double-click **`Install for Minecraft Launcher.bat`**.
   Windows may say *"Windows protected your PC"*, because the file isn't signed: click **More info > Run
   anyway**.
   It downloads about 380 MB (mods and resource packs) from their official websites and checks
   every file, and sets the game's memory from your computer's RAM. When it's done, press a key to close
   the window.
3. Open the launcher, click the version box next to the green **Play** button, choose **Monkey SMP**,
   press **Play**. The first start takes a few minutes.
4. **Multiplayer > Add Server**, type the address from the host, **Done**, **Join Server**.

Your normal Minecraft isn't touched: Monkey SMP keeps its own mods, settings and worlds in a separate
folder (`%APPDATA%\.monkey-smp`). To remove it, double-click **`Uninstall Monkey SMP.bat`**.

### Check a download

Every file we publish has its SHA-256 in a list named `SHA256SUMS.txt`:
[the website's list](https://monkeysmp.lscaturchio.xyz/pack/SHA256SUMS.txt) has the two player files, and each
release's page on GitHub (releases after 3.3.0) has all three. To check a file, work out its SHA-256 and compare
it with the line for that file:

- Windows (PowerShell): `Get-FileHash MonkeySMP-Client-<version>.mrpack`
- macOS: `shasum -a 256 MonkeySMP-Client-<version>.mrpack`
- Linux: `sha256sum MonkeySMP-Client-<version>.mrpack`

Capital and small letters count as the same. If the two differ, the file is damaged or isn't ours: delete it
and download it again.

### Updating

Always play the version that matches the server: 3.x is Minecraft 26.2; 2.x packs were 26.3 and 1.x packs 26.1.2,
and neither joins a 3.x server, so reinstall the pack for 3.0.0. When the host says the pack changed:

- **Modrinth App:** a pack installed from a file is updated by installing the new file the same way. One
  installed from Modrinth offers the update in the app; take it before you play.
- **Minecraft Launcher (B):** unzip the new player zip and double-click the installer again. It updates the same
  "Monkey SMP" installation and keeps your settings, worlds and screenshots.
- **Prism:** a pack installed from Modrinth updates on the instance's **Edit > Modpack** page; an imported
  `.mrpack` is updated by importing the new one.

**Performance:** if it stutters, lower **Video Settings > Render Distance**. On a slow computer, leave out the
heavy extras: see [Low-end PC](#low-end-pc).

**Voice chat:** press **V** to open Simple Voice Chat settings. Proximity voice works out of the box.

## Low-end PC

Most of the pack is there to look and sound good, not because the server needs it. Those files are
**optional**: the resource packs and about 105 of the mods. Leave them out and you still join and
play. The rest are **required**: the mods that add blocks, mobs and items, and the libraries they need. Without
one of them the server turns you away ("This server requires ... installed on your client").

How to leave files out:

- **Prism Launcher (A):** when you install or import the pack, Prism lists the optional files with tick boxes,
  all ticked. Untick what you don't want. Required files have no tick box. Later, switch mods off in the
  instance's **Edit > Mods**.
- **Modrinth App (A):** install the pack as usual, then switch mods off in the instance's **Content** tab. The
  app doesn't mark which ones are optional, so only switch off the ones below.
- **Minecraft Launcher (B):** the installer always installs everything. On a slow computer, use A.

After an update, check the list again: an update can switch them back on.

What to leave out:

1. **Resource packs:** Patrix 32x (73 MB, not switched on by default) and Enhanced Audio (18 MB) are the big
   ones. Fresh Animations needs Entity Model Features and Entity Texture Features to move.
2. **Animations and effects:** Entity Model Features, Entity Texture Features, 3D Skin Layers, Explosive
   Enhancement, Falling Leaves, Wakes, Windy, Better Smoke and the like.
3. **Extras:** Essential (cosmetics, friends and screenshots). Leave out Simple Voice Chat only if you don't want
   proximity voice: without it you can't hear or talk to anyone.

Keep the **speed mods** on: Sodium, Lithium, FerriteCore, ImmediatelyFast and Better Block Entities make the
game faster and lighter, not slower.

Some optional mods need another optional one. If you keep the first, keep the second too, or the game won't
start:

| Keep | Needs |
| --- | --- |
| Better Block Entities | Sodium |
| Entity Model Features | Entity Texture Features |
| Controlling | Searchables |
| Inventory Essentials | Balm |
| Better Stats | TCDCommons |
| Just Enough Professions | JEI |
| MAS Effects, Uku's Armor HUD | ukulib |

Give the game the memory from step 3 of A either way. The full list of optional mods, sorted by what they
do, is `OPTIONAL_MODS` in [`tools/client_env.py`](../tools/client_env.py).

## Playing

- **New here?** Right-click the **Guide** at spawn, with an empty hand, for the short rules, how to find a faction, and this week's
  challenges. The **Town Crier**, also at spawn, has this week's Saturday event.
- **Parties, allies and land claims** come from *Open Parties and Claims*:
  - Claim land: stand in a chunk and type `/oclaims claim`.
    Claimed land can't be broken into or griefed by outsiders.
  - Parties: `/oparties create`, then `/oparties member invite <player>`; the invited player types
    `/oparties join <party owner>`. Ally another party with `/oparties ally add <party owner>`.
  - Who can use your land: each player owns the chunks they claim. By default your party members have full
    access there and allies have none. Change it in the claims menu (the **Open Parties and Claims Menu** key,
    then **My Player Config**): who gets full access, your own player groups (for example "trusted"), one
    setting per kind of block (chests, doors, beds and more), and sub-configs for different rules in different
    chunks. Each player's settings cover only their own chunks.
  - Type `/oclaims`, `/oparties` or `/opac` and press **Tab** to see every command.
- **War and pacts:** `/trigger diplomacy` shows how your faction stands with the others. Your party's owner can
  declare war (kills between the two count double in the weekly standings until Sunday's close) or offer a pact
  (no war between you until one side breaks it). Claims and the rules stay the same.
- **Trading** is by hand, items for items: there is no money, shop or auction house on the server. Meet up,
  agree on the deal, then swap. Lying about what you're trading is a scam and breaks the rules: see
  [Trading](RULES.md#trading).
- **PvP is on** outside the spawn area. Spawn itself can't be built in.
- **Dying** drops your things where you died, as in plain Minecraft (there are no corpses since 2.8.0).
- **Loot chests refill:** a structure's loot chest that you empty fills again a week later. Once it has been
  opened, only staff can break it.
- **Bedrock** breaks with a netherite pickaxe, slowly. No holes into the void, no breaking the End's exit
  portal or gateways, and nothing on top of the Nether roof: rules 44 to 46 in [the rules](RULES.md#bedrock).
- **New in 3.0.0:** a new world on Minecraft 26.2. Amethyst Nether remakes the Nether, Grand Capitals rebuilds
  villages and illager structures, Crazy Chambers makes trial chambers bigger, and there are mobs of random sizes,
  emotes (Emotecraft) and more recipes. If two recipes clash, Polymorph+ lets you pick the result.
- **New in 3.1.0:** Amethyst Nether is gone, so the Nether is vanilla's terrain again, with new structures in it. Dungeons and Taverns reworks strongholds, ancient cities, fortresses, monuments, mansions, outposts,
  temples and mineshafts, and Moog's structures and bigger End cities add more to find. Their enchantments are event
  rewards only ([rule B18](RULES.md)).
- **New in 3.1.1:** only a few crafted maces can exist at once. When the cap is reached, no more can be crafted until one
  breaks or is destroyed.
- There is no land capture (that was Towns & Nations on the 1.x Paper server).
