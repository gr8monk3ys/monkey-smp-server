// Who is on, the whitelist, the operators and the bans (the old panel.js players part). These buttons type the
// console command for the staff member: POST /api/command, then the lists are read again.
import { useState } from "react";
import { get, post } from "../../lib/api";
import { emit, changed, useBus } from "../../lib/bus";
import { PLAYER_NAME } from "../../lib/format";
import { useMessages, useOnShow } from "../../lib/hooks";
import { Button, Empty, FormRow, Input, Messages, Panel, Panels, Row, Rows, useConfirm } from "../../ui/kit";

type Item = string | { name?: string; reason?: string };
interface Lists {
  online?: Item[];
  whitelist?: Item[];
  ops?: Item[];
  banned?: Item[];
  bans?: Item[];
}

const nameOf = (item: Item) => (typeof item === "string" ? item : item?.name) || "";
const reasonOf = (item: Item) => (item && typeof item === "object" && item.reason) || "";
const lower = (list: Item[] | undefined) => new Set((list || []).map((i) => nameOf(i).toLowerCase()));

export default function Roster({ active }: { active: boolean }) {
  const [data, setData] = useState<Lists>({});
  const [loaded, setLoaded] = useState(false);
  const m = useMessages();
  const [confirm, ask] = useConfirm();

  const load = async () => {
    try {
      setData(await get<Lists>("/api/players"));
      setLoaded(true);
    } catch (e) {
      m.fail(e);
    }
  };
  useOnShow(load, active);
  useBus("players-changed", () => {
    if (active) load();
  });

  const command = (text: string) =>
    m.run(async () => {
      const done = await post("/api/command", { command: text });
      const out = String(done.output || "").trim();
      m.say(out ? `Done. The server said: ${out}` : "Done.");
      await load();
      changed(); // the lists changed, and so did the record
      emit("players-changed", {});
    });

  const banned = data.banned || data.bans || [];
  const bannedNames = lower(banned);
  const opNames = lower(data.ops);
  const listed = lower(data.whitelist);
  const online = (data.online || []).filter((i) => nameOf(i));

  const ban = (name: string, why: string) => {
    // The game keeps a ban that is there ("Nothing changed"): a temporary one would then still end on time.
    if (bannedNames.has(name.toLowerCase())) {
      m.fail(new Error(`${name} is banned already. Pardon them (or lift their temporary ban) first, then ban them again.`));
      return;
    }
    ask({
      message: `Ban ${name}${why ? ` for "${why}"` : ""}? They can't join until pardoned.`,
      yes: `Yes, ban ${name}`,
      danger: true,
      onYes: () => command(`ban ${name}${why ? ` ${why}` : ""}`),
    });
  };

  return (
    <>
      <Messages of={m} />
      {confirm}
      <Panel
        wide
        title="Online now"
        meta={loaded ? online.length : ""}
        aside={<span className="fine">Kick types the console command for you.</span>}
      >
        <Rows label="Online now">
          {online.map((item) => {
            const name = nameOf(item);
            const marks = [opNames.has(name.toLowerCase()) && "operator", listed.has(name.toLowerCase()) && "whitelisted"].filter(Boolean);
            return (
              <Row
                key={name}
                title={<span className="wrap-anywhere">{name}</span>}
                about={marks.join(", ")}
                actions={
                  <Button
                    kind="danger"
                    small
                    onClick={() =>
                      ask({
                        message: `Kick ${name}? They are disconnected now and can join again at once.`,
                        yes: `Yes, kick ${name}`,
                        danger: true,
                        field: { label: "Reason", placeholder: "Reason they will see (optional)", max: 120 },
                        onYes: (why) => command(`kick ${name}${why ? ` ${why}` : ""}`),
                      })
                    }
                  >
                    Kick
                  </Button>
                }
              />
            );
          })}
          {loaded && !online.length && <Empty>Nobody is on.</Empty>}
        </Rows>
      </Panel>
      <Panels className="mt-4">
        <NameList
          title="Whitelist"
          none="Nobody is on the whitelist."
          items={data.whitelist || []}
          m={m}
          remove={{
            label: "Remove",
            danger: true,
            ask: (n) => `Take ${n} off the whitelist? They can't join until they are added again.`,
            yes: (n) => `Yes, remove ${n}`,
            run: (n) => command(`whitelist remove ${n}`),
            ask_fn: ask,
          }}
          add={{ label: "Add", run: (n) => command(`whitelist add ${n}`) }}
        />
        <NameList
          title="Operators"
          none="There are no operators."
          items={data.ops || []}
          m={m}
          remove={{
            label: "Deop",
            danger: true,
            ask: (n) => `Take operator away from ${n}? They lose the operator commands at once.`,
            yes: (n) => `Yes, deop ${n}`,
            run: (n) => command(`deop ${n}`),
            ask_fn: ask,
          }}
          add={{
            label: "Make operator",
            run: (n) =>
              ask({
                message: `Make ${n} an operator? Operators can run most commands in the game.`,
                yes: `Yes, make ${n} operator`,
                onYes: () => command(`op ${n}`),
              }),
          }}
        />
        <NameList
          wide
          title="Banned"
          none="Nobody is banned."
          items={banned}
          m={m}
          remove={{
            label: "Pardon",
            ask: (n) => `Pardon ${n}? They can join again at once.`,
            yes: (n) => `Yes, pardon ${n}`,
            run: (n) => command(`pardon ${n}`),
            ask_fn: ask,
          }}
          add={{ label: "Ban", reason: true, danger: true, run: ban }}
        />
      </Panels>
    </>
  );
}

