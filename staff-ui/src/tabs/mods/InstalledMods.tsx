import { useState, type ReactNode } from "react";
import { size } from "../../lib/format";
import { useSession } from "../../lib/session";
import { Button, Empty, Input, Message, Panel, Row, Rows } from "../../ui/kit";
import { KEEP_OFF, heldWords, useMods } from "./ctl";

export interface ModsData {
  mods: any[];
  held_gone: any[];
  holds_supported: boolean;
  players_missing: string[];
  players_pack: boolean;
}

// A pinned mod players have in their pack, which their game needs: keeping it off on the server may lock them out.
const playersHaveIt = (m: any) => m.client_side === "required" && m.in_players_pack;
const lockout = (m: any) =>
  playersHaveIt(m) ? " Players have it in their pack and need it there: with it off on the server, players may not be able to join." : "";

const withFacts = (title: ReactNode, facts: string) => (
  <>
    {title} {facts && <span className="meta">{facts}</span>}
  </>
);

export default function InstalledMods({ data }: { data: ModsData | null }) {
  const { can } = useSession();
  const { call, step, askPlayers } = useMods();
  const [filter, setFilter] = useState("");
  const typed = filter.trim().toLowerCase();
  const rows = (data?.mods ?? []).filter((m) => !typed || [m.name, m.id, m.file, m.description].join(" ").toLowerCase().includes(typed));
  const gone = (data?.held_gone ?? []).filter((g) => !typed || g.file.toLowerCase().includes(typed));
  const holds = data?.holds_supported !== false;
  const total = data?.mods.length ?? 0;

  const allow = (file: string) => (
    <Button
      key="allow"
      need="owner"
      small
      onClick={() =>
        step(`Let the release put ${file} back? The next start downloads it again.`, "Allow again", file, () =>
          call("/api/mod-hold", { file, held: false, confirm: file }, `${file} is allowed again.`),
        )
      }
    >
      Allow again
    </Button>
  );

  const buttons = (m: any) => {
    const on = m.enabled !== false;
    const base = String(m.file).replace(/\.disabled$/, "");
    const pinnedOff = m.holdable
      ? ` It is pinned: unless you keep it off, the next start puts the release's jar back.${lockout(m)}`
      : m.pinned
        ? ` It is pinned: the next start puts the release's jar back.${holds ? "" : " The running release can't keep it off."}${lockout(m)}`
        : "";
    const out: ReactNode[] = [
      <Button
        key="toggle"
        need="owner"
        small
        onClick={() =>
          step(
            on
              ? `Turn off ${m.file}? It is renamed to .jar.disabled and the server stops loading it at the next restart.${pinnedOff}`
              : `Turn ${m.file} back on?${m.held ? " It is kept off now: turning it on allows it again." : ""}`,
            on ? "Turn off" : "Turn on",
            m.file,
            (hold) => call("/api/mod-toggle", { file: m.file, enabled: !on, confirm: m.file, hold: on && hold }, on ? "Turned off." : "Turned on."),
            on && m.holdable ? KEEP_OFF : undefined,
            on,
          )
        }
      >
        {on ? "Turn off" : "Turn on"}
      </Button>,
      <Button
        key="remove"
        kind="danger"
        need="owner"
        small
        onClick={() =>
          step(
            `Remove ${m.file}? It is moved to mods-removed/ on the machine, never deleted.${pinnedOff}`,
            "Remove",
            m.file,
            (hold) => call("/api/mod-remove", { file: m.file, confirm: m.file, hold }, "Removed."),
            m.holdable ? KEEP_OFF : undefined,
            true,
          )
        }
      >
        Remove
      </Button>,
    ];
    // Only the owner changes which jars run (tools/staff_host.py, OWNER_MODS); admins see these greyed out.
    if (m.held) out.push(allow(base));
    if (!m.pinned && m.client_side === "unknown") {
      out.push(
        <Button key="side" need="admin" small onClick={() => askPlayers(m.file, false)}>
          Players need it?
        </Button>,
      );
    }
    return out;
  };

  const missing = data?.players_missing ?? [];
  const missingText = !missing.length
    ? ""
    : data?.players_pack
      ? `The players' pack is missing ${missing.length} mod(s) players need: ${missing.join(", ")}. Until the owner adds them in a release, players may not be able to join.`
      : `The players' pack couldn't be read here, so it can't be checked. These mods are marked as ones players need: ${missing.join(", ")}.`;

  return (
    <Panel
      wide
      title="Installed mods"
      meta={typed ? `(${rows.length} of ${total})` : `(${total})`}
      aside={
        <Input
          type="search"
          className="w-full sm:w-64"
          placeholder="Filter by name"
          aria-label="Filter the installed mods"
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
        />
      }
    >
      <Message kind="error">{missingText}</Message>
      <Rows label="Installed mods">
        {gone.map((g) => (
          <Row
            key={`gone-${g.file}`}
            title={withFacts(g.file, `(removed, ${heldWords(g.held)})`)}
            about={`${(g.held && g.held.why) || ""}${lockout(g)}`.trim()}
            actions={can("admin") ? allow(g.file) : undefined}
          />
        ))}
        {rows.map((m) => {
          const side = ({ client: "client only", server: "server only", both: "client and server" } as Record<string, string>)[m.environment] || "";
          const players = m.client_side === "required" ? "players need it" : "";
          const flags = [m.enabled === false ? "off" : "", m.pinned ? "pinned" : "", heldWords(m.held), players].filter(Boolean);
          return (
            <Row
              key={m.file}
              title={withFacts(
                m.error ? m.file : `${m.name} ${m.version || ""}`.trim(),
                m.error ? `(${m.error})` : `(${[m.id, side, size(m.size), ...flags].filter(Boolean).join(", ")})`,
              )}
              about={m.description}
              actions={can("admin") && m.file ? buttons(m) : undefined}
            />
          );
        })}
        {!gone.length && !rows.length && <Empty>{typed ? "No mod matches." : data ? "No mods found." : "Reading the mods..."}</Empty>}
      </Rows>
    </Panel>
  );
}
