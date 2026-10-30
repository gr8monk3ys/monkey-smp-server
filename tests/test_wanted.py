import json

import wanted

import standings

FILES = standings.datapack_files()


def fn(name):
    return FILES[f"data/monkey/function/wanted/{name}.mcfunction"]


def test_it_ships_off_and_staff_switch_it():
    assert wanted.WANTED_ON == 0
    assert "execute unless score #on wt matches 0.. run scoreboard players set #on wt 0" in fn("load")
    assert "scoreboard players set #on wt 1" in fn("on")
    assert "scoreboard players set #on wt 0" in fn("off")
    # Off, nobody can post or claim, and the Most Wanted leaves the board at once.
    assert fn("use").index("unless score #on wt matches 1") < fn("use").index("function monkey:wanted/post")
    assert "execute unless score #on wt matches 1 run return 0" in fn("slain")
    assert 'data modify storage monkey:standings wanted set value {text:""}' in fn("off")
    assert "function monkey:standings/publish" in fn("off")
    assert "monkey:wanted/load" in json.loads(FILES["data/minecraft/tags/function/load.json"])["values"]
    assert {"wanted/on", "wanted/off"} <= {cmd for cmd, _ in standings.HELP}


def test_it_runs_on_the_second_clock_not_every_tick():
    assert "wanted" not in FILES["data/monkey/function/standings/tick.mcfunction"]
    second = fn("second")
    assert "schedule function monkey:wanted/second 20t replace" in second
    assert "execute as @a[scores={wanted=1..}] run function monkey:wanted/use" in second


def test_posting_refuses_self_faction_mates_pacts_and_too_often():
    post = fn("post")
    for why in ("Join a faction first", "one every 12 hours", "Not on yourself", "They're in your faction.",
                "Your factions have a pact.", "give them a break", "Your bounty on them is still up.",
                "They're in no faction"):
        assert why in post, why
    # every refusal comes before the bounty is added
    added = post.index("scoreboard players add @a[tag=wt.target,limit=1] st.wanted 1")
    assert all(post.index(line) < added for line in post.splitlines() if "return run" in line)
    assert f"matches 0..{wanted.POST_HOURS * 72_000 - 1}" in post
    # reading wt.last in an operation would set it to 0 and refuse a first post on a world under 12 hours old
    assert all(line.startswith("execute if score @s wt.last matches") for line in post.splitlines() if
               "operation" in line and "wt.last" in line.split("operation", 1)[1].split("=")[-1])
    assert "if score #$(lo).$(hi) dp.pact matches 1 run return 1" in fn("pact_of")
    assert "function monkey:diplomacy/pair" in fn("pact")
    assert "Bounties open when the season launches." in fn("use")


def test_a_claim_is_announced_cosmetic_and_never_in_the_arena():
    slain = fn("slain")
    assert "execute if entity @s[tag=ev.arena] run return 0" in slain
    assert "execute unless score #launched rw.day matches 1 run return 0" in slain
    claim = fn("claim")
    assert claim.index("@s[tag=ev.arena] run return 0") < claim.index("st.hunts 1")
    assert claim.index("in your faction") < claim.index("st.hunts 1")
    assert claim.index("have a pact") < claim.index("st.hunts 1")
    assert "tellraw @a" in claim and "Bounty claimed: " in claim
    assert "execute if entity @s[team=] run team join bounty_hunter @s" in claim
    # cosmetic only: no items, no effects, no standings points (st.bounty is the staff bounties')
    assert not any(line.startswith(("give", "effect", "attribute", "item")) for line in claim.splitlines())
    assert "st.bounty" not in "".join(v for k, v in FILES.items() if "/wanted/" in k)
    assert "scoreboard players set @a[tag=wt.target,limit=1] st.wanted 0" in claim
    assert "wt.gen 1" in claim and f"wt.free {wanted.REST_HOURS * 72_000}" in claim


def test_the_victim_is_marked_before_the_killer_claims():
    slain = json.loads(FILES["data/monkey/advancement/wanted/slain.json"])
    kill = json.loads(FILES["data/monkey/advancement/wanted/kill.json"])
    assert slain["criteria"]["slain"]["trigger"] == "minecraft:entity_killed_player"
    assert kill["criteria"]["kill"]["trigger"] == "minecraft:player_killed_entity"
    assert "advancement revoke @s only monkey:wanted/slain" in fn("slain")
    assert "advancement revoke @s only monkey:wanted/kill" in fn("kill")
    assert "tag @a remove wt.victim" in fn("kill") and "tag @a[tag=wt.victim] remove wt.victim" in fn("second")


def test_the_menu_buttons_name_players_by_number():
    assert wanted.FIRST_ID > 9   # 1 to 9 open the menu
    assert f"scoreboard players set #next wt.id {wanted.FIRST_ID - 1}" in fn("load")
    assert '"command":"/trigger wanted set $(id)"' in fn("row_show")
    assert fn("row_show").startswith("$tellraw")


def test_most_wanted_on_the_board():
    scores = {"wt": {"#on": 1}, "st.wanted": {"Alex": 2, "bea": 4, "Cy": 2, "Dee": 1, "Ed": 0, "#x": 9}}
    assert wanted.most_wanted(scores) == [("bea", 4), ("Alex", 2), ("Cy", 2)]
    shown = json.dumps(wanted.section(scores))
    assert "Most Wanted" in shown and "1. bea: 4 bounties" in shown and "Dee" not in shown
    assert wanted.section({"st.wanted": {"Alex": 3}}) == {"text": ""}   # off: nothing on the board
    assert "No bounties posted." in json.dumps(wanted.section({"wt": {"#on": 1}}))
    assert standings.wanted_command(scores).startswith("data modify storage monkey:standings wanted set value {")
    publish = FILES["data/monkey/function/standings/publish.mcfunction"]
    assert publish.index("from storage monkey:standings week") < \
        publish.index("from storage monkey:standings wanted") < publish.index("from storage monkey:standings last")
