# Seasons and events

How Monkey SMP stays worth logging into: a season with a start, a middle and an ending, one scheduled
event every week, and a big moment every two to three weeks. `docs/RETENTION.md` covers the
wardrobe and how to read the numbers; `docs/RULES.md` is the rulebook this plan works around.

## What other servers do

Research from October 2026. The sources are server wikis, host blogs and practitioner guides, not
controlled studies, so treat them as patterns rather than proof.

- **Seasons with an ending beat one endless world.** Guides for long-running SMPs put a season at three
  to six months. At the end the world is locked, players get the download, and a fresh map starts.
  Lifesteal servers that run 2 to 4 week seasons are popular for the same reason: a beginning and an
  end give people a story to come back for. Seasons that ran on for years (one SMP's Season 4 lasted
  888 days) are the exception.
- **The calendar matters more than the event.** The advice that repeats is a shared moment every two to
  three weeks. It works because there is a date when everyone logs in again, whatever the event is.
  Live-service games say the same: events on a predictable two to four week cadence win back dormant
  players as much as they entertain active ones. Boredom is the main reason players quit around day 7.
- **End every season with a finale.** Lifesteal Network ends a season with "End of the World": the
  world shrinks to one last area and players fight to be the last one standing. Purge-style finales
  are the moments players remember.
- **Factions servers run events on timers.** Common ones are KOTH (hold a hill for points or time),
  envoys or supply drops (loot chests at announced spots, around spawn every few hours on big
  servers), bounties, and weekly faction-top payouts. Small servers run them weekly rather than hourly.
- **Don't eliminate people for a whole season.** Permanent elimination shrinks a 30-player server to 5
  in a month. When a mode removes players, they come back next season.
- **Battle passes come later.** Practitioners advise against one on a new, small server: fix the core
  retention first. Monkey SMP sells no passes of that kind anyway (cosmetics only, one access price).
- **Measure D1, D7 and D30.** Day 1 tests the first hour, day 7 tests whether the core loop has depth,
  and day 30 tests events, social ties and seasons. Mobile-game medians are about 22%, 4% and under 1%.
  A paid server of friend groups should be far above them; `docs/RETENTION.md` sets the bar at 30% for D7.

## The plan for Monkey SMP

### A season is about 12 weeks

Twelve weeks fits a factions server with Strength. Strength and gear pile up, so after about three
months new players can't catch up, and the veterans have nothing left to chase. Shorter seasons
(Lifesteal's 2 to 4 weeks) don't give factions time to build bases or alliances. Twelve weeks is
also three months of pass, so a season is an easy thing to sell: "Season II starts March 7, three months."

Each season has:

- **A fresh world and a new twist.** One rule or mechanic changes. Players vote on it in Discord during
  the off-season week from two or three options the owners pick (examples below).
- **A fixed end date, announced on day one.** Nobody should pay for a month the world ends in without
  knowing it.
- **A season skin.** A blade that anyone who plays in the season unlocks, like Founder's Edge in Season I.
  Season skins never come back, so playing in a season is a keepsake.
- **A champion.** The faction with the most Season Cup points (below) gets its banner hung in the Hall of
  Banners at the next season's spawn, a champion helm in the wardrobe, its name held for it next season,
  and a title for the whole roster ("The season champion", below).
- **Factions registered before launch.** Teams of up to four sign up in Discord before the server opens
  (one Open Parties and Claims party each, rule 29), so the first events have teams from day one.
  Solo players are matched into factions by staff. Each faction writes a one-paragraph charter when it
  signs up (below).

What carries over between seasons: wardrobe unlocks, days and hours played, tenure, invites, events
attended, holiday skins, weekly challenges done, the launch weekend's skin, supporter tiers and titles,
including the champion's (`tools/season.py carry`,
"Ending a season" below). What resets: the world, items, Strength and territory. Factions can re-form.

### Registering a faction

Sign-up opens in Discord a week before launch: one post per faction with its name, its members' Minecraft
names (up to four), its banner (the official flag is made from it) and a charter.

