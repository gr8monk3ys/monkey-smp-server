"""tools/staff_watch.py: what a problem probably is, and when the staff channel hears of it."""
import datetime as dt

import pytest
import staff_watch as w

NOW = dt.datetime(2026, 11, 15, 2, 0, tzinfo=dt.timezone.utc)  # noqa: UP017 (3.10)
MIN = dt.timedelta(minutes=1)


def iso(when):
    return when.strftime("%Y-%m-%dT%H:%M:%SZ")


@pytest.mark.parametrize("text, want", [
    ("java.lang.OutOfMemoryError: Java heap space", "out-of-memory"),
    ("Failed to save chunk: No space left on device", "disk-full"),
    ("Watching Server", "watchdog"),
    ("Ticking entity", "ticking"),
    ("Ticking block entity", "ticking"),
    ("Mod 'Create' (create) 6.0 requires version 0.16 or later of 'fabric-api', which is missing!",
     "missing-dependency"),
    ("Incompatible mods found!", "missing-dependency"),
    ("Mixin apply for mod sodium failed", "mixin"),
    ("Could not execute entrypoint stage 'main' due to errors, provided by 'foo'", "entrypoint"),
    ("**** FAILED TO BIND TO PORT!", "port"),
    ("Couldn't load chunk [12, -4]", "chunk"),
    ("Failed to load function monkey:events/tick", "datapack"),
    ("Error sending packet clientbound/minecraft:chunk", "network"),
    ("Exception in server tick loop", "crash"),
    ("Something only this mod says", None),
    (None, None),
])
def test_a_line_is_matched_to_its_likely_cause(text, want):
    found = w.known(text)
    assert (found.id if found else None) == want


def test_every_cause_has_a_title_a_fix_and_a_level():
    ids = [k.id for k in w.KNOWN]
    assert len(ids) == len(set(ids))
    for k in w.KNOWN:
        assert k.title and k.fix.endswith(".") and k.level in ("alert", "warn", "info")


def reading(**over):
    data = {"problems": {"errors": [], "crashes": []}, "history": [],
            "host": {"memory": {"total": 100, "available": 50}, "swap": {"total": 10, "free": 10},
                     "disk": {"total": 100, "free": 50}},
            "backups": {"offsite": "on"}}
    data.update(over)
    return data


def test_a_healthy_reading_has_no_advice():
    assert w.advice(reading()) == []


def test_advice_from_the_log_and_the_crash_reports_one_row_a_cause_worst_first():
    rows = w.advice(reading(problems={
        "errors": [{"text": "Error sending packet x"}, {"text": "Error sending packet y"},
                   {"text": "Mixin apply for mod foo failed"}, {"text": "nothing known"}, "junk"],
        "crashes": [{"when": "2026-11-15T01:00:00Z", "text": "Ticking entity"},
                    {"when": "2026-11-15T00:00:00Z", "text": None}]}))
    assert [(r["id"], r["level"], r["source"]) for r in rows] == [
        ("ticking", "alert", "crash"), ("crash", "alert", "crash"),
        ("mixin", "warn", "log"), ("network", "info", "log")]
    assert rows[1]["from"] == "a crash report with no description"


@pytest.mark.parametrize("p95s, lagging", [
    ([60, 70, 80], True), ([60, 40, 80], False), ([70, 80], False), ([None, 70, 80], False), ([60, 60, 50], False),
])
def test_lag_counts_only_when_it_lasts(p95s, lagging):
    history = [[i, 10, p95, 1, 50, 50] for i, p95 in enumerate(p95s)]
    rows = w.advice(reading(history=history))
    assert ("lag" in [r["id"] for r in rows]) is lagging


def test_the_machines_numbers():
    rows = w.advice(reading(host={"memory": {"total": 100, "available": 5}, "swap": {"total": 10, "free": 2},
                                  "disk": {"total": 100, "free": 4}}, backups={"offsite": "failing"}))
    levels = {r["id"]: r["level"] for r in rows}
    assert levels == {"memory": "alert", "disk": "alert", "backup": "alert", "swap": "warn"}
    assert all(r["source"] == "machine" for r in rows)
    assert w.advice(reading(host={"memory": None, "swap": {"total": 0, "free": 0}, "disk": "x"})) == []


def alert(id, source="machine", level="alert"):
    return {"id": id, "title": f"{id} title", "fix": "Do this.", "from": "a number", "level": level, "source": source}


def test_an_alert_is_posted_once_then_at_most_every_six_hours_and_cleared_once():
    lines, state = w.alerts({}, [alert("disk"), alert("swap", level="warn")], [], NOW)
    assert lines == ["Monkey SMP: disk title. a number. Do this."]
    lines, state = w.alerts(state, [alert("disk")], [], NOW + 2 * MIN)
    assert lines == []
    lines, state = w.alerts(state, [alert("disk")], [], NOW + w.QUIET)
    assert lines == ["Monkey SMP: disk title (still). a number. Do this."]
    lines, state = w.alerts(state, [], [], NOW + w.QUIET + 2 * MIN)
    assert lines == ["Monkey SMP: cleared: the disk has room again."]
    assert w.alerts(state, [], [], NOW + w.QUIET + 4 * MIN)[0] == []


def test_a_log_line_that_ages_out_is_not_cleared_aloud():
    lines, state = w.alerts({}, [alert("out-of-memory", source="log")], [], NOW)
    assert len(lines) == 1
    assert w.alerts(state, [], [], NOW + dt.timedelta(days=1))[0] == []


def test_a_crash_is_its_own_message_and_never_posted_twice_as_an_alert():
    first = [{"when": iso(NOW - 10 * MIN), "text": "Exception in server tick loop"}]
    lines, state = w.alerts({}, [], first, NOW)             # the first reading: what was there before isn't news
    assert lines == [] and state["crash_seen"] == iso(NOW - 10 * MIN)
    crashes = [*first, {"when": iso(NOW + MIN), "text": "Ticking entity"}]
    rows = [alert("ticking", source="crash")]
    lines, state = w.alerts(state, rows, crashes, NOW + 2 * MIN)
    assert len(lines) == 1 and "the game crashed: Ticking entity" in lines[0] and "Entity being ticked" in lines[0]
    lines, state = w.alerts(state, rows, crashes, NOW + 4 * MIN)
    assert lines == []                                      # the same crash, the next reading
    # Two more within the quiet half hour: held, then told together once it has passed.
    more = [*crashes, {"when": iso(NOW + 5 * MIN), "text": "Watching Server"}]
    lines, state = w.alerts(state, rows, more, NOW + 6 * MIN)
    assert lines == []
    more.append({"when": iso(NOW + 7 * MIN), "text": "Exception in server tick loop"})
    lines, state = w.alerts({**state, "crash_seen": iso(NOW + MIN)}, rows, more, NOW + 40 * MIN)
    assert len(lines) == 1 and "2 crash reports since the last message" in lines[0]


@pytest.mark.parametrize("state", [None, "x", {"posted": "x"}, {"posted": {"disk": "not a time", 5: "y"}}])
def test_a_broken_state_starts_afresh(state):
    lines, kept = w.alerts(state, [alert("disk")], [], NOW)
    assert len(lines) == 1 and kept["posted"] == {"disk": iso(NOW)}
