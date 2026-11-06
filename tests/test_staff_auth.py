import http.client
import json
import os
import re
import shutil
import subprocess
import threading
from pathlib import Path
from types import SimpleNamespace

import pytest
import staff_auth
import staff_panel
from test_staff_status import FAKES

from repo import REPO

DEPLOY = REPO.root / "deploy"
PAGE = DEPLOY / "staff"
GOOD = "correct horse battery"
OTHER = "another long password"


@pytest.fixture(autouse=True)
def quick_scrypt(monkeypatch):
    """A cheaper scrypt for the tests: the cost is in each hash, so checking still works the same way."""
    monkeypatch.setattr(staff_auth, "SCRYPT_N", 2 ** 8)


class Clock:
    def __init__(self):
        self.now = 1_800_000_000.0

    def __call__(self):
        return self.now


class FakeMailer:
    def __init__(self, backend="resend"):
        self.backend = backend
        self.sent: list[tuple[str, str, str]] = []

    def send(self, to, subject, text):
        self.sent.append((to, subject, text))
        return True


def token_in(text: str, page: str) -> str:
    return re.search(rf"/{page}#token=([A-Za-z0-9_-]+)", text)[1]


@pytest.fixture
def auth(tmp_path):
    clock, mail = Clock(), FakeMailer()
    box = SimpleNamespace(clock=clock, mail=mail, folder=tmp_path / "staff" / "auth")
    box.auth = staff_auth.Auth(box.folder, mail_settings=tmp_path / "no-mail", clock=clock, mailer=lambda: box.mail,
                               later=lambda fn: fn(), site_url="https://staff.example")

    def user(name, role="admin", email=None, verified=False, password=GOOD):
        link = box.auth.add_user("lorenzo", name, role, email, send=False)["link"]
        box.auth.reset(token_in(link, "reset"), password)
        if verified:
            with box.auth.store.change() as data:
                data["users"][name]["email_verified"] = True
        return name

    box.user = user
    return box


# ---------------------------------------------------------------- passwords and logins


def test_a_password_is_scrypt_with_its_own_salt_and_the_unit_can_afford_it(monkeypatch):
    monkeypatch.setattr(staff_auth, "SCRYPT_N", 2 ** 14)
    one, two = staff_auth.hash_password(GOOD), staff_auth.hash_password(GOOD)
    assert one != two and one.startswith("scrypt$16384$8$1$")
    assert staff_auth.check_password(GOOD, one) and not staff_auth.check_password(GOOD + "x", one)
    assert not staff_auth.check_password(GOOD, "garbage") and not staff_auth.check_password(GOOD, "bcrypt$1$2$3$4$5")
    # 128 * n * r bytes: 16 MB per check, well inside the unit's MemoryMax=512M.
    assert 128 * 2 ** 14 * 8 <= staff_auth.SCRYPT_MAXMEM < 512 * 1024 * 1024
    assert "compare_digest" in Path(staff_auth.__file__).read_text()


def test_login_works_and_wrong_or_unknown_get_the_same_sentence(auth):
    auth.user("diego")
    who, token = auth.auth.login("Diego ", GOOD, "203.0.113.1")
    assert who == {"user": "diego", "role": "admin"} and len(token) >= 40
    with pytest.raises(staff_auth.AuthError) as wrong:
        auth.auth.login("diego", "not it at all", "203.0.113.1")
    with pytest.raises(staff_auth.AuthError) as unknown:
        auth.auth.login("nobody", "not it at all", "203.0.113.1")
    same = (401, staff_auth.WRONG)
    assert (wrong.value.code, wrong.value.message) == (unknown.value.code, unknown.value.message) == same


def test_an_unknown_name_still_runs_a_full_password_check(auth, monkeypatch):
    auth.user("diego")
    seen = []
    real = staff_auth.check_password
    monkeypatch.setattr(staff_auth, "check_password", lambda p, h: seen.append(h) or real(p, h))
    for name in ("nobody", "diego"):
        with pytest.raises(staff_auth.AuthError):
            auth.auth.login(name, "not it at all", "203.0.113.1")
    assert len(seen) == 2 and all(h.startswith("scrypt$") for h in seen)
    assert seen[0] == auth.auth._dummy_hash() and seen[1] != seen[0]


def test_a_disabled_login_or_one_with_no_password_yet_cannot_log_in(auth):
    auth.user("diego")
    auth.user("lorenzo", "owner")
    auth.auth.set_disabled("lorenzo", "diego", True)
    auth.auth.add_user("lorenzo", "newbie", "moderator", send=False)
    for name in ("diego", "newbie"):
        with pytest.raises(staff_auth.AuthError) as e:
            auth.auth.login(name, GOOD, "203.0.113.1")
        assert e.value.message == staff_auth.WRONG


def test_five_wrong_passwords_lock_a_name_for_a_while_known_or_not(auth):
    auth.user("diego")
    for name in ("diego", "ghost"):
        for _ in range(staff_auth.LOCK_AFTER):
            with pytest.raises(staff_auth.AuthError) as e:
                auth.auth.login(name, "wrong wrong wrong", f"198.51.100.{len(name)}")
            assert e.value.code == 401
        with pytest.raises(staff_auth.AuthError) as e:
            auth.auth.login(name, GOOD, f"198.51.100.{len(name)}")
        assert (e.value.code, e.value.message) == (429, staff_auth.LOCKED)
    auth.clock.now += staff_auth.LOCK_FOR + 1
    assert auth.auth.login("diego", GOOD, "198.51.100.9")[0]["user"] == "diego"
    assert auth.auth.store.read()["users"]["diego"]["failed"] == 0


def test_one_address_gets_a_limited_number_of_wrong_guesses(auth):
    for i in range(staff_auth.IP_FAILS):
        with pytest.raises(staff_auth.AuthError):
            auth.auth.login(f"name{i}", "wrong wrong wrong", "192.0.2.7")
    with pytest.raises(staff_auth.AuthError) as e:
        auth.auth.login("someone", "wrong wrong wrong", "192.0.2.7")
    assert (e.value.code, e.value.message) == (429, staff_auth.TOO_MANY)
    with pytest.raises(staff_auth.AuthError) as e:                # another address is not held up
        auth.auth.login("someone", "wrong wrong wrong", "192.0.2.8")
    assert e.value.code == 401
    auth.clock.now += staff_auth.IP_WINDOW + 1
    with pytest.raises(staff_auth.AuthError) as e:
        auth.auth.login("someone", "wrong wrong wrong", "192.0.2.7")
    assert e.value.code == 401


# ---------------------------------------------------------------- sessions


def test_a_session_ends_after_12_idle_hours_or_7_days_and_at_logout(auth):
    auth.user("diego")
    _, token = auth.auth.login("diego", GOOD, "203.0.113.1")
    assert auth.auth.session(token)["user"] == "diego"
    auth.clock.now += staff_auth.IDLE - 60
    assert auth.auth.session(token)                     # used: the idle clock starts again
    auth.clock.now += staff_auth.IDLE - 60
    assert auth.auth.session(token)
    auth.clock.now += staff_auth.IDLE + 1
    assert auth.auth.session(token) is None

    _, token = auth.auth.login("diego", GOOD, "203.0.113.1")
    for _ in range(14):
        auth.clock.now += staff_auth.IDLE - 60
        assert auth.auth.session(token)
    auth.clock.now += 3600
    assert auth.auth.session(token) is None                               # 7 days in all, used or not

    _, token = auth.auth.login("diego", GOOD, "203.0.113.1")
    auth.auth.logout(token)
    assert auth.auth.session(token) is None


