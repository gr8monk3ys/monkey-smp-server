// The staff page's building blocks, in the site's block language (DESIGN.md). Every tab builds from these, so the
// page looks like one thing. Text only: nothing from the server ever goes in as HTML, and nothing has a style
// attribute (the policy refuses it): every look is a class.
import {
  forwardRef,
  useCallback,
  useEffect,
  useId,
  useRef,
  useState,
  type ButtonHTMLAttributes,
  type InputHTMLAttributes,
  type ReactNode,
  type SelectHTMLAttributes,
  type TextareaHTMLAttributes,
} from "react";
import type { Messages as MessageState } from "../lib/hooks";
import { useSession, type Role } from "../lib/session";

export const cx = (...names: (string | false | null | undefined)[]) => names.filter(Boolean).join(" ");

// ---------------------------------------------------------------- buttons

export type ButtonKind = "primary" | "ghost" | "danger" | "link";

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  /** primary: gold, the main step of a view. ghost (default): bone outline. danger: coral, takes something away. */
  kind?: ButtonKind;
  small?: boolean;
  /** The least role that may press it: below it the button is disabled and says why on hover. */
  need?: Role;
  icon?: ReactNode;
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  { kind = "ghost", small, need, icon, className, children, disabled, title, ...rest },
  ref,
) {
  const { can } = useSession();
  const locked = need !== undefined && !can(need);
  return (
    <button
      ref={ref}
      type="button"
      className={cx(kind === "link" ? "link" : "btn", kind === "primary" && "btn-primary", kind === "danger" && "btn-danger", small && "btn-small", className)}
      disabled={disabled || locked}
      title={locked ? `Needs an ${need} login` : title}
      {...rest}
    >
      {icon}
      {children}
    </button>
  );
});

/** A group of toggles (time range, console view): the pressed one is gold. */
export function Toggles<T extends string>({ label, value, options, onChange }: {
  label: string;
  value: T;
  options: { value: T; label: string }[];
  onChange: (value: T) => void;
}) {
  return (
    <div role="group" aria-label={label} className="flex flex-wrap gap-2">
      {options.map((o) => (
        <Button key={o.value} small aria-pressed={o.value === value} onClick={() => onChange(o.value)}>
          {o.label}
        </Button>
      ))}
    </div>
  );
}

/** A row of buttons. */
export const Actions = ({ children, className }: { children: ReactNode; className?: string }) => (
  <div className={cx("flex flex-wrap items-center gap-2", className)}>{children}</div>
);

// ---------------------------------------------------------------- fields

type InputProps = InputHTMLAttributes<HTMLInputElement> & { need?: Role };

/** A text box. Has `aria-label` or a <Label>; `need` disables it below a role. Spellcheck and autofill are off. */
export const Input = forwardRef<HTMLInputElement, InputProps>(function Input({ className, need, disabled, ...rest }, ref) {
  const { can } = useSession();
  return (
    <input
      ref={ref}
      type="text"
      autoComplete="off"
      autoCapitalize="off"
      spellCheck={false}
      className={cx(rest.type === "checkbox" ? "" : "field", className)}
      disabled={disabled || (need !== undefined && !can(need))}
      {...rest}
    />
  );
});

type SelectProps = SelectHTMLAttributes<HTMLSelectElement> & { need?: Role; options?: { value: string; label: string }[] };

export const Select = forwardRef<HTMLSelectElement, SelectProps>(function Select({ className, need, disabled, options, children, ...rest }, ref) {
  const { can } = useSession();
  return (
    <select ref={ref} className={cx("field", className)} disabled={disabled || (need !== undefined && !can(need))} {...rest}>
      {options?.map((o) => (
        <option key={o.value} value={o.value}>
          {o.label}
        </option>
      ))}
      {children}
    </select>
  );
});

type TextareaProps = TextareaHTMLAttributes<HTMLTextAreaElement> & { need?: Role };

