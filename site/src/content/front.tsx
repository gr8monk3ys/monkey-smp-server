import type { ReactNode } from "react";
import type { ItemName } from "@/components/item";
import { ConfigLink } from "@/components/links";

// The front page's lists, as data: the page (src/app/page.tsx) lays them out. Season 1 relaunch copy, 6 Feb 2027
// (docs/relaunch/marketing/brand.md has the voice and the taglines).

/** The game the server runs (Paper). Older Java clients join through ViaVersion. */
export const GAME = "Minecraft Java 26.3";

/** The address Bedrock players type. Bedrock can't follow the SRV record Java uses (config.json's ADDRESS), so it
 * needs the A record that SRV points at, and Geyser's port. Placeholder until the Paper server is live. */
export const BEDROCK_ADDRESS = "play.monkeysmp.lscaturchio.xyz";
export const BEDROCK_PORT = 19132;

/** How long a season runs, in weeks. */
export const SEASON_WEEKS = "8 to 10";

/** How it plays (#world): what you get; where a feature has a hard number, the number leads it. */
export const features: { item: ItemName; fig?: string; title: string; text: ReactNode }[] = [
  {
    item: "coin",
    fig: "$0",
    title: "Start broke, get rich",
    text: <>Everyone starts Season 1 with nothing, on the same day. Mine, farm and grind, sell at the server shop,
      and undercut your rivals in the auction house.</>,
  },
  {
    item: "heart",
    fig: "1 kill, 1 heart",
    title: "Steal hearts",
    text: <>Outside the safe zones PvP is on, and a kill steals a heart. Lose them all and you sit out until the
      mid-season revival. Extra hearts are crafted or bought with in-game money, never real money.</>,
  },
  {
    item: "banner",
    fig: "48 h",
    title: "Safe zones and a grace period",
    text: <>Spawn and your claimed base are safe. New players get 48 hours of PvP grace to find their feet before
      anyone can take a heart.</>,
  },
  {
    item: "clock",
    fig: `${SEASON_WEEKS} wks`,
    title: "Seasons with an ending",
    text: <>The border shrinks, a boss rises and the season ends in a finale. Then the world resets and everyone
      starts fresh. Titles and cosmetics carry over; items and money don&apos;t.</>,
  },
  {
    item: "sword",
    title: "Weekly events",
    text: <>Something new to fight over every week, each event built to end in a fight worth clipping. The Season 1
      line-up is announced before launch.</>,
  },
  {
    item: "map",
    title: "Phone, console or PC",
    text: <>Java and Bedrock players share one world, and a live 3D map shows it in your browser
      (<ConfigLink to="MAP_URL">take a look</ConfigLink>). No mods, no modpack, no beefy PC: if Minecraft runs, you
      can play.</>,
  },
];

/** The gallery (#gallery): img/<name>-800.webp and -1600.webp. The first is the big one, and loads first. */
export const shots: { name: string; where: string; alt: string; caption: ReactNode }[] = [
  // Empty until Season 1's beta world has been shot (the old shots showed the modded world).
];

/** What the cosmetic store sells (#store). Prices come with the store itself, which isn't open yet. */
export const cosmetics: { name: string; text: string }[] = [
  { name: "Supporter ranks", text: "Monthly: a chat colour, tag, title and particles, plus a role in the Discord." },
  { name: "Season pass", text: "A cosmetic track you unlock by playing the season, on top of the free track." },
  { name: "One-offs", text: "Weapon and armour skins, kill effects, banners and emotes." },
];

/** Questions (#faq). */
export const faq: { q: string; a: ReactNode }[] = [
  {
    q: "Is it really free?",
    a: "Yes. Joining and playing cost nothing. The store only sells cosmetics: nothing in it helps you fight, earn, "
      + "build or survive, and you can't buy in-game money.",
  },
  {
    q: "Can I play on Bedrock, console or phone?",
    a: <>Yes. Bedrock players on phones, consoles and Windows join the same world as Java players: add a server with
      the address <code>{BEDROCK_ADDRESS}</code> and port <code>{BEDROCK_PORT}</code>. Consoles don&apos;t let you
      add a server directly, so <ConfigLink to="DISCORD_INVITE">ask in the Discord</ConfigLink> how to get in.</>,
  },
  {
    q: "Do I need mods? Which version?",
    a: `No mods. The server runs ${GAME}, and older Java versions can join too. You can keep your own `
      + "performance mods and shaders on Java if you like.",
  },
  {
    q: "What happens when I lose all my hearts?",
    a: "You become a spectator until the revival event in the middle of the season, then you're back in. Your "
      + "base and claim stay yours.",
  },
  {
    q: "What carries over between seasons?",
    a: "Your season titles and your cosmetics. Items, money, bases and hearts reset with the world.",
  },
  {
    q: "I played Season I on the modded server.",
    a: <>Thank you. Every Season I player gets a Founder cosmetic on the new server and an invite to the closed beta
      in late January. Watch <ConfigLink to="DISCORD_INVITE">the Discord</ConfigLink> for it.</>,
  },
  {
    q: "I'm under 18.",
    a: "Welcome. Ask a parent or guardian before buying anything in the store. The server and the Discord are "
      + "moderated all-ages spaces.",
  },
  {
    q: "How do I bring friends?",
    a: "Send them the address. Once the store is open, a friend who names you and plays for three days earns you "
      + "both a cosmetic; the details come with the store.",
  },
];
