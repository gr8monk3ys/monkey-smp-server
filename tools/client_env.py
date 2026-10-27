"""Which files of the client pack a player may untick: `env.client` in client/modrinth.index.json.

The Modrinth App and Prism Launcher list each "optional" file of a .mrpack with a tick box, ticked by
default, so a player on a slow PC can leave out shaders, Distant Horizons or visual mods (docs/PLAYERS.md,
"Low-end PC"). Every other file is "required": the mods that add blocks, items, entities or other registry
entries the server sends, and the libraries those mods need. Without one of them Fabric turns the player
away at the door ("This server requires ... installed on your client").

A mod goes on the optional list only when it is client-side: it isn't on the server at all, or it is a
client-only mod by its fabric.mod.json, or Modrinth says its client half is optional (the server runs it
either way, like Open Parties and Claims or Simple Voice Chat). tests/test_client_env.py checks each entry
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
    "visuals": "looks only: shaders, animations, particles, far terrain",
    "audio": "sound only: voice chat, ambience, echo",
    "map": "the minimap and the world map",
    "interface": "HUD, tooltips, menus and controls",
    "library": "needed only by other optional mods, if at all",
    "server": "the server runs it; players need no copy of it",
}

# Modrinth project id -> (slug, kind). A mod not listed here is required.
OPTIONAL_MODS = {
    # performance
    "ONZm0H7Y": ("better-block-entities", "performance"),
    "VSNURh3q": ("c2me-fabric", "performance"),
    "uXXizFIs": ("ferrite-core", "performance"),
    "5ZwdcRci": ("immediatelyfast", "performance"),
    "fQEb0iXm": ("krypton", "performance"),
    "gvQqBUqZ": ("lithium", "performance"),
    "AANobbMI": ("sodium", "performance"),
    "wnEe9KBa": ("vmp-fabric", "performance"),
    # visuals
    "zV5r3pPn": ("3dskinlayers", "visuals"),
    "c8slFMT1": ("better-capes", "visuals"),
    "orXAsira": ("cape-provider", "visuals"),
    "SJDzFJH7": ("cirrus", "visuals"),
    "1IjD5062": ("continuity", "visuals"),
    "61PI8Hzj": ("cosy-critters", "visuals"),
    "uCdwusMi": ("distanthorizons", "visuals"),
    "zS8uflwP": ("easegui", "visuals"),
    "XpzGz7KD": ("elytra-trims", "visuals"),
    "4I1XuqiY": ("entity-model-features", "visuals"),
    "BVzZfTc1": ("entitytexturefeatures", "visuals"),
    "OSQ8mw2r": ("explosive-enhancement", "visuals"),
    "PZyzzLjz": ("falling-leaves-plus", "visuals"),
    "YL57xq9U": ("iris", "visuals"),
    "Ai97as0C": ("ks-mace-trims", "visuals"),
    "bppzc3HJ": ("maseffects-v2", "visuals"),
    "ba5MV2CF": ("mc2-interactive-foliage", "visuals"),
    "9gNVPfzw": ("minecraftcapes", "visuals"),
    "JuksLGBQ": ("optigui", "visuals"),
    "PLAGcSFJ": ("particle-effects", "visuals"),
    "8aoMKplv": ("punchy-fpa", "visuals"),
    "vgVfk0m2": ("real-arrow-tip", "visuals"),
    "pXo36Na4": ("sb-enchantment-effects", "visuals"),
    "eB5MDILu": ("thirdpersondeath-continued", "visuals"),
    "jExZM2Rj": ("tightfire", "visuals"),
    "E0SdeAoH": ("wakes-reforged", "visuals"),
    "EwYg6C78": ("windy", "visuals"),
    # audio
    "9eGKb6K1": ("simple-voice-chat", "audio"),
    # map
    "kwpTgbCk": ("diorama-map", "map"),
    "1bokaNcj": ("xaeros-minimap", "map"),
    "NcUtCpym": ("xaeros-world-map", "map"),
    # interface
    "9NM0dXub": ("advancement-plaques", "interface"),
    "EsAfCjCV": ("appleskin", "interface"),
    "uWsLN21d": ("better-client-enc", "interface"),
    "n6PXGAoM": ("better-stats", "interface"),
    "WeytAdLH": ("bindcommands", "interface"),
    "UIexcMP1": ("borderless-fullscreen", "interface"),
    "lO3s8hjs": ("bridging-mod", "interface"),
    "xUTHly0N": ("centered-crosshair", "interface"),
    "Wb5oqrBJ": ("chat-heads", "interface"),
    "LBKcRJTu": ("cinematic-zoom-fabric", "interface"),
    "65UyswbY": ("commandkeys", "interface"),
    "xv94TkTM": ("controlling", "interface"),
    "o1tyE5vJ": ("custom-crosshair-mod", "interface"),
    "smUP7V3r": ("durability-tooltip", "interface"),
    "UVtY3ZAC": ("enchantment-descriptions", "interface"),
    "k2ZPuTBm": ("essential", "interface"),
    "DIlqwRFH": ("fpsdisplay", "interface"),
    "vO9IpKuK": ("fresh-armor-bar", "interface"),
    "aEK1KhsC": ("full-brightness-toggle", "interface"),
    "Boon8xwi": ("inventory-essentials", "interface"),
    "adriDDJt": ("inventory-item-groups", "interface"),
    "cVNW5lr6": ("item-highlighter", "interface"),
    "u6dRKJwZ": ("jei", "interface"),
    "8qVa1XCN": ("lightoverlay", "interface"),
    "mOgUt4GM": ("modmenu", "interface"),
    "aC3cM3Vq": ("mouse-tweaks", "interface"),
    "gF3BGWvG": ("open-parties-and-claims", "interface"),
    "XD7XOrAF": ("overflowing-bars", "interface"),
    "8Pq6Exn2": ("packed-packs", "interface"),
    "ZX66K16c": ("pick-up-notifier", "interface"),
    "kFU5UCQz": ("picture-mode", "interface"),
    "8HLtNhbi": ("playereactions", "interface"),
    "RLzHAoZe": ("resourcify", "interface"),
    "yXAvIk0x": ("scribble", "interface"),
    "2M01OLQq": ("shulkerboxtooltip", "interface"),
    "GG6Bb564": ("smoothcamera", "interface"),
    "x02cBj9Y": ("status-effect-bars", "interface"),
    "IUfpx2Js": ("stepupagain2", "interface"),
    "HEds12HI": ("visualkeys", "interface"),
    "NSLJJooQ": ("worldedit-cui", "interface"),
    # library
    "OfKzpbRU": ("baguettelib", "library"),
    "MBAkmtvl": ("balm", "library"),
    "9s6osm5g": ("cloth-config", "library"),
    "eHe8QhtD": ("compose-multiplatform", "library"),
    "7tEfOcA7": ("mezzconfig", "library"),
    "AibBIVmj": ("oneconfig", "library"),
    "M1B8mLoH": ("overlaylib", "library"),
    "eXts2L7r": ("placeholder-api", "library"),
    "1OE8wbN0": ("prism-lib", "library"),
    "fuuu3xnx": ("searchables", "library"),
    "Gj6Yce3v": ("sway", "library"),
    "Eldc1g37": ("tcdcommons", "library"),
    "Y8uFrUil": ("ukulib", "library"),
    "7P86n6Vg": ("walksylib", "library"),
    # server
    "dzG7pw5M": ("advancements_plus", "server"),
    "cCStmVIN": ("banner-flags", "server"),
    "BLG002oq": ("better-craftables", "server"),
    "UT8WxaW1": ("blaze-attack-animation", "server"),
    "1VSGxqkt": ("block-runner", "server"),
    "fALzjamp": ("chunky", "server"),
    "Wnxd13zP": ("clumps", "server"),
    "j6oNCsqx": ("craft-tridents", "server"),
    "VNMEUT3N": ("craftablecobwebs", "server"),
    "FapP9XhG": ("crazy-chambers", "server"),
    "tpehi7ww": ("dungeons-and-taverns", "server"),
    "DNuNq5bb": ("dungeons-and-taverns-ancient-city-overhaul", "server"),
    "7JTDDmRT": ("dungeons-and-taverns-desert-temple-overhaul", "server"),
    "8Dbnvm77": ("dungeons-and-taverns-nether-fortress-overhaul", "server"),
    "z6GJ3ycD": ("dungeons-and-taverns-ocean-monument-overhaul", "server"),
    "QIt10I7z": ("dungeons-and-taverns-pillager-outpost-overhaul", "server"),
    "rYocd2LE": ("dungeons-and-taverns-stronghold-overhaul", "server"),
    "Kd03i2oU": ("enchantment-disabler", "server"),
    "wr1BCv8H": ("endercon", "server"),
    "t0YT91nL": ("epic-structures-dungeons", "server"),
    "eBvPjIeN": ("fortunate-ancient-debris", "server"),
    "ZvQgzPPs": ("grand-capitals", "server"),
    "BuWCQzqf": ("hopo-better-underwater-ruins", "server"),
    "DuUMFIfX": ("mastercutter", "server"),
    "JS7W12Jd": ("mob-civil-war", "server"),
    "j5LquiGA": ("naturally-charged-creepers", "server"),
    "NU7qMnLN": ("players-drop-heads", "server"),
    "NFlNaUBA": ("qraftys-end-villages", "server"),
    "aKeMRgHX": ("random-mob-sizes-dp", "server"),
    "MDljZreW": ("reach-behind", "server"),
    "E8egdGje": ("revault", "server"),
    "Cw8IlnGM": ("serversleep", "server"),
    "n2UxUWXF": ("silvers-datapack-tags-library", "server"),
    "wBo7DRiB": ("silvers_effects-library", "server"),
    "zJhgi9nK": ("silvers_inventory-library", "server"),
    "M15Gwx1o": ("silvers_strength-restrictions-season-4", "server"),
    "DEvdqUh9": ("silvers_strength-smp-season-4", "server"),
    "cuJqipOv": ("simple-fast-happy-ghasts", "server"),
    "fYAofsi6": ("smaller-nether-portals", "server"),
    "7F1sQUtH": ("sulfur-cube-expansion", "server"),
    "AihRqJiY": ("tnt-timer", "server"),
    "B7il7E9H": ("trident-all-weather-channeling", "server"),
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