The **charter** is one paragraph in the faction's own words: who they are, what they are after this
season, and how they deal with everyone else ("We hold the river and trade with anyone. We raid the
Red Monkeys and nobody else."). It gives each faction a story other players can read, so alliances and
rivalries start sooner, newcomers can pick a faction to join, and event posts have something to say
about the teams. A charter is not a rule: nobody is punished for breaking one, and the rulebook applies
as usual. Like any post it follows the conduct rules (all ages, no hate). Staff pin the charters in
`#smp-forum` at launch, and a faction can rewrite its own at any time.

A name held by last season's champion can't be taken by another faction, nor one a letter or two away.

### The acts of a season

The Season I rules already hold back some of the world (the first hour, the End, Netherite armor, the
2500 border). Opening those on a schedule turns them into the season's story. Weeks count from launch.

The four pillar events (below) run in every season. The acts and the catalog fill the weeks between them.

| Week | Act or event | What happens |
| --- | --- | --- |
| 0, days 1 and 2 | **Launch weekend: Build Battle** | Rule 23's peaceful hour, then PvP and the Nether open. The wheel spins at launch and factions build until judging on the second night. Founder's Edge for everyone, and Founder's Circlet for 10 minutes online before the end of Sunday (Pacific). Challenge week 0. |
| 1 | **Faction Raid I** | The first capture-the-flag night, once every faction has a base and a flag. |
| 2 | **The border breaks** | The border grows from 2500 to 4000, with supply drops in the new ring. New land for late joiners. The live map widens with it (docs/ADMIN.md, "The live map"). |
| 3 | **Dragon Night: Anarchy** | The End opens in the event slot, and for the next 90 minutes every rule is off except the griefing, cheating and conduct rules (below). |
| 4 | **Arena Glory I** | Kit duels (1v1) for individuals, then the 4v4 faction bracket. |
| 5 | **Netherite age** | Netherite armor is allowed (rule 24): `datapack disable "file/realms-no-netherite-armor"`. Announced a week ahead. |
| 6 | **Faction Raid II** | Flags again, now with Netherite and bigger bases. |
| 7 | **Build Battle II** | A shorter one: one evening, one spin, at spawn plots. |
| 8 | **The border breaks again** | 4000 to 6000, and the live map with it. |
| 9 | **Arena Glory II** | 2v2 and the 4v4 bracket. |
| 10 | **Faction Raid III** | Last raid. Cup standings set the finale's spawn order. |
| 11 | **The finale** | The border shrinks toward spawn over an evening, then a last fight. Worth the most Cup points. |
| 12 | **Off-season** | The world is locked, the download is posted, players vote on the next twist, and a creative or minigame weekend keeps the pass worth it. |

If the server is full early, open things sooner. If it is quiet, hold the finale back a week. The acts
are a plan, not a contract. What is promised is the end date.

#### Season I calendar

Season I opens on **Saturday 21 November 2026 at 5 PM Pacific** (8 PM Eastern; `LAUNCH_AT` in
`site/config.js`, and the run sheet in docs/LAUNCH.md). The tools keep these dates in one place,
`tools/season_calendar.py` (the weeks, the Saturdays, the drop nights and the launch weekend); a test checks it
against `LAUNCH_AT` and this table. Week N's event is the Saturday N weeks later at
6 PM Pacific, 9 PM Eastern. Daylight saving time ends on 1 November 2026 and starts again on 14 March 2027,
so every Season I time is standard time.

| Week | Saturday | The event | Also that week |
| --- | --- | --- | --- |
| 0 | 21 Nov 2026, 5 PM | Launch: the launch hour, then PvP and the Nether at 6 PM. The Build Battle wheel spins at 5 PM; judging Sunday 22 Nov, 6 PM. | Launch weekend runs to midnight on Sunday 22 Nov |
| 1 | 28 Nov | Faction Raid I | Thanksgiving is Thursday 26 Nov |
| 2 | 5 Dec | The border breaks: 2500 to 4000 | Town Hall (first Saturday). Midwinter announced. |
| 3 | 12 Dec | **Dragon Night**: the End opens, Anarchy for 90 minutes | Midwinter decorating at spawn starts |
| 4 | 19 Dec | Arena Glory I, as **Midwinter**: a snowball round in the arena, then gifts at spawn and the Midwinter Cap | Netherite age announced |
| 5 | 26 Dec | Netherite age (rule 24 lifted), plus a small event from the catalog | Midwinter comes down. The day after Christmas: expect a thin crowd. |
| 6 | 2 Jan 2027 | Faction Raid II | Town Hall. The first Base of the Month (entries by 25 Dec). |
| 7 | 9 Jan | Build Battle II | |
| 8 | 16 Jan | The border breaks again: 4000 to 6000 | |
| 9 | 23 Jan | Arena Glory II | "Two weeks before the end" (Ending a season, below): the end date again, the twist vote opens, Season II's date set |
| 10 | 30 Jan | Faction Raid III | The Cup standings set the finale's spawn order |
| 11 | 6 Feb | **The finale**. The world locks after it. | Town Hall. Base of the Month (entries by 25 Jan). |
| 12 | 13 Feb | Off-season weekend in the locked world: the download, the twist vote, a creative or minigame night | 3-month passes bought on launch day end on Friday 19 Feb |
| | 20 Feb | Season II opens (proposed; owners confirm it by 23 Jan) | |

- **The end date to announce on day one:** Season I ends with the finale on Saturday 6 February 2027. The
  world stays up, locked, through the off-season week, and Season II is planned for Saturday 20 February.
- **Holidays in the season:** only Midwinter (19 Dec). Hallowtide (31 Oct 2026) comes before launch, while
  the world is still closed, so Gravelight waits for Hallowtide 2027 (30 Oct). Midsummer (19 Jun 2027) is
  after Season I.
- **No Base of the Month in December.** Bases are four days old on 25 November.

### A weekly rhythm

One headline event a week, at a fixed time (Saturday, 6 pm Pacific, which is the group's evening).
Most weeks it is the act or pillar event from the table above. When a week has only an act
(the border breaking, Netherite age), add a small event from the catalog below.

- Create each one as a Discord event with Front Desk's `/gamenight` for Minecraft. Discord's
  "Interested" button is the RSVP, and the bot reminds people 15 minutes before.
- The monthly Town Hall the bot already runs (first Saturday) is where players give feedback on the
  season.
- Post the result and the screenshots in `#monkey-smp` the same night.
- On Sunday at 7 pm Pacific the week's faction standings close (below) and post themselves, the day
  after the event, so the event's Cup points are in.

### Weekly standings

Every faction gets one rank a week, from four things: event wins, land, strength and fighting. The Cup
alone decides the champion; the standings give the weeks between events something to play for, and a
faction that never wins an event still has a column it can lead.

| Column | What counts | Weight |
| --- | --- | --- |
| Cup | The faction's Season Cup points so far (`ev.cup`) | 40 |
| Land | Chunks its members have claimed (Open Parties and Claims) | 20 |
| Strength | Its members' Strength levels added up (a player in the arena counts with their own level) | 20 |
| Kills | PvP kills by its members this week, outside the event arena; a war enemy's count twice (War and pacts, below) | 20 |
| Bounties | +5 for each bounty a member claimed this week (the bounty board, below) | |
| Outposts | +1 for each whole hour the faction held an outpost this week, at most 20 (Outposts, below) | |

Each column gives a faction its share of the weight, in proportion to the leader of that column, rounded:
the faction with the most land gets 20, one with half as much gets 10. Add the columns up and the bounties
and outpost hours on top. The leader of every column would have 100. Example: the Red Monkeys have 30 Cup points (the most),
7 chunks (the most), Strength 7 (the most) and 4 kills to the Blue Herons' 6: 40 + 20 + 20 + 13 = 93, and
98 with a claimed bounty. A tie on points goes to more Cup points, then more kills this week; still tied,
the factions share the rank. Strength below zero counts as zero.

- **Who is a faction.** An Open Parties and Claims party; its name is the party name (`/openpac`), or
  "NAME's faction" after its owner if it has none. Players outside a party aren't ranked.
- **The Cup column** is matched on names: name a faction's Cup entry as the party is named (or after its
  owner), ignoring case, spaces and symbols. An entry that matches no party shows on its own.
- **Kills** count from a snapshot taken when the week starts, so only this week's count. Arena kills
  don't (the arena's fights are for the Cup). Feeding kills to a friend is exploit B13: staff take them
  back.
