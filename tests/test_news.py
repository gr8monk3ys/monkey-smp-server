"""tools/news.py and deploy/monkey-news.sh: what is news, firsts per season, the limits, never posting twice.

The saved files are shaped as Minecraft 26.3 writes them (tests/fake_world.py): advancements as on a 26.3 test
server's players/advancements/<uuid>.json (2026-10-25, DataVersion 5023), the ids from the 26.3 server jar's
data/minecraft/advancement/, the firsts' claims as the monkey-firsts pack stores them (tools/firsts.py). Players,
UUIDs and factions are made up.
"""
import datetime as dt
import http.client
import json
import os
import re
import shutil
import subprocess
import urllib.error
import uuid

import pytest
from fake_world import FakeWorld, member

import firsts
import news
import saved_world
import season_calendar
from repo import REPO

LAUNCH = season_calendar.LAUNCH                       # Saturday 7 November 2026, 5 PM Pacific
AFTER = LAUNCH + dt.timedelta(minutes=10)              # the first run after the launch
URL = "https://discord.com/api/webhooks/1/secret-token"
NAMES = ["Alex_Fake", "SamFake", "TomFake", "RinFake"]
PLAYERS = {name: str(uuid.uuid5(uuid.NAMESPACE_DNS, name)) for name in NAMES}
MONSTERS = "minecraft:adventure/kill_all_mobs"
DIET = "minecraft:husbandry/balanced_diet"


def saved_time(when: dt.datetime) -> str:
    """A criterion's time as 26.3 saves it: the server's local time with its offset."""
    return when.astimezone(season_calendar.PACIFIC).strftime("%Y-%m-%d %H:%M:%S %z")


def world(tmp_path, *, launched=True, season=1, held=None, advancements=None, parties=(), extra_scores=(),
          storage=None):
    """A saved world: the launch and season scores, firsts claims {id: (name, order)}, advancements {player:
    {adv: when}}, parties [(party id, owner name, faction name or None)], more of the monkey storage (diplomacy,
    factions) and the usercache with every player."""
    rows = [("rw.day", "#launched", 1 if launched else 0), ("rw.day", "#season", season), *extra_scores]
    fake = FakeWorld(tmp_path / "server" / "world").scores(*rows)
    if held or storage:
        fake.storage("monkey", {**(storage or {}), "firsts": {"held": {
            k: {"name": name, "order": order, "week": 0} for k, (name, order) in (held or {}).items()}}})
    for name, done in (advancements or {}).items():
        fake.advancements(PLAYERS[name], {adv: saved_time(when) for adv, when in done.items()})
    for party_id, owner, faction in parties:
        fake.party(party_id, member(PLAYERS[owner], owner), [member(PLAYERS[owner], owner)])
        if faction:
            fake.party_name(PLAYERS[owner], faction)
    (fake.path.parent / "usercache.json").write_text(json.dumps(
        [{"uuid": u, "name": n, "expiresOn": "2026-11-30 12:00:00 -0800"} for n, u in PLAYERS.items()]))
    return fake.path


def http_error(code):
    return urllib.error.HTTPError(URL, code, "no", {}, None)


class Discord:
    """A fake urlopen: records each post's JSON body; each of `fail` in turn is raised instead of answering."""

    def __init__(self, fail=()):
        self.posts, self.fail = [], list(fail)

    def __call__(self, request, timeout):
        assert request.full_url == URL and request.get_method() == "POST"
        body = json.loads(request.data)
        if self.fail:
            raise self.fail.pop(0)
        self.posts.append(body)

        class Answer:
            def __enter__(self):
                return self

            def __exit__(self, *_):
                return False

            def read(self):
                return b""
        return Answer()

    @property
    def lines(self):
        return [p["content"] for p in self.posts]


def armed(state, now, season=1):
    """The season's file as the runs before its launch leave it: the last one saw the world unlaunched five
    minutes before the launch (season 1: the calendar's, when `now` is after it) or before `now`."""
    before = (min(now, LAUNCH) if season == 1 else now) - dt.timedelta(minutes=5)
    kept = news.new_state(season, before)
    kept.update(unlaunched=news.iso(before), last_run=news.iso(before))
    state.mkdir(parents=True, exist_ok=True)
    (state / f"season-{season}.json").write_text(json.dumps(kept))


def run(folder, state, now, discord, arm=True):
    """One timer run. `arm`: the feed was on before the launch (the season's file is made as its runs make it)."""
    season = news.read_saved(folder).season
    if arm and not (state / f"season-{season}.json").exists():
        armed(state, now, season)
    return news.post(folder, state, now, URL, urlopen=discord, sleep=lambda s: None)


def saved(state, season=1):
    return json.loads((state / f"season-{season}.json").read_text())


# ---------------------------------------------------------------- what is news


def test_every_first_line_is_a_firsts_milestone_and_the_early_ones_stay_in_game():
    ids = {m["id"] for m in firsts.MILESTONES}
    assert set(news.FIRST_LINES) <= ids
    assert {"diamond", "fortress", "bastion", "debris", "vault"}.isdisjoint(news.FIRST_LINES)
    for line in news.FIRST_LINES.values():
        assert line.count("{p}") == 1 and line.endswith(". First this season.")
    assert news.FIRST_LINES["dragon"].format(p="Steve") == "Steve killed the Ender Dragon. First this season."


