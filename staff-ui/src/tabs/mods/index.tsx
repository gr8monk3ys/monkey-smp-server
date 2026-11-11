import { useCallback, useMemo, useRef, useState } from "react";
import type { TabProps } from "../../shell/tabs";
import { get, post } from "../../lib/api";
import { when } from "../../lib/format";
import { useMessages, useOnShow } from "../../lib/hooks";
import { useSession } from "../../lib/session";
import { Actions, Button, Empty, Fine, Message, Messages, PageHead, Panel, Panels, Row, Rows } from "../../ui/kit";
import { HELD_NOTE, ModsContext, PINNED_NOTE, playersNeed, type ModCtl } from "./ctl";
import DataPacks, { type PacksHandle } from "./DataPacks";
import InstalledMods, { type ModsData } from "./InstalledMods";
import { FindOnModrinth, InstallPack, UploadJar } from "./Installers";
import { useStep } from "./step";
import Updates from "./Updates";

// The owner's mod changes players need in their pack too, until a release has them (tools/staff_host.py, pack_waiting).
const PACK_HOW: Record<string, string> = { off: "turned off here", removed: "removed here", held: "kept off here" };

export default function ModsTab({ active }: TabProps) {
  const { can, me } = useSession();
  const m = useMessages();
  const [players, setPlayers] = useState("");
  const [data, setData] = useState<ModsData | null>(null);
  const [waiting, setWaiting] = useState<any[]>([]);
  const [stepNode, openStep] = useStep();
  const [asking, setAsking] = useState<{ file: string; failed: boolean } | null>(null);
  const packs = useRef<PacksHandle>(null);

  const reload = useCallback(async () => {
    try {
      const got = await get("/api/mods");
      setData({
        mods: got.mods || [],
        held_gone: got.held_gone || [],
        holds_supported: got.holds_supported !== false,
        players_missing: got.players_missing || [],
        players_pack: Boolean(got.players_pack),
      });
      setWaiting(got.pack_waiting || []);
    } catch (e) {
      m.fail(e);
    }
  }, [m.fail]); // eslint-disable-line react-hooks/exhaustive-deps

  const ctl = useMemo<ModCtl>(() => {
    const askPlayers = (file: string, failed: boolean) => setAsking({ file, failed });
    const done = (text: string, got: any) => {
      const pinned = got.held ? HELD_NOTE : got.pinned ? PINNED_NOTE : "";
      m.say(`${text}${got.kept_in ? ` The old file is kept in ${got.kept_in}.` : ""}${pinned} Restart the server (Server tab) for it to take effect.`);
      // The change is made; a note that could not be saved after it (keep it off, players need it) is said apart.
      m.setError([got.note_error, got.pack_error].filter(Boolean).join(" "));
      setPlayers(playersNeed(got));
      if (got.client_side === "unknown" && got.file) askPlayers(got.file, got.side_checked === false);
      reload();
    };
    return {
      m,
      openStep,
      step: (message, yes, file, onYes, check, danger) =>
        openStep({ message: `${message} Type ${file} to confirm.`, yes, danger, expect: file, label: "Jar file name", check, onYes }),
      call: async (url, body, words) => {
        m.clear();
        try {
          done(words, await post(url, body));
        } catch (e) {
          m.fail(e);
        }
      },
      done,
      askPlayers,
      reload,
    };
  }, [m, openStep, reload]);

  useOnShow(() => {
    reload();
    if (can("admin")) packs.current?.load();
  }, active && me !== null);

  const answer = async (file: string, who: string) => {
    setAsking(null);
    try {
      const got = await post("/api/mod-side", { file, players: who });
      setPlayers(playersNeed(got));
      reload();
    } catch (e) {
      m.fail(e);
    }
  };

  return (
    <ModsContext.Provider value={ctl}>
      <PageHead title="Mods">
        <p>
          The mods in the server's mods folder, read from each jar. Only the owner can add, turn off and remove them here, because a jar runs as the server;
          admins can look and say whether players need a mod. Each change asks you to type the jar's name, and every old jar is kept in mods-removed/ on the
          machine.
        </p>
      </PageHead>
      <div className="mb-4 flex flex-col gap-3">
        <Message kind="warn">
          Before you change a mod: a mod that players need too must match in their mod pack, or they can't join. The release's own (pinned) mods come back each
          time the server starts, and the next release deploy puts the mods folder back to that release's list. A change takes effect when the server
          restarts.
        </Message>
        <Messages of={m} />
        <Message kind="error">{players}</Message>
        {stepNode}
        {asking && (
          <div className="frame-stone step-in flex max-w-[52em] flex-col gap-3 px-3 py-3 text-ink" role="group" aria-label="Do players need it?">
            <p className="font-semibold wrap-anywhere">
              Do players need {asking.file} too? {asking.failed ? "Modrinth couldn't be asked about it." : "Modrinth doesn't say."} A mod that adds blocks,
              items or creatures usually must be in the players' pack.
            </p>
            <Actions>
              <Button className="btn-on-stone" need="admin" onClick={() => answer(asking.file, "required")}>
                Yes, players need it
              </Button>
              <Button className="btn-on-stone" need="admin" onClick={() => answer(asking.file, "no")}>
                No
              </Button>
              <Button className="btn-on-stone" need="admin" onClick={() => answer(asking.file, "unknown")}>
                Don't know
              </Button>
            </Actions>
          </div>
        )}
      </div>
      <Panels>
        <InstalledMods data={data} />
        <UploadJar />
        <FindOnModrinth />
        <InstallPack />
        <Updates active={active} onInstalled={reload} />
        {waiting.length > 0 && (
          <Panel wide title="Players' pack: waiting for a release" meta={`(${waiting.length})`}>
            <Fine>
              Mod changes on this server that players need in their pack too. Players get them only with the next release: the owner runs{" "}
              <code className="font-mono">python tools/pack_sync.py</code> on their PC, merges its pull request and tags a release. A line goes by itself once
              the pack has the change.
            </Fine>
            <Rows label="Waiting for a release">
              {waiting.map((w) => (
                <Row
                  key={w.file}
                  title={
                    <>
                      {w.file}{" "}
                      <span className="meta">
                        (
                        {[
                          w.action === "add" ? "add to the pack" : `take out of the pack, ${PACK_HOW[w.how] || "gone here"}`,
                          w.by ? `by ${w.by}` : "",
                          w.at ? when(w.at) : "",
                        ]
                          .filter(Boolean)
                          .join(", ")}
                        )
                      </span>
                    </>
                  }
                  about={w.action === "remove" && w.how === "off" ? "Still only turned off: pack_sync.py asks before it takes it out of the pack." : ""}
                />
              ))}
              {!waiting.length && <Empty>Nothing waiting.</Empty>}
            </Rows>
          </Panel>
        )}
        <DataPacks handle={packs} />
      </Panels>
    </ModsContext.Provider>
  );
}
