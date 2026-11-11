// Bans by address (the old server.js "bans by address" part). Admins only: the box is hidden below that.
import { useState } from "react";
import { get, post } from "../../lib/api";
import { useMessages, useOnShow } from "../../lib/hooks";
import { useSession } from "../../lib/session";
import { Button, Empty, Fine, FormRow, Input, Messages, Panel, Row, Rows, useConfirm } from "../../ui/kit";

interface IpBan {
  ip: string;
  reason?: string;
}

export default function IpBans({ active }: { active: boolean }) {
  const { can } = useSession();
  const [ips, setIps] = useState<IpBan[] | null | undefined>(undefined); // null: the file can't be read
  const [target, setTarget] = useState("");
  const [reason, setReason] = useState("");
  const m = useMessages();
  const [confirm, ask] = useConfirm();

  const load = async () => {
    if (!can("admin")) return;
    try {
      const data = await get("/api/ip-bans");
      setIps(data.ips ?? null);
    } catch (e) {
      m.fail(e);
    }
  };
  useOnShow(load, active);

  if (!can("admin")) return null;

  const said = (done: any) => m.say(done.said ? `Done. The server said: ${done.said}` : "Done.");

  const pardon = async (ip: string) => {
    m.clear();
    try {
      said(await post("/api/ip-pardon", { ip }));
    } catch (e) {
      m.fail(e);
    }
    load();
  };

  const ban = () => {
    const who = target.trim();
    const why = reason.replace(/\s+/g, " ").trim();
    if (!who) {
      m.fail(new Error("Type an address, or the name of a player who is online."));
      return;
    }
    m.clear();
    ask({
      message: `Ban the address ${who}? Everyone joining from it is refused, even under another name, until it is pardoned.`,
      yes: "Yes, ban the address",
      danger: true,
      onYes: async () => {
        try {
          said(await post("/api/ip-ban", { target: who, reason: why }));
          setTarget("");
          setReason("");
        } catch (e) {
          m.fail(e);
        }
        load();
      },
    });
  };
  const enter = (e: React.KeyboardEvent) => e.key === "Enter" && ban();

  return (
    <Panel title="Banned addresses" meta={ips ? ips.length || "" : ""}>
      <Fine>
        Bans an IP address, so nobody can join from it under any name. Type a public IPv4 or IPv6 address, or the name of a player who is online to ban the address they are on. A private or local address is refused: it could be a proxy's, and banning it would keep everyone out.
      </Fine>
      <Messages of={m} />
      {confirm}
      <Rows label="Banned addresses">
        {(ips || []).map((b) => (
          <Row
            key={b.ip}
            title={<span className="wrap-anywhere">{b.ip}</span>}
            about={b.reason ? `(${b.reason})` : undefined}
            actions={<Button small need="admin" onClick={() => pardon(b.ip)}>Pardon</Button>}
          />
        ))}
        {ips !== undefined && !(ips && ips.length) && <Empty>{ips ? "No address is banned." : "banned-ips.json can't be read."}</Empty>}
      </Rows>
      <FormRow>
        <Input maxLength={45} placeholder="Address or online player" aria-label="Address or online player" value={target} onChange={(e) => setTarget(e.target.value)} onKeyDown={enter} />
        <Input maxLength={120} placeholder="Reason (optional)" aria-label="Reason" value={reason} onChange={(e) => setReason(e.target.value)} onKeyDown={enter} />
        <Button kind="danger" need="admin" onClick={ban}>Ban address</Button>
      </FormRow>
    </Panel>
  );
}
