import camera
import drops
from diplomacy import FACTION

FILES = camera.datapack_files()
FN = "data/monkey/function/camera"


def fn(name: str) -> str:
    return FILES[f"{FN}/{name}.mcfunction"]


def test_ships_off_with_no_window():
    load = fn("load")
    assert "scoreboard players add #on cm 0" in load and "scoreboard players add #open cm 0" in load
    assert "set #on" not in load and "set #open" not in load


def test_the_warps_follow_the_toggle_and_the_menu_and_each_has_a_function():
    values = [v for _, _, v in camera.WARPS]
    assert values == list(range(3, 3 + len(values)))
    use = fn("use")
    for key, name, v in camera.WARPS:
        assert f"matches {v} run return run function monkey:camera/warp/{key}" in use
        assert f"/trigger camera set {v}" in fn("menu") and f"[{name}]" in fn("menu")
        assert f"{FN}/warp/{key}.mcfunction" in FILES


def test_going_in_checks_every_rule_before_spectator():
    enter = fn("enter")
    head = enter[:enter.index("gamemode spectator")]
    for rule in ("#on cm matches 1", "@s cm.ok matches 1", "#open cm matches 1..", f"@s {FACTION} matches 1..",
                 "tag=ev.arena", "@s cm.wait matches 1..", "gamemode=spectator"):
        assert rule in head, rule
    assert "tellraw @a" in enter  # everyone sees who is filming


def test_every_second_the_rules_hold_or_the_creator_is_put_back():
    check = fn("check")
    for rule in ("unless score #on cm matches 1", "unless score #open cm matches 1..", "unless score @s cm.ok",
                 f"if score @s {FACTION} matches 1..", "unless entity @s[gamemode=spectator]"):
        assert any(rule in line and line.endswith("function monkey:camera/leave") for line in check.splitlines()), rule
    assert "execute as @a[scores={cm.in=1}] run function monkey:camera/check" in fn("second")


def test_the_leash_holds_every_tick_and_inside_the_claim_gap():
    leash = fn("leash")
    assert "unless dimension minecraft:overworld run return run function monkey:camera/snap" in leash
    assert f"matches -{camera.LEASH}..{camera.LEASH} run return run function monkey:camera/snap" in leash
    assert "monkey:camera/tick" in FILES["data/minecraft/tags/function/tick.json"]
    assert fn("tick").strip().endswith("execute as @a[scores={cm.in=1}] run function monkey:camera/leash")
    assert camera.LEASH < drops.CLAIM_GAP * 16


def test_going_in_starts_at_the_public_spawn_and_the_rules_ask_for_a_stream_delay():
    enter = fn("enter")
    assert enter.index("unless data storage monkey:camera spawn.x") < enter.index("gamemode spectator")
    assert "function monkey:camera/warp/spawn" in enter[enter.index("gamemode spectator"):]
    assert "monkey:camera/anchor" not in enter
    assert "delay" in camera.RULES and "rule 10" in camera.RULES


def test_leaving_restores_the_place_dimension_and_game_mode():
    leave = fn("leave")
    for d in camera.DIMENSIONS:
        assert f'back.dim set value "{d}"' in leave
    for m in camera.MODES:
        assert f"gamemode {m} @s" in leave
    assert "$execute in minecraft:$(dim) run tp @s $(x) $(y) $(z)" in fn("back")


def test_staff_cannot_approve_a_faction_member():
    approve = fn("approve").splitlines()
    refusal = next(i for i, line in enumerate(approve) if FACTION in line)
    grant = next(i for i, line in enumerate(approve) if "cm.ok 1" in line)
    assert refusal < grant and "return" in approve[refusal]


def test_revoking_resets_approval_and_trigger():
    revoke = fn("revoke")
    assert "$scoreboard players reset $(name) cm.ok" in revoke
    assert "$scoreboard players reset $(name) camera" in revoke
