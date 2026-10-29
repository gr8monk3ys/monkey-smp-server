"""Every fast check a change needs before review, in one place: CI runs it and so does a maintainer.

    python tools/checks.py               every check this machine can run (a missing tool is skipped, and said)
    python tools/checks.py ruff pytest   only these
    python tools/checks.py --strict      a missing tool fails instead (CI)
    python tools/checks.py --list        the checks and what each runs
    python tools/checks.py --root DIR    check another checkout (tools/local_ci.py checks a PR's head this way)
    python tools/checks.py --boots       which of CI's boot jobs this run needs (ci.yml; see boots())

The checks: ruff, pytest, validate.py, the generated packs (datapacks.py --check), `dash -n` on every POSIX sh
script, Pester, and the site (in site/, with bun: install from the lockfile, lint, typecheck and build, then
tools/site_links.py --built checks the built pages against site/config.json). None of them boots the server;
that is CI's boot jobs and tests/smoke.ps1. On Windows, Git for Windows' own dash is used when dash isn't on
PATH, for `dash -n` and for the pytest tests that run deploy/lib.sh under dash. Exit status 1 if any check failed.
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from repo import REPO

WINDOWS = os.name == "nt"


@dataclass(frozen=True)
class Check:
    name: str
    needs: str                                   # the program it runs, "" for this Python, "module:X" for a module
    command: Callable[[Path], list[list[str]]]   # the commands, given the checkout
    about: str
    cwd: str = ""                                # where they run, from the checkout's root


def sh_scripts(root: Path) -> list[Path]:
    """The scripts that must stay POSIX sh (CLAUDE.md): the deploy scripts and the host's launchers."""
    found = [*sorted((root / "deploy").glob("*.sh")), *sorted((root / "package").glob("*.sh")),
             root / "package" / "realms" / "realms.sh", root / "package" / "Start Server.command"]
    return [p for p in found if p.is_file()]


def pester_files(root: Path) -> list[str]:
    # Player.Tests.ps1 covers the Windows-only player installer; CI runs it on Windows only.
    names = ["tests/Realms.Tests.ps1", *(["tests/Player.Tests.ps1"] if WINDOWS else [])]
    return [n for n in names if (root / n).is_file()]


def pester(root: Path) -> list[list[str]]:
    files = ", ".join(f"'{n}'" for n in pester_files(root))
    script = (f"Import-Module Pester -MinimumVersion 5.5; $r = Invoke-Pester -Path {files} -Output Minimal "
              "-PassThru; if ($r.FailedCount -or $r.Result -ne 'Passed') { exit 1 }")
    return [[shell, "-NoProfile", "-NonInteractive", "-Command", script] for shell in powershells()]


def site() -> list[list[str]]:
    """The site's own checks, run in site/ (site/README.md), then its built pages against config.json."""
    return [["bun", "install", "--frozen-lockfile"],
            *(["bun", "run", script] for script in ("lint", "typecheck", "build")),
            [sys.executable, "-X", "utf8", "../tools/site_links.py", "--check", "--built", "out"]]


# What to say when a program a check runs isn't installed.
WHERE = {"bun": "bun, which builds the site (https://bun.sh)"}


def powershells() -> list[str]:
    """Every PowerShell the tests must pass on here (ADR-0003): on Windows, Windows PowerShell 5.1 and pwsh too
    when it is installed; elsewhere pwsh."""
    return ["powershell", *(["pwsh"] if shutil.which("pwsh") else [])] if WINDOWS else ["pwsh"]


