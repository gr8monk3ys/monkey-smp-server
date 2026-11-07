"""The staff page's Mod settings tab: each mod's config file as a form. tools/staff_panel.py serves it (register()),
with the same login, role and change checks as its own; docs/LIVE.md, "The staff page", says what it does.

    GET  /api/mod-configs             the config files, one group per mod                         admin
    GET  /api/mod-config?path=F       one file's settings as typed fields                          admin
    PUT  /api/mod-config {"path", "mtime", "values"}  saves the changed ones                       admin

Which files: config/ (three folders deep) and the server folder's own *.properties except server.properties, as the
Files tab's rules allow them. .toml, .properties, .json and .json5 become forms; any other config file (.yml, .conf,
.cfg, ...) is listed with a link to the Files tab's raw editor, as is one that can't be read.

How a save works: each field is the exact span of its value in the file. A save replaces only the spans of the values
that changed, so every comment, blank line, key order and the rest of each line stay byte for byte. A value that
spans lines (a TOML multi-line string, an inline table, a list with comments in it, a date) is shown, never changed:
use Files. The new text then goes through staff_panel's own file save: the check that nobody saved since the file was
read, the copy in the history, the write and the "save" line in actions.log; this adds one "mod-setting" line naming
the keys. A key that says password, secret, token or seed is masked and locked, as in Files.

The comment above a key (and one after its value) is its help text. Forge-style "Range: A ~ B" and "Allowed Values:
A, B" in it become the field's limits and choices, and the save checks them too.

deploy/staff/mod-settings.json names each mod and its most-used keys, which the page shows first.

Stdlib only, Python 3.10 or newer (no tomllib: the parsers here read the files themselves). Imports nothing from
tools/ at load: staff_panel hands itself over in register().
"""
import bisect
import json
import math
import os
import re
import stat
from pathlib import Path, PurePosixPath

sp = None   # tools/staff_panel.py (register)

FORMATS = {".toml": "toml", ".properties": "properties", ".json": "json", ".json5": "json5"}
RAW_ONLY = {".yml", ".yaml", ".conf", ".cfg", ".ini", ".txt", ".hocon", ".snbt"}
CONFIG_DIR = "config"
DEPTH = 4                       # config/a/b/c/file
FILES_MAX = 600
TEXT_MAX_VALUE = 2000           # one text value
LIST_MAX = 1000                 # items in one list
VALUES_MAX = 500                # values in one save
INT_LIMIT = 2 ** 63
IMPORTANT = Path("deploy/staff/mod-settings.json")
# Files that do nothing on a dedicated server (the client side's own settings).
CLIENT_ONLY = re.compile(r"(?:^|[-_.])client(?:[-_.]|$)", re.I)
_SUFFIX = re.compile(r"[-_](?:common|server|config|settings)$", re.I)
_RANGE = re.compile(r"Range:\s*(-?[\d.]+(?:[eE][+-]?\d+)?)\s*~\s*(-?[\d.]+(?:[eE][+-]?\d+)?)")
_ALLOWED = re.compile(r"Allowed Values:\s*([^\n]+)")


class Bad(ValueError):
    """A part of the file this reader doesn't follow: the line is skipped (shown as not understood)."""


# ---------------------------------------------------------------- one field


def _about(lines: list[str]) -> str:
    return " ".join(s for s in (line.strip() for line in lines) if s)[:1500]


def field(key: str, kind: str, value, start: int, end: int, about: str, **extra) -> dict:
    """A setting: `key` (its path in the file), `kind` (bool, int, float, text, list or fixed), its value and the
    span [start, end) of the value's text. A fixed one is shown, never saved."""
    row = {"key": key, "type": kind, "value": value, "start": start, "end": end, "about": about, **extra}
    if kind in ("int", "float"):
        m = _RANGE.search(about)
        if m:
            low, high = float(m[1]), float(m[2])
            row["min"], row["max"] = (int(low), int(high)) if kind == "int" and low.is_integer() and \
                high.is_integer() else (low, high)
    if kind == "text":
        m = _ALLOWED.search(about)
        if m:
            choices = [c.strip().strip("\"'") for c in m[1].split(",") if c.strip()]
            if value in choices and len(choices) <= 50:
                row["choices"] = choices
    return row


def _list_layout(text: str, start: int, end: int, items: list[tuple[int, int]]) -> dict:
    """How a list was written, so it is written back the same way: on one line ("[a, b]" or "[ a, b ]") or one item
    per line with the first item's indent and the closing bracket's."""
    body = text[start:end]
    if "\n" not in body:
        return {"multiline": False, "pad": body[1:2] == " " and body != "[ ]"}
    line_start = text.rfind("\n", 0, end - 1) + 1
    close = text[line_start:end - 1]
    close = close if not close.strip() else ""
    if items:
        first = text.rfind("\n", 0, items[0][0]) + 1
        indent = text[first:items[0][0]]
        indent = indent if not indent.strip() else close + "  "
    else:
        indent = close + "  "
    return {"multiline": True, "indent": indent, "close": close}


