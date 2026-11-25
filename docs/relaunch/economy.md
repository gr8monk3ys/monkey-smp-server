# The Season 1 economy

How money works on the relaunched Monkey SMP (Season 1 from Saturday 6 Feb 2027): what earns it, what the server
shop and auction house charge, where it leaves the game, how it resets each season, how abuse is caught, and the
numbers to watch. It follows the relaunch plan ("Monkey SMP: growth and money plan"): a free economy survival
server with lifesteal PvP outside safe zones, 8 to 10 week seasons, Java and Bedrock with no client mods, and a
store that sells cosmetics only. **In-game money is never sold for real money**, because money buys gear.

Prices here are a starting point, not a measurement. Nobody publishes earn rates for a server like this, so the
closed beta (about 25 Jan to 3 Feb) and the first two weeks set the real numbers, and the price table is built to be
changed weekly.

## In short

- **One currency, dollars ($), held by EssentialsX Economy** behind VaultUnlocked. Everyone starts at $0.
- **Money comes in by selling to the server** (`/sell`, `/sellall`, the shop). Mining pays best per hour because it
  has no farm; anything a farm can make pays little.
- **The server shop sells building blocks, farm goods, redstone and tools, never anything that wins fights**:
  no totems, pearls, gapples, crystals, anchors, netherite, diamond gear, elytra, shulker boxes or enchanted books.
  Those come from play and change hands on the auction house, so money can't buy combat power at a fixed price.
- **The server sells for at least four times what it pays**, and no craft or smelt turns shop goods into profit.
  `tools/economy.py` checks both on every change.
- **The auction house takes 5% of every sale and 1% to list** (capped at $2,500), five listings each, the same for
  everyone. No paid rank changes any of this.
- **Money leaves through the shop's spread, auction fees, teleport fees and big in-game purchases** such as hearts.
- **Everything resets each season**: balances, listings and shop history. Titles and cosmetics carry over.
- **Watch the money supply weekly**; the table at the end says what to do when it moves.

## Plugins

| Job | Plugin | Why | Status for MC 26.3 |
|---|---|---|---|
| Money and `/pay`, `/bal`, `/baltop` | EssentialsX Economy (in the platform stack) | Already in the stack; logs every change | Dev builds only for 26.3 (platform thread) |
| Economy API | VaultUnlocked (in the platform stack) | What shop and auction plugins talk to | In the stack |
| Server shop, `/sell`, `/sellall`, sell GUI | **EconomyShopGUI** (free) | Free, Bedrock forms through Floodgate, transaction log, supports VaultUnlocked | Changelog lists 26.1, 26.1.2 and 26.2 (Jun 2026); **26.3 not confirmed** |
| Auction house `/ah` | **DonutAuctionHouse** ("Donut Auction", free, Apache-2.0) | DonutSMP-style; sales tax, listing fee, per-player limits, price floors, blacklist, bidding with anti-snipe, shulker previews, daily trade log | Says Paper 1.20.1 to 26.3, tested on 26.1.2, 26.2, 26.3 |

Both new plugins need adding to the platform's pinned list (docs/relaunch/plugin-stack.md). Two cautions:
DonutAuctionHouse is marked "Unlisted by staff" on Modrinth, so pin it from its GitHub release
(github.com/MeherBenSalem/DonutAuction) rather than Modrinth; and if EconomyShopGUI has no 26.3 build by mid
January, the price table still applies to any GUI shop, only the generator's output format would change.

**If EssentialsX has no 26.3 release by about 15 Jan 2027**, the money moves to another VaultUnlocked provider,
because a dev build shouldn't hold everyone's balance:

1. **TheNewEconomy** first. It comes from the same author as VaultUnlocked, so it supports VaultUnlocked natively,
   and it brings its own `/bal`, `/pay` and `/baltop`.
2. **CoinsEngine** second. EconomyShopGUI supports it directly (`COINS_ENGINE`), and it registers with Vault for
   the auction house.

