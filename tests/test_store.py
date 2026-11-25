import copy

import pytest

import store
from repo import REPO


def test_generated_files_are_current():
    """Edit tools/store.py's tables, then run it; the configs and the packages page are never edited by hand."""
    for path, body in store.outputs(REPO).items():
        assert path.read_text(encoding="utf-8") == body, f"{path.name} is stale: run python tools/store.py"


def test_the_catalog_has_no_problems():
    assert store.problems() == []


def test_everything_granted_is_cosmetic():
    """No package or rank may grant homes, kits, fly, money, keys or anything else that changes play."""
    for p in store.packages():
        for cmd in p["initial"] + p["renewal"]:
            parts = cmd.split()
            assert parts[:3] == ["lp", "user", "{username}"], cmd
            if parts[3] == "permission":
                assert parts[5].startswith(store.COSMETIC_NODES), cmd
            else:
                assert parts[3] == "parent" and parts[5] in {r["id"] for r in store.RANKS}, cmd


@pytest.mark.parametrize("bad", ["essentials.fly", "essentials.sethome.multiple.vip", "ultracosmetics.gadgets.tsunami",
                                 "ultracosmetics.treasurechests.buykey", "huskclaims.claim_blocks.1000"])
def test_a_gameplay_permission_on_a_rank_is_caught(monkeypatch, bad):
    monkeypatch.setattr(store, "rank_nodes", lambda r: [bad])
    assert any(bad in p for p in store.problems())


def test_cape_shaped_holiday_and_earned_cosmetics_are_never_sold(monkeypatch):
    for category, name in [("Particle-Effects", "SuperHero"), ("Pets", "Pumpling")]:
        shop = copy.deepcopy(store.SHOP)
        shop.setdefault(category, []).append(name)
        monkeypatch.setattr(store, "SHOP", shop)
        assert any("never sold" in p for p in store.problems()), name
        monkeypatch.undo()
    monkeypatch.setattr(store, "SHOP_TAGS", [*store.SHOP_TAGS, "founder"])
    assert any("earned only" in p for p in store.problems())


def test_a_name_ultracosmetics_lacks_is_caught(monkeypatch):
    shop = copy.deepcopy(store.SHOP)
    shop["Pets"].append("Phantom")
    monkeypatch.setattr(store, "SHOP", shop)
    assert "Pets Phantom isn't an UltraCosmetics cosmetic" in store.problems()


def test_gameplay_categories_and_random_boxes_are_off():
    config = store.ultracosmetics_config()
    for category in store.UC_OFF:
        assert f"  {category}: false" in config
    assert "TreasureChests:\n  Enabled: false" in config
    assert "Allow-Purchase: false" in config and "GENERIC_ARMOR: 2" not in config
    for name in store.CAPE_LIKE["Particle-Effects"]:
        assert f"  {name}:\n    Enabled: false" in config


def test_each_cosmetic_is_sold_one_way_and_ranks_climb():
    """A one-off never duplicates a rank or pass reward, and each rank costs more than the one below."""
    assert store.problems() == []
    monthly = [r["monthly"] for r in store.RANKS]
    lifetime = [r["lifetime"] for r in store.RANKS]
    assert monthly == sorted(monthly) and lifetime == sorted(lifetime)
    assert all(life >= 5 * month for life, month in zip(lifetime, monthly, strict=True))


def test_the_pass_rewards_every_tier_and_sells_no_skips():
    assert sorted(store.PREMIUM_TRACK) == list(range(1, 31))
    names = [p["name"].lower() for p in store.packages()]
    assert not any(word in n.split() for n in names for word in ("tier", "tiers", "skip", "xp", "boost"))
