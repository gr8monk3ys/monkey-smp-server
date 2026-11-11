// The Over time panel: three line charts drawn as SVG with attributes only (the policy refuses a style attribute),
// the range buttons and the readings as a table. One crosshair moves over all three charts, so their times line up.
import { useEffect, useRef, useState, type KeyboardEvent, type PointerEvent } from "react";
import { plural } from "../../lib/format";
import { Fine, Fold, TableScroll, Toggles, cx } from "../../ui/kit";

const READING_S = 120;
const LINE_LABELS: Record<string, string> = { avg: "Avg", p95: "P95", memory: "Mem", load: "CPU" };   // short: the right margin is 34 px

const CLOCK = new Intl.DateTimeFormat(undefined, { hour: "numeric", minute: "2-digit" });
export const DAY_CLOCK = new Intl.DateTimeFormat(undefined, { weekday: "short", hour: "numeric", minute: "2-digit" });
const HOUR = new Intl.DateTimeFormat(undefined, { hour: "numeric" });

type Row = any[];   // [time (s), avg ms, p95 ms, players, memory %, cpu %]; the last two are missing in old readings
const one = (n: number) => n.toFixed(1);
const missing = (value: unknown) => value === null || value === undefined;

// The three lines' looks (the series' stroke, the key's swatch and the crosshair's dot).
const LINES: Record<string, { stroke: string; fill: string; bg: string }> = {
  "line-1": { stroke: "stroke-line-1", fill: "fill-line-1", bg: "bg-line-1" },
  "line-2": { stroke: "stroke-line-2", fill: "fill-line-2", bg: "bg-line-2" },
  "line-solo": { stroke: "stroke-sage", fill: "fill-sage", bg: "bg-sage" },
};

interface Series { index: number; name: string; key?: string; line: string }
/** A moment on a chart: a crash (a coral line), a stall the log recorded (an amber tick at the top), or the day's peak
 * (a square on the line with its number). */
export interface Marker { t: number; kind: "crash" | "stall" | "peak"; label: string; v?: number }
interface Spec {
  height: number;
  unit: string;
  yTop: (rows: Row[]) => number;
  yTicks: (top: number) => number[];
  series: Series[];
  format: (n: number) => string;
  step: boolean;
  limit?: number;
  limitLabel?: string;
  machine?: boolean;
  what: string;
}

// The stretches of a series with readings; a missing reading or a long wait breaks the line rather than joining across it.
function segments(rows: Row[], index: number): Row[][] {
  const out: Row[][] = [];
  let run: Row[] = [];
  let last: number | null = null;
  for (const r of rows) {
    if (missing(r[index]) || (last !== null && r[0] - last > READING_S * 3)) {
      if (run.length) out.push(run);
      run = [];
    }
    if (!missing(r[index])) {
      run.push(r);
      last = r[0];
    }
  }
  if (run.length) out.push(run);
  return out;
}

// The stretches with no reading, between the readings on each side. `machine`: the machine's own numbers, which are
// read while the server is off too, so only a reading that has neither of them (or none at all) is a gap.
function gaps(rows: Row[], machine?: boolean): [number, number][] {
  const out: [number, number][] = [];
  let from: number | null = null;
  let previous: number | null = null;
  for (const r of rows) {
    const empty = machine ? missing(r[4]) && missing(r[5]) : r[3] === null && r[1] === null;
    if (empty && from === null) from = previous === null ? r[0] : previous;
    if (!empty) {
      if (from !== null) {
        out.push([from, r[0]]);
        from = null;
      } else if (previous !== null && r[0] - previous > READING_S * 3) {
        out.push([previous, r[0]]);
      }
    }
    previous = r[0];
  }
  if (from !== null && previous !== null) out.push([from, previous]);
  return out;
}

function timeTicks(start: number, end: number, hours: number, narrow: boolean) {
  const every = ({ 1: 15, 6: narrow ? 120 : 60, 24: narrow ? 480 : 240 } as Record<number, number>)[hours];
  const ticks: number[] = [];
  const t = new Date(start * 1000);
  t.setMinutes(Math.floor(t.getMinutes() / 15) * 15, 0, 0);
  for (; t.getTime() / 1000 <= end; t.setMinutes(t.getMinutes() + 15)) {
    const minutes = t.getHours() * 60 + t.getMinutes();
    if (t.getTime() / 1000 >= start && minutes % every === 0) ticks.push(t.getTime() / 1000);
  }
  return { ticks, every };
}

