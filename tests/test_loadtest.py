import json
from datetime import datetime

import pytest

import loadtest

TICK_QUERY = """The game is running normally
Target tick rate: 20.0 per second.
Average time per tick: 121.6ms (Target: 50.0ms)
Percentiles: P50: 120.4ms P95: 137.8ms P99: 189.4ms, sample: 100"""


def test_parse_tick_query():
    assert loadtest.parse_tick_query(TICK_QUERY) == {"mspt_avg": 121.6, "p50": 120.4, "p95": 137.8, "p99": 189.4}
    assert loadtest.parse_tick_query("Unknown command") == {}


def test_summarize():
    rows = [{"mspt_avg": 40.0, "p95": 45.0, "p99": 60.0}, {"mspt_avg": 60.0, "p95": 70.0, "p99": 90.0}, {}]
    rows[0]["p50"], rows[1]["p50"] = 30.0, 50.0
    assert loadtest.summarize(rows) == {"samples": 2, "mspt_mean": 50.0, "mspt_median": 50.0, "tps": 20.0,
                                        "samples_over_50ms": 1, "p50_median": 40.0, "p95_max": 70.0, "p99_max": 90.0}
    assert loadtest.summarize([]) == {"samples": 0}
    assert loadtest.summarize([{"mspt_avg": 250.0}])["tps"] == 4.0


@pytest.mark.parametrize(("frames", "want"), [
    (["net.minecraft.server.level.ServerLevel.modifyExpressionValue$deg000$lithium$lithiumRandomTick",
      "net.minecraft.server.level.ServerLevel.tick"], "lithium"),
    (["java.util.HashMap.getNode", "com.ishland.c2me.rewrites.chunksystem.Holder.get",
      "net.minecraft.server.MinecraftServer.tickServer"], "com.ishland.c2me"),
    (["java.util.HashMap.getNode", "net.minecraft.commands.Commands.executeCommandInContext"], "minecraft"),
    (["net.minecraft.commands.execution.CommandQueueEntry.wrapMethod$bim000$fabric-entity-events-v1$onExecute",
      "net.minecraft.commands.Commands.executeCommandInContext"], "minecraft"),
    ([], "minecraft"),
])
def test_owner(frames, want):
    assert loadtest.owner(frames) == want


def jfr_event(time, thread, frames):
    lines = ["jdk.ExecutionSample {", f"  startTime = {time} (2026-10-06)",
             f'  sampledThread = "{thread}" (javaThreadId = 50)', '  state = "STATE_RUNNABLE"', "  stackTrace = ["]
    lines += [f"    {f}(Args) line: 1" for f in frames] + ["    ...", "  ]", "}", ""]
    return lines


def test_read_samples_keeps_the_main_thread_inside_the_window():
    commands = ["net.minecraft.commands.execution.tasks.BuildContexts.execute",
                "net.minecraft.advancements.AdvancementRewards.grant"]
    text = (jfr_event("22:00:00.000", "Server thread", ["early.Frame.run"])
            + jfr_event("22:05:00.100", "Server thread", commands)
            + jfr_event("22:05:00.200", "c2me-worker-1", ["worker.Frame.run"])
            + jfr_event("22:06:00.000", "Server thread", ["java.util.HashMap.getNode"])
            + jfr_event("22:20:00.000", "Server thread", ["late.Frame.run"]))
    stacks = list(loadtest.read_samples(text, datetime(2026, 10, 6, 22, 5), datetime(2026, 10, 6, 22, 10)))
    assert stacks == [commands, ["java.util.HashMap.getNode"]]

    report = loadtest.profile_report(stacks)
    assert "main-thread samples: 2" in report
    assert " 50.0%  running commands (datapack functions, /commands);  50.0% started by advancement rewards" in report
    assert " 50.0%  net.minecraft.commands.execution.tasks.BuildContexts.execute" in report


def test_profile_report_without_samples():
    assert loadtest.profile_report([]) == "no main-thread samples in the measured window\n"


