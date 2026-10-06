# Joining The Realms

## What you need

- **Minecraft Java Edition** (the one from minecraft.net; not Bedrock / Windows 10 Edition), on Windows.
- **`TheRealms-Player-<version>.zip`** from the host. It sets up the mods the server needs: the server
  adds blocks, mobs and items, so plain Minecraft can't join.
- Your Minecraft username on the server's **guest list** (whitelist). Tell the host your exact name.
- The server address from the host (for example `something.joinmc.link`).

## Install (pick one)

### A. The normal Minecraft Launcher (most people)

1. Start the Minecraft Launcher once, sign in, then **close it**.
2. Unzip `TheRealms-Player-<version>.zip` and double-click **`Install for Minecraft Launcher.bat`**.
   If Windows says *"Windows protected your PC"*, click **More info > Run anyway**.
   It downloads about 450 MB (mods, resource packs, shaders) from their official websites and checks
   every file. When it's done, press a key to close the window.
3. Open the launcher, click the version box next to the green **Play** button, choose **The Realms**,
   press **Play**. The first start takes a few minutes.
4. **Multiplayer > Add Server**, type the address from the host, **Done**, **Join Server**.

Your normal Minecraft isn't touched: The Realms keeps its own mods, settings and worlds in a separate
folder (`%APPDATA%\.the-realms`). To remove it, double-click **`Uninstall The Realms.bat`**.

### B. Modrinth App or Prism Launcher (if you already use one)

Import the `TheRealms-Client-<version>.mrpack` file that's inside the player zip:

- [Modrinth App](https://modrinth.com/app): **+ > Import**, choose the `.mrpack`.
- [Prism Launcher](https://prismlauncher.org): **Add Instance > Import**, choose the `.mrpack`.

Both are free and use the same Microsoft account; you don't buy Minecraft again.

### Updating

When the host sends a newer version, run the new installer (or import the new `.mrpack`). Always use the
version that matches the server: 2.x is Minecraft 26.3; 1.x packs were 26.1.2 and won't join a 2.x server.

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