- **Where it shows.** Sunday at 7 pm Pacific the week closes: the final table is posted in Discord
  (`STANDINGS_WEBHOOK_URL`, else the main channel), announced in chat, and kept on the board. The board is
  a text display at spawn, and `/trigger standings` shows it in chat anywhere. It has this week so far,
  updated every hour, and last week's final top five.
- Everything is read from the world's own saved files, which the server writes every 5 minutes, so the
  board can be a few minutes behind. A kill just before the close counts in the next week; none is lost.

`tools/standings.py` works it out, the `realms-standings` data pack counts kills and holds the board, and
`deploy/realms-standings.sh` runs it on the VPS (docs/LIVE.md); staff commands are in docs/ADMIN.md.

Between events, three **weekly challenges** (one solo, one faction, one explore) give everyone something to
do that week, about one to three hours of play. A new set starts every Monday at 12 AM Pacific, after
the Saturday event, and each one done counts toward three wardrobe skins (`docs/RETENTION.md`, "Weekly
challenges"). The faction challenge is sometimes "Come to an event", so the Saturday slot counts for it. The
launch weekend is challenge week 0, and week 1 starts on Monday 23 November 2026. See what runs when with
`python tools/challenges.py schedule`.

### War and pacts

Factions can declare war and make pacts in game. It gives the weekly Kills column a reason, and it puts on
record who is with whom.

- **Who decides.** A faction's leader, the owner of its party, types `/trigger diplomacy`. Anyone in a
  faction can open it to see how theirs stands with every other faction; only the leader gets the buttons.
  It opens at the launch, so nothing from test play counts.
- **War.** A leader declares war on another faction. Everyone online is told, with a raid horn. Until
  Sunday's close (7 pm Pacific), a kill between the two factions counts twice in the weekly Kills column,
  for both sides. The close ends every war; a leader declares again to go on. Claims still protect, and the
  griefing rules and rule 41 still apply: a war changes the score, not what is allowed. Arena kills don't
  count, as for the Kills column.
- **Pacts.** A leader offers a pact and the other leader accepts it from their own menu. An offer lasts until
  Sunday's close. Accepting ends a war between the two. While a pact stands, neither can declare war on the
  other. It stands until either leader breaks it, and the break is announced with the faction and the player
  who broke it; 2 minutes later that leader can declare war. A faction holds at most 2 pacts (rule 31:
  alliances, not confederations). A pact is not an Open Parties and Claims ally: allies share claims, a pact
  shares nothing.
- **Limits.** One declaration (war, offer, acceptance or break) per faction every 2 minutes, so chat isn't
  flooded.
- **Where it shows.** In chat at once. Sunday's standings post in Discord adds the week's wars, pacts, peace
  and broken pacts (at most 10, then "and N more") and the pacts still standing. Offers stay out of it.
- **Feeding kills** to a war enemy is exploit B13, as with any kill: staff take both counts back
  (docs/ADMIN.md, "War and pacts").
- **New and gone factions.** The hourly board run gives each new party its faction number in game, so a
  party made a minute ago can't take part yet. When a party is gone, its wars and pacts end, announced, and
  its pact partners get the slot back.

`tools/diplomacy.py` makes it, inside the `realms-standings` data pack. It needs no timer of its own: the
standings' hourly board run writes the faction numbers, and the Sunday close ends the wars.

### Outposts

Four capture points out in the newest land, so factions have somewhere to meet between events.

- **Where.** One in each quarter of the newest border ring: North, East, South and West of the border's
  centre. Before the first border act that is past 400 blocks from spawn; after one, only the land it added.
  Each stands on dry ground, 6 or more chunks from every claim. They are placed within the hour after the
  launch, and again within the hour after each border act has finished growing.
- **Taking one.** Stand inside its square (25 blocks across, from 8 under the ground to 24 over it) with
  your faction and nobody from another faction for 60 seconds. Two factions inside: it is contested, and the
  count waits. Everyone leaves: the attempt ends. The holder's members are told when someone starts, and
  everyone is told when it falls. A text over it says who holds it, and particles mark its corners.
- **Who counts.** Players in survival with a faction number: in a party the hourly board run has picked up
  (War and pacts, "New and gone factions"). A player in no party, or in one made since the last board run,
  can't take one and doesn't block one. Players in the event arena don't count.
- **Points.** Each minute a faction holds an outpost while a survival player of another faction is online
  counts. Each whole hour of those this week is +1 standings point, at most 20 a week, on top of the 100
  (the Outposts row above). Holding all four for an hour is four hours. Nothing else is given: no items, no
  effects.
- **Moves.** A claim made within 3 chunks of an outpost moves it to a new spot in its quarter within the
  hour; its holder keeps it. After a border act all four move out to the new ring and start with no holder;
  hours already earned stay.
- **Where it shows.** `/trigger outposts` lists each one, where it is, who holds it, whether someone is
  taking it, and your faction's hours this season. The live map has an "Outposts" marker set with the four
  spots (not the holders: those change too often).
- **Restarts** keep the holders, the attempts' counts and the hours (scores and storage are saved with the
  world). Test play before the launch counts for nothing: the launch clears it.
