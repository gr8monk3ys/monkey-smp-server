import datetime as dt
import gzip
import json
import re
import shutil
import struct
import subprocess

import pytest

import drops
import events
import map_border
from repo import REPO

UTC = dt.timezone.utc  # noqa: UP017 (the module under test keeps to 3.10)
FILES = drops.datapack_files()
FUNCTIONS = {k for k in FILES if k.endswith(".mcfunction")}
SPAWN = (-80.0, 416.0)   # where the pinned seed puts spawn, and so the border's centre (tests/test_map_border.py)


def pacific(*args) -> dt.datetime:
    return dt.datetime(*args, tzinfo=drops.PACIFIC)


def fn(path: str) -> str:
    return FILES[f"{drops.FN}/{path}.mcfunction"]


# ---------------------------------------------------------------- a made-up world


class Long(int):
    pass


def nbt(value, name="") -> bytes:
    """A tiny NBT writer: dicts, lists, strings, ints (TAG_Int), floats (TAG_Double) and Long."""
    def tag(v) -> int:
        return (10 if isinstance(v, dict) else 9 if isinstance(v, list) else 8 if isinstance(v, str)
                else 6 if isinstance(v, float) else 4 if isinstance(v, Long) else 3)

    def payload(v) -> bytes:
        if isinstance(v, dict):
            return b"".join(bytes([tag(x)]) + string(k) + payload(x) for k, x in v.items()) + b"\x00"
        if isinstance(v, list):
            return bytes([tag(v[0]) if v else 0]) + struct.pack(">i", len(v)) + b"".join(payload(x) for x in v)
        if isinstance(v, str):
            return string(v)
        return struct.pack(">d" if isinstance(v, float) else ">q" if isinstance(v, Long) else ">i", v)

    def string(s: str) -> bytes:
        raw = s.encode()
        return struct.pack(">H", len(raw)) + raw
    return bytes([10]) + string(name) + payload(value)


def claim_file(chunks: dict[str, list[tuple[int, int]]]) -> dict:
    """A player-claims file as Open Parties and Claims 0.32 saves it."""
    return {"username": "x", "confirmedActivity": Long(0), "dimensions": {
        dim: {"claims": [{"state": {"subConfigIndex": -1, "forceloadable": 0},
                          "positions": [{"x": x, "z": z} for x, z in positions]}]}
        for dim, positions in chunks.items()}}


def make_world(root, size=2500.0, target=None, claims=None):
    world = root / "world"
    border = world / "dimensions" / "minecraft" / "overworld" / "data" / "minecraft" / "world_border.dat"
    border.parent.mkdir(parents=True)
    border.write_bytes(gzip.compress(nbt({"DataVersion": 5023, "data": {
        "center_x": SPAWN[0], "center_z": SPAWN[1], "size": size, "lerp_target": size if target is None else target,
        "lerp_time": Long(0), "warning_blocks": 5}})))
    folder = world / drops.OPAC_CLAIMS
    folder.mkdir(parents=True)
    for i, chunks in enumerate(claims or []):
        (folder / f"00000000-0000-0000-0000-00000000000{i}.nbt").write_bytes(nbt(claim_file(chunks)))
    return world


# A base south-east of spawn, one far to the west, the spawn claim (the server's) and a Nether claim that
# doesn't count.
BASE = [(cx, cz) for cx in range(10, 14) for cz in range(40, 44)]
WEST = [(-60, 20), (-60, 21)]
CLAIMS = [{drops.OVERWORLD: BASE}, {drops.OVERWORLD: WEST, "minecraft:the_nether": [(0, 0)]},
          {drops.OVERWORLD: [(-5, 26)]}]


@pytest.fixture
def world(tmp_path):
    return make_world(tmp_path, claims=CLAIMS)


def chunk(x: int, z: int) -> tuple[int, int]:
    return x // 16, z // 16


# ---------------------------------------------------------------- when


