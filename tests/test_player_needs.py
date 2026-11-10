import json

import player_needs
import validate
from repo import REPO, Repo


def test_the_numbers_and_every_text_that_states_them_agree():
    assert player_needs.problems() == []


def test_the_pack_size_comes_from_the_client_index():
    index = json.loads((REPO.client / "modrinth.index.json").read_text(encoding="utf-8"))
    total = sum(f["fileSize"] for f in index["files"])
    assert abs(player_needs.pack_mb() * 1e6 - total) <= 5e6
    needs = json.loads(player_needs.needs_file().read_text(encoding="utf-8"))
    assert needs["pack_mb"] == player_needs.pack_mb() and needs["ram_measured"] is False


def test_a_text_with_another_size_or_ram_fails():
    errors = player_needs.text_problems(
        "It downloads the mods (~520 MB).\nThe server downloads about 500 MB.\nA PC with 8 GB of RAM.\n"
        "Patrix 32x (73 MB) is optional.\nThe modpack (about 380 MB).", "x.md", 380, 16)
    assert errors == ["x.md:1: says the pack is 520 MB; it is about 380 MB (site/player-needs.json)",
                      "x.md:3: says 8 GB of RAM; site/player-needs.json says 16"]


def test_a_stale_size_in_the_file_fails_and_write_fixes_it(tmp_path):
    repo = Repo(tmp_path)
    repo.client.mkdir(parents=True)
    (repo.client / "modrinth.index.json").write_text(
        json.dumps({"files": [{"fileSize": 123_400_000}, {"fileSize": 1_000_000}]}), encoding="utf-8")
    (tmp_path / "site").mkdir()
    needs = player_needs.needs_file(repo)
    needs.write_text(json.dumps({"pack_mb": 380, "ram_gb": 16}), encoding="utf-8")
    assert "run python tools/player_needs.py --write" in player_needs.problems(repo)[0]
    assert player_needs.main(["--write"], repo) == 0
    assert json.loads(needs.read_text(encoding="utf-8"))["pack_mb"] == 120
    assert b"\r" not in needs.read_bytes()


def test_the_client_pack_version_is_the_release():
    assert validate.client_version_problems(REPO.load_manifest()) == []
    assert validate.client_version_problems({"version": "9.9.9"}) != []
