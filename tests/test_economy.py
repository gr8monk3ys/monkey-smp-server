from pathlib import Path

import economy
from repo import REPO

AH = REPO.root / "package/monkey/defaults/plugins/DonutAuctionHouse/config.yml"


def table() -> list[economy.Item]:
    return economy.read_table(REPO.root / economy.TABLE)


def item(material: str, buy: float | None, sell: float | None, section: str = "Test") -> economy.Item:
    return economy.Item(section, material, buy, sell, "")


# ---------------------------------------------------------------- the committed table and files


def test_the_price_table_follows_every_rule():
    assert economy.problems(table()) == []


def test_the_shop_files_are_up_to_date():
    assert economy.write(REPO.root, check=True) == 0


def test_no_section_spills_onto_a_second_page_unnoticed():
    for name, text in economy.shop_files(table()).items():
        if name.startswith("shops/"):
            assert text.count("  page") == 1, f"{name} needs a second page: check the menu still reads well"


def test_the_anchor_prices_hold():
    prices = {i.material: i for i in table()}
    assert prices["diamond"].sell == 100 and prices["diamond"].buy is None
    assert all(prices[m].buy is None for m in ("iron_ingot", "gold_ingot", "emerald", "ancient_debris"))


def test_the_auction_house_taxes_everyone_the_same():
    text = AH.read_text(encoding="utf-8")
    assert "sales-tax:\n    enabled: true\n    percent: 5.0\n    # No tiers." in text
    assert "    permissions: {}\n    deposit-to: ''" in text
    assert "listing-fee:\n    enabled: true" in text
    assert "default-limit: 5" in text


# ---------------------------------------------------------------- the rules


def test_a_narrow_spread_is_caught():
    assert any("under 4 times" in p for p in economy.problems([item("stone", 3, 1)]))


def test_combat_items_cant_be_sold_by_the_shop():
    assert any("wins fights" in p for p in economy.problems([item("totem_of_undying", 5000, None)]))
    assert economy.problems([item("blaze_rod", None, 4)]) == []


def test_crafting_shop_items_into_profit_is_caught():
    found = economy.problems([item("wheat", 1, 0.2), item("hay_block", 100, 25)])
    assert any("buying wheat and selling hay_block makes money" in p for p in found)


def test_uncrafting_a_cheap_block_into_profit_is_caught():
    found = economy.problems([item("coal", 12, 2), item("coal_block", 15, None)])
    assert any("buying coal_block and selling its coal makes money" in p for p in found)


def test_duplicates_and_empty_rows_are_caught():
    found = economy.problems([item("dirt", 2, None), item("dirt", 2, None), item("sand", None, None)])
    assert "dirt is in the table twice" in found
    assert "sand has neither a buy nor a sell price" in found


def test_unoffered_prices_are_written_as_minus_one():
    files = economy.shop_files([item("diamond", None, 100, "Ores")])
    assert "material: diamond\n        buy: -1\n        sell: 100\n        slot: 0" in files["shops/Ores.yml"]
    assert "material: diamond" in files["sections/Ores.yml"]


# ---------------------------------------------------------------- the money supply


def test_money_supply_reads_essentials_userdata(tmp_path: Path):
    for n, money in enumerate(["0", "'100.5'", "1000", "50000"]):
        (tmp_path / f"{n}.yml").write_text(f"lastAccountName: p{n}\nmoney: {money}\n", encoding="utf-8")
    (tmp_path / "nomoney.yml").write_text("lastAccountName: x\n", encoding="utf-8")
    s = economy.supply(tmp_path)
    assert s["players"] == 4
    assert s["total"] == 51100.5
    assert s["median"] == 550.25
    assert s["top_1pct_share"] == round(50000 / 51100.5, 3)


def test_money_supply_of_an_empty_folder(tmp_path: Path):
    assert economy.supply(tmp_path) == {"players": 0, "total": 0, "median": 0.0, "top_1pct_share": 0.0,
                                        "top_10_share": 0.0}
