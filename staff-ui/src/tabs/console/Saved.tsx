// Saved commands: the ones the staff use often, shared by every admin login (tools/staff_desk.py). Run sends one to
// the server as if typed, so it shows in the log with the answer.
import { useCallback, useState } from "react";
import { get, listOf, post } from "../../lib/api";
import { useMessages, useOnShow } from "../../lib/hooks";
import { useSession } from "../../lib/session";
import { Button, Empty, Fine, FormRow, Input, Messages, Panel, Row, Rows, useConfirm } from "../../ui/kit";

interface SavedCommand {
  id: string;
  label: string;
  command: string;
}

export default function Saved({ active, onRun }: { active: boolean; onRun: (command: string) => void }) {
  const { can } = useSession();
  const m = useMessages();
  const [confirm, ask] = useConfirm();
  const [rows, setRows] = useState<SavedCommand[] | null>(null);
  const [label, setLabel] = useState("");
  const [command, setCommand] = useState("");
  const { fail, setError } = m;

  const load = useCallback(async () => {
    try {
      const data = await get("/api/saved-commands");
      setRows(listOf<SavedCommand>(data, "commands"));
      setError("");
    } catch (e) {
      fail(e);
    }
  }, [fail, setError]);
  useOnShow(load, active && can("admin"));

  if (!can("admin")) return null;

  const call = async (url: string, body: object, words: string) => {
    m.clear();
    try {
      await post(url, body);
      m.say(words);
      return true;
    } catch (e) {
      fail(e);
      return false;
    } finally {
      load();
    }
  };

  const add = async () => {
    const l = label.trim();
    const c = command.trim();
    if (!l || !c) {
      m.clear();
      fail("Give the command a label, and the command itself.");
      return;
    }
    if (await call("/api/saved-commands", { label: l, command: c }, `Saved ${l}.`)) {
      setLabel("");
      setCommand("");
    }
  };

  return (
    <Panel title="Saved commands" meta={rows ? rows.length : undefined}>
      <Fine>
        Commands the staff use often, shared by everyone with an admin login. Run sends one to the server as if you had
        typed it.
      </Fine>
      <Messages of={m} />
      {confirm}
      <Rows label="Saved commands">
        {rows && rows.length === 0 && <Empty>No saved commands yet.</Empty>}
        {rows?.map((c) => (
          <Row
            key={c.id}
            title={c.label}
            about={<span className="font-mono wrap-anywhere">{c.command}</span>}
            actions={
              <>
                <Button
                  kind="primary"
                  small
                  onClick={() => {
                    onRun(c.command);
                    m.clear();
                    m.say(`Sent: ${c.command}`);
                  }}
                >
                  Run
                </Button>
                <Button
                  kind="danger"
                  small
                  onClick={() =>
                    ask({
                      message: `Delete the saved command ${c.label}?`,
                      yes: "Yes, delete",
                      danger: true,
                      onYes: () => void call("/api/saved-command-delete", { id: c.id }, "Deleted."),
                    })
                  }
                >
                  Delete
                </Button>
              </>
            }
          />
        ))}
      </Rows>
      <FormRow>
        <Input
          maxLength={40}
          value={label}
          onChange={(e) => setLabel(e.target.value)}
          placeholder="Label, e.g. Vote reminder"
          aria-label="Label for the saved command"
        />
        <Input
          className="font-mono"
          maxLength={1000}
          value={command}
          onChange={(e) => setCommand(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && add()}
          placeholder="Command, e.g. say Vote for the server!"
          aria-label="Command to save"
        />
        <Button kind="primary" onClick={add}>
          Save command
        </Button>
      </FormRow>
    </Panel>
  );
}
