"""The staff page's Mod settings tab: tools/staff_modcfg.py (parsers, line edits, endpoints), deploy/staff/modcfg.js."""
import json
from pathlib import Path

import pytest
import staff_modcfg as m
import staff_panel
from test_staff_panel import box  # noqa: F401 (the panel behind a real HTTP server, docker and the lock faked)

from repo import REPO

DEFAULTS = REPO.root / "package" / "monkey" / "defaults"

TOML = """\
# Top comment, not about any key.

# Whether the mod is on.
enabled = true   # trailing note
count = 5
ratio = 0.5
name = "Monkey \\"SMP\\""
literal = 'C:\\path'
list = ["a", "b"]
padded = [ 1, 2 ]
multi = [
    "x",
    "y",
]
with_comment = [
    "x", # why
]
when = 1979-05-27 07:32:00
text = \"\"\"
a = 1
\"\"\"
inline = { a = 1 }

[section."dotted.name"]
# Range: 1 ~ 10
level = 3
# Allowed Values: LOW, MID, HIGH
mode = "MID"

[[rules]]
id = 1
[[rules]]
id = 2
api_token = "tok-real"
"""

PROPS = """\
#LootRestock
# How often
reset_time_value=7
reset_time_unit = days
on: true
spaced value with spaces
caf\\u00e9=\\u00e9t\\u00e9
wrapped=one \\
  two
dup=1
dup=2
db_password=hunter2-real
"""

JSON5 = """\
{
  // Turns the logger on.
  "enabled": true,
  name: 'it\\'s', // the name
  "ratio": 1.5,
  "ids": [1, 2, 3],
  "words": [
    "a",
    "b"
  ],
  "nested": { "deep": { "x": -4 } },
  "objs": [ { "y": "z" } ],
  "nothing": null,
  "hex": 0x1F,
  "botSecret": "sec-real",
}
"""


def fields(fmt, text):
    rows, _ = m.parse(fmt, text)
    return {r["key"]: r for r in rows}


def changed_lines(old: str, new: str) -> list[int]:
    a, b = old.split("\n"), new.split("\n")
    assert len(a) == len(b)
    return [i for i, (x, y) in enumerate(zip(a, b, strict=True)) if x != y]


@pytest.fixture(autouse=True)
def registered():
    assert m.sp is staff_panel    # staff_panel registers this module on import


# ---------------------------------------------------------------- TOML


def test_toml_reads_types_tables_comments_and_limits():
    f = fields("toml", TOML)
    assert f["enabled"]["value"] is True and f["enabled"]["about"] == "Whether the mod is on. trailing note"
    assert f["count"]["value"] == 5 and f["ratio"]["value"] == 0.5
    assert f["name"]["value"] == 'Monkey "SMP"' and f["literal"]["value"] == "C:\\path"
    assert f["list"]["value"] == ["a", "b"] and f["list"]["item"] == "text"
    assert f["multi"]["type"] == "list" and f["multi"]["value"] == ["x", "y"]
    for key in ("with_comment", "when", "text", "inline"):
        assert f[key]["type"] == "fixed", key
    assert "a" not in f                              # the line inside the multi-line string is no key
    level = f['section."dotted.name".level']
    assert (level["min"], level["max"]) == (1, 10)
    assert f['section."dotted.name".mode']["choices"] == ["LOW", "MID", "HIGH"]
    assert f["rules[0].id"]["value"] == 1 and f["rules[1].id"]["value"] == 2


@pytest.mark.parametrize("key,value,line", [
    ("enabled", False, "enabled = false   # trailing note"),
    ("count", 12, "count = 12"),
    ("ratio", 2, "ratio = 2.0"),
    ("name", 'say "hi" \\ é', 'name = "say \\"hi\\" \\\\ é"'),
    ("literal", "D:\\other", "literal = 'D:\\other'"),
    ("literal", "it's", "literal = \"it's\""),
    ("list", ["c"], 'list = ["c"]'),
    ("padded", [3], "padded = [ 3 ]"),
])
def test_toml_edits_change_only_that_value(key, value, line):
    new, changed = m.edit("toml", TOML, {key: value})
    assert changed == [key]
    (n,) = changed_lines(TOML, new)
    assert new.split("\n")[n] == line
    assert fields("toml", new)[key]["value"] == value


