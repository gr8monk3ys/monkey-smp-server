// The dashboard's people: player cards from /api/known-players and staff actions this week from /api/activity. Both
// are read when the tab opens (useOnShow), through lib/api like every other call, so they carry the staff header.
import { useState } from "react";
import { get, messageOf, query } from "../../lib/api";
import { ago, plural } from "../../lib/format";
import { useOnShow } from "../../lib/hooks";
import { Fine, Message, Panel, cx } from "../../ui/kit";

const WEEK_S = 7 * 86400;
const NEW_HOURS = 2;
const CARDS = 12;
const ACTIVITY_PAGES = 5;   // 100 actions a page; past 500 in a week the count says "at least"

interface Known { name: string; last_seen: number | null; hours: number | null; op?: boolean; banned?: boolean }

// A pixel head from the name, so the same player always gets the same face. No skin service: the policy allows
// images from this site only.
const HAIR = ["fill-ink", "fill-ink-2", "fill-gold", "fill-stone", "fill-leaf-3"];
const SKIN = ["fill-bone", "fill-bone-2", "fill-gold-hi", "fill-sage"];
function hash(name: string) {
  let h = 2166136261;
  for (let i = 0; i < name.length; i++) h = Math.imul(h ^ name.charCodeAt(i), 16777619);
  return h >>> 0;
}
function Head({ name }: { name: string }) {
  const h = hash(name);
  const hair = HAIR[h % HAIR.length];
  const skin = SKIN[(h >>> 4) % SKIN.length];
  const fringe = (h >>> 8) % 3;   // how far the hair comes down the sides
  const px: [number, number, string][] = [];
  for (let y = 0; y < 8; y++) {
    for (let x = 0; x < 8; x++) {
      const side = x === 0 || x === 7;
      const isHair = y < 2 || (side && y < 2 + fringe);
      const eye = y === 4 && (x === 2 || x === 5);
      const mouth = y === 6 && x >= 3 && x <= 4;
      px.push([x, y, isHair ? hair : eye ? "fill-shade" : mouth ? "fill-stone" : skin]);
    }
  }
  return (
    <svg className="h-10 w-10 shrink-0" viewBox="0 0 8 8" shapeRendering="crispEdges" aria-hidden="true">
      {px.map(([x, y, c]) => <rect key={`${x}.${y}`} className={c} x={x} y={y} width={1} height={1} />)}
    </svg>
  );
}

function Badge({ children, kind }: { children: string; kind: "new" | "away" | "on" }) {
  return (
    <span className={cx("px-1.5 text-xs font-bold", kind === "new" ? "bg-gold text-ink" : kind === "on" ? "bg-ok text-ink" : "bg-leaf-2 text-bone-2")}>{children}</span>
  );
}

export function PlayerCards({ d, active }: { d: any; active: boolean }) {
  const [rows, setRows] = useState<Known[] | null>(null);
  const [error, setError] = useState("");
  useOnShow(async () => {
    try {
      const data = await get("/api/known-players");
      setRows((data.players || []).filter((p: Known) => p && typeof p.name === "string"));
      setError("");
    } catch (e) {
      setError(messageOf(e));
    }
  }, active);

  const now = Date.now() / 1000;
  const on = new Set<string>((d.players && d.players.names) || []);
  const list = (rows || []).slice().sort((a, b) => Number(on.has(b.name)) - Number(on.has(a.name)) || (b.last_seen || 0) - (a.last_seen || 0));
  const fresh = (p: Known) => p.last_seen !== null && now - p.last_seen < WEEK_S;
  const isNew = (p: Known) => fresh(p) && (p.hours || 0) < NEW_HOURS;
  const away = (p: Known) => p.last_seen !== null && now - p.last_seen >= WEEK_S;
  const counts = { week: list.filter(fresh).length, fresh: list.filter(isNew).length, away: list.filter(away).length };

  return (
    <Panel title="Players" meta={rows ? `${plural(counts.week, "player")} this week, ${counts.fresh} new, ${counts.away} away 7+ days` : undefined}
      aside={<a className="text-sm" href="#players">All players</a>}>
      {error && <Message kind="error">{error}</Message>}
      {rows === null && !error && <p className="text-sage">Reading the player list.</p>}
      {rows && !list.length && <p className="text-sage">Nobody has joined yet.</p>}
      {list.length > 0 && (
        <ul className="m-0 grid list-none grid-cols-1 gap-2 p-0 xs:grid-cols-2 lg:grid-cols-3">
          {list.slice(0, CARDS).map((p) => (
            <li key={p.name} className="flex min-w-0 items-center gap-3 bg-leaf p-2">
              <Head name={p.name} />
              <div className="min-w-0">
                <div className="flex flex-wrap items-center gap-1.5">
                  <b className="truncate text-bone">{p.name}</b>
                  {on.has(p.name) && <Badge kind="on">On now</Badge>}
                  {isNew(p) && <Badge kind="new">New</Badge>}
                  {away(p) && <Badge kind="away">Away 7+ days</Badge>}
                </div>
                <small className="block text-sm text-sage">
                  {`${p.hours === null || p.hours === undefined ? "No play time" : `${p.hours.toFixed(1)} h played`}, ${on.has(p.name) ? "on now" : p.last_seen ? `seen ${ago(now - p.last_seen)}` : "never seen"}`}
                </small>
              </div>
            </li>
          ))}
        </ul>
      )}
      <Fine>{`The server keeps no first-join date, so "New" means seen this week with under ${NEW_HOURS} hours played. The heads are drawn from the name, not the player's skin.`}</Fine>
    </Panel>
  );
}

