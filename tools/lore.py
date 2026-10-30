"""The season story: the Knotkeeper's chronicle, one page a week, announced by the Town Crier and hidden in the world.

    python tools/lore.py plan          each week's page: its Saturday, its title and where staff hide it
    python tools/datapacks.py          regenerates the monkey-lore data pack (with the others; --check only compares)

The story (docs/SEASONS.md, "The season story") is BEATS below, the one place to edit it: the title, the Crier's
line, where staff hide the page and the book's pages, by season week (tools/season_calendar.py). A test checks the
beats against the calendar: one page for every week from 1 to the finale, and the pages about the border, the End,
the Netherite age and the finale fall in the weeks those happen (tools/npcs.py EVENTS, the Crier's own list).

In game (the monkey-lore data pack, generated: edit this file, not it), while the switch is on (#on lr):
  - The Crier. Once a week has begun (#week rc.week, tools/challenges.py, from the VPS's weekly sync), each player
    online gets that week's line from the Town Crier in chat, once: whoever is on when the week turns, and anyone
    else the first time they are on that week. `/trigger lore` says it again, with the pages they have found.
  - The pages. Staff hide each week's page once per world: standing where it goes, `function monkey:lore/hide/<week>`
    leaves an invisible marker (lore.cache). From that week on, sparkles show at it, and a player who comes within
    REACH blocks gets that week's book (once each: lr.w<week>) and one more page found (lr.found). Before its week
    it shows and gives nothing, so every page can be hidden before the launch. Markers are entities: they work only
    while the chunk is loaded, which a player standing there does.
  - The title. Finding every page gives the Knotkeeper title (TITLE, a team like the other titles: season.py carries
    title_* teams). One a player already shows (a supporter color or another title) is never replaced; the chat line
    says so.
Off, nobody is told anything and no page is found (the markers stay, and so do the pages players have).
Stdlib only.
"""
import argparse
import sys
from dataclasses import dataclass
from pathlib import Path

import monuments
import season_calendar
from challenges import LAUNCHED
from datapacks import NS, function_tag, lines, mcmeta, text
from repo import Repo

DATAPACK = "monkey-lore"
FN = f"data/{NS}/function/lore"
OBJ = "lr"                  # #on: the switch; #told: the week the Crier last spoke of
SEEN = "lr.seen"            # the week a player was last told
FOUND = "lr.found"          # pages a player has found
TRIGGER = "lore"
WEEK = "#week rc.week"      # tools/challenges.py: the season's week (-1 until the timer sends one)
CACHE_TAG = "lore.cache"
LORE_ON = 0                 # ships off (docs/SEASONS.md, "Switches")
REACH = 4                   # blocks from a hidden page that find it
AUTHOR = "Mira Salt-Hand"
CHRONICLE = "the Knotkeeper's chronicle"
TITLE = ("title_knotkeeper", "dark_aqua", "[Knotkeeper] ")   # team, color, prefix: tools/season.py carries title_*
PAGE_CHARACTERS = 230       # a book page shows about 14 lines of 19 characters


@dataclass(frozen=True)
class Beat:
    title: str              # the book's title (at most 32 characters)
    cry: str                # what the Town Crier says that week
    where: str              # where staff hide the page, in players' words: "hidden <where>"
    pages: tuple[str, ...]  # the book
    tie: str = ""           # a word of that week's event (tools/npcs.py EVENTS) the page is about, checked by a test


