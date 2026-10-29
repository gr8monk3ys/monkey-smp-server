import datetime as dt
import json
import re
from pathlib import Path

import pytest
import wrapped
from fake_world import FakeWorld

import firsts
import season_calendar
import site_links
from repo import REPO

PACIFIC = season_calendar.PACIFIC
HOUR = wrapped.TICKS_AN_HOUR
LAUNCHED_AT = dt.datetime(2026, 11, 7, 17, 5, tzinfo=PACIFIC)


def launch_scores():
    """The scoreboard right after the launch: staff test play before it (Mod's hours, days and a kill), the
    challenges test play had done already wiped by the launch, and a pass bought in advance."""
    return [("rw.day", "#launched", 1), ("rw.play", "Mod", 5 * HOUR), ("rw.days", "Mod", 3), ("st.kills", "Mod", 2),
            ("rw.founder", "Mod", 1), ("rw.months", "Alex", 1), ("rw.play", "Alex", 600), ("rf", "#claimed", 0)]


def end_scores():
    return [
        ("rw.day", "#launched", 1),
        # Alex: a full season.
        ("rw.play", "Alex", 84 * HOUR + 600), ("rw.days", "Alex", 31), ("st.kills", "Alex", 12),
        ("rw.challenges", "Alex", 9), ("rw.events", "Alex", 4), ("rw.hours", "Alex", 84), ("rw.founder", "Alex", 1),
        ("rw.months", "Alex", 3), ("rw.tier", "Alex", 3), ("st.bounty", "alex", 2),
        # Mod: staff, played before the launch too. A staff reset of st.kills (below the launch's 2) counts in full.
        ("rw.play", "Mod", 7 * HOUR), ("rw.days", "Mod", 5), ("st.kills", "Mod", 1), ("rw.founder", "Mod", 1),
        # Kai: plays, but asked for no page.
        ("rw.play", "Kai", 3 * HOUR), ("rw.days", "Kai", 2), ("rw.founder", "Kai", 1), ("rw.events", "Kai", 3),
        # Blip: five minutes, too little for a page.
        ("rw.play", "Blip", 6000), ("rw.founder", "Blip", 1),
        ("rw.play", "#x", 9 * HOUR)]


def closed(path: Path, end: dt.datetime, rows: list[dict]) -> None:
    path.mkdir(parents=True, exist_ok=True)
    (path / f"{end:%Y-%m-%d}.json").write_text(json.dumps(
        {"start": None, "end": end.isoformat(), "rows": rows, "announced": True, "posted": True}), encoding="utf-8")


def row(name, rank, members):
    return {"name": name, "members": members, "cup": 0, "land": 0, "strength": 0, "kills": 0, "bounties": 0,
            "points": 0, "rank": rank}


def season_files(tmp_path, *, opt_out="Kai  # asked in #help\n\n"):
    start_world = FakeWorld(tmp_path / "launch" / "world").scores(*launch_scores()).path
    assert wrapped.main(["start", str(start_world), "--out", str(tmp_path / "start.json")]) == 0
    world = FakeWorld(tmp_path / "world").scores(*end_scores()).storage("monkey", {"firsts": {"held": {
        "nether": {"name": "Alex", "order": 1, "week": 0}, "dragon": {"name": "Kai", "order": 2, "week": 3},
        "elytra": {"name": "Alex", "order": 3, "week": 3}}}}).path
    weeks = tmp_path / "standings" / "weeks"
    sunday = dt.datetime(2026, 11, 15, 19, 0, tzinfo=PACIFIC)
    closed(weeks, dt.datetime(2026, 11, 1, 19, 0, tzinfo=PACIFIC), [row("Test", 1, ["Alex"])])   # before launch
    closed(weeks, sunday, [row("Red <Monkeys>", 3, ["Alex", "Mod"]), row("Blue", 1, []), row("Gold", 2, [])])
    closed(weeks, sunday + dt.timedelta(weeks=3), [row("Red <Monkeys>", 2, ["Alex"]), row("Blue", 1, [])])
    closed(weeks, sunday + dt.timedelta(weeks=4), [row("Herons", 2, ["Alex"]), row("Blue", 1, [])])
    closed(weeks, sunday + dt.timedelta(weeks=11), [row("Red <Monkeys>", 1, ["Alex"])])   # off-season: left out
    (tmp_path / "opt-out.txt").write_text(opt_out, encoding="utf-8")
    return world


