"""The staff page's own logins: names, passwords, sessions, reset and email links, for tools/staff_panel.py.

    python3 tools/staff_auth.py list                          the logins, without their secrets
    python3 tools/staff_auth.py add-user NAME ROLE [--email E]  a new login; prints a one-time set-password link
    python3 tools/staff_auth.py reset-link NAME               prints a one-time link to set a new password
    python3 tools/staff_auth.py send-verify NAME              emails NAME a link to confirm their address
    python3 tools/staff_auth.py set-role NAME ROLE            moderator, admin or owner
    python3 tools/staff_auth.py end-sessions NAME             logs NAME out everywhere
    python3 tools/staff_auth.py mail-test ADDRESS             sends one test email, to see that mail works

Run it as monkey (deploy/monkey-staff.sh --add-user and --reset-link do): the store is monkey's, mode 600.

Caddy (deploy/Caddyfile.staff-login) asks GET /auth/check before it serves anything but the login pages; a good
session answers 200 with X-Staff-User and X-Staff-Role, which Caddy copies onto the request, after taking off any the
browser sent itself. The rest of /auth/ is the login page's:

    GET  /auth/check         200 with the two headers, or 401 (a page visit: 302 to /login)
    GET  /auth/session       who is logged in: {user, role, email, email_verified}, or 401
    POST /auth/login         {name, password}: sets the monkey_staff cookie
    POST /auth/logout        ends this session
    POST /auth/forgot        {who}: a name or an email; the answer is the same whatever it is
    POST /auth/reset         {token, password}: a link's new password; ends every session of that login
    POST /auth/verify        {token}: confirms an email address
    POST /auth/password      {current, password}: ends this login's other sessions
    POST /auth/email         {current, email}: the new address gets a link; the old one is told

The rules, all here:
- A password is hashed with scrypt (n=2**14, r=8, p=1: 16 MB and about 50 ms, which the 2-thread machine and the
  unit's MemoryMax=512M can carry), a salt of its own, and compared in constant time. An unknown name is checked
  against a dummy hash, so it takes as long as a wrong password, and both get the same sentence.
- A session is 32 random bytes in an HttpOnly, Secure, SameSite=Strict cookie; only its SHA-256 is kept. It ends after
  12 hours unused or 7 days in all, at logout, and when the password changes (a reset ends them all).
- 5 wrong passwords in a row lock that name for 15 minutes (an unknown name too, so a lock says nothing); 20 failures
  from one address in 15 minutes stop that address for the rest of the window. Forgot-password asks are limited too.
- A reset or email link is 32 random bytes, kept only as a hash, good once: 30 minutes for a reset by email, 24 hours
  for an email check and for a link the owner hands over. A reset email goes only to an address its owner confirmed.
- No password, token, key or link is ever logged. Mail settings come from /etc/monkey-staff-mail.env (root:monkey,
  640), read as KEY=value lines and never run: Resend (RESEND_API_KEY) or SMTP with STARTTLS (SMTP_HOST, SMTP_PORT,
  SMTP_USER, SMTP_PASSWORD), and MAIL_FROM. With neither, the page says to ask the owner, who has this CLI.

Stdlib only, Python 3.10 or newer.
"""
import argparse
import base64
import contextlib
import datetime as dt
import hashlib
import hmac
import json
import os
import re
import secrets
import smtplib
import ssl
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
from email.message import EmailMessage
from http.cookies import CookieError, SimpleCookie
from pathlib import Path
from urllib.parse import urlsplit

ROLES = ("moderator", "admin", "owner")
NAME = re.compile(r"[a-z0-9_]{2,32}")
EMAIL = re.compile(r"[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]{1,64}@[A-Za-z0-9-]{1,63}(?:\.[A-Za-z0-9-]{1,63})+")
COOKIE = "monkey_staff"
SITE_URL = "https://staff.monkeysmp.lscaturchio.xyz"
MAIL_SETTINGS = Path("/etc/monkey-staff-mail.env")
RESEND_URL = "https://api.resend.com/emails"

SCRYPT_N, SCRYPT_R, SCRYPT_P = 2 ** 14, 8, 1
SCRYPT_MAXMEM = 64 * 1024 * 1024
PASSWORD_MIN, PASSWORD_MAX = 12, 256

IDLE = 12 * 3600
ABSOLUTE = 7 * 86400
TOUCH_EVERY = 300                    # a session's last use is written down at most this often
RESET_EMAIL_LIFE = 30 * 60
LINK_LIFE = 24 * 3600                # an email check, and a link the owner hands over
LOCK_AFTER = 5
LOCK_FOR = 15 * 60
IP_WINDOW = 15 * 60
IP_FAILS = 20
FORGOT_WINDOW = 3600
FORGOT_PER_IP = 5
FORGOT_PER_USER = 3
REMEMBERED = 10_000                  # names and addresses kept in the in-memory counters, at most
BODY_MAX = 16 * 1024

