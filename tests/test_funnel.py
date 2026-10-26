import datetime as dt
import gzip
import re

import pytest

import funnel
from repo import REPO

PAYMENTS = REPO.root / "tests" / "fixtures" / "tebex-payments.csv"  # synthetic: fake names, example.com
RENAMED = "0f0f0f0f-1111-4222-8333-444455556666"


def log(folder, day, *lines):
    with gzip.open(folder / f"{day}-1.log.gz", "wt", encoding="utf-8") as f:
        f.write("".join(f"[{t}] [{thread}]: {msg}\n" for t, thread, msg in lines))


def server(t, msg):
    return t, "Server thread/INFO", msg


def joins(t, name, how="joined"):
    return server(t, f"System chat: {name} {how} the game")


@pytest.fixture
def logs(tmp_path):
    log(tmp_path, "2026-09-01", ("10:30:00", "User Authenticator #1/INFO", "UUID of player AlexFake is "
                                 "aaaaaaaa-0000-4000-8000-000000000001"),
        joins("10:30:01", "AlexFake"), server("11:00:00", "<AlexFake> AlexFake left the game"),
        joins("12:30:01", "AlexFake", "left"))
    log(tmp_path, "2026-09-05", joins("11:05:00", "SamFake"), joins("11:25:00", "SamFake", "left"))
    log(tmp_path, "2026-09-09", joins("18:00:00", "AlexFake"), joins("18:30:00", "AlexFake", "left"))
    log(tmp_path, "2026-09-15", joins("20:00:00", "KaiFake"), server("20:45:00", "Stopping server"))
    log(tmp_path, "2026-09-20", joins("23:50:00", "LateFake"), joins("00:10:00", "LateFake", "left"))
    log(tmp_path, "2026-09-25", joins("10:00:00", "KaiFake"), joins("10:05:00", "KaiFake", "left"))
    log(tmp_path, "2026-10-01", ("11:59:00", "User Authenticator #2/INFO", f"UUID of player NewNameFake is {RENAMED}"),
        joins("12:00:00", "NewNameFake"), joins("13:00:00", "NewNameFake", "left"))
    log(tmp_path, "2026-11-20", joins("09:00:00", "AlexFake"))
    return tmp_path


def test_sessions_close_on_leave_stop_midnight_and_log_end(logs):
    played, names, first, last = funnel.sessions(logs, funnel.UTC)
    def at(*when):
        return dt.datetime(*when, tzinfo=funnel.UTC)
    assert played["kaifake"][0] == (at(2026, 9, 15, 20), at(2026, 9, 15, 20, 45))
    assert played["latefake"] == [(at(2026, 9, 20, 23, 50), at(2026, 9, 21, 0, 10))]
    assert sum((e - b for b, e in played["alexfake"][:1]), dt.timedelta()) == dt.timedelta(hours=2)  # chat line ignored
    assert played["alexfake"][-1][0] == played["alexfake"][-1][1]   # still online when the log ends
    assert names[RENAMED.replace("-", "")] == {"newnamefake"}
    assert (first, last) == (dt.date(2026, 9, 1), dt.date(2026, 11, 20))


def test_the_funnel_from_purchase_to_renewal(logs, capsys):
    assert funnel.main([str(PAYMENTS), str(logs)]) == 0
    out = capsys.readouterr().out
    lines = out.splitlines()
    assert lines[0] == "pass funnel as of 2026-11-20: 6 buyers, 9 paid pass payments"
    assert "statuses: Complete 10, Refund 1 (counted: Complete)" in out
    # Monthly: Alex and the renamed player renewed, Sam and Late didn't; NoShow isn't due yet.
    assert "Month-2 renewal, monthly passes: 2 of 4 renewed (50%); 1 not due yet" in lines
    assert "Renewal, 3-month passes: none due yet; 1 not due yet" in lines
    assert "Came back later: 1 bought again after their pass had lapsed" in lines
    rows = {line.split()[0]: line.split()[1:] for line in lines if re.match(r"\d{4}-\d{2} ", line)}
    # September: Alex, Sam, Kai, Late (Robin was refunded). Sam and Late played under 30 minutes;
    # Alex and Kai came back after a week; only Alex renewed (Kai's 3 months aren't up).
    assert rows["2026-09"] == ["4", "4", "2", "2/4", "1/3"]
    assert rows["2026-10"] == ["1", "1", "1", "0/1", "1/1"]   # found through the UUID after a rename
    assert rows["2026-11"] == ["1", "0", "0", "-", "-"]
    never = lines[lines.index("bought a pass but never joined (send install help):") + 1:]
    assert never == ["  NoShowFake       bought 2026-11-10 (10 days ago)"]


def test_as_of_moves_what_is_due(logs, capsys):
    funnel.main([str(PAYMENTS), str(logs), "--as-of", "2026-10-10"])
    out = capsys.readouterr().out
    assert "pass funnel as of 2026-10-10: 5 buyers, 6 paid pass payments" in out  # later payments wait
    # Alex renewed and Sam didn't; Late and the renamed player still have time.
    assert "Month-2 renewal, monthly passes: 1 of 2 renewed (50%); 2 not due yet" in out
    assert "NoShowFake" not in out and "Came back later" not in out


def test_columns_are_found_by_name_or_given():
    cols = funnel.find_columns(["Txn", "Created At", "Minecraft Username", "Package Name"], {})
    assert cols == {"username": "Minecraft Username", "date": "Created At", "package": "Package Name"}
    assert funnel.find_columns(["When", "Who", "What"], {"date": "When", "username": "Who", "package": "What"})
    with pytest.raises(SystemExit, match="username"):
        funnel.find_columns(["Date", "Package"], {})
    with pytest.raises(SystemExit, match="no such column"):
        funnel.find_columns(["Date", "Package", "Username"], {"username": "IGN"})


def test_day_month_order_comes_from_the_dates():
    assert funnel.date_format(["2026-09-01 10:00:00", "2026-09-01T10:00:00+00:00"]) is None
    assert funnel.date_format(["01/02/2026 10:00", "25/02/2026 10:00"]) == "%d/%m/%Y %H:%M"
    assert funnel.date_format(["02/01/2026 10:00", "02/25/2026 10:00"]) == "%m/%d/%Y %H:%M"
    assert funnel.parse_date("2026-09-01T03:00:00-07:00", None) == dt.datetime(2026, 9, 1, 10, tzinfo=funnel.UTC)


def test_log_times_in_another_zone(logs):
    played, *_ = funnel.sessions(logs, funnel.log_zone("-07:00"))
    assert played["kaifake"][0][0] == dt.datetime(2026, 9, 16, 3, tzinfo=funnel.UTC)


def test_the_fixture_holds_no_real_buyers():
    text = PAYMENTS.read_text(encoding="utf-8")
    emails = re.findall(r"[\w.+-]+@([\w.-]+)", text)
    assert emails and set(emails) == {"example.com"}
    assert set(re.findall(r",(\d+\.\d+\.\d+)\.\d+\n", text)) == {"203.0.113"}   # documentation addresses
    assert all(name.endswith("Fake") for name in re.findall(r"^tbx-fake-\d+,[^,]+,(\w+),", text, re.MULTILINE))
