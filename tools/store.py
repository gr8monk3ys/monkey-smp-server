"""The relaunch store: every rank, season-pass reward and one-off cosmetic, and the configs that grant them.

    python tools/store.py            write the generated files below (--check: only compare, exit 1 if stale)
    python tools/store.py luckperms  print the LuckPerms commands that create the rank groups (paste in the console,
                                     or send them with tools/rcon.py)

The tables here are the one source of truth; edit them, never the generated files:
  package/monkey/defaults/plugins/UltraCosmetics/config.yml  pets, particle, death and projectile effects (only)
  package/monkey/defaults/plugins/DeluxeTags/config.yml      the chat tags and the /tags picker
  docs/relaunch/store-packages.md                           every Tebex package: price, commands, LuckPerms setup

Everything sold is cosmetic (docs/relaunch/store.md, "Mojang's rules"). `problems()` is the guard: it fails
tests/test_store.py if a package grants anything outside COSMETIC_NODES, sells a never-sold item, or enables a
gameplay category in UltraCosmetics. Tebex runs the commands with {username}; Bedrock players' names carry
Floodgate's prefix, which is why LuckPerms needs `allow-invalid-usernames: true` (the platform's LuckPerms config).
"""
import argparse
import sys
from pathlib import Path

from repo import REPO, Repo

# ---------------------------------------------------------------- what may be granted

# Permission prefixes a package may grant. Anything else (homes, kits, fly, money, keys, /nick, /ec...) fails.
COSMETIC_NODES = ("ultracosmetics.pets.", "ultracosmetics.particleeffects.", "ultracosmetics.deatheffects.",
                  "ultracosmetics.projectileeffects.", "deluxetags.tag.", "lpc.chatcolor", "monkey.pass.")
# UltraCosmetics categories. Only these are on: the rest move players (gadgets, mounts, morphs), sit in an armor
# slot with an armor bonus by default (hats, emotes, suits: UC's Attribute-Bonus gives +2 armor), or are a random box.
UC_ON = {"Pets": "pets", "Particle-Effects": "particleeffects", "Death-Effects": "deatheffects",
         "Projectile-Effects": "projectileeffects"}
UC_OFF = ("Gadgets", "Mounts", "Morphs", "Hats", "Suits", "Emotes")
# Every cosmetic UltraCosmetics (3.17) has in the four categories that are on, by its config name. A name not here
# is a typo or a cosmetic UC dropped, and fails problems(). Anything here that no table assigns is switched off, so
# the menu shows only what can be had.
UC_KNOWN = {
    "Pets": [
        "Armadillo", "Piggy", "EasterBunny", "Cow", "Mooshroom", "Dog", "Chick", "ChristmasElf", "IronGolem", "Snowman",
        "Villager", "Bat", "Sheep", "Wither", "Slime", "Silverfish", "Blaze", "Creeper", "Enderman", "Skeleton",
        "Zombie", "CaveSpider", "Spider", "Endermite", "Guardian", "MagmaCube", "Witch", "Horse", "Sniffer", "Frog",
        "Warden", "Allay", "Tadpole", "Goat", "Axolotl", "Piglin", "Strider", "Hoglin", "PiglinBrute", "Zoglin",
        "ZombifiedPiglin", "Bee", "Panda", "Fox", "Kitty", "Ocelot", "WanderingTrader", "Pillager", "Ravager", "Cod",
        "Pufferfish", "Salmon", "TropicalFish", "Turtle", "Dolphin", "Drowned", "Parrot", "Illusioner", "Llama", "Vex",
        "Evoker", "Vindicator", "Donkey", "Mule", "SkeletonHorse", "ZombieHorse", "ElderGuardian", "WitherSkeleton",
        "ZombieVillager", "Husk", "Stray", "PolarBear", "Shulker", "Pumpling"
    ],
    "Particle-Effects": [
        "SnowCloud", "BloodHelix", "FrostLord", "FlameRings", "GreenSparks", "FrozenWalk", "Music", "Enchanted",
        "Inferno", "AngelWings", "RainbowWings", "SuperHero", "SantaHat", "EnderAura", "FlameFairy", "RainCloud",
        "CrushedCandyCane", "InLove", "MagicalRods", "FireWaves", "CursedHalo", "VolcanicHalo", "CursedFootprints",
        "SpringFootprints", "ShadowFootprints", "Notes", "Hearts", "EnderFootprints", "ArcaneFlame", "DivineHalo",
        "SnowFootprints", "SuperVillain", "CherryFairy"
    ],
    "Death-Effects": [
        "Explosion", "Firework", "Lightning", "PuffOfSmoke", "DragonBreath", "Flames", "ItemExplode"
    ],
    "Projectile-Effects": [
        "Rainbow", "Christmas", "RedstoneHelix", "FlameHelix", "CursedHelix", "SoulFireHelix", "Spark", "Redstone",
        "Flame", "Water", "Witch", "Emerald", "Note", "Love", "Lava", "Snow", "Slime", "Crit", "MagicCrit", "Explosion",
        "Cloud", "Smoke", "Portal", "DragonBreath", "SquidInk", "SoulFireFlame", "Snowflake", "GlowSquid",
        "GlowSquidInk", "Scrape", "WaxOff", "WaxOn", "SculkSoul"
    ],
}
# Particle effects shaped like a cape on the player's back: Mojang's rules forbid selling anything that "attempts to
# visually act like the feature of a Minecraft player cape", so they are switched off, not just unsold.
CAPE_LIKE = {"Particle-Effects": ["SuperHero", "SuperVillain"]}
# Holiday cosmetics: given free at that holiday's event (docs/SEASONS.md, "Holidays"), never sold.
HOLIDAY = {"Pets": ["Pumpling", "EasterBunny", "ChristmasElf"],
           "Particle-Effects": ["SantaHat", "CrushedCandyCane", "SpringFootprints"],
           "Projectile-Effects": ["Christmas"]}

