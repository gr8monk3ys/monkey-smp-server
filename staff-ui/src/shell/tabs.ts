// The tabs, ordered by job (DESIGN.md, "Staff page"): watching, running, then the owner's.
import type { ComponentType } from "react";
import type { Role } from "../lib/session";
import StatusTab from "../tabs/status";
import PlayersTab from "../tabs/players";
import ConsoleTab from "../tabs/console";
import ReportsTab from "../tabs/reports";
import ServerTab from "../tabs/server";
import SettingsTab from "../tabs/settings";
import ModsTab from "../tabs/mods";
import ModcfgTab from "../tabs/modcfg";
import FilesTab from "../tabs/files";
import UsersTab from "../tabs/users";

export interface TabProps {
  /** Whether this tab is the one showing. A tab stays mounted once opened (so an open file or a typed command
   * survives a look at another tab); it loads and polls only while active. */
  active: boolean;
}

export interface TabSpec {
  id: string;
  label: string;
  group: "Watching" | "Running" | "Owner";
  need?: Role;
  component: ComponentType<TabProps>;
}


export const TABS: TabSpec[] = [
  { id: "status", label: "Status", group: "Watching", component: StatusTab },
  { id: "players", label: "Players", group: "Watching", component: PlayersTab },
  { id: "console", label: "Console", group: "Watching", component: ConsoleTab },
  { id: "reports", label: "Reports", group: "Watching", component: ReportsTab },
  { id: "server", label: "Server", group: "Running", component: ServerTab },
  { id: "settings", label: "Settings", group: "Running", component: SettingsTab },
  { id: "mods", label: "Mods", group: "Running", component: ModsTab },
  { id: "modcfg", label: "Mod settings", group: "Running", component: ModcfgTab },
  { id: "files", label: "Files", group: "Running", component: FilesTab },
  { id: "users", label: "Users", group: "Owner", need: "owner", component: UsersTab },
];
