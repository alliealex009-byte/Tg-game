from .bluff import BluffGame
from .duel import CoinDuelGame, DiceDuelGame

GAMES = {"bluff": BluffGame, "coinduel": CoinDuelGame, "diceduel": DiceDuelGame}
INFO = {
    "bluff": {"title": "Bluff (Cheat)", "emoji": "🃏", "min": 3, "max": 6, "shuffle": True, "cmd": "playbluff", "cat": "Cards", "new": True, "turn": 25},
    "coinduel": {"title": "Coin Flip Duel", "emoji": "🪙", "min": 2, "max": 2, "shuffle": True, "cmd": "playflip", "cat": "Casino", "new": True, "turn": 12},
    "diceduel": {"title": "Dice Duel", "emoji": "🎲", "min": 2, "max": 2, "shuffle": True, "cmd": "playdice", "cat": "Casino", "new": True, "turn": 12},
}