CHECKS = (
    Check("ruff", "module:ruff", lambda root: [[sys.executable, "-m", "ruff", "check", "tools", "tests"]],
          "lint the tools and tests"),
    Check("pytest", "module:pytest", lambda root: [[sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider"]],
          "the unit tests"),
    Check("validate", "", lambda root: [[sys.executable, "-X", "utf8", "tools/validate.py"]],
          "the manifest, package, client pack and site agree"),
    Check("datapacks", "", lambda root: [[sys.executable, "-X", "utf8", "tools/datapacks.py", "--check"]],
          "the committed generated packs match their tables"),
    Check("sh", "dash", lambda root: [["dash", "-n", str(p)] for p in sh_scripts(root)],
          "dash -n on every POSIX sh script"),
    Check("pester", "powershell", pester, "the PowerShell unit tests (Pester 5)"),
    Check("site", "bun", lambda root: site(), "the site: install, lint, typecheck, build, and its built pages", "site"),
)
NAMES = [c.name for c in CHECKS]


def git_dash_dir() -> Path | None:
    """Git for Windows' usr/bin, which has dash, found from git itself (None when there isn't one)."""
    git = shutil.which("git")
    if not WINDOWS or not git:
        return None
    for up in Path(git).resolve().parents:
        if (up / "usr" / "bin" / "dash.exe").is_file():
            return up / "usr" / "bin"
    return None


def environment() -> dict[str, str]:
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    if not shutil.which("dash") and (extra := git_dash_dir()):
        env["PATH"] = os.pathsep.join([env.get("PATH", ""), str(extra)])
    return env


def missing(check: Check, env: dict[str, str]) -> str:
    """What this machine lacks to run the check ("" when nothing). A module check runs `python -m X`, so only
    this Python having the module counts, not a program of that name on PATH."""
    if check.needs == "":
        return ""
    if check.needs.startswith("module:"):
        name = check.needs.removeprefix("module:")
        found = subprocess.run([sys.executable, "-c", f"import {name}"], env=env, capture_output=True)
        return "" if found.returncode == 0 else f"the {name} module"
    if check.needs == "powershell":
        lacking = [s for s in powershells() if not shutil.which(s, path=env.get("PATH")) or not _has_pester(s)]
        return f"Pester 5.5+ in {' and '.join(lacking)}" if lacking else ""
    return "" if shutil.which(check.needs, path=env.get("PATH")) else WHERE.get(check.needs, check.needs)


def _has_pester(shell: str) -> bool:
    ask = "if (Get-Module -ListAvailable Pester | Where-Object Version -ge '5.5') { exit 0 } else { exit 1 }"
    found = subprocess.run([shell, "-NoProfile", "-NonInteractive", "-Command", ask], capture_output=True)
    return found.returncode == 0


@dataclass(frozen=True)
class Result:
    name: str
    state: str     # passed, failed or skipped
    seconds: float
    note: str = ""


def run(names: list[str], root: Path, strict: bool, out=sys.stdout) -> list[Result]:
    env = environment()
    results = []
    for check in (c for c in CHECKS if c.name in names):
        if needs := missing(check, env):
            results.append(Result(check.name, "failed" if strict else "skipped", 0.0, f"needs {needs}"))
            print(f"== {check.name}: {results[-1].state} (needs {needs})", file=out, flush=True)
            continue
        print(f"== {check.name}: {check.about}", file=out, flush=True)
        began, ok = time.monotonic(), True
        for command in check.command(root):
            # Windows looks a program up on this process's PATH, not the one in env, so find it here.
            program = shutil.which(command[0], path=env.get("PATH")) or command[0]
            try:
                done = subprocess.run([program, *command[1:]], cwd=root / check.cwd, env=env, stdout=subprocess.PIPE,
                                      stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace")
            except OSError as e:
                print(f"could not run {command[0]}: {e}", file=out, flush=True)
                ok = False
                continue
            if done.stdout:
                print(done.stdout.rstrip(), file=out, flush=True)
            ok = ok and done.returncode == 0
        results.append(Result(check.name, "passed" if ok else "failed", time.monotonic() - began))
    return results


def summary(results: list[Result]) -> str:
    """One line for a person or a commit status: failures first, then what was skipped."""
    failed = [r.name for r in results if r.state == "failed"]
    skipped = [r.name for r in results if r.state == "skipped"]
    head = f"failed: {', '.join(failed)}" if failed else "all passed"
    return head + (f"; skipped: {', '.join(skipped)}" if skipped else "")


# CI's boot jobs cost far more than these checks (Windows minutes count double), so a run boots only what its
# change can break. A path that starts with one of these needs the Linux boots (native and Docker) ...
SERVER_PATHS = ("package/", "tests/smoke.ps1", "tests/docker-smoke.sh", "tests/hosting-smoke.sh",
                ".github/workflows/ci.yml")
# ... and these also need the Windows boot (with PSScriptAnalyzer and the player installer's tests) and the
# hosting bundle it makes. The build (build.py and the repo.py it imports) makes the zip every boot unzips.
WINDOWS_PATHS = ("package/realms/realms.ps1", "package/realms/Realms.psm1", "package/realms/manifest.json",
                 "package/realms/pwsh.lock", "package/docker/", "player/", "tools/build.py", "tools/repo.py",
                 "tests/smoke.ps1", "tests/hosting-smoke.sh", "tests/Realms.Tests.ps1", "tests/Player.Tests.ps1",
                 "PSScriptAnalyzerSettings.psd1", ".github/workflows/ci.yml")
BOOT_LABEL = "boot"


def boots(event: str, ref: str, draft: bool, labels: list[str], changed: list[str] | None) -> dict[str, bool]:
    """Which boot jobs a CI run needs. Everything for a release tag, a manual run or a PR labelled `boot`;
    nothing for a draft PR; otherwise by what changed (None: unknown, so everything). A push to main boots on
    Linux only: its PR already booted on Windows when that was needed, and every release boots everywhere."""
    if event == "workflow_dispatch" or ref.startswith("refs/tags/") or BOOT_LABEL in labels:
        return {"linux": True, "windows": True}
    if event == "pull_request" and draft:
        return {"linux": False, "windows": False}
    if changed is None:
        linux = windows = True
    else:
        windows = any(p.startswith(WINDOWS_PATHS) or p.startswith("package/") and p.endswith(".bat")
                      for p in changed)
        linux = windows or any(p.startswith(SERVER_PATHS) for p in changed)
    return {"linux": linux, "windows": windows and event == "pull_request"}


def changed_paths(root: Path, base: str, head: str) -> list[str] | None:
    """The files a PR or push changed (from where it left base), or None when that can't be told: a new
    branch, a force push or a shallow clone."""
    if not base or set(base) == {"0"}:
        return None
    try:
        fork = subprocess.run(["git", "merge-base", base, head], cwd=root, check=True, capture_output=True,
                              text=True).stdout.strip()
        names = subprocess.run(["git", "diff", "--name-only", fork, head], cwd=root, check=True,
                               capture_output=True, text=True, encoding="utf-8").stdout
    except (OSError, subprocess.CalledProcessError):
        return None
    return names.splitlines()


def labels(given: str) -> list[str]:
    """The PR's label names from ci.yml's LABELS, a JSON list (a name can hold spaces); [] for a push."""
    try:
        names = json.loads(given or "[]")
    except ValueError:
        return []
    return [n for n in names if isinstance(n, str)] if isinstance(names, list) else []


def boot_plan(root: Path, env: dict[str, str]) -> str:
    """`linux=` and `windows=` lines for $GITHUB_OUTPUT, from the variables ci.yml's plan step sets."""
    plan = boots(env.get("EVENT", ""), env.get("REF", ""), env.get("DRAFT") == "true",
                 labels(env.get("LABELS", "")), changed_paths(root, env.get("BASE", ""), env.get("HEAD", "HEAD")))
    return "".join(f"{job}={str(on).lower()}\n" for job, on in plan.items())


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("checks", nargs="*", metavar="CHECK", help=" ".join(NAMES))
    parser.add_argument("--strict", action="store_true", help="a missing tool fails the check")
    parser.add_argument("--list", action="store_true", help="say what each check runs, run nothing")
    parser.add_argument("--root", type=Path, default=REPO.root, help="the checkout to check")
    parser.add_argument("--boots", action="store_true", help="print which boot jobs this CI run needs (ci.yml)")
    args = parser.parse_args(argv)
    if unknown := [n for n in args.checks if n not in NAMES]:
        parser.error(f"no check named {', '.join(unknown)} (the checks: {' '.join(NAMES)})")
    root = args.root.resolve()
    # The tools print what they like (Next's build prints check marks); a console that can't show a character
    # gets a stand-in rather than stopping the run.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(errors="replace")
    if args.boots:
        print(boot_plan(root, dict(os.environ)), end="")
        return 0
    if args.list:
        for check in CHECKS:
            print(f"{check.name:10} {check.about}")
        return 0
    results = run(args.checks or NAMES, root, args.strict)
    print()
    for r in results:
        print(f"{r.state:8} {r.name:10} {r.seconds:6.1f}s {r.note}".rstrip())
    print(summary(results))
    return 1 if any(r.state == "failed" for r in results) else 0


if __name__ == "__main__":
    sys.exit(main())
