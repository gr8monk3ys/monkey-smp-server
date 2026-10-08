"""Load-test an installed server package with Carpet fake players, and profile it.

  python tools/loadtest.py C:/temp/realms-test/TheRealms-Server --carpet C:/Downloads/fabric-carpet-26.3.jar
      Starts the server in that folder (an unzipped release installed once, e.g. by tests/smoke.ps1, so it
      has its own ports and a world), spawns --players fake players with Carpet over RCON, waits --warmup
      seconds, then samples `tick query` every 10 s for --minutes while Java Flight Recorder records CPU
      samples. Writes <folder>/loadtest/<name>/: summary.json, samples.jsonl, profile.txt (where the main
      thread spent that window) and server.log. Then stops the server and takes Carpet out again.

  Scenarios (--scenario):
      still    players stand on the ground: the steady cost of having them online
      walk     players sprint and jump in a straight line: they load and generate chunks as they go
      explore  players are teleported outward along spokes every 5 s: worst case, all new terrain

  --without SLUG [SLUG ...] moves those mods (manifest slugs) out of server/mods for the run and puts them
  back afterwards, to measure what a mod costs.

Use a throwaway copy: fake players leave player data behind, and walk/explore generate terrain, so later
runs on the same world measure something different. Carpet is not part of the pack; download the Fabric
build for the pack's Minecraft version from https://modrinth.com/mod/carpet.
"""
import argparse
import contextlib
import json
import math
import re
import shutil
import socket
import statistics
import struct
import subprocess
import sys
import time
import zipfile
from collections import Counter
from datetime import datetime
from pathlib import Path

SAMPLE_EVERY_S = 10
FORMATTING = re.compile("\u00a7.")
# Mixin handlers carry the mod id in their name: handler$ben000$fabric-biome-api-v1$finalizeWorldGen.
MIXIN = re.compile(r"\$[a-z]{3}\d{3}\$([A-Za-z0-9_.-]+)\$")
VANILLA = ("net.minecraft.", "com.mojang.", "java.", "javax.", "jdk.", "sun.", "it.unimi.", "com.google.",
           "io.netty.", "org.slf4j.", "org.apache.", "net.fabricmc.loader.", "org.spongepowered.", "org.objectweb.")


class Rcon:
    def __init__(self, port: int, password: str):
        self.sock = socket.create_connection(("127.0.0.1", port), timeout=300)
        self.id = 0
        self._send(3, password)
        if self._recv()[0] == -1:
            raise SystemExit("RCON login failed: check rcon.password in server.properties")

    def _send(self, kind: int, body: str):
        self.id += 1
        data = struct.pack("<ii", self.id, kind) + body.encode() + b"\x00\x00"
        self.sock.sendall(struct.pack("<i", len(data)) + data)

    def _recv(self) -> tuple[int, str]:
        data = self._exact(struct.unpack("<i", self._exact(4))[0])
        return struct.unpack("<i", data[:4])[0], data[8:-2].decode(errors="replace")

    def _exact(self, n: int) -> bytes:
        buf = b""
        while len(buf) < n:
            chunk = self.sock.recv(n - len(buf))
            if not chunk:
                raise ConnectionError("RCON connection closed")
            buf += chunk
        return buf

    def cmd(self, command: str) -> str:
        self._send(2, command)
        return FORMATTING.sub("", self._recv()[1])


def read_properties(path: Path) -> dict[str, str]:
    props = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.startswith("#"):
            key, value = line.split("=", 1)
            props[key] = value
    return props


def parse_tick_query(text: str) -> dict:
    """mspt_avg, p50, p95, p99 (ms) from the reply to `tick query`; {} if it has none."""
    row = {}
    if m := re.search(r"Average time per tick: ([\d.]+)ms", text):
        row["mspt_avg"] = float(m.group(1))
    if m := re.search(r"P50: ([\d.]+)ms P95: ([\d.]+)ms P99: ([\d.]+)ms", text):
        row["p50"], row["p95"], row["p99"] = map(float, m.groups())
    return row


def summarize(rows: list[dict]) -> dict:
    avg = [r["mspt_avg"] for r in rows if "mspt_avg" in r]
    if not avg:
        return {"samples": 0}
    mean = statistics.fmean(avg)
    p50 = [r["p50"] for r in rows if "p50" in r]
    return {"samples": len(avg), "mspt_mean": round(mean, 1), "mspt_median": round(statistics.median(avg), 1),
            "tps": round(min(20.0, 1000 / mean), 1), "samples_over_50ms": sum(v > 50 for v in avg),
            # the typical tick, which a few multi-second stalls (chunk generation, saving) don't skew
            "p50_median": round(statistics.median(p50), 1) if p50 else None,
            "p95_max": max((r["p95"] for r in rows if "p95" in r), default=None),
            "p99_max": max((r["p99"] for r in rows if "p99" in r), default=None)}


