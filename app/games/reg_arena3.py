from .bluff import BluffGame
from .cricket import CricketGame
from .duel import CoinDuelGame, DiceDuelGame

GAMES = {"cricket": CricketGame, "bluff": BluffGame, "coinduel": CoinDuelGame, "diceduel": DiceDuelGame}
INFO = {
    "cricket": {"title": "Hand Cricket", "emoji": "🏏", "min": 2, "max": 2, "shuffle": True, "cmd": "playcricket", "cat": "Classic", "new": True, "turn": 10},
    "bluff": {"title": "Bluff (Cheat)", "emoji": "🃏", "min": 3, "max": 6, "shuffle": True, "cmd": "playbluff", "cat": "Cards", "new": True, "turn": 25},
    "coinduel": {"title": "Coin Flip Duel", "emoji": "🪙", "min": 2, "max": 2, "shuffle": True, "cmd": "playflip", "cat": "Casino", "new": True, "turn": 12},
    "diceduel": {"title": "Dice Duel", "emoji": "🎲", "min": 2, "max": 2, "shuffle": True, "cmd": "playdice", "cat": "Casino", "new": True, "turn": 12},
}
