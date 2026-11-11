import { useCallback, useState } from "react";
import type { TabProps } from "../../shell/tabs";
import { get, messageOf, post } from "../../lib/api";
import { useMessages, useOnShow } from "../../lib/hooks";
import { useSession } from "../../lib/session";
import { Messages, PageHead, Panels } from "../../ui/kit";
import GameRules from "./GameRules";
import Properties, { type SettingsData } from "./Properties";
import ServerIcon from "./ServerIcon";

export default function SettingsTab({ active }: TabProps) {
  const { can, me } = useSession();
  const m = useMessages();
  const [data, setData] = useState<SettingsData | null>(null);
  const [rules, setRules] = useState<any[] | null>(null);
  const [rulesError, setRulesError] = useState("");
  const [rev, setRev] = useState(0);

  const loadRules = useCallback(async () => {
    try {
      const got = await get("/api/gamerules");
      setRules(got.rules || []);
      setRulesError("");
      setRev((n) => n + 1);
    } catch (e) {
      setRules([]);
      setRulesError(messageOf(e));
    }
  }, []);

  const loadSettings = useCallback(async () => {
    if (!can("admin")) {
      m.setError("Settings need an admin login.");
    } else {
      try {
        const got = await get("/api/settings");
        setData({ fields: got.fields || [], groups: got.groups || [], other: got.other || [], mtime: got.mtime });
        m.setError("");
      } catch (e) {
        m.fail(e);
      }
    }
    loadRules();
  }, [can, m.setError, m.fail, loadRules]); // eslint-disable-line react-hooks/exhaustive-deps

  useOnShow(() => {
    loadSettings();
  }, active && me !== null);

  const setRule = async (rule: any, value: boolean | number) => {
    if (typeof value === "number" && Number.isNaN(value)) {
      m.setError("Type a number.");
      return;
    }
    m.setError("");
    try {
      const done = await post("/api/gamerules", { name: rule.name, value });
      m.say(`${rule.name} is ${done.value} now.`);
    } catch (e) {
      m.fail(e);
      loadRules();
    }
  };

  return (
    <>
      <PageHead title="Settings">
        <p>
          server.properties as a form. Most changes take effect when the server restarts (Server tab). Ports, RCON, the seed, the world's name and online mode
          are locked here. Every save keeps the old file in Files, history.
        </p>
      </PageHead>
      <div className="mb-4 flex flex-col gap-3">
        <Messages of={m} />
      </div>
      <Panels>
        <Properties data={data} m={m} reload={loadSettings} />
        <ServerIcon active={active} />
        {rules !== null && <GameRules key={rev} rules={rules} error={rulesError} onSet={setRule} />}
      </Panels>
    </>
  );
}