def owner(frames: list[str]) -> str:
    """Which mod's code a stack is running: the first mixin handler or non-vanilla class from the top. Fabric API
    hooks are skipped: they wrap vanilla code (every command passes through fabric-entity-events-v1)."""
    for frame in frames:
        if m := MIXIN.search(frame):
            if m.group(1).startswith("fabric-"):
                continue
            return m.group(1)
        if not frame.startswith(VANILLA):
            return ".".join(frame.split(".")[:3])
    return "minecraft"


def read_samples(lines, start: datetime, end: datetime, thread: str = "Server thread"):
    """Stack traces (top frame first, methods without arguments) of `thread` from `jfr print` text output,
    for samples taken between start and end (local time)."""
    when, name, frames, in_stack = None, None, [], False
    for line in lines:
        line = line.strip()
        if line.startswith("startTime = "):
            m = re.match(r"startTime = ([\d:.]+) \((\d{4}-\d{2}-\d{2})\)", line)
            when = datetime.fromisoformat(f"{m.group(2)}T{m.group(1)}") if m else None
        elif line.startswith("sampledThread = "):
            name = line.split('"')[1]
        elif line == "stackTrace = [":
            frames, in_stack = [], True
        elif in_stack and line == "]":
            in_stack = False
            if name == thread and when and start <= when <= end:
                yield frames
        elif in_stack and line != "...":
            frames.append(line.split("(", 1)[0])


def profile_report(stacks) -> str:
    total, top, owners, commands, advancements = 0, Counter(), Counter(), 0, 0
    for frames in stacks:
        total += 1
        if frames:
            top[frames[0]] += 1
        owners[owner(frames)] += 1
        if any(f.startswith("net.minecraft.commands.") for f in frames):
            commands += 1
            advancements += any("AdvancementRewards" in f for f in frames)
    if not total:
        return "no main-thread samples in the measured window\n"

    def pct(n):
        return f"{n * 100 / total:5.1f}%"
    out = [f"main-thread samples: {total}",
           f"{pct(commands)}  running commands (datapack functions, /commands); "
           f"{pct(advancements)} started by advancement rewards",
           "", "== first mod on the stack"]
    out += [f"{pct(n)}  {name}" for name, n in owners.most_common(15)]
    out += ["", "== top frames (self time)"]
    out += [f"{pct(n)}  {name}" for name, n in top.most_common(25)]
    return "\n".join(out) + "\n"


PERF_LINE = re.compile(r"^\[(\d+)\][\s|]*(.+?)\((\d+)/(\d+)\) - ([\d.]+)%/([\d.]+)%")


def perf_report(profiling_txt: str, top: int = 25) -> str:
    """The costliest parts of a `perf` report (server/profiling.txt), as % of the whole tick: the tick's main
    sections, the entity types and the datapack functions."""
    rows = [(int(m[1]), m[2].strip(), int(m[4]), float(m[6]))
            for m in map(PERF_LINE.match, profiling_txt.splitlines()) if m]
    if not rows:
        return "no profile sections found\n"
    out = ["== tick (% of the whole tick, how many per tick)"]
    out += [f"{share:5.1f}%  {'  ' * depth}{name} ({per})" for depth, name, per, share in rows
            if depth <= 5 and share >= 1]
    # An entity type's section sits right under "entities > tick" and is named like minecraft:creeper.
    entities = sorted(((share, name, per) for depth, name, per, share in rows
                       if depth == 6 and re.fullmatch(r"[a-z0-9_.-]+:[a-z0-9_/.-]+", name)), reverse=True)
    out += ["", "== entity types (% of the whole tick, how many tick per tick)"]
    out += [f"{share:5.1f}%  {name} ({per})" for share, name, per in entities[:top]] or ["(none)"]
    functions = sorted(((share, name) for _, name, _, share in rows if name.startswith("function ")), reverse=True)
    out += ["", "== datapack functions (% of the whole tick)"]
    out += [f"{share:5.1f}%  {name[len('function '):]}" for share, name in functions[:top]] or ["(none)"]
    return "\n".join(out) + "\n"


