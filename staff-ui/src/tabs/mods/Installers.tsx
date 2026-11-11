import { useRef, useState } from "react";
import { api, get, post, query } from "../../lib/api";
import { size } from "../../lib/format";
import { useSession } from "../../lib/session";
import { Button, Empty, Fine, FormRow, Input, Panel, Row, Rows } from "../../ui/kit";
import { JAR_NAME, PACK_NAME, useMods } from "./ctl";

/** Upload a jar: owner only, because a jar runs as the server. */
export function UploadJar() {
  const { can } = useSession();
  const { m, step, done } = useMods();
  const file = useRef<HTMLInputElement>(null);
  if (!can("owner")) return null;

  const upload = () => {
    const picked = file.current?.files?.[0];
    m.clear();
    if (!picked) return m.fail("Pick a .jar file first.");
    if (!JAR_NAME.test(picked.name)) {
      return m.fail("A jar's name has letters, digits, spaces and . _ + - ( ) only, no '..', and ends in .jar: rename the file first.");
    }
    step(
      `Put ${picked.name} (${size(picked.size)}) in the server's mods folder? A jar with the same name or the same mod id is moved to mods-removed/ first.`,
      "Upload the mod",
      picked.name,
      async () => {
        try {
          const answer = await api("POST", "/api/mod-upload?" + query({ name: picked.name, confirm: picked.name }), undefined, { raw: picked });
          if (file.current) file.current.value = "";
          done(`Installed ${answer.name} ${answer.version || ""}.`.replace(" .", "."), answer);
        } catch (e) {
          m.fail(e);
        }
      },
    );
  };

  return (
    <Panel title="Upload a jar">
      <Fine>
        A Fabric jar of up to 64 MB. Client-only mods are refused: they go in the players' pack. Only the owner can upload a jar, because a jar runs as the
        server.
      </Fine>
      <FormRow>
        <Input ref={file} type="file" accept=".jar" aria-label="Mod jar file" need="owner" />
        <Button kind="primary" need="owner" onClick={upload}>
          Upload the jar
        </Button>
      </FormRow>
    </Panel>
  );
}

/** Find a mod on Modrinth (through the panel): admins search, the owner installs. */
export function FindOnModrinth() {
  const { m, step, done } = useMods();
  const [q, setQ] = useState("");
  const [result, setResult] = useState<{ version: string; hits: any[] } | null>(null);
  const [searching, setSearching] = useState(false);

  const install = async (project: string) => {
    m.clear();
    m.say("Downloading from Modrinth...");
    try {
      const answer = await post("/api/modrinth-install", { project, confirm: project });
      const needs = (answer.requires || []).length ? ` It needs these mods too (Modrinth IDs): ${answer.requires.join(", ")}.` : "";
      done(`Installed ${answer.name} ${answer.version || ""}.${needs}`.replace(" .", "."), answer);
    } catch (e) {
      m.say("");
      m.fail(e);
    }
  };

  const search = async () => {
    const text = q.trim();
    m.clear();
    if (!text) return;
    setSearching(true);
    try {
      const data = await get("/api/modrinth?" + query({ q: text }));
      setResult({ version: `Fabric mods for ${data.game_version} that run on a server.`, hits: data.hits || [] });
    } catch (e) {
      setResult(null);
      m.fail(e);
    } finally {
      setSearching(false);
    }
  };

  return (
    <Panel title="Find one on Modrinth">
      <Fine>
        Admins can search; only the owner can install, because a jar runs as the server. Modrinth files are checked against Modrinth's hash.
      </Fine>
      <FormRow>
        <Input
          type="search"
          maxLength={80}
          placeholder="Mod name"
          aria-label="Search Modrinth"
          need="admin"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") search();
          }}
        />
        <Button need="admin" onClick={search} disabled={searching}>
          Search
        </Button>
      </FormRow>
      {result && <Fine>{result.version}</Fine>}
      {(searching || result) && (
        <Rows label="Modrinth results">
          {searching && <Empty>Searching...</Empty>}
          {!searching && result && !result.hits.length && <Empty>No Fabric mod for this version matches.</Empty>}
          {!searching &&
            result?.hits.map((h) => (
              <Row
                key={h.slug}
                title={
                  <>
                    {h.title} ({h.slug}){" "}
                    <span className="meta">
                      {[h.downloads !== null && h.downloads !== undefined ? `${h.downloads} downloads` : "", `players need it: ${h.client_side}`].filter(Boolean).join(", ")}
                    </span>
                  </>
                }
                about={h.description}
                actions={
                  <Button
                    small
                    need="owner"
                    onClick={() =>
                      step(
                        `Install ${h.title} from Modrinth? The newest release for this game version is downloaded and its sha512 checked.`,
                        "Install",
                        h.slug,
                        () => install(h.slug),
                      )
                    }
                  >
                    Install
                  </Button>
                }
              />
            ))}
        </Rows>
      )}
    </Panel>
  );
}

/** Install a .mrpack: owner only. */
export function InstallPack() {
  const { can } = useSession();
  const { m, step, done } = useMods();
  const file = useRef<HTMLInputElement>(null);
  const [going, setGoing] = useState(false);
  if (!can("owner")) return null;

  const install = () => {
    const picked = file.current?.files?.[0];
    m.clear();
    if (!picked) return m.fail("Pick a .mrpack file first.");
    if (!PACK_NAME.test(picked.name)) {
      return m.fail("A modpack's name has letters, digits, spaces and . _ + ( ) - only and ends in .mrpack: rename the file first.");
    }
    step(
      `Install the server mods from ${picked.name} (${size(picked.size)})? A jar with the same name or mod id is moved to mods-removed/ first.`,
      "Install the pack",
      picked.name,
      async () => {
        m.say("Downloading and checking every mod... keep this page open.");
        setGoing(true);
        try {
          const answer = await api("POST", "/api/modpack?" + query({ name: picked.name, confirm: picked.name }), undefined, { raw: picked });
          if (file.current) file.current.value = "";
          const skipped = answer.skipped ? ` ${answer.skipped} client-only mod(s) skipped.` : "";
          const missing = (answer.players_missing || []).length
            ? ` Players need ${answer.players_missing.join(", ")} too, and ${
                answer.players_pack
                  ? "the players' pack doesn't have them yet, so they may not be able to join until the owner adds them"
                  : "the players' pack couldn't be read here, so check that it has them"
              }.`
            : "";
          done(`Installed ${answer.installed.length} mod(s) from ${answer.pack}.${skipped}${missing}`, {
            note_error: (answer.note_errors || []).join(" ") || null,
            pack_error: answer.pack_error,
          });
        } catch (e) {
          m.say("");
          m.fail(e);
        }
        setGoing(false);
      },
    );
  };

  return (
    <Panel title="Install a modpack">
      <Fine>
        A Modrinth .mrpack for this game version and Fabric, up to 64 MB. Its server mods are downloaded and checked first; only if every one passes are they put
        in the mods folder. Client-only mods and the pack's config files are skipped. Only the owner can install a pack.
      </Fine>
      <FormRow>
        <Input ref={file} type="file" accept=".mrpack" aria-label="Modpack file" need="owner" />
        <Button need="owner" onClick={install} disabled={going}>
          Install the pack
        </Button>
      </FormRow>
    </Panel>
  );
}