# ---------------------------------------------------------------- TOML


_BARE = re.compile(r"[A-Za-z0-9_-]+")
_TOML_TOKEN = re.compile(r"[^\s,\]}#]+")
_TOML_INT = re.compile(r"[+-]?(?:0x[0-9A-Fa-f](?:_?[0-9A-Fa-f])*|0o[0-7](?:_?[0-7])*|0b[01](?:_?[01])*|"
                       r"0|[1-9](?:_?\d)*)")
_TOML_FLOAT = re.compile(r"[+-]?(?:(?:0|[1-9](?:_?\d)*)(?:\.\d(?:_?\d)*)?(?:[eE][+-]?\d(?:_?\d)*)?|inf|nan)")
_DATE = re.compile(r"\d{4}-\d\d-\d\d|\d\d:\d\d:\d\d")
_TOML_ESCAPES = {"b": "\b", "t": "\t", "n": "\n", "f": "\f", "r": "\r", '"': '"', "\\": "\\", "e": "\x1b"}


class _Toml:
    def __init__(self, text: str):
        self.t, self.n = text, len(text)

    def ws(self, i: int) -> int:
        while i < self.n and self.t[i] in " \t":
            i += 1
        return i

    def basic(self, i: int) -> tuple[str, int]:
        """A "..." string at i: (value, the index after its closing quote)."""
        out, i = [], i + 1
        while i < self.n:
            c = self.t[i]
            if c == '"':
                return "".join(out), i + 1
            if c == "\n":
                raise Bad("a string runs past its line")
            if c == "\\":
                nxt = self.t[i + 1:i + 2]
                if nxt in _TOML_ESCAPES:
                    out.append(_TOML_ESCAPES[nxt])
                    i += 2
                    continue
                size = {"u": 4, "U": 8}.get(nxt)
                digits = self.t[i + 2:i + 2 + size] if size else ""
                if not size or not re.fullmatch(r"[0-9A-Fa-f]+", digits) or len(digits) != size:
                    raise Bad("an unknown escape")
                out.append(chr(int(digits, 16)))
                i += 2 + size
                continue
            out.append(c)
            i += 1
        raise Bad("a string with no end")

    def key(self, i: int, stop: str) -> tuple[list[str], int]:
        parts = []
        while True:
            i = self.ws(i)
            if self.t[i:i + 1] == '"':
                part, i = self.basic(i)
            elif self.t[i:i + 1] == "'":
                end = self.t.find("'", i + 1)
                if end < 0 or "\n" in self.t[i:end]:
                    raise Bad("a key with no end")
                part, i = self.t[i + 1:end], end + 1
            else:
                m = _BARE.match(self.t, i)
                if not m:
                    raise Bad("not a key")
                part, i = m[0], m.end()
            parts.append(part)
            i = self.ws(i)
            if self.t[i:i + 1] == ".":
                i += 1
                continue
            if self.t[i:i + len(stop)] != stop:
                raise Bad("a key must be followed by " + stop)
            return parts, i + len(stop)

    def skip_blank(self, i: int) -> tuple[int, bool, bool]:
        """Past spaces, new lines and comments inside a list: (index, crossed a line, had a comment)."""
        lines = comment = False
        while i < self.n:
            c = self.t[i]
            if c in " \t\r":
                i += 1
            elif c == "\n":
                lines, i = True, i + 1
            elif c == "#":
                comment = True
                end = self.t.find("\n", i)
                i = self.n if end < 0 else end
            else:
                break
        return i, lines, comment

    def value(self, i: int):
        """(kind, value, end, extra) of the value at i. A kind of "fixed" is one this page shows but doesn't edit."""
        t = self.t
        if t.startswith(('"""', "'''"), i):
            end = t.find(t[i:i + 3], i + 3)
            if end < 0:
                raise Bad("a multi-line string with no end")
            while t[end + 3:end + 4] == t[i]:   # """a"""" ends with the last three quotes
                end += 1
            return "fixed", t[i:end + 3], end + 3, {}
        if t[i:i + 1] == '"':
            value, end = self.basic(i)
            return "text", value, end, {"quote": '"'}
        if t[i:i + 1] == "'":
            end = t.find("'", i + 1)
            if end < 0 or "\n" in t[i:end]:
                raise Bad("a string with no end")
            return "text", t[i + 1:end], end + 1, {"quote": "'"}
        if t[i:i + 1] == "[":
            return self.array(i)
        if t[i:i + 1] == "{":
            depth, j = 0, i
            while j < self.n:
                c = t[j]
                if c in "\"'":
                    if c == '"':
                        j = self.basic(j)[1]
                    else:
                        j = t.find("'", j + 1) + 1
                        if not j:
                            raise Bad("a string with no end")
                    continue
                if c == "\n":
                    raise Bad("an inline table runs past its line")
                depth += {"{": 1, "}": -1}.get(c, 0)
                j += 1
                if depth == 0:
                    return "fixed", t[i:j], j, {}
            raise Bad("an inline table with no end")
        m = _TOML_TOKEN.match(t, i)
        if not m:
            raise Bad("no value")
        token, end = m[0], m.end()
        if token in ("true", "false"):
            return "bool", token == "true", end, {}
        if _DATE.match(token):
            # A date and time may hold one space: 1979-05-27 07:32:00.
            more = re.match(r"[ T]\d\d:\d\d(?::\d\d(?:\.\d+)?)?(?:Z|[+-]\d\d:\d\d)?", t[end:])
            return "fixed", token, end + (more.end() if more and token.count("-") == 2 and "T" not in token else 0), {}
        if _TOML_INT.fullmatch(token):
            clean = token.replace("_", "")
            base = {"0x": 16, "0o": 8, "0b": 2}.get(clean.lstrip("+-")[:2], 10)
            value = int(clean, base) if base == 10 else int(clean[0] + clean[3:] if clean[0] in "+-" else clean[2:],
                                                             base)
            return "int", value, end, {}
        if _TOML_FLOAT.fullmatch(token):
            value = float(token.replace("_", ""))
            return ("float" if math.isfinite(value) else "fixed"), (value if math.isfinite(value) else token), end, {}
        raise Bad("an unknown value")

    def array(self, i: int):
        start, i = i, i + 1
        items, spans, kinds, quotes, fixed, commented = [], [], set(), set(), False, False
        while True:
            i, _, comment = self.skip_blank(i)
            commented |= comment
            if i >= self.n:
                raise Bad("a list with no end")
            if self.t[i] == "]":
                i += 1
                break
            kind, value, end, extra = self.value(i)
            if kind in ("list", "fixed"):
                fixed = True
            kinds.add(kind)
            quotes.add(extra.get("quote"))
            items.append(value)
            spans.append((i, end))
            i, _, comment = self.skip_blank(end)
            commented |= comment
            if self.t[i:i + 1] == ",":
                i += 1
            elif self.t[i:i + 1] != "]":
                raise Bad("list items need commas between them")
        if fixed or commented or len(kinds) > 1:
            return "fixed", self.t[start:i], i, {}
        return "list", items, i, {"item": kinds.pop() if kinds else "text", "quote": (quotes - {None} or {'"'}).pop(),
                                  "layout": _list_layout(self.t, start, i, spans), "empty": not items}


