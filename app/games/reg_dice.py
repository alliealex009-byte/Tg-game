from .bingo import BingoGame
from .dots import DotsGame
from .liarsdice import LiarsDiceGame
from .mancala import MancalaGame
from .nim import NimGame
from .pig import PigGame

GAMES = {"pig": PigGame, "liarsdice": LiarsDiceGame, "bingo": BingoGame, "nim": NimGame, "mancala": MancalaGame, "dots": DotsGame}

INFO = {
    "pig": {"title": "Pig", "emoji": "🐷", "min": 2, "max": 4, "shuffle": True, "cmd": "playpig", "cat": "Casino", "new": True, "turn": 25},
    "liarsdice": {"title": "Liar's Dice", "emoji": "🎲", "min": 2, "max": 5, "shuffle": True, "cmd": "playliar", "cat": "Casino", "new": True, "turn": 30},
    "bingo": {"title": "Bingo", "emoji": "🎱", "min": 2, "max": 6, "shuffle": False, "cmd": "playbingo", "cat": "Party", "new": True, "turn": 30},
    "nim": {"title": "Nim", "emoji": "🪵", "min": 2, "max": 2, "shuffle": True, "cmd": "playnim", "cat": "Brain", "new": True, "turn": 25},
    "mancala": {"title": "Mancala", "emoji": "🥜", "min": 2, "max": 2, "shuffle": True, "cmd": "playmancala", "cat": "Brain", "new": True, "turn": 30},
    "dots": {"title": "Dots & Boxes", "emoji": "🔲", "min": 2, "max": 2, "shuffle": True, "cmd": "playdots", "cat": "Brain", "new": True, "turn": 25},
}
