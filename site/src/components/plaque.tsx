"use client";

import { useRef, useState } from "react";

/** The server address on its stone plaque. Copy puts it on the clipboard; where the browser won't allow that,
 * it selects the address so the visitor can copy it themselves. */
export function Plaque({ address }: { address: string }) {
  const code = useRef<HTMLElement>(null);
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
  return (
    <div className="plaque">
      <span>Server address</span>
      <code id="address" ref={code}>{address}</code>
      <button type="button" id="copy" onClick={copy}>{said}</button>
    </div>
  );
}
