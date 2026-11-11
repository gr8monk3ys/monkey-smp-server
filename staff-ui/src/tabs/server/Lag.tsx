// The lag finder: runs spark's profiler for a while, then links its report.
import { useState } from "react";
import { get, post } from "../../lib/api";
import { changed } from "../../lib/bus";
import { when } from "../../lib/format";
import { useMessages, usePoll } from "../../lib/hooks";
import { useSession } from "../../lib/session";
import { Actions, Button, Fine, FormRow, Messages, Panel, Select } from "../../ui/kit";

const SPARK_POLL_MS = 5_000;
const SPARK_LINK = /^https:\/\/spark\.lucko\.me\/[A-Za-z0-9]{6,32}$/;
const SPARK_MODES: Record<string, string> = { cpu: "everything the game does", lag: "lag spikes", memory: "memory" };

export default function Lag({ active }: { active: boolean }) {
  const { can } = useSession();
  const m = useMessages();
  const [data, setData] = useState<any>(null);
  const [mode, setMode] = useState("cpu");
  const [seconds, setSeconds] = useState("120");

  const load = async () => {
    try {
      setData(await get("/api/spark"));
      m.setError("");
    } catch (error) {
      m.fail(error);
    }
  };
  // Asked again every 5 seconds while a run is going or its report is on the way (and once when the tab opens).
  usePoll(load, SPARK_POLL_MS, active && Boolean(data?.running || data?.waiting));
  usePoll(load, 60 * SPARK_POLL_MS, active && !(data?.running || data?.waiting));

  const call = async (url: string, body: unknown, words: string) => {
    m.clear();
    try {
      await post(url, body);
      m.say(words);
    } catch (error) {
      m.fail(error);
    }
    load();
    changed();
  };

  const run = data?.run;
  const link: string | null = run && typeof run.link === "string" && SPARK_LINK.test(run.link) ? run.link : null;
  let words = "";
  if (data) {
    words = data.installed ? "No run yet." : "spark isn't in the server's mods, so this can't run.";
    if (run) {
      const what = `${SPARK_MODES[run.mode] || run.mode}, started by ${run.by} ${when(run.at)}`;
      if (data.running) words = `Running (${what}). It ends at ${when(run.ends)}; the report link shows here then.`;
      else if (link) words = `The last run (${what}) is ready.`;
      else if (data.waiting) words = `Finished (${what}). Waiting for spark to upload the report...`;
      else if (run.lost) words = `The server restarted during the last run (${what}), so it has no report.`;
      else words = `The last run (${what}) left no report link in the log. The Console tab has spark's own words.`;
    }
  }

  return (
    <Panel title="Find what causes lag" wide>
      <Fine>
        Runs spark's profiler for a while, then links its report: which mods, entities and chunks the game spends its time on. Run it while the server is
        slow, with players on. "Lag spikes" only looks at ticks over 100 ms; "Memory" at what fills the memory.
      </Fine>
      <Messages of={m} />
      <Fine role="status">{words}</Fine>
      {link && (
        <p>
          <a className="btn btn-primary" href={link} target="_blank" rel="noopener noreferrer">Open the report</a>
        </p>
      )}
      <FormRow>
        <Select
          aria-label="What to look at"
          value={mode}
          onChange={(e) => setMode(e.target.value)}
          options={[
            { value: "cpu", label: "Everything the game does" },
            { value: "lag", label: "Lag spikes only" },
            { value: "memory", label: "Memory" },
          ]}
        />
        <Select
          aria-label="For how long"
          value={seconds}
          onChange={(e) => setSeconds(e.target.value)}
          options={[
            { value: "60", label: "1 minute" },
            { value: "120", label: "2 minutes" },
            { value: "300", label: "5 minutes" },
            { value: "600", label: "10 minutes" },
          ]}
        />
      </FormRow>
      <Actions>
        {!data?.running && (
          <Button
            kind="primary"
            disabled={!can("admin") || !data?.installed}
            title={!can("admin") ? "Needs an admin login" : undefined}
            onClick={() => call("/api/spark", { mode, seconds: Number(seconds) }, "Started. Keep playing as normal: the report comes when it ends.")}
          >
            Start
          </Button>
        )}
        {data?.running && can("admin") && (
          <Button onClick={() => call("/api/spark-stop", {}, "Stopped. spark is uploading what it has.")}>Stop now</Button>
        )}
      </Actions>
    </Panel>
  );
}
