---
name: Monkey SMP
description: The public site for a small, paid, modded Minecraft Java factions server, drawn as a pixel jungle canopy.
colors:
  shade: "#0e3122"
  ground: "#133f2b"
  leaf: "#184e35"
  leaf-2: "#1f6142"
  leaf-3: "#2b7a4b"
  bone: "#f9f8f5"
  bone-2: "#e2dcce"
  sage: "#b3dcbf"
  gold: "#e8b23a"
  gold-hi: "#f3cb6b"
  gold-bevel: "#c98f1f"
  ink: "#1a1f23"
  ink-2: "#2e3530"
  stone: "#b6bcad"
  stone-hi: "#c9cec1"
  stone-bevel: "#959b8e"
typography:
  display:
    fontFamily: "Pixelify Sans Monkey, sans-serif"
    fontSize: "clamp(2.5rem, 5vw, 4.5rem)"
    fontWeight: 700
    lineHeight: 1.04
  headline:
    fontFamily: "Pixelify Sans Monkey, sans-serif"
    fontSize: "clamp(2.1rem, 4.2vw, 3.4rem)"
    fontWeight: 700
    lineHeight: 1.04
  title:
    fontFamily: "Pixelify Sans Monkey, sans-serif"
    fontSize: "1.3rem"
    fontWeight: 700
    lineHeight: 1.2
  numeral-price:
    fontFamily: "Pixelify Sans Monkey, sans-serif"
    fontSize: "clamp(3.5rem, 7vw, 5rem)"
    fontWeight: 700
    lineHeight: 1
  numeral-counter:
    fontFamily: "Pixelify Sans Monkey, sans-serif"
    fontSize: "2.75rem"
    fontWeight: 700
    lineHeight: 1
    fontFeature: "tnum"
  numeral-figure:
    fontFamily: "Pixelify Sans Monkey, sans-serif"
    fontSize: "2.25rem"
    fontWeight: 700
    lineHeight: 1
  lede:
    fontFamily: "Atkinson Hyperlegible Next, sans-serif"
    fontSize: "1.2rem"
    fontWeight: 400
    lineHeight: 1.6
  body:
    fontFamily: "Atkinson Hyperlegible Next, sans-serif"
    fontSize: "1.0625rem"
    fontWeight: 400
    lineHeight: 1.6
  small:
    fontFamily: "Atkinson Hyperlegible Next, sans-serif"
    fontSize: "0.95rem"
    fontWeight: 400
    lineHeight: 1.6
  label:
    fontFamily: "Atkinson Hyperlegible Next, sans-serif"
    fontSize: "0.8125rem"
    fontWeight: 700
    lineHeight: 1.5
  button:
    fontFamily: "Atkinson Hyperlegible Next, sans-serif"
    fontSize: "1.0625rem"
    fontWeight: 700
    lineHeight: 1.1
  mono:
    fontFamily: "Atkinson Hyperlegible Mono, monospace"
    fontSize: "0.94em"
    fontWeight: 500
    lineHeight: 1.3
rounded:
  square: "0px"
spacing:
  frame: "6px"
  tight: "14px"
  tablet-gap: "20px"
  block: "40px"
  column: "64px"
  section-mobile: "72px"
  section: "112px"
  gutter-min: "16px"
  measure: "32em"
  wide: "76rem"