def test_challenges_are_vanilla_ids_the_firsts_and_rules_dont_already_cover():
    mirrored = {"minecraft:" + m["mirrors"] for m in firsts.MILESTONES if m.get("mirrors")}
    for adv, title in news.CHALLENGES.items():
        assert re.fullmatch(r"minecraft:(adventure|husbandry|nether|end|story)/[a-z_]+", adv), adv
        assert adv not in mirrored and title and title == title.strip()
    banned = {"minecraft:adventure/totem_of_undying", "minecraft:end/respawn_dragon",
              "minecraft:adventure/hero_of_the_village", "minecraft:end/kill_dragon", "minecraft:end/elytra",
              "minecraft:nether/netherite_armor"}
    assert banned.isdisjoint(news.CHALLENGES)
    assert news.CHALLENGE_LINE.format(p="Steve", title="Monsters Hunted") == \
        "Steve completed Monsters Hunted. First this season."


def test_saved_advancements_keep_only_finished_wanted_ones_with_their_last_criterion(tmp_path):
    fake = FakeWorld(tmp_path / "world")
    assert saved_world.advancements(fake.path, {MONSTERS}) == {}   # no players folder yet
    alex = PLAYERS["Alex_Fake"]
    fake.advancements(alex, {MONSTERS: "2026-10-31 18:30:00 -0700",
                             "minecraft:story/mine_stone": "2026-10-31 17:01:00 -0700"},
                      undone={DIET: "2026-10-31 18:00:00 -0700"})
    # A finished advancement with several criteria: done when the last one was.
    path = fake.path / "players" / "advancements" / f"{alex}.json"
    data = json.loads(path.read_text())
    data[MONSTERS]["criteria"] = {"minecraft:zombie": "2026-10-31 17:20:00 -0700",
                                  "minecraft:warden": "2026-10-31 19:45:10 -0700"}
    path.write_text(json.dumps(data))
    found = saved_world.advancements(fake.path, {MONSTERS, DIET})
    assert found == {alex: {MONSTERS: dt.datetime(2026, 10, 31, 19, 45, 10,
                                                  tzinfo=dt.timezone(dt.timedelta(hours=-7)))}}
    path.write_text("{ half a file")
    with pytest.raises(ValueError, match=f"{alex}.json"):
        saved_world.advancements(fake.path, {MONSTERS})


def test_the_first_finish_is_the_earliest_since_the_launch_whoever_was_saved_first(tmp_path):
    folder = world(tmp_path, advancements={
        "Alex_Fake": {MONSTERS: LAUNCH + dt.timedelta(hours=5)},
        "SamFake": {MONSTERS: LAUNCH + dt.timedelta(hours=3), DIET: LAUNCH - dt.timedelta(hours=2)},   # test play
        "TomFake": {DIET: LAUNCH + dt.timedelta(hours=9)},
    })
    items = {i.key: i for i in news.challenge_items(folder, LAUNCH, news.read_saved(folder))}
    assert items[f"challenge:{MONSTERS}"].text == "SamFake completed Monsters Hunted. First this season."
    assert items[f"challenge:{DIET}"].text == "TomFake completed A Balanced Diet. First this season."
    assert items[f"challenge:{DIET}"].at == (LAUNCH + dt.timedelta(hours=9)).astimezone(dt.UTC).isoformat()


def test_names_are_escaped_and_a_player_without_a_name_is_passed_over(tmp_path):
    folder = world(tmp_path, held={"dragon": ("Alex_Fake", 1)}, advancements={"RinFake": {MONSTERS: AFTER}})
    cache = folder.parent / "usercache.json"
    cache.write_text(json.dumps([e for e in json.loads(cache.read_text()) if e["name"] != "RinFake"]))
    saved_now = news.read_saved(folder)
    assert [i.text for i in news.first_items(folder, saved_now)] == [
        r"Alex\_Fake killed the Ender Dragon. First this season."]
    assert news.challenge_items(folder, LAUNCH, saved_now) == []


FACTION_NAMES = {"names": {"f1": {"text": "Red_Monkeys"}, "f2": {"text": "Blue Herons"}}}
WARS = {"factions": FACTION_NAMES, "diplomacy": {"log": [{"kind": "declare", "a": 1, "b": 2, "n": 4}]}}


def test_a_seven_day_war_posts_when_declared_and_when_it_ends(tmp_path):
    log = [{"kind": "war", "a": 1, "b": 2, "n": 1},   # a war until Sunday's close stays in game and the recap
           {"kind": "declare", "a": 1, "b": 2, "n": 4},
           {"kind": "war_end", "a": 1, "b": 9, "n": 5, "how": "time", "ka": 3, "kb": 7},
           {"kind": "war_end", "a": 1, "b": 2, "n": 6, "how": "peace", "ka": 2, "kb": 1},
           {"kind": "war_end", "a": 1, "b": 2, "n": 7, "how": "staff", "ka": 0, "kb": 0}]
    folder = world(tmp_path, storage={"factions": FACTION_NAMES,
                                      "diplomacy": {"log": log, "gone": {"f9": {"text": "Gold Lemurs"}}}})
    items = news.war_items(folder)
    assert [(i.key, i.text) for i in items] == [
        ("war:4", r"War: Red\_Monkeys declared a 7-day war on Blue Herons."),
        ("war:5", r"Gold Lemurs won its war with Red\_Monkeys, 7 kills to 3."),   # a gone faction keeps its name
        ("war:6", r"Red\_Monkeys and Blue Herons ended their war with a pact, 2 kills to 1."),
    ]