function specs(data: any): Record<string, Spec> {
  return {
    tick: {
      // Capped, or one huge spike would flatten the rest of the day against the floor: the line pins at the top, and
      // the readout and the table still say the real number.
      height: 190, unit: " ms",
      yTop: (rows) => Math.min(250, Math.max(60, Math.ceil(Math.max(0, ...rows.map((r) => r[2] || 0)) * 1.1 / 10) * 10)),
      yTicks: (top) => (top <= 60 ? [0, 25, 50] : top <= 120 ? [0, 50, 100] : [0, 50, 100, 200].filter((n) => n < top)),
      series: [{ index: 2, name: "P95", key: "p95", line: "line-2" }, { index: 1, name: "Average", key: "avg", line: "line-1" }],
      format: one, step: false, limit: 50,
      what: "Time per tick",
    },
    players: {
      height: 120, unit: "",
      yTop: (rows) => Math.max((data.players && data.players.max) || 30, ...rows.map((r) => r[3] || 0)),
      yTicks: (top) => [0, Math.round(top / 3), Math.round(top * 2 / 3), top],
      series: [{ index: 3, name: "Players", line: "line-solo" }],
      format: String, step: true,
      what: "Players online",
    },
    machine: {
      // Both are shares of the machine's whole, so the scale is always 0 to 100.
      height: 150, unit: "%", yTop: () => 100, yTicks: () => [0, 50],
      series: [{ index: 5, name: "CPU in use", key: "load", line: "line-2" }, { index: 4, name: "Memory in use", key: "memory", line: "line-1" }],
      format: (n) => String(Math.round(n)), step: false, limit: 100, limitLabel: "All of it", machine: true,
      what: "The machine's memory and CPU in use",
    },
  };
}

/** Crashes and the stalls the log recorded, from staff.json's problems. The log keeps a stall's first and last time
 * and a count, not every one, so those two are marked. */
function healthMarks(data: any): Marker[] {
  const p = data.problems || {};
  const out: Marker[] = [];
  for (const c of p.crashes || []) {
    const t = Date.parse(c.when) / 1000;
    if (Number.isFinite(t)) out.push({ t, kind: "crash", label: "Crash" });
  }
  if (p.lag) {
    const first = Date.parse(p.lag.first) / 1000;
    const last = Date.parse(p.lag.last) / 1000;
    if (Number.isFinite(first)) out.push({ t: first, kind: "stall", label: p.lag.count > 1 && last !== first ? "Stalls from" : "Stall" });
    if (Number.isFinite(last) && last !== first) out.push({ t: last, kind: "stall", label: "last stall" });
  }
  return out;
}

/** The most players at once in the readings shown (the latest such reading), if anyone was on. */
function peakMark(rows: Row[]): Marker | null {
  let best: Row | null = null;
  for (const r of rows) if (!missing(r[3]) && (best === null || r[3] >= best[3])) best = r;
  return best && best[3] > 0 ? { t: best[0], kind: "peak", label: `Peak ${best[3]}`, v: best[3] } : null;
}

function useWidth() {
  const ref = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(0);
  useEffect(() => {
    const node = ref.current;
    if (!node) return;
    const watch = new ResizeObserver(() => setWidth(node.clientWidth));
    watch.observe(node);
    setWidth(node.clientWidth);
    return () => watch.disconnect();
  }, []);
  return [ref, width] as const;
}

interface Shared {
  rows: Row[];
  start: number;
  end: number;
  hours: number;
  hover: number | null;
  keyed: boolean;
  point: (t: number | null, keyed: boolean) => void;
}