# The Knotkeeper's chronicle: Season I, by week. An original story in its own world; keep it that way.
BEATS = {
    1: Beat(
        "The Rope",
        "A page of an old chronicle has turned up. It says the edge of our world is a rope, and that a monkey tied it.",
        "near spawn, where every road begins",
        ("I am Mira Salt-Hand, last keeper of the knots. Write this down, whoever finds it: the edge of your world "
         "is not a wall. It is a rope, and a monkey tied it.",
         "His name was Ruk. He was small, loud and always hungry, and he was king only because nobody else would "
         "climb that high. From the top of the tallest tree he saw the Hollow coming.",
         "The Hollow is not dark and not cold. It is unmade: land nobody has dreamed yet. Ruk tied a rope round his "
         "people so the Hollow could not take them. Then he sat on it.")),
    2: Beat(
        "The First Loosening",
        "The border breaks on Saturday, and the chronicle says why. A second page is loose.",
        "near the world border, before it moves",
        ("A rope that never moves is a noose. Ruk knew it. When his people grew loud and strong, he climbed out to "
         "the edge at dusk and let out an arm's length of rope.",
         "The Hollow drew back, and new land rolled in to fill the gap: hills nobody had walked, rivers with no "
         "names. Ruk named none of them. 'Let them argue about it,' he said.",
         "That is why your border breaks. Not a storm, not a curse. A monkey letting out rope, because you got too "
         "big for the old circle."),
        tie="border"),
    3: Beat(
        "The Far Gate",
        "The End opens this week. The third page tells who set a dragon on its door, and why.",
        "near the way to the End",
        ("Ruk had one fear: that the rope would fray from the far side. So he cut a door in the sky, a long way "
         "out, and set a dragon to sit on the hinge.",
         "'Not to keep them out,' he told the dragon. 'To make them earn the walk.' The dragon did not laugh. "
         "Dragons don't.",
         "If the gate stands open now, someone earned it. Look past the island. The rope's far knots are out there, "
         "black and cold, and nobody has counted them."),
        tie="End"),
    4: Beat(
        "Cloth and Quarrels",
        "Raid night again. The fourth page says raids are older than any of us.",
        "at one of the outposts",
        ("Ruk never fought for land. He fought for the right to say a thing first. Each band of his people carried "
         "a cloth, and where it flew, that band spoke first.",
         "They stole each other's cloths for sport. Ruk let them. 'A cloth taken back is worth two,' he said, and "
         "went to sleep in the middle of the war.",
         "Your raids are older than you think. Steal well.")),
    5: Beat(
        "The Deep Metal",
        "The Netherite age begins. The fifth page says who buried the old metal, and why it waited.",
        "in the Nether, near a portal",
        ("Under the world runs the hot country, and under that, metal so heavy it remembers. Ruk forbade it, not "
         "out of fear but out of patience.",
         "'When they can hold a rope, they can hold a hammer,' he said. He buried the old metal deep and told the "
         "fire to keep it until he asked.",
         "The fire has given it back. That means he asked. Hold it well."),
        tie="Netherite"),
    6: Beat(
        "The Long Night",
        "Midwinter. The sixth page is about fires along the rope and very bad singing.",
        "at spawn, under the Midwinter lights",
        ("Every winter the rope tightens with the cold. Ruk's people built fires along it and sang to keep the "
         "knots warm. The songs were bad. The knots held anyway.",
         "On the longest night Ruk gave one thing from his own pack to the loudest singer. Usually a stone. Once, "
         "a hat. Nobody knows where he got the hat.")),
    7: Beat(
        "The Second Loosening",
        "The border breaks again on Saturday. The seventh page warns there is not much rope left.",
        "near the world border, before it moves again",
        ("The second time is harder. Ruk's hands were older. He sat on the edge three nights before he untied the "
         "knot, listening to what his people were doing back home.",
         "'They're fighting over the river again,' he said. 'Good. They're still here.' Then he let the rope out, "
         "all of it he could spare.",
         "There is not much rope left, finder. Remember that when you spend the land."),
        tie="border"),
    8: Beat(
        "What He Built",
        "Build Battle week. The eighth page is about the one thing the Monkey King ever built.",
        "by the Build Battle plots",
        ("Ruk built one thing in his whole life: a chair at the top of the tallest tree. It wobbled. He loved it.",
         "Everything else his people built: halls, bridges, a tower that fell down twice. He judged all of it lying "
         "on his back, with one eye open.",
         "The tower that fell down twice won both times. He said falling was the bravest thing a tower can do.")),
    9: Beat(
        "The Borrowed Crown",
        "Arena week. The ninth page tells of the day someone asked the Monkey King for his crown.",
        "near the event arena",
        ("Once a challenger asked Ruk for the crown. He handed it over. The challenger wore it for one day, and the "
         "rope began to slip.",
         "It is not a crown that holds a rope. It is the hand that ties it. The challenger gave the crown back, and "
         "Ruk made him the first keeper of the knots.",
         "I learned the knots from his granddaughter. That is how I know.")),
    10: Beat(
        "Where Ruk Went",
        "The last raid. The tenth page answers the question everyone asks: did the Monkey King die?",
        "at one of the outposts",
        ("You will want to know if Ruk died. He did not. When his hands grew too old to untie a knot, he climbed "
         "into the rope and became the thing he had made.",
         "That is why the border hums at night if you stand close. That is why it moves when you grow. He is still "
         "letting you out, one arm's length at a time.")),
    11: Beat(
        "Drawing In",
        "The finale. The last page says why every circle closes, and what comes after.",
        "at spawn, before the finale",
        ("Every circle closes. When Ruk's people had walked all the land he could give, he drew the rope back in, "
         "slowly, toward the tree where it began.",
         "Not to punish them. To gather them: one last fight in a small circle, everyone close, then quiet. Then a "
         "new rope, tied somewhere new.",
         "Finder, if you hold all eleven of my pages, you are a keeper of the knots now. Tie them well next time."),
        tie="finale"),
}
WEEKS = tuple(sorted(BEATS))
FIRST, LAST = WEEKS[0], WEEKS[-1]
PAGES = len(BEATS)


