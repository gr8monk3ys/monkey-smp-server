# Hearts, safe zones and claims

How lifesteal works on the relaunched Monkey SMP, and why. The player rules are in `rules.md`; the settings
are in `package/monkey/defaults/plugins/` (LifeStealZ, PvPManager, GriefPreventionData), which the installer
copies into the server's `plugins/` folder on first install.

## Plugins this adds

| Plugin | Does | Settings |
| --- | --- | --- |
| LifeStealZ 2.21 | Hearts, heart items, elimination and revive beacons | `LifeStealZ/config.yml`, `items.yml` |
| PvPManager | Combat tag, combat-log punishment, newbie protection, safe-zone edges, kill-farm limits | `PvPManager/config.yml` |

GriefPrevention (claims) and WorldGuard (spawn and market) are in the platform's stack; this sets them up.

## Hearts

- Everyone starts with **10 hearts**. The most anyone can have is **20**.
- **A player kill moves one heart** from the victim to the killer. A killer already at 20 gets it as a
  Heart item to keep or give away.
- **Dying to anything else costs nothing**: mobs, falls, lava, the void. Bedrock and phone players lose
  more of those deaths to controls, and a lifesteal server should be about players.
- **One heart per 10 minutes from kills.** Kills inside that time still count but move no heart.
- **Kills between two accounts on the same internet connection move no heart**, and staff are told.
- **Killing the same player a fourth time within half an hour** kicks the killer and alerts staff (rule 14).
- **`/withdrawheart`** turns hearts into Heart items, but only hearts above the starting 10. An alt that never
  won a fight has nothing to give, so alts can't be farmed.
- **Combat logging** (leaving within 20 seconds of a hit) kills you and takes a heart. If the last hit came
  in the 5 seconds before you left, the attacker gets a heart too.

## Heart items

| Item | Where it comes from | Use |
| --- | --- | --- |
| Heart (nether star) | Kills at 20 hearts, `/withdrawheart` | +1 heart, up to 20 |
| Crafted Heart (glowing nether star) | 4 diamond blocks, 4 gold blocks, a totem, a netherite ingot | +1 heart, only while below 15 |
| Revive Beacon | 3 Hearts, a beacon, 4 diamond blocks, obsidian | Brings an eliminated player back with 3 hearts |

Crafting can win back what you lost, but only PvP takes you past 15. A revive costs 3 real hearts, which
someone above 10 has to give up, and gives back 3. Heart items don't burn or despawn, so a heart dropped in
lava isn't lost.

## Elimination and revives

- At **0 hearts you're eliminated**: kicked, and blocked from joining for **24 hours**. Then you're back with
  **3 hearts**, on your own, with no friend needed. A solo player is never out for good, and a day out still
  makes the last heart matter.
- **There is no spectating.** Spectator mode sees through walls, and an eliminated player watching bases
  would hand their friends every base's layout.
- **Faster, with friends:** a friend can **place a Revive Beacon** and pick you. It takes 60 seconds, anyone can
  break the beacon to stop it, and you come back with 3 hearts straight away.
- **Revival Nights:** staff revive everyone who is out (`/revive *`) on set Saturdays (`season-1.md`), so the
  wait ends early for everyone.
- **The finale is the exception:** from its start (`season-1.md`), nobody comes back until the season ends.
- A staff ban is separate: a revive doesn't lift it.
- Claims of anyone away 30 days are removed and their base becomes raidable. An eliminated player is out a day
  at most, so elimination never costs anyone their base.

LifeStealZ has no timer of its own, so the 24-hour return is a small server timer (a follow-up to this PR): every
10 minutes it reads LifeStealZ's player data, notes who is at 0 hearts and since when, and runs
`/revive <player>` once 24 hours have passed. It stops at the finale.

## New players

- **3 hours of newbie protection**, counted in play time: they can't hurt or be hurt by players. They can
  end it early with `/newbie disable`. From week 4 staff raise it to 8 hours for late joiners.
- Combat tags, item cooldowns and kill limits apply from the start.
- **PvP can't be switched off.** Nobody gets `pvpmanager.command.pvp`.

## Combat

- A hit tags both players for **20 seconds**: no teleporting (`/spawn`, `/home`, `/tpa`), no commands except
  messaging, and no opening chests inside a claim.
- A tagged player who walks into spawn or the market **stays hittable and is pushed back out**.
- Cooldowns in combat: ender pearls 10 s, wind charges 2 s, golden apples 15 s, enchanted golden apples 60 s.
- **End crystals, respawn anchors and beds don't damage players.** Bedrock players can't place them as fast,
  and they end fights without one. Totems and maces work as in vanilla.

## Claims and raiding

The line: **claims stop griefing and theft, not fights.**

| | Inside a claim | Outside a claim |
| --- | --- | --- |
| Breaking and placing blocks | Trusted players only | Anyone |
| Chests, furnaces, other containers | Trusted players only | Anyone |
| TNT and creepers | Can't break blocks | Break blocks as in vanilla |
| PvP | On | On |
| Doors and buttons | Anyone, unless the owner uses iron doors | Anyone |

- New players get **2000 claim blocks** (about 45 by 45), plus 150 an hour while active, up to 40000. The
  first chest someone places claims a small area around it automatically.
- Right-click two corners with a **golden shovel** to claim; `/trust`, `/containertrust` and `/accesstrust`
  share it; a stick shows claim borders.
- Claims and players are **not shown on the public map**, so it can't be used to find bases.
- Loot from a kill can be picked up by anyone, as in vanilla.

## Safe zones: spawn and the market

Two WorldGuard regions, made by staff once the new world is generated and spawn is built. Inside them
there's no PvP, no explosions, no fire spread and no claiming (GriefPrevention won't let a player claim
where WorldGuard doesn't let them build). Shops inside the market are the economy's, not set here.

With a WorldEdit selection around each area, in game as an admin:

```
/rg define spawn
/rg flag spawn pvp deny
/rg flag spawn tnt deny
/rg flag spawn creeper-explosion deny
/rg flag spawn other-explosion deny
/rg flag spawn fire-spread deny
/rg flag spawn lava-fire deny
/rg flag spawn enderpearl deny
/rg flag spawn deny-spawn zombie,skeleton,creeper,spider,cave_spider,enderman,witch,phantom,slime
/rg priority spawn 10
```

Then the same for `market`, adding `/rg flag market use allow` and `/rg flag market chest-access allow`
if the market's shops need players to open chests. Keep both regions about 100 blocks across: big enough
to arrive safely, small enough that they aren't a base.
