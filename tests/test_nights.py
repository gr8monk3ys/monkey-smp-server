"""monkey-nights: the launch night's grace period and build battle on a timer."""
import nights

import datapacks

FN = "data/monkey/function/nights"


def test_registered_and_clean():
    assert "nights" in datapacks.GENERATORS
    files = {f"monkey-nights/{k}": v for k, v in nights.pack_files().items()}
    assert datapacks.problems(files) == []


def test_phase_lengths():
    f = nights.pack_files()
    assert "scoreboard players set #left nt.timer 5400" in f[f"{FN}/grace/start.mcfunction"]   # 90 min
    assert "scoreboard players set #left nt.timer 10800" in f[f"{FN}/build/start.mcfunction"]  # 180 min


def test_grace_closes_and_opens_pvp_and_nether():
    f = nights.pack_files()
    for rule in ("pvp", "allow_entering_nether_using_portals"):
        assert f"gamerule {rule} false" in f[f"{FN}/grace/start.mcfunction"]
        assert f"gamerule {rule} true" in f[f"{FN}/grace/end.mcfunction"]
    assert "function monkey:nights/build/start" in f[f"{FN}/grace/end.mcfunction"]


def test_every_step_is_guarded_by_its_phase():
    """The VPS clock and the in-game countdown both send the end steps: only the first may act."""
    f = nights.pack_files()
    first = {name: f[f"{FN}/{name}.mcfunction"].splitlines()[2] for name in
             ("grace/start", "grace/end", "build/start", "build/end")}
    assert first["grace/start"].startswith("execute if score #phase nt.state matches 1.. run return run")
    assert first["build/start"].startswith("execute if score #phase nt.state matches 1.. run return run")
    assert first["grace/end"].startswith("execute unless score #phase nt.state matches 1 run return run")
    assert first["build/end"].startswith("execute unless score #phase nt.state matches 2 run return run")


def test_every_entry_step_sets_up_first():
    """An empty server doesn't tick, so the load tag may not have run when the VPS sends a step."""
    f = nights.pack_files()
    for name in ("grace/start", "grace/end", "build/start", "build/end", "stop"):
        assert f[f"{FN}/{name}.mcfunction"].splitlines()[1].startswith("function monkey:nights/load")
    assert f[f"{FN}/minutes.mcfunction"].splitlines()[0].startswith("function monkey:nights/load")
