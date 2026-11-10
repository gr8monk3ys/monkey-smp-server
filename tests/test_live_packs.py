import json

import live_packs
from repo import REPO, Repo

OFF = {"monkey-drops": "off", "monkey-npcs": "unknown", "monkey-boss": "on"}


def page(body: str, head: str = "") -> str:
    return f"<!DOCTYPE html><html><head>{head}</head><body><main>{body}</main></body></html>"


def test_the_list_names_every_shipped_pack_with_a_known_state():
    assert live_packs.list_problems() == []
    packs = live_packs.load()
    assert set(packs) == live_packs.shipped() and set(packs) <= set(live_packs.PHRASES)


def fake_repo(tmp_path, packs: dict[str, str], shipped: list[str]) -> Repo:
    repo = Repo(tmp_path)
    for name in shipped:
        (repo.monkey / "datapacks" / name).mkdir(parents=True)
    (tmp_path / "site").mkdir()
    (tmp_path / "site" / "live-packs.json").write_text(json.dumps({"packs": packs}), encoding="utf-8")
    return repo


def test_a_shipped_pack_missing_from_the_list_fails(tmp_path):
    repo = fake_repo(tmp_path, {"monkey-drops": "off", "monkey-gone": "on", "monkey-boss": "maybe"},
                     ["monkey-drops", "monkey-boss", "monkey-omens"])
    errors = live_packs.list_problems(repo)
    assert any("no line for monkey-omens" in e for e in errors)
    assert any("monkey-gone is not a pack" in e for e in errors)
    assert any("monkey-boss is 'maybe'" in e for e in errors)


def test_a_missing_list_fails_only_where_packs_ship(tmp_path):
    assert live_packs.list_problems(Repo(tmp_path)) == []
    (Repo(tmp_path).monkey / "datapacks" / "monkey-drops").mkdir(parents=True)
    assert live_packs.list_problems(Repo(tmp_path)) != []


def test_a_page_may_not_name_a_feature_whose_pack_is_off_or_unknown():
    errors = live_packs.page_problems(page("<p>Supply drops land every Friday. Ask the Guide.</p>"), OFF)
    assert [e.split(" (")[0] for e in errors] == ["names monkey-drops", "names monkey-npcs"]
    assert live_packs.page_problems(page("<p>The border boss wakes up.</p>"), OFF) == []   # it's on


def test_case_matters_where_a_phrase_says_so():
    assert live_packs.page_problems(page("<p>Read the guide first.</p>"), OFF) == []
    firsts = {"monkey-firsts": "off", "monkey-events": "off"}
    assert live_packs.page_problems(page("<p>Be the server first: a non-anarchy world.</p>"), firsts) == []
    assert len(live_packs.page_problems(page("<p>Server Firsts and Anarchy.</p>"), firsts)) == 2


def test_a_note_licenses_its_parent_element_only():
    note = '<p data-off="monkey-drops">Not running on the server right now: supply drops.</p>'
    inside = f"<section>{note}<p>Supply drops land every Friday.</p></section>"
    assert live_packs.page_problems(page(inside), OFF) == []
    outside = f"<section><div>{note}</div><p>Supply drops land every Friday.</p></section>"
    assert len(live_packs.page_problems(page(outside), OFF)) == 1
    other = f'<section><p data-off="monkey-omens">x</p><p>Supply drops land.</p></section>'
    assert len(live_packs.page_problems(page(other), OFF)) == 1


def test_the_head_counts_and_a_page_level_note_covers_it():
    head = '<title>Supply drops</title><meta name="description" content="Supply drops each Friday.">'
    assert len(live_packs.page_problems(page("<p>Hi.</p>", head), OFF)) == 2
    note = '<p data-off="monkey-drops">Not running on the server right now: supply drops.</p>'
    assert live_packs.page_problems(page(note, head), OFF) == []
    deeper = f"<section>{note}</section>"
    assert len(live_packs.page_problems(page(deeper, head), OFF)) == 2


def test_scripts_and_styles_are_not_text():
    body = "<script>const drops = 'supply drops';</script><style>.supply-drops{}</style><p>Hi.</p>"
    assert live_packs.page_problems(page(body), OFF) == []


def test_exempt_pages_are_skipped(tmp_path):
    repo = fake_repo(tmp_path, OFF, list(OFF))
    out = tmp_path / "out"
    out.mkdir()
    (out / "changes.html").write_text(page("<p>Supply drops are new.</p>"), encoding="utf-8")
    (out / "index.html").write_text(page("<p>Supply drops are new.</p>"), encoding="utf-8")
    errors = live_packs.built_problems(out, repo)
    assert len(errors) == 1 and errors[0].startswith("out/index.html: names monkey-drops")


def test_the_site_reads_the_same_list():
    live = (REPO.root / "site" / "src" / "lib" / "live.ts").read_text(encoding="utf-8")
    assert 'import list from "@live-packs"' in live
    tsconfig = json.loads((REPO.root / "site" / "tsconfig.json").read_text(encoding="utf-8"))
    assert tsconfig["compilerOptions"]["paths"]["@live-packs"] == ["./live-packs.json"]