def test_a_war_post_waits_out_the_limits_even_after_the_close_trims_the_log(tmp_path):
    folder = world(tmp_path, storage=WARS)
    state, discord = tmp_path / "news", Discord()
    entry = {"kind": news.WAR, "text": "x", "at": None, "order": 4, "seen": news.iso(AFTER), "status": news.PENDING}
    st = news.new_state(1, AFTER)
    st["items"]["war:4"] = entry
    news.merge(st, [], AFTER, [], False)   # the log no longer has it
    assert not entry.get("gone")
    run(folder, state, AFTER, discord)
    assert discord.lines == [r"War: Red\_Monkeys declared a 7-day war on Blue Herons."]


def siege_rows(on=1, open_=0, opened=None, closed=None, now=None):
    rows = [("sg", "#on", on), ("sg", "#open", open_)]
    rows += [("sg", k, v) for k, v in (("#opened", opened), ("#closed", closed), ("#now", now)) if v is not None]
    return rows


OPENED = int(season_calendar.LAUNCH.timestamp()) // 60 + 4 * 24 * 60 + 2 * 60   # Wed 11 Nov, 7 PM Pacific


def test_a_siege_window_posts_when_it_opens_and_when_it_closes_and_nothing_while_off(tmp_path):
    def items(**kw):
        return [(i.key, i.text) for i in news.siege_items(news.read_saved(world(tmp_path, extra_scores=siege_rows(
            **kw))))]
    assert items(open_=1, opened=OPENED, now=OPENED + 3) == [
        (f"siege:open:{OPENED}", "Outpost siege open until 9 PM Pacific: capture an outpost for a bonus hour "
                                 "held. Faction claims stay protected. `/trigger sieges` in game.")]
    closed = OPENED + 120
    assert items(opened=OPENED, closed=closed, now=closed + 10) == [
        (f"siege:closed:{closed}", "The outpost siege is over: captures earn no bonus until the next one.")]
    assert items(opened=OPENED, closed=closed, now=closed + news.CLOSE_FRESH + 1) == []   # old news
    assert items(on=0, open_=1, opened=OPENED, now=OPENED) == []
    assert items(on=0, closed=closed, now=closed) == []


def test_an_open_post_that_missed_its_window_is_never_posted(tmp_path):
    state, discord = tmp_path / "news", Discord()
    rows = siege_rows(open_=1, opened=OPENED, now=OPENED)
    run(world(tmp_path, extra_scores=rows), state, AFTER, discord)
    assert discord.lines == [news.SIEGE_OPEN.format(end="9 PM")]
    # the close is a new item; an open item no longer in the world is "gone" and waits, never posted late
    shutil.rmtree(tmp_path / "server")
    run(world(tmp_path, extra_scores=siege_rows(opened=OPENED, closed=OPENED + 120, now=OPENED + 125)), state,
        AFTER + dt.timedelta(minutes=10), discord)
    assert discord.lines[-1] == news.SIEGE_CLOSED


# ---------------------------------------------------------------- posting


def test_runs_before_the_launch_post_nothing_and_note_the_world_unlaunched(tmp_path):
    folder = world(tmp_path, launched=False, held={"dragon": ("SamFake", 1)})
    state, discord = tmp_path / "news", Discord()
    assert run(folder, state, LAUNCH - dt.timedelta(minutes=5), discord, arm=False) == 0
    kept = saved(state)
    assert discord.posts == [] and kept["launched"] is None and kept["items"] == {}
    assert kept["unlaunched"] == news.iso(LAUNCH - dt.timedelta(minutes=5))


def test_no_webhook_posts_nothing_and_keeps_nothing(tmp_path):
    folder, state = world(tmp_path, held={"dragon": ("SamFake", 1)}), tmp_path / "news"
    assert news.post(folder, state, AFTER, "") == 0 and not state.exists()


def test_a_launch_night_run_posts_firsts_and_factions_and_never_the_same_twice(tmp_path):
    folder = world(tmp_path, held={"diamond": ("TomFake", 1), "nether": ("Alex_Fake", 2)},
                   advancements={"SamFake": {MONSTERS: LAUNCH + dt.timedelta(minutes=5)}},
                   parties=[("p-red", "SamFake", "Red Wolves")])
    state, discord = tmp_path / "news", Discord()
    assert run(folder, state, AFTER, discord) == 0
    # The diamond stays in game; the challenge settles first; two posts a run.
    assert discord.lines == [r"Alex\_Fake reached the Nether. First this season.",
                             "New faction: Red Wolves, led by SamFake."]
    assert all(p["allowed_mentions"] == {"parse": []} for p in discord.posts)
    assert run(folder, state, AFTER + dt.timedelta(minutes=10), discord) == 0
    assert len(discord.posts) == 2   # still settling
    assert run(folder, state, AFTER + news.SETTLE, discord) == 0
    assert discord.lines[2:] == ["SamFake completed Monsters Hunted. First this season."]
    for minutes in (40, 50, 60):
        assert run(folder, state, AFTER + dt.timedelta(minutes=minutes), discord) == 0
    assert len(discord.posts) == 3
    kept = saved(state)
    assert {k: e["status"] for k, e in kept["items"].items()} == {
        "first:nether": "posted", "faction:p-red": "posted", f"challenge:{MONSTERS}": "posted"}
    assert kept["late"] is False and kept["sending"] is None
    assert URL not in (state / "season-1.json").read_text()


