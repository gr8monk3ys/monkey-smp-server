// The dashboard's top row (one card per number, with the last 24 hours as a small line where staff.json's history has
// it) and the hour-by-day heatmap of players online. SVG with attributes only: the policy refuses a style attribute.
import type { ReactNode } from "react";
import { LOW_DISK, agoMs } from "../../lib/status";
import { Mark, Panel, cx, type MarkKind } from "../../ui/kit";

type Row = any[];   // [time (s), avg ms, p95 ms, players, memory %, cpu %]
const DAY_S = 86400;
const ok = (v: unknown): v is number => typeof v === "number" && Number.isFinite(v);

/** The readings of the last 24 hours (the history keeps about that much). */
export const lastDay = (d: any): Row[] => {
  const rows: Row[] = d.history || [];
  const end = rows.length ? rows[rows.length - 1][0] : 0;
  return rows.filter((r) => r[0] > end - DAY_S);
};

/** Ticks a second from a reading's average tick time: the game runs 20 a second at most. */
const tpsOf = (avg: number) => Math.min(20, 1000 / Math.max(avg, 1e-6));
const tpsKind = (tps: number): MarkKind => (tps >= 19.5 ? "good" : tps >= 15 ? "busy" : "slow");
const KIND_TEXT: Record<MarkKind, string> = { good: "text-ok", busy: "text-warn", slow: "text-bad", off: "text-bone-2", unknown: "text-bone-2" };

/** A small line of one number over the readings; empty when there are fewer than two. */
function Spark({ values, top, label }: { values: (number | null)[]; top?: number; label: string }) {
  const known = values.filter(ok);
  if (known.length < 2) return <p className="mt-2 text-xs text-hint">The line shows after two readings.</p>;
  const hi = top ?? Math.max(...known, 1);
  const lo = top === undefined ? Math.min(...known, 0) : 0;
  const n = values.length;
  // Break the line where a reading is missing, so a gap doesn't look like a straight run.
  const parts: string[] = [];
  let run: string[] = [];
  values.forEach((v, i) => {
    if (!ok(v)) {
      if (run.length) parts.push(run.join(" "));
      run = [];
      return;
    }
    const x = n === 1 ? 0 : (i / (n - 1)) * 100;
    const y = 22 - ((v - lo) / Math.max(hi - lo, 1e-6)) * 20;
    run.push(`${x.toFixed(2)},${y.toFixed(2)}`);
  });
  if (run.length) parts.push(run.join(" "));
  return (
    <svg className="mt-2 block h-8 w-full" viewBox="0 0 100 24" preserveAspectRatio="none" role="img" aria-label={label}>
      <line className="stroke-leaf-2" x1={0} x2={100} y1={23} y2={23} strokeWidth={1} vectorEffect="non-scaling-stroke" />
      {parts.map((p, i) => (
        <polyline key={i} className="fill-none stroke-sage" points={p} strokeWidth={1.5} vectorEffect="non-scaling-stroke" strokeLinejoin="round" />
      ))}
    </svg>
  );
}

function Card({ label, value, unit, small, kind, children }: { label: string; value: ReactNode; unit?: string; small?: ReactNode; kind?: MarkKind; children?: ReactNode }) {
  return (
    <div className="panel flex min-w-0 flex-col p-3!">
      <dt className="text-sm text-sage">{label}</dt>
      <dd className="m-0 flex min-w-0 flex-1 flex-col">
        <div className="flex flex-wrap items-baseline gap-x-1.5">
          {kind && <Mark kind={kind} className="self-center" />}
          <span className={cx("text-2xl leading-tight font-bold wrap-anywhere", kind ? KIND_TEXT[kind] : "text-bone")}>{value}</span>
          {unit && <span className="text-sm text-sage">{unit}</span>}
        </div>
        {small && <small className="block text-sm text-sage">{small}</small>}
        <div className="mt-auto">{children}</div>
      </dd>
    </div>
  );
}

