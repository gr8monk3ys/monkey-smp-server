"""The relaunch economy: checks the server shop's price table and writes the EconomyShopGUI files from it.

    python tools/economy.py                  check docs/relaunch/economy-prices.csv and write the shop files
    python tools/economy.py --check          check, and fail if the shop files are out of date (CI, tests)
    python tools/economy.py supply DIR       the money supply from EssentialsX's userdata folder (weekly watch)
    python tools/economy.py supply DIR --json

The price table is the one file a person edits. Its rules are in docs/relaunch/economy.md ("The price rules"):
every price the server both buys and sells has a wide gap between the two, no item that wins fights is sold,
and no craft or smelt turns shop items into more money than they cost. The shop files under
package/monkey/defaults/plugins/EconomyShopGUI/
(shops/ and sections/) are generated output: edit the table, then run this.

`supply` reads the `money:` line of every player file EssentialsX keeps (plugins/Essentials/userdata/*.yml)
and prints the total, the median and how much the richest hold. Run it on a copy of the folder, weekly, and
keep the --json lines: the design doc says what to do when they move. Stdlib only.
"""
import argparse
import csv
import json
import re
import statistics
import sys
from dataclasses import dataclass
from pathlib import Path

from repo import REPO

TABLE = Path("docs/relaunch/economy-prices.csv")
SHOP_DIR = Path("package/monkey/defaults/plugins/EconomyShopGUI")

MIN_SPREAD = 4.0     # the shop's buy price is at least this many times its sell price
PER_PAGE = 45        # 6-row menus; the bottom row is EconomyShopGUI's navigation bar
ICONS = {"Blocks": "stone_bricks", "Wood": "oak_log", "Farming": "wheat", "Mob Drops": "bone", "Ores": "diamond",
         "Food": "bread", "Utility": "chest", "Redstone": "redstone"}   # a section's button in the main menu

# Items that win fights stay out of the server shop: players earn them in play and trade them on the auction
# house, so money can't be turned straight into combat power at a fixed price.
NEVER_SOLD = {
    "totem_of_undying", "end_crystal", "respawn_anchor", "ender_pearl", "golden_apple", "enchanted_golden_apple",
    "elytra", "mace", "trident", "shulker_box", "shulker_shell", "enchanted_book", "netherite_ingot",
    "netherite_sword", "netherite_axe", "netherite_helmet", "netherite_chestplate", "netherite_leggings",
    "netherite_boots", "diamond_sword", "diamond_axe", "diamond_helmet", "diamond_chestplate",
    "diamond_leggings", "diamond_boots", "bow", "crossbow", "arrow", "spectral_arrow", "tipped_arrow", "tnt",
    "tnt_minecart", "spawner", "trial_spawner", "heavy_core", "wind_charge", "cobweb", "potion",
    "splash_potion", "lingering_potion",
}

