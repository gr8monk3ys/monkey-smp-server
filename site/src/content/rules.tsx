import type { ReactNode } from "react";
import { LaunchTime } from "@/components/links";

// The front page's rules, one stone tablet each (#rules). Season 1 placeholders: the short form of the rules the
// relaunch plan sets out. The Season 1 rulebook (docs/RULES.md, being rewritten for the relaunch) replaces them, so
// change both together.
export type Tablet = { title: string; text: ReactNode };

export const rules: Tablet[] = [
  {
    title: "Season 1 launch",
    text: <>Launch: <LaunchTime template="{date} at {pacific} ({eastern})" />, everyone let in at once on a new
      world. Everyone starts with nothing.</>,
  },
  {
    title: "Hearts and PvP",
    text: "Outside spawn and claimed bases, PvP is on and a kill steals a heart. New players get 3 hours of "
      + "protection, counted in play time. No combat logging.",
  },
  {
    title: "Fair trades",
    text: "Give what you said you'd give. No lying about an item, an amount or a price, and no changing a deal once "
      + "it's agreed. Scammers give back what they took.",
  },
  {
    title: "No cheating",
    text: "No hacked clients, x-ray, duping or exploits, and no account sharing. Found a dupe or a bug? Report it to "
      + "staff; using one gets you banned.",
  },
  {
    title: "Real money stays out",
    text: "No buying or selling items, money, hearts or accounts for real money. The store sells cosmetics only.",
  },
  {
    title: "Respect people",
    text: "No slurs, hate, harassment or sharing anyone's personal information. Keep it all-ages, and no stream "
      + "sniping without permission.",
  },
];

// The creator terms (creators page, #terms): the Media rank leads across the top, the rest pair up.
export const terms: Tablet[] = [
  {
    title: "The Media rank, free",
    text: "Post a video or stream from Monkey SMP that passes one of the thresholds below and you get the Media rank "
      + "for 90 days: a Media tag in game and in the Discord, plus a supporter rank's cosmetics. Post another that "
      + "passes and the 90 days start again. It's cosmetic, like everything else here.",
  },
  {
    title: "The thresholds",
    text: "2,500 views on a YouTube video in its first 30 days, 25,000 views on a Short, TikTok or Reel, or an "
      + "average of 15 live viewers on a stream. It has to show the current season, with the server address on "
      + "screen or in the title or description.",
  },
  {
    title: "Creator codes",
    text: "Creators who make videos here regularly can also have a code. Buyers who enter it get 10% off, and you "
      + "get 20% of what they paid. Tebex, our store, pays it into your Tebex Wallet after holding each payment for "
      + "its settlement period, in case of refunds and chargebacks.",
  },
  {
    title: "Say that you're paid",
    text: "Whenever you show or mention your code, or post once you hold the Media rank, say that you get something "
      + "from the server: #ad in the title or post, or \"I have a code and a free rank on this server\" said out "
      + "loud, and the platform's own paid-promotion label where there is one. The FTC requires it in the US, and "
      + "Mojang's rules for servers ask for it too.",
  },
  {
    title: "Describe the server as it is",
    text: "Monkey SMP is free to play, and the store sells cosmetics only: nothing in it helps anyone fight, earn or "
      + "survive. Don't promise items, money, hearts or anything else the server doesn't sell.",
  },
  {
    title: "The rules still apply",
    text: "You play under the same rules as everyone else, recording or not. Many players are under 18: if "
      + "someone asks to stay off your stream or out of your video, keep them out.",
  },
  {
    title: "Either side can stop",
    text: "You can drop your code, and we can switch it or the rank off, at any time. Both are switched off at once "
      + "for breaking these terms. Shares already earned are paid out as Tebex pays them.",
  },
];