- **Feeding** an outpost to a friendly faction, or trading one back and forth for hours, is exploit B13, as
  feeding kills is: staff free it and take the hours back (docs/ADMIN.md, "Outposts").

`tools/outposts.py` places them and makes the `realms-outposts` data pack; `deploy/realms-outposts.sh` runs
every hour on the VPS (docs/LIVE.md). Staff commands are in docs/ADMIN.md.

### The pillar events

The owners' four events. They come back every season, so players know them and get better at them.
Each one awards **Season Cup** points to factions. The Cup decides the season champion, so a faction
that loses one fight is still in the race.

| Season Cup | 1st | 2nd | 3rd | Took part |
| --- | --- | --- | --- | --- |
| Build Battle | 30 | 20 | 10 | 5 |
| Faction Raid | 10 a captured flag held at the end, +10 for still holding your own | | | 5 |
| Arena Glory, faction bracket | 30 | 20 | 10 | 5 |
| Arena Glory, individual champion | 10 to their faction | | | |
| Anarchy | 20 to the faction with the dragon's last hit | | | |
| The finale | 50 | 30 | 15 | 5 |

Keep the standings on a sidebar at spawn (`scoreboard objectives add ev.cup dummy`, one entry per
faction) and post them in `#monkey-smp` after every event. The Cup is also the biggest column of the
weekly standings (above).

#### Build Battle (launch days 1 and 2)

- **The wheel.** At launch, staff spin a wheel of blocks three times, live in Discord. Each block is a
  bonus: a build that clearly uses it scores extra. The wheel only holds blocks you can get in survival
  before the End opens: no bedrock, spawners, command blocks, reinforced deepslate, budding amethyst or
  End blocks. A rare spin is the point, though. Someone has to go and get it.
- **Builders and scavengers.** Factions split up: some build, and some go out for the bonus blocks. PvP
  opens after the first hour (rule 23), so the scavengers fight over the same caves, villages and
  Nether spots.
- **Where.** On equal 32 x 32 plots in a showcase area next to spawn. Each plot is claimed for one
  faction for the event, so only that faction can place or break blocks there. Plots rather than
  territory, because on launch day nobody has territory yet, and a four-player faction's territory is
  four times a solo player's. The finished builds stay as the season's gallery.
- **The plots are a no-PvP zone** while the event runs. Everywhere else PvP opens after the first hour
  as usual, so the fight is over materials, not over the builds.
- **Visibly used** means at least 9 blocks of the wheel block, seen from the plot's edge. One block
  hidden in a wall doesn't count.
- **Survival only.** Every block comes from this world (it is new, so nothing is pre-built), and no
  schematic printers or other mods that place blocks (B15).
- **Judging,** on the second night: owners plus one guest judge. Each scores look (10) and idea (10).
  Each wheel block used visibly adds 5. Players vote in Discord as the tiebreak, and nobody can vote for
  their own faction.
- **Prizes:** Cup points; the winning build is featured on the site; every builder in the winning
  faction gets a title.

#### Faction Raid (capture the flag)

The territory rules (34, 37 and 39) protect bases, so a raid can't mean griefing. Instead:

- **Official flags.** Before the raid, staff give each faction one official flag: its banner, tagged so
  that a copy made at a loom doesn't count.
