"""Which files of the client pack a player may untick: `env.client` in client/modrinth.index.json.

The Modrinth App and Prism Launcher list each "optional" file of a .mrpack with a tick box, ticked by
default, so a player on a slow PC can leave out resource packs or visual mods (docs/PLAYERS.md,
"Low-end PC"). Every other file is "required": the mods that add blocks, items, entities or other registry
entries the server sends, the libraries those mods need, and a mod with a mandatory registry data map (Block
Runner: "This server does not support vanilla clients as it has mandatory registry data maps"). Without one of
them Fabric turns the player away at the door ("This server requires ... installed on your client").

A mod goes on the optional list only when it is client-side: it isn't on the server at all, or it is a
client-only mod by its fabric.mod.json, or Modrinth says its client half is optional (the server runs it
either way, like Simple Voice Chat). tests/test_client_env.py checks each entry
against facts recorded from the jars (tests/fixtures/client_mods.json, re-recorded with
tests/fixtures/record_client_mods.py), and that no required mod depends on an optional one. A mod missing
from the list is required, so a new mod is safe until someone sorts it.

snapshot.py writes these values into the index and validate.py checks the index still matches.
"""
import re

OPTIONAL_FOLDERS = ("resourcepacks/", "shaderpacks/")  # textures and shaders: never needed to join

# What each kind of optional mod is for (docs/PLAYERS.md explains them to players).
KINDS = {
    "performance": "makes the game faster or lighter: keep it on a slow PC",
    "visuals": "looks only: animations, particles, smoke and fog",
    "audio": "sound only: voice chat, ambience, echo",
    "map": "the minimap and world map",
    "interface": "HUD, tooltips, menus and controls",
    "library": "needed only by other optional mods, if at all",
    "server": "the server runs it; players need no copy of it",
}