def _toml_key(parts: list[str]) -> str:
    return ".".join(p if _BARE.fullmatch(p) else json.dumps(p) for p in parts)


def parse_toml(text: str) -> tuple[list[dict], int]:
    """(fields, lines not understood)."""
    r, fields, skipped = _Toml(text), [], 0
    table: list[str] = []
    counts: dict[str, int] = {}
    comments: list[str] = []
    i = 0
    while i < r.n:
        i = r.ws(i)
        line_end = text.find("\n", i)
        line_end = r.n if line_end < 0 else line_end
        if i >= r.n:
            break
        c = text[i]
        if c in "\r\n":
            comments = []
            i = line_end + 1
            continue
        if c == "#":
            comments.append(text[i + 1:line_end].rstrip("\r"))
            i = line_end + 1
            continue
        try:
            if c == "[":
                double = text.startswith("[[", i)
                parts, end = r.key(i + (2 if double else 1), "]]" if double else "]")
                name = _toml_key(parts)
                table = [_toml_key([x]) for x in parts]      # each part as it is shown: quoted if it must be
                if double:
                    counts[name] = counts.get(name, -1) + 1
                    table[-1] += f"[{counts[name]}]"
                comments = []
                rest = r.ws(end)
                if text[rest:rest + 1] not in ("", "\n", "\r", "#"):
                    raise Bad("text after a table header")
                i = line_end + 1
                continue
            parts, end = r.key(i, "=")
            vstart = r.ws(end)
            kind, value, vend, extra = r.value(vstart)
            after = r.ws(vend)
            trailing = ""
            if text[after:after + 1] == "#":
                close = text.find("\n", after)
                close = r.n if close < 0 else close
                trailing = text[after + 1:close].rstrip("\r")
                after = close
            if text[after:after + 1] not in ("", "\n", "\r"):
                raise Bad("text after a value")
            key = ".".join([*table, _toml_key(parts)])
            fields.append(field(key, kind, value, vstart, vend, _about([*comments, trailing]), **extra))
            comments = []
            nl = text.find("\n", after)
            i = r.n if nl < 0 else nl + 1
        except Bad:
            skipped += 1
            comments = []
            i = line_end + 1
    return fields, skipped


