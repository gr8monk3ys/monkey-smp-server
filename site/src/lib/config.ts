// The site's settings, read from site/config.json when the site is built. config.json is the one place the links,
// the server address and the launch time live; tools/site_links.py checks it from the Python side.
import settings from "@config";

export type Config = {
  ADDRESS: string;
  DISCORD_INVITE: string;
  /** The Tebex webstore. Empty until the store can take payments and run its commands (docs/LIVE.md). */
  STORE_URL: string;
  MODPACK_URL: string;
  INSTALLER_URL: string;
  MAP_URL: string;
  /** When the season opens: ISO 8601 with its offset. */
  LAUNCH_AT: string;
};

export const config: Config = settings;

/** The settings a page can link to. */
export type LinkKey = Exclude<keyof Config, "ADDRESS" | "LAUNCH_AT">;

export const SITE_URL = "https://monkeysmp.lscaturchio.xyz";

/** What a link not set yet says (tools/site_links.py's SOON). */
export const SOON = "Coming soon: ask in the Discord";

/** Where a link goes, and its title: a link whose URL isn't set yet points at the Discord and says so. */
export function target(key: LinkKey): { href: string; title?: string } {
  const url = config[key];
  if (url) return { href: url };
  if (key !== "DISCORD_INVITE" && config.DISCORD_INVITE) return { href: config.DISCORD_INVITE, title: SOON };
  return { href: "#" };
}

/** True once the store is open (STORE_URL is set). */
export const storeOpen = Boolean(config.STORE_URL);

const DAYS = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"];
const MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
  "November", "December"];

type Local = { year: number; month: number; day: number; weekday: number; hour: number; minute: number };

function local(when: Date, timeZone: string): Local {
  const parts = Object.fromEntries(
    new Intl.DateTimeFormat("en-US", {
      timeZone, year: "numeric", month: "numeric", day: "numeric", hour: "numeric", minute: "numeric",
      hourCycle: "h23",
    }).formatToParts(when).map((p) => [p.type, p.value]),
  );
  const [year, month, day] = [Number(parts.year), Number(parts.month), Number(parts.day)];
  return { year, month, day, weekday: new Date(Date.UTC(year, month - 1, day)).getUTCDay(),
    hour: Number(parts.hour), minute: Number(parts.minute) };
}

/** '5 PM', '8:30 PM', '12 AM' (tools/season_calendar.py's clock). */
function clock(t: Local): string {
  const hour = t.hour % 12 || 12;
  const minutes = t.minute ? `:${String(t.minute).padStart(2, "0")}` : "";
  return `${hour}${minutes} ${t.hour < 12 ? "AM" : "PM"}`;
}

/** The launch in words, exactly as tools/season_calendar.py's words() puts it: {date} 'Saturday 7 November
 * 2026', {pacific} '5 PM Pacific' and {eastern} '8 PM Eastern' (with the day when it is already the next one
 * there). tools/site_links.py --built checks every built page against the Python. */
export function launchWords(when: Date = new Date(config.LAUNCH_AT)): Record<"date" | "pacific" | "eastern", string> {
  const west = local(when, "America/Los_Angeles");
  const east = local(when, "America/New_York");
  let eastern = `${clock(east)} Eastern`;
  if (east.day !== west.day || east.month !== west.month || east.year !== west.year) {
    eastern = `${DAYS[east.weekday]} ${eastern}`;
  }
  return {
    date: `${DAYS[west.weekday]} ${west.day} ${MONTHS[west.month - 1]} ${west.year}`,
    pacific: `${clock(west)} Pacific`,
    eastern,
  };
}

/** A launch template ('{date} at {pacific} ({eastern})') filled in. */
export function sayLaunch(template: string): string {
  const words = launchWords();
  return template.replace(/\{(date|pacific|eastern)\}/g, (_, key: keyof typeof words) => words[key]);
}

/** '29 October 2026' from '2026-10-29'. */
export function dayLabel(iso: string): string {
  const [year, month, day] = iso.split("-").map(Number);
  return `${day} ${MONTHS[month - 1]} ${year}`;
}