def test_a_multi_line_list_keeps_its_layout_and_may_grow():
    new, _ = m.edit("toml", TOML, {"multi": ["x", "y", "z"]})
    assert 'multi = [\n    "x",\n    "y",\n    "z"\n]\nwith_comment' in new
    assert fields("toml", new)["multi"]["value"] == ["x", "y", "z"]
    assert new.replace('    "z"\n', "").replace('"y"\n]', '"y",\n]') == TOML


def test_values_sent_back_as_read_change_nothing():
    for fmt, text in (("toml", TOML), ("properties", PROPS), ("json5", JSON5)):
        rows = [r for r in m.parse(fmt, text)[0] if r["type"] != "fixed"]
        new, changed = m.edit(fmt, text, {r["key"]: r["value"] for r in rows})
        assert new == text and changed == [], fmt


@pytest.mark.parametrize("path", ["config/antixray.toml", "config/openpartiesandclaims-server.toml",
                                  "config/enchantmentdisabler/config.toml", "lootrestock.properties",
                                  "config/chunky/config.json"])
def test_the_packs_own_configs_read_whole_and_edit_one_line(path):
    text = (DEFAULTS / path).read_text(encoding="utf-8")
    fmt = m.FORMATS[Path(path).suffix]
    rows, skipped = m.parse(fmt, text)
    assert rows and skipped == 0
    first = next(r for r in rows if r["type"] in ("int", "bool"))
    value = not first["value"] if first["type"] == "bool" else first["value"] + 1
    new, changed = m.edit(fmt, text, {first["key"]: value})
    assert changed == [first["key"]] and len(changed_lines(text, new)) == 1


@pytest.mark.parametrize("key,value", [
    ("count", "5"), ("count", True), ("count", 1.5), ("enabled", 1), ("ratio", float("inf")),
    ('section."dotted.name".level', 11), ('section."dotted.name".mode', "ULTRA"), ("name", "two\nlines"),
    ("list", ["a", 1]), ("list", "a"), ("when", "2020-01-01"), ("text", "x"), ("missing", 1),
])
def test_bad_values_are_refused(key, value):
    with pytest.raises(staff_panel.Refused):
        m.edit("toml", TOML, {key: value})


# ---------------------------------------------------------------- .properties


def test_properties_read_and_edit():
    f = fields("properties", PROPS)
    assert f["reset_time_value"]["value"] == 7 and f["reset_time_value"]["about"] == "LootRestock How often"
    assert f["reset_time_unit"]["value"] == "days" and f["on"]["value"] is True
    assert f["spaced"]["value"] == "value with spaces" and f["café"]["value"] == "été"
    assert f["wrapped"]["type"] == "fixed" and "two" not in f
    assert f["dup"]["value"] == 2                   # the last line wins, as in Java
    new, _ = m.edit("properties", PROPS, {"reset_time_unit": "hours", "café": "ñ", "on": False})
    assert changed_lines(PROPS, new) == [3, 4, 6]
    assert "reset_time_unit = hours\n" in new and "caf\\u00e9=\\u00f1\n" in new and "on: false\n" in new


# ---------------------------------------------------------------- JSON and JSON5


def test_json5_reads_comments_quotes_and_nesting():
    f = fields("json5", JSON5)
    assert f["enabled"]["about"] == "Turns the logger on." and f["name"]["about"] == "the name"
    assert f["name"]["value"] == "it's" and f["ids"]["value"] == [1, 2, 3] and f["ids"]["item"] == "int"
    assert f["words"]["value"] == ["a", "b"] and f["nested.deep.x"]["value"] == -4
    assert f["objs[0].y"]["value"] == "z"
    assert f["nothing"]["type"] == "fixed" and f["hex"]["type"] == "fixed"


def test_json5_edits_keep_quotes_and_layout():
    new, changed = m.edit("json5", JSON5, {"name": "a'b", "ratio": 3, "words": ["c"], "nested.deep.x": 9,
                                           "enabled": False})
    assert changed == ["enabled", "name", "nested.deep.x", "ratio", "words"]
    assert "name: 'a\\'b', // the name" in new and '"ratio": 3.0,' in new
    assert '"words": [\n    "c"\n  ],' in new and '"x": 9' in new
    m.parse_json(new)


def test_a_broken_json_file_is_not_a_form():
    with pytest.raises(m.Bad):
        m.parse("json", '{"a": 1,, }')


