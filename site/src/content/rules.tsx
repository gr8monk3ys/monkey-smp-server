import type { ReactNode } from "react";
import { LaunchTime } from "@/components/links";

// The front page's rules, one stone tablet each (#rules). The full rulebook is docs/RULES.md, pinned in the
// Discord; this is its short form, so change both together.
export type Tablet = { title: string; text: ReactNode };

export const rules: Tablet[] = [
  {
    title: "Season I launch",
    text: <>Launch: <LaunchTime template="{date} at {pacific} ({eastern})" />, everyone let in at once. For the first
      hour, PvP, the Nether and the End are closed; then PvP and only the Nether open, and the End opens when we
      announce it. No Netherite armor until we say so: the smithing table won&apos;t make it, and armor you find
      comes off at your feet (Netherite tools and weapons are fine). The world border is 2500 &times; 2500 around
      spawn and grows as the server does.</>,
  },
  {
    title: "Factions and territory",
    text: <>Factions of up to four, public, each with a banner. Alliances yes, confederations no. Your territory is
      2 &times; 2 chunks a player, marked with your banner, or the inside of your base or walls at least 3 blocks
      tall. Nobody griefs, robs or farms a territory; everything outside one is fair game. Every base needs one
      feature visible from the surface.</>,
  },
  {
    title: "Spawn is sacred",
    text: "Nobody tampers with spawn or the admin building, and no TNT traps there.",
  },
  {
    title: "Fight fair",
    text: "You're in combat once someone hits you. No combat logging, no killing naked or AFK players, no "
      + "restocking mid-fight, and no rejoining a team fight for 10 minutes after you die. Land elytra 50 blocks "
      + "out, no elytra or lava in combat, no Happy Ghast PvP, and stay within about 30 blocks of shore.",
  },
  {
    title: "Strength",
    text: "Craft Strength only up to +3. Use Strength you're given right away unless you're at +5, and don't "
      + "ender-chest it below +5. No Strength on arrows or on other players.",
  },
  {
    title: "Banned",
    text: "Enchanted maces, ender pearls and enchanted golden apples (crafting only), totems, crystal PvP, bed "
      + "bombing, TNT minecarts, escape tunnels, and debuffs on others, except Slowness I, Weakness I, Poison I, "
      + "Instant Harming I and Turtle Master from a bow or crossbow. Fire Aspect and Flame are switched off on "
      + "the server.",
  },
  {
    title: "No cheating",
    text: "No hacked clients, x-ray of any kind (including the cushion glitch, F3+A and reloading shaders), "
      + "duping, health indicators, CIT packs, or Replay Mod and Flashback for an edge. No exploits, no "
      + "loopholes, no account sharing. Not sure? Ask an admin first.",
  },
  {
    title: "Fair trades",
    text: "Trade by hand, items for items: there's no money on the server. Give what you said you'd give: no "
      + "lying about the item, the amount or the price, no changing a deal once it's agreed, no renamed fakes. "
      + "Scammers give back what they took.",
  },
  {
    title: "Bedrock",
    text: "A netherite pickaxe breaks bedrock. No holes into the void, no breaking the End's exit portal or "
      + "gateways, and nothing on top of the Nether roof.",
  },
  {
    title: "Respect people",
    text: "No slurs, hate, harassment or sharing anyone's personal information. Keep it all-ages, no stream "
      + "sniping without permission, and no buying or selling anything for real money.",
  },
];

// The creator-code terms (creators page, #terms): what you earn leads across the top, the rest pair up.
export const terms: Tablet[] = [
  {
    title: "What you earn",
    text: "20% of every 3-month pass bought with your code: $2.80 of the $14. Tebex, our store, pays it into "
      + "your Tebex Wallet and holds each payment for 30 working days first, in case of refunds and chargebacks.",
  },
  {
    title: "Codes are for the 3-month pass",
    text: "Tebex pays a code's share only on the first payment of a subscription, and the first payment of a "
      + "monthly pass is $5. So send people to the 3-month pass, where your share is worth having.",
  },
  {
    title: "No discount for buyers",
    text: "Mojang's rules for paid servers say access costs the same for everyone, so a code takes nothing off "
      + "the price. It only tells us who sent the buyer.",
  },
  {
    title: "Say that you're paid",
    text: "Whenever you show or mention your code, say that you earn from it: #ad in the title or post, or \"I "
      + "get a share of passes bought with my code\" said out loud, and the platform's own paid-promotion label "
      + "where there is one. The FTC requires it in the US, and Mojang's rules for servers ask for it too.",
  },
  {
    title: "Describe the server as it is",
    text: "A pass buys access, supporter tiers buy looks, and nothing buys an advantage. Don't promise items, "
      + "ranks, slots or anything else the server doesn't sell.",
  },
  {
    title: "The rules still apply",
    text: "You play under the same rules as everyone else, recording or not. Many players are under 18: if "
      + "someone asks to stay off your stream or out of your video, keep them out.",
  },
  {
    title: "Either side can stop",
    text: "You can drop your code, and we can switch it off, at any time. A code is switched off at once for "
      + "breaking these terms. Shares already earned are paid out as Tebex pays them.",
  },
];
