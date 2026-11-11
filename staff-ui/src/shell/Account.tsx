// The account menu, top right of every tab: who you are, your role, two-step login, password and email, log out
// (tools/staff_auth.py through /auth/). It hangs from the sticky top bar, so the page can't scroll it into view: it
// scrolls itself, kept under the bar, and its sections fold (title and state show, the form opens on a click), so
// the whole menu fits on a phone (PR #178).
import { useCallback, useEffect, useRef, useState, type ReactNode, type SyntheticEvent } from "react";
import { ChevronDown, LogOut } from "lucide-react";
import { ended, staffAuth, type AuthError } from "../lib/auth";
import { useSession } from "../lib/session";
import { Actions, Button, cx, Field, Fine, Message } from "../ui/kit";

interface AuthSession {
  user: string;
  email?: string | null;
  email_verified?: boolean;
  two_step?: boolean;
  recovery_left?: number;
  two_step_needed?: boolean;
  held_role?: string;
}

interface Status {
  text: string;
  kind: "error" | "note";
}

const twoStepState = (s: AuthSession) => {
  if (!s.two_step) return "Off";
  const left = Number(s.recovery_left);
  return Number.isFinite(left) ? `On, ${left} recovery code${left === 1 ? "" : "s"}` : "On";
};

export function Account() {
  const { me } = useSession();
  const [session, setSession] = useState<AuthSession | null | undefined>(undefined);
  const [open, setOpen] = useState(false);
  const [status, setStatus] = useState<Status | null>(null);
  const [recovery, setRecovery] = useState<string[] | null>(null);
  const box = useRef<HTMLDetailsElement>(null);
  const statusRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!me) return;
    staffAuth<AuthSession>("GET", "/auth/session").then(
      (s) => {
        setSession(s);
        // An admin or owner login without two-step works as a moderator until it is on (staff_auth.working_role).
        if (s.two_step_needed) setOpen(true);
      },
      () => setSession(null), // the browser's password box: no session to manage here
    );
  }, [me]);

  // Close on a click elsewhere or Escape, as a menu does.
  useEffect(() => {
    if (!open) return;
    const away = (e: PointerEvent) => {
      if (box.current && !box.current.contains(e.target as Node)) setOpen(false);
    };
    const esc = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        setOpen(false);
        box.current?.querySelector("summary")?.focus();
      }
    };
    document.addEventListener("pointerdown", away);
    document.addEventListener("keydown", esc);
    return () => {
      document.removeEventListener("pointerdown", away);
      document.removeEventListener("keydown", esc);
    };
  }, [open]);

  const say = useCallback((text: string, kind: Status["kind"] = "note") => {
    setStatus(text ? { text, kind } : null);
  }, []);
  // The menu scrolls: bring the answer into view inside it.
  useEffect(() => {
    if (status) statusRef.current?.scrollIntoView({ block: "nearest" });
  }, [status]);

  if (!me) return null;
  const update = (patch: Partial<AuthSession>) => setSession((s) => (s ? { ...s, ...patch } : s));

  return (
    <details
      ref={box}
      className="group relative shrink-0 text-bone"
      open={open}
      onToggle={(e) => setOpen((e.currentTarget as HTMLDetailsElement).open)}
    >
      <summary className="frame-bone flex min-h-11 cursor-pointer list-none items-center gap-2 px-2.5 font-bold group-open:[border-image:var(--frame-bone-hover)_6_fill/6px] [&::-webkit-details-marker]:hidden">
        <span className="max-w-[9rem] truncate">{me.user}</span>
        <small className="hidden font-normal text-sage sm:inline">{me.role}</small>
        <ChevronDown aria-hidden="true" className="size-4 shrink-0 group-open:rotate-180" strokeWidth={2.5} />
      </summary>
      <div className="frame-shade absolute right-0 z-40 mt-1.5 grid max-h-[calc(100dvh-8rem)] w-[min(24rem,calc(100vw-2rem))] gap-3.5 overflow-y-auto overscroll-contain bg-shade bg-clip-padding p-3.5">
        <p className="m-0">
          Logged in as <b>{me.user}</b>, {me.role}.
        </p>
        <div ref={statusRef}>{status && <Message kind={status.kind}>{status.text}</Message>}</div>
        {recovery && <RecoveryCodes codes={recovery} done={() => setRecovery(null)} />}
        {session?.two_step_needed && (
          <Message kind="error">
            {`Your login is ${session.held_role}, but it works as a moderator until you turn on two-step login below. Then reload this page.`}
          </Message>
        )}
        {session === null && <Fine>This login is the browser's password box: ask the owner for a new password.</Fine>}
        {session && (
          <>
            <Fine>
              Email:{" "}
              {session.email ? `${session.email}${session.email_verified ? "" : " (not confirmed yet)"}` : "none"}
            </Fine>
            <div className="grid gap-1 border-t-2 border-leaf-2 pt-2">
              <MenuFold title="Two-step login" state={twoStepState(session)} open={Boolean(session.two_step_needed)}>
                <TwoStep session={session} say={say} update={update} showCodes={setRecovery} />
              </MenuFold>
              <MenuFold title="Change password">
                <PasswordForm say={say} />
              </MenuFold>
              <MenuFold title="Change email">
                <EmailForm say={say} session={session} />
              </MenuFold>
            </div>
            <Button
              kind="primary"
              className="justify-self-start"
              icon={<LogOut aria-hidden="true" className="size-4" strokeWidth={2.5} />}
              onClick={async () => {
                try {
                  await staffAuth("POST", "/auth/logout", {});
                } finally {
                  location.replace("/login");
                }
              }}
            >
              Log out
            </Button>
          </>
        )}
      </div>
    </details>
  );
}

