import json
import re

import rules
from repo import REPO


def test_the_border_is_set_once_and_centred_on_spawn():
    data = rules.rules_files()
    load = data["data/monkey/function/rules/load.mcfunction"]
    assert f"unless score #border {rules.OBJECTIVE} matches 1 run function monkey:rules/border" in load
    border = data["data/monkey/function/rules/border.mcfunction"]
    assert "worldborder center ~ ~" in border
    assert f"worldborder set {rules.BORDER}" in border
    assert f"scoreboard players set #border {rules.OBJECTIVE} 1" in border


def test_the_border_starts_at_6000_and_the_nethers_at_one_eighth():
    data = rules.rules_files()
    assert rules.BORDER == 6000
    nether = data["data/monkey/function/rules/nether_border.mcfunction"]
    assert "execute in minecraft:the_nether run worldborder set 750.0" in nether


def test_the_launch_opens_pvp_and_the_nether_at_once_and_keeps_the_end_closed():
    data = rules.rules_files()
    launch = data["data/monkey/function/rules/launch.mcfunction"]
    assert "gamerule pvp true" in launch and "gamerule allow_entering_nether_using_portals true" in launch
    assert "schedule" not in launch and "false" not in launch       # a test launch of old can't leave them shut
    load = data["data/monkey/function/rules/load.mcfunction"]
    assert f"scoreboard players reset #launching {rules.OBJECTIVE}" in load
    assert f"scoreboard players set #end_open {rules.OBJECTIVE} 0" in launch
    assert "data/monkey/function/rules/launch_over.mcfunction" not in data
    second = data["data/monkey/function/rules/second.mcfunction"]
    assert f"unless score #end_open {rules.OBJECTIVE} matches 1 in minecraft:the_end" in second
    assert "Dragon Night" in data["data/monkey/function/rules/leave_end.mcfunction"]


def test_the_relaunch_drops_grace_and_the_item_bans():
    data = rules.rules_files()
    every = "".join(data.values())
    assert "grace" not in every.lower() and "fire_aspect" not in every and "netherite" not in every.lower()
    assert not [p for p in data if "enchantment" in p or "advancement" in p]


def test_only_netherite_armor_recipes_are_removed():
    data = rules.netherite_files()
    recipes = {p for p in data if p.startswith("data/minecraft/recipe/")}
    assert recipes == {f"data/minecraft/recipe/{i}_smithing.json" for i in rules.NETHERITE_ARMOR}
    for path in recipes:
        recipe = json.loads(data[path])
        assert recipe["template"] == rules.NEVER_TEMPLATE
        assert recipe["base"].startswith("minecraft:diamond_")
    tag = json.loads(data["data/monkey/tags/item/netherite_armor.json"])["values"]
    assert not any("sword" in i or "axe" in i or "pickaxe" in i for i in tag)
    for slot in rules.ARMOR_SLOTS:
        assert f"data/monkey/function/netherite/drop_{slot}.mcfunction" in data


def test_party_limit_default_is_four():
    text = (REPO.defaults / "config" / "openpartiesandclaims-server.toml").read_text(encoding="utf-8")
    assert "maxPartyMembers = 4" in text


def test_claim_limit_is_two_by_two_chunks_per_member():
    # Rule 35: claims are per player (partyOwnedClaims stays at its default, false), 4 chunks each.
    text = (REPO.defaults / "config" / "openpartiesandclaims-server.toml").read_text(encoding="utf-8")
    assert "maxPlayerClaims = 4" in text
    assert "partyOwnedClaims" not in text


OPEN_FOUNDER = "execute unless score #launched rw.day matches 1 run function monkey:wardrobe/founder/open"


def test_the_launch_opens_the_launch_weekend_and_restarts_the_weekly_challenges():
    launch = rules.rules_files()["data/monkey/function/rules/launch.mcfunction"].splitlines()
    # Only the first launch opens the window: challenges/launch sets #launched, and a launch run again after the
    # weekend would open one that the wall-clock sync no longer closes.
    assert OPEN_FOUNDER in launch
    assert "function monkey:challenges/launch" in launch
    assert launch.index(OPEN_FOUNDER) < launch.index("function monkey:challenges/launch")
    assert not [line for line in launch if line.endswith("founder/open") and line != OPEN_FOUNDER]


