// What search engines and link previews read from each page: its title, description, canonical address and
// preview card, and the structured data (JSON-LD) that says what the site, the server and Season I's launch are.
import type { Metadata } from "next";
import { config, launchStage, launchWords, SITE_URL, storeOpen } from "@/lib/config";

export const SITE_NAME = "Monkey SMP";

/** A page's full address from its path on the site: "/" is the front page, "/guide" the guide. */
export const siteUrl = (path: string) => `${SITE_URL}${path}`;

/** The link-preview image: the logo over a Nether castle, 1200 x 630. */
export const OG_IMAGE = {
  url: "/img/og.jpg", width: 1200, height: 630,
  alt: "The Monkey SMP logo over a Nether castle: Claim land. Make allies. Keep what you can hold.",
};

/** A page's metadata: `title` is the whole title (the layout adds nothing to it), `path` its address on the site
 * ("/guide"), which becomes its canonical URL and the address its preview card links to. */
export function pageMetadata({ title, description, path }:
  { title: string; description: string; path: string }): Metadata {
  return {
    title: { absolute: title },
    description,
    alternates: { canonical: path },
    openGraph: {
      title, description, url: path, siteName: SITE_NAME, type: "website", locale: "en_US", images: [OG_IMAGE],
    },
    twitter: { card: "summary_large_image", title, description, images: [OG_IMAGE] },
  };
}

/** An ISO 8601 time in Pacific time with its offset ('2026-11-07T17:00:00-08:00'): how a search engine shows an
 * event at the time the server keeps, rather than in UTC. */
export function pacificIso(when: Date): string {
  const parts = Object.fromEntries(new Intl.DateTimeFormat("en-US", {
    timeZone: "America/Los_Angeles", year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit",
    minute: "2-digit", second: "2-digit", hourCycle: "h23", timeZoneName: "longOffset",
  }).formatToParts(when).map((p) => [p.type, p.value]));
  const offset = parts.timeZoneName === "GMT" ? "+00:00" : parts.timeZoneName.replace("GMT", "");
  return `${parts.year}-${parts.month}-${parts.day}T${parts.hour}:${parts.minute}:${parts.second}${offset}`;
}

const ORG_ID = siteUrl("/#organization");
const SITE_ID = siteUrl("/#website");

/** Who runs the site and what it is: on every page. */
export function siteGraph() {
  return {
    "@context": "https://schema.org",
    "@graph": [
      {
        "@type": "Organization", "@id": ORG_ID, name: SITE_NAME, url: siteUrl("/"),
        logo: { "@type": "ImageObject", url: siteUrl("/kit/mark-512.png"), width: 512, height: 512 },
        ...(config.DISCORD_INVITE && { sameAs: [config.DISCORD_INVITE] }),
      },
      {
        "@type": "WebSite", "@id": SITE_ID, name: SITE_NAME, url: siteUrl("/"), inLanguage: "en",
        publisher: { "@id": ORG_ID },
      },
    ],
  };
}

/** How long the launch event lasts in the structured data: the first evening on the new world. */
const LAUNCH_HOURS = 4;

/** Season I's launch as an online event, at config.json's LAUNCH_AT, with the pass (src/content/front.tsx) as its
 * offer. A build from the launch on (or with no launch time) leaves the event out: it is no longer to come. */
export function launchEvent(pass: { name: string; usd: number }, built: Date = new Date()) {
  if (launchStage(built) !== "soon") return null;
  const when = new Date(config.LAUNCH_AT);
  const words = launchWords(when);
  return {
    "@context": "https://schema.org",
    "@type": "Event",
    name: "Monkey SMP Season I launch",
    description: `Season I of Monkey SMP, a modded Minecraft Java factions server, opens ${words.date} at `
      + `${words.pacific} (${words.eastern}), with everyone let in at once on a new world.`,
    startDate: pacificIso(when),
    endDate: pacificIso(new Date(when.getTime() + LAUNCH_HOURS * 3600_000)),
    eventStatus: "https://schema.org/EventScheduled",
    eventAttendanceMode: "https://schema.org/OnlineEventAttendanceMode",
    location: { "@type": "VirtualLocation", url: siteUrl("/") },
    image: [siteUrl(OG_IMAGE.url)],
    organizer: { "@type": "Organization", "@id": ORG_ID, name: SITE_NAME, url: siteUrl("/") },
    offers: {
      "@type": "Offer", name: `${pass.name} (one month)`, price: pass.usd.toFixed(2), priceCurrency: "USD",
      // Until the store opens, passes are arranged in the Discord: the offer is the pricing section, to order ahead.
      url: config.STORE_URL || siteUrl("/#pricing"),
      availability: storeOpen ? "https://schema.org/InStock" : "https://schema.org/PreOrder",
    },
  };
}

/** The guide's trail, home > guide > this page, for a guide page's search result. */
export function guideTrail(title: string, path: string) {
  const items = [{ name: SITE_NAME, path: "/" }, { name: "Player guide", path: "/guide" }];
  if (path !== "/guide") items.push({ name: title, path });
  return {
    "@context": "https://schema.org",
    "@type": "BreadcrumbList",
    itemListElement: items.map((item, i) => ({
      "@type": "ListItem", position: i + 1, name: item.name, item: siteUrl(item.path),
    })),
  };
}
