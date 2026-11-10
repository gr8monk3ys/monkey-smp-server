"""Says whether a commit may go live on the VPS: what deploy/monkey-deploy.sh and deploy/install-root.sh ask before
they deploy or install anything. A pushed tag alone is not enough; it must be a release CI built and published.

    python3 tools/release_gate.py COMMIT --tag vX.Y.Z    a release tag: GitHub has a published release for the tag
                                                         (not a draft, not a pre-release), the tag on GitHub points at
                                                         COMMIT (the checkout's copy wasn't moved), and the required
                                                         check passed on COMMIT
    python3 tools/release_gate.py COMMIT                 a branch (TRACK=main): the required check passed on COMMIT

The required check is CHECK ("Checks (lint, tests, packs, sh, Pester), build"): every newest run of it on the commit,
from a push to main or from the release workflow's own CI ("ci / Checks ..."), finished with success, and there is
at least one. The release workflow publishes only after its CI passed, so a release made by hand is caught here too.

Exit codes: 0 it may go live, 1 not (yet): the line printed says why, 2 can't tell (GitHub didn't answer, or answered
something unreadable). The deploy treats 1 and 2 alike: it deploys nothing and asks again on its next run.

GitHub's API is read without a token (the repo is public; 60 requests an hour per address). A run asks 1 request when
there is no release yet and 3 when there is. GITHUB_REPO (owner/name) names another repo. No secret is read.
Plain stdlib, Python 3.10 or newer (the VPS's python3, like tools/rcon.py).
"""
import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

REPO = "gr8monk3ys/monkey-smp-server"
API = "https://api.github.com"
CHECK = "Checks (lint, tests, packs, sh, Pester), build"
OK, NOT_YET, CANT_TELL = 0, 1, 2
TAG = re.compile(r"v\d+\.\d+\.\d+")
SHA = re.compile(r"[0-9a-f]{40}")


class CantTell(Exception):
    pass


def get(path: str, urlopen=urllib.request.urlopen) -> dict | None:
    """GitHub's JSON answer for API path, or None for a 404; CantTell for anything else that isn't JSON."""
    request = urllib.request.Request(API + path, headers={
        "Accept": "application/vnd.github+json", "User-Agent": "monkey-smp-release-gate",
        "X-GitHub-Api-Version": "2022-11-28"})
    try:
        with urlopen(request, timeout=20) as answer:
            return json.loads(answer.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        raise CantTell(f"GitHub answered HTTP {e.code} for {path}") from None
    except (urllib.error.URLError, OSError, ValueError) as e:
        raise CantTell(f"could not read GitHub's answer for {path} ({type(e).__name__})") from None


def check_passed(repo: str, commit: str, urlopen=urllib.request.urlopen) -> str | None:
    """None when the required check passed on commit, else why not."""
    runs = get(f"/repos/{repo}/commits/{commit}/check-runs?filter=latest&per_page=100", urlopen)
    if runs is None:
        return f"GitHub has no commit {commit[:12]}"
    try:
        ours = [r for r in runs["check_runs"] if r["name"] == CHECK or r["name"].endswith(" / " + CHECK)]
        if not ours:
            return f'"{CHECK}" has not run on {commit[:12]}'
        for r in ours:
            if r["status"] != "completed":
                return f'"{r["name"]}" is still running on {commit[:12]}'
            if r["conclusion"] != "success":
                return f'"{r["name"]}" ended in {r["conclusion"]} on {commit[:12]}'
    except (KeyError, TypeError):
        raise CantTell("GitHub's check runs were not in the shape expected") from None
    return None


def why_not(commit: str, tag: str | None, repo: str = REPO, urlopen=urllib.request.urlopen) -> str | None:
    """None when commit (the release tag, if given) may go live, else why not. CantTell when GitHub didn't say."""
    if tag is not None:
        release = get(f"/repos/{repo}/releases/tags/{urllib.parse.quote(tag)}", urlopen)
        if release is None:
            return f"{tag} has no published release on GitHub yet"
        if not isinstance(release, dict):
            raise CantTell("GitHub's release was not in the shape expected")
        if release.get("draft") or release.get("prerelease"):
            return f"{tag}'s release is a draft or a pre-release"
        if release.get("tag_name") != tag:
            raise CantTell("GitHub's release was not in the shape expected")
        tagged = get(f"/repos/{repo}/commits/{urllib.parse.quote(tag)}", urlopen)
        sha = tagged.get("sha") if isinstance(tagged, dict) else None
        if not isinstance(sha, str) or not SHA.fullmatch(sha):
            raise CantTell(f"GitHub did not say which commit {tag} is")
        if sha != commit:
            return f"{tag} is {sha[:12]} on GitHub but {commit[:12]} in the checkout"
    return check_passed(repo, commit, urlopen)


def main(argv=None, urlopen=urllib.request.urlopen) -> int:
    ap = argparse.ArgumentParser(description="May this commit go live? (a published release and green CI)")
    ap.add_argument("commit", help="the full commit hash (40 hex digits)")
    ap.add_argument("--tag", help="the release tag, vX.Y.Z (leave out for a branch)")
    args = ap.parse_args(argv)
    repo = os.environ.get("GITHUB_REPO") or REPO
    if not SHA.fullmatch(args.commit) or (args.tag is not None and not TAG.fullmatch(args.tag)):
        print("release gate: a commit is 40 hex digits and a tag vX.Y.Z", file=sys.stderr)
        return CANT_TELL
    if not re.fullmatch(r"[\w.-]+/[\w.-]+", repo):
        print("release gate: GITHUB_REPO is owner/name", file=sys.stderr)
        return CANT_TELL
    what = args.tag or args.commit[:12]
    try:
        reason = why_not(args.commit, args.tag, repo, urlopen)
    except CantTell as e:
        print(f"release gate: can't tell whether {what} may go live: {e}")
        return CANT_TELL
    if reason:
        print(f"release gate: not yet: {reason}")
        return NOT_YET
    print(f"release gate: {what} has {'a published release and ' if args.tag else ''}green CI")
    return OK


if __name__ == "__main__":
    sys.exit(main())
