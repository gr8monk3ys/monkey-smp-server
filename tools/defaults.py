"""What the tools know about the Defaults, in particular the server.properties template.

The installer copies `defaults/server.properties` on first install and fills in `{{TOKEN}}`
placeholders. `TOKENS` is the one list of placeholders the installer supports; validation derives
the placeholders actually present in the template and checks them against it in both directions.
"""
import re

TOKENS = ("RCON_PASSWORD", "SEED", "LEVEL_NAME")

_PLACEHOLDER = re.compile(r"\{\{(\w+)\}\}")


def placeholders(text: str) -> set[str]:
    """Names of every `{{NAME}}` placeholder in a template."""
    return set(_PLACEHOLDER.findall(text))


def check_server_properties(text: str) -> list[str]:
    """Problems with the server.properties template (as error strings; empty means fine)."""
    found = placeholders(text)
    errors = [f"defaults/server.properties: unsupported placeholder {{{{{name}}}}} (supported: {', '.join(TOKENS)})"
              for name in sorted(found - set(TOKENS))]
    errors += [f"defaults/server.properties: missing {{{{{name}}}}}" for name in TOKENS if name not in found]
    if re.search(r"(?m)^rcon\.password=(?!\{\{)", text):
        errors.append("defaults/server.properties: a real RCON password is committed")
    return errors


def parse_properties(text: str) -> dict[str, str]:
    """Key/value pairs of a Java .properties file (comments and blank lines skipped)."""
    out = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith(("#", "!")):
            continue
        key, _, value = line.partition("=")
        out[key.strip()] = value.strip()
    return out