Neither one's 26.3 support has been checked yet, so the platform pin run should check both. Nothing else changes in
this design. Season 1 starts every balance at $0, so there is nothing to migrate. Three things move with the switch:
the EconomyShopGUI sections' `economy:` line (still `VAULTUNLOCKED` for TheNewEconomy, `COINS_ENGINE` for
CoinsEngine), the EssentialsX settings below (starting balance, $0 minimum and the `/pay` minimum move to the new
plugin's config), and `tools/economy.py supply`, which reads EssentialsX's userdata files and would need a reader for
the new plugin's storage. EssentialsX itself can stay for homes and teleports, with its economy left unused.

Considered and not picked: zAuctionHouse (free, but lists only up to 1.21.11), ShopGUIPlus (paid, $14.99, lists
up to 1.21.x), QuickShop or ChestShop player shops (more lag and more grief surface for a first season; the auction
house covers player selling).

## Where money comes from

| Source | How much | Who owns it |
|---|---|---|
| Selling to the server (`/sell`, `/sellall`, shop) | The price table; the main source | This doc |
| Weekly challenges, first-week quest, server goal | Cosmetics today; if they pay money, keep it under one hour of mining a week | Retention packs |
| Voting on server lists | $250 a vote, at most once a day per list | Votes (store/growth thread) |
| Events: drops, outposts, sieges, Server Firsts | Items, not money, where possible: items feed the auction house instead of adding dollars | Season events |
| Kills | No money. A kill steals a heart, nothing else | Rules / lifesteal |

**Starting balance $0.** Every dollar handed out free is multiplied by alt accounts. A new player can sell their
first stack of logs or ores within minutes.

### Rough earn rates (estimates to check in the beta)

| Activity | Per hour |
|---|---|
| Strip mining with Fortune at diamond level: about 20 diamonds plus iron, coal, redstone and lapis | about $2,500 |
| Early game: logs, crops, mob drops by hand | $300 to $800 |
| A good automatic sugar cane farm (about 2,000 cane) | about $1,000, while the owner is online |
| An iron farm (a few hundred ingots) | $1,500 to $2,500 |

Target: an engaged player clears about **$2,000 to $3,000 an hour** mid-season. Big purchases are priced in hours
of that (a heart at about $25,000 is 8 to 12 hours).

## The server shop

Players open `/shop`; eight sections (Blocks, Wood, Farming, Mob Drops, Ores, Food, Utility, Redstone), 158 items.
The whole table is [economy-prices.csv](economy-prices.csv); some anchors:

| Item | Shop sells for | Shop buys for | Why |
|---|---|---|---|
| Diamond | not sold | $100 | The anchor. Mining has no farm |
| Ancient debris / netherite scrap | not sold | $500 / $600 | Rare, slow |
| Iron ingot | not sold | $5 | Iron farms exist |
| Gold ingot | not sold | $3 | Gold farms make nuggets fast |
| Emerald | not sold | $8 | Villager trading makes them |
| Oak log | $8 | $1 | |
| Wheat | $6 | $1 | Hay bale $54 / $9, so crafting changes nothing |
| Sugar cane | $6 | $0.50 | AFK farms |
| Cobblestone, stone, sand | $2 to $4 | not bought | Made without limit |
| Hopper | $60 | not bought | |
| Experience bottle | $40 | not bought | A sink for mending repairs |
| Name tag | $500 | not bought | A sink |

### The price rules

`python tools/economy.py` checks these and writes the EconomyShopGUI files; a test fails if they drift.

1. **A wide spread.** Where the shop both buys and sells an item, its price is at least 4 times what it pays. Buying
   and selling back always loses money, and the gap is a sink.
2. **No combat items for sale.** The list is `NEVER_SOLD` in tools/economy.py.
3. **No craft or smelt arbitrage.** For every recipe in `RECIPES` (blocks of ingots, hay, wool, bone meal, smelting
   raw ores, and so on), buying the inputs and selling the output never pays, and for blocks that craft back,
   buying the block and selling the pieces never pays.
4. **Only what a farm can't make pays well.** Anything produced without limit (cobblestone, stone, sand, basalt,
   ice) is not bought at all. Farmable goods pay cents.

Not covered by the check, so watch them in play: villager trades (a trading hall can turn shop wheat into emeralds;
emeralds are kept at $8 for that reason) and loot from structures.

EconomyShopGUI settings to set after its first start (its config.yml is generated by the plugin, so these are a
checklist rather than a committed file): `economy-provider: VAULTUNLOCKED`, `bedrock-forms: enable: true`,
`transaction-log: true` and `advanced-transaction-log` on, `banned-gamemodes` with CREATIVE and SPECTATOR,
`allow-illegal-stacks: false`, `allow-unsafe-enchants: false`, `drop-remaining-items-on-ground: false` (the plugin's
own docs call it a crash risk), and the `sellall` and `sellgui` commands on. On first start, check that the plugin
did not add its own default sections (enchanting or potions, for example) next to ours; delete any it did.

## The auction house

`/ah` to browse, `/ah sell <price>` to list what's in your hand, `/ah search <text>`, `/ah collect` for items
bought or returned. Config: package/monkey/defaults/plugins/DonutAuctionHouse/config.yml.

