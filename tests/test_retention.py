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


def test_no_joins(tmp_path, capsys):
    assert retention.main([str(tmp_path)]) == 1
    assert "no joins" in capsys.readouterr().out
