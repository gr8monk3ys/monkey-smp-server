// The event timer (a boss bar with the minutes left) and the leaderboard update. Admins only.
import { useState } from "react";
import { get, post } from "../../lib/api";
import { useMessages, usePoll } from "../../lib/hooks";
import { useSession } from "../../lib/session";
import { Actions, Button, Fine, FormRow, Input, Messages, Panel, useConfirm } from "../../ui/kit";

const POLL_MS = 15_000;

interface Timer {
  running?: boolean;
  name?: string;
  minutes?: number;
}

export default function Events({ active }: { active: boolean }) {
  const { can } = useSession();
  const m = useMessages();
  const [confirm, ask] = useConfirm();
  const [timer, setTimer] = useState<Timer | null>(null);
  const [busy, setBusy] = useState(false);
  const [boardBusy, setBoardBusy] = useState(false);
  const [name, setName] = useState("");
  const [minutes, setMinutes] = useState("30");

  const load = async () => {
    try {
      setTimer((await get("/api/event-timer")).timer);
      m.setError("");
    } catch (error) {
      setTimer(null);
      m.fail(error);
    }
  };
  const admin = can("admin");
  usePoll(() => { if (!busy) load(); }, POLL_MS, active && admin);
  if (!admin) return null;

  const act = async (body: Record<string, unknown>) => {
    setBusy(true);
    m.clear();
    try {
      const done = await post("/api/event-timer", body);
      setTimer(done.timer);
      m.say(done.note || "Stopped.");
    } catch (error) {
      m.fail(error);
    }
    setBusy(false);
  };

  const start = () => {
    const label = name.trim();
    const n = Number(minutes);
    if (!label) {
      m.clear();
      m.fail(new Error("Type the event's name."));
      return;
    }
    if (!Number.isInteger(n) || n < 1 || n > 600) {
      m.clear();
      m.fail(new Error("Minutes: a whole number from 1 to 600."));
      return;
    }
    act({ action: "start", name: label, minutes: n });
  };

  const updateBoard = async () => {
    setBoardBusy(true);
    m.clear();
    m.say("Saving the world, then updating the leaderboard. This can take a minute.");
    try {
      const done = await post("/api/leaderboard", {});
      m.clear();
      m.say(done.note);
    } catch (error) {
      m.clear();
      m.fail(error);
    }
    setBoardBusy(false);
  };

  const running = Boolean(timer && timer.running);
  let state = "Checking";
  if (timer === null) state = "The timer's state isn't known.";
  else if (running) state = `Running: ${timer.name || "an event"}, ${timer.minutes === 1 ? "1 min left" : `${timer.minutes} min left`}.`;
  else state = "No event timer is running.";

  return (
    <Panel title="Event timer" wide>
      <Fine>
        A boss bar with the minutes left for everyone, warnings at 10, 5 and 1 minute, and an "Event over" title at the end. One at a time, apart from the
        raid and Anarchy timers. Give the Cup points by hand, then update the leaderboard.
      </Fine>
      <Messages of={m} />
      <p className="font-bold text-bone" role="status">{state}</p>
      <FormRow>
        <Input maxLength={40} placeholder="Event name, e.g. Boat Race" aria-label="Event name" value={name} onChange={(e) => setName(e.target.value)} />
        <Input type="number" min={1} max={600} aria-label="Minutes" className="max-w-28 basis-24" value={minutes} onChange={(e) => setMinutes(e.target.value)} />
        <Button kind="primary" disabled={busy || running} onClick={start}>Start</Button>
      </FormRow>
      <Actions>
        <Button
          disabled={busy || !running}
          onClick={() => ask({ message: 'End the event now? Everyone sees "Event over".', yes: "End it", onYes: () => act({ action: "finish" }) })}
        >
          End now (Event over)
        </Button>
        <Button
          disabled={busy || !running}
          onClick={() => ask({ message: 'Stop the timer? It goes away with no "Event over".', yes: "Stop it", onYes: () => act({ action: "stop" }) })}
        >
          Stop early (no Event over)
        </Button>
        <Button disabled={boardBusy} onClick={updateBoard}>Update the leaderboard now</Button>
      </Actions>
      {confirm}
    </Panel>
  );
}