export const Textarea = forwardRef<HTMLTextAreaElement, TextareaProps>(function Textarea({ className, need, disabled, ...rest }, ref) {
  const { can } = useSession();
  return (
    <textarea
      ref={ref}
      autoComplete="off"
      autoCapitalize="off"
      spellCheck={false}
      className={cx("field w-full", className)}
      disabled={disabled || (need !== undefined && !can(need))}
      {...rest}
    />
  );
});

export function Check({ label, className, ...rest }: InputHTMLAttributes<HTMLInputElement> & { label: ReactNode }) {
  return (
    <label className={cx("check", className)}>
      <input type="checkbox" {...rest} />
      {label}
    </label>
  );
}

/** A label above a field, with its help under it. `children` gets the field's id. */
export function Field({ label, help, children, className }: { label: ReactNode; help?: ReactNode; children: (id: string) => ReactNode; className?: string }) {
  const id = useId();
  return (
    <div className={cx("min-w-0", className)}>
      <label className="label" htmlFor={id}>
        {label}
      </label>
      {children(id)}
      {help && <p className="fine mt-1">{help}</p>}
    </div>
  );
}

/** A row of fields and buttons that wraps on a phone (the old page's `.add`). */
export const FormRow = ({ children, className }: { children: ReactNode; className?: string }) => (
  <div className={cx("flex flex-wrap items-stretch gap-2 [&>.field]:flex-1 [&>.field]:basis-40", className)}>{children}</div>
);

// ---------------------------------------------------------------- surfaces

/** A tab's heading and what it is for. */
export function PageHead({ title, children, aside }: { title: string; children?: ReactNode; aside?: ReactNode }) {
  return (
    <header className="mb-5 flex flex-wrap items-end justify-between gap-x-6 gap-y-3">
      <div className="min-w-0">
        <h1>{title}</h1>
        {children && <div className="fine mt-2 max-w-[60em] [&>p+p]:mt-2">{children}</div>}
      </div>
      {aside}
    </header>
  );
}

/** A framed block (shade fill, pixel corners). `wide` spans both columns of a <Panels> grid. */
export function Panel({ title, meta, aside, children, wide, className, id, labelledBy }: {
  title?: ReactNode;
  meta?: ReactNode;
  aside?: ReactNode;
  children?: ReactNode;
  wide?: boolean;
  className?: string;
  id?: string;
  labelledBy?: string;
}) {
  const headId = useId();
  return (
    <section id={id} className={cx("panel flex flex-col gap-3", wide && "lg:col-span-2", className)} aria-labelledby={title ? headId : labelledBy}>
      {(title || aside) && (
        <div className="panel-head flex flex-wrap items-center justify-between gap-x-4 gap-y-2">
          {title && (
            <h3 id={headId}>
              {title} {meta !== undefined && meta !== "" && <span className="meta">{meta}</span>}
            </h3>
          )}
          {aside}
        </div>
      )}
      {children}
    </section>
  );
}

/** Panels in two columns on a wide screen, one on a phone. */
export const Panels = ({ children, className }: { children: ReactNode; className?: string }) => (
  <div className={cx("grid grid-cols-1 gap-4 lg:grid-cols-2", className)}>{children}</div>
);

export const Fine = ({ children, className, ...rest }: { children: ReactNode; className?: string; id?: string; role?: string }) => (
  <p className={cx("fine", className)} {...rest}>
    {children}
  </p>
);

/** A folding section (the old <details class="table">). */
export function Fold({ title, children, open, onToggle, className }: { title: ReactNode; children: ReactNode; open?: boolean; onToggle?: (open: boolean) => void; className?: string }) {
  return (
    <details className={cx("fold", className)} open={open} onToggle={(e) => onToggle?.((e.currentTarget as HTMLDetailsElement).open)}>
      <summary>{title}</summary>
      <div className="mt-2">{children}</div>
    </details>
  );
}

// ---------------------------------------------------------------- messages

