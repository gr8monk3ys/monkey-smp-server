"use client";

import { type ReactNode, useSyncExternalStore } from "react";
import type { LaunchStage } from "@/lib/config";

const UNITS = ["day", "hour", "minute"];

// The clock the countdown reads: the time now, moved on every 15 seconds while a countdown is on the page. The
// page is built with no time at all (null), so the first render in the browser matches the built HTML.
let clock: number | null = null;
function subscribe(changed: () => void) {
  const timer = window.setInterval(() => {
    clock = Date.now();
    changed();
  }, 15000);
  return () => clearInterval(timer);
}
const now = () => (clock ??= Date.now());
const built = () => null;

/** The season launch: the page is built with the time in Pacific and Eastern (children); once the page runs,
 * this adds the visitor's own time and counts down the days, hours and minutes left, and once the launch has
 * passed says the season is live. A digit that changes drops into its block (the .drop animation in style.css,
 * off under reduced motion).
 *
 * Until the page's script runs, the built page holds the room the countdown will take (.pending, style.css), so
 * nothing below it jumps when it appears: the blocks and the visitor's own time before the launch, just the line
 * saying the server is open after it. `stage` is where the launch stood when the page was built; the small inline
 * script corrects that before the page is drawn (the launch has passed since, or LAUNCH_AT isn't a time), and lets
 * the room go if the page's script still hasn't run a few seconds after the page loaded. */
export function Countdown({ launchAt, stage, children }:
  { launchAt: string; stage: LaunchStage; children: ReactNode }) {
  const launch = new Date(launchAt).getTime();
  const time = useSyncExternalStore(subscribe, now, built);

  const running = time !== null && !isNaN(launch);
  const left = running ? launch - time : 0;
  const live = running && left <= 0;
  const minutes = Math.ceil(left / 60000);
  const counts = [Math.floor(minutes / 1440), Math.floor((minutes % 1440) / 60), minutes % 60];
  const yours = running && !live ? "Your time: " + new Date(launch).toLocaleString(undefined, {
    weekday: "long", month: "long", day: "numeric", hour: "numeric", minute: "2-digit", timeZoneName: "short",
  }) + "." : "";

  const held = { soon: "launch pending", live: "launch pending live", unset: "launch" }[stage];
  // A number in the script (NaN when LAUNCH_AT isn't a time); JSON.stringify keeps it a plain literal.
  const hold = `(function(d,l,n){if(!(l>0)){d.classList.remove("pending");return}d.classList.toggle("live",n>=l);`
    + `addEventListener("load",function(){setTimeout(function(){d.classList.remove("pending")},3000)})})`
    + `(document.currentScript.parentNode,${JSON.stringify(isNaN(launch) ? 0 : launch)},Date.now())`;

  return (
    // The inline script may change the class before React starts, so the first render's class can differ.
    <div className={running ? "launch" : held} suppressHydrationWarning>
      <p className="when">
        <span id="launch-label">{live ? "Season I is live" : "Season I launch"}</span>
        {" "}{children}
      </p>
      <p className="counter" id="counter" hidden={!running || live}>
        {UNITS.map((unit, i) => {
          const text = running ? String(counts[i]).padStart(2, "0") : "00";
          return (
            <span className="cell" key={unit}>
              {/* A new key for each new number remounts the digits, which runs the drop again. */}
              <b><i key={text} className={running ? "drop" : undefined}>{text}</i></b>{" "}
              <span className="unit">{unit + (counts[i] === 1 && running ? "" : "s")}</span>
            </span>
          );
        })}
      </p>
      <p id="countdown" hidden={!running}>
        {live ? "The server is open: copy the address below and join." : yours}
      </p>
      <script dangerouslySetInnerHTML={{ __html: hold }} />
    </div>
  );
}
