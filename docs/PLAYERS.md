# Joining The Realms

## What you need

- **Minecraft Java Edition** (not Bedrock / Windows 10 Edition).
- The **client pack** for this release (`TheRealms-Client-<version>.mrpack`). From 2.0 it is required:
  the server runs mods that add blocks, mobs and items, so plain Minecraft can't join.
- Your Minecraft username on the server's **whitelist**. Ask the host to add you.
- The server address from the host (for example `something.joinmc.link`).

## Install the client pack

1. Install [Prism Launcher](https://prismlauncher.org/download/) (free) and sign in with your Microsoft account.
2. Get **`TheRealms-Client-<version>.mrpack`** from the host (or the [latest release](https://github.com/gr8monk3ys/the-realms-server/releases/latest)).
3. In Prism: **Add Instance > Import**, choose the `.mrpack`, **OK**. It downloads everything (a few minutes).
4. Launch it, then **Multiplayer > Add Server** with the address from the host.

The [Modrinth App](https://modrinth.com/app) works just as well: **+ > Import**, choose the `.mrpack`.

**The normal Minecraft Launcher can't open `.mrpack` files.** You'd have to install Fabric and ~130 mods by
hand, so use the Modrinth App or Prism Launcher. Both are free and use the same Microsoft account; you
don't buy Minecraft again. Use the pack that matches the server's release
(2.x packs are Minecraft 26.3; 1.x packs were 26.1.2 and won't work on a 2.x server).

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
