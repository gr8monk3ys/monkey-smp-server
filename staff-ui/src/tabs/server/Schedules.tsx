// The machine's own timed jobs (read only) and the page's own schedules (admin).
import { useState } from "react";
import { api, get, listOf } from "../../lib/api";
import { when } from "../../lib/format";
import { useMessages, useOnShow } from "../../lib/hooks";
import { useSession } from "../../lib/session";
import { Actions, Button, Empty, Fine, FormRow, Input, Messages, Panel, Row, Rows, Select, TableScroll, useConfirm } from "../../ui/kit";

const DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];

export function Timers({ active }: { active: boolean }) {
  const m = useMessages();
  const [timers, setTimers] = useState<any[] | null>(null);

  useOnShow(async () => {
    try {
      setTimers(listOf(await get("/api/timers"), "timers"));
      m.setError("");
    } catch (error) {
      m.fail(error);
    }
  }, active);

  return (
    <Panel title="Timed jobs on the machine" wide>
      <Fine>The machine's own jobs: the daily restart, backups and deploys. Change them on the machine.</Fine>
      <Messages of={m} />
      <TableScroll label="Timed jobs on the machine">
        <table className="data">
          <thead>
            <tr>
              <th scope="col">Job</th>
              <th scope="col">Next run</th>
              <th scope="col">Last run</th>
            </tr>
          </thead>
          <tbody>
            {timers && timers.length === 0 && (
              <tr>
                <td colSpan={3}>No schedules found.</td>
              </tr>
            )}
            {(timers || []).map((t, i) => (
              <tr key={i}>
                <td className="wrap-anywhere">{String(t.name || "").replace(/\.timer$/, "")}</td>
                <td>{when(t.next)}</td>
                <td>{when(t.last)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </TableScroll>
    </Panel>
  );
}

function describe(s: any): string {
  const words: Record<string, string> = {
    command: `runs ${s.command}`,
    restart: "restarts the server (warnings at 5 min, 1 min, 10 s)",
    backup: "backs up off-site",
  };
  const only: Record<string, string> = { empty: ", only when nobody is online", players: ", only when someone is online" };
  return `${words[s.kind]}, ${s.describe}${only[s.only] || ""}`;
}

export function Schedules({ active }: { active: boolean }) {
  const { can } = useSession();
  const m = useMessages();
  const [confirm, ask] = useConfirm();
  const [data, setData] = useState<any>(null);
  const [name, setName] = useState("");
  const [kind, setKind] = useState("command");
  const [command, setCommand] = useState("");
  const [type, setType] = useState("daily");
  const [day, setDay] = useState("0");
  const [time, setTime] = useState("04:00");
  const [minutes, setMinutes] = useState("60");
  const [only, setOnly] = useState("always");

  const load = async () => {
    if (!can("admin")) return;
    try {
      setData(await get("/api/schedules"));
    } catch (error) {
      m.fail(error);
    }
  };
  useOnShow(load, active);
  if (!can("admin")) return null;

  const call = async (method: string, url: string, body: unknown, words: string) => {
    m.setError("");
    try {
      await api(method, url, body);
      m.say(words);
    } catch (error) {
      m.fail(error);
    }
    load();
  };

  const add = () => {
    const at: Record<string, unknown> = { type };
    if (type === "interval") at.minutes = Number(minutes);
    else at.time = time;
    if (type === "weekly") at.day = Number(day);
    const body: Record<string, unknown> = { name: name.trim(), kind, when: at, enabled: true, only };
    if (kind === "command") body.command = command.trim();
    call("POST", "/api/schedules", body, "Schedule added.");
  };

  const schedules: any[] = data?.schedules || [];
  return (
    <Panel title="Your schedules" wide>
      {data && <Fine>{`Times are the machine's: ${data.timezone}. It is ${data.now} there now.`}</Fine>}
      <Messages of={m} />
      {confirm}
      <Rows label="Your schedules">
        {data && schedules.length === 0 && <Empty>No schedules made here yet.</Empty>}
        {schedules.map((s) => (
          <Row
            key={s.id}
            title={`${s.name}${s.enabled ? "" : " (off)"}`}
            about={`${describe(s)}. Next: ${s.next || "-"}. Last: ${s.last_run ? `${when(s.last_run)}, ${s.last_result || ""}` : "never"}.`}
            actions={
              <>
                <Button small need="admin" onClick={() => call("PUT", "/api/schedules", { id: s.id, enabled: !s.enabled }, s.enabled ? "Turned off." : "Turned on.")}>
                  {s.enabled ? "Turn off" : "Turn on"}
                </Button>
                <Button
                  small
                  kind="danger"
                  need="admin"
                  onClick={() =>
                    ask({ message: `Delete the schedule ${s.name}?`, yes: "Yes, delete", danger: true, onYes: () => call("POST", "/api/schedule-delete", { id: s.id }, "Deleted.") })
                  }
                >
                  Delete
                </Button>
              </>
            }
          />
        ))}
      </Rows>
      <h4>Add a schedule</h4>
      <div className="flex flex-col gap-2">
        <FormRow>
          <Input maxLength={60} placeholder="Name" aria-label="Schedule name" value={name} onChange={(e) => setName(e.target.value)} />
          <Select aria-label="What it does" value={kind} onChange={(e) => setKind(e.target.value)}>
            <option value="command">Run a command</option>
            <option value="restart">Restart (with warnings)</option>
            <option value="backup" disabled={!data?.helper}>Back up off-site</option>
          </Select>
        </FormRow>
        {kind === "command" && (
          <Input maxLength={1000} placeholder="Command, e.g. say Vote for the server!" aria-label="Command" value={command} onChange={(e) => setCommand(e.target.value)} />
        )}
        <FormRow>
          <Select
            aria-label="How often"
            value={type}
            onChange={(e) => setType(e.target.value)}
            options={[
              { value: "daily", label: "Every day" },
              { value: "weekly", label: "Every week" },
              { value: "interval", label: "Every N minutes" },
            ]}
          />
          {type === "weekly" && <Select aria-label="Day" value={day} onChange={(e) => setDay(e.target.value)} options={DAYS.map((d, i) => ({ value: String(i), label: d }))} />}
          {type !== "interval" && <Input type="time" aria-label="Time" value={time} onChange={(e) => setTime(e.target.value)} />}
          {type === "interval" && (
            <Input type="number" min={10} max={10080} aria-label="Minutes between runs" value={minutes} onChange={(e) => setMinutes(e.target.value)} />
          )}
          <Select
            aria-label="Whether it depends on who is online"
            value={only}
            onChange={(e) => setOnly(e.target.value)}
            options={[
              { value: "always", label: "Whoever is online" },
              { value: "empty", label: "Only when nobody is online" },
              { value: "players", label: "Only when someone is online" },
            ]}
          />
        </FormRow>
        <Actions>
          <Button kind="primary" need="admin" onClick={add}>Add schedule</Button>
        </Actions>
      </div>
    </Panel>
  );
}