components:
  button-primary:
    backgroundColor: "{colors.gold}"
    textColor: "{colors.ink}"
    typography: "{typography.button}"
    rounded: "{rounded.square}"
    padding: "0 18px"
    height: "56px"
  button-primary-hover:
    backgroundColor: "{colors.gold-hi}"
    textColor: "{colors.ink}"
  button-ghost:
    backgroundColor: "transparent"
    textColor: "{colors.bone}"
    typography: "{typography.button}"
    rounded: "{rounded.square}"
    padding: "0 18px"
    height: "56px"
  button-ghost-hover:
    backgroundColor: "{colors.leaf-2}"
    textColor: "{colors.bone}"
  address-plaque:
    backgroundColor: "{colors.stone}"
    textColor: "{colors.ink}"
    typography: "{typography.mono}"
    rounded: "{rounded.square}"
    padding: "6px 4px 8px 12px"
  rule-tablet:
    backgroundColor: "{colors.stone}"
    textColor: "{colors.ink}"
    rounded: "{rounded.square}"
    padding: "18px 20px 22px"
  counter-block:
    backgroundColor: "{colors.shade}"
    textColor: "{colors.gold}"
    typography: "{typography.numeral-counter}"
    rounded: "{rounded.square}"
    padding: "4px 8px 2px"
    width: "84px"
  panel-pass:
    backgroundColor: "{colors.leaf-2}"
    textColor: "{colors.bone-2}"
    rounded: "{rounded.square}"
    padding: "22px 26px 28px"
  panel-supporter:
    backgroundColor: "transparent"
    textColor: "{colors.bone-2}"
    rounded: "{rounded.square}"
    padding: "22px 26px 28px"
  where-tag:
    backgroundColor: "{colors.ink}"
    textColor: "{colors.bone}"
    typography: "{typography.label}"
    rounded: "{rounded.square}"
    padding: "0 6px"
  date-tag:
    backgroundColor: "{colors.stone}"
    textColor: "{colors.ink}"
    typography: "{typography.label}"
    rounded: "{rounded.square}"
    padding: "0 6px"
---

# Design System: Monkey SMP

## Overview

**Creative North Star: "Canopy"**

The site sits under a pixel jungle canopy. The page is deep leaf green in stepped shades, a band of leaves hangs from the header, and the pixel monkey from the logo peers out of it on the front page. Everything else is drawn the way Minecraft and the logo draw things: blocks of flat colour with an outline, corners cut in two steps, motion that jumps in steps instead of easing. The server's hard numbers (the countdown, the prices, "Up to 4", "y 500", "20 TPS", the step numbers) are set large in the pixel display face and carry the structure of the page.

The colour code is strict and is the main way the page explains itself: leaf green is ground, bone is text, gold is action, stone is reference. A gold block is something to press. A stone block is something to read and keep (the server address, the rules, a changelog date). Density is moderate: generous section spacing (112 px), one idea per section, and body text held to a measure of about 70 characters.

The same world serves three pages. The front page (persuade) uses all of it: canopy, monkey, countdown, gallery, pricing band, rule tablets. The changelog (read) uses only the canopy, stone date tags and plain rows. The creator terms page reuses the rule tablets for its terms. Depth comes from frames, bevels and tonal steps of green, never from shadow.

