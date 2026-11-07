// The staff page's Mod settings tab (tools/staff_modcfg.py answers it): one card per mod, each config file a form.
// The same rules as panel.js: everything from the server goes in with textContent, no style attributes, no forms, no
// confirm() or alert(). The panel checks every value and role again; this only shapes the form.
"use strict";

(() => {
  const RANK = { moderator: 0, admin: 1, owner: 2 };
  const $ = (id) => document.getElementById(id);
  let role = "moderator";
  const can = (need) => RANK[role] >= RANK[need];
  const state = { mods: null, loaded: false };
  let uid = 0;

  function el(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  }

  function button(label, className, onClick) {
    const node = el("button", `btn ${className || ""}`.trim(), label);
    node.type = "button";
    node.addEventListener("click", onClick);
    return node;
  }

  async function api(method, url, body) {
    const headers = { "X-Monkey-Staff": "1" };
    let payload;
    if (body !== undefined) {
      headers["Content-Type"] = "application/json";
      payload = JSON.stringify(body);
    }
    let answer;
    try {
      answer = await fetch(url, { method, headers, body: payload, cache: "no-store" });
    } catch {
      throw new Error("The page can't reach the server's machine right now.");
    }
    let data = null;
    try {
      data = await answer.json();
    } catch {
      data = null;
    }
    if (answer.status === 401) throw new Error("Your login has run out. Reload this page to log in again.");
    if (!answer.ok || (data && data.ok === false)) {
      throw new Error((data && data.error) || `That didn't work (error ${answer.status}).`);
    }
    return data || {};
  }

  function say(node, text) {
    node.hidden = !text;
    node.textContent = text ? (text.message || String(text)) : "";
  }

  function openInFiles(path, writable) {
    window.dispatchEvent(new CustomEvent("monkey-open-file", { detail: { path, writable } }));
  }

  // ---------------------------------------------------------------- one field

  const ITEM_TYPES = { int: "whole numbers", float: "numbers", bool: "true or false", text: "text" };

  // The control for a field, and how to read its value back (undefined: not a valid value yet).
  function control(field, editable) {
    const id = `modcfg-f${uid += 1}`;
    let node;
    let read;
    if (field.type === "bool") {
      node = el("input");
      node.type = "checkbox";
      node.checked = field.value === true;
      read = () => node.checked;
    } else if (field.type === "int" || field.type === "float") {
      node = el("input");
      node.type = "number";
      node.step = field.type === "int" ? "1" : "any";
      if (field.min !== undefined) node.min = String(field.min);
      if (field.max !== undefined) node.max = String(field.max);
      node.value = String(field.value);
      read = () => {
        const text = node.value.trim();
        if (text === "") return undefined;
        const n = Number(text);
        if (!Number.isFinite(n) || (field.type === "int" && !Number.isInteger(n))) return undefined;
        return n;
      };
    } else if (field.type === "text" && field.choices) {
      node = el("select");
      for (const choice of field.choices) {
        const option = el("option", "", choice);
        option.value = choice;
        node.appendChild(option);
      }
      node.value = field.value;
      read = () => node.value;
    } else if (field.type === "list") {
      node = el("textarea", "mono");
      node.rows = Math.min(8, Math.max(2, field.value.length + 1));
      node.spellcheck = false;
      node.value = field.value.map(String).join("\n");
      read = () => {
        const items = node.value.split("\n").map((s) => s.trim()).filter((s) => s !== "");
        if (field.item === "text") return items;
        if (field.item === "bool") {
          return items.every((s) => s === "true" || s === "false") ? items.map((s) => s === "true") : undefined;
        }
        const numbers = items.map(Number);
        const ok = numbers.every((n) => Number.isFinite(n) && (field.item !== "int" || Number.isInteger(n)));
        return ok ? numbers : undefined;
      };
    } else if (field.type === "text") {
      node = el("input", "mono");
      node.type = "text";
      node.maxLength = 2000;
      node.spellcheck = false;
      node.value = field.value;
      read = () => node.value;
    } else {
      node = el("code", "fixed", String(field.value));
      read = () => field.value;
      editable = false;
    }
    node.id = id;
    if ("disabled" in node) node.disabled = !editable;
    node.setAttribute("aria-label", field.key);
    return { node, read, id };
  }

  function same(a, b) {
    return JSON.stringify(a) === JSON.stringify(b);
  }

  function fieldRow(field, editable, onChange) {
    const { node, read, id } = control(field, editable);
    const wide = field.type === "list" || field.type === "fixed" || (field.type === "text" && !field.choices);
    const row = el("div", wide ? "field long" : "field");
    const label = el("label", "", field.key);
    label.htmlFor = id;
    const holder = el("div", "control");
    holder.appendChild(node);
    row.append(label, holder);
    let about = field.about || "";
    if (field.type === "list") about = `${about} One item per line (${ITEM_TYPES[field.item]}).`.trim();
    if (field.min !== undefined) about = `${about} From ${field.min} to ${field.max}.`.trim();
    if (field.type === "fixed") about = `${about} ${field.locked || "Shown only: change it in Files."}`.trim();
    if (about) row.appendChild(el("p", "about", about));
    const entry = { field, read, row, bad: false };
    const mark = () => {
      const value = read();
      entry.bad = value === undefined;
      row.classList.toggle("changed", !entry.bad && !same(value, field.value));
      row.classList.toggle("invalid", entry.bad);
      onChange();
    };
    node.addEventListener("input", mark);
    node.addEventListener("change", mark);
    return entry;
  }

  // ---------------------------------------------------------------- one file

  async function loadFile(holder, file) {
    holder.replaceChildren(el("p", "fine", "Reading the file..."));
    let data;
    try {
      data = await api("GET", `/api/mod-config?path=${encodeURIComponent(file.path)}`);
    } catch (error) {
      holder.replaceChildren(el("p", "attention", error.message || String(error)));
      return;
    }
    renderFile(holder, file, data);
  }

  function renderFile(holder, file, data) {
    const editable = data.writable && can("admin");
    const error = el("p", "attention");
    const note = el("p", "note");
    error.setAttribute("role", "alert");
    note.setAttribute("role", "status");
    error.hidden = note.hidden = true;
    const parts = [error, note];
    if (data.error) {
      say(error, data.error);
      parts.push(button("Open in Files", "", () => openInFiles(file.path, data.writable)));
      holder.replaceChildren(...parts);
      return;
    }
    const entries = [];
    const count = el("p", "fine", "No unsaved changes.");
    count.setAttribute("role", "status");
    const bar = el("div", "savebar");
    const save = button("Save changes", "primary", () => saveFile(holder, file, data, entries, error, note, save));
    const onChange = () => {
      const n = entries.filter((e) => e.row.classList.contains("changed")).length;
      const bad = entries.filter((e) => e.bad).length;
      count.textContent = bad ? `${bad} value${bad === 1 ? " isn't" : "s aren't"} valid.`
        : n ? `${n} unsaved change${n === 1 ? "" : "s"}.` : "No unsaved changes.";
      bar.classList.toggle("dirty", n > 0 || bad > 0);
      save.disabled = !editable || bad > 0 || n === 0;
    };
    const important = new Set(data.important || []);
    const first = el("div", "fields");
    const rest = el("div", "fields");
    for (const field of data.fields) {
      const entry = fieldRow(field, editable, onChange);
      entries.push(entry);
      (important.has(field.key) ? first : rest).appendChild(entry.row);
    }
    if (!data.fields.length) parts.push(el("p", "fine", "This file has no settings this page can show."));
    if (first.children.length) parts.push(first);
    if (rest.children.length) {
      if (first.children.length) {
        const more = el("details", "more");
        more.appendChild(el("summary", "", `All settings (${rest.children.length} more)`));
        more.appendChild(rest);
        parts.push(more);
      } else {
        parts.push(rest);
      }
    }
    if (data.skipped) {
      parts.push(el("p", "fine", `${data.skipped} line${data.skipped === 1 ? "" : "s"} of this file can't be shown as fields: change ${data.skipped === 1 ? "it" : "them"} in Files.`));
    }
    const actions = el("div", "actions");
    actions.append(button("Reload", "", () => loadFile(holder, file)),
      button("Open in Files", "", () => openInFiles(file.path, data.writable)), save);
    bar.append(count, actions);
    parts.push(bar);
    if (!editable) {
      parts.push(el("p", "fine", can("admin") ? "This file is read-only here." : "Changing mod settings needs an admin login."));
    }
    holder.replaceChildren(...parts);
    onChange();
  }

  async function saveFile(holder, file, data, entries, error, note, save) {
    const values = {};
    for (const entry of entries) {
      if (!entry.row.classList.contains("changed")) continue;
      values[entry.field.key] = entry.read();
    }
    if (!Object.keys(values).length) return;
    say(error, null);
    save.disabled = true;
    try {
      const done = await api("PUT", "/api/mod-config", { path: file.path, values, mtime: data.mtime });
      await loadFile(holder, file);
      const when = data.applies === "reload" ? "It takes effect after /reload (Console tab) or a restart."
        : "It takes effect when the server restarts (Server tab).";
      const shown = holder.querySelector(".note");
      if (shown) say(shown, done.changed.length ? `Saved: ${done.changed.join(", ")}. ${when} The old file is in Files, history.` : "Nothing changed.");
    } catch (failure) {
      say(error, failure);
      save.disabled = false;
    }
  }

  // ---------------------------------------------------------------- the cards

  function card(mod) {
    const box = el("details", "box modcard");
    box.dataset.find = `${mod.title} ${mod.name} ${mod.files.map((f) => f.path).join(" ")}`.toLowerCase();
    const summary = el("summary");
    summary.append(el("span", "title", mod.title),
      el("span", "fine", mod.files.length === 1 ? mod.files[0].path : `${mod.files.length} files`));
    box.appendChild(summary);
    if (mod.about) box.appendChild(el("p", "fine", mod.about));
    const body = el("div", "stack");
    box.appendChild(body);
    let opened = false;
    box.addEventListener("toggle", () => {
      if (!box.open || opened) return;
      opened = true;
      for (const file of mod.files) {
        const section = el("section", "modfile");
        if (mod.files.length > 1) section.appendChild(el("h4", "mono", file.path));
        const holder = el("div");
        section.appendChild(holder);
        body.appendChild(section);
        if (file.format === "raw") {
          holder.append(el("p", "fine", "Not a format this page reads as a form."),
            button("Open in Files", "", () => openInFiles(file.path, true)));
        } else {
          loadFile(holder, file);
        }
      }
    });
    return box;
  }

  function filter() {
    const words = $("modcfg-search").value.trim().toLowerCase().split(/\s+/).filter(Boolean);
    for (const node of $("modcfg-list").children) {
      if (!node.dataset.find) continue;
      node.hidden = !words.every((w) => node.dataset.find.includes(w));
    }
  }

  async function load() {
    say($("modcfg-error"), null);
    if (!can("admin")) {
      say($("modcfg-error"), "Mod settings need an admin login.");
      return;
    }
    try {
      const data = await api("GET", "/api/mod-configs");
      state.mods = data.mods || [];
      const cards = state.mods.map(card);
      if (!cards.length) cards.push(el("p", "fine", "No config files yet: start the server once."));
      if (data.cut) cards.push(el("p", "fine", "There are more config files than this list shows: find the rest in Files."));
      $("modcfg-list").replaceChildren(...cards);
      state.loaded = true;
      filter();
    } catch (error) {
      say($("modcfg-error"), error);
    }
  }

  function show() {
    if (location.hash.slice(1) === "modcfg" && !state.loaded) load();
  }

  async function start() {
    try {
      const me = await api("GET", "/api/me");
      if (me.role in RANK) role = me.role;
    } catch {
      role = "moderator";   // the safe guess: the panel decides anyway
    }
    $("modcfg-search").addEventListener("input", filter);
    $("modcfg-reload").addEventListener("click", () => { state.loaded = false; load(); });
    window.addEventListener("hashchange", show);
    show();
  }

  start();
})();
