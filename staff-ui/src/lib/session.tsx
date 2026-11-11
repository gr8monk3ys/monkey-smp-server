// Who is logged in (GET /api/me) and what their role allows. The panel checks every role itself: this only hides or
// greys out what a login can't use, as the old scripts did.
import { createContext, useContext, type ReactNode } from "react";

export type Role = "moderator" | "admin" | "owner";
const RANK: Record<Role, number> = { moderator: 0, admin: 1, owner: 2 };

export interface Me {
  user: string;
  role: Role;
  /** Everything else /api/me answers (the login page's session fields among them). */
  [key: string]: any;
}

export interface Session {
  me: Me | null;
  /** Whether the login's role is at least `need`. False until /api/me has answered. */
  can: (need: Role) => boolean;
  /** Read /api/me again (after a change of password, email or two-step). */
  refresh: () => void;
}

const SessionContext = createContext<Session>({ me: null, can: () => false, refresh: () => {} });

export function SessionProvider({ value, children }: { value: Session; children: ReactNode }) {
  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>;
}

export const useSession = () => useContext(SessionContext);

export const roleAtLeast = (role: Role | undefined, need: Role) => role !== undefined && RANK[role] >= RANK[need];
