// The commands a moderator login may run in the console (tools/staff_lookup.py). Everyone sees the list; the owner
// edits it.
import { useCallback, useState } from "react";
import { api, get } from "../../lib/api";
import { when } from "../../lib/format";
import { useMessages, useOnShow } from "../../lib/hooks";
import { useSession } from "../../lib/session";
import { Button, Fine, FormRow, Input, Messages, Panel } from "../../ui/kit";

export default function ModCommands({ active }: { active: boolean }) {
  const { can } = useSession();
  const m = useMessages();
  const { fail, setError } = m;
  const [listed, setListed] = useState("");
  const [typed, setTyped] = useState("");
  const [allowed, setAllowed] = useState("");

  const load = useCallback(async () => {
    setError("");
    try {
      const data = await get("/api/mod-commands");
      const rows: string[] = data.commands || [];
      const who = data.default ? " (the standard list)" : data.broken ? "" : data.by ? ` (set by ${data.by}, ${when(data.at)})` : "";
      setListed(rows.length ? `${rows.join(", ")}${who}` : "None: a moderator login can't use the console.");
      if (data.broken) fail("mod-commands.json can't be read, so moderators can run nothing. Save the list again to fix it.");
      setTyped(rows.join(", "));
      setAllowed(`Commands that can be given: ${data.can_allow || ""}`);
    } catch (e) {
      fail(e);
    }
  }, [fail, setError]);
  useOnShow(load, active);

  const save = () =>
    m.run(async () => {
      const commands = typed.split(/[,\n]/).map((s) => s.trim()).filter(Boolean);
      const done = await api("PUT", "/api/mod-commands", { commands });
      m.say(done.commands.length ? `Saved. Moderators can run: ${done.commands.join(", ")}.` : "Saved. Moderators can't use the console now.");
      await load();
    });

  return (
    <Panel title="Commands moderators can run">
      <Fine>
        A moderator login can use this console for these commands only. An entry of two words allows only that pair:
        "whitelist add" allows <code>whitelist add NAME</code>, never <code>whitelist off</code>. Only known commands that
        can't run others, make operators, place a command block or send a click can be added (point at the box to see
        them).
      </Fine>
      <Messages of={m} />
      <p className="font-mono wrap-anywhere text-bone">{listed}</p>
      {can("owner") && (
        <FormRow>
          <Input
            className="font-mono"
            maxLength={1200}
            value={typed}
            onChange={(e) => setTyped(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && save()}
            title={allowed}
            placeholder="list, say, msg, kick, whitelist add"
            aria-label="Commands moderators can run, separated by commas"
          />
          <Button kind="primary" onClick={save} disabled={m.busy}>
            Save the list
          </Button>
        </FormRow>
      )}
    </Panel>
  );
}
