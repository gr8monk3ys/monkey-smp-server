import datetime as dt
import gzip

import retention


def log(folder, day, *names):
    lines = [f"[12:00:00] [Server thread/INFO]: {n} joined the game" for n in names]
    lines.append("[12:00:01] [Server thread/INFO]: <Alex> I joined the game yesterday")  # chat, not a join
    with gzip.open(folder / f"{day}-1.log.gz", "wt", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def test_cohorts_count_players_who_came_back(tmp_path):
    log(tmp_path, "2026-11-02", "Alex", "Sam")      # a Monday: both new that week
    log(tmp_path, "2026-11-03", "Alex")             # Alex back after 1 day
    log(tmp_path, "2026-11-10", "Alex", "Robin")    # Alex back after 8 days; Robin new the next week
    days, last = retention.play_days(tmp_path)

    assert days["Alex"] == {dt.date(2026, 11, 2), dt.date(2026, 11, 3), dt.date(2026, 11, 10)}
    assert last == dt.date(2026, 11, 10)
    lines = retention.report(days, last)
    first = next(line for line in lines if line.startswith("2026-11-02"))
    assert first.split() == ["2026-11-02", "2", "50%", "50%", "-"]
    robin = next(line for line in lines if line.startswith("2026-11-09"))
    assert robin.split() == ["2026-11-09", "1", "-", "-", "-"]  # too new to judge
    assert lines[-2:] == ["2026-11-02      2", "2026-11-09      2"]


def test_reads_26_3_join_lines(tmp_path):
    """26.3 logs joins through system chat; a renamed player carries their old name."""
    with gzip.open(tmp_path / "2026-10-23-1.log.gz", "wt", encoding="utf-8") as f:
        f.write("[12:05:44] [Server thread/INFO]: Alex[/203.0.113.7:51234] logged in with entity id 174 "
                "at (0.5, 70.0, 0.5)\n"
                "[12:05:45] [Server thread/INFO]: System chat: Alex joined the game\n"
                "[12:06:02] [Server thread/INFO]: System chat: Sam (formerly known as Sammy) joined the game\n"
                "[12:07:00] [Server thread/INFO]: [Not Secure] <Robin> System chat: Kai joined the game\n")
    days, _ = retention.play_days(tmp_path)
    assert set(days) == {"Alex", "Sam"}


def test_logs_are_read_in_order(tmp_path):
    for n in (10, 2, 1):
        with gzip.open(tmp_path / f"2026-10-23-{n}.log.gz", "wt", encoding="utf-8") as f:
            f.write(f"file {n}\n")
    (tmp_path / "latest.log").write_text("latest\n", encoding="utf-8")
    assert [text.strip() for _, text in retention.logs_by_day(tmp_path)] == ["file 1", "file 2", "file 10", "latest"]


def test_no_joins(tmp_path, capsys):
    assert retention.main([str(tmp_path)]) == 1
    assert "no joins" in capsys.readouterr().out