def _toml_text(value: str, quote: str) -> str:
    if quote == "'" and "'" not in value and all(c.isprintable() or c == "\t" for c in value):
        return f"'{value}'"
    out = []
    for c in value:
        if c in ('"', "\\"):
            out.append("\\" + c)
        elif c == "\t" or c.isprintable():
            out.append(c)
        else:
            out.append(f"\\u{ord(c):04x}" if ord(c) < 0x10000 else f"\\U{ord(c):08x}")
    return '"' + "".join(out) + '"'


# ---------------------------------------------------------------- .properties


_PROP = re.compile(r"(?P<key>(?:\\.|[^\s=:\\])+)(?P<sep>\s*[=:]\s*|\s+|$)(?P<value>.*)")
_INT = re.compile(r"-?(?:0|[1-9]\d{0,17})")
_FLOAT = re.compile(r"-?\d+\.\d+")


def parse_properties(text: str) -> tuple[list[dict], int]:
    unescape = sp_apex().unescape
    fields, comments, skipped, go_on = {}, [], 0, False
    for m in re.finditer(r"[^\n]*\n|[^\n]+", text):
        line = m[0].rstrip("\n").rstrip("\r")
        trail = len(line) - len(line.rstrip("\\"))
        if go_on:                      # the rest of a value that ended its line with a backslash
            go_on = trail % 2 == 1
            continue
        stripped = line.lstrip()
        if not stripped:
            comments = []
            continue
        if stripped[0] in "#!":
            comments.append(stripped[1:])
            continue
        lead = len(line) - len(stripped)
        p = _PROP.match(stripped)
        if not p:
            skipped += 1
            continue
        key = unescape(p["key"])
        start, end = m.start() + lead + p.start("value"), m.start() + lead + p.end("value")
        if trail % 2 == 1:
            go_on = True
            fields[key] = field(key, "fixed", stripped[p.start("value"):], start, end, _about(comments))
        else:
            raw = p["value"]
            value = unescape(raw)
            if raw in ("true", "false"):
                row = field(key, "bool", raw == "true", start, end, _about(comments))
            elif _INT.fullmatch(raw):
                row = field(key, "int", int(raw), start, end, _about(comments))
            elif _FLOAT.fullmatch(raw):
                row = field(key, "float", float(raw), start, end, _about(comments))
            else:
                row = field(key, "text", value, start, end, _about(comments))
            fields.pop(key, None)       # the last line of a key wins, as in Java
            fields[key] = row
        comments = []
    return list(fields.values()), skipped


# ---------------------------------------------------------------- JSON and JSON5


_J_NUM = re.compile(r"[+-]?(?:0[xX][0-9A-Fa-f]+|Infinity|NaN|(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?)")
_J_IDENT = re.compile(r"[A-Za-z_$][A-Za-z0-9_$]*")
_J_ESC = {"b": "\b", "f": "\f", "n": "\n", "r": "\r", "t": "\t", "v": "\v", "0": "\0", "\n": ""}


class _Tok:
    __slots__ = ("kind", "value", "start", "end", "before", "after", "raw")

    def __init__(self, kind, value, start, end, raw=""):
        self.kind, self.value, self.start, self.end, self.raw = kind, value, start, end, raw
        self.before: list[str] = []
        self.after: list[str] = []


