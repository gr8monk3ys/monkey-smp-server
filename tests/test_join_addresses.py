import datetime as dt
import gzip
import os

import join_addresses

YT, LIST, PLAY = "yt.monkeysmp.lscaturchio.xyz", "list.monkeysmp.lscaturchio.xyz", "play.monkeysmp.lscaturchio.xyz"


def line(name, address):
    return f"[12:00:00] [Server thread/INFO]: [STDOUT]: Player {name} connected via: {address}"


def log(folder, day, *lines, n=1):
    with gzip.open(folder / f"{day}-{n}.log.gz", "wt", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def test_counts_joins_players_and_new_players_per_address(tmp_path):
    log(tmp_path, "2026-11-02", line("Alex", YT), line("Sam", LIST),
        "[12:00:01] [Server thread/INFO]: System chat: Alex joined the game")
    log(tmp_path, "2026-11-03", line("Alex", PLAY), line("Robin", YT))
    log(tmp_path, "2026-11-03", line("Alex", YT), n=2)
    found = join_addresses.joins(tmp_path)

    assert [(d.isoformat(), name, a) for d, name, a in found] == [
        ("2026-11-02", "Alex", YT), ("2026-11-02", "Sam", LIST),
        ("2026-11-03", "Alex", PLAY), ("2026-11-03", "Robin", YT), ("2026-11-03", "Alex", YT)]
    lines = join_addresses.report(found)
    assert lines[0] == "joins per join address, 2026-11-02 to 2026-11-03"
    rows = [row.split() for row in lines[2:]]
    # Alex and Robin found the server through YouTube; Alex later also used the main address.
    assert rows == [[YT, "3", "2", "2"], [LIST, "1", "1", "1"], [PLAY, "1", "1", "0"]]


def test_since_counts_new_players_by_their_first_join(tmp_path):
    log(tmp_path, "2026-11-02", line("Alex", YT))
    log(tmp_path, "2026-11-10", line("Alex", PLAY), line("Sam", LIST))
    rows = [row.split() for row in join_addresses.report(join_addresses.joins(tmp_path), dt.date(2026, 11, 9))[2:]]
    # Alex was new before the window: their join counts, but not as a new player.
    assert rows == [[LIST, "1", "1", "1"], [PLAY, "1", "1", "0"]]


def test_addresses_are_normalised_and_quoted_chat_is_ignored(tmp_path):
    log(tmp_path, "2026-11-02",
        line("Alex", "YT.MonkeySMP.lscaturchio.xyz."),
        "[12:00:02] [Server thread/INFO]: <Sam> Player Sam connected via: fake.example.com",
        "[12:00:03] [Server thread/INFO]: [Sam] x]: [STDOUT]: Player Sam connected via: fake.example.com",
        "[12:00:04] [Server thread/INFO]: [STDOUT]: Disconnecting login attempt from domain: x (Not Whitelisted)")
    assert [(name, a) for _, name, a in join_addresses.joins(tmp_path)] == [("Alex", YT)]


def test_latest_log_comes_last_with_windows_line_endings(tmp_path):
    log(tmp_path, "2026-11-02", line("Alex", YT))
    latest = tmp_path / "latest.log"
    latest.write_bytes((line("Sam", LIST) + "\r\n").encode())
    stamp = dt.datetime(2026, 11, 5, 12).timestamp()
    os.utime(latest, (stamp, stamp))
    assert [(d.isoformat(), name, a) for d, name, a in join_addresses.joins(tmp_path)] == [
        ("2026-11-02", "Alex", YT), ("2026-11-05", "Sam", LIST)]


def test_no_joins(tmp_path, capsys):
    log(tmp_path, "2026-11-02", "[12:00:01] [Server thread/INFO]: System chat: Alex joined the game")
    assert join_addresses.main([str(tmp_path)]) == 1
    assert "no Hostname Catcher joins" in capsys.readouterr().out


def test_main_prints_the_table(tmp_path, capsys):
    log(tmp_path, "2026-11-02", line("Alex", YT))
    assert join_addresses.main([str(tmp_path), "--since", "2026-11-01"]) == 0
    out = capsys.readouterr().out
    assert "(counting from 2026-11-01)" in out
    assert out.splitlines()[-1].split() == [YT, "1", "1", "1"]
    assert join_addresses.main([str(tmp_path), "--since", "2026-11-03"]) == 1