def test_a_challenge_moves_to_an_earlier_finish_saved_while_it_settles(tmp_path):
    folder = world(tmp_path, advancements={"Alex_Fake": {MONSTERS: LAUNCH + dt.timedelta(hours=2)}})
    state, discord = tmp_path / "news", Discord()
    run(folder, state, LAUNCH + dt.timedelta(hours=2, minutes=5), discord)
    FakeWorld(folder).advancements(PLAYERS["TomFake"], {MONSTERS: saved_time(LAUNCH + dt.timedelta(hours=1))})
    run(folder, state, LAUNCH + dt.timedelta(hours=2, minutes=15), discord)
    run(folder, state, LAUNCH + dt.timedelta(hours=2, minutes=25), discord)
    assert discord.lines == ["TomFake completed Monsters Hunted. First this season."]


def test_a_first_reopened_before_it_posted_waits_and_posts_its_new_holder(tmp_path):
    held = {"nether": ("Alex_Fake", 1), "raid": ("SamFake", 2), "dragon": ("TomFake", 3)}
    folder, state, discord = world(tmp_path, held=held), tmp_path / "news", Discord()
    run(folder, state, AFTER, discord)   # two a run: the dragon waits
    world(tmp_path, held={k: v for k, v in held.items() if k != "dragon"})   # staff reopened it
    run(folder, state, AFTER + dt.timedelta(minutes=10), discord)
    assert len(discord.posts) == 2 and saved(state)["items"]["first:dragon"]["gone"] is True
    world(tmp_path, held=held | {"dragon": ("RinFake", 3)})
    run(folder, state, AFTER + dt.timedelta(minutes=20), discord)
    assert discord.lines[2:] == ["RinFake killed the Ender Dragon. First this season."]


def test_the_limits_hold_and_what_waits_posts_in_claim_order_or_is_dropped_when_stale(tmp_path):
    held = {"nether": ("Alex_Fake", 1), "raid": ("SamFake", 2), "beacon": ("TomFake", 3), "mace": ("RinFake", 4),
            "wither": ("SamFake", 5), "end": ("Alex_Fake", 6)}
    folder, state, discord = world(tmp_path, held=held), tmp_path / "news", Discord()
    for minutes in range(0, 60, 10):   # six runs in an hour
        run(folder, state, AFTER + dt.timedelta(minutes=minutes), discord)
    # Two a run, four firsts a day.
    assert [line.split(" ", 1)[1] for line in discord.lines] == [
        "reached the Nether. First this season.", "won a raid. First this season.",
        "lit a beacon. First this season.", "got a mace. First this season."]
    out = news.due(saved(state), AFTER + dt.timedelta(hours=1))[1]
    assert out == ["first:wither: over the limit for firsts (4 a day)",
                   "first:end: over the limit for firsts (4 a day)"]
    # A day after the first two posts, the window frees two.
    run(folder, state, AFTER + news.DAY, discord)
    assert discord.lines[4:] == ["SamFake defeated the Wither. First this season.",
                                 r"Alex\_Fake entered the End. First this season."]

    # What waits too long is dropped: never posted.
    folder2, state2, discord2 = world(tmp_path / "b", held=held), tmp_path / "b" / "news", Discord()
    run(folder2, state2, AFTER, discord2)
    run(folder2, state2, AFTER + dt.timedelta(minutes=10), discord2)
    run(folder2, state2, AFTER + news.STALE + dt.timedelta(minutes=1), discord2)
    assert len(discord2.posts) == 4
    assert {k: e["status"] for k, e in saved(state2)["items"].items() if e["status"] != "posted"} == {
        "first:wither": "dropped", "first:end": "dropped"}


def test_every_kind_together_stays_under_the_daily_cap(tmp_path):
    held = {k: (NAMES[i % 4], i + 1) for i, k in enumerate(["nether", "raid", "beacon", "mace"])}
    advs = {"Alex_Fake": {adv: AFTER for adv in list(news.CHALLENGES)[:3]}}
    parties = [("p-a", "SamFake", "A Team")]
    folder = world(tmp_path, held=held, advancements=advs, parties=parties, storage=WARS)
    state, discord = tmp_path / "news", Discord()
    for minutes in range(0, 24 * 60, 10):
        run(folder, state, AFTER + dt.timedelta(minutes=minutes), discord)
    kinds = [p["kind"] for p in saved(state)["posts"]]
    assert len(kinds) == news.DAILY and kinds.count("challenge") == news.LIMITS["challenge"]
    assert kinds.count("first") <= news.LIMITS["first"]


def test_new_factions_found_together_share_one_line(tmp_path):
    parties = [("p-1", "Alex_Fake", "Red Wolves"), ("p-2", "SamFake", None), ("p-3", "TomFake", "**@everyone**")]
    folder, state, discord = world(tmp_path, parties=parties), tmp_path / "news", Discord()
    run(folder, state, AFTER, discord)
    assert discord.lines == [r"New factions: Red Wolves, SamFake's faction and \*\*@everyone\*\*."]
    FakeWorld(folder).party("p-4", member(PLAYERS["RinFake"], "RinFake"), [member(PLAYERS["RinFake"], "RinFake")])
    run(folder, state, AFTER + dt.timedelta(minutes=10), discord)
    assert discord.lines[1:] == ["New faction: RinFake's faction."]
    assert all(p["allowed_mentions"] == {"parse": []} for p in discord.posts)


