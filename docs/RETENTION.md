# Keeping players: the wardrobe, events and the numbers

Monkey SMP earns its keep from monthly passes, so the number that matters most is how many players
come back. This page covers what rewards staying, the commands the store and staff run, and how to
read retention from the server logs.

## The wardrobe

`/trigger wardrobe` opens a clickable menu of skins for swords and helmets, on two pages: skins earned in
game, and pass and supporter skins (a link at the bottom switches). A skin changes only how the
item looks (its model, and on a helmet the worn look). Damage, armor, durability and enchantments
never change, and `tests/test_wardrobe.py` fails the build if one ever does. This follows Mojang's
rule that what players pay for must be cosmetic, and it keeps the server fair: the same pass price
for everyone, no advantage for sale.

Skins unlock by playing, by coming to events, by staying, by bringing friends, or by supporting:

![Every wardrobe skin: blades, helm icons and the helms as worn](img/wardrobe.png)

| Skin | Kind | Unlocks at | Score |
| --- | --- | --- | --- |
| Wayfarer | blade | 3 days played | `rw.days 3` |
| Laurel | helm | 7 days played | `rw.days 7` |
| Emberfang | blade | 10 hours played | `rw.hours 10` |
| Frostbite | blade | 15 days played | `rw.days 15` |
| Starfall | blade | 30 days played | `rw.days 30` |
| Verdant | blade | 1 friend invited | `rw.invites 1` |
| Horned Helm | helm | 3 friends invited | `rw.invites 3` |
| Rallier | blade | 3 events attended | `rw.events 3` |
| Plumed Helm | helm | 10 events attended | `rw.events 10` |
| Gravelight | blade | came to Hallowtide (late October) | `rw.hallowtide 1` |
| Midwinter Cap | helm | came to Midwinter (late December) | `rw.midwinter 1` |
| Solstice | blade | came to Midsummer (late June) | `rw.midsummer 1` |
| Oathblade I | blade | 1 month of pass | `rw.months 1` |
| Oathblade II | blade | 2 months of pass | `rw.months 2` |
| Oathblade III | blade | 3 months of pass | `rw.months 3` |
| Old Guard | blade | 6 months of pass | `rw.months 6` |
| Wanderer's Hood | helm | 12 months of pass | `rw.months 12` |
| Founder's Edge | blade | played in season 1 | `rw.founder 1` |
| Lantern | blade | Ember supporter | `rw.tier 1` |
| Standard | blade | Banner supporter | `rw.tier 2` |
| Regalia | blade | Crown supporter | `rw.tier 3` |
| Crown | helm | Crown supporter | `rw.tier 3` |

Why these counters:

- **Days played, not streaks.** A day counts when a player is online at any point that UTC day. Streaks
  punish a missed weekend and push people to log in out of guilt; a count only goes up.
- **Tenure** (`rw.months`) rewards renewing the pass: the Oathblades, the Old Guard and the Wanderer's
  Hood can't be bought, only kept. The ladder starts at month 1 and steps at 2 and 3, so a new buyer gets
  something at each early renewal, when most passes lapse, instead of waiting six months. Steps add up:
  a 3-month pass unlocks the first three at once.
- **Events attended** (`rw.events`): Rallier at 3 and the Plumed Helm at 10. The events pack counts one
  per event when staff run `attend` (`docs/ADMIN.md`, "Attendance").
- **Holidays** (Gravelight, Midwinter Cap, Solstice) come only from being at that holiday's event
  (`docs/SEASONS.md`, "Holidays"). They are never sold: no store command sets these scores, and
  `tests/test_wardrobe.py` fails if one does. A skin missed this year comes back at next year's event.
- **Founder.** Everyone who plays while `#season` is 1 gets Founder's Edge for good. End season 1 when
  the first wave is in (see below) so that the edge stays rare. If nobody does, the next season's carry
  sets `#season` to 2 in the new world.
- **Invites** line up with the invite ladder on the site (1, 3 and 5 friends).
- **Supporter tiers** get the flashiest skins, because they pay for the server.

`realms-day.timer` starts a new day at midnight UTC (`docs/LIVE.md`, step 7). Without it, nobody's day
count moves.

When the store, staff or an event raises a player's months, events or a holiday score, they get an
"Unlocked ..." line in chat within a second, or at their next login if they were offline. Days played
announce themselves the same way.

All these scores live in the world, so a new season's world would start them at zero. The season-end
runbook carries them over, hours played included, along with the supporter, title and champion teams
below (`docs/SEASONS.md`, "Ending a season"). The season champion's title is a team like the titles
below, `champion_s1` and so on (`docs/SEASONS.md`, "The season champion").

## Commands for the store and staff

Run these over RCON (`docs/LIVE.md`, "Day to day"). A Tebex package runs the same commands, with
`{username}` for the buyer's name.

| When | Command |
| --- | --- |
| A supporter tier is bought (1 Ember, 2 Banner, 3 Crown) | `scoreboard players set {username} rw.tier 2` |
| The same purchase: chat name color | `team join tier_banner {username}` (or `tier_ember`, `tier_crown`) |
| It expires or is refunded | `scoreboard players set {username} rw.tier 0` and `team leave {username}` |
| A Banner or Crown player picks a title, or earns Herald (staff) | see "Titles" below |
| A monthly pass renews | `scoreboard players add {username} rw.months 1` |
| A 3-month pass is bought | `scoreboard players add {username} rw.months 3` |
| A friend they invited buys a pass (staff) | `scoreboard players add NAME rw.invites 1` |
| Season 1 ends (once) | `scoreboard players set #season rw.day 2` |

Skins already applied stay on the item when a tier expires; the menu just stops offering locked ones.

### Name colors and titles

