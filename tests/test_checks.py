import io
import subprocess
import sys

import pytest

import checks
from repo import REPO


def test_every_posix_script_is_checked():
    found = {p.relative_to(REPO.root).as_posix() for p in checks.sh_scripts(REPO.root)}
    assert {"deploy/lib.sh", "package/start.sh", "package/realms/realms.sh", "package/Start Server.command"} <= found
    # tests/*-smoke.sh are bash on purpose (CI runs them with bash), so they stay out
    assert not any(name.startswith("tests/") for name in found)


def test_the_sh_check_runs_dash_on_each_script():
    sh = next(c for c in checks.CHECKS if c.name == "sh")
    commands = sh.command(REPO.root)
    assert len(commands) == len(checks.sh_scripts(REPO.root))
    assert all(cmd[:2] == ["dash", "-n"] for cmd in commands)


def test_a_missing_tool_is_skipped_or_failed_when_strict(monkeypatch, tmp_path):
    monkeypatch.setattr(checks, "available", lambda check, env: False)
    loose = checks.run(["sh"], tmp_path, strict=False, out=io.StringIO())
    strict = checks.run(["sh"], tmp_path, strict=True, out=io.StringIO())
    assert [r.state for r in loose] == ["skipped"]
    assert [r.state for r in strict] == ["failed"]


def test_a_failing_command_fails_its_check(monkeypatch, tmp_path):
    bad = checks.Check("bad", "", lambda root: [[sys.executable, "-c", "raise SystemExit(3)"]], "always fails")
    good = checks.Check("good", "", lambda root: [[sys.executable, "-c", "print('ok')"]], "always passes")
    monkeypatch.setattr(checks, "CHECKS", (bad, good))
    monkeypatch.setattr(checks, "available", lambda check, env: True)
    results = checks.run(["bad", "good"], tmp_path, strict=True, out=io.StringIO())
    assert [(r.name, r.state) for r in results] == [("bad", "failed"), ("good", "passed")]


def test_the_summary_names_failures_then_skips():
    r = checks.Result
    assert checks.summary([r("ruff", "passed", 1), r("sh", "passed", 1)]) == "all passed"
    assert checks.summary([r("pytest", "failed", 1), r("pester", "skipped", 0), r("sh", "failed", 1)]) \
        == "failed: pytest, sh; skipped: pester"


def test_an_unknown_check_is_refused(capsys):
    with pytest.raises(SystemExit) as stopped:
        checks.main(["pytset"])
    assert stopped.value.code == 2
    assert "no check named pytset" in capsys.readouterr().err


def test_a_draft_pr_boots_nothing_and_a_release_boots_everything():
    pack = ["package/realms/datapacks/realms-drops/data/realms/function/drops/try.mcfunction"]
    assert checks.boots("pull_request", "refs/pull/70/merge", True, [], pack) == {"linux": False, "windows": False}
    assert checks.boots("push", "refs/tags/v2.9.0", False, [], []) == {"linux": True, "windows": True}
    assert checks.boots("workflow_dispatch", "refs/heads/x", False, [], []) == {"linux": True, "windows": True}
    # the boot label boots a draft too
    assert checks.boots("pull_request", "r", True, ["boot"], []) == {"linux": True, "windows": True}


def test_a_ready_pr_boots_what_its_change_can_break():
    def plan(*paths):
        return checks.boots("pull_request", "refs/pull/1/merge", False, [], list(paths))
    assert plan("tools/standings.py", "tests/test_standings.py", "docs/ADMIN.md") == {"linux": False, "windows": False}
    assert plan("package/realms/datapacks/realms-drops/pack.mcmeta") == {"linux": True, "windows": False}
    assert plan("package/realms/Realms.psm1") == {"linux": True, "windows": True}
    assert plan("package/start.bat") == {"linux": True, "windows": True}
    assert plan("player/installer/PlayerInstall.psm1") == {"linux": True, "windows": True}
    # unknown (a new branch, a force push): everything
    assert checks.boots("pull_request", "r", False, [], None) == {"linux": True, "windows": True}


def test_a_push_to_main_boots_on_linux_only():
    assert checks.boots("push", "refs/heads/main", False, [], ["package/realms/Realms.psm1"]) \
        == {"linux": True, "windows": False}
    assert checks.boots("push", "refs/heads/main", False, [], ["docs/LIVE.md"]) == {"linux": False, "windows": False}


def test_the_plan_reads_what_changed_from_git(tmp_path):
    def git(*args):
        subprocess.run(["git", *args], cwd=tmp_path, check=True, capture_output=True)
    git("init", "-q")
    git("-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "--allow-empty", "-m", "base")
    (tmp_path / "package").mkdir()
    (tmp_path / "package" / "start.sh").write_text("#!/bin/sh\n")
    git("add", ".")
    git("-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", "change")
    assert checks.changed_paths(tmp_path, "HEAD~1", "HEAD") == ["package/start.sh"]
    assert checks.changed_paths(tmp_path, "0" * 40, "HEAD") is None
    assert checks.changed_paths(tmp_path, "no-such-commit", "HEAD") is None
    env = {"EVENT": "pull_request", "REF": "refs/pull/1/merge", "DRAFT": "false", "BASE": "HEAD~1", "HEAD": "HEAD"}
    assert checks.boot_plan(tmp_path, env) == "linux=true\nwindows=false\n"