def test_strict_json_strings_are_escaped_as_json():
    text = '{\n  "motd": "hi",\n  "n": 1\n}\n'
    new, _ = m.edit("json", text, {"motd": 'é "q" \\'})
    assert json.loads(new) == {"motd": 'é "q" \\', "n": 1}


def test_mod_names_group_a_mods_files():
    assert m.mod_name("config/combatlog-common.json5") == "combatlog"
    assert m.mod_name("config/luckperms/luckperms.conf") == "luckperms"
    assert m.mod_name("lootrestock.properties") == "lootrestock"
    assert m.mod_name("config/openpartiesandclaims-server.toml") == "openpartiesandclaims"


# ---------------------------------------------------------------- the endpoints


@pytest.fixture
def mods(box):  # noqa: F811 (box is the imported fixture)
    files = {"config/sample.toml": TOML, "config/logger.json5": JSON5, "lootrestock.properties": PROPS,
             "config/sample-client.toml": "a = 1\n", "config/luckperms/luckperms.conf": "a = 1\n"}
    for rel, text in files.items():
        (box.root / rel).parent.mkdir(parents=True, exist_ok=True)
        (box.root / rel).write_bytes(text.encode())
    (box.panel.repo / "deploy" / "staff").mkdir(parents=True)
    (box.panel.repo / m.IMPORTANT).write_text(json.dumps({"mods": {"sample": {
        "title": "Sample Mod", "keys": ["count"], "applies": "reload"}}}))
    return box


def test_the_list_groups_files_by_mod_and_skips_client_files(mods):
    code, data = mods.call("GET", "/api/mod-configs")
    assert code == 200
    names = [g["name"] for g in data["mods"]]
    assert names[0] == "sample" and data["mods"][0]["title"] == "Sample Mod"     # named ones come first
    paths = {f["path"]: f["format"] for g in data["mods"] for f in g["files"]}
    assert paths["config/sample.toml"] == "toml" and paths["lootrestock.properties"] == "properties"
    assert paths["config/luckperms/luckperms.conf"] == "raw" and paths["config/bot.json5"] == "json5"
    assert "config/sample-client.toml" not in paths and "server.properties" not in paths
    assert not any(p.endswith(".db") for p in paths)


def test_reading_masks_and_locks_secrets(mods):
    code, data = mods.call("GET", "/api/mod-config?path=config/sample.toml")
    assert code == 200 and data["important"] == ["count"] and data["applies"] == "reload"
    f = {r["key"]: r for r in data["fields"]}
    assert f["rules[1].api_token"]["value"] == staff_panel.MASK and f["rules[1].api_token"]["type"] == "fixed"
    raw = json.dumps(data)
    assert "tok-real" not in raw and "start" not in f["count"]
    _, data = mods.call("GET", "/api/mod-config?path=config/logger.json5")
    assert "sec-real" not in json.dumps(data)


def test_a_secret_inside_a_multi_line_value_is_masked(mods):
    # Files hides the second line; the form must not show it either, as part of the whole value.
    (mods.root / "config/spread.toml").write_text('notes = """\nhello\npassword = ml-real\n"""\nplain = 1\n')
    code, data = mods.call("GET", "/api/mod-config?path=config/spread.toml")
    assert code == 200 and "ml-real" not in json.dumps(data)
    f = {r["key"]: r for r in data["fields"]}
    assert f["notes"]["value"] == staff_panel.MASK and f["plain"]["value"] == 1
    # A bare carriage return is a line break to Files' masking: the same here.
    (mods.root / "config/cr").mkdir(exist_ok=True)
    (mods.root / "config/cr/cr.properties").write_bytes(b"notes=x\rpassword=cr-real\nplain=1\n")
    code, data = mods.call("GET", "/api/mod-config?path=config/cr/cr.properties")
    assert code == 200 and "cr-real" not in json.dumps(data)


def test_values_a_browser_would_round_or_lose_are_shown_only(mods):
    (mods.root / "config/ids.toml").write_text('channel = 123456789012345678\nnames = ["", " a"]\nok = 5\n')
    _, data = mods.call("GET", "/api/mod-config?path=config/ids.toml")
    f = {r["key"]: r for r in data["fields"]}
    assert f["channel"]["type"] == "fixed" and f["channel"]["value"] == "123456789012345678"
    assert f["names"]["type"] == "fixed" and f["ok"]["type"] == "int"
    code, _ = mods.call("PUT", "/api/mod-config", {"path": "config/ids.toml", "mtime": data["mtime"],
                                                   "values": {"channel": 1}})
    assert code == 403


