// The console: the server's log, a box to run a command (or, under Chat, to say something), the saved commands and
// the list of commands a moderator login may run. tools/staff_panel.py answers /api/console and /api/command.
import { memo, useCallback, useLayoutEffect, useRef, useState } from "react";
import { api, get, query } from "../../lib/api";
import { useBus } from "../../lib/bus";
import { useMessages, usePoll } from "../../lib/hooks";
import type { TabProps } from "../../shell/tabs";
import { Button, Input, Message, PageHead, Panel, Panels, Toggles } from "../../ui/kit";
import ModCommands from "./ModCommands";
import Saved from "./Saved";

const CONSOLE_MS = 2_000; // how often the log is asked for new lines while its tab is open
const LOG_LINES = 1500; // older lines drop off the top of the console
const HISTORY_CMDS = 100;

// A line of the log as the game writes it: [12:00:00] [Server thread/INFO]: text. A line without that start
// belongs to the one before it (a stack trace under its error).
const LOG_HEAD = /^\[\d\d:\d\d:\d\d\] \[[^\]]*\/(INFO|WARN|ERROR|FATAL)\](?: \[[^\]]*\])?: (.*)$/;
// What players and the server said, and who came and went: <Name> text, [Server] text, [Name] text (say from a
// player), with the game's own "[Not Secure] " in front or not.
const CHAT = /^(?:\[Not Secure\] )?(?:<[^>]{1,40}> |\[Server\] |\[[A-Za-z0-9_]{3,16}\] )|^[A-Za-z0-9_]{3,16} (?:joined|left) the game$/;

type View = "all" | "chat" | "problems";

interface Line {
  id: number;
  text: string;
  /** warn, error, chat, more (a continuation, with its level), sent (a command of ours), out (the answer) or "". */
  kind: string;
}

const VIEWS: { value: View; label: string }[] = [
  { value: "all", label: "Everything" },
  { value: "chat", label: "Chat" },
  { value: "problems", label: "Warnings and errors" },
];

/** Whether a line shows under the view and the filter chosen. The page's own lines (a command, its answer) show
 * under Everything only. */
function lineShows(line: Line, view: View, filter: string) {
  const kinds = line.kind.split(" ");
  if (view === "chat" && !kinds.includes("chat")) return false;
  if (view === "problems" && !kinds.includes("warn") && !kinds.includes("error")) return false;
  return !filter || line.text.toLowerCase().includes(filter);
}

const LOG_CLASS: Record<string, string> = { chat: "text-bone", out: "text-sage" };

const LogLine = memo(function LogLine({ line }: { line: Line }) {
  const names = line.kind.split(" ").filter(Boolean);
  const own = names.map((k) => LOG_CLASS[k]).filter(Boolean);
  return <div className={[...names.filter((k) => k !== "more" && k !== "chat" && k !== "out"), ...own].join(" ")}>{line.text}</div>;
});