# ---------------------------------------------------------------- ranks

# Each rank adds to the one below it (LuckPerms parent). Prefixes are MiniMessage (LPC reads only MiniMessage);
# Geyser shows Bedrock players the nearest of the 16 classic colours.
RANKS = [
    dict(id="ember", name="Ember", weight=100, color="#ff8a3d", monthly=4.99, lifetime=24.99,
         cosmetics={"Pets": ["Piggy", "Chick", "Kitty"],
                    "Particle-Effects": ["Notes", "Hearts", "GreenSparks"],
                    "Projectile-Effects": ["Rainbow", "Love"]},
         tags=["banana", "vine", "jungle"], chatcolor=True),
    dict(id="banner", name="Banner", weight=200, color="#4f7cff", monthly=9.99, lifetime=49.99,
         cosmetics={"Pets": ["Dog", "Fox", "Bee", "Axolotl", "Frog", "Panda", "Sheep", "Cow"],
                    "Particle-Effects": ["Music", "Enchanted", "InLove", "FlameRings", "SnowFootprints", "RainCloud"],
                    "Death-Effects": ["PuffOfSmoke", "Flames", "Firework"],
                    "Projectile-Effects": ["Flame", "Water", "Note", "Snow", "Crit"]},
         tags=["primate", "canopy", "troop", "trader", "raider"]),
    dict(id="crown", name="Crown", weight=300, color="#f1c232", monthly=19.99, lifetime=99.99,
         cosmetics={"Pets": ["Parrot", "Dolphin", "Turtle", "Goat", "Sniffer", "Allay", "Armadillo", "Llama",
                             "PolarBear", "Ocelot"],
                    "Particle-Effects": ["FrostLord", "Inferno", "EnderAura", "DivineHalo", "CursedHalo",
                                         "MagicalRods", "AngelWings"],
                    "Death-Effects": ["Lightning", "DragonBreath"],
                    "Projectile-Effects": ["RedstoneHelix", "FlameHelix", "Spark", "Redstone", "Witch", "Emerald",
                                           "Lava", "Slime", "MagicCrit", "Portal", "DragonBreath", "SoulFireFlame",
                                           "Snowflake", "GlowSquidInk", "WaxOn"]},
         tags=["silverback", "alpha", "legend", "royal"]),
]