def test_a_run_killed_mid_post_counts_it_as_posted_and_against_the_limits(tmp_path, capsys, monkeypatch):
    held = {"nether": ("Alex_Fake", 1), "raid": ("SamFake", 2), "beacon": ("TomFake", 3), "mace": ("RinFake", 4),
            "wither": ("SamFake", 5)}
    folder, state, discord = world(tmp_path, held=held), tmp_path / "news", Discord()
    run(folder, state, AFTER, discord)   # nether and raid
    real = news.send

    def killed(*a, **k):
        raise KeyboardInterrupt   # the run dies after the state was written "sending"
    monkeypatch.setattr(news, "send", killed)
    with pytest.raises(KeyboardInterrupt):
        run(folder, state, AFTER + dt.timedelta(minutes=10), discord)
    assert saved(state)["sending"]["keys"] == ["first:beacon"]
    monkeypatch.setattr(news, "send", real)
    run(folder, state, AFTER + dt.timedelta(minutes=20), discord)
    assert "counted as posted, not sent again" in capsys.readouterr().out
    kept = saved(state)
    assert kept["items"]["first:beacon"]["status"] == "posted" and kept["sending"] is None
    # The lost post still counts: four firsts in the day are nether, raid, beacon and mace, so the Wither waits.
    assert [p["keys"] for p in kept["posts"]] == [["first:nether"], ["first:raid"], ["first:beacon"], ["first:mace"]]
    assert discord.lines[2:] == ["RinFake got a mace. First this season."]
    assert kept["items"]["first:wither"]["status"] == "pending"


def test_a_refused_post_waits_for_the_next_run_and_never_shows_the_url(tmp_path, capsys):
    folder, state = world(tmp_path, held={"dragon": ("SamFake", 1), "end": ("TomFake", 2)}), tmp_path / "news"
    for refusal in (http_error(429), urllib.error.URLError(ConnectionRefusedError("refused"))):
        discord = Discord(fail=[refusal])
        assert run(folder, state, AFTER, discord) == 1
        out = capsys.readouterr()
        assert "the next run tries again" in out.err and "secret-token" not in out.out + out.err
        assert {e["status"] for e in saved(state)["items"].values()} == {"pending"} and saved(state)["posts"] == []
    assert run(folder, state, AFTER + dt.timedelta(minutes=10), discord) == 0
    assert discord.lines == ["SamFake killed the Ender Dragon. First this season.",
                             "TomFake entered the End. First this season."]


@pytest.mark.parametrize("lost", [TimeoutError("timed out"), ConnectionResetError("reset"),
                                  http.client.RemoteDisconnected("closed"), http_error(503)],
                         ids=["timeout", "reset", "disconnected", "http-503"])
def test_a_post_whose_answer_is_lost_counts_as_posted_never_sent_twice(tmp_path, capsys, lost):
    folder, state = world(tmp_path, held={"dragon": ("SamFake", 1)}), tmp_path / "news"
    discord = Discord(fail=[lost])
    assert run(folder, state, AFTER, discord) == 1
    out = capsys.readouterr()
    assert "counted as posted, never sent again" in out.err and "secret-token" not in out.out + out.err
    kept = saved(state)
    assert kept["items"]["first:dragon"]["status"] == "posted" and len(kept["posts"]) == 1
    assert run(folder, state, AFTER + dt.timedelta(minutes=10), discord) == 0 and discord.posts == []


def test_firsts_post_in_the_order_they_were_claimed(tmp_path):
    folder = world(tmp_path, held={"dragon": ("SamFake", 2), "end": ("TomFake", 1)})
    state, discord = tmp_path / "news", Discord()
    run(folder, state, AFTER, discord)
    assert discord.lines == ["TomFake entered the End. First this season.",
                             "SamFake killed the Ender Dragon. First this season."]


def test_an_unreadable_source_at_the_launch_waits_and_later_only_skips_itself(tmp_path):
    folder = world(tmp_path, held={"dragon": ("SamFake", 1)})
    (folder / "players" / "advancements").mkdir(parents=True)
    (folder / "players" / "advancements" / f"{PLAYERS['TomFake']}.json").write_text("{")
    state, discord = tmp_path / "news", Discord()
    assert run(folder, state, AFTER, discord) == 1 and discord.posts == [] and saved(state)["launched"] is None
    (folder / "players" / "advancements" / f"{PLAYERS['TomFake']}.json").unlink()
    assert run(folder, state, AFTER + dt.timedelta(minutes=10), discord) == 0 and len(discord.posts) == 1
    assert saved(state)["late"] is False
    # Later, a bad file only skips that source for the run.
    (folder / "players" / "advancements" / f"{PLAYERS['TomFake']}.json").write_text("{")
    FakeWorld(folder).party("p-1", member(PLAYERS["RinFake"], "RinFake"), [member(PLAYERS["RinFake"], "RinFake")])
    assert run(folder, state, AFTER + dt.timedelta(minutes=20), discord) == 1
    assert discord.lines[1:] == ["New faction: RinFake's faction."]


@pytest.mark.parametrize("error", [FileNotFoundError("party gone"), PermissionError("denied"),
                                   ModuleNotFoundError("No module named 'tomllib'")],
                         ids=["gone", "denied", "no-tomllib"])
