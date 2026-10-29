"use client";

import { usePathname } from "next/navigation";
import { useState, useSyncExternalStore } from "react";
import { pages, sections } from "@/content/guide/pages";

const noChange = () => () => {};

/** The guide's sidebar: every page under its heading, the one you're on marked. On a wide screen it stands
 * beside the page; on a phone it folds into a menu button above it. It folds only once JavaScript is running,
 * so without it the list is simply open. */
export function GuideNav() {
  const here = usePathname().replace(/\/$/, "") || "/";
  const ready = useSyncExternalStore(noChange, () => true, () => false);  // false while prerendered, true in a browser
  const [open, setOpen] = useState(false);  // the links are plain links: each page starts with the menu shut
  const current = pages.find((p) => p.href === here);
  return (
    <nav className="guide-nav" aria-label="Guide" data-ready={ready || undefined} data-open={open || undefined}>
      <button type="button" className="guide-menu" aria-expanded={open} aria-controls="guide-pages"
        onClick={() => setOpen(!open)}>
        <span>Guide</span>{current && <b>{current.title}</b>}
      </button>
      <div id="guide-pages">
        {sections.map((section) => (
          <div key={section.title}>
            <h2>{section.title}</h2>
            <ul>
              {section.pages.map((p) => (
                <li key={p.href}>
                  <a href={p.href} aria-current={p.href === here ? "page" : undefined}>{p.title}</a>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>
    </nav>
  );
}
