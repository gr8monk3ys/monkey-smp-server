"""tools/news.py and deploy/realms-news.sh: what is news, firsts per season, the limits, never posting twice.

The saved files are shaped as Minecraft 26.3 writes them (tests/fake_world.py): advancements as on a 26.3 test
server's players/advancements/<uuid>.json (2026-10-25, DataVersion 5023), the ids from the 26.3 server jar's
data/minecraft/advancement/, the firsts' claims as the realms-firsts pack stores them (tools/firsts.py). Players,
UUIDs and factions are made up.
"""
import datetime as dt
import json
import os
import re
import shutil
import subprocess
import uuid

import pytest
from fake_world import FakeWorld, member

import firsts
import news
import saved_world
import season_calendar
from repo import REPO

LAUNCH = season_calendar.LAUNCH                       # Saturday 31 October 2026, 5 PM Pacific
AFTER = LAUNCH + dt.timedelta(minutes=10)              # the first run after the launch
URL = "https://discord.com/api/webhooks/1/secret-token"
NAMES = ["Alex_Fake", "SamFake", "TomFake", "RinFake"]
PLAYERS = {name: str(uuid.uuid5(uuid.NAMESPACE_DNS, name)) for name in NAMES}
MONSTERS = "minecraft:adventure/kill_all_mobs"
DIET = "minecraft:husbandry/balanced_diet"


def saved_time(when: dt.datetime) -> str:
    """A criterion's time as 26.3 saves it: the server's local time with its offset."""
    return when.astimezone(season_calendar.PACIFIC).strftime("%Y-%m-%d %H:%M:%S %z")


def world(tmp_path, *, launched=True, season=1, held=None, advancements=None, parties=(), extra_scores=()):
    """A saved world: the launch and season scores, firsts claims {id: (name, order)}, advancements {player:
    {adv: when}}, parties [(party id, owner name, faction name or None)] and the usercache with every player."""
    rows = [("rw.day", "#launched", 1 if launched else 0), ("rw.day", "#season", season), *extra_scores]
    fake = FakeWorld(tmp_path / "server" / "world").scores(*rows)
    if held:
        fake.storage("realms", {"firsts": {"held": {
            k: {"name": name, "order": order, "week": 0} for k, (name, order) in held.items()}}})
    for name, done in (advancements or {}).items():
        fake.advancements(PLAYERS[name], {adv: saved_time(when) for adv, when in done.items()})
    for party_id, owner, faction in parties:
        fake.party(party_id, member(PLAYERS[owner], owner), [member(PLAYERS[owner], owner)])
        if faction:
            fake.party_name(PLAYERS[owner], faction)
    (fake.path.parent / "usercache.json").write_text(json.dumps(
        [{"uuid": u, "name": n, "expiresOn": "2026-11-30 12:00:00 -0800"} for n, u in PLAYERS.items()]))
    return fake.path


class Discord:
    """A fake urlopen: records each post's JSON body; `fail` posts answer HTTP 500."""

    def __init__(self, fail=0):
        self.posts, self.fail = [], fail

    def __call__(self, request, timeout):
        assert request.full_url == URL and request.get_method() == "POST"
        body = json.loads(request.data)
        if self.fail:
            self.fail -= 1
            import urllib.error
            raise urllib.error.HTTPError(URL, 500, "no", {}, None)
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


def run(folder, state, now, discord, launch=LAUNCH):
    return news.post(folder, state, now, launch, URL, urlopen=discord, sleep=lambda s: None)


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
    items = {i.key: i for i in news.challenge_items(folder, LAUNCH)}
    assert items[f"challenge:{MONSTERS}"].text == "SamFake completed Monsters Hunted. First this season."
    assert items[f"challenge:{DIET}"].text == "TomFake completed A Balanced Diet. First this season."
    assert items[f"challenge:{DIET}"].at == (LAUNCH + dt.timedelta(hours=9)).astimezone(dt.UTC).isoformat()


