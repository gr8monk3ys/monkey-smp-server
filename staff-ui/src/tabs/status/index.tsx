// The Status tab: reads staff.json (tools/staff_status.py, kept by the shell: useStatus) and draws it. It can only
// read. The verdict comes first, as a mark and a word and a sentence; the numbers below are the evidence for it.
import type { ReactNode } from "react";
import { LOW_DISK, agoMs, currentVerdict, isFresh, useStatus, type VerdictKind } from "../../lib/status";
import { Mark, Message, Panel, Panels, cx, type MarkKind } from "../../ui/kit";
import Charts, { DAY_CLOCK } from "./charts";
import { Advice, Problems } from "./problems";

const CRITICAL_DISK = 0.05;
const CLOCK = new Intl.DateTimeFormat(undefined, { hour: "numeric", minute: "2-digit" });
const one = (n: number) => n.toFixed(1);
const gb = (kib: number) => kib / 1048576;
const diskGb = (bytes: number) => bytes / 1073741824;

const WORD_COLOUR: Record<VerdictKind, string> = {
  good: "text-ok", busy: "text-warn", slow: "text-bad", off: "text-bone-2", unknown: "text-bone-2",
};

/** A meter: how much of a whole is used, as a flat bar (SVG attributes only). */
function Meter({ share, kind }: { share: number; kind?: "busy" | "slow" }) {
  const fill = kind === "slow" ? "fill-bad" : kind === "busy" ? "fill-warn" : "fill-sage";
  return (
    <svg className="mt-1 block h-1.5 w-full" viewBox="0 0 100 6" preserveAspectRatio="none" aria-hidden="true" shapeRendering="crispEdges">
      <rect className="fill-leaf-2" width={100} height={6} />
      <rect className={fill} width={Math.min(100, Math.max(0, share * 100))} height={6} />
    </svg>
  );
}

/** One number: its label, the figure big, its unit, a line under it and optionally a meter. */
function Stat({ label, value, unit, small, meter, word }: { label: string; value?: ReactNode; unit?: string; small?: string; meter?: ReactNode; word?: boolean }) {
  return (
    <div className="min-w-0">
      <dt className="text-sm text-sage">{label}</dt>
      <dd className="m-0">
        <div className="flex flex-wrap items-baseline gap-x-1.5 wrap-anywhere">
          <span className={word ? "flex items-center gap-2 text-lg font-bold text-bone" : "text-3xl leading-tight font-bold text-bone"}>{value}</span>
          {unit && <span className="text-sage">{unit}</span>}
        </div>
        {meter}
        {small && <small className="block text-sm text-sage">{small}</small>}
      </dd>
    </div>
  );
}

function Stats({ children }: { children: ReactNode }) {
  return <dl className="m-0 grid grid-cols-1 gap-x-6 gap-y-4 xs:grid-cols-2">{children}</dl>;
}

function Skeleton({ rows = 3 }: { rows?: number }) {
  return (
    <div className="flex flex-col gap-3" aria-hidden="true">
      {Array.from({ length: rows }, (_, i) => <i key={i} className="skeleton" />)}
    </div>
  );
}

function Game({ d }: { d: any }) {
  return (
    <Panel title="The game">
      <Stats>
        {d.tick ? (
          <>
            <Stat label="Ticks a second" value={one(d.tick.tps)} unit={`of ${Math.round(d.tick.target)}`} />
            <Stat label="Time per tick" value={one(d.tick.avg)} unit={`ms of ${Math.round(1000 / d.tick.target)}`}
              small={`P95 ${one(d.tick.p95)} ms, P99 ${one(d.tick.p99)} ms`} />
          </>
        ) : (
          <Stat label="Ticks a second" value="No reading" word />
        )}
        {d.players ? (
          <Stat label="Players" value={String(d.players.count)} unit={`of ${d.players.max}`} />
        ) : (
          <Stat label="Players" value="No reading" word />
        )}
      </Stats>
      {d.players && (
        <ul className="m-0 flex list-none flex-wrap gap-2 p-0" aria-label="Who is on">
          {d.players.names.length ? (
            d.players.names.map((name: string) => <li key={name} className="bg-leaf px-2 py-0.5 font-semibold text-bone wrap-anywhere">{name}</li>)
          ) : (
            <li className="text-sage">Nobody on right now</li>
          )}
        </ul>
      )}
    </Panel>
  );
}

