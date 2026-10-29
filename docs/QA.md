# Testing a release (staff QA)

A checklist for whoever tries a release in game before it goes live: what to set up, what to do, and what
you should see. Most of it is things the automated checks can't do: they boot the server and read every
file, but they can't right-click an NPC or pick up a cow. Each item marked **(never tried in game)** has only
been checked on paper so far; those come first when time is short.

How players see the same things: the site's [How it works](https://monkeysmp.lscaturchio.xyz/guide) page.
Commands for staff, in full: [ADMIN.md](ADMIN.md).

## The one rule: never on the live world

Test on your own copy of the server, never on the live VPS world, and never before launch. Several of these
steps happen only once per world. `function realms:rules/launch` on the live world before 5 PM on launch day
would open Founder's Circlet's window early and wipe the test play it's meant to wipe at the real launch, and
the real launch wouldn't open the window again. `challenges/sync` clears the week's progress, and
`firsts/clear` reopens every Server First. On a test copy all of that is fine; that's what it's for.

The one exception is war, pacts and outposts (below), which only the live server can run. There you only
watch and read status: no staff commands that change anything.

## Set up a test server (about 15 minutes)

1. From the [releases page](https://github.com/gr8monk3ys/monkey-smp-server/releases), download the release
   you're testing: `TheRealms-Server-<version>.zip` for the server and, unless you play through the Modrinth
   App, `TheRealms-Player-<version>.zip` (Windows, normal launcher) or `TheRealms-Client-<version>.mrpack`
   (Modrinth App or Prism) for the game. Same version for both.
2. Unzip the server into a **new, empty folder** (not over an old test server: a used world can hide a bug
   that only shows on a fresh one).
3. Windows: double-click `Start Server.bat` (Mac: `Start Server.command`; Linux: `sh start.sh`). Type `YES` for
   the EULA, then your Minecraft username: you become the admin, with op. The first start downloads about
   500 MB; wait for "Done".
4. Install the game side, start Minecraft with the Monkey SMP profile and join `localhost`.
5. Someone else to test with (needed for claims, Carry On in a claim and the Hunted omen): see "READ ME FIRST.txt", section 4, or
   have them on the same network join your computer's local address. Add them with `Add Player.bat`.

Your account has two hats. Most checks need both:

| To test as | In the server window |
|---|---|
| a plain player | `deop NAME`, then `lp user NAME parent set default` |
| a moderator | `lp user NAME parent set moderator` (still not op) |
| an admin again | `op NAME`, then `lp user NAME parent set admin` |

Rejoin after changing rank so the client catches up. Commands below with a `/` are typed in game; without
one, in the server window (they work in game too, with a `/`, as an op).

## Before the launch

These work on a fresh world before anyone runs the launch.

**The spawn NPCs.** As admin, stand at spawn and run `/function realms:npcs/guide/here`, then a few blocks
away `/function realms:npcs/crier/here`.

- [ ] The Guide (gold name) and the Town Crier (yellow) appear where you stood, facing your way, normal size.
- [ ] Walking within 8 blocks of the Guide shows a speech bubble; the Crier calls out every 5 minutes.
- [ ] **As a plain player, with an empty hand**, right-click each one: a dialog opens, not "You are not
  allowed to interact with this entity". **(never tried in game: the main fix in 2.9.1)**
- [ ] The Guide's buttons open this week's challenges, the standings and the wardrobe; the links button opens
  the Monkey SMP links.
- [ ] With something in your hand (a name tag, a lead), the click is refused.
- [ ] Hitting them or shooting them does nothing.

**WorldEdit.** **(never tried in game)**

- [ ] As admin: `//pos1`, move, `//pos2`, `//set stone` fills the box; `//undo` puts it back.
- [ ] As a plain player: `//pos1` is refused.

**Claims and Carry On.**

- [ ] As a plain player, `/oclaims claim` claims your chunk; `M` then right-click claims more, up to 4.
- [ ] Sneak + right-click with empty hands picks up a cow, a sheep or a chicken, and places it back.
  **(animals never tried in game)**
- [ ] It won't pick up a chest, barrel, furnace, hopper, spawner, bed, door or the NPCs.
- [ ] With a second player: they can't pick up anything, or break anything, inside your claim.

**Enchantments.** **(the table and trades never tried in game)**

- [ ] Enchant a few books and tools at an enchanting table with full bookshelves: no enchantment from Dungeons
  and Taverns (names you don't know from vanilla) ever shows up.
- [ ] Librarian villagers' trades never offer one either. Cycle a few by breaking and placing their lectern.

## The launch

On the test server only, as admin, run `function realms:rules/launch`.

- [ ] Chat announces the launch; the Nether and PvP are closed and open again an hour later. Nobody gets grace
  in that hour (rule 23).
- [ ] `scoreboard players get #founder.open rw.day` says 1: Founder's Circlet's window is open.
- [ ] After 10 minutes online, `/trigger wardrobe` shows Founder's Circlet unlocked.
  (`scoreboard players get NAME rw.launchtime` counts the seconds.)
- [ ] After the hour, an account joining for the first time gets 48 hours of grace; `/trigger end_grace` ends it
  early, and it says so.

The challenges, standings and drops below work during the launch hour. Wait for PvP and the Nether to open
before the omens and the Server Firsts: Truce Hour won't start while PvP is already off, a Hunted kill can't
land, and the Nether portal stays shut.

## The week

**Challenges.** `function realms:challenges/sync {week:1}` starts week 1.

- [ ] `/trigger challenges` lists three challenges, with what counts when you hover.
- [ ] Finish an easy one: chat says so, and the menu shows it done.
- [ ] `function realms:standings/place` at spawn puts the standings board there, and `/trigger standings`
  opens the standings in chat (empty until the VPS's hourly run fills them).

**Supply drops.** Stand somewhere outside every claim.

- [ ] `function realms:drops/here`: a chat message with the spot and a boss bar counting down 10 minutes,
  with reminders at 5 and 1.
- [ ] Chests land with a "Supply drop" label. Loot is food, iron, coal, arrows and the like: never diamonds,
  netherite, golden apples, potions or enchanted gear.
- [ ] `function realms:drops/stop` removes them; `function realms:drops/status` says nothing is on.

**Omens.**

- [ ] `function realms:omens/start/truce`: a boss bar, and players can't hurt each other for the hour.
  `function realms:omens/stop` ends it and PvP comes back.
- [ ] In the afternoon (`time set 9000`), `function realms:omens/start/blood_moon`: "The moon is coming up red
  tonight". Let the sun set by itself (about 3 minutes; jumping the clock may skip the nightfall it waits for):
  a title, the game goes to Hard, and mobs near you are faster. At dawn, or after 15 minutes, the difficulty
  goes back.
- [ ] With a second player: `function realms:omens/hunt {name:"THEIRNAME"}` puts a title and boss bar on them
  and posts a bounty; killing them names you in chat.

**Server Firsts.** After the launch, in survival:

- [ ] Go through a Nether portal: everyone gets the announcement, a title and a sound.
- [ ] `/trigger firsts` lists the 14 firsts and who holds each.
- [ ] Doing it again, or a second player doing it, announces nothing.

**War, pacts and outposts: on the live server after the launch, with an owner.** A faction's number, which
war, pacts and outpost captures all need, comes from the hourly standings run, and outposts are placed by
another hourly timer. Both run only on the VPS, against the live world, so a home test server (or the owners'
restore drill copy) never gets either. Check these in the first evening after the launch, once two real
factions exist and an hour has passed. Read and watch only: real players' wars and outposts are at stake.

- [ ] `function realms:diplomacy/staff/factions` lists both factions with their numbers.
- [ ] A faction leader's `/trigger diplomacy` shows buttons for war and a pact; a plain member's shows only
  how things stand.
- [ ] `function realms:outposts/status` lists four outposts, and the live map shows them. When a faction takes
  one, chat says so and `status` names the holder.

## Saturday events

- [ ] `function realms:events/arena/set_lobby`, `set_pit`, `open`: a player near the lobby with an empty
  inventory can `/trigger arena set 1` and lands in the pit in adventure mode; `/trigger arena set 2` clears
  the kit and puts them back at the entrance in survival.
- [ ] `function realms:events/season/lock` puts survival players in adventure with PvP off; `season/unlock`
  undoes it.

## Reporting what you find

For anything that isn't what this page says, note the release version, what you did (the exact command), what
you expected and what happened, plus a screenshot. Post it in the staff channel or as a
[GitHub issue](https://github.com/gr8monk3ys/monkey-smp-server/issues). If it passed, a tick in the staff channel
("2.9.1: NPCs OK as a plain player") is enough, and the "never tried in game" notes in ADMIN.md can go.

Shut the test server down when you're done (`stop`), and use a new folder for the next release.
