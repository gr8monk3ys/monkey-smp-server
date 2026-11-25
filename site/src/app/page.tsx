import type { Metadata } from "next";
import { Canopy, Footer } from "@/components/chrome";
import { Countdown, LaunchHold } from "@/components/countdown";
import { Item } from "@/components/item";
import { JsonLd } from "@/components/json-ld";
import { ConfigLink, LaunchTime, Store } from "@/components/links";
import { Place } from "@/components/place";
import { ServerStatus } from "@/components/status";
import { Plaque } from "@/components/plaque";
import { BEDROCK_ADDRESS, BEDROCK_PORT, cosmetics, faq, features, GAME, SEASON_WEEKS, shots } from "@/content/front";
import { rules } from "@/content/rules";
import { builtPhase, config, launchStage, sayLaunch } from "@/lib/config";
import { preloadMono } from "@/lib/fonts";
import { launchEvent, pageMetadata } from "@/lib/seo";

// Written for what people search: a free economy SMP, a lifesteal SMP, a Java and Bedrock server, a season SMP.
export const metadata: Metadata = pageMetadata({
  title: "Monkey SMP: a free economy lifesteal SMP for Java and Bedrock",
  description: sayLaunch("A free survival economy SMP with lifesteal PvP and short seasons. Shop, auction house, "
    + "steal hearts. Java and Bedrock, no mods. "
    + (builtPhase() === "live" ? "Season 1 is live." : "Season 1 opens {date}, {pacific}.")),
  path: "/",
});

