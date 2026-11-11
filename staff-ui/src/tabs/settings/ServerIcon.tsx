// The server icon: the picture next to the server in the players' list.
import { useRef, useState } from "react";
import { api, get, post } from "../../lib/api";
import { useMessages, useOnShow } from "../../lib/hooks";
import { useSession } from "../../lib/session";
import { Button, Fine, FormRow, Input, Messages, Panel, useConfirm } from "../../ui/kit";

export default function ServerIcon({ active }: { active: boolean }) {
  const { can, me } = useSession();
  const m = useMessages();
  const [icon, setIcon] = useState("");
  const file = useRef<HTMLInputElement>(null);
  const [confirm, ask] = useConfirm();

  const load = async () => {
    if (!can("admin")) return;
    try {
      setIcon((await get("/api/server-icon")).icon || "");
      m.setError("");
    } catch (e) {
      m.fail(e);
    }
  };
  useOnShow(load, active && me !== null);

  const call = async (url: string, body: unknown, words: string, raw?: File) => {
    m.clear();
    try {
      const done = raw ? await api("POST", url, undefined, { raw }) : await post(url, body);
      setIcon(done.icon || "");
      m.say(`${words}${done.kept_in ? ` The old icon is kept in ${done.kept_in}.` : ""} It shows after the next restart.`);
      return true;
    } catch (e) {
      m.fail(e);
      return false;
    }
  };

  const upload = async () => {
    const picked = file.current?.files?.[0];
    m.setError("");
    if (!picked) return m.fail("Pick a PNG first.");
    if (picked.size > 1048576) return m.fail("An icon is at most 1 MB.");
    await call("/api/server-icon", undefined, "Icon saved.", picked);
    if (file.current) file.current.value = "";
  };

  if (!can("admin")) return null;

  return (
    <Panel title="Server icon">
      <Fine>The picture next to the server in the players' list: a 64 by 64 pixel PNG. It shows after the next restart.</Fine>
      <Messages of={m} />
      <div className="flex flex-wrap items-center gap-4">
        {icon ? (
          <img src={icon} width={64} height={64} alt="The server icon now" className="pixelated size-16 shrink-0" />
        ) : (
          <Fine>No icon: players see the default.</Fine>
        )}
        <FormRow className="min-w-[min(16rem,100%)] flex-1">
          <Input ref={file} type="file" accept="image/png" aria-label="Icon PNG file" need="admin" />
          <Button need="admin" onClick={upload}>
            Upload
          </Button>
          {icon && (
            <Button
              kind="danger"
              need="admin"
              onClick={() =>
                ask({
                  message: "Remove the server icon? It is moved to staff-removed/ on the machine.",
                  yes: "Remove",
                  danger: true,
                  onYes: () => {
                    call("/api/server-icon-remove", {}, "Icon removed.");
                  },
                })
              }
            >
              Remove
            </Button>
          )}
        </FormRow>
      </div>
      {confirm}
    </Panel>
  );
}