# ---------------------------------------------------------------- one-off cosmetics and bundles

PRICES = {"Pets": 3.99, "Particle-Effects": 2.99, "Death-Effects": 2.99, "tag": 1.49}
SHOP = {"Pets": ["Mooshroom", "Snowman", "Villager", "Bat", "Slime", "MagmaCube", "Strider",
                 "Horse", "Donkey", "Mule", "Piglin", "Shulker", "Pufferfish", "TropicalFish", "Blaze", "Creeper",
                 "Enderman", "Skeleton", "Zombie", "Spider", "Salmon", "Husk", "Stray"],
        "Particle-Effects": ["FlameFairy", "CherryFairy", "FireWaves", "FrozenWalk", "SnowCloud", "ShadowFootprints",
                             "EnderFootprints", "CursedFootprints"],
        "Death-Effects": ["Explosion", "ItemExplode"]}
SHOP_TAGS = ["heartstealer", "bounty", "merchant", "builder", "miner", "nightowl", "nomad", "pirate", "frostbite",
             "inferno", "voidwalker", "diver"]
BUNDLE_PRICE = 7.99
BUNDLES = [
    dict(id="frost", name="Frost Bundle", items={"Pets": ["Snowman"], "Particle-Effects": ["FrozenWalk", "SnowCloud"]},
         tags=["frostbite"]),
    dict(id="inferno", name="Inferno Bundle", items={"Pets": ["Blaze", "MagmaCube"], "Particle-Effects": ["FireWaves"],
                                                     "Death-Effects": ["Explosion"]}, tags=["inferno"]),
    dict(id="void", name="Void Bundle",
         items={"Pets": ["Enderman", "Shulker"], "Particle-Effects": ["EnderFootprints"]}, tags=["voidwalker"]),
    dict(id="ocean", name="Ocean Bundle", items={"Pets": ["TropicalFish", "Pufferfish", "Salmon"]}, tags=["diver"]),
]

# ---------------------------------------------------------------- the season pass

SEASON = 1
PASS_PRICE = 7.99
STARTER_PRICE = 10.99   # the pass + 30 days of Ember ($12.98 apart)
PASS_NODE = f"monkey.pass.s{SEASON}.premium"   # the pass plugin's premium track asks for this permission
# Pass XP comes from play the server already counts (docs/RETENTION.md), never from money or PvP kills.
PASS_XP = {"weekly challenge done": 100, "day played": 20, "event attended": 50}
XP_PER_TIER = 80   # 2,400 XP for all 30 tiers (store.md, "The Monkey Pass")
# Free track: everyone, a reward every third tier. Premium track: a reward every tier. Every reward is permanent.
FREE_TRACK = {3: ("tag", "s1"), 6: ("Pets", "Cod"), 9: ("tag", "climber"), 12: ("Projectile-Effects", "Smoke"),
              15: ("tag", "s1_survivor"), 18: ("Pets", "Tadpole"), 21: ("Projectile-Effects", "Cloud"),
              24: ("tag", "s1_veteran"), 27: ("tag", "relentless"), 30: ("tag", "s1_finisher")}
PREMIUM_TRACK = {
    1: ("tag", "s1_pass"), 2: ("Projectile-Effects", "SculkSoul"), 3: ("Pets", "Silverfish"), 4: ("tag", "howler"),
    5: ("Particle-Effects", "ArcaneFlame"), 6: ("Pets", "Endermite"), 7: ("tag", "night_raider"),
    8: ("Projectile-Effects", "SoulFireHelix"), 9: ("Pets", "Vex"), 10: ("tag", "monkey_business"),
    11: ("Projectile-Effects", "CursedHelix"), 12: ("Pets", "Hoglin"), 13: ("tag", "jungle_king"),
    14: ("Particle-Effects", "VolcanicHalo"), 15: ("Pets", "Evoker"), 16: ("tag", "apex"),
    17: ("Projectile-Effects", "SquidInk"), 18: ("Pets", "Illusioner"), 19: ("tag", "untouchable"),
    20: ("Particle-Effects", "BloodHelix"), 21: ("Pets", "Zoglin"), 22: ("tag", "chaos"),
    23: ("Projectile-Effects", "Scrape"), 24: ("Pets", "Witch"), 25: ("tag", "showstopper"),
    26: ("Projectile-Effects", "GlowSquid"), 27: ("Pets", "WitherSkeleton"), 28: ("tag", "unstoppable"),
    29: ("Particle-Effects", "RainbowWings"), 30: ("tag", "s1_crowned"),
}