def test_names_are_escaped_and_a_player_without_a_name_is_passed_over(tmp_path):
    folder = world(tmp_path, held={"dragon": ("Alex_Fake", 1)}, advancements={"RinFake": {MONSTERS: AFTER}})
    cache = folder.parent / "usercache.json"
    cache.write_text(json.dumps([e for e in json.loads(cache.read_text()) if e["name"] != "RinFake"]))
    assert [i.text for i in news.first_items(folder)] == [r"Alex\_Fake killed the Ender Dragon. First this season."]
    assert news.challenge_items(folder, LAUNCH) == []


# ---------------------------------------------------------------- posting


def test_nothing_posts_or_is_kept_before_the_launch(tmp_path):
    folder = world(tmp_path, launched=False, held={"dragon": ("SamFake", 1)})
    state, discord = tmp_path / "news", Discord()
    assert run(folder, state, AFTER, discord) == 0
    assert discord.posts == [] and not state.exists()


def test_no_webhook_posts_nothing_and_keeps_nothing(tmp_path, capsys):
    folder, state = world(tmp_path, held={"dragon": ("SamFake", 1)}), tmp_path / "news"
    assert news.post(folder, state, AFTER, LAUNCH, "") == 0 and not state.exists()


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
    for minutes in (40, 50, 600):
        assert run(folder, state, AFTER + dt.timedelta(minutes=minutes), discord) == 0
    assert len(discord.posts) == 3
    kept = saved(state)
    assert {k: e["status"] for k, e in kept["items"].items()} == {
        "first:nether": "posted", "faction:p-red": "posted", f"challenge:{MONSTERS}": "posted"}
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
    folder = world(tmp_path, held=held, advancements=advs, parties=parties)
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


def test_a_run_killed_mid_post_counts_it_as_posted(tmp_path, capsys):
    folder, state, discord = world(tmp_path, held={"dragon": ("SamFake", 1)}), tmp_path / "news", Discord()
    real = news.standings.post_discord

    def killed(*a, **k):
        raise KeyboardInterrupt   # the run dies after the state was written "sending"
    news.standings.post_discord = killed
    try:
        with pytest.raises(KeyboardInterrupt):
            run(folder, state, AFTER, discord)
    finally:
        news.standings.post_discord = real
    assert saved(state)["items"]["first:dragon"]["status"] == "sending"
    assert run(folder, state, AFTER + dt.timedelta(minutes=10), discord) == 0
    assert discord.posts == [] and saved(state)["items"]["first:dragon"]["status"] == "posted"
    assert "counted as posted, not sent again" in capsys.readouterr().out


def test_a_failed_post_waits_for_the_next_run_and_never_shows_the_url(tmp_path, capsys):
    folder, state = world(tmp_path, held={"dragon": ("SamFake", 1), "end": ("TomFake", 2)}), tmp_path / "news"
    discord = Discord(fail=1)
    assert run(folder, state, AFTER, discord) == 1
    out = capsys.readouterr()
    assert "HTTP 500" in out.err and "secret-token" not in out.out + out.err
    assert {e["status"] for e in saved(state)["items"].values()} == {"pending"} and saved(state)["posts"] == []
    assert run(folder, state, AFTER + dt.timedelta(minutes=10), discord) == 0
    assert discord.lines == ["SamFake killed the Ender Dragon. First this season.",
                             "TomFake entered the End. First this season."]


def test_firsts_post_in_the_order_they_were_claimed(tmp_path):
    folder = world(tmp_path, held={"dragon": ("SamFake", 2), "end": ("TomFake", 1)})
    state, discord = tmp_path / "news", Discord()
    run(folder, state, AFTER, discord)
    assert discord.lines == ["TomFake entered the End. First this season.",
                             "SamFake killed the Ender Dragon. First this season."]


def test_an_unreadable_source_on_the_first_run_makes_no_file(tmp_path, capsys):
    folder = world(tmp_path, held={"dragon": ("SamFake", 1)})
    (folder / "players" / "advancements").mkdir(parents=True)
    (folder / "players" / "advancements" / f"{PLAYERS['TomFake']}.json").write_text("{")
    state, discord = tmp_path / "news", Discord()
    assert run(folder, state, AFTER, discord) == 1 and not state.exists() and discord.posts == []
    (folder / "players" / "advancements" / f"{PLAYERS['TomFake']}.json").unlink()
    assert run(folder, state, AFTER + dt.timedelta(minutes=10), discord) == 0 and len(discord.posts) == 1
    # Later, a bad file only skips that source for the run.
    (folder / "players" / "advancements" / f"{PLAYERS['TomFake']}.json").write_text("{")
    FakeWorld(folder).party("p-1", member(PLAYERS["RinFake"], "RinFake"), [member(PLAYERS["RinFake"], "RinFake")])
    assert run(folder, state, AFTER + dt.timedelta(minutes=20), discord) == 1
    assert discord.lines[1:] == ["New faction: RinFake's faction."]


