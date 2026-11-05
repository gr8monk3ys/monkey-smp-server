// Run with `bun test` (site/package.json's "test"). What the standings page may show: a file whole and fresh, or
// nothing.
import assert from "node:assert/strict";
import { test } from "node:test";
import { afterAnswer, cleanName, freshness, HIDDEN, NAME_LENGTH, parseStandings, roman } from "./standings";

const rows = [{ rank: 1, name: "Red Wolves", points: 87 }, { rank: 2, name: "Blue Herons", points: 60 }];
const good = () => ({
  version: 1, checked: "2026-11-15T02:00:00Z", season: 1, week_closes: "2026-11-16T03:00:00Z", factions: rows,
  last_week: { closed: "2026-11-09T03:00:00Z", factions: rows },
});
const many = (n: number) => Array.from({ length: n }, () => ({ rank: 1, name: "A", points: 1 }));

test("the file in the contract is read whole", () => {
  const file = parseStandings(good());
  assert.ok(file);
  assert.equal(file.season, 1);
  assert.equal(file.checked, Date.parse("2026-11-15T02:00:00Z"));
  assert.equal(file.closes, Date.parse("2026-11-16T03:00:00Z"));
  assert.deepEqual(file.factions, rows);
  assert.deepEqual(file.last, { closed: Date.parse("2026-11-09T03:00:00Z"), factions: rows });
});

test("last_week is null until a week has closed, and may be left out", () => {
  assert.equal(parseStandings({ ...good(), last_week: null })?.last, null);
  assert.equal(parseStandings({ ...good(), last_week: undefined })?.last, null);
});

test("week_closes is null once the season's last week has closed", () => {
  assert.equal(parseStandings({ ...good(), week_closes: null })?.closes, null);
});

test("an empty table is a table: nobody has points yet", () => {
  assert.deepEqual(parseStandings({ ...good(), factions: [] })?.factions, []);
});

test("ties share a rank", () => {
  const tied = [{ rank: 1, name: "A", points: 50 }, { rank: 1, name: "B", points: 50 }, { rank: 3, name: "C", points: 9 }];
  assert.equal(parseStandings({ ...good(), factions: tied })?.factions.length, 3);
});

test("equal points can rank apart: the tie-breaks are Cup points, then kills", () => {
  const apart = [{ rank: 1, name: "A", points: 50 }, { rank: 2, name: "B", points: 50 }];
  assert.equal(parseStandings({ ...good(), factions: apart })?.factions.length, 2);
});

test("a null name becomes A faction", () => {
  const hidden = [{ rank: 1, name: null, points: 5 }];
  assert.equal(parseStandings({ ...good(), factions: hidden })?.factions[0].name, "A faction");
  assert.equal(cleanName(null), HIDDEN);
});

const row = (change: object) => [{ rank: 1, name: "A", points: 1, ...change }];
const bad: [string, unknown][] = [
  ["not an object", "hello"], ["null", null], ["an array", []], ["a number", 3],
  ["another version", { ...good(), version: 2 }], ["no version", { ...good(), version: undefined }],
  ["no checked time", { ...good(), checked: undefined }],
  ["a checked time that is no time", { ...good(), checked: "soon" }],
  ["a date with no time", { ...good(), checked: "2026-11-15" }],
  ["a time with no offset", { ...good(), checked: "2026-11-15T02:00:00" }],
  ["a checked number", { ...good(), checked: 1763172000 }],
  ["no week_closes", { ...good(), week_closes: undefined }],
  ["a week_closes that is no time", { ...good(), week_closes: "soon" }],
  ["no season", { ...good(), season: undefined }],
  ["season 0", { ...good(), season: 0 }], ["season 1.5", { ...good(), season: 1.5 }],
  ["a season in words", { ...good(), season: "1" }],
  ["factions missing", { ...good(), factions: undefined }], ["factions an object", { ...good(), factions: {} }],
  ["a row that is a string", { ...good(), factions: ["Red Wolves"] }],
  ["a row that is null", { ...good(), factions: [null] }],
  ["a rank of 0", { ...good(), factions: row({ rank: 0 }) }],
  ["a rank in words", { ...good(), factions: row({ rank: "1" }) }],
  ["a rank that skips ahead", { ...good(), factions: row({ rank: 4 }) }],
  ["ranks out of order", {
    ...good(), factions: [{ rank: 2, name: "A", points: 9 }, { rank: 1, name: "B", points: 9 }],
  }],
  ["points going up", {
    ...good(), factions: [{ rank: 1, name: "A", points: 1 }, { rank: 2, name: "B", points: 9 }],
  }],
  ["a shared rank with different points", {
    ...good(), factions: [{ rank: 1, name: "A", points: 9 }, { rank: 1, name: "B", points: 5 }],
  }],
  ["a rank that isn't its place after a tie", {
    ...good(),
    factions: [{ rank: 1, name: "A", points: 9 }, { rank: 1, name: "B", points: 9 }, { rank: 2, name: "C", points: 1 }],
  }],
  ["a rank that skips with no tie", {
    ...good(), factions: [{ rank: 1, name: "A", points: 9 }, { rank: 3, name: "B", points: 5 }],
  }],
  ["negative points", { ...good(), factions: row({ points: -1 }) }],
  ["points in words", { ...good(), factions: row({ points: "9" }) }],
  ["points that are not finite", { ...good(), factions: row({ points: Infinity }) }],
  ["a name that is a number", { ...good(), factions: row({ name: 7 }) }],
  ["a name that is missing", { ...good(), factions: row({ name: undefined }) }],
  ["a last_week that is a string", { ...good(), last_week: "no" }],
  ["a last_week with no close time", { ...good(), last_week: { factions: rows } }],
  ["a last_week with a bad row", {
    ...good(), last_week: { closed: "2026-11-09T03:00:00Z", factions: row({ points: null }) },
  }],
  ["more factions than a server can have", { ...good(), factions: many(101) }],
];
for (const [what, data] of bad) {
  test(`${what} is no standings: none of it is shown`, () => {
    assert.equal(parseStandings(data), null);
  });
}

