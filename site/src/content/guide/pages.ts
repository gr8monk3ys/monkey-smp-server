// The guide's pages, in reading order: the sidebar lists them under these headings, and each page links to the
// one before and after it.

export type GuidePage = { href: string; title: string; description: string };

export const sections: { title: string; pages: GuidePage[] }[] = [
  {
    title: "Start here",
    pages: [
      {
        href: "/guide", title: "Your first hour",
        description: "What happens when you join Monkey SMP: the Guide at spawn, 48 hours of safety, voice chat and "
          + "launch night.",
      },
      {
        href: "/guide/factions", title: "Factions and land",
        description: "Factions of up to four, claiming land, allies, war and pacts, and trading by hand.",
      },
    ],
  },
  {
    title: "The season",
    pages: [
      {
        href: "/guide/week", title: "A week on the server",
        description: "The week's rhythm on Monkey SMP: challenges, supply drops, omens, outposts, standings and the "
          + "Saturday event.",
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

export const pages = sections.flatMap((section) => section.pages);

/** The ids of the per-rank command pages (/guide/commands/<id>), in reading order. */
export const rankIds = pages.flatMap((p) => p.href.match(/^\/guide\/commands\/([^/]+)$/)?.[1] ?? []);

export function guidePage(href: string): GuidePage {
  const found = pages.find((p) => p.href === href);
  if (!found) throw new Error(`No guide page at ${href}`);
  return found;
}
