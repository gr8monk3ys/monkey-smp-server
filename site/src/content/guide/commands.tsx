import type { ReactNode } from "react";

// Commands by rank: /guide/commands lists the ranks, and each rank with an `id` has its own page,
// /guide/commands/<id> (pages.ts lists them). Each rank can do everything the ranks above it can.

/** A rank in the summary at the top; `id` links it to its own commands below. */
export const ranks: { name: string; id?: string; does: string }[] = [
  { name: "Player", id: "players", does: "Play, claim land, join a faction, use voice chat, open the menus below." },
  {
    name: "Faction leader", id: "leaders",
    does: "The owner of a faction's party: invites members and allies, declares war and makes pacts.",
  },
  { name: "Supporter", id: "supporters", does: "Ember, Banner or Crown: a name color, a title and skins. No commands of their own." },
  { name: "Builder", does: "A player staff trust with build jobs. An admin switches them to creative for a job and back after." },
  { name: "Moderator", id: "moderators", does: "Warns, mutes, kicks and bans; watches quietly; checks and undoes griefing." },
  { name: "Admin", id: "admins", does: "Everything: ranks, the whitelist, events, and the server's own commands." },
];

/** One row: a command (set in mono), a key, or a few words, and what it does. */
export type Command = ({ code: string } | { kbd: string } | { term: string }) & { does: ReactNode };

/** A group of rows under a heading; `note` comes between the heading and the rows, `text` stands instead of
 * rows. */
export type Group = { heading?: string; note?: ReactNode; text?: ReactNode; cmds?: Command[] };

export type Role = { id: string; intro: ReactNode; groups: Group[]; after?: ReactNode };

