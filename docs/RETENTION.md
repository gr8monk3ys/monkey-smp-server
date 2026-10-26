# Keeping players: the wardrobe, events and the numbers

Monkey SMP earns its keep from monthly passes, so the number that matters most is how many players
come back. This page covers what rewards staying, the commands the store and staff run, and how to
read retention from the server logs.

## The wardrobe

`/trigger wardrobe` opens a clickable menu of skins for swords and helmets. A skin changes only how the
item looks (its model, and on a helmet the worn look). Damage, armor, durability and enchantments
never change, and `tests/test_wardrobe.py` fails the build if one ever does. This follows Mojang's
rule that what players pay for must be cosmetic, and it keeps the server fair: the same pass price
for everyone, no advantage for sale.

Skins unlock by playing, by staying, by bringing friends, or by supporting:

| Skin | Kind | Unlocks at | Score |
| --- | --- | --- | --- |
| Wayfarer | blade | 3 days played | `rw.days 3` |
| Laurel | helm | 7 days played | `rw.days 7` |
| Emberfang | blade | 10 hours played | `rw.hours 10` |
| Frostbite | blade | 15 days played | `rw.days 15` |
| Starfall | blade | 30 days played | `rw.days 30` |
| Verdant | blade | 1 friend invited | `rw.invites 1` |
| Horned Helm | helm | 3 friends invited | `rw.invites 3` |
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
- **Tenure** (`rw.months`) rewards renewing the pass: the Old Guard and the Wanderer's Hood can't be
  bought, only kept.
- **Founder.** Everyone who plays while `#season` is 1 gets Founder's Edge for good. End season 1 when
  the first wave is in (see below) so that the edge stays rare.
- **Invites** line up with the invite ladder on the site (1, 3 and 5 friends).
- **Supporter tiers** get the flashiest skins, because they pay for the server.

`realms-day.timer` starts a new day at midnight UTC (`docs/LIVE.md`, step 7). Without it, nobody's day
count moves.

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

### Crown landmarks

Each season, every Crown supporter may name one landmark in the new world: a peak, a lake, an island, a
road or a ruin, but never a faction's base or anything inside someone's territory. Staff put the name on a
sign there and list the season's named landmarks in the Discord. The name has to pass the chat rules, and it
stays for the season even if the tier lapses. A name is all it is: no claim, no protection, no warp. Crown
used to include a vote on next season's mods and events; that went before the store opened, because a paid
say in gameplay isn't cosmetic. Every pass holder votes on the season's twist (docs/SEASONS.md).

## What else keeps people playing

- **The first hour.** Most players who leave do so on day one. Greet new names in chat and in
  Discord, give them a faction to join, and point them at `/trigger wardrobe`, where Wayfarer is
  3 days away.
- **A weekly rhythm and seasons.** One event a week in a fixed slot, a big moment every two to three
  weeks, and 12-week seasons with a finale and a fresh world: see `docs/SEASONS.md`.
- **Comebacks.** When someone's pass lapses, a short Discord DM from staff about what's new does more
  than a discount.

## Reading the numbers

```sh
python3 /srv/realms/repo/tools/retention.py /srv/realms/TheRealms-Server/server/logs
```

This reads the joins in the server logs. Nothing leaves the machine. It prints, for each week's new
players, the share who came back at least 1, 7 and 30 days later (D1, D7, D30), plus the number of
different players each week. A cell shows `-` until enough days have passed to judge it.

Worth checking monthly, next to the store's pass renewals:

- **D7 under about 30%**: the first days aren't landing. Work on onboarding before adding content.
- **Different players each week falling** while D7 holds steady: you aren't getting new players. The
  invite ladder and the site matter more than features.
- **Pass churn** (passes not renewed, divided by passes active at the start of the month).

## Churn and the budget

Tebex takes a 5% platform fee and card processing about 2.49% + $0.30 of each payment. After both, the $5
monthly pass brings in about $4.33 and the $14 three-month pass about $12.65, or $4.22 a month. The server
costs about $50 a month (the $45 VPS in docs/LIVE.md, plus off-site backups and the fallback tunnel), so it
breaks even at 12 paying players whichever pass they choose. The table below assumes monthly passes.

Three monthly passes cost $15, so the three-month pass is about 7% cheaper. Mojang's rule is that access
costs the same for everyone, which the official server list reads as payment options "equal in value, or
close to". At $12 (20% off) the three-month pass stretched that reading and earned less than monthly
passes: about $10.80, or $3.60 a month. Tebex can't change the price of a subscription already sold, so
the prices were settled before the first sale (docs/adr/0008-pass-prices-settled-before-the-first-sale.md).

A creator code (site/creators.html) pays its creator 20% of a three-month pass, and Tebex takes 1% more on
payments made with a code, which leaves about $9.70 ($3.24 a month). Codes are for finding players, not
for paying the server.

| Monthly pass churn | Months a payer stays | Lifetime value | New payers a month to hold 30 |
| --- | --- | --- | --- |
| 25% | 4 | $17.32 | 7.5 |
| 15% | 6.7 | $28.87 | 4.5 |
| 10% | 10 | $43.30 | 3 |

Cutting churn from 25% to 10% is worth as much as more than doubling the new players you find each
month. That is why the wardrobe rewards days played and tenure, not purchases.
