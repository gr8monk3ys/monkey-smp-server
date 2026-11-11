// The Users tab (owners): the logins of the page's own login page (tools/staff_auth.py through tools/staff_panel.py's
// /api/users). A confirm step is two buttons on the page, never confirm().
import { useCallback, useState, type SyntheticEvent } from "react";
import { UserPlus } from "lucide-react";
import { ROLES, staffAuth } from "../../lib/auth";
import { useOnShow } from "../../lib/hooks";
import { useSession } from "../../lib/session";
import { Actions, Button, Empty, Field, Message, PageHead, Panel, Row, Rows, Select, useConfirm } from "../../ui/kit";
import type { TabProps } from "../../shell/tabs";

interface User {
  name: string;
  role: string;
  disabled?: boolean;
  locked?: boolean;
  password_set?: boolean;
  two_step?: boolean;
  email?: string | null;
  email_verified?: boolean;
  sessions: number;
  created?: string;
}

const DAY = new Intl.DateTimeFormat(undefined, { year: "numeric", month: "short", day: "numeric" });
// The server's ISO time as a plain date, e.g. "Nov 6, 2026".
const day = (iso?: string) => {
  const ms = Date.parse(iso || "");
  return Number.isNaN(ms) ? "?" : DAY.format(new Date(ms));
};
const roleOptions = ROLES.map((r) => ({ value: r, label: r }));

export default function UsersTab({ active }: TabProps) {
  const { me } = useSession();
  const [users, setUsers] = useState<User[] | null>(null);
  const [mail, setMail] = useState(false);
  const [error, setError] = useState("");
  const [note, setNote] = useState("");
  const [handover, setHandover] = useState<{ name: string; link: string } | null>(null);

  const load = useCallback(async () => {
    if (me?.role !== "owner") return;
    try {
      const data = await staffAuth<{ users: User[]; mail?: boolean }>("GET", "/api/users");
      setUsers(data.users);
      setMail(Boolean(data.mail));
    } catch (e) {
      setError((e as Error).message);
    }
  }, [me?.role]);
  useOnShow(load, active && me?.role === "owner");

  const act = useCallback(
    async <T,>(url: string, body: unknown, done?: (result: T) => void): Promise<T | null> => {
      setError("");
      try {
        const result = await staffAuth<T>("POST", url, body);
        done?.(result);
        await load();
        return result;
      } catch (e) {
        setError((e as Error).message);
        setNote("");
        return null;
      }
    },
    [load],
  );

  return (
    <>
      <PageHead title="Users">
        <p>The logins of the page's own login page. Owners only: the last owner can't be demoted, disabled or deleted.</p>
      </PageHead>
      <div className="mb-4 grid gap-3 empty:hidden">
        <Message kind="error">{error}</Message>
        <Message kind="note">{note}</Message>
        {handover && <Handover {...handover} done={() => setHandover(null)} />}
      </div>
      <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_22rem] lg:items-start">
        <Panel title="Logins" meta={users ? `(${users.length})` : undefined}>
          {users === null ? (
            <p className="skeleton h-24" aria-label="Loading" />
          ) : (
            <Rows label="Logins">
              {users.map((u) => (
                <UserRow key={u.name} u={u} self={me?.user} act={act} handover={setHandover} />
              ))}
              {!users.length && <Empty>No logins on the login page yet: add the first owner below.</Empty>}
            </Rows>
          )}
        </Panel>
        <Panel title="Add a login" className="lg:sticky lg:top-28">
          <AddForm
            act={act}
            added={(r) => {
              if (r.link) setHandover({ name: r.name, link: r.link });
              setNote(r.emailed ? `${r.name} was emailed a link to choose a password.` : `${r.name} is added. ${mail ? "" : "Email isn't set up, so "}pass on the link above.`);
            }}
          />
        </Panel>
      </div>
    </>
  );
}

type Act = <T>(url: string, body: unknown, done?: (result: T) => void) => Promise<T | null>;