export function Cards({ d, now }: { d: any; now: number }) {
  const rows = lastDay(d);
  const cards: ReactNode[] = [];

  if (d.players) {
    const peak = Math.max(0, ...rows.map((r) => r[3]).filter(ok));
    cards.push(
      <Card key="players" label="Players online" value={String(d.players.count)} unit={`of ${d.players.max}`} small={rows.length ? `Most at once today: ${peak}` : undefined}>
        <Spark values={rows.map((r) => (ok(r[3]) ? r[3] : null))} label="Players online over the last 24 hours" />
      </Card>,
    );
  }
  if (d.tick) {
    const tps = d.tick.tps;
    cards.push(
      <Card key="tps" label="Ticks a second" value={tps.toFixed(1)} unit={`of ${Math.round(d.tick.target)}`} kind={tpsKind(tps)}
        small={`${d.tick.avg.toFixed(1)} ms a tick`}>
        <Spark values={rows.map((r) => (ok(r[1]) ? tpsOf(r[1]) : null))} top={20} label="Ticks a second over the last 24 hours, worked out from each reading's time per tick" />
      </Card>,
    );
  }
  const mem = d.host && d.host.memory;
  if (mem && mem.total) {
    const share = (mem.total - mem.available) / mem.total;
    cards.push(
      <Card key="mem" label="Memory in use" value={String(Math.round(share * 100))} unit="%" small={`of ${Math.round(mem.total / 1048576)} GB`}>
        <Spark values={rows.map((r) => (ok(r[4]) ? r[4] : null))} top={100} label="Memory in use over the last 24 hours" />
      </Card>,
    );
  }
  const disk = d.host && d.host.disk;
  if (disk && disk.total) {
    const free = disk.free / disk.total;
    const kind: MarkKind = free < 0.05 ? "slow" : free < LOW_DISK ? "busy" : "good";
    cards.push(
      <Card key="disk" label="Disk free" value={String(Math.round(disk.free / 1073741824))} unit={`of ${Math.round(disk.total / 1073741824)} GB`} kind={kind}
        small="The history keeps no disk readings, so there is no line.">
        <svg className="mt-2 block h-1.5 w-full" viewBox="0 0 100 6" preserveAspectRatio="none" aria-hidden="true" shapeRendering="crispEdges">
          <rect className="fill-leaf-2" width={100} height={6} />
          <rect className={kind === "slow" ? "fill-bad" : kind === "busy" ? "fill-warn" : "fill-sage"} width={Math.min(100, (1 - free) * 100)} height={6} />
        </svg>
      </Card>,
    );
  }
  const backups = d.backups || {};
  const offsite = ({ on: ["good", "On"], failing: ["slow", "Failing"], "not set up": ["busy", "Not set up"] } as Record<string, [MarkKind, string]>)[backups.offsite] || ["unknown", "Unknown"];
  const local = backups.local ? Date.parse(backups.local) : NaN;
  cards.push(
    <Card key="backup" label="Off-site backups" value={offsite[1]} kind={offsite[0]}
      small={Number.isFinite(local) ? `Copy before the last update: ${agoMs(now - local)}` : "No copy from before an update"} />,
  );
  const box = d.container;
  cards.push(
    <Card key="up" label={box && box.state === "running" ? "Running for" : "Container"} value={box ? (box.state === "running" && box.uptime ? box.uptime : box.state) : "Unknown"}
      kind={box ? (box.state === "running" ? "good" : "off") : "unknown"} small={d.release ? `Release ${d.release}` : undefined} />,
  );

  return <dl className="m-0 grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6" aria-label="The server at a glance">{cards}</dl>;
}

const DAY = new Intl.DateTimeFormat(undefined, { weekday: "short" });

/** Players online by hour (columns) and day (rows), the average of that hour's readings. */
export function Heatmap({ d }: { d: any }) {
  const rows: Row[] = d.history || [];
  const cells = new Map<string, { sum: number; n: number }>();
  const days: string[] = [];
  const dayLabel = new Map<string, string>();
  for (const r of rows) {
    if (!ok(r[3])) continue;
    const at = new Date(r[0] * 1000);
    const day = `${at.getFullYear()}-${at.getMonth()}-${at.getDate()}`;
    if (!dayLabel.has(day)) {
      days.push(day);
      dayLabel.set(day, DAY.format(at));
    }
    const key = `${day}|${at.getHours()}`;
    const c = cells.get(key) || { sum: 0, n: 0 };
    c.sum += r[3];
    c.n += 1;
    cells.set(key, c);
  }
  const shown = days.slice(-7);
  const top = Math.max(1, ...[...cells.values()].map((c) => c.sum / c.n));
  const cell = 14, gap = 2, left = 34, head = 16;
  const width = left + 24 * (cell + gap);
  const height = head + shown.length * (cell + gap);
  return (
    <Panel title="When people play" meta="Players online, by hour">
      {shown.length ? (
        <>
          <svg className="block h-auto w-full max-w-[42rem]" viewBox={`0 0 ${width} ${height}`} role="img"
            aria-label={`Average players online for each hour, over ${shown.length === 1 ? "one day" : `${shown.length} days`}. The most in one hour: ${top.toFixed(1)}.`}>
            {[0, 6, 12, 18].map((h) => (
              <text key={h} className="fill-sage text-[12px]" x={left + h * (cell + gap)} y={11}>{`${h}:00`}</text>
            ))}
            {shown.map((day, i) => (
              <g key={day}>
                <text className="fill-sage text-[12px]" x={0} y={head + i * (cell + gap) + 11}>{dayLabel.get(day)}</text>
                {Array.from({ length: 24 }, (_, h) => {
                  const c = cells.get(`${day}|${h}`);
                  const x = left + h * (cell + gap);
                  const y = head + i * (cell + gap);
                  if (!c) return <rect key={h} className="fill-none stroke-leaf-2" x={x + 0.5} y={y + 0.5} width={cell - 1} height={cell - 1} />;
                  const avg = c.sum / c.n;
                  return (
                    <rect key={h} className={avg > 0 ? "fill-sage" : "fill-leaf-2"} fillOpacity={avg > 0 ? 0.25 + 0.75 * (avg / top) : 1} x={x} y={y} width={cell} height={cell}>
                      <title>{`${dayLabel.get(day)}, ${h}:00: ${avg.toFixed(1)} on average`}</title>
                    </rect>
                  );
                })}
              </g>
            ))}
          </svg>
          <p className="text-sm text-sage">
            {`Brighter means more players. An outlined square has no reading. The status history keeps about a day, so this shows ${shown.length === 1 ? "one day" : `${shown.length} days`}; it fills in as the history grows.`}
          </p>
        </>
      ) : (
        <p className="text-sage">No readings yet. This fills in as the status history grows.</p>
      )}
    </Panel>
  );
}