def test_drop_nights_are_monday_to_thursday_evenings_pacific_from_season_one():
    assert drops.night_of(pacific(2026, 11, 23, 18, 0)) == 20261123          # Monday of week 1, 6 PM
    assert drops.night_of(pacific(2026, 11, 26, 21, 59)) == 20261126         # Thursday, the last minute
    assert drops.night_of(pacific(2026, 11, 23, 17, 59)) is None
    assert drops.night_of(pacific(2026, 11, 23, 22, 0)) is None
    for day in (27, 28, 29):                                                 # Friday, Saturday (events), Sunday
        assert drops.night_of(pacific(2026, 11, day, 19, 0)) is None
    assert drops.night_of(pacific(2026, 11, 16, 19, 0)) is None              # before Season I's first week
    assert drops.FIRST_NIGHT.weekday() == 0
    # UTC in, the Pacific date out: 2 AM UTC Tuesday is 6 PM Monday (PST), 1 AM UTC is 6 PM in summer time.
    assert drops.night_of(dt.datetime(2026, 11, 24, 2, 0, tzinfo=UTC)) == 20261123
    assert drops.night_of(dt.datetime(2027, 3, 16, 1, 0, tzinfo=UTC)) == 20270315
    assert drops.night_of(dt.datetime(2027, 3, 16, 0, 59, tzinfo=UTC)) is None


def test_a_slot_is_ten_minutes():
    assert drops.slot_of(pacific(2026, 11, 23, 18, 0)) == drops.slot_of(pacific(2026, 11, 23, 18, 9, 59))
    assert drops.slot_of(pacific(2026, 11, 23, 18, 9)) != drops.slot_of(pacific(2026, 11, 23, 18, 10))
    assert drops.slot_of(pacific(2026, 11, 23, 18, 0)) != drops.slot_of(pacific(2026, 11, 24, 18, 0))


def test_parse_time_assumes_utc():
    assert drops.parse_time("2026-11-24T02:00:00") == dt.datetime(2026, 11, 24, 2, tzinfo=UTC)
    assert drops.parse_time("2026-11-24T02:00:00Z") == dt.datetime(2026, 11, 24, 2, tzinfo=UTC)


# ---------------------------------------------------------------- where


def test_the_ring_follows_the_border_acts():
    def ring(size):
        return drops.ring(map_border.Border(*SPAWN, size))
    assert ring(2500) == (drops.SPAWN_CLEAR, 1250 - drops.BORDER_MARGIN)   # before the first act: past spawn
    assert ring(4000) == (1250, 2000 - drops.BORDER_MARGIN)                # act 2: the new ring only
    assert ring(6000) == (2000, 3000 - drops.BORDER_MARGIN)
    assert ring(5000) == (2000, 2500 - drops.BORDER_MARGIN)                # between acts: past the last one


def test_reads_the_border_and_every_overworld_claim(world):
    assert drops.border_now(world) == map_border.Border(*SPAWN, 2500)
    assert drops.claimed_chunks(world) == set(BASE) | set(WEST) | {(-5, 26)}


def test_a_moving_border_counts_at_its_smaller_size(tmp_path):
    growing = make_world(tmp_path / "a", size=2500.0, target=4000.0)
    assert drops.border_now(growing).size == 2500
    shrinking = make_world(tmp_path / "b", size=4000.0, target=2500.0)
    assert drops.border_now(shrinking).size == 2500


def test_no_border_no_spots(tmp_path):
    assert drops.spots(tmp_path, "x") == []
    huge = make_world(tmp_path / "huge", size=float(map_border.NO_BORDER))
    assert drops.border_now(huge) is None and drops.spots(huge, "x") == []


