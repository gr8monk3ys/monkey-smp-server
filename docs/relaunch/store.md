# The store and ranks (Season 1 relaunch)

What Monkey SMP sells from the relaunch on Sat 6 Feb 2027, what it costs, why each item is allowed, and how players who
paid in Season I are looked after. Everything sold is cosmetic: nothing bought changes combat, hearts, money, land,
travel or queue position. That is Mojang's rule and the plan's ("Monkey SMP: growth and money plan"), and it is the one
thing no comparable lifesteal store we could read does (see "Prices").

- The catalog lives in one table file, [`tools/store.py`](../../tools/store.py). It writes the UltraCosmetics and
  DeluxeTags configs and [store-packages.md](store-packages.md) (every Tebex package with its commands), and
  `tests/test_store.py` fails if anything sold grants a permission outside the cosmetic list.
- Lorenzo sets up Tebex himself from [store-tebex-checklist.md](store-tebex-checklist.md).
- Read on 25 Nov 2026. Prices are in US dollars, before sales tax or VAT, which Tebex adds where it applies.

## The catalog

| What | Price | How it's charged |
| --- | --- | --- |
| **Ember** rank | $4.99 a month, or $24.99 lifetime | Monthly subscription, or one month paid once; lifetime once |
| **Banner** rank (includes Ember) | $9.99 a month, or $49.99 lifetime | as above |
| **Crown** rank (includes Banner) | $19.99 a month, or $99.99 lifetime | as above |
| Lifetime upgrades | $25.00 Ember to Banner, $50.00 Banner to Crown | Once; needs the lower lifetime rank |
| **Monkey Pass**, Season 1 | $7.99 | Once per season; rewards stay for good |
| Season 1 Starter (pass + 30 days of Ember) | $10.99 | Once (saves $1.99) |
| Pet (23 to pick from) | $3.99 each | Once, permanent |
| Particle effect (8) | $2.99 each | Once, permanent |
| Death effect (2) | $2.99 each | Once, permanent |
| Chat tag (12) | $1.49 each | Once, permanent |
| Themed bundle: Frost, Inferno, Void, Ocean | $7.99 each | Once, permanent (2 to 5 items, a tag included) |
| Community goal | (server-wide reward, nothing to buy) | Every $300 of sales in a month |
| Creator codes | (no price) | Creator gets 20% of the first payment |

Today's prices are Ember $3, Banner $7, Crown $15 a month and the Server Pass $5 a month (`docs/LIVE.md`). The relaunch
makes the server free to join, so the pass goes and the ranks carry more.

### What each rank gives

