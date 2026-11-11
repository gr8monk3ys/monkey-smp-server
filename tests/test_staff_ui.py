"""The staff page as built (deploy/staff, from staff-ui/ by bun): what the browser gets must run under Caddy's policy
(`script-src 'self'; style-src 'self'`, no inline script or style), and the source keeps to text only.
tools/staff_ui_fresh.py (in tools/checks.py) checks that the committed build is the build of the source."""
import re

import pytest
from staff_ui import PAGE, SRC, code, only_text, source

from repo import REPO

BUILT_PAGES = ["index.html", "login.html", "reset.html", "verify.html"]


@pytest.mark.parametrize("name", BUILT_PAGES)
def test_each_page_loads_one_script_and_one_stylesheet_of_its_own(name):
    html = (PAGE / name).read_text(encoding="utf-8")
    bundle = "app" if name == "index.html" else "auth"
    assert re.findall(r'<script\b[^>]*\bsrc="([^"]+)"', html) == [f"/{bundle}.js"]
    assert re.findall(r'<link\b[^>]*rel="stylesheet"[^>]*href="([^"]+)"', html) == [f"/{bundle}.css"]
    assert (PAGE / f"{bundle}.js").is_file() and (PAGE / f"{bundle}.css").is_file()
    assert not re.search(r'rel="modulepreload"', html)


def test_the_bundles_add_no_inline_style_or_code_at_run_time():
    for name in ("app.js", "auth.js"):
        script = (PAGE / name).read_text(encoding="utf-8")
        assert 'createElement("style")' not in script and "insertRule" not in script
        assert "new Function" not in script and not re.search(r"(?<![\w.$])eval\(", script)
        assert not re.search(r"setAttribute\(\s*[\"']style", script)
        # The addresses in React's build: its error decoder, only ever shown as text, and the XML namespace names
        # it creates SVG and MathML with, which are names, never fetched.
        found = set(re.findall(r"https?://[^\s\"'`]+", script))
        assert {a for a in found if not a.startswith("http://www.w3.org/")} <= {"https://react.dev/errors/"}


def test_the_login_pages_are_the_same_build_with_their_own_name():
    for page in ("reset", "verify"):
        html = (PAGE / f"{page}.html").read_text(encoding="utf-8")
        assert f'data-page="{page}"' in html and "/auth.js" in html


def test_caddy_lets_a_visitor_with_no_session_load_the_login_bundle():
    caddy = (REPO.root / "deploy" / "Caddyfile.staff-login").read_text(encoding="utf-8")
    locked = re.search(r"@locked not path (.+)", caddy)[1].split()
    assert "/auth.js" in locked and "/auth.css" in locked
    assert "/app.js" not in locked and "/app.css" not in locked


def test_every_source_file_only_uses_text():
    for path in sorted(p for p in SRC.rglob("*") if p.suffix in (".ts", ".tsx")):
        only_text(path.read_text(encoding="utf-8"))


def test_every_call_carries_the_staff_header():
    assert '"X-Monkey-Staff": "1"' in source("lib", "api.ts")
    assert '"X-Monkey-Staff": "1"' in source("lib", "auth.ts")
    assert '"X-Monkey-Staff": "1"' in source("lib", "status.tsx")
    # Nothing calls fetch() but those three: the panel, the login, and the shell's staff.json reading.
    callers = [p.relative_to(SRC).as_posix() for p in SRC.rglob("*") if p.suffix in (".ts", ".tsx")
               and re.search(r"(?<![\w.])fetch\(", code(p.read_text(encoding="utf-8")))]
    assert sorted(callers) == ["lib/api.ts", "lib/auth.ts", "lib/status.tsx"]
