"""package/realms/pwsh.lock: the portable PowerShell that realms.sh downloads on Linux and macOS.

One line per platform, `<platform> <url> <sha256>`, for the four Unix platforms of JAVA_PLATFORMS
(Windows runs the installer on its built-in Windows PowerShell 5.1). Lines starting with # are
comments. Every url is the same PowerShell release's .tar.gz from github.com/PowerShell/PowerShell;
realms.sh unpacks it into pwsh/<file name without .tar.gz>/ next to realms/ and checks the sha256 first.

  parse(text) -> [Pin]          the pins, in file order (ValueError on a malformed line)
  check(text) -> [str]          problems (empty = fine)
  version(pins) -> "7.6.6"      the PowerShell version the pins are for
  render(version, assets)       the file for a release, from powershell_release_assets(tag)
"""
import re
from typing import NamedTuple

from upstream import JAVA_PLATFORMS

# Our platform id -> the name PowerShell's release files use for it.
PLATFORMS = {"linux-x64": "linux-x64", "linux-aarch64": "linux-arm64", "mac-x64": "osx-x64", "mac-aarch64": "osx-arm64"}
URL = re.compile(r"https://github\.com/PowerShell/PowerShell/releases/download/v(?P<version>\d+\.\d+\.\d+)/"
                 r"powershell-(?P=version)-(?P<target>[a-z0-9-]+)\.tar\.gz")
HEADER = ("# PowerShell {version} (LTS) for realms.sh on Linux and macOS: <platform> <url> <sha256>.\n"
          "# Re-pin with `python tools/check_updates.py --apply`; check with `python tools/validate.py --online`.\n")

assert set(PLATFORMS) == set(JAVA_PLATFORMS) - {"windows-x64"}


class Pin(NamedTuple):
    platform: str
    url: str
    sha256: str

    @property
    def file(self) -> str:
        return self.url.rsplit("/", 1)[1]


def parse(text: str) -> list[Pin]:
    pins = []
    for n, line in enumerate(text.splitlines(), 1):
        if not line.strip() or line.startswith("#"):
            continue
        words = line.split()
        if len(words) != 3:
            raise ValueError(f"line {n}: expected '<platform> <url> <sha256>', got {line!r}")
        pins.append(Pin(*words))
    return pins


def version(pins: list[Pin]) -> str:
    m = URL.fullmatch(pins[0].url) if pins else None
    if not m:
        raise ValueError("no PowerShell release url in pwsh.lock")
    return m["version"]


def check(text: str) -> list[str]:
    if "\r" in text:
        return ["pwsh.lock must have LF line endings (realms.sh reads it with sh)"]
    try:
        pins = parse(text)
    except ValueError as err:
        return [f"pwsh.lock {err}"]
    errors = []
    platforms = [p.platform for p in pins]
    errors += [f"pwsh.lock: no line for {p}" for p in PLATFORMS if p not in platforms]
    errors += [f"pwsh.lock: unknown platform {p}" for p in platforms if p not in PLATFORMS]
    errors += [f"pwsh.lock: {p} is listed twice" for p in sorted({p for p in platforms if platforms.count(p) > 1})]
    versions = set()
    for p in pins:
        m = URL.fullmatch(p.url)
        if not m:
            errors.append(f"pwsh.lock {p.platform}: url must be a PowerShell release .tar.gz on github.com: {p.url}")
            continue
        versions.add(m["version"])
        if p.platform in PLATFORMS and m["target"] != PLATFORMS[p.platform]:
            errors.append(f"pwsh.lock {p.platform}: url is the {m['target']} build, not {PLATFORMS[p.platform]}")
        if not re.fullmatch(r"[0-9a-f]{64}", p.sha256):
            errors.append(f"pwsh.lock {p.platform}: sha256 is not 64 lowercase hex chars")
    if len(versions) > 1:
        errors.append(f"pwsh.lock: every platform must use the same PowerShell version, not {sorted(versions)}")
    return errors


def render(version_: str, assets: dict[str, dict]) -> str:
    """pwsh.lock for one release; `assets` is Upstream.powershell_release_assets(f"v{version_}")."""
    lines = [HEADER.format(version=version_)]
    for platform, target in PLATFORMS.items():
        name = f"powershell-{version_}-{target}.tar.gz"
        if name not in assets:
            raise LookupError(f"PowerShell {version_} has no {name} with a sha256 digest")
        lines.append(f"{platform} {assets[name]['url']} {assets[name]['sha256']}\n")
    return "".join(lines)