def _json_tokens(text: str) -> list[_Tok]:
    toks, i, n = [], 0, len(text)
    pending: list[str] = []
    line_since, line_has = True, False     # a new line since the last token; this line has a token or comment
    while i < n:
        c = text[i]
        if c in " \t\r\ufeff":
            i += 1
            continue
        if c == "\n":
            if not line_has:    # a blank line: the comments above it belong to nothing
                pending = []
            line_since, line_has = True, False
            i += 1
            continue
        if text.startswith(("//", "/*"), i):
            if text.startswith("//", i):
                end = text.find("\n", i)
                end = n if end < 0 else end
                said = text[i + 2:end]
            else:
                end = text.find("*/", i + 2)
                if end < 0:
                    raise Bad("a comment with no end")
                said = text[i + 2:end].replace("*", " ")
                end += 2
            if toks and not line_since:
                toks[-1].after.append(said)     # after a value on its own line: that value's help
            else:
                pending.append(said)
            line_has = True
            i = end
            continue
        start = i
        if c in "{}[]:,":
            tok = _Tok(c, c, i, i + 1)
            i += 1
        elif c in "\"'":
            out, i = [], i + 1
            while True:
                if i >= n:
                    raise Bad("a string with no end")
                ch = text[i]
                if ch == c:
                    i += 1
                    break
                if ch == "\n":
                    raise Bad("a string runs past its line")
                if ch == "\\":
                    nxt = text[i + 1:i + 2]
                    if nxt == "u" and re.fullmatch(r"[0-9A-Fa-f]{4}", text[i + 2:i + 6]):
                        out.append(chr(int(text[i + 2:i + 6], 16)))
                        i += 6
                        continue
                    if nxt == "\n":
                        raise Bad("a string runs past its line")
                    out.append(_J_ESC.get(nxt, nxt))
                    i += 2
                    continue
                out.append(ch)
                i += 1
            value = "".join(out)
            with_pairs = value.encode("utf-16", "surrogatepass")
            tok = _Tok("str", with_pairs.decode("utf-16", "replace"), start, i, c)
        else:
            m = _J_NUM.match(text, i) or _J_IDENT.match(text, i)
            if not m:
                raise Bad("not JSON")
            word = m[0]
            i = m.end()
            if word in ("true", "false"):
                tok = _Tok("bool", word == "true", start, i)
            elif word == "null":
                tok = _Tok("null", None, start, i)
            elif _J_NUM.fullmatch(word):
                tok = _Tok("num", word, start, i)
            else:
                tok = _Tok("ident", word, start, i)
        tok.before, pending, line_since, line_has = pending, [], False, True
        toks.append(tok)
    return toks


class _Json:
    def __init__(self, text: str, toks: list[_Tok]):
        self.text, self.toks, self.i, self.fields = text, toks, 0, []

    def peek(self) -> _Tok:
        if self.i >= len(self.toks):
            raise Bad("the file ends too soon")
        return self.toks[self.i]

    def take(self, kind: str) -> _Tok:
        tok = self.peek()
        if tok.kind != kind:
            raise Bad(f"expected {kind}")
        self.i += 1
        return tok

    @staticmethod
    def scalar(tok: _Tok):
        """(kind, value, extra) of a scalar token."""
        if tok.kind == "bool":
            return "bool", tok.value, {}
        if tok.kind == "str":
            return "text", tok.value, {"quote": tok.raw}
        if tok.kind == "num":
            word = tok.value
            if re.fullmatch(r"-?(?:0|[1-9]\d*)", word):
                return "int", int(word), {}
            if re.fullmatch(r"-?(?:0|[1-9]\d*)(?:\.\d+)?(?:[eE][+-]?\d+)?", word):
                return "float", float(word), {}
            return "fixed", word, {}
        return "fixed", "null", {}

    def help_of(self, key_tok: _Tok | None, last: _Tok) -> str:
        said = [*(key_tok.before if key_tok else []), *last.after]
        nxt = self.toks[self.i] if self.i < len(self.toks) else None
        if nxt is not None and nxt.kind == ",":
            said += nxt.after
        return _about(said)

    def value(self, path: str, key_tok: _Tok | None) -> None:
        tok = self.peek()
        if tok.kind == "{":
            self.i += 1
            while True:
                tok = self.peek()
                if tok.kind == "}":
                    self.i += 1
                    return
                if tok.kind not in ("str", "ident"):
                    raise Bad("an object key must be a name")
                self.i += 1
                self.take(":")
                key = tok.value if _BARE.fullmatch(tok.value) else json.dumps(tok.value)
                self.value(f"{path}.{key}" if path else key, tok)
                if self.peek().kind == ",":
                    self.i += 1
                elif self.peek().kind != "}":
                    raise Bad("expected , or }")
        elif tok.kind == "[":
            self.array(path, key_tok)
        elif tok.kind in ("str", "num", "bool", "null", "ident"):
            if tok.kind == "ident":
                raise Bad("a bare word as a value")
            self.i += 1
            kind, value, extra = self.scalar(tok)
            self.fields.append(field(path, kind, value, tok.start, tok.end, self.help_of(key_tok, tok), **extra))
        else:
            raise Bad("not a value")

    def array(self, path: str, key_tok: _Tok | None) -> None:
        open_tok = self.take("[")
        items, spans, kinds, quotes, simple = [], [], set(), set(), True
        depth, j = 0, self.i
        while True:     # look ahead: a list of scalars of one kind with no comments in it is one field
            if j >= len(self.toks):
                raise Bad("a list with no end")
            tok = self.toks[j]
            if tok.kind == "]" and depth == 0:
                break
            if tok.kind in "[{":
                depth += 1
                simple = False
            elif tok.kind in "]}":
                depth -= 1
            elif depth == 0 and tok.kind not in (",", ":"):
                kind, value, extra = self.scalar(tok)
                if kind == "fixed":
                    simple = False
                kinds.add(kind)
                quotes.add(extra.get("quote"))
                items.append(value)
                spans.append((tok.start, tok.end))
            if tok.before or tok.after:     # a comment inside the list: rewriting it would lose the comment
                simple = False
            j += 1
        close_tok = self.toks[j]
        if close_tok.before:
            simple = False
        if simple and len(kinds) <= 1:
            self.i = j + 1
            layout = _list_layout(self.text, open_tok.start, close_tok.end, spans)
            self.fields.append(field(path, "list", items, open_tok.start, close_tok.end,
                                     self.help_of(key_tok, close_tok), item=kinds.pop() if kinds else "text",
                                     quote=(quotes - {None} or {'"'}).pop(), layout=layout, empty=not items))
            return
        n = 0
        while self.peek().kind != "]":
            self.value(f"{path}[{n}]", None)
            n += 1
            if self.peek().kind == ",":
                self.i += 1
            elif self.peek().kind != "]":
                raise Bad("expected , or ]")
        self.i += 1