def build(tmp_path, world, *extra, out=None):
    out = out or tmp_path / "site" / "wrapped" / "season-1"
    args = ["build", str(world), "--season", "1", "--standings", str(tmp_path / "standings"),
            "--start", str(tmp_path / "start.json"), "--opt-out", str(tmp_path / "opt-out.txt"), "--out", str(out)]
    assert wrapped.main(args + list(extra)) == 0
    return out


def text(page: Path) -> str:
    """A page's words, tags taken out."""
    return " ".join(re.sub(r"<[^>]+>", " ", page.read_text(encoding="utf-8")).split())


def test_start_keeps_the_scores_at_the_launch_and_refuses_before_it(tmp_path, capsys):
    early = FakeWorld(tmp_path / "early").scores(("rw.play", "Mod", 100)).path
    assert wrapped.main(["start", str(early), "--out", str(tmp_path / "s.json")]) == 1
    assert "hasn't launched" in capsys.readouterr().err and not (tmp_path / "s.json").exists()
    world = FakeWorld(tmp_path / "world").scores(*launch_scores(), ("ev.cup", "red", 5)).path
    assert wrapped.main(["start", str(world), "--out", str(tmp_path / "s.json")]) == 0
    snap = json.loads((tmp_path / "s.json").read_text(encoding="utf-8"))
    assert dt.datetime.fromisoformat(snap["taken"]).tzinfo is not None
    assert snap["scores"]["rw.play"] == {"Alex": 600, "Mod": 5 * HOUR}
    assert snap["scores"]["st.kills"] == {"Mod": 2}
    assert "ev.cup" not in snap["scores"] and "#launched" not in snap["scores"]["rw.day"]


def test_a_card_counts_this_season_only(tmp_path):
    world = season_files(tmp_path)
    start = wrapped.read_start(tmp_path / "start.json")
    weeks = wrapped.closed_weeks(tmp_path / "standings", season_calendar.SEASON)
    cards = {c.name: c for c in wrapped.cards(wrapped.scores(world), firsts.holders(world), start, weeks)}
    assert sorted(cards) == ["Alex", "Kai", "Mod"]     # Blip played under 10 minutes; #x isn't a player
    alex, mod = cards["Alex"], cards["Mod"]
    assert (alex.hours, alex.days, alex.kills, alex.challenges, alex.events, alex.bounties) == ("84", 31, 12, 9, 4, 2)
    # Test play before the launch doesn't count; a counter reset below its start counts in full.
    assert (mod.hours, mod.days, mod.kills) == ("2.0", 2, 1)
    assert [f.id for f in alex.firsts] == ["nether", "elytra"] and cards["Kai"].firsts[0].id == "dragon"
    # Weeks before the launch and after the finale are left out; the best rank's faction is named.
    assert alex.faction == "Herons"
    assert alex.best == wrapped.Rank(2, 2, 4, "Red <Monkeys>")
    assert mod.faction == "Red <Monkeys>" and mod.best == wrapped.Rank(3, 3, 1, "Red <Monkeys>")
    assert cards["Kai"].best is None and cards["Kai"].faction == ""


