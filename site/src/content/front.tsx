import type { ReactNode } from "react";
import { ConfigLink } from "@/components/links";

// The front page's lists, as data: the page (src/app/page.tsx) lays them out.

/** The world (#world): what you get; where a feature has a hard number, the number leads it. */
export const features: { fig?: string; title: string; text: ReactNode }[] = [
  {
    fig: "Up to 4",
    title: "Factions, alliances, territory",
    text: <>Factions of up to four, each under its own banner. Your territory is 2 &times; 2 chunks a player and
      nobody may grief it; everything outside it is contested.</>,
  },
  {
    fig: "y 500",
    title: "Land worth fighting over",
    text: <>Tectonic and Terralith reshape the overworld and push its peaks past y&nbsp;500; Incendium remakes the
      Nether and Endercon the End. Dungeons, taverns and capitals are scattered across it.</>,
  },
  {
    fig: "3D",
    title: "A live map",
    text: <>BlueMap renders the world in 3D in your browser, so you can plan the next expedition before logging in.
      It is open to everyone: <ConfigLink to="MAP_URL">take a look</ConfigLink>.</>,
  },
  {
    fig: "20 TPS",
    title: "Runs smooth",
    text: "A fast dedicated CPU, a pre-generated world and tuned mob ticking keep it at 20 TPS for the crowd we "
      + "let in.",
  },
  {
    title: "Strength on the line",
    text: "Strength SMP is the centerpiece: win fights and your strength grows, lose them and it drains away. "
      + "Every fight has stakes.",
  },
  {
    title: "Talk in the world",
    text: "Proximity voice chat is built in. Negotiate at the border, or hear them coming.",
  },
];

/** The gallery (#gallery): img/<name>-800.webp and -1600.webp. The first is the big one, and loads first. */
export const shots: { name: string; where: string; alt: string; caption: ReactNode }[] = [
  {
    name: "mountains", where: "Overworld",
    alt: "A ridge of red, yellow and white painted stone rising above a sea of clouds",
    caption: <>The Painted Mountains, above the clouds. Tectonic and Terralith push peaks past y&nbsp;500.</>,
  },
  {
    name: "nether-castle", where: "The Nether",
    alt: "Blackstone towers with red roofs under falling lava, a piglin brute on the battlements",
    caption: "A Forbidden Castle in the Nether. It is guarded.",
  },
  {
    name: "end-citadel", where: "The End",
    alt: "A purpur citadel among spiked end-stone islands under a violet sky",
    caption: "The Phantom Citadel, out past the dragon's island.",
  },
  {
    name: "fortified-village", where: "Overworld",
    alt: "A walled village with a stone keep, built out over shallow water",
    caption: "A fortified village on the coast. Someone will claim it.",
  },
  {
    name: "floating-island", where: "Overworld",
    alt: "A cabin on a small floating island over the sea, snowy peaks behind",
    caption: "A cabin on a floating island, a long swim from anywhere.",
  },
  {
    name: "mage-tower", where: "Overworld",
    alt: "A tall stone mage tower with a green spire, standing in a shallow lake",
    caption: "A mage tower in the shallows.",
  },
];

/** The game the server runs: the page's description and its lede both name it. */
export const GAME = "Minecraft Java 26.3";

/** The pass's monthly price in US dollars: the price shown, the page's description and the launch event's offer
 * (src/lib/seo.ts) all come from it. */
const PASS_USD = 5;

/** The Server Pass (#pricing): one price to play, the same for everyone. */
export const pass = {
  name: "Server Pass",
  usd: PASS_USD,
  price: `$${PASS_USD}`,
  per: "/ month",
  alt: "or $14 for 3 months",
  needs: "Needs Minecraft Java Edition on a PC (Windows, macOS or Linux) with 16 GB of RAM. If the pack won't run "
    + "in your first 48 hours, you get your money back.",
  perks: [
    "Full access to the server and every mod",
    "A vote on each season's twist",
    "Proximity voice chat",
    "Member role, forum and events in the Discord",
  ],
};

/** Supporter tiers: cosmetic only. */
export const tiers: { name: string; price: string; perks: string }[] = [
  { name: "Ember", price: "$3 / mo", perks: "Chat name color, supporter tag in the Discord, the Lantern sword skin" },
  {
    name: "Banner", price: "$7 / mo",
    perks: "Ember, plus a title of your choice, your faction's banner in the spawn hall and the Standard sword skin",
  },
  {
    name: "Crown", price: "$15 / mo",
    perks: "Banner, plus the Crown helmet and Regalia sword skins, your name on the founders' wall and a landmark "
      + "you name in each season's world",
  },
];

/** What inviting friends earns (supporter time, never a discount). */
export const ladder: { friends: string; reward: string }[] = [
  { friends: "1 friend", reward: "one month of Ember and the Verdant sword skin" },
  { friends: "3 friends", reward: "one month of Banner, the Herald title and the Horned Helm skin" },
  { friends: "5 friends", reward: "one month of Crown" },
  { friends: "10 friends", reward: "Herald for good, and your name on the founders' wall" },
];

/** Questions (#faq). */
export const faq: { q: string; a: ReactNode }[] = [
  {
    q: "Why does it cost money?",
    a: "A modded server this size needs a fast dedicated CPU to stay smooth, and the pass keeps out players who "
      + "are only there to wreck things. The pass pays for the machine; anything above that goes back into it.",
  },
  {
    q: "Can I play on Bedrock, console or mobile?",
    a: "No. Monkey SMP is Java Edition with mods, so it needs a computer: Windows, macOS or Linux.",
  },
  {
    q: "How many players?",
    a: "Up to 30 online at once. When it fills up, we open a waitlist before we add anyone. Nobody can buy a way "
      + "in ahead of it: priority and reserved slots aren't for sale, to supporters or anyone else.",
  },
  {
    q: "Refunds?",
    a: "If you can't get the pack to run in your first 48 hours, ask in the Discord and you get your money back. "
      + "The monthly pass renews until you cancel it, and you can cancel any time; the 3-month pass doesn't renew.",
  },
  {
    q: "I'm under 18.",
    a: "Welcome. Ask a parent or guardian before buying anything. The server and the Discord are moderated "
      + "all-ages spaces.",
  },
  {
    q: "Can I make the pack lighter for a slower computer?",
    a: "Yes. Shaders, Distant Horizons, the resource packs and most of the visual and sound mods are optional. In "
      + "Prism Launcher, untick them when you install the pack; in the Modrinth App, switch them off in the "
      + "instance's Content tab. Start with Distant Horizons, which draws land far past your render distance. Keep "
      + "Sodium and the other speed mods on. The mods that add blocks, mobs and items can't be left out, and the "
      + "installer for the regular launcher always installs everything.",
  },
  {
    q: "How does trading work?",
    a: <>By hand, with items, not money: there&apos;s no currency, <code>/pay</code>, shop or auction house. Meet up,
      agree on the deal and swap. A trade that lies about what you get is a scam, and scammers give back what they
      took.</>,
  },
  {
    q: "What happens when the server updates?",
    a: "Updates are announced in the Discord, with a five-minute warning in chat, and the server is back in about "
      + "three minutes. When the mod list changes, the announcement says so: get the new pack from the modpack "
      + "link and import it again, or run the installer again.",
  },
];
