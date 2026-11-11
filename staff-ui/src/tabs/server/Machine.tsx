// The machine's side: the release in use, Java and memory, the SFTP login. All admin.
import { useState } from "react";
import { api, get } from "../../lib/api";
import { useMessages, useOnShow } from "../../lib/hooks";
import { useSession } from "../../lib/session";
import { Actions, Button, Facts, Field, Fine, FormRow, Input, Messages, Panel, Select, Textarea, useConfirm } from "../../ui/kit";
import { askHelper, useAlive } from "./ask";

export function Version({ active }: { active: boolean }) {
  const { can } = useSession();
  const m = useMessages();
  const alive = useAlive();
  const [confirm, ask] = useConfirm();
  const [data, setData] = useState<any>(null);
  const [tag, setTag] = useState("");

  const load = async () => {
    if (!can("admin")) return;
    try {
      const next = await get("/api/versions");
      setData(next);
      setTag((old) => ((next.tags || []).some((t: any) => t.tag === old) ? old : (next.tags || [])[0]?.tag || ""));
    } catch (error) {
      m.fail(error);
    }
  };
  useOnShow(load, active);
  if (!can("admin")) return null;

  const tags: { tag: string; live?: boolean }[] = data?.tags || [];
  const live = tags.find((t) => t.live);
  const state = data
    ? [
        live ? `Running ${live.tag}.` : data.deployed ? `Running commit ${data.deployed}.` : "Nothing deployed yet.",
        data.newest ? `Newest release: ${data.newest}.` : "",
        data.pinned ? `Pinned to ${data.pinned}: the nightly deploy stays on it until the newest release is picked.` : "",
      ]
        .filter(Boolean)
        .join(" ")
    : "";

  const switchTo = () => {
    if (!tag) return;
    ask({
      message: `Switch the server to ${tag}? Players are warned, the server restarts on that release's files, and its pinned mods come back. An older release stays until the newest one is picked again.`,
      yes: "Switch version",
      danger: true,
      word: tag,
      onYes: (typed) => askHelper("/api/version-switch", { tag, confirm: typed }, `Switch to ${tag} asked for.`, m, alive).then(load),
    });
  };

  return (
    <Panel title="Version">
      <Messages of={m} />
      <Fine>{state}</Fine>
      {data && !data.installed && <Fine>Switching needs the root helper (the owner's step: --install-helper).</Fine>}
      {tags.length > 0 && (
        <FormRow>
          <Select
            aria-label="Release"
            value={tag}
            onChange={(e) => setTag(e.target.value)}
            options={tags.map((t) => ({ value: t.tag, label: `${t.tag}${t.live ? " (running)" : ""}${t.tag === data.newest ? " (newest)" : ""}` }))}
          />
          <Button need="admin" disabled={!data.installed} onClick={switchTo}>Switch to this release</Button>
        </FormRow>
      )}
      {confirm}
    </Panel>
  );
}

export function Java({ active }: { active: boolean }) {
  const { can } = useSession();
  const m = useMessages();
  const [data, setData] = useState<any>(null);
  const [memory, setMemory] = useState("");
  const [flags, setFlags] = useState("");

  const load = async () => {
    if (!can("admin")) return;
    try {
      const next = await get("/api/java");
      setData(next);
      setMemory(next.memory_gb === null ? "" : String(next.memory_gb));
      setFlags((next.flags || []).join("\n"));
      m.setError("");
    } catch (error) {
      m.fail(error);
    }
  };
  useOnShow(load, active);
  if (!can("admin")) return null;

  const save = async () => {
    m.clear();
    const typed = memory.trim();
    if (typed && !/^\d+$/.test(typed)) {
      m.fail(new Error("Memory is a whole number of GB, or empty."));
      return;
    }
    const body = {
      memory_gb: typed ? Number(typed) : null,
      flags: flags.split("\n").map((f) => f.trim()).filter(Boolean),
    };
    try {
      const done = await api("PUT", "/api/java", body);
      m.say(`Saved.${done.running ? " Restart the server for it to take effect." : " It is used when the server starts."}`);
      load();
    } catch (error) {
      m.fail(error);
    }
  };

  return (
    <Panel title="Java and memory" wide>
      {data && <Fine>{`${data.java || "Java"}, pinned by the release.${data.total_gb ? ` The machine has ${data.total_gb} GB.` : ""}`}</Fine>}
      <Messages of={m} />
      <div className="grid grid-cols-1 gap-4 md:grid-cols-[minmax(0,16rem)_1fr]">
        <Field
          label="Memory, in GB"
          help={
            data &&
            (data.total_gb
              ? `Empty: picked from the machine (${data.default_gb} GB now). At most ${data.most_gb}: the machine keeps 2 GB for itself.`
              : `Empty: picked from the machine at each start. At most ${data.most_gb}.`)
          }
        >
          {(id) => (
            <Input
              id={id}
              type="number"
              min={1}
              step={1}
              inputMode="numeric"
              need="admin"
              max={data?.most_gb}
              placeholder={data ? String(data.default_gb) : ""}
              value={memory}
              onChange={(e) => setMemory(e.target.value)}
            />
          )}
        </Field>
        <Field
          label="Extra Java flags, one per line"
          help="Up to 20, like -XX:MaxGCPauseMillis=100 or -Dfile.encoding=UTF-8. The start script's own tuned flags stay; these come after them. Only garbage-collector and JIT tuning (G1..., MaxGCPauseMillis, ...) and a few plain properties: anything else goes in on the machine."
        >
          {(id) => <Textarea id={id} rows={4} need="admin" className="font-mono" value={flags} onChange={(e) => setFlags(e.target.value)} />}
        </Field>
      </div>
      <Actions>
        <Button kind="primary" need="admin" onClick={save}>Save</Button>
      </Actions>
      <Fine>
        Takes effect at the next restart. A bad flag can stop the server starting: clear it here and start again. The old settings are kept in
        staff-removed/ on the machine.
      </Fine>
    </Panel>
  );
}

export function Sftp({ active }: { active: boolean }) {
  const { can } = useSession();
  const m = useMessages();
  const [data, setData] = useState<any>(null);

  useOnShow(async () => {
    if (!can("admin")) return;
    try {
      setData(await get("/api/sftp"));
    } catch (error) {
      m.fail(error);
    }
  }, active);
  if (!can("admin")) return null;

  return (
    <Panel title="SFTP">
      <Messages of={m} />
      {data?.set_up ? (
        <Facts items={[["Host", data.host], ["Port", String(data.port)], ["Users", (data.users || []).join(", ")]]} />
      ) : (
        <Fine>No SFTP login is set up: ask the owner. Each login is key-only and sees only the server folder.</Fine>
      )}
    </Panel>
  );
}
