import json
import re
import tomllib

import rules
from repo import REPO


def test_fire_aspect_and_flame_are_out_of_every_source():
    data = rules.rules_files()
    tag = json.loads(data["data/minecraft/tags/enchantment/non_treasure.json"])
    assert tag["replace"] is True
    assert not set(rules.BANNED_ENCHANTMENTS) & set(tag["values"])
    # Everything else vanilla had is still there.
    assert len(tag["values"]) == len(rules.VANILLA_NON_TREASURE) - len(rules.BANNED_ENCHANTMENTS)
    for name in ("fire_aspect", "flame"):
        enchantment = json.loads(data[f"data/minecraft/enchantment/{name}.json"])
        assert enchantment["effects"] == {}
        assert enchantment["supported_items"] == []


def test_the_border_is_set_once_and_centred_on_spawn():
    data = rules.rules_files()
    load = data["data/monkey/function/rules/load.mcfunction"]
    assert f"unless score #border {rules.OBJECTIVE} matches 1 run function monkey:rules/border" in load
    border = data["data/monkey/function/rules/border.mcfunction"]
    assert "worldborder center ~ ~" in border
    assert f"worldborder set {rules.BORDER}" in border
    assert f"scoreboard players set #border {rules.OBJECTIVE} 1" in border


def test_launch_closes_pvp_and_the_nether_then_opens_them_but_not_the_end():
    data = rules.rules_files()
    launch = data["data/monkey/function/rules/launch.mcfunction"]
    over = data["data/monkey/function/rules/launch_over.mcfunction"]
    assert "gamerule pvp false" in launch and "gamerule allow_entering_nether_using_portals false" in launch
    assert f"schedule function monkey:rules/launch_over {rules.LAUNCH_SECONDS}s replace" in launch
    assert "gamerule pvp true" in over and "gamerule allow_entering_nether_using_portals true" in over
    assert "end_open" not in over


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


def test_grace_is_immunity_to_players_only_from_the_body_slot():
    data = rules.rules_files()
    grace = json.loads(data["data/monkey/enchantment/pvp_grace.json"])
    assert grace["slots"] == ["body"] and grace["supported_items"] == []
    assert set(grace["effects"]) == {"minecraft:damage_immunity", "minecraft:prevent_equipment_drop"}
    (immunity,) = grace["effects"]["minecraft:damage_immunity"]
    # 26.x condition format: "type", and component entity predicates (vanilla's protection.json)
    assert immunity["requirements"] == {"type": "minecraft:damage_source_properties",
                                        "predicate": {"source_entity": {"minecraft:entity_type": "minecraft:player"}}}
    assert '"monkey:pvp_grace":1' in rules.GRACE_STACK and "monkey_grace" in rules.GRACE_STACK
    # a player's body slot refuses anything not equippable there; only the pack may put it on, and only on players
    assert ('equippable={slot:"body",swappable:false,dispensable:false,allowed_entities:"minecraft:player"}'
            in rules.GRACE_STACK)
    # stray copies leave every inventory before the graced get theirs back; clear also empties the body slot,
    # so it runs only on players holding a copy somewhere else
    second = data["data/monkey/function/rules/second.mcfunction"].splitlines()
    clears = [i for i, line in enumerate(second) if f"run clear @s {rules.GRACE_ITEM}" in line]
    assert len(clears) == 4 and not any(line.startswith("clear @a") for line in second)
    assert "if items entity @s armor.body" not in "".join(second[i] for i in clears)
    assert max(clears) < next(i for i, line in enumerate(second) if f"with {rules.GRACE_STACK}" in line)


