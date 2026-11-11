// Which mods have a newer file on Modrinth (tools/staff_lookup.py answers; the panel asks Modrinth by each jar's hash).
import { useRef, useState } from "react";
import { changed } from "../../lib/bus";
import { get, post } from "../../lib/api";
import { plural, when } from "../../lib/format";
import { useMessages, useOnShow } from "../../lib/hooks";
import { useSession } from "../../lib/session";
import { Button, Empty, Fine, Messages, Panel, Row, Rows } from "../../ui/kit";
import { useStep } from "./step";

export default function Updates({ active, onInstalled }: { active: boolean; onInstalled: () => void }) {
  const { can, me } = useSession();
  const m = useMessages();
  const [step, openStep] = useStep();
  const [count, setCount] = useState("");
  const [rows, setRows] = useState<any[] | null>(null);
  const [checking, setChecking] = useState(false);
  const asked = useRef(false);

  const load = async (fresh: boolean) => {
    if (!can("admin")) return;
    m.setError("");
    setChecking(true);
    setCount("checking...");
    try {
      const data = await get("/api/mod-updates" + (fresh ? "?fresh=1" : ""));
      const list: any[] = data.updates || [];
      const unknown = data.unknown ? ` ${plural(data.unknown, "jar")} Modrinth doesn't know (added by hand or from elsewhere).` : "";
      setCount(`${list.length} of ${data.checked}`);
      m.say(
        `Checked ${plural(data.checked, "mod")} for ${data.game}, ${when(data.at)}${data.cached ? " (from the last check: press the button to ask again)" : ""}.${unknown}`,
      );
      setRows(list);
    } catch (e) {
      setCount("");
      m.fail(e);
    } finally {
      setChecking(false);
    }
  };

  // Modrinth is asked only once per page load unless someone presses the button; the panel keeps answers 30 minutes.
  useOnShow(() => {
    if (asked.current) return;
    asked.current = true;
    load(false);
  }, active && me !== null);

  const update = async (row: any) => {
    m.setError("");
    m.say(`Downloading ${row.slug} from Modrinth...`);
    try {
      const done = await post("/api/modrinth-install", { project: row.slug, confirm: row.slug });
      m.say(
        `Installed ${done.name || row.slug} ${done.version || ""}.${done.kept_in ? ` The old file is kept in ${done.kept_in}.` : ""} Restart the server (Server tab) for it to take effect.`,
      );
      changed();
      onInstalled();
      load(true).then(() => undefined);
    } catch (e) {
      m.say("");
      m.fail(e);
    }
  };

  if (!can("admin")) return null;

  return (
    <Panel
      wide
      title="Updates on Modrinth"
      meta={count}
      aside={
        <Button need="admin" onClick={() => load(true)} disabled={checking}>
          Check for updates
        </Button>
      }
    >
      <Fine>
        Asks Modrinth, by each jar's hash, whether it has a newer Fabric file for this game version. Only the hashes, the loader and the game version are sent.
        Read the changelog first. Only the owner updates a mod: type its short name to install the new file, and the old jar moves to mods-removed/. A
        release's own (pinned) mods are updated with a release, since the server puts their files back when it starts.
      </Fine>
      <Messages of={m} />
      {step}
      <Rows label="Updates on Modrinth">
        {rows && !rows.length && <Empty>Every mod Modrinth knows is up to date.</Empty>}
        {rows?.map((r) => {
          const type = r.type && r.type !== "release" ? ` (${r.type})` : "";
          const about = `${r.jar} now. Newer: ${r.version}${type}, ${when(r.published)}.${
            r.pinned ? " Comes with the release: update it in a release, since the server puts the pinned jar back when it starts." : ""
          }`;
          // The install takes Modrinth's newest release, so a beta or alpha is shown but not offered: the button would
          // install a different file from the one listed.
          const offer = can("owner") && r.slug && !r.pinned && (r.type || "release") === "release";
          return (
            <Row
              key={r.jar}
              title={r.name || r.slug}
              about={`${about}${!r.pinned && r.type && r.type !== "release" ? " Not a release, so it isn't offered here." : ""}`}
              actions={
                <>
                  {r.url && (
                    <a className="btn btn-small" href={r.url} target="_blank" rel="noopener noreferrer">
                      Changelog
                    </a>
                  )}
                  {offer && (
                    <Button
                      small
                      onClick={() =>
                        openStep({
                          message: `Update ${r.jar} to ${r.version}? The new file is downloaded from Modrinth and checked, and the old jar moves to mods-removed/. Type ${r.slug} to confirm.`,
                          yes: "Update it",
                          expect: r.slug,
                          label: "The mod's short name",
                          onYes: () => update(r),
                        })
                      }
                    >
                      Update
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