def test_the_store_keeps_only_hashes_of_sessions_and_passwords(auth):
    auth.user("diego")
    _, token = auth.auth.login("diego", GOOD, "203.0.113.1")
    text = (auth.folder / "auth.json").read_text()
    assert token not in text and GOOD not in text and staff_auth.token_hash(token) in text
    if os.name == "posix":
        assert (auth.folder / "auth.json").stat().st_mode & 0o777 == 0o600
        assert auth.folder.stat().st_mode & 0o777 == 0o700
    assert [p.name for p in auth.folder.iterdir() if p.name.startswith(".auth-")] == []


def test_the_cookie_is_httponly_secure_and_strict():
    cookie = staff_auth.Auth.cookie("t" * 43)
    for part in ("monkey_staff=", "HttpOnly", "Secure", "SameSite=Strict", "Path=/", "Max-Age=604800"):
        assert part in cookie
    assert "Max-Age=0" in staff_auth.Auth.cookie_gone()


def test_another_process_writing_the_store_is_seen(auth):
    auth.user("diego")
    other = staff_auth.Auth(auth.folder, mail_settings=Path("nothing"), clock=auth.clock)
    other.add_user("cli", "newbie", "moderator", send=False)
    assert "newbie" in auth.auth.store.read()["users"]


# ---------------------------------------------------------------- reset and email


def test_forgot_answers_the_same_and_mails_only_a_confirmed_address(auth):
    auth.user("diego", email="diego@example.com")                     # not confirmed
    auth.user("lorenzo", "owner", email="lorenzo@example.com", verified=True)
    answers = {auth.auth.forgot(who, "203.0.113.1") for who in ("nobody", "diego", "diego@example.com", "", None)}
    assert answers == {staff_auth.FORGOT_SENT} and auth.mail.sent == []
    assert auth.auth.forgot("LORENZO@example.com", "203.0.113.2") == staff_auth.FORGOT_SENT
    assert [m[0] for m in auth.mail.sent] == ["lorenzo@example.com"]
    assert "https://staff.example/reset#token=" in auth.mail.sent[0][2]


def test_with_no_mail_forgot_says_to_ask_the_owner(auth):
    auth.mail.backend = None
    auth.user("lorenzo", "owner", email="lorenzo@example.com", verified=True)
    assert auth.auth.forgot("lorenzo", "203.0.113.1") == staff_auth.NO_MAIL
    assert auth.mail.sent == []


def test_a_reset_link_works_once_for_30_minutes_and_ends_every_session(auth):
    auth.user("lorenzo", "owner", email="lorenzo@example.com", verified=True)
    _, session = auth.auth.login("lorenzo", GOOD, "203.0.113.1")
    auth.auth.forgot("lorenzo", "203.0.113.1")
    token = token_in(auth.mail.sent[-1][2], "reset")
    with pytest.raises(staff_auth.AuthError) as e:
        auth.auth.reset(token, "lorenzo-is-me-12")                   # the name in it
    assert e.value.code == 400
    with pytest.raises(staff_auth.AuthError):
        auth.auth.reset(token, "short")
    assert auth.auth.reset(token, OTHER) == {"user": "lorenzo"}      # a refused password left the link working
    assert auth.auth.session(session) is None
    assert auth.auth.login("lorenzo", OTHER, "203.0.113.1")
    with pytest.raises(staff_auth.AuthError) as e:
        auth.auth.reset(token, GOOD)
    assert e.value.message == staff_auth.BAD_LINK
    assert "password was changed" in auth.mail.sent[-1][1]

    auth.clock.now += 3600                                           # the per-login limit on asks starts again
    auth.auth.forgot("lorenzo", "203.0.113.3")
    late = token_in(auth.mail.sent[-1][2], "reset")
    auth.clock.now += staff_auth.RESET_EMAIL_LIFE + 1
    with pytest.raises(staff_auth.AuthError) as e:
        auth.auth.reset(late, GOOD)
    assert e.value.message == staff_auth.BAD_LINK
    with pytest.raises(staff_auth.AuthError):
        auth.auth.reset("x" * 43, GOOD)


def test_forgot_asks_are_limited_per_login(auth):
    auth.user("lorenzo", "owner", email="lorenzo@example.com", verified=True)
    for i in range(6):
        assert auth.auth.forgot("lorenzo", f"203.0.113.{i}") == staff_auth.FORGOT_SENT
    assert len(auth.mail.sent) == staff_auth.FORGOT_PER_USER


def test_changing_email_needs_the_password_sends_a_check_and_tells_the_old_address(auth):
    auth.user("lorenzo", "owner", email="old@example.com", verified=True)
    _, session = auth.auth.login("lorenzo", GOOD, "203.0.113.1")
    me = auth.auth.session(session)
    with pytest.raises(staff_auth.AuthError) as e:
        auth.auth.change_email(me, "wrong wrong wrong", "new@example.com")
    assert e.value.code == 403
    with pytest.raises(staff_auth.AuthError):
        auth.auth.change_email(me, GOOD, "not an email")
    assert auth.auth.change_email(me, GOOD, "new@example.com") == {"email": "new@example.com", "sent": True}
    (to_new, *_), (to_old, _, old_text) = auth.mail.sent
    assert to_new == "new@example.com" and to_old == "old@example.com" and "n***@example.com" in old_text
    user = auth.auth.store.read()["users"]["lorenzo"]
    assert user["email"] == "new@example.com" and user["email_verified"] is False
    # Until it is confirmed, no reset email goes to it.
    auth.auth.forgot("lorenzo", "203.0.113.1")
    assert len(auth.mail.sent) == 2
    token = token_in(auth.mail.sent[0][2], "verify")
    assert auth.auth.verify(token) == {"user": "lorenzo", "email": "new@example.com"}
    with pytest.raises(staff_auth.AuthError):
        auth.auth.verify(token)                                      # once only
    assert auth.auth.store.read()["users"]["lorenzo"]["email_verified"] is True
    auth.clock.now += 3600
    auth.auth.forgot("new@example.com", "203.0.113.9")
    assert auth.mail.sent[-1][0] == "new@example.com"


def test_a_verify_link_runs_out_after_a_day(auth):
    auth.user("diego", email="d@example.com")
    auth.auth.send_verify("lorenzo", "diego")
    token = token_in(auth.mail.sent[-1][2], "verify")
    auth.clock.now += staff_auth.LINK_LIFE + 1
    with pytest.raises(staff_auth.AuthError):
        auth.auth.verify(token)


