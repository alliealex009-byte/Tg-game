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


# Extra games live in reg_<group>.py files, each exposing GAMES and INFO dicts.
import importlib  # noqa: E402

import os  # noqa: E402

_WEB = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "webapp")
for _grp in ("boards", "cards", "dice", "party", "action", "arena", "arena2", "arena3"):
    # a group is only offered once its mini-app renderer exists (stub files are < 500 bytes)
    _js = os.path.join(_WEB, f"g_{_grp}.js")
    if not os.path.exists(_js) or os.path.getsize(_js) < 500:
        continue
    try:
        _m = importlib.import_module(f".reg_{_grp}", __name__)
    except ModuleNotFoundError as _e:  # group not written yet
        if _e.name and _e.name.endswith(f"reg_{_grp}"):
            continue
        raise
    GAMES.update(_m.GAMES)
    GAME_INFO.update(_m.INFO)

# categories for the home screen / bot menu: Board, Cards, Party, Casino, Brain, Classic
for _k in ("ludo", "snakes", "carrom", "connect4", "tictactoe", "rps", "memory"):
    GAME_INFO[_k].setdefault("cat", "Classic")

# Curated lineup: the classics people actually play. Everything else keeps working (engines, /play commands,
# tests) but is hidden from menus unless SHOW_ALL_GAMES=1.
FEATURED = [
    "ludo", "uno", "carrom", "chess", "snakes", "checkers", "connect4", "tictactoe", "dominoes", "battleship",
    "dots", "hangman", "bingo", "teenpatti", "mafia", "scribble", "trivia", "tank", "race", "memory", "crazy8", "cricket", "bluff", "coinduel", "diceduel",
]
LISTED = (
    dict(GAME_INFO)
    if os.environ.get("SHOW_ALL_GAMES", "").strip().lower() in ("1", "true", "yes")
    else {k: GAME_INFO[k] for k in FEATURED if k in GAME_INFO}
)