- **The flag yard.** Each faction plants its flag in the open, in a marked yard next to its territory
  but **outside** it (an unclaimed chunk, so claims don't protect it). It must be reachable on foot, and
  it can't be walled in, buried or trapped with lava. Defenders guard the yard. Raiders never need to
  break into a base.
- **Raid window.** Two hours, Saturday evening. Inside the window, a flag yard counts as open ground:
  KOS there is fine, and every combat rule and ban still applies (no elytra into the fight, no lava, no
  pearls, no restocking mid-fight).
- **Yard checks.** Staff check every yard in the hour before the window. The flag stands on open ground,
  with nothing within 3 blocks of it except the post it stands on, and no decoy banners in the yard. A
  faction whose yard fails the check sits the raid out.
- **Capturing.** Break the enemy flag, carry it to your own yard and plant it next to yours. You can't
  capture while your own flag is missing. A carrier who dies drops the flag, and anyone can pick it up.
- **A flag travels in your inventory,** never in a shulker box or ender chest. A flag stored there, or
  carried by a player who logs out, goes back to its owners and the capture doesn't count.
- **Swapping flags with an ally gains nothing:** both factions lose the bonus for holding their own,
  and neither can plant while its own flag is missing.
- **Deaths count as usual,** Strength included. A raid that is "Strength-safe" would need everyone's
  Strength saved and restored, and a player could withdraw Strength into items in between and then get
  the level back: a duplication bug. Raids are a risk worth taking, so they stay real.
- **Scoring.** At the end of the window, staff count the official flags in each yard (Cup table above).
  Flags go back to their factions afterwards.
- **Safety net.** Anything griefed outside the yards is rolled back with Ledger (`ledger rollback
  after:2h`, docs/ADMIN.md), and griefing outside the yards is still a rule 37 offence.

#### Arena Glory (kit combat)

- **The arena.** An admin-built arena next to spawn, with a waiting room, a 1v1 pit and a team floor.
  Spawn rules (22) don't stop staff from building it.
- **Kits only.** You enter with an empty inventory and armor slots, get the round's kit, and leave with
  nothing. Your own gear can't be lost, and a day-one player is on even terms with a veteran. Items
  dropped in the arena are cleared after each round.
- **Strength is set aside.** On entry your Strength level (`Strength_SMP+Strength_Level`) is saved and
  set to +3 for everyone, which is the level every player starts with. On exit it is restored. Dying in
  the arena costs no real Strength, and winning gains none.
- **No way to carry anything out.** The arena runs in adventure mode, so nobody can place an ender chest
  or break blocks. Your inventory is cleared when you leave, and items on the floor are cleared after
  every round. That also stops the Strength exploit: anything withdrawn as an item inside the arena is
  destroyed, and the restored level is the one you came in with.
- **Logging out inside** clears you on your next join: inventory cleared, Strength restored, sent back
  to the waiting room.
- **Kits follow the bans:** no totems, pearls, crystals, enchanted golden apples, enchanted maces or
  Fire Aspect/Flame; bow debuffs only as B6 allows. Rotate kits between rounds: sword and shield, bow
  and crossbow, axe, spear, and an unenchanted mace.
- **Formats.** 1v1 single elimination (best of three) for individuals; 2v2 and the 4v4 faction bracket
  for teams.
- **Prizes.** Individual champions get a title, an arena skin in the wardrobe and one event book (B18).
  Team winners get Cup points, and their banner hangs on the arena wall until the next Arena Glory.
- **Event books carry lore** ("Monkey SMP event reward, Season I"). An anvil can rename a book but
  can't add lore, so only books with that line may be applied under B18. A book is never above the
  vanilla maximum level, and never Fire Aspect or Flame.
- **Bracket seeding** keeps players from the same faction apart until the semifinal, so teammates can't
  throw matches to each other early.

#### Anarchy (when the End opens)

Staff open the End in the event slot in week 3 (`function realms:rules/open_end`, docs/RULES.md), and a 90-minute countdown starts (a boss bar for
everyone). The dragon fight happens in the middle of it.

**Off for the 90 minutes:** the combat rules (2 to 6, 9, 11 to 19), KOS limits in territory (34, 35
and 38), the faction size limit while fighting (32), and the gameplay bans B1 to B10 and B12: crystals,
beds, pearls, totems, enchanted golden apples, maces, debuffs, escape tunnels, TNT carts.

**Still on:**
- **Griefing.** Spawn (8, 22, B11), territory (36, 37, 39) and pets (20). You may kill someone in their
  base, but you may not break, rob or burn it. Lava and TNT in someone's territory are griefing.
  Claims still protect blocks.
- **Cheating.** Hacked clients, x-ray, exploits and duping (7, B13 to B17, B19), account sharing (21),
  and leaving the world border (25). Anarchy is about the rules of the fight, not the rules of the
  game.
- **People.** Harassment, hate, real-money trading and the all-ages rules.
- **Permanent gains.** The Strength crafting cap (28) and faction membership (29, 30, 33) stay, because
  their effects outlast the window.
- **Server config.** Anything the server disables (Fire Aspect and Flame, and Netherite armor until
  week 5) stays disabled. Anarchy doesn't change the config.

**When the window ends:**
- **Ceasefire for 10 minutes.** A fight that started in Anarchy doesn't carry over into normal rules,
  and nobody argues about who hit first.
- **Banned items must be gone by the end of the ceasefire:** used, destroyed or thrown in the void.
  Staff run `clear` on everyone online for totems, end crystals and enchanted golden apples, and the
  usual bans apply to anything found later, in an ender chest too. Pearls and golden apples kept for
  crafting stay legal, as before.
- **Traps come down.** Respawn and logout traps, and lava traps, built during Anarchy are removed by
  their builders during the ceasefire. Staff remove what's left with Ledger, and a death to one
  afterwards is judged under the normal rules.
- **What you won, you keep:** Strength taken in fights, and loot. Feeding Strength on purpose (a friend
  or an alt dying to you again and again) is an exploit (B13), Anarchy or not.
- **The dragon's last hit** earns its faction 20 Cup points and the egg.

Anyone who doesn't want to take part logs out before the countdown starts. That isn't combat logging,
because nobody is in a fight yet.

### The season champion

The faction with the most Cup points after the finale is the season's champion. Its prizes last into
the next season, because a prize that resets with the world is forgotten in a week:

- **Its name is held for it.** At the next season's sign-up no other faction may register that name.
  The champions can re-form under it or let it go; if none of them comes back, it is free again.
- **A title for the whole roster.** Everyone in the faction when the finale ended gets `[S1 Champion]`
  in gold before their name, in chat, the player list and on name tags, for good. Staff set it up once,
  after the finale (one team per season, so a two-time champion picks which to show):

  ```
  team add champion_s1
  team modify champion_s1 color gold
  team modify champion_s1 prefix "[S1 Champion] "
  team join champion_s1 NAME          # each member of the winning faction
  ```

  It is a scoreboard team like the supporter titles in `docs/RETENTION.md` ("Name colors and titles"),
  and a player shows one team at a time. A champion who is also a supporter picks the title or the
  supporter color; the supporter skins stay either way. The store's expiry command (`team leave`) also
  drops the title, so put the player back with `team join champion_s1 NAME`.
- **The banner and the helm** (above): the banner in the Hall of Banners at the next spawn, and a
  champion helm in the wardrobe. Neither is built yet.

### The event catalog

The weeks between pillar events rotate through these. All events follow the rulebook: no crystals, totems, pearls or Fire Aspect, and the combat rules apply.
Rewards are cosmetic or event-only. **B18 enchantment books** are the one gameplay reward, because the
rules already make them event-only. Give at most one per event, so events don't decide the season.

| Event | How it works | Good for |
| --- | --- | --- |
| **KOTH** | A hill outside every territory. Holding it earns points; most points after 30 minutes wins. | Faction PvP without base raids |
| **Supply drop** | Chests at coordinates announced 10 minutes ahead, in the newest border ring. Built: one comes by itself on weeknight evenings once 4 or more are on, and staff can start one any time (docs/ADMIN.md, "Supply drops"). | Exploration, small fights, new players |
| **Bounty board** | Staff post bounties on the top Strength holders. Whoever kills one in a fair fight outside the arena claims it: the Bounty Hunter title for the season and +5 weekly standings points for their faction. Nothing is sold and nothing helps in a fight. | Keeping the top in check |
| **Boss night** | Everyone against a boss in an arena (the Wither, or a boss the modpack adds). Truce. | A night everyone can join |
| **Treasure hunt** | Clues in Discord lead to a buried chest. | Players who don't PvP |
| **Market day** | Trading at spawn with stalls; spawn rules apply. | The economy, meeting other factions |

Twists for later seasons (pick two or three for the vote):

- Hardcore hearts: lose a heart a death; a player out of hearts sits out until the next weekly event.
  Nobody is out for the season.
- Bigger factions (5) and a smaller world.
- Strength cap +3, so fights are about skill.
- One shared village that every faction must protect from raids.
- A world seed with a huge ocean, so travel and the Happy Ghast matter.

### Holidays

Three dated events a year, whatever week of the season they fall in. A holiday is an overlay: spawn
gets decorated for the week and that Saturday's event takes the holiday's theme, but the season's acts
don't move.

| Holiday | When | Next | Spawn | The event | Skin |
| --- | --- | --- | --- | --- | --- |
| Hallowtide | the last Saturday of October | 2026-10-31 | pumpkins, soul lanterns, cobwebs | boss night after dark, or a haunted maze | Gravelight (blade) |
| Midwinter | the Saturday before December 25 | 2026-12-19 | snow, lights, a tree | snowball fight in the arena, then gifts at spawn | Midwinter Cap (helm) |
| Midsummer | the Saturday nearest June 21 | 2027-06-19 | flowers, banners, a bonfire | boat race or treasure hunt | Solstice (blade) |

- **The skin comes from being there.** Near the end of the event, a staff member standing with the crowd
  runs `/scoreboard players set @a[distance=..48] rw.hallowtide 1` (`rw.midwinter`, `rw.midsummer`),
  or `scoreboard players set NAME rw.hallowtide 1` one name at a time. Players see "Unlocked Gravelight"
  in chat. Run `begin` and `attend` too (`docs/ADMIN.md`, "Attendance"), so it counts toward Rallier and
  the Plumed Helm like any event.
- **Never sold.** No store package, supporter tier or favour sets a holiday score, and
  `tests/test_wardrobe.py` fails if a store command in `docs/RETENTION.md` does. A skin missed this
  year comes back at next year's event, so missing one costs a year's wait, not the skin.
- **Announce it two weeks ahead** with `/gamenight`, like any event, and say which skin it brings.
- **Decorate in creative** (spawn rules, 22) the week before, and take it down the weekend after.
- **In the off-season week** it runs anyway, in the locked world.

A holiday skin needs the client pack it shipped in. A player on an older pack still gets the score; the
skin is waiting in the wardrobe once they update.

### Base of the Month

Once a month the owners pick one base and show it off. A factions server mostly rewards building with
safety; this gives builders a moment of their own, the way events do for fighters.

- **Opt in.** A faction or a solo player enters by posting in the month's Base of the Month thread in
  `#smp-forum` by the 25th. Nobody's base is shown without asking.
- **Pictures from the live map, no coordinates.** Staff take two or three screenshots in BlueMap's free
  view, close enough to show the build. No coordinates and no map link in the post: the map is public,
  but there is no need to point raiders at the door.
- **Judged by the owners** on look and idea (10 each, as in Build Battle). The same faction can't win two
  months running.
- **Posted on the first Saturday**, at the Town Hall, in `#monkey-smp`: the pictures, the builders' names
  and a line from them about the build. The winners get a Base of the Month role in Discord for the month.
- **No Cup points.** It is for builders, and points would turn it into a chore for every faction.

### New players in mid-season

A Strength server gets harder to join every week, so catching up has to be built in:

- New land with every border act, so there is unmapped loot to find.
- Arena Glory and boss nights use kits and set Strength aside, so a day-one player can still win.
- The Cup is a faction score, so a newcomer who joins a faction adds to its total from their first event.
- Factions need members (rule 29 caps them at four, but most start smaller). Point newcomers at
  `#smp-forum` recruitment on their first day. The welcome screen a first join gets does this.
- A 48-hour PvP grace period for a first join (rule 26), built into the `realms-rules` data pack
  (`tools/rules.py`). Attacking a player ends it, and nobody gets it in the launch hour.

### Telling players what changed

Every rule, mod or config change players will notice goes in the player changelog, `site/changes.html`
on the site (`docs/ADMIN.md`, "Telling players what changed"), and the same lines go in Discord's
`#changelog` channel the day it goes live. A season that changes a rule mid-way without saying so loses
trust faster than one that never changes.

## Ending a season

The runbook for weeks 11 to 13, written before Season I's week 12 so the last weeks run from a checklist.
Paths are the live server's (`docs/LIVE.md`): commands run in `/srv/realms/TheRealms-Server/docker`, and
`realms rcon "..."` is short for `docker compose exec realms realms rcon "..."`. Season I and season 2
are the example; change the numbers.

**Two weeks before the end**

1. Announce the end date again (it was announced on day one), the finale, and what carries over (above).
2. Open the vote on next season's twist in Discord, and set the next start date.
3. Pick the next seed: try a few in singleplayer with the modpack, then put the winner in
   `package/realms/manifest.json` (`world.seed`) for the release that opens the season, so a fresh install
   matches the live world.

**After the finale (end of week 11)**

4. Post the final Cup standings and crown the champion: its title team ("The season champion", above).
5. Lock the world: `realms rcon "function realms:events/season/lock"`. Players in survival switch to
   adventure (they can look around and use doors, but not build or break; claims still guard
   containers), PvP is off and the difficulty is peaceful. It stays locked across restarts, and players who log in during the off-season
   are locked too. Staff in creative are not affected. `function realms:events/season/unlock` undoes it.
6. Back it up: `docker compose exec realms realms backup`. The backup folder keeps only the newest 14, so
   copy this one out of the rotation:
   `mkdir -p /srv/realms/seasons && cp -a ../backups/<newest> /srv/realms/seasons/season-I`. Keep a copy
   off the machine too: the off-site backups in `docs/LIVE.md` copy `backups/` only, so add
   `/srv/realms/seasons` to that job or upload the folder by hand.
7. Make the download:

   ```sh
   python3 /srv/realms/repo/tools/season.py download /srv/realms/seasons/season-I/world \
       --season I --modpack 2.5.0 --out "/srv/realms/seasons/Monkey SMP Season I.zip"
   ```

   `--modpack` is the release that is live (`realms-deploy.sh --status`). The zip holds the map, every
   player's inventory and stats, and the data packs, with a READ ME on opening it. It leaves out the Ledger
   database, server config and everything outside the world folder (the RCON password, ops, whitelist).
   Open it in singleplayer once before posting it.
8. Upload it where anyone can download it without an account (a public bucket of its own, or a file
   share set to "anyone with the link"), never the private backup bucket. Post the link in
   `#monkey-smp` and on the changelog page.

**Off-season (week 12)**

The locked world stays up for tours and screenshots. Holidays and the Town Hall run as usual. Pass
renewals keep counting: the store's commands still reach the old world, and the carry below picks them up.

**Starting the next season**

9. Release the update that opens the season (the new seed, the season's skin, the twist) and let it
   deploy. Then pause deploys for the switch: `sudo systemctl stop realms-deploy.timer`.
10. Stop the server: `docker compose stop`.
11. Move the old world out: `mv ../server/world /srv/realms/seasons/season-I/world-end`. This is the final
    state, off-season renewals included; the carry reads it.
12. Set the new seed in the live `../server/server.properties` (`level-seed=...`). Nothing else changes.
13. Carry the wardrobe over, before the first start:

    ```sh
    python3 /srv/realms/repo/tools/season.py carry /srv/realms/seasons/season-I/world-end \
        --into /srv/realms/TheRealms-Server/server/world --season 2
    ```

    It writes one small data pack, `realms-carry`, into the new world folder. It holds every player's
    wardrobe scores (days, months, invites, events, holidays, weekly challenges done, tier, founder and
    the launch weekend), their hours played, and the
    supporter, title and champion teams. It runs by itself at the new world's first load, once, and sets
    the season to 2, so no one gets Founder's Edge in the new world.
14. Start it: `docker compose up -d`. The world generates, the installer adds the Monkey SMP data packs, and
    the console says "Carried N players' wardrobe scores and K teams into season 2." Within the hour,
    `realms-week.timer` tells the new world the challenge week (it keeps the rotation going; this week's
    progress starts from zero).
15. Check: `realms rcon "scoreboard players get #carried rw.day"` gives 1,
    `realms rcon "scoreboard players get #season rw.day"` gives 2, and one regular's
    `scoreboard players get NAME rw.days` matches the old world.
16. Clear the old world off the live map (`realms rcon "bluemap purge world"`, and the same for
    `world_the_nether` and `world_the_end`, BlueMap's map ids), then pre-generate the new one as on the
    first setup (`docs/LIVE.md`, step 6).
17. Turn deploys back on: `sudo systemctl start realms-deploy.timer`. Launch as in week 0, with
    `function realms:rules/launch` (`docs/RULES.md`).

The new world starts unlocked; the lock lives in the old world. The `realms-carry` pack can stay (it
won't run twice). Delete its folder at the next restart to tidy up.

## What is built and what isn't

Built:
- The wardrobe and Founder's Edge.
- Weekly challenges (`tools/challenges.py`, in the `realms-wardrobe` data pack): three a week from a pool
  that rotates every Monday at 12 AM Pacific, `/trigger challenges`, and their skins at 3, 9 and 18
  challenges done (Trailblazer, the Vanguard Helm, Pinnacle). `realms-week.timer` sends the week.
- Founder's Circlet, for 10 minutes online on Season I's launch weekend: opened by `rules/launch`, closed
  at the end of Sunday, Pacific.
- The season counter (`#season rw.day`).
- `/gamenight` and the Town Hall in Front Desk.
- `tools/retention.py`.
- The event tooling, in the `realms-events` data pack (`tools/events.py`; commands in `docs/ADMIN.md`):
  - Arena functions: join (empty inventory, armor and offhand, at the entrance), leave, five kits that
    follow the bans, Strength saved and held at +3 (withdrawals blocked), drops cleaned every tick, and a
    player who logs out or is teleported out of the radius taken out with their Strength back. Kit gear
    is marked and can't leave: players inside hold nothing else, minecarts, chest boats and pack animals
    in the arena are removed, the ender chest can't hold a bundle and is stripped on the way out, and
    gear that still gets out is cleared from anyone outside the arena who takes it.
  - The Anarchy timer: a boss bar for 90 minutes, then the 10-minute ceasefire, then the `clear` of
    totems, end crystals and enchanted golden apples.
  - The Faction Raid timer: a 2-hour boss bar. A player who logs out during a raid loses any flag they
    carry.
  - Official flags: a faction's banner with a tag and a serial number, kept when placed and broken.
  - Event books (lore-tagged, vanilla max level, none for banned enchantments) and the `ev.cup` sidebar.
  - The attendance counter (`rw.events`, once per event), and its skins at 3 and 10 events (Rallier, the
    Plumed Helm).
  - The season lock (`function realms:events/season/lock` and `unlock`).
- The holiday skins (Gravelight, Midwinter Cap, Solstice) and the tenure ladder at 1, 2 and 3 months.
- The season-end runbook ("Ending a season") and `tools/season.py`: the world download, and carrying
  the wardrobe, hours played and title teams into the next world.
- The player changelog page, `site/changes.html`.
- The block wheel: `tools/block_wheel.py` draws from `tools/wheel_pool.txt` (every survival-obtainable
  block, built from the game's data reports) with a published seed, so anyone can check the draw.
- The first-join welcome, the pause menu's links and the 48-hour PvP grace (rule 26), in the
  `realms-rules` data pack (`tools/rules.py`). Grace is off in the arena, and fighting there doesn't end
  it.
- The weekly standings ("Weekly standings"): `tools/standings.py`, the `realms-standings` data pack (the
  week's kills, the board at spawn, `/trigger standings`, the bounty commands and the Bounty Hunter title)
  and the Sunday timer on the VPS (`deploy/realms-standings.sh`, set up with `deploy/install-standings.sh`).
  Seen in game on a test server on 26 October 2026 (2.6.0, Carpet fake players): the four columns, the board
  and `/trigger standings`, bounties posted and claimed (one offline) with the Bounty Hunter title, and a Sunday
  run of `deploy/realms-standings.sh` against a stand-in for docker. Not yet with real players or on the VPS.
- War and pacts ("War and pacts"): `tools/diplomacy.py`, in the `realms-standings` data pack:
  `/trigger diplomacy`, war kills counted twice, the Sunday post's lines and the wars' end at the close, and
  each faction's number in game (`st.faction`), written by the hourly board run for other features to use
  (docs/MAINTAINING.md, "The faction number in game"). Checked by the unit tests and the generated packs'
  checks only: not yet tried in game.
- Supply drops ("Supply drop" in the event catalog; docs/ADMIN.md, "Supply drops"): `tools/drops.py`, the
  `realms-drops` data pack and `deploy/realms-drops.sh` with its 10-minute timer. Monday to Thursday, 6 to
  10 PM Pacific, the first time 4 or more are online (staff change the number in game): a boss bar and chat
  give the coordinates 10 minutes ahead, then 1 chest per 4 players online (at most 3) lands in the newest
  border ring, 6 or more chunks from every claim, and despawns after 20 minutes. Modest loot (food, iron,
  arrows, wood): nothing Strength, no netherite, diamonds or emeralds. Tried on a test server: the pack
  loads, the chests land, scale and despawn, and a drop survives a restart.
- Outposts ("Outposts"): `tools/outposts.py`, the `realms-outposts` data pack and `deploy/realms-outposts.sh`
  with its hourly timer. Four capture points in the newest border ring, 6 or more chunks from every claim, 60
  seconds to take one, +1 standings point an hour held (at most 20 a week), and an "Outposts" marker set on
  the live map. Checked by the unit tests and the generated packs' checks only: not yet tried in game.

Not built:

| To build | Notes |
| --- | --- |
| Season skins after Season I | One new blade per season in `tools/wardrobe.py`, unlocked by the season number (as Founder's Edge is) |
| Champion helm and Hall of Banners | One helm and a build at each new spawn |
| Border acts | `worldborder set` over RCON on the date, for the Overworld and the Nether (1:8), then fit the live map to it and render it again with `tools/map_border.py` (docs/ADMIN.md, "The live map"). The `realms-rules` pack sets the starting 2500 border (and the Nether's at 1:8) once; grow both by hand |
| KOTH | Run by staff by hand at first. Automate only if events are weekly and well attended (supply drops are built: above) |
| Faction sign-up form | A form (Front Desk, in the Discord repo) for the name, members, banner and charter; a forum post works until then |
| Base of the Month role | A Discord role, handed out by hand |

Decided (the owners asked for whatever closes loopholes; change any of it in this file):

1. Raid deaths cost real Strength. A Strength-safe raid would need save and restore for the whole
   server, which opens a duplication exploit (Faction Raid, above).
2. Arena Glory sets everyone to +3, in adventure mode, and clears inventories on the way out.
3. Build Battle uses equal plots next to spawn, not territory.
4. One lore-tagged event book per individual champion, two Arena Glories a season. One book per event
   can't decide a season.
5. Every event is Saturday at 6 pm Pacific, announced a week ahead as a Discord event.
6. Anarchy keeps the griefing, cheating, conduct and permanent-gain rules, ends with a 10-minute
   ceasefire, and banned items must be gone when the ceasefire ends.

Add to `docs/RULES.md` when the rulebook is next edited (the config-enforcement session owns it right
now): an "Events" section that points here and says that event rules override the numbered rules
only for an event's window.

Check after every event: did the D7 of that week's new players rise, and how many people marked
Interested compared with how many joined. Drop events that nobody marks Interested twice in a row.

## Sources

- SMP Online wiki, season lengths: https://smponline.fandom.com/wiki/SMP_Online
- GGServers, keeping a vanilla SMP alive: https://ggservers.com/blog/how-to-keep-a-minecraft-vanilla-smp-alive/
- MC-Node, keeping an SMP fun for months: https://mc-node.net/blog/en/start-an-smp-with-friends/
- Pine Hosting, server analytics: https://pinehosting.com/blog/minecraft-server-analytics-what-owners-should-track-to-grow-their-community/
- Lifesteal Network, End of the World: https://lifestealnet.fandom.com/wiki/Lifesteal_Network
- Lifesteal SMP Season 7: https://lifesteal.fandom.com/wiki/Season_7
- Lifesteal SMP design guide (elimination): https://www.fumora.net/lab/minecraft-lifesteal-smp
- McServ, Lifesteal guide: https://mcserv.org/blog/what-is-lifesteal-smp-minecraft-complete-guide-2026
- Omen automated events (supply drops, scheduler): https://builtbybit.com/resources/omen-automated-server-events.115155/
- FoKoTH (scheduled KOTH): https://modrinth.com/plugin/fokoth
- Retention benchmarks and live events: https://gamegrowthadvisor.com/blog/2026-03-17-mobile-game-retention-strategies-2026/
- Retention benchmarks: https://segwise.ai/blog/mobile-gaming-app-user-retention-strategies