// What the user last pressed or sent, and when: a message is brought into view only when it answers that.
let acted: { at: number; target: EventTarget | null } = { at: 0, target: null };
if (typeof document !== "undefined") {
  const note = (e: Event) => { acted = { at: Date.now(), target: e.target }; };
  document.addEventListener("click", note, true);
  document.addEventListener("submit", note, true);
  document.addEventListener("keydown", note, true);
}

/** One message: an error (coral outline, octagon), a warning (stone, triangle) or a note (leaf, tick). When it
 * answers something the user just did in the same panel, it is brought into view, so the answer to a button far down
 * a phone's page is seen; a message that comes with a tab's first load leaves the page where it is. */
export function Message({ kind, children, id }: { kind: "error" | "warn" | "note"; children: ReactNode; id?: string }) {
  const ref = useRef<HTMLParagraphElement>(null);
  const text = typeof children === "string" ? children : "";
  useEffect(() => {
    const el = ref.current;
    const host = el?.closest("section, form, dialog") ?? null;
    if (el && host && acted.target instanceof Node && host.contains(acted.target) && Date.now() - acted.at < 60_000) {
      el.scrollIntoView({ block: "nearest" });
    }
  }, [text]);
  if (children === "" || children === null || children === undefined || children === false) return null;
  return (
    <p ref={ref} id={id} className={cx("msg", `msg-${kind}`)} role={kind === "error" ? "alert" : "status"}>
      <span className="min-w-0 wrap-anywhere">{children}</span>
    </p>
  );
}

/** A box's error and note (from useMessages). */
export function Messages({ of }: { of: Pick<MessageState, "error" | "note"> }) {
  return (
    <>
      <Message kind="error">{of.error}</Message>
      <Message kind="note">{of.note}</Message>
    </>
  );
}

// ---------------------------------------------------------------- the confirm step

export interface Ask {
  /** What will happen, in a sentence. */
  message: ReactNode;
  /** The button that does it. */
  yes: string;
  /** Coral (takes something away) or gold. */
  danger?: boolean;
  /** A text box under the message; what was typed (spaces folded) is onYes's argument. */
  field?: { label: string; placeholder?: string; value?: string; max?: number };
  /** For a big step: the word that must be typed before the button works (case as given). */
  word?: string;
  onYes: (typed?: string) => void;
}

/**
 * The in-page confirm step, in place of confirm(): what will happen, a button that does it and one that doesn't.
 * `const [confirm, ask] = useConfirm()`; put {confirm} where it should show; `ask({...})` opens it.
 */
export function useConfirm(): [ReactNode, (ask: Ask) => void, () => void] {
  const [asking, setAsking] = useState<Ask | null>(null);
  const close = useCallback(() => setAsking(null), []);
  const node = asking ? <ConfirmBox key={String(asking.yes) + String(asking.message)} ask={asking} close={close} /> : null;
  return [node, setAsking, close];
}

function ConfirmBox({ ask, close }: { ask: Ask; close: () => void }) {
  const [typed, setTyped] = useState(ask.field?.value ?? "");
  const box = useRef<HTMLDivElement>(null);
  const first = useRef<HTMLInputElement | HTMLButtonElement | null>(null);
  useEffect(() => {
    box.current?.scrollIntoView({ block: "nearest" });
    first.current?.focus();
  }, []);
  const folded = typed.replace(/\s+/g, " ").trim();
  const blocked = ask.word !== undefined && folded !== ask.word;
  const go = () => {
    if (blocked) return;
    close();
    ask.onYes(ask.field || ask.word !== undefined ? folded : undefined);
  };
  const hasBox = ask.field || ask.word !== undefined;
  return (
    <div ref={box} className="frame-stone step-in flex max-w-[52em] flex-col gap-3 px-3 py-3 text-ink" role="group" aria-label="Confirm">
      <div className="font-semibold [&_code]:text-ink">{ask.message}</div>
      {hasBox && (
        <input
          ref={(n) => {
            first.current = n;
          }}
          type="text"
          className="field text-bone"
          aria-label={ask.field?.label ?? `Type ${ask.word} to confirm`}
          placeholder={ask.field?.placeholder ?? ask.word}
          maxLength={ask.field?.max ?? 120}
          value={typed}
          autoComplete="off"
          autoCapitalize="off"
          spellCheck={false}
          onChange={(e) => setTyped(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") go();
            if (e.key === "Escape") close();
          }}
        />
      )}
      <Actions>
        <button
          ref={(n) => {
            if (!hasBox) first.current = n;
          }}
          type="button"
          className={cx("btn", ask.danger ? "btn-danger-solid" : "btn-primary")}
          disabled={blocked}
          onClick={go}
        >
          {ask.yes}
        </button>
        <button type="button" className="btn btn-on-stone" onClick={close}>
          Cancel
        </button>
      </Actions>
    </div>
  );
}

