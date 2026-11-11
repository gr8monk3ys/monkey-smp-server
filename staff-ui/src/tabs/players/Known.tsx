// Everyone who has joined, with the staff's notes on each (the old desk.js).
import { useEffect, useState } from "react";
import { get, post, query } from "../../lib/api";
import { useBus } from "../../lib/bus";
import { plural, when } from "../../lib/format";
import { useMessages, useOnShow } from "../../lib/hooks";
import { useSession } from "../../lib/session";
import { Button, Empty, Fine, FormRow, Input, Message, Messages, Panel, Row, Rows, useConfirm } from "../../ui/kit";

const KNOWN_SHOWN = 50; // players listed before "Show more"
const DAY = new Intl.DateTimeFormat(undefined, { month: "short", day: "numeric", year: "numeric" });

interface Known {
  name: string;
  last_seen?: number;
  hours?: number;
  op?: boolean;
  whitelisted?: boolean;
  banned?: boolean;
  notes?: number;
}
interface Note {
  id: string | number;
  text: string;
  by: string;
  at: unknown;
}

// How long ago, in words, for a time in seconds since 1970; a date once it is over a week.
function seen(seconds: unknown): string {
  if (typeof seconds !== "number") return "never joined";
  const minutes = Math.max(0, Math.round((Date.now() / 1000 - seconds) / 60));
  if (minutes < 2) return "seen just now";
  if (minutes < 60) return `seen ${minutes} minutes ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `seen ${plural(hours, "hour")} ago`;
  const days = Math.round(hours / 24);
  if (days <= 7) return `seen ${plural(days, "day")} ago`;
  return `seen ${DAY.format(new Date(seconds * 1000))}`;
}

export default function KnownPlayers({ active }: { active: boolean }) {
  const [rows, setRows] = useState<Known[]>([]);
  const [shown, setShown] = useState(KNOWN_SHOWN);
  const [open, setOpen] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [warning, setWarning] = useState("");
  const [version, setVersion] = useState(0); // bumps when the list is read again, so the open notes are too
  const m = useMessages();
  const [confirm, ask] = useConfirm();

  const load = async () => {
    try {
      const data = await get("/api/known-players");
      setRows((data.players || []).filter((p: Known) => p && typeof p.name === "string"));
      const unnamed: number = data.unnamed || 0;
      setWarning(
        data.world === false
          ? "The world has no players folder yet: last seen and play time show once someone has joined."
          : unnamed
            ? `${unnamed} more ${unnamed === 1 ? "player has" : "players have"} joined but the server no longer keeps ${unnamed === 1 ? "their name" : "their names"} (it keeps its 1000 most recent), so ${unnamed === 1 ? "isn't" : "aren't"} listed.`
            : "",
      );
      m.setError("");
      setVersion((v) => v + 1);
    } catch (e) {
      m.fail(e);
    }
  };
  useOnShow(load, active);
  useBus("changed", () => {
    if (active) load();
  });

  const wanted = search.trim().toLowerCase();
  const found = rows.filter((p) => !wanted || p.name.toLowerCase().includes(wanted));
  const visible = found.slice(0, shown);

  return (
    <Panel
      wide
      title="Everyone who has joined"
      meta={rows.length ? `(${rows.length})` : ""}
      aside={
        <Input
          type="search"
          className="w-full sm:w-64"
          maxLength={16}
          placeholder="Find a player"
          aria-label="Find a player by name"
          value={search}
          onChange={(e) => {
            setSearch(e.target.value);
            setShown(KNOWN_SHOWN);
          }}
        />
      }
    >
      <Fine>
        Whoever was on last comes first. Last seen is when the server last saved that player, so someone who is on now shows the last few minutes. Notes are for the staff only: players never see them.
      </Fine>
      <Message kind="warn">{warning}</Message>
      <Messages of={m} />
      {confirm}
      <Rows label="Everyone who has joined">
        {visible.map((p) => {
          const hours = typeof p.hours === "number" ? `${p.hours} ${p.hours === 1 ? "hour" : "hours"} played` : "";
          const notes = p.notes ? `${p.notes} note${p.notes === 1 ? "" : "s"}` : "";
          const marks = [p.op ? "operator" : "", p.whitelisted ? "whitelisted" : "", p.banned ? "banned" : ""].filter(Boolean);
          const isOpen = open === p.name;
          return (
            <Row
              key={p.name}
              title={<span className="wrap-anywhere">{p.name}</span>}
              about={[seen(p.last_seen), hours, ...marks, notes].filter(Boolean).join(", ")}
              actions={<Button small onClick={() => setOpen(isOpen ? null : p.name)}>{isOpen ? "Hide notes" : "Notes"}</Button>}
            >
              {isOpen && <Notes name={p.name} version={version} m={m} ask={ask} reload={load} />}
            </Row>
          );
        })}
        {!visible.length && <Empty>{rows.length ? "Nobody by that name has joined." : "Nobody has joined yet."}</Empty>}
      </Rows>
      {found.length > shown && (
        <div>
          <Button onClick={() => setShown(shown + KNOWN_SHOWN)}>Show more</Button>
        </div>
      )}
    </Panel>
  );
}

// A player's notes, under their row: the list, newest first, and a box to add one.
function Notes({ name, version, m, ask, reload }: {
  name: string;
  version: number;
  m: ReturnType<typeof useMessages>;
  ask: ReturnType<typeof useConfirm>[1];
  reload: () => Promise<void>;
}) {
  const { can } = useSession();
  const [list, setList] = useState<Note[] | null>(null);
  const [problem, setProblem] = useState("");
  const [text, setText] = useState("");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    let live = true;
    get(`/api/player-notes?${query({ name })}`)
      .then((data) => {
        if (live) {
          setList(data.notes || []);
          setProblem("");
        }
      })
      .catch((e) => live && setProblem(e.message));
    return () => {
      live = false;
    };
  }, [name, version]);

  const add = async () => {
    const t = text.trim();
    if (!t) return;
    setSaving(true);
    try {
      await post("/api/player-notes", { name, text: t });
      setText("");
      m.say(`Note added for ${name}.`);
      await reload(); // draws the list again, this player's notes with it
    } catch (e) {
      m.fail(e);
    }
    setSaving(false);
  };

  return (
    <div className="mt-3 flex flex-col gap-3 border-l-2 border-sage pl-3">
      <Rows label={`Notes about ${name}`}>
        {problem ? (
          <Empty>{problem}</Empty>
        ) : list === null ? (
          <Empty>Reading the notes...</Empty>
        ) : list.length ? (
          list.map((n) => (
            <Row
              key={n.id}
              title={<span className="wrap-anywhere">{n.text}</span>}
              about={`${n.by}, ${when(n.at)}`}
              actions={
                can("admin") && (
                  <Button
                    kind="danger"
                    small
                    onClick={() =>
                      ask({
                        message: `Delete this note about ${name}? "${n.text}"`,
                        yes: "Yes, delete",
                        danger: true,
                        onYes: async () => {
                          try {
                            await post("/api/player-note-delete", { name, id: n.id });
                            m.say("Note deleted.");
                            await reload();
                          } catch (e) {
                            m.fail(e);
                          }
                        },
                      })
                    }
                  >
                    Delete
                  </Button>
                )
              }
            />
          ))
        ) : (
          <Empty>No notes yet.</Empty>
        )}
      </Rows>
      <FormRow>
        <Input
          maxLength={500}
          placeholder="A note for the staff, e.g. warned about griefing near spawn"
          aria-label={`A new note about ${name}`}
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && add()}
        />
        <Button kind="primary" disabled={saving} onClick={add}>Add note</Button>
      </FormRow>
    </div>
  );
}
