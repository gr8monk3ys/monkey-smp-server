// Temporary bans (the old desk.js): a ban that lifts by itself.
import { useState } from "react";
import { get, post } from "../../lib/api";
import { changed, emit, useBus } from "../../lib/bus";
import { PLAYER_NAME, when } from "../../lib/format";
import { useMessages, useOnShow } from "../../lib/hooks";
import { useSession } from "../../lib/session";
import { Button, Empty, Fine, FormRow, Input, Messages, Panel, Row, Rows, Select, useConfirm } from "../../ui/kit";

interface TempBan {
  name: string;
  until: unknown;
  reason?: string;
  by?: string;
}

const LENGTHS = [
  { value: "1", label: "1 hour" },
  { value: "6", label: "6 hours" },
  { value: "24", label: "1 day" },
  { value: "72", label: "3 days" },
  { value: "168", label: "7 days" },
  { value: "720", label: "30 days" },
];

export default function TempBans({ active }: { active: boolean }) {
  const { can } = useSession();
  const [bans, setBans] = useState<TempBan[]>([]);
  const [loaded, setLoaded] = useState(false);
  const [name, setName] = useState("");
  const [hours, setHours] = useState("24");
  const [reason, setReason] = useState("");
  const m = useMessages();
  const [confirm, ask] = useConfirm();

  const load = async () => {
    try {
      const data = await get("/api/tempbans");
      setBans(data.bans || []);
      setLoaded(true);
    } catch (e) {
      m.fail(e);
    }
  };
  useOnShow(load, active);
  useBus("changed", () => {
    if (active) load();
  });

  const lift = (b: TempBan) =>
    ask({
      message: `Lift ${b.name}'s ban now? They can join at once.`,
      yes: "Yes, lift it",
      onYes: async () => {
        try {
          const done = await post("/api/tempban-end", { name: b.name });
          m.say(`${b.name}: ${done.result}.`);
        } catch (e) {
          m.fail(e);
        }
        load();
        emit("players-changed", {});
      },
    });

  const add = () => {
    const who = name.trim();
    const why = reason.replace(/\s+/g, " ").trim();
    if (!PLAYER_NAME.test(who)) {
      m.fail(new Error("A name is 3 to 16 letters, digits or underscores."));
      return;
    }
    const length = LENGTHS.find((l) => l.value === hours)?.label ?? hours;
    ask({
      message: `Ban ${who} for ${length}${why ? ` for "${why}"` : ""}? They are kicked if they are on, and can't join until it ends.`,
      yes: `Yes, ban ${who}`,
      danger: true,
      onYes: async () => {
        m.clear();
        try {
          await post("/api/tempban", { name: who, hours: Number(hours), reason: why });
          setName("");
          setReason("");
          m.say(`${who} is banned for ${length}.`);
          changed();
        } catch (e) {
          m.fail(e);
        }
        load();
        emit("players-changed", {});
      },
    });
  };
  const enter = (e: React.KeyboardEvent) => {
    if (e.key === "Enter") add();
  };

  return (
    <Panel title="Temporary bans" meta={loaded ? bans.length || "" : ""}>
      <Fine>
        A ban that lifts by itself. The player sees when it ends. The page pardons them at that time, unless someone pardoned them or banned them for good in the meantime.
      </Fine>
      <Messages of={m} />
      {confirm}
      <Rows label="Temporary bans">
        {bans.map((b) => (
          <Row
            key={b.name}
            title={<span className="wrap-anywhere">{b.name}</span>}
            about={[`until ${when(b.until)}`, b.reason, `by ${b.by}`].filter(Boolean).join(", ")}
            actions={can("admin") && <Button small onClick={() => lift(b)}>Lift now</Button>}
          />
        ))}
        {loaded && !bans.length && <Empty>No temporary bans.</Empty>}
      </Rows>
      {can("admin") && (
        <FormRow>
          <Input maxLength={16} placeholder="Player name" aria-label="Player to ban for a time" value={name} onChange={(e) => setName(e.target.value)} onKeyDown={enter} />
          <Select aria-label="For how long" options={LENGTHS} value={hours} onChange={(e) => setHours(e.target.value)} />
          <Input maxLength={120} placeholder="Reason they will see (optional)" aria-label="Reason" value={reason} onChange={(e) => setReason(e.target.value)} onKeyDown={enter} />
          <Button kind="danger" onClick={add}>Ban for a time</Button>
        </FormRow>
      )}
    </Panel>
  );
}
