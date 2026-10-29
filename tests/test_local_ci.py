import datetime as dt
import json
import subprocess

import local_ci

NOW = dt.datetime(2026, 10, 29, 3, 0, tzinfo=dt.timezone.utc)   # noqa: UP017
REPO_NAME = "owner/repo"


class FakeGh:
    """Answers the gh calls local_ci makes and records every status it posts."""

    def __init__(self, prs, statuses=None, fail_on=None):
        self.prs, self.statuses, self.posted, self.fail_on = prs, statuses or {}, [], fail_on

    def __call__(self, args):
        if args[:2] == ["repo", "view"]:
            return REPO_NAME + "\n"
        if args[:2] == ["pr", "view"]:
            number = int(args[2])
            sha, fork = self.prs[number]
            return json.dumps({"number": number, "headRefOid": sha, "isCrossRepository": fork})
        if args[:2] == ["pr", "list"]:
            return json.dumps([{"number": n} for n in self.prs])
        if args[0] == "api" and "/status?" in args[1]:
            # the combined status: each context's latest status only (the lists here are newest first)
            latest = {}
            for status in self.statuses.get(args[1].split("/")[4], []):
                latest.setdefault(status["context"], status)
            return json.dumps({"statuses": list(latest.values())})
        if args[:3] == ["api", "-X", "POST"]:
            fields = dict(a.split("=", 1) for a in args[5::2])
            self.posted.append((args[3].split("/")[-1], fields["state"], fields["description"]))
            if fields["state"] == self.fail_on:
                raise subprocess.CalledProcessError(1, ["gh", *args])
            assert fields["context"] == "local-ci" and len(fields["description"]) <= 140
            return "{}"
        raise AssertionError(f"unexpected gh call {args}")


PASSED = local_ci.Outcome(True, "all passed", "log")


def run(gh, numbers, tmp_path, outcome=PASSED, force=False, dry_run=False):
    checked, said = [], []

    def check(number, sha):
        checked.append((number, sha))
        return outcome

    failed = local_ci.ci(numbers, gh, check, tmp_path, force, dry_run, now=lambda: NOW, say=said.append)
    return failed, checked, said


def test_a_pr_gets_pending_then_its_result(tmp_path):
    gh = FakeGh({68: ("a" * 40, False)})
    failed, checked, _ = run(gh, [68], tmp_path)
    assert failed == 0 and checked == [(68, "a" * 40)]
    assert [(state, desc) for _, state, desc in gh.posted] == [
        ("pending", "checks.py is running on a maintainer's machine"), ("success", "all passed")]
    assert (tmp_path / "local-ci" / ("a" * 40 + ".log")).read_text(encoding="utf-8") == "log"
    assert "#68 aaaaaaa success: all passed" in (tmp_path / "local-ci.log").read_text(encoding="utf-8")


def test_a_failure_is_posted_and_counted(tmp_path):
    gh = FakeGh({70: ("b" * 40, False)})
    failed, _, _ = run(gh, [70], tmp_path, outcome=local_ci.Outcome(False, "failed: pytest", ""))
    assert failed == 1 and gh.posted[-1][1:] == ("failure", "failed: pytest")


def test_a_head_with_a_result_is_skipped_unless_forced(tmp_path):
    done = {"c" * 40: [{"context": "local-ci", "state": "success", "updated_at": "2026-10-29T01:00:00Z"}]}
    gh = FakeGh({66: ("c" * 40, False)}, done)
    assert run(gh, [66], tmp_path)[1] == []
    assert run(gh, [66], tmp_path, force=True)[1] == [(66, "c" * 40)]


def test_a_pending_status_is_a_run_still_going_until_it_is_two_hours_old(tmp_path):
    def pending(when):
        return {"d" * 40: [{"context": "local-ci", "state": "pending", "updated_at": when},
                           {"context": "local-ci", "state": "failure", "updated_at": "2026-10-28T20:00:00Z"}]}
    assert run(FakeGh({67: ("d" * 40, False)}, pending("2026-10-29T02:00:00Z")), [67], tmp_path)[1] == []
    assert run(FakeGh({67: ("d" * 40, False)}, pending("2026-10-29T00:30:00Z")), [67], tmp_path)[1] == [(67, "d" * 40)]


def test_other_contexts_dont_count(tmp_path):
    other = {"e" * 40: [{"context": "Vercel", "state": "success", "updated_at": "2026-10-29T01:00:00Z"}]}
    assert run(FakeGh({69: ("e" * 40, False)}, other), [69], tmp_path)[1] == [(69, "e" * 40)]


def test_a_fork_is_never_run(tmp_path):
    gh = FakeGh({99: ("f" * 40, True)})
    failed, checked, said = run(gh, [99], tmp_path)
    assert (failed, checked, gh.posted) == (0, [], [])
    assert said == ["#99: from a fork, not run"]


def test_a_dry_run_posts_nothing(tmp_path):
    gh = FakeGh({71: ("1" * 40, False)})
    assert run(gh, [71], tmp_path, dry_run=True)[1] == [(71, "1" * 40)]
    assert gh.posted == []


def test_a_long_summary_is_cut_to_what_github_takes(tmp_path):
    gh = FakeGh({61: ("2" * 40, False)})
    run(gh, [61], tmp_path, outcome=local_ci.Outcome(False, "failed: " + "x" * 300, ""))
    assert len(gh.posted[-1][2]) == 140


def test_one_run_at_a_time(tmp_path):
    lock = local_ci.one_at_a_time(tmp_path)
    assert lock is not None
    assert local_ci.one_at_a_time(tmp_path) is None
    # the OS lets go when the run ends, however it ends: nothing to time out or take over
    lock.close()
    again = local_ci.one_at_a_time(tmp_path)
    assert again is not None
    again.close()


def test_a_post_that_fails_leaves_an_error_not_pending_and_the_next_pr_still_runs(tmp_path):
    gh = FakeGh({68: ("a" * 40, False), 70: ("b" * 40, False)}, fail_on="success")
    failed, checked, said = run(gh, [68, 70], tmp_path)
    assert checked == [(68, "a" * 40), (70, "b" * 40)] and failed == 2
    assert [state for sha, state, _ in gh.posted if sha == "a" * 40] == ["pending", "success", "error"]
    assert any(line.startswith("#68: stopped:") for line in said)


def test_a_pr_is_checked_strictly(monkeypatch, tmp_path):
    # a check this machine can't run must fail the status, never pass as "skipped"
    calls = []
    monkeypatch.setattr(local_ci, "git", lambda *args, **kw: "")
    monkeypatch.setattr(local_ci.subprocess, "run",
                        lambda cmd, **kw: calls.append(cmd) or subprocess.CompletedProcess(cmd, 0, "all passed\n"))
    assert local_ci.check_commit(68, "a" * 40).summary == "all passed"
    assert "--strict" in next(cmd for cmd in calls if str(local_ci.CHECKS) in cmd)
