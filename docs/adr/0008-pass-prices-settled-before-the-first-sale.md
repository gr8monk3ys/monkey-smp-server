---
status: accepted
---
# Pass prices and perks are settled before the first sale

> The 3-month pass below was replaced by a 2-month pass on 2026-11-04: see "Changed on 2026-11-04".

Access to the server is a server pass: $5 a month (a Tebex subscription) or $14 for 3 months (a one-off
package that Tebex removes after 90 days). Supporter tiers (Ember, Banner, Crown at $3, $7 and $15 a month)
buy cosmetics only. Crown's extra is a landmark the player names in each season's world, not a vote: every
pass holder votes on the season's twist. Nothing sold gives an advantage or a place in line, so there are no
priority or reserved slots and the waitlist is first come, first served. Creator codes pay the creator 20% of
the price and give the buyer no discount. The monthly pass gets a 7-day free trial once a test purchase shows
the whitelist runs when the trial starts; until then, open-house evenings stand in for it.

These are fixed now because two things make changing them later costly. Tebex can't change the price of a
subscription already sold, so a price raised after launch leaves early buyers on the old one for as long as
they renew, and a price lowered can't reach them at all. And Mojang's Usage Guidelines allow charging for
access only at one price for everyone, with anything else sold being cosmetic: a vote for Crown buyers, a
priority slot or a code that takes money off would each sell something non-cosmetic or a second price.

The 3-month pass went from $12 to $14. After Tebex's fees (5%, plus about 2.49% and $0.30 for the card),
$12 (20% off three monthly passes) kept $3.60 a month against the monthly pass's $4.33, pulling buyers off
the monthly pass without paying for itself. $14 keeps $4.22 a month, close enough to the monthly pass to read as the same
price for the same access, and break-even (about $50 a month, docs/RETENTION.md) stays at about 12
payers whichever pass they choose.

## Considered Options

- Keep $12 for 3 months: cheaper for the committed players, but 12 payers on it fall short of the server's
  cost, and the official server list reads Mojang's rule as payment options "equal in value, or close to" each
  other.
- A season vote as a Crown perk: what top servers do, but it sells a say in the rules for money.
- Priority queue slots for supporters: the most common perk on full servers, and the clearest breach of the
  one-price rule, since it sells a better kind of access.
- Creator codes with a 5-10% buyer discount: the usual setup, but a second price for the same access.
- Per-person coupons as a trial (a free first week for named players): not open to everyone, so a second
  price.

## Changed on 2026-11-04

Before the store opened, the owner replaced the 3-month pass with a 2-month pass at $8, a one-off package that Tebex
removes after 60 days and that adds `rw.months 2`. No 3-month pass had been sold. After fees it keeps about $7.10, or
$3.55 a month against the monthly pass's $4.33, so break-even is about 15 payers on it instead of 12. It is 20% off two
monthly passes, the same discount turned down above at $12. And it ends before a 12-week season does: one bought on
launch day ends on 6 January 2027, before the 23 January finale.

## Changed on 2026-11-07

On launch day the owner made the 2-month pass renew: it is now a Tebex subscription at $8 every 2 months, and each
renewal adds `rw.months 2`. Passes bought before the change stay one-off and end after 60 days. Like the monthly pass,
its price can no longer change for subscriptions already sold.
