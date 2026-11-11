// The staff page's account menu (who you are, your role, your password and email, log out) and, for owners, the
// Users tab (tools/staff_auth.py, through tools/staff_panel.py's /api/users and /auth/). Everything from the server
// goes in with textContent; a confirm step is two buttons on the page, never confirm().
"use strict";

(() => {
  const ROLES = ["moderator", "admin", "owner"];
  const $ = (id) => document.getElementById(id);
  let me = null;

  function el(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  }

  const DAY = new Intl.DateTimeFormat(undefined, { year: "numeric", month: "short", day: "numeric" });

  // The server's ISO time as a plain date, e.g. "Nov 6, 2026".
  function day(iso) {
    const ms = Date.parse(iso || "");
    return Number.isNaN(ms) ? "?" : DAY.format(new Date(ms));
  }

  // " 2 other sessions logged out.", or nothing when there were none.
  function ended(count) {
    return count ? ` ${count} other session${count === 1 ? "" : "s"} logged out.` : "";
  }

  function button(label, className, onClick, type = "button") {
    const node = el("button", `btn ${className || ""}`.trim(), label);
    node.type = type;
    if (onClick) node.addEventListener("click", onClick);
    return node;
  }

  function field(label, input) {
    const box = el("div", "form-field");
    const id = input.id || `f-${Math.random().toString(36).slice(2)}`;
    input.id = id;
    const tag = el("label", "", label);
    tag.htmlFor = id;
    box.append(tag, input);
    return box;
  }

  function input(type, attrs) {
    const node = document.createElement("input");
    node.type = type;
    Object.assign(node, attrs || {});
    return node;
  }

  async function call(method, url, body) {
    const headers = { "X-Monkey-Staff": "1" };
    if (body !== undefined) headers["Content-Type"] = "application/json";
    let answer;
    try {
      answer = await fetch(url, { method, headers, body: body === undefined ? undefined : JSON.stringify(body),
                                  cache: "no-store", credentials: "same-origin" });
    } catch {
      throw new Error("The page can't reach the server's machine right now.");
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

  function say(node, text, kind) {
    node.className = kind === "error" ? "attention" : "note";
    node.hidden = !text;
    node.textContent = text || "";
  }

  // ------------------------------------------------ the account menu

  function passwordForm(status) {
    const form = el("form");
    const current = input("password", { autocomplete: "current-password", maxLength: 256 });
    const fresh = input("password", { autocomplete: "new-password", maxLength: 256, minLength: 12 });
    form.append(el("h3", "", "Change password"), field("Current password", current),
                field("New password (12 characters or more)", fresh), button("Change password", "", null, "submit"));
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      try {
        const done = await call("POST", "/auth/password", { current: current.value, password: fresh.value });
        say(status, `Password changed.${ended(done.ended)}`);
        current.value = fresh.value = "";
      } catch (error) {
        say(status, error.message, "error");
      }
    });
    return form;
  }

  function emailForm(status, session) {
    const form = el("form");
    const email = input("email", { autocomplete: "email", maxLength: 254, value: session.email || "" });
    const current = input("password", { autocomplete: "current-password", maxLength: 256 });
    form.append(el("h3", "", "Change email"), field("New email", email), field("Current password", current),
                button("Change email", "", null, "submit"));
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      try {
        const done = await call("POST", "/auth/email", { current: current.value, email: email.value.trim() });
        say(status, done.sent ? `A link to confirm ${done.email} is on its way: reset emails go there once it is.`
                              : "Saved. Email isn't set up on this server, so the address stays unconfirmed for now.");
        current.value = "";
      } catch (error) {
        say(status, error.message, "error");
      }
    });
    return form;
  }

  // Two-step login: a code from an authenticator app at every login, after the password.
  function codeInput(label) {
    const code = input("text", { autocomplete: "one-time-code", inputMode: "numeric", maxLength: 16,
                                 autocapitalize: "off", spellcheck: false });
    return [code, field(label, code)];
  }

  function recoveryBox(status, codes) {
    const box = el("div", "confirm handover");
    const list = el("ul", "recovery mono");
    for (const code of codes) list.append(el("li", "", code));
    box.append(el("p", "", "Your recovery codes, shown only now. Write them down or save them somewhere safe: each "
                           + "one logs you in once if you lose your phone."), list,
               button("I saved them", "", () => box.remove()));
    status.after(box);
  }

  function twoStep(status, session) {
    const box = el("div", "two-step");
    box.append(el("h3", "", "Two-step login"));
    if (!session.two_step) {
      box.append(el("p", "fine", "Off. With it on, logging in needs a 6-digit code from an authenticator app on "
                                 + "your phone, as well as the password."));
      const turnOn = button("Turn on two-step login", "", async () => {
        let started;
        turnOn.disabled = true;
        try {
          started = await call("POST", "/auth/2fa/start", {});
        } catch (error) {
          say(status, error.message, "error");
          turnOn.disabled = false;
          return;
        }
        turnOn.remove();
        const form = el("form");
        const qr = el("img", "qr");
        qr.src = started.qr;
        qr.alt = "A QR code: scan it with your authenticator app";
        qr.width = qr.height = started.modules * 4;     // whole pixels per module, so a camera reads it
        const link = el("a", "link", "On this phone? Open it in your authenticator app");
        link.href = started.link;
        const key = el("p", "mono", started.key);
        const current = input("password", { autocomplete: "current-password", maxLength: 256 });
        const [code, codeField] = codeInput("The 6-digit code the app shows now");
        form.append(el("p", "fine", "1. In your authenticator app (Google Authenticator, Microsoft Authenticator, "
                                    + "1Password and the like), add an account and scan this code with your phone:"),
                    qr, link,
                    el("p", "fine", "Can't scan it? Add the account by hand: choose a time-based key and type this:"),
                    key,
                    el("p", "fine", `2. Type the 6-digit code the app shows, and your password, within ${started.minutes} `
                                    + "minutes."),
                    field("Current password", current), codeField, button("Turn it on", "primary", null, "submit"));
        form.addEventListener("submit", async (e) => {
          e.preventDefault();
          try {
            const done = await call("POST", "/auth/2fa/confirm", { current: current.value, code: code.value.trim() });
            say(status, `Two-step login is on.${ended(done.ended)}`);
            current.value = code.value = "";
            session.two_step = true;
            session.recovery_left = done.recovery.length;
            box.replaceWith(twoStep(status, session));
            recoveryBox(status, done.recovery);
          } catch (error) {
            if (error.status === 410) box.replaceWith(twoStep(status, session));   // the key ran out: the button again
            say(status, error.message, "error");
          }
        });
        box.append(form);
        current.focus();
      });
      box.append(turnOn);
      return box;
    }
    box.append(el("p", "fine", `On. Recovery codes left: ${session.recovery_left}.`));
    const form = el("form");
    const current = input("password", { autocomplete: "current-password", maxLength: 256 });
    const [code, codeField] = codeInput("Code from your app, or a recovery code");
    const off = button("Turn off two-step login", "", null, "submit");
    const fresh = button("New recovery codes", "", null, "submit");
    const row = el("div", "actions");
    row.append(fresh, off);
    form.append(field("Current password", current), codeField, row);
    // Which button sent the form, without event.submitter (Safari before 15.4 lacks it). Enter clicks the first.
    let chosen = fresh;
    off.addEventListener("click", () => { chosen = off; });
    fresh.addEventListener("click", () => { chosen = fresh; });
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const body = { current: current.value, code: code.value.trim() };
      try {
        if (chosen === off) {
          const done = await call("POST", "/auth/2fa/off", body);
          say(status, `Two-step login is off.${ended(done.ended)}`);
          session.two_step = false;
          box.replaceWith(twoStep(status, session));
        } else {
          const done = await call("POST", "/auth/2fa/recovery", body);
          say(status, "New recovery codes are below. The old ones don't work any more.");
          session.recovery_left = done.recovery.length;
          box.replaceWith(twoStep(status, session));
          recoveryBox(status, done.recovery);
        }
        current.value = code.value = "";
      } catch (error) {
        say(status, error.message, "error");
      }
    });
    box.append(form);
    return box;
  }

  async function account() {
    const box = $("account");
    const body = $("account-body");
    if (!box || !body) return;
    let session = null;
    try {
      session = await call("GET", "/auth/session");
    } catch {
      session = null;            // the browser's password box: no session to manage here
    }
    const summary = $("account-name");
    summary.textContent = me.user;
    summary.append(" ", el("small", "", me.role));
    body.replaceChildren();
    const status = el("p", "note");
    status.hidden = true;
    status.setAttribute("role", "status");
    body.append(el("p", "", `Logged in as ${me.user}, ${me.role}.`), status);
    if (session && session.two_step_needed) {
      // An admin or owner login without two-step works as a moderator until it is on (staff_auth.working_role).
      body.append(el("p", "attention", `Your login is ${session.held_role}, but it works as a moderator until you `
                                       + "turn on two-step login below. Then reload this page."));
      box.open = true;
    }
    if (!session) {
      body.append(el("p", "fine", "This login is the browser's password box: ask the owner for a new password."));
    } else {
      const mail = session.email ? `${session.email}${session.email_verified ? "" : " (not confirmed yet)"}` : "none";
      body.append(el("p", "fine", `Email: ${mail}`), twoStep(status, session), passwordForm(status),
                  emailForm(status, session),
                  button("Log out", "primary", async () => {
                    try {
                      await call("POST", "/auth/logout", {});
                    } finally {
                      location.replace("/login");
                    }
                  }));
    }
    box.hidden = false;
  }

  // ------------------------------------------------ the Users tab (owners)

  function confirmStep(where, message, yes, onYes, onNo) {
    const box = el("div", "confirm");
    box.append(el("p", "", message));
    const row = el("div", "actions");
    row.append(button(yes, "primary", () => { box.remove(); onYes(); }),
               button("Cancel", "", () => { box.remove(); if (onNo) onNo(); }));
    box.append(row);
    where.append(box);
  }

  function handover(where, name, link) {
    const box = el("div", "confirm handover");
    const text = input("text", { value: link, readOnly: true });
    text.addEventListener("focus", () => text.select());
    box.append(el("p", "", `The link for ${name}, shown only now. It works once, for 24 hours: pass it on privately.`),
               text, button("Done", "", () => box.remove()));
    where.prepend(box);
  }

  async function act(url, body, done) {
    const note = $("users-note");
    const error = $("users-error");
    error.hidden = true;
    try {
      const result = await call("POST", url, body);
      if (done) done(result);
      await loadUsers();
      return result;
    } catch (e) {
      error.hidden = false;
      error.textContent = e.message;
      note.hidden = true;
      return null;
    }
  }

  function userRow(u, extras) {
    const li = el("li");
    const who = el("p", "who");
    who.append(el("b", "", u.name), el("span", "meta", u.role));
    const flags = [];
    if (u.disabled) flags.push("disabled");
    if (u.locked) flags.push("locked for now");
    if (!u.password_set) flags.push("no password yet");
    if (u.two_step) flags.push("2FA on");
    if (flags.length) who.append(el("span", "meta", flags.join(", ")));
    const mail = u.email ? `${u.email}${u.email_verified ? "" : " (not confirmed)"}` : "no email";
    li.append(who, el("p", "meta", `${mail}; ${u.sessions} session${u.sessions === 1 ? "" : "s"}; added ${day(u.created)}`));

    const row = el("div", "actions");
    const role = document.createElement("select");
    role.setAttribute("aria-label", `Role of ${u.name}`);
    for (const r of ROLES) {
      const option = el("option", "", r);
      option.value = r;
      option.selected = r === u.role;
      role.append(option);
    }
    role.addEventListener("change", () => {
      const next = role.value;
      confirmStep(li, `Change the role of ${u.name} from ${u.role} to ${next}? Their access changes at once.`, "Change role",
        () => act("/api/users/role", { name: u.name, role: next }),
        () => { role.value = u.role; });
    });
    row.append(role,
      button(u.disabled ? "Enable" : "Disable", "", () => act("/api/users/disable", { name: u.name, disabled: !u.disabled })),
      button("Log out everywhere", "", () => act("/api/users/sessions", { name: u.name })),
      button("New password link", "", () => act("/api/users/link", { name: u.name },
                                               (r) => handover(extras, u.name, r.link))),
      button("Delete", "danger", () => confirmStep(li, `Delete the login ${u.name}? It can't be undone.`, "Delete",
                                             () => act("/api/users/delete", { name: u.name }))));
    // A lost phone: only for someone else; your own goes from the account menu, with a code.
    if (u.two_step && u.name !== me.user) {
      row.append(button("Turn off 2FA", "", () => confirmStep(li,
        `Turn off two-step login for ${u.name}? Do this only if you know it's them (a lost phone): the password alone `
        + "will log in, and every session of theirs is logged out.", "Turn off 2FA",
        () => act("/api/users/2fa-off", { name: u.name }))));
    }
    li.append(row);
    return li;
  }

  function addForm(extras, mail) {
    const form = el("form", "add-user");
    const name = input("text", { maxLength: 32, autocomplete: "off", autocapitalize: "off", spellcheck: false });
    const email = input("email", { maxLength: 254, autocomplete: "off" });
    const role = document.createElement("select");
    for (const r of ROLES) {
      const option = el("option", "", r);
      option.value = r;
      role.append(option);
    }
    form.append(field("Name (small letters, digits, _)", name), field("Role", role), field("Email (optional)", email),
                button("Add", "primary", null, "submit"));
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const added = await act("/api/users", { name: name.value.trim(), role: role.value, email: email.value.trim() || null });
      if (!added) return;
      name.value = email.value = "";
      if (added.link) handover(extras, added.name, added.link);
      const note = $("users-note");
      note.hidden = false;
      note.textContent = added.emailed ? `${added.name} was emailed a link to choose a password.`
        : `${added.name} is added. ${mail ? "" : "Email isn't set up, so "}pass on the link above.`;
    });
    return form;
  }

  let extrasBox = null;

  async function loadUsers() {
    const body = $("users-body");
    if (!body || !me || me.role !== "owner") return;
    let data;
    try {
      data = await call("GET", "/api/users");
    } catch (error) {
      $("users-error").hidden = false;
      $("users-error").textContent = error.message;
      return;
    }
    if (!extrasBox) extrasBox = el("div");
    const list = el("ul", "users");
    for (const u of data.users) list.append(userRow(u, extrasBox));
    if (!data.users.length) list.append(el("li", "meta", "No logins on the login page yet: add the first owner below."));
    const people = el("section", "box");
    people.append(el("h3", "", `Logins (${data.users.length})`), list);
    const add = el("section", "box");
    add.append(el("h3", "", "Add a login"), addForm(extrasBox, data.mail));
    body.className = "stack";
    body.replaceChildren(extrasBox, people, add);
  }

  async function start() {
    try {
      me = await call("GET", "/api/me");
    } catch {
      return;
    }
    account();
    if (me.role === "owner" && $("users-tab")) {
      $("users-tab").hidden = false;
      if (location.hash === "#users") loadUsers();
      window.addEventListener("hashchange", () => {
        if (location.hash === "#users") loadUsers();
      });
    }
  }

  start();
})();
