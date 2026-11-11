// The record of changes made from the page, newest first, searchable and downloadable.
import { useCallback, useEffect, useState } from "react";
import { get, query } from "../../lib/api";
import { useBus } from "../../lib/bus";
import { when } from "../../lib/format";
import { useDebounced, useMessages } from "../../lib/hooks";
import { Actions, Button, Empty, Fine, FormRow, Input, Messages, Panel, Row, Rows, Select } from "../../ui/kit";

const SEARCH_MS = 250;           // a pause in typing before the record is searched

interface Change {
  action?: string;
  target?: string;
  user?: string;
  time?: unknown;
}

export default function Activity({ active }: { active: boolean }) {
  const m = useMessages();
  const [user, setUser] = useState("");
  const [kind, setKind] = useState("");
  const [text, setText] = useState("");
  const q = useDebounced(text.trim(), SEARCH_MS);
  const [users, setUsers] = useState<string[]>([]);
  const [kinds, setKinds] = useState<string[]>([]);
  const [rows, setRows] = useState<Change[] | null>(null);
  const [more, setMore] = useState<number | null>(null);
  const [cut, setCut] = useState(false);

  const params = { user, action: kind, q };

  const load = useCallback(
    async (older: boolean, before: number | null) => {
      try {
        const data = await get(`/api/activity?${query({ ...params, before: older && before !== null ? before : undefined })}`);
        if (!older) {
          setUsers(data.users || []);
          setKinds(data.kinds || []);
          // The menus keep what is picked, unless it is gone from the record.
          if (user && !(data.users || []).includes(user)) setUser("");
          if (kind && !(data.kinds || []).includes(kind)) setKind("");
        }
        setRows((old) => (older ? [...(old || []), ...(data.actions || [])] : data.actions || []));
        setMore(data.more ?? null);
        setCut(Boolean(data.cut));
        m.setError("");
      } catch (error) {
        m.fail(error);
      }
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [user, kind, q],
  );

  useEffect(() => {
    if (active) load(false, null);
  }, [active, load]);
  // Something was changed on another tab (a power action, a player list).
  useBus("changed", () => {
    if (active) load(false, null);
  });

  const anyFilter = Boolean(user || kind || q);
  return (
    <Panel title="Changes made here" wide>
      <Fine>Every command, save, upload and power action from this page, newest first: who did it and when.</Fine>
      <Messages of={m} />
      <FormRow>
        <Select aria-label="Whose changes" value={user} onChange={(e) => setUser(e.target.value)}>
          <option value="">Everyone</option>
          {users.map((u) => <option key={u} value={u}>{u}</option>)}
        </Select>
        <Select aria-label="Which kind of change" value={kind} onChange={(e) => setKind(e.target.value)}>
          <option value="">Every kind</option>
          {kinds.map((k) => <option key={k} value={k}>{k}</option>)}
        </Select>
        <Input type="search" maxLength={100} placeholder="With this text" aria-label="Only changes with this text" value={text} onChange={(e) => setText(e.target.value)} />
      </FormRow>
      <Rows label="Changes made here">
        {rows && rows.length === 0 && <Empty>{anyFilter ? "No changes match." : "Nothing yet."}</Empty>}
        {(rows || []).map((a, i) => (
          <Row key={i} title={[a.action, a.target].filter(Boolean).join(" ")} about={[a.user, when(a.time)].filter(Boolean).join(", ")} />
        ))}
      </Rows>
      {cut && <Fine>The record is longer than this page reads: the oldest changes are in actions.log on the machine.</Fine>}
      <Actions>
        {more !== null && <Button onClick={() => load(true, more)}>Show older</Button>}
        <a className="btn" href={`/api/activity-export?${query(params)}`} download>Download as a .csv file</a>
      </Actions>
    </Panel>
  );
}
