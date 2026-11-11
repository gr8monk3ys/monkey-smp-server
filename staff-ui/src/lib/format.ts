// Times, sizes and counts as the page says them (the same wording as the old panel.js and desk.js).

const MONTH_CLOCK = new Intl.DateTimeFormat(undefined, { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" });

/** Milliseconds from what the server sends: seconds or milliseconds since 1970, or ISO text. NaN when unreadable. */
export function toMs(value: unknown): number {
  if (value === null || value === undefined || value === "") return NaN;
  if (typeof value === "number") return value > 1e11 ? value : value * 1000;
  return Date.parse(String(value));
}

/** A time as the server sends it: "Nov 10, 4:05 PM", "never" for nothing, the text itself when unreadable. */
export function when(value: unknown): string {
  if (value === null || value === undefined || value === "") return "never";
  const ms = toMs(value);
  if (Number.isNaN(ms)) return String(value);
  return MONTH_CLOCK.format(new Date(ms));
}

/** "just now", "5 minutes ago", "3 hours ago", "2 days ago" for a number of seconds. */
export function ago(seconds: number): string {
  if (!Number.isFinite(seconds) || seconds < 60) return "just now";
  const minutes = Math.round(seconds / 60);
  if (minutes < 60) return `${plural(minutes, "minute")} ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 48) return `${plural(hours, "hour")} ago`;
  return `${plural(Math.round(hours / 24), "day")} ago`;
}

export function size(bytes: unknown): string {
  if (typeof bytes !== "number") return "";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1048576) return `${(bytes / 1024).toFixed(1)} KB`;
  if (bytes < 1073741824) return `${(bytes / 1048576).toFixed(1)} MB`;
  return `${(bytes / 1073741824).toFixed(1)} GB`;
}

export const plural = (n: number, word: string) => `${n} ${word}${n === 1 ? "" : "s"}`;

/** A player's name as Minecraft allows it. */
export const PLAYER_NAME = /^[A-Za-z0-9_]{3,16}$/;
