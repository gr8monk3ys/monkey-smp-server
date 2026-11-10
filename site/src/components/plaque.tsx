"use client";

import { type RefObject, useEffect, useRef, useState } from "react";

/** Copying the server address: `copy` puts it on the clipboard; where the browser won't allow that, it selects
 * the address (the element in `code`) so the visitor can copy it themselves. `said` is the word the button shows. */
function useCopy(address: string, code: RefObject<HTMLElement | null>) {
  const timer = useRef<number | undefined>(undefined);
  const [said, setSaid] = useState("Copy");
  const say = (word: string) => {
    setSaid(word);
    clearTimeout(timer.current);
    timer.current = window.setTimeout(() => setSaid("Copy"), 1600);
  };
  const select = () => {
    if (!code.current) return;
    const range = document.createRange();
    range.selectNodeContents(code.current);
    const selection = window.getSelection();
    selection?.removeAllRanges();
    selection?.addRange(range);
    say("Selected");
  };
  const copy = () => {
    if (navigator.clipboard && window.isSecureContext) {
      navigator.clipboard.writeText(address).then(() => say("Copied"), select);
    } else {
      select();
    }
  };
  return { said, copy };
}

/** The server address on its stone plaque, with Copy. A page can show it more than once, and an id must be
 * unique, so only the first one on a page (`first`) carries the ids. Nothing looks them up today. */
export function Plaque({ address, first = true }: { address: string; first?: boolean }) {
  const code = useRef<HTMLElement>(null);
  const { said, copy } = useCopy(address, code);
  return (
    <div className="plaque">
      <span>Server address</span>
      <code id={first ? "address" : undefined} ref={code}>{address}</code>
      <button type="button" id={first ? "copy" : undefined} onClick={copy}>{said}</button>
    </div>
  );
}

/** The dock: the address and the pass, in reach at the bottom of the screen once the page's own plaque has
 * scrolled away (on a page without one, from the start), and gone again while the footer's is in view. The page
 * is built without it, so nothing depends on it. */
export function Dock({ address, store }: { address: string; store: { href: string; title?: string } }) {
  const code = useRef<HTMLElement>(null);
  const { said, copy } = useCopy(address, code);
  const [shown, setShown] = useState(false);
  useEffect(() => {
    if (!("IntersectionObserver" in window)) return;
    const seen = new Map<Element, boolean>();
    const watcher = new IntersectionObserver((entries) => {
      entries.forEach((entry) => seen.set(entry.target, entry.isIntersecting));
      setShown(![...seen.values()].some(Boolean));
    });
    document.querySelectorAll(".plaque, footer").forEach((plaque) => {
      seen.set(plaque, true);
      watcher.observe(plaque);
    });
    return () => watcher.disconnect();
  }, []);
  return (
    <aside className="dock" aria-label="Join the server" hidden={!shown}>
      <button type="button" className="dock-address" onClick={copy}>
        <code ref={code}>{address}</code>
        <span aria-live="polite">{said}</span>
      </button>
      <a className="button" data-link="STORE_URL" href={store.href} title={store.title}>Get a pass</a>
    </aside>
  );
}