| Setting | Value | Why |
|---|---|---|
| Sales tax | 5% of the sale, removed from the game | The main sink once the market is busy. Guides suggest 5 to 10% (vendor guides, opinion) |
| Listing fee | 1%, capped at $2,500, not refunded | Makes relisting spam and price-probing cost something |
| Listings per player | 5, the same for everyone | Keeps page 1 readable; no paid extra slots |
| Listing lengths | 12, 24, 48 or 72 hours (48 by default) | Stale cheap stock clears in days, not a week |
| Lowest price | $10 a listing; diamond at least $100, diamond block $900, scrap $600, debris $500 | Stops $1 "sales" that move money between alts, and stops buying under the shop's own price to resell it |
| Bidding | On for everyone, 5% minimum raise, 30-second anti-snipe | Rare items find their price |
| Never listable | Spawners, command and structure blocks, barriers, knowledge books | |
| Creative and spectator | Can't list | Creative items never reach the market |
| Trade log | On, kept all season | Dupe hunts start here |

The plugin supports cheaper tax and more listings by permission (`donutauction.tax.*`, `donutauction.limit.*`,
`donutauction.slots.*`). **Never give those to a paid rank**: on a PvP economy server they're an advantage bought
with real money, which Mojang's rules and the relaunch plan both rule out. Staff only get `donutauction.admin`.

**Player-to-player `/pay`** stays on, with a $1 minimum and every payment in EssentialsX's economy log. It carries
no tax, so trades between friends stay simple; the auction house's floors stop most laundering, and the log catches
the rest.

## Where money goes

Guides suggest that about 50 to 70 cents of every dollar earned should leave again (a rule of thumb from a host's
guide, not data). The sinks:

| Sink | Size | Owner |
|---|---|---|
| The shop's spread: every block, tool and redstone part bought | Grows with building; likely the biggest early | This doc |
| Auction house: 5% tax and 1% listing fee | Grows with trade | This doc |
| Teleports: `/tpa` $25, `/home` $10 | Small and steady | Platform (EssentialsX `command-costs`) |
| Buying a heart back with money | About $25,000 a heart (8 to 12 hours of play) | Rules / lifesteal |
| Revival at a mid-season event | A fee, for example $50,000, if the event allows buying back in | Season events |
| Claim blocks bought with money, if HuskClaims' economy hook is used | For example $10 a block past the free amount | Claims |
| Late-season sinks: a finale entry or a season trophy bought in game | Set in week 6 from the money supply | Season events |

Avoided on purpose: a tax on everyone's balance (feels like theft), a death fee as a share of balance (punishes new
players in a PvP game), and repair-for-money commands (would sell combat durability at a fixed price).

## Bedrock players

Phone and console players join through Geyser and Floodgate, so every money action has to work without a mouse,
right-click or tab completion. What Geyser itself says it can't do: tell left from right clicks in inventories,
tab-complete or see the chat typing menu, or handle some command arguments outside Brigadier (GeyserMC, current
limitations).

- **The shop** uses EconomyShopGUI's Bedrock forms (needs Floodgate): Bedrock players get native buttons instead of
  a chest menu with left and right clicks.
- **The auction house** has no Bedrock mode. Bedrock players list and search with commands (`/ah sell 500`,
  `/ah search diamond`), and the beta must check that buying from the browse menu works with a tap. BedrockMenus,
  which turns chest menus into forms, can't handle menus where items are put in and was published in November 2026
  with no reports yet, so it is a fallback, not the plan.
- **Commands are listed in `/help`, the Guide NPC and the site**, because Bedrock has no tab completion.

## Abuse and dupes

DonutSMP's first season ended over an inflated economy and duping (a fan wiki). The defences, in order:

1. **No duping in the first place.** Paper's own exploit fixes stay on, Grim anti-cheat (platform stack), plugins
   kept current, and a pre-launch test of the known shulker, hopper, piston and chunk-reload dupes on the beta.
2. **Logs that can prove it.** EssentialsX economy log (every balance change), EconomyShopGUI transaction log,
   DonutAuctionHouse's daily trade log. A block-logging plugin such as CoreProtect would let staff roll back stolen
   or duped items; it isn't in the platform stack yet (a suggestion for the platform thread).
3. **Alarms.** The weekly money check below, plus `/baltop` at a glance each day: anyone up more than about
   $100,000 in a day, or a player in the top 10 who has played less than a day, gets looked at.
4. **Farm limits.** Low prices on farmable goods, no buying of infinite blocks, Paper's entity and redstone limits
   (platform). If AFK farms still flood the economy, EconomyShopGUI's paid edition adds per-player sell limits and
   dynamic prices that fall as more is sold; that is a purchase for Lorenzo to decide on, not part of this plan.