function UserRow({ u, self, act, handover }: { u: User; self?: string; act: Act; handover: (h: { name: string; link: string }) => void }) {
  const [confirm, ask] = useConfirm();
  const flags = [u.disabled && "disabled", u.locked && "locked for now", !u.password_set && "no password yet", u.two_step && "2FA on"].filter(Boolean);
  const mailText = u.email ? `${u.email}${u.email_verified ? "" : " (not confirmed)"}` : "no email";
  return (
    <Row
      title={
        <span className="flex flex-wrap items-baseline gap-x-2.5">
          <b className="wrap-anywhere">{u.name}</b>
          <span className={u.role === "owner" ? "text-gold" : "meta"}>{u.role}</span>
          {flags.length > 0 && <span className="meta">{flags.join(", ")}</span>}
        </span>
      }
      about={`${mailText}; ${u.sessions} session${u.sessions === 1 ? "" : "s"}; added ${day(u.created)}`}
    >
      <Actions className="mt-3">
        <Select
          aria-label={`Role of ${u.name}`}
          className="w-auto"
          value={u.role}
          options={roleOptions}
          onChange={(e) => {
            const next = e.target.value;
            ask({
              message: `Change the role of ${u.name} from ${u.role} to ${next}? Their access changes at once.`,
              yes: "Change role",
              onYes: () => act("/api/users/role", { name: u.name, role: next }),
            });
          }}
        />
        <Button small onClick={() => act("/api/users/disable", { name: u.name, disabled: !u.disabled })}>
          {u.disabled ? "Enable" : "Disable"}
        </Button>
        <Button small onClick={() => act("/api/users/sessions", { name: u.name })}>Log out everywhere</Button>
        <Button small onClick={() => act<{ link: string }>("/api/users/link", { name: u.name }, (r) => handover({ name: u.name, link: r.link }))}>
          New password link
        </Button>
        {/* A lost phone: only for someone else; your own goes from the account menu, with a code. */}
        {u.two_step && u.name !== self && (
          <Button
            small
            onClick={() =>
              ask({
                message: `Turn off two-step login for ${u.name}? Do this only if you know it's them (a lost phone): the password alone will log in, and every session of theirs is logged out.`,
                yes: "Turn off 2FA",
                onYes: () => act("/api/users/2fa-off", { name: u.name }),
              })
            }
          >
            Turn off 2FA
          </Button>
        )}
        <Button
          small
          kind="danger"
          onClick={() =>
            ask({ message: `Delete the login ${u.name}? It can't be undone.`, yes: "Delete", danger: true, onYes: () => act("/api/users/delete", { name: u.name }) })
          }
        >
          Delete
        </Button>
      </Actions>
      {confirm && <div className="mt-3">{confirm}</div>}
    </Row>
  );
}

interface Added {
  name: string;
  link?: string;
  emailed?: boolean;
}

function AddForm({ act, added }: { act: Act; added: (r: Added) => void }) {
  const [name, setName] = useState("");
  const [role, setRole] = useState<string>("moderator");
  const [email, setEmail] = useState("");
  async function send(e: SyntheticEvent) {
    e.preventDefault();
    const r = await act<Added>("/api/users", { name: name.trim(), role, email: email.trim() || null });
    if (!r) return;
    setName("");
    setEmail("");
    added(r);
  }
  return (
    <form className="grid gap-3" onSubmit={send}>
      <Field label="Name (small letters, digits, _)">
        {(id) => <input id={id} className="field w-full" maxLength={32} autoComplete="off" autoCapitalize="off" spellCheck={false} value={name} onChange={(e) => setName(e.target.value)} />}
      </Field>
      <Field label="Role">{(id) => <Select id={id} options={roleOptions} value={role} onChange={(e) => setRole(e.target.value)} />}</Field>
      <Field label="Email (optional)">
        {(id) => <input id={id} type="email" className="field w-full" maxLength={254} autoComplete="off" value={email} onChange={(e) => setEmail(e.target.value)} />}
      </Field>
      <button type="submit" className="btn btn-primary justify-self-start">
        <UserPlus aria-hidden="true" className="size-4" strokeWidth={2.5} />
        Add
      </button>
    </form>
  );
}

function Handover({ name, link, done }: { name: string; link: string; done: () => void }) {
  return (
    <div className="frame-stone step-in grid max-w-[52em] gap-3 p-3 text-ink">
      <p className="m-0 font-semibold">The link for {name}, shown only now. It works once, for 24 hours: pass it on privately.</p>
      <input type="text" className="field font-mono text-bone" readOnly value={link} aria-label={`Password link for ${name}`} onFocus={(e) => e.currentTarget.select()} />
      <button type="button" className="btn btn-on-stone justify-self-start" onClick={done}>Done</button>
    </div>
  );
}
