"use client";

import { usePathname } from "next/navigation";
import { useState } from "react";
import { pages, sections } from "@/content/guide/pages";

/** The guide's sidebar: every page under its label, the one you're on marked. On a wide screen it stands beside
 * the page; on a phone it is folded into a menu button above it from the first paint, so nothing jumps when
 * JavaScript arrives. Without JavaScript the <noscript> rule hides the button and leaves the list open. The labels
 * aren't headings, so a page's own <h1> is the first heading on it. */
export function GuideNav() {
  const here = usePathname().replace(/\/$/, "") || "/";
  const [open, setOpen] = useState(false);  // the links are plain links: each page starts with the menu shut
  const current = pages.find((p) => p.href === here);
  return (
    <nav className="guide-nav" aria-label="Guide" data-open={open || undefined}>
      <noscript><style>{".guide-nav .guide-menu { display: none } "
        + ".guide-nav:not([data-open]) #guide-pages { display: block; padding: 0 }"}</style></noscript>
      <button type="button" className="guide-menu" aria-expanded={open} aria-controls="guide-pages"
        onClick={() => setOpen(!open)}>
        <span>Guide</span>{current && <b>{current.title}</b>}
      </button>
      <div id="guide-pages">
        {sections.map((section, i) => (
          <div key={section.title}>
            <p className="guide-label" id={`guide-label-${i}`}>{section.title}</p>
            <ul aria-labelledby={`guide-label-${i}`}>
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
