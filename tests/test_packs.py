"""tools/packs.py: the one rule for whether a world data pack is on, the kept copy, and the restart queue."""
import packs
import pytest

import rcon

LISTED = ("There are 4 data pack(s) enabled: [vanilla (built-in)], [file/monkey-boss (world)], "
          "[file/monkey-drops-old (world)], [file/Enchant Disabler for DnT 5.3.0.zip (world)]")


@pytest.mark.parametrize(("name", "is_on"), [
    ("monkey-boss", True),
    ("monkey-drops-old", True),
    ("monkey-drops", False),                            # a prefix of a pack that is on is not on
    ("monkey", False),
    ("Enchant Disabler for DnT 5.3.0.zip", True),       # spaces: found whole
    ("Enchant", False),
    ("vanilla", False),                                 # built-in, not file/
])
def test_a_pack_is_on_only_when_the_list_shows_its_whole_name(name, is_on):
    assert packs.on(LISTED, [name]) == ([name] if is_on else [])
    assert packs.off(LISTED, [name]) == ([] if is_on else [name])


def test_on_keeps_the_listing_order_and_off_the_order_asked():
    names = ["Enchant Disabler for DnT 5.3.0.zip", "monkey-sieges", "monkey-boss"]
    assert packs.on(LISTED, names) == ["monkey-boss", "Enchant Disabler for DnT 5.3.0.zip"]
    assert packs.off(LISTED, names) == ["monkey-sieges"]


@pytest.mark.parametrize("said", ["", "Unknown or incomplete command", "something else", None])
def test_an_answer_that_is_not_the_list_never_reads_as_off(said):
    with pytest.raises(packs.Unreadable):
        packs.off(said, ["monkey-boss"])
    with pytest.raises(packs.Unreadable):
        packs.listing(lambda _: said, ".", "box1")


def test_the_kept_list_is_dropped_by_staff_age_or_a_new_container(tmp_path):
    server = rcon.Recorder({"datapack": LISTED})
    clock = [1000.0]

    def listed(box, **kw):
        return packs.listing(server, tmp_path, box, now=lambda: clock[0], **kw)

    assert listed("box1") == LISTED and listed("box1") == LISTED
    assert len(server.sent) == 1
    listed("box2")                                       # restarted: a new container
    assert len(server.sent) == 2
    clock[0] += packs.PACKS_CACHE_S
    listed("box2")                                       # too old
    assert len(server.sent) == 3
    packs.forget(tmp_path, now=lambda: clock[0])         # staff changed a pack
    clock[0] += 1
    listed("box2")
    assert len(server.sent) == 4
    listed("box2")                                       # kept again after that
    assert len(server.sent) == 4
    listed("box2", fresh=True)                           # the staff page: always asks, and keeps it
    assert len(server.sent) == 5
    listed("box2")
    assert len(server.sent) == 5
    packs.forget(tmp_path)
    packs.forget(tmp_path)                               # nothing to drop: fine


def test_a_list_asked_for_before_a_staff_change_is_not_kept(tmp_path):
    clock = [1000.0]

    class ChangedWhileAsking(rcon.Recorder):
        def __call__(self, command):
            answer = super().__call__(command)
            clock[0] += 1
            packs.forget(tmp_path, now=lambda: clock[0])     # staff turns a pack off mid-question
            clock[0] += 1
            return answer

    assert packs.listing(ChangedWhileAsking({"datapack": LISTED}), tmp_path, "box1", now=lambda: clock[0]) == LISTED
    assert not (tmp_path / packs.PACKS_CACHE).exists()


def test_an_unreadable_answer_is_never_kept_and_a_broken_copy_is_skipped(tmp_path):
    with pytest.raises(packs.Unreadable):
        packs.listing(rcon.Recorder({"datapack": "something else"}), tmp_path, "box1")
    assert not (tmp_path / packs.PACKS_CACHE).exists()
    (tmp_path / packs.PACKS_CACHE).write_text("not json", encoding="utf-8")
    assert packs.listing(rcon.Recorder({"datapack": LISTED}), tmp_path, "box1") == LISTED


