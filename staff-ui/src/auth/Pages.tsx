// The login, reset and email pages (login.html, reset.html, verify.html: one build, the body's data-page says which),
// talking to tools/staff_auth.py through /auth/. Everything from the server goes in as text. Forms are sent from
// here, never by the browser itself: Caddy's Content-Security-Policy refuses that (form-action 'none'), so a password
// can't end up in an address.
import { useEffect, useRef, useState, type InputHTMLAttributes, type ReactNode, type Ref, type SyntheticEvent } from "react";
import { auth, AuthError } from "../lib/auth";
import { Actions, Button, Field, Fine, Message } from "../ui/kit";

const messageOf = (e: unknown) => (e instanceof Error ? e.message : String(e));

// The link's token is in the address after #, which the browser never sends anywhere; it is taken off the address
// at once, so it isn't left in the history. This tab keeps it until it is used, so a reload (a phone does that when
// you switch apps) doesn't lose it.
const KEPT = `monkey-staff-link:${location.pathname.replace(/\.html$/, "")}`; // a reset link and a verify link apart
function readLinkToken(): string {
  let token = new URLSearchParams(location.hash.slice(1)).get("token") || "";
  if (location.hash) history.replaceState(null, "", location.pathname);
  try {
    if (token) sessionStorage.setItem(KEPT, token);
    else token = sessionStorage.getItem(KEPT) || "";
  } catch {
    /* no storage: only the address had it */
  }
  return token;
}
function linkUsed() {
  try {
    sessionStorage.removeItem(KEPT);
  } catch {
    /* nothing kept */
  }
}

/** Read once per page load: the token is taken off the address the first time. */
let linkToken: string | null = null;
const useLinkToken = () => {
  if (linkToken === null) linkToken = readLinkToken();
  return linkToken;
};

// ---------------------------------------------------------------- the frame

function Gate({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="gate-world flex min-h-dvh flex-col">
      <header className="bg-leaf-2">
        <div className="flex items-center gap-2.5 px-4 py-3 sm:px-6">
          <img src="/img/monkey.svg" alt="" width={28} height={28} className="pixelated size-7" />
          <p className="m-0 font-display text-xl leading-none text-bone">
            Monkey <span className="text-gold">SMP</span> <span className="text-sage">staff</span>
          </p>
        </div>
        <div className="canopy" aria-hidden="true" />
      </header>
      <main className="flex flex-1 flex-col items-center px-4 pb-16 pt-10 sm:pt-16">
        <img src="/img/monkey.svg" alt="" width={88} height={88} className="pixelated mb-6 size-[88px]" />
        <section className="panel step-in flex w-full max-w-[26rem] flex-col gap-4 px-5 py-6 sm:px-7" aria-labelledby="gate-title">
          <h1 id="gate-title">{title}</h1>
          {children}
        </section>
        <p className="fine mt-8 max-w-[26rem] text-center">Staff only. Every change made here is logged with your name.</p>
      </main>
    </div>
  );
}

type TextFieldProps = { label: string; help?: ReactNode; inputRef?: Ref<HTMLInputElement> } & InputHTMLAttributes<HTMLInputElement>;
const TextField = ({ label, help, inputRef, ...rest }: TextFieldProps) => {
  return (
    <Field label={label} help={help}>
      {(id) => <input id={id} ref={inputRef} className="field w-full" autoCapitalize="off" spellCheck={false} required {...rest} />}
    </Field>
  );
};

// ---------------------------------------------------------------- log in

type Step = "login" | "code" | "forgot";