def test_a_file_error_or_missing_module_skips_only_that_source(tmp_path, monkeypatch, capsys, error):
    folder = world(tmp_path, held={"dragon": ("SamFake", 1)}, parties=[("p-1", "Alex_Fake", "Red Wolves")])
    state, discord = tmp_path / "news", Discord()
    run(folder, state, AFTER, discord)
    world(tmp_path, held={"dragon": ("SamFake", 1), "end": ("TomFake", 2)})

    def broken(_world):
        raise error
    monkeypatch.setattr(news.saved_world, "parties", broken)
    assert run(folder, state, AFTER + dt.timedelta(minutes=10), discord) == 1
    assert discord.lines[2:] == ["TomFake entered the End. First this season."]
    assert f"could not read the factions: {type(error).__name__}" in capsys.readouterr().err


# ---------------------------------------------------------------- seasons, late starts and gaps


def test_a_late_start_keeps_what_is_already_there_as_baseline(tmp_path):
    folder = world(tmp_path, held={"dragon": ("SamFake", 1)}, parties=[("p-1", "Alex_Fake", "Red Wolves")],
                   advancements={"TomFake": {MONSTERS: LAUNCH + dt.timedelta(days=2)}})
    state, discord = tmp_path / "news", Discord()
    later = LAUNCH + dt.timedelta(days=4)
    assert run(folder, state, later, discord, arm=False) == 0 and discord.posts == []
    kept = saved(state)
    assert kept["late"] is True and {e["status"] for e in kept["items"].values()} == {"baseline"}
    # A challenge done before the feed started never counts; new news after it does.
    FakeWorld(folder).advancements(PLAYERS["RinFake"], {DIET: saved_time(later + dt.timedelta(minutes=5)),
                                                        "minecraft:husbandry/whole_pack": saved_time(LAUNCH)})
    run(folder, state, later + dt.timedelta(minutes=10), discord)
    run(folder, state, later + dt.timedelta(minutes=30), discord)
    assert discord.lines == ["RinFake completed A Balanced Diet. First this season."]


def test_a_late_start_that_finds_nothing_still_posts_what_comes_next(tmp_path):
    folder, state, discord = world(tmp_path), tmp_path / "news", Discord()
    later = LAUNCH + dt.timedelta(days=4)
    run(folder, state, later, discord, arm=False)
    assert saved(state)["late"] is True and saved(state)["items"] == {}
    world(tmp_path, held={"dragon": ("SamFake", 1)})
    run(folder, state, later + dt.timedelta(minutes=10), discord)
    assert discord.lines == ["SamFake killed the Ender Dragon. First this season."]


def test_the_launch_is_dated_by_the_runs_not_the_calendar(tmp_path):
    # The launch runs a week later than the calendar says: runs every 10 minutes before it saw the
    # world unlaunched, so it is on time, and test play before it doesn't count.
    real = LAUNCH + dt.timedelta(days=7)
    folder, state, discord = world(tmp_path, launched=False), tmp_path / "news", Discord()
    for minutes in (30, 20, 10):
        run(folder, state, real - dt.timedelta(minutes=minutes), discord, arm=False)
    world(tmp_path, held={"dragon": ("SamFake", 1)}, advancements={
        "TomFake": {DIET: real - dt.timedelta(hours=2)},                 # test play
        "RinFake": {MONSTERS: real + dt.timedelta(minutes=1)}})
    run(folder, state, real + dt.timedelta(minutes=5), discord, arm=False)
    kept = saved(state)
    assert kept["late"] is False and kept["launched"] == news.iso(real + dt.timedelta(minutes=5))
    assert news.parse(kept["since"]) == real - dt.timedelta(minutes=10) - news.SAVE_LAG
    run(folder, state, real + dt.timedelta(minutes=25), discord, arm=False)
    assert discord.lines == ["SamFake killed the Ender Dragon. First this season.",
                             "RinFake completed Monsters Hunted. First this season."]
    assert f"challenge:{DIET}" not in kept["items"]


def test_the_feed_turned_back_on_mid_season_keeps_what_happened_meanwhile_as_baseline(tmp_path):
    folder = world(tmp_path, season=2, held={"dragon": ("SamFake", 1)})
    state, discord = tmp_path / "news", Discord()
    run(folder, state, AFTER, discord)
    # The webhook was emptied for a week; the timer ran nothing. Then a first, and back on.
    world(tmp_path, season=2, held={"dragon": ("SamFake", 1), "end": ("TomFake", 2)})
    back = AFTER + dt.timedelta(days=7)
    assert run(folder, state, back, discord) == 0
    assert discord.lines == ["SamFake killed the Ender Dragon. First this season."]
    assert saved(state, 2)["items"]["first:end"]["status"] == "baseline"
    world(tmp_path, season=2, held={"dragon": ("SamFake", 1), "end": ("TomFake", 2), "elytra": ("RinFake", 3)})
    run(folder, state, back + dt.timedelta(minutes=10), discord)
    assert discord.lines[1:] == ["RinFake found an elytra. First this season."]


def test_a_later_season_turned_on_mid_season_is_late_even_with_last_seasons_file(tmp_path):
    state, discord = tmp_path / "news", Discord()
    run(world(tmp_path / "s1", held={"dragon": ("SamFake", 1)}), state, AFTER, discord)
    mid = LAUNCH + dt.timedelta(days=120)
    run(world(tmp_path / "s2", season=2, held={"dragon": ("TomFake", 1)}), state, mid, discord, arm=False)
    assert saved(state, 2)["late"] is True and len(discord.posts) == 1


