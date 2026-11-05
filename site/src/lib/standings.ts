// The public standings file (standings.json) and how the page reads it. No React in here, so the rules can be
// tested on their own (standings.test.ts). The file's shape is the one the server writes, once a week closes and
// every hour in between:
//
//   { version: 1, checked, season, week_closes, factions: [{ rank, name, points }],
//     last_week: null | { closed, factions: [...] } }
//
// Names, ranks and points only. Anything else in the file is never read, so it can never be shown.

export type Row = { rank: number; name: string; points: number };
export type Standings = {
  /** When the server wrote the file, ms since 1970. */
  checked: number;
  season: number;
  /** When this week's standings close, ms; null once the season's last week has closed. */
  closes: number | null;
  factions: Row[];
  last: { closed: number; factions: Row[] } | null;
};

/** Written every hour, so a file older than this has been missed twice: it says nothing about now. */
export const STALE_MS = 3 * 60 * 60_000;
/** A file dated further ahead than this is wrong (or the visitor's clock is): not shown. */
export const AHEAD_MS = 60 * 60_000;
/** More factions than a 30-player server can have: the file is not what it should be. */
const MAX_FACTIONS = 100;
/** Longer names are cut when shown. */
export const NAME_LENGTH = 48;
/** What a hidden or empty name shows as (the server writes null for a name staff have hidden). */
export const HIDDEN = "A faction";

const ISO = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(:\d{2}(\.\d+)?)?(Z|[+-]\d{2}:\d{2})$/;

function time(value: unknown): number {
  return typeof value === "string" && ISO.test(value) ? Date.parse(value) : NaN;
}

/** A table of factions, or null if any row of it is wrong: a table is shown whole or not at all. Ranks run from 1
 * in order. A tie shares a rank and its points, and the next rank is that row's place (1, 1, 3). Points never go up
 * down the table, and equal points can still rank apart: the tie-breaks are Cup points, then kills. */
function table(value: unknown): Row[] | null {
  if (!Array.isArray(value) || value.length > MAX_FACTIONS) return null;
  const rows: Row[] = [];
  for (const [i, item] of value.entries()) {
    if (!item || typeof item !== "object") return null;
    const { rank, name, points } = item as Record<string, unknown>;
    if (typeof rank !== "number" || !Number.isInteger(rank)) return null;
    if (typeof points !== "number" || !Number.isFinite(points) || points < 0 || points > 1_000_000) return null;
    if (name !== null && typeof name !== "string") return null;
    const before = rows[i - 1];
    if (!before && rank !== 1) return null;
    if (before && (rank === before.rank ? points !== before.points : rank !== i + 1 || points > before.points)) {
      return null;
    }
    rows.push({ rank, name: cleanName(name), points });
  }
  return rows;
}

/** The file, if it is a version 1 standings file all the way through; anything else is no file. */
export function parseStandings(data: unknown): Standings | null {
  if (!data || typeof data !== "object" || Array.isArray(data)) return null;
  const d = data as Record<string, unknown>;
  if (d.version !== 1) return null;
  const checked = time(d.checked);
  const closes = d.week_closes === null ? null : time(d.week_closes);
  if (isNaN(checked) || (closes !== null && isNaN(closes))) return null;
  if (typeof d.season !== "number" || !Number.isInteger(d.season) || d.season < 1 || d.season > 39) return null;
  const factions = table(d.factions);
  if (!factions) return null;
  let last: Standings["last"] = null;
  if (d.last_week !== null && d.last_week !== undefined) {
    if (typeof d.last_week !== "object" || Array.isArray(d.last_week)) return null;
    const week = d.last_week as Record<string, unknown>;
    const closed = time(week.closed);
    const rows = table(week.factions);
    if (isNaN(closed) || !rows) return null;
    last = { closed, factions: rows };
  }
  return { checked, season: d.season, closes, factions, last };
}

/** Whether the file can be shown at `now`: "ok", "stale" (written too long ago) or "ahead" (dated in the future). Once
 * the season's last week has closed, nothing more is coming: the final table stays up however old the file gets. */
export function freshness(file: Standings, now: number): "ok" | "stale" | "ahead" {
  const age = now - file.checked;
  if (age < -AHEAD_MS) return "ahead";
  return age > STALE_MS && file.closes !== null ? "stale" : "ok";
}

/** What a poll's answer leaves on show. A 5xx (a proxy reloading, say) says nothing about the file, so what was shown
 * stays, and goes stale by itself. Any other failure, or an answer that is no file (a 404 before the first one, a page
 * of HTML), is no standings. */
export function afterAnswer(shown: Standings | null, status: number, body: string | null): Standings | null {
  if (status >= 500) return shown;
  if (status < 200 || status >= 300 || body === null) return null;
  try {
    return parseStandings(JSON.parse(body));
  } catch {
    return null;
  }
}

// What tools/standings.py strips, in the same order, so the page holds up without it: controls, format characters
// (bidi marks among them, but not the emoji joiner), and the other characters that draw nothing.
const HIDDEN_CHARS = /(?!\u200d)[\p{Cc}\p{Cf}\p{Cs}\u034f\u115f\u1160\u17b4\u17b5\u180b-\u180f\u2065\u2800\u3164\ufe00-\ufe0e\uffa0\ufff0-\ufff8\u{e0000}-\u{e0fff}]/gu;
// Minecraft's formatting: a section sign and whatever follows it.
const FORMATTING = /§[\u200d\ufe0f]*[\s\S]?/gu;

/** A faction's name as plain text for the page: no hidden or formatting characters, spaces tidied, cut at
 * NAME_LENGTH characters, and "A faction" for a name that is null (hidden by staff) or has nothing left. The
 * page puts the result in a text node, never in markup. */
export function cleanName(name: string | null): string {
  if (name === null) return HIDDEN;
  const plain = name.replace(HIDDEN_CHARS, "").replace(FORMATTING, "").replace(/\s+/g, " ").trim();
  if (!plain) return HIDDEN;
  const chars = Array.from(plain);
  return chars.length > NAME_LENGTH ? chars.slice(0, NAME_LENGTH - 1).join("").trimEnd() + "…" : plain;
}

/** 1 -> "I", 2 -> "II": the way the site writes a season. */
export function roman(n: number): string {
  const digits: [number, string][] = [[10, "X"], [9, "IX"], [5, "V"], [4, "IV"], [1, "I"]];
  let out = "";
  for (const [value, letters] of digits) {
    while (n >= value) { out += letters; n -= value; }
  }
  return out;
}