function Login() {
  const [step, setStep] = useState<Step>("login");
  const [error, setError] = useState("");
  const [loggedIn, setLoggedIn] = useState("");
  const [busy, setBusy] = useState(false);
  const [name, setName] = useState("");
  const [password, setPassword] = useState("");
  const passwordBox = useRef<HTMLInputElement>(null);
  const nameBox = useRef<HTMLInputElement>(null);
  const [challenge, setChallenge] = useState("");

  useEffect(() => {
    auth<{ user: string }>("GET", "/auth/session").then((me) => setLoggedIn(me.user), () => {});
  }, []);

  useEffect(() => {
    if (step === "login") (name ? passwordBox : nameBox).current?.focus();
  }, [step]); // eslint-disable-line react-hooks/exhaustive-deps

  async function send(event: SyntheticEvent) {
    event.preventDefault();
    setError("");
    const who = name.trim().toLowerCase();
    if (!who || !password) {
      setError("Type your name and password.");
      return;
    }
    setBusy(true);
    try {
      const done = await auth<{ two_step?: boolean; challenge?: string }>("POST", "/auth/login", { name: who, password });
      setPassword("");
      if (done.two_step) {
        setChallenge(done.challenge || "");
        setStep("code");
        return;
      }
      location.replace("/");
    } catch (e) {
      setError(messageOf(e));
      setPassword("");
      passwordBox.current?.focus();
    } finally {
      setBusy(false);
    }
  }

  if (step === "code") {
    return (
      <Code
        challenge={challenge}
        back={(message) => {
          setChallenge("");
          setError(message);
          setStep("login");
        }}
      />
    );
  }
  if (step === "forgot") return <Forgot start={name} close={() => setStep("login")} />;

  return (
    <Gate title="Log in">
      <Message kind="error">{error}</Message>
      {loggedIn && (
        <div className="msg msg-note flex-wrap" role="status">
          <span className="min-w-0 wrap-anywhere">You are logged in as {loggedIn}.</span>
          <a className="btn btn-small" href="/">Open the staff page</a>
        </div>
      )}
      <form method="post" action="/auth/login" noValidate onSubmit={send} className="flex flex-col gap-4">
        <TextField label="Name" name="username" autoComplete="username" maxLength={32} value={name}
          onChange={(e) => setName(e.target.value)} inputRef={nameBox} />
        <TextField label="Password" name="password" type="password" autoComplete="current-password" maxLength={256}
          value={password} onChange={(e) => setPassword(e.target.value)} inputRef={passwordBox} />
        <Actions className="justify-between gap-y-3">
          <button className="btn btn-primary min-w-32" type="submit" disabled={busy}>Log in</button>
          <Button kind="link" onClick={() => setStep("forgot")}>Forgot password?</Button>
        </Actions>
      </form>
    </Gate>
  );
}

// Two-step login: the right password gave a challenge, good once for 5 minutes; the code turns it into a session.
function Code({ challenge, back }: { challenge: string; back: (message: string) => void }) {
  const [recovery, setRecovery] = useState(false);
  const [code, setCode] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const box = useRef<HTMLInputElement>(null);
  useEffect(() => {
    setCode("");
    box.current?.focus();
  }, [recovery]);

  async function send(event: SyntheticEvent) {
    event.preventDefault();
    setError("");
    const typed = code.trim();
    if (!typed) {
      setError(recovery ? "Type a recovery code." : "Type the 6-digit code from your app.");
      return;
    }
    setBusy(true);
    try {
      await auth("POST", "/auth/login/code", { challenge, code: typed });
      location.replace("/");
    } catch (e) {
      setCode("");
      // The challenge is gone (too slow, or the name got locked): start from the password again.
      if (e instanceof AuthError && (e.status === 400 || e.status === 429)) back(e.message);
      else {
        setError(messageOf(e));
        box.current?.focus();
      }
    } finally {
      setBusy(false);
    }
  }

  return (
    <Gate title="Two-step login">
      <Fine>
        {recovery
          ? "Type one of the recovery codes you saved when you turned on two-step login. Each works once."
          : "Open your authenticator app and type the 6-digit code it shows for Monkey SMP staff. You have 5 minutes."}
      </Fine>
      <Message kind="error">{error}</Message>
      <form method="post" action="/auth/login/code" noValidate onSubmit={send} className="flex flex-col gap-4">
        <TextField
          key={recovery ? "recovery" : "app"}
          label={recovery ? "Recovery code" : "Code from your app"}
          name="code"
          autoComplete={recovery ? "off" : "one-time-code"}
          inputMode={recovery ? "text" : "numeric"}
          maxLength={recovery ? 16 : 11}
          className="field w-full font-mono text-lg tracking-[0.2em]"
          value={code}
          onChange={(e) => setCode(e.target.value)}
          inputRef={box}
        />
        <button className="btn btn-primary self-start min-w-32" type="submit" disabled={busy}>Log in</button>
        <Actions className="gap-x-5">
          <Button kind="link" onClick={() => setRecovery(!recovery)}>
            {recovery ? "Use the code from your app" : "Use a recovery code"}
          </Button>
          <Button kind="link" onClick={() => back("")}>Start again</Button>
        </Actions>
      </form>
    </Gate>
  );
}