def test_grace_lasts_48_hours_and_ends_on_attack_or_trigger():
    data = rules.rules_files()
    fn = "data/monkey/function/rules/"
    start, end, second = (data[f"{fn}{n}.mcfunction"] for n in ("grace_start", "grace_end", "second"))
    assert rules.GRACE_TICKS == 48 * 60 * 60 * 20
    assert f"scoreboard players add @s {rules.GRACE} {rules.GRACE_TICKS}" in start
    assert f"scoreboard players enable @s {rules.END_GRACE}" in start
    assert f"scoreboard players reset @s {rules.GRACE}" in end and "armor.body with minecraft:air" in end
    assert f"if score @s {rules.GRACE} <= #now" in second
    assert f"@a[scores={{{rules.END_GRACE}=1..}}] run function monkey:rules/grace_end" in second
    attack = json.loads(data["data/monkey/advancement/rules/grace_attack.json"])
    criterion = attack["criteria"]["hurt_a_player"]
    assert criterion["trigger"] == "minecraft:player_hurt_entity"
    assert criterion["conditions"]["entity"]["predicate"] == {"minecraft:entity_type": "minecraft:player"}
    assert criterion["conditions"]["player"]["type"] == "minecraft:entity_scores"
    assert attack["rewards"]["function"] == "monkey:rules/grace_attack"
    forfeit = data[f"{fn}grace_attack.mcfunction"]
    assert "advancement revoke @s only monkey:rules/grace_attack" in forfeit
    # fights in the event arena don't end it, and the item is off there
    assert f"unless entity @s[tag={rules.ARENA_TAG}] run function monkey:rules/grace_end" in forfeit
    assert f"as @a[tag=!{rules.ARENA_TAG}] if score @s {rules.GRACE} > #now" in second
    assert f"as @a[tag={rules.ARENA_TAG}] if items entity @s armor.body {rules.GRACE_ITEM}" in second


def test_no_grace_from_the_launch_hour():
    data = rules.rules_files()
    fn = "data/monkey/function/rules/"
    launch, over, first = (data[f"{fn}{n}.mcfunction"] for n in ("launch", "launch_over", "first_join"))
    assert f"scoreboard players reset * {rules.GRACE}" in launch
    assert f"scoreboard players set #launching {rules.OBJECTIVE} 1" in launch
    assert f"scoreboard players set #launching {rules.OBJECTIVE} 0" in over
    assert f"unless score #launching {rules.OBJECTIVE} matches 1 run function monkey:rules/grace_start" in first
    assert f"tag @s add {rules.JOINED}" in first


OPEN_FOUNDER = "execute unless score #launched rw.day matches 1 run function monkey:wardrobe/founder/open"


def test_the_launch_opens_the_launch_weekend_and_restarts_the_weekly_challenges():
    launch = rules.rules_files()["data/monkey/function/rules/launch.mcfunction"].splitlines()
    # Only the first launch opens the window: challenges/launch sets #launched, and a launch run again after the
    # weekend would open one that the wall-clock sync no longer closes.
    assert OPEN_FOUNDER in launch
    assert "function monkey:challenges/launch" in launch
    assert launch.index(OPEN_FOUNDER) < launch.index("function monkey:challenges/launch")
    assert not [line for line in launch if line.endswith("founder/open") and line != OPEN_FOUNDER]


def test_players_from_before_the_pack_get_no_welcome_or_grace():
    # Nobody has the tag when the pack first reaches a running server; the game's own statistics tell who's new.
    data = rules.rules_files()
    first = data["data/monkey/function/rules/first_join.mcfunction"].splitlines()
    tag, returning = first.index(f"tag @s add {rules.JOINED}"), first.index(
        "execute if predicate monkey:rules/returning run return 0")
    assert tag < returning < min(i for i, line in enumerate(first) if rules.WELCOME in line or "grace_start" in line)
    predicate = json.loads(data["data/monkey/predicate/rules/returning.json"])
    assert predicate["type"] == "minecraft:any_of"
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


def test_distant_horizons_sends_no_lods_it_built_itself():
    # B15: server-built LODs come from the real world, so they would carry every buried ore past AntiXray.
    config = tomllib.loads((REPO.defaults / "config" / "DistantHorizons.toml").read_text(encoding="utf-8"))
    assert config["server"] == {"synchronizeOnLoad": False, "enableRealTimeUpdates": False}
    assert config["common"]["worldGenerator"]["generatorPlan"] == "DISABLED"