# ---------------------------------------------------------------- tags

# id -> MiniMessage text. Rank tags take the rank's colour.
TAG_TEXT = {
    "banana": "Banana", "vine": "Vine", "jungle": "Jungle", "primate": "Primate", "canopy": "Canopy",
    "troop": "Troop", "trader": "Trader", "raider": "Raider", "silverback": "Silverback", "alpha": "Alpha",
    "legend": "Legend", "royal": "Royal",
    "heartstealer": "<red>Heartstealer", "bounty": "<gold>Bounty Hunter", "merchant": "<green>Merchant",
    "builder": "<aqua>Builder", "miner": "<gray>Miner", "nightowl": "<dark_purple>Night Owl",
    "nomad": "<yellow>Nomad", "pirate": "<dark_red>Pirate", "frostbite": "<aqua>Frostbite",
    "inferno": "<gold>Inferno", "voidwalker": "<dark_purple>Voidwalker", "diver": "<blue>Deep Diver",
    "s1": "<green>S1", "climber": "<green>Climber", "s1_survivor": "<green>S1 Survivor",
    "s1_veteran": "<green>S1 Veteran", "relentless": "<green>Relentless", "s1_finisher": "<green>S1 Finisher",
    "s1_pass": "<light_purple>S1 Pass", "howler": "<light_purple>Howler", "night_raider": "<light_purple>Night Raider",
    "monkey_business": "<light_purple>Monkey Business", "jungle_king": "<light_purple>Jungle King",
    "apex": "<light_purple>Apex", "untouchable": "<light_purple>Untouchable", "chaos": "<light_purple>Chaos",
    "showstopper": "<light_purple>Showstopper", "unstoppable": "<light_purple>Unstoppable",
    "s1_crowned": "<gradient:#f1c232:#ff8a3d>S1 Crowned</gradient>",
    # Never sold (EARNED): Season I history and the community goal.
    "founder": "<gradient:#b9a3e8:#ff6fb1>Founder</gradient>", "s1_supporter": "<gold>Season I Supporter",
    "goal_getter": "<yellow>Goal Getter",
}
# Earned only: by playing Season I, by having supported it, or for everyone when a community goal is met. No package
# may grant these (tests/test_store.py).
EARNED_TAGS = ("founder", "s1_supporter", "goal_getter")


# ---------------------------------------------------------------- commands

def node(category: str, name: str) -> str:
    """The permission that unlocks one cosmetic; tags are DeluxeTags', the rest UltraCosmetics'."""
    if category == "tag":
        return f"deluxetags.tag.{name}"
    return f"ultracosmetics.{UC_ON[category]}.{name.lower()}"


def rank_nodes(rank: dict) -> list[str]:
    nodes = [node(c, n) for c, names in rank["cosmetics"].items() for n in names]
    nodes += [node("tag", t) for t in rank["tags"]]
    return nodes + (["lpc.chatcolor"] if rank.get("chatcolor") else [])


def luckperms_commands() -> list[str]:
    """Create the rank groups. Safe to run again: LuckPerms sets what is already set."""
    out = []
    parent = None
    for r in RANKS:
        g = r["id"]
        out += [f"lp creategroup {g}", f"lp group {g} setweight {r['weight']}",
                f"lp group {g} setdisplayname {r['name']}",
                f'lp group {g} meta setprefix {r["weight"]} "<{r["color"]}>[{r["name"]}]</{r["color"]}> "']
        if parent:
            out.append(f"lp group {g} parent add {parent}")
        out += [f"lp group {g} permission set {n} true" for n in rank_nodes(r)]
        parent = g
    out += ["lp group default permission set deluxetags.gui true",
            # Earned, never sold: every Season I player, and everyone who paid in Season I (store.md, "Season I").
            "lp creategroup founder", "lp group founder permission set deluxetags.tag.founder true",
            "lp creategroup s1_supporter", "lp group s1_supporter permission set deluxetags.tag.s1_supporter true"]
    return out


