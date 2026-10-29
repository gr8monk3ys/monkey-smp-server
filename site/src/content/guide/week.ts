// A week on the server (the guide's #week): Monday to Friday across the top with the omen band under them,
// Saturday and Sunday standing the full height at the end. Times are Pacific. Keep it in step with
// tools/season_calendar.py, tools/drops.py and tools/omens.py.
export type Day = {
  name: string;
  /** "omens" sets the block in the shade (guide.css); "sat" and "sun" mark the weekend. */
  place?: "omens" | "sat" | "sun";
  lines: { at?: string; text: string; quiet?: boolean }[];
};

const drop = { at: "6–10 PM", text: "A supply drop, once 4 or more are on." };

export const week: Day[] = [
  { name: "Monday", lines: [{ at: "12 AM", text: "Three new challenges: one solo, one for factions, one exploring." }, drop] },
  { name: "Tuesday", lines: [drop] },
  { name: "Wednesday", lines: [drop] },
  { name: "Thursday", lines: [drop] },
  { name: "Friday", lines: [{ text: "No drop. Build, trade, get ready for Saturday.", quiet: true }] },
  {
    name: "Omens", place: "omens",
    lines: [{ text: "One or two weekday evenings, with no warning: a Blood Moon, a Meteor, a Truce Hour or a Hunted player." }],
  },
  {
    name: "Saturday", place: "sat",
    lines: [{ at: "6 PM", text: "The week's event: a Faction Raid, Arena Glory, a Build Battle, or the border breaking open." }],
  },
  {
    name: "Sunday", place: "sun",
    lines: [{ at: "7 PM", text: "The week's faction standings close and go up in the Discord. Wars end." }],
  },
];