def test_skins_rarest_first_never_the_bought_ones(tmp_path):
    world = season_files(tmp_path)
    start = wrapped.read_start(tmp_path / "start.json")
    cards = {c.name: c for c in wrapped.cards(wrapped.scores(world), firsts.holders(world), start, [])}
    alex = cards["Alex"]
    # Emberfang (10 hours) only Alex holds; Rallier (3 events) Alex and Kai, Wayfarer (3 days) Alex and Mod (a tie
    # goes by name); Founder's Edge all three. The pass (rw.months) and tier skins (rw.tier) are left out.
    assert [s.id for s in alex.skins][-3:] == ["rallier", "wayfarer", "founders_edge"]
    assert {s.id for s in alex.skins} >= {"emberfang", "wayfarer", "frostbite", "laurel", "trailblazer", "vanguard"}
    assert not {s.id for s in alex.skins} & {"oath_i", "oath_ii", "oath_iii", "lantern", "regalia", "crown"}
    held = {s.id: s for s in alex.skins}
    assert (held["founders_edge"].holders, held["rallier"].holders, held["emberfang"].holders) == (3, 2, 1)
    # Founder's Edge was Mod's before the launch: not new for Mod, new for Alex.
    assert held["founders_edge"].new and not next(s for s in cards["Mod"].skins if s.id == "founders_edge").new


def test_build_writes_the_index_a_page_each_and_the_pictures(tmp_path):
    world = season_files(tmp_path)
    out = build(tmp_path, world)
    assert sorted(p.name for p in out.glob("*.html")) == ["alex.html", "index.html", "mod.html"]
    assert (out / "wrapped.css").is_file() and (out / "skins" / "emberfang.png").read_bytes()[:4] == b"\x89PNG"
    alex = text(out / "alex.html")
    for words in ("84 hours played", "31 days on the server", "12 PvP kills", "9 weekly challenges done",
                  "4 events attended", "Herons. Best weekly rank: 2nd of 2 , week 4, with Red <Monkeys>",
                  "2 bounties claimed", "Enter the Nether the launch weekend, the season's 1st first",
                  "Find an elytra week 3, the season's 3rd first", "Emberfang New this season only them",
                  "Founder's Edge New this season 3 of 3", "7 November 2026 to 23 January 2027"):
        assert words in alex.replace("&#x27;", "'").replace("&lt;", "<").replace("&gt;", ">"), words
    page = (out / "alex.html").read_text(encoding="utf-8")
    assert "Red &lt;Monkeys&gt;" in page and "<Monkeys>" not in page        # a faction's name is escaped
    assert '<meta name="robots" content="noindex">' in page
    assert ('<meta property="og:description" content="Alex on Monkey SMP, Season I: 84 hours over 31 days, '
            '12 PvP kills, 2 Server Firsts, 9 weekly challenges.">') in page
    assert '<meta property="og:url" content="https://monkeysmp.lscaturchio.xyz/wrapped/season-1/alex.html">' in page
    assert "None this season." in text(out / "mod.html") and "No faction" not in text(out / "mod.html")


def test_an_opted_out_player_has_no_page_and_isnt_named(tmp_path):
    world = season_files(tmp_path)
    out = build(tmp_path, world)
    assert not (out / "kai.html").exists()
    index = text(out / "index.html")
    assert "Kai" not in index
    assert "Slay the dragon a player who asked not to be named, week 3" in index
    assert "1 player asked not to have a page." in index
    # The totals still count everyone who played: 84 + 2 + 3 hours, 3 players (Blip too little for a page).
    assert "3 players" in index and "89 hours played" in index and "3 Server Firsts claimed" in index
    assert "The most: Alex , with 2, and the Pioneer title." in index
    assert 'href="alex.html"' in (out / "index.html").read_text(encoding="utf-8")


def test_a_rerun_replaces_its_pages_and_never_touches_other_files(tmp_path):
    world = season_files(tmp_path, opt_out="")
    out = build(tmp_path, world)
    assert (out / "kai.html").exists()
    (tmp_path / "opt-out.txt").write_text("kai\nnobody\n", encoding="utf-8")
    build(tmp_path, world)
    assert not (out / "kai.html").exists() and (out / "alex.html").exists()
    (out / "notes.txt").write_text("mine", encoding="utf-8")
    with pytest.raises(SystemExit, match="notes.txt, which this tool didn't write"):
        build(tmp_path, world)
    assert (out / "alex.html").exists()


