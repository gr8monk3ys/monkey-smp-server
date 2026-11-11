// The problems timeline: the last 24 hours as one axis, a lane each for crashes, stalls, the most frequent error
// groups and the gaps with no reading. staff.json keeps a group's first and last time and a count, not every
// moment, so a group draws as a span from first to last.
import type { ReactNode } from "react";
import { plural } from "../../lib/format";
import { Fine, Panel } from "../../ui/kit";

const DAY_S = 86400;
const LANES_OF_ERRORS = 4;
const GAP_S = 6 * 60;   // three missed readings in a row

interface Lane { label: string; about: string; kind: "bad" | "warn" | "sage" | "hint"; spans: [number, number][] }

const FILL = { bad: "fill-bad", warn: "fill-warn", sage: "fill-sage", hint: "fill-hint" } as const;

function Strip({ lane, start }: { lane: Lane; start: number }) {
  const x = (t: number) => Math.min(1000, Math.max(0, ((t - start) / DAY_S) * 1000));
  return (
    <svg className="block h-3 w-full" viewBox="0 0 1000 12" preserveAspectRatio="none" aria-hidden="true" shapeRendering="crispEdges">
      <rect className="fill-leaf-2" y={5} width={1000} height={2} />
      {lane.spans.map(([a, b], i) => {
        const left = x(a);
        const w = Math.max(6, x(b) - left);
        return <rect key={i} className={FILL[lane.kind]} x={Math.min(left, 1000 - w)} y={0} width={w} height={12} />;
      })}
    </svg>
  );
}

export function Timeline({ d }: { d: any }) {
  const end = Date.parse(d.checked) / 1000;
  const start = end - DAY_S;
  const inDay = (t: number) => Number.isFinite(t) && t >= start - 1 && t <= end + 1;
  const p = d.problems || {};
  const lanes: Lane[] = [];

  const crashes = (p.crashes || []).map((c: any) => Date.parse(c.when) / 1000).filter(inDay);
  lanes.push({ label: "Crashes", about: crashes.length ? plural(crashes.length, "crash") : "none", kind: "bad", spans: crashes.map((t: number) => [t, t]) });

  if (p.lag) {
    const a = Date.parse(p.lag.first) / 1000, b = Date.parse(p.lag.last) / 1000;
    lanes.push({ label: "Stalls", about: `${plural(p.lag.count, "stall")}, the worst ${(p.lag.worst / 1000).toFixed(1)} s`, kind: "warn",
      spans: Number.isFinite(a) && Number.isFinite(b) ? [[Math.max(a, start), Math.min(b, end)]] : [] });
  } else {
    lanes.push({ label: "Stalls", about: "none", kind: "warn", spans: [] });
  }

  const errors: any[] = (p.errors || []).slice().sort((a: any, b: any) => b.count - a.count).slice(0, LANES_OF_ERRORS);
  for (const e of errors) {
    const a = Date.parse(e.first) / 1000, b = Date.parse(e.last) / 1000;
    if (!Number.isFinite(a) || !Number.isFinite(b)) continue;
    lanes.push({ label: e.text, about: plural(e.count, "time"), kind: "sage", spans: [[Math.max(a, start), Math.min(b, end)]] });
  }

  // Gaps: no reading for three checks or more, so the server or the check was down. A check's step is the usual
  // distance between readings (2 minutes on the server), so a slower timer doesn't count every step as a gap.
  const rows: any[] = (d.history || []).filter((r: any[]) => r[0] >= start);
  const steps = rows.slice(1).map((r, i) => r[0] - rows[i][0]).sort((a, b) => a - b);
  const step = steps.length ? steps[Math.floor(steps.length / 2)] : GAP_S / 3;
  const gapS = Math.max(GAP_S, step * 3);
  const gaps: [number, number][] = [];
  let prev = start;
  for (const r of rows) {
    if (r[0] - prev > gapS) gaps.push([prev, r[0]]);
    prev = r[0];
  }
  if (rows.length) lanes.push({ label: "No reading", about: gaps.length ? plural(gaps.length, "gap") : "none", kind: "hint", spans: gaps });

  const axis: ReactNode = (
    <div className="flex justify-between text-xs text-sage" aria-hidden="true">
      <span>24 h ago</span><span>18 h</span><span>12 h</span><span>6 h</span><span>now</span>
    </div>
  );
  return (
    <Panel title="Problems over the day" meta="The last 24 hours">
      <ul className="m-0 flex list-none flex-col gap-2.5 p-0">
        {lanes.map((lane, i) => (
          <li key={i} className="min-w-0">
            <div className="flex items-baseline justify-between gap-3 text-sm">
              <span className="truncate font-semibold text-bone" title={lane.label}>{lane.label}</span>
              <span className="shrink-0 text-sage">{lane.about}</span>
            </div>
            <Strip lane={lane} start={start} />
          </li>
        ))}
      </ul>
      {axis}
      <Fine>The server's log keeps each problem's first and last time and a count, so a bar runs from the first to the last; it doesn't mean the problem lasted the whole time.</Fine>
    </Panel>
  );
}
