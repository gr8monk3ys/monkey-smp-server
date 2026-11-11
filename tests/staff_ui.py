"""The staff page as the tests read it: its source (staff-ui/src, React + TypeScript) and its build (deploy/staff,
what Caddy serves). Checks about what a tab asks the panel for read the source; checks about what the browser gets
(the security policy) read the build. tests/test_staff_ui.py checks the build as a whole."""
import re

from repo import REPO

PAGE = REPO.root / "deploy" / "staff"
SRC = REPO.root / "staff-ui" / "src"


def source(*parts: str) -> str:
    """The text of staff-ui/src/<parts>: one file, or every .ts and .tsx file under a folder, joined."""
    where = SRC.joinpath(*parts)
    files = [where] if where.is_file() else sorted(p for p in where.rglob("*") if p.suffix in (".ts", ".tsx"))
    assert files, f"nothing at {where}"
    return "\n".join(p.read_text(encoding="utf-8") for p in files)


def code(text: str) -> str:
    """The text without its // comment lines, for checks that comments may mention (confirm(, innerHTML)."""
    return "\n".join(line for line in text.splitlines() if not line.lstrip().startswith(("//", "*", "/*")))


def only_text(text: str) -> None:
    """What every part of the page keeps to, whatever it does: text only, never HTML from the server; no style
    attribute (the policy refuses it); no confirm(), alert() or prompt(): the confirm step is on the page."""
    body = code(text)
    assert "innerHTML" not in body and "dangerouslySetInnerHTML" not in body and "document.write" not in body
    assert "eval(" not in body and "new Function" not in body
    assert not re.search(r"\.style\.|setAttribute\(\s*[\"']style|\sstyle=\{", body)
    assert not re.search(r"(?<![\w.])(confirm|alert|prompt)\(", body)
    assert "localStorage" not in body