WRONG = "That name and password don't match."
LOCKED = "Too many wrong passwords for that name: wait 15 minutes, or reset the password."
TOO_MANY = "Too many tries from here: wait 15 minutes."
FORGOT_SENT = "If that account has a verified email, a link is on its way."
NO_MAIL = "Email isn't set up on this server: ask the owner for a reset link."
BAD_LINK = "That link has expired or was already used: ask for a new one."


class AuthError(Exception):
    """An answer of `code` with `message`, a plain sentence for the page."""

    def __init__(self, code: int, message: str):
        super().__init__(message)
        self.code, self.message = code, message


def _b64(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    key = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=SCRYPT_N, r=SCRYPT_R, p=SCRYPT_P,
                         maxmem=SCRYPT_MAXMEM, dklen=32)
    return f"scrypt${SCRYPT_N}${SCRYPT_R}${SCRYPT_P}${_b64(salt)}${_b64(key)}"


def check_password(password: str, stored: str) -> bool:
    try:
        kind, n, r, p, salt, key = stored.split("$")
        if kind != "scrypt":
            return False
        want = base64.b64decode(key)
        got = hashlib.scrypt(password.encode("utf-8"), salt=base64.b64decode(salt), n=int(n), r=int(r), p=int(p),
                             maxmem=SCRYPT_MAXMEM, dklen=len(want))
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(got, want)


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def password_problem(password, name: str) -> str | None:
    """Why a new password is refused, or None."""
    if not isinstance(password, str):
        return "Type a password."
    if len(password) < PASSWORD_MIN:
        return f"A password needs at least {PASSWORD_MIN} characters."
    if len(password) > PASSWORD_MAX:
        return f"A password can be at most {PASSWORD_MAX} characters."
    if name and name.lower() in password.lower():
        return "The password can't contain the login's name."
    return None


def checked_email(email) -> str:
    if not isinstance(email, str) or len(email) > 254 or not EMAIL.fullmatch(email.strip()):
        raise AuthError(400, "That doesn't look like an email address.")
    return email.strip()