interface Spec {
  title: string;
  none: string;
  items: Item[];
  wide?: boolean;
  m: ReturnType<typeof useMessages>;
  remove: {
    label: string;
    danger?: boolean;
    ask: (name: string) => string;
    yes: (name: string) => string;
    run: (name: string) => void;
    ask_fn: ReturnType<typeof useConfirm>[1];
  };
  add: { label: string; reason?: boolean; danger?: boolean; run: (name: string, reason: string) => void };
}

function NameList({ title, none, items, wide, m, remove, add }: Spec) {
  const [name, setName] = useState("");
  const [reason, setReason] = useState("");
  const names = items.filter((i) => nameOf(i));
  const go = () => {
    const typed = name.trim();
    if (!PLAYER_NAME.test(typed)) {
      m.fail(new Error("A name is 3 to 16 letters, digits or underscores."));
      return;
    }
    m.clear();
    add.run(typed, reason.replace(/\s+/g, " ").trim());
    setName("");
    setReason("");
  };
  const enter = (e: React.KeyboardEvent) => {
    if (e.key === "Enter") go();
  };
  return (
    <Panel title={title} meta={names.length || ""} wide={wide}>
      <Rows label={title}>
        {names.map((item) => {
          const n = nameOf(item);
          const why = reasonOf(item);
          return (
            <Row
              key={n}
              title={<span className="wrap-anywhere">{n}</span>}
              about={why ? `(${why})` : undefined}
              actions={
                <Button
                  kind={remove.danger ? "danger" : "ghost"}
                  small
                  onClick={() =>
                    remove.ask_fn({
                      message: remove.ask(n),
                      yes: remove.yes(n),
                      danger: remove.danger,
                      onYes: () => remove.run(n),
                    })
                  }
                >
                  {remove.label}
                </Button>
              }
            />
          );
        })}
        {!names.length && <Empty>{none}</Empty>}
      </Rows>
      <FormRow>
        <Input maxLength={16} placeholder="Player name" aria-label={`${add.label}: player name`} value={name} onChange={(e) => setName(e.target.value)} onKeyDown={enter} />
        {add.reason && (
          <Input maxLength={120} placeholder="Reason (optional)" aria-label="Reason" value={reason} onChange={(e) => setReason(e.target.value)} onKeyDown={enter} />
        )}
        <Button kind={add.danger ? "danger" : "primary"} onClick={go}>
          {add.label}
        </Button>
      </FormRow>
    </Panel>
  );
}
