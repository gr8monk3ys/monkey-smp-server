# Keeping players: the counters, events and the numbers

Monkey SMP earns its keep from monthly passes, so the number that matters most is how many players
come back. This page covers what rewards staying, the commands the store and staff run, and how to
read retention from the server logs.

## Cosmetics: the wardrobe skins are retired

Until the relaunch, `/trigger wardrobe` gave out cosmetic skins for swords and helmets (the Wayfarer, the
Oathblades, Founder's Edge and Circlet, the holiday and season skins, the Pathfinder blade and the rest). Their
models lived in the client pack's resource pack. The relaunch (Paper 26.3, Season 1 in February 2027) has
players join with plain vanilla Java or Bedrock clients, with no client pack and no server resource pack, so a
skinned item would show a missing model. The owners retired the skins: none can be unlocked or put on, and
`tools/wardrobe.py` no longer writes any.

Cosmetics now come from **UltraCosmetics**, a plugin in the store plan (gadgets, pets, particles;
`docs/relaunch/plugin-stack.md`). It needs nothing on the player's side. What players pay for stays cosmetic
only, as Mojang's rules require: the same pass price for everyone, no advantage for sale.

## The counters

The monkey-wardrobe data pack still keeps every retention counter, because the store, staff, the events pack,
the season carry-over and the tools set or read them. They unlock nothing in game any more:

| Score | What it counts | Set by |
| --- | --- | --- |
| `rw.days` | days played (one per UTC day a player is online) | the pack, at their first login of the day |
| `rw.hours` | hours played, this world and earlier ones | the pack (play time plus `rw.playbase`) |
| `rw.months` | months of pass bought in total | the store |
| `rw.tier` | supporter tier: 1 Ember, 2 Banner, 3 Crown, 0 when it lapses | the store |
| `rw.invites` | friends invited who bought a pass | staff, Front Desk's `/referral` |
| `rw.kin` | 1 for both players of a referral | Front Desk's `/referral` |
| `rw.events` | events attended | the events pack (`docs/ADMIN.md`, "Attendance") |
| `rw.hallowtide`, `rw.midwinter`, `rw.midsummer` | came to that holiday's event | staff, at the event |
| `rw.challenges` | weekly challenges done, all seasons together | the challenges |
| `rw.quest` | 1 once the first-week quest is done | the quest |
| `rw.founder` | 1 for everyone who played while `#season` is 1 | the pack |
| `rw.launch` | 1 for 10 minutes online on Season I's launch weekend | the pack (see "The launch weekend") |
| `rw.s2` | 1 for everyone who played while `#season` is 2 | the pack |
| `rw.champion` | 1 for the season champion's roster | staff, after the finale |

Why these counters:

- **Days played, not streaks.** A day counts when a player is online at any point that UTC day. Streaks
  punish a missed weekend and push people to log in out of guilt; a count only goes up.
- **Tenure** (`rw.months`) is what renewing the pass builds; Season Wrapped and the numbers below read it,
  and nobody's spending is shown to other players.
- **Events, holidays, challenges, the quest and the launch weekend** are earned by showing up. No store
  command sets these scores, and `tests/test_wardrobe.py` fails if one does.
- **Founder.** Everyone who plays while `#season` is 1 is a founder for good. If nobody ends season 1, the
  next season's carry sets `#season` to 2 in the new world.
- **Invites** line up with the invite ladder on the site (1, 3 and 5 friends).
- **Referrals.** A member's `/referral` code (Front Desk, the Discord bot) on a new buyer's Tebex purchase sets
  `rw.kin` for both and counts one `rw.invites` for the code's owner. Never sold and no discount. Off until the
  owner turns it on (discord-server, `docs/TEBEX_WEBHOOK.md`, "Referrals").

`/trigger wardrobe` (any value, so old links still work) and `/trigger challenges` now open one menu: days and
hours played, events attended and challenges done, this week's challenges, the weekly server goal, and the
first-week quest's progress for a player taking it. The Guide's "Your progress" button opens it too.

`monkey-day.timer` starts a new day at midnight UTC (`docs/LIVE.md`, step 7), one per UTC date even when it
retries. Without it, nobody's day count moves.

All these scores live in the world, so a new season's world would start them at zero. The season-end
runbook carries them over, hours played included, along with the supporter, title and champion teams
below (`docs/SEASONS.md`, "Ending a season"). The season champion's title is a team like the titles
below, `champion_s1` and so on (`docs/SEASONS.md`, "The season champion").

### Weekly challenges

Three challenges a week, one of each kind: **solo** (mining, fishing, mobs, trading and the like),
**faction** (an event, a village raid, Nether and trial-chamber fights, easier with friends but done by each
player) and **explore** (loot chests and structures). Together they take about one to three hours of normal
play. Players see them with `/trigger challenges` (or `/trigger wardrobe`): each one with the player's
progress, and a hover that says what counts. The first time a player is online in a new week, chat lists
the three. Finishing one plays a sound and says so in chat, and every finished challenge adds one to
`rw.challenges`, the count in all seasons. It used to unlock the challenge skins; since they were retired, a
challenge gives nothing but the count.

A new week starts every **Monday at 12 AM Pacific** (Sunday night, after the Saturday event). The
challenges rotate in a fixed order from a pool in `tools/challenges.py`, so anyone can see what is coming:
`python tools/challenges.py schedule` (`docs/ADMIN.md`, "Weekly challenges", also covers editing the pool).
The launch weekend is week 0 and runs the first of each kind; week 1 starts on Monday 9 November 2026.
`rules/launch` starts the week's progress from zero, and in Season I challenges done before the launch (test
play) don't count; later seasons keep the count they carried.

