# Tebex setup checklist (Lorenzo)

Steps to set up the relaunch store yourself. Claude doesn't sign in to Tebex, accept terms or set up payments. Each
package's exact price and commands are in [store-packages.md](store-packages.md); why they are what they are is in
[store.md](store.md). Tebex's screens move around; where a name here doesn't match, look for the nearest one.

## 1. Before you start (by mid-January)

- [ ] In Tebex, open **Webstore settings** and check the **store type**. It must be **Minecraft: Offline/Geyser** for
      Bedrock players to pay with their Bedrock name.
  - If it is: keep this webstore, so existing subscribers keep their packages.
  - If it isn't: create a new webstore of that type for the relaunch (the type can't be changed later). Plan the
    switch for Season I subscribers as store.md, "Season I buyers", describes.
- [ ] Download the payments export (Payments, Export) and keep it: it is the list of Season I buyers for the Supporter
      tag and any refunds.
- [ ] Pick the pass plugin. Recommended: **BattlePass by ResistanceCore** (free, on Modrinth). Install it on the
      beta server and check that its premium track opens with `battlepass.premium` and that its quests can give the XP
      in store.md. Only if it falls short, buy EcoBattlepass ($15.99, BuiltByBit).

## 2. Season I wind-down

- [ ] Before **23 Jan 2027**, stop new sales of the Server Pass and the 2-month pass (disable the packages).
- [ ] Cancel renewals on active Server Pass subscriptions so none renews after 23 Jan (Payments or Subscriptions,
      cancel at the end of the period).
- [ ] For anyone with paid days left after 23 Jan: give those days plus 30 as free Ember on the new server, for
      example `lp user <name> parent addtemp ember 45d accumulate` for 15 days left. No refunds needed.
- [ ] Old Ember, Banner and Crown packages ($3/$7/$15): if you keep this webstore, **don't delete them**. Hide them
      from the store and change their commands to the new ones in store-packages.md (the same group names: `ember`,
      `banner`, `crown`), so existing subscribers keep their price. Delete nothing that has active subscriptions.

## 3. Connect the new server

- [ ] On the relaunch server, with the Tebex plugin installed, run `/tebex secret <your secret key>` in the console.
      The key is under Webstore settings, Game servers. Never paste it in Discord, a ticket or the repo.
- [ ] If the server sits behind Velocity or another proxy, set `server: proxy: true` in `plugins/Tebex/config.yml`.
- [ ] Run `/tebex info` and check it names the right webstore.
- [ ] Run the LuckPerms setup once: `python tools/store.py luckperms` prints the commands (also at the end of
      store-packages.md). Paste them in the console or send them with `tools/rcon.py`.

## 4. Categories

Create these, in this order: **Ranks**, **Season pass**, **Bundles**, **Pets**, **Particle effects**, **Death
effects**, **Tags**.

## 5. Packages

For each package in store-packages.md:

- [ ] Name and price exactly as listed. Add a one-line description and an image; the description says what you see
      in game.
- [ ] **Payment type**: monthly ranks are **Both** (subscription every 1 month, or one-time with **Remove after 30
      days**). Lifetime ranks, upgrades, the pass, bundles and single cosmetics are **One-time**. The Season 1 Starter
      is one-time with **Remove after 30 days**.
- [ ] Commands: add each command under its timing (**Initial purchase**, **Renewal**, **Expiry**, and the same refund
      command under both **Refund** and **Chargeback**). Tick **Require the player to be online** on every command.
- [ ] Lifetime upgrades: set **Required packages** to the lower lifetime rank, so only owners can buy them.
- [ ] One-off cosmetics and bundles: allow **gifting** (the buyer types another player's name).
- [ ] Buy nothing to test with real money. Use Tebex's test or sandbox checkout if your plan has one, or a 100% coupon
      limited to your own account and deleted after, and check the command ran with `/tebex forcecheck` and
      `/lp user <name> info`.

## 6. Season pass

- [ ] Install the pass plugin (BattlePass, or the one you picked). Its premium permission is `battlepass.premium`,
      which the `pass_s1` group has; with another plugin, change `PASS_PERMISSION` in `tools/store.py` and re-run it.
- [ ] Enter the free and premium rewards from store-packages.md, "Season pass rewards", each as the command shown
      (with the plugin's player placeholder), and the XP sources: weekly challenge 100, day played 20, event attended
      50, 80 XP a tier.

## 7. Creator codes

- [ ] Turn on **Creator codes**. Share 20% of the first payment, with **10% off** for the customer.
- [ ] Each creator agrees to say on stream or in the video that they're paid (Mojang's rules require it).

## 8. Community goal

- [ ] Create a **Community goal** of $300 (or your number), repeating monthly, with no in-game command (Goal Night is
      run by hand as an event), and show its progress bar on the store's home page.

## 9. Store page

- [ ] Home page text, at the top: "Nothing you can buy here gives you an advantage. Everything is cosmetic." Then
      the rank table from store.md.
- [ ] Footer: "NOT AN OFFICIAL MINECRAFT PRODUCT. NOT APPROVED BY OR ASSOCIATED WITH MOJANG OR MICROSOFT." and a
      contact email (not a Discord link).
- [ ] A line for Bedrock players ("Buy with your Bedrock name. Wardrobe skins are Java only for now.") and one for
      parents ("Under 18? Ask a parent before you buy.").
- [ ] Make sure every price is visible without signing in, so players see it before they join.

## 10. Launch day (6 Feb)

- [ ] Enable the new packages, check the store loads, and watch the first purchases arrive in game (`/tebex info`,
      the console log).
- [ ] Give the `founder` and `s1_supporter` groups to Season I players from the export (`lp user <name> parent add
      founder`), or have the season workstream's script do it.
