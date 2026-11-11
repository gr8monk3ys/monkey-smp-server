// One mod config file as a form (GET and PUT /api/mod-config).
import { useState } from "react";
import { api, get, query } from "../../lib/api";
import { emit } from "../../lib/bus";
import { useMessages, useOnShow } from "../../lib/hooks";
import { useSession } from "../../lib/session";
import { Actions, Button, Fine, Fold, Messages, Message } from "../../ui/kit";
import { Fields, SaveBar, useForm } from "./form";

export const openInFiles = (path: string, writable?: boolean) => emit("open-file", { path, writable });

function Form({ file, data, m, reload }: { file: any; data: any; m: ReturnType<typeof useMessages>; reload: () => Promise<void> }) {
  const { can } = useSession();
  const editable = Boolean(data.writable) && can("admin");
  const form = useForm(data.fields);
  const important = new Set<string>(data.important || []);
  const first = form.states.filter((s) => important.has(s.field.key));
  const rest = form.states.filter((s) => !important.has(s.field.key));
  const [saving, setSaving] = useState(false);

  const save = async () => {
    if (!form.changes.length) return;
    m.clear();
    setSaving(true);
    try {
      const done = await api("PUT", "/api/mod-config", { path: file.path, values: form.values(), mtime: data.mtime });
      const takes = data.applies === "reload" ? "It takes effect after /reload (Console tab) or a restart." : "It takes effect when the server restarts (Server tab).";
      await reload();
      m.say(done.changed.length ? `Saved: ${done.changed.join(", ")}. ${takes} The old file is in Files, history.` : "Nothing changed.");
    } catch (e) {
      m.fail(e);
    } finally {
      setSaving(false);
    }
  };

  const view = (states: typeof form.states) => <Fields form={{ ...form, states }} editable={editable} />;
  return (
    <div className="flex flex-col gap-4">
      {!data.fields.length && <Fine>This file has no settings this page can show.</Fine>}
      {first.length > 0 && view(first)}
      {rest.length > 0 &&
        (first.length ? <Fold title={`All settings (${rest.length} more)`}>{view(rest)}</Fold> : view(rest))}
      {data.skipped > 0 && (
        <Fine>
          {data.skipped} line{data.skipped === 1 ? "" : "s"} of this file can't be shown as fields: change {data.skipped === 1 ? "it" : "them"} in Files.
        </Fine>
      )}
      <SaveBar form={form} editable={editable} onSave={save} saving={saving}>
        <Button onClick={() => reload()}>Reload</Button>
        <Button onClick={() => openInFiles(file.path, data.writable)}>Open in Files</Button>
      </SaveBar>
      {!editable && <Fine>{can("admin") ? "This file is read-only here." : "Changing mod settings needs an admin login."}</Fine>}
    </div>
  );
}

export default function FileForm({ file }: { file: any }) {
  const m = useMessages();
  const [data, setData] = useState<any>(null);
  const [loadError, setLoadError] = useState("");
  const [rev, setRev] = useState(0);

  const load = async () => {
    try {
      const got = await get("/api/mod-config?" + query({ path: file.path }));
      setData(got);
      setLoadError("");
      setRev((n) => n + 1);
    } catch (e) {
      setLoadError(e instanceof Error ? e.message : String(e));
    }
  };
  useOnShow(load, true);

  if (loadError) return <Message kind="error">{loadError}</Message>;
  if (!data) return <Fine>Reading the file...</Fine>;
  if (data.error) {
    return (
      <div className="flex flex-col gap-3">
        <Message kind="error">{data.error}</Message>
        <Actions>
          <Button onClick={() => openInFiles(file.path, data.writable)}>Open in Files</Button>
        </Actions>
      </div>
    );
  }
  return (
    <div className="flex flex-col gap-3">
      <Messages of={m} />
      <Form key={rev} file={file} data={data} m={m} reload={load} />
    </div>
  );
}