def spawn_players(rcon: Rcon, names: list[str], scenario: str, radius: int):
    for i, name in enumerate(names):
        angle = 2 * math.pi * i / len(names)
        x, z = (0, 0) if scenario == "explore" else (radius * math.cos(angle), radius * math.sin(angle))
        rcon.cmd(f"player {name} spawn at {x:.0f} 200 {z:.0f} facing {math.degrees(angle):.0f} 0 "
                 "in minecraft:overworld in survival")
        rcon.cmd(f"spreadplayers {x:.0f} {z:.0f} 0 1 false {name}")
        rcon.cmd(f"effect give {name} minecraft:resistance infinite 255 true")
        rcon.cmd(f"effect give {name} minecraft:saturation infinite 255 true")
        if scenario == "walk":
            for action in ("sprint", "move forward", "jump continuous"):
                rcon.cmd(f"player {name} {action}")
        time.sleep(0.5)


def find_one(root: Path, pattern: str) -> Path:
    found = sorted(root.glob(pattern))
    if not found:
        raise SystemExit(f"{pattern} not found under {root}: is this an installed server package?")
    return found[0]


def launch_arguments(root: Path, memory_gb: int) -> list[str]:
    """The JVM and server arguments the package's own launcher uses (Get-LaunchArguments in Realms.psm1)."""
    script = (f"Import-Module '{root / 'realms' / 'Realms.psm1'}'; "
              f"$ctx = New-RealmsContext -Root '{root}' -RealmsDir '{root / 'realms'}' -NonInteractive; "
              f"Get-LaunchArguments -Manifest $ctx.Manifest -MemoryGB {memory_gb}")
    out = subprocess.run(["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script],
                         capture_output=True, text=True, check=True).stdout
    return [line for line in out.splitlines() if line.strip()]


def wait_for_rcon(proc: subprocess.Popen, port: int, password: str, timeout_s: int) -> Rcon:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        if proc.poll() is not None:
            raise SystemExit(f"the server exited with code {proc.returncode} while starting; see server.log")
        try:
            rcon = Rcon(port, password)
            rcon.cmd("list")
            return rcon
        except (OSError, ConnectionError):
            time.sleep(5)
    raise SystemExit(f"RCON did not answer within {timeout_s} s")


def planned_parking(root: Path, slugs: list[str], parked: Path) -> list[tuple[Path, Path]]:
    """(jar in server/mods, where it waits during the run) for each mod slug to leave out."""
    manifest = json.loads((root / "realms" / "manifest.json").read_text(encoding="utf-8"))
    files = {m["slug"]: m["file"] for m in manifest.get("mods", [])}
    unknown = [s for s in slugs if s not in files]
    if unknown:
        raise SystemExit(f"not mods in the manifest: {', '.join(unknown)}")
    return [(root / "server" / "mods" / files[s], parked / files[s]) for s in slugs]


def main(argv=None):
    ap = argparse.ArgumentParser(description=(__doc__ or "").split("\n\n")[0])
    ap.add_argument("root", type=Path, help="an installed server package (the folder with realms/ and server/)")
    ap.add_argument("--carpet", type=Path, required=True, help="the Carpet mod jar for the pack's Minecraft version")
    ap.add_argument("--players", type=int, default=25)
    ap.add_argument("--scenario", choices=("still", "walk", "explore"), default="still")
    ap.add_argument("--minutes", type=float, default=5)
    ap.add_argument("--warmup", type=int, default=120, help="seconds between spawning players and measuring")
    ap.add_argument("--memory-gb", type=int, default=8)
    ap.add_argument("--radius", type=int, default=500, help="still/walk: players start this far from 0,0")
    ap.add_argument("--without", nargs="*", default=[], metavar="SLUG", help="mods to leave out for this run")
    ap.add_argument("--keep-recording", action="store_true",
                    help="keep rec.jfr (the whole run, startup included) to dig into a stall with `jfr print`")
    ap.add_argument("--name", help="results folder name (default: scenario-players[-without-...]-time)")
    args = ap.parse_args(argv)

    root = args.root.resolve()
    server = root / "server"
    props = read_properties(server / "server.properties")
    port, rcon_port = int(props["server-port"]), int(props["rcon.port"])
    for p in (port, rcon_port):
        with socket.socket() as s:
            if s.connect_ex(("127.0.0.1", p)) == 0:
                raise SystemExit(f"something already listens on port {p}; stop it or use another installed copy")
    name = args.name or "-".join([args.scenario, str(args.players)] + (["without", *args.without] if args.without
                                                                         else []) + [time.strftime("%Y%m%d-%H%M")])
    out = root / "loadtest" / name
    out.mkdir(parents=True, exist_ok=True)
    java = find_one(root, "java/*/bin/java.exe")
    jfr = find_one(root, "java/*/bin/jfr.exe")
    jvm = launch_arguments(root, args.memory_gb)
    recording = out / "rec.jfr"
    # JFR writes its chunks here as it goes, so a server that hangs and gets killed still leaves a readable trail.
    repository = out / "jfr-chunks"
    repository.mkdir(exist_ok=True)

    carpet = server / "mods" / args.carpet.name
    added_carpet = not carpet.exists()
    if added_carpet:
        shutil.copy2(args.carpet, carpet)
    moves = planned_parking(root, args.without, root / "loadtest" / "parked")
    proc = None
    try:
        for src, dst in moves:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(src, dst)
        log = open(out / "server.log", "w", encoding="utf-8")
        cmd = [str(java), f"-XX:FlightRecorderOptions=repository={repository}",
               f"-XX:StartFlightRecording=settings=profile,filename={recording},dumponexit=true", *jvm]
        proc = subprocess.Popen(cmd, cwd=server, stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT)
        print(f"started java (pid {proc.pid}); waiting for RCON on {rcon_port}", flush=True)
        rcon = wait_for_rcon(proc, rcon_port, props["rcon.password"], 900)
        names = [f"Load{i:02d}" for i in range(args.players)]
        spawn_players(rcon, names, args.scenario, args.radius)
        print(rcon.cmd("list"), flush=True)
        print(f"warming up {args.warmup} s", flush=True)
        time.sleep(args.warmup)

        start = datetime.now()
        end_at = time.time() + args.minutes * 60
        perf_at = start.timestamp() + args.minutes * 30  # Minecraft's own 10 s profile, halfway through
        rows, last = [], 0.0
        with open(out / "samples.jsonl", "w", encoding="utf-8") as samples:
            while time.time() < end_at:
                if args.scenario == "explore":
                    far = 32 + 5.6 * (time.time() - start.timestamp())  # sprinting pace (5.6 blocks/s)
                    for i, n in enumerate(names):
                        a = 2 * math.pi * i / len(names)
                        rcon.cmd(f"tp {n} {far * math.cos(a):.1f} 200 {far * math.sin(a):.1f}")
                if perf_at and time.time() >= perf_at:
                    rcon.cmd("perf start")  # names each datapack function; JFR can't
                    perf_at = 0
                if time.time() - last >= SAMPLE_EVERY_S:
                    row = {"t": round(time.time(), 1), **parse_tick_query(rcon.cmd("tick query"))}
                    rows.append(row)
                    samples.write(json.dumps(row) + "\n")
                    samples.flush()
                    last = time.time()
                    print(time.strftime("%H:%M:%S"), row, flush=True)
                time.sleep(5 if args.scenario == "explore" else 1)
        end = datetime.now()
        for n in names:
            rcon.cmd(f"player {n} kill")
        with contextlib.suppress(ConnectionError):  # the server can close RCON before it replies
            rcon.cmd("stop")
        proc.wait(timeout=300)
    finally:
        if proc and proc.poll() is None:
            proc.kill()
            print(f"killed the server; JFR chunks (with periodic thread dumps) are in {repository}", flush=True)
            proc.wait()
        if added_carpet:
            carpet.unlink(missing_ok=True)
        for src, dst in moves:
            if dst.exists():
                shutil.move(dst, src)

    for report in sorted((server / "debug").rglob("*.zip")):
        if report.stat().st_mtime >= start.timestamp():
            with zipfile.ZipFile(report) as z:
                text = next((z.read(n).decode(errors="replace") for n in z.namelist()
                             if n.endswith("server/profiling.txt")), "")
            (out / "perf.txt").write_text(perf_report(text), encoding="utf-8")
            shutil.move(report, out / report.name)
    log_text = (out / "server.log").read_text(encoding="utf-8", errors="replace")
    summary = {"scenario": args.scenario, "players": args.players, "without": args.without,
               "memory_gb": args.memory_gb, "minutes": args.minutes, "warmup_s": args.warmup,
               **summarize(rows),
               "command_limit_hits": log_text.count("Command execution stopped due to limit"),
               "cant_keep_up_warnings": log_text.count("Can't keep up!")}
    if recording.exists():
        with subprocess.Popen([str(jfr), "print", "--events", "jdk.ExecutionSample", "--stack-depth", "96",
                               str(recording)], stdout=subprocess.PIPE, text=True, encoding="utf-8",
                              errors="replace") as printer:
            (out / "profile.txt").write_text(profile_report(read_samples(printer.stdout, start, end)),
                                             encoding="utf-8")
        if not args.keep_recording:
            recording.unlink()
        shutil.rmtree(repository, ignore_errors=True)
    (out / "summary.json").write_text(json.dumps(summary, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=1))
    print(f"results: {out}")


if __name__ == "__main__":
    sys.exit(main())
