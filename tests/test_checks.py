import io
import os
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


def test_the_site_check_builds_the_site_then_checks_its_pages():
    site = next(c for c in checks.CHECKS if c.name == "site")
    assert (site.needs, site.cwd) == ("bun", "site")
    commands = site.command(REPO.root)
    assert commands[:4] == [["bun", "install", "--frozen-lockfile"], ["bun", "run", "lint"],
                            ["bun", "run", "typecheck"], ["bun", "run", "build"]]
    assert commands[-1][-4:] == ["../tools/site_links.py", "--check", "--built", "out"]


def test_a_check_runs_in_its_own_folder(monkeypatch, tmp_path):
    (tmp_path / "sub").mkdir()
    here = checks.Check("here", "", lambda root: [[sys.executable, "-c", "import os; print(os.getcwd())"]], "cwd",
                        "sub")
    monkeypatch.setattr(checks, "CHECKS", (here,))
    out = io.StringIO()
    [result] = checks.run(["here"], tmp_path, strict=True, out=out)
    assert result.state == "passed" and str(tmp_path / "sub") in out.getvalue()


def test_a_failing_site_step_fails_the_check(monkeypatch, tmp_path):
    (tmp_path / "site").mkdir()
    site = next(c for c in checks.CHECKS if c.name == "site")
    fails = [[sys.executable, "-c", "raise SystemExit(1)"]]
    broken = checks.Check("site", "", lambda root: fails, site.about, site.cwd)
    monkeypatch.setattr(checks, "CHECKS", (broken,))
    [result] = checks.run(["site"], tmp_path, strict=True, out=io.StringIO())
    assert result.state == "failed"


def test_without_bun_the_site_is_skipped_and_says_why(monkeypatch, tmp_path):
    monkeypatch.setattr(checks.shutil, "which", lambda name, path=None: None)
    site = next(c for c in checks.CHECKS if c.name == "site")
    assert "https://bun.sh" in checks.missing(site, {})
    out = io.StringIO()
    [result] = checks.run(["site"], tmp_path, strict=False, out=out)
    assert result.state == "skipped" and "== site: skipped (needs bun, which builds the site" in out.getvalue()


def test_a_missing_tool_is_skipped_or_failed_when_strict(monkeypatch, tmp_path):
    monkeypatch.setattr(checks, "missing", lambda check, env: "dash")
    loose = checks.run(["sh"], tmp_path, strict=False, out=io.StringIO())
    strict = checks.run(["sh"], tmp_path, strict=True, out=io.StringIO())
    assert [r.state for r in loose] == ["skipped"]
    assert [r.state for r in strict] == ["failed"]


def test_a_failing_command_fails_its_check(monkeypatch, tmp_path):
    bad = checks.Check("bad", "", lambda root: [[sys.executable, "-c", "raise SystemExit(3)"]], "always fails")
    good = checks.Check("good", "", lambda root: [[sys.executable, "-c", "print('ok')"]], "always passes")
    monkeypatch.setattr(checks, "CHECKS", (bad, good))
    monkeypatch.setattr(checks, "missing", lambda check, env: "")
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
    # the build makes the zip every boot unzips, Windows' included
    assert plan("tools/build.py") == {"linux": True, "windows": True}
    assert plan("tools/repo.py") == {"linux": True, "windows": True}
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


def test_a_program_is_found_on_the_checks_path_not_just_this_process(monkeypatch, tmp_path):
    # Git for Windows' dash is only on the PATH checks.py gives its commands; Windows doesn't search that one
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    if os.name == "nt":
        (bin_dir / "only-here.bat").write_text("@exit /b 0\r\n")
    else:
        (bin_dir / "only-here").write_text("#!/bin/sh\nexit 0\n")
        (bin_dir / "only-here").chmod(0o755)
    env = dict(os.environ, PATH=os.pathsep.join([os.environ.get("PATH", ""), str(bin_dir)]))
    there = checks.Check("there", "", lambda root: [["only-here"]], "a program on the checks' PATH only")
    gone = checks.Check("gone", "", lambda root: [["no-such-program-anywhere"]], "a program nowhere")
    monkeypatch.setattr(checks, "CHECKS", (there, gone))
    monkeypatch.setattr(checks, "environment", lambda: env)
    monkeypatch.setattr(checks, "missing", lambda check, env: "")
    out = io.StringIO()
    results = checks.run(["there", "gone"], tmp_path, strict=True, out=out)
    assert [(r.name, r.state) for r in results] == [("there", "passed"), ("gone", "failed")]
    assert "could not run no-such-program-anywhere" in out.getvalue()


def test_a_module_check_needs_the_module_in_this_python():
    env = dict(os.environ)
    assert checks.missing(checks.Check("m", "module:json", lambda root: [], ""), env) == ""
    assert checks.missing(checks.Check("m", "module:no_such_module_xyz", lambda root: [], ""), env) \
        == "the no_such_module_xyz module"
    assert [c.needs for c in checks.CHECKS if c.name in ("ruff", "pytest")] == ["module:ruff", "module:pytest"]


def test_pester_runs_on_windows_powershell_and_pwsh_when_both_are_there(monkeypatch, tmp_path):
    monkeypatch.setattr(checks, "WINDOWS", True)
    monkeypatch.setattr(checks.shutil, "which", lambda name, path=None: name)
    assert checks.powershells() == ["powershell", "pwsh"]
    assert [cmd[0] for cmd in checks.pester(tmp_path)] == ["powershell", "pwsh"]
    monkeypatch.setattr(checks, "_has_pester", lambda shell: shell == "powershell")
    pester = next(c for c in checks.CHECKS if c.name == "pester")
    assert checks.missing(pester, {}) == "Pester 5.5+ in pwsh"
    monkeypatch.setattr(checks, "WINDOWS", False)
    assert checks.powershells() == ["pwsh"]


def test_labels_are_read_as_json_so_a_name_with_spaces_stays_whole():
    assert checks.labels('["no boot", "needs-triage"]') == ["no boot", "needs-triage"]
    assert checks.labels("null") == [] and checks.labels("") == [] and checks.labels("not json") == []
    assert checks.boots("pull_request", "r", False, checks.labels('["no boot"]'), []) \
        == {"linux": False, "windows": False}
    assert checks.boots("pull_request", "r", True, checks.labels('["boot"]'), []) == {"linux": True, "windows": True}