def found_objective(week: int) -> str:
    return f"lr.w{week}"


# ---------------------------------------------------------------- the data pack


def gray(s: str) -> dict:
    return {"text": s, "color": "gray"}


def book(week: int) -> str:
    """The written book of a week's page, as an item for /give."""
    beat = BEATS[week]
    content = {"title": beat.title, "author": AUTHOR, "pages": list(beat.pages)}
    name = {"text": f"Page {WEEKS.index(week) + 1} of {PAGES}, {CHRONICLE}", "color": "gray", "italic": False}
    return (f"minecraft:written_book[minecraft:written_book_content={monuments.snbt(content)},"
            f"minecraft:lore=[{monuments.snbt(name)}]]")


def crier_line(week: int) -> str:
    beat = BEATS[week]
    return text("", {"text": "[Town Crier] ", "color": "yellow"}, {"text": f"Hear ye! {beat.cry} ", "color": "white"},
                gray(f"Page {WEEKS.index(week) + 1}, \"{beat.title}\", is hidden {beat.where}. "),
                {"text": f"/trigger {TRIGGER}", "color": "aqua",
                 "click_event": {"action": "run_command", "command": f"/trigger {TRIGGER}"}})


def datapack_files() -> dict[str, str]:
    team, color, prefix = TITLE
    f: dict[str, str] = {}
    f[f"{FN}/load.mcfunction"] = lines(
        "# Generated by tools/lore.py. Scores and markers are kept across restarts.",
        f"scoreboard objectives add {OBJ} dummy",
        f"scoreboard objectives add {SEEN} dummy",
        f"scoreboard objectives add {FOUND} dummy",
        *(f"scoreboard objectives add {found_objective(w)} dummy" for w in WEEKS),
        f"scoreboard objectives add {TRIGGER} trigger",
        f"execute unless score #on {OBJ} matches 0.. run scoreboard players set #on {OBJ} {LORE_ON}",
        f"team add {team}",
        f"team modify {team} color {color}",
        f"team modify {team} prefix " + text({"text": prefix, "color": color}),
        f"schedule function {NS}:lore/second 20t replace",
    )
    f[f"{FN}/second.mcfunction"] = lines(
        f"schedule function {NS}:lore/second 20t replace",
        f"execute unless score #on {OBJ} matches 1 run return 0",
        f"scoreboard players enable @a {TRIGGER}",
        f"execute as @a[scores={{{TRIGGER}=1..}}] run function {NS}:lore/use",
        f"execute unless score {LAUNCHED} matches 1 run return 0",
        f"execute if score {WEEK} matches {FIRST}..{LAST} unless score #told {OBJ} = {WEEK} run "
        f"scoreboard players operation #told {OBJ} = {WEEK}",
        f"execute if score #told {OBJ} matches {FIRST}..{LAST} as @a unless score @s {SEEN} = #told {OBJ} run "
        f"function {NS}:lore/greet",
        f"execute as @e[type=minecraft:marker,tag={CACHE_TAG}] at @s run function {NS}:lore/cache",
    )
    f[f"{FN}/greet.mcfunction"] = lines(
        "# As a player who hasn't heard this week's line from the Crier.",
        f"scoreboard players operation @s {SEEN} = #told {OBJ}",
        *(f"execute if score #told {OBJ} matches {w} run tellraw @s {crier_line(w)}" for w in WEEKS),
    )
    f[f"{FN}/cache.mcfunction"] = lines(
        "# As a hidden page's marker, once a second: from its week on, it sparkles and players close by find it.",
        *(f"execute if entity @s[tag=lore.w{w}] if score {WEEK} matches {w}.. run function {NS}:lore/near/{w}"
          for w in WEEKS),
    )
    f[f"{FN}/use.mcfunction"] = lines(
        f"# /trigger {TRIGGER}: this week's line again, and the pages this player has found.",
        f"scoreboard players set @s {TRIGGER} 0",
        f"execute if score #told {OBJ} matches {FIRST}..{LAST} run function {NS}:lore/greet",
        f"execute unless score #told {OBJ} matches {FIRST}..{LAST} run tellraw @s " + text(gray(
            f"The Town Crier has no page of {CHRONICLE} yet: the first is announced in week {FIRST}.")),
        f"execute unless score @s {FOUND} matches 1.. run scoreboard players set @s {FOUND} 0",
        "tellraw @s " + text("", {"text": "Pages you have found: ", "color": "gold"},
                             {"score": {"name": "@s", "objective": FOUND}, "color": "white"},
                             gray(f" of {PAGES}. Find them all for the Knotkeeper title.")),
    )
    f[f"{FN}/complete.mcfunction"] = lines(
        "# As a player who just found the last page.",
        "tellraw @a " + text("", {"selector": "@s", "color": "white"},
                             {"text": f" has found every page of {CHRONICLE}: a Knotkeeper!", "color": "dark_aqua"}),
        "# The title, unless they show another (a supporter color or a title is never taken away for it).",
        "execute unless entity @s[team=] run return run tellraw @s " + text(gray(
            "You already show a title or a supporter color, so it stays. Ask staff if you'd rather show "
            "Knotkeeper.")),
        f"team join {team} @s",
    )
    f[f"{FN}/on.mcfunction"] = lines(
        "# Staff: the Crier tells the story and hidden pages can be found (docs/SEASONS.md, \"Switches\").",
        f"scoreboard players set #on {OBJ} 1",
        "tellraw @s " + text({"text": "The season story is on.", "color": "green"}),
    )
    f[f"{FN}/off.mcfunction"] = lines(
        "# Staff: nobody is told anything and no page is found. Pages already found stay.",
        f"scoreboard players set #on {OBJ} 0",
        "tellraw @s " + text({"text": "The season story is off.", "color": "yellow"}),
    )
    f[f"{FN}/unhide.mcfunction"] = lines(
        "# Staff, in game: removes the hidden page nearest you (within 5 blocks).",
        f"execute unless entity @e[type=minecraft:marker,tag={CACHE_TAG},distance=..5] run return run tellraw @s "
        + text({"text": "No hidden page within 5 blocks.", "color": "red"}),
        f"kill @e[type=minecraft:marker,tag={CACHE_TAG},distance=..5,sort=nearest,limit=1]",
        "tellraw @s " + text({"text": "Removed the nearest hidden page.", "color": "yellow"}),
    )
    for w in WEEKS:
        beat = BEATS[w]
        n = WEEKS.index(w) + 1
        f[f"{FN}/hide/{w}.mcfunction"] = lines(
            f"# Staff, in game, standing where it goes: hides week {w}'s page, \"{beat.title}\" ({beat.where}).",
            f"# It shows and can be found from week {w}. Run it again elsewhere to add a second spot for it.",
            "execute unless entity @s[type=minecraft:player] run return run say Run this in game, where the page goes.",
            f"execute align xyz positioned ~0.5 ~0.5 ~0.5 run summon minecraft:marker ~ ~ ~ "
            f"{{Tags:[\"{CACHE_TAG}\",\"lore.w{w}\"]}}",
            "tellraw @s " + text({"text": f"Hid week {w}'s page \"{beat.title}\" here: ", "color": "green"},
                                 {"nbt": "Pos", "color": "white",
                                  "entity": f"@e[type=minecraft:marker,tag=lore.w{w},sort=nearest,limit=1]"}),
        )
        f[f"{FN}/near/{w}.mcfunction"] = lines(
            f"# As week {w}'s hidden page, from week {w} on.",
            "particle minecraft:enchant ~ ~0.5 ~ 0.3 0.6 0.3 0.4 6",
            f"execute as @a[distance=..{REACH},gamemode=!spectator] unless score @s {found_objective(w)} matches 1 "
            f"run function {NS}:lore/find/{w}",
        )
        f[f"{FN}/find/{w}.mcfunction"] = lines(
            f"# As a player who found week {w}'s page for the first time (staff: execute as NAME run function ...).",
            f"execute if score @s {found_objective(w)} matches 1 run return 0",
            f"scoreboard players set @s {found_objective(w)} 1",
            f"scoreboard players add @s {FOUND} 1",
            f"function {NS}:lore/book/{w}",
            "playsound minecraft:item.book.page_turn player @s ~ ~ ~ 1 1",
            "tellraw @s " + text("", {"text": f"You found page {n} of {CHRONICLE}: \"{beat.title}\". ",
                                      "color": "gold"},
                                 gray("Pages found: "), {"score": {"name": "@s", "objective": FOUND}, "color": "white"},
                                 gray(f" of {PAGES}.")),
            f"execute if score @s {FOUND} matches {PAGES}.. run function {NS}:lore/complete",
        )
        f[f"{FN}/book/{w}.mcfunction"] = lines(
            f"# Gives week {w}'s book, nothing else (staff: a lost copy, execute as NAME run function ...).",
            f"give @s {book(w)}",
        )
    return f


def packs(repo: Repo) -> dict[Path, dict[str, str]]:
    f = {
        "pack.mcmeta": mcmeta("Monkey SMP season story and monument contests (generated by tools/lore.py and "
                              "tools/monuments.py)"),
        "data/minecraft/tags/function/load.json": function_tag(f"{NS}:lore/load", f"{NS}:monuments/load"),
        **datapack_files(),
        **monuments.datapack_files(),
    }
    return {repo.monkey / "datapacks" / DATAPACK: f}


# ---------------------------------------------------------------- the command line


def plan() -> str:
    out = []
    for w in WEEKS:
        beat = BEATS[w]
        out.append(f"week {w:<2} {season_calendar.day_words(season_calendar.week_start(w)):<22} \"{beat.title}\": "
                   f"hide it {beat.where} (function {NS}:lore/hide/{w})")
    return "\n".join(out)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="The season story: each week's page and where to hide it.")
    ap.add_argument("command", choices=["plan"])
    ap.parse_args(argv)
    print(plan())
    return 0


if __name__ == "__main__":
    sys.exit(main())