function MenuFold({ title, state, open, children }: { title: string; state?: string; open?: boolean; children: ReactNode }) {
  return (
    <details className="fold" open={open}>
      <summary>
        <span>{title}</span>
        {state && <small className="ml-auto font-normal text-sage">{state}</small>}
      </summary>
      <div className="grid gap-3 pb-3 pt-1">{children}</div>
    </details>
  );
}

/** Your recovery codes, shown once. */
export function RecoveryCodes({ codes, done }: { codes: string[]; done: () => void }) {
  return (
    <div className="frame-stone step-in grid gap-3 p-3 text-ink">
      <p className="m-0 font-semibold">
        Your recovery codes, shown only now. Write them down or save them somewhere safe: each one logs you in once if
        you lose your phone.
      </p>
      <ul className="m-0 grid list-none grid-cols-2 gap-x-4 gap-y-1 p-0 font-mono">
        {codes.map((c) => (
          <li key={c}>{c}</li>
        ))}
      </ul>
      <button type="button" className="btn btn-on-stone justify-self-start" onClick={done}>
        I saved them
      </button>
    </div>
  );
}

const Password = ({ label, value, set, fresh }: { label: string; value: string; set: (v: string) => void; fresh?: boolean }) => (
  <Field label={label}>
    {(id) => (
      <input
        id={id}
        type="password"
        className="field w-full"
        autoComplete={fresh ? "new-password" : "current-password"}
        maxLength={256}
        minLength={fresh ? 12 : undefined}
        value={value}
        onChange={(e) => set(e.target.value)}
      />
    )}
  </Field>
);

// Two-step login: a code from an authenticator app at every login, after the password.
const CodeBox = ({ label, value, set }: { label: string; value: string; set: (v: string) => void }) => (
  <Field label={label}>
    {(id) => (
      <input
        id={id}
        type="text"
        className="field w-full font-mono tracking-[0.15em]"
        autoComplete="one-time-code"
        inputMode="numeric"
        maxLength={16}
        autoCapitalize="off"
        spellCheck={false}
        value={value}
        onChange={(e) => set(e.target.value)}
      />
    )}
  </Field>
);

type Say = (text: string, kind?: "error" | "note") => void;

function PasswordForm({ say }: { say: Say }) {
  const [current, setCurrent] = useState("");
  const [fresh, setFresh] = useState("");
  async function send(e: SyntheticEvent) {
    e.preventDefault();
    try {
      const done = await staffAuth<{ ended?: number }>("POST", "/auth/password", { current, password: fresh });
      say(`Password changed.${ended(done.ended)}`);
      setCurrent("");
      setFresh("");
    } catch (error) {
      say((error as Error).message, "error");
    }
  }
  return (
    <form className="grid gap-3" onSubmit={send}>
      <Password label="Current password" value={current} set={setCurrent} />
      <Password label="New password (12 characters or more)" value={fresh} set={setFresh} fresh />
      <button type="submit" className="btn justify-self-start">Change password</button>
    </form>
  );
}

function EmailForm({ say, session }: { say: Say; session: AuthSession }) {
  const [email, setEmail] = useState(session.email || "");
  const [current, setCurrent] = useState("");
  async function send(e: SyntheticEvent) {
    e.preventDefault();
    try {
      const done = await staffAuth<{ sent?: boolean; email?: string }>("POST", "/auth/email", { current, email: email.trim() });
      say(
        done.sent
          ? `A link to confirm ${done.email} is on its way: reset emails go there once it is.`
          : "Saved. Email isn't set up on this server, so the address stays unconfirmed for now.",
      );
      setCurrent("");
    } catch (error) {
      say((error as Error).message, "error");
    }
  }
  return (
    <form className="grid gap-3" onSubmit={send}>
      <Field label="New email">
        {(id) => (
          <input id={id} type="email" className="field w-full" autoComplete="email" maxLength={254} value={email} onChange={(e) => setEmail(e.target.value)} />
        )}
      </Field>
      <Password label="Current password" value={current} set={setCurrent} />
      <button type="submit" className="btn justify-self-start">Change email</button>
    </form>
  );
}