**Key Characteristics:**
- Stepped green ground: five greens from shade to leaf-3, used as layers, never blended.
- Pixel frames on every object: 14 × 14 SVG `border-image` frames sliced at 6 px, two-step corners, filled at the padding box.
- Gold fill only on things you press; stone only on reference material.
- Numbers as structure, set in the pixel display face.
- Stepped motion only, and none under reduced motion. The one glide is the browser's own smooth scroll to
  an in-page link (owner's call, 29 October 2026), also off under reduced motion.
- No shadows, glows, blurs, gradients, rounded corners or pills.

## Colors

A dark, saturated jungle green ramp carries the page, with bone text, a single warm gold for actions and a grey-green stone for reference surfaces.

### Primary
- **Wordmark Gold** (gold): the fill of every button and the skip link, the countdown digits, the step numbers, links, list markers in pricing, the FAQ plus/minus, text selection and the caret. Taken from "SMP" in the wordmark.
- **Lit Gold** (gold-hi): the hover state of links and FAQ summaries, and the light top row of the gold frame.
- **Gold Bevel** (gold-bevel): the dark bottom bevel of the gold frame; when pressed, the bevel shrinks to one row.

### Secondary
- **Cobble Stone** (stone): the fill of reference surfaces: the server address plaque, the rule tablets, the creator-terms tablets and the changelog date tags. Text on it is ink.
- **Stone Light** (stone-hi) and **Stone Bevel** (stone-bevel): the top highlight row and bottom bevel of the stone frame.

### Neutral
- **Shade** (shade): the deepest green. Countdown and step-number blocks, the footer, the scrollbar track.
- **Ground** (ground): the page background.
- **Leaf** (leaf): the pricing band background and the hairline rules inside the pass panel.
- **Canopy Leaf** (leaf-2): the header band, the crown strips, the pass panel fill, ghost-button hover fill, and 2 px row dividers (FAQ, changelog, ladder).
- **Light Leaf** (leaf-3): the top highlight in leaf frames, the moss strip, the Supporter outline, the scrollbar thumb.
- **Bone** (bone): headings, strong text, nav links, the focus ring, ghost-button outline. Taken from the wordmark.
- **Warm Bone** (bone-2): body text.
- **Sage** (sage): secondary text: captions, small print, counter units, price units.
- **Ink** (ink): every outline, and text on gold and stone.
- **Ink Soft** (ink-2): secondary text on stone (the "Server address" label).

### Named Rules
**The Colour Code Rule.** Leaf is ground, bone is text, gold is action, stone is reference. A new element takes its colour from its job, not from what would look good.

**The Gold Block Rule.** A gold-filled block is always pressable (buttons, the Copy button, the skip link). Gold may also mark numbers and links as text, but nothing that cannot be pressed gets a gold fill.

**The One Solid Price Rule.** In pricing, the Server Pass is the one solid, filled panel. Optional tiers are drawn as an outline only (the line frame in light leaf), so they read as extras.

## Typography

**Display Font:** Pixelify Sans Monkey (with sans-serif). A modified Pixelify Sans, weight 700 only, self-hosted, with the 5 redrawn so it no longer reads as an S.
**Body Font:** Atkinson Hyperlegible Next (with sans-serif), variable 200 to 800, self-hosted.
**Label/Mono Font:** Atkinson Hyperlegible Mono (with monospace), for the server address, commands and in-game text.

**Character:** A blocky pixel face in the logo's spirit for headings and numbers, against a hyperlegible sans for everything people have to read, so the world shows in the headings without costing young readers any legibility.

### Hierarchy
- **Display** (700, clamp(2.5rem, 5vw, 4.5rem), 1.04): the h1 hook on each page. Bone, balanced wrapping.
- **Headline** (700, clamp(2.1rem, 4.2vw, 3.4rem), 1.04): section h2s.
- **Title** (700, 1.3rem, 1.2): h3s for features, steps, rules, terms. Grows to 1.5rem in the changelog and 1.6rem in pricing panels and the launch label.
- **Numerals** (display face 700, line-height 1): the price at clamp(3.5rem, 7vw, 5rem); countdown digits at 2.75rem (2.25rem on phones) with tabular figures; step numbers at 2.5rem; feature figures at 2.25rem; tier and ladder names at 1.25rem.
- **Lede** (400, 1.2rem): the paragraph under the hook. 1.125rem on phones and for section notes.
- **Body** (400, 1.0625rem, 1.6): everything else, held to a 32em measure (about 70 characters).
- **Small** (400, 0.95rem): sage small print and captions.
- **Label** (700, 0.8125rem, 1.5): the "where it was taken" tags on screenshots and the "optional" tag. Changelog date tags use 0.875rem.
- **Mono** (500, 0.94em, 1.3): inline code and commands in bone; the address on the plaque at 1.25rem, weight 600, in ink.

### Named Rules
**The Numbers Lead Rule.** Where a feature has a hard number, the number goes first, in the display face, as a run-in above its heading. Features without a number simply start with the heading; never invent a number to fill the slot.

**The One Weight Rule.** The display face is only ever set at 700. No uppercase transforms and no added letter-spacing anywhere; the pixel face carries its own character.

## Layout

Content sits between gutters of max(16px, (100% − 76rem) / 2), so the page centres at 76rem and keeps at least 16 px of edge on a phone. Sections are separated by space and colour, not boxes: 112 px top and bottom (72 px under 760 px), with the pricing band at 128 px top (88 px on phones) and the footer at 112/64.

The front-page hero is a two-column grid: the hook across the top, the lede beside the launch countdown, then the address plaque with the two buttons, then the trailer at the fold. Under 760 px it becomes one column and reorders to hook, launch, ways in, lede, trailer, so the countdown, the address and both buttons fit on the first phone screen. The address then takes its own full-width line so it never breaks mid-name.

Recurring grids: features in two columns beside the section heading (1 : 2.6); a six-column gallery whose first shot spans four columns and two rows; three join steps; two pricing panels (1.15 : 1); rule tablets as CSS columns (3 × 19rem, 20 px gaps) so each tablet is as tall as its rule; creator terms as a two-column grid with the first term full width; FAQ in two columns. Everything goes to one column at 960 px (world, plans, steps) or 760 px (features, FAQ, gallery, terms). The changelog is a single 32em column; from 960 px the date tags move into a 10rem rail on the left.

Breakpoints: 960 px, 760 px and 380 px (max-width), plus a 960 px min-width rail on the changelog.

## Elevation & Depth

There are no shadows in this system. Depth comes from three things: the tonal steps of green (shade under ground under leaf under leaf-2), the one-row bevels drawn into the frames (a lighter top row and a darker bottom row on gold, stone and leaf frames), and overlap: the canopy fringe and the monkey hang over the section below, and the moss strip sits 4 px above a tablet's top edge.

### Named Rules
**The No Shadow Rule.** Nothing casts a shadow, glows or blurs: no `box-shadow`, no `text-shadow`, no `filter: blur`, no backdrop blur. A raised object is a framed block with a bevel; a pressed one moves down 2 px onto a shorter bevel.

**The Stepped Not Smooth Rule.** Colour changes in steps, never as a gradient: on surfaces, on text and in the art. The canopy, the moss and the frames are drawn pixel by pixel with crisp edges.

## Shapes

There are no rounded corners. Every corner is a two-step pixel stair. Framed objects get it from the 14 × 14 SVG frames (2 px pixels, sliced at 6, drawn at 6 px with `fill` so the centre colour fills the padding box). Pictures get the same shape from a clip path: a 4 px two-step stair on the outer edge and a 2 px stair on the picture inside a 2 px ink outline. Pixel art (logo, monkey, kit images) is rendered `pixelated`, at whole-number scales.

The frame family: gold (with hover and pressed variants), bone outline (with a leaf-filled hover), stone, leaf, shade, ink, and line (light-leaf outline, no fill). Two horizontal motifs repeat the leaf edge: the canopy fringe (a 256 × 48 px tile, 192 × 36 px on phones) hung under the header and from the top of crowned sections (the pricing band and the footer), and the moss strip (32 × 8 px) along the top of each stone tablet.

## Components

### Buttons
Chunky gold blocks that press down a pixel.
- **Shape:** gold frame with ink outline and two-step corners, no radius; 56 px tall minimum, 18 px side padding inside the 6 px frame.
- **Primary:** gold fill, ink text, body face 700 at 1.0625rem. Used for "Get a pass", the Copy button on the plaque (48 px tall there, 44 px on phones) and the skip link.
- **Hover / Focus:** hover swaps to a brighter gold frame; pressing swaps to a frame with a one-row bevel and moves the button down 2 px with no transition. Focus is a 2 px bone outline at 3 px offset (ink on stone surfaces).
- **Ghost:** bone outline frame, no fill, bone text ("Join the Discord", "Support the server"). Hover fills it with canopy leaf. For secondary actions only: beside a gold button, or as the one action on the optional Supporter tier.

### Chips / Tags
- **Where tag:** ink block with bone label text, pinned 12 px into the top-left of every screenshot to say where it was taken (Overworld, The Nether, The End). The same ink block marks "optional" beside the Supporter heading.
- **Date tag:** stone block with ink label text, the date of each changelog entry.

### Cards / Containers
- **Corner Style:** two-step pixel corners from the frames; no radius.
- **Background:** pass panel in canopy leaf on the leaf pricing band; Supporter panel unfilled with a light-leaf line frame; tablets in stone.
- **Shadow Strategy:** none (see Elevation & Depth).
- **Border:** the 6 px frame image; inner dividers are 2 px solid leaf lines.
- **Internal Padding:** panels 22/26/28 px (18/18/24 on phones); tablets 18/20/22 px.

### Address plaque
A stone block holding the "Server address" label in ink-soft, the address in mono at 1.25rem, and the gold Copy button spanning both rows on the right. On phones the address drops to its own full-width line.

### Countdown
Three shade blocks with ink-framed edges, each holding two gold digits in the display face, with a sage unit label below. When a digit changes it drops in from above in four steps over 320 ms, the hours and minutes delayed by 80 ms and 160 ms. Under reduced motion the digits just change.

### Server status
A shade block, the countdown's colour, under the ways in on the front page: three cells (Server, Next, Border),
each a sage label over a bone value and a sage line under it, in a row (one column on phones). A 10 px square
beside "Server" is lit sage while the server is online, a hollow sage outline while it is offline, and leaf
otherwise. Every state, the quiet fallback included, fills the same two lines a cell, so nothing moves when the
status arrives. The guide hub has the same status as one line under its lede.

### Placed blocks
The countdown's move, on scroll. The blocks of a list marked `data-place` (the gallery, the steps, the plans,
the rules, the kit, the changes, the week) that start below the fold wait out of sight, then drop 18 px into
place in three steps over 240 ms as they come into view, 60 ms apart, never more than 300 ms behind the first.
Blocks on screen at load never move. Under reduced motion, without JavaScript and in print, everything is simply there.

