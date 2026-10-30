import type { Metadata } from "next";
import { Canopy, Footer } from "@/components/chrome";
import { Countdown } from "@/components/countdown";
import { JsonLd } from "@/components/json-ld";
import { ConfigLink, LaunchTime, Store } from "@/components/links";
import { Place } from "@/components/place";
import { ServerStatus } from "@/components/status";
import { Plaque } from "@/components/plaque";
import { Trailer } from "@/components/trailer";
import { faq, features, GAME, ladder, pass, shots, tiers } from "@/content/front";
import { rules } from "@/content/rules";
import { builtPhase, config, launchStage, sayLaunch } from "@/lib/config";
import { preloadMono } from "@/lib/fonts";
import { launchEvent, pageMetadata } from "@/lib/seo";

// Written for what people search: a Minecraft factions server, a Fabric SMP, a paid-whitelist server, a season SMP.
export const metadata: Metadata = pageMetadata({
  title: "Monkey SMP: a Minecraft factions SMP server on Fabric",
  description: sayLaunch(`A paid-whitelist Fabric SMP for ${GAME}: factions of four, territory, PvP, new dungeons `
    + `and magic. One pass, ${pass.price} a month, the same for everyone. Season I opens {date}, {pacific}.`),
  path: "/",
});

export default function Home() {
  preloadMono(); // the address on the plaque and in the join steps
  const event = launchEvent(pass);
  return (
    <>
      <Canopy home="#" label="Sections" items={[
        { label: "The world", href: "#world" },
        { label: "Gallery", href: "#gallery" },
        { label: "Join", href: "#join" },
        { label: "Pricing", href: "#pricing" },
        { label: "Rules", href: "#rules" },
        { label: "FAQ", href: "#faq" },
        { label: "Guide", href: "/guide" },
      ]} />

      {event && <JsonLd data={event} />}
      <main id="main">
        <section className="hero">
          <img className="monkey" src="/img/monkey.svg" alt="" width={224} height={224} />
          <h1>Claim land.<br />Make allies.<br />Keep what you can hold.</h1>
          <p className="lede">Monkey SMP is a modded factions server on {GAME} (Fabric) for a small crowd
            that plays evenings, Pacific time. Factions of four, alliances, banner-marked territory, PvP outside your
            walls, reworked terrain, new dungeons, mobs and magic.</p>
          <Countdown launchAt={config.LAUNCH_AT} stage={launchStage()}>
            <LaunchTime template="{date}, {pacific} ({eastern})" />
          </Countdown>
          <div className="ways">
            <Plaque address={config.ADDRESS} />
            <div className="cta">
              <ConfigLink to="STORE_URL" className="button">Get a pass</ConfigLink>
              <ConfigLink to="DISCORD_INVITE" className="button ghost">Join the Discord</ConfigLink>
            </div>
          </div>
          {config.STATUS_URL && <ServerStatus url={config.STATUS_URL} mapUrl={config.MAP_URL}
            launchAt={config.LAUNCH_AT} builtPhase={builtPhase()} />}
          <Trailer />
        </section>

        <section id="world">
          <h2>The world</h2>
          <div className="features">
            {features.map((f) => (
              <article key={f.title}>
                {f.fig && <p className="fig" aria-hidden="true">{f.fig}</p>}
                <h3>{f.title}</h3>
                <p>{f.text}</p>
              </article>
            ))}
          </div>
        </section>

        <section id="gallery">
          <h2>Out there</h2>
          <p className="note">Screenshots from the server&apos;s own world, taken with the shaders that ship in the
            pack.</p>
          <Place className="gallery">
            {shots.map((s, i) => (
              <figure key={s.name}>
                <div className="shot">
                  <span className="where">{s.where}</span>
                  <img src={`/img/${s.name}-${i ? 800 : 1600}.webp`}
                    srcSet={`/img/${s.name}-800.webp 800w, /img/${s.name}-1600.webp 1600w`}
                    sizes={i ? "(max-width: 760px) 100vw, 33vw" : "(max-width: 760px) 100vw, 66vw"}
                    width={1600} height={900} loading={i ? "lazy" : undefined} decoding="async" alt={s.alt} />
                </div>
                <figcaption>{s.caption}</figcaption>
              </figure>
            ))}
          </Place>
        </section>

        <section id="join">
          <h2>How to join</h2>
          <Place as="ol" className="steps">
            <li>
              <h3>Get a pass</h3>
              <Store when="open">
                <p><ConfigLink to="STORE_URL">Buy it</ConfigLink> with your Minecraft Java name. You&apos;re on the
                  whitelist within a minute or two, and you get the member role in the Discord.</p>
              </Store>
              <Store when="soon">
                <p>The store isn&apos;t open yet. Until it is, passes are arranged in{" "}
                  <ConfigLink to="DISCORD_INVITE">the Discord</ConfigLink>: ask there with your Minecraft Java name,
                  and staff add you to the whitelist by hand.</p>
              </Store>
            </li>
            <li>
              <h3>Install the modpack</h3>
              <p>The server adds blocks, mobs and items, so you need the pack (about 560 MB). In the Modrinth App or
                Prism Launcher, import <ConfigLink to="MODPACK_URL" download>the modpack</ConfigLink>. For the
                regular Minecraft Launcher on Windows, unzip <ConfigLink to="INSTALLER_URL" download>the
                installer</ConfigLink> and double-click <code>Install for Minecraft Launcher.bat</code>.</p>
            </li>
            <li>
              <h3>Connect</h3>
              <p>Multiplayer, Add Server, <code>{config.ADDRESS}</code>. No port needed. A computer with 16 GB of RAM
                and a mid-range graphics card runs it well; the installer sets the game&apos;s memory for you.</p>
            </li>
          </Place>
        </section>

        <section id="pricing" className="crown">
          <h2>Pricing</h2>
          <p className="note">One price to play, the same for everyone. Supporter tiers are cosmetic only: nothing
            that helps you fight, build faster or earn more. Everyone earns wardrobe skins for swords and helmets just
            by playing: days online, months on the pass, friends invited and the weekly challenges
            (<code>/trigger wardrobe</code> in game). Founder&apos;s Circlet is only for playing on Season I&apos;s
            launch weekend.</p>

          <Place className="plans">
            <article className="panel">
              <h3>{pass.name}</h3>
              <p className="price">{pass.price} <span>{pass.per}</span></p>
              <p className="alt">{pass.alt}</p>
              <p className="needs">{pass.needs}</p>
              <ul>
                {pass.perks.map((perk) => <li key={perk}>{perk}</li>)}
              </ul>
              <Store when="soon">
                <p className="small">Until the store opens, passes are arranged in the Discord and staff add you to
                  the whitelist by hand.</p>
              </Store>
              <ConfigLink to="STORE_URL" className="button">Get a pass</ConfigLink>
            </article>
            <article className="panel support">
              <h3>Supporter <span className="tag">optional</span></h3>
              <table className="tiers">
                <tbody>
                  {tiers.map((t) => (
                    <tr key={t.name}><th>{t.name} <span>{t.price}</span></th><td>{t.perks}</td></tr>
                  ))}
                </tbody>
              </table>
              <ConfigLink to="STORE_URL" className="button ghost">Support the server</ConfigLink>
            </article>
          </Place>

          <div className="extras">
            <article>
              <h3>Bring your friends</h3>
              <Store when="open">
                <p>When a friend buys a pass and names you at checkout, you earn supporter time:</p>
              </Store>
              <Store when="soon">
                <p>When a friend gets a pass and names you to staff, you earn supporter time:</p>
              </Store>
              <ul className="ladder">
                {ladder.map((step) => <li key={step.friends}><b>{step.friends}</b> {step.reward}</li>)}
              </ul>
              <p className="small">Your friends pay the same price as everyone else. Mojang&apos;s rules require one
                price for access, so invites earn perks rather than discounts.</p>
            </article>
            <article>
              <h3>Where the money goes</h3>
              <p>The server costs about $50 a month to run: the machine, backups off-site, and the fallback tunnel.
                Everything above that goes back into the server first: a reserve, faster hardware when it fills up,
                and events. Each month we post what came in and what it paid for in the Discord.</p>
              <p className="small">Streaming or making videos on the server? Read the <a href="/creators">creator
                code terms</a>.</p>
            </article>
          </div>
        </section>

        <section id="rules">
          <h2>Rules</h2>
          <p className="note">Season I, hosted by Diego and Lorenzo Scaturchio. The full rulebook, every numbered rule
            and ban, is pinned in the Discord; if a rule turns out unfun or unfair, it changes with player
            feedback.</p>
          <Place as="ol" className="rules">
            {rules.map((r) => <li key={r.title}><h3>{r.title}</h3><p>{r.text}</p></li>)}
          </Place>
          <p className="small">Enforcement goes warning, temporary ban, permanent ban. Cheating, hate and doxxing can
            skip straight to a ban. A ban doesn&apos;t refund time already paid for.</p>
        </section>

        <section id="faq">
          <h2>Questions</h2>
          <div className="faq">
            {faq.map((item) => (
              <details key={item.q}>
                <summary>{item.q}</summary>
                <p>{item.a}</p>
              </details>
            ))}
          </div>
        </section>

        <section id="kit">
          <h2>Spread the word</h2>
          <p className="note">The logo and banners, free to use when you post about the server: videos, server
            lists, your own Discord.</p>
          <Place className="kit">
            <figure>
              <img className="plate" src="/kit/logo-1392w.png" width={348} height={64} loading="lazy"
                alt="The Monkey SMP logo: a pixel-art monkey on a green tile beside the words MONKEY SMP" />
              <figcaption>Logo, for dark backgrounds. <a href="/kit/logo-1392w.png" download>Wide</a> &middot;{" "}
                <a href="/kit/logo-stacked-704w.png" download>Stacked</a> &middot;{" "}
                <a href="/kit/mark-512.png" download>Monkey only</a></figcaption>
            </figure>
            <figure>
              <img src="/kit/server-list-468x60.png" width={468} height={60} loading="lazy"
                alt="Monkey SMP server-list banner" />
              <figcaption>Server-list banner, 468 &times; 60. <a href="/kit/server-list-468x60.png"
                download>Download</a></figcaption>
            </figure>
            <figure>
              <div className="shot"><img className="wide" src="/kit/discord-banner-960x540.png" width={960}
                height={540} loading="lazy" alt="Monkey SMP Discord banner" /></div>
              <figcaption>Discord banner, 960 &times; 540. <a href="/kit/discord-banner-960x540.png"
                download>Download</a></figcaption>
            </figure>
          </Place>
        </section>
      </main>

      <Footer items={[
        { label: "Discord", to: "DISCORD_INVITE" },
        { label: "Rules", href: "#rules" },
        { label: "Live map", to: "MAP_URL" },
        { label: "How it works", href: "/guide" },
        { label: "Logo and banners", href: "#kit" },
        { label: "Creator codes", href: "/creators" },
        { label: "What changed", href: "/changes" },
      ]} />
    </>
  );
}