# Crafts and smelts that could turn shop purchases into sales: (inputs, output, how many come out, reversible).
# Reversible means the output crafts back into the inputs (a block of iron into 9 ingots).
RECIPES: list[tuple[dict[str, float], str, int, bool]] = [
    *[({f"{m}_ingot": 9}, f"{m}_block", 1, True) for m in ("iron", "gold", "copper")],
    ({"diamond": 9}, "diamond_block", 1, True),
    ({"emerald": 9}, "emerald_block", 1, True),
    ({"coal": 9}, "coal_block", 1, True),
    ({"redstone": 9}, "redstone_block", 1, True),
    ({"lapis_lazuli": 9}, "lapis_block", 1, True),
    ({"wheat": 9}, "hay_block", 1, True),
    ({"slime_ball": 9}, "slime_block", 1, True),
    ({"bone_meal": 9}, "bone_block", 1, True),
    ({"bone": 1}, "bone_meal", 3, False),
    ({"string": 4}, "white_wool", 1, False),
    ({"glowstone_dust": 4}, "glowstone", 1, False),
    ({"quartz": 4}, "quartz_block", 1, False),
    ({"melon_slice": 9}, "melon", 1, False),
    ({"wheat": 3}, "bread", 1, False),
    ({"raw_iron": 1}, "iron_ingot", 1, False),
    ({"raw_gold": 1}, "gold_ingot", 1, False),
    ({"raw_copper": 1}, "copper_ingot", 1, False),
    ({"ancient_debris": 1}, "netherite_scrap", 1, False),
    ({"cobblestone": 1}, "stone", 1, False),
    ({"stone": 1}, "smooth_stone", 1, False),
    ({"sand": 1}, "glass", 1, False),
    ({"clay": 1}, "terracotta", 1, False),
    ({"potato": 1}, "baked_potato", 1, False),
    ({"iron_ingot": 1}, "bucket", 1, False),
    ({"iron_ingot": 31}, "anvil", 1, False),
    ({"iron_ingot": 5, "chest": 1}, "hopper", 1, False),
    ({"book": 3}, "bookshelf", 1, False),
    ({"leather": 1}, "book", 1, False),
    ({"honeycomb": 4}, "honeycomb_block", 1, False),
]


@dataclass(frozen=True)
class Item:
    section: str
    material: str
    buy: float | None
    sell: float | None
    note: str


def read_table(path: Path) -> list[Item]:
    rows = [line for line in path.read_text(encoding="utf-8").splitlines() if line and not line.startswith("#")]
    items = []
    for row in csv.DictReader(rows):
        def price(value: str) -> float | None:
            return float(value) if value.strip() else None
        items.append(Item(row["section"].strip(), row["material"].strip().lower(), price(row["buy"]),
                          price(row["sell"]), (row.get("note") or "").strip()))
    return items


def problems(items: list[Item]) -> list[str]:
    """Everything wrong with the table, as sentences; empty when it follows every price rule."""
    found = []
    seen: dict[str, Item] = {}
    for it in items:
        if it.material in seen:
            found.append(f"{it.material} is in the table twice")
        seen[it.material] = it
        if not re.fullmatch(r"[a-z0-9_]+", it.material):
            found.append(f"{it.material!r} is not an item id")
        if it.buy is None and it.sell is None:
            found.append(f"{it.material} has neither a buy nor a sell price")
        for kind, value in (("buy", it.buy), ("sell", it.sell)):
            if value is not None and value <= 0:
                found.append(f"{it.material}'s {kind} price must be above 0 (leave it empty for not offered)")
        if it.material in NEVER_SOLD and it.buy is not None:
            found.append(f"{it.material} wins fights, so the shop must not sell it")
        if it.buy and it.sell and it.buy < MIN_SPREAD * it.sell:
            found.append(f"{it.material}: buy {it.buy:g} is under {MIN_SPREAD:g} times sell {it.sell:g}")
    for inputs, output, count, reversible in RECIPES:
        out = seen.get(output)
        ins = {m: seen.get(m) for m in inputs}
        # Buy the inputs, craft, sell the output: must not pay.
        if out and out.sell and all(i and i.buy for i in ins.values()):
            cost = sum(ins[m].buy * n for m, n in inputs.items())
            if out.sell * count > cost:
                found.append(f"buying {', '.join(inputs)} and selling {output} makes money")
        # Buy the output, craft it back, sell the inputs: must not pay either.
        if reversible and out and out.buy and all(i and i.sell for i in ins.values()):
            back = sum(ins[m].sell * n for m, n in inputs.items())
            if back > out.buy * count:
                found.append(f"buying {output} and selling its {', '.join(inputs)} makes money")
    return found


def number(value: float) -> str:
    return str(int(value)) if value == int(value) else f"{value:g}"


def section_id(section: str) -> str:
    return section.replace(" ", "_")