def test_players_from_before_the_pack_get_no_welcome_or_kit():
    # Nobody has the tag when the pack first reaches a running server; the game's own statistics tell who's new.
    data = rules.rules_files()
    first = data["data/monkey/function/rules/first_join.mcfunction"].splitlines()
    tag, returning = first.index(f"tag @s add {rules.JOINED}"), first.index(
        "execute if predicate monkey:rules/returning run return 0")
    assert tag < returning < min(i for i, line in enumerate(first) if rules.WELCOME in line or "catchup" in line)
    predicate = json.loads(data["data/monkey/predicate/rules/returning.json"])
    assert predicate["condition"] == "minecraft:any_of"
    stats = {t["predicate"]["minecraft:type_specific/player"]["stats"][0]["stat"] for t in predicate["terms"]}
    assert stats == {"minecraft:leave_game", "minecraft:play_time"}


def test_welcome_points_at_the_discord_and_the_pause_menu_has_the_links():
    data = rules.rules_files()
    config = json.loads((REPO.root / "site" / "config.json").read_text(encoding="utf-8"))
    assert (config["DISCORD_INVITE"], config["MAP_URL"]) == (rules.DISCORD, rules.MAP)
    site_config = (REPO.root / "site" / "src" / "lib" / "config.ts").read_text(encoding="utf-8")
    assert f'SITE_URL = "{rules.SITE}"' in site_config
    welcome = json.loads(data["data/monkey/dialog/welcome.json"])
    assert welcome["type"] == "minecraft:notice"
    assert welcome["action"]["action"] == {"type": "minecraft:open_url", "url": rules.DISCORD}
    assert "dialog show @s monkey:welcome" in data["data/monkey/function/rules/welcome.mcfunction"]
    links = json.loads(data["data/monkey/dialog/links.json"])
    assert links["type"] == "minecraft:multi_action"
    urls = [a["action"]["url"] for a in links["actions"]]
    assert urls == [url for _, url, _ in rules.LINKS] and all(u.startswith("https://") for u in urls)
    tag = json.loads(data["data/minecraft/tags/dialog/pause_screen_additions.json"])
    assert tag == {"values": ["monkey:links"]}


def test_code_of_conduct_is_on_and_quotes_real_rules():
    props = (REPO.defaults / "server.properties").read_text(encoding="utf-8")
    assert "\nenable-code-of-conduct=true\n" in props
    conduct = (REPO.defaults / "codeofconduct" / "en_us.txt").read_bytes()
    assert conduct.isascii() and b"\r" not in conduct
    book = (REPO.root / "docs" / "RULES.md").read_text(encoding="utf-8")
    rules_in_book = {m for m in re.findall(r"(?m)^(\d+)\. ", book)}
    bans_in_book = {f"B{m}" for m in re.findall(r"\*\*B(\d+)\.\*\*", book)}
    cited = set()
    for group in re.findall(r"\(([B\d][B\d, -]*)\)", conduct.decode()):
        for part in group.split(","):
            first, _, last = part.strip().partition("-")
            if last:
                prefix = "B" if first.startswith("B") else ""
                cited |= {f"{prefix}{n}" for n in range(int(first.lstrip("B")), int(last.lstrip("B")) + 1)}
            else:
                cited.add(first)
    assert cited and cited <= rules_in_book | bans_in_book, cited - rules_in_book - bans_in_book


def test_servercore_breeding_cap_and_villager_lobotomy_are_on():
    lines = (REPO.defaults / "config" / "servercore" / "config.yml").read_text(encoding="utf-8").splitlines()

    def enabled_after(key: str) -> str:
        start = next(i for i, line in enumerate(lines) if line.strip() == key)
        return next(line.split(":", 1)[1].strip() for line in lines[start:] if line.strip().startswith("enabled:"))

    assert enabled_after("breeding-cap:") == "true"
    assert enabled_after("lobotomize-villagers:") == "true"


def test_welcome_explains_lifesteal_the_team_size_and_where_the_rulebook_is():
    welcome = json.loads(rules.rules_files()["data/monkey/dialog/welcome.json"])
    text = " ".join(b["contents"] for b in welcome["body"] if isinstance(b["contents"], str))
    assert "lifesteal" in text and "24 hours" in text and "golden shovel" in text and "faction" not in text
    assert f"teams of up to {rules.say_number(rules.TEAM_SIZE)}" in text and "rulebook is on the website" in text
    assert ("Rules", f"{rules.SITE}/guide/rules") in [(label, url) for label, url, _ in rules.LINKS]