# Modrinth project id -> (slug, kind). A mod not listed here is required.
OPTIONAL_MODS = {
    # performance
    "ONZm0H7Y": ("better-block-entities", "performance"),
    "uXXizFIs": ("ferrite-core", "performance"),
    "5ZwdcRci": ("immediatelyfast", "performance"),
    "gvQqBUqZ": ("lithium", "performance"),
    "AANobbMI": ("sodium", "performance"),
    # visuals
    "zV5r3pPn": ("3dskinlayers", "visuals"),
    "A0W9tMly": ("aitk", "visuals"),
    "kIhxG5zE": ("armor-trim-item-fix", "visuals"),
    "Effrh3ze": ("better-smoke", "visuals"),
    "BdKIyOLe": ("boat-item-view", "visuals"),
    "kcoiKSkz": ("brighter", "visuals"),
    "46n24c6r": ("clear-fog", "visuals"),
    "1IjD5062": ("continuity", "visuals"),
    "7YjclEGc": ("dynamic-lights", "visuals"),
    "zS8uflwP": ("easegui", "visuals"),
    "4I1XuqiY": ("entity-model-features", "visuals"),
    "BVzZfTc1": ("entitytexturefeatures", "visuals"),
    "OSQ8mw2r": ("explosive-enhancement", "visuals"),
    "WhbRG4iK": ("fallingleaves", "visuals"),
    "p19vrgc2": ("fusion-connected-textures", "visuals"),
    "bppzc3HJ": ("maseffects-v2", "visuals"),
    "8aoMKplv": ("punchy-fpa", "visuals"),
    "vgVfk0m2": ("real-arrow-tip", "visuals"),
    "pXo36Na4": ("sb-enchantment-effects", "visuals"),
    "XTAy8Fqs": ("shield-banner-fix", "visuals"),
    "4q8UOK1d": ("subtle-effects", "visuals"),
    "Hf3Qz2H3": ("superresolution", "visuals"),
    "eB5MDILu": ("thirdpersondeath-continued", "visuals"),
    "jExZM2Rj": ("tightfire", "visuals"),
    "W2K5WNdH": ("twod_projectiles", "visuals"),
    "dlNu0RQY": ("wakes", "visuals"),
    "EwYg6C78": ("windy", "visuals"),
    # audio
    "9eGKb6K1": ("simple-voice-chat", "audio"),
    # map
    "kwpTgbCk": ("diorama-map", "map"),
    # interface
    "n6PXGAoM": ("better-stats", "interface"),
    "UIexcMP1": ("borderless-fullscreen", "interface"),
    "lO3s8hjs": ("bridging-mod", "interface"),
    "xUTHly0N": ("centered-crosshair", "interface"),
    "Wb5oqrBJ": ("chat-heads", "interface"),
    "uUn9PlWe": ("cleanf3", "interface"),
    "65UyswbY": ("commandkeys", "interface"),
    "xv94TkTM": ("controlling", "interface"),
    "o1tyE5vJ": ("custom-crosshair-mod", "interface"),
    "h3XWIuzM": ("dark-loading-screen", "interface"),
    "UVtY3ZAC": ("enchantment-descriptions", "interface"),
    "k2ZPuTBm": ("essential", "interface"),
    "DIlqwRFH": ("fpsdisplay", "interface"),
    "Boon8xwi": ("inventory-essentials", "interface"),
    "adriDDJt": ("inventory-item-groups", "interface"),
    "cVNW5lr6": ("item-highlighter", "interface"),
    "u6dRKJwZ": ("jei", "interface"),
    "kB56GtWA": ("just-enough-professions-jep", "interface"),
    "uEfK2CXF": ("just-enough-resources-jer", "interface"),
    "9Pk89J3g": ("justenoughbreeding", "interface"),
    "mOgUt4GM": ("modmenu", "interface"),
    "2VF6JEnL": ("multi-key-bindings", "interface"),
    "JHgf35QL": ("nemos-inventory-sorting", "interface"),
    "TvL1V8O5": ("norecipebook", "interface"),
    "TnOXNf5e": ("peek", "interface"),
    "ZX66K16c": ("pick-up-notifier", "interface"),
    "gvl7lVcV": ("ping-view", "interface"),
    "hvqcuDMT": ("rp-renames", "interface"),
    "kepjj2sy": ("shoulder-surfing-reloaded", "interface"),
    "T9FDHbY5": ("statuseffecttimer", "interface"),
    "9ggA4qiy": ("stepitup", "interface"),
    "wF189hn9": ("ukus-armor-hud", "interface"),
    # library
    "MBAkmtvl": ("balm", "library"),
    "fuuu3xnx": ("searchables", "library"),
    "Eldc1g37": ("tcdcommons", "library"),
    "Y8uFrUil": ("ukulib", "library"),
    # server
    "dzG7pw5M": ("advancements_plus", "server"),
    "9EFaPoo8": ("amethyst-nether", "server"),
    "pcN1B3cK": ("banner-bedsheets", "server"),
    "vz3NiXrd": ("bat-membrane", "server"),
    "UT8WxaW1": ("blaze-attack-animation", "server"),
    "fALzjamp": ("chunky", "server"),
    "Wnxd13zP": ("clumps", "server"),
    "hCf7CjRg": ("colorful-trims", "server"),
    "ua9u8yK9": ("craft-horse-armor", "server"),
    "j6oNCsqx": ("craft-tridents", "server"),
    "rM6o3WUr": ("craftable-bell", "server"),
    "raz4aMjT": ("craftable-chainmail-armor-by-sumbaii999", "server"),
    "VNMEUT3N": ("craftablecobwebs", "server"),
    "FapP9XhG": ("crazy-chambers", "server"),
    "Kd03i2oU": ("enchantment-disabler", "server"),
    "eBvPjIeN": ("fortunate-ancient-debris", "server"),
    "jxeW9Fvw": ("glowing-glow-squids", "server"),
    "ZvQgzPPs": ("grand-capitals", "server"),
    "Dv9hvreZ": ("many-more-banners", "server"),
    "DuUMFIfX": ("mastercutter", "server"),
    "57KDkTen": ("nether-gold-ore-drops-raw-gold", "server"),
    "aKeMRgHX": ("random-mob-sizes-dp", "server"),
    "MDljZreW": ("reach-behind", "server"),
    "Go9Vr0TE": ("reimagined-trims", "server"),
    "E8egdGje": ("revault", "server"),
    "8kLBMwES": ("rotten-flesh-to-leather", "server"),
    "Cw8IlnGM": ("serversleep", "server"),
    "pmzEEeIf": ("silvers_strength-restrictions-season-5", "server"),
    "VmxEUiAL": ("silvers_strength-smp-season-5", "server"),
    "cuJqipOv": ("simple-fast-happy-ghasts", "server"),
    "ofDka6PS": ("spawn-animations-compats", "server"),
    "7F1sQUtH": ("sulfur-cube-expansion", "server"),
    "AihRqJiY": ("tnt-timer", "server"),
    "yxIf0Dct": ("too-cheap", "server"),
    "NzkisNaN": ("unlimited-trading", "server"),
    "T2Z3j2pD": ("warden-with-loot", "server"),
}