def shop_files(items: list[Item]) -> dict[str, str]:
    """The EconomyShopGUI files: sections/<Section>.yml (the main menu's buttons) and shops/<Section>.yml."""
    sections: dict[str, list[Item]] = {}
    for it in items:
        sections.setdefault(it.section, []).append(it)
    header = ("# Generated by tools/economy.py from docs/relaunch/economy-prices.csv. "
              "Edit the table, not this file.\n")
    files = {}
    for slot, (section, rows) in enumerate(sections.items()):
        sid = section_id(section)
        files[f"sections/{sid}.yml"] = header + "\n".join([
            "enable: true",
            f"slot: {10 + slot}",
            f"title: '&8{section}'",
            "hidden: false",
            "economy: VAULTUNLOCKED",
            "fill-item:",
            "  material: gray_stained_glass_pane",
            "item:",
            f"  material: {ICONS.get(section, rows[0].material)}",
            f"  name: '&e&l{section}'",
            "  lore:",
            f"  - '&7{len(rows)} items'",
            "",
        ])
        lines = [header.rstrip("\n"), "pages:"]
        for page in range(0, len(rows), PER_PAGE):
            lines += [f"  page{page // PER_PAGE + 1}:", "    gui-rows: 6", f"    title: '&8{section}'", "    items:"]
            for n, it in enumerate(rows[page:page + PER_PAGE]):
                lines += [f"      {page + n + 1}:", f"        material: {it.material}",
                          f"        buy: {number(it.buy) if it.buy else -1}",
                          f"        sell: {number(it.sell) if it.sell else -1}",
                          f"        slot: {n}"]
        files[f"shops/{sid}.yml"] = "\n".join(lines) + "\n"
    return files


def write(root: Path, check: bool) -> int:
    items = read_table(root / TABLE)
    bad = problems(items)
    for line in bad:
        print(f"economy-prices.csv: {line}", file=sys.stderr)
    if bad:
        return 1
    stale = []
    for name, text in shop_files(items).items():
        path = root / SHOP_DIR / name
        if path.is_file() and path.read_text(encoding="utf-8") == text:
            continue
        if check:
            stale.append(name)
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8", newline="\n")
    if stale:
        print(f"Out of date: {', '.join(stale)}. Run python tools/economy.py", file=sys.stderr)
        return 1
    print(f"{len(items)} items in {len({i.section for i in items})} sections: the table follows every price rule.")
    return 0


MONEY = re.compile(r"^money:\s*'?([-0-9.Ee]+)'?\s*$", re.MULTILINE)


def supply(userdata: Path) -> dict[str, float]:
    """Total money, players holding it, median balance and the richest 1% and 10 players' share of it."""
    balances = []
    for f in sorted(userdata.glob("*.yml")):
        m = MONEY.search(f.read_text(encoding="utf-8", errors="replace"))
        if m:
            balances.append(float(m.group(1)))
    balances.sort(reverse=True)
    total = sum(balances)
    top1 = balances[:max(1, len(balances) // 100)] if balances else []
    return {
        "players": len(balances),
        "total": round(total, 2),
        "median": round(statistics.median(balances), 2) if balances else 0.0,
        "top_1pct_share": round(sum(top1) / total, 3) if total > 0 else 0.0,
        "top_10_share": round(sum(balances[:10]) / total, 3) if total > 0 else 0.0,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true", help="fail if the shop files are out of date")
    sub = ap.add_subparsers(dest="cmd")
    sp = sub.add_parser("supply", help="the money supply from EssentialsX's userdata folder")
    sp.add_argument("userdata", type=Path)
    sp.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    if args.cmd == "supply":
        s = supply(args.userdata)
        if args.json:
            print(json.dumps(s))
        else:
            print(f"{s['players']} players hold ${s['total']:,.2f}; median ${s['median']:,.2f}; "
                  f"the richest 1% hold {s['top_1pct_share']:.0%}, the top 10 {s['top_10_share']:.0%}")
        return 0
    return write(REPO.root, args.check)


if __name__ == "__main__":
    sys.exit(main())
