/* Ludo board geometry on a 15x15 grid. Must match app/games/ludo.py (START, SAFE, positions). */
(function (root) {
  "use strict";
  const PATH = [];
  const seg = (r, c, dr, dc, n) => { for (let i = 0; i < n; i++) PATH.push([r + dr * i, c + dc * i]); };
  seg(6, 1, 0, 1, 5);    // 0-4    red arm, heading right
  seg(5, 6, -1, 0, 6);   // 5-10   up the top arm (left column)
  seg(0, 7, 0, 1, 2);    // 11-12  across the top
  seg(1, 8, 1, 0, 5);    // 13-17  down the top arm (right column)
  seg(6, 9, 0, 1, 6);    // 18-23  right arm (top row)
  seg(7, 14, 1, 0, 2);   // 24-25  across the right edge
  seg(8, 13, 0, -1, 5);  // 26-30  right arm (bottom row), heading left
  seg(9, 8, 1, 0, 6);    // 31-36  down the bottom arm (right column)
  seg(14, 7, 0, -1, 2);  // 37-38  across the bottom
  seg(13, 6, -1, 0, 5);  // 39-43  up the bottom arm (left column)
  seg(8, 5, 0, -1, 6);   // 44-49  left arm (bottom row), heading left
  seg(7, 0, -1, 0, 2);   // 50-51  across the left edge

  const START = [0, 13, 26, 39];
  const SAFE = new Set([0, 8, 13, 21, 26, 34, 39, 47]);
  // seats: 0 red (top-left), 1 green (top-right), 2 yellow (bottom-right), 3 blue (bottom-left)
  const HOMECOL = [
    [[7, 1], [7, 2], [7, 3], [7, 4], [7, 5]],
    [[1, 7], [2, 7], [3, 7], [4, 7], [5, 7]],
    [[7, 13], [7, 12], [7, 11], [7, 10], [7, 9]],
    [[13, 7], [12, 7], [11, 7], [10, 7], [9, 7]],
  ];
  const FINISH = [[7, 6], [6, 7], [7, 8], [8, 7]];
  const YARD_ORIGIN = [[0, 0], [0, 9], [9, 9], [9, 0]];
  const YARD_SLOTS = [[1.5, 1.5], [1.5, 3.5], [3.5, 1.5], [3.5, 3.5]];

  /** Top-left cell coordinate [row, col] (may be fractional) of a token. */
  function tokenCell(seat, idx, pos) {
    if (pos < 0) {
      const o = YARD_ORIGIN[seat], s = YARD_SLOTS[idx];
      return [o[0] + s[0], o[1] + s[1]];
    }
    if (pos <= 50) return PATH[(START[seat] + pos) % 52];
    if (pos <= 55) return HOMECOL[seat][pos - 51];
    return FINISH[seat];
  }

  const api = { PATH, START, SAFE, HOMECOL, FINISH, YARD_ORIGIN, YARD_SLOTS, tokenCell };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.LudoBoard = api;
})(typeof window !== "undefined" ? window : globalThis);