// ---------------------------------------------------------------- rows

/** A list of rows split by leaf lines (the old `ul.entries`). */
export const Rows = ({ children, className, label }: { children: ReactNode; className?: string; label?: string }) => (
  <ul className={cx("rows", className)} aria-label={label}>
    {children}
  </ul>
);

/** One row: a title, what it is under it, and its buttons on the right (under it on a phone). */
export function Row({ title, about, actions, children, className }: { title?: ReactNode; about?: ReactNode; actions?: ReactNode; children?: ReactNode; className?: string }) {
  return (
    <li className={cx("flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between", className)}>
      <div className="min-w-0 flex-1">
        {title !== undefined && <div className="row-title">{title}</div>}
        {about !== undefined && about !== "" && <div className="row-about">{about}</div>}
        {children}
      </div>
      {actions && <div className="flex shrink-0 flex-wrap gap-2">{actions}</div>}
    </li>
  );
}

export const Empty = ({ children }: { children: ReactNode }) => <li className="empty">{children}</li>;

/** A table that scrolls sideways on its own on a phone. */
export const TableScroll = ({ label, children, className }: { label: string; children: ReactNode; className?: string }) => (
  <div className={cx("table-scroll", className)} tabIndex={0} role="region" aria-label={label}>
    {children}
  </div>
);

/** Facts as label and value pairs (the old <dl>). */
export function Facts({ items, className }: { items: [ReactNode, ReactNode][]; className?: string }) {
  return (
    <dl className={cx("grid grid-cols-[auto_1fr] gap-x-4 gap-y-1.5", className)}>
      {items.map(([k, v], i) => (
        <div key={i} className="contents">
          <dt className="text-sage">{k}</dt>
          <dd className="m-0 min-w-0 wrap-anywhere text-bone">{v}</dd>
        </div>
      ))}
    </dl>
  );
}

// ---------------------------------------------------------------- the status marks

export type MarkKind = "good" | "busy" | "slow" | "off" | "unknown";

const MARK_PATHS: Record<MarkKind, string> = {
  good: "M1 1h10v10H1z",                                       // a filled square
  busy: "M5 1h2v2h1v2h1v2h1v2h1v2H1V9h1V7h1V5h1V3h1z",           // a triangle
  slow: "M5 0h2v2h2v2h2v4H9v2H7v2H5v-2H3V8H1V4h2V2h2z",          // an octagon
  off: "M1 1h10v10H1zM3 3v6h6V3z",                             // a hollow square
  unknown: "M1 1h10v10H1zM3 3v6h6V3zM5 5h2v2H5z",              // a hollow square with a dot
};

/** The pixel shape that goes with a status word. Decoration unless `label` is given: the word beside it says it. */
export function Mark({ kind, className, label }: { kind: MarkKind; className?: string; label?: string }) {
  return (
    <svg
      className={cx("mark", `mark-${kind}`, className)}
      viewBox="0 0 12 12"
      role={label ? "img" : undefined}
      aria-label={label}
      aria-hidden={label ? undefined : "true"}
    >
      <path d={MARK_PATHS[kind]} fillRule="evenodd" />
    </svg>
  );
}
