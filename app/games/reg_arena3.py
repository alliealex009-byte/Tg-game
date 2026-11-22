from .bluff import BluffGame
from .cricket import CricketGame

GAMES = {"cricket": CricketGame, "bluff": BluffGame}
INFO = {
    "cricket": {"title": "Hand Cricket", "emoji": "🏏", "min": 2, "max": 2, "shuffle": True, "cmd": "playcricket", "cat": "Classic", "new": True, "turn": 10},
    "bluff": {"title": "Bluff (Cheat)", "emoji": "🃏", "min": 3, "max": 6, "shuffle": True, "cmd": "playbluff", "cat": "Cards", "new": True, "turn": 25},
}
