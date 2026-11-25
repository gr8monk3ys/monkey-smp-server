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
    text: "Outside spawn and claimed bases, PvP is on and a kill steals a heart. New players have 48 hours of PvP "
      + "grace. No combat logging.",
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

// The creator-code terms (creators page, #terms): what you earn leads across the top, the rest pair up.
export const terms: Tablet[] = [
  {
    title: "What you earn",
    text: "20% of every 2-month pass bought with your code: $1.60 of the $8. Tebex, our store, pays it into "
      + "your Tebex Wallet and holds each payment for 30 working days first, in case of refunds and chargebacks.",
  },
  {
    title: "Codes are for the 2-month pass",
    text: "Tebex pays a code's share only on the first payment of a subscription, and the first payment of a "
      + "monthly pass is $5. So send people to the 2-month pass, where your share is worth having.",
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
