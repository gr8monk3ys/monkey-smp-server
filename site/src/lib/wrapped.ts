// Season Wrapped (tools/wrapped.py writes public/wrapped/season-<n>/): which seasons have one, read when the site
// is built, so the footer links the newest only once it exists.
import { existsSync, readdirSync } from "node:fs";
import path from "node:path";

const ROMAN = ["", "I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X", "XI", "XII"];

/** The newest season with a Wrapped index in public/, as a footer link; null while there is none. */
export function newestWrapped(dir = path.join(process.cwd(), "public", "wrapped")): { label: string; href: string } | null {
  let seasons: number[] = [];
  try {
    seasons = readdirSync(dir)
      .map((name) => /^season-(\d+)$/.exec(name))
      .filter((m): m is RegExpExecArray => m !== null && existsSync(path.join(dir, m[0], "index.html")))
      .map((m) => Number(m[1]));
  } catch {
    return null;
  }
  if (!seasons.length) return null;
  const n = Math.max(...seasons);
  return { label: `Season ${ROMAN[n] || n} Wrapped`, href: `/wrapped/season-${n}/` };
}