Only this week's play counts, and nothing can be farmed with an alt or a friend:

- **Blocks** count mined minus the same blocks placed, so placing and breaking again counts nothing, and
  blocks a friend places only move progress between the two of them.
- **Mobs** count only the listed mob types, never players, so the challenges never reward PvP.
- **Loot chests** count when a structure chest's loot is made, which happens once per chest, for whoever
  opens it first.
- **Structures** count once per kind, by setting foot in one.
- **Statistics** are only ones that take real play (fish caught, animals bred, trades, enchanting, raids
  won). Distance travelled and time online are never used: a water stream or a minecart loop would farm them.
- **Events** count any event begun this week (`docs/ADMIN.md`, "Attendance").

None of them needs griefing: structures and loot are out in the world, and nothing asks for another
faction's base.

Minecraft has no calendar, so `monkey-week.timer` tells the server the week every hour
(`deploy/monkey-week.sh`, `docs/LIVE.md`, step 7). The week is a score in the world, so the daily restart
and deploys keep it. Without the timer the week never turns over.

### The first week

A player new this season gets a short quest: five steps that walk them from spawn out into the world
(`tools/quest.py`). Finishing it sets `rw.quest`; it used to give the Pathfinder blade, and since the skins were
retired it gives nothing else. `/trigger quest`, or the Guide's "Your first week",
shows the steps, each with a hover that says what counts:

| Step | Done when | Counted by |
| --- | --- | --- |
| Talk to the Guide at spawn | they right-click the Guide | the Guide sets `rq.guide` (an Easy NPC action) |
| Set your spawn at a bed | they use a bed (there is no /home: a bed is home) | an advancement on vanilla's `any_block_use` |
| Join or start a faction | they are in an Open Parties and Claims party | `st.faction`, from the hourly standings run |
| Claim a chunk | they hold claimed land | `st.claimed`, from the same hourly run |
| Visit an outpost | they stand in an outpost's square | `op.visit`, set by the outposts pack |

Nothing polls for it: each step reads a score something else already keeps, once a second, and only for
players taking part. A step once done stays done. The faction and claim steps can take up to an hour to tick.

Who gets it: a player first seen after the launch with no play carried from an earlier season
(`rw.playbase`) and at most 3 days played. Everyone else is marked as not taking part and never hears of it,
so veterans get no spam. Chat says so once when it starts, and once a day for their first 7 days played while
it is unfinished. **[Hide]** stops the reminders (`/trigger quest` brings it back). The menu
(`/trigger wardrobe`) shows how many steps a player taking part has done.

### The weekly server goal

One target a week that everyone's play counts toward together: chop 4,000 logs, defeat 2,500 mobs, and so
on (`POOL` in `tools/goal.py`; `python tools/goal.py schedule`). It changes with the challenges, every Monday
at 12 AM Pacific, and the launch weekend runs the first. The server's total shows under the week's challenges
(`/trigger challenges` and the weekly hello). Chat tells everyone at half way, and when it is reached everyone
online gets a title, a sound, and fireworks over the standings board at spawn. Nothing is given: the reward is
the moment, so there is nothing to farm. The Sunday recap has a line for it.

It counts vanilla statistics: blocks mined minus the same blocks placed (as the challenges do), or one
statistic such as fish caught. Creative and spectator play never counts, and nothing counts before the
launch. Staff switches: `docs/SEASONS.md`, "Switches".

### The launch weekend

The launch weekend marks who was there at the start (`rw.launch`); it used to give Founder's Circlet, a helm
skin, and now gives only the mark. `function monkey:rules/launch` (rule 23, the launch hour)
opens the window, and it closes by itself at the end of Sunday, Pacific: 31 hours of game time from the
Season I launch, kept to the wall clock by `monkey-week.timer` (game time stops while the server is empty). Every
second a player is online while it is open counts, so players who join hours after the launch hour get it
the same way; at 10 minutes in all it is set. Their seconds online (`rw.launchtime`) are not carried; the
mark (`rw.launch`) is. It works in Season I only. Staff fallbacks are in `docs/ADMIN.md`, "Weekly
challenges".

## Commands for the store and staff

Run these over RCON (`docs/LIVE.md`, "Day to day"). A Tebex package runs the same commands, with
`{username}` for the buyer's name.

