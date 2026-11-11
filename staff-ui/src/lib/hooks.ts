// Small hooks every tab uses.
import { useCallback, useEffect, useRef, useState } from "react";
import { messageOf } from "./api";

/**
 * The messages of one box: an error (coral, octagon) and a note that something was done (leaf, tick). Show them
 * with <Messages of={m} />. `run` wraps a step: it clears both, sets `busy` while it runs, and puts a failure in
 * the error, so a handler is just the happy path.
 */
export function useMessages() {
  const [error, setError] = useState("");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const fail = useCallback((e: unknown) => setError(messageOf(e)), []);
  const say = useCallback((text: string) => setNote(text), []);
  const clear = useCallback(() => {
    setError("");
    setNote("");
  }, []);
  const run = useCallback(async <T,>(step: () => Promise<T>): Promise<T | undefined> => {
    setError("");
    setNote("");
    setBusy(true);
    try {
      return await step();
    } catch (e) {
      setError(messageOf(e));
      return undefined;
    } finally {
      setBusy(false);
    }
  }, []);
  return { error, note, busy, fail, say, clear, run, setError, setNote };
}
export type Messages = ReturnType<typeof useMessages>;

/** Call `tick` now and every `ms` while `on` (and the browser tab is visible). */
export function usePoll(tick: () => void, ms: number, on: boolean) {
  const latest = useRef(tick);
  useEffect(() => {
    latest.current = tick;
  });
  useEffect(() => {
    if (!on) return;
    let timer = 0;
    const go = () => {
      if (!document.hidden) latest.current();
    };
    go();
    timer = window.setInterval(go, ms);
    const back = () => {
      if (!document.hidden) latest.current();
    };
    document.addEventListener("visibilitychange", back);
    return () => {
      window.clearInterval(timer);
      document.removeEventListener("visibilitychange", back);
    };
  }, [ms, on]);
}

/** Run `load` each time `active` turns true (a tab is opened), and give a way to run it again. */
export function useOnShow(load: () => void, active: boolean) {
  const latest = useRef(load);
  useEffect(() => {
    latest.current = load;
  });
  useEffect(() => {
    if (active) latest.current();
  }, [active]);
}

/** A value that settles `ms` after the last change (a search box). */
export function useDebounced<T>(value: T, ms: number): T {
  const [settled, setSettled] = useState(value);
  useEffect(() => {
    const timer = window.setTimeout(() => setSettled(value), ms);
    return () => window.clearTimeout(timer);
  }, [value, ms]);
  return settled;
}