def test_spark_url():
    log = ("[04:30:01] [spark-worker-pool-1-thread-1/INFO]: [spark] Profiler stopped & upload complete!\n"
           "[04:30:02] [spark-worker-pool-1-thread-1/INFO]: https://spark.lucko.me/AbCdEf1234\n")
    assert loadtest.spark_url(log) == "https://spark.lucko.me/AbCdEf1234"
    assert loadtest.spark_url("https://spark.lucko.me/old1 then https://spark.lucko.me/new2") == \
        "https://spark.lucko.me/new2"
    assert loadtest.spark_url("Done (12.3s)!") == ""
    # spark also points at its docs; those are never the profile.
    assert loadtest.spark_url("see https://spark.lucko.me/docs/misc/Using-async-profiler") == ""
    assert loadtest.spark_url("https://spark.lucko.me/docs") == ""
    assert loadtest.spark_url("https://spark.lucko.me/AbCdEf1234\nhttps://spark.lucko.me/docs") == \
        "https://spark.lucko.me/AbCdEf1234"
    # What spark 1.10.187 logged on 26.3 after `spark profiler stop` (the first VPS load test).
    stop = ("[05:38:22] [spark-worker-pool-1-thread-3/INFO]: See here for more information: "
            "https://spark.lucko.me/docs/misc/Java-agent-warning\n")
    assert loadtest.spark_url(stop) == ""
    stop += "[05:38:27] [spark-worker-pool-1-thread-3/INFO]: System chat: https://spark.lucko.me/fyE6dSvpV0\n"
    assert loadtest.spark_url(stop) == "https://spark.lucko.me/fyE6dSvpV0"


def test_wait_for_spark_url_reads_only_new_lines(tmp_path):
    log = tmp_path / "server.log"
    log.write_text("https://spark.lucko.me/old1\n", encoding="utf-8")
    seen = log.stat().st_size
    assert loadtest.wait_for_spark_url(log, seen, timeout_s=0) == ""
    with open(log, "a", encoding="utf-8") as f:
        f.write("[spark] see https://spark.lucko.me/docs/misc/Using-async-profiler\n")
    assert loadtest.wait_for_spark_url(log, seen, timeout_s=0) == ""  # keeps waiting for the upload
    with open(log, "a", encoding="utf-8") as f:
        f.write("[spark] https://spark.lucko.me/new2\n")
    assert loadtest.wait_for_spark_url(log, seen, timeout_s=0) == "https://spark.lucko.me/new2"


def test_planned_parking(tmp_path):
    (tmp_path / "realms").mkdir()
    manifest = {"mods": [{"slug": "silvers_strength-smp-season-4", "file": "strength.jar"}]}
    (tmp_path / "realms" / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    parked = tmp_path / "loadtest" / "parked"
    assert loadtest.planned_parking(tmp_path, ["silvers_strength-smp-season-4"], parked) == [
        (tmp_path / "server" / "mods" / "strength.jar", parked / "strength.jar")]
    with pytest.raises(SystemExit, match="not mods in the manifest: nope"):
        loadtest.planned_parking(tmp_path, ["nope"], parked)


PROFILING_TXT = """--- BEGIN PROFILE DUMP ---

[00] tick(201/1) - 95.00%/95.00%
[01] |   levels(201/1) - 99.00%/94.00%
[02] |   |   ServerLevel[world] minecraft:overworld(201/1) - 99.00%/93.00%
[03] |   |   |   tick(201/1) - 99.00%/92.00%
[04] |   |   |   |   entities(201/1) - 60.00%/55.00%
[05] |   |   |   |   |   tick(330000/1640) - 95.00%/52.00%
[06] |   |   |   |   |   |   minecraft:creeper(43000/215) - 15.00%/7.70%
[07] |   |   |   |   |   |   |   ai(43000/215) - 37.00%/2.90%
[06] |   |   |   |   |   |   naturalist:whale(1200/6) - 2.00%/1.00%
[04] |   |   |   |   scheduledFunctions(201/1) - 17.00%/16.00%
[05] |   |   |   |   |   function incendium:clocks/main(201/1) - 43.00%/7.40%
[06] |   |   |   |   |   |   prepare execute as @e run function incendium:x(201/1) - 19.00%/1.40%
[05] |   |   |   |   |   function nullscape:tick(201/1) - 2.00%/0.57%

--- END PROFILE DUMP ---
"""


def test_perf_report():
    report = loadtest.perf_report(PROFILING_TXT)
    sections = dict(part.split("\n", 1) for part in report.split("\n\n"))
    tick = sections["== tick (% of the whole tick, how many per tick)"]
    assert "  7.4%            function incendium:clocks/main (1)" in tick
    assert sections["== entity types (% of the whole tick, how many tick per tick)"].splitlines() == [
        "  7.7%  minecraft:creeper (215)", "  1.0%  naturalist:whale (6)"]
    assert sections["== datapack functions (% of the whole tick)"].splitlines() == [
        "  7.4%  incendium:clocks/main", "  0.6%  nullscape:tick"]
    assert loadtest.perf_report("nothing here") == "no profile sections found\n"
