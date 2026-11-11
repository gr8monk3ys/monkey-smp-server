// Data packs of the world (the Mods tab): on and off, remove, upload, reload, and the troubleshooting set.
import { useCallback, useImperativeHandle, useRef, useState, type Ref } from "react";
import { api, get, messageOf, post, query } from "../../lib/api";
import { size, when } from "../../lib/format";
import { useMessages } from "../../lib/hooks";
import { useSession } from "../../lib/session";
import { Actions, Button, Empty, Fine, FormRow, Input, Message, Messages, Panel, Row, Rows } from "../../ui/kit";
import { DATAPACK_NAME } from "./ctl";
import { useStep } from "./step";

export interface PacksHandle {
  load: () => void;
}

const failedWords = (failed: any[] | undefined) => (failed || []).map((f) => `${f.name} (${f.why})`).join("; ");

export default function DataPacks({ handle }: { handle: Ref<PacksHandle> }) {
  const { can } = useSession();
  const m = useMessages();
  const [step, openStep] = useStep();
  const [data, setData] = useState<any>(null);
  const file = useRef<HTMLInputElement>(null);

  const load = useCallback(async () => {
    try {
      setData(await get("/api/datapacks"));
    } catch (e) {
      setData(null);
      // Its own line, so a reload after an action never wipes that action's error.
      m.setError((prev) => prev || messageOf(e));
    }
  }, [m.setError]); // eslint-disable-line react-hooks/exhaustive-deps
  useImperativeHandle(handle, () => ({ load }), [load]);

  const call = async (url: string, body: unknown, words: string) => {
    m.clear();
    try {
      const done = await post(url, body);
      m.say(`${words}${done.kept_in ? ` The old copy is kept in ${done.kept_in}.` : ""}`);
    } catch (e) {
      m.fail(e);
    }
    load();
  };

  const packStep = (message: string, yes: string, name: string, onYes: () => void) =>
    openStep({ message: `${message} Type ${name} to confirm.`, yes, danger: true, expect: name, label: "Data pack name", onYes });

  if (!can("admin")) return null;

  const packs: any[] = data?.packs ?? [];
  const running = Boolean(data?.running);
  const saved = data?.saved;
  const off = !running || !can("admin");
  const stillOff = typeof saved?.off === "number" ? `${saved.off} of ${saved.count} saved packs still off.` : `${saved?.count} packs saved.`;
  const savedText = saved ? saved.error || `Troubleshooting since ${when(saved.at)} by ${saved.by}: ${stillOff}` : "";

  const allOff = () =>
    openStep({
      message:
        "Save the list of data packs that are on, then turn every one of them off? Vanilla, Fabric's and the mods' built-in packs stay on. The game changes at once, without a restart. Type ALL OFF to confirm.",
      yes: "Turn all off",
      danger: true,
      expect: "ALL OFF",
      label: "Confirm word",
      onYes: async () => {
        m.clear();
        try {
          const done = await post("/api/datapacks-save-off", { confirm: "ALL OFF" });
          const failed = failedWords(done.failed);
          m.say(
            `Saved ${done.saved} packs and turned ${done.off.length} off.${failed ? ` These didn't turn off: ${failed}.` : ""} Turn them back on one at a time to find the trouble, or all at once with Turn saved set back on.`,
          );
        } catch (e) {
          m.fail(e);
        }
        load();
      },
    });

  const restore = () =>
    openStep({
      message: "Turn the saved set of data packs back on, in the order they had? The saved list stays until you clear it.",
      yes: "Turn them back on",
      onYes: async () => {
        m.clear();
        try {
          const done = await post("/api/datapacks-restore", {});
          const failed = failedWords(done.failed);
          m.say(`Turned ${done.on.length} of ${done.saved} back on.${failed ? ` These didn't: ${failed}.` : ""} Clear the saved set when you are done.`);
        } catch (e) {
          m.fail(e);
        }
        load();
      },
    });

  const clear = () =>
    openStep({
      message: "Forget the saved set? The packs stay as they are now; only the list of what was on is gone.",
      yes: "Clear it",
      onYes: () => call("/api/datapacks-saved-clear", {}, "The saved set is cleared."),
    });

  const upload = () => {
    const picked = file.current?.files?.[0];
    m.clear();
    if (!picked) return m.fail("Pick a data pack .zip first.");
    if (!DATAPACK_NAME.test(picked.name)) {
      return m.fail("A data pack's name has letters, digits, . _ + - only and ends in .zip: rename the file first.");
    }
    packStep(
      `Put ${picked.name} (${size(picked.size)}) in the world's datapacks folder? A pack with the same name is moved to staff-removed/ first.`,
      "Upload the pack",
      picked.name,
      async () => {
        try {
          const done = await api("POST", "/api/datapack-upload?" + query({ name: picked.name, confirm: picked.name }), undefined, { raw: picked });
          if (file.current) file.current.value = "";
          m.say(
            `Added ${done.name}.${done.kept_in ? ` The old copy is kept in ${done.kept_in}.` : ""} ${done.running ? "Press Reload data packs to turn it on." : "It is turned on when the server starts."}`,
          );
        } catch (e) {
          m.fail(e);
        }
        load();
      },
    );
  };

  return (
    <Panel
      wide
      title="Data packs"
      meta={`(${packs.length})`}
      aside={
        <Button
          need="admin"
          disabled={!running}
          title={running ? "" : "The server isn't running."}
          onClick={() => call("/api/datapack-reload", {}, "Reloaded.")}
        >
          Reload data packs
        </Button>
      }
    >
      <Fine>
        The world's datapacks folder. A new pack is turned on when you press Reload or the server restarts. The release's own packs come back at every start, so
        they can be turned off but not removed.
      </Fine>
      <Fine>
        To find a pack that causes trouble: Turn all off saves which packs are on, then turns them all off. Turn them back on one at a time, then Turn saved set
        back on puts the rest back in their old order.
      </Fine>
      <Actions>
        <Button need="admin" disabled={off || Boolean(saved)} onClick={allOff}>
          Turn all off
        </Button>
        <Button need="admin" disabled={off || !saved || Boolean(saved.error)} onClick={restore}>
          Turn saved set back on
        </Button>
        {saved && (
          <Button need="admin" onClick={clear}>
            Clear the saved set
          </Button>
        )}
      </Actions>
      <Message kind="warn">{savedText}</Message>
      <Messages of={m} />
      {data && !data.running && (
        <Fine>The server isn't running, so on and off can't be read or changed. Uploads and removals still work.</Fine>
      )}
      {step}
      <FormRow>
        <Input ref={file} type="file" accept=".zip" aria-label="Data pack zip file" need="owner" />
        <Button need="owner" onClick={upload}>
          Upload the pack
        </Button>
      </FormRow>
      <Rows label="Data packs">
        {data && !packs.length && <Empty>No data packs in this world.</Empty>}
        {packs.map((p) => {
          const state = p.enabled === null ? "" : p.enabled ? "on" : "off";
          const facts = [p.kind === "folder" ? "folder" : size(p.size), state, p.release ? "release" : ""].filter(Boolean);
          return (
            <Row
              key={p.name}
              title={
                <>
                  {p.name} <span className="meta">({facts.join(", ")})</span>
                </>
              }
              about={p.description}
              actions={
                <>
                  {running && p.enabled !== null && (
                    <Button
                      small
                      need="admin"
                      onClick={() => call("/api/datapack-toggle", { name: p.name, enabled: !p.enabled }, p.enabled ? "Turned off." : "Turned on.")}
                    >
                      {p.enabled ? "Turn off" : "Turn on"}
                    </Button>
                  )}
                  {!p.release && (
                    <Button
                      small
                      kind="danger"
                      need="admin"
                      onClick={() =>
                        packStep(
                          `Remove ${p.name}? It is moved to staff-removed/ on the machine, never deleted. Its changes to the world stay until the server reloads.`,
                          "Remove",
                          p.name,
                          () => call("/api/datapack-remove", { name: p.name, confirm: p.name }, "Removed. Press Reload to unload it."),
                        )
                      }
                    >
                      Remove
                    </Button>
                  )}
                </>
              }
            />
          );
        })}
      </Rows>
    </Panel>
  );
}