export default function ConsoleTab({ active }: TabProps) {
  const m = useMessages();
  const { fail, setError } = m;
  const [lines, setLines] = useState<Line[]>([]);
  const [view, setView] = useState<View>("all");
  const [filter, setFilter] = useState("");
  const [cmd, setCmd] = useState("");
  const [sending, setSending] = useState(false);
  const next = useRef(1);
  const offset = useRef<number | null>(null);
  const level = useRef("");
  const polling = useRef(false);
  const busy = useRef(false);   // a command is on its way: state alone lets a quick second Enter through
  const history = useRef<string[]>([]);
  const at = useRef(0);
  const log = useRef<HTMLDivElement>(null);
  const stuck = useRef(true);
  const input = useRef<HTMLInputElement>(null);

  // The classes of a line from the log: its level, and whether it is chat.
  const kindOf = (text: string) => {
    const head = LOG_HEAD.exec(text);
    if (!head) return `${level.current} more`; // a continuation: as the line it hangs under, without its mark
    level.current = head[1] === "WARN" ? "warn" : head[1] === "INFO" ? "" : "error";
    return level.current || (CHAT.test(head[2]) ? "chat" : "");
  };

  const addLines = useCallback((texts: string[], kind?: string) => {
    const made = texts.map((text) => ({ id: next.current++, text, kind: kind === undefined ? kindOf(text) : kind }));
    setLines((old) => [...old, ...made].slice(-LOG_LINES));
  }, []);

  const filtered = filter.trim().toLowerCase();
  const shown = lines.filter((l) => lineShows(l, view, filtered));

  // Stay at the bottom while the reader is there; a new view or filter goes to the bottom too.
  useLayoutEffect(() => {
    if (stuck.current && log.current) log.current.scrollTop = log.current.scrollHeight;
  }, [lines, active]);
  useLayoutEffect(() => {
    if (log.current) log.current.scrollTop = log.current.scrollHeight;
    stuck.current = true;
  }, [view, filtered]);

  const tick = async () => {
    if (polling.current) return;
    polling.current = true;
    try {
      const after = offset.current === null ? "" : `?${query({ after: offset.current })}`;
      const data = await get(`/api/console${after}`);
      if (data.reset) {
        setLines([]);
        level.current = "";
      }
      addLines(data.lines || []);
      offset.current = data.offset;
      setError("");
    } catch (e) {
      fail(e);
    }
    polling.current = false;
  };
  usePoll(tick, CONSOLE_MS, active);

  // `given`: a saved command (or another tab's), sent as it is. Otherwise what is in the box: a command, or under
  // Chat a message for everyone unless it starts with /.
  const send = async (given?: string) => {
    const typed = typeof given === "string" ? given : cmd.trim();
    if (!typed) return;
    if (busy.current) {
      // One at a time, so a kick or ban is never sent twice; what is typed stays in the box.
      if (typeof given === "string") addLines([`Not sent: ${typed}. Wait for the last command's answer, then run it again.`], "out");
      return;
    }
    const saying = typeof given !== "string" && view === "chat" && !typed.startsWith("/");
    const command = saying ? `say ${typed}` : typed;
    // Kept as a command (with its /), so Up then Enter sends it again as it went, in Chat too: never "say say hi".
    const kept = saying ? `/${command}` : command;
    if (history.current[history.current.length - 1] !== kept) history.current.push(kept);
    if (history.current.length > HISTORY_CMDS) history.current.shift();
    at.current = history.current.length;
    if (typeof given !== "string") setCmd("");
    addLines([`> ${command}`], "sent");
    const first = command.replace(/^\//, "").split(/\s+/)[0].toLowerCase();
    if (first === "stop") {
      addLines(["Not sent. Use the Server tab to stop or restart the server."], "out");
      return;
    }
    if (first === "seed") {
      addLines(["Not sent. The world seed is kept secret."], "out");
      return;
    }
    busy.current = true;
    setSending(true);
    try {
      const data = await api("POST", "/api/command", { command });
      const output = String(data.output || "").split("\n").filter((line) => line.trim());
      addLines(output.length ? output : ["(no output)"], "out");
      setError("");
    } catch (e) {
      fail(e);
    }
    busy.current = false;
    setSending(false);
    input.current?.focus();
  };

  // A saved command's Run button, or another tab: sent as if typed here, so it shows in the log with its answer.
  useBus("run-command", (detail) => void send(String(detail.command)));

  const key = (e: React.KeyboardEvent<HTMLInputElement>) => {
    const past = history.current;
    if (e.key === "Enter") {
      e.preventDefault();
      void send();
    } else if (e.key === "ArrowUp" && past.length) {
      e.preventDefault();
      at.current = Math.max(0, at.current - 1);
      setCmd(past[at.current]);
    } else if (e.key === "ArrowDown" && past.length) {
      e.preventDefault();
      at.current = Math.min(past.length, at.current + 1);
      setCmd(past[at.current] || "");
    }
  };

  const chat = view === "chat";
  const narrowed = view !== "all" || filtered;

  return (
    <>
      <PageHead title="Console">
        <p>
          Commands run as the server console. To stop or restart the server, use the Server tab. The lines the game logs
          each time a scheduled job connects (RCON) are left out; Files, logs has the whole file while it is under 2 MB.
        </p>
      </PageHead>
      <Panels>
        <Panel
          wide
          title="Server log"
          meta={narrowed ? `${shown.length} of ${lines.length} lines` : undefined}
          aside={<Toggles label="Which lines to show" value={view} options={VIEWS} onChange={setView} />}
        >
          <Message kind="error">{m.error}</Message>
          <Input
            type="search"
            maxLength={100}
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            placeholder="Only lines with..."
            aria-label="Show only lines with this text"
          />
          <div
            ref={log}
            className="log"
            role="log"
            tabIndex={0}
            aria-label="Server log"
            onScroll={(e) => {
              const box = e.currentTarget;
              stuck.current = box.scrollHeight - box.scrollTop - box.clientHeight < 40;
            }}
          >
            {shown.map((line) => (
              <LogLine key={line.id} line={line} />
            ))}
          </div>
          <div className="flex gap-2">
            <label className="sr-only" htmlFor="console-cmd">
              {chat ? "Message to everyone, or a command starting with /" : "Command"}
            </label>
            <Input
              id="console-cmd"
              ref={input}
              className="min-w-0 flex-1 font-mono"
              maxLength={1000}
              value={cmd}
              onChange={(e) => setCmd(e.target.value)}
              onKeyDown={key}
              placeholder={chat ? "Say something to everyone" : "list"}
            />
            <Button kind="primary" disabled={sending} onClick={() => void send()}>
              {chat ? "Say" : "Send"}
            </Button>
          </div>
          {chat && (
            <p className="fine">
              In Chat, what you type is said to everyone as the server. Start with / to run a command instead.
            </p>
          )}
        </Panel>
        <Saved active={active} onRun={(command) => void send(command)} />
        <ModCommands active={active} />
      </Panels>
    </>
  );
}