### Rule tablets
Stone blocks with an ink title in the display face, ink body text and ink links, a moss strip along the top. On the front page they flow in columns; on the creator page they sit in a two-column grid with the first one across the top.

### Screenshots
A 2 px ink outline clipped to the stair shape, the image 16:9 and covering, a where tag in the corner, and a sage caption under it. The trailer uses the same frame.

### Navigation
The header is a canopy-leaf band with the logo (48 px tall, 32 px on phones) on the left and bone, bold, underline-free links on the right; hover underlines them 6 px below the text. The canopy fringe hangs from its bottom edge. On phones the links wrap under the logo with tighter padding.

### Questions (FAQ)
Rows separated by 2 px canopy-leaf lines. The summary is bone body text at 1.125rem, 700, with a 12 px gold pixel plus on the right that becomes a minus when open; hover turns the summary lit gold.

## Do's and Don'ts

### Do:
- **Do** frame every new object with one of the existing pixel frames at 6 px (`border-image: <frame> 6 fill / 6px` on a 6 px transparent border, background clipped to the padding box).
- **Do** pick colour by job: gold fill for something pressable, stone for reference, leaf for ground, bone for text.
- **Do** set hard numbers in the display face and let them lead their item.
- **Do** tag every screenshot with where it was taken, and clip it to the stair shape inside a 2 px ink outline.
- **Do** use `steps()` timing for any motion, and turn it off under `prefers-reduced-motion`.
- **Do** keep body text at 32em or narrower, in Atkinson Hyperlegible Next.
- **Do** render pixel art with `image-rendering: pixelated` at whole-number scales.

### Don't:
- **Don't** add shadows of any kind, glows, blurs or backdrop blur.
- **Don't** use gradients, on surfaces or on text.
- **Don't** round corners or use pill shapes.
- **Don't** give a gold fill to anything that isn't an action, or use the ghost button for the main action of a section.
- **Don't** draw a second solid pricing block; optional tiers stay an outline.
- **Don't** ease or glide: no transitions on buttons, no fades, nothing that slides in from the side. Smooth
  scrolling to in-page links is the one exception.
- **Don't** set the display face at any weight but 700, transform it to uppercase or add letter-spacing.
- **Don't** put the moss strip or the canopy fringe on everything: moss tops stone tablets only; the fringe hangs from the header and from crowned sections only (pricing and the footer).