def test_without_a_start_season_one_counts_from_zero_and_later_seasons_stop(tmp_path, capsys):
    world = season_files(tmp_path)
    out = tmp_path / "out"
    assert wrapped.main(["build", str(world), "--season", "1", "--standings", str(tmp_path / "standings"),
                         "--out", str(out)]) == 0
    assert "test play before the launch counts" in capsys.readouterr().err
    assert "7.0 hours played" in text(out / "mod.html")
    with pytest.raises(SystemExit, match="Season II needs --start"):
        wrapped.main(["build", str(world), "--season", "2", "--launch", "2027-02-20T17:00-08:00",
                      "--standings", str(tmp_path / "standings"), "--out", str(tmp_path / "out2")])


def test_a_later_season_takes_its_dates_from_its_launch_not_the_start(tmp_path, capsys):
    world = season_files(tmp_path)
    start = tmp_path / "start.json"
    snap = json.loads(start.read_text(encoding="utf-8"))
    snap["taken"] = "2027-02-23T09:00:00-08:00"    # kept three days late
    start.write_text(json.dumps(snap), encoding="utf-8")
    out = tmp_path / "s2"
    args = ["build", str(world), "--season", "2", "--standings", str(tmp_path / "standings"), "--start", str(start),
            "--out", str(out)]
    with pytest.raises(SystemExit, match="Season II needs --launch"):
        wrapped.main(args)
    with pytest.raises(SystemExit):
        wrapped.main([*args, "--launch", "2027-02-20T17:00"])    # no UTC offset
    assert "--launch" in capsys.readouterr().err
    assert wrapped.main([*args, "--launch", "2027-02-20T17:00-08:00"]) == 0
    assert "20 February 2027 to 8 May 2027" in text(out / "index.html")     # from the launch, not the start
    assert "not at the launch" in capsys.readouterr().err                  # and the late start is flagged
    assert "No faction in the weekly standings this season." in text(out / "alex.html")   # Season I's weeks


def test_the_pages_point_at_the_sites_own_files():
    # The pages sit in site/public/wrapped/season-<n>/: two folders up is what the site serves, a file from
    # site/public/ or one of its pages, built as <page>.html (site/src/app/<page>/page.tsx), so the links work on
    # any static server as well as on Vercel, where clean URLs redirect them.
    site = REPO.root / "site"
    config = (site / "src" / "lib" / "config.ts").read_text(encoding="utf-8")
    assert f'SITE_URL = "{wrapped.SITE}"' in config
    page = wrapped.head("t", "d", "u") + wrapped.foot({}, dt.date(2027, 1, 17))
    refs = re.findall(r'(?:href|src)="\.\./\.\./([^"#]*)', page)
    assert "wrapped/site.css" in refs and "changes.html" in refs
    for ref in refs:
        page = site / "src" / "app" / ref.removesuffix(".html") / "page.tsx"
        assert (site / "public" / ref).is_file() or page.is_file(), ref
    assert (site / "public" / "img" / "og.jpg").is_file()
    assert wrapped.slug("Steve_01") == "steve_01" and wrapped.slug(".bedrock").startswith("player-")
    assert [wrapped.ordinal(n) for n in (1, 2, 3, 4, 11, 12, 13, 21, 22, 101)] == [
        "1st", "2nd", "3rd", "4th", "11th", "12th", "13th", "21st", "22nd", "101st"]


def test_a_start_kept_away_from_the_launch_is_flagged(tmp_path, capsys):
    world = season_files(tmp_path)
    start = tmp_path / "start.json"
    snap = json.loads(start.read_text(encoding="utf-8"))
    for taken, flagged in (("2026-11-01T17:01:00-08:00", True), ("2026-11-07T17:02:00-08:00", False),
                           ("2026-11-09T09:00:00-08:00", True)):
        start.write_text(json.dumps(snap | {"taken": taken}), encoding="utf-8")
        build(tmp_path, world)
        assert ("not at the launch" in capsys.readouterr().err) is flagged, taken


