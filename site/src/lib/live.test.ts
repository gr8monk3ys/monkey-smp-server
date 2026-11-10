// Run with `bun test`. The live-pack list (site/live-packs.json) and the "not running now" notes made from it.
import assert from "node:assert/strict";
import { test } from "node:test";
import list from "@live-packs";
import { NAMES, notRunning, offText, type Pack, running, sayList } from "./live";

const packs = Object.keys(list.packs) as Pack[];

test("only a pack that is on runs; off and unknown don't", () => {
  for (const pack of packs) assert.equal(running(pack), list.packs[pack] === "on");
  assert.deepEqual(notRunning(packs), packs.filter((pack) => list.packs[pack] !== "on"));
});

test("every pack in the list has a name for the notes", () => {
  assert.deepEqual(Object.keys(NAMES).sort(), [...packs].sort());
});

test("lists read as English", () => {
  assert.equal(sayList([]), "");
  assert.equal(sayList(["a"]), "a");
  assert.equal(sayList(["a", "b"]), "a and b");
  assert.equal(sayList(["a", "b", "c"]), "a, b and c");
});

test("a note names what isn't running, and is empty when all of it is", () => {
  const on = packs.filter(running);
  const off = packs.filter((pack) => list.packs[pack] === "off");
  if (on.length) assert.equal(offText(on), "");
  if (off.length >= 3) {
    const text = offText(off.slice(0, 3));
    assert.equal(text, `Not running on the server right now: ${NAMES[off[0]]}; ${NAMES[off[1]]}; and ${NAMES[off[2]]}.`);
  }
  if (off.length) assert.equal(offText([off[0]]), `Not running on the server right now: ${NAMES[off[0]]}.`);
});

test("a pack coming back is said apart, and still doesn't run", () => {
  const returning = packs.filter((pack) => list.packs[pack] === "returning");
  for (const pack of returning) assert.equal(running(pack), false);
  const off = packs.filter((pack) => list.packs[pack] === "off");
  if (returning.length && off.length) {
    assert.equal(offText([off[0], returning[0]]), `Not running on the server right now: ${NAMES[off[0]]}. `
      + `Coming back this season, not running yet: ${NAMES[returning[0]]}.`);
  }
});
