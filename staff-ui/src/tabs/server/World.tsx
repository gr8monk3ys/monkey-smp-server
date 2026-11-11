// The world: download it (owner), reset it with a new seed, upload one and swap it in (admin).
import { useRef, useState } from "react";
import { api, get, post } from "../../lib/api";
import { size, when } from "../../lib/format";
import { useMessages, useOnShow } from "../../lib/hooks";
import { useSession } from "../../lib/session";
import { Actions, Button, FormRow, Fine, Input, Messages, Panel, useConfirm } from "../../ui/kit";
import { askHelper, useAlive } from "./ask";

const MAX_WORLD = 8_000_000_000;

export function Download() {
  const { can } = useSession();
  const m = useMessages();
  const [confirm, ask] = useConfirm();
  if (!can("owner")) return null;

  const download = async () => {
    m.clear();
    try {
      const done = await post("/api/world-download", {});
      const a = document.createElement("a");
      a.href = done.url;
      a.download = "";
      document.body.appendChild(a);
      a.click();
      a.remove();
      m.say("The download was asked for: check your browser's downloads bar. If it shows as failed there, the server refused it (it must be running, and no other job can be busy). Saving is off while it runs and comes back on when it ends.");
    } catch (error) {
      m.fail(error);
    }
  };

  return (
    <Panel title="Download the world">
      <Fine>A zip of the whole world folder, for keeping or testing at home. Owners only, one at a time.</Fine>
      <Messages of={m} />
      <Actions>
        <Button
          need="owner"
          onClick={() =>
            ask({
              message: "Download the whole world as a zip? It is a few GB. Saving stops while it streams (the game keeps running) and comes back on when it ends.",
              yes: "Yes, download",
              onYes: download,
            })
          }
        >
          Download the world
        </Button>
      </Actions>
      {confirm}
    </Panel>
  );
}

export function Reset() {
  const m = useMessages();
  const alive = useAlive();
  const [confirm, ask] = useConfirm();
  const [seed, setSeed] = useState("");

  const reset = () => {
    const given = seed.trim();
    ask({
      message: `Reset the world${given ? " with a new seed" : ""}? Players are warned, the server stops, the overworld, nether and end move aside (kept in backups/ on the machine), and a new world is made when it starts.`,
      yes: "Reset the world",
      danger: true,
      word: "RESET",
      onYes: (typed) => {
        setSeed("");
        askHelper("/api/world-reset", given ? { confirm: typed, seed: given } : { confirm: typed }, "Reset asked for.", m, alive);
      },
    });
  };

  return (
    <Panel title="Reset the world">
      <Fine>A new world, with a new seed if you give one. The old world is kept on the machine, never deleted. The seed is never shown or logged.</Fine>
      <Messages of={m} />
      <FormRow>
        <Input need="admin" maxLength={64} placeholder="New seed (empty: keep it)" aria-label="New seed" value={seed} onChange={(e) => setSeed(e.target.value)} />
        <Button kind="danger" need="admin" onClick={reset}>Reset the world</Button>
      </FormRow>
      {confirm}
    </Panel>
  );
}

export function Upload({ active }: { active: boolean }) {
  const { can } = useSession();
  const m = useMessages();
  const alive = useAlive();
  const [confirm, ask] = useConfirm();
  const file = useRef<HTMLInputElement>(null);
  const [sending, setSending] = useState(false);
  const [waiting, setWaiting] = useState<{ upload: string; time: unknown; size: number; files?: number } | null>(null);

  const load = async () => {
    if (!can("admin")) return;
    try {
      const data = await get("/api/world-upload");
      setWaiting(data.upload ? data : null);
    } catch (error) {
      m.fail(error);
    }
  };
  useOnShow(load, active);

  const send = async () => {
    const picked = file.current?.files?.[0];
    m.clear();
    if (!picked) {
      m.fail(new Error("Pick a .zip of a world folder first."));
      return;
    }
    if (picked.size > MAX_WORLD) {
      m.fail(new Error("A world upload is at most 8 GB."));
      return;
    }
    setSending(true);
    m.say(`Uploading ${size(picked.size)}... keep this page open.`);
    try {
      const done = await api("POST", "/api/world-upload", undefined, { raw: picked });
      if (file.current) file.current.value = "";
      m.say(`Uploaded and checked: ${done.files} files${done.folder ? ` in ${done.folder}/` : ""}. Nothing has changed yet: press Swap it in.`);
    } catch (error) {
      m.clear();
      m.fail(error);
    }
    setSending(false);
    load();
  };

  const apply = () => {
    const id = waiting?.upload;
    if (!id) return;
    ask({
      message: "Replace the live world with the uploaded one? Players are warned, the server stops, the current world is kept in backups/ on the machine, and the server starts on the uploaded world.",
      yes: "Swap it in",
      danger: true,
      word: "REPLACE",
      onYes: (typed) => askHelper("/api/world-upload-apply", { upload: id, confirm: typed }, "Swap asked for.", m, alive).then(load),
    });
  };

  return (
    <Panel title="Upload a world">
      <Fine>
        A .zip of a world folder (level.dat at the top or one folder in), up to 8 GB. It is checked when it arrives and changes nothing until you swap it in;
        the live world is kept on the machine first.
      </Fine>
      <Messages of={m} />
      <FormRow>
        <Input ref={file} type="file" accept=".zip" aria-label="World zip file" need="admin" />
        <Button need="admin" disabled={sending} onClick={send}>Upload</Button>
      </FormRow>
      {waiting && (
        <Fine>{`Waiting to be swapped in: an upload from ${when(waiting.time)}, ${size(waiting.size)}${waiting.files ? `, ${waiting.files} files` : ""}.`}</Fine>
      )}
      <Actions>
        <Button need="admin" disabled={!waiting} onClick={apply}>Swap it in</Button>
      </Actions>
      {confirm}
    </Panel>
  );
}
