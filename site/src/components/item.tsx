/** Item sprites for the front page's features: each sits in a slot like an inventory's, drawn on a 12 x 12 grid
 * in the site's own colours. A sprite is twelve rows of twelve characters; each character is a colour (PAINT) or
 * `.` for nothing. They are decoration: the heading beside each one says what it is. */

const PAINT: Record<string, string> = {
  o: "#1a1f23", // ink
  b: "#f9f8f5", // bone
  B: "#e2dcce", // bone-2
  g: "#e8b23a", // gold
  G: "#c98f1f", // gold, dark side
  s: "#b6bcad", // stone
  S: "#959b8e", // stone, dark side
  l: "#2b7a4b", // leaf
  L: "#b3dcbf", // sage
  w: "#9c6334", // wood, from the monkey
  W: "#7a4a26",
};

const SPRITES = {
  banner: [
    ".WWWWWWWWWW.",
    "..gggggggg..",
    "..gggbbggg..",
    "..ggbbbbgg..",
    "..gbbggbbg..",
    "..gbbggbbg..",
    "..ggbbbbgg..",
    "..gggbbggG..",
    "..ggggggGG..",
    "..ggG..gGG..",
    "..gG....GG..",
    "..G......G..",
  ],
  keep: [
    "ss.ss..ss.ss",
    "ss.ss..ss.ss",
    "ssssssssssss",
    "sSssssssssSS",
    ".sssSssssSS.",
    ".ssssssssSS.",
    ".sSsssssSSS.",
    ".ssssoosSSS.",
    ".sssooooSSS.",
    ".sssooooSSS.",
    "ssssooooSSSS",
    "SSSSSSSSSSSS",
  ],
  map: [
    "bbbbbbbbbbbB",
    "bllbbbbbLLbB",
    "blllbbbLLLbB",
    "bllbbbbbLbbB",
    "bbbbggbbbbbB",
    "bbbgbbgbblbB",
    "bbbbbbgblllB",
    "bLLbbgbbllbB",
    "bLLLbbbbbbbB",
    "bbLbbgbbbbbB",
    "bbbbbbbbbbbB",
    "BBBBBBBBBBBB",
  ],
  clock: [
    "...gggggg...",
    "..gbbbbbbG..",
    ".gbbbbobbbG.",
    "gbbbbbobbbbG",
    "gbbbbbobbbbG",
    "gbbbbbobbbbG",
    "gbbbbboooobG",
    "gbbbbbbbbbbG",
    "gbbbbbbbbbbG",
    ".gbbbbbbbbG.",
    "..gbbbbbbG..",
    "...GGGGGG...",
  ],
  sword: [
    ".........bbb",
    "........bbBb",
    ".......bbBb.",
    "......bbBb..",
    ".....bbBb...",
    "W...bbBb....",
    "WW.bbBb.....",
    ".WWbBb......",
    "..WWW.......",
    ".wWWWW......",
    "ww..WW......",
    "w...........",
  ],
  voice: [
    ".bbbbbbbbbb.",
    "bbbbbbbbbbbB",
    "bbbbbbbbbbbB",
    "bboobboobbbB",
    "bboobboobbbB",
    "bbbbbbbbbbbB",
    "bbbbbbbbbbbB",
    ".BBbbbBBBBB.",
    "...bbB......",
    "...bB.......",
    "...B........",
    "............",
  ],
};

export type ItemName = keyof typeof SPRITES;

export function Item({ name }: { name: ItemName }) {
  return (
    <span className="slot" aria-hidden="true">
      <svg viewBox="0 0 12 12" shapeRendering="crispEdges">
        {SPRITES[name].flatMap((row, y) => [...row].map((c, x) =>
          c === "." ? null : <rect key={`${x}-${y}`} x={x} y={y} width={1} height={1} fill={PAINT[c]} />))}
      </svg>
    </span>
  );
}
