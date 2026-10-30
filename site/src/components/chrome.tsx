import { Fragment } from "react";
import type { LinkKey } from "@/lib/config";
import { newestWrapped } from "@/lib/wrapped";
import { ConfigLink } from "./links";

/** A link in the nav or the footer: a path or in-page anchor, or one of config.json's URLs. */
export type NavItem = { label: string; href: string } | { label: string; to: LinkKey };

function Item({ item }: { item: NavItem }) {
  return "to" in item ? <ConfigLink to={item.to}>{item.label}</ConfigLink> : <a href={item.href}>{item.label}</a>;
}

/** The canopy: the logo and the page's nav, in a band of leaves that hang over the top of the page. */
export function Canopy({ home = "/", label, items }: { home?: string; label: string; items: NavItem[] }) {
  return (
    <>
      <a className="skip" href="#main">Skip to content</a>
      <header className="canopy">
        <a className="brand" href={home}><img src="/kit/logo-1392w.png" alt="Monkey SMP" width={261} height={48} /></a>
        <nav aria-label={label}>
          {items.map((item) => <Item key={item.label} item={item} />)}
        </nav>
      </header>
    </>
  );
}

/** The footer: the page's links in a row (and the newest Season Wrapped once there is one), and the line every
 * Minecraft server owes Mojang. */
export function Footer({ items }: { items: NavItem[] }) {
  const wrapped = newestWrapped();
  if (wrapped) items = [...items, wrapped];
  return (
    <footer className="crown">
      <p>
        {items.map((item, i) => (
          <Fragment key={item.label}>{i > 0 && " · "}<Item item={item} /></Fragment>
        ))}
      </p>
      <p className="small">Not an official Minecraft product. Not approved by or associated with Mojang or Microsoft.</p>
    </footer>
  );
}