def test_a_damaged_closed_week_is_left_out(tmp_path, capsys):
    weeks = tmp_path / "weeks"
    sunday = dt.datetime(2026, 11, 15, 19, 0, tzinfo=PACIFIC)
    closed(weeks, sunday, [row("Red", 1, ["Alex"]), row("Blue", None, ["Kai"]), "junk"])
    (weeks / "2026-11-22.json").write_text('{"end": "2026-11-22T19:00:00", "rows": []}', encoding="utf-8")
    (weeks / "2026-11-29.json").write_text("not json", encoding="utf-8")
    found = wrapped.closed_weeks(tmp_path, season_calendar.SEASON)
    assert [len(w["rows"]) for w in found] == [1]
    assert capsys.readouterr().err.count("left out") == 2
    assert wrapped.faction_ranks("kai", found) == ("", None)


# ---------------------------------------------------------------- the review of #69


def test_a_player_named_index_never_replaces_the_index(tmp_path):
    world = season_files(tmp_path)
    FakeWorld(world).scores(*end_scores(), ("rw.play", "Index", 2 * HOUR))
    out = build(tmp_path, world)
    page = wrapped.slug("Index")
    assert page.startswith("player-") and wrapped.slug("INDEX") != "index"
    assert "Season I, player by player" in text(out / "index.html")
    assert "Index" in text(out / f"{page}.html") and f'href="{page}.html"' in (out / "index.html").read_text("utf-8")


def test_bedrock_names_get_distinct_fixed_length_pages(tmp_path, monkeypatch):
    one, two, short = wrapped.slug(".BedrockPlayer1"), wrapped.slug(".BedrockPlayer2"), wrapped.slug(".a")
    assert len({one, two, short}) == 3 and len(one) == len(two) == len(short) == len("player-") + 16
    world = season_files(tmp_path)
    monkeypatch.setattr(wrapped, "slug", lambda name: "same")
    with pytest.raises(SystemExit, match="would share the page same.html"):
        build(tmp_path, world)
    assert not (tmp_path / "site").exists()


def test_start_never_replaces_the_launchs_file_without_force(tmp_path, capsys):
    world = FakeWorld(tmp_path / "world").scores(*launch_scores()).path
    out = tmp_path / "start.json"
    assert wrapped.main(["start", str(world), "--out", str(out)]) == 0
    first = out.read_text(encoding="utf-8")
    FakeWorld(world).scores(*launch_scores(), ("rw.play", "Late", 99))
    assert wrapped.main(["start", str(world), "--out", str(out)]) == 1
    assert "--force" in capsys.readouterr().err and out.read_text(encoding="utf-8") == first
    assert wrapped.main(["start", str(world), "--out", str(out), "--force"]) == 0
    assert (tmp_path / "start.json.bak").read_text(encoding="utf-8") == first
    assert "Late" in json.loads(out.read_text(encoding="utf-8"))["scores"]["rw.play"]


def test_a_late_close_counts_for_the_week_it_closed(tmp_path):
    weeks = tmp_path / "weeks"
    season = season_calendar.SEASON
    sunday = dt.datetime(2026, 11, 15, 19, 0, tzinfo=PACIFIC)                 # week 1's close
    finale = sunday + dt.timedelta(weeks=wrapped.FINALE_WEEK - 1)              # week 11's, Sunday 7 PM
    late = dt.timedelta(hours=5, minutes=30)                                    # Monday 12:30 AM, after a reboot

    def week_file(begun, end, rank, name):
        weeks.mkdir(parents=True, exist_ok=True)
        (weeks / f"{end:%Y-%m-%d-%H}.json").write_text(json.dumps(
            {"start": begun.isoformat() if begun else None, "end": end.isoformat(),
             "rows": [row(name, rank, ["Alex"])]}), encoding="utf-8")

    week_file(sunday - dt.timedelta(weeks=1), sunday + late, 3, "Week one")
    week_file(None, sunday + dt.timedelta(weeks=1) + late, 2, "Week two")             # no start saved
    week_file(finale - dt.timedelta(weeks=1), finale + late, 1, "The finale")
    week_file(finale, finale + dt.timedelta(weeks=1), 1, "Off-season")              # week 12: left out
    found = wrapped.closed_weeks(tmp_path, season)
    assert [(w["week"], w["rows"][0]["name"]) for w in found] == [(1, "Week one"), (2, "Week two"),
                                                                  (wrapped.FINALE_WEEK, "The finale")]
    assert wrapped.faction_ranks("alex", found)[1] == wrapped.Rank(1, 1, wrapped.FINALE_WEEK, "The finale")


