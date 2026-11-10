import { config, type LinkKey, target } from "@/lib/config";
import { newestWrapped } from "@/lib/wrapped";
import { ConfigLink } from "./links";
import { Dock, Plaque } from "./plaque";

/** A link in the nav or the footer: a path or in-page anchor, or one of config.json's URLs. */
export type NavItem = { label: string; href: string } | { label: string; to: LinkKey };

/** Where a page sits in the site, for the nav: its link is marked as the current page. */
export type Here = "home" | "guide" | "changes" | "elsewhere";

function Item({ item, current }: { item: NavItem; current?: boolean }) {
  return "to" in item
    ? <ConfigLink to={item.to}>{item.label}</ConfigLink>
    : <a href={item.href} aria-current={current ? "page" : undefined}>{item.label}</a>;
}

/** The canopy: the logo and the site's nav, in a band of leaves that hang over the top of the page. Every page
 * has the same six links, so nobody has to learn a second menu; on the front page the first three scroll to
 * their sections, and everywhere else Rules opens the full rulebook. */
export function Canopy({ here = "elsewhere" }: { here?: Here }) {
  const front = here === "home" ? "" : "/";
  const items: (NavItem & { at?: Here })[] = [
    { label: "Join", href: `${front}#join` },
    { label: "Pricing", href: `${front}#pricing` },
    { label: "Rules", href: here === "home" ? "#rules" : "/guide/rules" },
    { label: "Guide", href: "/guide", at: "guide" },
    { label: "Map", to: "MAP_URL" },
    { label: "News", href: "/changes", at: "changes" },
  ];
  return (
    <>
      <a className="skip" href="#main">Skip to content</a>
      <header className="canopy">
        <a className="brand" href={here === "home" ? "#" : "/"}>
          <img src="/kit/logo-1392w.png" alt="Monkey SMP" width={261} height={48} />
        </a>
        <nav aria-label="Site">
          {items.map((item) => <Item key={item.label} item={item} current={item.at === here} />)}
        </nav>
      </header>
    </>
  );
}

/** The footer, the same on every page: the address again, then every link in three short lists by what you came
 * for (the newest Season Wrapped joins once there is one), and the line every Minecraft server owes Mojang. The
 * dock (the address and the pass at the bottom of the screen) lives here too, so every page has it. */
export function Footer({ here = "elsewhere" }: { here?: Here }) {
  const front = here === "home" ? "" : "/";
  const wrapped = newestWrapped();
  const lists: { title: string; items: NavItem[] }[] = [
    {
      title: "Play",
      items: [
        { label: "Get a pass", to: "STORE_URL" },
        { label: "Install the modpack", href: `${front}#join` },
        { label: "Live map", to: "MAP_URL" },
        { label: "Questions", href: `${front}#faq` },
      ],
    },
    {
      title: "Read",
      items: [
        { label: "How it works", href: "/guide" },
        { label: "The rulebook", href: "/guide/rules" },
        { label: "What changed", href: "/changes" },
        ...(wrapped ? [wrapped] : []),
      ],
    },
    {
      title: "Talk",
      items: [
        { label: "Discord", to: "DISCORD_INVITE" },
        { label: "Contact", to: "CONTACT_URL" },
        { label: "Creator codes", href: "/creators" },
        { label: "Logo and banners", href: `${front}#kit` },
      ],
    },
  ];
  return (
    <>
      <footer className="crown">
        <div className="foot">
          <div className="foot-home">
            <a className="brand" href={here === "home" ? "#" : "/"}>
              <img src="/kit/logo-1392w.png" alt="Monkey SMP" width={261} height={48} loading="lazy" />
            </a>
            <Plaque address={config.ADDRESS} first={false} />
          </div>
          {lists.map((list) => (
            <nav key={list.title} aria-label={list.title}>
              <h2>{list.title}</h2>
              <ul>
                {list.items.map((item) => <li key={item.label}><Item item={item} /></li>)}
              </ul>
            </nav>
          ))}
        </div>
        <p className="small">
          <a href="/privacy">Privacy</a> · <a href="/terms">Terms</a> · Not an official Minecraft product. Not approved
          by or associated with Mojang or Microsoft.
        </p>
      </footer>
      <Dock address={config.ADDRESS} store={target("STORE_URL")} />
    </>
  );
}