def test_a_new_season_is_a_new_file_and_its_firsts_post_again(tmp_path):
    state, discord = tmp_path / "news", Discord()
    run(world(tmp_path / "s1", held={"dragon": ("SamFake", 1)}), state, AFTER, discord)
    season_two = LAUNCH + dt.timedelta(days=90)
    s2 = world(tmp_path / "s2", season=2, launched=False)
    run(s2, state, season_two - dt.timedelta(minutes=5), discord, arm=False)
    world(tmp_path / "s2", season=2, held={"dragon": ("TomFake", 1)},
          advancements={"Alex_Fake": {MONSTERS: season_two + dt.timedelta(minutes=1)}})
    run(s2, state, season_two + dt.timedelta(minutes=5), discord, arm=False)
    run(s2, state, season_two + dt.timedelta(minutes=25), discord, arm=False)
    assert discord.lines == ["SamFake killed the Ender Dragon. First this season.",
                             "TomFake killed the Ender Dragon. First this season.",
                             "Alex\\_Fake completed Monsters Hunted. First this season."]
    assert saved(state, 2)["late"] is False and saved(state, 1)["items"]["first:dragon"]["status"] == "posted"


def test_preview_and_found_change_nothing(tmp_path, capsys):
    folder = world(tmp_path, held={"dragon": ("SamFake", 1)}, parties=[("p-1", "Alex_Fake", None)])
    state = tmp_path / "news"
    armed(state, AFTER)
    before = (state / "season-1.json").read_text()
    assert news.preview(folder, state, AFTER) == 0
    out = capsys.readouterr().out
    assert "SamFake killed the Ender Dragon" in out and "New faction: Alex\\_Fake's faction." in out
    assert (state / "season-1.json").read_text() == before
    assert news.preview(folder, tmp_path / "none", AFTER) == 0   # no file: a late start, everything baseline
    assert "kept as baseline" in capsys.readouterr().out and not (tmp_path / "none").exists()
    assert news.show_found(folder) == 0
    assert "first:dragon" in capsys.readouterr().out
    assert news.main(["preview", str(tmp_path / "missing")]) == 2


# ---------------------------------------------------------------- the VPS script


DEPLOY = REPO.root / "deploy"
SCRIPT = DEPLOY / "monkey-news.sh"
UNITS = ["monkey-news.service", "monkey-news.timer"]
DASH = shutil.which("dash")


@pytest.mark.parametrize("name", ["monkey-news.sh", *UNITS])
def test_deploy_files_are_plain_ascii_with_lf(name):
    data = (DEPLOY / name).read_bytes()
    assert data.isascii() and b"\r" not in data


def test_the_script_reads_settings_without_sourcing_and_never_prints_the_webhook():
    text = SCRIPT.read_text()
    code = "\n".join(line for line in text.splitlines() if not line.lstrip().startswith("#"))
    assert text.startswith("#!/bin/sh\n") and ". \"$ENV_FILE\"" not in code and "rcon" not in code.lower()
    assert set(re.findall(r"\$\(setting (\w+)", text)) == {"REPO_DIR", "LIVE_DIR", "LOCK_FILE", "NEWS_DIR",
                                                           "NEWS_WEBHOOK_URL"}
    for line in text.splitlines():
        if "$NEWS_WEBHOOK_URL" in line or "${NEWS_WEBHOOK_URL" in line:
            assert re.fullmatch(r'\s*(NEWS_WEBHOOK_URL=\$\{NEWS_WEBHOOK_URL:-\$\(setting NEWS_WEBHOOK_URL\)\}|'
                                r'if \[ -n "\$NEWS_WEBHOOK_URL" \]; then .*|'
                                r'\[ -n "\$NEWS_WEBHOOK_URL" \] \|\| .*)', line), line
    assert "DISCORD_WEBHOOK_URL" not in text and "STANDINGS_WEBHOOK_URL" not in text
    example = (DEPLOY / "monkey-deploy.env.example").read_text()
    assert "\nNEWS_WEBHOOK_URL=\n" in example and "#NEWS_DIR=/srv/monkey/news\n" in example


def test_units_run_it_as_monkey_every_ten_minutes_clear_of_the_other_jobs():
    service = (DEPLOY / "monkey-news.service").read_text()
    assert "User=monkey\n" in service and "ExecStart=/bin/sh /srv/monkey/repo/deploy/monkey-news.sh\n" in service
    timer = (DEPLOY / "monkey-news.timer").read_text()
    assert "OnCalendar=*-*-* *:02/10:15\n" in timer and "Persistent=false\n" in timer
    others = [p.read_text() for p in DEPLOY.glob("*.timer") if p.name != "monkey-news.timer"]
    assert not any("*:02/10" in t for t in others)