function Machine({ d }: { d: any }) {
  const host = d.host || {};
  const history: any[] = d.history || [];
  const cpu = history.length ? history[history.length - 1][5] : null;
  const stats: ReactNode[] = [];
  if (host.memory) {
    const used = host.memory.total - host.memory.available;
    stats.push(<Stat key="mem" label="Memory in use" value={one(gb(used))} unit={`of ${Math.round(gb(host.memory.total))} GB`} meter={<Meter share={used / host.memory.total} />} />);
  }
  if (host.swap && host.swap.total) {
    const used = host.swap.total - host.swap.free;
    stats.push(<Stat key="swap" label="Swap in use" value={one(gb(used))} unit={`of ${one(gb(host.swap.total))} GB`} />);
  }
  // CPU in use since the reading before (the history's sixth number), the same number the chart draws; the load
  // average stays as the line under it, since it also counts work waiting for a turn.
  if (typeof cpu === "number" || host.load) {
    const threads = host.threads || 0;
    const load = host.load ? `Load ${host.load[0].toFixed(2)} over 1 minute${threads ? `, on ${threads} threads` : ""}` : "";
    stats.push(
      typeof cpu === "number"
        ? <Stat key="cpu" label="CPU in use" value={String(Math.round(cpu))} unit="%" small={load} meter={<Meter share={cpu / 100} />} />
        : <Stat key="cpu" label="CPU in use" value="reading at the next check" word small={load} />,
    );
  }
  if (host.disk) {
    const free = host.disk.free / host.disk.total;
    const kind = free < CRITICAL_DISK ? "slow" : free < LOW_DISK ? "busy" : undefined;
    stats.push(<Stat key="disk" label="Disk free" value={String(Math.round(diskGb(host.disk.free)))} unit={`of ${Math.round(diskGb(host.disk.total))} GB`} meter={<Meter share={1 - free} kind={kind} />} />);
  }
  if (!stats.length) stats.push(<Stat key="none" label="Numbers" value="No reading" word />);
  return (
    <Panel title="The machine">
      <Stats>{stats}</Stats>
    </Panel>
  );
}

function Upkeep({ d, now }: { d: any; now: number }) {
  const box = d.container;
  const running = box && box.state === "running" && box.uptime;
  const backups = d.backups || {};
  const offsite: [MarkKind, string] = ({ on: ["good", "On"], failing: ["slow", "Failing"], "not set up": ["busy", "Not set up"] } as Record<string, [MarkKind, string]>)[backups.offsite] || ["unknown", "Unknown"];
  const local = backups.local ? new Date(backups.local) : null;
  return (
    <Panel title="Upkeep">
      <Stats>
        <Stat label="Release" value={d.release || "Unknown"} word />
        {box && <Stat label={running ? "Running for" : "Container"} value={running ? box.uptime : box.state} word />}
        {/* The copy a deploy takes before it updates; the hourly backups are the off-site row. */}
        <Stat label="Copy before the last update" word
          value={local ? agoMs(now - local.getTime()) : "None found"} small={local ? DAY_CLOCK.format(local) : undefined} />
        <Stat label="Off-site backups" word value={<><Mark kind={offsite[0]} />{offsite[1]}</>} />
      </Stats>
    </Panel>
  );
}

export default function StatusTab() {
  const s = useStatus();
  const d = s.data;
  const now = s.now;
  const v = currentVerdict(s);
  const fresh = isFresh(s);

  const nobody = fresh && d.online && d.players && d.players.count === 0;
  const alerts: string[] = [];
  const crashed = d && d.problems && d.problems.crashes && d.problems.crashes[0];
  if (fresh && crashed) alerts.push(`The server crashed ${agoMs(now - Date.parse(crashed.when))}.`);
  if (fresh && d.backups && d.backups.offsite === "failing") alerts.push("Off-site backups are failing.");
  const disk = d && d.host && d.host.disk;
  const free = disk && disk.total ? disk.free / disk.total : null;
  if (fresh && free !== null && free < LOW_DISK) alerts.push(`The disk is nearly full: ${Math.round(free * 100)}% free.`);

  const kind: VerdictKind = v ? v.kind : "unknown";
  const checked = d ? new Date(d.checked) : null;

  return (
    <>
      <section className="panel mb-4 flex flex-col gap-4" aria-live="polite" aria-label="How the server is">
        <div className="flex items-center gap-4 sm:gap-6">
          <Mark kind={kind as MarkKind} className="h-14! w-14! sm:h-20! sm:w-20!" />
          <h1 className={cx("min-w-0 text-5xl! leading-none sm:text-7xl!", WORD_COLOUR[kind])}>{v ? v.word : "Checking"}</h1>
        </div>
        <p className="max-w-[40em] text-xl leading-snug text-bone">{v ? v.text : "Asking the server how it is doing."}</p>
        {checked && (
          <p className="text-sage">{`Checked ${agoMs(now - checked.getTime())}, at ${CLOCK.format(checked)}`}</p>
        )}
        {nobody && <p className="text-sage">Nobody is on, so the server has little to do. These numbers will look different with a crowd.</p>}
        {alerts.length > 0 && <Message kind="warn">{alerts.join(" ")}</Message>}
        {d && s.trouble && <Message kind="warn">{s.trouble}</Message>}
      </section>

      {d ? (
        <div className="flex flex-col gap-4">
          <Panels>
            <Game d={d} />
            <Machine d={d} />
            <Upkeep d={d} now={now} />
            <Problems data={d} now={now} />
          </Panels>
          <Advice data={d} />
          <Panel title="Over time">
            <Charts data={d} />
          </Panel>
        </div>
      ) : (
        !s.loaded && (
          <Panels>
            <Panel title="The game"><Skeleton /></Panel>
            <Panel title="The machine"><Skeleton /></Panel>
            <Panel title="Upkeep"><Skeleton rows={2} /></Panel>
            <Panel title="Recent problems"><Skeleton rows={1} /></Panel>
          </Panels>
        )
      )}
    </>
  );
}