Each rank includes everything below it. All of it is visible only (a name tag, chat colour, a following pet that
can't be hit or block anything, particles, a trail on arrows, an effect where you die).

| | Ember | Banner | Crown |
| --- | --- | --- | --- |
| Chat prefix | orange [Ember] | blue [Banner] | gold [Crown] |
| Chat colour and formatting (`lpc.chatcolor`) | yes | yes | yes |
| Pets | Piggy, Chick, Kitty (3) | + Dog, Fox, Bee, Axolotl, Frog, Panda, Sheep, Cow (11) | + Parrot, Dolphin, Turtle, Goat, Sniffer, Allay, Armadillo, Llama, Polar Bear, Ocelot (21) |
| Particle effects | Notes, Hearts, Green Sparks (3) | + 6 (9) | + 7, with Angel Wings and the halos (16) |
| Death effects | none | Puff of Smoke, Flames, Firework (3) | + Lightning, Dragon Breath (5) |
| Arrow trails | Rainbow, Love (2) | + 5 (7) | + 15 (22) |
| Chat tags | 3 | + 5 (8) | + 4 (12) |
| Wardrobe skin | Lantern blade | Standard blade | Regalia blade + Crown helm |
| Other | Discord role | Discord role | Names one landmark each season (ADR-0008) |

The full lists are in `RANKS` in `tools/store.py` and in [store-packages.md](store-packages.md). The wardrobe skins are
the existing `rw.tier` unlocks; they need the wardrobe ported to the new server (see "For other workstreams").

### The Monkey Pass

- **Free track** for everyone: a reward every third tier (10 rewards: tags, two pets, two trails).
- **Premium track** for $7.99: a reward on every one of 30 tiers (11 tags, 9 pets, 6 trails, 4 particle effects
  including Rainbow Wings at tier 29, and the "S1 Crowned" tag at 30). These pets and effects are sold nowhere else.
- **Pass XP comes only from play**: 100 for a weekly challenge, 20 for each day played, 50 for an event attended; a
  tier every 80 XP. 2,400 XP finishes it: by my estimate about 9 weeks for a player who plays most days, does the
  weekly challenge and comes to the weekly event, so a regular finishes inside an 8 to 10 week season. Nothing sells XP or tier skips, and PvP kills give none (so no one is
  hunted for pass progress).
- **Buying late is fine**: the premium track pays out the tiers already reached.
- Rewards stay after the season. Next season gets a new pass with new rewards.

The pass needs a plugin, which is Lorenzo's call (see "Decisions"). The store grants `monkey.pass.s1.premium`, which
the plugin's premium track must check.

### One-offs and bundles

Permanent, gift-able, and each sold one way only: a pet in the shop is never also a rank or pass reward
(`problems()` checks this). Bundles cost 30% to 50% less than their items bought apart. Projectile trails are not
sold one at a time: they come with ranks and the pass.

### Community goal

Every $300 of store sales in a calendar month, everyone online gets a Goal Night (fireworks over spawn and a
server-wide event) and everyone who joined that month gets the earned "Goal Getter" tag. Mojang allows exactly this:
"you may offer all players server wide rewards if donation goals are met". The $300 level is Lorenzo's to set.

### Creator codes

Kept as ADR-0008 has them: the creator gets 20% of the first payment and the buyer gets no discount. Tebex pays the
creator after its settlement period and charges the store 1% more on those sales. A creator must say on stream or in
the video that they're paid, as Mojang's rules ask ("disclose their relationship with you and follow the guidelines
published by the U.S. Federal Trade Commission").

### Never sold

- Capes, back items, elytra skins, and particle effects shaped like a cape (UltraCosmetics' SuperHero and SuperVillain
  are switched off).
- Random boxes, keys or crates of any kind (UltraCosmetics' treasure chests are off, and the menu can't sell anything).
- Gameplay: hearts, revives, money, items, kits, homes, warps, fly, `/nick`, portable crafting or ender chests, claim
  blocks, auction slots, XP boosts, queue priority or reserved slots, pass tiers.
- UltraCosmetics' gadgets, mounts, morphs, hats, suits and emotes: they move players, hide them, or sit in an armour
  slot (UltraCosmetics even gives hats and emotes +2 armour by default; the config sets it to 0 and turns them off).
- Holiday cosmetics (Pumpling, Easter Bunny, Christmas Elf, Santa Hat and the like): given free at that holiday's event.
- The Founder, Season I Supporter and Goal Getter tags: earned only.

## Mojang's rules, item by item

Sources: [Minecraft Usage Guidelines](https://www.minecraft.net/en-us/usage-guidelines) (no "last updated" date on the
page), the [EULA](https://www.minecraft.net/en-us/eula), and Mojang's notes on the 2023
([article](https://www.minecraft.net/en-us/article/minecraft-eula-and-commercial-usage-guidelines-updates)) and 2020
([article](https://www.minecraft.net/en-us/article/commercial-usage-guidelines-updated)) changes. The EULA lets a
server make money only as the Usage Guidelines allow, and the same guidelines cover Java and Bedrock.

| Item | Rule | Verdict |
| --- | --- | --- |
| Ranks, tags, chat colour, pets, particles, trails, death effects | "Selling cosmetics, except for capes or anything that attempts to visually act like the feature of a Minecraft player cape" | Allowed |
| Particle wings (Angel Wings, Rainbow Wings) | Same rule | **Borderline, low risk.** They are particle shapes, not a worn item, and nothing about wings is in the rules. If Mojang ever reads wings as cape-like, switch both off in `CAPE_LIKE` and give owners a swap. |
| Cape-shaped effects, back items, elytra skins | Same rule | Not sold |
| Monthly subscriptions and lifetime ranks | Nothing in the rules on subscriptions; they are cosmetic sales | Allowed |
| Season pass | Nothing on passes; every reward is cosmetic and XP can't be bought | Allowed |
| Random boxes | "All servers, entitlements, and advertising are suitable for audiences of all ages (for example, gambling…)" | Not sold |
| Community goal | "you may offer all players server wide rewards if donation goals are met" | Allowed |
| Gifting | Not mentioned; it is a cosmetic sale to someone else | Allowed |
| Free to join | "Charging for access to your server, provided that the cost to access the server is the same for everyone" | Not charging at all |
| Store obligations | "You provide any user who gives you real-world currency an online payment and purchase history"; "You provide information to users on all the content and pricing applicable to your server before a person joins, signs up, or signs in"; a contact method ("chat and forum links are not acceptable methods"); the "NOT AN OFFICIAL MINECRAFT [PRODUCT/SERVICE/EVENT/etc.]. NOT APPROVED BY OR ASSOCIATED WITH MOJANG OR MICROSOFT" notice | Tebex gives buyers their payment history. The website must show this catalog and the notice and give an email address (the website workstream). |
| Creator codes | Influencers "disclose their relationship with you and follow the guidelines published by the U.S. Federal Trade Commission" | Allowed with disclosure (in the creator terms) |

Mojang also says it can "decide if the way you are monetizing your server is consistent with our brand", so the rule
of thumb stays: if a player who didn't pay would feel worse off in a fight or on the leaderboard, it isn't sold.

## Bedrock players

- **Paying:** a Bedrock player buys with their Bedrock name. Tebex only accepts those names in a **Minecraft:
  Offline/Geyser** store, and the store type is set when a webstore is made, so the current Java store may need to be
  replaced (the checklist checks). Commands use `{username}`, never `{uuid}`.
- **Names:** Floodgate puts a prefix (`.` by default) before Bedrock names. LuckPerms refuses such names unless its
  config has `allow-invalid-usernames: true` (the platform workstream owns that file).
- **What they see:** prefixes, tags and pets work. Bedrock shows the nearest of the 16 classic colours for the hex
  colours and gradients. Particles mostly come through Geyser; a few shapes may look thinner. The wardrobe skins use the
  Java resource pack, so until Geyser mappings exist they show as the plain item on Bedrock: the store page says
  "Wardrobe skins are Java only for now".
- **Consoles** (Xbox, PlayStation, Switch) can't add a server without a workaround, so console players can buy but may
  not be able to play. The store page shouldn't promise console support.
- **Young players:** many Bedrock players are under 18. Tebex's checkout handles consent and refunds; the store page
  should tell younger players to ask a parent before buying.

## Season I buyers

Season I ends on 23 Jan 2027 and the plan stops pass renewals then.

1. **Every Season I player** gets the permanent Founder tag (LuckPerms group `founder`) and keeps the Founder's Edge
   and Founder's Circlet skins (their `rw` scores carry over with the wardrobe).
2. **Everyone who paid in Season I** (pass or rank) gets the Season I Supporter tag (group `s1_supporter`), never sold.
3. **Server Pass subscribers:** turn off renewals in Tebex before 23 Jan. Anyone with paid days left past 23 Jan gets,
   as Lorenzo chooses, either a refund of those days through Tebex or the same number of days of Ember plus 30 days free.
   The pass itself isn't needed any more because the server is free.
4. **Ember, Banner and Crown subscribers** (at $3, $7, $15): Tebex can't change the price of a subscription already
   sold. If the store stays the same webstore, their packages are kept hidden and re-pointed to the new commands, so
   they keep their old price for as long as they stay subscribed. If a new Offline/Geyser store is needed, their
   subscriptions can't move: cancel them at the end of their paid month and give each the same rank free for that
   month plus 30 days. (No personal coupons: ADR-0008.)
5. Run all of this from the Tebex payments export; `tools/funnel.py` already reads it.

## Prices

Compared on 25 Nov 2026 with the stores I could read (several big lifesteal stores, DonutSMP, Lifesteal.net,
FreshSMP, PvPWars, CubeCraft and InsanityCraft, wouldn't load or need a login):

| Server | Ranks | Monthly membership | Sells gameplay? |
| --- | --- | --- | --- |
| [Pika Network](https://store.pika-network.net) (lifesteal) | $11 to $274 once | Pika Plus $8 / $25 / $82 | Yes: gold, keys, queue priority |
| Jartex Network | same as Pika | same as Pika | Yes |
| [ManaCube](https://store.manacube.com) | VIP $9.99 to ELITE $179.99 once | Mana+ $19.99 / $59.99 / $119.99 per 30 days | Yes: kits, homes, keys. Cosmetic flag bundles $4.50 to $7.50 |
| Hypixel (secondary source, undated) | VIP $6.99 to MVP+ $44.99 once | MVP++ $7.99 | No |
| DonutSMP (fan wiki, secondary) | | Donut+ $5.49 per 30 days | Yes: homes, priority queue |

No public battle-pass price turned up. Monkey SMP's monthly prices sit with Donut+ and Pika Plus at the low end and
below at the top; lifetime ranks cost five months of the monthly price, the low end of Pika and ManaCube's one-time
ranks. Being cosmetic-only is what sets it apart from every one of these, so it goes on the store page.

## Plugins this adds

All go in `package/monkey/defaults/plugins/<name>/` and in the platform's plugin list and pin run:

| Plugin | Licence | What for | 26.3 build? |
| --- | --- | --- | --- |
| Tebex (Modrinth `tebex`) | GPL-3.0 | Runs purchase commands | Not yet (25 Nov); has 26.2 |
| UltraCosmetics | AGPL-3.0 | Pets, particle effects, death effects, arrow trails, `/uc menu` | Not yet; has 26.2 |
| DeluxeTags | MIT | Chat tags and the `/tags` picker | Yes, pinned |
| LPC (Modrinth `lpc-chat`) | MIT | Chat format with prefixes and colours (the platform's pick in place of EssentialsX Chat) | Not yet |
| A season pass plugin | | The Monkey Pass | Lorenzo's decision |

The platform re-runs the pins in mid-January and drops to 26.2 if these still lack 26.3 builds. Nothing here depends on
26.3: the configs and commands are the same on 26.2. UltraCosmetics' config here holds only the settings Monkey SMP
changes; it fills in the rest from its own defaults on first start.

## For other workstreams

- **Platform (LuckPerms and LPC):** `allow-invalid-usernames: true` in LuckPerms' config for Bedrock names; LPC's chat
  format needs `%deluxetags_tag%` before the name (PlaceholderAPI on) and `allow-gradient-tags: true` for the gradient
  tags; staff groups need a weight above 300 so their prefix wins.
- **Wardrobe port:** Tebex used to set `rw.tier`; the new rank packages only set LuckPerms groups. The wardrobe should
  read the rank from LuckPerms (or a rank change should set `rw.tier`) so the Lantern, Standard and Regalia skins keep
  working, and a lapsed monthly rank must not take away a lifetime rank's skin.
- **Website:** show the catalog and prices before anyone joins, the Mojang notice, an email contact, "Wardrobe skins are
  Java only for now", and a line for parents.
- **Season and events:** award `founder` and `s1_supporter` from the Season I records, run Goal Nights, and give the
  holiday cosmetics at their events.

## Decisions for Lorenzo

1. **Lifetime ranks:** sell them ($24.99 / $49.99 / $99.99) or monthly only. They bring money in early but less over a
   long-lived server; most competitors sell one-time ranks.
2. **Season pass plugin:** which to buy (for example BattlePass by advancedplugins, or EcoBattlepass at $15.99), or have
   the pass built into the existing challenge and wardrobe system later.
3. **Tebex store type:** if the current webstore isn't Offline/Geyser, make a new one so Bedrock players can pay.
4. **Season I pass days left after 23 Jan:** refund them, or turn them into Ember days.
5. **Creator codes:** keep "no buyer discount" (ADR-0008), or give buyers 10% off with a code (Mojang allows it).
6. **Community goal:** $300 a month, or another level.