def test_a_save_changes_only_the_edited_lines_through_the_panels_save(mods):
    path = mods.root / "config/sample.toml"
    _, data = mods.call("GET", "/api/mod-config?path=config/sample.toml")
    code, done = mods.call("PUT", "/api/mod-config", {"path": "config/sample.toml", "mtime": data["mtime"],
                                                      "values": {"count": 9, "enabled": True}})
    assert code == 200 and done["changed"] == ["count"]
    new = path.read_text()
    assert changed_lines(TOML, new) == [4] and "tok-real" in new
    log = (mods.staff / "actions.log").read_text()
    assert "diego save config/sample.toml" in log and "diego mod-setting config/sample.toml: count" in log
    assert any(p.name == "sample.toml" for p in (mods.staff / "history").rglob("*"))
    code, _ = mods.call("PUT", "/api/mod-config", {"path": "config/sample.toml", "mtime": data["mtime"],
                                                   "values": {"count": 10}})
    assert code == 409


@pytest.mark.parametrize("body,code", [
    ({"path": "config/sample.toml", "values": {"rules[1].api_token": "x"}}, 403),
    ({"path": "config/sample.toml", "values": {"count": "lots"}}, 400),
    ({"path": "server.properties", "values": {"motd": "x"}}, 403),
    ({"path": "config/plain.yml", "values": {"a": 2}}, 415),
    ({"path": "config/../server.properties", "values": {"motd": "x"}}, 400),
    ({"path": "world/level.dat", "values": {"a": 1}}, 403),
    ({"path": "config/sample.toml", "values": {}}, 400),
])
def test_a_save_refuses_secrets_bad_values_and_other_files(mods, body, code):
    target = mods.root / "config/sample.toml"
    before = target.read_text()
    body = {**body, "mtime": target.stat().st_mtime}
    got, answer = mods.call("PUT", "/api/mod-config", body)
    assert got == code and answer["ok"] is False
    assert target.read_text() == before


def test_mod_settings_need_an_admin(mods):
    for method, path, body in (("GET", "/api/mod-configs", None), ("GET", "/api/mod-config?path=config/sample.toml",
                                                                   None),
                               ("PUT", "/api/mod-config", {"path": "config/sample.toml", "values": {"count": 1},
                                                           "mtime": 1})):
        code, _ = mods.call(method, path, body, role="moderator")
        assert code == 403


def test_every_route_names_who_may_use_it():
    for key in m.ROUTES:
        assert staff_panel.NEEDS[key] == "admin" and key in staff_panel.ROUTES


# ---------------------------------------------------------------- the page


def test_the_tab_code_runs_under_the_strict_policy():
    import re

    page = REPO.root / "deploy" / "staff"
    script = (page / "modcfg.js").read_text(encoding="utf-8")
    code = re.sub(r"//.*", "", script)
    assert "innerHTML" not in script and "eval(" not in script and "document.write" not in script
    assert not re.search(r"\.style\.|setAttribute\(\s*[\"']style|confirm\(|alert\(", code)
    assert not re.search(r"https?://", script)
    html = (page / "index.html").read_text(encoding="utf-8")
    assert '<script src="modcfg.js" defer></script>' in html
    missing = [i for i in set(re.findall(r'\$\("([\w-]+)"\)', script)) if f'id="{i}"' not in html]
    assert not missing
    panel = (page / "panel.js").read_text(encoding="utf-8")
    assert 'id="tab-modcfg"' in html and 'data-tab="modcfg"' in html and '"modcfg"' in panel
    assert "monkey-open-file" in panel and "monkey-open-file" in script
    # Every route the tab calls is one the panel serves.
    for route in re.findall(r'"(/api/[\w-]+)', script):
        assert route in staff_panel.PATHS, route


def test_the_important_keys_file_is_valid():
    data = json.loads((REPO.root / m.IMPORTANT).read_text(encoding="utf-8"))
    for name, mod in data["mods"].items():
        assert name == name.lower() and mod["title"]
        assert all(isinstance(k, str) for k in mod.get("keys", []))
        assert mod.get("applies", "restart") in ("restart", "reload")