def iso(when: float | None) -> str | None:
    return None if not when else dt.datetime.fromtimestamp(when, dt.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def masked_email(email: str) -> str:
    """j***@example.com, for a notice to an old address."""
    local, _, domain = email.partition("@")
    return f"{local[:1]}***@{domain}"


# ---------------------------------------------------------------- mail


def settings_of(path: Path) -> dict[str, str]:
    from staff_panel import settings_file  # the panel's own KEY=value reader (a late import: it imports this)

    return settings_file(path)


class Mailer:
    """Sends one plain-text email by Resend or by SMTP with STARTTLS, as the settings say. `urlopen` and `smtp` are
    for the tests. A failure is one line on stderr naming its kind, never a key, an address or a link."""

    def __init__(self, settings: dict[str, str], urlopen=None, smtp=None):
        self.settings = settings
        self.urlopen = urlopen or urllib.request.urlopen
        self.smtp = smtp or smtplib.SMTP

    @property
    def backend(self) -> str | None:
        s = self.settings
        if not s.get("MAIL_FROM"):
            return None
        want = (s.get("MAIL_BACKEND") or "").lower()
        if want in ("", "resend") and s.get("RESEND_API_KEY"):
            return "resend"
        if want in ("", "smtp") and s.get("SMTP_HOST"):
            return "smtp"
        return None

    def send(self, to: str, subject: str, text: str) -> bool:
        backend = self.backend
        try:
            if backend == "resend":
                self._resend(to, subject, text)
            elif backend == "smtp":
                self._smtp(to, subject, text)
            else:
                return False
            return True
        except (OSError, smtplib.SMTPException, ValueError) as e:
            code = getattr(e, "code", "")
            print(f"monkey-panel: mail by {backend} failed: {type(e).__name__} {code}".rstrip(), file=sys.stderr)
            return False

    def request(self, to: str, subject: str, text: str) -> urllib.request.Request:
        body = json.dumps({"from": self.settings["MAIL_FROM"], "to": [to], "subject": subject, "text": text}).encode()
        return urllib.request.Request(RESEND_URL, data=body, method="POST", headers={
            "Authorization": f"Bearer {self.settings['RESEND_API_KEY']}", "Content-Type": "application/json",
            "User-Agent": "monkey-panel"})

    def _resend(self, to: str, subject: str, text: str) -> None:
        with self.urlopen(self.request(to, subject, text), timeout=20) as answer:
            if not 200 <= answer.status < 300:
                raise OSError(f"status {answer.status}")

    def message(self, to: str, subject: str, text: str) -> EmailMessage:
        msg = EmailMessage()
        msg["From"], msg["To"], msg["Subject"] = self.settings["MAIL_FROM"], to, subject
        msg.set_content(text)
        return msg

    def _smtp(self, to: str, subject: str, text: str) -> None:
        s = self.settings
        port = int(s.get("SMTP_PORT") or 587)
        with self.smtp(s["SMTP_HOST"], port, timeout=20) as conn:
            conn.ehlo()
            conn.starttls(context=ssl.create_default_context())    # refuses to go on in the clear
            conn.ehlo()
            if s.get("SMTP_USER"):
                conn.login(s["SMTP_USER"], s.get("SMTP_PASSWORD", ""))
            conn.send_message(self.message(to, subject, text))


# ---------------------------------------------------------------- the store


class Store:
    """auth.json in its own folder (mode 700, the file 600): users, sessions and links. Every change reads the file
    again if someone else (the CLI) wrote it, and writes a whole new file, under a lock both share."""

    def __init__(self, folder: Path):
        self.folder = Path(folder)
        self.path = self.folder / "auth.json"
        self._lock = threading.RLock()
        self._data: dict | None = None
        self._stamp = None

    @staticmethod
    def empty() -> dict:
        return {"users": {}, "sessions": {}, "tokens": {}}

    def _file_stamp(self):
        try:
            st = self.path.stat()
        except FileNotFoundError:
            return None
        return st.st_mtime_ns, st.st_size, st.st_ino

    def _load(self) -> dict:
        stamp = self._file_stamp()
        if self._data is not None and stamp == self._stamp:
            return self._data
        if stamp is None:
            data = self.empty()
        else:
            try:
                data = json.loads(self.path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                raise AuthError(500, "The login store can't be read: see journalctl -u monkey-panel.") from None
            if not isinstance(data, dict):
                raise AuthError(500, "The login store can't be read: see journalctl -u monkey-panel.")
            for key in ("users", "sessions", "tokens"):
                data.setdefault(key, {})
        self._data, self._stamp = data, stamp
        return data

    @contextlib.contextmanager
    def _file_lock(self):
        try:
            import fcntl
        except ImportError:                 # Windows, in the tests: one process
            yield
            return
        self.folder.mkdir(parents=True, exist_ok=True)
        fd = os.open(self.folder / ".lock", os.O_RDWR | os.O_CREAT, 0o600)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX)
            yield
        finally:
            os.close(fd)

    def read(self) -> dict:
        with self._lock:
            return self._load()

    @contextlib.contextmanager
    def change(self):
        with self._lock, self._file_lock():
            # A copy: a change that is refused half way leaves nothing behind, on disk or here.
            data = json.loads(json.dumps(self._load()))
            yield data
            self._save(data)

    def _save(self, data: dict) -> None:
        self.folder.mkdir(parents=True, exist_ok=True)
        with contextlib.suppress(OSError):
            os.chmod(self.folder, 0o700)
        fd, tmp = tempfile.mkstemp(prefix=".auth-", suffix=".tmp", dir=self.folder)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=1, sort_keys=True)
                f.flush()
                os.fsync(f.fileno())
            os.chmod(tmp, 0o600)
            os.replace(tmp, self.path)
        except BaseException:
            with contextlib.suppress(OSError):
                os.unlink(tmp)
            raise
        self._data, self._stamp = data, self._file_stamp()


# ---------------------------------------------------------------- the logins


