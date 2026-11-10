import io
import json
import urllib.error

import pytest

import release_gate as gate

COMMIT = "a" * 40
OTHER = "b" * 40
CHECK = "Checks (lint, tests, packs, sh, Pester), build"


def run(name, conclusion="success", status="completed"):
    return {"name": name, "status": status, "conclusion": conclusion}


class FakeGitHub:
    """Answers API paths from a table: a dict or list is JSON, an int is that HTTP error, an exception is raised."""

    def __init__(self, release=None, tagged=COMMIT, runs=None):
        self.asked = []
        self.table = {
            "/releases/tags/v1.2.3": release if release is not None else
            {"tag_name": "v1.2.3", "draft": False, "prerelease": False},
            "/commits/v1.2.3": {"sha": tagged} if isinstance(tagged, str) else tagged,
            f"/commits/{COMMIT}/check-runs": {"check_runs": runs if runs is not None else
                                               [run(CHECK), run("ci / " + CHECK), run("Boot", "skipped")]},
        }

    def __call__(self, request, timeout):
        path = request.full_url.removeprefix(gate.API + "/repos/" + gate.REPO).split("?")[0]
        self.asked.append(path)
        answer = self.table.get(path, 404)
        if isinstance(answer, Exception):
            raise answer
        if isinstance(answer, int):
            raise urllib.error.HTTPError(request.full_url, answer, "nope", {}, None)
        return io.BytesIO(json.dumps(answer).encode())


def test_a_published_release_with_green_ci_may_go_live(capsys):
    github = FakeGitHub()
    assert gate.main([COMMIT, "--tag", "v1.2.3"], github) == gate.OK
    assert "v1.2.3 has a published release and green CI" in capsys.readouterr().out
    assert len(github.asked) == 3


def test_a_tag_with_no_release_yet_asks_once_and_waits(capsys):
    github = FakeGitHub(release=404)
    assert gate.main([COMMIT, "--tag", "v1.2.3"], github) == gate.NOT_YET
    assert "no published release" in capsys.readouterr().out and len(github.asked) == 1


@pytest.mark.parametrize("release", [{"tag_name": "v1.2.3", "draft": True},
                                     {"tag_name": "v1.2.3", "prerelease": True}])
def test_a_draft_or_pre_release_does_not_go_live(release):
    assert gate.main([COMMIT, "--tag", "v1.2.3"], FakeGitHub(release=release)) == gate.NOT_YET


def test_a_tag_that_points_elsewhere_on_github_does_not_go_live(capsys):
    assert gate.main([COMMIT, "--tag", "v1.2.3"], FakeGitHub(tagged=OTHER)) == gate.NOT_YET
    assert "bbbbbbbbbbbb on GitHub but aaaaaaaaaaaa in the checkout" in capsys.readouterr().out


@pytest.mark.parametrize(("runs", "why"), [
    ([], "has not run"),
    ([run("Boot (Linux)")], "has not run"),
    ([run(CHECK), run("ci / " + CHECK, "failure")], "ended in failure"),
    ([run(CHECK, None, "in_progress")], "still running"),
    ([run(CHECK, "cancelled")], "ended in cancelled"),
])
def test_ci_that_did_not_pass_keeps_it_out(runs, why, capsys):
    assert gate.main([COMMIT, "--tag", "v1.2.3"], FakeGitHub(runs=runs)) == gate.NOT_YET
    assert why in capsys.readouterr().out


def test_a_branch_needs_only_green_ci():
    github = FakeGitHub()
    assert gate.main([COMMIT], github) == gate.OK
    assert github.asked == [f"/commits/{COMMIT}/check-runs"]


@pytest.mark.parametrize("trouble", [503, urllib.error.URLError("down"), TimeoutError()])
def test_github_not_answering_is_cant_tell_never_a_yes(trouble, capsys):
    github = FakeGitHub()
    github.table["/commits/v1.2.3"] = trouble
    assert gate.main([COMMIT, "--tag", "v1.2.3"], github) == gate.CANT_TELL
    assert "can't tell" in capsys.readouterr().out


def test_an_answer_in_another_shape_is_cant_tell():
    github = FakeGitHub(runs=[{"name": CHECK}])
    assert gate.main([COMMIT, "--tag", "v1.2.3"], github) == gate.CANT_TELL
    github = FakeGitHub(tagged={"sha": "not-a-sha"})
    assert gate.main([COMMIT, "--tag", "v1.2.3"], github) == gate.CANT_TELL


@pytest.mark.parametrize("argv", [["abc"], [COMMIT, "--tag", "main"], [COMMIT, "--tag", "v1.2.3; rm -rf /"]])
def test_only_a_full_commit_and_a_release_tag_are_asked_about(argv):
    github = FakeGitHub()
    assert gate.main(argv, github) == gate.CANT_TELL and github.asked == []


def test_another_repo_from_the_environment(monkeypatch):
    monkeypatch.setenv("GITHUB_REPO", "someone/else")
    seen = []

    def urlopen(request, timeout):
        seen.append(request.full_url)
        raise urllib.error.HTTPError(request.full_url, 404, "nope", {}, None)
    assert gate.main([COMMIT, "--tag", "v1.2.3"], urlopen) == gate.NOT_YET
    assert seen[0].startswith("https://api.github.com/repos/someone/else/")
