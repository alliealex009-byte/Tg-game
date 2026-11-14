"""Game registry. To add a game: write an engine (see tictactoe.py), register it here,
add a renderer in webapp/games.js, and a /play command in app/bot.py."""
from .carrom import CarromGame
from .connect4 import ConnectFourGame
from .ludo import LudoGame
from .memory import MemoryGame
from .rps import RPSGame
from .snakes import SnakesGame
from .tictactoe import TicTacToeGame

GAMES = {
    "ludo": LudoGame,
    "snakes": SnakesGame,
    "carrom": CarromGame,
    "connect4": ConnectFourGame,
    "tictactoe": TicTacToeGame,
    "rps": RPSGame,
    "memory": MemoryGame,
}

# shuffle: randomise who goes first / which colour you get
GAME_INFO = {
    "ludo": {"title": "Ludo", "emoji": "🎲", "min": 2, "max": 4, "shuffle": False, "cmd": "playludo"},
    "snakes": {"title": "Snakes & Ladders", "emoji": "🐍", "min": 2, "max": 4, "shuffle": True, "cmd": "playsnake"},
    "carrom": {"title": "Carrom", "emoji": "🎯", "min": 2, "max": 2, "shuffle": True, "cmd": "playcarrom"},
    "connect4": {"title": "Connect Four", "emoji": "🔴", "min": 2, "max": 2, "shuffle": True, "cmd": "playc4"},
    "tictactoe": {"title": "Tic-Tac-Toe", "emoji": "❌", "min": 2, "max": 2, "shuffle": True, "cmd": "playttt"},
    "rps": {"title": "Rock Paper Scissors", "emoji": "✊", "min": 2, "max": 2, "shuffle": True, "cmd": "playrps"},
    "memory": {"title": "Memory Match", "emoji": "🧠", "min": 2, "max": 2, "shuffle": True, "cmd": "playmemory"},
}
