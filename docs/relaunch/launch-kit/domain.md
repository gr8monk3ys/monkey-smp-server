# Domain: what to buy

Checked 25 Nov 2026, about 06:05 to 06:35 UTC. Nothing bought. Prices move, so check the total at checkout.

## Pick: `playmonkeysmp.com` at Cloudflare Registrar, $10.46 a year

- **Why this name:** `monkeysmp.net` and `monkeysmp.com` are both taken (the .net since April 2025; the .com since
  April 2026, parked on an aftermarket, so it would cost a resale price). `@monkeysmp` is also taken on TikTok,
  YouTube and Twitch, so the brand's fallback applies: **playmonkeysmp** everywhere, domain and handles alike, so a
  viewer who finds one finds the rest. "Play" also reads as an instruction on an end card.
- **Why Cloudflare:** cheapest for a .com, and the price never goes up at renewal ($10.46 first year and every year;
  at-cost, no markup). WHOIS details are redacted for free. Free email forwarding, so `hello@playmonkeysmp.com` can
  forward to Lorenzo's inbox and be used for the social sign-ups. Needs a free Cloudflare account, and the domain's
  DNS stays on Cloudflare (set the Minecraft records to "DNS only", grey cloud, not proxied).
- **Fallback:** Porkbun, $11.81 a year flat, fees included, free WHOIS privacy, any DNS host.
- **Checkout:** https://dash.cloudflare.com, Domain Registration, Register Domains. Total: **$10.46** for one year,
  plus any sales tax Cloudflare adds for the billing address.

## Everything checked

| Domain | Status | Cloudflare (1st yr / renew) | Porkbun | Namecheap |
| --- | --- | --- | --- | --- |
| monkeysmp.net | Taken | | | |
| monkeysmp.com | Taken, parked for resale | | | |
| **playmonkeysmp.com** | **Available** | **$10.46 / $10.46** | $11.81 / $11.81 | $12.08 / $19.98 |
| joinmonkeysmp.com | Available | $10.46 / $10.46 | $11.81 / $11.81 | $12.08 / $19.98 |
| monkeysmp.org | Available | $8.50 / $11.20 | $7.98 sale / $11.84 | $8.48 / $18.98 |
| monkeysmp.co | Available | $30.00 / $30.00 | $15.76 sale / $31.20 | $5.98 / $45.48 |
| monkeysmp.gg | Available | not sold | $51.80 / $51.80 | $68.98 / $82.98 |

Sources: Verisign and PIR RDAP for the .com, .net and .org status; Vercel's domain check for the rest; Porkbun's
public price list; cfdomainpricing.com (Cloudflare at-cost list, dated 24 Nov); domainoffer.net for Namecheap (the
Namecheap site itself stopped at a bot check). Namecheap adds a $0.20 ICANN fee.

`.org` is a cheap defensive extra that could redirect to the .com. Skip `.gg`: five times the price for no gain.

## After buying (platform thread or Lorenzo)

- Java address becomes `playmonkeysmp.com` (an SRV or A record to the server), Bedrock the same host on port 19132.
  Keep the `lscaturchio.xyz` names pointing at the server too, so nothing that already printed them breaks.
- Site: add the domain to the site's host and update `site/config.json` (brand thread's file).
- Re-render the kit with the new address: `MONKEY_JAVA=playmonkeysmp.com MONKEY_BEDROCK=playmonkeysmp.com` before
  `kit.py` and `teaser.py` (see README.md).