@pytest.fixture
def script(tmp_path):
    """Runs monkey-news.sh under dash with fake python3, flock, id, stat, install and systemctl first on PATH;
    each records its arguments (and python3 whether NEWS_WEBHOOK_URL reached it) in `calls`. python3's version
    check (python_ok) answers FAKE_RC_version and isn't recorded."""
    if not DASH:
        pytest.skip("needs dash")
    bin_dir, calls = tmp_path / "bin", tmp_path / "calls"
    bin_dir.mkdir()
    for name in ("python3", "flock", "install", "systemctl", "stat"):
        first = ('case "$1" in -c) exit "${FAKE_RC_version:-0}" ;; --version) echo "Python 3.9.2"; exit 0 ;; esac\n'
                 if name == "python3" else "")
        extra = 'echo "webhook ${NEWS_WEBHOOK_URL:+given}" >>"$FAKE_CALLS"\n' if name == "python3" else ""
        out = 'echo monkey\n' if name == "stat" else ""
        (bin_dir / name).write_text(f'#!/bin/sh\n{first}echo "{name} $*" >>"$FAKE_CALLS"\n{extra}{out}'
                                    f'exit "${{FAKE_RC_{name}:-0}}"\n', newline="\n")
    (bin_dir / "id").write_text('#!/bin/sh\necho "${FAKE_ID:-1000}"\n', newline="\n")
    for fake in bin_dir.iterdir():
        fake.chmod(0o755)   # PATH skips a file that isn't executable, and the real command would run instead
    repo = tmp_path / "repo"
    (repo / "tools").mkdir(parents=True)
    (repo / "tools" / "news.py").write_text("")
    shutil.copytree(DEPLOY, repo / "deploy", ignore=shutil.ignore_patterns("*.env*"))
    env_file = tmp_path / "monkey-deploy.env"

    def run(*args, settings="", **env):
        env_file.write_text(f"REPO_DIR={repo.as_posix()}\nLIVE_DIR=/srv/live\n"
                            f"NEWS_DIR={(tmp_path / 'news').as_posix()}\n{settings}", newline="\n")
        environ = {k: v for k, v in os.environ.items() if "WEBHOOK" not in k and k not in ("REPO_DIR", "NEWS_DIR")}
        environ |= {"PATH": str(bin_dir) + os.pathsep + os.environ["PATH"], "FAKE_CALLS": calls.as_posix(),
                    "LOCK_FILE": (tmp_path / "lock").as_posix(), "MONKEY_DEPLOY_ENV": env_file.as_posix(), **env}
        done = subprocess.run([DASH, (repo / "deploy" / "monkey-news.sh").as_posix(), *args], env=environ,
                              stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        said = calls.read_text().splitlines() if calls.exists() else []
        calls.unlink(missing_ok=True)
        out = [re.sub(r"^\S+ \S+ \[monkey-news\] ", "", line) for line in done.stdout.splitlines()]
        return done.returncode, out, said
    run.repo, run.news = repo, tmp_path / "news"
    return run


def test_the_script_posts_as_monkey_under_the_lock_with_the_webhook_in_its_environment(script):
    code, out, calls = script(settings=f"NEWS_WEBHOOK_URL={URL}\n")
    world = "/srv/live/server/world"
    tool = f"{script.repo.as_posix()}/tools/news.py"
    post = f"python3 -B -u {tool} post {world} --state {script.news.as_posix()}"
    assert code == 0 and calls == ["flock -w 60 9", post, "webhook given"]
    assert script.news.is_dir() and URL not in "\n".join(out)


def test_the_script_without_a_webhook_runs_nothing(script):
    code, out, calls = script()
    assert code == 0 and out == ["no NEWS_WEBHOOK_URL in the settings; not posting"] and calls == []


def test_the_script_skips_a_run_while_the_deploy_lock_is_held_and_refuses_root(script):
    code, out, calls = script(settings=f"NEWS_WEBHOOK_URL={URL}\n", FAKE_RC_flock="1")
    assert code == 0 and out[-1].endswith("skipping this run") and not any(c.startswith("python3") for c in calls)
    code, out, calls = script(settings=f"NEWS_WEBHOOK_URL={URL}\n", FAKE_ID="0")
    assert code == 1 and "run it as monkey" in out[-1] and calls == []


def test_check_says_whether_the_webhook_is_set_never_its_value(script):
    code, out, calls = script("--check", settings=f"NEWS_WEBHOOK_URL={URL}\n")
    assert code == 0 and out[0] == "webhook: set" and out[-1] == "check finished: nothing was changed"
    assert URL not in "\n".join(out + calls)
    assert any(c.startswith("python3 -B ") and " preview /srv/live/server/world --state " in c for c in calls)
    assert "webhook: not set (NEWS_WEBHOOK_URL): nothing posts" in script("--check")[1]


def test_install_makes_the_news_folder_and_starts_the_timer_as_root_only(script):
    code, out, calls = script("--install")
    assert code == 1 and "run as root" in out[-1]
    code, out, calls = script("--install", FAKE_ID="0")
    assert code == 0 and f"install -d -m 755 -o monkey -g monkey {script.news.as_posix()}" in calls
    assert any(c.startswith("systemctl enable --now monkey-news.timer") for c in calls)
    assert script("--bogus")[0] == 2


def test_the_script_refuses_a_python3_older_than_3_11(script):
    code, out, calls = script(settings=f"NEWS_WEBHOOK_URL={URL}\n", FAKE_RC_version="1")
    assert code == 1 and "python3 is older than 3.11" in out[-1] and "Python 3.9.2" in out[-1]
    assert calls == []
    assert script("--check", settings=f"NEWS_WEBHOOK_URL={URL}\n", FAKE_RC_version="1")[0] == 1


def test_check_fails_when_the_preview_does(script):
    code, out, calls = script("--check", settings=f"NEWS_WEBHOOK_URL={URL}\n", FAKE_RC_python3="1")
    assert code == 1 and "the preview failed (exit 1): a source couldn't be read, see above" in out
    assert out[-1] == "check finished: nothing was changed"