The server has no chat-formatting mod, so supporter colors and titles use vanilla scoreboard teams: a
team's color and prefix show on the player's name in chat, the player list and the name tag. Nothing else on
the server uses teams (factions are Open Parties and Claims parties), and a player is on one team at a time.

Once, before the store opens:

```
team add tier_ember
team modify tier_ember color gold
team add tier_banner
team modify tier_banner color green
team add tier_crown
team modify tier_crown color light_purple
```

A title is a team of its own, with the tier's color and the title as a prefix (staff, by hand):

```
team add title_NAME
team modify title_NAME color green
team modify title_NAME prefix "[Herald] "
team join title_NAME NAME
```

When the tier expires, `team leave NAME` drops the color and the title; Herald earned with 10 invites is kept,
so put that player back with `team join title_NAME NAME`. Not yet checked in game: run these on a test server
and look at chat before the store opens.
That is deliberate: taking away a cosmetic someone paid for feels worse than the few cents it costs.

## What else keeps people playing

- **The first hour.** Most players who leave do so on day one. Greet new names in chat and in
  Discord, give them a faction to join, and point them at `/trigger wardrobe`, where Wayfarer is
  3 days away.
- **A weekly rhythm and seasons.** One event a week in a fixed slot, a big moment every two to three
  weeks, and 12-week seasons with a finale and a fresh world: see `docs/SEASONS.md`.
- **Comebacks.** Reach out while a cancelled pass is still running, not after it has lapsed (below). A
  short, personal Discord DM about what's coming does more than a discount.

### When a pass is ending

A player who cancels a monthly pass keeps it until the month they paid for runs out. Until then Tebex
lists it as **Ending** (creator panel, Payments, Recurring Payments). That is the moment to talk to
them: they still have the server, and they decided recently enough to change their mind. A month after
it has lapsed, they have usually moved on.

- **Twice a week** (Monday and Thursday), a staff member filters Recurring Payments to Ending and sends
  each new name one Discord DM: what's coming this season, the next event, and one question, "Was there
  something that would have kept you?" No discount, no guilt, and no second message if they don't answer.
- **Write down the answer** next to their name in the staff channel, even when it is "no time".
- **Once a month**, read those answers with the reasons buyers gave Tebex when they cancelled, in the
  same sitting as the funnel numbers below. Three people saying the same thing is the next thing to fix.

Tebex can also send a webhook when a buyer cancels (`recurring-payment.cancellation.requested`), so
Front Desk could post each new Ending pass in the staff channel instead of someone checking. That is a
job for the Discord bot's repo, not built yet.

## Reading the numbers

```sh
python3 /srv/realms/repo/tools/retention.py /srv/realms/TheRealms-Server/server/logs
```

This reads the joins in the server logs. Nothing leaves the machine. It prints, for each week's new
players, the share who came back at least 1, 7 and 30 days later (D1, D7, D30), plus the number of
different players each week. A cell shows `-` until enough days have passed to judge it.

Worth checking monthly, next to the pass funnel below:

- **D7 under about 30%**: the first days aren't landing. Work on onboarding before adding content.
- **Different players each week falling** while D7 holds steady: you aren't getting new players. The
  invite ladder and the site matter more than features.
- **Pass churn** (passes not renewed, divided by passes active at the start of the month).

### The pass funnel: from purchase to renewal

```sh
python3 /srv/realms/repo/tools/funnel.py ~/payments.csv /srv/realms/TheRealms-Server/server/logs --log-tz America/Los_Angeles
```

Export the payments from Tebex (creator panel, Payments, Export as CSV) and copy the file to the VPS.
The tool matches each buyer to the server logs by name, and by UUID after a name change, and follows
them through five steps: the purchase, their first join, 30 minutes played, coming back a week after
that first join (D7), and the pass renewed. It prints:

- **Month-2 renewal**, the headline: of the monthly passes whose first month is over, the share that
  paid for a second. The budget below runs on this number. Passes whose month isn't over yet are counted
  as "not due yet", not as lost.
- The same for 3-month passes, once their three months are up.
- A row for each month's new buyers: how many joined, played 30 minutes, came back after a week, and
  renewed.
- **Bought a pass but never joined**: send each of them the install help (`docs/SHARING.md`) that day.

D7 is the diagnostic, renewal is the result. Read the steps in order and fix the first one that leaks:

- **Buyers who never join, or leave before 30 minutes**: the install or the first hour is the problem
  (the modpack download, the launch-hour rules, nobody saying hello), not the content.
- **30 minutes, but no D7**: the first week. See "The first hour" and the weekly rhythm above.
- **A good D7, but no renewal**: the month itself, its events and the Ending DMs' answers.

The CSV holds buyers' emails and IP addresses: keep it on the VPS or your own machine, never in the
repo (`.gitignore` skips `*.csv`; the only one committed is the made-up fixture in `tests/fixtures/`),
and delete it after the run. Tebex's dates are UTC and the live server logs Pacific time (`TZ` in
`docker/.env`), which is what `--log-tz` is for. The tool finds Tebex's columns by name and says
which it used; `--col username="Minecraft Username"` overrides a wrong guess. It warns about buyers who
bought before the oldest log, since it can't follow them.

## Churn and the budget

From the plan's cost model: a paying player brings in about $4.94 a month after fees, the server costs
$62.50 a month, and the server breaks even at 13 paying players.

| Monthly pass churn | Months a payer stays | Lifetime value | New payers a month to hold 30 |
| --- | --- | --- | --- |
| 25% | 4 | $19.76 | 7.5 |
| 15% | 6.7 | $32.93 | 4.5 |
| 10% | 10 | $49.40 | 3 |

Cutting churn from 25% to 10% is worth as much as more than doubling the new players you find each
month. That is why the wardrobe rewards days played and tenure, not purchases.
