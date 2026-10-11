# Sharing The Realms

Each release has three downloads. Send each person only what they need.

| File | Who gets it | What they do with it |
|---|---|---|
| `TheRealms-Server-<version>.zip` | **the host** (one person) | Runs the server on their Windows PC, Mac or Linux machine (or with Docker), or prepares it for an online host |
| `TheRealms-Player-<version>.zip` | **every player** (the host too, if they play) | Installs the game mods (Windows), then joins |
| `TheRealms-Client-<version>.mrpack` | players on a **Mac or Linux**, or who already use the Modrinth App or Prism Launcher | Import it instead of using the player zip (the player zip contains this file too) |

All three are tiny (under 1 MB). They don't contain the game files themselves: those are downloaded from
their official websites the first time, and every file is checked before it is used.

Always send the files from the **same release** (same version number) to everyone. A player on 2.0.0
can't join a server on 2.1.0 if the mods changed.

## Message for the host

Copy, fill in the blanks, and send with `TheRealms-Server-<version>.zip`:

```text
Here's The Realms server (Minecraft Java 26.3, modded factions/PvP).

To run it on your computer (Windows 10/11, a Mac or Linux, 12 GB+ RAM):
1. Unzip it somewhere permanent, like Documents.
2. Windows: double-click "Start Server.bat". If Windows says "protected your PC",
   click More info > Run anyway.
   Mac or Linux: follow section 2 of "READ ME FIRST.txt" (on a Mac you double-click
   "Start Server.command"; on Linux you type  sh start.sh  in a terminal).
3. Type YES for the Minecraft EULA, then your Minecraft username (you become the admin).
4. The first start downloads ~500 MB and builds the world: give it 5-10 minutes,
   until the window says "Done". Keep that window open while people play.
5. To let friends join from anywhere, follow section 4 of "READ ME FIRST.txt" (playit.gg, free).
6. Add each friend with "Add Player.bat" (Mac or Linux:  sh add-player.sh THEIRNAME ).

Got a Linux server (VPS)? Run it there the same way, or with Docker (section 9 of the READ ME).
For a Minecraft hosting company, use "Prepare for Hosting" instead (also section 9).

You also need to play with the mods: use the player zip I'm sending everyone.
```

## Message for players

Copy, fill in the server address, and send with `TheRealms-Player-<version>.zip`:

```text
Here's how to join The Realms (Minecraft Java Edition, modded):

1. Make sure you have Minecraft Java Edition and the normal Minecraft Launcher
   (minecraft.net). Start the launcher once, sign in, then close it.
2. Unzip TheRealms-Player-<version>.zip and double-click "Install for Minecraft Launcher.bat".
   If Windows says "protected your PC", click More info > Run anyway.
   It downloads the mods (~450 MB) and adds "The Realms" to your launcher. Takes a few minutes.
3. Open the Minecraft Launcher, choose "The Realms" next to the Play button, press Play.
   The first start is slow (a few minutes) - that's normal.
4. Multiplayer > Add Server > Server Address: ____________________ > Done > Join.

On a Mac or Linux (or if you already use the Modrinth App or Prism Launcher): skip step 2,
install Prism Launcher (prismlauncher.org) or the Modrinth App, and import the .mrpack file
from the zip instead. Then do step 4 there.
Tell me your exact Minecraft username so I can add you to the guest list.
```

## When a new release comes out

- **Host:** stop the server, unzip the new server zip **over** the old folder, start it again.
  (Exception: going from 1.x to 2.x needs a new folder - it's a new world.) On a Mac, Finder won't
  unzip over a folder; [ADMIN.md](ADMIN.md#day-to-day) says what to do instead.
- **Players:** unzip the new player zip and double-click the installer again. It updates the same
  "The Realms" installation and keeps your settings, worlds and screenshots. Prism Launcher and
  Modrinth App players import the new `.mrpack`.
