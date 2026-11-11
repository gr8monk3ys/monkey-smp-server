// The Reports tab's wording and the week as Discord messages (the old reports.js).

export const LEVELS: Record<string, string> = { clear: "clear in the logs", likely: "likely", unclear: "unclear: worth a look" };
const DISCORD_MAX = 1990;     // Discord's limit is 2,000 characters a message

/** "2026-11-02 00:00" as "Mon 2 Nov". */
export function day(text: string | undefined): string {
  const m = /^(\d{4})-(\d\d)-(\d\d)/.exec(text || "");
  if (!m) return text || "";
  const d = new Date(Date.UTC(+m[1], +m[2] - 1, +m[3]));
  return d.toLocaleDateString("en-GB", { weekday: "short", day: "numeric", month: "short", timeZone: "UTC" });
}

export const span = (report: any) => `${day(report.from)} to ${day(report.to)}, Pacific`;

/** A cell's other levels, as ", also 3 unclear". */
export function also(cell: any): string {
  const rest = Object.entries(cell.also || {}).map(([level, n]) => `${n} ${level}`);
  return rest.length ? `, also ${rest.join(", ")}` : "";
}

const pad = (text: unknown, width: number) => {
  const t = String(text);
  return t.length > width ? `${t.slice(0, width - 1)}~` : t.padEnd(width);
};

/** The week as Discord messages: code blocks of fixed-width lines, each message under 2,000 characters. */
export function discord(report: any): string[] {
  const top = [`Monkey SMP rule check ${report.week} (${span(report)})`,
    "Only a report: look at the rows on the staff page before acting.",
    "clear = plain in the logs, likely = probably, unclear = worth a look"];
  if (report.partial) top.push(`Not a whole week: ${report.partial}`);
  const lines: string[] = [];
  for (const p of report.players) {
    for (const c of report.checks) {
      const cell = p.cells[c.id];
      if (cell) lines.push(`${pad(p.name, 17)}${pad(c.rule, 13)}${pad(`${cell.count} ${c.title}`, 30)}${cell.level}${also(cell)}`);
    }
  }
  if (!lines.length) lines.push("Nobody: every check came back clean.");
  const clean = (report.clean || []).map((c: any) => `${c.title} (${c.rule})`).join(", ");
  const tail = clean ? [`Checked and clean: ${clean}`] : [];
  const messages: string[] = [];
  let body: string[] = [];
  const wrap = (text: string, rows: string[]) => `${text}\n\`\`\`\n${rows.join("\n")}\n\`\`\``;
  let head = top.join("\n");
  for (const line of lines) {
    if (body.length && wrap(head, [...body, line]).length > DISCORD_MAX) {
      messages.push(wrap(head, body));
      head = `${report.week}, continued`;
      body = [];
    }
    body.push(line);
  }
  messages.push(wrap(head, body));
  for (const extra of tail) {
    const last = messages.length - 1;
    if (`${messages[last]}\n${extra}`.length <= DISCORD_MAX) messages[last] += `\n${extra}`;
    else messages.push(extra.slice(0, DISCORD_MAX));
  }
  return messages;
}
