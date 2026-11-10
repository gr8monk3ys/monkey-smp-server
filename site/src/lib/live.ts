// Which of the server's own data packs run on the live server this season, read from site/live-packs.json when the
// site is built. A pack's features are shown only while it is "on": "off" and "unknown" both mean the site can't
// say it runs. tools/live_packs.py checks the built pages against the same file.
import list from "@live-packs";

export type Pack = keyof typeof list.packs;
export type PackState = "on" | "off" | "unknown";

const states = list.packs as Record<Pack, PackState>;

/** True when the pack runs on the live server now. */
export function running(pack: Pack): boolean {
  return states[pack] === "on";
}

/** What each pack gives players, in their words, for the "not running now" notes. */
export const NAMES: Record<Pack, string> = {
  "monkey-armor-repair": "diamond repair of netherite armor",
  "monkey-boss": "the border boss",
  "monkey-camera": "the creator camera",
  "monkey-clips": "clip markers",
  "monkey-drops": "supply drops",
  "monkey-events": "staff events (the arena, Faction Raids, the Cup)",
  "monkey-finale": "the season finale",
  "monkey-firsts": "Server Firsts",
  "monkey-lore": "the season story",
  "monkey-nights": "event nights",
  "monkey-no-netherite-armor": "the Netherite armor lock",
  "monkey-npcs": "the spawn NPCs (the Guide, the Town Crier)",
  "monkey-omens": "omens",
  "monkey-outposts": "outposts",
  "monkey-rules": "the welcome screen and PvP grace for new players",
  "monkey-sieges": "outpost sieges",
  "monkey-standings": "the weekly standings (bounties, wars, pacts)",
  "monkey-wardrobe": "the wardrobe (skins, challenges, the first-week quest)",
};

/** The packs of `packs` that aren't running, in the order given. */
export function notRunning(packs: Pack[]): Pack[] {
  return packs.filter((pack) => !running(pack));
}

/** "a", "a and b", "a, b and c". */
export function sayList(items: string[]): string {
  if (items.length < 2) return items.join("");
  return `${items.slice(0, -1).join(", ")} and ${items[items.length - 1]}`;
}

/** The text of a "not running now" note for `packs` ("" when they all run). */
export function offText(packs: Pack[]): string {
  const off = notRunning(packs);
  if (!off.length) return "";
  // The names have commas of their own, so a longer list is split with semicolons.
  const names = off.map((pack) => NAMES[pack]);
  const said = names.length > 2 ? `${names.slice(0, -1).join("; ")}; and ${names[names.length - 1]}` : sayList(names);
  return `Not running on the server right now: ${said}.`;
}
