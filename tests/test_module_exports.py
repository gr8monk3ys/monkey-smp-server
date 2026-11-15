"""monkey.ps1 can only call what Monkey.psm1 exports: a call to a module function left out of Export-ModuleMember
fails at run time, and only on the path that calls it ("The term 'Write-Note' is not recognized", 2026-11-14:
the start path that caps a staff page memory setting bigger than the machine)."""
import re

from repo import REPO

MODULE = REPO.monkey / "Monkey.psm1"
SCRIPT = REPO.monkey / "monkey.ps1"


def exported() -> set[str]:
    text = MODULE.read_text(encoding="ascii")
    block = text[text.index("Export-ModuleMember"):]
    return set(re.findall(r"'([A-Za-z]+-[A-Za-z]+)'", block))


def module_functions() -> set[str]:
    return set(re.findall(r"^function ([A-Za-z]+-[A-Za-z]+)", MODULE.read_text(encoding="ascii"), re.M))


def test_every_module_function_monkey_ps1_calls_is_exported():
    script = SCRIPT.read_text(encoding="ascii")
    own = set(re.findall(r"^\s*function ([A-Za-z]+-[A-Za-z]+)", script, re.M))
    called = {name for name in module_functions() - own if re.search(rf"(?<![\w-]){re.escape(name)}(?![\w-])", script)}
    assert called, "found no module calls: the pattern is wrong"
    assert called - exported() == set()
