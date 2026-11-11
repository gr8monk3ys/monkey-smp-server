// One config form: a field per setting, what changed marked, and the bar with the save button. Used by every file
// card and by Strength SMP.
import { useState, type ReactNode } from "react";
import { Actions, Button, Field, Input, Select, Textarea, cx } from "../../ui/kit";

export type Raw = string | boolean;

const ITEM_TYPES: Record<string, string> = { int: "whole numbers", float: "numbers", bool: "true or false", text: "text" };

export function initialRaw(field: any): Raw {
  if (field.type === "bool") return field.value === true;
  if (field.type === "list") return (field.value as unknown[]).map(String).join("\n");
  return String(field.value);
}

/** The value a field's control holds, or undefined when it is not a valid value yet. */
export function readRaw(field: any, raw: Raw): unknown {
  if (field.type === "bool") return raw;
  if (field.type === "int" || field.type === "float") {
    const text = String(raw).trim();
    if (text === "") return undefined;
    const n = Number(text);
    if (!Number.isFinite(n) || (field.type === "int" && !Number.isInteger(n))) return undefined;
    return n;
  }
  if (field.type === "list") {
    const items = String(raw).split("\n").map((s) => s.trim()).filter((s) => s !== "");
    if (field.item === "text") return items;
    if (field.item === "bool") return items.every((s) => s === "true" || s === "false") ? items.map((s) => s === "true") : undefined;
    const numbers = items.map(Number);
    return numbers.every((n) => Number.isFinite(n) && (field.item !== "int" || Number.isInteger(n))) ? numbers : undefined;
  }
  if (field.type === "text") return raw;
  return field.value; // fixed
}

const same = (a: unknown, b: unknown) => JSON.stringify(a) === JSON.stringify(b);

export interface FieldState {
  field: any;
  raw: Raw;
  bad: boolean;
  changed: boolean;
  value: unknown;
}

/** The drafts of a form's fields. A form is made new (by `key`) when its file is read again. */
export function useForm(fields: any[]) {
  const [raws, setRaws] = useState<Record<string, Raw>>({});
  const states: FieldState[] = fields.map((field) => {
    const raw = field.key in raws ? raws[field.key] : initialRaw(field);
    const value = readRaw(field, raw);
    const bad = value === undefined;
    return { field, raw, value, bad, changed: !bad && !same(value, field.value) };
  });
  const set = (key: string, raw: Raw) => setRaws((r) => ({ ...r, [key]: raw }));
  const changes = states.filter((s) => s.changed);
  const bad = states.filter((s) => s.bad).length;
  const values = () => Object.fromEntries(changes.map((s) => [s.field.key, s.value]));
  return { states, set, changes, bad, values };
}
export type Form = ReturnType<typeof useForm>;

function Control({ state, id, editable, set }: { state: FieldState; id: string; editable: boolean; set: (raw: Raw) => void }) {
  const { field, raw } = state;
  const off = !editable;
  if (field.type === "bool") {
    return <Input id={id} type="checkbox" className="size-5 accent-gold" checked={raw === true} disabled={off} aria-label={field.key} onChange={(e) => set(e.target.checked)} />;
  }
  if (field.type === "int" || field.type === "float") {
    return (
      <Input
        id={id}
        type="number"
        step={field.type === "int" ? "1" : "any"}
        min={field.min}
        max={field.max}
        value={String(raw)}
        disabled={off}
        aria-label={field.key}
        onChange={(e) => set(e.target.value)}
      />
    );
  }
  if (field.type === "text" && field.choices) {
    // The value on disk is always an option, even when the mod's comment doesn't list it.
    const choices: string[] = field.choices.includes(field.value) ? field.choices : [field.value, ...field.choices];
    return <Select id={id} value={String(raw)} disabled={off} aria-label={field.key} options={choices.map((c) => ({ value: c, label: c }))} onChange={(e) => set(e.target.value)} />;
  }
  if (field.type === "list") {
    return (
      <Textarea
        id={id}
        className="font-mono"
        rows={Math.min(8, Math.max(2, (field.value as unknown[]).length + 1))}
        value={String(raw)}
        disabled={off}
        aria-label={field.key}
        onChange={(e) => set(e.target.value)}
      />
    );
  }
  if (field.type === "text") {
    return <Input id={id} className="font-mono" maxLength={2000} value={String(raw)} disabled={off} aria-label={field.key} onChange={(e) => set(e.target.value)} />;
  }
  return <code className="block font-mono wrap-anywhere text-bone">{String(field.value)}</code>;
}

export function Fields({ form, editable }: { form: Form; editable: boolean }) {
  return (
    <div className="grid grid-cols-1 gap-x-6 gap-y-4 md:grid-cols-2">
      {form.states.map((s) => {
        const { field } = s;
        let about: string = field.about || "";
        if (field.type === "list") about = `${about} One item per line (${ITEM_TYPES[field.item]}).`.trim();
        if (field.min !== undefined) about = `${about} From ${field.min} to ${field.max}.`.trim();
        if (field.type === "fixed") about = `${about} ${field.locked || "Shown only: change it in Files."}`.trim();
        const wide = field.type === "list" || field.type === "fixed" || (field.type === "text" && !field.choices);
        return (
          <Field
            key={field.key}
            label={field.label || field.key}
            help={about}
            className={cx("border-l-4 py-1 pl-3", s.bad ? "border-bad" : s.changed ? "border-gold" : "border-transparent", wide && "md:col-span-2")}
          >
            {(id) => <Control state={s} id={id} editable={editable && field.type !== "fixed"} set={(raw) => form.set(field.key, raw)} />}
          </Field>
        );
      })}
    </div>
  );
}

/** How many changes, and the buttons. */
export function SaveBar({ form, editable, onSave, saving, children }: { form: Form; editable: boolean; onSave: () => void; saving?: boolean; children?: ReactNode }) {
  const n = form.changes.length;
  const text = form.bad
    ? `${form.bad} value${form.bad === 1 ? " isn't" : "s aren't"} valid.`
    : n
      ? `${n} unsaved change${n === 1 ? "" : "s"}.`
      : "No unsaved changes.";
  return (
    <div className={cx("flex flex-wrap items-center justify-between gap-3 border-t-2 pt-3", n || form.bad ? "border-gold" : "border-leaf-2")}>
      <p className="fine" role="status">
        {text}
      </p>
      <Actions>
        {children}
        <Button kind="primary" onClick={onSave} disabled={!editable || form.bad > 0 || n === 0 || saving}>
          Save changes
        </Button>
      </Actions>
    </div>
  );
}