function Chart({ spec, title, caption, shared, marks = [] }: { spec: Spec; title: string; caption?: string; shared: Shared; marks?: Marker[] }) {
  const [ref, width] = useWidth();
  const { rows, start, end, hours, hover, keyed, point } = shared;
  const shownMarks = marks.filter((m) => m.t >= start && m.t <= end);
  // The same sides on every chart, so their times line up under the crosshair; room on top for the marks' words.
  const pad = { left: 30, right: 34, top: shownMarks.some((m) => m.kind !== "peak") ? 20 : 8, bottom: 22 };
  const height = spec.height + pad.top - 8;
  const top = spec.yTop(rows);
  const x = (t: number) => pad.left + (t - start) / (end - start) * (width - pad.left - pad.right);
  const y = (v: number) => height - pad.bottom - Math.min(v, top) / top * (height - pad.top - pad.bottom);

  const picked = hover === null ? null : rows.find((r) => r[0] === hover) || null;
  const shown = picked || (rows.length ? rows[rows.length - 1] : null);
  const latest = rows.length ? rows[rows.length - 1] : null;
  const words = spec.series.map((s) => `${s.name} ${latest && !missing(latest[s.index]) ? spec.format(latest[s.index]) + spec.unit : "no reading"}`);
  const label = `${spec.what}, the last ${plural(hours, "hour")}. Latest: ${words.join(", ")}. The table below has every reading. Arrow keys step through them.`;

  const onMove = (e: PointerEvent<SVGSVGElement>) => {
    const box = e.currentTarget.getBoundingClientRect();
    const t = start + ((e.clientX - box.left) / box.width * width - pad.left) / (width - pad.left - pad.right) * (end - start);
    let best: number | null = null;
    for (const r of rows) if (best === null || Math.abs(r[0] - t) < Math.abs(best - t)) best = r[0];
    point(best, false);
  };
  const onKey = (e: KeyboardEvent<SVGSVGElement>) => {
    if (e.key === "Escape") {
      point(null, false);
      return;
    }
    const by = ({ ArrowLeft: -1, ArrowRight: 1 } as Record<string, number>)[e.key];
    if (!by || !rows.length) return;
    e.preventDefault();
    const at = hover === null ? rows.length - 1 : rows.findIndex((r) => r[0] >= hover);
    point(rows[Math.min(rows.length - 1, Math.max(0, at + by))][0], true);
  };

  const { ticks, every } = timeTicks(start, end, hours, width < 480);
  const ends: { key: string; y: number; x: number }[] = [];
  const lines: React.ReactNode[] = [];
  for (const s of spec.series) {
    const look = LINES[s.line];
    segments(rows, s.index).forEach((run, n) => {
      if (run.length === 1) {
        lines.push(<rect key={`${s.index}-${n}`} className={cx(look.fill)} x={x(run[0][0]) - 3} y={y(run[0][s.index]) - 3} width={6} height={6} />);
        return;
      }
      let path = `M${x(run[0][0]).toFixed(1)} ${y(run[0][s.index]).toFixed(1)}`;
      for (const r of run.slice(1)) {
        path += spec.step ? `H${x(r[0]).toFixed(1)}V${y(r[s.index]).toFixed(1)}` : `L${x(r[0]).toFixed(1)} ${y(r[s.index]).toFixed(1)}`;
      }
      lines.push(<path key={`${s.index}-${n}`} className={cx("fill-none", look.stroke)} strokeWidth={2} strokeLinejoin="bevel" d={path} />);
    });
    if (latest && !missing(latest[s.index]) && s.key) ends.push({ key: s.key, y: y(latest[s.index]), x: x(latest[0]) });
  }
  // Direct labels at the lines' ends, pushed apart where the lines run close.
  ends.sort((a, b) => a.y - b.y);
  for (let i = 1; i < ends.length; i++) ends[i].y = Math.max(ends[i].y, ends[i - 1].y + 14);

  return (
    <figure className="m-0 min-w-0">
      <figcaption>
        <h4>{title}</h4>
        {caption && <p className="fine">{caption}</p>}
      </figcaption>
      <p className="mt-2 flex min-h-[1.6em] flex-wrap items-baseline gap-x-4 gap-y-0.5 text-[0.9375rem] text-sage" aria-live={keyed && picked ? "polite" : undefined}>
        <span>{shown ? DAY_CLOCK.format(new Date(shown[0] * 1000)) : "No readings yet"}</span>
        {/* Top line of the chart first in the key: the series are drawn back to front. */}
        {[...spec.series].reverse().map((s) => (
          <span key={s.index} className="inline-flex items-baseline gap-1.5">
            {spec.series.length > 1 && (
              <>
                <i className={cx("inline-block h-1 w-3.5 self-center", LINES[s.line].bg)} />
                <span>{s.name}</span>
              </>
            )}
            <b className="font-bold text-bone">{shown && !missing(shown[s.index]) ? spec.format(shown[s.index]) + spec.unit : "no reading"}</b>
          </span>
        ))}
      </p>
      <div ref={ref} className="relative mt-1.5 touch-pan-y">
        {width > 0 && (
          <svg
            className="block w-full cursor-crosshair text-[13px] focus-visible:outline-offset-1"
            viewBox={`0 0 ${width} ${height}`}
            height={height}
            role="img"
            tabIndex={0}
            aria-label={label}
            onPointerMove={onMove}
            onPointerLeave={() => point(null, false)}
            onBlur={() => point(null, false)}
            onKeyDown={onKey}
          >
            {spec.yTicks(top).filter((v) => v !== spec.limit).map((v) => (
              <g key={v}>
                <line className="stroke-leaf-2" strokeWidth={1} shapeRendering="crispEdges" x1={pad.left} x2={width - pad.right} y1={y(v)} y2={y(v)} />
                <text className="fill-sage" x={pad.left - 6} y={y(v) + 4} textAnchor="end">{String(v)}</text>
              </g>
            ))}
            {ticks.map((t) => (
              <text key={t} className="fill-sage" x={x(t)} y={height - 6} textAnchor="middle">
                {(every < 60 ? CLOCK : HOUR).format(new Date(t * 1000))}
              </text>
            ))}
            {gaps(rows, spec.machine).map(([from, to]) => (
              <rect key={from} className="fill-leaf-2" x={x(from)} y={pad.top} width={Math.max(2, x(to) - x(from))} height={height - pad.top - pad.bottom} />
            ))}
            {spec.limit !== undefined && (
              <g>
                <line className="stroke-bone-2" strokeWidth={1} strokeDasharray="4 3" shapeRendering="crispEdges" x1={pad.left} x2={width - pad.right} y1={y(spec.limit)} y2={y(spec.limit)} />
                <text className="fill-sage" x={pad.left - 6} y={y(spec.limit) + 4} textAnchor="end">{String(spec.limit)}</text>
                <text className="fill-bone-2" x={pad.left + 4} y={y(spec.limit) - 4}>{spec.limitLabel || "The limit"}</text>
              </g>
            )}
            {lines}
            {shownMarks.map((m, i) => {
              const at = x(m.t);
              const left = at > width - pad.right - 60;
              if (m.kind === "peak" && m.v !== undefined) {
                return (
                  <g key={`m${i}`}>
                    <rect className="fill-bone stroke-shade" strokeWidth={1} shapeRendering="crispEdges" x={at - 4} y={y(m.v) - 4} width={8} height={8} />
                    <text className="fill-bone font-bold" x={left ? at - 7 : at + 7} y={Math.max(pad.top + 10, y(m.v) - 6)} textAnchor={left ? "end" : "start"}>{m.label}</text>
                  </g>
                );
              }
              const crash = m.kind === "crash";
              return (
                <g key={`m${i}`}>
                  {crash
                    ? <line className="stroke-bad" strokeWidth={2} shapeRendering="crispEdges" x1={at} x2={at} y1={pad.top - 6} y2={height - pad.bottom} />
                    : <rect className="fill-warn" shapeRendering="crispEdges" x={at - 2} y={pad.top - 8} width={4} height={8} />}
                  <text className={crash ? "fill-bad" : "fill-warn"} x={left ? at - 5 : at + 5} y={pad.top - 9} textAnchor={left ? "end" : "start"}>{m.label}</text>
                </g>
              );
            })}
            {ends.map((e) => (
              <text key={e.key} className="fill-sage" x={e.x + 5} y={Math.min(e.y + 4, height - pad.bottom)}>{LINE_LABELS[e.key]}</text>
            ))}
            {rows.length < 2 && (
              <text className="fill-hint" x={width / 2} y={height / 2} textAnchor="middle">
                {width < 400 ? "A reading comes every 2 minutes." : "This fills in as readings come in, one every 2 minutes."}
              </text>
            )}
            {picked && (
              <line className="stroke-bone-2" strokeWidth={1} shapeRendering="crispEdges" x1={x(picked[0])} x2={x(picked[0])} y1={pad.top} y2={height - pad.bottom} />
            )}
            {picked && spec.series.map((s) => (
              missing(picked[s.index]) ? null : (
                <rect key={s.index} className={cx("stroke-bone", LINES[s.line].fill)} strokeWidth={1} shapeRendering="crispEdges" width={8} height={8} x={x(picked[0]) - 4} y={y(picked[s.index]) - 4} />
              )
            ))}
          </svg>
        )}
      </div>
    </figure>
  );
}

