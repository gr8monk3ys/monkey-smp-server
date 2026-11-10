import { type Pack, running, sayList } from "@/lib/live";

// The guide's pages, in reading order: the sidebar lists them under these headings, and each page links to the
// one before and after it. A page with a `pack` is about that data pack's feature: while the pack isn't running
// (site/live-packs.json) the page still builds, saying so, but the sidebar and the pager leave it out.

export type GuidePage = { href: string; title: string; description: string; pack?: Pack };

/** The words of `parts` whose pack runs (a part with no pack always does). */
function live(parts: [string, Pack?][]): string[] {
  return parts.filter(([, pack]) => !pack || running(pack)).map(([words]) => words);
}

const everySection: { title: string; pages: GuidePage[] }[] = [
  {
    title: "Start here",
    pages: [
      {
        href: "/guide", title: "Your first hour",
        description: `What happens when you join Monkey SMP: ${sayList(live([["the Guide at spawn", "monkey-npcs"],
          ["48 hours of safety", "monkey-rules"], ["voice chat"], ["launch night"]]))}.`,
      },
      {
        href: "/guide/factions", title: "Factions and land",
        description: running("monkey-standings")
          ? "Factions of up to four, claiming land, allies, war and pacts, and trading by hand."
          : "Factions of up to four, claiming land, allies, and trading by hand.",
      },
      {
        href: "/guide/rules", title: "The full rulebook",
        description: "Monkey SMP's Season I rulebook: every numbered rule and ban, how they're enforced, and appeals.",
      },
    ],
  },
  {
    title: "The season",
    pages: [
      {
        href: "/guide/week", title: "A week on the server",
        description: `The week's rhythm on Monkey SMP: ${sayList(live([["challenges", "monkey-wardrobe"],
          ["supply drops", "monkey-drops"], ["omens", "monkey-omens"], ["outposts", "monkey-outposts"],
          ["standings", "monkey-standings"], ["the Saturday event"]]))}.`,
      },
      {
        href: "/guide/standings", title: "Weekly standings", pack: "monkey-standings",
        description: running("monkey-standings")
          ? "Monkey SMP's weekly faction standings: this week's table, last week's final one, and how a "
            + "faction's points add up."
          : "Monkey SMP's weekly faction standings are not running on the server right now.",
      },
    ],
  },
  {
    title: "Commands",
    pages: [
      {
        href: "/guide/commands", title: "Ranks",
        description: "Every rank on Monkey SMP, from player to admin, and what each can do.",
      },
      // One page per rank in commands.tsx's `roles`, by id; the titles live here. commands/[rank]/page.tsx fails
      // the build when the two lists differ.
      ...[
        ["players", "Players"], ["leaders", "Faction leaders"], ["supporters", "Supporters"],
        ["moderators", "Moderators"], ["admins", "Admins"],
      ].map(([id, title]) => ({
        href: `/guide/commands/${id}`, title,
        description: `Every command ${title.toLowerCase()} can use on Monkey SMP, a Minecraft factions server, and what `
          + "each one does.",
      })),
    ],
  },
  {
    title: "Discord",
    pages: [
      {
        href: "/guide/discord", title: "Monkey SMP on Discord",
        description: "Where Monkey SMP lives on the Discord: its channels, chatting with the game, and the /smp "
          + "commands.",
      },
    ],
  },
];

/** Every page the guide builds, shown or not (the sitemap lists them all). */
export const allPages = everySection.flatMap((section) => section.pages);

/** The sidebar's sections: the pages whose pack runs. */
export const sections = everySection
  .map((section) => ({ ...section, pages: section.pages.filter((p) => !p.pack || running(p.pack)) }))
  .filter((section) => section.pages.length);

/** The pages the sidebar and the pager show, in reading order. */
export const pages = sections.flatMap((section) => section.pages);

/** The ids of the per-rank command pages (/guide/commands/<id>), in reading order. */
export const rankIds = allPages.flatMap((p) => p.href.match(/^\/guide\/commands\/([^/]+)$/)?.[1] ?? []);

export function guidePage(href: string): GuidePage {
  const found = allPages.find((p) => p.href === href);
  if (!found) throw new Error(`No guide page at ${href}`);
  return found;
}
