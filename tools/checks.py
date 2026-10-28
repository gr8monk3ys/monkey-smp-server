"""Every fast check a change needs before review, in one place: CI runs it and so does a maintainer.

    python tools/checks.py               every check this machine can run (a missing tool is skipped, and said)
    python tools/checks.py ruff pytest   only these
    python tools/checks.py --strict      a missing tool fails instead (CI)
    python tools/checks.py --list        the checks and what each runs
    python tools/checks.py --root DIR    check another checkout (tools/local_ci.py checks a PR's head this way)
    python tools/checks.py --boots       which of CI's boot jobs this run needs (ci.yml; see boots())

The checks: ruff, pytest, validate.py, the generated packs (datapacks.py --check), `dash -n` on every POSIX sh
script, and Pester. None of them boots the server; that is CI's boot jobs and tests/smoke.ps1. On Windows,
Git for Windows' own dash is used when dash isn't on PATH, for `dash -n` and for the pytest tests that run
deploy/lib.sh under dash. Exit status 1 if any check failed.
"""
import argparse
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
    needs: str                                   # the program it runs, "" for this Python
    command: Callable[[Path], list[list[str]]]   # the commands, given the checkout
    about: str


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
    return [[powershell(), "-NoProfile", "-NonInteractive", "-Command", script]]


def powershell() -> str:
    """pwsh where it is installed; Windows PowerShell 5.1 otherwise (both must pass, ADR-0003)."""
    return "pwsh" if shutil.which("pwsh") or not WINDOWS else "powershell"


CHECKS = (
    Check("ruff", "", lambda root: [[sys.executable, "-m", "ruff", "check", "tools", "tests"]],
          "lint the tools and tests"),
    Check("pytest", "", lambda root: [[sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider"]],
          "the unit tests"),
    Check("validate", "", lambda root: [[sys.executable, "-X", "utf8", "tools/validate.py"]],
          "the manifest, package, client pack and site agree"),
    Check("datapacks", "", lambda root: [[sys.executable, "-X", "utf8", "tools/datapacks.py", "--check"]],
          "the committed generated packs match their tables"),
    Check("sh", "dash", lambda root: [["dash", "-n", str(p)] for p in sh_scripts(root)],
          "dash -n on every POSIX sh script"),
    Check("pester", "powershell", pester, "the PowerShell unit tests (Pester 5)"),
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


def available(check: Check, env: dict[str, str]) -> bool:
    if check.needs == "":
        return check.name != "ruff" or _has_module("ruff", env)
    program = powershell() if check.needs == "powershell" else check.needs
    return shutil.which(program, path=env.get("PATH")) is not None and (check.name != "pester" or _has_pester())


def _has_module(name: str, env: dict[str, str]) -> bool:
    found = subprocess.run([sys.executable, "-c", f"import {name}"], env=env, capture_output=True)
    return found.returncode == 0 or shutil.which(name, path=env.get("PATH")) is not None


def _has_pester() -> bool:
    ask = "if (Get-Module -ListAvailable Pester | Where-Object Version -ge '5.5') { exit 0 } else { exit 1 }"
    found = subprocess.run([powershell(), "-NoProfile", "-NonInteractive", "-Command", ask], capture_output=True)
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
        if not available(check, env):
            needs = "the ruff module" if check.name == "ruff" else ("Pester 5.5+" if check.name == "pester"
                                                                     else check.needs)
            results.append(Result(check.name, "failed" if strict else "skipped", 0.0, f"needs {needs}"))
            print(f"== {check.name}: {results[-1].state} (needs {needs})", file=out, flush=True)
            continue
        print(f"== {check.name}: {check.about}", file=out, flush=True)
        began, ok = time.monotonic(), True
        for command in check.command(root):
            done = subprocess.run(command, cwd=root, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                  text=True, encoding="utf-8", errors="replace")
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
SERVER_PATHS = ("package/", "tools/build.py", "tests/smoke.ps1", "tests/docker-smoke.sh", "tests/hosting-smoke.sh",
                ".github/workflows/ci.yml")
# ... and these also need the Windows boot (with PSScriptAnalyzer and the player installer's tests) and the
# hosting bundle it makes.
WINDOWS_PATHS = ("package/realms/realms.ps1", "package/realms/Realms.psm1", "package/realms/manifest.json",
                 "package/realms/pwsh.lock", "package/docker/", "player/", "tests/smoke.ps1", "tests/hosting-smoke.sh",
                 "tests/Realms.Tests.ps1", "tests/Player.Tests.ps1", "PSScriptAnalyzerSettings.psd1",
                 ".github/workflows/ci.yml")
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


def boot_plan(root: Path, env: dict[str, str]) -> str:
    """`linux=` and `windows=` lines for $GITHUB_OUTPUT, from the variables ci.yml's plan step sets."""
    plan = boots(env.get("EVENT", ""), env.get("REF", ""), env.get("DRAFT") == "true",
                 env.get("LABELS", "").split(), changed_paths(root, env.get("BASE", ""), env.get("HEAD", "HEAD")))
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
