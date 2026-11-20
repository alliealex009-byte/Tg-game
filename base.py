"""Interface every game engine implements. Engines are pure logic: no I/O, no asyncio."""
from __future__ import annotations


class GameError(Exception):
    """A user-facing rule violation (shown as a toast in the mini app)."""


class BaseGame:
    name = ""
    min_players = 2
    max_players = 2

    players: list
    winner = None
    finished = False
    draw = False

    def current(self):
        """uid whose turn it is, or None when the game is over."""
        raise NotImplementedError

    def handle(self, uid: int, msg: dict) -> None:
        """Apply a player action. Raise GameError if it is illegal."""
        raise NotImplementedError

    def auto_play(self) -> None:
        """Play one step for the current player (timeouts, AFK players and bots)."""
        raise NotImplementedError

    def remove_player(self, uid: int) -> None:
        """Player left or was kicked. Must finish the game if it can no longer continue."""
        raise NotImplementedError

    def public_state(self) -> dict:
        raise NotImplementedError

    winners = None  # optional list of uids for multi-winner games (team games, Mafia...)

    def view(self, uid: int) -> dict:
        """State as seen by one player. Hidden-information games override this; default is public."""
        return self.public_state()
