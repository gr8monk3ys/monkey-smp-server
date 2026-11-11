// Strength SMP: in-game settings read and set over RCON (GET and PUT /api/strength), no config file.
import { useState } from "react";
import { get, post, api } from "../../lib/api";
import { useMessages, useOnShow } from "../../lib/hooks";
import { useSession } from "../../lib/session";
import { Button, Fine, Messages, useConfirm } from "../../ui/kit";
import { Fields, SaveBar, useForm } from "./form";

const GROUPS: [string, string][] = [["cooldown", "Ultimate cooldowns"], ["lifetime", "Ultimate lifetimes"], ["other", "Other"]];

function StrengthForm({ settings, m, reload }: { settings: any[]; m: ReturnType<typeof useMessages>; reload: () => Promise<void> }) {
  const { can } = useSession();
  const editable = can("admin");
  const [confirm, ask] = useConfirm();
  const [saving, setSaving] = useState(false);
  const fields = settings.map((s) => {
    const shownDefault = s.type === "bool" ? (s.default ? "on" : "off") : String(s.default);
    // A score the world doesn't hold yet: the mod uses its default, so the form starts there.
    return { ...s, value: s.missing ? s.default : s.value, about: `${s.about} Default ${shownDefault}.${s.missing ? " Not set yet: the mod uses the default." : ""}` };
  });
  const form = useForm(fields);

  const save = async () => {
    if (!form.changes.length) return;
    m.setError("");
    setSaving(true);
    try {
      const done = await api("PUT", "/api/strength", { values: form.values() });
      const labels = new Map(fields.map((f) => [f.key, f.label]));
      await reload();
      m.say(`Set: ${done.changed.map((k: string) => labels.get(k) || k).join(", ")}. It counts from the next ultimate used.`);
    } catch (e) {
      m.fail(e);
    } finally {
      setSaving(false);
    }
  };

  const reset = async () => {
    m.setError("");
    try {
      await post("/api/strength-reset", { confirm: "RESET" });
      await reload();
      m.say("Every Strength SMP setting is back to its default.");
    } catch (e) {
      m.fail(e);
    }
  };

  return (
    <div className="flex flex-col gap-5">
      {GROUPS.map(([group, title]) => {
        const states = form.states.filter((s) => s.field.group === group);
        if (!states.length) return null;
        return (
          <div key={group} className="flex flex-col gap-3">
            <h4>{title}</h4>
            <Fields form={{ ...form, states }} editable={editable} />
          </div>
        );
      })}
      <SaveBar form={form} editable={editable} onSave={save} saving={saving}>
        <Button onClick={() => reload()}>Reload</Button>
      </SaveBar>
      {editable ? (
        <div className="flex flex-wrap items-center gap-3">
          <span className="fine">Every setting back to the mod's default:</span>
          <Button
            kind="danger"
            onClick={() =>
              ask({
                message: "Put every Strength SMP setting back to its default?",
                yes: "Reset to defaults",
                danger: true,
                word: "RESET",
                onYes: reset,
              })
            }
          >
            Reset to defaults
          </Button>
        </div>
      ) : (
        <Fine>Changing these needs an admin login.</Fine>
      )}
      {confirm}
    </div>
  );
}

/** Read the first time its card is opened (the card is made new when Reload at the top is pressed). */
export default function Strength() {
  const m = useMessages();
  const [settings, setSettings] = useState<any[] | null>(null);
  const [failed, setFailed] = useState(false);
  const [n, setN] = useState(0);

  const load = async () => {
    m.setError("");
    try {
      const data = await get("/api/strength");
      setSettings(data.settings || []);
      setFailed(false);
      setN((k) => k + 1);
    } catch (e) {
      setFailed(true);
      m.fail(e);
    }
  };
  useOnShow(load, true);

  return (
    <div className="flex flex-col gap-3">
      <Fine>
        No config file: these live in the world. A change needs no restart and stays after one. A new cooldown or lifetime counts from the next ultimate: one
        already running keeps its old time. Times are in seconds (about). The start level, the level range and the mace and lunge cooldowns are fixed in the mod
        and can't be changed here.
      </Fine>
      <Messages of={m} />
      {settings === null && !failed && <Fine>Asking the server...</Fine>}
      {failed && settings === null && <Button onClick={load}>Try again</Button>}
      {settings && <StrengthForm key={n} settings={settings} m={m} reload={load} />}
    </div>
  );
}
