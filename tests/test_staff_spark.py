"""tools/staff_spark.py: spark's profiler from the Server tab, and its report link read from the log."""
import json

import pytest
import staff_panel
import staff_spark
from test_staff_panel import actions, box  # noqa: F401 (box: a panel over a fake server folder)

LINK = "https://spark.lucko.me/AbCdEf1234"


@pytest.fixture
def sp(box):  # noqa: F811
    (box.root / "mods" / "spark-1.10.187-fabric.jar").write_bytes(b"jar")
    s = staff_spark.spark(box.panel)
    clock = [1_800_000_000.0]
    s.clock = lambda: clock[0]
    box.clock, box.s = clock, s
    for command in ("spark profiler start --timeout 60", "spark profiler start --timeout 120 --only-ticks-over 100",
                    "spark profiler start --timeout 30 --alloc", "spark profiler start --timeout 600",
                    "spark profiler stop"):
        box.docker.answers[command] = ""
    return box


def log(where, *lines):
    with open(where.root / "logs" / "latest.log", "a", encoding="utf-8") as f:
        f.writelines(f"{line}\n" for line in lines)


def test_every_route_names_who_may_use_it():
    assert set(staff_spark.NEEDS) == set(staff_spark.ROUTES)
    for key in staff_spark.ROUTES:
        assert staff_panel.ROUTES[key] is staff_spark.ROUTES[key]
    assert staff_spark.NEEDS[("POST", "/api/spark")] == "admin" == staff_spark.NEEDS[("POST", "/api/spark-stop")]


def test_a_moderator_can_look_but_not_start(sp):
    assert sp.call("GET", "/api/spark", headers={"X-Staff-Role": "moderator"})[0] == 200
    moderator = {"X-Staff-Role": "moderator"}
    assert sp.call("POST", "/api/spark", {"mode": "cpu", "seconds": 60}, headers=moderator)[0] == 403
    assert sp.docker.calls == []


@pytest.mark.parametrize("mode, seconds, command", [
    ("cpu", 60, "spark profiler start --timeout 60"),
    ("lag", 120, "spark profiler start --timeout 120 --only-ticks-over 100"),
    ("memory", 30, "spark profiler start --timeout 30 --alloc"),
])
def test_a_run_starts_with_only_checked_values(sp, mode, seconds, command):
    code, data = sp.call("POST", "/api/spark", {"mode": mode, "seconds": seconds})
    assert code == 200 and data["ends"] == sp.clock[0] + seconds
    assert [c[-1] for c in sp.docker.calls if "exec" in c] == [command]
    assert f"diego spark-start {mode}, {seconds} seconds" in actions(sp)


@pytest.mark.parametrize("body", [
    {"mode": "cpu; stop", "seconds": 60}, {"mode": "cpu", "seconds": 29}, {"mode": "cpu", "seconds": 601},
    {"mode": "cpu", "seconds": "60"}, {"mode": "cpu", "seconds": True}, {"mode": "cpu"},
])
def test_a_bad_run_is_refused(sp, body):
    assert sp.call("POST", "/api/spark", body)[0] == 400 and sp.docker.calls == []


def test_one_run_at_a_time_and_spark_must_be_there(sp):
    assert sp.call("POST", "/api/spark", {"mode": "cpu", "seconds": 60})[0] == 200
    assert sp.call("POST", "/api/spark", {"mode": "cpu", "seconds": 60})[0] == 409
    sp.clock[0] += 61
    assert sp.call("POST", "/api/spark", {"mode": "cpu", "seconds": 60})[0] == 200
    (sp.root / "mods" / "spark-1.10.187-fabric.jar").rename(sp.root / "mods" / "spark-1.10.187-fabric.jar.disabled")
    sp.clock[0] += 61
    code, data = sp.call("POST", "/api/spark", {"mode": "cpu", "seconds": 60})
    assert code == 409 and "spark isn't" in data["error"]
    assert sp.call("GET", "/api/spark")[1]["installed"] is False


def test_the_report_link_is_read_from_the_log_after_the_start_only(sp):
    log(sp, f"[10:00:00] [Server thread/INFO]: [spark] old report {LINK.replace('AbCd', 'Zzzz')}")
    sp.call("POST", "/api/spark", {"mode": "cpu", "seconds": 60})
    data = sp.call("GET", "/api/spark")[1]
    assert data["running"] is True and data["run"]["link"] is None and data["waiting"] is True
    log(sp, "[10:01:00] [spark-worker-pool-1/INFO]: [⚡] Profiler stopped & upload complete!",
        f"[10:01:00] [spark-worker-pool-1/INFO]: [⚡] {LINK}", "[10:01:01] secret https://spark.lucko.me/Other99999")
    data = sp.call("GET", "/api/spark")[1]
    assert data["run"]["link"] == LINK and data["running"] is False and data["waiting"] is False
    assert json.loads((sp.staff / "spark.json").read_text())["link"] == LINK


def test_a_link_is_looked_for_a_while_after_the_end_then_given_up(sp):
    sp.call("POST", "/api/spark", {"mode": "cpu", "seconds": 60})
    sp.clock[0] += 60 + staff_spark.GRACE - 1
    assert sp.call("GET", "/api/spark")[1]["waiting"] is True
    sp.clock[0] += 2
    data = sp.call("GET", "/api/spark")[1]
    assert data["waiting"] is False and data["run"]["link"] is None


def test_a_new_log_ends_the_search(sp):
    sp.call("POST", "/api/spark", {"mode": "cpu", "seconds": 60})
    (sp.root / "logs" / "latest.log").write_text(f"[11:00:00] [Server thread/INFO]: Starting\n{LINK}\n")
    data = sp.call("GET", "/api/spark")[1]
    assert data["run"]["lost"] is True and data["run"]["link"] is None and data["waiting"] is False


def test_stop_ends_a_run_and_still_waits_for_its_link(sp):
    assert sp.call("POST", "/api/spark-stop", {})[0] == 409
    sp.call("POST", "/api/spark", {"mode": "cpu", "seconds": 600})
    sp.clock[0] += 30
    assert sp.call("POST", "/api/spark-stop", {})[0] == 200
    assert [c[-1] for c in sp.docker.calls if "exec" in c][-1] == "spark profiler stop"
    data = sp.call("GET", "/api/spark")[1]
    assert data["running"] is False and data["waiting"] is True and data["run"]["stopped"] is True
    assert "diego spark-stop" in actions(sp)


@pytest.mark.parametrize("text, found", [
    (LINK, LINK), (f"see {LINK}.", LINK), ("https://spark.lucko.me/abc", None),
    ("https://spark.lucko.me.evil.example/AbCdEf1234", None), ("http://spark.lucko.me/AbCdEf1234", None),
    (f"{LINK}xyz-more", "https://spark.lucko.me/AbCdEf1234xyz"),
])
def test_only_a_report_link_is_taken(text, found):
    m = staff_spark.LINK.search(text)
    assert (m[0] if m else None) == found


def test_the_page_uses_every_route_and_only_opens_a_report_link():
    from repo import REPO
    script = (REPO.root / "deploy" / "staff" / "desk.js").read_text(encoding="utf-8")
    for _, path in staff_spark.ROUTES:
        assert f'"{path}"' in script
    # The link's href is set only after the page checks its shape again.
    assert 'SPARK_LINK.test(run.link)' in script and 'rel="noopener noreferrer"' in (
        REPO.root / "deploy" / "staff" / "index.html").read_text(encoding="utf-8")
