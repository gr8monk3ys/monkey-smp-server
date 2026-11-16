"use client";

import { track } from "@vercel/analytics";
import { useEffect } from "react";
import { storeOpen } from "@/lib/config";

/** Counts clicks on any store link (every one carries data-link="STORE_URL") as a Vercel Analytics event, so the
 * visits-to-checkout step of the funnel shows up next to page views. While the store is closed those links go to
 * the Discord instead, so nothing is counted. */
export function StoreClicks() {
  useEffect(() => {
    if (!storeOpen) return;
    const onClick = (event: MouseEvent) => {
      if (event.type === "auxclick" && event.button !== 1) return;
      if (event.target instanceof Element && event.target.closest('a[data-link="STORE_URL"]')) {
        track("Store click", { page: location.pathname });
      }
    };
    document.addEventListener("click", onClick);
    document.addEventListener("auxclick", onClick);
    return () => {
      document.removeEventListener("click", onClick);
      document.removeEventListener("auxclick", onClick);
    };
  }, []);
  return null;
}