def test_spots_are_in_the_ring_clear_of_claims_and_apart(world):
    border = drops.border_now(world)
    inner, outer = drops.ring(border)
    claims = drops.claimed_chunks(world)
    for seed in ("a", "b", "20261123-180", "20261123-181"):
        found = drops.spots(world, seed)
        assert len(found) == drops.SPOTS
        for x, z in found:
            assert x % 16 == 8 and z % 16 == 8                                # a chunk's middle
            assert inner <= max(abs(x - SPAWN[0]), abs(z - SPAWN[1])) <= outer
            cx, cz = chunk(x, z)
            assert min(max(abs(cx - a), abs(cz - b)) for a, b in claims) > drops.CLAIM_GAP
        for i, a in enumerate(found):
            for b in found[i + 1:]:
                assert max(abs(chunk(*a)[0] - chunk(*b)[0]), abs(chunk(*a)[1] - chunk(*b)[1])) >= drops.SPOT_GAP


def test_spots_are_the_same_for_a_slot_and_new_for_the_next(world):
    assert drops.spots(world, "20261123-180") == drops.spots(world, "20261123-180")
    assert drops.spots(world, "20261123-180") != drops.spots(world, "20261123-181")


def test_a_claim_next_to_a_spot_moves_it(tmp_path):
    first = drops.spots(make_world(tmp_path / "a"), "s")[0]
    cx, cz = chunk(*first)
    claimed = make_world(tmp_path / "b", claims=[{drops.OVERWORLD: [(cx + drops.CLAIM_GAP, cz)]}])
    assert first not in drops.spots(claimed, "s")


