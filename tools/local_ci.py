"""CI on a maintainer's machine: checks a PR's head commit and posts the result on GitHub as a commit status.

    python tools/local_ci.py 68 70        check these PRs
    python tools/local_ci.py --open       every open PR whose head has no local-ci result yet
    python tools/local_ci.py --open --force      check them again even if they have one
    python tools/local_ci.py 68 --dry-run        check, post nothing

For when Actions can't run (this private repo's included minutes ran out in October 2026, and the account's
Actions budget is $0), and for the checks a PR needs before review either way. It needs `git` and an
authenticated `gh` (it posts statuses with `gh api`; it reads no token itself).

Each PR's head is checked out into a temporary worktree (never this checkout), then THIS file's
tools/checks.py checks it with `--root`, so a PR older than checks.py is still checked the same way. The
status is called `local-ci`: pending while it runs, then success or failure with checks.py's one-line summary
(what failed, what this machine had to skip). PRs from forks are never run. The full output of each run goes
to `.git/local-ci/<sha>.log` and a line per run to `.git/local-ci.log` (in the git common folder, so every
worktree of the clone shares them and nothing lands in the repo). One run at a time: a second one stops
straight away. A status the tool left pending for over two hours (a run that was cut off) counts as none.
"""
import argparse
import contextlib
import datetime as dt
import json
import os
import subprocess
import sys
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import IO

from repo import REPO

if os.name == "nt":
    import msvcrt
else:
    import fcntl

CONTEXT = "local-ci"
CHECKS = Path(__file__).resolve().with_name("checks.py")
STALE = dt.timedelta(hours=2)
UTC = dt.timezone.utc   # noqa: UP017 (the module UTC, like the VPS tools)

Gh = Callable[[list[str]], str]   # runs `gh ARGS`, returns its stdout, raises CalledProcessError


def real_gh(args: list[str]) -> str:
    return subprocess.run(["gh", *args], cwd=REPO.root, check=True, capture_output=True, text=True,
                          encoding="utf-8").stdout


@dataclass(frozen=True)
class Pr:
    number: int
    sha: str
    from_fork: bool


def pr(gh: Gh, number: int) -> Pr:
    got = json.loads(gh(["pr", "view", str(number), "--json", "number,headRefOid,isCrossRepository"]))
    return Pr(got["number"], got["headRefOid"], got["isCrossRepository"])


def open_prs(gh: Gh) -> list[int]:
    return sorted(p["number"] for p in json.loads(gh(["pr", "list", "--state", "open", "--json", "number",
                                                      "--limit", "200"])))


def repo_name(gh: Gh) -> str:
    return gh(["repo", "view", "--json", "nameWithOwner", "--jq", ".nameWithOwner"]).strip()


def has_result(gh: Gh, repo: str, sha: str, now: dt.datetime) -> bool:
    """Whether the commit already has a local-ci result: a finished one, or a run still going (pending under
    two hours old). The combined status holds each context's latest status, one per context."""
    combined = json.loads(gh(["api", f"repos/{repo}/commits/{sha}/status?per_page=100"]))
    mine = [s for s in combined.get("statuses", []) if s.get("context") == CONTEXT]
    if not mine:
        return False
    latest = mine[0]
    if latest["state"] != "pending":
        return True
    when = dt.datetime.fromisoformat(latest["updated_at"].replace("Z", "+00:00"))
    return now - when < STALE


def post(gh: Gh, repo: str, sha: str, state: str, description: str) -> None:
    gh(["api", "-X", "POST", f"repos/{repo}/statuses/{sha}", "-f", f"state={state}", "-f", f"context={CONTEXT}",
        "-f", f"description={description[:140]}"])


@dataclass(frozen=True)
class Outcome:
    ok: bool
    summary: str
    output: str


def git(*args: str, cwd: Path = REPO.root) -> str:
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True,
                          encoding="utf-8").stdout


def check_commit(number: int, sha: str) -> Outcome:
    """Checks out the PR's head into a temporary worktree, runs checks.py on it, removes the worktree."""
    git("fetch", "--quiet", "origin", f"+refs/pull/{number}/head")
    folder = Path(tempfile.mkdtemp(prefix=f"local-ci-{number}-"))
    try:
        git("worktree", "add", "--quiet", "--detach", str(folder), sha)
        # --strict: a check this machine can't run fails, so success always means every check ran
        done = subprocess.run([sys.executable, str(CHECKS), "--strict", "--root", str(folder)], cwd=folder,
                              stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8",
                              errors="replace")
        lines = done.stdout.strip().splitlines()
        return Outcome(done.returncode == 0, lines[-1] if lines else "checks.py printed nothing", done.stdout)
    finally:
        subprocess.run(["git", "worktree", "remove", "--force", str(folder)], cwd=REPO.root, capture_output=True)
        subprocess.run(["git", "worktree", "prune"], cwd=REPO.root, capture_output=True)


