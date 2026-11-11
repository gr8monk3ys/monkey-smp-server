// A player's history and "who changed this block" (the old lookup.js; both answered by tools/staff_lookup.py).
import { useState } from "react";
import { get, query } from "../../lib/api";
import { PLAYER_NAME, plural } from "../../lib/format";
import { useMessages } from "../../lib/hooks";
import { Button, Empty, Fine, FormRow, Input, Message, Messages, Panel, Row, Rows, Select } from "../../ui/kit";

const CLOCK = new Intl.DateTimeFormat(undefined, { month: "short", day: "numeric", year: "numeric", hour: "numeric", minute: "2-digit" });

// A time from the server: seconds since 1970, or text such as 2026-11-10T12:00:00Z. Text with no zone is shown as it is.
function when(value: unknown): string {
  if (value === null || value === undefined || value === "") return "never";
  if (typeof value === "number") return CLOCK.format(new Date(value > 1e11 ? value : value * 1000));
  const text = String(value);
  if (!/(Z|[+-]\d\d:?\d\d)$/.test(text)) return text.replace("T", " ");
  const ms = Date.parse(text);
  return Number.isNaN(ms) ? text : CLOCK.format(new Date(ms));
}

interface Line {
  title: string;
  about?: string;
}

export function PlayerHistory() {
  const [name, setName] = useState("");
  const [summary, setSummary] = useState("");
  const [lines, setLines] = useState<Line[] | null>(null);
  const [cut, setCut] = useState(false);
  const m = useMessages();

  const go = async () => {
    const who = name.trim();
    m.clear();
    setSummary("");
    setLines(null);
    setCut(false);
    if (!PLAYER_NAME.test(who)) {
      m.fail(new Error("A player name is 3 to 16 letters, digits or _."));
      return;
    }
    await m.run(async () => {
      const h = await get(`/api/player-history?name=${encodeURIComponent(who)}`);
      const facts: string[] = [];
      facts.push(h.known ? `Has joined. Last seen ${when(h.last_seen)}.` : "Has never joined (or joined before the server kept a record).");
      if (typeof h.hours === "number") facts.push(`Played ${h.hours} hours.`);
      facts.push(h.whitelisted ? "On the whitelist." : "Not on the whitelist.");
      if (h.op) facts.push("An operator.");
      setSummary(`${h.name}: ${facts.join(" ")}`);
      const rows: Line[] = [];
      if (h.ban) {
        rows.push({
          title: `Banned: ${h.ban.reason || "no reason given"}`,
          about: `by ${h.ban.source || "?"}, ${h.ban.created || "?"}${h.ban.expires && h.ban.expires !== "forever" ? `, until ${h.ban.expires}` : ""}`,
        });
      }
      if (h.tempban) {
        rows.push({
          title: `Temporary ban until ${when(h.tempban.until)}${h.tempban.reason ? `: ${h.tempban.reason}` : ""}`,
          about: `by ${h.tempban.by || "?"}, ${when(h.tempban.at)}`,
        });
      }
      for (const n of h.notes || []) rows.push({ title: `Note: ${n.text}`, about: `by ${n.by || "?"}, ${when(n.at)}` });
      for (const c of h.changes || []) rows.push({ title: `${c.action}: ${c.target}`, about: `by ${c.user}, ${when(c.time)}` });
      setCut(!!h.cut);
      setLines(rows);
    });
  };

  return (
    <Panel title="A player's history">
      <Fine>
        Everything the page knows about one player in one place: their lists, a ban and its reason, a temporary ban, staff's notes, and every staff change that names them (kicks, bans, notes, commands).
      </Fine>
      <Messages of={m} />
      <FormRow>
        <Input maxLength={16} placeholder="Player name" aria-label="Player whose history to show" value={name} onChange={(e) => setName(e.target.value)} onKeyDown={(e) => e.key === "Enter" && go()} />
        <Button kind="primary" disabled={m.busy} onClick={go}>Show history</Button>
      </FormRow>
      <Fine role="status" className="wrap-anywhere">{summary}</Fine>
      {lines && (
        <Rows label="History">
          {lines.map((l, i) => (
            <Row key={i} title={<span className="wrap-anywhere">{l.title}</span>} about={l.about} />
          ))}
          {cut && <Empty>Older changes are in the record's earlier files on the server (actions.log.1 and older).</Empty>}
          {!lines.length && !cut && <Empty>No ban, notes or staff changes for this player.</Empty>}
        </Rows>
      )}
    </Panel>
  );
}

const ACTIONS: Record<string, string> = {
  "block-break": "broke", "block-place": "placed", "block-change": "changed", "item-insert": "put in",
  "item-remove": "took out", "entity-kill": "killed", "item-pick-up": "picked up", "item-drop": "dropped",
};

interface BlockRow {
  action: string;
  who: string;
  object: string;
  old?: string;
  rolled_back?: boolean;
  time: string;
  x: number;
  y: number;
  z: number;
}

export function BlockHistory() {
  const [at, setAt] = useState({ x: "", y: "", z: "" });
  const [world, setWorld] = useState("Overworld");
  const [radius, setRadius] = useState("2");
  const [hours, setHours] = useState("72");
  const [kind, setKind] = useState("all");
  const [player, setPlayer] = useState("");
  const [summary, setSummary] = useState("");
  const [rows, setRows] = useState<BlockRow[] | null>(null);
  const m = useMessages();

  const go = async () => {
    m.clear();
    setSummary("");
    setRows(null);
    const q: Record<string, string> = {};
    for (const key of ["x", "y", "z"] as const) {
      const value = at[key].trim();
      if (!/^-?\d+$/.test(value)) {
        m.fail(new Error(`Type the block's ${key.toUpperCase()} as a whole number (F3 shows it in game).`));
        return;
      }
      q[key] = value;
    }
    Object.assign(q, { world, radius, hours, kind });
    const who = player.trim();
    if (who) {
      if (!PLAYER_NAME.test(who)) {
        m.fail(new Error("A player name is 3 to 16 letters, digits or _."));
        return;
      }
      q.player = who;
    }
    setSummary("Reading Ledger's record...");
    const done = await m.run(async () => {
      const data = await get(`/api/block-history?${query(q)}`);
      const list: BlockRow[] = data.rows || [];
      const box = data.box;
      let text: string =
        data.note ||
        (box
          ? `${plural(list.length, "change")} within ${box.radius} of ${box.x} ${box.y} ${box.z} in the ${box.world}, last ${plural(box.hours, "hour")}. Times are ${data.zone || "Pacific"}, newest first.`
          : "");
      if (data.more) text += " There are more: pick a smaller area or a shorter time.";
      if (data.stopped) text += " The look-up stopped early so the game doesn't slow down: pick a smaller area or a shorter time.";
      setSummary(text);
      setRows(list);
      return true;
    });
    if (!done) setSummary("");
  };
  const enter = (e: React.KeyboardEvent) => e.key === "Enter" && go();

  return (
    <Panel title="Who changed this block">
      <Fine>
        From Ledger's record: who placed, broke or took from a block and the blocks around it. Stand on the spot and press F3 for its coordinates. It only reads: to undo grief, use Ledger's rollback in game. Times are Pacific.
      </Fine>
      <Messages of={m} />
      <FormRow>
        <Input inputMode="numeric" maxLength={9} placeholder="X" aria-label="X coordinate" value={at.x} onChange={(e) => setAt({ ...at, x: e.target.value })} onKeyDown={enter} />
        <Input inputMode="numeric" maxLength={5} placeholder="Y" aria-label="Y coordinate" value={at.y} onChange={(e) => setAt({ ...at, y: e.target.value })} onKeyDown={enter} />
        <Input inputMode="numeric" maxLength={9} placeholder="Z" aria-label="Z coordinate" value={at.z} onChange={(e) => setAt({ ...at, z: e.target.value })} onKeyDown={enter} />
        <Select aria-label="World" value={world} onChange={(e) => setWorld(e.target.value)} options={[
          { value: "Overworld", label: "Overworld" }, { value: "Nether", label: "Nether" }, { value: "End", label: "End" },
        ]} />
      </FormRow>
      <FormRow>
        <Select aria-label="How far around it" value={radius} onChange={(e) => setRadius(e.target.value)} options={[
          { value: "0", label: "That block only" }, { value: "2", label: "2 blocks around" },
          { value: "5", label: "5 blocks around" }, { value: "8", label: "8 blocks around" },
        ]} />
        <Select aria-label="How far back" value={hours} onChange={(e) => setHours(e.target.value)} options={[
          { value: "6", label: "Last 6 hours" }, { value: "24", label: "Last day" }, { value: "72", label: "Last 3 days" },
          { value: "168", label: "Last week" }, { value: "720", label: "Last 30 days" },
        ]} />
        <Select aria-label="What kind of change" value={kind} onChange={(e) => setKind(e.target.value)} options={[
          { value: "all", label: "Everything" }, { value: "blocks", label: "Blocks placed and broken" },
          { value: "containers", label: "Items into and out of chests" }, { value: "kills", label: "Kills" },
        ]} />
        <Input maxLength={16} placeholder="Only this player (optional)" aria-label="Only this player" value={player} onChange={(e) => setPlayer(e.target.value)} onKeyDown={enter} />
        <Button kind="primary" disabled={m.busy} onClick={go}>Look up</Button>
      </FormRow>
      <Message kind="note">{summary}</Message>
      {rows && (
        <Rows label="Changes">
          {rows.map((r, i) => {
            const verb = ACTIONS[r.action] || r.action;
            // Ledger keeps a broken block in old (object is then air), and a changed one as old to object.
            const what =
              r.action === "block-break" ? r.old || r.object : r.action === "block-change" && r.old && r.old !== r.object ? `${r.old} to ${r.object}` : r.object;
            return (
              <Row key={i} title={<span className="wrap-anywhere">{`${r.who} ${verb} ${what}${r.rolled_back ? " (rolled back)" : ""}`}</span>} about={`${r.time} at ${r.x} ${r.y} ${r.z}`} />
            );
          })}
          {!rows.length && <Empty>No changes there in that time.</Empty>}
        </Rows>
      )}
    </Panel>
  );
}
