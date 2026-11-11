// The in-page typed step of the Mods tab. The kit's confirm step has no tick box, and a change to one jar needs
// one ("Keep it off after restarts"), so the Mods tab has its own, built the same way and looking the same.
import { useCallback, useEffect, useRef, useState, type ReactNode } from "react";
import { Actions, cx } from "../../ui/kit";

export interface StepSpec {
  /** What will happen, in a sentence. */
  message: ReactNode;
  /** The button that does it. */
  yes: string;
  danger?: boolean;
  /** The text that must be typed before the button works (a jar's file name, a pack's name). */
  expect?: string;
  /** The aria-label of the box the text goes in. */
  label?: string;
  /** A tick box under it; its state is onYes's argument. */
  check?: { label: string; checked: boolean };
  onYes: (ticked: boolean) => void;
}

/** `const [node, open, close] = useStep()`: put {node} where it should show; open({...}) shows it. */
export function useStep(): [ReactNode, (spec: StepSpec) => void, () => void] {
  const [spec, setSpec] = useState<(StepSpec & { n: number }) | null>(null);
  const count = useRef(0);
  const close = useCallback(() => setSpec(null), []);
  const open = useCallback((next: StepSpec) => {
    count.current += 1;
    setSpec({ ...next, n: count.current });
  }, []);
  const node = spec ? <StepBox key={spec.n} spec={spec} close={close} /> : null;
  return [node, open, close];
}

function StepBox({ spec, close }: { spec: StepSpec; close: () => void }) {
  const [typed, setTyped] = useState("");
  const [ticked, setTicked] = useState(spec.check?.checked ?? false);
  const box = useRef<HTMLDivElement>(null);
  const field = useRef<HTMLInputElement>(null);
  const yes = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    box.current?.scrollIntoView({ block: "nearest" });
    (field.current ?? yes.current)?.focus();
  }, []);
  const blocked = spec.expect !== undefined && typed.trim() !== spec.expect;
  const go = () => {
    if (blocked) return;
    close();
    spec.onYes(ticked);
  };
  return (
    <div ref={box} className="frame-stone step-in flex max-w-[52em] flex-col gap-3 px-3 py-3 text-ink" role="group" aria-label="Confirm">
      <div className="font-semibold wrap-anywhere">{spec.message}</div>
      {spec.expect !== undefined && (
        <input
          ref={field}
          type="text"
          className="field text-bone"
          aria-label={spec.label ?? "Type to confirm"}
          placeholder={spec.expect}
          maxLength={128}
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
      {spec.check && (
        <label className="check">
          <input type="checkbox" checked={ticked} onChange={(e) => setTicked(e.target.checked)} />
          {spec.check.label}
        </label>
      )}
      <Actions>
        <button ref={yes} type="button" className={cx("btn", spec.danger ? "btn-danger-solid" : "btn-primary")} disabled={blocked} onClick={go}>
          {spec.yes}
        </button>
        <button type="button" className="btn btn-on-stone" onClick={close}>
          Cancel
        </button>
      </Actions>
    </div>
  );
}
