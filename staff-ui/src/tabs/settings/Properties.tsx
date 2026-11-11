// server.properties as a form (GET and PUT /api/settings).
import { useState } from "react";
import { api } from "../../lib/api";
import type { Messages } from "../../lib/hooks";
import { useSession } from "../../lib/session";
import { Button, Check, Field, Input, Panel, Select, cx } from "../../ui/kit";

// The value as the form holds it: a tick box is "true" or "false", a number is its text.
function current(field: any, draft: Record<string, string>): string {
  const raw = draft[field.key] ?? field.value;
  return field.type === "int" ? raw.trim() : raw;
}

function Setting({ field, draft, set }: { field: any; draft: Record<string, string>; set: (key: string, value: string) => void }) {
  const { can } = useSession();
  const editable = field.editable && can("admin");
  const value: string = draft[field.key] ?? field.value;
  const changed = current(field, draft) !== field.value;
  const about = field.locked ? `${field.about} Locked: ${field.locked}` : field.about;
  const wide = field.type === "text";
  return (
    <Field
      label={<span className="font-mono">{field.key}</span>}
      help={about}
      className={cx("border-l-4 py-1 pl-3", changed ? "border-gold" : "border-transparent", wide && "md:col-span-2")}
    >
      {(id) => {
        if (field.type === "bool") {
          return (
            <Check id={id} checked={value === "true"} disabled={!editable} label={value === "true" ? "on" : "off"} onChange={(e) => set(field.key, e.target.checked ? "true" : "false")} />
          );
        }
        if (field.type === "int") {
          return <Input id={id} type="number" min={field.min} max={field.max} step={1} value={value} disabled={!editable} onChange={(e) => set(field.key, e.target.value)} />;
        }
        if (field.type === "enum") {
          const choices: string[] = field.choices.includes(field.value) ? field.choices : [field.value, ...field.choices];
          return <Select id={id} value={value} disabled={!editable} options={choices.map((c) => ({ value: c, label: c }))} onChange={(e) => set(field.key, e.target.value)} />;
        }
        return <Input id={id} className="font-mono" maxLength={field.max || 500} value={value} disabled={!editable} onChange={(e) => set(field.key, e.target.value)} />;
      }}
    </Field>
  );
}

export interface SettingsData {
  fields: any[];
  groups: string[];
  other: any[];
  mtime: unknown;
}

export default function Properties({ data, m, reload }: { data: SettingsData | null; m: Messages; reload: () => Promise<void> }) {
  const { can } = useSession();
  const [draft, setDraft] = useState<Record<string, string>>({});
  const [rev, setRev] = useState(0);

  if (!data) return null;
  const count = data.fields.filter((f) => current(f, draft) !== f.value).length;

  const save = async () => {
    const values: Record<string, string | number> = {};
    for (const field of data.fields) {
      if (!field.editable) continue;
      const value = current(field, draft);
      if (value === field.value) continue;
      if (field.type === "int") {
        if (value === "") continue; // a cleared box is not a 0
        const n = Number(value);
        if (Number.isNaN(n)) {
          m.clear();
          m.setError(`${field.key}: type a number.`);
          return;
        }
        values[field.key] = n;
      } else {
        values[field.key] = value;
      }
    }
    m.clear();
    if (!Object.keys(values).length) {
      m.say("Nothing changed.");
      return;
    }
    try {
      const done = await api("PUT", "/api/settings", { values, mtime: data.mtime });
      m.say(
        done.changed.length
          ? `Saved: ${done.changed.join(", ")}. Most settings take effect when the server restarts (Server tab). The old file is in Files, history.`
          : "Nothing changed.",
      );
      setDraft({});
      setRev((n) => n + 1);
      await reload();
    } catch (e) {
      m.fail(e);
    }
  };

  const set = (key: string, value: string) => setDraft((d) => ({ ...d, [key]: value }));

  return (
    <>
      {data.groups.map((group) => {
        const fields = data.fields.filter((f) => f.group === group);
        if (!fields.length) return null;
        return (
          <Panel key={`${group}-${rev}`} title={group}>
            <div className="grid grid-cols-1 gap-x-6 gap-y-4 md:grid-cols-2">
              {fields.map((f) => (
                <Setting key={f.key} field={f} draft={draft} set={set} />
              ))}
            </div>
          </Panel>
        );
      })}
      {(data.other || []).length > 0 && (
        <Panel title="Locked here, and other keys">
          <ul className="flex flex-col gap-2">
            {data.other.map((row) => (
              <li key={row.key} className="min-w-0 wrap-anywhere">
                <code className="font-mono text-bone">
                  {row.key}={row.value}
                </code>{" "}
                <span className="fine">{row.locked}</span>
              </li>
            ))}
          </ul>
        </Panel>
      )}
      <div className={cx("sticky bottom-0 z-10 flex flex-wrap items-center justify-between gap-3 border-t-2 bg-ground py-3 lg:col-span-2", count ? "border-gold" : "border-leaf-2")}>
        <p className="fine" role="status">
          {count ? `${count} unsaved change${count === 1 ? "" : "s"}.` : "No unsaved changes."}
        </p>
        <div className="flex flex-wrap gap-2">
          <Button
            onClick={() => {
              setDraft({});
              m.clear();
              reload();
            }}
          >
            Reload
          </Button>
          <Button kind="primary" need="admin" disabled={!can("admin")} onClick={save}>
            Save changes
          </Button>
        </div>
      </div>
    </>
  );
}