def parse_json(text: str) -> tuple[list[dict], int]:
    """(fields, 0): a JSON or JSON5 file is understood whole or not at all (Bad)."""
    p = _Json(text, _json_tokens(text))
    p.value("", None)
    if p.i != len(p.toks):
        raise Bad("text after the end")
    return p.fields, 0


def _json_text(value: str, quote: str) -> str:
    out = json.dumps(value, ensure_ascii=False)
    if quote != "'":
        return out
    inner = out[1:-1].replace('\\"', '"').replace("'", "\\'")
    return f"'{inner}'"


# ---------------------------------------------------------------- writing a value


def _number(value, kind: str) -> str:
    if kind == "int":
        return str(value)
    text = repr(float(value))
    return text if any(c in text for c in ".eE") else text + ".0"


def render(fmt: str, row: dict, value) -> str:
    """The text that replaces row's span for `value`."""
    kind = row["type"]
    if kind == "list":
        item = row["item"]
        parts = [render(fmt, {"type": item, "quote": row.get("quote", '"')}, v) for v in value]
        layout = row["layout"]
        if not parts:
            return "[]"
        if layout["multiline"]:
            return "[\n" + ",\n".join(layout["indent"] + p for p in parts) + "\n" + layout["close"] + "]"
        return "[ " + ", ".join(parts) + " ]" if layout["pad"] else "[" + ", ".join(parts) + "]"
    if kind == "bool":
        return "true" if value else "false"
    if kind in ("int", "float"):
        return _number(value, kind)
    if fmt == "toml":
        return _toml_text(value, row.get("quote", '"'))
    if fmt == "properties":
        return sp_apex().escape(value)
    return _json_text(value, row.get("quote", '"'))


def checked(row: dict, value):
    """The value as its field takes it, or Refused."""
    key, kind = row["key"], row["type"]
    if kind == "fixed" or row.get("locked"):
        raise sp.Refused(403, f"{key} can't be changed here: use Files.")
    if kind == "list":
        if not isinstance(value, list) or len(value) > LIST_MAX:
            raise sp.Refused(400, f"{key} must be a list of at most {LIST_MAX} items.")
        return [checked({"key": f"{key} item", "type": row["item"]}, v) for v in value]
    if kind == "bool":
        if not isinstance(value, bool):
            raise sp.Refused(400, f"{key} must be true or false.")
        return value
    if kind in ("int", "float"):
        if isinstance(value, bool) or not isinstance(value, int | float):
            raise sp.Refused(400, f"{key} must be a number.")
        if kind == "int":
            if isinstance(value, float):
                if not value.is_integer():
                    raise sp.Refused(400, f"{key} must be a whole number.")
                value = int(value)
            if not -INT_LIMIT <= value < INT_LIMIT:
                raise sp.Refused(400, f"{key} is too big.")
        elif not math.isfinite(value):
            raise sp.Refused(400, f"{key} must be a finite number.")
        if "min" in row and not row["min"] <= value <= row["max"]:
            raise sp.Refused(400, f"{key} must be from {row['min']} to {row['max']}.")
        return value
    if not isinstance(value, str) or len(value) > TEXT_MAX_VALUE:
        raise sp.Refused(400, f"{key} must be text of at most {TEXT_MAX_VALUE} characters.")
    if any(not (c.isprintable() or c == "\t") for c in value):
        raise sp.Refused(400, f"{key} can't hold a new line or a control character.")
    if "choices" in row and value not in row["choices"]:
        raise sp.Refused(400, f"{key} must be one of: {', '.join(row['choices'])}.")
    return value