# ---------------------------------------------------------------- seasons and late starts


def test_a_late_start_keeps_what_is_already_there_as_baseline(tmp_path):
    folder = world(tmp_path, held={"dragon": ("SamFake", 1)}, parties=[("p-1", "Alex_Fake", "Red Wolves")],
                   advancements={"TomFake": {MONSTERS: LAUNCH + dt.timedelta(days=2)}})
    state, discord = tmp_path / "news", Discord()
    later = LAUNCH + dt.timedelta(days=4)
    assert run(folder, state, later, discord) == 0 and discord.posts == []
    kept = saved(state)
    assert kept["late"] is True and {e["status"] for e in kept["items"].values()} == {"baseline"}
    # A challenge done before the feed started never counts; new news after it does.
    FakeWorld(folder).advancements(PLAYERS["RinFake"], {DIET: saved_time(later + dt.timedelta(minutes=5)),
                                                        "minecraft:husbandry/whole_pack": saved_time(LAUNCH)})
    run(folder, state, later + dt.timedelta(minutes=10), discord)
    run(folder, state, later + dt.timedelta(minutes=30), discord)
    assert discord.lines == ["RinFake completed A Balanced Diet. First this season."]


def test_installed_before_the_launch_is_on_time(tmp_path):
    folder, state, discord = world(tmp_path, launched=False), tmp_path / "news", Discord()
    run(folder, state, LAUNCH - dt.timedelta(days=1), discord)
    folder = world(tmp_path, held={"dragon": ("SamFake", 1)})
    run(folder, state, LAUNCH + dt.timedelta(minutes=2, hours=2), discord)
    assert saved(state)["late"] is False and discord.lines == ["SamFake killed the Ender Dragon. First this season."]


def test_a_new_season_is_a_new_file_and_its_firsts_post_again(tmp_path):
    state, discord = tmp_path / "news", Discord()
    run(world(tmp_path / "s1", held={"dragon": ("SamFake", 1)}), state, AFTER, discord)
    season_two = LAUNCH + dt.timedelta(days=90)
    run(world(tmp_path / "s2", season=2, held={"dragon": ("TomFake", 1)},
              advancements={"Alex_Fake": {MONSTERS: season_two - dt.timedelta(minutes=5)}}),
        state, season_two + dt.timedelta(minutes=5), discord)
    assert discord.lines == ["SamFake killed the Ender Dragon. First this season.",
                             "TomFake killed the Ender Dragon. First this season."]
    assert saved(state, 2)["late"] is False and saved(state, 1)["items"]["first:dragon"]["status"] == "posted"
    # Without last season's file a later season's first run is a late start: its launch isn't in the calendar.
    other = tmp_path / "other"
    run(world(tmp_path / "s3", season=2, held={"dragon": ("TomFake", 1)}), other, season_two, discord)
    assert saved(other, 2)["late"] is True and len(discord.posts) == 2


def test_preview_and_found_change_nothing(tmp_path, capsys):
    folder = world(tmp_path, held={"dragon": ("SamFake", 1)}, parties=[("p-1", "Alex_Fake", None)])
    state = tmp_path / "news"
    assert news.preview(folder, state, AFTER, LAUNCH) == 0
    out = capsys.readouterr().out
    assert "SamFake killed the Ender Dragon" in out and "New faction: Alex\\_Fake's faction." in out
    assert not state.exists()
    assert news.show_found(folder, LAUNCH) == 0
    assert "first:dragon" in capsys.readouterr().out and not state.exists()
    assert news.main(["preview", str(tmp_path / "missing")]) == 2


