// Power first: the server's state, start / restart / stop, and the errors logged since a restart pressed here.
import { useState } from "react";
import { get, listOf, post } from "../../lib/api";
import { changed } from "../../lib/bus";
import { when } from "../../lib/format";
import { useMessages, useOnShow, usePoll } from "../../lib/hooks";
import { playersOn, useStatus } from "../../lib/status";
import { Actions, Button, Facts, Fine, Mark, Messages, Panel, Row, Rows, useConfirm, type MarkKind } from "../../ui/kit";

const POWER_MS = 5_000;          // how often the server's state is asked again
const ERRORS_SHOWN = 8;
// That a restart or start was pressed here, and the server's start time just before it ("before"): the errors shown
// are those after the server's next start time, which GET /api/power says (its "since" when running). A normal
// restart waits 5 minutes, so the time of the click is not when the server started.
const PRESSED_KEY = "monkey-panel-pressed";

type Action = "restart" | "restart-now" | "stop" | "start";

const POWER: Record<Action, [string, string, string]> = {
  "restart": ["Restart in 5 minutes? Players get a warning in chat, then the server restarts and is back after a few minutes.", "Yes, restart", "Restart with a 5-minute warning started."],
  "restart-now": ["Restart right now? Nobody gets a warning: players are disconnected at once and can rejoin after a few minutes.", "Yes, restart now", "Restarting now."],
  "stop": ["Stop the server? Players are disconnected, and it stays off until someone presses Start.", "Yes, stop", "Stopping."],
  "start": ["Start the server? It takes a few minutes before players can join.", "Yes, start", "Starting."],
};

const STATES: Record<string, [MarkKind, string]> = {
  running: ["good", "Running"],
  stopped: ["off", "Stopped"],
  restarting: ["busy", "Restarting"],
};

interface Pressed {
  before: string | null;
}

// sessionStorage can throw (storage off, a private window): then the page works without remembering.
function pressedRead(): Pressed | null {
  try {
    const kept = JSON.parse(sessionStorage.getItem(PRESSED_KEY) || "null");
    return kept && typeof kept === "object" ? kept : null;
  } catch {
    return null;
  }
}

function pressedWrite(value: Pressed) {
  try {
    sessionStorage.setItem(PRESSED_KEY, JSON.stringify(value));
  } catch {
    /* not kept: no error list after this restart */
  }
}

export function Power({ active }: { active: boolean }) {
  const m = useMessages();
  const status = useStatus();
  const [confirm, ask] = useConfirm();
  const [power, setPower] = useState<{ state?: string; since?: string | null } | null>(null);
  const [pressed, setPressed] = useState<Pressed | null>(pressedRead);

  const load = async () => {
    try {
      const data = await get("/api/power");
      setPower({ state: data.state, since: data.since || null });
      m.setError("");
    } catch (error) {
      m.fail(error);
    }
  };
  usePoll(load, POWER_MS, active);

  const doPower = async (action: Action) => {
    m.clear();
    try {
      await post("/api/power", { action });
      m.say(POWER[action][2]);
      if (action !== "stop") {
        const next = { before: power?.state === "running" ? power.since || null : null };
        pressedWrite(next);
        setPressed(next);
      }
    } catch (error) {
      m.fail(error);
    }
    load();
    changed();
  };

  const press = (action: Action) => {
    // With no fresh reading the step says so: silence would read as "nobody is on".
    const on = playersOn(status);
    let who = "";
    if (action !== "start") {
      if (on === null) who = " The page can't tell how many players are on right now.";
      else if (on > 0) who = ` ${on === 1 ? "1 player is" : `${on} players are`} on right now.`;
    }
    ask({ message: POWER[action][0] + who, yes: POWER[action][1], danger: action === "stop" || action === "restart-now", onYes: () => doPower(action) });
  };

  const [kind, word]: [MarkKind, string] = (power?.state && STATES[power.state]) || ["unknown", power ? "Unknown" : "Checking"];
  const stopped = power?.state === "stopped";

  // The errors logged since the server started again after a restart or start pressed here: staff.json's groups
  // (tools/staff_status.py), whose last line came after that start. The file is written every 2 minutes, so it lags.
  const started = pressed && power?.state === "running" && power.since && power.since !== pressed.before ? Date.parse(power.since) : NaN;
  let head = "";
  let errors: { text: string; last: string }[] = [];
  if (pressed) {
    if (Number.isNaN(started)) head = "Errors since your restart show here once the server has started again.";
    else if (!status.data) head = status.trouble || status.missing ? "The errors since your restart can't be read right now." : "";
    else {
      errors = listOf<{ text: string; last: string }>(status.data.problems, "errors").filter((e) => Date.parse(e.last) >= started);
      head = errors.length
        ? `Errors logged since the server started again at ${when(started)}:`
        : `No errors logged since the server started again at ${when(started)}. The list updates every 2 minutes.`;
    }
  }

  return (
    <Panel title="Power">
      <Messages of={m} />
      <p className="flex items-center gap-3 text-xl font-bold text-bone" role="status">
        <Mark kind={kind} />
        <span>{power?.since ? `${word}, since ${when(power.since)}` : word}</span>
      </p>
      <Actions className="gap-3">
        <Button kind={stopped ? "ghost" : "primary"} onClick={() => press("restart")}>Restart (5-minute warning)</Button>
        <Button kind={stopped ? "primary" : "ghost"} onClick={() => press("start")}>Start</Button>
      </Actions>
      <Actions className="gap-3">
        <Button kind="danger" onClick={() => press("restart-now")}>Restart now</Button>
        <Button kind="danger" onClick={() => press("stop")}>Stop</Button>
      </Actions>
      {confirm}
      {pressed && head && (
        <div>
          <Fine>{head}</Fine>
          {errors.length > 0 && (
            <Rows label="Errors since your restart">
              {errors.slice(0, ERRORS_SHOWN).map((e, i) => (
                // e.count covers the whole window staff.json reads, so only the last time is said.
                <Row key={i} title={<span className="font-mono text-sm font-normal">{`${e.text} (last seen ${when(e.last)})`}</span>} />
              ))}
            </Rows>
          )}
        </div>
      )}
    </Panel>
  );
}

export function LastBackup({ active }: { active: boolean }) {
  const m = useMessages();
  const [backup, setBackup] = useState<any>(null);

  useOnShow(async () => {
    try {
      const data = await get("/api/backups");
      setBackup(data.backups || data);
      m.setError("");
    } catch (error) {
      m.fail(error);
    }
  }, active);

  // The hourly backups go off-site; the copy on this machine is the one a deploy takes before it updates.
  const offsite: Record<string, string> = { on: "On, every hour", failing: "Failing", "not set up": "Not set up" };
  return (
    <Panel title="Last backup">
      <Messages of={m} />
      {backup && (
        <Facts
          items={[
            ["Off-site", offsite[backup.offsite] || backup.offsite || "Unknown"],
            ["Copy before the last update", backup.local ? when(backup.local) : "None found"],
          ]}
        />
      )}
    </Panel>
  );
}
