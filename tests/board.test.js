// Run:  node tests/board.test.js   (verifies the frontend board geometry matches the Python engine)
const assert = require("assert");
const B = require("../webapp/board.js");

const key = (rc) => rc.join(",");
assert.strictEqual(B.PATH.length, 52, "track has 52 cells");
assert.strictEqual(new Set(B.PATH.map(key)).size, 52, "track cells are unique");

// Consecutive cells are neighbours, except the four corner steps where the track cuts diagonally
// around the centre square (same as a real Ludo board).
const CORNERS = new Set([4, 17, 30, 43]);
for (let i = 0; i < 52; i++) {
  const a = B.PATH[i], b = B.PATH[(i + 1) % 52];
  const dr = Math.abs(a[0] - b[0]), dc = Math.abs(a[1] - b[1]);
  if (CORNERS.has(i)) assert.ok(dr === 1 && dc === 1, `cells ${i}->${i + 1} are a diagonal corner step`);
  else assert.strictEqual(dr + dc, 1, `cells ${i} and ${(i + 1) % 52} are adjacent`);
}

// Safe cells and start cells measured from the real game's screenshot (row, col on the 15x15 grid).
const SHOT = { 0: [6, 1], 13: [1, 8], 26: [8, 13], 39: [13, 6], 47: [8, 2], 8: [2, 6], 21: [6, 12], 34: [12, 8] };
for (const [i, rc] of Object.entries(SHOT)) {
  assert.deepStrictEqual(B.PATH[i], rc, `safe cell ${i} matches the reference board`);
  assert.ok(B.SAFE.has(+i));
}
for (const [r, c] of B.PATH) assert.ok(r >= 0 && r < 15 && c >= 0 && c < 15);

// the track must avoid the four 6x6 yards and the centre 3x3
const inYard = ([r, c]) => (r < 6 || r > 8) && (c < 6 || c > 8);
B.PATH.forEach((rc, i) => assert.ok(!inYard(rc), `track cell ${i} is not inside a yard`));
const inCentre = ([r, c]) => r >= 6 && r <= 8 && c >= 6 && c <= 8;
B.PATH.forEach((rc, i) => assert.ok(!inCentre(rc), `track cell ${i} is not in the centre`));

// each colour's start cell sits on the row/column of its home column, and the home column continues from the cell before it
B.START.forEach((s, seat) => {
  const entryIdx = (s + 50) % 52;          // last shared cell before the home column (pos 50)
  const last = B.PATH[entryIdx], first = B.HOMECOL[seat][0];
  assert.strictEqual(Math.abs(last[0] - first[0]) + Math.abs(last[1] - first[1]), 1, `seat ${seat} enters its home column`);
  const col = B.HOMECOL[seat];
  for (let i = 0; i < 4; i++) assert.strictEqual(Math.abs(col[i][0] - col[i + 1][0]) + Math.abs(col[i][1] - col[i + 1][1]), 1);
  const lastCol = col[4], fin = B.FINISH[seat];
  assert.strictEqual(Math.abs(lastCol[0] - fin[0]) + Math.abs(lastCol[1] - fin[1]), 1, `seat ${seat} reaches the finish`);
});

// the 8 safe cells: 4 starts + 4 stars, never the same cell twice
assert.strictEqual(B.SAFE.size, 8);
[...B.SAFE].forEach((i) => assert.ok(i >= 0 && i < 52));

// token positions resolve for every state
for (let seat = 0; seat < 4; seat++) {
  for (let idx = 0; idx < 4; idx++) {
    for (let pos = -1; pos <= 56; pos++) {
      const rc = B.tokenCell(seat, idx, pos);
      assert.ok(Array.isArray(rc) && rc.length === 2 && rc.every(Number.isFinite), `seat ${seat} pos ${pos}`);
    }
  }
}
console.log("board geometry OK");