interface Action { at: number; time: string; user: string; action: string; target?: string }

export function StaffWeek({ active }: { active: boolean }) {
  const [rows, setRows] = useState<Action[] | null>(null);
  const [capped, setCapped] = useState(false);
  const [error, setError] = useState("");
  useOnShow(async () => {
    try {
      const since = Date.now() - WEEK_S * 1000;
      const out: Action[] = [];
      let before: number | undefined;
      let more = true;
      for (let page = 0; page < ACTIVITY_PAGES && more; page++) {
        const data = await get(`/api/activity?${query({ before })}`);
        const got: Action[] = data.actions || [];
        out.push(...got);
        const oldest = got[got.length - 1];
        more = !!data.more && !!oldest && Date.parse(oldest.time) >= since;
        before = oldest ? oldest.at : undefined;
      }
      setCapped(more);
      setRows(out.filter((a) => Date.parse(a.time) >= since));
      setError("");
    } catch (e) {
      setError(messageOf(e));
    }
  }, active);

  const by = new Map<string, number>();
  for (const a of rows || []) by.set(a.user, (by.get(a.user) || 0) + 1);
  const ranked = [...by.entries()].sort((a, b) => b[1] - a[1]);
  const top = Math.max(1, ...ranked.map((r) => r[1]));
  return (
    <Panel title="Staff this week" meta={rows ? `${capped ? "At least " : ""}${plural(rows.length, "action")}` : undefined}
      aside={<a className="text-sm" href="#server">Full log</a>}>
      {error && <Message kind="error">{error}</Message>}
      {rows === null && !error && <p className="text-sage">Reading the staff log.</p>}
      {rows && !rows.length && <p className="text-sage">No staff actions in the last 7 days.</p>}
      {ranked.length > 0 && (
        <dl className="m-0 flex flex-col gap-2">
          {ranked.map(([user, n]) => (
            <div key={user} className="grid grid-cols-[minmax(0,8rem)_1fr_auto] items-center gap-3">
              <dt className="truncate font-semibold text-bone">{user}</dt>
              <dd className="m-0">
                <svg className="block h-2 w-full" viewBox="0 0 100 6" preserveAspectRatio="none" aria-hidden="true" shapeRendering="crispEdges">
                  <rect className="fill-leaf-2" width={100} height={6} />
                  <rect className="fill-sage" width={(n / top) * 100} height={6} />
                </svg>
              </dd>
              <dd className="m-0 text-right text-sage tabular-nums">{n}</dd>
            </div>
          ))}
        </dl>
      )}
      {rows && rows.length > 0 && (
        <>
          <h3 className="mt-2 text-sm font-semibold text-sage">Latest</h3>
          <ul className="m-0 flex list-none flex-col gap-1 p-0 text-sm">
            {rows.slice(0, 5).map((a) => (
              <li key={a.at} className="wrap-anywhere">
                <span className="text-sage">{`${ago((Date.now() - Date.parse(a.time)) / 1000)}: `}</span>
                <b className="text-bone">{a.user}</b>{` ${a.action}${a.target ? ` ${a.target}` : ""}`}
              </li>
            ))}
          </ul>
        </>
      )}
    </Panel>
  );
}
