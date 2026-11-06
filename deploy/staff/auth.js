// The login, reset and email pages (login.html, reset.html, verify.html), talking to tools/staff_auth.py through
// /auth/. Everything from the server goes in with textContent. Forms are sent from here, never by the browser itself:
// Caddy's Content-Security-Policy refuses that (form-action 'none'), so a password can't end up in an address.
"use strict";

(() => {
  const $ = (id) => document.getElementById(id);
  const page = document.body.dataset.page;

  function say(id, text) {
    const node = $(id);
    if (!node) return;
    node.hidden = !text;
    node.textContent = text || "";
  }

  // One call to /auth/. A refusal comes back as an Error whose message is the server's own sentence.
  async function auth(method, path, body) {
    const headers = { "X-Monkey-Staff": "1" };
    if (body !== undefined) headers["Content-Type"] = "application/json";
    let answer;
    try {
      answer = await fetch(path, { method, headers, body: body === undefined ? undefined : JSON.stringify(body),
                                   cache: "no-store", credentials: "same-origin" });
    } catch {
      throw new Error("The page can't reach the server right now.");
    }
    let data = null;
    try {
      data = await answer.json();
    } catch {
      data = null;
    }
    if (!answer.ok || !data || data.ok === false) {
      const error = new Error((data && data.error) || `That didn't work (error ${answer.status}).`);
      error.status = answer.status;
      throw error;
    }
    return data;
  }

  // The link's token is in the address after #, which the browser never sends anywhere; it is taken off the address
  // at once, so it isn't left in the history. This tab keeps it until it is used, so a reload (a phone does that when
  // you switch apps) doesn't lose it.
  const KEPT = `monkey-staff-link:${location.pathname.replace(/\.html$/, "")}`;   // a reset link and a verify link apart
  function linkToken() {
    let token = new URLSearchParams(location.hash.slice(1)).get("token") || "";
    if (location.hash) history.replaceState(null, "", location.pathname);
    try {
      if (token) sessionStorage.setItem(KEPT, token);
      else token = sessionStorage.getItem(KEPT) || "";
    } catch { /* no storage: only the address has it */ }
    return token;
  }

  function linkUsed() {
    try { sessionStorage.removeItem(KEPT); } catch { /* nothing kept */ }
  }

  function busy(button, on) {
    if (button) button.disabled = on;
  }

  function login() {
    const form = $("login-form");
    const forgotCard = $("forgot-card");
    const loginCard = $("login-card");

    auth("GET", "/auth/session").then((me) => {
      say("note", `You are logged in as ${me.user}.`);
      const open = document.createElement("a");
      open.className = "btn";
      open.href = "/";
      open.textContent = "Open the staff page";
      $("note").append(" ", open);
    }).catch(() => {});

    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      say("error", "");
      const name = $("name").value.trim().toLowerCase();
      const password = $("password").value;
      if (!name || !password) {
        say("error", "Type your name and password.");
        return;
      }
      busy($("login"), true);
      try {
        const done = await auth("POST", "/auth/login", { name, password });
        $("password").value = "";
        if (done.two_step) {
          askCode(done.challenge);
          return;
        }
        location.replace("/");
      } catch (error) {
        say("error", error.message);
        $("password").value = "";
        $("password").focus();
      } finally {
        busy($("login"), false);
      }
    });

    // Two-step login: the right password gave a challenge, good once for 5 minutes; the code turns it into a session.
    const codeCard = $("code-card");
    let challenge = "";
    let recovery = false;

    function codeKind(useRecovery) {
      recovery = useRecovery;
      const code = $("code");
      code.value = "";
      code.inputMode = recovery ? "text" : "numeric";
      code.autocomplete = recovery ? "off" : "one-time-code";
      code.maxLength = recovery ? 16 : 11;
      $("code-label").textContent = recovery ? "Recovery code" : "Code from your app";
      $("code-help").textContent = recovery
        ? "Type one of the recovery codes you saved when you turned on two-step login. Each works once."
        : "Open your authenticator app and type the 6-digit code it shows for Monkey SMP staff. You have 5 minutes.";
      $("code-switch").textContent = recovery ? "Use the code from your app" : "Use a recovery code";
      code.focus();
    }

    function askCode(token) {
      challenge = token;
      say("code-error", "");
      loginCard.hidden = true;
      codeCard.hidden = false;
      codeKind(false);
    }

    function backToLogin(message) {
      challenge = "";
      codeCard.hidden = true;
      loginCard.hidden = false;
      say("error", message || "");
      $("password").focus();
    }

    $("code-switch").addEventListener("click", () => codeKind(!recovery));
    $("code-back").addEventListener("click", () => backToLogin(""));
    $("code-form").addEventListener("submit", async (event) => {
      event.preventDefault();
      say("code-error", "");
      const code = $("code").value.trim();
      if (!code) {
        say("code-error", recovery ? "Type a recovery code." : "Type the 6-digit code from your app.");
        return;
      }
      busy($("code-send"), true);
      try {
        await auth("POST", "/auth/login/code", { challenge, code });
        location.replace("/");
      } catch (error) {
        $("code").value = "";
        // The challenge is gone (too slow, or the name got locked): start from the password again.
        if (error.status === 400 || error.status === 429) backToLogin(error.message);
        else {
          say("code-error", error.message);
          $("code").focus();
        }
      } finally {
        busy($("code-send"), false);
      }
    });

    $("forgot-open").addEventListener("click", () => {
      loginCard.hidden = true;
      forgotCard.hidden = false;
      $("who").value = $("name").value;
      $("who").focus();
    });
    $("forgot-close").addEventListener("click", () => {
      forgotCard.hidden = true;
      loginCard.hidden = false;
      $("name").focus();
    });
    $("forgot-form").addEventListener("submit", async (event) => {
      event.preventDefault();
      say("forgot-error", "");
      say("forgot-note", "");
      const who = $("who").value.trim();
      if (!who) {
        say("forgot-error", "Type your name or your email.");
        return;
      }
      busy($("forgot"), true);
      try {
        const done = await auth("POST", "/auth/forgot", { who });
        say("forgot-note", done.message);
      } catch (error) {
        say("forgot-error", error.message);
      } finally {
        busy($("forgot"), false);
      }
    });
  }

  function reset() {
    const token = linkToken();
    if (!token) {
      say("error", "This page needs the link from the email or from the owner. Ask for a new one if it's lost.");
      $("reset-form").hidden = true;
      return;
    }
    $("reset-form").addEventListener("submit", async (event) => {
      event.preventDefault();
      say("error", "");
      const password = $("password").value;
      if (password.length < 12) {
        say("error", "A password needs at least 12 characters.");
        return;
      }
      if (password !== $("again").value) {
        say("error", "The two passwords aren't the same.");
        return;
      }
      busy($("reset"), true);
      try {
        const done = await auth("POST", "/auth/reset", { token, password });
        linkUsed();
        $("reset-form").hidden = true;
        say("note", `The password of ${done.user} is set. Log in with it now.`);
        $("done").hidden = false;
      } catch (error) {
        say("error", error.message);
      } finally {
        busy($("reset"), false);
      }
    });
  }

  function verify() {
    const token = linkToken();
    if (!token) {
      say("error", "This page needs the link from the email. Ask for a new one if it's lost.");
      $("verify").hidden = true;
      return;
    }
    // A button, not at once: a mail scanner that opens the link doesn't confirm anything.
    $("verify").addEventListener("click", async () => {
      say("error", "");
      busy($("verify"), true);
      try {
        const done = await auth("POST", "/auth/verify", { token });
        linkUsed();
        say("note", `${done.email} is confirmed for ${done.user}.`);
        $("verify").hidden = true;
      } catch (error) {
        say("error", error.message);
        busy($("verify"), false);
      }
    });
  }

  ({ login, reset, verify })[page]?.();
})();