class Auth:
    """Everything the logins do, apart from HTTP. `clock` is time.time's shape, `mailer()` gives a Mailer and
    `later(fn)` runs a slow step (an email) after the answer: the tests replace them."""

    def __init__(self, folder: Path, mail_settings: Path = MAIL_SETTINGS, clock=time.time, mailer=None, later=None,
                 site_url: str | None = None):
        self.store = Store(folder)
        self.mail_settings = Path(mail_settings)
        self.clock = clock
        self._mailer = mailer
        self.later = later or (lambda fn: threading.Thread(target=fn, daemon=True).start())
        self._site_url = site_url
        self._dummy: str | None = None
        self._counters = threading.Lock()
        self._ip_fails: dict[str, list[float]] = {}
        self._name_fails: dict[str, list] = {}        # unknown names: [failures, locked until]
        self._forgot_ip: dict[str, list[float]] = {}
        self._forgot_user: dict[str, list[float]] = {}

    # ------------------------------------------------ settings

    def mail_env(self) -> dict[str, str]:
        return settings_of(self.mail_settings)

    def mailer(self) -> Mailer:
        return self._mailer() if self._mailer else Mailer(self.mail_env())

    def site_url(self) -> str:
        if self._site_url:
            return self._site_url
        url = self.mail_env().get("STAFF_URL") or SITE_URL
        parts = urlsplit(url)
        return url.rstrip("/") if parts.scheme == "https" and parts.netloc else SITE_URL

    def link(self, page: str, token: str) -> str:
        # In the fragment: a browser never sends it to the server, so it is in no log.
        return f"{self.site_url()}/{page}#token={token}"

    # ------------------------------------------------ small helpers

    def _dummy_hash(self) -> str:
        if self._dummy is None:
            self._dummy = hash_password(secrets.token_urlsafe(16))
        return self._dummy

    @staticmethod
    def _recent(stamps: list[float], now: float, window: float) -> list[float]:
        return [t for t in stamps if now - t < window]

    def _remember(self, table: dict, key: str, value) -> None:
        if key not in table and len(table) >= REMEMBERED:
            table.pop(next(iter(table)))
        table[key] = value

    @staticmethod
    def _user(data: dict, name) -> dict | None:
        return data["users"].get(name) if isinstance(name, str) else None

    def _prune(self, data: dict, now: float) -> None:
        for key, s in list(data["sessions"].items()):
            if not self._session_ok(data, s, now):
                del data["sessions"][key]
        for key, t in list(data["tokens"].items()):
            if t.get("expires", 0) <= now or t.get("user") not in data["users"]:
                del data["tokens"][key]

    @staticmethod
    def _session_ok(data: dict, s: dict, now: float) -> bool:
        user = data["users"].get(s.get("user"))
        return bool(user and not user.get("disabled") and now - s.get("created", 0) < ABSOLUTE
                    and now - s.get("seen", 0) < IDLE)

    def _end_sessions(self, data: dict, name: str, keep: str | None = None) -> int:
        gone = [k for k, s in data["sessions"].items() if s.get("user") == name and k != keep]
        for k in gone:
            del data["sessions"][k]
        return len(gone)

    def _new_token(self, data: dict, kind: str, name: str, life: float, email: str | None = None) -> str:
        """A one-time link token; an older one of the same kind for the same login stops working."""
        for k, t in list(data["tokens"].items()):
            if t.get("user") == name and t.get("kind") == kind:
                del data["tokens"][k]
        token = secrets.token_urlsafe(32)
        data["tokens"][token_hash(token)] = {"kind": kind, "user": name, "email": email,
                                             "expires": self.clock() + life}
        return token

    def _take_token(self, data: dict, token, kinds: tuple[str, ...]) -> dict:
        if not isinstance(token, str) or not 20 <= len(token) <= 100:
            raise AuthError(400, BAD_LINK)
        key = token_hash(token)
        found = data["tokens"].get(key)
        if not found or found.get("kind") not in kinds or found.get("expires", 0) <= self.clock() \
                or found.get("user") not in data["users"]:
            raise AuthError(400, BAD_LINK)
        del data["tokens"][key]
        return found

    def _send(self, to: str, subject: str, text: str) -> None:
        mailer = self.mailer()
        self.later(lambda: mailer.send(to, subject, text))

    def mail_ready(self) -> bool:
        return self.mailer().backend is not None

    # ------------------------------------------------ sessions

    def session_token(self, cookie_header: str | None) -> str | None:
        if not cookie_header:
            return None
        jar = SimpleCookie()
        try:
            jar.load(cookie_header)
        except CookieError:
            return None
        morsel = jar.get(COOKIE)
        return morsel.value if morsel and 20 <= len(morsel.value) <= 100 else None

    def session(self, token: str | None) -> dict | None:
        """{user, role, email, email_verified, key} for a good session, else None. Marks it used."""
        if not token:
            return None
        key, now = token_hash(token), self.clock()
        data = self.store.read()
        s = data["sessions"].get(key)
        if not s or not self._session_ok(data, s, now):
            return None
        if now - s.get("seen", 0) >= TOUCH_EVERY:
            with self.store.change() as data:
                s = data["sessions"].get(key)
                if not s or not self._session_ok(data, s, now):
                    return None
                s["seen"] = now
        user = data["users"][s["user"]]
        return {"user": s["user"], "role": user["role"], "email": user.get("email"),
                "email_verified": bool(user.get("email_verified")), "key": key}

    @staticmethod
    def cookie(token: str, max_age: int = ABSOLUTE) -> str:
        return f"{COOKIE}={token}; HttpOnly; Secure; SameSite=Strict; Path=/; Max-Age={max_age}"

    @staticmethod
    def cookie_gone() -> str:
        return f"{COOKIE}=; HttpOnly; Secure; SameSite=Strict; Path=/; Max-Age=0"

    def login(self, name, password, ip: str) -> tuple[dict, str]:
        """({user, role}, the new session's token), or AuthError with the same sentence for every wrong guess."""
        if not isinstance(name, str) or not isinstance(password, str) or len(password) > 1024 or len(name) > 64:
            raise AuthError(400, "Type your name and password.")
        name, now = name.strip().lower(), self.clock()
        with self._counters:
            fails = self._recent(self._ip_fails.get(ip, []), now, IP_WINDOW)
            if len(fails) >= IP_FAILS:
                raise AuthError(429, TOO_MANY)
        user = self._user(self.store.read(), name)
        stored = user.get("hash") if user else None
        # The slow check runs every time, a dummy one for an unknown name, so the time taken says nothing.
        good = check_password(password, stored) if stored else (check_password(password, self._dummy_hash()) and False)
        if user is not None:
            with self.store.change() as data:
                user = self._user(data, name)
                if user is None:
                    good = False
                elif user.get("locked_until", 0) > now:
                    raise AuthError(429, LOCKED)
                elif good and not user.get("disabled"):
                    user["failed"], user["locked_until"] = 0, 0
                    token = secrets.token_urlsafe(32)
                    self._prune(data, now)
                    data["sessions"][token_hash(token)] = {"user": name, "created": now, "seen": now}
                    return {"user": name, "role": user["role"]}, token
                else:
                    user["failed"] = user.get("failed", 0) + 1
                    if user["failed"] >= LOCK_AFTER:
                        user["failed"], user["locked_until"] = 0, now + LOCK_FOR
        else:
            with self._counters:
                count, until = self._name_fails.get(name, [0, 0])
                if until > now:
                    raise AuthError(429, LOCKED)
                count += 1
                self._remember(self._name_fails, name, [0, now + LOCK_FOR] if count >= LOCK_AFTER else [count, 0])
        with self._counters:
            self._remember(self._ip_fails, ip, [*self._recent(self._ip_fails.get(ip, []), now, IP_WINDOW), now])
        raise AuthError(401, WRONG)

    def logout(self, token: str | None) -> None:
        if token:
            with self.store.change() as data:
                data["sessions"].pop(token_hash(token), None)

    # ------------------------------------------------ passwords and email

    def forgot(self, who, ip: str) -> str:
        """The same sentence whatever `who` is; an email only for an enabled login with a confirmed address."""
        if not self.mail_ready():
            return NO_MAIL
        if not isinstance(who, str) or not who.strip() or len(who) > 254:
            return FORGOT_SENT
        who, now = who.strip().lower(), self.clock()
        with self._counters:
            asks = self._recent(self._forgot_ip.get(ip, []), now, FORGOT_WINDOW)
            if len(asks) >= FORGOT_PER_IP:
                return FORGOT_SENT
            self._remember(self._forgot_ip, ip, [*asks, now])
        data = self.store.read()
        name = who if who in data["users"] else next(
            (n for n, u in data["users"].items() if (u.get("email") or "").lower() == who), None)
        user = self._user(data, name)
        if not user or user.get("disabled") or not user.get("email") or not user.get("email_verified"):
            return FORGOT_SENT
        with self._counters:
            asks = self._recent(self._forgot_user.get(name, []), now, FORGOT_WINDOW)
            if len(asks) >= FORGOT_PER_USER:
                return FORGOT_SENT
            self._remember(self._forgot_user, name, [*asks, now])
        # After the answer, link and all: an account that gets an email answers as fast as one that doesn't.
        self.later(lambda: self._send_reset(name, user["email"]))
        return FORGOT_SENT

    def _send_reset(self, name: str, email: str) -> None:
        with self.store.change() as data:
            token = self._new_token(data, "reset", name, RESET_EMAIL_LIFE)
        self.mailer().send(email, "Monkey SMP staff: reset your password",
                           f"Someone asked to reset the password of the Monkey SMP staff login {name}.\n\n"
                           f"To choose a new one, open this link within 30 minutes. It works once:\n\n"
                           f"{self.link('reset', token)}\n\n"
                           "If that wasn't you, ignore this email: nothing changes.\n")

    def reset(self, token, password) -> dict:
        """Sets a new password from a link; every session of that login ends."""
        with self.store.change() as data:
            found = self._take_token(data, token, ("reset", "setup"))
            name = found["user"]
            user = data["users"][name]
            problem = password_problem(password, name)
            if problem:
                data["tokens"][token_hash(token)] = found       # the link still works for a better password
                raise AuthError(400, problem)
            had_password = bool(user.get("hash"))
            user["hash"], user["changed"] = hash_password(password), self.clock()
            user["failed"], user["locked_until"] = 0, 0
            if found.get("email") and found["email"] == user.get("email"):
                user["email_verified"] = True                  # the link went to that address and came back
            self._end_sessions(data, name)
            notify = user.get("email") if user.get("email_verified") and had_password else None
        if notify:
            self._send(notify, "Monkey SMP staff: your password was changed",
                       f"The password of the Monkey SMP staff login {name} was just changed with a reset link, and "
                       "every session was logged out.\n\nIf that wasn't you, tell the owner at once.\n")
        return {"user": name}

    def verify(self, token) -> dict:
        with self.store.change() as data:
            found = self._take_token(data, token, ("verify",))
            user = data["users"][found["user"]]
            if found.get("email") != user.get("email"):
                raise AuthError(400, BAD_LINK)
            user["email_verified"], user["changed"] = True, self.clock()
        return {"user": found["user"], "email": found["email"]}

    def _check_current(self, data: dict, name: str, current) -> dict:
        user = data["users"].get(name)
        if not user or not isinstance(current, str) or not user.get("hash") \
                or not check_password(current[:1024], user["hash"]):
            raise AuthError(403, "Your current password isn't right.")
        return user

    def change_password(self, me: dict, current, password) -> dict:
        name = me["user"]
        problem = password_problem(password, name)
        if problem:
            raise AuthError(400, problem)
        with self.store.change() as data:
            user = self._check_current(data, name, current)
            user["hash"], user["changed"] = hash_password(password), self.clock()
            ended = self._end_sessions(data, name, keep=me["key"])
            notify = user.get("email") if user.get("email_verified") else None
        if notify:
            self._send(notify, "Monkey SMP staff: your password was changed",
                       f"The password of the Monkey SMP staff login {name} was just changed on the staff page. "
                       "Other sessions were logged out.\n\nIf that wasn't you, reset it and tell the owner.\n")
        return {"ended": ended}

    def _verify_mail(self, data: dict, name: str, email: str) -> bool:
        """Sends a link to confirm `email`; whether mail is set up to send it."""
        if not self.mail_ready():
            return False
        token = self._new_token(data, "verify", name, LINK_LIFE, email)
        self._send(email, "Monkey SMP staff: confirm your email",
                   f"Confirm that this is the email of the Monkey SMP staff login {name}: open this link within 24 "
                   f"hours. It works once:\n\n{self.link('verify', token)}\n\n"
                   "Until then, password reset emails don't go here. Not you? Ignore this email.\n")
        return True

    def change_email(self, me: dict, current, email) -> dict:
        name = me["user"]
        email = checked_email(email)
        with self.store.change() as data:
            user = self._check_current(data, name, current)
            if any((u.get("email") or "").lower() == email.lower() for n, u in data["users"].items() if n != name):
                raise AuthError(409, "Another login has that email.")
            old = user.get("email") if user.get("email_verified") else None
            user["email"], user["email_verified"], user["changed"] = email, False, self.clock()
            for k, t in list(data["tokens"].items()):
                if t.get("user") == name and t.get("kind") in ("reset", "verify"):
                    del data["tokens"][k]
            sent = self._verify_mail(data, name, email)
        if old and old.lower() != email.lower():
            self._send(old, "Monkey SMP staff: your email was changed",
                       f"The email of the Monkey SMP staff login {name} was just changed to {masked_email(email)}. "
                       "Reset emails no longer come here.\n\nIf that wasn't you, tell the owner at once.\n")
        return {"email": email, "sent": sent}

    # ------------------------------------------------ the owner's tools

    @staticmethod
    def _owners_left(data: dict, without: str) -> int:
        return sum(1 for n, u in data["users"].items()
                   if n != without and u.get("role") == "owner" and not u.get("disabled"))

    def _target(self, data: dict, name) -> dict:
        user = self._user(data, name)
        if user is None:
            raise AuthError(404, "There is no login with that name.")
        return user

    def _keep_an_owner(self, data: dict, name: str) -> None:
        user = data["users"][name]
        if user.get("role") == "owner" and not user.get("disabled") and not self._owners_left(data, name):
            raise AuthError(409, f"{name} is the last owner: make another owner first.")

    def list_users(self) -> dict:
        data, now = self.store.read(), self.clock()
        rows = []
        for name, u in sorted(data["users"].items()):
            rows.append({"name": name, "role": u.get("role"), "email": u.get("email"),
                         "email_verified": bool(u.get("email_verified")), "disabled": bool(u.get("disabled")),
                         "password_set": bool(u.get("hash")), "locked": u.get("locked_until", 0) > now,
                         "created": iso(u.get("created")), "changed": iso(u.get("changed")),
                         "sessions": sum(1 for s in data["sessions"].values()
                                         if s.get("user") == name and self._session_ok(data, s, now))})
        return {"users": rows, "mail": self.mail_ready()}

    def add_user(self, by: str, name, role, email=None, send: bool = True) -> dict:
        """A new login with no password yet. With mail set up and an email, the set-password link goes there (and,
        used, confirms the address); otherwise the link comes back, for the owner to hand over."""
        if not isinstance(name, str) or not NAME.fullmatch(name):
            raise AuthError(400, "A name is 2 to 32 small letters, digits or _.")
        if role not in ROLES:
            raise AuthError(400, "The role must be moderator, admin or owner.")
        email = checked_email(email) if email else None
        emailed = False
        with self.store.change() as data:
            if name in data["users"]:
                raise AuthError(409, "There is already a login with that name.")
            if email and any((u.get("email") or "").lower() == email.lower() for u in data["users"].values()):
                raise AuthError(409, "Another login has that email.")
            now = self.clock()
            data["users"][name] = {"role": role, "email": email, "email_verified": False, "hash": None,
                                   "disabled": False, "failed": 0, "locked_until": 0, "created": now, "changed": now,
                                   "added_by": by}
            if send and email and self.mail_ready():
                token = self._new_token(data, "setup", name, LINK_LIFE, email)
                emailed = True
            else:
                token = self._new_token(data, "setup", name, LINK_LIFE)
        if emailed:
            self._send(email, "Monkey SMP staff: your login",
                       f"You have a Monkey SMP staff login: {name} ({role}). Choose your password with this link "
                       f"within 24 hours. It works once, and it confirms this email too:\n\n"
                       f"{self.link('reset', token)}\n")
            return {"name": name, "emailed": True}
        return {"name": name, "emailed": False, "link": self.link("reset", token)}

    def handover_link(self, by: str, name) -> dict:
        """A one-time link to set a new password (24 hours), for the owner to pass on privately."""
        with self.store.change() as data:
            self._target(data, name)
            token = self._new_token(data, "reset", name, LINK_LIFE)
        return {"name": name, "link": self.link("reset", token)}

    def send_verify(self, by: str, name) -> dict:
        with self.store.change() as data:
            user = self._target(data, name)
            if not user.get("email"):
                raise AuthError(400, f"{name} has no email.")
            if not self.mail_ready():
                raise AuthError(503, "Email isn't set up: see docs/LIVE.md, \"The staff page\".")
            self._verify_mail(data, name, user["email"])
        return {"name": name, "sent": True}

    def set_role(self, by: str, name, role) -> dict:
        if role not in ROLES:
            raise AuthError(400, "The role must be moderator, admin or owner.")
        with self.store.change() as data:
            user = self._target(data, name)
            if role != "owner":
                self._keep_an_owner(data, name)
            user["role"], user["changed"] = role, self.clock()
        return {"name": name, "role": role}

    def set_disabled(self, by: str, name, disabled) -> dict:
        if not isinstance(disabled, bool):
            raise AuthError(400, "disabled must be true or false.")
        with self.store.change() as data:
            user = self._target(data, name)
            if disabled:
                self._keep_an_owner(data, name)
                self._end_sessions(data, name)
            user["disabled"], user["changed"] = disabled, self.clock()
        return {"name": name, "disabled": disabled}

    def delete_user(self, by: str, name) -> dict:
        with self.store.change() as data:
            self._target(data, name)
            self._keep_an_owner(data, name)
            del data["users"][name]
            self._end_sessions(data, name)
            for k, t in list(data["tokens"].items()):
                if t.get("user") == name:
                    del data["tokens"][k]
        return {"name": name, "deleted": True}

    def end_sessions(self, by: str, name) -> dict:
        with self.store.change() as data:
            self._target(data, name)
            ended = self._end_sessions(data, name)
        return {"name": name, "ended": ended}

    # ------------------------------------------------ HTTP

    def http(self, method: str, path: str, body: dict, headers, ip: str) -> tuple[int, dict, list[tuple[str, str]]]:
        """(status, JSON answer, extra headers) for one /auth/ request. `headers` has .get(name)."""
        try:
            return self._http(method, path, body, headers, ip)
        except AuthError as e:
            return e.code, {"ok": False, "error": e.message}, []

    def _http(self, method, path, body, headers, ip):
        token = self.session_token(headers.get("Cookie"))
        if (method, path) == ("GET", "/auth/check"):
            me = self.session(token)
            if me:
                return 200, {"ok": True}, [("X-Staff-User", me["user"]), ("X-Staff-Role", me["role"])]
            wanted = urlsplit(headers.get("X-Forwarded-Uri") or "/").path
            if (headers.get("X-Forwarded-Method") or "GET") == "GET" and not wanted.startswith("/api/") \
                    and wanted != "/staff.json":
                return 302, {"ok": False, "error": "Log in first."}, [("Location", "/login")]
            return 401, {"ok": False, "error": "Your login has run out: log in again."}, []
        if (method, path) == ("GET", "/auth/session"):
            me = self.session(token)
            if not me:
                return 401, {"ok": False, "error": "Not logged in."}, []
            return 200, {"ok": True, "user": me["user"], "role": me["role"], "email": me["email"],
                         "email_verified": me["email_verified"], "mail": self.mail_ready()}, []
        if method != "POST":
            raise AuthError(404, "There is no such request.")
        if path == "/auth/login":
            who, new = self.login(body.get("name"), body.get("password"), ip)
            if token:
                self.logout(token)
            return 200, {"ok": True, **who}, [("Set-Cookie", self.cookie(new))]
        if path == "/auth/logout":
            self.logout(token)
            return 200, {"ok": True}, [("Set-Cookie", self.cookie_gone())]
        if path == "/auth/forgot":
            return 200, {"ok": True, "message": self.forgot(body.get("who"), ip)}, []
        if path == "/auth/reset":
            return 200, {"ok": True, **self.reset(body.get("token"), body.get("password"))}, []
        if path == "/auth/verify":
            return 200, {"ok": True, **self.verify(body.get("token"))}, []
        if path in ("/auth/password", "/auth/email"):
            me = self.session(token)
            if not me:
                raise AuthError(401, "Your login has run out: log in again.")
            if path == "/auth/password":
                return 200, {"ok": True, **self.change_password(me, body.get("current"), body.get("password"))}, []
            return 200, {"ok": True, **self.change_email(me, body.get("current"), body.get("email"))}, []
        raise AuthError(404, "There is no such request.")