def test_a_world_with_everything_claimed_has_no_spots(tmp_path):
    lo, hi = int((SPAWN[0] - 1250) // 16), int((SPAWN[0] + 1250) // 16)
    lo_z, hi_z = int((SPAWN[1] - 1250) // 16), int((SPAWN[1] + 1250) // 16)
    every = [(x, z) for x in range(lo, hi + 1, drops.CLAIM_GAP) for z in range(lo_z, hi_z + 1, drops.CLAIM_GAP)]
    assert drops.spots(make_world(tmp_path, claims=[{drops.OVERWORLD: every}]), "s") == []


# ---------------------------------------------------------------- the timer's commands


def test_commands_send_the_spots_then_try_tonight(world):
    when = pacific(2026, 11, 24, 19, 5)
    out = drops.commands(world, when)
    assert len(out) == 2
    listed = ",".join(f"{{x:{x},z:{z}}}" for x, z in drops.spots(world, drops.slot_of(when)))
    assert out[0] == f"data modify storage realms:drops spots set value [{listed}]"
    assert out[1] == "function realms:drops/try {night:20261124}"
    for c in out:
        assert c.isascii() and "\n" not in c and len(c.encode()) <= drops.RCON_LIMIT


def test_no_commands_outside_drop_hours_or_without_spots(world, tmp_path):
    assert drops.commands(world, pacific(2026, 11, 24, 23, 0)) == []
    assert drops.commands(world, pacific(2026, 11, 28, 19, 0)) == []
    assert drops.commands(tmp_path / "nothing", pacific(2026, 11, 24, 19, 0)) == []


def test_main_prints_the_commands_and_the_spots(world, capsys):
    assert drops.main(["commands", str(world), "--at", "2026-11-25T03:00:00Z"]) == 0
    out = capsys.readouterr().out.splitlines()
    assert out[1] == "function realms:drops/try {night:20261124}"
    assert drops.main(["commands", str(world), "--at", "2026-11-25T08:00:00Z"]) == 0
    assert capsys.readouterr().out == ""
    assert drops.main(["spots", str(world), "--at", "2026-11-25T03:00:00Z"]) == 0
    out = capsys.readouterr().out
    assert "drop night 20261124" in out and "claimed chunks in the Overworld: 19" in out
    assert drops.main(["spots", str(world.parent / "none")]) == 1


# ---------------------------------------------------------------- the loot


FORBIDDEN = ("netherite", "diamond", "emerald", "golden_apple", "enchanted", "potion", "totem", "elytra",
             "shulker", "beacon", "strength", "ancient_debris", "trident", "mace", "spawner", "_spawn_egg")


def test_the_loot_is_modest():
    for pool, item, weight, lo, hi in drops.LOOT:
        assert pool in drops.ROLLS and weight > 0 and 1 <= lo <= hi <= 16, item
        assert re.fullmatch(r"[a-z_]+", item) and not any(word in item for word in FORBIDDEN), item
    assert {p for p, *_ in drops.LOOT} == set(drops.ROLLS)


def test_the_loot_table_is_26_3s_form():
    table = json.loads(FILES["data/realms/loot_table/drops/supply.json"])
    assert table["type"] == "minecraft:chest" and len(table["pools"]) == len(drops.ROLLS)
    for pool in table["pools"]:
        for entry in pool["entries"]:
            assert "functions" not in entry
            if "modifier" in entry:
                assert entry["modifier"]["type"] == "minecraft:set_count"
                assert entry["modifier"]["count"]["min"] < entry["modifier"]["count"]["max"]
    names = [e["name"] for p in table["pools"] for e in p["entries"]]
    assert names == [f"minecraft:{item}" for pool in drops.ROLLS for p, item, *_ in drops.LOOT if p == pool]


# ---------------------------------------------------------------- the data pack


def test_committed_pack_matches_the_generator():
    assert drops.differences(REPO) == [], "run python tools/drops.py pack"


def test_pack_uses_the_events_pack_format():
    pack = json.loads(FILES["pack.mcmeta"])["pack"]
    assert pack["min_format"] == pack["max_format"] == drops.DATA_FORMAT == events.DATA_FORMAT


def test_every_called_function_exists():
    for path, body in FILES.items():
        for name in re.findall(rf"function {drops.NS}:([\w/]+)", body):
            assert f"data/{drops.NS}/function/{name}.mcfunction" in FUNCTIONS, f"{path} calls {name}"


def test_macro_lines_are_marked_and_marked_lines_are_macros():
    for path in FUNCTIONS:
        for line in FILES[path].splitlines():
            if not line.startswith("#"):
                assert ("$(" in line) == line.startswith("$"), f"{path}: {line}"


def test_json_files_parse_and_text_is_ascii_safe():
    for path, body in FILES.items():
        if path.endswith((".json", ".mcmeta")):
            json.loads(body)
        assert body.endswith("\n") and "\r" not in body, path


def test_try_returns_every_code_and_checks_the_events():
    body = fn("try")
    assert set(map(int, re.findall(r"return (\d+)$", body, re.M))) == set(drops.TRY_CODES)
    for cond in drops.EVENTS_ON:
        assert f"execute if score {cond} run return 13" in body
    # Every event state the drop checks is one realms-events sets.
    events_text = "\n".join(events.datapack_files().values())
    for cond in drops.EVENTS_ON:
        holder = cond.split()[0]
        assert f"scoreboard players set {holder} ev.state 1" in events_text, holder
    script = (REPO.root / "deploy" / "realms-drops.sh").read_text()
    for code, about in drops.TRY_CODES.items():
        assert f"*' returned {code}') echo " in script and about in script, code


def test_the_order_of_the_checks():
    body = [line for line in fn("try").splitlines() if not line.startswith("#")]
    assert body[0].endswith("return 10") and body[1].endswith("return 11") and body[2].endswith("return 12")
    assert body[-2] == "function realms:drops/locate" and body[-1] == "return 1"


def test_chests_scale_with_players_and_stay_within_the_cap():
    found = fn("found")
    assert "scoreboard players operation #chests dr /= #min dr" in found
    assert "execute if score #chests dr matches ..0 run scoreboard players set #chests dr 1" in found
    assert f"matches {drops.MAX_CHESTS + 1}.. run scoreboard players set #chests dr {drops.MAX_CHESTS}" in found
    assert len(drops.CHEST_AT) == drops.MAX_CHESTS
    chests = fn("chests")
    for k in range(drops.MAX_CHESTS):
        assert f"if score #chests dr matches {k + 1}.. " in chests
    # Never side by side (two chests would join), and inside the loaded area.
    for i, (ax, az) in enumerate(drops.CHEST_AT):
        assert max(abs(ax), abs(az)) <= drops.REACH
        for bx, bz in drops.CHEST_AT[i + 1:]:
            assert abs(ax - bx) + abs(az - bz) > 1


def test_chests_land_only_on_natural_ground_and_replace_only_plants_or_air():
    ground = json.loads(FILES["data/realms/tags/block/drops/ground.json"])["values"]
    assert not any(word in v for v in ground for word in ("planks", "log", "wool", "glass", "brick", "concrete"))
    open_ = json.loads(FILES["data/realms/tags/block/drops/open.json"])["values"]
    assert {"id": "minecraft:short_dry_grass", "required": False} in open_
    assert "minecraft:air" in open_ and not any("water" in str(v) for v in open_)
    check = fn("check_at")
    assert "if block ~ ~-1 ~ #realms:drops/ground if block ~ ~ ~ #realms:drops/open" in check
    assert "positioned over motion_blocking_no_leaves" in check   # water is motion-blocking: a sea spot fails


def test_only_drop_chests_are_removed():
    for name in ("expire", "stop"):
        body = fn(name)
        for line in body.splitlines():
            if "setblock" in line and not line.startswith("#"):
                assert line.startswith("execute as @e[type=minecraft:marker,tag=dr.chest] at @s if block ~ ~ ~ "
                                       "minecraft:chest if data block ~ ~ ~ {CustomName:\"Supply drop\"}"), line
    assert fn("emptied").splitlines()[1] == "setblock ~ ~ ~ minecraft:air"
    assert "at @s unless data block ~ ~ ~ Items[0] run function realms:drops/emptied" in fn("landed")


def test_drop_chests_are_filled_when_placed_so_loot_restock_never_refills_them():
    # Loot Restock refills, a week later, any chest that is opened while it still has a loot table. A drop chest
    # never has one: it is filled when it lands.
    body = [line for line in fn("place").splitlines() if not line.startswith("#")]
    assert body[0] == 'setblock ~ ~ ~ minecraft:chest{CustomName:"Supply drop"}'
    assert body[1] == "loot insert ~ ~ ~ loot realms:drops/supply"
    assert "LootTable" not in "".join(body)


def test_a_drop_ends_cleanly():
    cleanup = fn("cleanup")
    for want in ("kill @e[type=minecraft:marker,tag=dr.chest]", "kill @e[type=minecraft:marker,tag=dr.spot]",
                 "kill @e[type=minecraft:text_display,tag=dr.label]", "bossbar remove realms:drop",
                 "function realms:drops/release with storage realms:drops spot", "schedule clear realms:drops/check",
                 "scoreboard players set #state dr 0"):
        assert want in cleanup, want
    for name in ("looted", "expire", "blocked", "stop"):
        assert "function realms:drops/cleanup" in fn(name), name
    assert "forceload add $(x0) $(z0) $(x1) $(z1)" in fn("hold")
    assert "forceload remove $(x0) $(z0) $(x1) $(z1)" in fn("release")


def test_the_loaded_chunks_are_always_the_overworlds():
    # forceload acts in the dimension it runs in. Staff running start, here or stop from the Nether or the End
    # loaded (or released) the chunks there, and the Overworld's stayed loaded for good (seen on a test server).
    assert fn("hold") == "$execute in minecraft:overworld run forceload add $(x0) $(z0) $(x1) $(z1)\n"
    assert fn("release") == "$execute in minecraft:overworld run forceload remove $(x0) $(z0) $(x1) $(z1)\n"
    for path in FUNCTIONS:
        for line in FILES[path].splitlines():
            if "forceload" in line and not line.startswith("#"):
                assert "in minecraft:overworld run forceload" in line, f"{path}: {line}"
    # The ground check and the chests already run in the Overworld (in at the spot, at the markers).
    assert "execute in minecraft:overworld positioned $(x) 0 $(z)" in fn("check_at")


def test_here_refuses_outside_the_overworld():
    first = [line for line in fn("here").splitlines() if not line.startswith("#")][0]
    assert first.startswith("execute unless dimension minecraft:overworld run return run tellraw @s ")


def test_timings():
    assert f"scoreboard players set #timer dr {drops.COUNTDOWN}" in fn("found")
    assert f"scoreboard players set #timer dr {drops.DESPAWN}" in fn("land")
    assert drops.COUNTDOWN == 600   # docs/SEASONS.md: announced 10 minutes ahead
    for s in drops.WARN_AT:
        assert f"execute if score #timer dr matches {s} run tellraw @a" in fn("countdown")
    assert "execute if score #timer dr matches ..0 run function realms:drops/land" in fn("countdown")
    assert "execute if score #timer dr matches ..0 run function realms:drops/expire" in fn("landed")


def test_a_restart_picks_the_drop_up_again():
    load = fn("load")
    assert "schedule function realms:drops/second 20t replace" in load
    assert "execute if score #state dr matches 1 run schedule function realms:drops/check 20t replace" in load
    # Settings staff changed survive a reload.
    assert "execute unless score #min dr matches 1.. run scoreboard players set #min dr 4" in load
    assert "execute unless score #auto dr matches 0.. run scoreboard players set #auto dr 1" in load


def test_a_staff_drop_keeps_tonights():
    start = fn("start")
    assert start.splitlines()[1].startswith("execute if score #state dr matches 1.. run return run tellraw @s")
    assert "execute store result storage realms:drops night int 1 run scoreboard players get #night dr" in start


def test_announcements_name_the_place_and_never_spread_bold():
    for path in FUNCTIONS:
        for line in FILES[path].splitlines():
            if line.startswith("tellraw @a ") or " run tellraw @a " in line:
                parts = json.loads(line[line.index("tellraw @a ") + len("tellraw @a "):])
                assert parts[0] == "" and parts[1] == drops.HEAD, f"{path}: {line}"
    assert "spot.y" in fn("found") and "spot.x" in fn("found") and "spot.z" in fn("found")
    assert "bossbar set realms:drop players @a" in fn("found")


def test_help_lists_every_staff_command():
    help_ = fn("help")
    assert help_.count("suggest_command") == len(drops.HELP)
    for cmd, _ in drops.HELP:
        assert f"/function realms:drops/{cmd}" in help_


# ---------------------------------------------------------------- the VPS scripts


DEPLOY = REPO.root / "deploy"
SCRIPT = "realms-drops.sh"
UNITS = ["realms-drops.service", "realms-drops.timer"]


@pytest.mark.parametrize("name", [SCRIPT, *UNITS])
def test_deploy_files_are_plain_ascii_with_lf(name):
    data = (DEPLOY / name).read_bytes()
    assert data.isascii() and b"\r" not in data


def test_the_script_is_posix_sh_and_reads_no_secret():
    text = (DEPLOY / SCRIPT).read_text()
    assert text.startswith("#!/bin/sh\n") and "set -eu" in text
    assert ". \"$ENV_FILE\"" not in text and "rcon.password" not in text and "WEBHOOK" not in text
    assert set(re.findall(r"\$\(setting (\w+)", text)) == {"REPO_DIR", "LIVE_DIR"}
    assert 'python3 -B "$TOOL" commands "$WORLD"' in text and "WORLD=$LIVE_DIR/server/world" in text
    for unit in UNITS:
        assert unit in text
    shell = shutil.which("dash")
    if shell:
        subprocess.run([shell, "-n", str(DEPLOY / SCRIPT)], check=True)


def test_units_run_the_script_as_realms_every_ten_minutes():
    service = (DEPLOY / "realms-drops.service").read_text()
    assert "User=realms" in service and "ExecStart=/bin/sh /srv/realms/repo/deploy/realms-drops.sh\n" in service
    timer = (DEPLOY / "realms-drops.timer").read_text()
    assert f"OnCalendar=*-*-* *:00/{drops.SLOT_MINUTES}:30" in timer