| When | Command |
| --- | --- |
| A pass is bought | `whitelist add {username}` |
| The pass ends (cancelled, expired or refunded) | `whitelist remove {username}` |
| A supporter tier is bought (1 Ember, 2 Banner, 3 Crown) | `scoreboard players set {username} rw.tier 2` |
| The same purchase: chat name color | `team join tier_banner {username}` (or `tier_ember`, `tier_crown`) |
| It expires or is refunded | `scoreboard players set {username} rw.tier 0` and `team leave {username}` |
| A Banner or Crown player picks a title, or earns Herald (staff) | see "Titles" below |
| A Crown player names a landmark (staff, once a season) | see "Crown landmarks" below |
| A monthly pass renews | `scoreboard players add {username} rw.months 1` |
| A 2-month pass is bought, or renews | `scoreboard players add {username} rw.months 2` |
| A 2-month pass is refunded or charged back | `scoreboard players remove {username} rw.months 2` |
| A friend they invited buys a pass (staff) | `scoreboard players add NAME rw.invites 1` |
| A referral (Front Desk posts these in the mod channel, or sends them itself) | `scoreboard players set BUYER rw.kin 1`, `scoreboard players set NAME rw.kin 1`, `scoreboard players add NAME rw.invites 1` |
| That purchase is refunded or charged back (only if staff decide to) | `scoreboard players remove NAME rw.invites 1`, `scoreboard players reset BUYER rw.kin` (the referrer keeps theirs) |
| Season 1 ends (once) | `scoreboard players set #season rw.day 2` |

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

### Crown landmarks

Each season, every Crown supporter may name one landmark in the new world: a peak, a lake, an island, a
road or a ruin, but never a faction's base or anything inside someone's territory. Staff put the name on a
sign there and list the season's named landmarks in the Discord. The name has to pass the chat rules, and it
stays for the season even if the tier lapses. A name is all it is: no claim, no protection, no warp. Crown
used to include a vote on next season's mods and events; that went before the store opened, because a paid
say in gameplay isn't cosmetic. Every pass holder votes on the season's twist (docs/SEASONS.md).

## What else keeps people playing

- **The first hour.** Most players who leave do so on day one. Greet new names in chat and in
  Discord, give them a faction to join, and point them at `/trigger quest` and `/trigger challenges`.
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

Tebex can also send a webhook when a buyer cancels (`recurring-payment.cancellation.requested`). Front Desk
receives it and posts each new Ending pass (the player, the package, the end date and the reason) in the staff
channel, so nobody has to check (gr8monk3ys/discord-server, `docs/TEBEX_WEBHOOK.md`). It is off until the
owner exposes the endpoint over HTTPS, adds it in the Tebex panel and puts its secret in the bot's
`server/.env`; until then, check Recurring Payments by hand as above.

## Reading the numbers

```sh
python3 /srv/monkey/repo/tools/retention.py /srv/monkey/MonkeySMP-Server/server/logs
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
python3 /srv/monkey/repo/tools/funnel.py ~/payments.csv /srv/monkey/MonkeySMP-Server/server/logs --log-tz America/Los_Angeles
```

Export the payments from Tebex (creator panel, Payments, Export as CSV) and copy the file to the VPS.
The tool matches each buyer to the server logs by name, and by UUID after a name change, and follows
them through five steps: the purchase, their first join, 30 minutes played, coming back a week after
that first join (D7), and the pass renewed. It prints:

- **Month-2 renewal**, the headline: of the monthly passes whose first month is over, the share that
  paid for a second. The budget below runs on this number. Passes whose month isn't over yet are counted
  as "not due yet", not as lost.
- The same for 2-month passes, once their two months are up.
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

Tebex takes a 5% platform fee and card processing about 2.49% + $0.30 of each payment. After both, the $5
monthly pass brings in about $4.33 and the $8 two-month pass about $7.10, or $3.55 a month. The server
costs about $50 a month (the $45 VPS in docs/LIVE.md, plus off-site backups and the fallback tunnel), so it
breaks even at 12 paying players on monthly passes, or 15 on two-month passes. The table below assumes
monthly passes.

Two monthly passes cost $10, so the two-month pass is 20% cheaper. Mojang's rule is that access
costs the same for everyone, which the official server list reads as payment options "equal in value, or
close to". The first prices turned down 20% off ($12 for 3 months) for stretching that reading and earning
less than monthly passes. The owner chose $8 for 2 months on 4 November 2026, before the first sale
(docs/adr/0008-pass-prices-settled-before-the-first-sale.md). The risk that a list reads this as a second price was
flagged to the owner that day, and the price stood. Since 7 November 2026 the 2-month pass is a subscription too (every 2 months), so
Tebex can't change its price for passes already sold: a new price reaches new buyers only. The monthly pass's $5 has to
hold for the same reason.

A creator code (the site's /creators page) pays its creator 20% of a two-month pass, and Tebex takes 1% more on
payments made with a code, which leaves about $5.42 ($2.71 a month). Codes are for finding players, not
for paying the server.

| Monthly pass churn | Months a payer stays | Lifetime value | New payers a month to hold 30 |
| --- | --- | --- | --- |
| 25% | 4 | $17.32 | 7.5 |
| 15% | 6.7 | $28.87 | 4.5 |
| 10% | 10 | $43.30 | 3 |

Cutting churn from 25% to 10% is worth as much as more than doubling the new players you find each
month. That is why the counters reward days played and tenure, not purchases.
