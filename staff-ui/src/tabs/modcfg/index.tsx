// Mod settings: one card per mod, each config file a form (tools/staff_modcfg.py answers). The mod list comes from
// GET /api/mod-configs, which reads deploy/staff/mod-settings.json on the server side for titles and first keys.
import { useState } from "react";
import type { TabProps } from "../../shell/tabs";
import { get } from "../../lib/api";
import { useMessages, useOnShow } from "../../lib/hooks";
import { useSession } from "../../lib/session";
import { Button, Fine, FormRow, Fold, Input, Messages, PageHead } from "../../ui/kit";
import FileForm, { openInFiles } from "./FileForm";
import Strength from "./Strength";

const STRENGTH_FIND = "strength smp ultimate cooldown lifetime armor powers tag";

/** A card that opens on a click and reads its files only the first time it is opened. */
function Card({ title, where, children }: { title: string; where: string; children: () => React.ReactNode }) {
  const [open, setOpen] = useState(false);
  const [opened, setOpened] = useState(false);
  return (
    <section className="panel">
      <Fold
        open={open}
        onToggle={(v) => {
          setOpen(v);
          if (v) setOpened(true);
        }}
        title={
          <span className="flex min-w-0 flex-wrap items-baseline gap-x-3">
            <span className="font-display text-lg">{title}</span>
            <span className="fine wrap-anywhere">{where}</span>
          </span>
        }
      >
        {opened && children()}
      </Fold>
    </section>
  );
}

export default function ModcfgTab({ active }: TabProps) {
  const { can, me } = useSession();
  const m = useMessages();
  const [mods, setMods] = useState<any[] | null>(null);
  const [cut, setCut] = useState(false);
  const [search, setSearch] = useState("");
  const [rev, setRev] = useState(0);
  const [loaded, setLoaded] = useState(false);

  const load = async () => {
    m.clear();
    if (!can("admin")) {
      m.setError("Mod settings need an admin login.");
      return;
    }
    try {
      const data = await get("/api/mod-configs");
      setMods(data.mods || []);
      setCut(Boolean(data.cut));
      setLoaded(true);
    } catch (e) {
      m.fail(e);
    }
  };
  useOnShow(() => {
    if (!loaded) load();
  }, active && me !== null);

  const words = search.trim().toLowerCase().split(/\s+/).filter(Boolean);
  const matches = (find: string) => words.every((w) => find.includes(w));
  const shown = (mods ?? []).filter((mod) => matches(`${mod.title} ${mod.name} ${mod.files.map((f: any) => f.path).join(" ")}`.toLowerCase()));

  return (
    <>
      <PageHead title="Mod settings">
        <p>
          Each mod's config file as a form, with the file's own comments as help. A save changes only the values you changed: every comment and line order
          stays. Most changes take effect when the server restarts (Server tab). Every save keeps the old file in Files, history, and goes in the record of
          changes.
        </p>
      </PageHead>
      <div className="mb-4 flex flex-col gap-3">
        <Messages of={m} />
        <FormRow className="max-w-[40em]">
          <Input
            type="search"
            maxLength={80}
            placeholder="Find a mod or file"
            aria-label="Find a mod or file"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
          <Button
            onClick={() => {
              setLoaded(false);
              setRev((n) => n + 1);
              load();
            }}
          >
            Reload
          </Button>
        </FormRow>
      </div>
      <div className="flex flex-col gap-3">
        {can("admin") && matches(STRENGTH_FIND) && (
          <Card key={`strength-${rev}`} title="Strength SMP" where="in-game settings, over RCON">
            {() => <Strength />}
          </Card>
        )}
        {shown.map((mod) => (
          <Card key={`${mod.name}-${rev}`} title={mod.title} where={mod.files.length === 1 ? mod.files[0].path : `${mod.files.length} files`}>
            {() => (
              <div className="flex flex-col gap-4">
                {mod.about && <Fine>{mod.about}</Fine>}
                {mod.files.map((file: any) => (
                  <section key={file.path} className="flex flex-col gap-3">
                    {mod.files.length > 1 && <h4 className="font-mono wrap-anywhere">{file.path}</h4>}
                    {file.format === "raw" ? (
                      <div className="flex flex-col items-start gap-3">
                        <Fine>Not a format this page reads as a form.</Fine>
                        <Button onClick={() => openInFiles(file.path, true)}>Open in Files</Button>
                      </div>
                    ) : (
                      <FileForm file={file} />
                    )}
                  </section>
                ))}
              </div>
            )}
          </Card>
        ))}
        {mods && !mods.length && <Fine>No config files yet: start the server once.</Fine>}
        {cut && <Fine>There are more config files than this list shows: find the rest in Files.</Fine>}
      </div>
    </>
  );
}
