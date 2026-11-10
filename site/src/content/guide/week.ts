// A week on the server (/guide/week): one row per day, Monday to Sunday, with the omens between Friday and
// Saturday. Times are Pacific. Keep it in step with tools/season_calendar.py, tools/drops.py and tools/omens.py.
// A line with a `pack` shows only while that data pack runs (site/live-packs.json), and a day with no line left
// isn't shown.
import { type Pack, running } from "@/lib/live";

export type Day = {
  name: string;
  /** "omens" sets the row in the shade (guide.css). */
  place?: "omens";
  lines: { at?: string; text: string; quiet?: boolean; pack?: Pack }[];
};

const drop = { at: "6–10 PM", text: "A supply drop, once 4 or more are on.", pack: "monkey-drops" as const };

/** "a", "a or b", "a, b, or c". */
function sayOr(items: string[]): string {
  return items.length < 3 ? items.join(" or ") : `${items.slice(0, -1).join(", ")}, or ${items[items.length - 1]}`;
}

/** Saturday's events, those whose pack runs. */
const saturday = ([["a Faction Raid", "monkey-events"], ["Arena Glory", "monkey-events"],
  ["a Build Battle", "monkey-nights"], ["the border breaking open"]] as [string, Pack?][])
  .filter(([, pack]) => !pack || running(pack)).map(([words]) => words);

const days: Day[] = [
  {
    name: "Monday",
    lines: [{ at: "12 AM", text: "Three new challenges: one solo, one for factions, one exploring.", pack: "monkey-wardrobe" }, drop],
  },
  { name: "Tuesday", lines: [drop] },
  { name: "Wednesday", lines: [drop] },
  { name: "Thursday", lines: [drop] },
  { name: "Friday", lines: [{ text: "No drop. Build, trade, get ready for Saturday.", quiet: true, pack: "monkey-drops" }] },
  {
    name: "Omens", place: "omens",
    lines: [{
      text: "One or two weekday evenings, with no warning: a Blood Moon, a Meteor, a Truce Hour or a Hunted player.",
      pack: "monkey-omens",
    }],
  },
  {
    name: "Saturday",
    lines: [{ at: "6 PM", text: `The week's event: ${sayOr(saturday)}.` }],
  },
  {
    name: "Sunday",
    lines: [{
      at: "7 PM", text: "The week's faction standings close and go up on the standings page and in the Discord. Wars end.",
      pack: "monkey-standings",
    }],
  },
];

export const week: Day[] = days
  .map((day) => ({ ...day, lines: day.lines.filter((line) => !line.pack || running(line.pack)) }))
  .filter((day) => day.lines.length);
