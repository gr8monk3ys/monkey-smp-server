// Run with `bun test`. The live-pack list (site/live-packs.json) and the "not running now" notes made from it.
import assert from "node:assert/strict";
import { test } from "node:test";
import { fromAny } from "@total-typescript/shoehorn";
import list from "@live-packs";
import { NAMES, notRunning, offText, type Pack, running, sayList } from "./live";

const packs = fromAny<Pack[], string[]>(Object.keys(list.packs));

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
  const [first, second, third] = off;
  if (first && second && third) {
    const text = offText([first, second, third]);
    assert.equal(text, `Not running on the server right now: ${NAMES[first]}; ${NAMES[second]}; and ${NAMES[third]}.`);
  }
  if (first) assert.equal(offText([first]), `Not running on the server right now: ${NAMES[first]}.`);
});

test("a pack coming back is said apart, and still doesn't run", () => {
  const returning = packs.filter((pack) => list.packs[pack] === "returning");
  for (const pack of returning) assert.equal(running(pack), false);
  const off = packs.filter((pack) => list.packs[pack] === "off");
  const [offPack] = off;
  const [back] = returning;
  if (offPack && back) {
    assert.equal(offText([offPack, back]), `Not running on the server right now: ${NAMES[offPack]}. `
      + `Coming back this season, not running yet: ${NAMES[back]}.`);
  }
});