test("members, players and coordinates in the file are never read", () => {
  const extra = {
    ...good(),
    factions: row({ name: "Red Wolves", points: 87, members: ["Steve"], players: ["Alex"], x: 100, z: -40 }),
    players: ["Steve"],
  };
  const file = parseStandings(extra);
  assert.deepEqual(file?.factions, [{ rank: 1, name: "Red Wolves", points: 87 }]);
  assert.ok(!JSON.stringify(file).match(/Steve|Alex|"x"/));
});

test("a file is fresh for three hours, then stale, and one from the future is not shown", () => {
  const file = parseStandings(good())!;
  const at = (minutes: number) => file.checked + minutes * 60_000;
  assert.equal(freshness(file, at(0)), "ok");
  assert.equal(freshness(file, at(179)), "ok");
  assert.equal(freshness(file, at(181)), "stale");
  assert.equal(freshness(file, at(-30)), "ok");
  assert.equal(freshness(file, at(-90)), "ahead");
});

test("after the season's last close, the final table stays up however old the file is", () => {
  const over = parseStandings({ ...good(), week_closes: null })!;
  assert.equal(freshness(over, over.checked + 100 * 24 * 60 * 60_000), "ok");
  assert.equal(freshness(over, over.checked - 90 * 60_000), "ahead");
});

test("a 5xx keeps what was shown, and any other bad answer is no standings", () => {
  const shown = parseStandings(good())!;
  const body = JSON.stringify(good());
  assert.equal(afterAnswer(shown, 502, null), shown);
  assert.equal(afterAnswer(null, 503, null), null);
  assert.equal(afterAnswer(shown, 404, null), null);
  assert.equal(afterAnswer(shown, 200, "<html>"), null);
  assert.equal(afterAnswer(shown, 200, JSON.stringify({ version: 2 })), null);
  assert.deepEqual(afterAnswer(null, 200, body), shown);
});

test("names are plain text: markup stays characters", () => {
  assert.equal(cleanName("<img src=x onerror=alert(1)>"), "<img src=x onerror=alert(1)>");
  assert.equal(cleanName("[click](https://evil.example)"), "[click](https://evil.example)");
});

test("names lose hidden and formatting characters and extra spaces", () => {
  assert.equal(cleanName("  Red ‮evlow  Wolves​ "), "Red evlow Wolves");
  assert.equal(cleanName("§cRed §lWolves"), "Red Wolves");
  assert.equal(cleanName("a\u0000b\u001fc\u007fd"), "abcd");
  assert.equal(cleanName("   "), HIDDEN);
  assert.equal(cleanName("​‮"), HIDDEN);
  assert.equal(cleanName(""), HIDDEN);
});

test("names hold up without the server's own cleaning", () => {
  assert.equal(cleanName("§\u200bcRed"), "Red");     // a hidden character can't split a code from its letter
  assert.equal(cleanName("§zRed§"), "Red");          // any code, and a sign on its own
  assert.equal(cleanName("\u00adRed\u061c\ufff9"), "Red");
  assert.equal(cleanName("Red\u{e0041}\ufe00"), "Red");
  assert.equal(cleanName("\u3164\u115f \u2800"), HIDDEN);
  assert.equal(cleanName("\u{1F468}\u200d\u{1F469}\ufe0f"), "\u{1F468}\u200d\u{1F469}\ufe0f");   // one emoji stays one
});

test("a very long name is cut, by whole characters", () => {
  const long = cleanName("W".repeat(500));
  assert.equal(Array.from(long).length, NAME_LENGTH);
  assert.ok(long.endsWith("…"));
  const emoji = cleanName("\u{1F412}".repeat(100));
  assert.equal(Array.from(emoji).length, NAME_LENGTH);
  assert.ok(!emoji.includes("�"));
  assert.equal(cleanName("W".repeat(NAME_LENGTH)), "W".repeat(NAME_LENGTH));
});

test("seasons are written in Roman numerals", () => {
  assert.deepEqual([1, 2, 3, 4, 9, 10, 14].map(roman), ["I", "II", "III", "IV", "IX", "X", "XIV"]);
});