5. **When a dupe is found:** close the hole, remove the money with `/eco take`, remove duped items, ban by the rules
   page, and post a short public note so honest players see it was dealt with.

## Each season

Seasons are 8 to 10 weeks, and items and money don't carry over. At the reset, with the server stopped:

1. Keep copies of the economy logs, the auction trade logs and the final `supply --json` line (they set next
   season's prices).
2. Delete `plugins/DonutAuctionHouse/auctions.db` (listings, unclaimed items, history).
3. Reset every balance to $0 with EssentialsX (`/eco reset ** 0` should cover offline players too; **check this on
   the beta** and fall back to removing the `money:` line from each `plugins/Essentials/userdata/*.yml`).
4. Review the price table against what moved: items whose auction price ended far above the shop's are underpriced in
   the shop; items nobody bought are overpriced. Change the CSV, run `python tools/economy.py`, ship it with the new
   season.
5. Season titles, cosmetics and Founder items carry over through the wardrobe, not the economy.

## What to watch

Run weekly on a copy of the userdata folder and keep the line:
`python tools/economy.py supply plugins/Essentials/userdata --json`.

| Number | Healthy | If not |
|---|---|---|
| Money supply, week on week | Grows with players early, then flattens by week 4 | Growing more than 25% a week after week 3 with flat players: cut the top sell prices 20% and add a sink |
| Median balance | Rises slowly | Falling while the total rises: a few players hold everything. Look at the top 10 |
| Richest 1% share | Under about 40% | Above 50%: check the top accounts for dupes or alt funnels |
| Auction price basket (diamond, netherite ingot, shulker box, elytra, totem, mending book) | Within about 25% of week 2 | Doubling: inflation. Raise auction tax to 7.5% and cut farm prices |
| Auction volume (sales a day) | Grows with players | Falls while players hold: prices stuck or listings spammed |
| Shop buy vs sell totals (EconomyShopGUI logs) | Sells pay out more than buys take in, by a narrowing margin | Sell payouts more than 3 times buy spending after week 2: the shop is the faucet; cut sell prices |
| Diamonds sold to the shop per player hour | About 20 | Far above: a dupe or an x-ray. Check Grim and the logs |

The money supply is also a good season-end beat for clips: "the economy hit $50M" is a post.

## Settings for other workstreams

For the platform thread's EssentialsX `config.yml`:

```yaml
starting-balance: 0
currency-symbol: '$'
max-money: 1000000000000
min-money: 0               # no debt
minimum-pay-amount: 1
economy-log-enabled: true
economy-log-update-enabled: true
show-zero-baltop: false
command-costs:
  tpa: 25
  tpahere: 25
  home: 10
```

For the store and ranks thread: no rank gets any `donutauction.tax.*`, `donutauction.limit.*`,
`donutauction.slots.*` or `donutauction.fee.exempt` permission, and no EconomyShopGUI sell multiplier. For the
lifesteal thread: a heart costs about $25,000 if hearts can be bought with money, and should be priced in hours of
play as the beta measures them.

## Test on the beta

- Every shop section opens on Java and on a Bedrock phone, and buying and selling work in both.
- `/sellall` and the sell GUI pay the table's prices.
- `/ah sell`, `/ah search`, buying, bidding and `/ah collect` work on Bedrock.
- Tax and listing fee are taken: list a $1,000 item, check $10 is gone, sell it, check the sale pays $950 ($940 after the fee).
- `/eco reset ** 0` reaches offline players.
- The known dupes don't work; the three logs record every test.
- Measure real earn rates for the activities above and adjust the table before launch.

## Sources

Read 25 Nov 2026. Prices and earn rates in this doc are my estimates unless a row says otherwise.

- The relaunch plan, "Monkey SMP: growth and money plan" (rev 30), and its sources on DonutSMP.
- DonutSMP fan wiki, "Making money" (donutsmp-wiki.pages.dev): players start with nothing; auction and order
  flipping. A fan site, unverified.
- MineGuard and Space-Node economy guides (mineguard.pro, space-node.net): starting balances, 5 to 10% auction tax,
  2 to 5% listing fee, 24 to 72 hour listings, sinks of 50 to 70% of inflow, anti-dupe plugins. Both companies sell
  hosting or protection, and their numbers are advice, not data.
- mc-mod.net, "How inflation happens in Minecraft server economies": fixed-price shops and farmable currency as
  causes.
- GeyserMC wiki, current limitations; BedrockMenus on Hangar.
- EconomyShopGUI wiki (wiki.gpplugins.com) and changelog; DonutAuctionHouse's Modrinth page, docs and default
  config; zAuctionHouse 4.0.0.4 on Modrinth; EssentialsX 2.22.0 release notes.