def test_the_restart_queue_keeps_one_change_per_pack_and_only_safe_names(tmp_path):
    written = {}

    def write(path, data):
        written[path.name] = data
        path.write_bytes(data)

    packs.set_at_restart(tmp_path, "monkey-npcs", "enable", write)
    packs.set_at_restart(tmp_path, "monkey-lore", "disable", write)
    packs.set_at_restart(tmp_path, "monkey-npcs", "disable", write)      # the later ask wins
    assert packs.at_restart(tmp_path) == {"monkey-lore": "disable", "monkey-npcs": "disable"}
    (tmp_path / packs.AT_RESTART).write_text("enable ../x\nenable monkey-npcs\nreload monkey-boss\n", encoding="utf-8")
    assert packs.at_restart(tmp_path) == {"monkey-npcs": "enable"}
    packs.set_at_restart(tmp_path, "monkey-npcs", None, write)          # dropped: nothing queued, no file
    assert not (tmp_path / packs.AT_RESTART).exists()


def test_lib_sh_names_the_tools_exit_codes():
    """deploy/lib.sh can't import rcon.py's codes, so it names its own copies: they must agree."""
    from repo import REPO
    lib = (REPO.root / "deploy" / "lib.sh").read_text()
    for name in ("NOT_RUNNING", "GAVE_UP", "PACK_OFF"):
        assert f"\nJOB_{name}={getattr(rcon, name)}\n" in lib


def test_the_week_job_names_the_wardrobe_pack():
    import challenges
    import wardrobe
    assert challenges.JOB_PACKS == (wardrobe.DATAPACK,)


@pytest.mark.parametrize(("tool", "needs"), [
    ("drops", ("monkey-drops",)), ("omens", ("monkey-omens", "monkey-drops")), ("outposts", ("monkey-outposts",)),
    ("sieges", ("monkey-sieges",)), ("wardrobe", ("monkey-wardrobe",)), ("challenges", ("monkey-wardrobe",)),
])
def test_each_timed_job_declares_the_packs_its_script_used_to(tool, needs):
    """What deploy/monkey-*.sh's JOB_PACKS said before the tools declared it (omens' sky needs the drops pack)."""
    import importlib
    assert needs == importlib.import_module(tool).JOB_PACKS


def test_a_job_with_no_packs_never_asks_the_server(capsys):
    server = rcon.Recorder()
    assert rcon.packs_on(server, [], ".") == 0 and server.sent == []
    assert capsys.readouterr().out == "data packs on: none needed\n"


def test_packs_on_fresh_asks_the_server_even_with_a_kept_list(tmp_path):
    """install-standings.sh: staff may have just turned the pack on with `monkey rcon`, which drops nothing."""
    server = rcon.Recorder({"datapack": LISTED})
    assert rcon.main(["packs-on", "monkey-boss", "--docker", str(tmp_path)], server=lambda folder: server) == 0
    assert rcon.main(["packs-on", "monkey-boss", "--docker", str(tmp_path)], server=lambda folder: server) == 0
    assert len(server.sent) == 1                                          # the second used the kept list
    assert rcon.main(["packs-on", "monkey-boss", "--docker", str(tmp_path), "--fresh"],
                     server=lambda folder: server) == 0
    assert len(server.sent) == 2


def test_the_border_asks_the_server_not_the_kept_list(tmp_path, monkeypatch):
    """A boss left out of its act is left out for good, so the border never decides from a list up to 30 minutes old."""
    import border
    seen = []
    monkeypatch.setattr(rcon, "packs_off", lambda server, names, folder=None, fresh=False: seen.append(folder) or [])
    server = rcon.Recorder()
    server.folder = tmp_path                                              # as rcon.Docker has
    assert border.without_packs_off(server, ["function monkey:boss/act {act:1}"], print) == [
        "function monkey:boss/act {act:1}"]
    assert seen == [None]