# Optional mods that have left the client pack (project id -> slug). They stay optional so the indexes of
# earlier releases (tests/fixtures/manifests) still validate; none may be in the current pack.
RETIRED_OPTIONAL = {
    # 2.8.0: gone from the shared mod folder
    "kzwxhsjp": "accurate-block-placement-reborn",
    "fM515JnW": "ambientsounds",
    "g96Z4WVZ": "badoptimizations",
    "m5T5xmUy": "bettergrassify",
    "rrwQMaWQ": "camera-utils",
    "LQ3K71Q1": "dynamic-fps",
    "NNAgCjsB": "entityculling",
    "nvQzSEkH": "jade",
    "51shyZVL": "moreculling",
    "HJR6V0I2": "more-mobs",
    "MPCX6s5C": "not-enough-animations",
    "jzoouHnf": "player-death-corpses",
    "Bh37bMuy": "reeses-sodium-options",
    "PtjYWJkn": "sodium-extra",
    "qyVF9oeo": "sound-physics-remastered",
    "rI0hvYcd": "visuality",
    # 3.0.0: not on the 26.2 mod list (or a server-only tool, which players need no copy of)
    "9NM0dXub": "advancement-plaques",
    "EsAfCjCV": "appleskin",
    "OfKzpbRU": "baguettelib",
    "cCStmVIN": "banner-flags",
    "c8slFMT1": "better-capes",
    "uWsLN21d": "better-client-enc",
    "BLG002oq": "better-craftables",
    "WeytAdLH": "bindcommands",
    "VSNURh3q": "c2me-fabric",
    "orXAsira": "cape-provider",
    "LBKcRJTu": "cinematic-zoom-fabric",
    "SJDzFJH7": "cirrus",
    "eHe8QhtD": "compose-multiplatform",
    "61PI8Hzj": "cosy-critters",
    "uCdwusMi": "distanthorizons",
    "tpehi7ww": "dungeons-and-taverns",
    "DNuNq5bb": "dungeons-and-taverns-ancient-city-overhaul",
    "7JTDDmRT": "dungeons-and-taverns-desert-temple-overhaul",
    "8Dbnvm77": "dungeons-and-taverns-nether-fortress-overhaul",
    "z6GJ3ycD": "dungeons-and-taverns-ocean-monument-overhaul",
    "QIt10I7z": "dungeons-and-taverns-pillager-outpost-overhaul",
    "rYocd2LE": "dungeons-and-taverns-stronghold-overhaul",
    "smUP7V3r": "durability-tooltip",
    "XpzGz7KD": "elytra-trims",
    "wr1BCv8H": "endercon",
    "t0YT91nL": "epic-structures-dungeons",
    "PZyzzLjz": "falling-leaves-plus",
    "vO9IpKuK": "fresh-armor-bar",
    "aEK1KhsC": "full-brightness-toggle",
    "BuWCQzqf": "hopo-better-underwater-ruins",
    "YL57xq9U": "iris",
    "fQEb0iXm": "krypton",
    "Ai97as0C": "ks-mace-trims",
    "8qVa1XCN": "lightoverlay",
    "ba5MV2CF": "mc2-interactive-foliage",
    "7tEfOcA7": "mezzconfig",
    "9gNVPfzw": "minecraftcapes",
    "JS7W12Jd": "mob-civil-war",
    "aC3cM3Vq": "mouse-tweaks",
    "j5LquiGA": "naturally-charged-creepers",
    "AibBIVmj": "oneconfig",
    "gF3BGWvG": "open-parties-and-claims",
    "JuksLGBQ": "optigui",
    "XD7XOrAF": "overflowing-bars",
    "M1B8mLoH": "overlaylib",
    "8Pq6Exn2": "packed-packs",
    "PLAGcSFJ": "particle-effects",
    "kFU5UCQz": "picture-mode",
    "eXts2L7r": "placeholder-api",
    "8HLtNhbi": "playereactions",
    "NU7qMnLN": "players-drop-heads",
    "1OE8wbN0": "prism-lib",
    "NFlNaUBA": "qraftys-end-villages",
    "RLzHAoZe": "resourcify",
    "yXAvIk0x": "scribble",
    "2M01OLQq": "shulkerboxtooltip",
    "n2UxUWXF": "silvers-datapack-tags-library",
    "wBo7DRiB": "silvers_effects-library",
    "zJhgi9nK": "silvers_inventory-library",
    "M15Gwx1o": "silvers_strength-restrictions-season-4",
    "DEvdqUh9": "silvers_strength-smp-season-4",
    "fYAofsi6": "smaller-nether-portals",
    "GG6Bb564": "smoothcamera",
    "x02cBj9Y": "status-effect-bars",
    "IUfpx2Js": "stepupagain2",
    "Gj6Yce3v": "sway",
    "B7il7E9H": "trident-all-weather-channeling",
    "HEds12HI": "visualkeys",
    "wnEe9KBa": "vmp-fabric",
    "E0SdeAoH": "wakes-reforged",
    "7P86n6Vg": "walksylib",
    "NSLJJooQ": "worldedit-cui",
    "1bokaNcj": "xaeros-minimap",
    "NcUtCpym": "xaeros-world-map",
}

CDN = re.compile(r"https://cdn\.modrinth\.com/data/([^/]+)/")


def project_id(file: dict) -> str | None:
    """The Modrinth project of one entry of the index's files (from its CDN download URL)."""
    m = CDN.match(file["downloads"][0]) if file.get("downloads") else None
    return m.group(1) if m else None


def client_env(file: dict) -> str:
    """'optional' or 'required' for one entry of the index's files."""
    pid = project_id(file)
    if file["path"].startswith(OPTIONAL_FOLDERS) or pid in OPTIONAL_MODS or pid in RETIRED_OPTIONAL:
        return "optional"
    return "required"


def env(file: dict) -> dict:
    """The whole `env` of an index entry: nothing in the client pack goes on a server."""
    return {"client": client_env(file), "server": "unsupported"}


def check(index: dict) -> list[str]:
    """Every file of the index must carry the env this module gives it (a hand edit can't drift)."""
    return [f"client {f['path']}: env must be {env(f)} (see tools/client_env.py)"
            for f in index["files"] if f.get("env") != env(f)]