export default function Charts({ data }: { data: any }) {
  const [hours, setHours] = useState(6);
  const [hover, setHover] = useState<number | null>(null);
  const [keyed, setKeyed] = useState(false);
  const [open, setOpen] = useState(false);

  const all: Row[] = data.history || [];
  const end = Date.parse(data.checked) / 1000;
  const start = end - hours * 3600;
  const rows = all.filter((r) => r[0] >= start && r[0] <= end + 1);
  const shared: Shared = {
    rows, start, end, hours, hover, keyed,
    point: (t, k) => {
      setHover(t);
      setKeyed(k);
    },
  };
  const all3 = specs(data);
  const health = healthMarks(data);
  const peak = peakMark(rows);
  const fill = (v: unknown, text: () => string) => (missing(v) ? "no reading" : text());

  return (
    <div className="flex flex-col gap-5">
      <Toggles
        label="How far back to show"
        value={String(hours)}
        options={[{ value: "1", label: "1 hour" }, { value: "6", label: "6 hours" }, { value: "24", label: "24 hours" }]}
        onChange={(v) => {
          setHours(Number(v));
          setHover(null);
        }}
      />
      <Chart spec={all3.tick} title="Time per tick" caption="Lower is better. Past the 50 ms line, the game falls behind and players feel lag. A coral line marks a crash; an amber tick, a stall the server's log recorded." shared={shared} marks={health} />
      <Chart spec={all3.players} title="Players online" caption={peak ? `The most at once in this range: ${peak.v}.` : undefined} shared={shared} marks={peak ? [peak] : []} />
      <Chart
        spec={all3.machine}
        title="The machine"
        caption="How much of the machine's memory and CPU is in use. The game shares them with the map, the backups and everything else on the machine."
        shared={shared}
      />
      <Fine>
        A reading is taken every 2 minutes and covers about 5 seconds, so a short spike between readings won't show. P95
        means 19 ticks in 20 were faster than this. Shaded stretches had no reading: the server was restarting, stopped or
        not answering.
      </Fine>
      <Fold title="The readings as a table" open={open} onToggle={setOpen}>
        {open && (
          <TableScroll label="The readings">
            <table className="data">
              <thead>
                <tr><th scope="col">When</th><th scope="col">Average</th><th scope="col">P95</th><th scope="col">Players</th><th scope="col">Memory</th><th scope="col">CPU in use</th></tr>
              </thead>
              <tbody>
                {[...rows].reverse().map((r) => (
                  <tr key={r[0]}>
                    <td className="whitespace-nowrap">{DAY_CLOCK.format(new Date(r[0] * 1000))}</td>
                    <td className="whitespace-nowrap">{fill(r[1], () => `${one(r[1])} ms`)}</td>
                    <td className="whitespace-nowrap">{fill(r[2], () => `${one(r[2])} ms`)}</td>
                    <td>{fill(r[3], () => String(r[3]))}</td>
                    <td>{fill(r[4], () => `${Math.round(r[4])}%`)}</td>
                    <td>{fill(r[5], () => `${Math.round(r[5])}%`)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </TableScroll>
        )}
      </Fold>
    </div>
  );
}