def parse(fmt: str, text: str) -> tuple[list[dict], int]:
    if fmt == "toml":
        return parse_toml(text)
    if fmt == "properties":
        return parse_properties(text)
    return parse_json(text)


def edit(fmt: str, text: str, values: dict) -> tuple[str, list[str]]:
    """(the new text, the keys that changed): only the changed values' spans are replaced."""
    rows = {row["key"]: row for row in parse(fmt, text)[0]}
    spans = []
    for key, value in values.items():
        row = rows.get(key) if isinstance(key, str) else None
        if row is None:
            raise sp.Refused(400, f"{str(key)[:80]} is not a setting in this file: reload it.")
        value = checked(row, value)
        if value == row["value"] and type(value) is type(row["value"]) or row["type"] == "float" and \
                float(value) == row["value"]:
            continue
        spans.append((row["start"], row["end"], render(fmt, row, value), key))
    for start, end, new, _ in sorted(spans, reverse=True):
        text = text[:start] + new + text[end:]
    return text, sorted(k for *_, k in spans)


# ---------------------------------------------------------------- the panel's side


def _line_starts(text: str) -> list[int]:
    return [0] + [m.end() for m in re.finditer("\n", text)]


def sp_apex():
    import staff_apex
    return staff_apex


def mod_name(rel: str) -> str:
    """The mod a config file belongs to: its folder under config/, else its own name less -common, -server, ..."""
    parts = PurePosixPath(rel).parts
    if parts[0] == CONFIG_DIR and len(parts) > 2:
        return parts[1].lower()
    stem = PurePosixPath(parts[-1]).stem
    while _SUFFIX.search(stem):
        stem = _SUFFIX.sub("", stem)
    return stem.lower() or parts[-1].lower()


def _secret(row: dict, lines: list[str], starts: list[int]) -> bool:
    """Whether a value is a secret: its key says so, or any line its text touches is one Files would hide. A value
    that spans lines is checked on every line, so the form never shows what Files masks."""
    if sp._SECRET_KEY.search(row["key"]):
        return True
    first = bisect.bisect_right(starts, row["start"]) - 1
    last = bisect.bisect_right(starts, max(row["start"], row["end"] - 1)) - 1
    return any(sp._secret_line(line.rstrip("\r")) for line in lines[first:last + 1])