export const roles: Role[] = [
  {
    id: "players",
    intro: <>Menus open in chat; click a line to use it. Type the start of a command and press <kbd>Tab</kbd> to see
      the rest.</>,
    groups: [
      {
        heading: "Menus",
        cmds: [
          { code: "/trigger wardrobe", does: "Your skins: the ones you've unlocked, and how to unlock the rest." },
          { code: "/trigger challenges", does: "This week's three challenges and how far you've got. Hover one for what counts." },
          { code: "/trigger standings", does: "This week's faction standings so far." },
          { code: "/trigger diplomacy", does: "How your faction stands with every other: wars, pacts, offers." },
          { code: "/trigger outposts", does: "The four outposts: where, who holds them, and your faction's hours." },
          { code: "/trigger firsts", does: "The season's Server Firsts and who holds each." },
          { code: "/trigger end_grace", does: "Ends your 48 hours of safety now. There's no getting it back." },
        ],
      },
      {
        heading: "Factions and land",
        cmds: [
          { code: "/oparties create", does: "Starts a party: your faction. You're its leader." },
          { code: "/oparties join <leader>", does: "Joins the party that invited you, named by its leader." },
          { code: "/oclaims claim", does: <>Claims the chunk you&apos;re standing in. Or press <kbd>M</kbd> and right-click chunks.</> },
          {
            code: "/opac",
            does: <>Your party and claims settings. <code>/oclaims</code> and <code>/oparties</code> with <kbd>Tab</kbd> list
              everything else.</>,
          },
        ],
      },
      {
        heading: "Events",
        cmds: [
          {
            code: "/trigger arena set 1",
            does: "Joins Arena Glory while it's open: stand by the entrance, in survival, with an empty inventory, "
              + "armor and offhand.",
          },
          { code: "/trigger arena set 2", does: "Leaves the arena. You come out with what you went in with." },
        ],
      },
      {
        heading: "Keys",
        cmds: [
          { kbd: "V", does: "Voice chat settings." },
          { kbd: "M", does: "The world map, where you claim land." },
          {
            term: "Sneak + right-click",
            does: "With both hands empty: picks up a passive animal or a block like an enchanting table. Right-click "
              + "to put it down. Nothing that stores items, and nothing in someone else's claim.",
          },
        ],
      },
    ],
  },
  {
    id: "leaders",
    intro: "The player who made the party leads it. Everything players can do, plus:",
    groups: [{
      cmds: [
        { code: "/oparties member invite <player>", does: "Invites a player. Four is the most a faction can have." },
        { code: "/oparties ally add <leader>", does: "Makes another party an ally. Allies share claims." },
        {
          code: "/trigger diplomacy",
          does: "For a leader it has buttons: declare war, offer a pact, accept one, break one. One move every 2 "
            + "minutes. Wars and offers end at Sunday's close; pacts stand until broken.",
        },
      ],
    }],
  },
  {
    id: "supporters",
    intro: <>Nothing to type. Your name color shows by itself, and your skins appear in <code>/trigger wardrobe</code>{" "}
      with an &quot;Unlocked&quot; line in chat. Banner and Crown supporters tell staff the title they want, and staff
      set it.</>,
    groups: [],
  },
  {
    id: "moderators",
    intro: <>Typed in game, without the <code>/</code> where shown. Every punishment needs a reason, which the player
      sees and the next moderator can look up. Start the reason with <code>-s</code> to keep it out of public chat.
      Durations look like <code>30m</code>, <code>12h</code>, <code>3d</code> or <code>1d12h</code>.</>,
    groups: [
      {
        heading: "Punishments, in the rules' order",
        cmds: [
          { code: "/warn NAME reason", does: "Step 1. Five warnings ban a player for 5 hours by themselves." },
          { code: "/tempban NAME 3d reason", does: "Step 2: a ban of 1 to 7 days." },
          { code: "/ban NAME reason", does: "Step 3, or straight away for cheating, hate or doxxing." },
          {
            code: "/tempmute NAME 1h reason",
            does: <>No chat or private messages for a while. <code>/mute</code> is for good. Voice chat isn&apos;t
              covered: ask an admin.</>,
          },
          { code: "/kick NAME reason", does: "Out of the server, free to come back." },
          { code: "/unban NAME", does: <>Also <code>/unmute</code> and <code>/unwarn</code>.</> },
        ],
      },
      {
        heading: "Watching quietly",
        cmds: [
          { code: "/vanish", does: "Hides you from players, the tab list and the server list until you run it again." },
          {
            code: "/view inv NAME",
            does: <>Looks into a player&apos;s inventory; <code>/view echest NAME</code> their ender chest. Look only.</>,
          },
          {
            code: "/mtrack check NAME",
            does: <>A player&apos;s mining alerts. Lucky players set it off too, so look before you act.{" "}
              <code>/mtrack reset NAME</code> clears them.</>,
          },
        ],
      },
      {
        heading: "Griefing",
        cmds: [
          { code: "/ledger inspect", does: "Turns inspect on or off; then click a block to see who changed it." },
          { code: "/ledger search source:NAME range:30 after:2h", does: "What NAME did in the last 2 hours within 30 blocks." },
          {
            code: "/ledger rollback source:NAME range:30 after:2h",
            does: <>Undoes it. <code>/ledger restore</code> with the same words redoes it.</>,
          },
          {
            code: "/ledger tp minecraft:overworld X Y Z",
            does: <>Takes you to a spot (the Nether is <code>minecraft:the_nether</code>). Or click &quot;Click to
              teleport&quot; in Ledger&apos;s results.</>,
          },
        ],
      },
    ],
    after: "Moderators can't teleport to a player, move someone else, change game modes or whitelist anyone: those "
      + "need an admin.",
  },
  {
    id: "admins",
    intro: <>Every mod&apos;s commands, plus Minecraft&apos;s own (<code>/tp</code>, <code>/gamemode</code>,{" "}
      <code>/give</code>, <code>/whitelist</code> and the rest), which need op as well as the rank.</>,
    groups: [
      {
        heading: "People",
        cmds: [
          {
            code: "/lp user NAME parent set moderator",
            does: <>Makes NAME a moderator. <code>parent remove moderator</code> takes it back.</>,
          },
          { code: "/lp user NAME permission settemp voicechat.speak false 1d", does: "Mutes NAME's voice for a day." },
          { code: "/ban-ip", does: "Admins only: an address is often a whole household." },
          {
            code: "/gamemode creative NAME",
            does: <>Puts a builder in creative for a job; <code>/gamemode survival NAME</code> when it&apos;s done.</>,
          },
          { code: "/view inv NAME", does: "For an admin, items can be taken out too." },
        ],
      },
      {
        heading: "The season's systems",
        note: "Each one lists its own commands in chat, clickable.",
        cmds: [
          { code: "/function realms:events/help", does: "Events: the arena, Anarchy, the Faction Raid, flags, books and the Cup." },
          { code: "/function realms:standings/help", does: "The standings board and bounties." },
          { code: "/function realms:diplomacy/help", does: "Faction numbers, and ending a war or pact by hand." },
          { code: "/function realms:drops/help", does: "Supply drops: status, a drop now, on and off." },
          { code: "/function realms:omens/help", does: "Omens: status, start, stop, on and off." },
          { code: "/function realms:outposts/help", does: "Outposts: status, freeing one, on and off." },
        ],
      },
      {
        heading: "Building",
        cmds: [
          {
            code: "//wand",
            does: <>WorldEdit&apos;s selection wand; <code>{"//pos1"}</code> and <code>{"//pos2"}</code> set the corners,{" "}
              <code>{"//undo"}</code> takes a change back.</>,
          },
          {
            code: "/lp user NAME permission set worldedit.* true",
            does: <>Lends WorldEdit to a builder; <code>permission unset worldedit.*</code> takes it back.</>,
          },
        ],
      },
      {
        heading: "Testing a release",
        text: <>Try each release on your own test server first, never on the live world: the{" "}
          <a href="https://github.com/gr8monk3ys/monkey-smp-server/blob/main/docs/QA.md">staff test checklist</a>{" "}
          says how to set one up, what to try as a player and as an admin, and what you should see.</>,
      },
    ],
  },
];
