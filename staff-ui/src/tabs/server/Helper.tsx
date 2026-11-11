// Backups from here: the root helper's backup, the snapshot list, restore (owner), and what the helper did last.
import { useState } from "react";
import { get } from "../../lib/api";
import { size, when } from "../../lib/format";
import { useMessages, useOnShow } from "../../lib/hooks";
import { useSession } from "../../lib/session";
import { Actions, Button, Empty, Fine, Messages, Panel, Row, Rows, useConfirm } from "../../ui/kit";
import { askHelper, useAlive, useJobFeed, type Job } from "./ask";

interface Snapshot {
  id: string;
  short_id: string;
  time: unknown;
  tags?: string[];
  size?: number;
}

export default function Helper({ active }: { active: boolean }) {
  const { can } = useSession();
  const m = useMessages();
  const alive = useAlive();
  const [confirm, ask] = useConfirm();
  const [installed, setInstalled] = useState<boolean | null>(null);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [snaps, setSnaps] = useState<Snapshot[]>([]);
  const [listedAt, setListedAt] = useState<unknown>(null);

  useJobFeed((data) => setJobs(data.jobs || []));

  const loadSnapshots = async () => {
    try {
      const data = await get("/api/snapshots");
      setSnaps((data.snapshots || []).slice(0, 60));
      setListedAt(data.time || null);
    } catch (error) {
      m.fail(error);
    }
  };

  const load = async () => {
    try {
      const data = await get("/api/helper");
      setInstalled(Boolean(data.installed));
      setJobs(data.jobs || []);
      if (data.installed && can("admin")) loadSnapshots();
    } catch (error) {
      m.fail(error);
    }
  };
  useOnShow(load, active);

  const run = async (url: string, words: string, then: () => void) => {
    await askHelper(url, undefined, words, m, alive);
    then();
  };

  const restore = (s: Snapshot) =>
    ask({
      message: `Put the world back as it was at ${when(s.time)}? Players are warned, the server stops for a few minutes, and everything built since then is gone from the live world (the current world is kept in backups/ on the machine).`,
      yes: "Restore this snapshot",
      danger: true,
      word: s.short_id,
      onYes: (typed) => askHelper("/api/world-restore", { snapshot: s.id, confirm: typed }, "Restore asked for.", m, alive),
    });

  return (
    <Panel title="Backups from here" wide>
      <Messages of={m} />
      {installed === false && (
        <Fine>
          The backup helper isn't installed, so backups can't be started or restored from here. The owner installs it once on the
          machine: <code className="font-mono">sudo sh /srv/monkey/repo/deploy/monkey-staff.sh --install-helper</code>
        </Fine>
      )}
      {installed && (
        <>
          <Actions>
            <Button need="admin" onClick={() => run("/api/backup-now", "Backup asked for.", load)}>Back up now</Button>
            <Button need="admin" onClick={() => run("/api/snapshots", "Snapshot list asked for.", loadSnapshots)}>List the snapshots</Button>
          </Actions>
          {confirm}
          {listedAt ? <Fine>{`Listed ${when(listedAt)}.`}</Fine> : null}
          <Rows label="Snapshots">
            {snaps.length === 0 && <Empty>{listedAt ? "No snapshots." : "Not listed yet: press List the snapshots."}</Empty>}
            {snaps.map((s) => (
              <Row
                key={s.id}
                title={`${s.short_id} ${when(s.time)}`}
                about={[(s.tags || []).join(" "), size(s.size)].filter(Boolean).join(", ")}
                actions={can("owner") && <Button small need="owner" onClick={() => restore(s)}>Restore</Button>}
              />
            ))}
          </Rows>
          <Fine>
            Only an owner can restore, and types the snapshot's short ID to confirm. The world as it was is kept on the machine, in
            backups/before-restore-TIME.
          </Fine>
          <h4>What the helper did last</h4>
          <Rows label="What the helper did last">
            {jobs.length === 0 && <Empty>Nothing asked of the helper yet.</Empty>}
            {jobs.slice(0, 5).map((j) => (
              <Row key={j.id} title={`${j.action}: ${j.state}`} about={`${when(j.time)}. ${j.message}`} />
            ))}
          </Rows>
        </>
      )}
    </Panel>
  );
}