def test_changing_the_password_ends_the_other_sessions_only(auth):
    auth.user("diego", email="d@example.com", verified=True)
    _, here = auth.auth.login("diego", GOOD, "203.0.113.1")
    _, there = auth.auth.login("diego", GOOD, "203.0.113.2")
    me = auth.auth.session(here)
    with pytest.raises(staff_auth.AuthError):
        auth.auth.change_password(me, "wrong wrong wrong", OTHER)
    with pytest.raises(staff_auth.AuthError):
        auth.auth.change_password(me, GOOD, "diego-diego-diego")
    assert auth.auth.change_password(me, GOOD, OTHER) == {"ended": 1}
    assert auth.auth.session(here) and auth.auth.session(there) is None
    assert auth.mail.sent[-1][0] == "d@example.com" and "password was changed" in auth.mail.sent[-1][1]


def test_an_owner_added_login_with_mail_gets_a_link_that_also_confirms_the_email(auth):
    done = auth.auth.add_user("lorenzo", "diego", "admin", "diego@example.com")
    assert done == {"name": "diego", "emailed": True} and auth.mail.sent[-1][0] == "diego@example.com"
    auth.auth.reset(token_in(auth.mail.sent[-1][2], "reset"), GOOD)
    assert auth.auth.store.read()["users"]["diego"]["email_verified"] is True


def test_with_no_mail_the_owner_gets_the_link_and_the_email_stays_unconfirmed(auth):
    auth.mail.backend = None
    done = auth.auth.add_user("lorenzo", "diego", "admin", "diego@example.com")
    assert done["emailed"] is False and "/reset#token=" in done["link"] and auth.mail.sent == []
    auth.auth.reset(token_in(done["link"], "reset"), GOOD)
    assert auth.auth.store.read()["users"]["diego"]["email_verified"] is False


# ---------------------------------------------------------------- the owner's tools


def test_the_last_owner_stays(auth):
    auth.user("lorenzo", "owner")
    auth.user("diego")
    for change in (lambda: auth.auth.set_role("x", "lorenzo", "admin"),
                   lambda: auth.auth.set_disabled("x", "lorenzo", True),
                   lambda: auth.auth.delete_user("x", "lorenzo")):
        with pytest.raises(staff_auth.AuthError) as e:
            change()
        assert e.value.code == 409 and "last owner" in e.value.message
    auth.auth.set_role("lorenzo", "diego", "owner")
    assert auth.auth.set_role("diego", "lorenzo", "admin")["role"] == "admin"
    with pytest.raises(staff_auth.AuthError):
        auth.auth.delete_user("x", "diego")


def test_names_roles_and_emails_are_checked(auth):
    for name, role, email in (("Diego", "admin", None), ("d", "admin", None), ("a" * 33, "admin", None),
                              ("diego", "root", None), ("diego", "admin", "x@y"), ("diego", "admin", "a b@c.de")):
        with pytest.raises(staff_auth.AuthError):
            auth.auth.add_user("lorenzo", name, role, email)
    auth.auth.add_user("lorenzo", "diego", "admin", "d@example.com", send=False)
    with pytest.raises(staff_auth.AuthError) as e:
        auth.auth.add_user("lorenzo", "diego", "admin")
    assert e.value.code == 409
    with pytest.raises(staff_auth.AuthError):
        auth.auth.add_user("lorenzo", "other", "admin", "D@example.com")       # one address, one login


def test_disabling_or_deleting_ends_the_sessions(auth):
    auth.user("lorenzo", "owner")
    auth.user("diego")
    _, token = auth.auth.login("diego", GOOD, "203.0.113.1")
    auth.auth.set_disabled("lorenzo", "diego", True)
    assert auth.auth.session(token) is None
    auth.auth.set_disabled("lorenzo", "diego", False)
    _, token = auth.auth.login("diego", GOOD, "203.0.113.1")
    assert auth.auth.end_sessions("lorenzo", "diego")["ended"] == 1 and auth.auth.session(token) is None
    auth.auth.delete_user("lorenzo", "diego")
    assert "diego" not in auth.auth.list_users()["users"]


# ---------------------------------------------------------------- two-step login