function Forgot({ start, close }: { start: string; close: () => void }) {
  const [who, setWho] = useState(start);
  const [error, setError] = useState("");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const box = useRef<HTMLInputElement>(null);
  useEffect(() => box.current?.focus(), []);

  async function send(event: SyntheticEvent) {
    event.preventDefault();
    setError("");
    setNote("");
    if (!who.trim()) {
      setError("Type your name or your email.");
      return;
    }
    setBusy(true);
    try {
      const done = await auth<{ message: string }>("POST", "/auth/forgot", { who: who.trim() });
      setNote(done.message);
    } catch (e) {
      setError(messageOf(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Gate title="Forgot password">
      <Fine>
        Type your name or your email. If the login has a confirmed email, a link to set a new password goes there; it
        works once, for 30 minutes.
      </Fine>
      <Message kind="error">{error}</Message>
      <Message kind="note">{note}</Message>
      <form method="post" action="/auth/forgot" noValidate onSubmit={send} className="flex flex-col gap-4">
        <TextField label="Name or email" name="who" autoComplete="username" maxLength={254} value={who}
          onChange={(e) => setWho(e.target.value)} inputRef={box} />
        <Actions className="justify-between gap-y-3">
          <button className="btn btn-primary" type="submit" disabled={busy}>Send the link</button>
          <Button kind="link" onClick={close}>Back to log in</Button>
        </Actions>
      </form>
    </Gate>
  );
}

// ---------------------------------------------------------------- reset and verify

function Reset() {
  const token = useLinkToken();
  const [password, setPassword] = useState("");
  const [again, setAgain] = useState("");
  const [error, setError] = useState(token ? "" : "This page needs the link from the email or from the owner. Ask for a new one if it's lost.");
  const [done, setDone] = useState("");
  const [busy, setBusy] = useState(false);

  async function send(event: SyntheticEvent) {
    event.preventDefault();
    setError("");
    if (password.length < 12) {
      setError("A password needs at least 12 characters.");
      return;
    }
    if (password !== again) {
      setError("The two passwords aren't the same.");
      return;
    }
    setBusy(true);
    try {
      const answer = await auth<{ user: string }>("POST", "/auth/reset", { token, password });
      linkUsed();
      setPassword("");
      setAgain("");
      setDone(`The password of ${answer.user} is set. Log in with it now.`);
    } catch (e) {
      setError(messageOf(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Gate title="Choose a password">
      <Fine>
        At least 12 characters, and not your login's name. A long phrase is easiest to remember. Every place you are
        logged in is logged out.
      </Fine>
      <Message kind="error">{error}</Message>
      <Message kind="note">{done}</Message>
      {done ? (
        <a className="btn btn-primary self-start" href="/login">Log in</a>
      ) : token ? (
        <form method="post" action="/auth/reset" noValidate onSubmit={send} className="flex flex-col gap-4">
          <TextField label="New password" name="new-password" type="password" autoComplete="new-password" minLength={12}
            maxLength={256} value={password} onChange={(e) => setPassword(e.target.value)} autoFocus />
          <TextField label="The same again" name="again" type="password" autoComplete="new-password" minLength={12}
            maxLength={256} value={again} onChange={(e) => setAgain(e.target.value)} />
          <button className="btn btn-primary self-start" type="submit" disabled={busy}>Set the password</button>
        </form>
      ) : null}
    </Gate>
  );
}

function Verify() {
  const token = useLinkToken();
  const [error, setError] = useState(token ? "" : "This page needs the link from the email. Ask for a new one if it's lost.");
  const [done, setDone] = useState("");
  const [busy, setBusy] = useState(false);

  // A button, not at once: a mail scanner that opens the link doesn't confirm anything.
  async function confirmEmail() {
    setError("");
    setBusy(true);
    try {
      const answer = await auth<{ email: string; user: string }>("POST", "/auth/verify", { token });
      linkUsed();
      setDone(`${answer.email} is confirmed for ${answer.user}.`);
    } catch (e) {
      setError(messageOf(e));
      setBusy(false);
    }
  }

  return (
    <Gate title="Confirm your email">
      <Fine>Once confirmed, a forgotten password can be reset by email.</Fine>
      <Message kind="error">{error}</Message>
      <Message kind="note">{done}</Message>
      <Actions className="gap-x-5">
        {token && !done && (
          <button className="btn btn-primary" type="button" disabled={busy} onClick={confirmEmail}>Confirm</button>
        )}
        <a className="link" href="/login">Log in</a>
      </Actions>
    </Gate>
  );
}

export function AuthPage() {
  const page = document.body.dataset.page;
  if (page === "reset") return <Reset />;
  if (page === "verify") return <Verify />;
  return <Login />;
}