def items_commands(items: dict, tags: list[str], user="{username}", unset=False) -> list[str]:
    verb = "unset" if unset else "set"
    nodes = [node(c, n) for c, names in items.items() for n in names] + [node("tag", t) for t in tags]
    return [f"lp user {user} permission {verb} {n}" + ("" if unset else " true") for n in nodes]


def packages() -> list[dict]:
    """Every Tebex package: name, category, price, how it is charged, and its commands by event."""
    out = []
    for r in RANKS:
        g = r["id"]
        out.append(dict(category="Ranks", name=f"{r['name']} (monthly)", price=r["monthly"],
                        charge="Both: a monthly subscription, or one-time with Remove After 30 days",
                        initial=[f"lp user {{username}} parent addtemp {g} 32d replace"],
                        renewal=[f"lp user {{username}} parent addtemp {g} 32d replace"],
                        expiry=[f"lp user {{username}} parent removetemp {g}"],
                        refund=[f"lp user {{username}} parent removetemp {g}"]))
        out.append(dict(category="Ranks", name=f"{r['name']} (lifetime)", price=r["lifetime"], charge="One-time",
                        initial=[f"lp user {{username}} parent add {g}"], renewal=[], expiry=[],
                        refund=[f"lp user {{username}} parent remove {g}"]))
    # Tebex has no tiered packages for Minecraft stores, so moving up a lifetime rank is its own package that needs the
    # one below (Tebex: the package's "Required packages"). The price is the difference.
    for low, high in zip(RANKS, RANKS[1:], strict=False):
        out.append(dict(category="Ranks", name=f"Upgrade: {low['name']} to {high['name']} (lifetime)",
                        price=round(high["lifetime"] - low["lifetime"], 2),
                        charge=f"One-time; requires {low['name']} (lifetime)",
                        initial=[f"lp user {{username}} parent add {high['id']}"], renewal=[], expiry=[],
                        refund=[f"lp user {{username}} parent remove {high['id']}"]))
    out.append(dict(category="Season pass", name=f"Monkey Pass, Season {SEASON}", price=PASS_PRICE,
                    charge="One-time (the season's premium track; its rewards stay for good)",
                    initial=[f"lp user {{username}} permission set {PASS_NODE} true"], renewal=[], expiry=[],
                    refund=[f"lp user {{username}} permission unset {PASS_NODE}"]))
    out.append(dict(category="Season pass", name=f"Season {SEASON} Starter (pass + 30 days of Ember)",
                    price=STARTER_PRICE, charge="One-time with Remove After 30 days",
                    initial=[f"lp user {{username}} permission set {PASS_NODE} true",
                             "lp user {username} parent addtemp ember 32d accumulate"], renewal=[],
                    expiry=["lp user {username} parent removetemp ember"],
                    refund=[f"lp user {{username}} permission unset {PASS_NODE}",
                            "lp user {username} parent removetemp ember"]))
    for b in BUNDLES:
        out.append(dict(category="Bundles", name=b["name"], price=BUNDLE_PRICE, charge="One-time",
                        initial=items_commands(b["items"], b["tags"]), renewal=[], expiry=[],
                        refund=items_commands(b["items"], b["tags"], unset=True)))
    labels = {"Pets": "Pet", "Particle-Effects": "Particle effect", "Death-Effects": "Death effect"}
    for cat, names in SHOP.items():
        for n in names:
            out.append(dict(category=labels[cat] + "s", name=f"{labels[cat]}: {n}", price=PRICES[cat],
                            charge="One-time", initial=items_commands({cat: [n]}, []), renewal=[], expiry=[],
                            refund=items_commands({cat: [n]}, [], unset=True)))
    for t in SHOP_TAGS:
        out.append(dict(category="Tags", name=f"Tag: {plain(TAG_TEXT[t])}", price=PRICES["tag"], charge="One-time",
                        initial=items_commands({}, [t]), renewal=[], expiry=[],
                        refund=items_commands({}, [t], unset=True)))
    return out