def test_a_link_not_set_yet_goes_to_the_discord_titled_coming_soon():
    links = {"DISCORD_INVITE": "https://discord.gg/x", "MAP_URL": ""}
    foot = wrapped.foot(links, dt.date(2027, 1, 17))
    assert f'<a href="https://discord.gg/x" title="{site_links.SOON}">Live map</a>' in foot
    assert '<a href="https://discord.gg/x">Discord</a>' in foot
    assert "Live map" not in wrapped.foot({}, dt.date(2027, 1, 17))
    assert '<a href="https://map.example">Live map</a>' in wrapped.foot(links | {"MAP_URL": "https://map.example"},
                                                                       dt.date(2027, 1, 17))


def test_a_build_that_fails_part_way_leaves_the_earlier_pages(tmp_path, monkeypatch):
    world = season_files(tmp_path, opt_out="")
    out = build(tmp_path, world)
    before = {p.relative_to(out): p.read_bytes() for p in out.rglob("*") if p.is_file()}
    written = []
    real = wrapped.write

    def fails_on_the_third(path, data):
        written.append(path)
        if len(written) == 3:
            raise OSError("disk full")
        real(path, data)
    monkeypatch.setattr(wrapped, "write", fails_on_the_third)
    (tmp_path / "opt-out.txt").write_text("kai\n", encoding="utf-8")
    with pytest.raises(OSError, match="disk full"):
        build(tmp_path, world)
    assert {p.relative_to(out): p.read_bytes() for p in out.rglob("*") if p.is_file()} == before
    assert sorted(p.name for p in out.parent.iterdir()) == ["season-1"]        # nothing half-made left beside it
    monkeypatch.setattr(wrapped, "write", real)
    build(tmp_path, world)
    assert not (out / "kai.html").exists() and sorted(p.name for p in out.parent.iterdir()) == ["season-1"]


def test_a_start_without_a_utc_offset_is_refused(tmp_path):
    start = tmp_path / "start.json"
    start.write_text(json.dumps({"taken": "2026-11-07T17:02:00", "scores": {}}), encoding="utf-8")
    with pytest.raises(SystemExit, match="is not a file `wrapped.py start` wrote .*no UTC offset"):
        wrapped.read_start(start)


def test_build_reads_the_world_once(tmp_path, monkeypatch):
    world = season_files(tmp_path)
    calls = {"holders": 0, "scores": 0}
    holders, scores = firsts.holders, wrapped.scores

    def counted(name, real):
        def call(*args):
            calls[name] += 1
            return real(*args)
        return call
    monkeypatch.setattr(firsts, "holders", counted("holders", holders))
    monkeypatch.setattr(wrapped, "scores", counted("scores", scores))
    build(tmp_path, world)
    assert calls == {"holders": 1, "scores": 1}


@pytest.mark.parametrize(("ticks", "shown"), [
    (int(9.94 * HOUR), "9.9"), (int(9.96 * HOUR), "10"), (int(9.999 * HOUR), "10"), (10 * HOUR, "10"),
    (int(10.49 * HOUR), "10"), (int(10.51 * HOUR), "11"), (int(0.04 * HOUR), "0.0"), (0, "0.0")])
def test_hours_round_once(ticks, shown):
    assert wrapped.hours(ticks) == shown
    assert wrapped.Card("A", "a", ticks, 0, 0, 0, 0, 0).hours == shown


def test_the_index_total_rounds_as_the_cards_do(tmp_path):
    world = season_files(tmp_path)
    # Alex 84 h (and 10 minutes), Mod 2, Kai 3, Zed 0.6: 89.6 hours, which floor division showed as 89.
    FakeWorld(world).scores(*end_scores(), ("rw.play", "Zed", int(0.6 * HOUR)))
    out = build(tmp_path, world)
    assert "90 hours played" in text(out / "index.html")