def common_dir() -> Path:
    return Path(git("rev-parse", "--path-format=absolute", "--git-common-dir").strip())


def ci(numbers: list[int], gh: Gh, check: Callable[[int, str], Outcome], logs: Path, force: bool, dry_run: bool,
       now: Callable[[], dt.datetime] = lambda: dt.datetime.now(UTC), say=print) -> int:
    """Checks each PR, posting local-ci statuses. Returns how many PRs failed their checks or couldn't be
    checked; a PR that can't be (gh or git failed) is said and counted, and the rest are still checked."""
    repo, failed = repo_name(gh), 0
    for number in numbers:
        try:
            failed += check_pr(number, repo, gh, check, logs, force, dry_run, now, say) is False
        except (OSError, ValueError, KeyError, subprocess.CalledProcessError) as e:
            say(f"#{number}: stopped: {e}")
            failed += 1
    return failed


def check_pr(number: int, repo: str, gh: Gh, check: Callable[[int, str], Outcome], logs: Path, force: bool,
             dry_run: bool, now: Callable[[], dt.datetime], say) -> bool | None:
    """Whether the PR passed (None: not run). Once its pending status is posted, a run that stops for any
    reason first posts an error, so the status never stays pending."""
    head = pr(gh, number)
    if head.from_fork:
        say(f"#{number}: from a fork, not run")
        return None
    if not force and has_result(gh, repo, head.sha, now()):
        say(f"#{number} {head.sha[:7]}: already has a {CONTEXT} result")
        return None
    say(f"#{number} {head.sha[:7]}: checking")
    if dry_run:
        return run_checks(number, head.sha, check, logs, now, say).ok
    post(gh, repo, head.sha, "pending", "checks.py is running on a maintainer's machine")
    try:
        result = run_checks(number, head.sha, check, logs, now, say)
        post(gh, repo, head.sha, "success" if result.ok else "failure", result.summary)
    except BaseException:
        with contextlib.suppress(Exception):
            post(gh, repo, head.sha, "error", "the local-ci run stopped before it finished")
        raise
    return result.ok


def run_checks(number: int, sha: str, check: Callable[[int, str], Outcome], logs: Path,
               now: Callable[[], dt.datetime], say) -> Outcome:
    try:
        result = check(number, sha)
    except (OSError, subprocess.CalledProcessError) as e:
        result = Outcome(False, f"could not check it out: {e}", str(e))
    (logs / CONTEXT).mkdir(parents=True, exist_ok=True)
    (logs / CONTEXT / f"{sha}.log").write_text(result.output, encoding="utf-8")
    line = f"{now():%Y-%m-%d %H:%M} #{number} {sha[:7]} {'success' if result.ok else 'failure'}: {result.summary}"
    with (logs / f"{CONTEXT}.log").open("a", encoding="utf-8") as log:
        log.write(line + "\n")
    say(line)
    return result


def one_at_a_time(logs: Path) -> IO[bytes] | None:
    """Takes the run lock: an OS lock on local-ci.lock, held while the returned file is open. The OS lets go
    of it when the run ends, however it ends, so a run that was cut off never leaves it held. None if another
    run holds it."""
    f = (logs / f"{CONTEXT}.lock").open("a+b")
    try:
        if os.name == "nt":
            f.seek(0)
            msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        f.close()
        return None
    return f


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("prs", nargs="*", type=int, metavar="PR")
    parser.add_argument("--open", action="store_true", help="every open PR")
    parser.add_argument("--force", action="store_true", help="check even a head that has a result")
    parser.add_argument("--dry-run", action="store_true", help="check, but post no status")
    args = parser.parse_args(argv)
    if bool(args.prs) == args.open:
        parser.error("name PRs or pass --open (not both)")
    logs = common_dir()
    lock = one_at_a_time(logs)
    if lock is None:
        print("another local-ci run is going (it holds .git/local-ci.lock); not starting a second")
        return 2
    with lock:
        numbers = open_prs(real_gh) if args.open else args.prs
        return 1 if ci(numbers, real_gh, check_commit, logs, args.force, args.dry_run) else 0


if __name__ == "__main__":
    sys.exit(main())