def pass_reward_commands(category: str, name: str) -> str:
    """What the pass plugin runs when a player reaches a tier ({player} in most pass plugins)."""
    return f"lp user {{player}} permission set {node(category, name)} true"


def plain(mini: str) -> str:
    """A tag's text without MiniMessage tags, for package names."""
    out, skip = [], False
    for ch in mini:
        if ch == "<":
            skip = True
        elif ch == ">":
            skip = False
        elif not skip:
            out.append(ch)
    return "".join(out)


# ---------------------------------------------------------------- the guard

def assigned() -> set[tuple[str, str]]:
    """Every UltraCosmetics cosmetic someone can have: a rank's, a one-off, a pass reward or a holiday gift."""
    out = {(c, n) for r in RANKS for c, ns in r["cosmetics"].items() for n in ns}
    out |= {(c, n) for c, ns in SHOP.items() for n in ns}
    out |= {(c, n) for c, n in [*FREE_TRACK.values(), *PREMIUM_TRACK.values()] if c != "tag"}
    return out | {(c, n) for c, ns in HOLIDAY.items() for n in ns}


def problems() -> list[str]:
    found = []
    named = assigned() | {(c, n) for b in BUNDLES for c, ns in b["items"].items() for n in ns}
    named |= {(c, n) for c, ns in CAPE_LIKE.items() for n in ns}
    found += [f"{c} {n} isn't an UltraCosmetics cosmetic" for c, n in sorted(named) if n not in UC_KNOWN.get(c, [])]
    sold_tags = {t for r in RANKS for t in r["tags"]} | set(SHOP_TAGS) | {t for b in BUNDLES for t in b["tags"]}
    pass_tags = {n for c, n in [*FREE_TRACK.values(), *PREMIUM_TRACK.values()] if c == "tag"}
    for t in sorted(sold_tags | pass_tags):
        if t not in TAG_TEXT:
            found.append(f"tag {t} has no text in TAG_TEXT")
    for t in EARNED_TAGS:
        if t in sold_tags | pass_tags:
            found.append(f"tag {t} is earned only, but something sells or awards it")
    never = {(c, n) for table in (CAPE_LIKE, HOLIDAY) for c, names in table.items() for n in names}
    never |= {("tag", t) for t in EARNED_TAGS}
    granted = []
    for p in packages():
        for cmd in p["initial"] + p["renewal"]:
            parts = cmd.split()
            if parts[:2] != ["lp", "user"]:
                found.append(f"{p['name']}: runs something other than LuckPerms: {cmd}")
            elif parts[3] == "permission":
                granted.append(parts[5])
                if not parts[5].startswith(COSMETIC_NODES):
                    found.append(f"{p['name']}: grants a non-cosmetic permission: {parts[5]}")
            elif parts[3] == "parent" and parts[5] not in {r["id"] for r in RANKS}:
                found.append(f"{p['name']}: gives a group that isn't a cosmetic rank: {parts[5]}")
    for r in RANKS:
        granted += rank_nodes(r)
        for n in rank_nodes(r):
            if not n.startswith(COSMETIC_NODES):
                found.append(f"rank {r['id']}: grants a non-cosmetic permission: {n}")
    for c, n in [*FREE_TRACK.values(), *PREMIUM_TRACK.values()]:
        granted.append(node(c, n))
    never_nodes = {node(c, n) for c, n in never}
    for n in sorted(set(granted) & never_nodes):
        found.append(f"{n} is never sold (cape-like, holiday or earned), but something grants it")
    pools = [("rank", c, n) for r in RANKS for c, ns in r["cosmetics"].items() for n in ns]
    pools += [("shop", c, n) for c, ns in SHOP.items() for n in ns]
    pools += [("pass", c, n) for c, n in [*FREE_TRACK.values(), *PREMIUM_TRACK.values()] if c != "tag"]
    seen: dict[tuple[str, str], str] = {}
    for pool, c, n in pools:
        if (c, n) in seen and seen[(c, n)] != pool:
            found.append(f"{c} {n} is in both the {seen[(c, n)]} and {pool} pools: each cosmetic is sold one way")
        seen[(c, n)] = pool
    for b in BUNDLES:
        for c, ns in b["items"].items():
            found += [f"{b['name']}: {c} {n} isn't a one-off" for n in ns if n not in SHOP.get(c, [])]
    if sorted(FREE_TRACK) != list(range(3, 31, 3)) or sorted(PREMIUM_TRACK) != list(range(1, 31)):
        found.append("the pass needs a free reward every third tier and a premium reward on each of 30 tiers")
    return found