class ModConfigs:
    def __init__(self, panel):
        self.p = panel

    def important(self) -> dict:
        try:
            data = json.loads((self.p.repo / IMPORTANT).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}
        return data.get("mods", {}) if isinstance(data, dict) else {}

    def _candidates(self):
        root = self.p.root
        with os.scandir(root) as it:
            for d in it:
                if d.is_file() and d.name.endswith(".properties") and d.name != "server.properties":
                    yield d.name
        base = root / CONFIG_DIR
        if not base.is_dir():
            return
        for folder, dirs, names in os.walk(base):
            depth = len(Path(folder).relative_to(base).parts)
            dirs[:] = sorted(d for d in dirs if depth + 1 < DEPTH)
            for name in sorted(names):
                yield Path(os.path.relpath(os.path.join(folder, name), root)).as_posix()

    def _allowed(self, rel: str) -> tuple[Path, tuple[str, ...]] | None:
        try:
            path, parts = self.p.resolve(rel, "write")
        except sp.Refused:
            return None
        return path, parts

    def list(self) -> dict:
        known = self.important()
        groups: dict[str, dict] = {}
        count = 0
        for rel in self._candidates():
            suffix = PurePosixPath(rel).suffix.lower()
            if (suffix not in FORMATS and suffix not in RAW_ONLY) or CLIENT_ONLY.search(PurePosixPath(rel).stem) \
                    or PurePosixPath(rel).name.startswith(".staff-"):
                continue
            found = self._allowed(rel)
            if not found:
                continue
            try:
                st = found[0].stat()
            except OSError:
                continue
            if not stat.S_ISREG(st.st_mode):
                continue
            name = mod_name(rel)
            info = known.get(name, {})
            group = groups.setdefault(name, {"name": name, "title": info.get("title") or name, "files": [],
                                             "about": info.get("about", ""), "first": bool(info)})
            group["files"].append({"path": "/".join(found[1]), "format": FORMATS.get(suffix, "raw"),
                                   "size": st.st_size, "mtime": st.st_mtime})
            count += 1
            if count >= FILES_MAX:
                break
        rows = sorted(groups.values(), key=lambda g: (not g["first"], g["title"].lower()))
        return {"mods": rows, "cut": count >= FILES_MAX}

    def _file(self, rel) -> tuple[Path, tuple[str, ...], str]:
        path, parts = self.p.resolve(rel, "read")
        name = "/".join(parts)
        top_ok = len(parts) == 1 and name.endswith(".properties") and name != "server.properties"
        if not (top_ok or (len(parts) > 1 and parts[0] == CONFIG_DIR)):
            raise sp.Refused(403, "Only config/ and the server folder's own .properties files are mod settings.")
        fmt = FORMATS.get(PurePosixPath(name).suffix.lower())
        if not fmt:
            raise sp.Refused(415, "This page can't read that kind of file as a form: edit it in Files.")
        return path, parts, fmt

    def read(self, rel) -> dict:
        path, parts, fmt = self._file(rel)
        text, st = self.p._text(path)
        name = "/".join(parts)
        lines, starts = text.split("\n"), _line_starts(text)
        try:
            rows, skipped = parse(fmt, text)
        except Bad as e:
            return {"path": name, "format": fmt, "mtime": st.st_mtime, "fields": [], "skipped": 0,
                    "error": f"This file can't be read as a form ({e}): edit it in Files.",
                    "writable": self.p._rules(parts) == "writable"}
        out = []
        for row in rows:
            shown = {k: v for k, v in row.items() if k not in ("start", "end", "layout")}
            shown["about"] = sp.mask_secrets(row["about"])[0]
            if _secret(row, lines, starts):
                shown.update(value=sp.MASK, type="fixed", locked="A secret: change it in Files.")
            out.append(shown)
        info = self.important().get(mod_name(name), {})
        important = [k for k in info.get("keys", []) if isinstance(k, str)]
        return {"path": name, "format": fmt, "mtime": st.st_mtime, "fields": out, "skipped": skipped,
                "important": important, "writable": self.p._rules(parts) == "writable",
                "applies": info.get("applies", "restart")}

    def save(self, user: str, body: dict) -> dict:
        values, mtime = body.get("values"), body.get("mtime")
        if not isinstance(values, dict) or not values or len(values) > VALUES_MAX:
            raise sp.Refused(400, "values must be the settings to change.")
        if not isinstance(mtime, int | float) or isinstance(mtime, bool):
            raise sp.Refused(400, "mtime must be the number the file was read with.")
        path, parts, fmt = self._file(body.get("path"))
        name = "/".join(parts)
        text, st = self.p._text(path)
        if st.st_mtime != mtime:
            raise sp.Refused(409, "Someone else saved this file since you opened it: reload it.")
        lines, starts = text.split("\n"), _line_starts(text)
        try:
            rows = {row["key"]: row for row in parse(fmt, text)[0]}
        except Bad as e:
            raise sp.Refused(400, f"This file can't be read as a form ({e}): edit it in Files.") from None
        for key in values:
            row = rows.get(key) if isinstance(key, str) else None
            if row and _secret(row, lines, starts):
                raise sp.Refused(403, f"{key} is a secret: change it in Files.")
        new, changed = edit(fmt, text, values)
        if not changed:
            return {"changed": [], "mtime": st.st_mtime}
        if fmt in ("json", "json5"):
            parse_json(new)             # still readable as a whole, or nothing is written
        if new.count("\n") != text.count("\n") and not any(rows[k]["type"] == "list" for k in changed):
            raise sp.Refused(500, "That change would have moved other lines: nothing was saved.")
        # Staff_panel's own save: it checks the time again under its lock, keeps the old file in the history, puts
        # each ******** back as the value on disk and logs "save PATH".
        shown, _ = sp.mask_secrets(new)
        done = self.p.save(user, {"path": name, "text": shown, "mtime": mtime})
        self.p.record(user, "mod-setting", f"{name}: {', '.join(changed)}")
        return {"changed": changed, "mtime": done["mtime"]}


def configs(panel) -> ModConfigs:
    found = getattr(panel, "_modcfg", None)
    if found is None:
        found = panel._modcfg = ModConfigs(panel)
    return found


ROUTES = {
    ("GET", "/api/mod-configs"): lambda p, u, q, b: configs(p).list(),
    ("GET", "/api/mod-config"): lambda p, u, q, b: configs(p).read(q.get("path") or ""),
    ("PUT", "/api/mod-config"): lambda p, u, q, b: configs(p).save(u, b),
}
NEEDS = dict.fromkeys(ROUTES, "admin")


def register(module) -> None:
    """Adds these routes to staff_panel's (`module` is staff_panel itself, as it runs, __main__ or imported)."""
    global sp
    sp = module
    module.ROUTES.update(ROUTES)
    module.NEEDS.update(NEEDS)
    module.PATHS.update(path for _, path in ROUTES)
