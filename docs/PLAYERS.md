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
   for "Monkey SMP" in the app's Discover). It downloads about 520 MB: the mods, resource packs and shaders.
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
   It downloads about 520 MB (mods, resource packs, shaders) from their official websites and checks
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
profile or turn shaders off, and lower **Video Settings > Render Distance**.

**Voice chat:** press **V** to open Simple Voice Chat settings. Proximity voice works out of the box.

## Playing

- **Parties, allies and land claims** come from *Open Parties and Claims*:
  - Claim land on the map: open Xaero's World Map (**M**) or the minimap, then right-click chunks to claim them.
    Claimed land can't be broken into or griefed by outsiders.
  - Parties: `/openpac-parties create`, then `/openpac-parties invite <player>`; ally another party with
    `/openpac-parties ally add <party owner>`. Allies and party members share claims.
  - `/openpac` lists everything; the claims screen shows how many chunks you can still claim.
- **PvP is on** outside the spawn area. Spawn itself can't be built in.
- There are no wars or land capture in 2.x (that was Towns & Nations on the 1.x Paper server).