# ---------------------------------------------------------------- generated files

HEADER = "# Generated by tools/store.py: edit its tables, then run it. Don't edit this file.\n"


def yaml_str(s: str) -> str:
    return "'" + s.replace("'", "''") + "'"


def ultracosmetics_config() -> str:
    lines = [HEADER.rstrip(),
             "# Only the settings Monkey SMP changes. UltraCosmetics fills in every other key from its own defaults.",
             "Categories-Enabled:"]
    lines += [f"  {c}: true" for c in UC_ON] + [f"  {c}: false" for c in UC_OFF]
    lines += ["# No random boxes: keys bought with in-game money are a lottery, and many players are children.",
              "TreasureChests:", "  Enabled: false",
              "# Cosmetics are unlocked by permission only (the store, ranks, the pass), never bought in the menu.",
              "No-Permission:", "  Show-In-Lore: true", "  Allow-Purchase: false",
              "# Armor bonuses would make a cosmetic a gameplay item. The categories that use them are off as well.",
              "Attribute-Bonus:", "  EMOTES:", "    GENERIC_ARMOR: 0", "  HATS:", "    GENERIC_ARMOR: 0",
              "# Pets must not block shots, body-block in fights, mask footsteps or litter the ground.",
              "Pets-Have-Collision: false", "Pets-Are-Silent: true", "Pets-Drop-Items: false",
              "Pets-Can-Ride: false", "Pets-Are-Babies: true", "Airlift-Pets: false",
              "Pets-Rename:", "  Enabled: false",
              "Cosmetics-Affect-Entities: false",
              "# No menu item in the hotbar: a PvP server's hotbar is for fighting. Players open it with /uc menu.",
              "Menu-Item:", "  Enabled: false"]
    have = assigned()
    for section in UC_ON:
        off = [n for n in UC_KNOWN[section] if (section, n) not in have]
        cape = CAPE_LIKE.get(section)
        why = "every one that no rank, one-off, pass tier or holiday gives"
        if cape:
            why = f"{' and '.join(cape)} (cape-shaped, Mojang's cape rule), and {why}"
        elif section == "Pets":
            why += " (big pets that block the view, and mobs that look like a raid)"
        lines.append(f"# Off: {why}.")
        lines.append(f"{section}:")
        for n in off:
            lines += [f"  {n}:", "    Enabled: false"]
    return "\n".join(lines) + "\n"


def deluxetags_config() -> str:
    rank_of = {t: r for r in RANKS for t in r["tags"]}
    lines = [HEADER.rstrip(),
             "# The chat shows the selected tag through PlaceholderAPI: LPC's chat format includes %deluxetags_tag%.",
             "papi_chat: true", "format_chat:", "  enabled: false", "use_minimessage: true", "deluxetags:"]
    for order, (tid, text) in enumerate(TAG_TEXT.items(), start=1):
        r = rank_of.get(tid)
        body = f"<{r['color']}>{text}</{r['color']}>" if r else text
        how = (f"{r['name']} rank" if r else "Earned, never sold" if tid in EARNED_TAGS
               else "Season pass" if tid not in SHOP_TAGS else "Store")
        tag = yaml_str(f"<dark_gray>[</dark_gray>{body}<dark_gray>]</dark_gray> ")
        lines += [f"  {tid}:", f"    order: {order}", f"    tag: {tag}",
                  "    description:", f"    - {yaml_str(how)}", f"    permission: deluxetags.tag.{tid}"]
    return "\n".join(lines) + "\n"


