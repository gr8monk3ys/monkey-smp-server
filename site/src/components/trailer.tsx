"use client";

import { useEffect, useRef } from "react";

/** The trailer plays muted while it's on screen, unless the visitor asked for less motion or less data. A pause
 * the visitor made sticks. */
export function Trailer() {
  const ref = useRef<HTMLVideoElement>(null);
  useEffect(() => {
    const trailer = ref.current;
    const calm = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
    const saveData = (navigator as Navigator & { connection?: { saveData?: boolean } }).connection?.saveData;
    if (!trailer || calm || saveData || !("IntersectionObserver" in window)) return;
    // The pause event fires after pause() returns, so the flag for our own pause is cleared there.
    let userPaused = false;
    let autoPause = false;
    const paused = () => {
      if (autoPause) autoPause = false;
      else userPaused = true;
    };
    trailer.addEventListener("pause", paused);
    const watch = new IntersectionObserver((entries) => {
      const on = entries[0].isIntersecting;
      if (on && trailer.paused && !userPaused) {
        trailer.play().catch(() => {});
      } else if (!on && !trailer.paused) {
        autoPause = true;
        trailer.pause();
      }
    }, { threshold: 0.5 });
    watch.observe(trailer);
    return () => {
      watch.disconnect();
      trailer.removeEventListener("pause", paused);
    };
  }, []);
  return (
    <figure className="trailer">
      <div className="shot">
        <video id="trailer" ref={ref} controls muted loop playsInline preload="none" width={1280} height={720}
          poster="/media/trailer-poster.webp" aria-label="Monkey SMP trailer">
          <source src="/media/trailer-720p.mp4" type="video/mp4" />
        </video>
      </div>
      <figcaption>The trailer, one minute. The event scenes are staged on a test server with stand-in players. It
        plays muted: turn the sound on in the player.</figcaption>
    </figure>
  );
}