def code_at(key: str, now: float, steps: int = 0) -> str:
    return staff_auth.hotp(staff_auth.totp_key_bytes(key.replace(" ", "")), int(now // staff_auth.TOTP_STEP) + steps)


def two_step_on(auth, name):
    """Turns two-step login on for `name`, logged in once: (key, recovery codes, that session's token)."""
    _, token = auth.auth.login(name, GOOD, "203.0.113.1")
    me = auth.auth.session(token)
    key = auth.auth.two_step_start(me)["key"].replace(" ", "")
    codes = auth.auth.two_step_confirm(me, GOOD, code_at(key, auth.clock.now))["recovery"]
    auth.clock.now += staff_auth.TOTP_STEP           # the code just used can't log in again
    return key, codes, token


def test_totp_matches_rfc_6238_appendix_b():
    seed = b"12345678901234567890"                   # the SHA-1 seed
    for when, want in ((59, "94287082"), (1111111109, "07081804"), (1111111111, "14050471"),
                       (1234567890, "89005924"), (2000000000, "69279037"), (20000000000, "65353130")):
        assert staff_auth.hotp(seed, when // 30, 8) == want
    key = staff_auth.base64.b32encode(seed).decode()
    assert staff_auth.totp_step(key, "287082", 59, 0) == 1 and staff_auth.totp_step(key, "287082", 59, 1) == -1
    # One step either side is accepted, two isn't.
    assert staff_auth.totp_step(key, "287082", 89, 0) == 1 and staff_auth.totp_step(key, "287082", 119, 0) is None
    assert len(staff_auth.new_totp_key()) == 32


def test_turning_two_step_on_needs_the_password_and_a_code_and_ends_other_sessions(auth):
    auth.user("diego")
    _, other = auth.auth.login("diego", GOOD, "203.0.113.1")
    _, token = auth.auth.login("diego", GOOD, "203.0.113.1")
    me = auth.auth.session(token)
    started = auth.auth.two_step_start(me)
    key = started["key"].replace(" ", "")
    assert re.fullmatch(r"([A-Z2-7]{4} ){7}[A-Z2-7]{4}", started["key"])
    assert started["link"] == (f"otpauth://totp/Monkey%20SMP%20staff%3Adiego?secret={key}"
                               "&issuer=Monkey%20SMP%20staff")
    # Not on until confirmed: the password alone still logs in.
    assert auth.auth.login("diego", GOOD, "203.0.113.1")[1]
    for current, code, message in ((OTHER, code_at(key, auth.clock.now), "Your current password isn't right."),
                                   (GOOD, "000000" if code_at(key, auth.clock.now) != "000000" else "111111",
                                    staff_auth.WRONG_CODE),
                                   (GOOD, "abc", "Type the 6-digit code your app shows for this key.")):
        with pytest.raises(staff_auth.AuthError) as e:
            auth.auth.two_step_confirm(me, current, code)
        assert e.value.message == message
    done = auth.auth.two_step_confirm(me, GOOD, code_at(key, auth.clock.now))
    assert done["two_step"] is True and done["ended"] == 2 and len(set(done["recovery"])) == 8
    assert all(re.fullmatch(r"[a-z2-9]{5}-[a-z2-9]{5}", c) for c in done["recovery"])
    assert auth.auth.session(other) is None and auth.auth.session(token)["two_step"] is True
    assert auth.auth.session(token)["recovery_left"] == 8
    stored = json.dumps(auth.auth.store.read())
    assert not any(c in stored for c in done["recovery"]) and "totp_pending" not in stored
    with pytest.raises(staff_auth.AuthError) as e:
        auth.auth.two_step_start(me)
    assert e.value.code == 409


def test_a_pending_key_runs_out(auth):
    auth.user("diego")
    _, token = auth.auth.login("diego", GOOD, "203.0.113.1")
    me = auth.auth.session(token)
    key = auth.auth.two_step_start(me)["key"].replace(" ", "")
    auth.clock.now += staff_auth.PENDING_LIFE + 1
    with pytest.raises(staff_auth.AuthError) as e:
        auth.auth.two_step_confirm(auth.auth.session(token), GOOD, code_at(key, auth.clock.now))
    assert e.value.message == "That key has run out: start again."


def test_with_two_step_on_the_password_gives_a_challenge_and_the_code_a_session(auth):
    auth.user("diego")
    key, _, _ = two_step_on(auth, "diego")
    # A wrong password says nothing of two-step login.
    with pytest.raises(staff_auth.AuthError) as e:
        auth.auth.login("diego", OTHER, "203.0.113.1")
    assert e.value.message == staff_auth.WRONG
    sessions = len(auth.auth.store.read()["sessions"])
    who, token = auth.auth.login("diego", GOOD, "203.0.113.1")
    assert token is None and who["two_step"] is True and set(who) == {"two_step", "challenge"}
    assert len(auth.auth.store.read()["sessions"]) == sessions
    assert token_hash_in(auth, who["challenge"]) and who["challenge"] not in json.dumps(auth.auth.store.read())
    who2, session = auth.auth.login_code(who["challenge"], code_at(key, auth.clock.now), "203.0.113.1")
    assert who2 == {"user": "diego", "role": "admin", "recovery_left": 8} and auth.auth.session(session)
    # The challenge works once.
    with pytest.raises(staff_auth.AuthError) as e:
        auth.auth.login_code(who["challenge"], code_at(key, auth.clock.now, 1), "203.0.113.1")
    assert (e.value.code, e.value.message) == (400, staff_auth.CHALLENGE_GONE)
    # And for 5 minutes.
    auth.clock.now += staff_auth.TOTP_STEP
    challenge = auth.auth.login("diego", GOOD, "203.0.113.1")[0]["challenge"]
    auth.clock.now += staff_auth.CHALLENGE_LIFE + 1
    with pytest.raises(staff_auth.AuthError) as e:
        auth.auth.login_code(challenge, code_at(key, auth.clock.now), "203.0.113.1")
    assert e.value.message == staff_auth.CHALLENGE_GONE
    # A reset link's token is no challenge.
    link = auth.auth.handover_link("lorenzo", "diego")["link"]
    with pytest.raises(staff_auth.AuthError) as e:
        auth.auth.login_code(token_in(link, "reset"), code_at(key, auth.clock.now), "203.0.113.1")
    assert e.value.message == staff_auth.CHALLENGE_GONE


def token_hash_in(auth, token) -> bool:
    return staff_auth.token_hash(token) in auth.auth.store.read()["tokens"]


def test_a_code_works_once_and_wrong_codes_say_so(auth):
    auth.user("diego")
    key, _, _ = two_step_on(auth, "diego")
    code = code_at(key, auth.clock.now)
    challenge = auth.auth.login("diego", GOOD, "203.0.113.1")[0]["challenge"]
    auth.auth.login_code(challenge, code, "203.0.113.1")
    challenge = auth.auth.login("diego", GOOD, "203.0.113.1")[0]["challenge"]
    wrong = "000000" if code != "000000" else "111111"
    for typed, status, message in ((code, 401, staff_auth.USED_CODE), (wrong, 401, staff_auth.WRONG_CODE),
                                   ("", 400, staff_auth.NO_CODE), ("not-a-code", 401, staff_auth.WRONG_CODE)):
        with pytest.raises(staff_auth.AuthError) as e:
            auth.auth.login_code(challenge, typed, "203.0.113.1")
        assert (e.value.code, e.value.message) == (status, message)
    # An earlier step than the last one used is refused too; the next step works on the same challenge.
    with pytest.raises(staff_auth.AuthError) as e:
        auth.auth.login_code(challenge, code_at(key, auth.clock.now, -1), "203.0.113.1")
    assert e.value.message == staff_auth.USED_CODE
    assert auth.auth.login_code(challenge, code_at(key, auth.clock.now, 1), "203.0.113.1")[1]


def test_a_recovery_code_logs_in_once(auth):
    auth.user("diego")
    _, codes, _ = two_step_on(auth, "diego")
    challenge = auth.auth.login("diego", GOOD, "203.0.113.1")[0]["challenge"]
    who, _ = auth.auth.login_code(challenge, " " + codes[0].upper().replace("-", " ") + " ", "203.0.113.1")
    assert who["recovery_left"] == 7
    challenge = auth.auth.login("diego", GOOD, "203.0.113.1")[0]["challenge"]
    with pytest.raises(staff_auth.AuthError) as e:
        auth.auth.login_code(challenge, codes[0], "203.0.113.1")
    assert e.value.message == staff_auth.WRONG_CODE
    assert auth.auth.login_code(challenge, codes[1], "203.0.113.1")[0]["recovery_left"] == 6


def test_wrong_codes_count_like_wrong_passwords_and_the_password_buys_no_new_guesses(auth):
    auth.user("diego")
    key, _, _ = two_step_on(auth, "diego")
    wrong = "000000" if code_at(key, auth.clock.now) != "000000" else "111111"
    # 4 wrong codes, then the right password again, then one more wrong code: locked.
    challenge = auth.auth.login("diego", GOOD, "198.51.100.1")[0]["challenge"]
    for _ in range(staff_auth.LOCK_AFTER - 1):
        with pytest.raises(staff_auth.AuthError):
            auth.auth.login_code(challenge, wrong, "198.51.100.1")
    challenge = auth.auth.login("diego", GOOD, "198.51.100.1")[0]["challenge"]
    with pytest.raises(staff_auth.AuthError) as e:
        auth.auth.login_code(challenge, wrong, "198.51.100.1")
    assert e.value.code == 401
    assert not token_hash_in(auth, challenge)              # a lock takes the challenge away
    with pytest.raises(staff_auth.AuthError) as e:
        auth.auth.login("diego", GOOD, "198.51.100.1")
    assert (e.value.code, e.value.message) == (429, staff_auth.LOCKED)
    auth.clock.now += staff_auth.LOCK_FOR + 1
    challenge = auth.auth.login("diego", GOOD, "198.51.100.1")[0]["challenge"]
    auth.auth.login_code(challenge, code_at(key, auth.clock.now), "198.51.100.1")
    assert auth.auth.store.read()["users"]["diego"]["failed"] == 0


def test_wrong_codes_count_for_the_address_too(auth):
    auth.user("diego")
    key, _, _ = two_step_on(auth, "diego")
    wrong = "000000" if code_at(key, auth.clock.now) != "000000" else "111111"
    for i in range(staff_auth.IP_FAILS):
        if i % (staff_auth.LOCK_AFTER - 1) == 0:
            with auth.auth.store.change() as data:
                data["users"]["diego"]["failed"] = 0     # keep the name unlocked: only the address is counted here
            challenge = auth.auth.login("diego", GOOD, "192.0.2.9")[0]["challenge"]
        with pytest.raises(staff_auth.AuthError):
            auth.auth.login_code(challenge, wrong, "192.0.2.9")
    with pytest.raises(staff_auth.AuthError) as e:
        auth.auth.login_code(challenge, code_at(key, auth.clock.now), "192.0.2.9")
    assert (e.value.code, e.value.message) == (429, staff_auth.TOO_MANY)


def test_a_reset_link_keeps_two_step_on_and_ends_an_open_challenge(auth):
    auth.user("lorenzo", "owner")
    auth.user("diego", email="d@example.com", verified=True)
    key, _, _ = two_step_on(auth, "diego")
    challenge = auth.auth.login("diego", GOOD, "203.0.113.1")[0]["challenge"]
    auth.auth.forgot("diego", "203.0.113.1")
    auth.auth.reset(token_in(auth.mail.sent[-1][2], "reset"), OTHER)
    with pytest.raises(staff_auth.AuthError) as e:
        auth.auth.login_code(challenge, code_at(key, auth.clock.now), "203.0.113.1")
    assert e.value.message == staff_auth.CHALLENGE_GONE
    link = auth.auth.handover_link("lorenzo", "diego")["link"]
    auth.auth.reset(token_in(link, "reset"), GOOD)
    who, token = auth.auth.login("diego", GOOD, "203.0.113.1")
    assert token is None and who["two_step"] is True


def test_turning_two_step_off_or_new_recovery_codes_need_the_password_and_a_code(auth):
    auth.user("diego")
    key, codes, token = two_step_on(auth, "diego")
    _, other = auth.auth.login_code(auth.auth.login("diego", GOOD, "203.0.113.1")[0]["challenge"],
                                    code_at(key, auth.clock.now), "203.0.113.1")
    auth.clock.now += staff_auth.TOTP_STEP
    me = auth.auth.session(token)
    for current, code, message in ((OTHER, code_at(key, auth.clock.now), "Your current password isn't right."),
                                   (GOOD, "zzzzz-zzzzz", staff_auth.WRONG_CODE), (GOOD, None, staff_auth.NO_CODE)):
        for step in (auth.auth.two_step_off, auth.auth.two_step_recovery):
            with pytest.raises(staff_auth.AuthError) as e:
                step(me, current, code)
            assert e.value.message == message
    fresh = auth.auth.two_step_recovery(me, GOOD, code_at(key, auth.clock.now))["recovery"]
    assert len(fresh) == 8 and not set(fresh) & set(codes) and auth.auth.session(other)
    with pytest.raises(staff_auth.AuthError):
        auth.auth.two_step_off(me, GOOD, codes[2])            # the old codes stopped working
    done = auth.auth.two_step_off(me, GOOD, fresh[0])
    assert done == {"two_step": False, "ended": 1} and auth.auth.session(other) is None
    assert "totp" not in auth.auth.store.read()["users"]["diego"]
    assert auth.auth.login("diego", GOOD, "203.0.113.1")[1]


def test_an_owner_turns_off_someone_elses_two_step_but_not_their_own(auth):
    auth.user("lorenzo", "owner")
    auth.user("diego")
    two_step_on(auth, "lorenzo")
    key, _, _ = two_step_on(auth, "diego")
    _, session = auth.auth.login_code(auth.auth.login("diego", GOOD, "203.0.113.1")[0]["challenge"],
                                      code_at(key, auth.clock.now), "203.0.113.1")
    assert {u["name"]: u["two_step"] for u in auth.auth.list_users()["users"]} == {"lorenzo": True, "diego": True}
    with pytest.raises(staff_auth.AuthError) as e:
        auth.auth.two_step_off_for("lorenzo", "lorenzo")
    assert e.value.message == "Turn off your own two-step login from your account menu."
    done = auth.auth.two_step_off_for("lorenzo", "diego")
    assert done == {"name": "diego", "two_step": False, "ended": 2} and auth.auth.session(session) is None
    assert auth.auth.login("diego", GOOD, "203.0.113.1")[1]
    with pytest.raises(staff_auth.AuthError) as e:
        auth.auth.two_step_off_for("lorenzo", "diego")
    assert e.value.code == 409


# ---------------------------------------------------------------- HTTP, through the panel


@pytest.fixture
def web(tmp_path, auth):
    panel = staff_panel.Panel(tmp_path / "live", tmp_path / "staff", tmp_path / "repo", auth=auth.auth,
                              run=lambda *a, **k: None, lock=SimpleNamespace(take=lambda w: None, release=None))
    httpd = staff_panel.PanelServer(panel, "127.0.0.1", 0)
    threading.Thread(target=httpd.serve_forever, args=(0.05,), daemon=True).start()

    def call(method, path, body=None, headers=None, marked=True):
        conn = http.client.HTTPConnection("127.0.0.1", httpd.server_address[1], timeout=10)
        sent = {"X-Monkey-Staff": "1"} if marked and method != "GET" else {}
        data = None
        if body is not None:
            data = json.dumps(body).encode()
            sent["Content-Type"] = "application/json"
        sent.update(headers or {})
        conn.request(method, path, body=data, headers=sent)
        r = conn.getresponse()
        raw = r.read()
        conn.close()
        return SimpleNamespace(status=r.status, headers=r.headers, json=json.loads(raw) if raw else None)

    auth.call = call
    yield auth
    httpd.shutdown()
    httpd.server_close()


def cookie_of(answer) -> str:
    return answer.headers["Set-Cookie"].split(";", 1)[0]


def test_the_session_check_names_the_login_for_caddy(web):
    web.user("diego")
    answer = web.call("POST", "/auth/login", {"name": "diego", "password": GOOD})
    assert answer.status == 200 and answer.json == {"ok": True, "user": "diego", "role": "admin"}
    cookie = cookie_of(answer)
    check = web.call("GET", "/auth/check", headers={"Cookie": cookie})
    assert check.status == 200 and check.headers["X-Staff-User"] == "diego" and check.headers["X-Staff-Role"] == "admin"
    # Without a session: a page visit goes to the login page, the rest is refused.
    page = web.call("GET", "/auth/check", headers={"X-Forwarded-Method": "GET", "X-Forwarded-Uri": "/index.html"})
    assert page.status == 302 and page.headers["Location"] == "/login" and "X-Staff-User" not in page.headers
    for method, uri in (("GET", "/api/console"), ("POST", "/api/command"), ("GET", "/staff.json?x=1"),
                        ("POST", "/")):
        answer = web.call("GET", "/auth/check", headers={"X-Forwarded-Method": method, "X-Forwarded-Uri": uri,
                                                         "Cookie": "monkey_staff=" + "x" * 43})
        assert answer.status == 401 and "X-Staff-User" not in answer.headers
    assert web.call("GET", "/auth/session", headers={"Cookie": cookie}).json["user"] == "diego"
    out = web.call("POST", "/auth/logout", {}, headers={"Cookie": cookie})
    assert "Max-Age=0" in out.headers["Set-Cookie"]
    gone = web.call("GET", "/auth/check", headers={"Cookie": cookie, "X-Forwarded-Method": "POST"})
    assert gone.status == 401 and "X-Staff-User" not in gone.headers


def test_every_auth_change_must_come_from_the_page_login_included(web):
    web.user("diego")
    body = {"name": "diego", "password": GOOD}
    assert web.call("POST", "/auth/login", body, marked=False).status == 403
    assert web.call("POST", "/auth/login", body, headers={"Sec-Fetch-Site": "cross-site"}).status == 403
    assert web.call("POST", "/auth/forgot", {"who": "diego"}, marked=False).status == 403
    assert web.call("POST", "/auth/login", body, headers={"Sec-Fetch-Site": "same-origin"}).status == 200
    assert web.call("PUT", "/auth/login", body).status == 405
    assert web.call("POST", "/auth/nothing", {}).status == 404


def test_a_forwarded_address_counts_for_the_limit_and_a_header_cannot_name_the_login(web):
    for i in range(staff_auth.IP_FAILS):
        web.call("POST", "/auth/login", {"name": f"n{i}", "password": "wrong wrong wrong"},
                 headers={"X-Forwarded-For": "203.0.113.50"})
    blocked = web.call("POST", "/auth/login", {"name": "n", "password": "wrong wrong wrong"},
                       headers={"X-Forwarded-For": "203.0.113.50"})
    assert blocked.status == 429
    other = web.call("POST", "/auth/login", {"name": "n", "password": "wrong wrong wrong"},
                     headers={"X-Forwarded-For": "203.0.113.51"})
    assert other.status == 401
    # /auth/ never takes a name from a header.
    spoof = web.call("GET", "/auth/session", headers={"X-Staff-User": "lorenzo", "X-Staff-Role": "owner"})
    assert spoof.status == 401


def test_only_an_owner_manages_logins_and_nobody_raises_their_own_role(web):
    web.user("lorenzo", "owner")
    web.user("diego", "admin")
    admin = {"X-Staff-User": "diego", "X-Staff-Role": "admin"}
    owner = {"X-Staff-User": "lorenzo", "X-Staff-Role": "owner"}
    assert web.call("GET", "/api/users", headers=admin).status == 403
    assert web.call("POST", "/api/users/role", {"name": "diego", "role": "owner"}, headers=admin).status == 403
    assert web.call("POST", "/api/users", {"name": "x1", "role": "owner"}, headers=admin).status == 403
    for path in staff_panel.USER_ROUTES:
        assert staff_panel.NEEDS[path] == "owner"
    # The account requests change the password or the email, never the role, whatever the body says.
    cookie = cookie_of(web.call("POST", "/auth/login", {"name": "diego", "password": GOOD}))
    web.call("POST", "/auth/email", {"current": GOOD, "email": "d@example.com", "role": "owner"},
             headers={"Cookie": cookie})
    assert web.auth.store.read()["users"]["diego"]["role"] == "admin"
    listed = web.call("GET", "/api/users", headers=owner)
    assert listed.status == 200 and {u["name"] for u in listed.json["users"]} == {"lorenzo", "diego"}
    assert all("hash" not in u for u in listed.json["users"])
    added = web.call("POST", "/api/users", {"name": "newbie", "role": "moderator", "email": None}, headers=owner)
    assert added.status == 200 and added.json["emailed"] is False and "/reset#token=" in added.json["link"]
    last = web.call("POST", "/api/users/role", {"name": "lorenzo", "role": "admin"}, headers=owner)
    assert last.status == 409 and "last owner" in last.json["error"]
    assert web.call("POST", "/api/users/role", {"name": "diego", "role": "owner"}, headers=owner).status == 200


def test_the_password_and_email_requests_need_a_session(web):
    web.user("diego")
    for path, body in (("/auth/password", {"current": GOOD, "password": OTHER}),
                       ("/auth/email", {"current": GOOD, "email": "d@example.com"})):
        assert web.call("POST", path, body).status == 401


def test_no_token_or_password_reaches_the_journal(web, capfd):
    web.user("lorenzo", "owner", email="l@example.com", verified=True)
    web.call("POST", "/auth/login", {"name": "lorenzo", "password": GOOD})
    web.call("POST", "/auth/forgot", {"who": "lorenzo"})
    token = token_in(web.mail.sent[-1][2], "reset")
    web.call("POST", "/auth/reset", {"token": token, "password": OTHER})
    out = "".join(capfd.readouterr())
    assert token not in out and GOOD not in out and OTHER not in out


def test_two_step_login_over_http_sets_the_cookie_only_after_the_code(web):
    web.user("diego")
    cookie = cookie_of(web.call("POST", "/auth/login", {"name": "diego", "password": GOOD}))
    for path in staff_auth.TWO_STEP:
        assert web.call("POST", path, {"current": GOOD, "code": "123456"}).status == 401
    started = web.call("POST", "/auth/2fa/start", {}, headers={"Cookie": cookie})
    key = started.json["key"].replace(" ", "")
    on = web.call("POST", "/auth/2fa/confirm", {"current": GOOD, "code": code_at(key, web.clock.now)},
                  headers={"Cookie": cookie})
    assert on.status == 200 and len(on.json["recovery"]) == 8
    session = web.call("GET", "/auth/session", headers={"Cookie": cookie}).json
    assert session["two_step"] is True and session["recovery_left"] == 8
    web.clock.now += staff_auth.TOTP_STEP
    first = web.call("POST", "/auth/login", {"name": "diego", "password": GOOD})
    assert first.status == 200 and first.json["two_step"] is True and "Set-Cookie" not in first.headers
    wrong = web.call("POST", "/auth/login/code", {"challenge": first.json["challenge"], "code": "zzzzz-zzzzz"})
    assert wrong.status == 401 and wrong.json["error"] == staff_auth.WRONG_CODE and "Set-Cookie" not in wrong.headers
    good = web.call("POST", "/auth/login/code", {"challenge": first.json["challenge"],
                                                 "code": code_at(key, web.clock.now)})
    assert good.status == 200 and good.json["user"] == "diego"
    check = web.call("GET", "/auth/check", headers={"Cookie": cookie_of(good)})
    assert check.status == 200 and check.headers["X-Staff-User"] == "diego"
    assert web.call("POST", "/auth/login/code", {"challenge": "x" * 43, "code": "123456"},
                    marked=False).status == 403


def test_an_owner_turns_off_two_step_from_the_users_tab_and_it_is_recorded(web):
    web.user("lorenzo", "owner")
    web.user("diego")
    two_step_on(web, "diego")
    owner = {"X-Staff-User": "lorenzo", "X-Staff-Role": "owner"}
    admin = {"X-Staff-User": "diego", "X-Staff-Role": "admin"}
    assert staff_panel.NEEDS[("POST", "/api/users/2fa-off")] == "owner"
    assert web.call("POST", "/api/users/2fa-off", {"name": "diego"}, headers=admin).status == 403
    listed = web.call("GET", "/api/users", headers=owner).json["users"]
    assert {u["name"]: u["two_step"] for u in listed} == {"lorenzo": False, "diego": True}
    own = web.call("POST", "/api/users/2fa-off", {"name": "lorenzo"}, headers=owner)
    assert own.status == 409 and "account menu" in own.json["error"]
    done = web.call("POST", "/api/users/2fa-off", {"name": "diego"}, headers=owner)
    assert done.status == 200 and done.json["two_step"] is False
    log = (web.folder.parent / "actions.log").read_text(encoding="utf-8")
    assert log.strip().endswith("lorenzo 2fa-off diego")


def test_the_login_page_asks_for_the_code_the_way_phones_fill_it():
    html = (PAGE / "login.html").read_text(encoding="utf-8")
    field = re.search(r'<input id="code"[^>]*>', html)[0]
    assert 'autocomplete="one-time-code"' in field and 'inputmode="numeric"' in field
    assert "Use a recovery code" in html
    script = (PAGE / "auth.js").read_text(encoding="utf-8")
    assert "/auth/login/code" in script and "challenge" in script
    users = (PAGE / "users.js").read_text(encoding="utf-8")
    assert "/auth/2fa/confirm" in users and "/api/users/2fa-off" in users


# ---------------------------------------------------------------- mail


class FakeAnswer:
    status = 200

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def test_resend_gets_one_json_post_with_the_key_in_a_header():
    seen = []
    mailer = staff_auth.Mailer({"RESEND_API_KEY": "re_test_notreal", "MAIL_FROM": "Monkey SMP <staff@example.com>"},
                               urlopen=lambda req, timeout: seen.append((req, timeout)) or FakeAnswer())
    assert mailer.backend == "resend"
    assert mailer.send("diego@example.com", "Hello", "Body text\n") is True
    req, timeout = seen[0]
    assert req.full_url == "https://api.resend.com/emails" and req.get_method() == "POST" and timeout == 20
    assert req.get_header("Authorization") == "Bearer re_test_notreal"
    assert req.get_header("Content-type") == "application/json"
    assert json.loads(req.data) == {"from": "Monkey SMP <staff@example.com>", "to": ["diego@example.com"],
                                    "subject": "Hello", "text": "Body text\n"}


def test_smtp_starts_tls_before_it_logs_in():
    steps = []

    class FakeSMTP:
        def __init__(self, host, port, timeout):
            steps.append(("connect", host, port))

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def ehlo(self):
            steps.append(("ehlo",))

        def starttls(self, context):
            steps.append(("starttls", context.verify_mode.name))

        def login(self, user, password):
            steps.append(("login", user))

        def send_message(self, msg):
            steps.append(("send", msg["To"], msg["Subject"], msg["From"]))

    mailer = staff_auth.Mailer({"SMTP_HOST": "smtp.example.com", "SMTP_USER": "u", "SMTP_PASSWORD": "p-notreal",
                                "MAIL_FROM": "staff@example.com"}, smtp=FakeSMTP)
    assert mailer.backend == "smtp" and mailer.send("d@example.com", "Hi", "x") is True
    assert steps == [("connect", "smtp.example.com", 587), ("ehlo",), ("starttls", "CERT_REQUIRED"), ("ehlo",),
                     ("login", "u"), ("send", "d@example.com", "Hi", "staff@example.com")]


def test_a_failed_send_says_its_kind_and_nothing_secret(capsys):
    def refuse(req, timeout):
        raise OSError("boom with re_test_notreal inside")

    mailer = staff_auth.Mailer({"RESEND_API_KEY": "re_test_notreal", "MAIL_FROM": "s@example.com"}, urlopen=refuse)
    assert mailer.send("d@example.com", "Hi", "secret link") is False
    err = capsys.readouterr().err
    assert "mail by resend failed: OSError" in err and "re_test_notreal" not in err and "d@example.com" not in err


def test_mail_settings_come_from_the_env_file_and_need_a_sender(tmp_path):
    env = tmp_path / "mail.env"
    env.write_text("# comment\nRESEND_API_KEY='re_test_notreal'\n", newline="\n")
    auth = staff_auth.Auth(tmp_path / "auth", mail_settings=env)
    assert auth.mailer().backend is None                       # no MAIL_FROM: no mail
    env.write_text("RESEND_API_KEY=re_test_notreal\nMAIL_FROM=staff@example.com\nSTAFF_URL=http://evil.example\n")
    assert auth.mailer().backend == "resend" and auth.site_url() == staff_auth.SITE_URL
    assert staff_auth.Mailer({"SMTP_HOST": "h", "MAIL_FROM": "f", "MAIL_BACKEND": "smtp",
                              "RESEND_API_KEY": "k"}).backend == "smtp"


# ---------------------------------------------------------------- the command line


def test_the_cli_prints_a_one_time_link_and_lists_without_secrets(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("STAFF_DIR", str(tmp_path / "staff"))
    monkeypatch.setenv("MONKEY_DEPLOY_ENV", str(tmp_path / "none"))
    monkeypatch.setenv("MONKEY_STAFF_MAIL_ENV", str(tmp_path / "no-mail"))
    if hasattr(os, "geteuid"):
        monkeypatch.setattr(os, "geteuid", lambda: 0)
        assert staff_auth.main(["list"]) == 1 and "run it as monkey" in capsys.readouterr().err
        monkeypatch.setattr(os, "geteuid", lambda: 1000)       # the unit's user, monkey
    assert staff_auth.main(["ready"]) == 1
    assert staff_auth.main(["add-user", "lorenzo", "owner", "--email", "l@example.com"]) == 0
    out = capsys.readouterr().out
    link = re.search(r"https://staff\.monkeysmp\.lscaturchio\.xyz/reset#token=\S+", out)[0]
    assert "stays unconfirmed" in out
    store = staff_auth.Auth(tmp_path / "staff" / "auth", mail_settings=tmp_path / "no-mail")
    store.reset(link.split("token=")[1], GOOD)
    assert staff_auth.main(["ready"]) == 0
    assert staff_auth.main(["reset-link", "lorenzo"]) == 0 and "/reset#token=" in capsys.readouterr().out
    assert staff_auth.main(["list"]) == 0
    listed = capsys.readouterr().out
    assert "lorenzo" in listed and "scrypt" not in listed and "token" not in listed
    assert staff_auth.main(["reset-link", "nobody"]) == 1
    assert staff_auth.main(["mail-test", "x@example.com"]) == 1


# ---------------------------------------------------------------- Caddy and the pages


def test_caddy_strips_the_login_headers_before_the_session_check_and_in_order():
    caddy = (DEPLOY / "Caddyfile.staff-login").read_text()
    assert caddy.isascii() and "\r" not in caddy and "basic_auth" not in caddy
    route = caddy[caddy.index("route {"):]
    order = [route.index(s) for s in ("request_header -X-Staff-*", "request_header -X_Staff_*", "forward_auth @locked",
                                      "handle /auth/*", "handle /api/*", "handle /staff.json", "handle {")]
    assert order == sorted(order)
    assert "uri /auth/check" in caddy and "copy_headers X-Staff-User X-Staff-Role" in caddy
    locked = re.search(r"@locked not path (.+)", caddy)[1].split()
    assert "/auth/*" in locked and "/login" in locked and "/api/*" not in locked and "/staff.json" not in locked
    assert all(p.startswith(("/login", "/reset", "/verify", "/auth", "/fonts/", "/staff.css")) for p in locked)
    assert "max_size 64MB" in caddy and "header_up X-Staff-User" not in caddy
    basic = (DEPLOY / "Caddyfile.staff").read_text()
    for policy in ("default-src 'none'", "form-action 'none'", "frame-ancestors 'none'", "X-Robots-Tag", "no-store"):
        assert policy in caddy and policy in basic
    assert "header_up -X-Staff-Role" in basic           # the password box: a browser can't pick its own role


@pytest.mark.parametrize("name", ["login.html", "reset.html", "verify.html", "index.html"])
def test_the_pages_run_under_the_strict_policy(name):
    html = (PAGE / name).read_text(encoding="utf-8")
    assert not re.search(r"<script(?![^>]*\bsrc=)", html) and not re.search(r"<style\b", html)
    assert not re.search(r"\sstyle=|\son\w+=", html) and not re.search(r"https?://", html)
    assert re.search(r'<meta name="robots" content="noindex', html)


@pytest.mark.parametrize("name", ["auth.js", "users.js"])
def test_the_scripts_only_use_text(name):
    script = (PAGE / name).read_text(encoding="utf-8")
    assert "innerHTML" not in script and "eval(" not in script and "document.write" not in script
    assert not re.search(r"\.style\.|setAttribute\(\s*[\"']style", script) and not re.search(r"https?://", script)
    assert "localStorage" not in script and "X-Monkey-Staff" in script


def test_the_login_page_has_a_forgot_link_and_the_reset_token_stays_out_of_requests():
    assert "Forgot password?" in (PAGE / "login.html").read_text(encoding="utf-8")
    script = (PAGE / "auth.js").read_text(encoding="utf-8")
    assert "location.hash" in script and "history.replaceState" in script and "location.search" not in script


# ---------------------------------------------------------------- monkey-staff.sh


@pytest.fixture
def site(tmp_path):
    """The real monkey-staff.sh under dash, as test_staff_status's `staff`, with the controls' answer faked too."""
    shell = shutil.which("dash")
    if not shell:
        pytest.skip("needs dash")
    bin_dir, caddy, calls = tmp_path / "bin", tmp_path / "caddy", tmp_path / "calls"
    bin_dir.mkdir()
    caddy.mkdir()
    fakes = {**FAKES,
             "curl": 'case "$*" in\n  *127.0.0.1:8130*) printf %s "${FAKE_PANEL:-403}" ;;\n'
                     '  *staff.json*) printf %s "${FAKE_DATA:-${FAKE_CODE:-401}}" ;;\n'
                     '  *) printf %s "${FAKE_CODE:-401}" ;;\nesac',
             "python3": 'echo "python3 $*" >>"$FAKE_CALLS"\necho "LINK-SHOWN-ONCE"\nexit "${FAKE_RC_python:-0}"'}
    for name, body in fakes.items():
        (bin_dir / name).write_text(f"#!/bin/sh\n{body}\n", newline="\n")
        (bin_dir / name).chmod(0o755)
    (caddy / "Caddyfile").write_text("map.example.com {\n\trespond map\n}\n", newline="\n")

    def run(*args, **env):
        calls.unlink(missing_ok=True)
        environ = {**os.environ, "PATH": str(bin_dir) + os.pathsep + os.environ["PATH"], "FAKE_CALLS": calls.as_posix(),
                   "MONKEY_DEPLOY_ENV": (tmp_path / "none").as_posix(), "REPO_DIR": REPO.root.as_posix(),
                   "LIVE_DIR": "/srv/live", "STAFF_DIR": (tmp_path / "staff").as_posix(),
                   "CADDY_DIR": caddy.as_posix(), **env}
        done = subprocess.run([shell, (DEPLOY / "monkey-staff.sh").as_posix(), *args], env=environ,
                              stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        return SimpleNamespace(code=done.returncode, out=done.stdout,
                               calls=calls.read_text().splitlines() if calls.exists() else [])

    (tmp_path / "staff-logins").write_text("diego $2a$08$fakehash\n", newline="\n")
    shutil.copy(tmp_path / "staff-logins", caddy / "staff-logins")
    return SimpleNamespace(run=run, site=caddy / "staff.caddy", folder=caddy)


def test_add_user_and_reset_link_run_the_tool_as_monkey_and_show_its_link(site):
    done = site.run("--add-user", "lorenzo", "owner", "l@example.com")
    assert done.code == 0 and done.out.count("LINK-SHOWN-ONCE") == 1
    assert any(c.startswith("python3 -B ") and c.endswith("staff_auth.py add-user lorenzo owner --email l@example.com")
               for c in done.calls)
    done = site.run("--reset-link", "diego")
    assert done.code == 0 and any(c.endswith("staff_auth.py reset-link diego") for c in done.calls)
    for bad in (("--add-user", "Lorenzo", "owner"), ("--add-user", "lorenzo", "root"), ("--add-user",),
                ("--add-user", "x", "admin", "a;b@c.de"), ("--reset-link",)):
        assert site.run(*bad).code == 2
    assert site.run("--add-user", "lorenzo", "owner", FAKE_ID="1000").code == 1


def test_switching_to_the_login_page_and_back(site):
    assert site.run("--install").code == 0
    assert site.site.read_text() == (DEPLOY / "Caddyfile.staff").read_text()
    # It refuses while the controls don't answer or no owner can log in yet.
    done = site.run("--use-new-login", FAKE_PANEL="000")
    assert done.code == 1 and "don't answer" in done.out
    done = site.run("--use-new-login", FAKE_RC_python="1")
    assert done.code == 1 and "no owner can log in" in done.out
    assert site.site.read_text() == (DEPLOY / "Caddyfile.staff").read_text()
    # A visit with no session must go to the login page: anything else puts the password box back.
    done = site.run("--use-new-login")
    assert done.code == 1 and "the login is as it was" in done.out
    assert site.site.read_text() == (DEPLOY / "Caddyfile.staff").read_text()
    done = site.run("--use-new-login", FAKE_CODE="302", FAKE_DATA="401")
    assert done.code == 0 and "systemctl reload caddy" in done.calls and "caddy validate" in " ".join(done.calls)
    assert site.site.read_text() == (DEPLOY / "Caddyfile.staff-login").read_text()
    # --install again keeps the login page, and --check says which one is live.
    assert site.run("--install", FAKE_CODE="302", FAKE_DATA="401").code == 0
    assert site.site.read_text() == (DEPLOY / "Caddyfile.staff-login").read_text()
    done = site.run("--check", FAKE_CODE="302", FAKE_DATA="401")
    assert "login: the page's own login page" in done.out and "gets: 302 (302 is right" in done.out
    # Caddy refusing the switch back changes nothing; then the rollback.
    assert site.run("--use-basic-auth", FAKE_RC_validate="1").code == 1
    assert site.site.read_text() == (DEPLOY / "Caddyfile.staff-login").read_text()
    done = site.run("--use-basic-auth")
    assert done.code == 0 and site.site.read_text() == (DEPLOY / "Caddyfile.staff").read_text()
    assert "login: the browser's password box" in site.run("--check").out
    assert [p.name for p in site.folder.iterdir() if p.name.startswith(".")] == []


def test_switching_needs_the_site_in_caddy_first(site):
    done = site.run("--use-new-login", FAKE_CODE="302", FAKE_DATA="401")
    assert done.code == 1 and "--install first" in done.out and not site.site.exists()