export default function Home() {
  preloadMono(); // the addresses on the plaques and in the join steps
  const event = launchEvent();
  return (
    <>
      <Canopy here="home" />

      {event && <JsonLd data={event} />}
      <main id="main">
        <section className="hero">
          <img className="monkey" src="/img/monkey.svg" alt="" width={224} height={224} />
          <h1>Survive.<br />Trade.<br /><span className="steal">Steal hearts.</span></h1>
          <p className="lede">Monkey SMP is a free survival economy server with lifesteal PvP and short seasons. Get
            rich at the shop and the auction house, take hearts outside the safe zones, and be standing when the
            border closes in. Java and Bedrock, no mods.</p>
          <Countdown launchAt={config.LAUNCH_AT} stage={launchStage()}>
            Season 1: <LaunchTime template="{date}, {pacific} ({eastern})" />
          </Countdown>
          <div className="ways">
            <Plaque address={config.ADDRESS} label="Java address" />
            <div className="cta">
              <ConfigLink to="DISCORD_INVITE" className="button">Join the Discord</ConfigLink>
              <a className="button ghost" href="#join">How to join</a>
            </div>
          </div>
          <ul className="facts">
            <li>Free to play</li>
            <li>Java and Bedrock</li>
            <li>No mods needed</li>
          </ul>
          {config.STATUS_URL && <ServerStatus url={config.STATUS_URL} mapUrl={config.MAP_URL}
            launchAt={config.LAUNCH_AT} builtPhase={builtPhase()} />}
          <LaunchHold launchAt={config.LAUNCH_AT} />
        </section>

        <section id="world">
          <h2>How it plays</h2>
          <div className="features">
            {features.map((f) => (
              <article key={f.title}>
                <Item name={f.item} />
                <div>
                  {f.fig && <p className="fig" aria-hidden="true">{f.fig}</p>}
                  <h3>{f.title}</h3>
                  <p>{f.text}</p>
                </div>
              </article>
            ))}
          </div>
        </section>

        {shots.length > 0 && (
          <section id="gallery">
            <h2>Out there</h2>
            <p className="note">Screenshots from the server&apos;s own world.</p>
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
        )}

        <section id="join">
          <h2>How to join</h2>
          <p className="note">Free, no whitelist, no mods. The server opens on{" "}
            <LaunchTime template="{date} at {pacific}" />.</p>
          <Place as="ol" className="steps">
            <li>
              <h3>Java Edition</h3>
              <p>On PC, Mac or Linux: Multiplayer, Add Server, then <code>{config.ADDRESS}</code>. No port needed.
                The server runs {GAME}, and older versions can join too.</p>
            </li>
            <li>
              <h3>Bedrock Edition</h3>
              <p>On phone, tablet or Windows: Play, Servers, Add Server. Server address{" "}
                <code>{BEDROCK_ADDRESS}</code>, port <code>{BEDROCK_PORT}</code>. On Xbox, PlayStation and Switch you
                can&apos;t add a server directly, so{" "}
                <ConfigLink to="DISCORD_INVITE">ask in the Discord</ConfigLink> how to get in.</p>
            </li>
            <li>
              <h3>Say hi</h3>
              <p><ConfigLink to="DISCORD_INVITE">The Discord</ConfigLink> is optional, but it&apos;s where events,
                season dates and trades are announced first.</p>
            </li>
          </Place>
        </section>

        <section id="season" className="crown">
          <h2>Seasons</h2>
          <p className="note">Each season runs {SEASON_WEEKS} weeks on a fresh world. Everyone starts on the same day
            with nothing.</p>
          <Place as="ol" className="steps">
            <li>
              <h3>Launch day</h3>
              <p>Season 1 opens <LaunchTime template="{date} at {pacific} ({eastern})" />, with a launch-only
                cosmetic for everyone who plays that weekend.</p>
            </li>
            <li>
              <h3>Mid-season</h3>
              <p>Weekly events, the revival for players out of hearts, and the economy heating up.</p>
            </li>
            <li>
              <h3>The finale</h3>
              <p>The border shrinks, the boss rises, and the season ends in one last fight. Then the world resets and
                the next season starts.</p>
            </li>
          </Place>
        </section>

        <section id="store">
          <h2>The store</h2>
          <p className="note">Our promise: the store sells cosmetics only, and always will. Nothing in it helps you
            fight, earn, build or survive. No in-game money, hearts, gear, spawners, keys or queue skips, ever.
            Everything in the game is earned in the game.</p>
          <Place className="extras">
            {cosmetics.map((c) => <article key={c.name}><h3>{c.name}</h3><p>{c.text}</p></article>)}
          </Place>
          <Store when="soon">
            <p className="small">The store opens before Season 1. Prices and the full list come with it.</p>
          </Store>
          <p><ConfigLink to="STORE_URL" className="button ghost">Visit the store</ConfigLink></p>
          <p className="small">Making videos on the server? Pass a view count and you get a free Media rank;
            regular creators get a code with 10% off for viewers. <a href="/creators">The creator terms</a>.</p>
        </section>

        <section id="rules">
          <h2>Rules</h2>
          <p className="note">The short version for Season 1. <a href="/guide/rules">The full rulebook</a> has every
            rule; if a rule turns out unfun or unfair, it changes with player feedback.</p>
          <Place as="ol" className="rules">
            {rules.map((r) => <li key={r.title}><h3>{r.title}</h3><p>{r.text}</p></li>)}
          </Place>
          <p className="small">Enforcement goes warning, temporary ban, permanent ban. Cheating, duping, hate and
            doxxing can skip straight to a ban.</p>
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

        <section id="start" className="outro">
          <img className="monkey" src="/img/monkey.svg" alt="" width={160} height={160} loading="lazy" />
          <h2>See you in the jungle.</h2>
          <ul className="facts">
            <li>Free to play</li>
            <li>Java and Bedrock</li>
            <li>No mods needed</li>
          </ul>
          <div className="ways">
            <Plaque address={config.ADDRESS} first={false} label="Java address" />
            <div className="cta">
              <ConfigLink to="DISCORD_INVITE" className="button">Join the Discord</ConfigLink>
              <a className="button ghost" href="#join">How to join</a>
            </div>
          </div>
        </section>
      </main>

      <Footer here="home" />
    </>
  );
}