def from_settings(staff_dir: Path, env: dict | None = None) -> Auth:
    env = os.environ if env is None else env
    return Auth(Path(staff_dir) / "auth", Path(env.get("MONKEY_STAFF_MAIL_ENV") or MAIL_SETTINGS))


# ---------------------------------------------------------------- the owner's command line


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    sub = ap.add_subparsers(dest="command", required=True)
    sub.add_parser("list")
    sub.add_parser("ready", help="exit 0 when an owner can log in (monkey-staff.sh --use-new-login asks)")
    p = sub.add_parser("add-user")
    p.add_argument("name")
    p.add_argument("role", choices=ROLES)
    p.add_argument("--email")
    for name in ("reset-link", "send-verify", "end-sessions"):
        sub.add_parser(name).add_argument("name")
    p = sub.add_parser("set-role")
    p.add_argument("name")
    p.add_argument("role", choices=ROLES)
    sub.add_parser("mail-test").add_argument("address")
    args = ap.parse_args(argv)

    if hasattr(os, "geteuid") and os.geteuid() == 0:
        print("run it as monkey (sudo -u monkey ...): the login store is monkey's", file=sys.stderr)
        return 1
    from staff_panel import settings_file

    file = settings_file(Path(os.environ.get("MONKEY_DEPLOY_ENV") or "/etc/monkey-deploy.env"))
    staff_dir = os.environ.get("STAFF_DIR") or file.get("STAFF_DIR") or "/srv/monkey/staff"
    # The CLI waits for its own emails: there is no answer to send first.
    auth = from_settings(Path(staff_dir))
    auth.later = lambda fn: fn()
    try:
        if args.command == "list":
            rows = auth.list_users()
            print(f"mail: {'set up' if rows['mail'] else 'not set up'}")
            for u in rows["users"]:
                flags = [f for f, on in (("disabled", u["disabled"]), ("locked", u["locked"]),
                                         ("no password yet", not u["password_set"])) if on]
                email = (u["email"] or "no email") + ("" if u["email_verified"] or not u["email"] else " (unconfirmed)")
                print(f"  {u['name']:<20} {u['role']:<10} {email}; sessions: {u['sessions']}"
                      + (f"; {', '.join(flags)}" if flags else ""))
            return 0
        if args.command == "ready":
            users = auth.list_users()["users"]
            owners = [u["name"] for u in users if u["role"] == "owner" and u["password_set"] and not u["disabled"]]
            print(f"{len(users)} login(s), {len(owners)} owner(s) with a password; mail "
                  f"{'set up' if auth.mail_ready() else 'not set up'}")
            return 0 if owners else 1
        if args.command == "add-user":
            done = auth.add_user("cli", args.name, args.role, args.email, send=False)
            if args.email:
                sent = auth.mail_ready() and auth.send_verify("cli", args.name)["sent"]
                print(f"A link to confirm {args.email} was emailed." if sent else
                      "Email isn't set up, so the address stays unconfirmed and gets no reset emails. Once mail works: "
                      f"python3 tools/staff_auth.py send-verify {args.name}")
            print(f"\nLogin {args.name} ({args.role}). Its set-password link, good once for 24 hours, shown only this "
                  f"once:\n\n  {done['link']}\n\nPass it on privately.")
            return 0
        if args.command == "reset-link":
            done = auth.handover_link("cli", args.name)
            print(f"\nA new-password link for {args.name}, good once for 24 hours, shown only this once:\n\n"
                  f"  {done['link']}\n\nPass it on privately.")
            return 0
        if args.command == "send-verify":
            auth.send_verify("cli", args.name)
            print(f"A link to confirm the email of {args.name} was sent.")
            return 0
        if args.command == "set-role":
            auth.set_role("cli", args.name, args.role)
            print(f"{args.name} is now {args.role}.")
            return 0
        if args.command == "end-sessions":
            print(f"{args.name}: {auth.end_sessions('cli', args.name)['ended']} session(s) ended.")
            return 0
        mailer = auth.mailer()
        if not mailer.backend:
            print(f"mail isn't set up: fill in {auth.mail_settings} (docs/LIVE.md, \"The staff page\")",
                  file=sys.stderr)
            return 1
        ok = mailer.send(checked_email(args.address), "Monkey SMP staff: test email",
                         "This is a test from the Monkey SMP staff page. Mail works.\n")
        if not ok:
            print("not sent: see the line above", file=sys.stderr)
            return 1
        print(f"sent by {mailer.backend}")
        return 0
    except AuthError as e:
        print(e.message, file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
