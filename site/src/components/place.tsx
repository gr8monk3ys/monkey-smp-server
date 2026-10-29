"use client";

import { type ElementType, type ReactNode, useEffect, useRef } from "react";

/** A list whose blocks drop into place as they scroll into view, a few at a time (.unplaced and .placed in
 * style.css, a 240 ms steps(3) drop). Only the blocks below the fold at load move; the ones on screen are left
 * alone, and so is everything for visitors who asked for less motion. The page is rendered with every block in
 * place, so without JavaScript nothing waits, and printing shows them all. */
export function Place({ as: Tag = "div", className, children }:
  { as?: ElementType; className?: string; children: ReactNode }) {
  const ref = useRef<HTMLElement>(null);
  useEffect(() => {
    const list = ref.current;
    const calm = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
    if (!list || calm || !("IntersectionObserver" in window)) return;
    // Measure every block first, then hide: one layout, not one per block.
    const waiting = Array.from(list.children).filter((block) => block.getBoundingClientRect().top > window.innerHeight);
    waiting.forEach((block) => block.classList.add("unplaced"));
    const timers: number[] = [];
    const placer = new IntersectionObserver((entries) => {
      let n = 0;
      entries.forEach((entry) => {
        if (!entry.isIntersecting) return;
        const block = entry.target;
        placer.unobserve(block);
        timers.push(window.setTimeout(() => {
          block.classList.remove("unplaced");
          block.classList.add("placed");
        }, Math.min(n++ * 60, 300)));
      });
    }, { rootMargin: "0px 0px -8% 0px" });
    waiting.forEach((block) => placer.observe(block));
    const print = () => waiting.forEach((block) => block.classList.remove("unplaced"));
    window.addEventListener("beforeprint", print);
    return () => {
      placer.disconnect();
      timers.forEach(clearTimeout);
      window.removeEventListener("beforeprint", print);
      waiting.forEach((block) => block.classList.remove("unplaced", "placed"));
    };
  }, []);
  return <Tag ref={ref} className={className} data-place="">{children}</Tag>;
}
