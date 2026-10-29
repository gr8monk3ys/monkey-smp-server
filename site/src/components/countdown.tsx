"use client";

import { type ReactNode, useSyncExternalStore } from "react";

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
 * off under reduced motion). */
export function Countdown({ launchAt, children }: { launchAt: string; children: ReactNode }) {
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

  return (
    <div className="launch">
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
    </div>
  );
}