interface Started {
  qr: string;
  modules: number;
  link: string;
  key: string;
  minutes: number;
}

function TwoStep({ session, say, update, showCodes }: {
  session: AuthSession;
  say: Say;
  update: (patch: Partial<AuthSession>) => void;
  showCodes: (codes: string[]) => void;
}) {
  const [started, setStarted] = useState<Started | null>(null);
  const [starting, setStarting] = useState(false);
  const [current, setCurrent] = useState("");
  const [code, setCode] = useState("");
  const chosen = useRef<"fresh" | "off">("fresh");
  const reset = () => {
    setCurrent("");
    setCode("");
  };

  if (!session.two_step) {
    if (!started) {
      return (
        <>
          <Fine>Off. With it on, logging in needs a 6-digit code from an authenticator app on your phone, as well as the password.</Fine>
          <Button
            className="justify-self-start"
            disabled={starting}
            onClick={async () => {
              setStarting(true);
              try {
                setStarted(await staffAuth<Started>("POST", "/auth/2fa/start", {}));
              } catch (error) {
                say((error as Error).message, "error");
              } finally {
                setStarting(false);
              }
            }}
          >
            Turn on two-step login
          </Button>
        </>
      );
    }
    const side = started.modules * 4; // whole pixels per module, so a camera reads it
    return (
      <form
        className="grid gap-3"
        onSubmit={async (e) => {
          e.preventDefault();
          try {
            const done = await staffAuth<{ ended?: number; recovery: string[] }>("POST", "/auth/2fa/confirm", { current, code: code.trim() });
            // A login held back to moderator gets its own role at the next load of the page.
            const held = session.two_step_needed ? " Reload this page to work as your own role." : "";
            say(`Two-step login is on.${ended(done.ended)}${held}`);
            reset();
            setStarted(null);
            update({ two_step: true, two_step_needed: false, recovery_left: done.recovery.length });
            showCodes(done.recovery);
          } catch (error) {
            if ((error as AuthError).status === 410) {
              // the key ran out: the button again
              reset();
              setStarted(null);
            }
            say((error as Error).message, "error");
          }
        }}
      >
        <Fine>
          1. In your authenticator app (Google Authenticator, Microsoft Authenticator, 1Password and the like), add an
          account and scan this code with your phone:
        </Fine>
        <img src={started.qr} alt="A QR code: scan it with your authenticator app" width={side} height={side} className="pixelated justify-self-start bg-white p-2" />
        <a className="link justify-self-start" href={started.link}>
          On this phone? Open it in your authenticator app
        </a>
        <Fine>Can't scan it? Add the account by hand: choose a time-based key and type this:</Fine>
        <p className="m-0 select-all font-mono wrap-anywhere">{started.key}</p>
        <Fine>2. Type the 6-digit code the app shows, and your password, within {started.minutes} minutes.</Fine>
        <Password label="Current password" value={current} set={setCurrent} />
        <CodeBox label="The 6-digit code the app shows now" value={code} set={setCode} />
        <button type="submit" className="btn btn-primary justify-self-start">Turn it on</button>
      </form>
    );
  }

  return (
    <form
      className="grid gap-3"
      onSubmit={async (e) => {
        e.preventDefault();
        const body = { current, code: code.trim() };
        try {
          if (chosen.current === "off") {
            const done = await staffAuth<{ ended?: number }>("POST", "/auth/2fa/off", body);
            say(`Two-step login is off.${ended(done.ended)}`);
            update({ two_step: false });
          } else {
            const done = await staffAuth<{ recovery: string[] }>("POST", "/auth/2fa/recovery", body);
            say("New recovery codes are below. The old ones don't work any more.");
            update({ recovery_left: done.recovery.length });
            showCodes(done.recovery);
          }
          reset();
        } catch (error) {
          say((error as Error).message, "error");
        } finally {
          chosen.current = "fresh"; // Enter presses the first button
        }
      }}
    >
      <Fine>On. Recovery codes left: {session.recovery_left}.</Fine>
      <Password label="Current password" value={current} set={setCurrent} />
      <CodeBox label="Code from your app, or a recovery code" value={code} set={setCode} />
      <Actions>
        <button type="submit" className="btn" onClick={() => (chosen.current = "fresh")}>New recovery codes</button>
        <button type="submit" className={cx("btn btn-danger")} onClick={() => (chosen.current = "off")}>Turn off two-step login</button>
      </Actions>
    </form>
  );
}