def money(x: float) -> str:
    return f"${x:.2f}"


def packages_doc() -> str:
    lines = ["<!-- Generated by tools/store.py: edit its tables, then run it. Don't edit this file. -->",
             "# Store packages and rank setup", "",
             "The Tebex packages, their prices and the commands each runs, and the LuckPerms commands that create the "
             "ranks. Why each item is priced and allowed is in [store.md](store.md); how to enter them in Tebex is in "
             "[store-tebex-checklist.md](store-tebex-checklist.md).", "",
             "Every command runs with **Require the player to be online** on, so LuckPerms knows the player. "
             "Use `{username}` (never `{uuid}`): the store is a Minecraft Offline/Geyser store so Bedrock names work.",
             "", "## Packages", ""]
    cat = None
    for p in packages():
        if p["category"] != cat:
            cat = p["category"]
            lines += ["", f"### {cat}", "", "| Package | Price | Charged | On purchase | On renewal | On expiry | "
                      "On refund or chargeback |", "| --- | --- | --- | --- | --- | --- | --- |"]
        cell = lambda cmds: "<br>".join(f"`{c}`" for c in cmds) or "-"  # noqa: E731
        lines.append(f"| {p['name']} | {money(p['price'])} | {p['charge']} | {cell(p['initial'])} | "
                     f"{cell(p['renewal'])} | {cell(p['expiry'])} | {cell(p['refund'])} |")
    lines += ["", "## Season pass rewards", "",
              f"Premium track: `{PASS_NODE}`. XP: " + ", ".join(f"{v} per {k}" for k, v in PASS_XP.items()) +
              f"; a tier every {XP_PER_TIER} XP. Each reward runs one command in the pass plugin.", "",
              "| Tier | Free track | Premium track |", "| --- | --- | --- |"]
    for tier in range(1, 31):
        free = FREE_TRACK.get(tier)
        prem = PREMIUM_TRACK[tier]
        show = lambda r: f"{r[0].rstrip('s').replace('-', ' ')}: {plain(TAG_TEXT[r[1]]) if r[0] == 'tag' else r[1]}"  # noqa: E731
        lines.append(f"| {tier} | {show(free) if free else '-'} | {show(prem)} |")
    lines += ["", "Reward command: `" + pass_reward_commands("Pets", "Vex") + "` (the cosmetic's node from the "
              "tables above; `{player}` is the pass plugin's placeholder).", "",
              "## LuckPerms setup", "", "Run once on the new server (console, or `python tools/store.py luckperms`):",
              "", "```", *luckperms_commands(), "```", ""]
    return "\n".join(lines)


def outputs(repo: Repo) -> dict[Path, str]:
    plugins = repo.defaults / "plugins"
    return {plugins / "UltraCosmetics" / "config.yml": ultracosmetics_config(),
            plugins / "DeluxeTags" / "config.yml": deluxetags_config(),
            repo.root / "docs" / "relaunch" / "store-packages.md": packages_doc()}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="The relaunch store's tables and generated configs.")
    ap.add_argument("what", nargs="?", choices=["write", "luckperms"], default="write")
    ap.add_argument("--check", action="store_true", help="only compare the generated files")
    args = ap.parse_args(argv)
    if args.what == "luckperms":
        print("\n".join(luckperms_commands()))
        return 0
    if found := problems():
        print("\n".join(found), file=sys.stderr)
        return 1
    stale = []
    for path, body in outputs(REPO).items():
        current = path.read_text(encoding="utf-8") if path.is_file() else None
        if current == body:
            continue
        if args.check:
            stale.append(path.relative_to(REPO.root).as_posix())
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(body, encoding="utf-8", newline="\n")
    if stale:
        print("stale, run python tools/store.py: " + ", ".join(stale), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
