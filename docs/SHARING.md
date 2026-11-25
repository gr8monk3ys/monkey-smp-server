# Sharing Monkey SMP

Each release has one download, `MonkeySMP-Server-<version>.zip`, and it is for **the host** (one person): it
runs the server on their Windows PC, Mac or Linux machine (or with Docker), or prepares it for an online host.
It is tiny (under 1 MB). It doesn't contain the game files themselves: those are downloaded from their official
websites the first time, and every file is checked before it is used.

Players need no file at all. They join with Minecraft as it comes, Java or Bedrock, with no mods
([PLAYERS.md](PLAYERS.md)).

## Message for the host

Copy, fill in the blanks, and send with `MonkeySMP-Server-<version>.zip`:

```text
Here's Monkey SMP server (Minecraft 26.3 on Paper; Java and Bedrock players can join).

To run it on your computer (Windows 10/11, a Mac or Linux, 12 GB+ RAM):
1. Unzip it somewhere permanent, like Documents.
2. Windows: double-click "Start Server.bat". If Windows says "protected your PC",
   click More info > Run anyway.
   Mac or Linux: follow section 2 of "READ ME FIRST.txt" (on a Mac you double-click
   "Start Server.command"; on Linux you type  sh start.sh  in a terminal).
3. Type YES for the Minecraft EULA, then your Minecraft username (you become the admin).
4. The first start downloads the server files and builds the world: give it 5-10 minutes,
   until the window says "Done". Keep that window open while people play.
5. To let friends join from anywhere, follow section 4 of "READ ME FIRST.txt" (playit.gg, free).
6. Add each friend with "Add Player.bat" (Mac or Linux:  sh add-player.sh THEIRNAME ).

Got a Linux server (VPS)? Run it there the same way, or with Docker (section 9 of the READ ME).
For a Minecraft hosting company, use "Prepare for Hosting" instead (also section 9).

To play yourself, just join with your normal Minecraft: no mods needed.
```

## Message for players

Copy, fill in the addresses, and send. For Monkey SMP's own server they are `monkeysmp.lscaturchio.xyz` (Java)
and `play.monkeysmp.lscaturchio.xyz`, port `19132` (Bedrock):

```text
Here's how to join Monkey SMP. No mods, no downloads: just Minecraft.

Java Edition (PC, Mac, Linux):
  Multiplayer > Add Server > Server Address: ____________________ > Done > Join Server.

Bedrock Edition (phone, tablet, console, Windows):
  Play > Servers > Add Server
  Server Address: ____________________   Port: 19132
  Save, then join.
```

## When a new release comes out

- **Host:** stop the server, unzip the new server zip **over** the old folder, start it again.
  (Exception: going from 1.x to 2.x needs a new folder - it's a new world.) On a Mac, Finder won't
  unzip over a folder; [ADMIN.md](ADMIN.md#day-to-day) says what to do instead.
- **Players:** nothing to do. They keep joining with their normal Minecraft.