# ---------------------------------------------------------------- the VPS script


DEPLOY = REPO.root / "deploy"
SCRIPT = DEPLOY / "realms-news.sh"
UNITS = ["realms-news.service", "realms-news.timer"]
DASH = shutil.which("dash")


@pytest.mark.parametrize("name", ["realms-news.sh", *UNITS])
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
    example = (DEPLOY / "realms-deploy.env.example").read_text()
    assert "\nNEWS_WEBHOOK_URL=\n" in example and "#NEWS_DIR=/srv/realms/news\n" in example


def test_units_run_it_as_realms_every_ten_minutes_clear_of_the_other_jobs():
    service = (DEPLOY / "realms-news.service").read_text()
    assert "User=realms\n" in service and "ExecStart=/bin/sh /srv/realms/repo/deploy/realms-news.sh\n" in service
    timer = (DEPLOY / "realms-news.timer").read_text()
    assert "OnCalendar=*-*-* *:02/10:15\n" in timer and "Persistent=false\n" in timer
    others = [p.read_text() for p in DEPLOY.glob("*.timer") if p.name != "realms-news.timer"]
    assert not any("*:02/10" in t for t in others)


@pytest.fixture
def script(tmp_path):
    """Runs realms-news.sh under dash with fake python3, flock, id, stat, install and systemctl first on PATH;
    each records its arguments (and python3 whether NEWS_WEBHOOK_URL reached it) in `calls`."""
    if not DASH:
        pytest.skip("needs dash")
    bin_dir, calls = tmp_path / "bin", tmp_path / "calls"
    bin_dir.mkdir()
    for name in ("python3", "flock", "install", "systemctl", "stat"):
        extra = 'echo "webhook ${NEWS_WEBHOOK_URL:+given}" >>"$FAKE_CALLS"\n' if name == "python3" else ""
        out = 'echo realms\n' if name == "stat" else ""
        (bin_dir / name).write_text(f'#!/bin/sh\necho "{name} $*" >>"$FAKE_CALLS"\n{extra}{out}'
                                    f'exit "${{FAKE_RC_{name}:-0}}"\n', newline="\n")
    (bin_dir / "id").write_text('#!/bin/sh\necho "${FAKE_ID:-1000}"\n', newline="\n")
    repo = tmp_path / "repo"
    (repo / "tools").mkdir(parents=True)
    (repo / "tools" / "news.py").write_text("")
    shutil.copytree(DEPLOY, repo / "deploy", ignore=shutil.ignore_patterns("*.env*"))
    env_file = tmp_path / "realms-deploy.env"

    def run(*args, settings="", **env):
        env_file.write_text(f"REPO_DIR={repo.as_posix()}\nLIVE_DIR=/srv/live\n"
                            f"NEWS_DIR={(tmp_path / 'news').as_posix()}\n{settings}", newline="\n")
        environ = {k: v for k, v in os.environ.items() if "WEBHOOK" not in k and k not in ("REPO_DIR", "NEWS_DIR")}
        environ |= {"PATH": str(bin_dir) + os.pathsep + os.environ["PATH"], "FAKE_CALLS": calls.as_posix(),
                    "LOCK_FILE": (tmp_path / "lock").as_posix(), "REALMS_DEPLOY_ENV": env_file.as_posix(), **env}
        done = subprocess.run([DASH, (repo / "deploy" / "realms-news.sh").as_posix(), *args], env=environ,
                              stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        said = calls.read_text().splitlines() if calls.exists() else []
        calls.unlink(missing_ok=True)
        out = [re.sub(r"^\S+ \S+ \[realms-news\] ", "", line) for line in done.stdout.splitlines()]
        return done.returncode, out, said
    run.repo, run.news = repo, tmp_path / "news"
    return run


def test_the_script_posts_as_realms_under_the_lock_with_the_webhook_in_its_environment(script):
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
    assert code == 1 and "run it as realms" in out[-1] and calls == []


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
    assert code == 0 and f"install -d -m 755 -o realms -g realms {script.news.as_posix()}" in calls
    assert any(c.startswith("systemctl enable --now realms-news.timer") for c in calls)
    assert script("--bogus")[0] == 2
